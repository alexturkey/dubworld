# -*- coding: utf-8 -*-
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict

import numpy as np


@dataclass
class SupertonicPreparedAudio:
    index: int
    wav_array: np.ndarray
    start_time: float
    raw_duration: float
    engine_raw_duration: float
    processed_duration: float
    trim_meta: dict
    engine_name: str = "Supertonic TTS"


def prepare_supertonic_audio_for_tts_execution(
    wav_array: np.ndarray,
    sample_rate: int,
    output_sample_rate: int,
) -> tuple[np.ndarray, float, float, dict]:
    audio = np.asarray(wav_array, dtype=np.float32)
    engine_raw_duration = len(audio) / sample_rate if sample_rate > 0 else 0.0
    processed = audio
    if sample_rate != output_sample_rate:
        from scipy import signal
        num_samples = int(len(processed) * output_sample_rate / sample_rate)
        processed = signal.resample(processed, num_samples).astype(np.float32)
    processed = processed.astype(np.float32, copy=False)
    processed_duration = len(processed) / output_sample_rate if output_sample_rate > 0 else 0.0
    trim_meta = {
        "engine_raw_duration": engine_raw_duration,
        "processed_duration": processed_duration,
        "trim_source": "none",
    }
    return processed, engine_raw_duration, processed_duration, trim_meta


def prepare_supertonic_result_for_segment(
    seg,
    raw_result: dict,
    output_sample_rate: int,
    voice_id: str,
):
    idx = seg.index
    wav_array = raw_result["wav_array"]
    sample_rate = int(raw_result["sample_rate"])
    wav_array, engine_raw_duration, processed_duration, trim_meta = prepare_supertonic_audio_for_tts_execution(
        wav_array,
        sample_rate,
        output_sample_rate,
    )
    original_duration = seg.end - seg.start
    timing_info = {
        "segment_index": idx,
        "tts_processed_duration": processed_duration,
        "tts_engine_raw_duration": engine_raw_duration,
        "original_duration": original_duration,
        "start_time": seg.start,
        "engine": "supertonic",
        "voice_id": voice_id,
        "supertonic_trim_source": trim_meta.get("trim_source", ""),
    }
    segment_audio = SupertonicPreparedAudio(
        index=idx,
        wav_array=wav_array,
        start_time=seg.start,
        raw_duration=processed_duration,
        engine_raw_duration=engine_raw_duration,
        processed_duration=processed_duration,
        trim_meta=trim_meta,
    )
    return idx, wav_array, timing_info, segment_audio


def prepare_supertonic_results_parallel(
    segments,
    supertonic_results: Dict[int, dict],
    output_sample_rate: int,
    voice_id: str,
    worker_count: int,
):
    items = [(seg, supertonic_results[seg.index]) for seg in segments if seg.index in supertonic_results]
    if len(items) <= 1:
        return [
            prepare_supertonic_result_for_segment(
                seg,
                raw_result,
                output_sample_rate,
                str((raw_result.get("debug") or {}).get("voice_id") or voice_id),
            )
            for seg, raw_result in items
        ]
    max_workers = min(worker_count, len(items))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                prepare_supertonic_result_for_segment,
                seg,
                raw_result,
                output_sample_rate,
                str((raw_result.get("debug") or {}).get("voice_id") or voice_id),
            )
            for seg, raw_result in items
        ]
        return [future.result() for future in futures]


def prepare_supertonic_candidate_result_for_key(
    eval_id: int,
    raw_result: dict,
    output_sample_rate: int,
    eval_id_to_key: Dict[int, tuple],
):
    key = eval_id_to_key.get(eval_id)
    wav_array = raw_result.get("wav_array") if isinstance(raw_result, dict) else None
    if not key or wav_array is None:
        return None
    sample_rate = int(raw_result.get("sample_rate", output_sample_rate))
    source_wav_array = np.asarray(wav_array, dtype=np.float32)
    wav_array, engine_raw_duration, processed_duration, trim_meta = prepare_supertonic_audio_for_tts_execution(
        wav_array,
        sample_rate,
        output_sample_rate,
    )
    segment_audio = SupertonicPreparedAudio(
        index=eval_id,
        wav_array=wav_array,
        start_time=0.0,
        raw_duration=processed_duration,
        engine_raw_duration=engine_raw_duration,
        processed_duration=processed_duration,
        trim_meta=trim_meta,
    )
    actual_chunks = list(raw_result.get("actual_chunks") or [])
    if actual_chunks:
        actual_chunk_texts = [str(chunk.get("text") or "").strip() for chunk in actual_chunks]
        actual_chunk_sample_counts = [
            len(np.asarray(chunk.get("wav_array"), dtype=np.float32))
            for chunk in actual_chunks
        ]
        if any(not text for text in actual_chunk_texts):
            raise RuntimeError(f"Supertonic aday lane gercek chunk metni gecersiz: eval_id={eval_id}")
        if any(sample_count <= 0 for sample_count in actual_chunk_sample_counts):
            raise RuntimeError(f"Supertonic aday lane gercek chunk WAV bilgisi gecersiz: eval_id={eval_id}")
        inter_chunk_silence_samples = int(
            float(raw_result.get("inter_chunk_silence_seconds") or 0.0) * sample_rate
        )
        expected_source_samples = (
            sum(actual_chunk_sample_counts)
            + inter_chunk_silence_samples * max(0, len(actual_chunk_sample_counts) - 1)
        )
        if expected_source_samples != len(source_wav_array):
            raise RuntimeError(
                "Supertonic aday lane gercek chunk WAV toplami birlesik sesle uyusmuyor: "
                f"eval_id={eval_id} expected={expected_source_samples} actual={len(source_wav_array)}"
            )
        setattr(segment_audio, "actual_chunk_sample_counts", actual_chunk_sample_counts)
        setattr(segment_audio, "actual_chunk_texts", actual_chunk_texts)
        setattr(segment_audio, "inter_chunk_silence_source_samples", inter_chunk_silence_samples)
        setattr(segment_audio, "physical_source_sample_count", expected_source_samples)
        setattr(segment_audio, "preserve_physical_audio_bounds", True)
    chunk_timeline = list((raw_result.get("debug") or {}).get("chunk_timeline") or [])
    if chunk_timeline:
        setattr(segment_audio, "chunk_timeline", chunk_timeline)
    return key, segment_audio


def prepare_supertonic_candidate_results_parallel(
    results: Dict[int, dict],
    output_sample_rate: int,
    eval_id_to_key: Dict[int, tuple],
    worker_count: int,
):
    ordered_items = sorted(results.items(), key=lambda item: int(item[0]))
    if len(ordered_items) <= 1:
        return [
            item for item in (
                prepare_supertonic_candidate_result_for_key(eval_id, raw_result, output_sample_rate, eval_id_to_key)
                for eval_id, raw_result in ordered_items
            )
            if item is not None
        ]
    max_workers = min(worker_count, len(ordered_items))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(prepare_supertonic_candidate_result_for_key, eval_id, raw_result, output_sample_rate, eval_id_to_key)
            for eval_id, raw_result in ordered_items
        ]
        return [item for item in (future.result() for future in futures) if item is not None]
