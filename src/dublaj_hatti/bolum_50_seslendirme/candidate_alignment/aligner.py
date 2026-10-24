from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import huggingface_home
from dublaj_hatti.bolum_00_omurga.runtime.whisperx_runtime import build_whisperx_subprocess_env, resolve_whisperx_python

DEBUG_DIR_NAME = "candidate_alignment"
CANDIDATE_ALIGNMENT_SOURCE = "candidate_audio_forced_alignment"
CANDIDATE_ALIGNMENT_TIME_MAPPING = "candidate_audio_local_forced_alignment"
PRE_GAP_SECONDS = 0.35
POST_GAP_SECONDS = 0.35
CUT_START_BUFFER_SECONDS = 0.05
CUT_END_BUFFER_SECONDS = 0.08
# Neden: olculen tasma ilk kelimede 0.1-0.3 ms, son kelimede ~20 ms; daha gevsek tolerans pencere kaymasini gizler. bkz. docs/engineering/pinned-values.md#duration-matching
ALIGNMENT_START_BOUNDARY_TOLERANCE_SECONDS = 0.005
ALIGNMENT_END_BOUNDARY_TOLERANCE_SECONDS = 0.025
ALIGNMENT_BOUNDARY_POLICY = "physical_window_v1"


def align_candidate_audio_batch(
    audio_by_key: dict,
    candidate_records: list[dict],
    language: str,
    run_dir: str,
    sample_rate: int,
    round_label: str,
    debug_dir_name: str = DEBUG_DIR_NAME,
    model_name: str = "large-v3-turbo",
    compute_type: str = "float32",
) -> dict[str, Any]:
    validated_debug_dir_name = _validate_debug_dir_name(debug_dir_name)
    debug_dir = Path(run_dir) / "real_tts_candidate_selection" / round_label / validated_debug_dir_name
    debug_dir.mkdir(parents=True, exist_ok=True)
    batch_items = _collect_batch_items(audio_by_key, candidate_records, sample_rate)
    report_path = debug_dir / "alignment_report.json"
    if not batch_items:
        report = {
            "mode": "candidate_audio_forced_alignment",
            "round": round_label,
            "enabled": False,
            "candidate_count": 0,
            "failed": False,
            "error": "",
        }
        _write_json(report_path, report)
        return report

    batch_audio_path = debug_dir / "candidate_batch.wav"
    batch_segments = _write_batch_audio(batch_audio_path, batch_items, sample_rate)
    job_path = debug_dir / "alignment_job.json"
    output_path = debug_dir / "alignment_result.json"
    cache_dir = str(huggingface_home())
    job = {
        "language": str(language or "tr").strip().lower()[:2] or "tr",
        "device": "auto",
        "cache_dir": cache_dir,
        "audio_path": str(batch_audio_path),
        "segments": batch_segments,
        "model_name": str(model_name or "large-v3-turbo"),
        "compute_type": str(compute_type or "float32"),
    }
    _write_json(job_path, job)
    worker_path = Path(__file__).with_name("worker.py")
    cmd = [
        str(resolve_whisperx_python()),
        str(worker_path),
        "--job",
        str(job_path),
        "--output",
        str(output_path),
    ]
    report = {
        "mode": "candidate_audio_forced_alignment",
        "round": round_label,
        "enabled": True,
        "candidate_count": len(batch_items),
        "word_count": 0,
        "failed": False,
    }
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            env=build_whisperx_subprocess_env(cache_dir),
        )
        report["worker_returncode"] = completed.returncode
        report["worker_stdout"] = completed.stdout[-4000:]
        report["worker_stderr"] = completed.stderr[-4000:]
        if not output_path.exists():
            report["failed"] = True
            report["error"] = "worker_output_missing"
            _write_json(report_path, report)
            raise RuntimeError("Aday alignment worker cikti dosyasi uretmedi")
        result = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        report["failed"] = True
        report["error"] = str(exc)
        _write_json(report_path, report)
        raise

    report["worker_success"] = bool(result.get("success"))
    report["language"] = result.get("language", job["language"])
    report["device"] = result.get("device", job["device"])
    report["model_name"] = result.get("model_name", job["model_name"])
    report["compute_type"] = result.get("compute_type", job["compute_type"])
    report["custom_align_model"] = result.get("custom_align_model", "")
    report["word_count"] = int(result.get("word_count", 0) or 0)
    if not result.get("success"):
        report["failed"] = True
        report["error"] = result.get("error", "worker_failed")
        report["traceback"] = result.get("traceback", "")
        _write_json(report_path, report)
        raise RuntimeError(f"Aday alignment basarisiz: {report['error']}")

    try:
        application_report = apply_candidate_alignment_result(
            audio_by_key,
            batch_items,
            result,
            sample_rate,
        )
    except Exception as exc:
        report["failed"] = True
        report["error"] = str(exc)
        _write_json(report_path, report)
        raise
    report.update(application_report)
    _write_json(report_path, report)
    return report


