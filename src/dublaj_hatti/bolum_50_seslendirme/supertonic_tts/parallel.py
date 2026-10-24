# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Lock
from time import perf_counter
from typing import List, Optional

import numpy as np

from .synthesis_profile import SUPERTONIC_SYNTHESIS_CONTRACT, SUPERTONIC_TOTAL_STEPS, get_supertonic_synthesis_profile
from .runtime import chunk_text, deterministic_seed_from_hasher
from .speed_policy import (
    SUPERTONIC_SPEED_POLICY,
    get_supertonic_voice_speed,
    validate_supertonic_voice_speed,
)

logger = logging.getLogger("dublaj_hatti")

# Neden: 4 serit x 2 is parcacigi olculen en hizli ve cikti ayni; daha cok is parcacigi ciktiyi degistirdi. bkz. docs/engineering/pinned-values.md#supertonic-synthesis
SUPERTONIC_PARALLEL_LANES = 4
SUPERTONIC_PARALLEL_INTRA_OP_THREADS = 2
SUPERTONIC_PARALLEL_INTER_OP_THREADS = 1
SUPERTONIC_DIRECT_INTRA_OP_THREADS = 3
SUPERTONIC_DIRECT_INTER_OP_THREADS = 1
@dataclass
class SupertonicRuntimeContext:
    synthesizers: dict[tuple, object] = field(default_factory=dict)
    lock: object = field(default_factory=Lock)


def start_supertonic_direct_runtime_prewarm(voice_id: str, language: str) -> bool:
    return False


def get_supertonic_direct_runtime_context(voice_id: str, language: str) -> SupertonicRuntimeContext:
    get_supertonic_voice_speed(str(voice_id or "F1").strip().upper())
    return SupertonicRuntimeContext()


def synthesize_supertonic_voice_segments_parallel(
    synthesize_segments,
    voice_segments: List[dict],
    voice_id: str,
    language: str,
    measure_work_dir: str,
    runtime_context: Optional[SupertonicRuntimeContext] = None,
    return_actual_chunks: bool = False,
):
    selected_voice_id = str(voice_id or "F1").strip().upper()
    selected_speed = get_supertonic_voice_speed(selected_voice_id)
    for item in voice_segments:
        item_voice_id = str(item.get("voice_id") or selected_voice_id).strip().upper()
        if item_voice_id != selected_voice_id:
            raise RuntimeError(
                f"Supertonic paralel ses profili uyusmuyor: expected={selected_voice_id} actual={item_voice_id}"
            )
        if item.get("speed") is None:
            raise RuntimeError(f"Supertonic segment hizi yok: segment={item.get('index', '')}")
        validate_supertonic_voice_speed(selected_voice_id, item["speed"])
    if runtime_context is not None:
        with runtime_context.lock:
            return _synthesize_supertonic_voice_segments_parallel_unlocked(
                synthesize_segments,
                voice_segments,
                selected_voice_id,
                language,
                measure_work_dir,
                runtime_context,
                selected_speed,
                return_actual_chunks,
            )
    return _synthesize_supertonic_voice_segments_parallel_unlocked(
        synthesize_segments,
        voice_segments,
        selected_voice_id,
        language,
        measure_work_dir,
        runtime_context,
        selected_speed,
        return_actual_chunks,
    )


