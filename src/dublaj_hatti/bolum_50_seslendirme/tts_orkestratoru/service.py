# -*- coding: utf-8 -*-
"""TTS servisi: segment seslendirme ve gercek aday secimi (Supertonic 3)."""

from __future__ import annotations

import logging
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, TYPE_CHECKING

import numpy as np

from dublaj_hatti.bolum_50_seslendirme.candidate_alignment import align_candidate_audio_batch
from dublaj_hatti.bolum_50_seslendirme.tts_orkestratoru.processor import SegmentAudio
from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.api import (
    SUPERTONIC_ATEMPO_MAX_FACTOR,
    SUPERTONIC_ATEMPO_MIN_FACTOR,
    SupertonicAtempoPlan,
    SupertonicRuntimeContext,
    build_supertonic_audio_mix,
    build_supertonic_dubbed_audio,
    get_supertonic_default_voice_id,
    get_supertonic_direct_runtime_context,
    get_supertonic_voice_specs,
    measure_supertonic_candidate_lanes,
    plan_supertonic_atempo_candidates,
    process_supertonic_atempo_audio,
    resolve_supertonic_voice_id,
    start_supertonic_direct_runtime_prewarm,
    write_supertonic_atempo_report,
)
from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.flow_modes import get_supertonic_flow_settings
from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.speed_policy import get_supertonic_segment_speed

if TYPE_CHECKING:
    from dublaj_hatti.bolum_00_omurga.core.dubber import DubConfig, Segment

logger = logging.getLogger("dublaj_hatti")
# Neden: kanonik kabul bandi (ADR 0010); eski 0.70 esigi geri gelmemeli. bkz. docs/engineering/pinned-values.md#duration-matching
REAL_TTS_MIN_VIDEO_SPEED = 0.90
REAL_TTS_MAX_VIDEO_SPEED = 1.15


@dataclass
class TTSBuildResult:
    audio: np.ndarray
    timing_infos: List
    segment_audios: Mapping[int, np.ndarray]
    verified_word_timeline: List[dict] = field(default_factory=list)


@dataclass
class RealTTSCandidateSelectionResult:
    tts_result: TTSBuildResult
    selected_texts_by_id: Dict[str, str]
    selected_segments: List[dict]
    problem_segments: List[dict]
    candidate_report: List[dict]
    report_path: str
    selected_audio_by_id: Dict[str, SegmentAudio]
    measured_audio_by_key: Dict[tuple, SegmentAudio]


def _segment_voice_id(seg: "Segment", cfg: "DubConfig", global_voice_id: str) -> str:
    return global_voice_id


def _segment_pitch(seg: "Segment", cfg: "DubConfig") -> str:
    seg_pitch = getattr(seg, "pitch", "+0Hz")
    if seg_pitch == "+0Hz" and cfg.tts_pitch != "+0Hz":
        return cfg.tts_pitch
    return seg_pitch


def _clean_candidate_texts(values: List[str], fallback_text: str) -> List[str]:
    cleaned = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    if not cleaned and str(fallback_text or "").strip():
        cleaned.append(str(fallback_text).strip())
    return cleaned


def _candidate_status(video_speed: float) -> str:
    if REAL_TTS_MIN_VIDEO_SPEED <= video_speed <= REAL_TTS_MAX_VIDEO_SPEED:
        return "accepted"
    if video_speed > REAL_TTS_MAX_VIDEO_SPEED:
        return "too_short_audio"
    return "too_long_audio"


def _candidate_score(item: dict) -> tuple:
    accepted_penalty = 0 if item["status"] == "accepted" else 1
    atempo_distance = (
        abs(float(item.get("requested_atempo_factor", 1.0)) - 1.0)
        if item.get("atempo_selection_enabled")
        else 0.0
    )
    return (
        accepted_penalty,
        abs(float(item.get("duration_seconds", item["duration"])) - float(item.get("target_duration_seconds", item["target_duration"]))),
        atempo_distance,
        int(item["candidate_number"]),
    )


def _candidate_input_score_before_atempo(item: dict) -> tuple:
    processed_duration = float(item["processed_duration"])
    target_duration = float(item["target_duration"])
    video_speed = target_duration / processed_duration if processed_duration > 0 else 1.0
    return _candidate_score({
        "status": _candidate_status(video_speed),
        "duration_seconds": processed_duration,
        "duration": processed_duration,
        "target_duration_seconds": target_duration,
        "target_duration": target_duration,
        "candidate_number": int(item["candidate_number"]),
    })


def _processed_audio_duration(segment_audio: SegmentAudio) -> float:
    return float(getattr(segment_audio, "processed_duration", getattr(segment_audio, "raw_duration", 0.0) or 0.0) or 0.0)


def _measured_candidate_audio_is_reusable(segment_audio: Optional[SegmentAudio]) -> bool:
    if segment_audio is None or not isinstance(getattr(segment_audio, "wav_array", None), np.ndarray):
        return False
    if segment_audio.wav_array.ndim != 1 or segment_audio.wav_array.dtype != np.float32:
        return False
    if segment_audio.wav_array.size <= 0 or not np.isfinite(segment_audio.wav_array).all():
        return False
    if _processed_audio_duration(segment_audio) <= 0:
        return False
    alignment = dict(getattr(segment_audio, "candidate_alignment", {}) or {})
    word_boundaries = list(getattr(segment_audio, "word_boundaries", []) or [])
    return bool(alignment.get("success") and word_boundaries)


def _scale_word_boundaries_for_atempo(
    word_boundaries: List[dict],
    input_duration: float,
    output_duration: float,
) -> List[dict]:
    if input_duration <= 0.0 or output_duration <= 0.0:
        raise RuntimeError("Supertonic atempo zaman olcegi icin ses suresi pozitif olmali")
    time_scale = output_duration / input_duration
    scaled_boundaries = []
    for word in word_boundaries:
        start = float(word.get("start", 0.0) or 0.0)
        end = float(word.get("end", 0.0) or 0.0)
        if start < 0.0 or start >= input_duration or end <= start:
            raise RuntimeError("Supertonic atempo kelime zamani ilk alignment sonucunda gecersiz")
        scaled_word = dict(word)
        end = min(end, input_duration)
        if end <= start:
            raise RuntimeError("Supertonic atempo kelime zamani fiziksel ses sinirinda gecersiz")
        scaled_start = round(min(max(start * time_scale, 0.0), output_duration), 6)
        scaled_end = round(min(max(end * time_scale, scaled_start), output_duration), 6)
        if scaled_end <= scaled_start:
            raise RuntimeError("Supertonic atempo kelime zamani olcekleme sonrasi gecersiz")
        scaled_word["start"] = scaled_start
        scaled_word["end"] = scaled_end
        scaled_word["raw_start"] = scaled_start
        scaled_word["raw_end"] = scaled_end
        scaled_word["cut_start_seconds"] = 0.0
        scaled_boundaries.append(scaled_word)
    if not scaled_boundaries:
        raise RuntimeError("Supertonic atempo icin ilk alignment kelime zamani uretmedi")
    return scaled_boundaries


