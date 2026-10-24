from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import statistics
import time
import traceback
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from types import SimpleNamespace
from runtime_efficiency import reuse_window_encoder
from multilingual_timing import TranscriptCoverageError, language_timing_context, require_timed_text_coverage
NORMALIZATION_CONTRACT_VERSION = 'not_applicable_in_production_worker'
NO_SPACE_LANGUAGE_CODES = {'ja', 'lo', 'my', 'th', 'yue', 'zh'}
_coverage_replan_module = None
_coverage_replan_marker = 'OUTER_WINDOW_REPLAN_REQUIRED'
_model_call_durations: list[float] = []
_encoder_counts = {'encoder_calls': 0, 'encoder_reuse_hits': 0}
_decode_beam_size = 1

def normalize_token(value: str) -> str:
    return ''.join((character.lower() for character in value if character.isalnum()))

def same_overlapping_word_occurrence(left: dict[str, object], right: dict[str, object]) -> bool:
    if normalize_token(str(left.get('word') or '')) != normalize_token(str(right.get('word') or '')):
        return False
    return min(float(left['end']), float(right['end'])) > max(float(left['start']), float(right['start']))

def assemble_word_stream(words: list[dict[str, object]], language: str) -> tuple[str, str]:
    separator = '' if language.lower() in NO_SPACE_LANGUAGE_CODES else ' '
    assembly = 'no_space_stitched_word_stream' if not separator else 'space_joined_stitched_word_stream'
    return (separator.join((str(word['word']) for word in words)), assembly)

def result_words(result: object, language: str) -> list[dict[str, object]]:
    words = [{'word': value.word, 'start': value.start, 'end': value.end} for value in list(result.words or [])]
    if language.lower() not in NO_SPACE_LANGUAGE_CODES:
        return words
    try:
        require_timed_text_coverage(result.text, words)
    except TranscriptCoverageError as error:
        error.native_coverage_diagnostic = {'decoded_text': str(result.text or ''), 'timed_words': words}
        raise
    return words

def result_chunks(result: object) -> list[dict[str, object]]:
    return [{'chunk_idx': value.chunk_idx, 'start_sec': value.start_sec, 'end_sec': value.end_sec, 'text': value.text, 'context': value.context, 'is_last': value.is_last} for value in list(result.chunks or [])]

def set_coverage_replan_allowed(allowed: bool) -> None:
    if _coverage_replan_module is not None:
        _coverage_replan_module.WINDOW_REPLAN_ALLOWED = bool(allowed)

def is_coverage_replan_error(error: BaseException) -> bool:
    return str(error) == _coverage_replan_marker

def natural_boundary_seconds(spans: list[dict[str, object]], sample_rate: int) -> list[float]:
    return [int(span['compact_end_sample']) / sample_rate for span in spans]

def choose_vad_window_end(start_seconds: float, duration_seconds: float, boundaries: list[float], target_seconds: float, maximum_seconds: float, minimum_seconds: float) -> tuple[float, str]:
    maximum_end = min(duration_seconds, start_seconds + maximum_seconds)
    if maximum_end >= duration_seconds - 1e-09:
        return (duration_seconds, 'final')
    candidates = [boundary for boundary in boundaries if boundary >= start_seconds + minimum_seconds - 1e-06 and boundary <= maximum_end + 1e-06 and (duration_seconds - boundary >= minimum_seconds - 1e-06)]
    if candidates:
        target_end = start_seconds + target_seconds
        return (min(candidates, key=lambda value: (abs(value - target_end), value)), 'vad_silence_boundary')
    return (maximum_end, 'model_limit')

def compact_time_to_original(spans: list[dict[str, object]], compact_seconds: float, sample_rate: int, prefer_previous: bool) -> float:
    compact_sample = float(compact_seconds) * sample_rate
    epsilon = 0.0001 * sample_rate
    selected = None
    for (index, span) in enumerate(spans):
        start = float(span['compact_start_sample'])
        end = float(span['compact_end_sample'])
        if start - epsilon <= compact_sample < end - epsilon:
            selected = index
            break
        if abs(compact_sample - end) <= epsilon:
            selected = index if prefer_previous else min(index + 1, len(spans) - 1)
            break
    if selected is None:
        selected = 0 if compact_sample < float(spans[0]['compact_start_sample']) else len(spans) - 1
    span = spans[selected]
    clamped = min(max(compact_sample, float(span['compact_start_sample'])), float(span['compact_end_sample']))
    original_sample = float(span['original_start_sample']) + clamped - float(span['compact_start_sample'])
    original_sample = min(max(original_sample, float(span['original_start_sample'])), float(span['original_end_sample']))
    return original_sample / sample_rate