def apply_candidate_alignment_result(
    audio_by_key: dict,
    batch_items: list[dict],
    result: dict,
    sample_rate: int,
) -> dict[str, Any]:
    words_by_alignment_id: dict[int, list[dict]] = {}
    for word in result.get("words", []) or []:
        alignment_id = int(word.get("segment_index", 0) or 0)
        if alignment_id <= 0:
            continue
        words_by_alignment_id.setdefault(alignment_id, []).append(word)

    applied = []
    for item in batch_items:
        alignment_ids = [int(value) for value in item.get("alignment_ids", []) or [item["alignment_id"]]]
        alignment_id = alignment_ids[0]
        audio = audio_by_key[item["audio_key"]]
        words, boundary_adjustments = _normalize_alignment_words(
            words_by_alignment_id,
            item,
            alignment_ids,
        )
        audio_duration = len(audio.wav_array) / sample_rate if sample_rate else float(getattr(audio, "raw_duration", 0.0) or 0.0)
        local_words = _local_words(words, float(item["batch_start"]), audio_duration)
        first_start = min(float(word["start"]) for word in local_words)
        last_end = max(float(word["end"]) for word in local_words)
        preserve_physical_audio_bounds = bool(getattr(audio, "preserve_physical_audio_bounds", False))
        if preserve_physical_audio_bounds:
            cut_start = 0.0
            cut_end = audio_duration
        else:
            cut_start = max(first_start - CUT_START_BUFFER_SECONDS, 0.0)
            cut_end = min(last_end + CUT_END_BUFFER_SECONDS, audio_duration)
        if cut_end <= cut_start:
            raise RuntimeError(f"Aday alignment gecersiz kesim verdi: alignment_id={alignment_id}")
        start_sample = int(round(cut_start * sample_rate))
        end_sample = int(round(cut_end * sample_rate))
        end_sample = max(end_sample, start_sample + 1)
        cropped = np.asarray(audio.wav_array[start_sample:end_sample], dtype=np.float32)
        adjusted_words = _shift_words(local_words, cut_start, len(cropped) / sample_rate)
        chunk_timeline = _shift_chunk_timeline(getattr(audio, "chunk_timeline", []), cut_start, len(cropped) / sample_rate)
        audio.wav_array = cropped
        audio.raw_duration = len(cropped) / sample_rate
        setattr(audio, "processed_duration", len(cropped) / sample_rate)
        setattr(audio, "word_boundaries", adjusted_words)
        if chunk_timeline:
            setattr(audio, "chunk_timeline", chunk_timeline)
        setattr(audio, "word_timing_source", CANDIDATE_ALIGNMENT_SOURCE)
        setattr(audio, "candidate_alignment", {
            "success": True,
            "alignment_id": alignment_id,
            "alignment_ids": alignment_ids,
            "alignment_window_count": len(alignment_ids),
            "source": CANDIDATE_ALIGNMENT_SOURCE,
            "active_start_seconds": round(first_start, 6),
            "active_end_seconds": round(last_end, 6),
            "active_duration_seconds": round(last_end - first_start, 6),
            "cut_start_seconds": round(cut_start, 6),
            "cut_end_seconds": round(cut_end, 6),
            "cut_duration_seconds": round(len(cropped) / sample_rate, 6),
            "word_count": len(adjusted_words),
            "physical_audio_bounds_preserved": preserve_physical_audio_bounds,
            "boundary_policy": ALIGNMENT_BOUNDARY_POLICY,
            "boundary_adjustment_count": len(boundary_adjustments),
            "boundary_adjustments": boundary_adjustments,
        })
        applied.append({
            "alignment_id": alignment_id,
            "alignment_ids": alignment_ids,
            "alignment_window_count": len(alignment_ids),
            "segment_id": item["segment_id"],
            "candidate_number": item["candidate_number"],
            "word_count": len(adjusted_words),
            "active_start_seconds": round(first_start, 6),
            "active_end_seconds": round(last_end, 6),
            "active_duration_seconds": round(last_end - first_start, 6),
            "cut_start_seconds": round(cut_start, 6),
            "cut_end_seconds": round(cut_end, 6),
            "cut_duration_seconds": round(len(cropped) / sample_rate, 6),
            "physical_audio_bounds_preserved": preserve_physical_audio_bounds,
            "boundary_policy": ALIGNMENT_BOUNDARY_POLICY,
            "boundary_adjustment_count": len(boundary_adjustments),
            "boundary_adjustments": boundary_adjustments,
        })
    return {
        "aligned_candidate_count": len(applied),
        "boundary_policy": ALIGNMENT_BOUNDARY_POLICY,
        "boundary_adjustment_count": sum(item["boundary_adjustment_count"] for item in applied),
        "boundary_adjustment_max_ms": max(
            [
                adjustment["delta_ms"]
                for item in applied
                for adjustment in item["boundary_adjustments"]
            ]
            or [0.0]
        ),
        "candidates": applied,
    }


