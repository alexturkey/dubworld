from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import uuid
from functools import lru_cache
from pathlib import Path, PureWindowsPath
from time import perf_counter
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PACKAGE_ROOT = Path(__file__).resolve().parents[2]  # src/dublaj_hatti (paket kökü)
ENGINE_ID = "crisperwhisper_turbo_ct2"
MODEL_ID = "CrisperWhisper2.0_turbo"
MODEL_COMMIT = "de0369c8a68025b7f6e86387b6eb5a3b369787c8"
REQUEST_SCHEMA_VERSION = 3
RESPONSE_SCHEMA_VERSION = 3
RUNTIME_CONTRACT_VERSION = "crisperwhisper_turbo_ct2_v6"
# Neden: 1.5 sn ustu kelime yalniz olculen konusma araliginda kabul; gercek kelimede ic sessizlik <= 0.36 sn. bkz. docs/engineering/pinned-values.md#transcription
SHARED_ALIGNMENT_SILENCE_LIMIT_SECONDS = 1.5
SHARED_ALIGNMENT_REPAIR_LIMIT_SECONDS = 0.3
SHARED_ALIGNMENT_RAW_SILENCE_LIMIT_SECONDS = 0.5
ROOT_ENV = "DUBLAJ_CRISPERWHISPER_TURBO_CT2_ROOT"
WSL_DISTRO_ENV = "DUBLAJ_CRISPERWHISPER_TURBO_CT2_WSL_DISTRO"
EXPECTED_ARTIFACTS = {
    "raw": "crisperwhisper_turbo_ct2_raw.json",
    "dubbing_ready": "crisperwhisper_turbo_ct2_dubbing_ready.json",
    "diagnostics": "crisperwhisper_turbo_ct2_diagnostics.json",
    "profile": "transcription_profile_crisperwhisper_turbo_ct2.json",
    "language_detection": "crisperwhisper_turbo_ct2_language_detection.json",
    "language_profile": "language_detection_profile_crisperwhisper_turbo_ct2.json",
    "ctc_alignment": "crisperwhisper_turbo_ct2_ctc_alignment.json",
}
LONG_WORD_CHECK_FILENAME = "crisperwhisper_turbo_ct2_long_word_check.json"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise RuntimeError(f"UTF-8 BOM yasak: {path}")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON kok nesnesi gecersiz: {path}")
    return value


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def crisperwhisper_turbo_ct2_root() -> Path:
    configured = os.environ.get(ROOT_ENV, "").strip()
    # Kurulum (scripts/kur.ps1 -Adim crisper) motor kodunu, modeli ve WSL ortamini buraya koyar.
    root = Path(configured).expanduser() if configured else PROJECT_ROOT / "runtime_assets" / "transkripsiyon_motorlari" / "crisperwhisper_turbo_ct2"
    return root.resolve()


def windows_path_to_wsl(path: str | Path) -> str:
    resolved = Path(path).expanduser().resolve()
    pure = PureWindowsPath(str(resolved))
    if not pure.drive or not re.fullmatch(r"[A-Za-z]:", pure.drive):
        raise ValueError(f"Yalniz mutlak Windows surucu yolu desteklenir: {resolved}")
    parts = pure.parts[1:]
    if any(part in {"", ".", ".."} or any(ord(char) < 32 for char in part) for part in parts):
        raise ValueError(f"Guvenli olmayan Windows yolu: {resolved}")
    suffix = "/".join(part.replace("\\", "/") for part in parts)
    return f"/mnt/{pure.drive[0].lower()}/{suffix}"


def resolve_worker_path() -> Path:
    path = crisperwhisper_turbo_ct2_root() / "src" / "worker_entry.py"
    if not path.is_file():
        raise FileNotFoundError(f"CrisperWhisper Turbo CT2 worker bulunamadi: {path}")
    return path


def resolve_wsl_python_path() -> Path:
    path = crisperwhisper_turbo_ct2_root() / ".venv_wsl_ct2" / "bin" / "python"
    if not os.path.lexists(path) or not (path.parents[1] / "pyvenv.cfg").is_file():
        raise FileNotFoundError(f"CrisperWhisper Turbo CT2 WSL Python bulunamadi: {path}")
    return path