def map_compact_words_to_original(words: list[dict[str, object]], spans: list[dict[str, object]], sample_rate: int) -> list[dict[str, object]]:
    mapped = []
    for word in words:
        start = compact_time_to_original(spans, float(word['start']), sample_rate, False)
        end = compact_time_to_original(spans, float(word['end']), sample_rate, True)
        mapped.append({**word, 'start': start, 'end': max(start, end)})
    return mapped

def outer_overlap_candidates(minimum_seconds: float, maximum_seconds: float) -> list[float]:
    if minimum_seconds < 0 or maximum_seconds < minimum_seconds:
        raise ValueError('Invalid outer overlap bounds')
    values = []
    for value in (minimum_seconds, 3.0, 5.0, 7.0, maximum_seconds):
        bounded = min(maximum_seconds, max(minimum_seconds, float(value)))
        if not any((abs(bounded - existing) <= 1e-09 for existing in values)):
            values.append(bounded)
    return sorted(values)

def select_initial_overlap(merged_words: list[dict[str, object]], previous_end_seconds: float, candidates: list[float], minimum_context_words: int) -> tuple[float, dict[str, int]]:
    if minimum_context_words < 2:
        raise ValueError('At least two context words required')
    counts = {}
    for overlap_seconds in candidates:
        count = sum((1 for word in merged_words if float(word['end']) >= previous_end_seconds - overlap_seconds + 0.02 and float(word['start']) <= previous_end_seconds - 0.02 and normalize_token(str(word.get('word') or ''))))
        counts[f'{overlap_seconds:g}'] = count
        if count >= minimum_context_words:
            return (overlap_seconds, counts)
    return (candidates[-1], counts)

def select_silence_aware_initial_overlap(merged_words: list[dict[str, object]], previous_end_seconds: float, candidates: list[float], minimum_context_words: int) -> tuple[float, dict[str, int], dict[str, object]]:
    minimum_overlap = candidates[0]
    maximum_gap_overlap = min(candidates[-1], max(3.0, minimum_overlap))
    viable_gaps = []
    ordered_words = sorted(merged_words, key=lambda word: (float(word['start']), float(word['end'])))
    for (left, right) in zip(ordered_words, ordered_words[1:]):
        gap_start = float(left['end'])
        gap_end = float(right['start'])
        gap_seconds = gap_end - gap_start
        if gap_seconds < 0.04:
            continue
        boundary_seconds = (gap_start + gap_end) / 2.0
        overlap_seconds = previous_end_seconds - boundary_seconds
        if overlap_seconds < minimum_overlap - 1e-09 or overlap_seconds > maximum_gap_overlap + 1e-09:
            continue
        context_word_count = sum((1 for word in merged_words if float(word['end']) >= boundary_seconds + 0.02 and float(word['start']) <= previous_end_seconds - 0.02 and normalize_token(str(word.get('word') or ''))))
        if context_word_count < minimum_context_words:
            continue
        viable_gaps.append((overlap_seconds, -gap_seconds, boundary_seconds, gap_start, gap_end, context_word_count))
    if viable_gaps:
        (overlap_seconds, negative_gap_seconds, boundary_seconds, gap_start, gap_end, context_word_count) = min(viable_gaps)
        return (overlap_seconds, {f'{overlap_seconds:g}': context_word_count}, {'method': 'word_gap_midpoint', 'boundary_seconds': boundary_seconds, 'gap_start_seconds': gap_start, 'gap_end_seconds': gap_end, 'gap_seconds': -negative_gap_seconds})
    (overlap_seconds, counts) = select_initial_overlap(merged_words, previous_end_seconds, candidates, minimum_context_words)
    return (overlap_seconds, counts, {'method': 'context_count_fallback'})

def offset_words(words: list[dict[str, object]], offset_seconds: float) -> list[dict[str, object]]:
    return [{**word, 'start': float(word['start']) + offset_seconds, 'end': float(word['end']) + offset_seconds} for word in words]

def offset_chunks(chunks: list[dict[str, object]], offset_seconds: float) -> list[dict[str, object]]:
    return [{**chunk, 'start_sec': float(chunk['start_sec']) + offset_seconds, 'end_sec': float(chunk['end_sec']) + offset_seconds} for chunk in chunks]

