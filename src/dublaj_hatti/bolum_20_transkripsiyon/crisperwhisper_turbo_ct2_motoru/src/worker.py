from __future__ import annotations

import argparse
import importlib.metadata
import platform
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from contract import (
    ENGINE_ID,
    MODEL_ID,
    RESPONSE_SCHEMA_VERSION,
    RUNTIME_CONTRACT_VERSION,
    read_json,
    require_request,
    sha256_file,
    write_json_atomic,
)
from file_integrity import FileIntegrity
from dubbing_ready import load_acoustic_event_contract
from native_softmax import NativeSoftmax
from runtime_efficiency import execution_policy, prepare_model_and_audio
from result_builder import write_success_artifacts
from vad import VadSettings, compact_audio, speech_regions


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "config" / "runtime_profile.json"
MODEL_MANIFEST_PATH = ROOT / "config" / "model_manifest.json"
MODEL_PATH = ROOT / "model_assets" / "ct2_float16_align"
VAD_MODEL_PATH = ROOT / "model_assets" / "silero_vad" / "silero_vad.onnx"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def verified_profile(sha256_file=sha256_file) -> dict[str, Any]:
    profile = read_json(PROFILE_PATH)
    manifest = read_json(MODEL_MANIFEST_PATH)
    if profile.get("engine") != ENGINE_ID:
        raise RuntimeError("Runtime profile engine identity mismatch")
    if manifest.get("owner") != "crisperwhisper_turbo_ct2_motoru":
        raise RuntimeError("Model manifest owner identity mismatch")
    manifest_model = dict(manifest["model"])
    if manifest_model.get("resolved_commit") != profile["model"].get("resolved_commit"):
        raise RuntimeError("Model manifest commit mismatch")
    if manifest_model.get("files") != profile["model"].get("files"):
        raise RuntimeError("Model manifest and runtime profile file sets differ")
    for name, expected in dict(profile["model"]["files"]).items():
        path = MODEL_PATH / name
        if not path.is_file():
            raise FileNotFoundError(f"Required model file is missing: {path}")
        size = expected.get("size_bytes")
        if size is not None and path.stat().st_size != int(size):
            raise RuntimeError(f"Model file size mismatch: {name}")
        if sha256_file(path) != str(expected["sha256"]).lower():
            raise RuntimeError(f"Model file SHA256 mismatch: {name}")
    if not VAD_MODEL_PATH.is_file():
        raise FileNotFoundError(f"Silero VAD model is missing: {VAD_MODEL_PATH}")
    if sha256_file(VAD_MODEL_PATH) != str(manifest["vad"]["sha256"]).lower():
        raise RuntimeError("Silero VAD model SHA256 mismatch")
    if profile.get("execution") != execution_policy:
        raise RuntimeError("Runtime execution policy mismatch")
    return profile


def runtime_identity(profile: dict[str, Any]) -> dict[str, Any]:
    import ctranslate2
    import onnxruntime

    supported = sorted(ctranslate2.get_supported_compute_types("cuda"))
    expected_runtime = dict(profile["runtime"])
    identity = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "crisperwhisper": importlib.metadata.version("crisperwhisper"),
        "ctranslate2_crisperwhisper": importlib.metadata.version(
            "ctranslate2-crisperwhisper"
        ),
        "onnxruntime": importlib.metadata.version("onnxruntime"),
        "device": "cuda",
        "compute_type": "int8",
        "cpu_fallback": False,
        "supported_cuda_compute_types": supported,
    }
    for key in (
        "python",
        "crisperwhisper",
        "ctranslate2_crisperwhisper",
        "onnxruntime",
        "device",
        "compute_type",
        "cpu_fallback",
    ):
        if identity[key] != expected_runtime[key]:
            raise RuntimeError(
                f"Runtime identity mismatch for {key}: "
                f"expected {expected_runtime[key]!r}, got {identity[key]!r}"
            )
    if "int8" not in supported:
        raise RuntimeError("CUDA INT8 is not supported by this CTranslate2 runtime")
    return identity


