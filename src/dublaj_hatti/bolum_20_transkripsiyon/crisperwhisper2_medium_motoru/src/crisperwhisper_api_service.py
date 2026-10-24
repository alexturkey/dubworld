from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import sys
import time
import traceback
from pathlib import Path

import soundfile as sf

from crisperwhisper2_medium_transkript import model_runtime_evidence, package_version, word_value
from crisperwhisper_dubbing_ready import (
    ACOUSTIC_EVENT_LABELS,
    DUBBING_READY_CONTRACT_VERSION,
    DUBBING_READY_RESULT_ARTIFACT_NAME,
    FILLER_NORMALIZATION,
    RAW_RESULT_ARTIFACT_NAME,
    build_dubbing_ready_result,
    join_timed_word_text,
    load_acoustic_event_contract,
)
from crisperwhisper_longform import (
    SAMPLE_RATE,
    annotate_window_coverage,
    build_compact_timeline,
    classify_lexically_unconfirmed_final_tail,
    classify_timed_repetitions,
    choose_window_end,
    compact_time_to_original,
    detect_speech_regions,
    load_silero_model,
    map_words_to_original,
    natural_boundary_seconds,
    overlap_candidates,
    pathological_repetitions,
    reconcile_compact_seam_crossings,
    stitch_with_anchor,
    transcribe_window,
    word_timing_errors,
)
from crisperwhisper_no_space_languages import (
    CrisperWhisperNoSpaceDiagnosticError,
    DEFAULT_LONGFORM_ROUTE,
    NO_SPACE_ADAPTIVE_RETRY_CHUNK_DURATION_SECONDS,
    NO_SPACE_ADAPTIVE_RETRY_OVERLAP_SECONDS,
    NO_SPACE_ADAPTIVE_RETRY_POLICY,
    NO_SPACE_ADAPTIVE_RETRY_STRIDE_SECONDS,
    NO_SPACE_CHUNK_DURATION_SECONDS,
    NO_SPACE_CONTEXT_BUDGET_POLICY,
    NO_SPACE_CONTEXT_GROUPS,
    NO_SPACE_CONTEXT_OVERFLOW_POLICY,
    NO_SPACE_COVERAGE_COUNT_MODE,
    NO_SPACE_EXPECTED_MAX_TARGET_POSITIONS,
    NO_SPACE_FALLBACK_POLICY,
    NO_SPACE_INTENDED_CONSENSUS_MAXIMUM_TOKEN_DENSITY,
    NO_SPACE_INTENDED_CONSENSUS_MINIMUM_CANDIDATES,
    NO_SPACE_INTENDED_CONSENSUS_POLICY,
    NO_SPACE_INTENDED_CONSENSUS_SEED_COUNT,
    NO_SPACE_INTENDED_CONSENSUS_SEEDS,
    NO_SPACE_INTENDED_CONSENSUS_TEMPERATURE,
    NO_SPACE_LANGUAGE_CODES,
    NO_SPACE_LONGFORM_ROUTE,
    NO_SPACE_LOOP_RECOVERY_POLICY,
    NO_SPACE_MAX_NEW_TOKENS,
    NO_SPACE_MAX_UNCOVERED_ACTIVE_TAIL_SECONDS,
    NO_SPACE_MIN_CONTENT_TOKENS_PER_ACTIVE_SECOND,
    NO_SPACE_MIN_SIBLING_CONTENT_TOKENS,
    NO_SPACE_MIN_SPEECH_SECONDS,
    NO_SPACE_OVERLAP_SUFFIX_RECOVERY_POLICY,
    NO_SPACE_PLAIN_CONSENSUS_MINIMUM_FRACTION,
    NO_SPACE_PLAIN_CONSENSUS_SEED_COUNT,
    NO_SPACE_PLAIN_CONSENSUS_TEMPERATURE,
    NO_SPACE_STRIDE_SECONDS,
    NO_SPACE_TOKEN_DECODE_POLICY,
    select_longform_route,
    transcribe_no_space_language,
)
from crisperwhisper_runtime_optimization import (
    OPTION12_RUNTIME_OPTIMIZATION_ID,
    Option12RuntimeOptimization,
    option12_language_route,
)
API_SCHEMA_VERSION = 3
RUNTIME_CONTRACT_VERSION = 24
PROFILE_SCHEMA_VERSION = 20
TIMED_REPETITION_CONTRACT_VERSION = 1
TIMED_REPETITION_POLICY = "accept_strictly_increasing_occurrence_start_seconds"
QUALITY_FAILURE_SCHEMA_VERSION = 2
QUALITY_FAILURE_ARTIFACT_NAME = "crisperwhisper2_medium_quality_failure.json"
MODEL_REPO = "nyralabs/CrisperWhisper2.0_medium"
MODEL_SNAPSHOT_ID = "ca981a994a008f70b7ce343ef1e261ff7eadc1d9"
ENGINE = "crisperwhisper2_medium"
GLOBAL_FIRST_WINDOW_LANGUAGE_MODE = "global_first_window"
PER_WINDOW_LANGUAGE_MODE = "per_window"
CONTINUOUS_STREAM_LANGUAGE_MODE = "continuous_stream"
LANGUAGE_DETECTION_MODES = {
    GLOBAL_FIRST_WINDOW_LANGUAGE_MODE,
    PER_WINDOW_LANGUAGE_MODE,
    CONTINUOUS_STREAM_LANGUAGE_MODE,
}
RESULT_PREFIX = "CRISPER_API_JSON="
EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]


class CrisperWhisperQualityGateError(RuntimeError):
    def __init__(self, message: str, artifact_name: str):
        super().__init__(message)
        self.artifact_name = artifact_name


class CrisperWhisperDiagnosticError(RuntimeError):
    def __init__(self, message: str, diagnostic: dict):
        super().__init__(message)
        self.artifact_name = QUALITY_FAILURE_ARTIFACT_NAME
        self.diagnostic = diagnostic


def configure_cache() -> None:
    cache_root = EXPERIMENT_ROOT / "model_cache"
    huggingface_root = cache_root / "huggingface"
    for path in (
        huggingface_root,
        huggingface_root / "hub",
        huggingface_root / "transformers",
        cache_root / "torch",
    ):
        path.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(huggingface_root)
    os.environ["HF_HUB_CACHE"] = str(huggingface_root / "hub")
    os.environ["TRANSFORMERS_CACHE"] = str(huggingface_root / "transformers")
    os.environ["TORCH_HOME"] = str(cache_root / "torch")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def load_signal(path: Path):
    info = sf.info(str(path))
    if info.samplerate != SAMPLE_RATE or info.channels != 1 or info.subtype != "PCM_16":
        raise RuntimeError(f"Expected real 16 kHz mono PCM16 WAV: {path}")
    signal, sample_rate = sf.read(str(path), dtype="float32", always_2d=False)
    if sample_rate != SAMPLE_RATE or signal.ndim != 1:
        raise RuntimeError(f"Unexpected decoded real audio shape/rate: {signal.shape} {sample_rate}")
    return signal, sample_rate


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def diagnose_local_model_snapshot(snapshot: Path) -> list[dict]:
    manifest_path = Path(__file__).resolve().parent / "configs" / "model_snapshot_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        int(manifest.get("schema_version") or 0) != 1
        or manifest.get("model_repo") != MODEL_REPO
        or manifest.get("model_snapshot_id") != MODEL_SNAPSHOT_ID
        or manifest.get("load_policy")
        != "direct_local_first_validate_manifest_only_after_load_failure"
        or manifest.get("known_compatible_extra_weight_keys")
        != ["encoder_blank_head.bias", "encoder_blank_head.weight"]
    ):
        raise RuntimeError("CrisperWhisper local model manifest is not canonical")
    problems = []
    for relative_path, expected in dict(manifest.get("files") or {}).items():
        model_path = snapshot / relative_path
        if not model_path.is_file():
            problems.append({"path": relative_path, "problem": "missing"})
            continue
        actual_size = model_path.stat().st_size
        expected_size = int(expected.get("size_bytes") or -1)
        if actual_size != expected_size:
            problems.append(
                {
                    "path": relative_path,
                    "problem": "size_mismatch",
                    "expected_size_bytes": expected_size,
                    "actual_size_bytes": actual_size,
                }
            )
            continue
        actual_hash = sha256_file(model_path)
        expected_hash = str(expected.get("sha256") or "").lower()
        if actual_hash != expected_hash:
            problems.append({"path": relative_path, "problem": "sha256_mismatch"})
    return problems


def write_exception_diagnostic(request: dict, error: Exception, traceback_text: str) -> str:
    output_value = request.get("output_dir")
    if not isinstance(output_value, str) or not output_value.strip():
        return ""
    output_dir = Path(output_value).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnostic_path = output_dir / QUALITY_FAILURE_ARTIFACT_NAME
    if diagnostic_path.is_file() and isinstance(error, CrisperWhisperQualityGateError):
        return QUALITY_FAILURE_ARTIFACT_NAME
    audio_value = str(request.get("audio_path") or "")
    diagnostic = dict(getattr(error, "diagnostic", {}) or {})
    failure_phase = str(diagnostic.pop("failure_phase", "api_execution"))
    failure_type = str(diagnostic.pop("failure_type", type(error).__name__))
    payload = {
        "schema_version": QUALITY_FAILURE_SCHEMA_VERSION,
        "artifact_type": "crisperwhisper_quality_failure",
        "success": False,
        "engine": ENGINE,
        "api_schema_version": API_SCHEMA_VERSION,
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "model_repo": MODEL_REPO,
        "model_snapshot_id": MODEL_SNAPSHOT_ID,
        "failure_phase": failure_phase,
        "failure_type": failure_type,
        "error": {
            "class": type(error).__name__,
            "message": str(error),
            "traceback": traceback_text,
        },
        "request_context": {
            "operation": request.get("operation"),
            "language_detection_mode": request.get("language_detection_mode"),
            "platform_language": request.get("platform_language"),
            "audio_path": audio_value,
            "audio_name": Path(audio_value).name if audio_value else "",
        },
        "diagnostic": diagnostic,
    }
    write_json(diagnostic_path, payload)
    return QUALITY_FAILURE_ARTIFACT_NAME