def longest_common_contiguous_by_time(reference: list[tuple[int, str]], candidate: list[tuple[int, str]], reference_words: list[dict[str, object]], candidate_words: list[dict[str, object]]) -> tuple[int, int, int]:
    matches = []
    for reference_start in range(len(reference)):
        for candidate_start in range(len(candidate)):
            length = 0
            center_deltas = []
            while reference_start + length < len(reference) and candidate_start + length < len(candidate) and (reference[reference_start + length][1] == candidate[candidate_start + length][1]):
                reference_word = reference_words[reference[reference_start + length][0]]
                candidate_word = candidate_words[candidate[candidate_start + length][0]]
                reference_center = (float(reference_word['start']) + float(reference_word['end'])) / 2.0
                candidate_center = (float(candidate_word['start']) + float(candidate_word['end'])) / 2.0
                center_deltas.append(abs(reference_center - candidate_center))
                length += 1
            if length < 2 or max(center_deltas) > 0.75:
                continue
            matches.append((-length, sum(center_deltas) / length, max(center_deltas), -(reference_start + length), reference_start, candidate_start))
    if not matches:
        return (0, 0, 0)
    selected = min(matches)
    return (selected[4], selected[5], -selected[0])

def stitch_window_words(merged_words: list[dict[str, object]], current_words: list[dict[str, object]], overlap_start_seconds: float, previous_end_seconds: float) -> tuple[list[dict[str, object]], dict[str, object]]:
    previous_pairs = [(index, normalize_token(str(word.get('word') or ''))) for (index, word) in enumerate(merged_words) if float(word['end']) >= overlap_start_seconds + 0.02 and float(word['start']) <= previous_end_seconds - 0.02 and normalize_token(str(word.get('word') or ''))]
    current_pairs = [(index, normalize_token(str(word.get('word') or ''))) for (index, word) in enumerate(current_words) if float(word['end']) >= overlap_start_seconds + 0.02 and float(word['start']) <= previous_end_seconds - 0.02 and normalize_token(str(word.get('word') or ''))]
    if not previous_pairs and (not current_pairs):
        appended = [dict(word) for word in current_words if float(word['start']) >= previous_end_seconds - 1e-09]
        return ([*merged_words, *appended], {'method': 'shared_silence_boundary', 'anchor_word_count': 0, 'appended_word_count': len(appended)})
    (reference_index, candidate_index, match_length) = longest_common_contiguous_by_time(previous_pairs, current_pairs, merged_words, current_words)
    if match_length < 2:
        raise RuntimeError(f'Outer window stitch requires at least two consecutive shared words: previous={len(previous_pairs)} current={len(current_pairs)} best={match_length}')
    previous_end_index = previous_pairs[reference_index + match_length - 1][0]
    current_end_index = current_pairs[candidate_index + match_length - 1][0]
    kept = [dict(word) for word in merged_words[:previous_end_index + 1]]
    appended = [dict(word) for word in current_words[current_end_index + 1:]]
    boundary_resolution = 'already_monotonic'
    repaired_seconds = 0.0
    if kept and appended and (float(kept[-1]['end']) > float(appended[0]['start'])):
        previous_start = float(kept[-1]['start'])
        previous_end = float(kept[-1]['end'])
        next_start = float(appended[0]['start'])
        next_end = float(appended[0]['end'])
        intersection_start = max(previous_start, next_start)
        intersection_end = min(previous_end, next_end)
        if intersection_end <= intersection_start:
            raise RuntimeError('Outer window stitch produced a non-local time overlap')
        shared_boundary = (intersection_start + intersection_end) / 2.0
        kept[-1]['end'] = shared_boundary
        appended[0]['start'] = shared_boundary
        boundary_resolution = 'local_interval_midpoint'
        repaired_seconds = previous_end - next_start
    return ([*kept, *appended], {'method': 'two_word_contiguous_anchor', 'anchor_word_count': match_length, 'anchor_words': [previous_pairs[index][1] for index in range(reference_index, reference_index + match_length)], 'kept_previous_through_index': previous_end_index, 'used_current_from_index': current_end_index + 1, 'appended_word_count': len(appended), 'boundary_resolution': boundary_resolution, 'boundary_overlap_repaired_seconds': repaired_seconds})

