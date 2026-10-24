from __future__ import annotations

import re
import unicodedata
from typing import Iterable


TOKEN_PATTERN = re.compile(
    r"\[[^\]\r\n]{1,100}\]|<[^>\r\n]{1,100}>|[^\W_]+(?:['-][^\W_]+)*",
    re.UNICODE,
)
WORD_PATTERN = re.compile(r"[^\W_]+(?:['-][^\W_]+)*", re.UNICODE)
EVENT_PATTERN = re.compile(r"^(?:\[[^\]]+\]|<[^>]+>)$")
COUNT_PATTERN = re.compile(r"^\s*Toplam kelime\s*:\s*(\d+)\s*$", re.IGNORECASE)


def canonical_unicode(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    replacements = {
        "’": "'",
        "‘": "'",
        "‛": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "‑": "-",
        "−": "-",
        "…": "...",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def normalize_token(value: str) -> str:
    token = canonical_unicode(value).strip().lower()
    if EVENT_PATTERN.fullmatch(token):
        inner = re.sub(r"\s+", " ", token[1:-1]).strip()
        return f"[{inner}]"
    return token.strip("'\-")


def tokenize(value: str) -> list[str]:
    text = canonical_unicode(value)
    return [normalize_token(match.group(0)) for match in TOKEN_PATTERN.finditer(text)]


def lexical_tokens(tokens: Iterable[str]) -> list[str]:
    return [token for token in tokens if not EVENT_PATTERN.fullmatch(token)]


def event_tokens(tokens: Iterable[str]) -> list[str]:
    return [token for token in tokens if EVENT_PATTERN.fullmatch(token)]


def extract_elevenlabs_body(raw_text: str) -> str:
    text = canonical_unicode(raw_text).replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    count_index = None
    for index, line in enumerate(lines):
        if COUNT_PATTERN.match(line):
            count_index = index
            break
    if count_index is not None:
        lines = lines[:count_index]
    separator_index = None
    for index, line in enumerate(lines):
        if len(line.strip()) >= 5 and set(line.strip()) == {"="}:
            separator_index = index
            break
    if separator_index is not None:
        lines = lines[separator_index + 1 :]
    filtered = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.upper().startswith("ELEVENLABS SCRIBE"):
            continue
        filtered.append(stripped)
    return " ".join(filtered).strip()


def token_summary(tokens: Iterable[str]) -> dict:
    values = list(tokens)
    events = event_tokens(values)
    lexical = lexical_tokens(values)
    return {
        "total_token_count": len(values),
        "lexical_word_count": len(lexical),
        "event_token_count": len(events),
        "event_tokens": events,
        "tokens": values,
    }


def normalize_word_entries(entries: Iterable[dict]) -> list[dict]:
    normalized = []
    for index, entry in enumerate(entries):
        original = str(entry.get("word", ""))
        values = tokenize(original)
        if not values:
            continue
        start = entry.get("start")
        end = entry.get("end")
        for token in values:
            normalized.append(
                {
                    "index": index,
                    "token": token,
                    "original": original,
                    "start": float(start) if start is not None else None,
                    "end": float(end) if end is not None else None,
                }
            )
    return normalized


def _last_row(reference: list[str], candidate: list[str]) -> list[int]:
    previous = list(range(len(candidate) + 1))
    for reference_token in reference:
        current = [previous[0] + 1]
        for column, candidate_token in enumerate(candidate, start=1):
            substitution = previous[column - 1] + (reference_token != candidate_token)
            deletion = previous[column] + 1
            insertion = current[column - 1] + 1
            current.append(min(substitution, deletion, insertion))
        previous = current
    return previous


def _small_alignment(reference: list[str], candidate: list[str]) -> list[tuple[str, int | None, int | None]]:
    rows = len(reference) + 1
    columns = len(candidate) + 1
    costs = [[0] * columns for _ in range(rows)]
    for row in range(1, rows):
        costs[row][0] = row
    for column in range(1, columns):
        costs[0][column] = column
    for row in range(1, rows):
        for column in range(1, columns):
            substitution = costs[row - 1][column - 1] + (
                reference[row - 1] != candidate[column - 1]
            )
            deletion = costs[row - 1][column] + 1
            insertion = costs[row][column - 1] + 1
            costs[row][column] = min(substitution, deletion, insertion)
    alignment = []
    row = len(reference)
    column = len(candidate)
    while row or column:
        if row and column and costs[row][column] == costs[row - 1][column - 1] + (
            reference[row - 1] != candidate[column - 1]
        ):
            operation = "equal" if reference[row - 1] == candidate[column - 1] else "substitute"
            alignment.append((operation, row - 1, column - 1))
            row -= 1
            column -= 1
        elif row and costs[row][column] == costs[row - 1][column] + 1:
            alignment.append(("delete", row - 1, None))
            row -= 1
        else:
            alignment.append(("insert", None, column - 1))
            column -= 1
    alignment.reverse()
    return alignment


def _shift_alignment(
    alignment: Iterable[tuple[str, int | None, int | None]],
    reference_offset: int,
    candidate_offset: int,
) -> list[tuple[str, int | None, int | None]]:
    shifted = []
    for operation, reference_index, candidate_index in alignment:
        shifted.append(
            (
                operation,
                reference_index + reference_offset if reference_index is not None else None,
                candidate_index + candidate_offset if candidate_index is not None else None,
            )
        )
    return shifted


def _align_tokens(
    reference: list[str],
    candidate: list[str],
    reference_offset: int,
    candidate_offset: int,
) -> list[tuple[str, int | None, int | None]]:
    if not reference:
        return [
            ("insert", None, candidate_offset + index)
            for index in range(len(candidate))
        ]
    if not candidate:
        return [
            ("delete", reference_offset + index, None)
            for index in range(len(reference))
        ]
    if len(reference) <= 1 or len(candidate) <= 1:
        return _shift_alignment(
            _small_alignment(reference, candidate),
            reference_offset,
            candidate_offset,
        )
    midpoint = len(reference) // 2
    left = _last_row(reference[:midpoint], candidate)
    right = _last_row(reference[midpoint:][::-1], candidate[::-1])
    split = min(
        range(len(candidate) + 1),
        key=lambda index: left[index] + right[len(candidate) - index],
    )
    return _align_tokens(
        reference[:midpoint],
        candidate[:split],
        reference_offset,
        candidate_offset,
    ) + _align_tokens(
        reference[midpoint:],
        candidate[split:],
        reference_offset + midpoint,
        candidate_offset + split,
    )


def align_tokens(reference: list[str], candidate: list[str]) -> list[tuple[str, int | None, int | None]]:
    return _align_tokens(reference, candidate, 0, 0)


def alignment_summary(
    alignment: Iterable[tuple[str, int | None, int | None]],
    reference: list[str],
    candidate: list[str],
) -> dict:
    operations = list(alignment)
    counts = {"equal": 0, "substitute": 0, "delete": 0, "insert": 0}
    differences = []
    for operation, reference_index, candidate_index in operations:
        counts[operation] += 1
        if operation != "equal" and len(differences) < 200:
            differences.append(
                {
                    "operation": operation,
                    "reference_index": reference_index,
                    "reference_token": reference[reference_index] if reference_index is not None else None,
                    "candidate_index": candidate_index,
                    "candidate_token": candidate[candidate_index] if candidate_index is not None else None,
                }
            )
    reference_count = len(reference)
    errors = counts["substitute"] + counts["delete"] + counts["insert"]
    return {
        "reference_token_count": reference_count,
        "candidate_token_count": len(candidate),
        "matched_token_count": counts["equal"],
        "substitution_count": counts["substitute"],
        "deletion_count": counts["delete"],
        "insertion_count": counts["insert"],
        "edit_error_count": errors,
        "wer": errors / reference_count if reference_count else None,
        "candidate_minus_reference": len(candidate) - reference_count,
        "candidate_to_reference_ratio": len(candidate) / reference_count if reference_count else None,
        "differences_first_200": differences,
    }
