from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
# Motor klasörü paketin içindedir (src/dublaj_hatti/bolum_20_transkripsiyon/...); paket kökünden bulunur,
# repo düzenine bağlı değildir. DUBLAJ_CRISPERWHISPER_ROOT ile geçersiz kılınır.
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CRISPERWHISPER_ROOT = PACKAGE_ROOT / "bolum_20_transkripsiyon" / "crisperwhisper2_medium_motoru"
CRISPERWHISPER_ENGINE = "crisperwhisper2_medium"
CRISPERWHISPER_MODEL_NAME = "CrisperWhisper2.0_medium"
CRISPERWHISPER_MODEL_REPO = "nyralabs/CrisperWhisper2.0_medium"
CRISPERWHISPER_SNAPSHOT_ID = "ca981a994a008f70b7ce343ef1e261ff7eadc1d9"
CRISPERWHISPER_PYTHON_ENV = "DUBLAJ_CRISPERWHISPER_PYTHON"
CRISPERWHISPER_ROOT_ENV = "DUBLAJ_CRISPERWHISPER_ROOT"
CRISPERWHISPER_PROFILE_SCHEMA_VERSION = 20
CRISPERWHISPER_RUNTIME_CONTRACT_VERSION = 24
CRISPERWHISPER_TIMED_REPETITION_CONTRACT_VERSION = 1
CRISPERWHISPER_TIMED_REPETITION_POLICY = "accept_strictly_increasing_occurrence_start_seconds"
CRISPERWHISPER_QUALITY_FAILURE_SCHEMA_VERSION = 2
CRISPERWHISPER_QUALITY_FAILURE_ARTIFACT = "crisperwhisper2_medium_quality_failure.json"
CRISPERWHISPER_API_SCHEMA_VERSION = 3
CRISPERWHISPER_LANGUAGE_DETECTION_CONTRACT_VERSION = 6
CRISPERWHISPER_GLOBAL_FIRST_WINDOW_LANGUAGE_MODE = "global_first_window"
CRISPERWHISPER_PER_WINDOW_LANGUAGE_MODE = "per_window"
CRISPERWHISPER_CONTINUOUS_STREAM_LANGUAGE_MODE = "continuous_stream"
CRISPERWHISPER_LANGUAGE_DETECTION_MODES = {
    CRISPERWHISPER_GLOBAL_FIRST_WINDOW_LANGUAGE_MODE,
    CRISPERWHISPER_PER_WINDOW_LANGUAGE_MODE,
    CRISPERWHISPER_CONTINUOUS_STREAM_LANGUAGE_MODE,
}
CRISPERWHISPER_VAD_MODEL_ENV = "DUBLAJ_CRISPERWHISPER_VAD_MODEL"
CRISPERWHISPER_SOURCE_FILES = (
    "src/crisperwhisper2_medium_transkript.py",
    "src/transcript_normalization.py",
    "src/crisperwhisper_longform.py",
    "src/crisperwhisper_no_space_languages.py",
    "src/crisperwhisper_runtime_optimization.py",
    "src/crisperwhisper_dubbing_ready.py",
    "src/crisperwhisper_api_service.py",
    "src/configs/model_snapshot_manifest.json",
)


def crisperwhisper_root() -> Path:
    configured_root = os.environ.get(CRISPERWHISPER_ROOT_ENV, "").strip()
    root = Path(configured_root).expanduser() if configured_root else DEFAULT_CRISPERWHISPER_ROOT
    return root.resolve()


def resolve_crisperwhisper_python() -> Path:
    configured_path = os.environ.get(CRISPERWHISPER_PYTHON_ENV, "").strip()
    python_path = (
        Path(configured_path).expanduser()
        if configured_path
        else crisperwhisper_root() / ".venv" / "Scripts" / "python.exe"
    ).resolve()
    if not python_path.is_file():
        raise FileNotFoundError(
            f"CrisperWhisper Python bulunamadi: {python_path}. "
            f"{CRISPERWHISPER_PYTHON_ENV} ile farkli bir yol belirtilebilir."
        )
    return python_path