def _normalize_alignment_words(
    words_by_alignment_id: dict[int, list[dict]],
    item: dict,
    alignment_ids: list[int],
) -> tuple[list[dict], list[dict]]:
    window_ranges = _alignment_window_ranges(item, alignment_ids)
    normalized_words = []
    boundary_adjustments = []
    for alignment_id in alignment_ids:
        current_words = list(words_by_alignment_id.get(alignment_id, []) or [])
        if not current_words:
            raise RuntimeError(f"Aday alignment kelime bulamadi: alignment_id={alignment_id}")
        current_words.sort(key=lambda word: (float(word.get("start", 0.0) or 0.0), float(word.get("end", 0.0) or 0.0)))
        window_start, window_end = window_ranges[alignment_id]
        for word_index, source_word in enumerate(current_words):
            if "start" not in source_word or "end" not in source_word:
                raise RuntimeError(f"Aday alignment kelime zamani eksik: alignment_id={alignment_id}")
            word = dict(source_word)
            raw_start = float(word["start"])
            raw_end = float(word["end"])
            start = raw_start
            end = raw_end
            actions = []
            if start < window_start:
                delta_ms = (window_start - start) * 1000.0
                if delta_ms > ALIGNMENT_START_BOUNDARY_TOLERANCE_SECONDS * 1000.0:
                    raise RuntimeError(
                        f"Aday alignment kelime baslangici pencere disinda: alignment_id={alignment_id} word={word.get('word', '')} delta_ms={delta_ms:.3f}"
                    )
                start = window_start
                actions.append("start_clamped_rounding")
                boundary_adjustments.append({
                    "alignment_id": alignment_id,
                    "word": str(word.get("word") or ""),
                    "action": "start_clamped_rounding",
                    "delta_ms": round(delta_ms, 6),
                    "window_start": round(window_start, 6),
                    "window_end": round(window_end, 6),
                })
            if start >= window_end:
                raise RuntimeError(
                    f"Aday alignment kelime baslangici pencere sonrasinda: alignment_id={alignment_id} word={word.get('word', '')}"
                )
            if end > window_end:
                delta_ms = (end - window_end) * 1000.0
                if word_index != len(current_words) - 1 or delta_ms > ALIGNMENT_END_BOUNDARY_TOLERANCE_SECONDS * 1000.0:
                    raise RuntimeError(
                        f"Aday alignment kelime bitisi pencere disinda: alignment_id={alignment_id} word={word.get('word', '')} delta_ms={delta_ms:.3f}"
                    )
                end = window_end
                actions.append("end_clamped_frame")
                boundary_adjustments.append({
                    "alignment_id": alignment_id,
                    "word": str(word.get("word") or ""),
                    "action": "end_clamped_frame",
                    "delta_ms": round(delta_ms, 6),
                    "window_start": round(window_start, 6),
                    "window_end": round(window_end, 6),
                })
            if end <= start or end > window_end:
                raise RuntimeError(
                    f"Aday alignment kelime zamani fiziksel pencerede gecersiz: alignment_id={alignment_id} word={word.get('word', '')}"
                )
            word["start"] = round(start, 6)
            word["end"] = round(end, 6)
            word["alignment_raw_start"] = round(raw_start, 6)
            word["alignment_raw_end"] = round(raw_end, 6)
            word["alignment_window_start"] = round(window_start, 6)
            word["alignment_window_end"] = round(window_end, 6)
            word["boundary_action"] = "+".join(actions) if actions else "none"
            normalized_words.append(word)
    normalized_words.sort(key=lambda word: (float(word["start"]), float(word["end"])))
    return normalized_words, boundary_adjustments


