from __future__ import annotations

import calendar
import hashlib
import json
import logging
import os
import re
import shutil
import socket
import threading
import time
import unicodedata
import uuid
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from dublaj_hatti.bolum_00_omurga.core.asama_sozlesmesi import (
    SelectionGraphError,
    get_graph_identity,
    validate_runtime_graph_compatibility,
)
from dublaj_hatti.bolum_00_omurga.core.asama_sozlesmesi import (
    pipeline_stage_registry as graph_pipeline_stage_registry,
)
from dublaj_hatti.bolum_00_omurga.runtime.surec_durumu import process_is_alive

PIPELINE_STATE_SCHEMA_VERSION = 1
DEFAULT_LARGE_FILE_THRESHOLD = 32 * 1024 * 1024
DEFAULT_SAMPLE_SIZE = 1024 * 1024
FULL_DIGEST_AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus"})

logger = logging.getLogger(__name__)

SEGMENT_SYNC_CHECKPOINT_STAGES = graph_pipeline_stage_registry("segment_sync")
FULL_TEXT_CHECKPOINT_STAGES = graph_pipeline_stage_registry("full_text")


class PipelineCheckpointError(RuntimeError):
    pass


class PipelineCheckpointLockedError(PipelineCheckpointError):
    pass


class GozdenGecirmeBekleniyor(Exception):  # noqa: N818 - hata değil, temiz durma işareti
    """Hata DEĞİL: aşama bitti ve checkpoint'i yazıldı; `genel.gozden_gecir` gereği hat burada temiz durur.

    İş "inceleme_bekliyor" olur (is_yonetimi); kullanıcı metni düzeltip aynı işi sonraki aşamadan sürdürür."""

    def __init__(self, stage_id: str, result_path: str = "") -> None:
        super().__init__(f"{stage_id} bitti; gözden geçirme bekleniyor")
        self.stage_id = stage_id
        self.result_path = result_path