def read_request(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("CrisperWhisper API request must be an object")
    return value


def require_exact_request(request: dict) -> dict:
    if int(request.get("schema_version") or 0) != API_SCHEMA_VERSION:
        raise RuntimeError("Unsupported CrisperWhisper API request schema")
    if int(request.get("runtime_contract_version") or 0) != RUNTIME_CONTRACT_VERSION:
        raise RuntimeError("Unsupported CrisperWhisper runtime contract")
    if request.get("operation") != "transcribe":
        raise RuntimeError("CrisperWhisper API only accepts operation=transcribe")
    language_detection_mode = str(request.get("language_detection_mode") or "")
    if language_detection_mode not in LANGUAGE_DETECTION_MODES:
        raise RuntimeError(
            "Unsupported CrisperWhisper language detection mode: "
            f"{language_detection_mode!r}"
        )
    platform_language = request.get("platform_language")
    if not isinstance(platform_language, str) or (
        platform_language and not re.fullmatch(r"[a-z]{2,3}", platform_language)
    ):
        raise RuntimeError("Unsupported CrisperWhisper platform language")
    profile = dict(request.get("profile") or {})
    expected = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "model_repo": MODEL_REPO,
        "model_snapshot_id": MODEL_SNAPSHOT_ID,
        "backend": "transformers",
        "device": "cuda",
        "compute_type": "float16",
        "runtime_optimization_id": OPTION12_RUNTIME_OPTIMIZATION_ID,
        "mode": "verbatim",
        "language": "platform_or_detected_by_crisper_language_id",
        "platform_language_policy": "global_first_window_prefer_valid_platform_else_detect_continuous_evidence_only",
        "word_timestamps": True,
        "longform_strategy": "detected_language_route",
        "default_longform_strategy": "silero_vad_compact_timeline_dynamic_overlap_stitch",
        "no_space_longform_strategy": NO_SPACE_LONGFORM_ROUTE,
        "no_space_language_codes": sorted(NO_SPACE_LANGUAGE_CODES),
        "no_space_chunk_duration_seconds": NO_SPACE_CHUNK_DURATION_SECONDS,
        "no_space_stride_seconds": NO_SPACE_STRIDE_SECONDS,
        "no_space_context_groups": NO_SPACE_CONTEXT_GROUPS,
        "no_space_context_budget_policy": NO_SPACE_CONTEXT_BUDGET_POLICY,
        "no_space_context_overflow_policy": NO_SPACE_CONTEXT_OVERFLOW_POLICY,
        "no_space_expected_max_target_positions": NO_SPACE_EXPECTED_MAX_TARGET_POSITIONS,
        "no_space_generation_token_reserve": NO_SPACE_MAX_NEW_TOKENS,
        "no_space_max_new_tokens": NO_SPACE_MAX_NEW_TOKENS,
        "no_space_max_uncovered_active_tail_seconds": (
            NO_SPACE_MAX_UNCOVERED_ACTIVE_TAIL_SECONDS
        ),
        "no_space_adaptive_retry_chunk_duration_seconds": (
            NO_SPACE_ADAPTIVE_RETRY_CHUNK_DURATION_SECONDS
        ),
        "no_space_adaptive_retry_overlap_seconds": (
            NO_SPACE_ADAPTIVE_RETRY_OVERLAP_SECONDS
        ),
        "no_space_adaptive_retry_stride_seconds": (
            NO_SPACE_ADAPTIVE_RETRY_STRIDE_SECONDS
        ),
        "no_space_adaptive_retry_policy": NO_SPACE_ADAPTIVE_RETRY_POLICY,
        "no_space_overlap_suffix_recovery_policy": (
            NO_SPACE_OVERLAP_SUFFIX_RECOVERY_POLICY
        ),
        "no_space_plain_consensus_temperature": (
            NO_SPACE_PLAIN_CONSENSUS_TEMPERATURE
        ),
        "no_space_plain_consensus_seed_count": (
            NO_SPACE_PLAIN_CONSENSUS_SEED_COUNT
        ),
        "no_space_plain_consensus_minimum_fraction": (
            NO_SPACE_PLAIN_CONSENSUS_MINIMUM_FRACTION
        ),
        "no_space_intended_consensus_seed_count": (
            NO_SPACE_INTENDED_CONSENSUS_SEED_COUNT
        ),
        "no_space_intended_consensus_seeds": list(
            NO_SPACE_INTENDED_CONSENSUS_SEEDS
        ),
        "no_space_intended_consensus_batch_size": len(
            NO_SPACE_INTENDED_CONSENSUS_SEEDS
        ),
        "no_space_intended_consensus_temperature": (
            NO_SPACE_INTENDED_CONSENSUS_TEMPERATURE
        ),
        "no_space_intended_consensus_minimum_candidates": (
            NO_SPACE_INTENDED_CONSENSUS_MINIMUM_CANDIDATES
        ),
        "no_space_intended_consensus_maximum_token_density": (
            NO_SPACE_INTENDED_CONSENSUS_MAXIMUM_TOKEN_DENSITY
        ),
        "no_space_intended_consensus_policy": NO_SPACE_INTENDED_CONSENSUS_POLICY,
        "no_space_token_decode_policy": NO_SPACE_TOKEN_DECODE_POLICY,
        "no_space_coverage_count_mode": NO_SPACE_COVERAGE_COUNT_MODE,
        "no_space_fallback_policy": NO_SPACE_FALLBACK_POLICY,
        "no_space_loop_recovery_policy": NO_SPACE_LOOP_RECOVERY_POLICY,
        "no_space_min_speech_seconds": NO_SPACE_MIN_SPEECH_SECONDS,
        "no_space_min_content_tokens_per_active_second": (
            NO_SPACE_MIN_CONTENT_TOKENS_PER_ACTIVE_SECOND
        ),
        "no_space_min_sibling_content_tokens": NO_SPACE_MIN_SIBLING_CONTENT_TOKENS,
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
        "dubbing_ready_contract_version": DUBBING_READY_CONTRACT_VERSION,
        "acoustic_event_policy": "exact_snapshot_tokenizer_labels_removed",
        "filler_normalization": FILLER_NORMALIZATION,
        "unknown_bracket_policy": "preserve_and_report",
        "raw_result_artifact": RAW_RESULT_ARTIFACT_NAME,
        "dubbing_ready_result_artifact": DUBBING_READY_RESULT_ARTIFACT_NAME,
        "quality_failure_schema_version": QUALITY_FAILURE_SCHEMA_VERSION,
        "quality_failure_artifact": QUALITY_FAILURE_ARTIFACT_NAME,
        "timed_repetition_contract_version": TIMED_REPETITION_CONTRACT_VERSION,
        "timed_repetition_policy": TIMED_REPETITION_POLICY,
        "cpu_fallback": False,
    }
    mismatches = {
        key: {"expected": expected_value, "actual": profile.get(key)}
        for key, expected_value in expected.items()
        if profile.get(key) != expected_value
    }
    if mismatches:
        raise RuntimeError(f"CrisperWhisper API profile is not canonical: {mismatches}")
    return profile


def language_scores(model, torch, signal) -> tuple[str, list[dict], list[str]]:
    engine = getattr(model, "_engine", None)
    language_ids = getattr(engine, "_lang_ids", None)
    model_module = getattr(engine, "model", None)
    start_token_id = getattr(engine, "sot_id", None)
    if not isinstance(language_ids, dict) or not language_ids:
        raise RuntimeError("CrisperWhisper accepted language id map is unavailable")
    if model_module is None or start_token_id is None:
        raise RuntimeError("CrisperWhisper language detection primitives are unavailable")
    features = engine.extract_features(signal)
    decoder_input_ids = torch.tensor(
        [[int(start_token_id)]],
        device=features.device,
        dtype=torch.long,
    )
    with torch.no_grad():
        output = model_module(
            input_features=features,
            decoder_input_ids=decoder_input_ids,
            use_cache=False,
        )
    logits = output.logits[0, -1].float()
    languages = list(language_ids)
    token_tensor = torch.tensor(
        [int(language_ids[language]) for language in languages],
        device=logits.device,
        dtype=torch.long,
    )
    probabilities = torch.softmax(logits[token_tensor], dim=0).detach().cpu().tolist()
    candidates = sorted(
        [
            {
                "language": language,
                "token_id": int(language_ids[language]),
                "probability": float(probability),
            }
            for language, probability in zip(languages, probabilities)
        ],
        key=lambda item: item["probability"],
        reverse=True,
    )
    if not candidates:
        raise RuntimeError("CrisperWhisper language detection returned no candidate")
    return str(candidates[0]["language"]), candidates[:10], sorted(str(value) for value in languages)


def platform_language_evidence(model, language: str) -> tuple[list[dict], list[str]]:
    engine = getattr(model, "_engine", None)
    language_ids = getattr(engine, "_lang_ids", None)
    if not isinstance(language_ids, dict) or not language_ids:
        raise RuntimeError("CrisperWhisper accepted language id map is unavailable")
    language_id = engine.get_language_id(language)
    if language_id is None:
        raise RuntimeError(f"CrisperWhisper platform language is not accepted: {language!r}")
    return [
        {
            "language": language,
            "token_id": int(language_id),
            "probability": 1.0,
            "source": "platform_metadata",
        }
    ], sorted(str(value) for value in language_ids)


