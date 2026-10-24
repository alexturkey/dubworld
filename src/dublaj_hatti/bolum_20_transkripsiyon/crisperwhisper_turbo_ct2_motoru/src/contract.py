from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


ENGINE_ID = "crisperwhisper_turbo_ct2"
MODEL_ID = "CrisperWhisper2.0_turbo"
REQUEST_SCHEMA_VERSION = 3
RESPONSE_SCHEMA_VERSION = 3
RUNTIME_CONTRACT_VERSION = "crisperwhisper_turbo_ct2_v6"


def read_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM is forbidden: {path}")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary.write_text(payload, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def require_request(value: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "engine": ENGINE_ID,
        "model": MODEL_ID,
        "full_duration_required": True,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise ValueError(
                f"Invalid request {key}: expected {expected_value!r}, got {value.get(key)!r}"
            )
    for key in ("audio_path", "output_dir", "audio_sha256"):
        if not isinstance(value.get(key), str) or not value[key]:
            raise ValueError(f"Request {key} must be a non-empty string")
    duration = float(value.get("audio_duration_seconds", 0.0))
    if duration <= 0.0:
        raise ValueError("Request audio_duration_seconds must be positive")
    if value.get("language_detection_mode") not in {
        "global_first_window",
        "continuous_stream",
    }:
        raise ValueError("Request language_detection_mode is invalid")
    platform_language = value.get("platform_language")
    if not isinstance(platform_language, str) or (
        platform_language and not re.fullmatch(r"[a-z]{2,3}", platform_language)
    ):
        raise ValueError("Request platform_language is invalid")
    expected_language = (
        platform_language
        if value["language_detection_mode"] == "global_first_window" and platform_language
        else "detected_by_ct2_language_id"
    )
    if value.get("language") != expected_language:
        raise ValueError(
            f"Invalid request language: expected {expected_language!r}, got {value.get('language')!r}"
        )
    return value


def validate_words(words: list[dict[str, Any]], duration_seconds: float) -> None:
    if not words:
        raise ValueError("The worker did not produce word timestamps")
    previous_start = -1.0
    previous_end = -1.0
    for index, word in enumerate(words):
        text = str(word.get("word", ""))
        start = float(word.get("start", -1.0))
        end = float(word.get("end", -1.0))
        if not text.strip():
            raise ValueError(f"Word {index} has empty text")
        if start < 0.0 or end < start:
            raise ValueError(f"Word {index} has an invalid interval: {start}..{end}")
        if start + 1e-6 < previous_start or end + 1e-6 < previous_end:
            raise ValueError(f"Word {index} is not chronological")
        if end > duration_seconds + 1.0:
            raise ValueError(f"Word {index} exceeds physical audio duration")
        previous_start = start
        previous_end = end