def stitch_window_words_by_temporal_seam(merged_words: list[dict[str, object]], current_words: list[dict[str, object]], overlap_start_seconds: float, previous_end_seconds: float) -> tuple[list[dict[str, object]], dict[str, object]]:
    seam_seconds = (overlap_start_seconds + previous_end_seconds) / 2.0
    kept = [dict(word) for word in merged_words if (float(word['start']) + float(word['end'])) / 2.0 <= seam_seconds]
    appended = [dict(word) for word in current_words if (float(word['start']) + float(word['end'])) / 2.0 > seam_seconds]
    if not kept or not appended:
        raise RuntimeError('Temporal seam could not preserve both window sides')
    duplicate_removed = False
    if same_overlapping_word_occurrence(kept[-1], appended[0]):
        appended = appended[1:]
        duplicate_removed = True
    boundary_resolution = 'already_monotonic'
    repaired_seconds = 0.0
    if appended and float(kept[-1]['end']) > float(appended[0]['start']):
        previous_start = float(kept[-1]['start'])
        previous_end = float(kept[-1]['end'])
        next_start = float(appended[0]['start'])
        next_end = float(appended[0]['end'])
        intersection_start = max(previous_start, next_start)
        intersection_end = min(previous_end, next_end)
        if intersection_end <= intersection_start:
            raise RuntimeError('Temporal seam produced a non-local time overlap')
        shared_boundary = (intersection_start + intersection_end) / 2.0
        kept[-1]['end'] = shared_boundary
        appended[0]['start'] = shared_boundary
        boundary_resolution = 'local_interval_midpoint'
        repaired_seconds = previous_end - next_start
    boundary_gap_seconds = max(0.0, float(appended[0]['start']) - float(kept[-1]['end'])) if appended else 0.0
    return ([*kept, *appended], {'method': 'temporal_midpoint_seam', 'seam_seconds': seam_seconds, 'kept_previous_word_count': len(kept), 'appended_word_count': len(appended), 'duplicate_removed': duplicate_removed, 'boundary_resolution': boundary_resolution, 'boundary_overlap_repaired_seconds': repaired_seconds, 'boundary_gap_seconds': boundary_gap_seconds})

def stitch_window_words_by_temporal_coverage(merged_words: list[dict[str, object]], current_words: list[dict[str, object]], overlap_start_seconds: float, previous_end_seconds: float) -> tuple[list[dict[str, object]], dict[str, object]]:
    seam_seconds = (overlap_start_seconds + previous_end_seconds) / 2.0
    if merged_words and len(current_words) >= 2:
        previous_last = dict(merged_words[-1])
        leading = dict(current_words[0])
        following = dict(current_words[1])
        leading_duration = float(leading['end']) - float(leading['start'])
        available_gap = float(following['start']) - float(previous_last['end'])
        leading_is_left_edge = float(leading['start']) - overlap_start_seconds <= 0.3
        leading_has_delayed_follower = float(following['start']) - float(leading['end']) >= 0.8
        leading_has_content = bool(normalize_token(str(leading.get('word') or '')))
        leading_is_not_overlapping_duplicate = not same_overlapping_word_occurrence(previous_last, leading)
        if 0.0 < leading_duration <= 0.4 and available_gap >= leading_duration + 0.04 and leading_is_left_edge and leading_has_delayed_follower and leading_has_content and leading_is_not_overlapping_duplicate:
            padding = (available_gap - leading_duration) / 2.0
            leading['start'] = float(previous_last['end']) + padding
            leading['end'] = float(leading['start']) + leading_duration
            appended = [leading, *[dict(word) for word in current_words[1:]]]
            return ([*[dict(word) for word in merged_words], *appended], {'method': 'left_edge_short_word_union', 'seam_seconds': seam_seconds, 'kept_previous_word_count': len(merged_words), 'appended_word_count': len(appended), 'duplicate_removed': False, 'skipped_previous_crossing_word_count': 0, 'skipped_current_crossing_word_count': 0, 'boundary_resolution': 'retimed_left_edge_connector_into_gap', 'boundary_shared_seconds': None, 'boundary_overlap_repaired_seconds': 0.0, 'boundary_gap_seconds': padding, 'selection_score': 0.0})
    previous_indices = [index for (index, word) in enumerate(merged_words) if float(word['end']) >= overlap_start_seconds - 0.02 and float(word['start']) <= previous_end_seconds + 0.02]
    current_indices = [index for (index, word) in enumerate(current_words) if float(word['end']) >= overlap_start_seconds - 0.02 and float(word['start']) <= previous_end_seconds + 0.02]
    candidates = []
    for previous_index in previous_indices:
        for current_index in current_indices:
            kept = [dict(word) for word in merged_words[:previous_index + 1]]
            appended = [dict(word) for word in current_words[current_index:]]
            if not kept or not appended:
                continue
            duplicate_removed = False
            if same_overlapping_word_occurrence(kept[-1], appended[0]):
                appended = appended[1:]
                duplicate_removed = True
                if not appended:
                    continue
            previous_word = kept[-1]
            next_word = appended[0]
            previous_start = float(previous_word['start'])
            previous_end = float(previous_word['end'])
            next_start = float(next_word['start'])
            next_end = float(next_word['end'])
            if previous_end < previous_start or next_end < next_start:
                continue
            overlap_seconds = max(0.0, previous_end - next_start)
            boundary_resolution = 'already_monotonic'
            shared_boundary = None
            if overlap_seconds > 0.0:
                lower = max(previous_start, next_start)
                upper = min(previous_end, next_end)
                if kept[:-1]:
                    lower = max(lower, float(kept[-2]['end']))
                if appended[1:]:
                    upper = min(upper, float(appended[1]['start']))
                if upper < lower - 1e-09:
                    continue
                shared_boundary = (lower + upper) / 2.0
                kept[-1]['end'] = shared_boundary
                appended[0]['start'] = shared_boundary
                boundary_resolution = 'coverage_preserving_local_midpoint'
            skipped_previous = [word for word in merged_words[previous_index + 1:] if float(word['start']) < seam_seconds]
            skipped_current = [word for word in current_words[:current_index] if float(word['end']) > seam_seconds]
            boundary_gap_seconds = max(0.0, float(appended[0]['start']) - float(kept[-1]['end']))
            boundary_center = (float(kept[-1]['end']) + float(appended[0]['start'])) / 2.0
            score = 1000.0 * (len(skipped_previous) + len(skipped_current)) + 10.0 * boundary_gap_seconds + overlap_seconds + abs(boundary_center - seam_seconds)
            candidates.append((score, previous_index, current_index, kept, appended, {'method': 'temporal_coverage_boundary', 'seam_seconds': seam_seconds, 'kept_previous_word_count': len(kept), 'appended_word_count': len(appended), 'duplicate_removed': duplicate_removed, 'skipped_previous_crossing_word_count': len(skipped_previous), 'skipped_current_crossing_word_count': len(skipped_current), 'boundary_resolution': boundary_resolution, 'boundary_shared_seconds': shared_boundary, 'boundary_overlap_repaired_seconds': overlap_seconds, 'boundary_gap_seconds': boundary_gap_seconds, 'selection_score': score}))
    if not candidates:
        return stitch_window_words_by_temporal_seam(merged_words, current_words, overlap_start_seconds, previous_end_seconds)
    (_, _, _, kept, appended, diagnostic) = min(candidates, key=lambda value: (value[0], -value[1], value[2]))
    return ([*kept, *appended], diagnostic)