def load_runtime_profile() -> dict[str, Any]:
    path = crisperwhisper_turbo_ct2_root() / "config" / "runtime_profile.json"
    profile = _read_json(path)
    expected = {
        "schema_version": 3,
        "engine": ENGINE_ID,
    }
    for key, value in expected.items():
        if profile.get(key) != value:
            raise RuntimeError(f"CrisperWhisper Turbo CT2 profil {key} gecersiz")
    model = dict(profile.get("model") or {})
    runtime = dict(profile.get("runtime") or {})
    contract = dict(profile.get("contract") or {})
    exact = {
        "model.application_model_id": (model.get("application_model_id"), MODEL_ID),
        "model.resolved_commit": (model.get("resolved_commit"), MODEL_COMMIT),
        "model.storage_format": (model.get("storage_format"), "CTranslate2"),
        "model.storage_compute_type": (model.get("storage_compute_type"), "float16"),
        "runtime.device": (runtime.get("device"), "cuda"),
        "runtime.compute_type": (runtime.get("compute_type"), "int8"),
        "runtime.cpu_fallback": (runtime.get("cpu_fallback"), False),
        "contract.request_schema_version": (
            contract.get("request_schema_version"),
            REQUEST_SCHEMA_VERSION,
        ),
        "contract.response_schema_version": (
            contract.get("response_schema_version"),
            RESPONSE_SCHEMA_VERSION,
        ),
        "contract.runtime_contract_version": (
            contract.get("runtime_contract_version"),
            RUNTIME_CONTRACT_VERSION,
        ),
        "decoder.language": (dict(profile.get("decoder") or {}).get("language"), "platform_or_detected_by_ct2_language_id"),
        "contract.supported_languages": (contract.get("supported_languages"), "model_language_id_table"),
        "contract.external_forced_alignment": (contract.get("external_forced_alignment"), True),
    }
    mismatches = {
        key: {"actual": actual, "expected": expected_value}
        for key, (actual, expected_value) in exact.items()
        if actual != expected_value
    }
    if mismatches:
        raise RuntimeError(f"CrisperWhisper Turbo CT2 profil kanonik degil: {mismatches}")
    return profile


@lru_cache(maxsize=1)
def verified_model_identity() -> dict[str, Any]:
    profile = load_runtime_profile()
    motor_root = crisperwhisper_turbo_ct2_root()
    manifest = _read_json(motor_root / "config" / "model_manifest.json")
    if manifest.get("owner") != "crisperwhisper_turbo_ct2_motoru":
        raise RuntimeError("CrisperWhisper Turbo CT2 model manifest sahibi gecersiz")
    manifest_model = dict(manifest["model"])
    if manifest_model.get("resolved_commit") != MODEL_COMMIT:
        raise RuntimeError("CrisperWhisper Turbo CT2 model manifest commit'i gecersiz")
    if manifest_model.get("files") != profile["model"].get("files"):
        raise RuntimeError("CrisperWhisper Turbo CT2 profil/manifest dosyalari uyusmuyor")
    model_root = motor_root / "model_assets" / "ct2_float16_align"
    identity: dict[str, Any] = {}
    for name, specification in dict(profile["model"]["files"]).items():
        path = model_root / name
        if not path.is_file():
            raise FileNotFoundError(f"CrisperWhisper Turbo CT2 model dosyasi yok: {path}")
        expected_size = specification.get("size_bytes")
        if expected_size is not None and path.stat().st_size != int(expected_size):
            raise RuntimeError(f"CrisperWhisper Turbo CT2 model boyutu gecersiz: {name}")
        actual_hash = _sha256_file(path)
        if actual_hash != str(specification["sha256"]).lower():
            raise RuntimeError(f"CrisperWhisper Turbo CT2 model hash gecersiz: {name}")
        identity[name] = {"size_bytes": path.stat().st_size, "sha256": actual_hash}
    vad_path = motor_root / str(manifest["vad"]["relative_path"])
    if not vad_path.is_file():
        raise FileNotFoundError(f"CrisperWhisper Turbo CT2 VAD modeli yok: {vad_path}")
    vad_hash = _sha256_file(vad_path)
    if vad_hash != str(manifest["vad"]["sha256"]).lower():
        raise RuntimeError("CrisperWhisper Turbo CT2 VAD model hash gecersiz")
    identity["silero_vad.onnx"] = {
        "size_bytes": vad_path.stat().st_size,
        "sha256": vad_hash,
    }
    return identity


