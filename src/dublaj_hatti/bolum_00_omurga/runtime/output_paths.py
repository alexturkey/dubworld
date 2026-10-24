# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "cikti"
# Yalnız uygulamaya özgü ad: genel "OUTPUT_DIR" başka araçların ortamından sızıp çıktıyı beklenmedik yere yazdırabilirdi.
OUTPUT_ENV_NAMES = ("DUBLAJ_OUTPUT_DIR",)


def _load_project_env() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(PROJECT_ROOT / ".env", encoding="utf-8-sig", override=False)


_load_project_env()


def configured_output_root(base_dir: str | Path | None = None) -> Path:
    raw_value = ""
    for name in OUTPUT_ENV_NAMES:
        value = os.environ.get(name, "").strip()
        if value:
            raw_value = value
            break
    root = Path(raw_value) if raw_value else DEFAULT_OUTPUT_ROOT
    if not root.is_absolute():
        anchor = Path(base_dir) if base_dir else PROJECT_ROOT
        root = anchor / root
    return root


def get_output_root(base_dir: str | Path | None = None, create: bool = True) -> Path:
    root = configured_output_root(base_dir).expanduser()
    drive = root.drive
    if drive and not Path(drive + "\\").exists():
        raise RuntimeError(f"Output diski bulunamadi: {drive}")
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root