def transcribe_vad_compact_audio(model: object, compact_audio: object, spans: list[dict[str, object]], sample_rate: int, language: str, outer_window_seconds: float, outer_overlap_seconds: float, outer_maximum_overlap_seconds: float, outer_minimum_context_words: int, quality_retry_seconds: tuple[float, ...] = (15.0, 10.0)) -> dict[str, object]:
    target_window_seconds = min(25.0, outer_window_seconds)
    minimum_window_seconds = 5.0
    duration_seconds = len(compact_audio) / sample_rate
    boundaries = natural_boundary_seconds(spans, sample_rate)
    overlap_candidates = outer_overlap_candidates(outer_overlap_seconds, outer_maximum_overlap_seconds)
    if overlap_candidates[-1] >= outer_window_seconds:
        raise ValueError('Outer overlap must be shorter than outer window')
    started = time.perf_counter()
    merged_words: list[dict[str, object]] = []
    outer_windows = []
    language_result = language
    mode_result = 'verbatim'
    previous_end_seconds = 0.0
    previous_end_kind = 'first'
    window_index = 0
    while previous_end_seconds < duration_seconds - 1e-09:
        direct_vad_seam = window_index > 0 and previous_end_kind == 'vad_silence_boundary'
        if window_index == 0 or direct_vad_seam:
            candidates = [0.0]
            context_counts = {}
            selected_initial_overlap = 0.0
            initial_overlap_selection = {'method': 'first_window' if window_index == 0 else 'vad_silence_boundary'}
        else:
            (selected_initial_overlap, context_counts, initial_overlap_selection) = select_silence_aware_initial_overlap(merged_words, previous_end_seconds, overlap_candidates, outer_minimum_context_words)
            candidates = [selected_initial_overlap] + [value for value in overlap_candidates if value > selected_initial_overlap + 1e-09]
        attempts = []
        accepted = None
        last_stitch_error = None
        window_plans = [(overlap, outer_window_seconds) for overlap in candidates]
        if language.lower() in NO_SPACE_LANGUAGE_CODES:
            window_plans.extend((overlap, limit) for limit in quality_retry_seconds for overlap in candidates if overlap < limit and limit < outer_window_seconds)
        seen_ranges = set()
        for (candidate_index, (overlap_seconds, window_limit)) in enumerate(window_plans):
            start_seconds = 0.0 if window_index == 0 else previous_end_seconds - overlap_seconds
            (end_seconds, end_kind) = choose_vad_window_end(start_seconds, duration_seconds, boundaries, min(target_window_seconds, window_limit), window_limit, minimum_window_seconds)
            if end_seconds <= previous_end_seconds + 1e-09:
                continue
            start_frame = int(round(start_seconds * sample_rate))
            end_frame = int(round(end_seconds * sample_rate))
            if (start_frame, end_frame) in seen_ranges:
                continue
            seen_ranges.add((start_frame, end_frame))
            window_started = time.perf_counter()
            try:
                with language_timing_context(model, language):
                    result = transcribe_model(model, compact_audio[start_frame:end_frame], sample_rate, language, allow_coverage_replan=candidate_index < len(window_plans) - 1)
                words = offset_words(result_words(result, language), start_seconds)
            except RuntimeError as error:
                if not is_coverage_replan_error(error) and not isinstance(error, TranscriptCoverageError):
                    raise
                last_stitch_error = error
                attempts.append({'overlap_seconds': overlap_seconds, 'start_seconds': start_seconds, 'end_seconds': end_seconds, 'end_kind': end_kind, 'audio_seconds': end_seconds - start_seconds, 'accepted': False, 'coverage_replan': True, 'error': str(error), 'elapsed_seconds': time.perf_counter() - window_started})
                if isinstance(error, TranscriptCoverageError):
                    attempts[-1]['native_coverage'] = getattr(error, 'native_coverage_diagnostic', None)
                print(f'CORPUS_VAD_REPLAN window={window_index + 1} overlap={overlap_seconds:.3f}', flush=True)
                continue
            window_elapsed = time.perf_counter() - window_started
            chunks = offset_chunks(result_chunks(result), start_seconds)
            attempt = {'overlap_seconds': overlap_seconds, 'start_seconds': start_seconds, 'end_seconds': end_seconds, 'end_kind': end_kind, 'audio_seconds': end_seconds - start_seconds, 'elapsed_seconds': window_elapsed, 'word_count': len(words)}
            if not words:
                attempt['accepted'] = False
                attempt['error'] = 'empty_speech_window'
                attempts.append(attempt)
                del result
                continue
            if window_index == 0:
                candidate_merged = words
                stitch = None
            elif direct_vad_seam:
                candidate_merged = [*merged_words, *words]
                stitch = {'method': 'vad_silence_boundary', 'seam_seconds': previous_end_seconds, 'anchor_word_count': 0}
            else:
                try:
                    (candidate_merged, stitch) = stitch_window_words(merged_words, words, start_seconds, previous_end_seconds)
                except RuntimeError as error:
                    last_stitch_error = error
                    if language.lower() in NO_SPACE_LANGUAGE_CODES:
                        attempt['accepted'] = False
                        attempt['stitch_error'] = str(error)
                        attempts.append(attempt)
                        del result
                        continue
                    try:
                        (candidate_merged, stitch) = stitch_window_words_by_temporal_coverage(merged_words, words, start_seconds, previous_end_seconds)
                    except RuntimeError as temporal_error:
                        last_stitch_error = temporal_error
                        attempt['accepted'] = False
                        attempt['stitch_error'] = str(error)
                        attempt['temporal_stitch_error'] = str(temporal_error)
                        attempts.append(attempt)
                        print(f'CORPUS_VAD_RETRY window={window_index + 1} overlap={overlap_seconds:.3f} error={temporal_error}', flush=True)
                        del result
                        continue
                    stitch['lexical_anchor_error'] = str(error)
            attempt['accepted'] = True
            attempts.append(attempt)
            accepted = {'merged_words': candidate_merged, 'stitch': stitch, 'result_text': result.text, 'result_language': result.language, 'result_mode': result.mode, 'chunks': chunks, 'words': words, 'start_seconds': start_seconds, 'end_seconds': end_seconds, 'end_kind': end_kind, 'elapsed_seconds': window_elapsed, 'attempts': attempts, 'overlap_seconds': overlap_seconds}
            del result
            break
        if accepted is None:
            error = RuntimeError('VAD compact window stitch exhausted overlap candidates')
            error.window_diagnostic = {'language': language, 'window_index': window_index, 'previous_end_seconds': previous_end_seconds, 'attempts': attempts}
            raise error from last_stitch_error
        merged_words = list(accepted['merged_words'])
        language_result = accepted['result_language']
        mode_result = accepted['result_mode']
        previous_end_seconds = float(accepted['end_seconds'])
        previous_end_kind = str(accepted['end_kind'])
        words = list(accepted['words'])
        outer_windows.append({'window_index': window_index, 'start_seconds': accepted['start_seconds'], 'end_seconds': accepted['end_seconds'], 'end_kind': accepted['end_kind'], 'audio_seconds': float(accepted['end_seconds']) - float(accepted['start_seconds']), 'elapsed_seconds': accepted['elapsed_seconds'], 'word_count': len(words), 'text': accepted['result_text'], 'chunks': accepted['chunks'], 'stitch': accepted['stitch'], 'accepted_overlap_seconds': accepted['overlap_seconds'], 'selected_initial_overlap_seconds': selected_initial_overlap, 'initial_overlap_selection': initial_overlap_selection, 'context_word_counts_by_overlap': context_counts, 'attempts': accepted['attempts']})
        print(f"CORPUS_VAD_DONE window={window_index + 1} range={float(accepted['start_seconds']):.3f}-{float(accepted['end_seconds']):.3f} kind={accepted['end_kind']} seconds={float(accepted['elapsed_seconds']):.3f} words={len(words)}", flush=True)
        window_index += 1
    elapsed = time.perf_counter() - started
    mapped_words = map_compact_words_to_original(merged_words, spans, sample_rate)
    (assembled_text, text_assembly) = assemble_word_stream(mapped_words, language_result)
    return {'text': assembled_text, 'text_assembly': text_assembly, 'language': language_result, 'mode': mode_result, 'words': mapped_words, 'chunks': outer_windows[0]['chunks'] if len(outer_windows) == 1 else [], 'outer_windows': outer_windows, 'elapsed_seconds': elapsed, 'windowed': len(outer_windows) > 1, 'route_diagnostics': {'route': 'canonical_vad_compact_timeline_ct2', 'compact_duration_seconds': duration_seconds, 'span_count': len(spans), 'natural_boundaries_seconds': boundaries}}