def window_summary(window: dict) -> dict:
    return {
        key: window[key]
        for key in (
            "window_index",
            "attempt_index",
            "start_seconds",
            "end_seconds",
            "duration_seconds",
            "processing_seconds",
            "word_count",
            "timestamp_repair_count",
            "timestamp_repairs",
            "timestamp_drop_count",
            "timestamp_drops",
            "end_kind",
            "accepted",
            "coverage_status",
            "coverage_last_word_end_seconds",
            "coverage_tail_gap_seconds",
            "coverage_tail_limit_seconds",
            "advance_end_seconds",
        )
        if key in window
    }


def longform_failure(
    message: str,
    failure_type: str,
    language: str,
    duration_seconds: float,
    attempts: list[dict],
    accepted_windows: list[dict],
    transitions: list[dict],
    local_compact_second: float,
    window_index: int,
    **details,
) -> CrisperWhisperDiagnosticError:
    return CrisperWhisperDiagnosticError(
        message,
        {
            "failure_phase": "longform_windowing",
            "failure_type": failure_type,
            "detected_language": language,
            "window_index": window_index,
            "local_compact_second": local_compact_second,
            "run_duration_seconds": duration_seconds,
            "attempts_before_failure": attempts,
            "accepted_windows_before_failure": [
                window_summary(window) for window in accepted_windows
            ],
            "transitions_before_failure": transitions,
            **details,
        },
    )


def run_longform(
    model,
    compact_signal,
    boundaries,
    language: str,
    profile: dict,
    allow_lexically_unconfirmed_final_tail: bool = True,
) -> tuple[list[dict], list[dict], dict]:
    duration_seconds = len(compact_signal) / SAMPLE_RATE
    target_seconds = float(profile["target_window_seconds"])
    maximum_seconds = float(profile["maximum_window_seconds"])
    minimum_seconds = float(profile["minimum_window_seconds"])
    timestamp_tolerance = float(profile["inference_window_timestamp_tolerance_seconds"])
    minimum_overlap = float(profile["minimum_overlap_seconds"])
    maximum_overlap = float(profile["maximum_overlap_seconds"])
    max_new_tokens = int(profile["max_new_tokens"])
    accepted_windows = []
    attempts = []
    transitions = []
    pending_bridge = None

    first_end, first_kind = choose_window_end(
        0.0,
        duration_seconds,
        boundaries,
        target_seconds,
        maximum_seconds,
        minimum_seconds,
    )
    first = transcribe_window(
        model,
        compact_signal,
        0.0,
        first_end,
        language,
        max_new_tokens,
        word_value,
        0,
        0,
        timestamp_tolerance,
    )
    first.update({"end_kind": first_kind, "accepted": bool(first["words"])})
    annotate_window_coverage(first)
    attempts.append(window_summary(first))
    if not first["words"]:
        raise longform_failure(
            "CrisperWhisper first speech window returned no words",
            "empty_first_speech_window",
            language,
            duration_seconds,
            attempts,
            accepted_windows,
            transitions,
            0.0,
            0,
        )
    accepted_windows.append(first)
    merged_words = list(first["words"])
    previous = first

    while float(previous["advance_end_seconds"] or 0.0) < duration_seconds - 1e-6:
        bridge_to_validate = pending_bridge
        seam = float(previous["advance_end_seconds"] or 0.0)
        window_index = len(accepted_windows)
        if (
            previous["end_kind"] == "vad_silence_boundary"
            and previous["coverage_status"] == "complete"
        ):
            end_seconds, end_kind = choose_window_end(
                seam,
                duration_seconds,
                boundaries,
                target_seconds,
                maximum_seconds,
                minimum_seconds,
            )
            current = transcribe_window(
                model,
                compact_signal,
                seam,
                end_seconds,
                language,
                max_new_tokens,
                word_value,
                window_index,
                0,
                timestamp_tolerance,
            )
            current.update({"end_kind": end_kind, "accepted": bool(current["words"])})
            annotate_window_coverage(current)
            attempts.append(window_summary(current))
            if not current["words"]:
                raise longform_failure(
                    f"CrisperWhisper VAD speech window returned no words: {window_index}",
                    "empty_vad_speech_window",
                    language,
                    duration_seconds,
                    attempts,
                    accepted_windows,
                    transitions,
                    seam,
                    window_index,
                )
            if float(current["advance_end_seconds"] or 0.0) <= seam + 0.01:
                raise longform_failure(
                    f"CrisperWhisper window coverage recovery did not advance at compact second {seam:.3f}",
                    "window_coverage_recovery_did_not_advance",
                    language,
                    duration_seconds,
                    attempts,
                    accepted_windows,
                    transitions,
                    seam,
                    window_index,
                )
            merged_words.extend(current["words"])
            transition = {
                "window_index": window_index,
                "method": "vad_silence_boundary",
                "seam_seconds": seam,
                "validated": True,
                "anchor_word_count": 0,
            }
            transitions.append(transition)
            accepted_windows.append(current)
            previous = current
        else:
            accepted = None
            accepted_merge = None
            accepted_transition = None
            current_window_attempts = []
            candidates = overlap_candidates(seam, boundaries, minimum_overlap, maximum_overlap)
            for attempt_index, candidate in enumerate(candidates, start=1):
                start_seconds = float(candidate["start_seconds"])
                end_seconds, end_kind = choose_window_end(
                    start_seconds,
                    duration_seconds,
                    boundaries,
                    target_seconds,
                    maximum_seconds,
                    minimum_seconds,
                )
                if end_seconds <= seam + 0.01:
                    continue
                current = transcribe_window(
                    model,
                    compact_signal,
                    start_seconds,
                    end_seconds,
                    language,
                    max_new_tokens,
                    word_value,
                    window_index,
                    attempt_index,
                    timestamp_tolerance,
                )
                current.update({"end_kind": end_kind, "accepted": False})
                annotate_window_coverage(current)
                stitched, diagnostic = stitch_with_anchor(
                    merged_words,
                    current["words"],
                    start_seconds,
                    seam,
                )
                attempt_summary = {**window_summary(current), **diagnostic}
                attempts.append(attempt_summary)
                current_window_attempts.append(attempt_summary)
                if stitched is None:
                    continue
                if float(current["advance_end_seconds"] or 0.0) <= seam + 0.01:
                    continue
                current["accepted"] = True
                accepted = current
                accepted_merge = stitched
                accepted_transition = {
                    "window_index": window_index,
                    "method": "dynamic_overlap_stitch",
                    "seam_seconds": seam,
                    "overlap_seconds": float(candidate["overlap_seconds"]),
                    "overlap_source": candidate["source"],
                    **diagnostic,
                }
                break
            if accepted is None:
                bridge_start = max(0.0, seam - maximum_overlap)
                bridge_end = min(duration_seconds, bridge_start + maximum_seconds)
                bridge = transcribe_window(
                    model,
                    compact_signal,
                    bridge_start,
                    bridge_end,
                    language,
                    max_new_tokens,
                    word_value,
                    window_index,
                    len(candidates) + 1,
                    timestamp_tolerance,
                )
                bridge.update({"end_kind": "bridge_recovery", "accepted": False})
                annotate_window_coverage(bridge)
                stitched, diagnostic = stitch_with_anchor(
                    merged_words,
                    bridge["words"],
                    bridge_start,
                    seam,
                )
                bridge_summary = {**window_summary(bridge), **diagnostic, "bridge": True}
                attempts.append(bridge_summary)
                current_window_attempts.append(bridge_summary)
                if stitched is None:
                    error = longform_failure(
                        f"CrisperWhisper unvalidated transition at compact second {seam:.3f}",
                        "unvalidated_transition",
                        language,
                        duration_seconds,
                        attempts,
                        accepted_windows,
                        transitions,
                        seam,
                        window_index,
                        overlap_candidates=candidates,
                        failed_window_attempts=current_window_attempts,
                    )
                    error.diagnostic["failure_phase"] = "longform_stitch"
                    raise error
                if float(bridge["advance_end_seconds"] or 0.0) <= seam + 0.01:
                    tail_transition = None
                    if allow_lexically_unconfirmed_final_tail and bridge_to_validate is None:
                        tail_transition = classify_lexically_unconfirmed_final_tail(
                            current_window_attempts,
                            seam,
                            duration_seconds,
                        )
                    if tail_transition is not None:
                        for failed_attempt in current_window_attempts:
                            failed_attempt.pop("anchor_rejection_reason", None)
                            failed_attempt.pop("previous_overlap_words", None)
                            failed_attempt.pop("current_overlap_words", None)
                        transitions.append(
                            {
                                "window_index": window_index,
                                **tail_transition,
                            }
                        )
                        break
                    raise longform_failure(
                        f"CrisperWhisper window coverage recovery did not advance at compact second {seam:.3f}",
                        "bridge_coverage_recovery_did_not_advance",
                        language,
                        duration_seconds,
                        attempts,
                        accepted_windows,
                        transitions,
                        seam,
                        window_index,
                        failed_window_attempts=current_window_attempts,
                    )
                bridge["accepted"] = True
                accepted = bridge
                accepted_merge = stitched
                accepted_transition = {
                    "window_index": window_index,
                    "method": "bridge_recovery",
                    "seam_seconds": seam,
                    "overlap_seconds": seam - bridge_start,
                    "left_anchor_validated": True,
                    "right_transition_validated": bridge_end >= duration_seconds - 1e-6,
                    **diagnostic,
                }
                pending_bridge = accepted_transition if bridge_end < duration_seconds - 1e-6 else None
            for failed_attempt in current_window_attempts:
                failed_attempt.pop("anchor_rejection_reason", None)
                failed_attempt.pop("previous_overlap_words", None)
                failed_attempt.pop("current_overlap_words", None)
            transitions.append(accepted_transition)
            accepted_windows.append(accepted)
            merged_words = accepted_merge
            previous = accepted

        if bridge_to_validate is not None:
            bridge_to_validate["right_transition_validated"] = bool(transitions[-1].get("validated"))
            if not bridge_to_validate["right_transition_validated"]:
                raise longform_failure(
                    "CrisperWhisper bridge recovery could not validate its right transition",
                    "bridge_right_transition_unvalidated",
                    language,
                    duration_seconds,
                    attempts,
                    accepted_windows,
                    transitions,
                    seam,
                    window_index,
                    bridge_transition=bridge_to_validate,
                )
            if pending_bridge is bridge_to_validate:
                pending_bridge = None
        if len(accepted_windows) > 10000:
            raise longform_failure(
                "CrisperWhisper window planner exceeded its safety limit",
                "window_planner_safety_limit",
                language,
                duration_seconds,
                attempts,
                accepted_windows,
                transitions,
                seam,
                window_index,
            )

    if pending_bridge is not None:
        raise longform_failure(
            "CrisperWhisper bridge recovery ended without a right transition",
            "bridge_ended_without_right_transition",
            language,
            duration_seconds,
            attempts,
            accepted_windows,
            transitions,
            float(pending_bridge.get("seam_seconds") or duration_seconds),
            int(pending_bridge.get("window_index") or len(accepted_windows) - 1),
            bridge_transition=pending_bridge,
        )
    return merged_words, [window_summary(window) for window in accepted_windows], {"attempts": attempts, "transitions": transitions}


