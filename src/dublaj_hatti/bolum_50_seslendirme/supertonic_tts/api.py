# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from time import perf_counter
from typing import Dict, List, Optional

import numpy as np

from .synthesis_profile import SUPERTONIC_SYNTHESIS_CONTRACT, get_supertonic_synthesis_profile
from .atempo_sure_uyumu import (
    SUPERTONIC_ATEMPO_MAX_FACTOR,
    SUPERTONIC_ATEMPO_MIN_FACTOR,
    SupertonicAtempoPlan,
    SupertonicAtempoReportRecord,
    plan_supertonic_atempo_candidates,
    process_supertonic_atempo_audio,
    write_supertonic_atempo_report,
)
from .process import synthesize_segments, synthesize_segments_multi_voice, synthesize_supertonic_voice_segments_parallel
from .execution import (
    SupertonicPreparedAudio,
    prepare_supertonic_candidate_results_parallel,
    prepare_supertonic_results_parallel,
)
from .candidate_lanes import build_candidate_lanes
from .parallel import (
    SUPERTONIC_DIRECT_INTER_OP_THREADS,
    SUPERTONIC_DIRECT_INTRA_OP_THREADS,
    SUPERTONIC_PARALLEL_LANES,
    SupertonicRuntimeContext,
    get_supertonic_direct_runtime_context,
    start_supertonic_direct_runtime_prewarm,
    write_supertonic_parallel_summary,
)
from .speed_policy import get_supertonic_segment_speed

logger = logging.getLogger("dublaj_hatti")

SUPERTONIC_VOICE_SPECS = [
    ("F1", "Supertonic F1 (kadin)", "tr", "female"),
    ("F2", "Supertonic F2 (kadin)", "tr", "female"),
    ("F3", "Supertonic F3 (kadin)", "tr", "female"),
    ("F4", "Supertonic F4 (kadin)", "tr", "female"),
    ("F5", "Supertonic F5 (kadin)", "tr", "female"),
    ("M1", "Supertonic M1 (erkek)", "tr", "male"),
    ("M2", "Supertonic M2 (erkek)", "tr", "male"),
    ("M3", "Supertonic M3 (erkek)", "tr", "male"),
    ("M4", "Supertonic M4 (erkek)", "tr", "male"),
    ("M5", "Supertonic M5 (erkek)", "tr", "male"),
]
VALID_SUPERTONIC_VOICE_IDS = {item[0] for item in SUPERTONIC_VOICE_SPECS}
SUPERTONIC_VOICE_GENDERS = {item[0]: item[3] for item in SUPERTONIC_VOICE_SPECS}


@dataclass
class SupertonicDubResult:
    audio: np.ndarray
    timing_infos: List[dict]
    segment_audios: Dict[int, np.ndarray]
    prepared_audios: Dict[int, SupertonicPreparedAudio]


@dataclass
class SupertonicCandidateMeasurementResult:
    audio_by_key: Dict[tuple, SupertonicPreparedAudio]


@dataclass
class SupertonicCandidateLaneMeasurementResult:
    lanes: List[dict]
    lane_audio_by_key: Dict[tuple, SupertonicPreparedAudio]


def get_supertonic_voice_specs() -> List[tuple[str, str, str, str]]:
    return list(SUPERTONIC_VOICE_SPECS)


def get_supertonic_default_voice_id() -> str:
    return SUPERTONIC_VOICE_SPECS[0][0]


def get_supertonic_voice_gender(voice_id: str) -> str:
    normalized_voice_id = str(voice_id or "").strip().upper()
    return SUPERTONIC_VOICE_GENDERS.get(normalized_voice_id, "")


def apply_manual_supertonic_voice_metadata(segments, voice_id: str) -> None:
    normalized_voice_id = str(voice_id or "").strip().upper()
    gender = get_supertonic_voice_gender(normalized_voice_id)
    if not gender:
        raise ValueError(f"Gecersiz Supertonic manuel ses kimligi: {voice_id}")
    for segment in segments:
        setattr(segment, "supertonic_voice_id", normalized_voice_id)
        setattr(segment, "gender", gender)


def resolve_supertonic_voice_id(seg, cfg, global_voice_id: str) -> str:
    if getattr(cfg, "konusmaci_basina_ses", False):
        segment_voice_id = str(getattr(seg, "supertonic_voice_id", "") or "").strip().upper()
        if segment_voice_id in VALID_SUPERTONIC_VOICE_IDS:
            return segment_voice_id
    voice_id = str(getattr(cfg, "tts_voice_id", "") or global_voice_id or get_supertonic_default_voice_id()).strip().upper()
    return voice_id if voice_id in VALID_SUPERTONIC_VOICE_IDS else get_supertonic_default_voice_id()


