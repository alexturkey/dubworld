from __future__ import annotations

from typing import Any

from .config import WhisperCppCpuAlignConfig


def validate_words(words: list[dict[str, Any]]) -> None:
    if not words:
        raise RuntimeError("CTC kelime hizalama bos kelime listesi dondurdu")
    previous_start = -1.0
    for index, word in enumerate(words):
        text = str(word.get("word") or "").strip()
        start = float(word.get("start"))
        end = float(word.get("end"))
        if not text:
            raise RuntimeError(f"Aligned word text is empty at index {index}")
        if end < start:
            raise RuntimeError(f"Aligned word end before start at index {index}")
        if start < previous_start:
            raise RuntimeError(f"Aligned word order is not monotonic at index {index}")
        previous_start = start


def convert_result(
    whisper_cpp_result: dict[str, Any],
    alignment_result: dict[str, Any],
    config: WhisperCppCpuAlignConfig,
    total_seconds: float,
) -> dict[str, Any]:
    words = alignment_result.get("words") or []
    validate_words(words)
    segments = alignment_result.get("segments") or []
    profile_steps = [
        {
            "step": "whisper_cpp_transcribe",
            "seconds": whisper_cpp_result.get("seconds", 0),
            "alignment_input_mode": whisper_cpp_result.get("alignment_input_mode", ""),
            "alignment_input_segment_count": len(whisper_cpp_result.get("segments") or []),
            "whisper_cpp_segment_count": whisper_cpp_result.get("whisper_cpp_segment_count", 0),
        },
        {
            "step": "ctc_kelime_hizalama",
            "seconds": alignment_result.get("alignment_subprocess_seconds", 0),
            "word_count": len(words),
            "segment_count": len(segments),
        },
    ]
    for step in alignment_result.get("profile_steps") or []:
        profile_steps.append(step)
    profile_summary = {
        "engine": config.engine_id,
        "engine_display_name": config.engine_display_name,
        "transcribe_engine": "whisper.cpp",
        "alignment_engine": "ctc_kelime_hizalama",
        "model_filename": config.model_filename,
        "language": config.language,
        "detected_language": alignment_result.get("detected_language", config.language),
        "alignment_device": config.alignment_device,
        "total_worker_seconds": round(total_seconds, 3),
        "total_words": len(words),
        "total_segments": len(segments),
        "alignment_input_mode": whisper_cpp_result.get("alignment_input_mode", ""),
        "alignment_input_segment_count": len(whisper_cpp_result.get("segments") or []),
        "whisper_cpp_segment_count": whisper_cpp_result.get("whisper_cpp_segment_count", 0),
    }
    return {
        "success": True,
        "engine": config.engine_id,
        "words": words,
        "segments": segments,
        "detected_language": alignment_result.get("detected_language", config.language),
        "total_words": len(words),
        "total_segments": len(segments),
        "profile_steps": profile_steps,
        "profile_summary": profile_summary,
        "raw_transcript": whisper_cpp_result.get("transcript_text", ""),
    }