def crisperwhisper_turbo_ct2_contract_inputs() -> dict[str, Any]:
    from dublaj_hatti.bolum_00_omurga.runtime.whisperx_runtime import resolve_whisperx_python

    profile = load_runtime_profile()
    ctc_python = resolve_whisperx_python()
    ctc_packages = ctc_python.parents[1] / "Lib" / "site-packages"
    source_root = crisperwhisper_turbo_ct2_root()
    ctc_box = PACKAGE_ROOT / "bolum_30_hizalama_ve_segment" / "ctc_kelime_hizalama"
    # Zaman onarımının gerçekten çalışan kopyası (_repair_shared_alignment_timeline içe aktarır); değişirse ara kayıt geçersiz olur.
    timeline_repair_source = ctc_box / "zaman_onarimi.py"
    sources = {
        name: _sha256_file(source_root / "src" / name)
        for name in ("worker_entry.py", "worker.py", "native_softmax.py", "native/softmax_shim.c", "native/softmax.ptx", "native/softmax_padded.cu", "native/softmax_packed.cu", "engine.py", "multilingual_timing.py", "runtime_efficiency.py", "file_integrity.py", "language_detection.py", "coverage_recovery.py", "vad.py", "contract.py", "result_builder.py", "dubbing_ready.py")
    }
    return {
        "crisperwhisper_turbo_ct2_runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "crisperwhisper_turbo_ct2_profile_sha256": _sha256_file(source_root / "config" / "runtime_profile.json"),
        "crisperwhisper_turbo_ct2_model": MODEL_ID,
        "crisperwhisper_turbo_ct2_model_commit": MODEL_COMMIT,
        "crisperwhisper_turbo_ct2_model_files": verified_model_identity(),
        "crisperwhisper_turbo_ct2_runtime": dict(profile["runtime"]),
        "crisperwhisper_turbo_ct2_decoder": dict(profile["decoder"]),
        "crisperwhisper_turbo_ct2_vad": dict(profile["vad"]),
        "crisperwhisper_turbo_ct2_segmentation": dict(profile["segmentation"]),
        "crisperwhisper_turbo_ct2_language_detection": dict(profile["language_detection"]),
        "crisperwhisper_turbo_ct2_sources": sources,
        "crisperwhisper_turbo_ct2_ctc_alignment_box_sha256": {
            name: _sha256_file(ctc_box / name) for name in ("worker.py", "ctc_konusma_siniri.py", "client.py")
        },
        "crisperwhisper_turbo_ct2_shared_timeline_repair_source_sha256": _sha256_file(timeline_repair_source),
        "crisperwhisper_turbo_ct2_adapter_sha256": _sha256_file(Path(__file__)),
        "crisperwhisper_turbo_ct2_ctc_runtime_sha256": _sha256_file(Path(__file__).with_name("whisperx_runtime.py")),
        "crisperwhisper_turbo_ct2_ctc_environment": {
            "python": str(ctc_python),
            "alignment_sha256": _sha256_file(ctc_packages / "whisperx" / "alignment.py"),
            "torch_version_sha256": _sha256_file(ctc_packages / "torch" / "version.py"),
        },
        "crisperwhisper_turbo_ct2_native_manifest_sha256": _sha256_file(source_root / "config" / "native_softmax.json"),
    }


def _audio_duration_seconds(audio_path: Path) -> float:
    import soundfile

    info = soundfile.info(str(audio_path))
    if int(info.frames) <= 0 or int(info.samplerate) <= 0:
        raise RuntimeError(f"Ses suresi cozumlenemedi: {audio_path}")
    return int(info.frames) / int(info.samplerate)


def _validate_words(words: list[dict[str, Any]], duration_seconds: float) -> None:
    if not words:
        raise RuntimeError("CrisperWhisper Turbo CT2 kelime zamani uretmedi")
    previous_start = -1.0
    previous_end = -1.0
    for index, word in enumerate(words):
        start = float(word.get("start", -1.0))
        end = float(word.get("end", -1.0))
        if not str(word.get("word", "")).strip() or not all(map(math.isfinite, (start, end))) or start < 0.0 or end < start:
            raise RuntimeError(f"CrisperWhisper Turbo CT2 kelime araligi gecersiz: {index}")
        if start + 1e-6 < previous_start or end + 1e-6 < previous_end:
            raise RuntimeError(f"CrisperWhisper Turbo CT2 kelimeleri kronolojik degil: {index}")
        if end > duration_seconds + 1.0:
            raise RuntimeError(f"CrisperWhisper Turbo CT2 kelimesi ses suresini asti: {index}")
        previous_start = start
        previous_end = end