def _synthesize_supertonic_voice_segments_parallel_unlocked(
    synthesize_segments,
    voice_segments: List[dict],
    voice_id: str,
    language: str,
    measure_work_dir: str,
    runtime_context: Optional[SupertonicRuntimeContext] = None,
    speed: Optional[float] = None,
    return_actual_chunks: bool = False,
):
    selected_speed = (
        get_supertonic_voice_speed(voice_id)
        if speed is None
        else validate_supertonic_voice_speed(voice_id, speed)
    )
    lane_count = min(SUPERTONIC_PARALLEL_LANES, len(voice_segments))
    if lane_count <= 1:
        if runtime_context is not None and len(voice_segments) == 1:
            parallel_result = synthesize_supertonic_single_segment_parallel_chunks(
                voice_segments[0],
                voice_id,
                language,
                measure_work_dir,
                runtime_context,
                selected_speed,
                return_actual_chunks,
            )
            if parallel_result is not None:
                return parallel_result
        results = call_supertonic_synthesize_segments(
            synthesize_segments,
            segments=voice_segments,
            voice_id=voice_id,
            language=language,
            work_dir=measure_work_dir,
            runtime_context=runtime_context,
            lane_index=0,
            speed=selected_speed,
            return_records=True,
            return_actual_chunks=return_actual_chunks,
        )
        return results

    lanes = split_supertonic_segments_by_cost(voice_segments, lane_count)
    lane_root = os.path.join(measure_work_dir, "supertonic_parallel", voice_id)
    combined_results = {}
    debug_records = []
    logger.info(
        "[SUPERTONIC] Paralel olcum basliyor voice=%s lanes=%d segments=%d",
        voice_id,
        lane_count,
        len(voice_segments),
    )
    with ThreadPoolExecutor(max_workers=lane_count) as executor:
        futures = [
            executor.submit(
                synthesize_supertonic_lane,
                synthesize_segments,
                lane_segments,
                voice_id,
                language,
                os.path.join(lane_root, f"lane_{lane_index + 1}"),
                runtime_context,
                lane_index,
                selected_speed,
                return_actual_chunks,
            )
            for lane_index, lane_segments in enumerate(lanes)
            if lane_segments
        ]
        for future in futures:
            lane_results, lane_records = future.result()
            combined_results.update(lane_results)
            debug_records.extend(lane_records)
    logger.info(
        "[SUPERTONIC] Paralel olcum tamamlandi voice=%s produced=%d",
        voice_id,
        len(combined_results),
    )
    return combined_results, debug_records