def build_supertonic_dubbed_audio(
    segments,
    cfg,
    run_dir: str,
) -> SupertonicDubResult:
    segment_dicts = []
    voice_id = cfg.tts_voice_id if cfg.tts_voice_id else get_supertonic_default_voice_id()
    for seg in segments:
        seg_voice_id = resolve_supertonic_voice_id(seg, cfg, voice_id)
        segment_dicts.append({
            "index": seg.index,
            "text": seg.text,
            "start": seg.start,
            "duration": max(seg.end - seg.start, 0.1),
            "gender": getattr(seg, "gender", ""),
            "speaker": getattr(seg, "speaker", ""),
            "voice_id": seg_voice_id,
            "speed": get_supertonic_segment_speed(seg, seg_voice_id),
        })

    if getattr(cfg, "konusmaci_basina_ses", False):
        try:
            supertonic_results = synthesize_segments_multi_voice(
                segments=segment_dicts,
                language=cfg.target_lang,
                work_dir=run_dir,
                intra_op_threads=SUPERTONIC_DIRECT_INTRA_OP_THREADS,
                inter_op_threads=SUPERTONIC_DIRECT_INTER_OP_THREADS,
            )
        except TypeError as error:
            message = str(error)
            if "intra_op_threads" not in message and "inter_op_threads" not in message:
                raise
            supertonic_results = synthesize_segments_multi_voice(
                segments=segment_dicts,
                language=cfg.target_lang,
                work_dir=run_dir,
            )
    elif len(segment_dicts) > 1:
        started = perf_counter()
        runtime_context = get_supertonic_direct_runtime_context(voice_id, cfg.target_lang)
        supertonic_results, debug_records = synthesize_supertonic_voice_segments_parallel(
            synthesize_segments,
            voice_segments=segment_dicts,
            voice_id=voice_id,
            language=cfg.target_lang,
            measure_work_dir=run_dir,
            runtime_context=runtime_context,
        )
        write_supertonic_parallel_summary(
            run_dir,
            debug_records,
            len(segment_dicts),
            [voice_id],
            cfg.target_lang,
            perf_counter() - started,
        )
    else:
        try:
            supertonic_results = synthesize_segments(
                segments=segment_dicts,
                voice_id=voice_id,
                language=cfg.target_lang,
                work_dir=run_dir,
                speed=segment_dicts[0]["speed"],
                intra_op_threads=SUPERTONIC_DIRECT_INTRA_OP_THREADS,
                inter_op_threads=SUPERTONIC_DIRECT_INTER_OP_THREADS,
            )
        except TypeError as error:
            message = str(error)
            if "intra_op_threads" not in message and "inter_op_threads" not in message:
                raise
            supertonic_results = synthesize_segments(
                segments=segment_dicts,
                voice_id=voice_id,
                language=cfg.target_lang,
                work_dir=run_dir,
                speed=segment_dicts[0]["speed"],
            )

    missing_indices = [seg.index for seg in segments if seg.index not in (supertonic_results or {})]
    if missing_indices:
        raise RuntimeError(
            f"Supertonic seslendirme basarisiz: {len(missing_indices)}/{len(segments)} segment seslendirilemedi "
            f"(ilk: {missing_indices[:10]}); segment hatalari logda [SUPERTONIC] seg=N HATA satirlarinda"
        )

    timing_infos = []
    segment_audios = {}
    prepared_audios = {}
    max_end = max((seg.end for seg in segments), default=0.0)

    for idx, wav_array, timing_info, prepared_audio in prepare_supertonic_results_parallel(
        segments,
        supertonic_results,
        cfg.sample_rate,
        voice_id,
        SUPERTONIC_PARALLEL_LANES,
    ):
        segment_audios[idx] = wav_array
        timing_infos.append(timing_info)
        prepared_audios[idx] = prepared_audio

    mix = build_supertonic_audio_mix(prepared_audios, max_end, cfg.sample_rate)
    logger.info("Supertonic miks islemi tamamlandi.")
    return SupertonicDubResult(
        audio=mix,
        timing_infos=timing_infos,
        segment_audios=segment_audios,
        prepared_audios=prepared_audios,
    )

