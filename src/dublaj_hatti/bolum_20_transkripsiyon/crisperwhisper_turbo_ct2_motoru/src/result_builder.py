from __future__ import annotations

from pathlib import Path
from typing import Any

from contract import sha256_file, validate_words, write_json_atomic
from dubbing_ready import build_dubbing_ready_result


def write_success_artifacts(
    output_dir: Path,
    *,
    raw_result: dict[str, Any],
    tokenizer_contract: dict[str, Any],
    diagnostics: dict[str, Any],
    profile: dict[str, Any],
    language_detection: dict[str, Any],
    language_profile: dict[str, Any],
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    raw_path = output_dir / "crisperwhisper_turbo_ct2_raw.json"
    dubbing_path = output_dir / "crisperwhisper_turbo_ct2_dubbing_ready.json"
    diagnostics_path = output_dir / "crisperwhisper_turbo_ct2_diagnostics.json"
    profile_path = output_dir / "transcription_profile_crisperwhisper_turbo_ct2.json"
    language_detection_path = output_dir / "crisperwhisper_turbo_ct2_language_detection.json"
    language_profile_path = output_dir / "language_detection_profile_crisperwhisper_turbo_ct2.json"

    write_json_atomic(raw_path, raw_result)
    prepared_result = build_dubbing_ready_result(raw_result, tokenizer_contract)
    validate_words(prepared_result["words"], float(raw_result["physical_audio_seconds"]))
    dubbing_result = {
        "schema_version": 1,
        "engine": raw_result["engine"],
        "model": raw_result["model"],
        "language": raw_result["language"],
        "detected_languages": raw_result["detected_languages"],
        "language_detection_mode": raw_result["language_detection_mode"],
        "text": prepared_result["text"],
        "words": prepared_result["words"],
        "segments": prepared_result["segments"],
        "dubbing_ready": prepared_result["dubbing_ready"],
        "word_timestamps": "native_crisperwhisper_ct2",
        "external_forced_alignment": False,
    }
    profile["raw_word_count"] = len(raw_result["words"])
    profile["word_count"] = len(dubbing_result["words"])
    profile["dubbing_ready"] = prepared_result["profile_summary"]["dubbing_ready"]
    write_json_atomic(dubbing_path, dubbing_result)
    write_json_atomic(diagnostics_path, diagnostics)
    write_json_atomic(language_detection_path, language_detection)
    write_json_atomic(language_profile_path, language_profile)
    profile["artifacts"] = {
        "raw": {"path": str(raw_path), "sha256": sha256_file(raw_path)},
        "dubbing_ready": {
            "path": str(dubbing_path),
            "sha256": sha256_file(dubbing_path),
        },
        "diagnostics": {
            "path": str(diagnostics_path),
            "sha256": sha256_file(diagnostics_path),
        },
        "language_detection": {
            "path": str(language_detection_path),
            "sha256": sha256_file(language_detection_path),
        },
        "language_profile": {
            "path": str(language_profile_path),
            "sha256": sha256_file(language_profile_path),
        },
    }
    write_json_atomic(profile_path, profile)
    return {
        **profile["artifacts"],
        "profile": {"path": str(profile_path), "sha256": sha256_file(profile_path)},
    }, dubbing_result