def _alignment_window_ranges(item: dict, alignment_ids: list[int]) -> dict[int, tuple[float, float]]:
    batch_start = float(item["batch_start"])
    alignment_windows = list(item.get("alignment_windows", []) or [])
    if not alignment_windows:
        return {alignment_ids[0]: (batch_start, float(item["batch_end"]))}
    if len(alignment_windows) != len(alignment_ids):
        raise RuntimeError(f"Aday alignment pencere sayisi uyusmuyor: segment_id={item.get('segment_id', '')}")
    ranges = {}
    for alignment_id, window in zip(alignment_ids, alignment_windows):
        start = batch_start + max(float(window.get("start", 0.0) or 0.0), 0.0)
        end = batch_start + max(float(window.get("end", 0.0) or 0.0), 0.0)
        if end <= start:
            raise RuntimeError(f"Aday alignment penceresi gecersiz: alignment_id={alignment_id}")
        ranges[alignment_id] = (start, end)
    return ranges


def _collect_batch_items(audio_by_key: dict, candidate_records: list[dict], sample_rate: int) -> list[dict]:
    batch_items = []
    seen = set()
    for record in candidate_records:
        key = record.get("audio_key")
        audio = audio_by_key.get(key)
        if key is None or audio is None or getattr(audio, "wav_array", None) is None:
            continue
        if dict(getattr(audio, "candidate_alignment", {}) or {}).get("success"):
            continue
        if key in seen:
            continue
        seen.add(key)
        text = str(record.get("spoken_text") or record.get("display_text") or "").strip()
        if not text:
            continue
        duration = len(audio.wav_array) / sample_rate if sample_rate else float(getattr(audio, "raw_duration", 0.0) or 0.0)
        if duration <= 0:
            continue
        batch_items.append({
            "alignment_id": len(batch_items) + 1,
            "audio_key": key,
            "audio": audio,
            "segment_id": str(record.get("segment_id", "")),
            "segment_index": int(record.get("segment_index", 0) or 0),
            "candidate_number": int(record.get("candidate_number", 0) or 0),
            "text": text,
            "duration": duration,
            "alignment_windows": [dict(window) for window in record.get("alignment_windows", []) or []],
        })
    return batch_items


def _write_batch_audio(path: Path, batch_items: list[dict], sample_rate: int) -> list[dict]:
    parts = []
    segments = []
    cursor = 0.0
    pre_gap = np.zeros(int(round(PRE_GAP_SECONDS * sample_rate)), dtype=np.float32)
    post_gap = np.zeros(int(round(POST_GAP_SECONDS * sample_rate)), dtype=np.float32)
    for item in batch_items:
        parts.append(pre_gap)
        cursor += len(pre_gap) / sample_rate
        audio = np.asarray(item["audio"].wav_array, dtype=np.float32)
        if audio is None:
            raise RuntimeError("Aday batch audio hazirlanamadi")
        start = cursor
        parts.append(audio)
        cursor += len(audio) / sample_rate
        end = cursor
        parts.append(post_gap)
        cursor += len(post_gap) / sample_rate
        item["batch_start"] = start
        item["batch_end"] = end
        alignment_windows = list(item.get("alignment_windows", []) or [])
        alignment_ids = []
        if alignment_windows:
            audio_duration = len(audio) / sample_rate
            for window in alignment_windows:
                window_text = str(window.get("text") or "").strip()
                window_start = max(float(window.get("start", 0.0) or 0.0), 0.0)
                window_end = min(max(float(window.get("end", window_start) or window_start), window_start + 0.01), audio_duration)
                if not window_text or window_end <= window_start:
                    raise RuntimeError(f"Aday alignment penceresi gecersiz: segment_id={item['segment_id']}")
                alignment_id = len(segments) + 1
                alignment_ids.append(alignment_id)
                segments.append({
                    "segment_index": alignment_id,
                    "start": round(start + window_start, 6),
                    "end": round(start + window_end, 6),
                    "text": window_text,
                })
        else:
            alignment_id = len(segments) + 1
            alignment_ids.append(alignment_id)
            segments.append({
                "segment_index": alignment_id,
                "start": round(start, 6),
                "end": round(end, 6),
                "text": item["text"],
            })
        item["alignment_id"] = alignment_ids[0]
        item["alignment_ids"] = alignment_ids
    batch_audio = np.concatenate(parts).astype(np.float32, copy=False)
    sf.write(str(path), batch_audio, sample_rate, subtype="FLOAT" if np.max(np.abs(batch_audio), initial=0) >= 1 else "PCM_16")
    return segments