def run(request: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    progress = {}
    native = NativeSoftmax(ROOT)
    try:
        return run_request(request, progress, native)
    except Exception as error:
        diagnostic = {
            'schema_version': 1,
            'status': 'error',
            'engine': ENGINE_ID,
            'timings': {**progress, 'total_seconds': time.perf_counter() - started},
            'error_type': type(error).__name__,
            'error': str(error),
            'window': getattr(error, 'window_diagnostic', None),
        }
        error.worker_diagnostic = diagnostic
        write_json_atomic(Path(request['output_dir']) / 'crisperwhisper_turbo_ct2_diagnostics.json', diagnostic)
        raise
    finally:
        native.close()


def run_request(request: dict[str, Any], progress: dict[str, Any], native: NativeSoftmax) -> dict[str, Any]:
    started = time.perf_counter()
    phase_started = started
    integrity = FileIntegrity()
    profile = verified_profile(integrity)
    tokenizer_contract = load_acoustic_event_contract(MODEL_PATH)
    preflight_seconds = progress['preflight_seconds'] = time.perf_counter() - phase_started

    phase_started = time.perf_counter()
    import soundfile
    import crisperwhisper.fallback as fallback_module
    from crisperwhisper import CrisperWhisperModel
    import coverage_recovery
    import engine
    import language_detection

    identity = runtime_identity(profile)
    runtime_import_seconds = progress['runtime_import_seconds'] = time.perf_counter() - phase_started
    engine._coverage_replan_module = coverage_recovery
    engine._decode_beam_size = 1
    fallback_module.decode_with_coverage_fallback = (
        coverage_recovery.decode_with_direct_coverage_recovery
    )

    audio_path = Path(request["audio_path"]).resolve()
    output_dir = Path(request["output_dir"]).resolve()
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file is missing: {audio_path}")
    phase_started = time.perf_counter()
    if integrity(audio_path) != request["audio_sha256"].lower():
        raise RuntimeError("Input audio SHA256 mismatch")
    progress["input_integrity_seconds"] = time.perf_counter() - phase_started

    phase_started = time.perf_counter()
    audio, sample_rate = soundfile.read(audio_path, dtype="float32", always_2d=False)
    audio_read_seconds = progress['audio_read_seconds'] = time.perf_counter() - phase_started
    if getattr(audio, "ndim", 1) != 1:
        raise RuntimeError("Mono audio is required")
    if int(sample_rate) != 16000:
        raise RuntimeError(f"A 16000 Hz source is required, got {sample_rate}")
    physical_audio_seconds = len(audio) / sample_rate
    if abs(physical_audio_seconds - float(request["audio_duration_seconds"])) > 0.01:
        raise RuntimeError(
            "Full-duration audio mismatch: "
            f"decoded={physical_audio_seconds:.6f}, "
            f"request={float(request['audio_duration_seconds']):.6f}"
        )

    vad_profile = dict(profile["vad"])
    settings = VadSettings(
        threshold=float(vad_profile["threshold"]),
        negative_threshold=float(vad_profile["negative_threshold"]),
        minimum_speech_ms=int(vad_profile["minimum_speech_ms"]),
        minimum_silence_ms=int(vad_profile["minimum_silence_ms"]),
        speech_pad_ms=int(vad_profile["speech_pad_ms"]),
        sample_rate=int(vad_profile["sample_rate"]),
        frame_samples=int(vad_profile["frame_samples"]),
    )
    def load_model():
        model = CrisperWhisperModel(
            str(MODEL_PATH),
            backend="ct2",
            device="cuda",
            compute_type="int8",
        )
        native.prepare()
        return model

    def prepare_audio():
        regions, probabilities = speech_regions(audio, VAD_MODEL_PATH, settings)
        inference_audio, spans = compact_audio(audio, regions, sample_rate)
        return regions, probabilities, inference_audio, spans

    model, prepared_audio = prepare_model_and_audio(load_model, prepare_audio, progress)
    regions, probabilities, inference_audio, spans = prepared_audio
    vad_seconds = progress['vad_seconds']
    model_load_seconds = progress['model_load_seconds']

    segmentation = dict(profile["segmentation"])
    detection_profile = dict(profile["language_detection"])
    engine._model_call_durations.clear()
    engine._encoder_counts.update(encoder_calls=0, encoder_reuse_hits=0)
    phase_started = time.perf_counter()
    platform_language = str(request["platform_language"])
    use_platform_language = bool(
        platform_language
        and request["language_detection_mode"] == language_detection.GLOBAL_FIRST_WINDOW
    )
    if use_platform_language:
        language_runs, language_detections = language_detection.platform_language_runs(
            model,
            inference_audio,
            sample_rate,
            platform_language,
        )
        language_source = "platform_metadata"
    else:
        language_runs, language_detections = language_detection.detect_language_runs(
            model,
            inference_audio,
            sample_rate,
            str(request["language_detection_mode"]),
            detection_profile,
        )
        language_source = (
            "crisper_continuous_stream_language_detection"
            if request["language_detection_mode"] == language_detection.CONTINUOUS_STREAM
            else "crisper_global_first_window_language_detection"
        )
    language_detection_seconds = progress['language_detection_seconds'] = time.perf_counter() - phase_started
    phase_started = time.perf_counter()
    transcription = engine.transcribe_language_runs(
        model,
        inference_audio,
        spans,
        sample_rate,
        language_runs,
        segmentation,
    )
    transcription_seconds = progress['transcription_seconds'] = time.perf_counter() - phase_started
    words = [dict(value) for value in list(transcription["words"])]
    text = str(transcription["text"])
    if not text.strip():
        raise RuntimeError("The full-duration transcription is empty")
    identity["native_softmax"] = native.evidence()
    language_durations: dict[str, float] = {}
    detected_languages = []
    for run_value in language_runs:
        language = str(run_value["detected_language"])
        if language not in detected_languages:
            detected_languages.append(language)
        language_durations[language] = language_durations.get(language, 0.0) + (
            float(run_value["end_seconds"]) - float(run_value["start_seconds"])
        )
    detected_language = min(
        language_durations,
        key=lambda language: (-language_durations[language], language),
    )

    timings = {
        "input_integrity_seconds": progress["input_integrity_seconds"],
        "model_wait_seconds": progress["model_wait_seconds"],
        "preparation_total_seconds": progress["preparation_total_seconds"],
        "preparation_overlap_seconds": progress["preparation_overlap_seconds"],
        "preflight_seconds": preflight_seconds,
        "runtime_import_seconds": runtime_import_seconds,
        "audio_read_seconds": audio_read_seconds,
        "vad_seconds": vad_seconds,
        "model_load_seconds": model_load_seconds,
        "language_detection_seconds": language_detection_seconds,
        "transcription_seconds": transcription_seconds,
        "model_call_seconds": sum(engine._model_call_durations),
        "model_call_count": len(engine._model_call_durations),
        "total_seconds": time.perf_counter() - started,
    }
    raw_result = {
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "engine": ENGINE_ID,
        "model": MODEL_ID,
        "model_commit": profile["model"]["resolved_commit"],
        "language": detected_language,
        "detected_languages": detected_languages,
        "language_detection_mode": request["language_detection_mode"],
        "language_source": language_source,
        "platform_language": platform_language,
        "text": text,
        "words": words,
        "segments": list(transcription["outer_windows"]),
        "physical_audio_seconds": physical_audio_seconds,
        "inference_input_seconds": len(inference_audio) / sample_rate,
        "full_duration_processed": True,
    }
    diagnostics = {
        "schema_version": 1,
        "status": "success",
        "engine": ENGINE_ID,
        "runtime_identity": identity,
        "timings": timings,
        "execution": {
            "policy": execution_policy,
            "encoder": dict(engine._encoder_counts),
            "integrity": integrity.measurements,
        },
        "vad": {
            "provider": vad_profile["provider"],
            "frame_count": len(probabilities),
            "region_count": len(regions),
            "compact_spans": spans,
            "probability_minimum": min(probabilities),
            "probability_maximum": max(probabilities),
            "probability_mean": float(np.mean(probabilities)),
        },
        "segmentation": {
            "profile": segmentation,
            "route_diagnostics": transcription.get("route_diagnostics"),
            "metrics": engine.segmentation_efficiency(
                transcription, len(inference_audio) / sample_rate
            ),
        },
        "language_detection": {
            "mode": request["language_detection_mode"],
            "language_source": language_source,
            "platform_language": platform_language,
            "profile": detection_profile,
            "detected_language": detected_language,
            "detected_languages": detected_languages,
            "language_runs": transcription["language_runs"],
            "tick_count": len(language_detections),
        },
    }
    result_profile = {
        "schema_version": 1,
        "engine": ENGINE_ID,
        "model": MODEL_ID,
        "model_commit": profile["model"]["resolved_commit"],
        "runtime_identity": identity,
        "physical_audio_seconds": physical_audio_seconds,
        "inference_input_seconds": len(inference_audio) / sample_rate,
        "full_duration_processed": True,
        "word_count": len(words),
        "detected_language": detected_language,
        "detected_languages": detected_languages,
        "language_detection_mode": request["language_detection_mode"],
        "language_source": language_source,
        "platform_language": platform_language,
        "timings": timings,
        "vad": {"compact_spans": spans, "region_count": len(regions)},
    }
    artifacts, dubbing_result = write_success_artifacts(
        output_dir,
        raw_result=raw_result,
        tokenizer_contract=tokenizer_contract,
        diagnostics=diagnostics,
        profile=result_profile,
        language_detection={
            "schema_version": 1,
            "engine": ENGINE_ID,
            "model": MODEL_ID,
            "mode": request["language_detection_mode"],
            "language_source": language_source,
            "platform_language": platform_language,
            "detected_language": detected_language,
            "detected_languages": detected_languages,
            "detections": language_detections,
            "language_runs": transcription["language_runs"],
            "transcript_produced": False,
            "word_timestamps_produced": False,
        },
        language_profile={
            "schema_version": 1,
            "engine": ENGINE_ID,
            "provider": detection_profile["provider"],
            "mode": request["language_detection_mode"],
            "language_source": language_source,
            "platform_language": platform_language,
            "profile": detection_profile,
            "model_commit": profile["model"]["resolved_commit"],
            "transcript_produced": False,
            "word_timestamps_produced": False,
        },
    )
    return {
        "status": "success",
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "engine": ENGINE_ID,
        "model": MODEL_ID,
        "model_commit": profile["model"]["resolved_commit"],
        "language": detected_language,
        "detected_languages": detected_languages,
        "language_detection_mode": request["language_detection_mode"],
        "language_source": language_source,
        "platform_language": platform_language,
        "runtime_identity": identity,
        "physical_audio_seconds": physical_audio_seconds,
        "full_duration_processed": True,
        "text": dubbing_result["text"],
        "words": dubbing_result["words"],
        "segments": dubbing_result["segments"],
        "timings": timings,
        "artifacts": artifacts,
        "completed_at": utc_now(),
    }


def main() -> int:
    args = parse_args()
    request: dict[str, Any] = {}
    try:
        request = require_request(read_json(args.request.resolve()))
        response = run(request)
        write_json_atomic(args.response.resolve(), response)
        print("CRISPER_TURBO_CT2_WORKER_SUCCESS", flush=True)
        return 0
    except BaseException as error:
        response = {
            "status": "error",
            "schema_version": RESPONSE_SCHEMA_VERSION,
            "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
            "engine": ENGINE_ID,
            "model": MODEL_ID,
            "language_detection_mode": request.get("language_detection_mode"),
            "platform_language": request.get("platform_language"),
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
            "diagnostics": getattr(error, 'worker_diagnostic', None),
            "completed_at": utc_now(),
        }
        write_json_atomic(args.response.resolve(), response)
        print(f"CRISPER_TURBO_CT2_WORKER_ERROR {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