def plan_language_detection_windows(compact_signal, boundaries, profile: dict) -> list[dict]:
    duration_seconds = len(compact_signal) / SAMPLE_RATE
    target_seconds = float(profile["target_window_seconds"])
    maximum_seconds = float(profile["maximum_window_seconds"])
    minimum_seconds = float(profile["minimum_window_seconds"])
    windows = []
    start_seconds = 0.0
    while start_seconds < duration_seconds - 1e-6:
        end_seconds, end_kind = choose_window_end(
            start_seconds,
            duration_seconds,
            boundaries,
            target_seconds,
            maximum_seconds,
            minimum_seconds,
        )
        if end_seconds <= start_seconds + 1e-6:
            raise RuntimeError("CrisperWhisper language window planner did not advance")
        windows.append(
            {
                "window_index": len(windows),
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "duration_seconds": end_seconds - start_seconds,
                "end_kind": end_kind,
            }
        )
        start_seconds = end_seconds
        if len(windows) > 10000:
            raise RuntimeError("CrisperWhisper language window planner exceeded its safety limit")
    if not windows:
        raise RuntimeError("CrisperWhisper language window planner returned no windows")
    return windows


def detect_window_languages(model, torch, compact_signal, windows: list[dict]) -> list[dict]:
    detections = []
    for window in windows:
        start_sample = round(float(window["start_seconds"]) * SAMPLE_RATE)
        end_sample = min(
            len(compact_signal),
            round(float(window["end_seconds"]) * SAMPLE_RATE),
        )
        chunk = compact_signal[start_sample:end_sample]
        if not len(chunk):
            raise RuntimeError(
                "CrisperWhisper language detection received an empty window: "
                f"{window['window_index']}"
            )
        language, candidates, accepted_codes = language_scores(model, torch, chunk)
        if not language or model._engine.get_language_id(language) is None:
            raise RuntimeError(
                f"CrisperWhisper accepted language code required: {language!r}"
            )
        detections.append(
            {
                **dict(window),
                "detected_language": language,
                "selected_route": select_longform_route(language),
                "candidates": candidates,
                "accepted_language_codes": accepted_codes,
            }
        )
    return detections


def build_language_runs(detections: list[dict]) -> list[dict]:
    runs = []
    for detection in detections:
        language = str(detection["detected_language"])
        if runs and runs[-1]["detected_language"] == language:
            runs[-1]["end_seconds"] = float(detection["end_seconds"])
            runs[-1]["last_window_index"] = int(detection["window_index"])
            runs[-1]["window_count"] += 1
            continue
        runs.append(
            {
                "run_index": len(runs),
                "detected_language": language,
                "selected_route": str(detection["selected_route"]),
                "start_seconds": float(detection["start_seconds"]),
                "end_seconds": float(detection["end_seconds"]),
                "first_window_index": int(detection["window_index"]),
                "last_window_index": int(detection["window_index"]),
                "window_count": 1,
            }
        )
    if not runs:
        raise RuntimeError("CrisperWhisper per-window language detection returned no runs")
    return runs


def plan_continuous_language_ticks(compact_signal, profile: dict) -> list[dict]:
    duration_seconds = len(compact_signal) / SAMPLE_RATE
    context_seconds = min(
        float(profile["continuous_language_context_seconds"]),
        duration_seconds,
    )
    tick_seconds = float(profile["continuous_language_tick_seconds"])
    if context_seconds <= 0.0 or tick_seconds <= 0.0:
        raise RuntimeError("CrisperWhisper continuous language timing is invalid")
    first_center = context_seconds / 2.0
    last_center = duration_seconds - context_seconds / 2.0
    centers = []
    center = first_center
    while center <= last_center + 1e-6:
        centers.append(center)
        center += tick_seconds
        if len(centers) > 100000:
            raise RuntimeError("CrisperWhisper continuous language planner exceeded its safety limit")
    terminal_center_added = False
    if not centers:
        centers = [duration_seconds / 2.0]
    elif last_center - centers[-1] > 1e-6:
        centers.append(last_center)
        terminal_center_added = True
    ticks = []
    for index, center_value in enumerate(centers):
        ticks.append({
            "tick_index": index,
            "tick_center_seconds": float(center_value),
            "tick_kind": (
                "terminal_coverage"
                if terminal_center_added and index == len(centers) - 1
                else "regular"
            ),
            "nominal_tick_seconds": tick_seconds,
            "previous_tick_delta_seconds": (
                None
                if index == 0
                else float(center_value) - float(centers[index - 1])
            ),
            "context_start_seconds": max(0.0, float(center_value) - context_seconds / 2.0),
            "context_end_seconds": min(
                duration_seconds,
                float(center_value) + context_seconds / 2.0,
            ),
            "context_duration_seconds": context_seconds,
        })
    return ticks


def detect_continuous_languages(model, torch, compact_signal, ticks: list[dict], profile: dict) -> list[dict]:
    detections = []
    minimum_probability = float(profile["continuous_language_min_top_probability"])
    minimum_margin = float(profile["continuous_language_min_margin"])
    for tick in ticks:
        start_sample = round(float(tick["context_start_seconds"]) * SAMPLE_RATE)
        end_sample = min(
            len(compact_signal),
            round(float(tick["context_end_seconds"]) * SAMPLE_RATE),
        )
        chunk = compact_signal[start_sample:end_sample]
        if not len(chunk):
            raise RuntimeError(
                "CrisperWhisper continuous language detection received an empty tick: "
                f"{tick['tick_index']}"
            )
        started = time.perf_counter()
        language, candidates, accepted_codes = language_scores(model, torch, chunk)
        processing_seconds = time.perf_counter() - started
        if not language or model._engine.get_language_id(language) is None:
            raise RuntimeError(
                f"CrisperWhisper accepted language code required: {language!r}"
            )
        top_probability = float(candidates[0]["probability"])
        second_probability = float(candidates[1]["probability"])
        margin = top_probability - second_probability
        detections.append(
            {
                **dict(tick),
                "detected_language": language,
                "selected_route": select_longform_route(language),
                "top_probability": top_probability,
                "second_probability": second_probability,
                "probability_margin": margin,
                "confident": (
                    top_probability >= minimum_probability
                    and margin >= minimum_margin
                ),
                "processing_seconds": processing_seconds,
                "candidates": candidates,
                "candidate_limit": 10,
                "candidate_count_total": len(accepted_codes),
                "candidate_scope": "top_probability_ranked",
                "accepted_language_codes": accepted_codes,
            }
        )
    return detections


def build_continuous_language_runs(detections: list[dict], duration_seconds: float, profile: dict) -> list[dict]:
    confirmation_ticks = int(profile["continuous_language_confirmation_ticks"])
    if confirmation_ticks < 1:
        raise RuntimeError("CrisperWhisper continuous confirmation tick count is invalid")
    active_language = ""
    active_start = 0.0
    last_stable_center = 0.0
    active_first_tick = -1
    pending_language = ""
    pending_count = 0
    pending_first_center = 0.0
    pending_first_tick = -1
    runs = []
    for detection in detections:
        if not detection.get("confident"):
            pending_language = ""
            pending_count = 0
            detection["pending_language"] = None
            detection["pending_confirmation_count"] = 0
            detection["stable_language"] = active_language or None
            detection["language_decision"] = "unconfident_observation"
            continue
        language = str(detection["detected_language"])
        center = float(detection["tick_center_seconds"])
        if not active_language:
            if language != pending_language:
                pending_language = language
                pending_count = 1
                pending_first_center = center
                pending_first_tick = int(detection["tick_index"])
            else:
                pending_count += 1
            detection["pending_language"] = pending_language
            detection["pending_confirmation_count"] = pending_count
            detection["stable_language"] = None
            detection["language_decision"] = "initial_language_pending"
            if pending_count < confirmation_ticks:
                continue
            active_language = pending_language
            active_first_tick = pending_first_tick
            last_stable_center = center
            detection["pending_language"] = None
            detection["pending_confirmation_count"] = 0
            detection["stable_language"] = active_language
            detection["language_decision"] = "initial_language_confirmed"
            pending_language = ""
            pending_count = 0
            continue
        if language == active_language:
            last_stable_center = center
            pending_language = ""
            pending_count = 0
            detection["pending_language"] = None
            detection["pending_confirmation_count"] = 0
            detection["stable_language"] = active_language
            detection["language_decision"] = "stable_language_observation"
            continue
        if language != pending_language:
            pending_language = language
            pending_count = 1
            pending_first_center = center
            pending_first_tick = int(detection["tick_index"])
        else:
            pending_count += 1
        detection["pending_language"] = pending_language
        detection["pending_confirmation_count"] = pending_count
        detection["stable_language"] = active_language
        detection["language_decision"] = "language_change_pending"
        if pending_count < confirmation_ticks:
            continue
        boundary = (last_stable_center + pending_first_center) / 2.0
        if boundary <= active_start or boundary >= duration_seconds:
            raise RuntimeError("CrisperWhisper continuous language boundary did not advance")
        runs.append(
            {
                "run_index": len(runs),
                "detected_language": active_language,
                "selected_route": select_longform_route(active_language),
                "start_seconds": active_start,
                "end_seconds": boundary,
                "first_tick_index": active_first_tick,
                "last_tick_index": pending_first_tick - 1,
                "confirmation_ticks": confirmation_ticks,
                "confirmation_method": "consecutive_confident_ticks",
                "decision_validated": True,
                "acoustic_word_anchor_validated": False,
            }
        )
        active_language = pending_language
        active_start = boundary
        active_first_tick = pending_first_tick
        last_stable_center = center
        detection["pending_language"] = None
        detection["pending_confirmation_count"] = 0
        detection["stable_language"] = active_language
        detection["language_decision"] = "language_change_confirmed"
        pending_language = ""
        pending_count = 0
    if not active_language:
        raise RuntimeError(
            "CrisperWhisper continuous language detection had no confirmed language sequence"
        )
    runs.append(
        {
            "run_index": len(runs),
            "detected_language": active_language,
            "selected_route": select_longform_route(active_language),
            "start_seconds": active_start,
            "end_seconds": duration_seconds,
            "first_tick_index": active_first_tick,
            "last_tick_index": int(detections[-1]["tick_index"]),
            "confirmation_ticks": confirmation_ticks,
            "confirmation_method": "consecutive_confident_ticks",
            "decision_validated": True,
            "acoustic_word_anchor_validated": False,
        }
    )
    for detection in detections:
        center = float(detection["tick_center_seconds"])
        detection["assigned_run_language"] = next(
            str(run["detected_language"])
            for run in runs
            if float(run["start_seconds"]) <= center <= float(run["end_seconds"]) + 1e-6
        )
    return runs


