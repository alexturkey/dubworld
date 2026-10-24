from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SUBTITLE_TIMING_CONTRACT_SCHEMA_VERSION = 1
# Segment TTS motorlarının hepsi (dubber.SEGMENT_TTS_ENGINES) aynı sözleşmeyi yazar ve okur; "edge" kaynak uyumu için kalır.
SUPPORTED_ENGINES = {"edge", "supertonic", "xtts", "voxcpm2"}


def write_subtitle_timing_contract(
    run_dir: str,
    language: str,
    engine: str,
    timing_source: str,
    timing_method: str,
    word_timeline_path: str,
    timing_report_path: str,
    verification_evidence_paths: list[str],
) -> str:
    run_path = Path(run_dir).resolve()
    engine_key = _normalize_engine(engine)
    lang = _normalize_language(language)
    timeline_path = _require_file_in_run(run_path, word_timeline_path, "word timeline")
    report_path = _require_file_in_run(run_path, timing_report_path, "timing report")
    evidence_paths = [
        _require_file_in_run(run_path, path, "verification evidence")
        for path in verification_evidence_paths
    ]
    if not evidence_paths:
        raise RuntimeError("Altyazi timing sozlesmesi dogrulama kaniti icermiyor")

    words = _read_json_list(timeline_path, "word timeline")
    report = _read_json_object(report_path, "timing report")
    _validate_words(words)
    if str(report.get("engine") or "").strip().lower() != engine_key:
        raise RuntimeError("Altyazi timing raporu motoru istekle uyusmuyor")
    if str(report.get("timing_source") or "") != str(timing_source):
        raise RuntimeError("Altyazi timing raporu kaynagi istekle uyusmuyor")
    if str(report.get("method") or "") != str(timing_method):
        raise RuntimeError("Altyazi timing raporu yontemi istekle uyusmuyor")
    if int(report.get("word_count") or 0) != len(words):
        raise RuntimeError("Altyazi timing raporu kelime sayisi timeline ile uyusmuyor")

    contract_dir = timeline_path.parent
    contract_path = contract_dir / "subtitle_timing_contract.json"
    payload = {
        "schema_version": SUBTITLE_TIMING_CONTRACT_SCHEMA_VERSION,
        "engine": engine_key,
        "language": lang,
        "timing_source": str(timing_source),
        "timing_method": str(timing_method),
        "word_count": len(words),
        "segment_count": int(report.get("segment_count") or 0),
        "word_timeline_path": _relative_path(run_path, timeline_path),
        "timing_report_path": _relative_path(run_path, report_path),
        "verification_evidence_paths": [_relative_path(run_path, path) for path in evidence_paths],
    }
    contract_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    load_subtitle_timing_contract(
        str(contract_path),
        run_dir=str(run_path),
        expected_engine=engine_key,
        expected_language=lang,
    )
    return str(contract_path)


