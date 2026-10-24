from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any


DUBBING_READY_CONTRACT_VERSION = 1
RAW_RESULT_ARTIFACT_NAME = "crisperwhisper_turbo_ct2_raw.json"
DUBBING_READY_RESULT_ARTIFACT_NAME = "crisperwhisper_turbo_ct2_dubbing_ready.json"
ACOUSTIC_EVENT_LABELS = (
    "[laughter]",
    "[sniff]",
    "[throatclearing]",
    "[cough]",
    "[sigh]",
    "[breath]",
    "[lipsmack]",
    "[yawn]",
    "[noise]",
    "[crying]",
    "[fart]",
    "[scream]",
    "[sneeze]",
)
FILLER_NORMALIZATION = {
    "[UM]": "um",
    "[UH]": "uh",
}
UNKNOWN_BRACKET_PATTERN = re.compile(r"\[[^\[\]\r\n]+\]")
NO_SPACE_LANGUAGE_CODES = frozenset({"ja", "lo", "my", "th", "yue", "zh"})


def load_acoustic_event_contract(model_snapshot: Path) -> dict[str, Any]:
    added_tokens_path = model_snapshot / "added_tokens.json"
    token_values = json.loads(added_tokens_path.read_text(encoding="utf-8"))
    if not isinstance(token_values, dict):
        raise RuntimeError("CrisperWhisper added_tokens.json must be an object")
    missing = [label for label in ACOUSTIC_EVENT_LABELS if label not in token_values]
    missing_fillers = [label for label in FILLER_NORMALIZATION if label not in token_values]
    if missing or missing_fillers:
        raise RuntimeError(
            "CrisperWhisper tokenizer dubbing contract is incomplete: "
            f"acoustic={missing}, fillers={missing_fillers}"
        )
    acoustic_token_ids = {
        label: int(token_values[label])
        for label in ACOUSTIC_EVENT_LABELS
    }
    filler_token_ids = {
        label: int(token_values[label])
        for label in FILLER_NORMALIZATION
    }
    identity_payload = {
        "contract_version": DUBBING_READY_CONTRACT_VERSION,
        "acoustic_token_ids": acoustic_token_ids,
        "filler_token_ids": filler_token_ids,
        "filler_normalization": FILLER_NORMALIZATION,
        "unknown_bracket_policy": "preserve_and_report",
    }
    identity = hashlib.sha256(
        json.dumps(
            identity_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        **identity_payload,
        "tokenizer_contract_sha256": identity,
        "added_tokens_path": str(added_tokens_path),
    }


def _contains_spoken_content(value: str) -> bool:
    return any(character.isalnum() for character in value)


def join_timed_word_text(words: list[dict[str, Any]], default_language: str) -> str:
    values = []
    previous_language = ""
    normalized_default = str(default_language or "").strip().lower()
    for word in words:
        value = str(word.get("word") or "").strip()
        if not value:
            continue
        language = str(word.get("detected_language") or normalized_default).strip().lower()
        if values:
            separator = (
                ""
                if language == previous_language and language in NO_SPACE_LANGUAGE_CODES
                else " "
            )
            values.append(separator)
        values.append(value)
        previous_language = language
    return "".join(values).strip()


def _transform_word(
    source_word: dict[str, Any],
    source_position: int,
    acoustic_labels: tuple[str, ...],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    word = copy.deepcopy(source_word)
    original_text = str(word.get("word") or "")
    transformed_text = original_text
    removed_events: list[dict[str, Any]] = []
    normalized_fillers: list[dict[str, Any]] = []
    source_index = int(source_word.get("index", source_position))
    for label in acoustic_labels:
        occurrence_count = transformed_text.count(label)
        for _ in range(occurrence_count):
            removed_events.append({
                "label": label,
                "start": float(source_word.get("start", 0.0)),
                "end": float(source_word.get("end", 0.0)),
                "source_index": source_index,
                "source_word": original_text,
            })
        transformed_text = transformed_text.replace(label, "")
    for label, replacement in FILLER_NORMALIZATION.items():
        occurrence_count = transformed_text.count(label)
        for _ in range(occurrence_count):
            normalized_fillers.append({
                "label": label,
                "replacement": replacement,
                "start": float(source_word.get("start", 0.0)),
                "end": float(source_word.get("end", 0.0)),
                "source_index": source_index,
            })
        transformed_text = transformed_text.replace(label, replacement)
    transformed_text = transformed_text.strip()
    unknown_brackets = UNKNOWN_BRACKET_PATTERN.findall(transformed_text)
    if removed_events and not _contains_spoken_content(transformed_text):
        return None, removed_events, normalized_fillers, unknown_brackets
    if not transformed_text:
        return None, removed_events, normalized_fillers, unknown_brackets
    word["word"] = transformed_text
    return word, removed_events, normalized_fillers, unknown_brackets


def build_dubbing_ready_result(
    raw_result: dict[str, Any],
    tokenizer_contract: dict[str, Any],
) -> dict[str, Any]:
    source_words = list(raw_result.get("words") or [])
    if not source_words:
        raise RuntimeError("CrisperWhisper raw result has no timed words")
    acoustic_labels = tuple(str(value) for value in tokenizer_contract["acoustic_token_ids"])
    clean_words: list[dict[str, Any]] = []
    removed_events: list[dict[str, Any]] = []
    normalized_fillers: list[dict[str, Any]] = []
    unknown_brackets: list[dict[str, Any]] = []
    for source_position, source_word in enumerate(source_words):
        clean_word, word_events, word_fillers, word_unknown = _transform_word(
            dict(source_word),
            source_position,
            acoustic_labels,
        )
        removed_events.extend(word_events)
        normalized_fillers.extend(word_fillers)
        source_index = int(source_word.get("index", source_position))
        for label in word_unknown:
            unknown_brackets.append({
                "label": label,
                "start": float(source_word.get("start", 0.0)),
                "end": float(source_word.get("end", 0.0)),
                "source_index": source_index,
                "source_word": str(source_word.get("word") or ""),
            })
        if clean_word is None:
            continue
        clean_word["index"] = len(clean_words)
        clean_words.append(clean_word)
    if not clean_words:
        raise RuntimeError("CrisperWhisper dubbing-ready result has no spoken words")

    detected_language = str(raw_result.get("language") or "").strip().lower()
    clean_text = join_timed_word_text(clean_words, detected_language)
    clean_segments = [{
        "index": 0,
        "start": float(clean_words[0]["start"]),
        "end": float(clean_words[-1]["end"]),
        "text": clean_text,
        "words": clean_words,
    }]

    diagnostics = {
        "contract_version": DUBBING_READY_CONTRACT_VERSION,
        "tokenizer_contract_sha256": tokenizer_contract["tokenizer_contract_sha256"],
        "acoustic_event_labels": list(acoustic_labels),
        "removed_acoustic_event_count": len(removed_events),
        "removed_acoustic_events": removed_events,
        "normalized_filler_count": len(normalized_fillers),
        "normalized_fillers": normalized_fillers,
        "unknown_bracket_count": len(unknown_brackets),
        "unknown_brackets": unknown_brackets,
        "unknown_bracket_policy": "preserve_and_report",
        "raw_word_count": len(source_words),
        "dubbing_ready_word_count": len(clean_words),
    }
    result = copy.deepcopy(raw_result)
    result["text"] = clean_text
    result["words"] = clean_words
    result["segments"] = clean_segments
    result["total_words"] = len(clean_words)
    result["total_segments"] = len(clean_segments)
    result["dubbing_ready"] = diagnostics
    profile_summary = dict(result.get("profile_summary") or {})
    profile_summary["dubbing_ready"] = {
        key: diagnostics[key]
        for key in (
            "contract_version",
            "tokenizer_contract_sha256",
            "removed_acoustic_event_count",
            "normalized_filler_count",
            "unknown_bracket_count",
            "unknown_bracket_policy",
            "raw_word_count",
            "dubbing_ready_word_count",
        )
    }
    result["profile_summary"] = profile_summary
    return result