def _validate_response(
    output_dir: Path,
    response: dict[str, Any],
    duration_seconds: float,
    requested_language: str,
    language_detection_mode: str,
    *,
    require_ctc_alignment: bool = True,
) -> None:
    expected = {
        "status": "success",
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "engine": ENGINE_ID,
        "model": MODEL_ID,
        "model_commit": MODEL_COMMIT,
        "full_duration_processed": True,
    }
    for key, value in expected.items():
        if response.get(key) != value:
            raise RuntimeError(
                f"CrisperWhisper Turbo CT2 yanit {key} gecersiz: {response.get(key)!r}"
            )
    identity = dict(response.get("runtime_identity") or {})
    runtime = dict(load_runtime_profile()["runtime"])
    for key in ("python", "crisperwhisper", "ctranslate2_crisperwhisper", "onnxruntime", "device", "compute_type", "cpu_fallback"):
        if identity.get(key) != runtime[key]:
            raise RuntimeError(f"CrisperWhisper Turbo CT2 runtime kimligi gecersiz: {key}")
    if "int8" not in list(identity.get("supported_cuda_compute_types") or []):
        raise RuntimeError("CrisperWhisper Turbo CT2 CUDA INT8 kaniti yok")
    _validate_native_softmax(identity.get("native_softmax"))
    if abs(float(response.get("physical_audio_seconds", 0.0)) - duration_seconds) > 0.01:
        raise RuntimeError("CrisperWhisper Turbo CT2 tam sure kaniti gecersiz")
    _validate_words([dict(value) for value in list(response.get("words") or [])], duration_seconds)
    language = str(response.get("language") or "").strip()
    detected_languages = [str(value).strip() for value in list(response.get("detected_languages") or [])]
    if not language or language not in detected_languages:
        raise RuntimeError("CrisperWhisper Turbo CT2 dil kaniti gecersiz")
    if response.get("language_detection_mode") not in {"global_first_window", "continuous_stream"}:
        raise RuntimeError("CrisperWhisper Turbo CT2 dil tespit modu gecersiz")
    expected_source = (
        "platform_metadata"
        if language_detection_mode == "global_first_window" and requested_language
        else "crisper_continuous_stream_language_detection"
        if language_detection_mode == "continuous_stream"
        else "crisper_global_first_window_language_detection"
    )
    if response.get("language_source") != expected_source:
        raise RuntimeError("CrisperWhisper Turbo CT2 dil kaynagi gecersiz")
    if requested_language and language_detection_mode == "global_first_window" and language != requested_language:
        raise RuntimeError("CrisperWhisper Turbo CT2 platform dili korunmadi")

    artifacts = dict(response.get("artifacts") or {})
    for key, filename in EXPECTED_ARTIFACTS.items():
        if key == "ctc_alignment" and not require_ctc_alignment:
            continue
        data = dict(artifacts.get(key) or {})
        expected_path = (output_dir / filename).resolve()
        if Path(str(data.get("path") or "")).name != filename:
            raise RuntimeError(f"CrisperWhisper Turbo CT2 artefakt adi gecersiz: {key}")
        if not expected_path.is_file():
            raise FileNotFoundError(f"CrisperWhisper Turbo CT2 artefakti yok: {expected_path}")
        expected_hash = str(data.get("sha256") or "").lower()
        if len(expected_hash) != 64 or _sha256_file(expected_path) != expected_hash:
            raise RuntimeError(f"CrisperWhisper Turbo CT2 artefakt hash gecersiz: {key}")

    dubbing_result = _read_json(output_dir / EXPECTED_ARTIFACTS["dubbing_ready"])
    if dict(dubbing_result.get("dubbing_ready") or {}).get("contract_version") != 1:
        raise RuntimeError("CrisperWhisper Turbo CT2 dubbing-ready contract mismatch")
    for key in ("text", "words", "segments"):
        if key not in response or response[key] != dubbing_result.get(key):
            raise RuntimeError(f"CrisperWhisper Turbo CT2 dubbing-ready response mismatch: {key}")
    if require_ctc_alignment:
        evidence = _read_json(output_dir / EXPECTED_ARTIFACTS["ctc_alignment"])
        if (
            evidence.get("status") != "verified"
            or evidence.get("contract_version") != 2
            or evidence.get("words") != response["words"]
            or response.get("external_forced_alignment") is not True
            or dubbing_result.get("external_forced_alignment") is not True
        ):
            raise RuntimeError("CrisperWhisper Turbo CT2 verified CTC delivery missing")
        _validate_shared_alignment_words(
            response["words"],
            duration_seconds,
            _evidence_speech_spans(evidence, response["words"]),
            _evidence_raw_silences(evidence),
        )


def _canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _is_sentence_end_word(value: str) -> bool:
    return bool(re.search(r"[.!?…。！？]$", value.strip()))


def _build_shared_alignment_segments(words: list[dict[str, Any]], audio_duration: float) -> list[dict[str, Any]]:
    if not words:
        raise RuntimeError("CrisperWhisper Turbo CT2 shared alignment source words are empty")
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    previous_end: float | None = None
    for word in words:
        start = float(word["start"])
        if current:
            group_start = float(current[0]["start"])
            gap = start - float(previous_end if previous_end is not None else group_start)
            if gap > 2.5 or start - group_start > 18.0 or len(current) >= 80:
                groups.append(current)
                current = []
        current.append(word)
        previous_end = float(word["end"])
        if _is_sentence_end_word(str(word["word"])):
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    segments: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        start = max(0.0, float(group[0]["start"]) - 0.25)
        next_start = float(groups[index + 1][0]["start"]) if index + 1 < len(groups) else audio_duration
        end = min(audio_duration, max(next_start, float(group[-1]["end"]) + 0.25))
        if end <= start:
            end = min(audio_duration, start + 0.25)
        segments.append({
            "index": index,
            "start": round(start, 3),
            "end": round(end, 3),
            "text": " ".join(str(value["word"]) for value in group),
        })
    return segments