def synthesize_supertonic_single_segment_parallel_chunks(
    segment: dict,
    voice_id: str,
    language: str,
    work_dir: str,
    runtime_context: SupertonicRuntimeContext,
    speed: float,
    return_actual_chunks: bool,
):
    text = str(segment.get("text") or "")
    chunks = chunk_text(text, 120 if str(language).strip().lower()[:2] in ("ko", "ja") else 300)
    if len(chunks) <= 1:
        return None

    started = perf_counter()
    segment_index = int(segment["index"])
    target_duration = float(segment.get("duration") or 0.0)
    synthesizer_pairs = [
        get_supertonic_synthesizer(runtime_context, voice_id, language, lane_index, speed)
        for lane_index in range(min(SUPERTONIC_PARALLEL_LANES, len(chunks)))
    ]
    synthesizers = [item[0] for item in synthesizer_pairs]
    runtime_reused = all(item[1] for item in synthesizer_pairs)
    first = synthesizers[0]
    base_seed = deterministic_seed_from_hasher(text, first.seed_hasher_template)
    assignments = [[] for _ in synthesizers]
    for chunk_index, chunk in enumerate(chunks):
        assignments[chunk_index % len(synthesizers)].append((chunk_index, chunk))

    def run_lane(lane_index: int):
        synthesizer = synthesizers[lane_index]
        lane_results = []
        for chunk_index, chunk in assignments[lane_index]:
            wav, duration = synthesizer.runtime.infer(
                [chunk],
                [synthesizer.language],
                synthesizer.style,
                synthesizer.total_step,
                synthesizer.speed,
                (base_seed + chunk_index) % (2 ** 32),
            )
            lane_results.append((chunk_index, chunk, wav, float(duration[0])))
        return lane_results

    try:
        with ThreadPoolExecutor(max_workers=len(synthesizers)) as executor:
            lane_results = list(executor.map(run_lane, range(len(synthesizers))))
        ordered_chunks = sorted(
            (item for lane_result in lane_results for item in lane_result),
            key=lambda item: item[0],
        )
        silence_seconds = 0.3
        silence = np.zeros((1, int(silence_seconds * first.runtime.sample_rate)), dtype=np.float32)
        wav_parts = []
        chunk_timeline = []
        actual_chunks = []
        predicted_duration = 0.0
        for chunk_index, (_, chunk, wav, duration) in enumerate(ordered_chunks):
            if chunk_index:
                wav_parts.append(silence)
                predicted_duration += silence_seconds
            chunk_start = predicted_duration
            wav_parts.append(wav)
            actual_chunks.append({"text": chunk, "wav_array": wav[0].astype(np.float32, copy=False)})
            predicted_duration += duration
            chunk_timeline.append({"text": chunk, "start": chunk_start, "end": predicted_duration})
        wav = wav_parts[0] if len(wav_parts) == 1 else np.concatenate(wav_parts, axis=1)
        audio = wav[0].astype(np.float32, copy=False)
        raw_duration = len(audio) / first.runtime.sample_rate
        elapsed = perf_counter() - started
        debug = {
            "status": "ok",
            "voice_id": first.voice_id,
            "language": first.language,
            "seed": base_seed,
            "speed": first.speed,
            "synthesis_profile": get_supertonic_synthesis_profile(),
            "total_step": first.total_step,
            "chunk_count": len(chunks),
            "chunk_timeline": chunk_timeline,
            "predicted_duration": predicted_duration,
            "raw_duration": raw_duration,
            "target_duration": target_duration,
            "elapsed_seconds": elapsed,
            "parallel_chunk_lanes": len(synthesizers),
            "runtime_reused": runtime_reused,
        }
        result = {
            "wav_array": audio,
            "sample_rate": first.runtime.sample_rate,
            "debug": debug,
            "actual_chunks": actual_chunks if return_actual_chunks else [],
            "inter_chunk_silence_seconds": silence_seconds if return_actual_chunks else 0.0,
        }
        record = {
            "segment_index": segment_index,
            "status": "ok",
            "voice_id": first.voice_id,
            "language": first.language,
            "seed": base_seed,
            "speed": first.speed,
            "synthesis_profile": get_supertonic_synthesis_profile(),
            "total_step": first.total_step,
            "chunk_count": len(chunks),
            "predicted_duration": round(predicted_duration, 6),
            "raw_duration": round(raw_duration, 6),
            "target_duration": round(target_duration, 6),
            "duration_ratio": round(raw_duration / target_duration, 6) if target_duration > 0 else None,
            "elapsed_seconds": round(elapsed, 3),
            "parallel_chunk_lanes": len(synthesizers),
            "runtime_reused": runtime_reused,
        }
        _write_supertonic_single_segment_debug(work_dir, record, first, elapsed, True, runtime_reused)
        logger.info(
            "[SUPERTONIC] Paralel chunk olcum tamamlandi voice=%s chunks=%d lanes=%d elapsed=%.3fs",
            voice_id,
            len(chunks),
            len(synthesizers),
            elapsed,
        )
        return {segment_index: result}, [record]
    except Exception as error:
        elapsed = perf_counter() - started
        record = {
            "segment_index": segment_index,
            "status": "failed",
            "voice_id": first.voice_id,
            "language": first.language,
            "error": str(error),
            "elapsed_seconds": round(elapsed, 3),
            "parallel_chunk_lanes": len(synthesizers),
            "runtime_reused": runtime_reused,
        }
        _write_supertonic_single_segment_debug(work_dir, record, first, elapsed, False, runtime_reused)
        logger.warning("[SUPERTONIC] Paralel chunk olcum hatasi seg=%d: %s", segment_index, error)
        return {}, [record]


