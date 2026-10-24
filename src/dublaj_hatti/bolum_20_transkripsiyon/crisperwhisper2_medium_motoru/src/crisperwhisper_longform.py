from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Callable

import numpy as np

from transcript_normalization import tokenize


SAMPLE_RATE = 16000
VAD_FRAME_SAMPLES = 512
MAX_WORD_TIMING_TOLERANCE_SECONDS = 0.05


def load_silero_model(torch, model_path: Path):
    path = Path(model_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Silero VAD model not found: {path}")
    model = torch.jit.load(str(path), map_location="cpu")
    model.eval()
    return model


def detect_speech_regions(
    torch,
    signal: np.ndarray,
    model,
    threshold: float,
    min_speech_duration_ms: int,
    min_silence_duration_ms: int,
    speech_pad_ms: int,
) -> tuple[list[dict], dict]:
    if signal.ndim != 1:
        raise RuntimeError(f"Silero VAD expects mono signal: {signal.shape}")
    if not 0.0 < threshold < 1.0:
        raise ValueError("VAD threshold must be in (0, 1)")
    model.reset_states()
    tensor = torch.from_numpy(np.asarray(signal, dtype=np.float32))
    probabilities = []
    started = time.perf_counter()
    with torch.no_grad():
        for frame_start in range(0, len(tensor), VAD_FRAME_SAMPLES):
            frame = tensor[frame_start : frame_start + VAD_FRAME_SAMPLES]
            if len(frame) < VAD_FRAME_SAMPLES:
                frame = torch.nn.functional.pad(frame, (0, VAD_FRAME_SAMPLES - len(frame)))
            probabilities.append(float(model(frame, SAMPLE_RATE).item()))

    negative_threshold = max(threshold - 0.15, 0.01)
    min_speech_samples = round(SAMPLE_RATE * min_speech_duration_ms / 1000)
    min_silence_samples = round(SAMPLE_RATE * min_silence_duration_ms / 1000)
    speech_pad_samples = round(SAMPLE_RATE * speech_pad_ms / 1000)
    triggered = False
    speech_start = 0
    possible_end = 0
    core_regions = []
    for frame_index, probability in enumerate(probabilities):
        frame_start = frame_index * VAD_FRAME_SAMPLES
        if probability >= threshold:
            if not triggered:
                triggered = True
                speech_start = frame_start
            possible_end = 0
            continue
        if not triggered or probability >= negative_threshold:
            continue
        if not possible_end:
            possible_end = frame_start
        if frame_start - possible_end < min_silence_samples:
            continue
        if possible_end - speech_start >= min_speech_samples:
            core_regions.append({"start_sample": speech_start, "end_sample": possible_end})
        triggered = False
        speech_start = 0
        possible_end = 0
    if triggered and len(signal) - speech_start >= min_speech_samples:
        core_regions.append({"start_sample": speech_start, "end_sample": len(signal)})

    padded_regions = []
    for core in core_regions:
        padded_start = max(0, int(core["start_sample"]) - speech_pad_samples)
        padded_end = min(len(signal), int(core["end_sample"]) + speech_pad_samples)
        if padded_regions and padded_start <= padded_regions[-1]["end_sample"]:
            padded_regions[-1]["end_sample"] = max(padded_regions[-1]["end_sample"], padded_end)
            padded_regions[-1]["core_end_sample"] = int(core["end_sample"])
        else:
            padded_regions.append(
                {
                    "start_sample": padded_start,
                    "end_sample": padded_end,
                    "core_start_sample": int(core["start_sample"]),
                    "core_end_sample": int(core["end_sample"]),
                }
            )
    return padded_regions, {
        "processing_seconds": round(time.perf_counter() - started, 3),
        "frame_count": len(probabilities),
        "core_region_count": len(core_regions),
        "region_count": len(padded_regions),
        "negative_threshold": negative_threshold,
    }


def build_compact_timeline(signal: np.ndarray, regions: list[dict]) -> tuple[np.ndarray, list[dict]]:
    if not regions:
        raise RuntimeError("Silero VAD did not find a speech region")
    parts = []
    spans = []
    compact_cursor = 0
    for region_index, region in enumerate(regions):
        original_start = int(region["start_sample"])
        original_end = int(region["end_sample"])
        if original_end <= original_start:
            continue
        part = np.asarray(signal[original_start:original_end], dtype=np.float32)
        compact_end = compact_cursor + len(part)
        spans.append(
            {
                "region_index": region_index,
                "compact_start_sample": compact_cursor,
                "compact_end_sample": compact_end,
                "original_start_sample": original_start,
                "original_end_sample": original_end,
                "core_start_sample": int(region["core_start_sample"]),
                "core_end_sample": int(region["core_end_sample"]),
            }
        )
        parts.append(part)
        compact_cursor = compact_end
    if not parts:
        raise RuntimeError("Silero VAD speech regions produced an empty compact timeline")
    return np.concatenate(parts).astype(np.float32, copy=False), spans


def natural_boundary_seconds(spans: list[dict]) -> list[float]:
    return [float(span["compact_end_sample"]) / SAMPLE_RATE for span in spans]


def choose_window_end(
    start_seconds: float,
    duration_seconds: float,
    boundaries: list[float],
    target_seconds: float,
    maximum_seconds: float,
    minimum_seconds: float,
) -> tuple[float, str]:
    maximum_end = min(duration_seconds, start_seconds + maximum_seconds)
    if maximum_end >= duration_seconds - 1e-9:
        return duration_seconds, "final"
    candidates = [
        boundary
        for boundary in boundaries
        if boundary >= start_seconds + minimum_seconds - 1e-6
        and boundary <= maximum_end + 1e-6
        and duration_seconds - boundary >= minimum_seconds - 1e-6
    ]
    if candidates:
        target_end = start_seconds + target_seconds
        selected = min(candidates, key=lambda value: (abs(value - target_end), value))
        return selected, "vad_silence_boundary"
    return maximum_end, "model_limit"


def overlap_candidates(
    seam_seconds: float,
    boundaries: list[float],
    minimum_seconds: float,
    maximum_seconds: float,
) -> list[dict]:
    natural = sorted(
        {
            round(seam_seconds - boundary, 6)
            for boundary in boundaries
            if minimum_seconds <= seam_seconds - boundary <= maximum_seconds
        }
    )
    fallback = [minimum_seconds, 3.0, 5.0, 7.0, maximum_seconds]
    values = []
    for value in [*natural, *fallback]:
        normalized = min(maximum_seconds, max(minimum_seconds, float(value)))
        if not any(abs(normalized - existing) <= 1e-6 for existing in values):
            values.append(normalized)
    values.sort()
    return [
        {
            "overlap_seconds": value,
            "start_seconds": max(0.0, seam_seconds - value),
            "source": "vad_boundary" if any(abs(value - item) <= 1e-6 for item in natural) else "forced_retry",
        }
        for value in values
    ]


def normalized_word_token(word: dict) -> str:
    tokens = tokenize(str(word.get("word", "")))
    return tokens[0] if len(tokens) == 1 else ""


def annotate_window_coverage(window: dict) -> dict:
    words = list(window.get("words") or [])
    duration_seconds = float(window["duration_seconds"])
    planned_end_seconds = float(window["end_seconds"])
    last_word_end_seconds = (
        max(float(word["compact_end"]) for word in words)
        if words
        else None
    )
    tail_gap_seconds = (
        max(0.0, planned_end_seconds - last_word_end_seconds)
        if last_word_end_seconds is not None
        else None
    )
    tail_limit_seconds = min(5.0, max(3.0, duration_seconds * 0.15))
    coverage_complete = (
        last_word_end_seconds is not None
        and tail_gap_seconds is not None
        and tail_gap_seconds <= tail_limit_seconds
    )
    window.update(
        {
            "coverage_status": "complete" if coverage_complete else "recovery_required",
            "coverage_last_word_end_seconds": last_word_end_seconds,
            "coverage_tail_gap_seconds": tail_gap_seconds,
            "coverage_tail_limit_seconds": tail_limit_seconds,
            "advance_end_seconds": (
                planned_end_seconds if coverage_complete else last_word_end_seconds
            ),
        }
    )
    return window


def classify_lexically_unconfirmed_final_tail(
    attempts: list[dict],
    seam_seconds: float,
    duration_seconds: float,
) -> dict | None:
    if not attempts or duration_seconds <= seam_seconds + 0.01:
        return None
    for attempt in attempts:
        last_word_end = attempt.get("coverage_last_word_end_seconds")
        advance_end = attempt.get("advance_end_seconds")
        if float(attempt.get("end_seconds") or 0.0) < duration_seconds - 1e-6:
            return None
        if attempt.get("coverage_status") != "recovery_required":
            return None
        if last_word_end is None or float(last_word_end) > seam_seconds + 0.01:
            return None
        if advance_end is None or float(advance_end) > seam_seconds + 0.01:
            return None
        if attempt.get("anchor_validated") is not True:
            return None
        if attempt.get("temporal_boundary_validated") is not True:
            return None
        if attempt.get("validated") is not True:
            return None
        if attempt.get("boundary_resolution") != "no_appended_word":
            return None
    return {
        "method": "lexically_unconfirmed_final_vad_tail",
        "seam_seconds": seam_seconds,
        "excluded_start_seconds": seam_seconds,
        "excluded_end_seconds": duration_seconds,
        "excluded_duration_seconds": duration_seconds - seam_seconds,
        "evidence_attempt_count": len(attempts),
        "anchor_validated": True,
        "temporal_boundary_validated": True,
        "boundary_resolution": "no_appended_word",
        "validated": True,
    }


def longest_common_contiguous(reference: list[str], candidate: list[str]) -> tuple[int, int, int]:
    best_reference = 0
    best_candidate = 0
    best_length = 0
    previous = [0] * (len(candidate) + 1)
    for reference_index, reference_token in enumerate(reference, start=1):
        current = [0] * (len(candidate) + 1)
        for candidate_index, candidate_token in enumerate(candidate, start=1):
            if reference_token != candidate_token:
                continue
            current[candidate_index] = previous[candidate_index - 1] + 1
            length = current[candidate_index]
            best_end = best_reference + best_length
            candidate_end = reference_index
            if length > best_length or (length == best_length and candidate_end > best_end):
                best_length = length
                best_reference = reference_index - length
                best_candidate = candidate_index - length
        previous = current
    return best_reference, best_candidate, best_length


def resolve_stitch_boundary(kept: list[dict], appended: list[dict]) -> tuple[bool, dict]:
    diagnostic = {
        "temporal_boundary_validated": True,
        "boundary_resolution": "not_applicable",
        "boundary_rejection_reason": "",
        "boundary_overlap_seconds": 0.0,
        "boundary_overlap_repaired_seconds": 0.0,
    }
    if not kept:
        diagnostic["boundary_resolution"] = "no_previous_word"
        return True, diagnostic
    if not appended:
        diagnostic["boundary_resolution"] = "no_appended_word"
        return True, diagnostic

    previous_word = kept[-1]
    next_word = appended[0]
    previous_start = float(previous_word["compact_start"])
    previous_end = float(previous_word["compact_end"])
    next_start = float(next_word["compact_start"])
    next_end = float(next_word["compact_end"])
    overlap_seconds = max(0.0, previous_end - next_start)
    diagnostic.update(
        {
            "boundary_previous_word": str(previous_word.get("word", "")),
            "boundary_next_word": str(next_word.get("word", "")),
            "boundary_previous_start_before": previous_start,
            "boundary_previous_end_before": previous_end,
            "boundary_next_start_before": next_start,
            "boundary_next_end_before": next_end,
            "boundary_overlap_seconds": overlap_seconds,
        }
    )
    if previous_end < previous_start or next_end < next_start:
        diagnostic.update(
            {
                "temporal_boundary_validated": False,
                "boundary_resolution": "retry",
                "boundary_rejection_reason": "invalid_boundary_word_range",
            }
        )
        return False, diagnostic
    if overlap_seconds <= 0.0:
        diagnostic["boundary_resolution"] = "already_monotonic"
        return True, diagnostic

    previous_token = normalized_word_token(previous_word)
    next_token = normalized_word_token(next_word)
    repeated_boundary_token = bool(previous_token and previous_token == next_token)
    repeated_boundary_start_validated = bool(
        repeated_boundary_token and next_start > previous_start
    )
    diagnostic.update(
        {
            "repeated_boundary_token": repeated_boundary_token,
            "repeated_boundary_start_validated": repeated_boundary_start_validated,
        }
    )
    if repeated_boundary_token and not repeated_boundary_start_validated:
        diagnostic.update(
            {
                "temporal_boundary_validated": False,
                "boundary_resolution": "retry",
                "boundary_rejection_reason": "repeated_boundary_token_non_increasing_start",
            }
        )
        return False, diagnostic

    if kept[:-1] and float(kept[-2]["compact_end"]) > next_start:
        diagnostic.update(
            {
                "temporal_boundary_validated": False,
                "boundary_resolution": "retry",
                "boundary_rejection_reason": "overlap_reaches_previous_neighbor",
            }
        )
        return False, diagnostic
    if appended[1:] and float(appended[1]["compact_start"]) < previous_end:
        diagnostic.update(
            {
                "temporal_boundary_validated": False,
                "boundary_resolution": "retry",
                "boundary_rejection_reason": "overlap_reaches_next_neighbor",
            }
        )
        return False, diagnostic

    intersection_start = max(previous_start, next_start)
    intersection_end = min(previous_end, next_end)
    if intersection_end <= intersection_start:
        diagnostic.update(
            {
                "temporal_boundary_validated": False,
                "boundary_resolution": "retry",
                "boundary_rejection_reason": "no_local_interval_intersection",
            }
        )
        return False, diagnostic

    shared_boundary = (intersection_start + intersection_end) / 2.0
    kept[-1]["compact_end"] = shared_boundary
    appended[0]["compact_start"] = shared_boundary
    diagnostic.update(
        {
            "boundary_resolution": "local_interval_midpoint",
            "boundary_shared_seconds": shared_boundary,
            "boundary_previous_end_after": shared_boundary,
            "boundary_next_start_after": shared_boundary,
            "boundary_previous_adjustment_seconds": previous_end - shared_boundary,
            "boundary_next_adjustment_seconds": shared_boundary - next_start,
            "boundary_overlap_repaired_seconds": overlap_seconds,
        }
    )
    return True, diagnostic


def stitch_with_anchor(
    merged_words: list[dict],
    current_words: list[dict],
    current_start_seconds: float,
    previous_end_seconds: float,
) -> tuple[list[dict] | None, dict]:
    previous_pairs = [
        (index, token)
        for index, word in enumerate(merged_words)
        if float(word["compact_end"]) >= current_start_seconds + 0.02
        and float(word["compact_start"]) <= previous_end_seconds - 0.02
        and (token := normalized_word_token(word))
    ]
    current_pairs = [
        (index, token)
        for index, word in enumerate(current_words)
        if float(word["compact_end"]) >= current_start_seconds + 0.02
        and float(word["compact_start"]) <= previous_end_seconds - 0.02
        and (token := normalized_word_token(word))
    ]
    reference_index, candidate_index, match_length = longest_common_contiguous(
        [token for _, token in previous_pairs],
        [token for _, token in current_pairs],
    )
    diagnostic = {
        "previous_overlap_word_count": len(previous_pairs),
        "current_overlap_word_count": len(current_pairs),
        "anchor_word_count": match_length,
        "anchor_validated": match_length >= 2,
        "temporal_boundary_validated": False,
        "validated": False,
        "previous_overlap_words": [
            {
                "index": index,
                "word": str(merged_words[index].get("word", "")),
                "normalized_token": token,
                "compact_start": float(merged_words[index]["compact_start"]),
                "compact_end": float(merged_words[index]["compact_end"]),
            }
            for index, token in previous_pairs[-80:]
        ],
        "current_overlap_words": [
            {
                "index": index,
                "word": str(current_words[index].get("word", "")),
                "normalized_token": token,
                "compact_start": float(current_words[index]["compact_start"]),
                "compact_end": float(current_words[index]["compact_end"]),
            }
            for index, token in current_pairs[-80:]
        ],
    }
    if match_length < 2:
        diagnostic.update(
            {
                "anchor_rejection_reason": (
                    "insufficient_overlap_words"
                    if len(previous_pairs) < 2 or len(current_pairs) < 2
                    else "no_two_word_contiguous_anchor"
                ),
            }
        )
        return None, diagnostic
    previous_end_index = previous_pairs[reference_index + match_length - 1][0]
    current_end_index = current_pairs[candidate_index + match_length - 1][0]
    appended = [dict(word) for word in current_words[current_end_index + 1 :]]
    kept = [dict(word) for word in merged_words[: previous_end_index + 1]]
    diagnostic.update(
        {
            "anchor_words": [
                previous_pairs[index][1]
                for index in range(reference_index, reference_index + match_length)
            ],
            "kept_previous_through_index": previous_end_index,
            "used_current_from_index": current_end_index + 1,
        }
    )
    boundary_validated, boundary_diagnostic = resolve_stitch_boundary(kept, appended)
    diagnostic.update(boundary_diagnostic)
    diagnostic["validated"] = boundary_validated
    if not boundary_validated:
        return None, diagnostic
    return kept + appended, diagnostic


def compact_time_to_original(
    spans: list[dict],
    compact_seconds: float,
    prefer_previous: bool,
) -> tuple[float, int]:
    compact_sample = float(compact_seconds) * SAMPLE_RATE
    epsilon = 1e-4 * SAMPLE_RATE
    for index, span in enumerate(spans):
        start = float(span["compact_start_sample"])
        end = float(span["compact_end_sample"])
        if start - epsilon <= compact_sample < end - epsilon:
            selected = index
            break
        if abs(compact_sample - end) <= epsilon:
            selected = index if prefer_previous else min(index + 1, len(spans) - 1)
            break
    else:
        selected = 0 if compact_sample < float(spans[0]["compact_start_sample"]) else len(spans) - 1
    span = spans[selected]
    clamped = min(
        max(compact_sample, float(span["compact_start_sample"])),
        float(span["compact_end_sample"]),
    )
    original_sample = float(span["original_start_sample"]) + clamped - float(span["compact_start_sample"])
    original_sample = min(
        max(original_sample, float(span["original_start_sample"])),
        float(span["original_end_sample"]),
    )
    return original_sample / SAMPLE_RATE, selected


def map_words_to_original(words: list[dict], spans: list[dict]) -> tuple[list[dict], list[dict]]:
    mapped = []
    seam_crossings = []
    for index, word in enumerate(words):
        start, start_span = compact_time_to_original(spans, float(word["compact_start"]), False)
        end, end_span = compact_time_to_original(spans, float(word["compact_end"]), True)
        value = {
            "index": index,
            "word": str(word.get("word", "")),
            "start": start,
            "end": max(start, end),
        }
        if word.get("probability") is not None:
            value["probability"] = float(word["probability"])
        if word.get("detected_language"):
            value["detected_language"] = str(word["detected_language"])
        mapped.append(value)
        if start_span != end_span:
            seam_crossings.append(
                {
                    "word_index": index,
                    "word": value["word"],
                    "start_span": start_span,
                    "end_span": end_span,
                }
            )
    return mapped, seam_crossings


def reconcile_compact_seam_crossings(
    words: list[dict],
    spans: list[dict],
    tolerance_seconds: float,
) -> tuple[list[dict], list[dict], list[dict]]:
    boundaries = [float(span["compact_end_sample"]) / SAMPLE_RATE for span in spans[:-1]]
    reconciled = []
    repairs = []
    unresolved = []
    for index, source_word in enumerate(words):
        word = dict(source_word)
        start = float(word["compact_start"])
        end = float(word["compact_end"])
        crossed = [boundary for boundary in boundaries if start < boundary < end]
        if not crossed:
            reconciled.append(word)
            continue
        if len(crossed) != 1:
            unresolved.append(
                {
                    "word_index": index,
                    "word": str(word.get("word", "")),
                    "reason": "multiple_compact_seams",
                    "compact_start": start,
                    "compact_end": end,
                    "crossed_seams": crossed,
                }
            )
            reconciled.append(word)
            continue
        boundary = crossed[0]
        left_seconds = boundary - start
        right_seconds = end - boundary
        if min(left_seconds, right_seconds) > tolerance_seconds + 1e-9:
            unresolved.append(
                {
                    "word_index": index,
                    "word": str(word.get("word", "")),
                    "reason": "compact_seam_crossing_exceeds_tolerance",
                    "compact_start": start,
                    "compact_end": end,
                    "seam_seconds": boundary,
                    "left_seconds": left_seconds,
                    "right_seconds": right_seconds,
                    "tolerance_seconds": tolerance_seconds,
                }
            )
            reconciled.append(word)
            continue
        if right_seconds <= left_seconds:
            word["compact_end"] = boundary
            action = "clip_end_to_previous_span"
            adjustment_seconds = right_seconds
        else:
            word["compact_start"] = boundary
            action = "clip_start_to_next_span"
            adjustment_seconds = left_seconds
        repairs.append(
            {
                "word_index": index,
                "word": str(word.get("word", "")),
                "action": action,
                "compact_start_before": start,
                "compact_end_before": end,
                "compact_start_after": float(word["compact_start"]),
                "compact_end_after": float(word["compact_end"]),
                "seam_seconds": boundary,
                "adjustment_seconds": adjustment_seconds,
            }
        )
        reconciled.append(word)
    return reconciled, repairs, unresolved


def pathological_repetitions(words: list[dict]) -> list[dict]:
    token_words = [
        {"token": token, "word_index": word_index}
        for word_index, word in enumerate(words)
        if (token := normalized_word_token(word))
    ]
    tokens = [item["token"] for item in token_words]
    findings = []
    for phrase_length in range(1, 11):
        index = 0
        while index + phrase_length * 5 <= len(tokens):
            phrase = tokens[index : index + phrase_length]
            repeat_count = 1
            cursor = index + phrase_length
            while tokens[cursor : cursor + phrase_length] == phrase:
                repeat_count += 1
                cursor += phrase_length
            if repeat_count >= 5:
                repeated_entries = token_words[index:cursor]
                word_start_index = int(repeated_entries[0]["word_index"])
                word_end_index = int(repeated_entries[-1]["word_index"])
                occurrences = []
                occurrence_token_starts = list(
                    range(index, cursor, phrase_length)
                )
                occurrence_start_seconds = []
                for token_start in occurrence_token_starts:
                    occurrence_entry = token_words[token_start]
                    occurrence_word = words[int(occurrence_entry["word_index"])]
                    raw_start = occurrence_word.get("start")
                    try:
                        parsed_start = float(raw_start)
                    except (TypeError, ValueError):
                        parsed_start = None
                    occurrence_start_seconds.append(
                        parsed_start
                        if parsed_start is not None and math.isfinite(parsed_start)
                        else None
                    )
                selected_occurrence_starts = occurrence_token_starts[:10]
                if len(occurrence_token_starts) > 20:
                    selected_occurrence_starts.extend(occurrence_token_starts[-10:])
                else:
                    selected_occurrence_starts.extend(occurrence_token_starts[10:])
                for occurrence_index, token_start in enumerate(
                    selected_occurrence_starts
                ):
                    token_end = token_start + phrase_length
                    occurrence_entries = token_words[token_start:token_end]
                    occurrence_word_start = int(
                        occurrence_entries[0]["word_index"]
                    )
                    occurrence_word_end = int(
                        occurrence_entries[-1]["word_index"]
                    )
                    occurrence_words = words[
                        occurrence_word_start : occurrence_word_end + 1
                    ]
                    start_seconds = float(occurrence_words[0].get("start", 0.0))
                    end_seconds = float(occurrence_words[-1].get("end", start_seconds))
                    occurrences.append(
                        {
                            "occurrence_index": (
                                occurrence_token_starts.index(token_start)
                            ),
                            "token_start_index": token_start,
                            "token_end_index": token_end - 1,
                            "word_start_index": occurrence_word_start,
                            "word_end_index": occurrence_word_end,
                            "start_seconds": start_seconds,
                            "end_seconds": end_seconds,
                            "start_timestamp": timeline_timestamp(start_seconds),
                            "end_timestamp": timeline_timestamp(end_seconds),
                            "words": [
                                timed_word_diagnostic(word, position)
                                for position, word in enumerate(
                                    occurrence_words,
                                    start=occurrence_word_start,
                                )
                            ],
                        }
                    )
                context_start = max(0, word_start_index - 5)
                context_end = min(len(words), word_end_index + 6)
                start_seconds = float(words[word_start_index].get("start", 0.0))
                end_seconds = float(words[word_end_index].get("end", start_seconds))
                findings.append(
                    {
                        "token_index": index,
                        "token_end_index": cursor - 1,
                        "word_start_index": word_start_index,
                        "word_end_index": word_end_index,
                        "start_seconds": start_seconds,
                        "end_seconds": end_seconds,
                        "start_timestamp": timeline_timestamp(start_seconds),
                        "end_timestamp": timeline_timestamp(end_seconds),
                        "phrase": phrase,
                        "repeat_count": repeat_count,
                        "occurrence_start_seconds": occurrence_start_seconds,
                        "occurrences": occurrences,
                        "occurrences_truncated": len(occurrence_token_starts) > 20,
                        "context_word_start_index": context_start,
                        "context_word_end_index": context_end - 1,
                        "context_words": [
                            timed_word_diagnostic(word, position)
                            for position, word in enumerate(
                                words[context_start:context_end],
                                start=context_start,
                            )
                        ],
                    }
                )
                index = cursor
            else:
                index += 1
    return findings


def classify_timed_repetitions(findings: list[dict]) -> tuple[list[dict], list[dict]]:
    accepted = []
    rejected = []
    for source_finding in findings:
        finding = dict(source_finding)
        starts = list(finding.get("occurrence_start_seconds") or [])
        expected_count = int(finding.get("repeat_count") or 0)
        complete = (
            len(starts) == expected_count
            and expected_count >= 5
            and all(
                isinstance(value, (int, float)) and math.isfinite(float(value))
                for value in starts
            )
        )
        strictly_increasing = complete and all(
            float(current) > float(previous)
            for previous, current in zip(starts, starts[1:])
        )
        finding["occurrence_start_count"] = len(starts)
        finding["occurrence_start_evidence_complete"] = complete
        finding["occurrence_starts_strictly_increasing"] = strictly_increasing
        if strictly_increasing:
            finding["timed_repetition_decision"] = "accepted_distinct_occurrence_starts"
            accepted.append(finding)
        else:
            finding["timed_repetition_decision"] = "rejected_missing_or_non_increasing_start"
            rejected.append(finding)
    return accepted, rejected


def timeline_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def timed_word_diagnostic(word: dict, position: int) -> dict:
    start_seconds = float(word.get("start", 0.0))
    end_seconds = float(word.get("end", start_seconds))
    return {
        "word_index": position,
        "word": str(word.get("word", "")),
        "start_seconds": start_seconds,
        "end_seconds": end_seconds,
        "start_timestamp": timeline_timestamp(start_seconds),
        "end_timestamp": timeline_timestamp(end_seconds),
    }


def word_timing_errors(words: list[dict], duration_seconds: float) -> list[dict]:
    errors = []
    previous_end = 0.0
    for index, word in enumerate(words):
        start = float(word.get("start", -1.0))
        end = float(word.get("end", -1.0))
        if not math.isfinite(start) or not math.isfinite(end) or start < 0.0 or end < start:
            errors.append({"word_index": index, "reason": "invalid_range", "start": start, "end": end})
        elif end > duration_seconds + 0.05:
            errors.append({"word_index": index, "reason": "past_audio_end", "end": end})
        elif start < previous_end - MAX_WORD_TIMING_TOLERANCE_SECONDS:
            errors.append(
                {
                    "word_index": index,
                    "reason": "non_monotonic",
                    "start": start,
                    "previous_end": previous_end,
                }
            )
        previous_end = max(previous_end, end)
    return errors


def transcribe_window(
    model,
    compact_signal: np.ndarray,
    start_seconds: float,
    end_seconds: float,
    language: str,
    max_new_tokens: int,
    word_converter: Callable,
    window_index: int,
    attempt_index: int,
    timestamp_tolerance_seconds: float,
) -> dict:
    start_sample = round(start_seconds * SAMPLE_RATE)
    end_sample = round(end_seconds * SAMPLE_RATE)
    chunk = compact_signal[start_sample:end_sample]
    if not len(chunk):
        raise RuntimeError("CrisperWhisper planned an empty inference window")
    started = time.perf_counter()
    result = model.transcribe(
        chunk,
        sr=SAMPLE_RATE,
        language=language,
        mode="verbatim",
        temperature_fallback=True,
        hallucination_mitigation=True,
        max_new_tokens=max_new_tokens,
        word_timestamps=True,
    )
    words = []
    timestamp_repairs = []
    timestamp_drops = []
    chunk_duration_seconds = len(chunk) / SAMPLE_RATE
    for word_index, item in enumerate(list(getattr(result, "words", None) or [])):
        word = word_converter(item)
        raw_start = float(word["start"])
        raw_end = float(word["end"])
        if (
            math.isfinite(raw_start)
            and math.isfinite(raw_end)
            and raw_end >= raw_start
            and raw_start >= chunk_duration_seconds
        ):
            timestamp_drops.append(
                {
                    "word_index": word_index,
                    "word": str(word.get("word", "")),
                    "reason": "fully_outside_inference_window",
                    "start": raw_start,
                    "end": raw_end,
                    "window_duration_seconds": chunk_duration_seconds,
                }
            )
            continue
        if (
            not math.isfinite(raw_start)
            or not math.isfinite(raw_end)
            or raw_end < raw_start
            or raw_start < -timestamp_tolerance_seconds
            or raw_end > chunk_duration_seconds + timestamp_tolerance_seconds
        ):
            raise RuntimeError(
                "CrisperWhisper word timestamp exceeded its inference window: "
                f"window={window_index}, attempt={attempt_index}, word={word_index}, "
                f"start={raw_start}, end={raw_end}, duration={chunk_duration_seconds}"
            )
        bounded_start = min(chunk_duration_seconds, max(0.0, raw_start))
        bounded_end = min(chunk_duration_seconds, max(0.0, raw_end))
        if bounded_end < bounded_start:
            raise RuntimeError(
                "CrisperWhisper word timestamp became invalid after inference-window bounding: "
                f"window={window_index}, attempt={attempt_index}, word={word_index}"
            )
        if bounded_start != raw_start or bounded_end != raw_end:
            timestamp_repairs.append(
                {
                    "word_index": word_index,
                    "word": str(word.get("word", "")),
                    "start_before": raw_start,
                    "end_before": raw_end,
                    "start_after": bounded_start,
                    "end_after": bounded_end,
                    "window_duration_seconds": chunk_duration_seconds,
                }
            )
        value = {
            "word": str(word.get("word", "")),
            "compact_start": bounded_start + start_seconds,
            "compact_end": bounded_end + start_seconds,
        }
        if word.get("probability") is not None:
            value["probability"] = float(word["probability"])
        words.append(value)
    return {
        "window_index": window_index,
        "attempt_index": attempt_index,
        "start_seconds": start_seconds,
        "end_seconds": end_seconds,
        "duration_seconds": end_seconds - start_seconds,
        "processing_seconds": round(time.perf_counter() - started, 3),
        "text": str(getattr(result, "text", "")),
        "word_count": len(words),
        "timestamp_repair_count": len(timestamp_repairs),
        "timestamp_repairs": timestamp_repairs,
        "timestamp_drop_count": len(timestamp_drops),
        "timestamp_drops": timestamp_drops,
        "words": words,
    }
