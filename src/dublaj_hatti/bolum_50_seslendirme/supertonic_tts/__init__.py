# -*- coding: utf-8 -*-
from .synthesis_profile import SUPERTONIC_SYNTHESIS_CONTRACT, get_supertonic_synthesis_profile
from .engine import (
    SupertonicMultiVoiceSegmentSynthesizer,
    SupertonicSegmentSynthesizer,
)
from .process import synthesize_segments, synthesize_segments_multi_voice, synthesize_supertonic_voice_segments_parallel
from .api import (
    SupertonicCandidateMeasurementResult,
    SupertonicDubResult,
    apply_manual_supertonic_voice_metadata,
    build_supertonic_dubbed_audio,
    get_supertonic_default_voice_id,
    get_supertonic_voice_gender,
    get_supertonic_voice_specs,
    measure_supertonic_candidate_segments,
    resolve_supertonic_voice_id,
)
from .execution import (
    SupertonicPreparedAudio,
    prepare_supertonic_audio_for_tts_execution,
    prepare_supertonic_candidate_results_parallel,
    prepare_supertonic_results_parallel,
)
from .final_audio_profile import (
    SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER,
    apply_supertonic_final_audio_profile,
    resolve_supertonic_final_audio_profile,
    render_supertonic_constant_gain,
)
from .parallel import (
    SupertonicRuntimeContext,
    get_supertonic_direct_runtime_context,
    start_supertonic_direct_runtime_prewarm,
    write_supertonic_parallel_summary,
)

__all__ = [
    "SupertonicCandidateMeasurementResult",
    "SupertonicDubResult",
    "SupertonicMultiVoiceSegmentSynthesizer",
    "SupertonicPreparedAudio",
    "SupertonicRuntimeContext",
    "SupertonicSegmentSynthesizer",
    "SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER",
    "SUPERTONIC_SYNTHESIS_CONTRACT",
    "get_supertonic_synthesis_profile",
    "resolve_supertonic_final_audio_profile",
    "render_supertonic_constant_gain",
    "apply_manual_supertonic_voice_metadata",
    "apply_supertonic_final_audio_profile",
    "build_supertonic_dubbed_audio",
    "get_supertonic_default_voice_id",
    "get_supertonic_direct_runtime_context",
    "get_supertonic_voice_gender",
    "get_supertonic_voice_specs",
    "measure_supertonic_candidate_segments",
    "prepare_supertonic_audio_for_tts_execution",
    "prepare_supertonic_candidate_results_parallel",
    "prepare_supertonic_results_parallel",
    "resolve_supertonic_voice_id",
    "start_supertonic_direct_runtime_prewarm",
    "synthesize_segments",
    "synthesize_segments_multi_voice",
    "synthesize_supertonic_voice_segments_parallel",
    "write_supertonic_parallel_summary",
]
