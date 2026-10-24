from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import huggingface_home
from dublaj_hatti.bolum_00_omurga.runtime.whisperx_runtime import build_whisperx_subprocess_env, resolve_whisperx_python

DEBUG_DIR_NAME = "final_dub_alignment"


def align_final_dub_audio(
    audio_path: str,
    segments: list,
    language: str,
    run_dir: str,
    device: str = "auto",
) -> dict[str, Any]:
    debug_dir = Path(run_dir) / DEBUG_DIR_NAME
    debug_dir.mkdir(parents=True, exist_ok=True)
    job_segments = []
    for segment in segments:
        text = str(getattr(segment, "text", "") or "").strip()
        if not text:
            continue
        start = max(float(getattr(segment, "start", 0.0) or 0.0), 0.0)
        end = max(float(getattr(segment, "end", start) or start), start + 0.01)
        job_segments.append({
            "segment_index": int(getattr(segment, "index", 0) or 0),
            "start": start,
            "end": end,
            "text": text,
        })

    report = {
        "mode": "final_dub_audio_forced_alignment",
        "enabled": bool(job_segments),
        "audio_path": audio_path,
        "segment_count": len(job_segments),
        "word_count": 0,
        "failed": False,
    }
    report_path = debug_dir / "alignment_report.json"
    if not job_segments:
        report["failed"] = True
        report["error"] = "no_segments_to_align"
        _write_json(report_path, report)
        return report
    if not audio_path or not os.path.exists(audio_path):
        report["failed"] = True
        report["error"] = "audio_path_missing"
        _write_json(report_path, report)
        return report

    job_path = debug_dir / "alignment_job.json"
    output_path = debug_dir / "alignment_result.json"
    cache_dir = str(huggingface_home())
    job = {
        "language": str(language or "tr").strip().lower()[:2] or "tr",
        "device": str(device or "auto").strip().lower(),
        "cache_dir": cache_dir,
        "audio_path": audio_path,
        "segments": job_segments,
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
            return report
        result = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        report["failed"] = True
        report["error"] = str(exc)
        _write_json(report_path, report)
        return report

    report["worker_success"] = bool(result.get("success"))
    report["language"] = result.get("language", job["language"])
    report["device"] = result.get("device", job["device"])
    report["custom_align_model"] = result.get("custom_align_model", "")
    report["word_count"] = int(result.get("word_count", 0) or 0)
    report["segments"] = list(result.get("segments", []) or [])
    if not result.get("success"):
        report["failed"] = True
        report["error"] = result.get("error", "worker_failed")
        report["traceback"] = result.get("traceback", "")
    else:
        expected_segment_indexes = {int(item["segment_index"]) for item in job_segments}
        aligned_segment_indexes = {
            int(item.get("segment_index", -1))
            for item in report["segments"]
            if bool(item.get("success")) and int(item.get("word_count", 0) or 0) > 0
        }
        missing_segment_indexes = sorted(expected_segment_indexes - aligned_segment_indexes)
        report["missing_segment_indexes"] = missing_segment_indexes
        if missing_segment_indexes:
            report["failed"] = True
            report["error"] = "alignment_segments_missing: " + ",".join(
                str(segment_index) for segment_index in missing_segment_indexes
            )
    _write_json(report_path, report)
    return report


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
