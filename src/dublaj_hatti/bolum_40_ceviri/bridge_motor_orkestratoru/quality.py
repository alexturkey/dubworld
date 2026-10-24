# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Iterable


SOURCE_LIKE_SIMILARITY_THRESHOLD = 0.90
PROTECTED_IDENTITY_MAX_WORDS = 3
PROTECTED_IDENTITY_BLOCKLIST = {
    "no",
    "yes",
    "yeah",
    "yep",
    "nope",
    "ok",
    "okay",
    "alright",
    "fine",
}


@dataclass(frozen=True)
class SourceLikeMatch:
    text: str
    similarity: float


def source_similarity(source_text: str, returned_text: str) -> float:
    source = str(source_text or "").casefold().strip()
    returned = str(returned_text or "").casefold().strip()
    if not source or not returned:
        return 0.0
    source_normalized = re.sub(r"[^\w\s]", " ", source)
    source_normalized = re.sub(r"\s+", " ", source_normalized).strip()
    returned_normalized = re.sub(r"[^\w\s]", " ", returned)
    returned_normalized = re.sub(r"\s+", " ", returned_normalized).strip()
    if source_normalized and source_normalized == returned_normalized:
        return 1.0
    return SequenceMatcher(None, source, returned).ratio()


def is_source_like_translation(
    source_text: str,
    returned_text: str,
    threshold: float = SOURCE_LIKE_SIMILARITY_THRESHOLD,
) -> bool:
    return source_similarity(source_text, returned_text) >= threshold


def normalize_identity_text(text: str) -> str:
    words = re.findall(r"\b[\w.-]+\b", str(text or ""), flags=re.UNICODE)
    return " ".join(word.strip(".-").casefold() for word in words if word.strip(".-"))


def is_single_word_source_segment(source_text: str) -> bool:
    source_value = str(source_text or "").strip()
    source_words = re.findall(r"\b[\w.-]+\b", source_value, flags=re.UNICODE)
    return len(source_words) == 1


def looks_like_protected_identity(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    words = re.findall(r"\b[\w.-]+\b", value, flags=re.UNICODE)
    if not words or len(words) > PROTECTED_IDENTITY_MAX_WORDS:
        return False
    normalized = " ".join(word.strip(".-").casefold() for word in words)
    if normalized in PROTECTED_IDENTITY_BLOCKLIST:
        return False
    if any(any(ch.isdigit() for ch in word) for word in words):
        return True
    if any("-" in word or "." in word for word in words):
        return True
    clean_words = [word.strip(".-") for word in words]
    if any(word.isupper() and len(word.strip(".-")) >= 2 for word in words):
        return True
    if any(any(ch.isupper() for ch in word[1:]) for word in words):
        return True
    return False


def is_protected_identity_translation(
    source_text: str,
    returned_text: str,
    protected_terms: Iterable[str] | None = None,
) -> bool:
    if source_similarity(source_text, returned_text) < 1.0:
        return False
    source_value = str(source_text or "").strip()
    if not source_value:
        return False
    normalized_source = normalize_identity_text(source_value)
    for term in protected_terms or []:
        normalized_term = normalize_identity_text(str(term or ""))
        if normalized_term and normalized_term == normalized_source:
            return True
    return looks_like_protected_identity(source_value)


def filter_source_like_translations(
    source_text: str,
    returned_texts: Iterable[str],
    threshold: float = SOURCE_LIKE_SIMILARITY_THRESHOLD,
) -> tuple[list[str], list[SourceLikeMatch]]:
    accepted: list[str] = []
    rejected: list[SourceLikeMatch] = []
    for item in returned_texts:
        text = str(item or "").strip()
        if not text:
            continue
        similarity = source_similarity(source_text, text)
        if similarity >= threshold:
            rejected.append(SourceLikeMatch(text=text, similarity=similarity))
        else:
            accepted.append(text)
    return accepted, rejected
