from __future__ import annotations

import os
import sys
from pathlib import Path

from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import build_model_cache_env


DEFAULT_WHISPERX_PYTHON = Path(sys.executable)
WHISPERX_PYTHON_ENV = "DUBLAJ_WHISPERX_PYTHON"
ALIGN_FAST_WILDCARD_ENV = "WHISPERX_ALIGN_FAST_WILDCARD"


def resolve_whisperx_python() -> Path:
    configured_path = os.environ.get(WHISPERX_PYTHON_ENV, "").strip()
    python_path = Path(configured_path).expanduser() if configured_path else DEFAULT_WHISPERX_PYTHON
    python_path = python_path.resolve()
    if not python_path.is_file():
        raise FileNotFoundError(
            f"WhisperX clean CTC Python bulunamadi: {python_path}. "
            f"{WHISPERX_PYTHON_ENV} ile farkli bir yol belirtilebilir."
        )
    return python_path


def build_whisperx_subprocess_env(cache_dir: str | Path | None = None) -> dict[str, str]:
    env = build_model_cache_env(cache_dir)
    env["PYTHONIOENCODING"] = "utf-8"
    env[ALIGN_FAST_WILDCARD_ENV] = "0"
    return env
