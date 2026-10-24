from __future__ import annotations

from typing import Any, Dict, List

MIN_REPAIRED_WORD_DURATION_SECONDS = 0.01


def repair_aligned_word_timeline(words: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], int]:
    repaired_words = [dict(word) for word in words]
    fixed = 0
    for index, word in enumerate(repaired_words):
        start = float(word["start"])
        end = float(word["end"])
        if end < start + MIN_REPAIRED_WORD_DURATION_SECONDS:
            word["end"] = start + MIN_REPAIRED_WORD_DURATION_SECONDS
            fixed += 1

    for index in range(len(repaired_words) - 1):
        current = repaired_words[index]
        next_word = repaired_words[index + 1]
        current_start = float(current["start"])
        current_end = float(current["end"])
        next_start = float(next_word["start"])
        next_end = float(next_word["end"])
        if current_end > next_start:
            lower_boundary = current_start + MIN_REPAIRED_WORD_DURATION_SECONDS
            upper_boundary = next_end - MIN_REPAIRED_WORD_DURATION_SECONDS
            if lower_boundary <= upper_boundary:
                midpoint = (current_end + next_start) / 2.0
                boundary = min(max(midpoint, lower_boundary), upper_boundary)
                current["end"] = round(boundary, 3)
                next_word["start"] = round(boundary, 3)
            else:
                next_word["start"] = current_end
                next_word["end"] = max(next_end, current_end + MIN_REPAIRED_WORD_DURATION_SECONDS)
            fixed += 1
        if float(next_word["end"]) < float(next_word["start"]) + MIN_REPAIRED_WORD_DURATION_SECONDS:
            next_word["end"] = float(next_word["start"]) + MIN_REPAIRED_WORD_DURATION_SECONDS
            fixed += 1

    return repaired_words, fixed


def max_timing_adjustment_seconds(
    original_words: List[Dict[str, Any]],
    repaired_words: List[Dict[str, Any]],
) -> float:
    max_adjustment = 0.0
    for original, repaired in zip(original_words, repaired_words):
        max_adjustment = max(
            max_adjustment,
            abs(float(original["start"]) - float(repaired["start"])),
            abs(float(original["end"]) - float(repaired["end"])),
        )
    return max_adjustment