def resolve_crisperwhisper_model_snapshot() -> Path:
    snapshot = (
        crisperwhisper_root()
        / "model_cache"
        / "huggingface"
        / "models--nyralabs--CrisperWhisper2.0_medium"
        / CRISPERWHISPER_SNAPSHOT_ID
    ).resolve()
    if snapshot.name != CRISPERWHISPER_SNAPSHOT_ID or not (snapshot / "model.safetensors").is_file():
        raise FileNotFoundError(
            f"CrisperWhisper model snapshot bulunamadi: {snapshot}"
        )
    return snapshot


def resolve_crisperwhisper_vad_model() -> Path:
    configured_path = os.environ.get(CRISPERWHISPER_VAD_MODEL_ENV, "").strip()
    model_path = (
        Path(configured_path).expanduser()
        if configured_path
        else PROJECT_ROOT
        / "runtime_assets"
        / "model_cache"
        / "torch"
        / "hub"
        / "snakers4_silero-vad_master"
        / "src"
        / "silero_vad"
        / "data"
        / "silero_vad.jit"
    ).resolve()
    if not model_path.is_file():
        raise FileNotFoundError(
            f"CrisperWhisper Silero VAD modeli bulunamadi: {model_path}. "
            f"{CRISPERWHISPER_VAD_MODEL_ENV} ile farkli bir yol belirtilebilir."
        )
    return model_path


def resolve_crisperwhisper_api_script() -> Path:
    script = (crisperwhisper_root() / "src" / "crisperwhisper_api_service.py").resolve()
    if not script.is_file():
        raise FileNotFoundError(f"CrisperWhisper deney API servisi bulunamadi: {script}")
    return script


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def crisperwhisper_source_identity() -> dict[str, str]:
    root = crisperwhisper_root()
    identity = {}
    for relative_path in CRISPERWHISPER_SOURCE_FILES:
        source_path = root / Path(relative_path)
        if not source_path.is_file():
            raise FileNotFoundError(f"CrisperWhisper deney kaynagi bulunamadi: {source_path}")
        identity[relative_path] = _sha256_file(source_path)
    return identity


