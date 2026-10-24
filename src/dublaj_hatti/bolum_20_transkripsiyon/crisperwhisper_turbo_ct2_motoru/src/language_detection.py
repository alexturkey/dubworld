from __future__ import annotations

import time
from typing import Any


GLOBAL_FIRST_WINDOW = "global_first_window"
CONTINUOUS_STREAM = "continuous_stream"
SUPPORTED_MODES = {GLOBAL_FIRST_WINDOW, CONTINUOUS_STREAM}


def platform_language_runs(
    model: object,
    audio: object,
    sample_rate: int,
    language: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    engine = getattr(model, "_engine", None)
    language_id = engine.get_language_id(language) if engine is not None else None
    if language_id is None:
        raise RuntimeError(f"CT2 model does not accept platform language: {language!r}")
    duration_seconds = len(audio) / sample_rate
    run = _run(0, language, 0.0, duration_seconds, 0, 0, 1)
    run.update(
        confirmation_method="trusted_platform_metadata",
        language_source="platform_metadata",
    )
    detection = {
        "tick_index": 0,
        "tick_center_seconds": 0.0,
        "tick_kind": "platform_metadata",
        "nominal_tick_seconds": None,
        "previous_tick_delta_seconds": None,
        "context_start_seconds": 0.0,
        "context_end_seconds": 0.0,
        "context_duration_seconds": 0.0,
        "detected_language": language,
        "stable_language": language,
        "assigned_run_language": language,
        "language_decision": "platform_language_accepted",
        "language_source": "platform_metadata",
        "detection_skipped": True,
        "processing_seconds": 0.0,
        "candidates": [
            {
                "language": language,
                "token_id": int(language_id),
                "probability": 1.0,
                "source": "platform_metadata",
            }
        ],
        "candidate_limit": 1,
        "candidate_count_total": 1,
        "candidate_scope": "trusted_platform_metadata",
    }
    return [run], [detection]


def normalize_language_token(value: str) -> str:
    token = str(value).strip()
    if token.startswith("<|") and token.endswith("|>"):
        token = token[2:-2]
    return token.lower()


def language_scores(model: object, audio: object) -> tuple[str, list[dict[str, Any]]]:
    features = model._engine.extract_features(audio)
    batches = model._engine.model.detect_language(features)
    if not batches or not batches[0]:
        raise RuntimeError("CT2 language detection returned no candidates")
    candidates = [
        {
            "language": normalize_language_token(token),
            "probability": float(probability),
        }
        for token, probability in batches[0]
    ]
    candidates = [item for item in candidates if item["language"]]
    candidates.sort(key=lambda item: (-item["probability"], item["language"]))
    if len(candidates) < 2:
        raise RuntimeError("CT2 language detection requires at least two candidates")
    return str(candidates[0]["language"]), candidates


def plan_continuous_ticks(audio: object, sample_rate: int, profile: dict[str, Any]) -> list[dict[str, Any]]:
    duration_seconds = len(audio) / sample_rate
    context_seconds = min(float(profile["context_seconds"]), duration_seconds)
    tick_seconds = float(profile["tick_seconds"])
    if context_seconds <= 0.0 or tick_seconds <= 0.0:
        raise RuntimeError("Continuous language timing is invalid")
    first_center = context_seconds / 2.0
    last_center = duration_seconds - context_seconds / 2.0
    centers = []
    center = first_center
    while center <= last_center + 1e-6:
        centers.append(center)
        center += tick_seconds
        if len(centers) > 100000:
            raise RuntimeError("Continuous language planner exceeded its safety limit")
    terminal_added = False
    if not centers:
        centers = [duration_seconds / 2.0]
    elif last_center - centers[-1] > 1e-6:
        centers.append(last_center)
        terminal_added = True
    return [
        {
            "tick_index": index,
            "tick_center_seconds": float(value),
            "tick_kind": "terminal_coverage" if terminal_added and index == len(centers) - 1 else "regular",
            "nominal_tick_seconds": tick_seconds,
            "previous_tick_delta_seconds": None if index == 0 else float(value) - float(centers[index - 1]),
            "context_start_seconds": max(0.0, float(value) - context_seconds / 2.0),
            "context_end_seconds": min(duration_seconds, float(value) + context_seconds / 2.0),
            "context_duration_seconds": context_seconds,
        }
        for index, value in enumerate(centers)
    ]


def detect_ticks(model: object, audio: object, sample_rate: int, ticks: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    detections = []
    for tick in ticks:
        start_sample = round(float(tick["context_start_seconds"]) * sample_rate)
        end_sample = min(len(audio), round(float(tick["context_end_seconds"]) * sample_rate))
        chunk = audio[start_sample:end_sample]
        if not len(chunk):
            raise RuntimeError(f"Continuous language tick is empty: {tick['tick_index']}")
        started = time.perf_counter()
        language, all_candidates = language_scores(model, chunk)
        candidates = all_candidates[:10]
        top_probability = float(candidates[0]["probability"])
        second_probability = float(candidates[1]["probability"])
        margin = top_probability - second_probability
        detections.append(
            {
                **dict(tick),
                "detected_language": language,
                "top_probability": top_probability,
                "second_probability": second_probability,
                "probability_margin": margin,
                "confident": top_probability >= float(profile["minimum_top_probability"])
                and margin >= float(profile["minimum_margin"]),
                "processing_seconds": time.perf_counter() - started,
                "candidates": candidates,
                "candidate_limit": 10,
                "candidate_count_total": len(all_candidates),
                "candidate_scope": "top_probability_ranked",
            }
        )
    return detections


def build_continuous_runs(detections: list[dict[str, Any]], duration_seconds: float, profile: dict[str, Any]) -> list[dict[str, Any]]:
    confirmation_ticks = int(profile["confirmation_ticks"])
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
            detection.update(pending_language=None, pending_confirmation_count=0, stable_language=active_language or None, language_decision="unconfident_observation")
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
            detection.update(pending_language=pending_language, pending_confirmation_count=pending_count, stable_language=None, language_decision="initial_language_pending")
            if pending_count < confirmation_ticks:
                continue
            active_language = pending_language
            active_first_tick = pending_first_tick
            last_stable_center = center
            detection.update(pending_language=None, pending_confirmation_count=0, stable_language=active_language, language_decision="initial_language_confirmed")
            pending_language = ""
            pending_count = 0
            continue
        if language == active_language:
            last_stable_center = center
            pending_language = ""
            pending_count = 0
            detection.update(pending_language=None, pending_confirmation_count=0, stable_language=active_language, language_decision="stable_language_observation")
            continue
        if language != pending_language:
            pending_language = language
            pending_count = 1
            pending_first_center = center
            pending_first_tick = int(detection["tick_index"])
        else:
            pending_count += 1
        detection.update(pending_language=pending_language, pending_confirmation_count=pending_count, stable_language=active_language, language_decision="language_change_pending")
        if pending_count < confirmation_ticks:
            continue
        boundary = (last_stable_center + pending_first_center) / 2.0
        if boundary <= active_start or boundary >= duration_seconds:
            raise RuntimeError("Continuous language boundary did not advance")
        runs.append(_run(len(runs), active_language, active_start, boundary, active_first_tick, pending_first_tick - 1, confirmation_ticks))
        active_language = pending_language
        active_start = boundary
        active_first_tick = pending_first_tick
        last_stable_center = center
        detection.update(pending_language=None, pending_confirmation_count=0, stable_language=active_language, language_decision="language_change_confirmed")
        pending_language = ""
        pending_count = 0
    if not active_language:
        raise RuntimeError("Continuous language detection had no confirmed language sequence")
    runs.append(_run(len(runs), active_language, active_start, duration_seconds, active_first_tick, int(detections[-1]["tick_index"]), confirmation_ticks))
    for detection in detections:
        center = float(detection["tick_center_seconds"])
        detection["assigned_run_language"] = next(
            str(run["detected_language"])
            for run in runs
            if float(run["start_seconds"]) <= center <= float(run["end_seconds"]) + 1e-6
        )
    return runs


def _run(index: int, language: str, start: float, end: float, first_tick: int, last_tick: int, confirmation_ticks: int) -> dict[str, Any]:
    return {
        "run_index": index,
        "detected_language": language,
        "start_seconds": start,
        "end_seconds": end,
        "first_tick_index": first_tick,
        "last_tick_index": last_tick,
        "confirmation_ticks": confirmation_ticks,
        "confirmation_method": "consecutive_confident_ticks",
        "decision_validated": True,
        "acoustic_word_anchor_validated": False,
    }


def detect_language_runs(model: object, audio: object, sample_rate: int, mode: str, profile: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    duration_seconds = len(audio) / sample_rate
    if mode == GLOBAL_FIRST_WINDOW:
        detection_seconds = min(float(profile["global_first_window_seconds"]), duration_seconds)
        tick = {
            "tick_index": 0,
            "tick_center_seconds": detection_seconds / 2.0,
            "tick_kind": "global_first_window",
            "nominal_tick_seconds": None,
            "previous_tick_delta_seconds": None,
            "context_start_seconds": 0.0,
            "context_end_seconds": detection_seconds,
            "context_duration_seconds": detection_seconds,
        }
        detections = detect_ticks(model, audio, sample_rate, [tick], {**profile, "minimum_top_probability": 0.0, "minimum_margin": 0.0})
        language = str(detections[0]["detected_language"])
        detections[0].update(stable_language=language, assigned_run_language=language, language_decision="global_language_confirmed")
        return [_run(0, language, 0.0, duration_seconds, 0, 0, 1)], detections
    if mode != CONTINUOUS_STREAM:
        raise RuntimeError(f"Unsupported language detection mode: {mode}")
    ticks = plan_continuous_ticks(audio, sample_rate, profile)
    detections = detect_ticks(model, audio, sample_rate, ticks, profile)
    return build_continuous_runs(detections, duration_seconds, profile), detections
