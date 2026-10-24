from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def transcribe_audio(
    audio_path: str,
    language: str = "en",
    run_dir: str | None = None,
    cache_dir: str = "",
    alignment_device: str = "cuda",
    use_diarization: bool = False,
) -> dict[str, Any]:
    if use_diarization:
        raise ValueError("parakeet_cpu_align does not support diarization")
    audio = Path(audio_path).expanduser().resolve()
    if not audio.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio}")
    actual_run_dir = Path(run_dir).expanduser().resolve() if run_dir else audio.parent
    actual_run_dir.mkdir(parents=True, exist_ok=True)
    worker_path = Path(__file__).resolve().parent / "worker.py"
    command = [
        sys.executable,
        str(worker_path),
        "--audio_path",
        str(audio),
        "--run_dir",
        str(actual_run_dir),
        "--language",
        language or "en",
        "--cache_dir",
        cache_dir or "",
        "--alignment_device",
        alignment_device or "cuda",
    ]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=2400,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"parakeet_cpu_align output parse failed: {exc}") from exc
    if result.returncode != 0 or not data.get("success"):
        raise RuntimeError(data.get("error") or f"parakeet_cpu_align failed with code {result.returncode}")
    return data