def _measured_speech_spans(worker_result: dict[str, Any], word_count: int) -> list[tuple[float, float] | None]:
    recorded = worker_result.get("speech_spans")
    if not isinstance(recorded, list) or len(recorded) != word_count:
        return [None] * word_count
    return [
        (float(span[0]), float(span[1])) if isinstance(span, list) and len(span) == 2 else None
        for span in recorded
    ]


def _evidence_speech_spans(evidence: dict[str, Any], words: list[dict[str, Any]]) -> list[tuple[float, float] | None] | None:
    recorded = evidence.get("measured_speech_spans")
    if not isinstance(recorded, list) or len(recorded) != len(words):
        return None
    spans: list[tuple[float, float] | None] = []
    for span in recorded:
        if isinstance(span, list) and len(span) == 2:
            spans.append((float(span[0]), float(span[1])))
        else:
            spans.append(None)
    return spans


def _is_long_word(word: dict[str, Any]) -> bool:
    return float(word["end"]) - float(word["start"]) > SHARED_ALIGNMENT_SILENCE_LIMIT_SECONDS


def _long_word_raw_silences(source: Path, words: list[dict[str, Any]]) -> dict[int, float | None]:
    import soundfile

    from dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama.ctc_konusma_siniri import (
        RAW_SILENCE_CONTEXT_SECONDS,
        longest_silent_run_seconds,
    )

    long_indexes = [index for index, word in enumerate(words) if _is_long_word(word)]
    if not long_indexes:
        return {}
    info = soundfile.info(str(source))
    silences: dict[int, float | None] = {}
    for index in long_indexes:
        start, end = float(words[index]["start"]), float(words[index]["end"])
        first = max(0, int((start - RAW_SILENCE_CONTEXT_SECONDS) * info.samplerate))
        last = min(int(info.frames), int((end + RAW_SILENCE_CONTEXT_SECONDS) * info.samplerate))
        samples, _ = soundfile.read(str(source), start=first, stop=last, dtype="float32", always_2d=True)
        offset = first / info.samplerate
        silences[index] = longest_silent_run_seconds(samples.mean(axis=1), info.samplerate, start - offset, end - offset)
    return silences


def _evidence_raw_silences(evidence: dict[str, Any]) -> dict[int, float | None] | None:
    recorded = evidence.get("long_word_raw_silence")
    if not isinstance(recorded, list):
        return None
    return {
        int(entry["index"]): None if entry.get("longest_silent_run_seconds") is None else float(entry["longest_silent_run_seconds"])
        for entry in recorded
    }


def _raw_audio_confirms_speech(index: int, raw_silences: dict[int, float | None] | None) -> bool:
    if raw_silences is None or raw_silences.get(index) is None:
        return False
    return raw_silences[index] <= SHARED_ALIGNMENT_RAW_SILENCE_LIMIT_SECONDS


def _long_word_check_report(
    words: list[dict[str, Any]],
    speech_spans: list[tuple[float, float] | None],
    raw_silences: dict[int, float | None],
) -> dict[str, Any]:
    from dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama.ctc_konusma_siniri import (
        RAW_SILENCE_CONTEXT_SECONDS,
        RAW_SILENCE_FRAME_SECONDS,
        RAW_SILENCE_LEVEL_RATIO,
        RAW_SILENCE_MINIMUM_CONTRAST_DB,
        SPEECH_PAD_SECONDS,
    )

    checked = []
    for index, silence in sorted(raw_silences.items()):
        word = words[index]
        span = speech_spans[index]
        inside_span = _inside_measured_speech(word, span)
        raw_confirms = _raw_audio_confirms_speech(index, raw_silences)
        checked.append({
            "index": index,
            "word": str(word["word"]),
            "start": float(word["start"]),
            "end": float(word["end"]),
            "duration_seconds": round(float(word["end"]) - float(word["start"]), 3),
            "measured_speech_span": list(span) if span is not None else None,
            "inside_measured_speech": inside_span,
            "longest_silent_run_seconds": silence,
            "raw_audio_confirms_speech": raw_confirms,
            "decision": "accepted" if inside_span and raw_confirms else "rejected",
        })
    return {
        "long_word_limit_seconds": SHARED_ALIGNMENT_SILENCE_LIMIT_SECONDS,
        "speech_span_allowance_seconds": round(SPEECH_PAD_SECONDS + SHARED_ALIGNMENT_REPAIR_LIMIT_SECONDS, 3),
        "raw_silence_limit_seconds": SHARED_ALIGNMENT_RAW_SILENCE_LIMIT_SECONDS,
        "raw_silence_method": {
            "frame_seconds": RAW_SILENCE_FRAME_SECONDS,
            "context_seconds": RAW_SILENCE_CONTEXT_SECONDS,
            "level_ratio": RAW_SILENCE_LEVEL_RATIO,
            "minimum_contrast_db": RAW_SILENCE_MINIMUM_CONTRAST_DB,
        },
        "checked_word_count": len(checked),
        "rejected_word_count": sum(1 for entry in checked if entry["decision"] == "rejected"),
        "words": checked,
    }