def _offset_run_words(
    words: list[dict],
    offset_seconds: float,
    language: str,
) -> list[dict]:
    return [
        {
            **dict(word),
            "compact_start": float(word["compact_start"]) + offset_seconds,
            "compact_end": float(word["compact_end"]) + offset_seconds,
            "detected_language": language,
        }
        for word in words
    ]


def _offset_run_windows(
    windows: list[dict],
    offset_seconds: float,
    run_index: int,
    language: str,
    starting_index: int,
) -> list[dict]:
    result = []
    for local_index, window in enumerate(windows):
        item = dict(window)
        item.update(
            {
                "window_index": starting_index + local_index,
                "local_window_index": int(window.get("window_index") or local_index),
                "language_run_index": run_index,
                "detected_language": language,
                "start_seconds": float(window["start_seconds"]) + offset_seconds,
                "end_seconds": float(window["end_seconds"]) + offset_seconds,
            }
        )
        result.append(item)
    return result


def _run_with_option12_language_route(model, language, function, *args, **kwargs):
    with option12_language_route(model, language):
        return function(*args, **kwargs)


def transcribe_language_runs(
    model,
    compact_signal,
    boundaries,
    language_runs: list[dict],
    profile: dict,
) -> tuple[list[dict], list[dict], dict, dict]:
    merged_words = []
    accepted_windows = []
    attempts = []
    transitions = []
    route_runs = []
    for run in language_runs:
        run_index = int(run["run_index"])
        language = str(run["detected_language"])
        start_seconds = float(run["start_seconds"])
        end_seconds = float(run["end_seconds"])
        start_sample = round(start_seconds * SAMPLE_RATE)
        end_sample = min(len(compact_signal), round(end_seconds * SAMPLE_RATE))
        run_signal = compact_signal[start_sample:end_sample]
        if not len(run_signal):
            raise RuntimeError(f"CrisperWhisper language run is empty: {run_index}")
        local_boundaries = [
            float(boundary) - start_seconds
            for boundary in boundaries
            if start_seconds < float(boundary) < end_seconds
        ]
        selected_route = select_longform_route(language)
        if selected_route == NO_SPACE_LONGFORM_ROUTE:
            try:
                run_words, run_windows, run_diagnostics, route = _run_with_option12_language_route(
                    model,
                    language,
                    transcribe_no_space_language,
                    model,
                    run_signal,
                    language,
                    profile,
                    SAMPLE_RATE,
                )
            except CrisperWhisperNoSpaceDiagnosticError as error:
                local_second = error.diagnostic.get("local_compact_second")
                error.diagnostic.update(
                    {
                        "language_run_index": run_index,
                        "detected_language": language,
                        "selected_route": NO_SPACE_LONGFORM_ROUTE,
                        "language_run_start_seconds": start_seconds,
                        "language_run_end_seconds": end_seconds,
                        "global_compact_second": (
                            float(local_second) + start_seconds
                            if local_second is not None
                            else None
                        ),
                    }
                )
                raise
        else:
            try:
                run_words, run_windows, run_diagnostics = _run_with_option12_language_route(
                    model,
                    language,
                    run_longform,
                    model,
                    run_signal,
                    local_boundaries,
                    language,
                    profile,
                    allow_lexically_unconfirmed_final_tail=(
                        end_seconds >= len(compact_signal) / SAMPLE_RATE - 1e-6
                    ),
                )
            except CrisperWhisperDiagnosticError as error:
                local_second = error.diagnostic.get("local_compact_second")
                error.diagnostic.update(
                    {
                        "language_run_index": run_index,
                        "detected_language": language,
                        "selected_route": DEFAULT_LONGFORM_ROUTE,
                        "language_run_start_seconds": start_seconds,
                        "language_run_end_seconds": end_seconds,
                        "global_compact_second": (
                            float(local_second) + start_seconds
                            if local_second is not None
                            else None
                        ),
                    }
                )
                raise
            route = {
                "detected_language": language,
                "selected_route": DEFAULT_LONGFORM_ROUTE,
                "language_group": sorted(NO_SPACE_LANGUAGE_CODES),
                "token_decode_policy": "not_applicable",
            }
        if run_index:
            transitions.append(
                {
                    "language_run_index": run_index,
                    "method": "language_run_boundary",
                    "seam_seconds": start_seconds,
                    "validated": True,
                    "validation_scope": "language_decision",
                    "validation_method": "consecutive_confident_ticks_midpoint",
                    "acoustic_word_anchor_validated": False,
                    "anchor_word_count": 0,
                    "previous_language": str(language_runs[run_index - 1]["detected_language"]),
                    "detected_language": language,
                }
            )
        word_offset = len(merged_words)
        merged_words.extend(_offset_run_words(run_words, start_seconds, language))
        global_windows = _offset_run_windows(
            run_windows,
            start_seconds,
            run_index,
            language,
            len(accepted_windows),
        )
        accepted_windows.extend(global_windows)
        for attempt in list(run_diagnostics.get("attempts") or []):
            item = dict(attempt)
            item.update(
                {
                    "language_run_index": run_index,
                    "detected_language": language,
                    "start_seconds": float(item["start_seconds"]) + start_seconds,
                    "end_seconds": float(item["end_seconds"]) + start_seconds,
                }
            )
            attempts.append(item)
        for transition in list(run_diagnostics.get("transitions") or []):
            item = dict(transition)
            item.update(
                {
                    "language_run_index": run_index,
                    "detected_language": language,
                    "seam_seconds": float(item.get("seam_seconds") or 0.0) + start_seconds,
                }
            )
            for field in ("excluded_start_seconds", "excluded_end_seconds"):
                if item.get(field) is not None:
                    item[field] = float(item[field]) + start_seconds
            transitions.append(item)
        route_runs.append(
            {
                **dict(run),
                "word_start_index": word_offset,
                "word_end_index": len(merged_words) - 1,
                "route": route,
            }
        )
    language_route = {
        "selected_route": "per_window_detected_language_runs",
        "language_group": sorted(NO_SPACE_LANGUAGE_CODES),
        "language_runs": route_runs,
    }
    return merged_words, accepted_windows, {"attempts": attempts, "transitions": transitions}, language_route


