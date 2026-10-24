"""Video kodlayıcı seçimi: NVIDIA NVENC kullanılabiliyorsa h264_nvenc, değilse işlemcide libx264.

NVENC; GPU yoksa, işlemci kipinde (CUDA_VISIBLE_DEVICES="") ya da sürücü ffmpeg'in istediği NVENC API
sürümünden eskiyse çalışmaz. Karar bir kez, 0,1 sn'lik boş bir deneme kodlamasıyla verilir ve günlüğe
gerekçesiyle yazılır. Elle seçim: DUBLAJ_VIDEO_KODLAYICI = auto | nvenc | x264.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from functools import lru_cache

logger = logging.getLogger(__name__)
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@lru_cache(maxsize=1)
def nvenc_kullanilabilir() -> bool:
    secim = os.environ.get("DUBLAJ_VIDEO_KODLAYICI", "auto").strip().lower()
    if secim in ("x264", "libx264", "cpu"):
        logger.info("Video kodlayıcı: libx264 (DUBLAJ_VIDEO_KODLAYICI=%s)", secim)
        return False
    if secim == "auto" and os.environ.get("CUDA_VISIBLE_DEVICES") == "":
        logger.info("Video kodlayıcı: libx264 (işlemci kipi)")
        return False
    komut = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=s=256x256:d=0.1",
             "-c:v", "h264_nvenc", "-f", "null", "-"]
    try:
        sonuc = subprocess.run(komut, capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as hata:
        logger.info("Video kodlayıcı: libx264 (NVENC denemesi çalışmadı: %s)", hata)
        return False
    if sonuc.returncode == 0:
        logger.info("Video kodlayıcı: h264_nvenc (GPU)")
        return True
    if secim == "nvenc":
        raise RuntimeError(f"DUBLAJ_VIDEO_KODLAYICI=nvenc ama NVENC çalışmıyor: {sonuc.stderr.strip()[:300]}")
    logger.info("Video kodlayıcı: libx264 (NVENC kullanılamıyor: %s)", sonuc.stderr.strip().splitlines()[-1:] or "-")
    return False