def _candidate_audio_key(record: dict, cfg: "DubConfig"):
    return record.get("audio_key") or (
        record["spoken_text"],
        record["voice_id"],
        record["pitch"],
        cfg.target_lang,
        record.get("speed") if cfg.tts_engine == "supertonic" else None,
    )


def _apply_supertonic_atempo_candidates(
    audio_by_key: Dict,
    candidate_records: List[dict],
    cfg: "DubConfig",
    run_dir: str,
    round_label: str,
) -> dict:
    enabled = (
        bool(getattr(cfg, "supertonic_atempo_enabled", False))
        and cfg.tts_engine == "supertonic"
        and str(getattr(cfg, "dubbing_mode", "segment_sync") or "segment_sync").strip().lower() == "segment_sync"
    )
    state = {
        "enabled": enabled,
        "eligible_segment_count": 0,
        "planned_segment_count": 0,
        "applied_segment_count": 0,
        "word_timing_rescaled_count": 0,
        "reused_variant_count": 0,
        "records": [],
        "report_path": "",
    }
    if not enabled:
        return state

    repair_enabled = bool(
        get_supertonic_flow_settings(getattr(cfg, "supertonic_flow_mode", None)).get("repair_enabled", False)
    )
    candidate_inputs = []
    record_by_candidate_key = {}
    report_by_candidate_key = {}
    eligible_segment_ids = set()
    for record in candidate_records:
        base_key = _candidate_audio_key(record, cfg)
        audio = audio_by_key.get(base_key)
        if audio is None:
            continue
        alignment = dict(getattr(audio, "candidate_alignment", {}) or {})
        if not alignment.get("success"):
            continue
        processed_duration = _processed_audio_duration(audio)
        target_duration = max(float(record.get("duration") or 0.0), 0.1)
        requested_factor = round(processed_duration / target_duration, 6)
        candidate_key = (int(record["segment_index"]), int(record["candidate_number"]))
        eligible = SUPERTONIC_ATEMPO_MIN_FACTOR <= processed_duration / target_duration <= SUPERTONIC_ATEMPO_MAX_FACTOR
        if eligible:
            eligible_segment_ids.add(str(record["segment_id"]))
        candidate_input = {
            "segment_id": int(record["segment_index"]),
            "candidate_number": int(record["candidate_number"]),
            "candidate_key": candidate_key,
            "processed_duration": processed_duration,
            "target_duration": target_duration,
            "required_atempo_factor": requested_factor,
        }
        candidate_inputs.append(candidate_input)
        record_by_candidate_key[candidate_key] = record
        report_record = {
            "segment_id": int(record["segment_index"]),
            "candidate_number": int(record["candidate_number"]),
            "candidate_key": list(candidate_key),
            "pre_atempo_processed_duration": processed_duration,
            "target_duration": target_duration,
            "required_atempo_factor": requested_factor,
            "requested_atempo_factor": requested_factor,
            "factor_clamped": False,
            "atempo_applied": False,
            "atempo_output_duration": None,
            "post_atempo_processed_duration": None,
            "post_atempo_video_speed": None,
            "pre_atempo_alignment": alignment,
            "word_timing_scale": None,
            "skip_reason": "" if eligible else "outside_factor_bounds",
        }
        if eligible and requested_factor == 1.0:
            report_record["skip_reason"] = "already_matches_target"
        report_by_candidate_key[candidate_key] = report_record

    if repair_enabled:
        for candidate_input in candidate_inputs:
            candidate_key = candidate_input["candidate_key"]
            record = record_by_candidate_key[candidate_key]
            record["requested_atempo_factor"] = candidate_input["required_atempo_factor"]
            record["atempo_selection_enabled"] = True
        plans = plan_supertonic_atempo_candidates(candidate_inputs)
    else:
        inputs_by_segment = {}
        for candidate_input in candidate_inputs:
            inputs_by_segment.setdefault(int(candidate_input["segment_id"]), []).append(candidate_input)
        plans = []
        selected_candidate_keys = set()
        for segment_id in sorted(inputs_by_segment):
            selected_input = min(inputs_by_segment[segment_id], key=_candidate_input_score_before_atempo)
            candidate_key = selected_input["candidate_key"]
            selected_candidate_keys.add(candidate_key)
            required_factor = float(selected_input["required_atempo_factor"])
            requested_factor = round(
                min(max(required_factor, SUPERTONIC_ATEMPO_MIN_FACTOR), SUPERTONIC_ATEMPO_MAX_FACTOR),
                6,
            )
            record = record_by_candidate_key[candidate_key]
            record["requested_atempo_factor"] = requested_factor
            record["atempo_selection_enabled"] = True
            report_record = report_by_candidate_key[candidate_key]
            report_record["requested_atempo_factor"] = requested_factor
            report_record["factor_clamped"] = requested_factor != required_factor
            report_record["skip_reason"] = "already_matches_target" if requested_factor == 1.0 else ""
            eligible_segment_ids.add(str(segment_id))
            if requested_factor != 1.0:
                plans.append(SupertonicAtempoPlan(
                    segment_id=segment_id,
                    candidate_number=int(selected_input["candidate_number"]),
                    candidate_key=candidate_key,
                    pre_atempo_processed_duration=float(selected_input["processed_duration"]),
                    target_duration=float(selected_input["target_duration"]),
                    requested_atempo_factor=requested_factor,
                ))
        for candidate_input in candidate_inputs:
            candidate_key = candidate_input["candidate_key"]
            if candidate_key not in selected_candidate_keys:
                report_by_candidate_key[candidate_key]["skip_reason"] = "not_selected_before_atempo"

    planned_candidate_keys = {plan.candidate_key for plan in plans}
    for candidate_input in candidate_inputs:
        candidate_key = candidate_input["candidate_key"]
        report_record = report_by_candidate_key[candidate_key]
        if (
            not report_record["skip_reason"]
            and candidate_key not in planned_candidate_keys
        ):
            report_record["skip_reason"] = "not_selected_for_atempo"

    pending_atempo_inputs = {}
    for plan in plans:
        record = record_by_candidate_key[plan.candidate_key]
        base_key = _candidate_audio_key(record, cfg)
        base_audio = audio_by_key[base_key]
        target_samples = int(round(plan.target_duration * cfg.sample_rate))
        variant_key = (
            "supertonic_atempo_v1",
            base_key,
            str(record["segment_id"]),
            target_samples,
            f"{plan.requested_atempo_factor:.6f}",
        )
        cached_variant = audio_by_key.get(variant_key)
        if cached_variant is None or not _measured_candidate_audio_is_reusable(cached_variant):
            pending_atempo_inputs[plan.candidate_key] = (
                np.asarray(base_audio.wav_array, dtype=np.float32),
                cfg.sample_rate,
                plan.requested_atempo_factor,
            )

    def process_atempo_input(item):
        candidate_key, process_args = item
        return candidate_key, process_supertonic_atempo_audio(*process_args)

    processed_atempo_audio = {}
    if pending_atempo_inputs:
        worker_count = min(4, len(pending_atempo_inputs))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            processed_atempo_audio.update(executor.map(process_atempo_input, pending_atempo_inputs.items()))

    for plan in plans:
        record = record_by_candidate_key[plan.candidate_key]
        base_key = _candidate_audio_key(record, cfg)
        base_audio = audio_by_key[base_key]
        target_samples = int(round(plan.target_duration * cfg.sample_rate))
        variant_key = (
            "supertonic_atempo_v1",
            base_key,
            str(record["segment_id"]),
            target_samples,
            f"{plan.requested_atempo_factor:.6f}",
        )
        record["effective_audio_key"] = variant_key
        record["atempo_variant_key"] = variant_key
        report_record = report_by_candidate_key[plan.candidate_key]
        cached_variant = audio_by_key.get(variant_key)
        if cached_variant is not None and _measured_candidate_audio_is_reusable(cached_variant):
            cached_meta = dict(getattr(cached_variant, "atempo_meta", {}) or {})
            report_record.update({
                "atempo_applied": bool(cached_meta.get("atempo_applied", True)),
                "atempo_output_duration": cached_meta.get("output_duration"),
                "post_atempo_processed_duration": _processed_audio_duration(cached_variant),
                "post_atempo_video_speed": plan.target_duration / _processed_audio_duration(cached_variant),
                "word_timing_scale": cached_meta.get("word_timing_scale"),
                "skip_reason": "reused_atempo_variant" if cached_meta.get("atempo_applied", True) else "reused_short_audio_noop",
            })
            state["reused_variant_count"] += 1
            continue

        processed_audio = processed_atempo_audio[plan.candidate_key]
        output_duration = len(processed_audio) / cfg.sample_rate
        input_duration = len(base_audio.wav_array) / cfg.sample_rate
        atempo_applied = not np.isclose(output_duration, input_duration, atol=1.0 / cfg.sample_rate)
        word_timing_scale = output_duration / input_duration
        base_alignment = dict(getattr(base_audio, "candidate_alignment", {}) or {})
        word_boundaries = _scale_word_boundaries_for_atempo(
            list(getattr(base_audio, "word_boundaries", []) or []),
            input_duration,
            output_duration,
        )
        scaled_alignment = dict(base_alignment)
        active_start = min(max(float(base_alignment.get("active_start_seconds", 0.0)), 0.0), input_duration)
        active_end = min(max(float(base_alignment.get("active_end_seconds", input_duration)), active_start), input_duration)
        scaled_alignment.update({
            "source": "candidate_audio_forced_alignment_atempo_scaled",
            "mode": "uniform_atempo_time_scale",
            "active_start_seconds": round(active_start * word_timing_scale, 6),
            "active_end_seconds": round(active_end * word_timing_scale, 6),
            "active_duration_seconds": round((active_end - active_start) * word_timing_scale, 6),
            "cut_start_seconds": 0.0,
            "cut_end_seconds": round(output_duration, 6),
            "cut_duration_seconds": round(output_duration, 6),
            "word_count": len(word_boundaries),
            "physical_audio_bounds_preserved": True,
            "word_timing_scale": round(word_timing_scale, 9),
        })
        word_timing_source = (
            "candidate_audio_forced_alignment_atempo_scaled"
            if atempo_applied
            else str(getattr(base_audio, "word_timing_source", "") or "candidate_audio_forced_alignment")
        )
        scaled_alignment["source"] = word_timing_source
        scaled_alignment["word_timing_transform"] = (
            "uniform_atempo_time_scale" if atempo_applied else "atempo_short_audio_noop"
        )
        variant_audio = SegmentAudio(
            index=int(record.get("eval_id") or base_audio.index),
            wav_array=processed_audio,
            start_time=0.0,
            engine_name=base_audio.engine_name,
            raw_duration=output_duration,
            spoken_text=str(record.get("spoken_text") or ""),
        )
        setattr(variant_audio, "supertonic_trim_meta", dict(getattr(base_audio, "supertonic_trim_meta", {}) or {}))
        setattr(variant_audio, "engine_raw_duration", getattr(base_audio, "engine_raw_duration", base_audio.raw_duration))
        setattr(variant_audio, "processed_duration", output_duration)
        setattr(variant_audio, "word_boundaries", word_boundaries)
        setattr(variant_audio, "word_timing_source", word_timing_source)
        setattr(variant_audio, "candidate_alignment", scaled_alignment)
        setattr(variant_audio, "pre_atempo_alignment", base_alignment)
        setattr(variant_audio, "atempo_meta", {
            "atempo_applied": atempo_applied,
            "requested_factor": plan.requested_atempo_factor,
            "pre_atempo_processed_duration": plan.pre_atempo_processed_duration,
            "target_duration": plan.target_duration,
            "output_duration": output_duration,
            "word_timing_scale": word_timing_scale,
            "word_timing_transform": scaled_alignment["word_timing_transform"],
            "variant_key": variant_key,
        })
        audio_by_key[variant_key] = variant_audio
        report_record.update({
            "atempo_applied": atempo_applied,
            "atempo_output_duration": output_duration,
            "post_atempo_processed_duration": output_duration,
            "post_atempo_video_speed": plan.target_duration / output_duration,
            "word_timing_scale": word_timing_scale,
            "skip_reason": "" if atempo_applied else "ffmpeg_empty_output_preserved_input",
        })

    state["eligible_segment_count"] = len(eligible_segment_ids)
    state["planned_segment_count"] = len(plans)
    state["applied_segment_count"] = sum(
        bool(item.get("atempo_applied")) for item in report_by_candidate_key.values()
    )
    state["word_timing_rescaled_count"] = sum(
        bool(item.get("atempo_applied")) for item in report_by_candidate_key.values()
    )
    state["records"] = list(report_by_candidate_key.values())
    state["report_dir"] = os.path.join(
        run_dir,
        "real_tts_candidate_selection",
        round_label,
        "supertonic_atempo_sure_uyumu",
    )
    return state