def load_subtitle_timing_contract(
    contract_path: str,
    *,
    run_dir: str,
    expected_engine: str,
    expected_language: str,
) -> dict[str, Any]:
    if not str(contract_path or "").strip():
        raise RuntimeError("Altyazi timing sozlesmesi yolu zorunludur")
    run_path = Path(run_dir).resolve()
    resolved_contract_path = _require_file_in_run(run_path, contract_path, "timing contract")
    payload = _read_json_object(resolved_contract_path, "timing contract")
    if int(payload.get("schema_version") or 0) != SUBTITLE_TIMING_CONTRACT_SCHEMA_VERSION:
        raise RuntimeError("Desteklenmeyen altyazi timing sozlesmesi surumu")
    engine_key = _normalize_engine(expected_engine)
    lang = _normalize_language(expected_language)
    if str(payload.get("engine") or "").strip().lower() != engine_key:
        raise RuntimeError("Altyazi timing sozlesmesi motoru istekle uyusmuyor")
    if str(payload.get("language") or "").strip().lower() != lang:
        raise RuntimeError("Altyazi timing sozlesmesi dili istekle uyusmuyor")

    timeline_path = _require_relative_file(run_path, payload.get("word_timeline_path"), "word timeline")
    report_path = _require_relative_file(run_path, payload.get("timing_report_path"), "timing report")
    evidence_values = payload.get("verification_evidence_paths")
    if not isinstance(evidence_values, list) or not evidence_values:
        raise RuntimeError("Altyazi timing sozlesmesi dogrulama kaniti icermiyor")
    evidence_paths = [
        _require_relative_file(run_path, value, "verification evidence")
        for value in evidence_values
    ]
    words = _read_json_list(timeline_path, "word timeline")
    report = _read_json_object(report_path, "timing report")
    _validate_words(words)
    timing_source = str(payload.get("timing_source") or "")
    timing_method = str(payload.get("timing_method") or "")
    if not timing_source or not timing_method:
        raise RuntimeError("Altyazi timing sozlesmesi kaynak veya yontem icermiyor")
    if str(report.get("engine") or "").strip().lower() != engine_key:
        raise RuntimeError("Altyazi timing raporu motoru sozlesmeyle uyusmuyor")
    if str(report.get("timing_source") or "") != timing_source:
        raise RuntimeError("Altyazi timing raporu kaynagi sozlesmeyle uyusmuyor")
    if str(report.get("method") or "") != timing_method:
        raise RuntimeError("Altyazi timing raporu yontemi sozlesmeyle uyusmuyor")
    if int(payload.get("word_count") or 0) != len(words) or int(report.get("word_count") or 0) != len(words):
        raise RuntimeError("Altyazi timing kelime sayilari birbiriyle uyusmuyor")
    result = dict(payload)
    result.update({
        "contract_path": str(resolved_contract_path),
        "word_timeline_path": str(timeline_path),
        "timing_report_path": str(report_path),
        "verification_evidence_paths": [str(path) for path in evidence_paths],
    })
    return result


def _validate_words(words: list[dict[str, Any]]) -> None:
    if not words:
        raise RuntimeError("Altyazi word timeline bos")
    previous_start = -1.0
    for index, word in enumerate(words, start=1):
        if not isinstance(word, dict) or not str(word.get("word") or "").strip():
            raise RuntimeError(f"Altyazi word timeline gecersiz kelime kaydi: {index}")
        try:
            start = float(word["start"])
            end = float(word["end"])
            segment_index = int(word["segment_index"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Altyazi word timeline gecersiz zaman kaydi: {index}") from exc
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
            raise RuntimeError(f"Altyazi word timeline zaman araligi gecersiz: {index}")
        if segment_index <= 0 or start < previous_start:
            raise RuntimeError(f"Altyazi word timeline sirasi veya segmenti gecersiz: {index}")
        previous_start = start


def _normalize_engine(value: str) -> str:
    engine = str(value or "").strip().lower()
    if engine not in SUPPORTED_ENGINES:
        raise RuntimeError(f"Desteklenmeyen altyazi motoru: {engine}")
    return engine


def _normalize_language(value: str) -> str:
    language = str(value or "tr").strip().lower()[:2] or "tr"
    if not language.isalpha():
        raise RuntimeError("Gecersiz altyazi dili")
    return language


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} JSON nesnesi degil")
    return value


def _read_json_list(path: Path, label: str) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise RuntimeError(f"{label} JSON listesi degil")
    return value


def _require_relative_file(run_path: Path, value: Any, label: str) -> Path:
    path = Path(str(value or ""))
    if path.is_absolute() or not str(value or "").strip():
        raise RuntimeError(f"{label} yolu run_dir altinda goreli olmali")
    return _require_file_in_run(run_path, run_path / path, label)


def _require_file_in_run(run_path: Path, value: str | Path, label: str) -> Path:
    path = Path(value).resolve()
    try:
        path.relative_to(run_path)
    except ValueError as exc:
        raise RuntimeError(f"{label} run_dir disinda") from exc
    if not path.is_file():
        raise RuntimeError(f"{label} bulunamadi: {path}")
    return path


def _relative_path(run_path: Path, path: Path) -> str:
    return path.relative_to(run_path).as_posix()