def load_crisperwhisper_runtime_profile() -> dict[str, Any]:
    profile_path = crisperwhisper_root() / "src" / "configs" / "runtime_profile.json"
    if not profile_path.is_file():
        raise FileNotFoundError(f"CrisperWhisper runtime profili bulunamadi: {profile_path}")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        raise RuntimeError("CrisperWhisper runtime profili nesne degil")
    expected = {
        "schema_version": CRISPERWHISPER_PROFILE_SCHEMA_VERSION,
        "model_repo": CRISPERWHISPER_MODEL_REPO,
        "model_snapshot_id": CRISPERWHISPER_SNAPSHOT_ID,
        "backend": "transformers",
        "device": "cuda",
        "compute_type": "float16",
        "runtime_optimization_id": "runtime23_v5_language_route",
        "mode": "verbatim",
        "language": "platform_or_detected_by_crisper_language_id",
        "platform_language_policy": "global_first_window_prefer_valid_platform_else_detect_continuous_evidence_only",
        "word_timestamps": True,
        "longform_strategy": "detected_language_route",
        "default_longform_strategy": "silero_vad_compact_timeline_dynamic_overlap_stitch",
        "no_space_longform_strategy": "continuation",
        "no_space_language_codes": ["ja", "lo", "my", "th", "yue", "zh"],
        "no_space_chunk_duration_seconds": 29.5,
        "no_space_stride_seconds": 24.5,
        "no_space_context_groups": 64,
        "no_space_context_budget_policy": "live_model_limit_preserve_generation_budget",
        "no_space_context_overflow_policy": "retain_recent_unicode_safe_token_suffix_or_no_context",
        "no_space_expected_max_target_positions": 448,
        "no_space_generation_token_reserve": 256,
        "no_space_max_new_tokens": 256,
        "no_space_max_uncovered_active_tail_seconds": 3.0,
        "no_space_adaptive_retry_chunk_duration_seconds": 15.0,
        "no_space_adaptive_retry_overlap_seconds": 5.0,
        "no_space_adaptive_retry_stride_seconds": 10.0,
        "no_space_adaptive_retry_policy": (
            "retry_same_compact_audio_with_overlap_and_deterministic_plain_consensus"
        ),
        "no_space_overlap_suffix_recovery_policy": (
            "restore_unrecaptured_exact_timed_suffix_in_source_order"
        ),
        "no_space_plain_consensus_temperature": 0.8,
        "no_space_plain_consensus_seed_count": 4,
        "no_space_plain_consensus_minimum_fraction": 0.25,
        "no_space_intended_consensus_seed_count": 3,
        "no_space_intended_consensus_seeds": [5, 8, 15],
        "no_space_intended_consensus_batch_size": 3,
        "no_space_intended_consensus_temperature": 0.8,
        "no_space_intended_consensus_minimum_candidates": 3,
        "no_space_intended_consensus_maximum_token_density": 1.5,
        "no_space_intended_consensus_policy": (
            "sparse_timed_sibling_median_length_then_bpe_rank"
        ),
        "no_space_token_decode_policy": "decode_minimum_unicode_safe_token_groups",
        "no_space_coverage_count_mode": "content_tokens",
        "no_space_fallback_policy": "verbatim_intended_then_temperature_or_plain_transcribe_sibling",
        "no_space_loop_recovery_policy": "reject_missing_or_non_increasing_timed_loop_then_temperature_safe_sibling_or_intended_continuation",
        "no_space_min_speech_seconds": 5.0,
        "no_space_min_content_tokens_per_active_second": 0.5,
        "no_space_min_sibling_content_tokens": 8,
        "target_window_seconds": 25.0,
        "maximum_window_seconds": 29.5,
        "minimum_window_seconds": 5.0,
        "continuous_language_context_seconds": 4.0,
        "continuous_language_tick_seconds": 1.0,
        "continuous_language_confirmation_ticks": 2,
        "continuous_language_min_top_probability": 0.6,
        "continuous_language_min_margin": 0.2,
        "continuous_language_boundary_policy": "midpoint_between_last_stable_and_first_confirmed_new_tick_centers",
        "inference_window_timestamp_tolerance_seconds": 0.1,
        "inference_window_timestamp_policy": "clip_supported_endpoint_drop_fully_outside_or_fail",
        "compact_seam_tolerance_seconds": 0.05,
        "compact_seam_policy": "clip_shorter_side_within_tolerance_or_fail",
        "minimum_overlap_seconds": 1.5,
        "maximum_overlap_seconds": 10.0,
        "minimum_anchor_words": 2,
        "stitch_boundary_contract_version": 3,
        "stitch_boundary_policy": "local_interval_midpoint_distinct_repeated_start_or_retry",
        "window_coverage_contract_version": 2,
        "window_coverage_policy": "rewind_overlap_then_exclude_lexically_unconfirmed_final_vad_tail",
        "vad_threshold": 0.15,
        "vad_min_speech_duration_ms": 0,
        "vad_min_silence_duration_ms": 100,
        "vad_speech_pad_ms": 600,
        "max_new_tokens": 400,
        "temperature_fallback": True,
        "hallucination_mitigation": True,
        "dubbing_ready_contract_version": 1,
        "acoustic_event_policy": "exact_snapshot_tokenizer_labels_removed",
        "filler_normalization": {"[UM]": "um", "[UH]": "uh"},
        "unknown_bracket_policy": "preserve_and_report",
        "raw_result_artifact": "crisperwhisper2_medium_raw.json",
        "dubbing_ready_result_artifact": "crisperwhisper2_medium_dubbing_ready.json",
        "quality_failure_schema_version": CRISPERWHISPER_QUALITY_FAILURE_SCHEMA_VERSION,
        "quality_failure_artifact": CRISPERWHISPER_QUALITY_FAILURE_ARTIFACT,
        "timed_repetition_contract_version": CRISPERWHISPER_TIMED_REPETITION_CONTRACT_VERSION,
        "timed_repetition_policy": CRISPERWHISPER_TIMED_REPETITION_POLICY,
        "cpu_fallback": False,
        "synthetic_tests": False,
        "real_physical_audio_required": True,
    }
    mismatches = {
        key: {"expected": value, "actual": profile.get(key)}
        for key, value in expected.items()
        if profile.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"CrisperWhisper runtime profili kanonik degil: {mismatches}")
    return profile