def canonical_json_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    encoded = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    try:
        with open(temporary_path, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(5):
            try:
                os.replace(temporary_path, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise PipelineCheckpointError(f"Checkpoint UTF-8 BOM iceremez: {path}")
        value = json.loads(raw.decode("utf-8"))
    except PipelineCheckpointError:
        raise
    except Exception as exc:
        raise PipelineCheckpointError(f"Checkpoint okunamadi: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PipelineCheckpointError(f"Checkpoint kok degeri nesne olmali: {path}")
    return value


def checkpoint_stage_registry(
    pipeline_kind: str,
    graph_version: str = "",
    graph_hash: str = "",
) -> tuple[tuple[str, int, int], ...]:
    try:
        return graph_pipeline_stage_registry(
            str(pipeline_kind).strip(),
            graph_version=str(graph_version or ""),
            graph_hash=str(graph_hash or ""),
        )
    except SelectionGraphError as exc:
        raise PipelineCheckpointError(str(exc)) from exc


def stage_runtime_contract_matches(stage_id: str, inputs: dict[str, Any]) -> bool:
    if stage_id in {"altyazi_hazirlama", "full_text_final_altyazi_alignment"} and inputs.get("subtitle_mode") == "rollup":
        from dublaj_hatti.bolum_50_seslendirme.altyazili_dublaj.rollup import rollup_contract_inputs

        try:
            return inputs.get("rollup_contract") == rollup_contract_inputs()
        except (OSError, RuntimeError, ValueError):
            return False
    if stage_id == "transkripsiyon" and inputs.get("engine") == "crisperwhisper_turbo_ct2":
        from dublaj_hatti.bolum_00_omurga.runtime.crisperwhisper_turbo_ct2_runtime import RUNTIME_CONTRACT_VERSION

        return inputs.get("crisperwhisper_turbo_ct2_runtime_contract_version") == RUNTIME_CONTRACT_VERSION
    if stage_id == "transkripsiyon" and inputs.get("engine") == "moonshine_medium_streaming_en":
        from dublaj_hatti.bolum_00_omurga.runtime.moonshine_medium_streaming_runtime import (
            RUNTIME_CONTRACT_VERSION,
            moonshine_contract_inputs,
        )

        if inputs.get("moonshine_runtime_contract_version") != RUNTIME_CONTRACT_VERSION:
            return False
        try:
            current_runtime = moonshine_contract_inputs()
        except (OSError, RuntimeError, ValueError):
            return False
        return all(key in inputs and inputs[key] == value for key, value in current_runtime.items())
    if stage_id != "full_text_tek_ses_tts" and not (
        stage_id == "tts_ve_segment_sesleri" and inputs.get("tts_engine") == "supertonic"
    ):
        return True
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts import SUPERTONIC_SYNTHESIS_CONTRACT

    return inputs.get("supertonic_synthesis_contract") == SUPERTONIC_SYNTHESIS_CONTRACT


def checkpoint_resume_options(run_dir: str | Path) -> list[dict[str, Any]]:
    resolved_run_dir = Path(run_dir).resolve()
    state = _read_json(resolved_run_dir / "pipeline_state.json")
    stages = state.get("stages")
    if not isinstance(stages, dict):
        raise PipelineCheckpointError("Checkpoint stages degeri nesne olmali")
    options = []
    for stage_id, stage_order, contract_version in checkpoint_stage_registry(
        str(state.get("pipeline_kind") or ""),
        graph_version=str(state.get("selection_graph_version") or ""),
        graph_hash=str(state.get("selection_graph_hash") or ""),
    ):
        stage = stages.get(stage_id)
        if not isinstance(stage, dict) or stage.get("status") not in {"completed", "skipped"}:
            break
        if int(stage.get("order") or 0) != stage_order:
            break
        if int(stage.get("contract_version") or 0) != contract_version:
            break
        if not stage_runtime_contract_matches(stage_id, dict(stage.get("inputs") or {})):
            break
        artifacts = stage.get("artifacts", [])
        if not isinstance(artifacts, list) or not all(
            _validate_artifact_record(resolved_run_dir, record)
            for record in artifacts
        ):
            break
        options.append({
            "stage_id": stage_id,
            "stage_order": stage_order,
            "status": str(stage.get("status") or ""),
        })
    return options


def _stage_copy_cutoff_ns(stage: dict[str, Any]) -> int:
    precise = int(stage.get("completed_cutoff_ns") or 0)
    if precise > 0:
        return precise
    completed_at = str(stage.get("completed_at") or "")
    try:
        return int(calendar.timegm(time.strptime(completed_at, "%Y-%m-%dT%H:%M:%SZ")) * 1_000_000_000) + 999_999_999
    except (OverflowError, ValueError):
        raise PipelineCheckpointError("Secilen checkpoint tamamlanma zamani gecersiz") from None


def _resume_target_directory_name(source: Path, new_job_id: int | str) -> str:
    normalized = unicodedata.normalize("NFKD", source.name).encode("ascii", "ignore").decode("ascii")
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", normalized).strip("_") or "run"
    safe_name = safe_name[:96].rstrip("_") or "run"
    source_hash = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:10]
    return f"checkpoint_devam_{safe_name}_{source_hash}_job_{new_job_id}"


def _normalize_legacy_smart_frame_source(source: Path, temporary: Path, cloned_state: dict[str, Any]) -> None:
    stages = cloned_state.get("stages")
    if not isinstance(stages, dict):
        return
    source_stage = stages.get("video_indirme_veya_kopyalama")
    if not isinstance(source_stage, dict):
        return
    source_inputs = dict(source_stage.get("inputs") or {})
    source_payload = dict(source_stage.get("payload") or {})
    legacy_smart = source_payload.get("smart_frame_capture")
    if not isinstance(legacy_smart, dict) and "smart_frame_capture_enabled" not in source_inputs:
        return
    current_relative = str(source_payload.get("video_path") or "")
    raw_relative = current_relative
    analysis_path = source / "smart_frame_analysis.json"
    if analysis_path.is_file():
        analysis = _read_json(analysis_path)
        raw_source_path = Path(str(analysis.get("input_path") or "")).resolve()
        try:
            raw_relative = raw_source_path.relative_to(source).as_posix()
        except ValueError:
            raw_relative = raw_source_path.name
    raw_target_path = (temporary / raw_relative).resolve()
    try:
        raw_target_path.relative_to(temporary.resolve())
    except ValueError as exc:
        raise PipelineCheckpointError("Eski akilli kare kaynak yolu devam klasoru disinda") from exc
    if not raw_target_path.is_file():
        raw_source_path = (source / raw_relative).resolve()
        try:
            raw_source_path.relative_to(source)
        except ValueError as exc:
            raise PipelineCheckpointError("Eski akilli kare kaynak yolu is klasoru disinda") from exc
        if not raw_source_path.is_file():
            raise PipelineCheckpointError("Eski akilli kare isinin ham videosu bulunamadi")
        raw_target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(raw_source_path, raw_target_path)
    source_payload.pop("smart_frame_capture", None)
    source_payload["video_path"] = raw_relative
    source_stage["payload"] = source_payload
    source_stage["inputs"] = {"source": str(cloned_state.get("source_identity") or "")}
    source_stage["input_hash"] = canonical_json_hash(source_stage["inputs"])
    artifact_record = _file_digest(raw_target_path)
    artifact_record["path"] = raw_relative
    source_stage["artifacts"] = [artifact_record]
    audio_stage = stages.get("kaynak_ses_cikarma")
    if isinstance(audio_stage, dict):
        audio_inputs = dict(audio_stage.get("inputs") or {})
        audio_inputs["video_path"] = raw_relative
        audio_stage["inputs"] = audio_inputs
        audio_stage["input_hash"] = canonical_json_hash(audio_inputs)


def _normalize_legacy_disabled_demucs_stage(cloned_state: dict[str, Any]) -> None:
    stages = cloned_state.get("stages")
    if not isinstance(stages, dict):
        return
    demucs_stage = stages.get("demucs_vokal_ayirma")
    if not isinstance(demucs_stage, dict) or demucs_stage.get("status") != "skipped":
        return
    demucs_inputs = dict(demucs_stage.get("inputs") or {})
    if bool(demucs_inputs.get("enabled")) or not bool(demucs_inputs.get("prepare_asr_ready")):
        return
    demucs_inputs["prepare_asr_ready"] = False
    demucs_stage["inputs"] = demucs_inputs
    demucs_stage["input_hash"] = canonical_json_hash(demucs_inputs)


def _normalize_legacy_visual_stage_without_smart_frame(source: Path, cloned_state: dict[str, Any]) -> None:
    if (source / "smart_frame_analysis.json").is_file():
        return
    stages = cloned_state.get("stages")
    if not isinstance(stages, dict):
        return
    source_stage = stages.get("video_indirme_veya_kopyalama")
    if not isinstance(source_stage, dict):
        return
    source_video_path = str((source_stage.get("payload") or {}).get("video_path") or "")
    if not source_video_path:
        return
    visual_stage_id = (
        "full_text_final_altyazi_alignment"
        if str(cloned_state.get("pipeline_kind") or "") == "full_text"
        else "altyazi_hazirlama"
    )
    visual_stage = stages.get(visual_stage_id)
    if not isinstance(visual_stage, dict) or visual_stage.get("status") not in {"completed", "skipped"}:
        return
    visual_inputs = dict(visual_stage.get("inputs") or {})
    if "smart_frame_capture_enabled" in visual_inputs or "source_video_path" in visual_inputs:
        return
    visual_inputs["smart_frame_capture_enabled"] = False
    visual_inputs["source_video_path"] = source_video_path
    visual_stage["inputs"] = visual_inputs
    visual_stage["input_hash"] = canonical_json_hash(visual_inputs)


def _normalize_segment_translation_stage(cloned_state: dict[str, Any]) -> None:
    if str(cloned_state.get("pipeline_kind") or "") != "segment_sync":
        return
    stage = (cloned_state.get("stages") or {}).get("ceviri")
    if not isinstance(stage, dict) or stage.get("status") not in {"completed", "skipped"}:
        return
    current_inputs = dict(stage.get("inputs") or {})
    if isinstance(current_inputs.get("translation_strategy"), dict):
        return  # güncel biçim; seslendirme paketini yüklemeye gerek yok
    if not {"source_segments_hash", "source_lang", "target_lang", "translator_engine", "tts_engine"}.issubset(current_inputs):
        return
    # Tembel içe aktarma: seslendirme paketleri yalnız eski biçimli devam kopyasında gerekir.
    from dublaj_hatti.bolum_00_omurga.core.pipeline_selection_contract import (
        normalize_segment_translation_checkpoint_inputs,
    )

    normalized_inputs = normalize_segment_translation_checkpoint_inputs(current_inputs)
    if normalized_inputs == current_inputs:
        return
    stage["inputs"] = normalized_inputs
    stage["input_hash"] = canonical_json_hash(normalized_inputs)


def _normalize_legacy_manual_voice_routing_stage(cloned_state: dict[str, Any]) -> None:
    if str(cloned_state.get("pipeline_kind") or "") != "segment_sync":
        return
    stage = (cloned_state.get("stages") or {}).get("ses_ve_cinsiyet_yonlendirme")
    if not isinstance(stage, dict) or stage.get("status") not in {"completed", "skipped"}:
        return
    inputs = dict(stage.get("inputs") or {})
    if bool(inputs.get("edge_auto_gender")):
        return
    defaults = {
        "edge_female_pitch": "",
        "edge_male_pitch": "",
        "rvc_auto_gender": False,
        "rvc_female_voice_id": "",
        "rvc_male_voice_id": "",
    }
    changed = False
    for key, value in defaults.items():
        if key not in inputs:
            inputs[key] = value
            changed = True
    if not changed:
        return
    stage["inputs"] = inputs
    stage["input_hash"] = canonical_json_hash(inputs)


def clone_checkpoint_for_resume(
    source_run_dir: str | Path,
    new_job_id: int | str,
    selected_stage_id: str,
    target_pipeline_kind: str | None = None,
    target_graph_version: str = "",
    target_graph_hash: str = "",
) -> Path:
    source = Path(source_run_dir).resolve()
    state_path = source / "pipeline_state.json"
    state = _read_json(state_path)
    options = checkpoint_resume_options(source)
    selected = next((item for item in options if item["stage_id"] == selected_stage_id), None)
    if selected is None:
        raise PipelineCheckpointError(f"Secilen checkpoint devam icin kullanilamaz: {selected_stage_id}")
    selected_order = int(selected["stage_order"])
    selected_stage = state["stages"][selected_stage_id]
    source_pipeline_kind = str(state.get("pipeline_kind") or "")
    resolved_pipeline_kind = str(target_pipeline_kind or source_pipeline_kind).strip()
    target_identity = get_graph_identity(
        target_graph_version or str(state.get("selection_graph_version") or ""),
        target_graph_hash or (str(state.get("selection_graph_hash") or "") if not target_graph_version else ""),
    )
    if target_graph_version:
        validate_runtime_graph_compatibility(
            str(state.get("selection_graph_version") or ""), str(state.get("selection_graph_hash") or ""),
        )
        validate_runtime_graph_compatibility(target_identity["graph_version"], target_identity["graph_hash"])
    target_stage_ids = {
        stage_id
        for stage_id, stage_order, contract_version in checkpoint_stage_registry(
            resolved_pipeline_kind,
            graph_version=target_identity["graph_version"],
            graph_hash=target_identity["graph_hash"],
        )
        if stage_order <= selected_order
    }
    if selected_stage_id not in target_stage_ids:
        raise PipelineCheckpointError("Secilen checkpoint hedef dublaj moduyla ortak degil")
    cutoff_ns = _stage_copy_cutoff_ns(selected_stage)
    precise_cutoff = int(selected_stage.get("completed_cutoff_ns") or 0) > 0
    target = source.parent / _resume_target_directory_name(source, new_job_id)
    temporary = source.parent / f".{target.name}.hazirlaniyor"

    if target.exists():
        existing_state = _read_json(target / "pipeline_state.json")
        valid_existing = (
            str(existing_state.get("job_id") or "") == str(new_job_id)
            and str(existing_state.get("resume_source_job_id") or "") == str(state.get("job_id") or "")
            and str(existing_state.get("resume_after_stage") or "") == selected_stage_id
            and str(existing_state.get("source_identity") or "") == str(state.get("source_identity") or "")
            and str(existing_state.get("pipeline_kind") or "") == resolved_pipeline_kind
            and str(existing_state.get("selection_graph_version") or "") == target_identity["graph_version"]
            and str(existing_state.get("selection_graph_hash") or "") == target_identity["graph_hash"]
        )
        if not valid_existing:
            raise PipelineCheckpointError(f"Devam hedef klasoru baska bir ise ait: {target}")
        existing_options = checkpoint_resume_options(target)
        if selected_stage_id not in {str(item["stage_id"]) for item in existing_options}:
            existing_stage = (existing_state.get("stages") or {}).get(selected_stage_id)
            if isinstance(existing_stage, dict) and existing_stage.get("status") in {"completed", "skipped"}:
                raise PipelineCheckpointError(f"Mevcut devam kopyasi bozuk: {selected_stage_id}")
            raise PipelineCheckpointError("Mevcut devam kopyasi secilen checkpoint'i icermiyor")
        verifier = PipelineCheckpointStore(
            target,
            pipeline_kind=str(existing_state.get("pipeline_kind") or ""),
            source_identity=str(existing_state.get("source_identity") or ""),
            job_id=new_job_id,
        )
        for option in existing_options:
            if int(option["stage_order"]) > selected_order:
                break
            stage = existing_state["stages"][option["stage_id"]]
            if not all(verifier._validate_artifact_record(record) for record in stage.get("artifacts", [])):
                raise PipelineCheckpointError(f"Mevcut devam kopyasi bozuk: {option['stage_id']}")
        return target
    if temporary.exists():
        shutil.rmtree(temporary)

    preserved_stages = {}
    preserved_artifact_paths = set()
    downstream_artifact_paths = set()
    for stage_id, stage in state["stages"].items():
        stage_order = int(stage.get("order") or 0)
        artifact_paths = {str(record.get("path") or "") for record in stage.get("artifacts", [])}
        if stage_id in target_stage_ids and stage_order <= selected_order and stage.get("status") in {"completed", "skipped"}:
            preserved_stages[stage_id] = stage
            preserved_artifact_paths.update(artifact_paths)
        elif stage_order > selected_order:
            downstream_artifact_paths.update(artifact_paths)

    def ignore_newer_files(directory: str, names: list[str]) -> set[str]:
        ignored = set()
        current = Path(directory)
        for name in names:
            child = current / name
            relative_path = child.relative_to(source).as_posix()
            if child == state_path or child.name == ".pipeline_execution.lock":
                ignored.add(name)
            elif (
                child.is_file()
                and relative_path in downstream_artifact_paths
                and relative_path not in preserved_artifact_paths
            ):
                ignored.add(name)
            elif child.is_file() and relative_path not in preserved_artifact_paths:
                is_newer = (
                    child.stat().st_mtime_ns >= cutoff_ns
                    if precise_cutoff
                    else child.stat().st_mtime_ns > cutoff_ns
                )
                if is_newer:
                    ignored.add(name)
            elif child.is_symlink():
                raise PipelineCheckpointError(f"Checkpoint kopyasinda sembolik bag desteklenmiyor: {child}")
        return ignored

    try:
        shutil.copytree(source, temporary, copy_function=shutil.copy2, ignore=ignore_newer_files)
        for stage in state["stages"].values():
            if int(stage.get("order") or 0) <= selected_order:
                continue
            for record in stage.get("artifacts", []):
                relative_path = str(record.get("path") or "")
                if not relative_path or relative_path in preserved_artifact_paths:
                    continue
                artifact_path = (temporary / relative_path).resolve()
                try:
                    artifact_path.relative_to(temporary.resolve())
                except ValueError as error:
                    raise PipelineCheckpointError(f"Checkpoint artefakti kopya klasoru disinda: {relative_path}") from error
                if artifact_path.is_dir():
                    shutil.rmtree(artifact_path)
                elif artifact_path.exists():
                    artifact_path.unlink()
        cloned_state = dict(state)
        cloned_state["job_id"] = str(new_job_id)
        cloned_state["status"] = "created"
        cloned_state["active_stage"] = ""
        cloned_state["last_completed_stage"] = selected_stage_id
        cloned_state["failed_stage"] = ""
        cloned_state["resume_attempt_count"] = 0
        cloned_state["stages"] = preserved_stages
        cloned_state["pipeline_kind"] = resolved_pipeline_kind
        for identity_key in ("graph_id", "graph_version", "graph_hash"):
            cloned_state[f"selection_{identity_key}"] = target_identity[identity_key]
        cloned_state["resume_source_pipeline_kind"] = source_pipeline_kind
        cloned_state["resume_source_job_id"] = str(state.get("job_id") or "")
        cloned_state["resume_source_run_dir"] = str(source)
        cloned_state["resume_after_stage"] = selected_stage_id
        cloned_state["created_at"] = _utc_timestamp()
        cloned_state["updated_at"] = cloned_state["created_at"]
        _normalize_legacy_smart_frame_source(source, temporary, cloned_state)
        _normalize_legacy_disabled_demucs_stage(cloned_state)
        _normalize_legacy_visual_stage_without_smart_frame(source, cloned_state)
        _normalize_segment_translation_stage(cloned_state)
        _normalize_legacy_manual_voice_routing_stage(cloned_state)
        _atomic_write_json(temporary / "pipeline_state.json", cloned_state)
        verifier = PipelineCheckpointStore(
            temporary,
            pipeline_kind=str(cloned_state.get("pipeline_kind") or ""),
            source_identity=str(cloned_state.get("source_identity") or ""),
            job_id=new_job_id,
        )
        for option in options:
            if int(option["stage_order"]) > selected_order:
                break
            stage = cloned_state["stages"][option["stage_id"]]
            if not verifier.can_restore(
                option["stage_id"],
                int(option["stage_order"]),
                int(stage["contract_version"]),
                dict(stage.get("inputs") or {}),
            ):
                raise PipelineCheckpointError(f"Kopyalanan checkpoint dogrulanamadi: {option['stage_id']}")
        temporary.rename(target)
        return target
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def _file_digest(path: Path) -> dict[str, Any]:
    stat = path.stat()
    digest = hashlib.sha256()
    if path.suffix.lower() in FULL_DIGEST_AUDIO_EXTENSIONS or stat.st_size <= DEFAULT_LARGE_FILE_THRESHOLD:
        with open(path, "rb") as stream:
            while True:
                chunk = stream.read(DEFAULT_SAMPLE_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
        digest_mode = "full_sha256"
    else:
        digest.update(str(stat.st_size).encode("ascii"))
        with open(path, "rb") as stream:
            digest.update(stream.read(DEFAULT_SAMPLE_SIZE))
            stream.seek(max(0, stat.st_size - DEFAULT_SAMPLE_SIZE))
            digest.update(stream.read(DEFAULT_SAMPLE_SIZE))
        digest_mode = "sampled_sha256"
    return {
        "kind": "file",
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "digest_mode": digest_mode,
        "digest": digest.hexdigest(),
    }


def _directory_digest(path: Path) -> dict[str, Any]:
    records = []
    total_size = 0
    for child in sorted((item for item in path.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        stat = child.stat()
        relative_path = child.relative_to(path).as_posix()
        records.append([relative_path, int(stat.st_size), int(stat.st_mtime_ns)])
        total_size += int(stat.st_size)
    return {
        "kind": "directory",
        "file_count": len(records),
        "size": total_size,
        "digest_mode": "directory_listing_sha256",
        "digest": canonical_json_hash(records),
    }


def _validate_artifact_record(run_dir: Path, record: dict[str, Any]) -> bool:
    try:
        raw_relative = str(record["path"])
        path = (run_dir / raw_relative).resolve()
        path.relative_to(run_dir)
        if not path.exists():
            return False
        current = _directory_digest(path) if path.is_dir() else _file_digest(path)
        current["path"] = path.relative_to(run_dir).as_posix()
    except (KeyError, OSError, TypeError, ValueError):
        return False
    return current == record


def _process_is_alive(pid: int) -> bool:
    return process_is_alive(pid)


def ciktiyi_guncelle(run_dir: str | Path, stage_id: str, artifact_path: str | Path, icerik: bytes) -> None:
    """Tamamlanmış bir aşamanın çıktısını bilerek (kullanıcı düzeltmesi) değiştirir ve kayıtlı özetini yeniler.

    Doğrulamayı gevşetmez: `can_restore` aynı sıkılıkla çalışır, yalnız kayıtlı özet yeni dosyaya göre yazılır.
    Aşamanın girdi özeti (`input_hash`) ve diğer aşamalar değişmez. Yalnız `artifact_path` aşamanın kayıtlı
    çıktısıysa, aşama tamamlanmışsa ve iş çalışmıyorsa (kilit tutan canlı süreç yok) yapılır. Dosya geçici
    dosya + `os.replace` ile yazılır; durum dosyası da atomik kaydedilir.
    """
    kok = Path(run_dir).resolve()
    hedef = Path(artifact_path)
    hedef = hedef.resolve() if hedef.is_absolute() else (kok / hedef).resolve()
    try:
        goreli = hedef.relative_to(kok).as_posix()
    except ValueError as exc:
        raise PipelineCheckpointError("Checkpoint artefakti run_dir disinda olamaz") from exc
    kilit = kok / ".pipeline_execution.lock"
    if kilit.exists():
        try:
            pid = int(_read_json(kilit).get("pid") or 0)
        except PipelineCheckpointError:
            pid = 0
        if pid and _process_is_alive(pid):
            raise PipelineCheckpointLockedError(f"Pipeline calisiyor (pid={pid}); cikti simdi degistirilemez")
    durum_yolu = kok / "pipeline_state.json"
    durum = _read_json(durum_yolu)
    asama = (durum.get("stages") or {}).get(stage_id)
    if not isinstance(asama, dict) or asama.get("status") != "completed":
        raise PipelineCheckpointError(f"Tamamlanmis asama bulunamadi: {stage_id}")
    kayit = next((k for k in asama.get("artifacts", []) if k.get("path") == goreli), None)
    if kayit is None:
        raise PipelineCheckpointError(f"{goreli} {stage_id} asamasinin kayitli ciktisi degil")
    gecici = hedef.with_name(f".{hedef.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(gecici, "wb") as akis:
            akis.write(icerik)
            akis.flush()
            os.fsync(akis.fileno())
        yeni = _file_digest(gecici)  # os.replace değiştirme zamanını korur: kayıtlı mtime yerleşmiş dosyayla eşleşir
        yeni["path"] = goreli
        os.replace(gecici, hedef)
    finally:
        if gecici.exists():
            gecici.unlink()
    kayit.clear()
    kayit.update(yeni)
    asama["edited_at"] = _utc_timestamp()
    durum["updated_at"] = _utc_timestamp()
    _atomic_write_json(durum_yolu, durum)


class PipelineCheckpointStore:
    def __init__(
        self,
        run_dir: str | Path,
        pipeline_kind: str,
        source_identity: str,
        job_id: int | str | None = None,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
        selection_graph_version: str = "",
        selection_graph_hash: str = "",
    ):
        self.run_dir = Path(run_dir).resolve()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.run_dir / "pipeline_state.json"
        self.lock_path = self.run_dir / ".pipeline_execution.lock"
        self.pipeline_kind = str(pipeline_kind).strip()
        self.source_identity = str(source_identity).strip()
        self.job_id = "" if job_id is None else str(job_id)
        self.event_callback = event_callback
        self.requested_selection_graph_version = str(selection_graph_version or "")
        self.requested_selection_graph_hash = str(selection_graph_hash or "")
        self.enforce_graph_contract = bool(
            self.requested_selection_graph_version or self.requested_selection_graph_hash
        )
        self.selection_graph_identity: dict[str, str] = {}
        self._thread_lock = threading.RLock()
        self._lock_token = ""
        self.state = self._load_or_create_state()
        self._stage_contracts = {
            stage_id: (stage_order, contract_version)
            for stage_id, stage_order, contract_version in checkpoint_stage_registry(
                self.pipeline_kind,
                graph_version=str(self.state.get("selection_graph_version") or ""),
                graph_hash=str(self.state.get("selection_graph_hash") or ""),
            )
        }
        self._validate_recorded_stage_contracts()

    def _validate_stage_contract(
        self,
        stage_id: str,
        stage_order: int,
        contract_version: int,
    ) -> None:
        if not self.enforce_graph_contract:
            return
        expected = self._stage_contracts.get(str(stage_id))
        actual = (int(stage_order), int(contract_version))
        if expected is None or expected != actual:
            raise PipelineCheckpointError(
                f"Checkpoint asama sozlesmesi grafikle uyusmuyor: {stage_id} beklenen={expected} gercek={actual}"
            )

    def _validate_recorded_stage_contracts(self) -> None:
        if not self.enforce_graph_contract:
            return
        for stage_id, stage in self.state.get("stages", {}).items():
            self._validate_stage_contract(
                str(stage_id),
                int(stage.get("order") or 0),
                int(stage.get("contract_version") or 0),
            )

    def _load_or_create_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            state = _read_json(self.state_path)
            if int(state.get("schema_version") or 0) != PIPELINE_STATE_SCHEMA_VERSION:
                raise PipelineCheckpointError("Checkpoint schema surumu desteklenmiyor")
            if str(state.get("pipeline_kind") or "") != self.pipeline_kind:
                raise PipelineCheckpointError("Checkpoint pipeline turu mevcut istekle uyusmuyor")
            if str(state.get("source_identity") or "") != self.source_identity:
                raise PipelineCheckpointError("Checkpoint kaynak kimligi mevcut istekle uyusmuyor")
            stored_job_id = str(state.get("job_id") or "")
            if stored_job_id and self.job_id and stored_job_id != self.job_id:
                raise PipelineCheckpointError("Checkpoint is kimligi mevcut istekle uyusmuyor")
            if self.job_id and not stored_job_id:
                state["job_id"] = self.job_id
                self.state = state
                self._save()
            stored_graph_version = str(state.get("selection_graph_version") or "")
            stored_graph_hash = str(state.get("selection_graph_hash") or "")
            if stored_graph_version:
                try:
                    self.selection_graph_identity = get_graph_identity(stored_graph_version, stored_graph_hash)
                except SelectionGraphError as exc:
                    raise PipelineCheckpointError(str(exc)) from exc
                if self.requested_selection_graph_version and self.requested_selection_graph_version != stored_graph_version:
                    raise PipelineCheckpointError("Checkpoint secim grafigi surumu mevcut istekle uyusmuyor")
                if self.requested_selection_graph_hash and self.requested_selection_graph_hash != stored_graph_hash:
                    raise PipelineCheckpointError("Checkpoint secim grafigi hash degeri mevcut istekle uyusmuyor")
            return state
        try:
            self.selection_graph_identity = get_graph_identity(
                self.requested_selection_graph_version,
                self.requested_selection_graph_hash,
            )
        except SelectionGraphError as exc:
            raise PipelineCheckpointError(str(exc)) from exc
        now = _utc_timestamp()
        state = {
            "schema_version": PIPELINE_STATE_SCHEMA_VERSION,
            "pipeline_kind": self.pipeline_kind,
            "source_identity": self.source_identity,
            "job_id": self.job_id,
            "selection_graph_id": self.selection_graph_identity["graph_id"],
            "selection_graph_version": self.selection_graph_identity["graph_version"],
            "selection_graph_hash": self.selection_graph_identity["graph_hash"],
            "status": "created",
            "active_stage": "",
            "last_completed_stage": "",
            "failed_stage": "",
            "created_at": now,
            "updated_at": now,
            "resume_attempt_count": 0,
            "stages": {},
            "invalidations": [],
        }
        self.state = state
        self._save()
        return state

    def _save(self) -> None:
        self.state["updated_at"] = _utc_timestamp()
        _atomic_write_json(self.state_path, self.state)

    def _emit(self, event_type: str, stage_id: str = "") -> None:
        if not self.event_callback:
            return
        event = {
            "event": event_type,
            "stage_id": stage_id,
            "run_dir": str(self.run_dir),
            "status": self.state.get("status", ""),
            "last_completed_stage": self.state.get("last_completed_stage", ""),
            "failed_stage": self.state.get("failed_stage", ""),
        }
        try:
            self.event_callback(event)
        except Exception as exc:
            logger.warning("Pipeline checkpoint event callback basarisiz: %s", str(exc)[:300])

    def emit_artifact_ready(self, artifact_kind: str, artifact_path: str | Path) -> None:
        if not self.event_callback:
            return
        resolved_path = self._normalize_artifact_path(artifact_path)
        if not resolved_path.is_file():
            raise PipelineCheckpointError(f"Hazir artifact dosyasi bulunamadi: {resolved_path}")
        event = {
            "event": "artifact_ready",
            "artifact_kind": str(artifact_kind),
            "artifact_path": str(resolved_path),
            "run_dir": str(self.run_dir),
            "status": self.state.get("status", ""),
            "last_completed_stage": self.state.get("last_completed_stage", ""),
            "failed_stage": self.state.get("failed_stage", ""),
        }
        try:
            self.event_callback(event)
        except Exception as exc:
            logger.warning("Pipeline artifact event callback basarisiz: %s", str(exc)[:300])

    def relocate(self, new_run_dir: str | Path) -> None:
        with self._thread_lock:
            target = Path(new_run_dir).resolve()
            if not target.exists() or not target.is_dir():
                raise PipelineCheckpointError(f"Yeni checkpoint klasoru bulunamadi: {target}")
            old_state_path = self.state_path
            self.run_dir = target
            self.state_path = target / old_state_path.name
            self.lock_path = target / ".pipeline_execution.lock"
            if not self.state_path.exists():
                raise PipelineCheckpointError(f"Tasinmis checkpoint dosyasi bulunamadi: {self.state_path}")
            self._save()
            self._emit("pipeline_relocated")

    def acquire(self) -> None:
        with self._thread_lock:
            if self._lock_token:
                raise PipelineCheckpointLockedError("Checkpoint kilidi bu nesne tarafindan zaten tutuluyor")
            if self.lock_path.exists():
                existing = _read_json(self.lock_path)
                existing_pid = int(existing.get("pid") or 0)
                if _process_is_alive(existing_pid):
                    raise PipelineCheckpointLockedError(
                        f"Pipeline baska bir surec tarafindan calistiriliyor: pid={existing_pid}"
                    )
                self.lock_path.unlink()
            token = uuid.uuid4().hex
            lock_record = {
                "token": token,
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "created_at": _utc_timestamp(),
            }
            try:
                descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc:
                raise PipelineCheckpointLockedError("Pipeline kilidi ayni anda baska bir calistirici tarafindan alindi") from exc
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(json.dumps(lock_record, ensure_ascii=False, sort_keys=True).encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            self._lock_token = token
            self.state["resume_attempt_count"] = int(self.state.get("resume_attempt_count") or 0) + 1
            self._save()
            self._emit("pipeline_acquired")

    def release(self) -> None:
        with self._thread_lock:
            if not self._lock_token:
                return
            if self.lock_path.exists():
                existing = _read_json(self.lock_path)
                if str(existing.get("token") or "") == self._lock_token:
                    self.lock_path.unlink()
            self._lock_token = ""
            self._emit("pipeline_released")

    def __enter__(self) -> PipelineCheckpointStore:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.release()

    def _normalize_artifact_path(self, artifact_path: str | Path) -> Path:
        path = Path(artifact_path)
        resolved = path.resolve() if path.is_absolute() else (self.run_dir / path).resolve()
        try:
            resolved.relative_to(self.run_dir)
        except ValueError as exc:
            raise PipelineCheckpointError(f"Checkpoint artefakti run_dir disinda olamaz: {resolved}") from exc
        return resolved

    def _build_artifact_record(self, artifact_path: str | Path) -> dict[str, Any]:
        path = self._normalize_artifact_path(artifact_path)
        if not path.exists():
            raise PipelineCheckpointError(f"Checkpoint artefakti bulunamadi: {path}")
        signature = _directory_digest(path) if path.is_dir() else _file_digest(path)
        signature["path"] = path.relative_to(self.run_dir).as_posix()
        return signature

    def _validate_artifact_record(self, record: dict[str, Any]) -> bool:
        return _validate_artifact_record(self.run_dir, record)

    def invalidate_from(self, stage_order: int, reason: str) -> None:
        with self._thread_lock:
            removed = []
            for stage_id, stage in list(self.state.get("stages", {}).items()):
                if int(stage.get("order") or 0) >= int(stage_order):
                    removed.append(stage_id)
                    del self.state["stages"][stage_id]
            if removed:
                self.state.setdefault("invalidations", []).append({
                    "from_order": int(stage_order),
                    "reason": str(reason),
                    "removed_stages": removed,
                    "created_at": _utc_timestamp(),
                })
                self.state["status"] = "running"
                self.state["active_stage"] = ""
                self.state["failed_stage"] = ""
                remaining = sorted(
                    self.state.get("stages", {}).values(),
                    key=lambda item: int(item.get("order") or 0),
                )
                self.state["last_completed_stage"] = remaining[-1]["stage_id"] if remaining else ""
                self._save()
                self._emit("pipeline_invalidated")

    def can_restore(
        self,
        stage_id: str,
        stage_order: int,
        contract_version: int,
        inputs: dict[str, Any],
    ) -> bool:
        with self._thread_lock:
            self._validate_stage_contract(stage_id, stage_order, contract_version)
            stage = self.state.get("stages", {}).get(stage_id)
            if not stage:
                return False
            expected_input_hash = canonical_json_hash(inputs)
            valid_contract = (
                int(stage.get("contract_version") or 0) == int(contract_version)
                and stage_runtime_contract_matches(stage_id, dict(stage.get("inputs") or {}))
            )
            valid_order = int(stage.get("order") or 0) == int(stage_order)
            valid_inputs = str(stage.get("input_hash") or "") == expected_input_hash
            valid_status = stage.get("status") in {"completed", "skipped"}
            valid_artifacts = all(
                self._validate_artifact_record(record)
                for record in stage.get("artifacts", [])
            )
            if valid_contract and valid_order and valid_inputs and valid_status and valid_artifacts:
                self._emit("stage_restored", stage_id)
                return True
            self.invalidate_from(stage_order, f"stage_validation_failed:{stage_id}")
            return False

    def stage_payload(self, stage_id: str) -> dict[str, Any]:
        stage = self.state.get("stages", {}).get(stage_id)
        if not stage or stage.get("status") not in {"completed", "skipped"}:
            raise PipelineCheckpointError(f"Tamamlanmis checkpoint yuku bulunamadi: {stage_id}")
        payload = stage.get("payload", {})
        if not isinstance(payload, dict):
            raise PipelineCheckpointError(f"Checkpoint yuku nesne olmali: {stage_id}")
        return dict(payload)

    def begin_stage(
        self,
        stage_id: str,
        stage_order: int,
        contract_version: int,
        inputs: dict[str, Any],
    ) -> None:
        with self._thread_lock:
            self._validate_stage_contract(stage_id, stage_order, contract_version)
            previous = self.state.get("stages", {}).get(stage_id, {})
            attempts = int(previous.get("attempts") or 0) + 1
            self.invalidate_from(stage_order, f"stage_restarted:{stage_id}")
            self.state.setdefault("stages", {})[stage_id] = {
                "stage_id": stage_id,
                "order": int(stage_order),
                "contract_version": int(contract_version),
                "input_hash": canonical_json_hash(inputs),
                "inputs": inputs,
                "status": "running",
                "attempts": attempts,
                "started_at": _utc_timestamp(),
                "completed_at": "",
                "payload": {},
                "artifacts": [],
                "error": "",
            }
            self.state["status"] = "running"
            self.state["active_stage"] = stage_id
            self.state["failed_stage"] = ""
            self._save()
            self._emit("stage_started", stage_id)

    def complete_stage(
        self,
        stage_id: str,
        payload: dict[str, Any] | None = None,
        artifact_paths: Iterable[str | Path] = (),
    ) -> None:
        with self._thread_lock:
            stage = self.state.get("stages", {}).get(stage_id)
            if not stage or stage.get("status") != "running":
                raise PipelineCheckpointError(f"Baslatilmamis asama tamamlanamaz: {stage_id}")
            records = [self._build_artifact_record(path) for path in artifact_paths]
            stage["status"] = "completed"
            stage["completed_at"] = _utc_timestamp()
            stage["completed_cutoff_ns"] = time.time_ns()
            stage["payload"] = dict(payload or {})
            stage["artifacts"] = records
            stage["error"] = ""
            self.state["status"] = "running"
            self.state["active_stage"] = ""
            self.state["last_completed_stage"] = stage_id
            self.state["failed_stage"] = ""
            self._save()
            self._emit("stage_completed", stage_id)

    def skip_stage(
        self,
        stage_id: str,
        stage_order: int,
        contract_version: int,
        inputs: dict[str, Any],
        reason: str,
    ) -> None:
        self.begin_stage(stage_id, stage_order, contract_version, inputs)
        with self._thread_lock:
            stage = self.state["stages"][stage_id]
            stage["status"] = "skipped"
            stage["completed_at"] = _utc_timestamp()
            stage["completed_cutoff_ns"] = time.time_ns()
            stage["payload"] = {"skip_reason": str(reason)}
            self.state["active_stage"] = ""
            self.state["last_completed_stage"] = stage_id
            self._save()
            self._emit("stage_skipped", stage_id)

    def fail_stage(self, stage_id: str, error: BaseException | str) -> None:
        with self._thread_lock:
            stage = self.state.get("stages", {}).get(stage_id)
            if not stage:
                raise PipelineCheckpointError(f"Baslatilmamis asama basarisiz yapilamaz: {stage_id}")
            stage["status"] = "failed"
            stage["completed_at"] = _utc_timestamp()
            stage["error"] = str(error)
            self.state["status"] = "failed"
            self.state["active_stage"] = ""
            self.state["failed_stage"] = stage_id
            self._save()
            self._emit("stage_failed", stage_id)

    def mark_pipeline_completed(self) -> None:
        with self._thread_lock:
            self.state["status"] = "completed"
            self.state["active_stage"] = ""
            self.state["failed_stage"] = ""
            self._save()
            self._emit("pipeline_completed")