def _clone_segment_audio(segment_audio: SegmentAudio) -> SegmentAudio:
    cloned = SegmentAudio(
        index=int(segment_audio.index),
        wav_array=segment_audio.wav_array,
        start_time=float(segment_audio.start_time),
        engine_name=str(segment_audio.engine_name),
        raw_duration=float(segment_audio.raw_duration or 0.0),
        spoken_text=str(getattr(segment_audio, "spoken_text", "") or ""),
    )
    setattr(cloned, "supertonic_trim_meta", dict(getattr(segment_audio, "supertonic_trim_meta", {}) or {}))
    setattr(cloned, "engine_raw_duration", getattr(segment_audio, "engine_raw_duration", cloned.raw_duration))
    setattr(cloned, "processed_duration", getattr(segment_audio, "processed_duration", cloned.raw_duration))
    setattr(cloned, "word_boundaries", list(getattr(segment_audio, "word_boundaries", []) or []))
    setattr(cloned, "word_timing_source", getattr(segment_audio, "word_timing_source", ""))
    setattr(cloned, "candidate_alignment", dict(getattr(segment_audio, "candidate_alignment", {}) or {}))
    setattr(cloned, "candidate_lane_provenance", dict(getattr(segment_audio, "candidate_lane_provenance", {}) or {}))
    return cloned