def _inside_measured_speech(word: dict[str, Any], speech_span: tuple[float, float] | None) -> bool:
    from dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama.ctc_konusma_siniri import SPEECH_PAD_SECONDS

    if speech_span is None:
        return False
    allowance = SPEECH_PAD_SECONDS + SHARED_ALIGNMENT_REPAIR_LIMIT_SECONDS + 1e-6
    return (
        float(word["start"]) >= speech_span[0] - allowance
        and float(word["end"]) <= speech_span[1] + allowance
    )


def _validate_shared_alignment_words(
    words: list[dict[str, Any]],
    duration_seconds: float,
    speech_spans: list[tuple[float, float] | None] | None = None,
    raw_silences: dict[int, float | None] | None = None,
) -> None:
    _validate_words(words, duration_seconds)
    spans = speech_spans if speech_spans is not None else [None] * len(words)
    # Her kelimenin tek ölçülmüş konuşma aralığı var: _measured_speech_spans/_evidence_speech_spans boyu len(words) ya da None.
    for index, (word, speech_span) in enumerate(zip(words, spans, strict=True)):
        if not _is_long_word(word):
            continue
        if not _inside_measured_speech(word, speech_span):
            raise RuntimeError(f"CrisperWhisper Turbo CT2 shared alignment silence-swallowing word: {index}")
        if not _raw_audio_confirms_speech(index, raw_silences):
            silence = None if raw_silences is None else raw_silences.get(index)
            raise RuntimeError(
                f"CrisperWhisper Turbo CT2 shared alignment silence-swallowing word: {index} "
                f"(raw audio silence inside word: {silence})"
            )
    # Ardışık çiftler: words[1:] bilerek bir kısa, son kelimenin ardılı yok.
    for index, (current, following) in enumerate(zip(words, words[1:], strict=False)):
        if float(current["end"]) > float(following["start"]) + 1e-6:
            raise RuntimeError(f"CrisperWhisper Turbo CT2 shared alignment overlap: {index}")


def _repair_shared_alignment_timeline(words: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, float]:
    from dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama.zaman_onarimi import (
        max_timing_adjustment_seconds,
        repair_aligned_word_timeline,
    )

    repaired, repaired_count = repair_aligned_word_timeline(words)
    return repaired, repaired_count, max_timing_adjustment_seconds(words, repaired)


