from __future__ import annotations

from typing import Any

from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.flow_modes import get_supertonic_flow_settings


def translation_flow_signature(tts_engine: str, supertonic_flow_mode: str = "") -> dict[str, Any]:
    settings = get_supertonic_flow_settings(supertonic_flow_mode) if tts_engine == "supertonic" else {}
    return {
        "candidate_count": int(settings.get("initial_candidate_count", settings.get("candidate_count")) or 1),
        "translation_group_size": int(settings.get("translation_group_size") or 0),
        "translation_prompt_mode": str(settings.get("translation_prompt_mode") or ""),
    }


def segment_translation_checkpoint_inputs(
    source_segments_hash: str,
    source_lang: str,
    target_lang: str,
    translator_engine: str,
    bridge_backend: str,
    tts_engine: str,
    tts_voice_id: str,
    tts_speed_factor: float,
    supertonic_flow_mode: str = "",
) -> dict[str, Any]:
    engine = str(tts_engine or "supertonic").strip().lower()
    return {
        "source_segments_hash": str(source_segments_hash or ""),
        "source_lang": str(source_lang or ""),
        "target_lang": str(target_lang or ""),
        "translator_engine": str(translator_engine or ""),
        "bridge_backend": str(bridge_backend or ""),
        "translation_strategy": {
            "tts_engine": engine,
            "tts_voice_id": str(tts_voice_id or ""),
            "tts_speed_factor": float(tts_speed_factor),
            **translation_flow_signature(engine, supertonic_flow_mode),
        },
    }


def normalize_segment_translation_checkpoint_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Eski düz biçimli çeviri checkpoint girdilerini `translation_strategy` biçimine çevirir (devam kopyası için)."""
    current = dict(inputs or {})
    if isinstance(current.get("translation_strategy"), dict):
        return current
    required = {"source_segments_hash", "source_lang", "target_lang", "translator_engine", "tts_engine"}
    if not required.issubset(current):
        return current
    return segment_translation_checkpoint_inputs(
        source_segments_hash=str(current.get("source_segments_hash") or ""),
        source_lang=str(current.get("source_lang") or ""),
        target_lang=str(current.get("target_lang") or ""),
        translator_engine=str(current.get("translator_engine") or ""),
        bridge_backend=str(current.get("bridge_backend") or ""),
        tts_engine=str(current.get("tts_engine") or "supertonic"),
        tts_voice_id=str(current.get("tts_voice_id") or ""),
        tts_speed_factor=float(current.get("tts_speed_factor") or 1.0),
        supertonic_flow_mode=str(current.get("supertonic_flow_mode") or ""),
    )