def _candidate_record_voice_id(seg: "Segment", cfg: "DubConfig", global_voice_id: str) -> str:
    if cfg.tts_engine == "supertonic":
        return resolve_supertonic_voice_id(seg, cfg, global_voice_id)
    return _segment_voice_id(seg, cfg, global_voice_id)


def _segment_audio_from_prepared_audio(prepared_audio) -> SegmentAudio:
    segment_audio = SegmentAudio(
        index=int(prepared_audio.index),
        wav_array=prepared_audio.wav_array,
        start_time=float(prepared_audio.start_time),
        engine_name=str(prepared_audio.engine_name),
        raw_duration=float(prepared_audio.raw_duration),
    )
    setattr(segment_audio, "engine_raw_duration", float(prepared_audio.engine_raw_duration))
    setattr(segment_audio, "processed_duration", float(prepared_audio.processed_duration))
    setattr(segment_audio, "supertonic_trim_meta", dict(prepared_audio.trim_meta or {}))
    setattr(segment_audio, "word_boundaries", list(getattr(prepared_audio, "word_boundaries", []) or []))
    setattr(segment_audio, "word_timing_source", getattr(prepared_audio, "word_timing_source", ""))
    setattr(segment_audio, "candidate_alignment", dict(getattr(prepared_audio, "candidate_alignment", {}) or {}))
    setattr(segment_audio, "candidate_lane_provenance", dict(getattr(prepared_audio, "candidate_lane_provenance", {}) or {}))
    return segment_audio