def align_dubbing_delivery(source: Path, output_dir: Path, response: dict, timeout_seconds: int) -> dict:
    from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import huggingface_home
    from dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama import WORKER_PATH, run_ctc_word_alignment

    request_path = output_dir / "crisperwhisper_turbo_ct2_ctc_request.json"
    result_path = output_dir / EXPECTED_ARTIFACTS["ctc_alignment"]
    request_id = uuid.uuid4().hex
    source_words = [dict(word) for word in list(response.get("words") or [])]
    source_text = str(response.get("text") or "")
    source_duration = float(response["physical_audio_seconds"])
    alignment_segments = _build_shared_alignment_segments(source_words, source_duration)
    request_path.write_text(
        json.dumps(alignment_segments, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    alignment_started = perf_counter()
    worker_result = run_ctc_word_alignment(
        source, request_path, str(response["language"]), huggingface_home(), timeout_seconds
    )
    alignment_elapsed_seconds = round(perf_counter() - alignment_started, 3)
    aligned_words = [dict(word) for word in list(worker_result.get("words") or [])]
    if len(aligned_words) != len(source_words) or [word.get("word") for word in aligned_words] != [word.get("word") for word in source_words]:
        raise RuntimeError("CrisperWhisper Turbo CT2 shared WhisperX alignment changed transcript")
    words = []
    # Boy eşitliği hemen yukarıda denetlendi; strict yalnız bu sözleşmeyi koda yazar.
    for source_word, aligned_word in zip(source_words, aligned_words, strict=True):
        merged_word = dict(source_word)
        merged_word["start"] = float(aligned_word["start"])
        merged_word["end"] = float(aligned_word["end"])
        if aligned_word.get("score") is not None:
            merged_word["alignment_score"] = float(aligned_word["score"])
        words.append(merged_word)
    words, repaired_count, max_adjustment_seconds = _repair_shared_alignment_timeline(words)
    if max_adjustment_seconds > SHARED_ALIGNMENT_REPAIR_LIMIT_SECONDS:
        raise RuntimeError(
            "CrisperWhisper Turbo CT2 shared WhisperX timing repair exceeds 300 ms"
        )
    speech_spans = _measured_speech_spans(worker_result, len(words))
    raw_silences = _long_word_raw_silences(source, words)
    long_word_check = _long_word_check_report(words, speech_spans, raw_silences)
    _write_json_atomic(output_dir / LONG_WORD_CHECK_FILENAME, long_word_check)
    _validate_shared_alignment_words(words, source_duration, speech_spans, raw_silences)
    evidence = {
        "status": "verified",
        "contract_version": 2,
        "request_id": request_id,
        "method": "ctc_kelime_hizalama_kutusu",
        "worker_path": str(WORKER_PATH),
        "worker_command": [str(value) for value in worker_result["command"]],
        "audio_sha256": _sha256_file(source),
        "source_text": source_text,
        "source_text_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        "source_words": source_words,
        "source_words_sha256": _canonical_json_sha256(source_words),
        "alignment_input_segments": alignment_segments,
        "alignment_input_sha256": _sha256_file(request_path),
        "words": words,
        "measured_speech_spans": [list(span) if span is not None else None for span in speech_spans],
        "long_word_raw_silence": long_word_check["words"],
        "timing_repair": {
            "implementation": "dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama.zaman_onarimi.repair_aligned_word_timeline",
            "repaired_word_count": repaired_count,
            "max_adjustment_seconds": max_adjustment_seconds,
            "maximum_allowed_adjustment_seconds": 0.3,
        },
        "alignment_worker_profile": dict(worker_result.get("profile_summary") or {}),
        "elapsed_seconds": alignment_elapsed_seconds,
    }
    _write_json_atomic(result_path, evidence)
    segments = [{"index": 0, "start": words[0]["start"], "end": words[-1]["end"],
                 "text": response["text"], "words": words}]
    alignment_summary = {key: evidence[key] for key in (
        "contract_version", "method", "worker_path", "elapsed_seconds",
    )}
    updates = {"words": words, "segments": segments, "total_segments": 1,
               "word_timestamps": "ctc_kelime_hizalama", "external_forced_alignment": True,
               "ctc_alignment": alignment_summary}
    ready_path = output_dir / EXPECTED_ARTIFACTS["dubbing_ready"]
    ready = _read_json(ready_path)
    ready.update(updates)
    ready.setdefault("profile_summary", {}).update({
        "external_forced_alignment": True, "ctc_alignment": alignment_summary,
        "word_timestamps": "ctc_kelime_hizalama",
    })
    _write_json_atomic(ready_path, ready)
    response.update(updates)
    response["profile_summary"] = ready["profile_summary"]
    for key in ("profile", "diagnostics"):
        path = output_dir / EXPECTED_ARTIFACTS[key]
        payload = _read_json(path)
        payload.update({"external_forced_alignment": True, "ctc_alignment": alignment_summary})
        if key == "profile":
            for artifact_key in ("dubbing_ready", "ctc_alignment"):
                artifact_path = output_dir / EXPECTED_ARTIFACTS[artifact_key]
                payload.setdefault("artifacts", {})[artifact_key] = {
                    "path": artifact_path.name, "sha256": _sha256_file(artifact_path),
                }
            payload["word_timestamps"] = "ctc_kelime_hizalama"
        _write_json_atomic(path, payload)
    for key in ("dubbing_ready", "profile", "diagnostics", "ctc_alignment"):
        path = output_dir / EXPECTED_ARTIFACTS[key]
        response.setdefault("artifacts", {})[key] = {"path": path.name, "sha256": _sha256_file(path)}
    return response


def _validate_native_softmax(evidence: Any) -> None:
    manifest_path = crisperwhisper_turbo_ct2_root() / "config" / "native_softmax.json"
    manifest = _read_json(manifest_path)
    expected = {
        "implementation": manifest["implementation"],
        "kernel": manifest["kernel"],
        "variant": manifest["variant"],
        "thread_cap": manifest["thread_cap"],
        "manifest_sha256": _sha256_file(manifest_path),
        "native_sha256": manifest["native_sha256"],
        "ptx_sha256": manifest["sources"]["softmax.ptx"],
        "shim_sha256": manifest["shim_sha256"],
        "compute_capability": manifest["compute_capability"],
        "transcript_cache": False,
    }
    if not isinstance(evidence, dict) or any(evidence.get(key) != value for key, value in expected.items()):
        raise RuntimeError("CrisperWhisper Turbo CT2 native Softmax identity mismatch")
    if type(evidence.get("changed_calls")) is not int or evidence["changed_calls"] <= 0:
        raise RuntimeError("CrisperWhisper Turbo CT2 native Softmax execution evidence missing")


def worker_environment() -> dict[str, str]:
    environment = os.environ.copy()
    name = "DUBLAJ_CT2_HOST_PYTHON"
    environment[name] = str(Path(sys.executable).resolve())
    inherited = [entry for entry in environment.get("WSLENV", "").split(":") if entry and entry.split("/", 1)[0] != name]
    environment["WSLENV"] = ":".join([*inherited, name + "/p"])
    return environment


def invoke_crisperwhisper_turbo_ct2(
    audio_path: str | Path,
    run_dir: str | Path,
    language_detection_mode: str = "global_first_window",
    platform_language: str = "",
    timeout_seconds: int = 2700,
) -> tuple[dict[str, Any], subprocess.CompletedProcess[str]]:
    source = Path(audio_path).resolve()
    output_dir = Path(run_dir).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"CrisperWhisper Turbo CT2 ses dosyasi yok: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)
    if language_detection_mode not in {"global_first_window", "continuous_stream"}:
        raise ValueError(
            f"CrisperWhisper Turbo CT2 dil tespit modu gecersiz: {language_detection_mode}"
        )
    normalized_platform_language = str(platform_language or "").strip().lower()
    if normalized_platform_language and not re.fullmatch(r"[a-z]{2,3}", normalized_platform_language):
        raise ValueError(
            "CrisperWhisper Turbo CT2 platform dil kodu gecersiz: "
            f"{normalized_platform_language!r}"
        )
    load_runtime_profile()
    verified_model_identity()
    duration_seconds = _audio_duration_seconds(source)
    request_path = output_dir / "crisperwhisper_turbo_ct2_request.json"
    response_path = output_dir / "crisperwhisper_turbo_ct2_response.json"
    request = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "engine": ENGINE_ID,
        "model": MODEL_ID,
        "language": (
            normalized_platform_language
            if language_detection_mode == "global_first_window" and normalized_platform_language
            else "detected_by_ct2_language_id"
        ),
        "platform_language": normalized_platform_language,
        "language_detection_mode": language_detection_mode,
        "full_duration_required": True,
        "audio_path": windows_path_to_wsl(source),
        "output_dir": windows_path_to_wsl(output_dir),
        "audio_sha256": _sha256_file(source),
        "audio_duration_seconds": duration_seconds,
    }
    _write_json_atomic(request_path, request)
    distro = os.environ.get(WSL_DISTRO_ENV, "Ubuntu").strip() or "Ubuntu"
    command = [
        "wsl.exe",
        "-d",
        distro,
        "--",
        windows_path_to_wsl(resolve_wsl_python_path()),
        windows_path_to_wsl(resolve_worker_path()),
        "--request",
        windows_path_to_wsl(request_path),
        "--response",
        windows_path_to_wsl(response_path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=worker_environment(),
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),  # konsol penceresi açmadan (Windows)
    )
    if not response_path.is_file():
        raise RuntimeError(
            "CrisperWhisper Turbo CT2 yaniti uretilmedi: "
            f"returncode={completed.returncode}, stderr={(completed.stderr or '')[-4000:]}"
        )
    response = _read_json(response_path)
    if completed.returncode != 0 or response.get("status") != "success":
        raise RuntimeError(
            "CrisperWhisper Turbo CT2 worker basarisiz: "
            f"returncode={completed.returncode}, error={response.get('error')!r}, "
            f"stderr={(completed.stderr or '')[-4000:]}"
        )
    _validate_response(
        output_dir,
        response,
        duration_seconds,
        normalized_platform_language,
        language_detection_mode,
        require_ctc_alignment=False,
    )
    try:
        response = align_dubbing_delivery(source, output_dir, response, timeout_seconds)
        _validate_response(output_dir, response, duration_seconds, normalized_platform_language, language_detection_mode)
    except Exception as error:
        _write_json_atomic(response_path, {
            "status": "error", "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
            "stage": "ctc_alignment", "error": str(error),
        })
        raise
    _write_json_atomic(response_path, response)
    return response, completed
