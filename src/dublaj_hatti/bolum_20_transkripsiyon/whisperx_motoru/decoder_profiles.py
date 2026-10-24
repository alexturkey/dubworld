from __future__ import annotations

from typing import Any


WHISPERX_FLOAT32_QUALITY_PROFILE = "whisperx_float32_quality_v1"
WHISPERX_ENGINE_DEFAULT_PROFILE = "whisperx_engine_default_v1"
TRANSCRIPTION_DECODER_NOT_APPLICABLE_PROFILE = "not_applicable"
WHISPERX_DECODER_CONTRACT_VERSION = 1
TRANSCRIPTION_DECODER_NOT_APPLICABLE_CONTRACT_VERSION = 0
WHISPERX_QUALITY_MODEL_NAME = "large-v3-turbo"


def expected_transcription_decoder_profile(
    engine: str,
    model_name: str,
    compute_type: str,
) -> str:
    normalized_engine = str(engine or "").strip().lower()
    normalized_model = str(model_name or "").strip().lower()
    normalized_compute = str(compute_type or "").strip().lower()
    if normalized_engine != "whisperx":
        return TRANSCRIPTION_DECODER_NOT_APPLICABLE_PROFILE
    if (
        normalized_model in {"", WHISPERX_QUALITY_MODEL_NAME}
        and normalized_compute == "float32"
    ):
        return WHISPERX_FLOAT32_QUALITY_PROFILE
    return WHISPERX_ENGINE_DEFAULT_PROFILE


def resolve_transcription_decoder_profile(
    engine: str,
    model_name: str,
    compute_type: str,
    requested_profile: str = "",
) -> str:
    expected_profile = expected_transcription_decoder_profile(engine, model_name, compute_type)
    normalized_requested = str(requested_profile or "").strip().lower()
    if normalized_requested in {"", "auto"}:
        return expected_profile
    supported_profiles = {
        WHISPERX_FLOAT32_QUALITY_PROFILE,
        WHISPERX_ENGINE_DEFAULT_PROFILE,
        TRANSCRIPTION_DECODER_NOT_APPLICABLE_PROFILE,
    }
    if normalized_requested not in supported_profiles:
        raise ValueError(f"Bilinmeyen transkripsiyon decoder profili: {requested_profile}")
    if (
        expected_profile == TRANSCRIPTION_DECODER_NOT_APPLICABLE_PROFILE
        and normalized_requested == WHISPERX_ENGINE_DEFAULT_PROFILE
    ):
        return expected_profile
    if normalized_requested != expected_profile:
        raise ValueError(
            "Transkripsiyon decoder profili motor/model/compute sozlesmesiyle uyusmuyor: "
            f"{engine}:{model_name}:{compute_type}:{normalized_requested}"
        )
    return normalized_requested


def transcription_decoder_contract_version(engine: str) -> int:
    if str(engine or "").strip().lower() == "whisperx":
        return WHISPERX_DECODER_CONTRACT_VERSION
    return TRANSCRIPTION_DECODER_NOT_APPLICABLE_CONTRACT_VERSION


def whisperx_decoder_options(
    model_name: str,
    compute_type: str,
    requested_profile: str = "",
) -> tuple[str, dict[str, Any]]:
    profile = resolve_transcription_decoder_profile(
        "whisperx",
        model_name,
        compute_type,
        requested_profile,
    )
    suppress_tokens = [] if profile == WHISPERX_FLOAT32_QUALITY_PROFILE else [-1]
    return profile, {
        "condition_on_previous_text": False,
        "suppress_tokens": suppress_tokens,
    }


def effective_whisperx_decoder_options(model: Any) -> dict[str, Any]:
    options = getattr(model, "options", None)
    if options is None:
        raise RuntimeError("WhisperX yuklenen model decoder seceneklerini aciklamadi")
    suppress_tokens = getattr(options, "suppress_tokens", None)
    if suppress_tokens is None:
        raise RuntimeError("WhisperX yuklenen model suppress_tokens degerini aciklamadi")
    return {
        "condition_on_previous_text": bool(
            getattr(options, "condition_on_previous_text", True)
        ),
        "suppress_tokens": [int(value) for value in suppress_tokens],
    }


def validate_whisperx_decoder_options(
    model: Any,
    expected_options: dict[str, Any],
) -> dict[str, Any]:
    effective_options = effective_whisperx_decoder_options(model)
    normalized_expected = {
        "condition_on_previous_text": bool(
            expected_options["condition_on_previous_text"]
        ),
        "suppress_tokens": [int(value) for value in expected_options["suppress_tokens"]],
    }
    if effective_options != normalized_expected:
        raise RuntimeError(
            "WhisperX decoder secenekleri istenen profille uyusmuyor: "
            f"beklenen={normalized_expected}, etkin={effective_options}"
        )
    return effective_options