def build_dubbed_audio_with_real_candidate_selection(
    segments: List["Segment"],
    cfg: "DubConfig",
    run_dir: str,
    candidates_by_id: Dict[str, List[str]],
    round_label: str = "round_1",
    segment_ids_to_measure: Optional[set[str]] = None,
    previous_selection: Optional[RealTTSCandidateSelectionResult] = None,
    supertonic_runtime_context: Optional[SupertonicRuntimeContext] = None,
) -> RealTTSCandidateSelectionResult:
    if cfg.tts_engine == "supertonic":
        manager = None
        primary_engine_name = "Supertonic TTS"
        global_voice_id = cfg.tts_voice_id if cfg.tts_voice_id else get_supertonic_default_voice_id()
    else:
        raise ValueError(f"Desteklenmeyen TTS motoru: {cfg.tts_engine}")

    measure_ids = None if segment_ids_to_measure is None else {str(item) for item in segment_ids_to_measure}
    previous_reports_by_id = {}
    previous_audio_by_id = {}
    previous_measured_audio_by_key = {}
    if cfg.tts_engine == "supertonic":
        from dublaj_hatti.bolum_50_seslendirme.supertonic_tts import SUPERTONIC_SYNTHESIS_CONTRACT

        if getattr(previous_selection, "supertonic_synthesis_contract", None) != SUPERTONIC_SYNTHESIS_CONTRACT:
            previous_selection = None
    if previous_selection is not None:
        previous_reports_by_id = {
            str(item.get("segment_id")): item
            for item in getattr(previous_selection, "selected_segments", [])
            if str(item.get("segment_id", "")).strip()
        }
        previous_audio_by_id = getattr(previous_selection, "selected_audio_by_id", {}) or {}
        previous_measured_audio_by_key = getattr(previous_selection, "measured_audio_by_key", {}) or {}
    segment_list = list(segments)

    candidate_records = []
    phonetic_plan_inputs = []
    for seg in segments:
        seg_id = str(seg.index)
        if (
            previous_selection is not None
            and measure_ids is not None
            and seg_id not in measure_ids
            and seg_id in previous_reports_by_id
            and seg_id in previous_audio_by_id
        ):
            continue
        candidates = _clean_candidate_texts(candidates_by_id.get(seg_id, []), seg.text)
        seg_voice_id = _candidate_record_voice_id(seg, cfg, global_voice_id)
        seg_pitch = _segment_pitch(seg, cfg)
        for candidate_number, candidate_text in enumerate(candidates, start=1):
            seg_reference_wav = ""
            record = {
                "segment_index": seg.index,
                "segment_id": seg_id,
                "candidate_number": candidate_number,
                "display_text": candidate_text,
                "voice_id": seg_voice_id,
                "pitch": seg_pitch,
                "start": seg.start,
                "duration": max(seg.end - seg.start, 0.1),
                "speaker_id": str(getattr(seg, "speaker", "") or "").strip(),
            }
            if cfg.tts_engine == "supertonic":
                record["speed"] = get_supertonic_segment_speed(seg, seg_voice_id)
            if seg_reference_wav:
                record["reference_wav"] = seg_reference_wav
            candidate_records.append(record)
            phonetic_plan_inputs.append({
                "text": candidate_text,
                "engine": cfg.tts_engine,
                "target_lang": cfg.target_lang,
                "voice_id": seg_voice_id,
                "run_dir": run_dir,
                "segment_index": seg.index,
                "protected_terms": getattr(seg, "protected_terms", None),
            })

    phonetic_plans = [{"output": item["text"]} for item in phonetic_plan_inputs]
    unique_segments = []
    unique_key_to_eval_id = {}
    eval_id_to_key = {}
    audio_by_key = {}
    for cached_key, cached_audio in previous_measured_audio_by_key.items():
        if isinstance(cached_key, tuple) and cached_key and cached_key[0] == "supertonic_atempo_v1":
            audio_by_key[cached_key] = cached_audio
    cached_unique_keys = set()
    invalid_cached_unique_keys = set()
    cache_validation_by_key = {}
    for record, plan in zip(candidate_records, phonetic_plans):
        spoken_text = str(plan.get("output") or record["display_text"]).strip()
        record["spoken_text"] = spoken_text
        key = (
            spoken_text,
            record["voice_id"],
            record["pitch"],
            cfg.target_lang,
            record.get("speed") if cfg.tts_engine == "supertonic" else None,
        )
        if cfg.tts_engine == "supertonic":
            key += (SUPERTONIC_SYNTHESIS_CONTRACT,)
        cached_audio = previous_measured_audio_by_key.get(key)
        if key not in cache_validation_by_key:
            cache_validation_by_key[key] = (
                cached_audio is not None
                and (
                    cfg.tts_engine != "supertonic"
                    or _measured_candidate_audio_is_reusable(cached_audio)
                )
            )
        cached_audio_is_reusable = cache_validation_by_key[key]
        if cached_audio_is_reusable:
            audio_by_key[key] = cached_audio
            cached_unique_keys.add(key)
        else:
            if cfg.tts_engine == "supertonic" and cached_audio is not None:
                invalid_cached_unique_keys.add(key)
        cached_provenance = dict(getattr(cached_audio, "candidate_lane_provenance", {}) or {}) if cached_audio_is_reusable else {}
        record["candidate_origin_round"] = str(cached_provenance.get("round_label") or round_label)
        if key not in cached_unique_keys and key not in unique_key_to_eval_id:
            eval_id = len(unique_key_to_eval_id) + 1
            unique_key_to_eval_id[key] = eval_id
            eval_id_to_key[eval_id] = key
            source_seg = next((s for s in segments if s.index == record["segment_index"]), None)
            unique_segments.append({
                    "index": eval_id,
                    "text": spoken_text,
                    "start": 0.0,
                    "duration": record["duration"],
                    "voice_id": record["voice_id"],
                    "pitch": record["pitch"],
                    "gender": getattr(source_seg, "gender", ""),
                    "speaker": getattr(source_seg, "speaker", ""),
                    "reference_wav": record.get("reference_wav", ""),
                    "speed": record.get("speed") if cfg.tts_engine == "supertonic" else None,
                })
        record["eval_id"] = unique_key_to_eval_id.get(key, 0)
        record["audio_key"] = key

    alignment_report = {}
    supertonic_lane_report = []
    supertonic_candidate_records_to_measure = [
        record
        for record in candidate_records
        if record["audio_key"] not in cached_unique_keys
    ]
    if cfg.tts_engine == "supertonic" and supertonic_candidate_records_to_measure:
        lane_measurement = measure_supertonic_candidate_lanes(
            supertonic_candidate_records_to_measure,
            cfg,
            run_dir,
            round_label,
            runtime_context=supertonic_runtime_context,
        )
        from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.candidate_lanes import build_candidate_lane_alignment_windows, demux_verified_candidate_lane
        lane_records = []
        for lane in lane_measurement.lanes:
            lane_audio = lane_measurement.lane_audio_by_key[lane["audio_key"]]
            setattr(lane_audio, "preserve_physical_audio_bounds", True)
            alignment_windows = build_candidate_lane_alignment_windows(lane, lane_audio, cfg.sample_rate)
            lane_record = {
                "audio_key": lane["audio_key"], "spoken_text": lane["alignment_text"], "display_text": lane["alignment_text"],
                "segment_id": lane["lane_id"], "segment_index": int(lane["eval_id"]), "candidate_number": int(lane["candidate_number"]),
            }
            if alignment_windows:
                lane_record["alignment_windows"] = alignment_windows
            lane_records.append(lane_record)
        alignment_report = align_candidate_audio_batch(
            audio_by_key=lane_measurement.lane_audio_by_key,
            candidate_records=lane_records,
            language=cfg.target_lang,
            run_dir=run_dir,
            sample_rate=cfg.sample_rate,
            round_label=round_label,
            debug_dir_name="candidate_lane_alignment",
            model_name=(str(getattr(cfg, "model_name", "") or "large-v3-turbo") if str(getattr(cfg, "transcription_engine", "")).lower() == "whisperx" else "large-v3-turbo"),
            compute_type=str(getattr(cfg, "compute_type", "") or "float32"),
        )
        for lane in lane_measurement.lanes:
            lane_audio = lane_measurement.lane_audio_by_key[lane["audio_key"]]
            lane["lane_audio"] = lane_audio
            for key, prepared_audio in demux_verified_candidate_lane(lane, lane_audio, cfg.sample_rate).items():
                audio_by_key[key] = _segment_audio_from_prepared_audio(prepared_audio)
        for lane in lane_measurement.lanes:
            lane_alignment = dict(getattr(lane["lane_audio"], "candidate_alignment", {}) or {})
            supertonic_lane_report.append({
                "lane_id": lane["lane_id"],
                "round_label": lane["round_label"],
                "candidate_number": lane["candidate_number"],
                "voice_id": lane["voice_id"],
                "speaker_id": lane["speaker_id"],
                "source_audio_key": lane["audio_key"],
                "segment_indices": [int(record["segment_index"]) for record in lane["records"]],
                "spoken_text": lane["spoken_text"],
                "alignment_success": bool(lane_alignment.get("success")),
                "alignment_scope": "candidate_lane_with_physical_chunk_fence",
            })
    elif unique_segments:
        if cfg.tts_engine == "supertonic":
            raise RuntimeError("Supertonic aday olcumu lane kapisindan gecmeden calisamaz")
        else:
            raise ValueError(f"Desteklenmeyen TTS motoru: {cfg.tts_engine}")

    if cfg.tts_engine != "supertonic":
        alignment_report = align_candidate_audio_batch(
            audio_by_key=audio_by_key,
            candidate_records=candidate_records,
            language=cfg.target_lang,
            run_dir=run_dir,
            sample_rate=cfg.sample_rate,
            round_label=round_label,
            model_name=(str(getattr(cfg, "model_name", "") or "large-v3-turbo") if str(getattr(cfg, "transcription_engine", "")).lower() == "whisperx" else "large-v3-turbo"),
            compute_type=str(getattr(cfg, "compute_type", "") or "float32"),
        )

    records_by_segment: Dict[str, List[dict]] = {}
    for record in candidate_records:
        records_by_segment.setdefault(record["segment_id"], []).append(record)

    atempo_state = _apply_supertonic_atempo_candidates(
        audio_by_key=audio_by_key,
        candidate_records=candidate_records,
        cfg=cfg,
        run_dir=run_dir,
        round_label=round_label,
    )
    atempo_report_by_key = {
        (int(item["segment_id"]), int(item["candidate_number"])): item
        for item in atempo_state.get("records", [])
    }

    selected_texts_by_id: Dict[str, str] = {}
    selected_segments = []
    problem_segments = []
    candidate_report = []
    chosen_audios: Dict[int, SegmentAudio] = {}
    selected_audio_by_id: Dict[str, SegmentAudio] = {}
    timing_infos = []
    reused_segment_count = 0

    for seg in segments:
        seg_id = str(seg.index)
        original_duration = max(seg.end - seg.start, 0.1)
        if seg_id not in records_by_segment and seg_id in previous_reports_by_id and seg_id in previous_audio_by_id:
            previous_report = dict(previous_reports_by_id[seg_id])
            previous_audio = previous_audio_by_id[seg_id]
            previous_report["reused_from_previous_round"] = True
            selected_texts_by_id[seg_id] = str(previous_report.get("selected_text", "")).strip()
            reused_audio = SegmentAudio(
                index=seg.index,
                wav_array=previous_audio.wav_array,
                start_time=seg.start,
                engine_name=previous_audio.engine_name,
                raw_duration=float(previous_audio.raw_duration or previous_report.get("selected_duration", 0.0) or 0.0),
                spoken_text=str(previous_report.get("selected_spoken_text", previous_report.get("selected_text", "")) or ""),
            )
            setattr(reused_audio, "supertonic_trim_meta", getattr(previous_audio, "supertonic_trim_meta", {}) or {})
            setattr(reused_audio, "engine_raw_duration", getattr(previous_audio, "engine_raw_duration", reused_audio.raw_duration))
            setattr(reused_audio, "processed_duration", getattr(previous_audio, "processed_duration", reused_audio.raw_duration))
            setattr(reused_audio, "word_boundaries", list(getattr(previous_audio, "word_boundaries", []) or []))
            setattr(reused_audio, "word_timing_source", getattr(previous_audio, "word_timing_source", ""))
            setattr(reused_audio, "candidate_alignment", dict(getattr(previous_audio, "candidate_alignment", {}) or {}))
            setattr(reused_audio, "pre_atempo_alignment", dict(getattr(previous_audio, "pre_atempo_alignment", {}) or {}))
            setattr(reused_audio, "atempo_meta", dict(getattr(previous_audio, "atempo_meta", {}) or {}))
            setattr(reused_audio, "candidate_lane_provenance", dict(getattr(previous_audio, "candidate_lane_provenance", {}) or {}))
            chosen_audios[seg.index] = reused_audio
            selected_audio_by_id[seg_id] = reused_audio
            selected_segments.append(previous_report)
            candidate_report.append(previous_report)
            if previous_report.get("status") != "accepted":
                problem_segments.append({
                    **previous_report,
                    "problem": previous_report.get("status", "reused_problem"),
                })
            timing_info = {
                "segment_index": seg.index,
                "tts_processed_duration": float(previous_report.get("selected_duration", reused_audio.raw_duration)),
                "original_duration": original_duration,
                "start_time": seg.start,
                "selection_source": "real_tts_candidate_selection",
            }
            if "selected_engine_raw_duration" in previous_report:
                timing_info["tts_engine_raw_duration"] = float(previous_report["selected_engine_raw_duration"])
            timing_infos.append(timing_info)
            reused_segment_count += 1
            continue

        measured_candidates = []
        for record in records_by_segment.get(seg_id, []):
            key = record.get("effective_audio_key") or _candidate_audio_key(record, cfg)
            seg_audio = audio_by_key.get(key)
            if not seg_audio:
                measured_candidates.append({
                    "candidate_number": record["candidate_number"],
                    "text": record["display_text"],
                    "spoken_text": record["spoken_text"],
                    "status": "tts_failed",
                    "target_duration": round(original_duration, 3),
                })
                continue
            candidate_alignment = dict(getattr(seg_audio, "candidate_alignment", {}) or {})
            if not candidate_alignment.get("success"):
                measured_candidates.append({
                    "candidate_number": record["candidate_number"],
                    "text": record["display_text"],
                    "spoken_text": record["spoken_text"],
                    "status": "alignment_failed",
                    "target_duration": round(original_duration, 3),
                })
                continue
            processed_duration = _processed_audio_duration(seg_audio)
            video_speed = original_duration / processed_duration if processed_duration > 0 else 1.0
            status = _candidate_status(video_speed)
            measured_candidate = {
                "candidate_number": record["candidate_number"],
                "text": record["display_text"],
                "spoken_text": record["spoken_text"],
                "duration_seconds": processed_duration,
                "duration": round(processed_duration, 3),
                "processed_duration_seconds": processed_duration,
                "processed_duration": round(processed_duration, 3),
                "target_duration_seconds": original_duration,
                "target_duration": round(original_duration, 3),
                "video_speed": round(video_speed, 3),
                "status": status,
                "engine": seg_audio.engine_name,
                "timing_source": candidate_alignment.get("source", "candidate_audio_forced_alignment"),
                "alignment_active_start_seconds": candidate_alignment.get("active_start_seconds", 0.0),
                "alignment_active_end_seconds": candidate_alignment.get("active_end_seconds", 0.0),
                "alignment_active_duration_seconds": candidate_alignment.get("active_duration_seconds", 0.0),
                "alignment_cut_start_seconds": candidate_alignment.get("cut_start_seconds", 0.0),
                "alignment_cut_end_seconds": candidate_alignment.get("cut_end_seconds", 0.0),
                "alignment_word_count": candidate_alignment.get("word_count", 0),
                "candidate_lane_provenance": dict(getattr(seg_audio, "candidate_lane_provenance", {}) or {}),
                "origin_round": str(record.get("candidate_origin_round") or round_label),
            }
            if record.get("atempo_selection_enabled"):
                measured_candidate["atempo_selection_enabled"] = True
                measured_candidate["requested_atempo_factor"] = float(record.get("requested_atempo_factor", 1.0))
            atempo_meta = dict(getattr(seg_audio, "atempo_meta", {}) or {})
            if atempo_meta:
                measured_candidate["atempo_applied"] = bool(atempo_meta.get("atempo_applied", True))
                measured_candidate["pre_atempo_processed_duration"] = atempo_meta.get("pre_atempo_processed_duration")
                measured_candidate["atempo_output_duration"] = atempo_meta.get("output_duration")
                measured_candidate["word_timing_scale"] = atempo_meta.get("word_timing_scale")
                measured_candidate["post_atempo_processed_duration"] = processed_duration
                measured_candidate["post_atempo_video_speed"] = round(video_speed, 6)
            engine_raw_duration = getattr(seg_audio, "engine_raw_duration", None)
            if engine_raw_duration is not None:
                measured_candidate["engine_raw_duration_seconds"] = float(engine_raw_duration)
                measured_candidate["engine_raw_duration"] = round(float(engine_raw_duration), 3)
            trim_meta = getattr(seg_audio, "supertonic_trim_meta", {}) or {}
            if trim_meta:
                measured_candidate["trim_source"] = trim_meta.get("trim_source", "")
                measured_candidate["trim_start_seconds"] = round(float(trim_meta.get("trim_start_seconds", 0.0)), 6)
                measured_candidate["trim_end_seconds"] = round(float(trim_meta.get("trim_end_seconds", 0.0)), 6)
            measured_candidates.append(measured_candidate)

        usable_candidates = [
            item for item in measured_candidates
            if item.get("status") not in {"tts_failed", "alignment_failed"}
        ]
        if not usable_candidates:
            raise RuntimeError(f"Gercek TTS adaylarinin hicbiri metni soylemedi: segment={seg_id}")

        selected = sorted(usable_candidates, key=_candidate_score)[0]
        selected_audio_record = next(
            record for record in records_by_segment.get(seg_id, [])
            if int(record["candidate_number"]) == int(selected["candidate_number"])
        )
        selected_key = selected_audio_record.get("effective_audio_key") or _candidate_audio_key(selected_audio_record, cfg)
        selected_audio = audio_by_key[selected_key]
        chosen_audio = SegmentAudio(
            index=seg.index,
            wav_array=selected_audio.wav_array,
            start_time=seg.start,
            engine_name=selected_audio.engine_name,
            raw_duration=float(selected.get("duration_seconds", selected["duration"])),
            spoken_text=str(selected.get("spoken_text", selected.get("text", "")) or ""),
        )
        setattr(chosen_audio, "supertonic_trim_meta", getattr(selected_audio, "supertonic_trim_meta", {}) or {})
        setattr(chosen_audio, "engine_raw_duration", getattr(selected_audio, "engine_raw_duration", chosen_audio.raw_duration))
        setattr(chosen_audio, "processed_duration", getattr(selected_audio, "processed_duration", chosen_audio.raw_duration))
        setattr(chosen_audio, "word_boundaries", list(getattr(selected_audio, "word_boundaries", []) or []))
        setattr(chosen_audio, "word_timing_source", getattr(selected_audio, "word_timing_source", ""))
        setattr(chosen_audio, "candidate_alignment", dict(getattr(selected_audio, "candidate_alignment", {}) or {}))
        setattr(chosen_audio, "pre_atempo_alignment", dict(getattr(selected_audio, "pre_atempo_alignment", {}) or {}))
        setattr(chosen_audio, "atempo_meta", dict(getattr(selected_audio, "atempo_meta", {}) or {}))
        setattr(chosen_audio, "candidate_lane_provenance", dict(getattr(selected_audio, "candidate_lane_provenance", {}) or {}))
        chosen_audios[seg.index] = chosen_audio
        selected_audio_by_id[seg_id] = chosen_audios[seg.index]
        selected_texts_by_id[seg_id] = str(selected["text"])
        segment_report = {
            "segment_index": seg.index,
            "segment_id": seg_id,
            "source_duration": round(original_duration, 3),
            "selected_candidate_number": selected["candidate_number"],
            "selected_text": selected["text"],
            "selected_spoken_text": selected.get("spoken_text", selected["text"]),
            "selected_duration": selected["duration"],
            "selected_processed_duration": selected.get("processed_duration", selected["duration"]),
            "video_speed": selected["video_speed"],
            "status": selected["status"],
            "selected_candidate_origin_round": str(selected.get("origin_round") or round_label),
            "candidates": measured_candidates,
        }
        if "engine_raw_duration" in selected:
            segment_report["selected_engine_raw_duration"] = selected["engine_raw_duration"]
        selected_atempo_report = atempo_report_by_key.get((int(seg.index), int(selected["candidate_number"])))
        if selected_atempo_report is not None:
            selected_atempo_report["final_selected"] = True
            selected_atempo_report["final_status"] = selected["status"]
            selected_atempo_report["final_duration"] = selected.get("processed_duration", selected["duration"])
            segment_report["selected_atempo"] = dict(selected_atempo_report)
        selected_segments.append(segment_report)
        candidate_report.append(segment_report)
        if selected["status"] != "accepted":
            problem_segments.append({
                **segment_report,
                "problem": selected["status"],
            })
        timing_info = {
            "segment_index": seg.index,
            "tts_processed_duration": float(selected.get("processed_duration_seconds", selected.get("duration_seconds", selected["duration"]))),
            "original_duration": original_duration,
            "start_time": seg.start,
            "selection_source": "real_tts_candidate_selection",
        }
        if "engine_raw_duration_seconds" in selected:
            timing_info["tts_engine_raw_duration"] = float(selected["engine_raw_duration_seconds"])
        if selected.get("atempo_applied"):
            timing_info["supertonic_atempo_applied"] = True
            timing_info["supertonic_atempo_factor"] = float(selected.get("requested_atempo_factor", 1.0))
        timing_infos.append(timing_info)

    max_end = max((seg.end for seg in segments), default=0.0)
    if cfg.tts_engine == "supertonic":
        mix = build_supertonic_audio_mix(chosen_audios, max_end, cfg.sample_rate)
    else:
        raise ValueError(f"Desteklenmeyen TTS motoru: {cfg.tts_engine}")

    if atempo_state.get("enabled"):
        for item in atempo_state.get("records", []):
            item.setdefault("final_selected", False)
            item.setdefault("final_status", "not_selected")
        resolved_segment_count = sum(
            bool(item.get("atempo_applied"))
            and bool(item.get("final_selected"))
            and item.get("final_status") == "accepted"
            for item in atempo_state.get("records", [])
        )
        atempo_state["resolved_segment_count"] = resolved_segment_count
        atempo_state["remaining_problem_count"] = len(problem_segments)
        atempo_state["report_path"] = write_supertonic_atempo_report(
            atempo_state["report_dir"],
            atempo_state.get("records", []),
            summary={
                "enabled": True,
                "eligible_segment_count": atempo_state.get("eligible_segment_count", 0),
                "planned_segment_count": atempo_state.get("planned_segment_count", 0),
                "applied_segment_count": atempo_state.get("applied_segment_count", 0),
                "word_timing_rescaled_count": atempo_state.get("word_timing_rescaled_count", 0),
                "reused_variant_count": atempo_state.get("reused_variant_count", 0),
                "resolved_segment_count": resolved_segment_count,
                "remaining_problem_count": len(problem_segments),
            },
        )

    report_dir = os.path.join(run_dir, "real_tts_candidate_selection")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"{round_label}.json")
    cached_candidate_count = sum(
        1
        for record in candidate_records
        if record["audio_key"] in cached_unique_keys
    )
    new_candidate_count = (
        len(supertonic_candidate_records_to_measure)
        if cfg.tts_engine == "supertonic"
        else len(candidate_records) - cached_candidate_count
    )
    invalid_cached_candidate_count = sum(
        1
        for record in candidate_records
        if record["audio_key"] in invalid_cached_unique_keys
    )
    candidate_reuse_summary = {
        "enabled": cfg.tts_engine == "supertonic",
        "cumulative_candidate_count": len(candidate_records),
        "new_candidate_tts_count": new_candidate_count,
        "reused_candidate_tts_count": cached_candidate_count,
        "prevented_candidate_tts_count": cached_candidate_count,
        "invalid_cached_tts_count": invalid_cached_candidate_count,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "status": "completed",
            "round": round_label,
            "segment_count": len(segments),
            "measured_segment_count": len(records_by_segment),
            "reused_segment_count": reused_segment_count,
            "candidate_count": len(candidate_records),
            "unique_tts_count": len(supertonic_lane_report) if cfg.tts_engine == "supertonic" else len(unique_segments),
            "cached_tts_count": len(cached_unique_keys),
            "candidate_reuse": candidate_reuse_summary,
            "selected_count": len(selected_segments),
            "problem_count": len(problem_segments),
            "acceptance": {
                "min_video_speed": REAL_TTS_MIN_VIDEO_SPEED,
                "max_video_speed": REAL_TTS_MAX_VIDEO_SPEED,
            },
            "segments": candidate_report,
            "candidate_alignment": alignment_report,
            "supertonic_candidate_lanes": supertonic_lane_report,
            "supertonic_atempo": {
                "enabled": atempo_state.get("enabled", False),
                "eligible_segment_count": atempo_state.get("eligible_segment_count", 0),
                "planned_segment_count": atempo_state.get("planned_segment_count", 0),
                "applied_segment_count": atempo_state.get("applied_segment_count", 0),
                "word_timing_rescaled_count": atempo_state.get("word_timing_rescaled_count", 0),
                "reused_variant_count": atempo_state.get("reused_variant_count", 0),
                "resolved_segment_count": atempo_state.get("resolved_segment_count", 0),
                "remaining_problem_count": atempo_state.get("remaining_problem_count", len(problem_segments)),
                "report_path": atempo_state.get("report_path", ""),
            },
        }, f, ensure_ascii=False, indent=2)

    logger.info(
        "Gercek TTS aday secimi tamamlandi: round=%s segment=%d olculen_segment=%d reused=%d aday=%d ideal_sure_uyumu_disinda=%d report=%s",
        round_label,
        len(segments),
        len(records_by_segment),
        reused_segment_count,
        len(candidate_records),
        len(problem_segments),
        report_path,
    )
    problem_segment_ids = {
        str(item.get("segment_id", "")).strip()
        for item in problem_segments
        if str(item.get("segment_id", "")).strip()
    }
    measured_audio_by_key = dict(previous_measured_audio_by_key)
    if problem_segment_ids:
        for record in candidate_records:
            if str(record.get("segment_id", "")).strip() not in problem_segment_ids:
                continue
            keys = [_candidate_audio_key(record, cfg)]
            if record.get("effective_audio_key") is not None:
                keys.append(record["effective_audio_key"])
            for key in keys:
                audio = audio_by_key.get(key)
                if audio is not None:
                    measured_audio_by_key[key] = audio
    result = RealTTSCandidateSelectionResult(
        tts_result=TTSBuildResult(
            audio=mix,
            timing_infos=timing_infos,
            segment_audios={idx: audio.wav_array for idx, audio in chosen_audios.items()},
            verified_word_timeline=[
                {
                    **dict(word),
                    "segment_index": int(segment_index),
                    "source": str(getattr(audio, "word_timing_source", "") or "candidate_audio_forced_alignment"),
                    "candidate_lane_provenance": dict(getattr(audio, "candidate_lane_provenance", {}) or {}),
                }
                for segment_index, audio in chosen_audios.items()
                for word in list(getattr(audio, "word_boundaries", []) or [])
            ],
        ),
        selected_texts_by_id=selected_texts_by_id,
        selected_segments=selected_segments,
        problem_segments=problem_segments,
        candidate_report=candidate_report,
        report_path=report_path,
        selected_audio_by_id=selected_audio_by_id,
        measured_audio_by_key=measured_audio_by_key,
    )
    if cfg.tts_engine == "supertonic":
        setattr(result, "supertonic_synthesis_contract", SUPERTONIC_SYNTHESIS_CONTRACT)
    setattr(result, "atempo_summary", {
        "enabled": atempo_state.get("enabled", False),
        "eligible_segment_count": atempo_state.get("eligible_segment_count", 0),
        "planned_segment_count": atempo_state.get("planned_segment_count", 0),
        "applied_segment_count": atempo_state.get("applied_segment_count", 0),
        "word_timing_rescaled_count": atempo_state.get("word_timing_rescaled_count", 0),
        "reused_variant_count": atempo_state.get("reused_variant_count", 0),
        "resolved_segment_count": atempo_state.get("resolved_segment_count", 0),
        "remaining_problem_count": atempo_state.get("remaining_problem_count", len(problem_segments)),
        "report_path": atempo_state.get("report_path", ""),
    })
    setattr(result, "candidate_reuse_summary", candidate_reuse_summary)
    return result


