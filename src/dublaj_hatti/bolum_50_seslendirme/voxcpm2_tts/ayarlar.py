"""VoxCPM2 kurulum yollari ve sabit surum bilgisi."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]

# Kardes repo (README "Family"; kaynak kod bu repoya kopyalanmaz, bu adaptor onu ayri sanal ortamda calistirir).
# Adres yayinda doldurulur (yer tutucu), catal icin DUBLAJ_TTS_REPO_URL; kurulum betigi bu commit'i dogrular.
VOXCPM2_REPO_URL = os.environ.get("DUBLAJ_TTS_REPO_URL", "").strip() or "https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi"
VOXCPM2_COMMIT = "93e8b426738905437e1b621c6b359630b59e292b"
VOXCPM2_ROOT_ENV = "DUBLAJ_VOXCPM2_ROOT"
VOXCPM2_PYTHON_ENV = "DUBLAJ_VOXCPM2_PYTHON"
VOXCPM2_VARSAYILAN_SES = "hazir/haber_spikeri"
VOXCPM2_ADIM = 16  # bilgi amacli; kalite ayari kardes repoda sabittir
VOXCPM2_CFG = 2.0
VOXCPM2_ORNEKLEME = 48000


def voxcpm2_kok() -> Path:
    configured = os.environ.get(VOXCPM2_ROOT_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return PROJECT_ROOT / "runtime_assets" / "tts_motorlari" / "voxcpm2" / "repo"


def voxcpm2_python() -> Path:
    configured = os.environ.get(VOXCPM2_PYTHON_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    kok = voxcpm2_kok()
    windows = kok / ".venv" / "Scripts" / "python.exe"
    return windows if windows.exists() or os.name == "nt" else kok / ".venv" / "bin" / "python"
