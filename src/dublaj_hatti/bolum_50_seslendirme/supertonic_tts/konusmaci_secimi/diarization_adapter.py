# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Iterable


DIARIZATION_TIMEOUT_SECONDS = 3600
audio_only_min_cluster_size = 0
audio_only_merge_cos = 0.8
audio_only_ahc_rescue_threshold = 0.2


def default_worker_script() -> Path:
    return Path(__file__).resolve().parent / "diarization_worker.py"


def default_vendor_script() -> Path:
    box_root = Path(__file__).resolve().parent
    return box_root / "vendor" / "3D-Speaker" / "speakerlab" / "bin" / "infer_diarization.py"


def run_3d_speaker_diarization(audio_path: Path, work_dir: Path, vendor_script: Path | None = None) -> list[dict]:
    vendor_script_path = vendor_script or default_vendor_script()
    worker_script_path = default_worker_script()
    if not vendor_script_path.exists():
        raise FileNotFoundError(f"3D-Speaker vendor script not found: {vendor_script_path}")
    if not worker_script_path.exists():
        raise FileNotFoundError(f"3D-Speaker worker script not found: {worker_script_path}")
    work_dir.mkdir(parents=True, exist_ok=True)
    output_dir = work_dir / "raw_3d_speaker"
    output_dir.mkdir(parents=True, exist_ok=True)
    model_diagnostic_path = work_dir / "3d_speaker_model_diagnostic.json"
    failure_path = work_dir / "3d_speaker_failure.json"
    progress_path = work_dir / "3d_speaker_progress.jsonl"
    command = [
        sys.executable,
        str(worker_script_path),
        "--wav",
        str(audio_path),
        "--out_dir",
        str(output_dir),
        "--vendor_script",
        str(vendor_script_path),
        "--min_cluster_size",
        str(audio_only_min_cluster_size),
        "--merge_cos",
        str(audio_only_merge_cos),
        "--ahc_rescue_threshold",
        str(audio_only_ahc_rescue_threshold),
        "--model_diagnostic_path",
        str(model_diagnostic_path),
        "--failure_path",
        str(failure_path),
        "--progress_path",
        str(progress_path),
    ]
    subprocess_started_monotonic = perf_counter()
    subprocess_started_at_utc = datetime.now(timezone.utc).isoformat()
    worker_environment = dict(os.environ)
    worker_environment["DUBLAJ_3D_SPEAKER_SUBPROCESS_STARTED_MONOTONIC"] = str(
        subprocess_started_monotonic
    )
    try:
        result = subprocess.run(
            command,
            cwd=str(Path(__file__).resolve().parents[5]),
            env=worker_environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=DIARIZATION_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        (work_dir / "3d_speaker_stdout.txt").write_text(_safe_text(exc.stdout), encoding="utf-8")
        (work_dir / "3d_speaker_stderr.txt").write_text(_safe_text(exc.stderr), encoding="utf-8")
        raise RuntimeError(f"3D-Speaker timeout after {DIARIZATION_TIMEOUT_SECONDS} seconds") from exc
    (work_dir / "3d_speaker_command.json").write_text(
        json.dumps(
            {
                "command": command,
                "cwd": str(Path(__file__).resolve().parents[5]),
                "returncode": result.returncode,
                "subprocess_started_at_utc": subprocess_started_at_utc,
                "subprocess_elapsed_seconds": round(perf_counter() - subprocess_started_monotonic, 6),
                "model_diagnostic_path": str(model_diagnostic_path),
                "failure_path": str(failure_path),
                "progress_path": str(progress_path),
                "policy": {
                    "input_mode": "audio_only",
                    "speaker_count_mode": "automatic",
                    "min_cluster_size": audio_only_min_cluster_size,
                    "merge_cos": audio_only_merge_cos,
                    "ahc_rescue_threshold": audio_only_ahc_rescue_threshold,
                    "clustering_strategy": "spectral_then_ahc_if_single",
                    "overlap_enabled": False,
                    "video_analysis_enabled": False,
                    "worker_call_count": 1,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (work_dir / "3d_speaker_stdout.txt").write_text(result.stdout or "", encoding="utf-8")
    (work_dir / "3d_speaker_stderr.txt").write_text(result.stderr or "", encoding="utf-8")
    if result.returncode != 0:
        failure = _load_failure_report(failure_path)
        if failure:
            category = str(failure.get("category") or "worker_failed")
            message = str(failure.get("message") or "no failure message")
            raise RuntimeError(
                f"3D-Speaker failed: category={category}; {message}; "
                f"details={failure_path}"
            )
        stderr_tail = _last_nonempty_line(result.stderr or "")
        detail = f"; stderr={stderr_tail}" if stderr_tail else ""
        raise RuntimeError(
            f"3D-Speaker failed: category=worker_failed; returncode={result.returncode}{detail}; "
            f"details={work_dir / '3d_speaker_stderr.txt'}"
        )
    runtime_report = _extract_worker_runtime(result.stdout or "")
    if runtime_report:
        (work_dir / "3d_speaker_runtime.json").write_text(
            json.dumps(runtime_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    raw_segments = _load_raw_segments(output_dir)
    return normalize_speaker_timeline(raw_segments)


def _extract_worker_runtime(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "clustering_strategy_used" in value:
            return value
    return {}


def _safe_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _load_failure_report(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _last_nonempty_line(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def normalize_speaker_timeline(raw_segments: Iterable[dict]) -> list[dict]:
    sorted_segments = sorted(
        [
            {
                "start": float(item["start"]),
                "end": float(item["end"]),
                "speaker": str(item["speaker"]),
            }
            for item in raw_segments
            if "start" in item and "end" in item and "speaker" in item
        ],
        key=lambda item: (item["start"], item["end"]),
    )
    if not sorted_segments:
        raise RuntimeError("3D-Speaker returned no speaker segments")
    speaker_map: dict[str, str] = {}
    normalized = []
    for item in sorted_segments:
        raw_speaker = item["speaker"]
        if raw_speaker not in speaker_map:
            speaker_map[raw_speaker] = f"SPEAKER_{len(speaker_map):02d}"
        normalized.append(
            {
                "start": round(float(item["start"]), 3),
                "end": round(float(item["end"]), 3),
                "speaker": speaker_map[raw_speaker],
                "raw_speaker": raw_speaker,
            }
        )
    return normalized


def _load_raw_segments(output_dir: Path) -> list[dict]:
    json_files = sorted(output_dir.rglob("*.json"))
    for json_path in json_files:
        try:
            data = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        segments = _extract_segments_from_json(data)
        if segments:
            return segments
    rttm_files = sorted(output_dir.rglob("*.rttm"))
    for rttm_path in rttm_files:
        segments = _parse_rttm(rttm_path)
        if segments:
            return segments
    return []


def _extract_segments_from_json(data) -> list[dict]:
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = []
        for key in ["segments", "diarization", "data", "result"]:
            value = data.get(key)
            if isinstance(value, list):
                items = value
                break
        if not items:
            items = [value for value in data.values() if isinstance(value, dict)]
    else:
        items = []
    segments = []
    for item in items:
        if not isinstance(item, dict):
            continue
        start = item.get("start", item.get("begin", item.get("start_time")))
        end = item.get("end", item.get("stop", item.get("end_time")))
        speaker = item.get("speaker", item.get("label", item.get("spk", item.get("speaker_id"))))
        if start is None or end is None or speaker is None:
            continue
        segments.append({"start": float(start), "end": float(end), "speaker": str(speaker)})
    return segments


def _parse_rttm(path: Path) -> list[dict]:
    segments = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 8 or parts[0] != "SPEAKER":
            continue
        start = float(parts[3])
        duration = float(parts[4])
        speaker = parts[7]
        segments.append({"start": start, "end": start + duration, "speaker": speaker})
    return segments