def build_dubbed_audio(
    segments: List["Segment"],
    cfg: "DubConfig",
    run_dir: str,
) -> TTSBuildResult:
    """
    Segmentleri seslendirip mix audio ve timing bilgilerini dondurur.

    Bu fonksiyon TTS islemlerinin ana giris noktasidir.
    Fallback sistemi otomatik calisir - birincil motor basarisiz olursa
    diger motorlar denenir.

    Args:
        segments: Segment listesi (text iceren)
        cfg: DubConfig (tts_engine, tts_voice_id, target_lang, vb.)
        run_dir: Calisma dizini (gecici dosyalar icin)

    Returns:
        TTSBuildResult - audio (numpy array) ve timing_infos (list)

    Raises:
        RuntimeError: Tum motorlar basarisiz olursa
    """

    if cfg.tts_engine == "voxcpm2":
        from dublaj_hatti.bolum_50_seslendirme.voxcpm2_tts import build_voxcpm2_dubbed_audio

        supertonic_result = build_voxcpm2_dubbed_audio(segments, cfg, run_dir)
    elif cfg.tts_engine == "ema_lightning":
        from dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts import build_ema_dubbed_audio

        supertonic_result = build_ema_dubbed_audio(segments, cfg, run_dir)
    elif cfg.tts_engine == "xtts":
        from dublaj_hatti.bolum_50_seslendirme.xtts_tts import build_xtts_dubbed_audio

        supertonic_result = build_xtts_dubbed_audio(segments, cfg, run_dir)
    elif cfg.tts_engine == "supertonic":
        supertonic_result = build_supertonic_dubbed_audio(segments, cfg, run_dir)
    else:
        raise ValueError(f"Desteklenmeyen TTS motoru: {cfg.tts_engine}")
    audio = supertonic_result.audio
    if str(getattr(cfg, "rvc_model_yolu", "") or "").strip():
        # isteğe bağlı RVC: karışım sesi kullanıcının kendi modeline çevrilir (rıza onayı zorunlu)
        from dublaj_hatti.bolum_50_seslendirme.rvc_ses_donusturme import rvc_ayari_cfgden, rvc_karisima_uygula

        rvc_ayar = rvc_ayari_cfgden(cfg)
        if rvc_ayar is not None:
            audio = rvc_karisima_uygula(audio, cfg.sample_rate, rvc_ayar, run_dir, logger=logger)
    return TTSBuildResult(
        audio=audio,
        timing_infos=supertonic_result.timing_infos,
        segment_audios=supertonic_result.segment_audios,
    )