def slice_compact_spans(spans: list[dict[str, object]], start_sample: int, end_sample: int) -> list[dict[str, object]]:
    sliced = []
    for span in spans:
        compact_start = int(span['compact_start_sample'])
        compact_end = int(span['compact_end_sample'])
        overlap_start = max(start_sample, compact_start)
        overlap_end = min(end_sample, compact_end)
        if overlap_end <= overlap_start:
            continue
        original_start = int(span['original_start_sample']) + overlap_start - compact_start
        original_end = original_start + overlap_end - overlap_start
        sliced.append({
            **dict(span),
            'compact_start_sample': overlap_start - start_sample,
            'compact_end_sample': overlap_end - start_sample,
            'original_start_sample': original_start,
            'original_end_sample': original_end,
        })
    if not sliced:
        raise RuntimeError('Language run does not intersect a VAD compact span')
    return sliced

def transcribe_language_runs(model: object, compact_audio: object, spans: list[dict[str, object]], sample_rate: int, language_runs: list[dict[str, object]], segmentation: dict[str, object]) -> dict[str, object]:
    words = []
    windows = []
    run_results = []
    texts = []
    for run in language_runs:
        run_index = int(run['run_index'])
        language = str(run['detected_language'])
        start_sample = max(0, round(float(run['start_seconds']) * sample_rate))
        end_sample = min(len(compact_audio), round(float(run['end_seconds']) * sample_rate))
        if end_sample <= start_sample:
            raise RuntimeError(f'Language run is empty: {run_index}')
        run_spans = slice_compact_spans(spans, start_sample, end_sample)
        result = transcribe_vad_compact_audio(
            model,
            compact_audio[start_sample:end_sample],
            run_spans,
            sample_rate,
            language,
            float(segmentation['outer_window_seconds']),
            float(segmentation['outer_overlap_seconds']),
            float(segmentation['outer_maximum_overlap_seconds']),
            int(segmentation['outer_minimum_context_words']),
            quality_retry_seconds=tuple(segmentation.get('no_space_quality_retry_seconds', (15.0, 10.0))),
        )
        run_words = [{**dict(word), 'detected_language': language} for word in list(result['words'])]
        run_windows = []
        for local_index, window in enumerate(list(result['outer_windows'])):
            item = dict(window)
            item.update({
                'window_index': len(windows) + local_index,
                'local_window_index': int(window.get('window_index') or local_index),
                'language_run_index': run_index,
                'detected_language': language,
                'compact_start_seconds': float(window['start_seconds']) + start_sample / sample_rate,
                'compact_end_seconds': float(window['end_seconds']) + start_sample / sample_rate,
            })
            run_windows.append(item)
        words.extend(run_words)
        windows.extend(run_windows)
        texts.append(str(result['text']).strip())
        run_results.append({
            **dict(run),
            'word_count': len(run_words),
            'text': str(result['text']),
            'text_assembly': str(result['text_assembly']),
            'window_count': len(run_windows),
            'route_diagnostics': dict(result['route_diagnostics']),
        })
    words.sort(key=lambda word: (float(word['start']), float(word['end'])))
    return {
        'text': ' '.join(text for text in texts if text),
        'words': words,
        'outer_windows': windows,
        'language_runs': run_results,
        'route_diagnostics': {
            'route': 'detected_language_runs_ct2',
            'run_count': len(run_results),
            'compact_duration_seconds': len(compact_audio) / sample_rate,
            'span_count': len(spans),
        },
    }