def _write_supertonic_single_segment_debug(
    work_dir: str,
    record: dict,
    synthesizer,
    elapsed_seconds: float,
    success: bool,
    runtime_reused: bool,
) -> None:
    debug_dir = os.path.join(work_dir, "supertonic_tts")
    os.makedirs(debug_dir, exist_ok=True)
    summary = {
        "status": "completed" if success else "partial",
        "segment_count": 1,
        "successful_count": 1 if success else 0,
        "failed_count": 0 if success else 1,
        "voice_id": synthesizer.voice_id,
        "language": synthesizer.language,
        "speed": synthesizer.speed,
        "synthesis_profile": get_supertonic_synthesis_profile(),
        "total_step": synthesizer.total_step,
        "model_dir": str(synthesizer.model_dir),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "runtime_reused": runtime_reused,
        "parallel_chunk_lanes": int(record.get("parallel_chunk_lanes") or 1),
    }
    with open(os.path.join(debug_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(debug_dir, "segments.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def synthesize_supertonic_lane(
    synthesize_segments,
    lane_segments: List[dict],
    voice_id: str,
    language: str,
    work_dir: str,
    runtime_context: Optional[SupertonicRuntimeContext] = None,
    lane_index: int = 0,
    speed: Optional[float] = None,
    return_actual_chunks: bool = False,
):
    results = call_supertonic_synthesize_segments(
        synthesize_segments,
        segments=lane_segments,
        voice_id=voice_id,
        language=language,
        work_dir=work_dir,
        runtime_context=runtime_context,
        lane_index=lane_index,
        speed=speed,
        return_records=True,
        write_debug_files=False,
        return_actual_chunks=return_actual_chunks,
    )
    return results


def get_supertonic_synthesizer(
    runtime_context: SupertonicRuntimeContext,
    voice_id: str,
    language: str,
    lane_index: int,
    speed: Optional[float] = None,
):
    from .engine import SupertonicSegmentSynthesizer

    selected_speed = (
        get_supertonic_voice_speed(voice_id)
        if speed is None
        else validate_supertonic_voice_speed(voice_id, speed)
    )
    key = (
        str(voice_id or "F1").strip().upper(),
        str(language or "tr").strip().lower()[:2],
        int(lane_index),
        round(selected_speed, 6),
        SUPERTONIC_PARALLEL_INTRA_OP_THREADS,
        SUPERTONIC_PARALLEL_INTER_OP_THREADS,
        SUPERTONIC_SYNTHESIS_CONTRACT,
    )
    synthesizer = runtime_context.synthesizers.get(key)
    if synthesizer is None:
        synthesizer = SupertonicSegmentSynthesizer(
            voice_id=voice_id,
            language=language,
            speed=selected_speed,
            intra_op_threads=SUPERTONIC_PARALLEL_INTRA_OP_THREADS,
            inter_op_threads=SUPERTONIC_PARALLEL_INTER_OP_THREADS,
        )
        runtime_context.synthesizers[key] = synthesizer
        return synthesizer, False
    return synthesizer, True


def call_supertonic_synthesize_segments(
    synthesize_segments,
    segments: List[dict],
    voice_id: str,
    language: str,
    work_dir: str,
    runtime_context: Optional[SupertonicRuntimeContext] = None,
    lane_index: int = 0,
    speed: Optional[float] = None,
    return_records: bool = False,
    write_debug_files: bool = True,
    return_actual_chunks: bool = False,
):
    if runtime_context is not None:
        started = perf_counter()
        synthesizer, runtime_reused = get_supertonic_synthesizer(runtime_context, voice_id, language, lane_index, speed)
        results, records, successful, failed = synthesizer.synthesize_segments(
            segments,
            work_dir,
            return_actual_chunks=return_actual_chunks,
        )
        if write_debug_files:
            debug_dir = os.path.join(work_dir, "supertonic_tts")
            os.makedirs(debug_dir, exist_ok=True)
            summary = {
                "status": "completed" if failed == 0 else "partial",
                "segment_count": len(segments),
                "successful_count": successful,
                "failed_count": failed,
                "voice_id": synthesizer.voice_id,
                "language": synthesizer.language,
                "speed": synthesizer.speed,
                "synthesis_profile": get_supertonic_synthesis_profile(),
                "total_step": synthesizer.total_step,
                "model_dir": str(synthesizer.model_dir),
                "elapsed_seconds": round(perf_counter() - started, 3),
                "runtime_reused": runtime_reused,
            }
            with open(os.path.join(debug_dir, "summary.json"), "w", encoding="utf-8") as fh:
                json.dump(summary, fh, ensure_ascii=False, indent=2)
            with open(os.path.join(debug_dir, "segments.jsonl"), "w", encoding="utf-8") as fh:
                for record in records:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        if return_records:
            return results, records
        return results
    try:
        results = synthesize_segments(
            segments=segments,
            voice_id=voice_id,
            language=language,
            work_dir=work_dir,
            intra_op_threads=SUPERTONIC_PARALLEL_INTRA_OP_THREADS,
            inter_op_threads=SUPERTONIC_PARALLEL_INTER_OP_THREADS,
            speed=speed,
            return_actual_chunks=return_actual_chunks,
        )
        if return_records:
            return results, read_supertonic_debug_records(os.path.join(work_dir, "supertonic_tts"))
        return results
    except TypeError as error:
        message = str(error)
        if "intra_op_threads" not in message and "inter_op_threads" not in message:
            raise
        results = synthesize_segments(
            segments=segments,
            voice_id=voice_id,
            language=language,
            work_dir=work_dir,
            speed=speed,
            return_actual_chunks=return_actual_chunks,
        )
        if return_records:
            return results, read_supertonic_debug_records(os.path.join(work_dir, "supertonic_tts"))
        return results


def split_supertonic_segments_by_cost(segments: List[dict], lane_count: int) -> List[List[dict]]:
    lanes = [[] for _ in range(lane_count)]
    lane_weights = [0.0 for _ in range(lane_count)]
    ordered_segments = sorted(
        segments,
        key=lambda item: (float(item.get("duration") or 0.0), len(str(item.get("text") or ""))),
        reverse=True,
    )
    for item in ordered_segments:
        lane_index = min(range(lane_count), key=lambda idx: lane_weights[idx])
        lanes[lane_index].append(item)
        lane_weights[lane_index] += max(
            float(item.get("duration") or 0.0),
            len(str(item.get("text") or "")) / 18.0,
            0.1,
        )
    return lanes


def read_supertonic_debug_records(debug_dir: str) -> List[dict]:
    records_path = os.path.join(debug_dir, "segments.jsonl")
    if not os.path.exists(records_path):
        return []
    records = []
    with open(records_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_supertonic_parallel_summary(measure_work_dir: str, records: List[dict], segment_count: int, voice_ids: List[str], language: str, elapsed_seconds: float) -> None:
    debug_dir = os.path.join(measure_work_dir, "supertonic_tts")
    os.makedirs(debug_dir, exist_ok=True)
    ordered_records = sorted(records, key=lambda item: int(item.get("segment_index") or 0))
    records_path = os.path.join(debug_dir, "segments.jsonl")
    with open(records_path, "w", encoding="utf-8") as fh:
        for record in ordered_records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    failed_count = sum(1 for item in ordered_records if item.get("status") == "failed")
    summary = {
        "status": "completed" if failed_count == 0 else "partial",
        "segment_count": segment_count,
        "successful_count": segment_count - failed_count,
        "failed_count": failed_count,
        "voice_id": voice_ids[0] if len(voice_ids) == 1 else "multiple",
        "voice_ids": voice_ids,
        "language": language,
        "speed_policy": SUPERTONIC_SPEED_POLICY,
        "voice_speeds": {
            voice_id: get_supertonic_voice_speed(voice_id)
            for voice_id in sorted(set(voice_ids))
        },
        "speed_values": sorted({round(float(item["speed"]), 6) for item in ordered_records if item.get("speed") is not None}),
        "synthesis_profile": get_supertonic_synthesis_profile(),
        "total_step": SUPERTONIC_TOTAL_STEPS,
        "parallel_lanes": SUPERTONIC_PARALLEL_LANES,
        "intra_op_threads": SUPERTONIC_PARALLEL_INTRA_OP_THREADS,
        "inter_op_threads": SUPERTONIC_PARALLEL_INTER_OP_THREADS,
        "elapsed_seconds": round(elapsed_seconds, 3),
    }
    with open(os.path.join(debug_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