def crisperwhisper_contract_inputs() -> dict[str, Any]:
    profile = load_crisperwhisper_runtime_profile()
    source_identity = crisperwhisper_source_identity()
    return {
        "crisperwhisper_runtime_contract_version": CRISPERWHISPER_RUNTIME_CONTRACT_VERSION,
        "crisperwhisper_profile_schema_version": CRISPERWHISPER_PROFILE_SCHEMA_VERSION,
        "crisperwhisper_model_repo": profile["model_repo"],
        "crisperwhisper_model_snapshot_id": profile["model_snapshot_id"],
        "crisperwhisper_backend": profile["backend"],
        "crisperwhisper_device": profile["device"],
        "crisperwhisper_compute_type": profile["compute_type"],
        "crisperwhisper_runtime_optimization_id": profile[
            "runtime_optimization_id"
        ],
        "crisperwhisper_mode": profile["mode"],
        "crisperwhisper_language": profile["language"],
        "crisperwhisper_api_schema_version": CRISPERWHISPER_API_SCHEMA_VERSION,
        "crisperwhisper_language_detection_contract_version": CRISPERWHISPER_LANGUAGE_DETECTION_CONTRACT_VERSION,
        "crisperwhisper_language_detection_modes": sorted(
            CRISPERWHISPER_LANGUAGE_DETECTION_MODES
        ),
        "crisperwhisper_language_detection_window_seconds": float(profile["maximum_window_seconds"]),
        "crisperwhisper_continuous_language_context_seconds": float(
            profile["continuous_language_context_seconds"]
        ),
        "crisperwhisper_continuous_language_tick_seconds": float(
            profile["continuous_language_tick_seconds"]
        ),
        "crisperwhisper_continuous_language_confirmation_ticks": int(
            profile["continuous_language_confirmation_ticks"]
        ),
        "crisperwhisper_continuous_language_min_top_probability": float(
            profile["continuous_language_min_top_probability"]
        ),
        "crisperwhisper_continuous_language_min_margin": float(
            profile["continuous_language_min_margin"]
        ),
        "crisperwhisper_continuous_language_boundary_policy": profile[
            "continuous_language_boundary_policy"
        ],
        "crisperwhisper_word_timestamps": bool(profile["word_timestamps"]),
        "crisperwhisper_longform_strategy": profile["longform_strategy"],
        "crisperwhisper_default_longform_strategy": profile["default_longform_strategy"],
        "crisperwhisper_no_space_longform_strategy": profile["no_space_longform_strategy"],
        "crisperwhisper_no_space_language_codes": list(profile["no_space_language_codes"]),
        "crisperwhisper_no_space_chunk_duration_seconds": float(
            profile["no_space_chunk_duration_seconds"]
        ),
        "crisperwhisper_no_space_stride_seconds": float(profile["no_space_stride_seconds"]),
        "crisperwhisper_no_space_context_groups": int(profile["no_space_context_groups"]),
        "crisperwhisper_no_space_context_budget_policy": profile[
            "no_space_context_budget_policy"
        ],
        "crisperwhisper_no_space_context_overflow_policy": profile[
            "no_space_context_overflow_policy"
        ],
        "crisperwhisper_no_space_expected_max_target_positions": int(
            profile["no_space_expected_max_target_positions"]
        ),
        "crisperwhisper_no_space_generation_token_reserve": int(
            profile["no_space_generation_token_reserve"]
        ),
        "crisperwhisper_no_space_max_new_tokens": int(profile["no_space_max_new_tokens"]),
        "crisperwhisper_no_space_max_uncovered_active_tail_seconds": float(
            profile["no_space_max_uncovered_active_tail_seconds"]
        ),
        "crisperwhisper_no_space_adaptive_retry_chunk_duration_seconds": float(
            profile["no_space_adaptive_retry_chunk_duration_seconds"]
        ),
        "crisperwhisper_no_space_adaptive_retry_overlap_seconds": float(
            profile["no_space_adaptive_retry_overlap_seconds"]
        ),
        "crisperwhisper_no_space_adaptive_retry_stride_seconds": float(
            profile["no_space_adaptive_retry_stride_seconds"]
        ),
        "crisperwhisper_no_space_adaptive_retry_policy": profile[
            "no_space_adaptive_retry_policy"
        ],
        "crisperwhisper_no_space_overlap_suffix_recovery_policy": profile[
            "no_space_overlap_suffix_recovery_policy"
        ],
        "crisperwhisper_no_space_plain_consensus_temperature": float(
            profile["no_space_plain_consensus_temperature"]
        ),
        "crisperwhisper_no_space_plain_consensus_seed_count": int(
            profile["no_space_plain_consensus_seed_count"]
        ),
        "crisperwhisper_no_space_plain_consensus_minimum_fraction": float(
            profile["no_space_plain_consensus_minimum_fraction"]
        ),
        "crisperwhisper_no_space_intended_consensus_seed_count": int(
            profile["no_space_intended_consensus_seed_count"]
        ),
        "crisperwhisper_no_space_intended_consensus_seeds": list(
            profile["no_space_intended_consensus_seeds"]
        ),
        "crisperwhisper_no_space_intended_consensus_batch_size": int(
            profile["no_space_intended_consensus_batch_size"]
        ),
        "crisperwhisper_no_space_intended_consensus_temperature": float(
            profile["no_space_intended_consensus_temperature"]
        ),
        "crisperwhisper_no_space_intended_consensus_minimum_candidates": int(
            profile["no_space_intended_consensus_minimum_candidates"]
        ),
        "crisperwhisper_no_space_intended_consensus_maximum_token_density": float(
            profile["no_space_intended_consensus_maximum_token_density"]
        ),
        "crisperwhisper_no_space_intended_consensus_policy": profile[
            "no_space_intended_consensus_policy"
        ],
        "crisperwhisper_no_space_token_decode_policy": profile["no_space_token_decode_policy"],
        "crisperwhisper_no_space_coverage_count_mode": profile[
            "no_space_coverage_count_mode"
        ],
        "crisperwhisper_no_space_fallback_policy": profile["no_space_fallback_policy"],
        "crisperwhisper_no_space_loop_recovery_policy": profile[
            "no_space_loop_recovery_policy"
        ],
        "crisperwhisper_no_space_min_speech_seconds": float(
            profile["no_space_min_speech_seconds"]
        ),
        "crisperwhisper_no_space_min_content_tokens_per_active_second": float(
            profile["no_space_min_content_tokens_per_active_second"]
        ),
        "crisperwhisper_no_space_min_sibling_content_tokens": int(
            profile["no_space_min_sibling_content_tokens"]
        ),
        "crisperwhisper_target_window_seconds": float(profile["target_window_seconds"]),
        "crisperwhisper_maximum_window_seconds": float(profile["maximum_window_seconds"]),
        "crisperwhisper_minimum_window_seconds": float(profile["minimum_window_seconds"]),
        "crisperwhisper_inference_window_timestamp_tolerance_seconds": float(
            profile["inference_window_timestamp_tolerance_seconds"]
        ),
        "crisperwhisper_inference_window_timestamp_policy": profile[
            "inference_window_timestamp_policy"
        ],
        "crisperwhisper_compact_seam_tolerance_seconds": float(
            profile["compact_seam_tolerance_seconds"]
        ),
        "crisperwhisper_compact_seam_policy": profile["compact_seam_policy"],
        "crisperwhisper_minimum_overlap_seconds": float(profile["minimum_overlap_seconds"]),
        "crisperwhisper_maximum_overlap_seconds": float(profile["maximum_overlap_seconds"]),
        "crisperwhisper_minimum_anchor_words": int(profile["minimum_anchor_words"]),
        "crisperwhisper_stitch_boundary_contract_version": int(profile["stitch_boundary_contract_version"]),
        "crisperwhisper_stitch_boundary_policy": profile["stitch_boundary_policy"],
        "crisperwhisper_window_coverage_contract_version": int(
            profile["window_coverage_contract_version"]
        ),
        "crisperwhisper_window_coverage_policy": profile["window_coverage_policy"],
        "crisperwhisper_vad_threshold": float(profile["vad_threshold"]),
        "crisperwhisper_vad_min_speech_duration_ms": int(profile["vad_min_speech_duration_ms"]),
        "crisperwhisper_vad_min_silence_duration_ms": int(profile["vad_min_silence_duration_ms"]),
        "crisperwhisper_vad_speech_pad_ms": int(profile["vad_speech_pad_ms"]),
        "crisperwhisper_max_new_tokens": int(profile["max_new_tokens"]),
        "crisperwhisper_temperature_fallback": bool(profile["temperature_fallback"]),
        "crisperwhisper_hallucination_mitigation": bool(profile["hallucination_mitigation"]),
        "crisperwhisper_dubbing_ready_contract_version": int(
            profile["dubbing_ready_contract_version"]
        ),
        "crisperwhisper_acoustic_event_policy": profile["acoustic_event_policy"],
        "crisperwhisper_filler_normalization": dict(profile["filler_normalization"]),
        "crisperwhisper_unknown_bracket_policy": profile["unknown_bracket_policy"],
        "crisperwhisper_raw_result_artifact": profile["raw_result_artifact"],
        "crisperwhisper_dubbing_ready_result_artifact": profile[
            "dubbing_ready_result_artifact"
        ],
        "crisperwhisper_quality_failure_schema_version": int(
            profile["quality_failure_schema_version"]
        ),
        "crisperwhisper_quality_failure_artifact": profile[
            "quality_failure_artifact"
        ],
        "crisperwhisper_timed_repetition_contract_version": int(
            profile["timed_repetition_contract_version"]
        ),
        "crisperwhisper_timed_repetition_policy": profile[
            "timed_repetition_policy"
        ],
        "crisperwhisper_continuation": profile["no_space_longform_strategy"] == "continuation",
        "crisperwhisper_reference_text_used": False,
        "crisperwhisper_transcript_source_sha256": source_identity["src/crisperwhisper2_medium_transkript.py"],
        "crisperwhisper_normalization_source_sha256": source_identity["src/transcript_normalization.py"],
        "crisperwhisper_longform_source_sha256": source_identity["src/crisperwhisper_longform.py"],
        "crisperwhisper_no_space_languages_source_sha256": source_identity[
            "src/crisperwhisper_no_space_languages.py"
        ],
        "crisperwhisper_dubbing_ready_source_sha256": source_identity[
            "src/crisperwhisper_dubbing_ready.py"
        ],
        "crisperwhisper_api_service_source_sha256": source_identity["src/crisperwhisper_api_service.py"],
        "crisperwhisper_model_snapshot_manifest_sha256": source_identity[
            "src/configs/model_snapshot_manifest.json"
        ],
        "crisperwhisper_cpu_fallback": bool(profile["cpu_fallback"]),
    }