def segmentation_efficiency(transcription: dict[str, object], inference_input_seconds: float) -> dict[str, object]:
    windows = list(transcription.get('outer_windows') or [])
    attempts = [dict(attempt) for window in windows for attempt in list(dict(window).get('attempts') or [])]
    attempted_audio_seconds = sum((float(attempt.get('audio_seconds') or 0.0) for attempt in attempts))
    accepted_overlaps = [float(dict(window).get('accepted_overlap_seconds') or 0.0) for window in windows[1:]]
    reprocessed_audio_seconds = max(0.0, attempted_audio_seconds - float(inference_input_seconds))
    return {'window_count': len(windows), 'attempt_count': len(attempts), 'replanned_window_count': sum((1 for window in windows if len(list(dict(window).get('attempts') or [])) > 1)), 'attempted_audio_seconds': attempted_audio_seconds, 'unique_inference_input_seconds': float(inference_input_seconds), 'reprocessed_audio_seconds': reprocessed_audio_seconds, 'reprocessed_audio_ratio': reprocessed_audio_seconds / float(inference_input_seconds) if inference_input_seconds > 0 else 0.0, 'mean_accepted_overlap_seconds': sum(accepted_overlaps) / len(accepted_overlaps) if accepted_overlaps else 0.0, 'maximum_accepted_overlap_seconds': max(accepted_overlaps) if accepted_overlaps else 0.0}