def _process_request(request: dict) -> dict:
    profile = require_exact_request(request)
    language_detection_mode = str(request["language_detection_mode"])
    platform_language = str(request["platform_language"])
    audio_path = Path(str(request.get("audio_path") or "")).resolve()
    output_dir = Path(str(request.get("output_dir") or "")).resolve()
    snapshot = Path(str(request.get("model_snapshot") or "")).resolve()
    vad_model_path = Path(str(request.get("vad_model_path") or "")).resolve()
    if not audio_path.is_file():
        raise FileNotFoundError(f"ASR audio not found: {audio_path}")
    if snapshot.name != MODEL_SNAPSHOT_ID:
        raise RuntimeError(f"Exact CrisperWhisper model snapshot required: {snapshot}")
    if not (snapshot / "model.safetensors").is_file():
        snapshot_problems = diagnose_local_model_snapshot(snapshot)
        raise RuntimeError(
            f"CrisperWhisper local model snapshot is incomplete or corrupt: {snapshot_problems}"
        )
    tokenizer_contract = load_acoustic_event_contract(snapshot)
    output_dir.mkdir(parents=True, exist_ok=True)
    quality_failure_path = output_dir / QUALITY_FAILURE_ARTIFACT_NAME
    quality_failure_path.unlink(missing_ok=True)
    configure_cache()
    import torch
    from crisperwhisper import CrisperWhisperModel

    signal, sample_rate = load_signal(audio_path)
    if sample_rate != SAMPLE_RATE:
        raise RuntimeError(f"CrisperWhisper requires {SAMPLE_RATE} Hz audio")
    silero_model = load_silero_model(torch, vad_model_path)
    regions, vad_runtime = detect_speech_regions(
        torch,
        signal,
        silero_model,
        float(profile["vad_threshold"]),
        int(profile["vad_min_speech_duration_ms"]),
        int(profile["vad_min_silence_duration_ms"]),
        int(profile["vad_speech_pad_ms"]),
    )
    compact_signal, spans = build_compact_timeline(signal, regions)
    boundaries = natural_boundary_seconds(spans)
    del silero_model

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; CrisperWhisper CPU fallback is forbidden")
    try:
        model = CrisperWhisperModel(
            str(snapshot),
            backend="transformers",
            device="cuda",
            compute_type="float16",
        )
    except Exception as model_load_error:
        snapshot_problems = diagnose_local_model_snapshot(snapshot)
        if snapshot_problems:
            raise RuntimeError(
                f"CrisperWhisper local model snapshot is incomplete or corrupt: {snapshot_problems}"
            ) from model_load_error
        raise RuntimeError(
            "CrisperWhisper local model files match the canonical manifest; "
            f"actual model load error: {type(model_load_error).__name__}: {model_load_error}"
        ) from model_load_error
    runtime = model_runtime_evidence(model, torch)
    if runtime.get("parameter_device_type") != "cuda" or runtime.get("parameter_dtype") != "torch.float16":
        raise RuntimeError(f"CrisperWhisper runtime is not CUDA/float16: {runtime}")
    if language_detection_mode == GLOBAL_FIRST_WINDOW_LANGUAGE_MODE:
        if platform_language:
            language = platform_language
            candidates, accepted_codes = platform_language_evidence(model, language)
            language_window_samples = 0
            language_source = "platform_metadata"
        else:
            language_window_samples = min(
                len(compact_signal),
                round(float(profile["maximum_window_seconds"]) * SAMPLE_RATE),
            )
            language, candidates, accepted_codes = language_scores(
                model,
                torch,
                compact_signal[:language_window_samples],
            )
            language_source = "crisper_global_first_window_language_detection"
        if not language or model._engine.get_language_id(language) is None:
            raise RuntimeError(f"CrisperWhisper accepted language code required: {language!r}")
        selected_route = select_longform_route(language)
        if selected_route == NO_SPACE_LONGFORM_ROUTE:
            try:
                compact_words, windows, longform, language_route = _run_with_option12_language_route(
                    model,
                    language,
                    transcribe_no_space_language,
                    model,
                    compact_signal,
                    language,
                    profile,
                    SAMPLE_RATE,
                )
            except CrisperWhisperNoSpaceDiagnosticError as error:
                local_second = float(error.diagnostic.get("local_compact_second") or 0.0)
                original_second, span_index = compact_time_to_original(
                    spans,
                    local_second,
                    False,
                )
                error.diagnostic.update(
                    {
                        "language_detection_mode": language_detection_mode,
                        "global_compact_second": local_second,
                        "original_audio_second": original_second,
                        "vad_span_index": span_index,
                        "language_detections": [
                            {
                                "window_index": 0,
                                "start_seconds": 0.0,
                                "end_seconds": language_window_samples / SAMPLE_RATE,
                                "language_source": language_source,
                                "platform_language": platform_language,
                                "detection_skipped": language_source == "platform_metadata",
                                "detected_language": language,
                                "selected_route": selected_route,
                                "candidates": candidates,
                            }
                        ],
                    }
                )
                raise
        else:
            try:
                compact_words, windows, longform = _run_with_option12_language_route(
                    model,
                    language,
                    run_longform,
                    model,
                    compact_signal,
                    boundaries,
                    language,
                    profile,
                )
            except CrisperWhisperDiagnosticError as error:
                original_second, span_index = compact_time_to_original(
                    spans,
                    float(error.diagnostic["local_compact_second"]),
                    False,
                )
                error.diagnostic.update(
                    {
                        "language_detection_mode": language_detection_mode,
                        "global_compact_second": error.diagnostic.get(
                            "local_compact_second"
                        ),
                        "original_audio_second": original_second,
                        "vad_span_index": span_index,
                        "language_detections": [
                            {
                                "window_index": 0,
                                "start_seconds": 0.0,
                                "end_seconds": language_window_samples / SAMPLE_RATE,
                                "language_source": language_source,
                                "platform_language": platform_language,
                                "detection_skipped": language_source == "platform_metadata",
                                "detected_language": language,
                                "selected_route": selected_route,
                                "candidates": candidates,
                            }
                        ],
                    }
                )
                raise
            language_route = {
                "detected_language": language,
                "selected_route": DEFAULT_LONGFORM_ROUTE,
                "language_group": sorted(NO_SPACE_LANGUAGE_CODES),
                "token_decode_policy": "not_applicable",
            }
        language_detections = [
            {
                "window_index": 0,
                "start_seconds": 0.0,
                "end_seconds": language_window_samples / SAMPLE_RATE,
                "duration_seconds": language_window_samples / SAMPLE_RATE,
                "end_kind": "global_first_window",
                "language_source": language_source,
                "detection_skipped": language_source == "platform_metadata",
                "detected_language": language,
                "selected_route": selected_route,
                "candidates": candidates,
            }
        ]
        language_runs = [
            {
                "run_index": 0,
                "detected_language": language,
                "selected_route": selected_route,
                "start_seconds": 0.0,
                "end_seconds": len(compact_signal) / SAMPLE_RATE,
                "first_window_index": 0,
                "last_window_index": 0,
                "window_count": 1,
            }
        ]
    elif language_detection_mode == PER_WINDOW_LANGUAGE_MODE:
        language_source = "crisper_per_window_language_detection"
        planned_language_windows = plan_language_detection_windows(
            compact_signal,
            boundaries,
            profile,
        )
        language_detections = detect_window_languages(
            model,
            torch,
            compact_signal,
            planned_language_windows,
        )
        language_runs = build_language_runs(language_detections)
        language_duration = {}
        for detection in language_detections:
            detected = str(detection["detected_language"])
            language_duration[detected] = language_duration.get(detected, 0.0) + float(
                detection["duration_seconds"]
            )
        language = max(language_duration, key=lambda value: (language_duration[value], value))
        candidates = list(language_detections[0]["candidates"])
        accepted_codes = list(language_detections[0]["accepted_language_codes"])
        language_window_samples = round(float(language_detections[0]["duration_seconds"]) * SAMPLE_RATE)
        try:
            compact_words, windows, longform, language_route = transcribe_language_runs(
                model,
                compact_signal,
                boundaries,
                language_runs,
                profile,
            )
        except (CrisperWhisperDiagnosticError, CrisperWhisperNoSpaceDiagnosticError) as error:
            global_second = float(error.diagnostic["global_compact_second"])
            original_second, span_index = compact_time_to_original(
                spans,
                global_second,
                False,
            )
            error.diagnostic.update(
                {
                    "language_detection_mode": language_detection_mode,
                    "original_audio_second": original_second,
                    "vad_span_index": span_index,
                    "language_detections": language_detections,
                    "language_runs": language_runs,
                }
            )
            raise
        selected_route = "per_window_detected_language_runs"
    else:
        language_source = "crisper_continuous_stream_language_detection"
        planned_language_ticks = plan_continuous_language_ticks(
            compact_signal,
            profile,
        )
        language_detections = detect_continuous_languages(
            model,
            torch,
            compact_signal,
            planned_language_ticks,
            profile,
        )
        language_runs = build_continuous_language_runs(
            language_detections,
            len(compact_signal) / SAMPLE_RATE,
            profile,
        )
        language_duration = {
            str(run["detected_language"]): 0.0 for run in language_runs
        }
        for run in language_runs:
            detected = str(run["detected_language"])
            language_duration[detected] += (
                float(run["end_seconds"]) - float(run["start_seconds"])
            )
        language = max(language_duration, key=lambda value: (language_duration[value], value))
        candidates = list(language_detections[0]["candidates"])
        accepted_codes = list(language_detections[0]["accepted_language_codes"])
        language_window_samples = round(
            float(language_detections[0]["context_duration_seconds"]) * SAMPLE_RATE
        )
        try:
            compact_words, windows, longform, language_route = transcribe_language_runs(
                model,
                compact_signal,
                boundaries,
                language_runs,
                profile,
            )
        except (CrisperWhisperDiagnosticError, CrisperWhisperNoSpaceDiagnosticError) as error:
            global_second = float(error.diagnostic["global_compact_second"])
            original_second, span_index = compact_time_to_original(
                spans,
                global_second,
                False,
            )
            error.diagnostic.update(
                {
                    "language_detection_mode": language_detection_mode,
                    "original_audio_second": original_second,
                    "vad_span_index": span_index,
                    "language_detections": language_detections,
                    "language_runs": language_runs,
                }
            )
            raise
        language_route["selected_route"] = "continuous_stream_detected_language_runs"
        selected_route = "continuous_stream_detected_language_runs"
    compact_words, compact_seam_repairs, unresolved_compact_seams = reconcile_compact_seam_crossings(
        compact_words,
        spans,
        float(profile["compact_seam_tolerance_seconds"]),
    )
    words, seam_crossings = map_words_to_original(compact_words, spans)
    if unresolved_compact_seams:
        seam_crossings = [*seam_crossings, *unresolved_compact_seams]
    timing_errors = word_timing_errors(words, len(signal) / sample_rate)
    repetition_findings = pathological_repetitions(words)
    accepted_timed_repetitions, repetitions = classify_timed_repetitions(
        repetition_findings
    )
    unvalidated = [
        transition
        for transition in longform["transitions"]
        if not transition.get("validated")
        and not (
            transition.get("method") == "bridge_recovery"
            and transition.get("left_anchor_validated")
            and transition.get("right_transition_validated")
        )
    ]
    failures = []
    if not words:
        failures.append("no_words")
    if seam_crossings:
        failures.append("word_crossed_compact_timeline_seam")
    if timing_errors:
        failures.append("invalid_word_timing")
    if repetitions:
        failures.append("pathological_repetition_loop")
    if unvalidated:
        failures.append("unvalidated_transition")
    if failures:
        quality_failure = {
            "schema_version": QUALITY_FAILURE_SCHEMA_VERSION,
            "artifact_type": "crisperwhisper_quality_failure",
            "success": False,
            "engine": ENGINE,
            "api_schema_version": API_SCHEMA_VERSION,
            "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
            "failure_phase": "post_transcription_quality_gate",
            "failure_type": "quality_gate_rejection",
            "model_repo": MODEL_REPO,
            "model_snapshot_id": MODEL_SNAPSHOT_ID,
            "audio": {
                "name": audio_path.name,
                "duration_seconds": len(signal) / sample_rate,
                "sample_rate": sample_rate,
                "channels": 1,
                "subtype": "PCM_16",
            },
            "language_detection_mode": language_detection_mode,
            "language_source": language_source,
            "platform_language": platform_language,
            "detected_language": language,
            "detected_languages": sorted(
                {
                    str(item["detected_language"])
                    for item in language_runs
                }
            ),
            "language_route": language_route,
            "quality_gate": {
                "status": "failed",
                "failure_reasons": failures,
                "seam_crossings": seam_crossings,
                "timing_errors": timing_errors,
                "pathological_repetitions": repetitions,
                "accepted_timed_repetitions": accepted_timed_repetitions,
                "unvalidated_transitions": unvalidated,
            },
            "windows": windows,
            "window_attempts": longform["attempts"],
            "transitions": longform["transitions"],
            "compact_seam_repairs": compact_seam_repairs,
        }
        write_json(quality_failure_path, quality_failure)
        repeat_locations = [
            {
                "phrase": finding["phrase"],
                "repeat_count": finding["repeat_count"],
                "start_timestamp": finding["start_timestamp"],
                "end_timestamp": finding["end_timestamp"],
            }
            for finding in repetitions[:5]
        ]
        raise CrisperWhisperQualityGateError(
            f"CrisperWhisper quality gate failed: failures={failures}, "
            f"seams={seam_crossings[:5]}, timing={timing_errors[:5]}, "
            f"repeat_locations={repeat_locations}, "
            f"diagnostic={QUALITY_FAILURE_ARTIFACT_NAME}",
            QUALITY_FAILURE_ARTIFACT_NAME,
        )

    text = join_timed_word_text(words, language)
    segment = {
        "index": 0,
        "start": float(words[0]["start"]),
        "end": float(words[-1]["end"]),
        "text": text,
        "words": words,
    }
    language_data = {
        "success": True,
        "language_detection_mode": language_detection_mode,
        "language_source": language_source,
        "platform_language": platform_language,
        "detected_language": language,
        "detected_languages": sorted(
            {str(item["detected_language"]) for item in language_runs}
        ),
        "accepted_language_codes": accepted_codes,
        "candidates": candidates,
        "candidate_limit": 10,
        "candidate_count_total": len(accepted_codes),
        "candidate_scope": "top_probability_ranked",
        "windows": language_detections,
        "language_runs": language_runs,
        "profile_summary": {
            "engine": ENGINE,
            "language_detection_mode": language_detection_mode,
            "language_source": language_source,
            "platform_language": platform_language,
            "language_detection_only": True,
            "transcript_generated": False,
            "words_generated": False,
            "segments_generated": False,
            "alignment_run": False,
            "cpu_fallback": False,
            "window_seconds": language_window_samples / SAMPLE_RATE,
            "window_count": len(language_detections),
            "tick_count": (
                len(language_detections)
                if language_detection_mode == CONTINUOUS_STREAM_LANGUAGE_MODE
                else 0
            ),
            "total_detection_processing_seconds": sum(
                float(item.get("processing_seconds") or 0.0)
                for item in language_detections
            ),
        },
    }
    lexically_unconfirmed_tail_exclusions = []
    for transition in longform["transitions"]:
        if transition.get("method") != "lexically_unconfirmed_final_vad_tail":
            continue
        compact_start = float(transition["excluded_start_seconds"])
        compact_end = float(transition["excluded_end_seconds"])
        original_start, start_span = compact_time_to_original(spans, compact_start, False)
        original_end, end_span = compact_time_to_original(spans, compact_end, True)
        lexically_unconfirmed_tail_exclusions.append(
            {
                **dict(transition),
                "original_start_seconds": original_start,
                "original_end_seconds": original_end,
                "start_span_index": start_span,
                "end_span_index": end_span,
            }
        )
    quality_gate = {
        "status": "complete",
        "failure_reasons": [],
        "empty_window_indices": [window["window_index"] for window in windows if not window["word_count"]],
        "seam_crossing_word_count": 0,
        "timing_error_count": 0,
        "pathological_loop_count": 0,
        "timed_repetition_contract_version": TIMED_REPETITION_CONTRACT_VERSION,
        "timed_repetition_policy": TIMED_REPETITION_POLICY,
        "timed_repetition_accepted_count": len(accepted_timed_repetitions),
        "accepted_timed_repetitions": accepted_timed_repetitions,
        "unvalidated_transition_count": 0,
        "local_boundary_repair_count": sum(
            transition.get("boundary_resolution") == "local_interval_midpoint"
            for transition in longform["transitions"]
        ),
        "coverage_recovery_window_count": sum(
            window.get("coverage_status") == "recovery_required" for window in windows
        ),
        "lexically_unconfirmed_final_vad_tail_count": len(
            lexically_unconfirmed_tail_exclusions
        ),
        "lexically_unconfirmed_final_vad_tail_seconds": sum(
            float(item["excluded_duration_seconds"])
            for item in lexically_unconfirmed_tail_exclusions
        ),
        "inference_window_timestamp_repair_count": sum(
            int(attempt.get("timestamp_repair_count") or 0) for attempt in longform["attempts"]
        ),
        "fully_outside_inference_window_drop_count": sum(
            int(attempt.get("timestamp_drop_count") or 0) for attempt in longform["attempts"]
        ),
        "compact_seam_repair_count": len(compact_seam_repairs),
        "temporal_boundary_retry_count": sum(
            attempt.get("anchor_validated") is True
            and attempt.get("temporal_boundary_validated") is False
            for attempt in longform["attempts"]
        ),
    }
    profile_summary = {
        "engine": ENGINE,
        "api_schema_version": API_SCHEMA_VERSION,
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "model_repo": MODEL_REPO,
        "model_snapshot_id": MODEL_SNAPSHOT_ID,
        "language": language,
        "detected_languages": language_data["detected_languages"],
        "language_detection_mode": language_detection_mode,
        "language_source": language_source,
        "platform_language": platform_language,
        "backend": "transformers",
        "device": runtime.get("parameter_device"),
        "device_type": runtime.get("parameter_device_type"),
        "dtype": runtime.get("parameter_dtype"),
        "python": platform.python_version(),
        "torch": str(torch.__version__),
        "torch_cuda": str(torch.version.cuda),
        "crisperwhisper": package_version("crisperwhisper"),
        "transformers": package_version("transformers"),
        "runtime_optimization": model._option12_runtime_optimization.evidence(),
        "word_timestamps": True,
        "alignment_run": False,
        "continuation": (
            selected_route == NO_SPACE_LONGFORM_ROUTE
            or any(
                str(run["selected_route"]) == NO_SPACE_LONGFORM_ROUTE
                for run in language_runs
            )
        ),
        "language_route": language_route,
        "reference_text_not_used": True,
        "cpu_fallback": False,
        "audio_duration_seconds": len(signal) / sample_rate,
        "compact_duration_seconds": len(compact_signal) / sample_rate,
        "lexically_confirmed_compact_duration_seconds": (
            float(lexically_unconfirmed_tail_exclusions[0]["excluded_start_seconds"])
            if lexically_unconfirmed_tail_exclusions
            else len(compact_signal) / sample_rate
        ),
        "vad": {
            "threshold": profile["vad_threshold"],
            "min_speech_duration_ms": profile["vad_min_speech_duration_ms"],
            "min_silence_duration_ms": profile["vad_min_silence_duration_ms"],
            "speech_pad_ms": profile["vad_speech_pad_ms"],
            **vad_runtime,
            "regions": regions,
            "compact_spans": spans,
            "lexically_unconfirmed_tail_exclusions": (
                lexically_unconfirmed_tail_exclusions
            ),
        },
        "window_policy": {
            "selected_route": selected_route,
            "language_detection_mode": language_detection_mode,
            "language_source": language_source,
            "platform_language": platform_language,
            "default_longform_strategy": profile["default_longform_strategy"],
            "no_space_longform_strategy": profile["no_space_longform_strategy"],
            "no_space_language_codes": profile["no_space_language_codes"],
            "no_space_chunk_duration_seconds": profile["no_space_chunk_duration_seconds"],
            "no_space_stride_seconds": profile["no_space_stride_seconds"],
            "no_space_context_groups": profile["no_space_context_groups"],
            "no_space_context_budget_policy": profile[
                "no_space_context_budget_policy"
            ],
            "no_space_context_overflow_policy": profile[
                "no_space_context_overflow_policy"
            ],
            "no_space_expected_max_target_positions": profile[
                "no_space_expected_max_target_positions"
            ],
            "no_space_generation_token_reserve": profile[
                "no_space_generation_token_reserve"
            ],
            "no_space_max_new_tokens": profile["no_space_max_new_tokens"],
            "no_space_max_uncovered_active_tail_seconds": profile[
                "no_space_max_uncovered_active_tail_seconds"
            ],
            "no_space_adaptive_retry_chunk_duration_seconds": profile[
                "no_space_adaptive_retry_chunk_duration_seconds"
            ],
            "no_space_adaptive_retry_overlap_seconds": profile[
                "no_space_adaptive_retry_overlap_seconds"
            ],
            "no_space_adaptive_retry_stride_seconds": profile[
                "no_space_adaptive_retry_stride_seconds"
            ],
            "no_space_adaptive_retry_policy": profile[
                "no_space_adaptive_retry_policy"
            ],
            "no_space_overlap_suffix_recovery_policy": profile[
                "no_space_overlap_suffix_recovery_policy"
            ],
            "no_space_plain_consensus_temperature": profile[
                "no_space_plain_consensus_temperature"
            ],
            "no_space_plain_consensus_seed_count": profile[
                "no_space_plain_consensus_seed_count"
            ],
            "no_space_plain_consensus_minimum_fraction": profile[
                "no_space_plain_consensus_minimum_fraction"
            ],
            "no_space_intended_consensus_seed_count": profile[
                "no_space_intended_consensus_seed_count"
            ],
            "no_space_intended_consensus_seeds": profile[
                "no_space_intended_consensus_seeds"
            ],
            "no_space_intended_consensus_batch_size": profile[
                "no_space_intended_consensus_batch_size"
            ],
            "no_space_intended_consensus_temperature": profile[
                "no_space_intended_consensus_temperature"
            ],
            "no_space_intended_consensus_minimum_candidates": profile[
                "no_space_intended_consensus_minimum_candidates"
            ],
            "no_space_intended_consensus_maximum_token_density": profile[
                "no_space_intended_consensus_maximum_token_density"
            ],
            "no_space_intended_consensus_policy": profile[
                "no_space_intended_consensus_policy"
            ],
            "no_space_token_decode_policy": profile["no_space_token_decode_policy"],
            "no_space_coverage_count_mode": profile["no_space_coverage_count_mode"],
            "no_space_fallback_policy": profile["no_space_fallback_policy"],
            "no_space_loop_recovery_policy": profile[
                "no_space_loop_recovery_policy"
            ],
            "no_space_min_speech_seconds": profile["no_space_min_speech_seconds"],
            "no_space_min_content_tokens_per_active_second": profile[
                "no_space_min_content_tokens_per_active_second"
            ],
            "no_space_min_sibling_content_tokens": profile[
                "no_space_min_sibling_content_tokens"
            ],
            "target_seconds": profile["target_window_seconds"],
            "maximum_seconds": profile["maximum_window_seconds"],
            "minimum_seconds": profile["minimum_window_seconds"],
            "continuous_language_context_seconds": profile[
                "continuous_language_context_seconds"
            ],
            "continuous_language_tick_seconds": profile[
                "continuous_language_tick_seconds"
            ],
            "continuous_language_confirmation_ticks": profile[
                "continuous_language_confirmation_ticks"
            ],
            "continuous_language_min_top_probability": profile[
                "continuous_language_min_top_probability"
            ],
            "continuous_language_min_margin": profile[
                "continuous_language_min_margin"
            ],
            "continuous_language_boundary_policy": profile[
                "continuous_language_boundary_policy"
            ],
            "inference_window_timestamp_tolerance_seconds": profile[
                "inference_window_timestamp_tolerance_seconds"
            ],
            "inference_window_timestamp_policy": profile["inference_window_timestamp_policy"],
            "compact_seam_tolerance_seconds": profile["compact_seam_tolerance_seconds"],
            "compact_seam_policy": profile["compact_seam_policy"],
            "minimum_overlap_seconds": profile["minimum_overlap_seconds"],
            "maximum_overlap_seconds": profile["maximum_overlap_seconds"],
            "minimum_anchor_words": profile["minimum_anchor_words"],
            "stitch_boundary_contract_version": profile["stitch_boundary_contract_version"],
            "stitch_boundary_policy": profile["stitch_boundary_policy"],
            "window_coverage_contract_version": profile["window_coverage_contract_version"],
            "window_coverage_policy": profile["window_coverage_policy"],
        },
        "windows": windows,
        "window_attempts": longform["attempts"],
        "transitions": longform["transitions"],
        "compact_seam_repairs": compact_seam_repairs,
        "quality_gate": quality_gate,
        "word_count": len(words),
        "dubbing_ready_contract": {
            "contract_version": DUBBING_READY_CONTRACT_VERSION,
            "tokenizer_contract_sha256": tokenizer_contract["tokenizer_contract_sha256"],
            "acoustic_event_labels": list(ACOUSTIC_EVENT_LABELS),
            "filler_normalization": FILLER_NORMALIZATION,
            "unknown_bracket_policy": "preserve_and_report",
        },
    }
    language_artifact_name = "crisperwhisper2_medium_language_detection.json"
    language_profile_name = "language_detection_profile_crisperwhisper2_medium.json"
    transcription_profile_name = "transcription_profile_crisperwhisper2_medium.json"
    raw_name = RAW_RESULT_ARTIFACT_NAME
    dubbing_ready_name = DUBBING_READY_RESULT_ARTIFACT_NAME
    write_json(output_dir / language_artifact_name, language_data)
    write_json(
        output_dir / language_profile_name,
        {
            "success": True,
            "language_detection_mode": language_detection_mode,
            "detected_language": language,
            "detected_languages": language_data["detected_languages"],
            "candidates": candidates,
            "candidate_limit": language_data["candidate_limit"],
            "candidate_count_total": language_data["candidate_count_total"],
            "candidate_scope": language_data["candidate_scope"],
            "windows": language_detections,
            "language_runs": language_runs,
            "profile_summary": language_data["profile_summary"],
        },
    )
    raw_result = {
        "schema_version": API_SCHEMA_VERSION,
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "success": True,
        "language_detection_mode": language_detection_mode,
        "language_source": language_source,
        "platform_language": platform_language,
        "detected_language": language,
        "detected_languages": language_data["detected_languages"],
        "words": words,
        "segments": [segment],
        "total_words": len(words),
        "total_segments": 1,
        "profile_summary": profile_summary,
        "language_detection": {
            "mode": language_detection_mode,
            "language_source": language_source,
            "platform_language": platform_language,
            "detected_language": language,
            "detected_languages": language_data["detected_languages"],
            "accepted_language_codes": accepted_codes,
            "candidates": candidates,
            "candidate_limit": language_data["candidate_limit"],
            "candidate_count_total": language_data["candidate_count_total"],
            "candidate_scope": language_data["candidate_scope"],
            "windows": language_detections,
            "language_runs": language_runs,
            "artifact_path": language_artifact_name,
            "profile_path": language_profile_name,
            "profile_summary": language_data["profile_summary"],
        },
        "artifacts": {
            "api_request_path": "crisperwhisper2_medium_api_request.json",
            "transcription_profile_path": transcription_profile_name,
            "raw_result_path": raw_name,
            "dubbing_ready_result_path": dubbing_ready_name,
            "language_detection_artifact_path": language_artifact_name,
            "language_detection_profile_path": language_profile_name,
        },
    }
    write_json(output_dir / raw_name, raw_result)
    result = build_dubbing_ready_result(raw_result, tokenizer_contract)
    write_json(output_dir / dubbing_ready_name, result)
    language_artifact_sha256 = hashlib.sha256(
        (output_dir / language_artifact_name).read_bytes()
    ).hexdigest()
    language_profile_sha256 = hashlib.sha256(
        (output_dir / language_profile_name).read_bytes()
    ).hexdigest()
    raw_sha256 = hashlib.sha256((output_dir / raw_name).read_bytes()).hexdigest()
    dubbing_ready_sha256 = hashlib.sha256((output_dir / dubbing_ready_name).read_bytes()).hexdigest()
    write_json(
        output_dir / transcription_profile_name,
        {
            "success": True,
            "subprocess_returncode": 0,
            "language_detection_mode": language_detection_mode,
            "detected_language": language,
            "detected_languages": language_data["detected_languages"],
            "total_words": int(result["total_words"]),
            "total_segments": int(result["total_segments"]),
            "raw_total_words": len(words),
            "raw_total_segments": 1,
            "raw_result_sha256": raw_sha256,
            "dubbing_ready_result_sha256": dubbing_ready_sha256,
            "language_detection_artifact_sha256": language_artifact_sha256,
            "language_detection_profile_sha256": language_profile_sha256,
            "dubbing_ready": result["dubbing_ready"],
            "profile_summary": profile_summary,
        },
    )
    return result