def _write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _verify_dubbing_ready_artifact_hashes(output_dir: Path, data: dict[str, Any]) -> None:
    if not data.get("success"):
        return
    artifacts = dict(data.get("artifacts") or {})
    expected_paths = {
        "raw_result_path": "crisperwhisper2_medium_raw.json",
        "dubbing_ready_result_path": "crisperwhisper2_medium_dubbing_ready.json",
        "transcription_profile_path": "transcription_profile_crisperwhisper2_medium.json",
        "language_detection_artifact_path": "crisperwhisper2_medium_language_detection.json",
        "language_detection_profile_path": "language_detection_profile_crisperwhisper2_medium.json",
    }
    resolved_paths: dict[str, Path] = {}
    for key, expected_name in expected_paths.items():
        if str(artifacts.get(key) or "") != expected_name:
            raise RuntimeError(f"CrisperWhisper API artefakt yolu gecersiz: {key}")
        artifact_path = (output_dir / expected_name).resolve()
        if artifact_path.parent != output_dir or not artifact_path.is_file():
            raise RuntimeError(f"CrisperWhisper API artefakti bulunamadi: {expected_name}")
        resolved_paths[key] = artifact_path
    profile = json.loads(
        resolved_paths["transcription_profile_path"].read_text(encoding="utf-8")
    )
    expected_hashes = {
        "raw_result_path": str(profile.get("raw_result_sha256") or ""),
        "dubbing_ready_result_path": str(profile.get("dubbing_ready_result_sha256") or ""),
        "language_detection_artifact_path": str(
            profile.get("language_detection_artifact_sha256") or ""
        ),
        "language_detection_profile_path": str(
            profile.get("language_detection_profile_sha256") or ""
        ),
    }
    for key, expected_hash in expected_hashes.items():
        if len(expected_hash) != 64 or _sha256_file(resolved_paths[key]) != expected_hash:
            raise RuntimeError(f"CrisperWhisper API artefakt hash gecersiz: {key}")