def _local_words(words: list[dict], batch_start: float, audio_duration: float) -> list[dict]:
    local = []
    for index, word in enumerate(words, start=1):
        text = str(word.get("word") or "").strip()
        if not text:
            continue
        start = max(float(word.get("start", 0.0) or 0.0) - batch_start, 0.0)
        end = max(float(word.get("end", start) or start) - batch_start, start + 0.01)
        start = min(start, max(audio_duration - 0.01, 0.0))
        end = min(max(end, start + 0.01), audio_duration)
        local_word = {
            "word": text,
            "start": round(start, 6),
            "end": round(end, 6),
            "raw_start": round(start, 6),
            "raw_end": round(end, 6),
            "word_index": index,
            "source": CANDIDATE_ALIGNMENT_SOURCE,
            "time_mapping": CANDIDATE_ALIGNMENT_TIME_MAPPING,
        }
        for key in (
            "alignment_raw_start",
            "alignment_raw_end",
            "alignment_window_start",
            "alignment_window_end",
            "boundary_action",
        ):
            if key in word:
                local_word[key] = word[key]
        local.append(local_word)
    return local


def _shift_words(words: list[dict], cut_start: float, duration: float) -> list[dict]:
    shifted = []
    for index, word in enumerate(words, start=1):
        start = max(float(word["start"]) - cut_start, 0.0)
        end = min(max(float(word["end"]) - cut_start, start + 0.01), duration)
        item = dict(word)
        item["word_index"] = index
        item["start"] = round(start, 6)
        item["end"] = round(end, 6)
        item["raw_start"] = round(start, 6)
        item["raw_end"] = round(end, 6)
        item["cut_start_seconds"] = round(cut_start, 6)
        shifted.append(item)
    return shifted


def _shift_chunk_timeline(chunks: list[dict], cut_start: float, duration: float) -> list[dict]:
    shifted = []
    for chunk in chunks:
        start = max(float(chunk.get("start", 0.0) or 0.0) - cut_start, 0.0)
        end = min(max(float(chunk.get("end", start) or start) - cut_start, start), duration)
        if end > start:
            shifted.append({**dict(chunk), "start": round(start, 6), "end": round(end, 6)})
    return shifted


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def _validate_debug_dir_name(debug_dir_name: str) -> str:
    if not isinstance(debug_dir_name, str):
        raise ValueError("Aday alignment debug klasor adi metin olmali")
    if not debug_dir_name or debug_dir_name != debug_dir_name.strip():
        raise ValueError("Aday alignment debug klasor adi bos veya kenar bosluklu olamaz")
    if debug_dir_name in {".", ".."}:
        raise ValueError("Aday alignment debug klasor adi tek guvenli bilesen olmali")
    if any(character in debug_dir_name for character in ("/", "\\", ":", "\x00")):
        raise ValueError("Aday alignment debug klasor adi tek guvenli bilesen olmali")
    if Path(debug_dir_name).is_absolute() or Path(debug_dir_name).name != debug_dir_name:
        raise ValueError("Aday alignment debug klasor adi tek guvenli bilesen olmali")
    if re.fullmatch(r"[A-Za-z0-9_](?:[A-Za-z0-9._-]*[A-Za-z0-9_-])?", debug_dir_name) is None:
        raise ValueError("Aday alignment debug klasor adi tek guvenli bilesen olmali")
    reserved_name = debug_dir_name.split(".", 1)[0].upper()
    if reserved_name in {"CON", "PRN", "AUX", "NUL"} or re.fullmatch(r"(?:COM|LPT)[1-9]", reserved_name):
        raise ValueError("Aday alignment debug klasor adi Windows aygit adi olamaz")
    return debug_dir_name