def process_request(request: dict) -> dict:
    import torch
    import crisperwhisper

    original_constructor = crisperwhisper.CrisperWhisperModel
    optimizers = []

    def optimized_constructor(*args, **kwargs):
        model = original_constructor(*args, **kwargs)
        optimizer = Option12RuntimeOptimization(model, torch)
        optimizer.__enter__()
        optimizers.append(optimizer)
        return model

    crisperwhisper.CrisperWhisperModel = optimized_constructor
    try:
        with torch.inference_mode():
            return _process_request(request)
    finally:
        for optimizer in reversed(optimizers):
            optimizer.__exit__(None, None, None)
        crisperwhisper.CrisperWhisperModel = original_constructor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    request = None
    try:
        request = read_request(args.request.resolve())
        result = process_request(request)
        return_code = 0
    except Exception as error:
        traceback_text = traceback.format_exc()
        diagnostic_artifact_name = ""
        if isinstance(request, dict):
            diagnostic_artifact_name = write_exception_diagnostic(
                request,
                error,
                traceback_text,
            )
        result = {
            "schema_version": API_SCHEMA_VERSION,
            "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
            "success": False,
            "error": str(error),
            "traceback": traceback_text,
            "profile_summary": {
                "engine": ENGINE,
                "alignment_run": False,
                "continuation": False,
                "reference_text_not_used": True,
                "cpu_fallback": False,
            },
        }
        diagnostic_artifact_name = (
            diagnostic_artifact_name or getattr(error, "artifact_name", "")
        )
        if diagnostic_artifact_name:
            result["artifacts"] = {
                "quality_failure_diagnostic_path": diagnostic_artifact_name,
            }
        return_code = 1
    write_json(args.response.resolve(), result)
    print(
        RESULT_PREFIX
        + json.dumps(
            {
                "success": bool(result.get("success")),
                "response_path": str(args.response.resolve()),
                "word_count": int(result.get("total_words") or 0),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        flush=True,
    )
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