def invoke_crisperwhisper_api(
    audio_path: str | Path,
    run_dir: str | Path,
    language_detection_mode: str = CRISPERWHISPER_GLOBAL_FIRST_WINDOW_LANGUAGE_MODE,
    platform_language: str = "",
    timeout_seconds: int = 2700,
) -> tuple[dict[str, Any], subprocess.CompletedProcess[str]]:
    selected_language_mode = str(language_detection_mode or "").strip()
    if selected_language_mode not in CRISPERWHISPER_LANGUAGE_DETECTION_MODES:
        raise ValueError(
            "CrisperWhisper dil tespit modu gecersiz: "
            f"{selected_language_mode!r}"
        )
    output_dir = Path(run_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = load_crisperwhisper_runtime_profile()
    request_path = output_dir / "crisperwhisper2_medium_api_request.json"
    response_path = output_dir / "crisperwhisper2_medium_dubbing_ready.json"
    request = {
        "schema_version": CRISPERWHISPER_API_SCHEMA_VERSION,
        "runtime_contract_version": CRISPERWHISPER_RUNTIME_CONTRACT_VERSION,
        "operation": "transcribe",
        "language_detection_mode": selected_language_mode,
        "platform_language": str(platform_language or "").strip().lower(),
        "audio_path": str(Path(audio_path).resolve()),
        "output_dir": str(output_dir),
        "model_snapshot": str(resolve_crisperwhisper_model_snapshot()),
        "vad_model_path": str(resolve_crisperwhisper_vad_model()),
        "profile": profile,
    }
    _write_json_atomic(request_path, request)
    command = [
        str(resolve_crisperwhisper_python()),
        str(resolve_crisperwhisper_api_script()),
        "--request",
        str(request_path),
        "--response",
        str(response_path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        encoding="utf-8",
        errors="replace",
        env=build_crisperwhisper_subprocess_env(),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if not response_path.is_file():
        raise RuntimeError(
            "CrisperWhisper deney API yaniti uretilmedi: "
            f"returncode={completed.returncode}, stderr={(completed.stderr or '')[-4000:]}"
        )
    data = json.loads(response_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("CrisperWhisper deney API yaniti nesne degil")
    _verify_dubbing_ready_artifact_hashes(output_dir, data)
    return data, completed


def build_crisperwhisper_subprocess_env() -> dict[str, str]:
    root = crisperwhisper_root()
    cache_root = root / "model_cache"
    huggingface_root = cache_root / "huggingface"
    env = os.environ.copy()
    env["CRISPERWHISPER_EXPERIMENT_ROOT"] = str(root)
    env["HF_HOME"] = str(huggingface_root)
    env["HF_HUB_CACHE"] = str(huggingface_root / "hub")
    env["TRANSFORMERS_CACHE"] = str(huggingface_root / "transformers")
    env["TORCH_HOME"] = str(cache_root / "torch")
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env