def measure_supertonic_candidate_segments(
    unique_segments: List[dict],
    cfg,
    run_dir: str,
    round_label: str,
    eval_id_to_key: Dict[int, tuple],
    runtime_context: Optional[SupertonicRuntimeContext] = None,
) -> SupertonicCandidateMeasurementResult:
    audio_by_key = {}
    measure_work_dir = os.path.join(run_dir, "real_tts_candidate_selection", round_label)
    segments_by_voice = {}
    for item in unique_segments:
        voice_id = str(item.get("voice_id") or get_supertonic_default_voice_id()).strip().upper()
        segments_by_voice.setdefault(voice_id, []).append(item)

    all_debug_records = []
    started = perf_counter()
    for voice_id, voice_segments in segments_by_voice.items():
        results, debug_records = synthesize_supertonic_voice_segments_parallel(
            synthesize_segments=synthesize_segments,
            voice_segments=voice_segments,
            voice_id=voice_id,
            language=cfg.target_lang,
            measure_work_dir=measure_work_dir,
            runtime_context=runtime_context,
        )
        all_debug_records.extend(debug_records)
        for key, prepared_audio in prepare_supertonic_candidate_results_parallel(
            results,
            cfg.sample_rate,
            eval_id_to_key,
            SUPERTONIC_PARALLEL_LANES,
        ):
            audio_by_key[key] = prepared_audio
    write_supertonic_parallel_summary(
        measure_work_dir,
        all_debug_records,
        len(unique_segments),
        sorted(segments_by_voice.keys()),
        cfg.target_lang,
        perf_counter() - started,
    )
    return SupertonicCandidateMeasurementResult(audio_by_key=audio_by_key)


def measure_supertonic_candidate_lanes(
    candidate_records: List[dict],
    cfg,
    run_dir: str,
    round_label: str,
    runtime_context: Optional[SupertonicRuntimeContext] = None,
) -> SupertonicCandidateLaneMeasurementResult:
    lanes = build_candidate_lanes(candidate_records, round_label)
    lane_segments = []
    lane_key_to_lane = {}
    for eval_id, lane in enumerate(lanes, start=1):
        lane_key = ("supertonic_candidate_lane", lane["lane_id"])
        lane["audio_key"] = lane_key
        lane_key_to_lane[lane_key] = lane
        speeds = {record.get("speed") for record in lane["records"]}
        if len(speeds) != 1:
            raise RuntimeError(f"Supertonic aday lane hizlari uyusmuyor: lane={lane['lane_id']}")
        lane_segments.append({
            "index": eval_id,
            "text": lane["spoken_text"],
            "start": 0.0,
            "duration": sum(float(record["duration"]) for record in lane["records"]),
            "voice_id": lane["voice_id"],
            "speed": next(iter(speeds)),
        })
        lane["eval_id"] = eval_id
    if not lane_segments:
        return SupertonicCandidateLaneMeasurementResult(lanes=[], lane_audio_by_key={})
    work_dir = os.path.join(run_dir, "real_tts_candidate_selection", round_label, "candidate_lanes")
    grouped = {}
    for item in lane_segments:
        grouped.setdefault(str(item["voice_id"]), []).append(item)
    raw_results = {}
    for voice_id, items in grouped.items():
        results, _ = synthesize_supertonic_voice_segments_parallel(
            synthesize_segments=synthesize_segments,
            voice_segments=items,
            voice_id=voice_id,
            language=cfg.target_lang,
            measure_work_dir=work_dir,
            runtime_context=runtime_context,
            return_actual_chunks=True,
        )
        raw_results.update(results)
    lane_audio_by_key = {}
    eval_id_to_lane_key = {int(lane["eval_id"]): lane["audio_key"] for lane in lanes}
    for lane_key, prepared_audio in prepare_supertonic_candidate_results_parallel(
        raw_results,
        cfg.sample_rate,
        eval_id_to_lane_key,
        SUPERTONIC_PARALLEL_LANES,
    ):
        lane_audio_by_key[lane_key] = prepared_audio
    missing = [lane["lane_id"] for lane in lanes if lane["audio_key"] not in lane_audio_by_key]
    if missing:
        raise RuntimeError(f"Supertonic aday lane sesleri eksik: {missing}")
    return SupertonicCandidateLaneMeasurementResult(lanes=lanes, lane_audio_by_key=lane_audio_by_key)


def build_supertonic_audio_mix(
    segment_audios: Dict[int, SupertonicPreparedAudio],
    total_duration: float,
    sample_rate: int,
) -> np.ndarray:
    total_samples = int((total_duration + 1.0) * sample_rate)
    mix = np.zeros(total_samples, dtype=np.float32)
    for seg_audio in segment_audios.values():
        start_sample = int(seg_audio.start_time * sample_rate)
        audio = seg_audio.wav_array
        end_sample = start_sample + len(audio)
        if end_sample > len(mix):
            end_sample = len(mix)
            audio = audio[:end_sample - start_sample]
        mix[start_sample:end_sample] += audio
    peak = float(np.max(np.abs(mix)) or 1.0)
    return mix / peak * 0.9
