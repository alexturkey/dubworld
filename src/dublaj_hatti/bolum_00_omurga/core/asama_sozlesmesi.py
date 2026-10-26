from __future__ import annotations

import hashlib
import json

PIPELINE_ID = "dublaj_hatti.pipeline"
PIPELINE_VERSION = "1"

PIPELINE_STAGES: dict[str, tuple[tuple[str, int, int], ...]] = {
    "segment_sync": (
        ("video_indirme_veya_kopyalama", 2, 1),
        ("kaynak_ses_cikarma", 3, 1),
        ("demucs_vokal_ayirma", 4, 2),
        ("asr_sesi_hazirlama", 5, 1),
        ("transkripsiyon", 6, 1),
        ("forced_alignment_ve_nihai_segmentler", 7, 1),
        ("konusmaci_yonlendirme", 8, 2),
        ("ceviri", 9, 2),
        ("ses_yonlendirme", 10, 2),
        ("tts_ve_segment_sesleri", 11, 2),
        ("altyazi_hazirlama", 12, 1),
        ("video_timeline_ve_final_mux", 13, 2),
        ("arka_plan_miksi", 15, 2),
        ("final_altyazi_yakma", 16, 1),
        ("final_dogrulama_ve_meta", 17, 1),
    ),
    "full_text": (
        ("video_indirme_veya_kopyalama", 2, 1),
        ("kaynak_ses_cikarma", 3, 1),
        ("demucs_vokal_ayirma", 4, 2),
        ("asr_sesi_hazirlama", 5, 1),
        ("transkripsiyon", 6, 1),
        ("full_text_konusma_penceresi", 7, 1),
        ("full_text_ceviri", 8, 3),
        ("full_text_tek_ses_tts", 9, 1),
        ("full_text_final_altyazi_alignment", 10, 1),
        ("full_text_video_sure_uyumu_ve_final_mux", 11, 2),
        ("arka_plan_miksi", 15, 2),
        ("final_dogrulama_ve_meta", 17, 1),
    ),
}


class SelectionGraphError(ValueError):
    pass


def _contract_hash() -> str:
    encoded = json.dumps(PIPELINE_STAGES, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get_graph_identity(graph_version: str = "", graph_hash: str = "") -> dict[str, str]:
    current_hash = _contract_hash()
    if graph_version and graph_version != PIPELINE_VERSION:
        raise SelectionGraphError(f"Bilinmeyen hat surumu: {graph_version}")
    if graph_hash and graph_hash != current_hash:
        raise SelectionGraphError("Hat asama sozlesmesi degismis; checkpoint yeniden kullanilamaz")
    return {"graph_id": PIPELINE_ID, "graph_version": PIPELINE_VERSION, "graph_hash": current_hash}


def validate_runtime_graph_compatibility(graph_version: str, graph_hash: str = "", require_active_presentation: bool = False) -> dict[str, str]:
    return get_graph_identity(graph_version, graph_hash)


def pipeline_stage_registry(pipeline_kind: str, graph_version: str = "", graph_hash: str = "") -> tuple[tuple[str, int, int], ...]:
    get_graph_identity(graph_version, graph_hash)
    stages = PIPELINE_STAGES.get(str(pipeline_kind or "").strip())
    if stages is None:
        raise SelectionGraphError(f"Desteklenmeyen pipeline: {pipeline_kind}")
    return stages