def transcribe_model(model: object, audio: object, sample_rate: int, language: str, allow_coverage_replan: bool=False) -> object:
    with reuse_window_encoder(model, _encoder_counts):
        return decode_window(model, audio, sample_rate, language, allow_coverage_replan)


def decode_window(model: object, audio: object, sample_rate: int, language: str, allow_coverage_replan: bool=False) -> object:
    set_coverage_replan_allowed(allow_coverage_replan)
    started = time.perf_counter()
    try:
        if _decode_beam_size > 1:
            from crisperwhisper.prompt import PromptBuilder, strip_prompt_artifacts
            from crisperwhisper.word_timing import extract_word_timings
            engine = model._engine
            prompt_tokens = PromptBuilder(engine, language=language).verbatim()
            engine.enable_attention(None)
            (features, mel) = engine.extract_features_with_mel(audio)
            generated = engine.generate(features, [prompt_tokens], max_length=400, beam_size=_decode_beam_size, suppress_tokens=None)[0]
            attention = engine.cross_attention_for_tokens(features, prompt_tokens, generated)
            timed_words = extract_word_timings(engine, generated, attention, mel, audio_duration_s=len(audio) / sample_rate)
            return SimpleNamespace(text=strip_prompt_artifacts(engine.decode_tokens(generated, skip_special=True)), words=timed_words, chunks=[], language=language, mode='verbatim')
        return model.transcribe(audio, sr=sample_rate, language=language, mode='verbatim', word_timestamps=True, temperature_fallback=True, max_new_tokens=400, speculative_decoding=False, hallucination_mitigation=True, early_eot_recovery=True, suppress_tokens=None)
    finally:
        _model_call_durations.append(time.perf_counter() - started)
