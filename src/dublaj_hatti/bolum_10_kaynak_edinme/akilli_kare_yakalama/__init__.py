"""Akıllı kare (isteğe bağlı): videodaki siyah/sabit kenar bantlarını bulup içerik kutusuna kırpar.

OpenCV gerektirir (`pip install .[akilli-kare]`). Kurulu değilse `apply_smart_frame_capture` açık bir
`AkilliKareKuruluDegil` hatası verir; hat bu durumda kaynak videoyu değiştirmeden kullanır.
"""

from __future__ import annotations

import importlib.util
from typing import Any

from dublaj_hatti.bolum_10_kaynak_edinme.akilli_kare_yakalama.config import (
    SMART_FRAME_CONFIG_KEY,
    smart_frame_capture_enabled,
)

KURULUM_IPUCU = "Akıllı kare için OpenCV kurulu değil: pip install .[akilli-kare]  (opencv-python-headless)"


class AkilliKareKuruluDegil(RuntimeError):
    pass


def akilli_kare_kurulu() -> bool:
    return importlib.util.find_spec("cv2") is not None


def _servis():
    if not akilli_kare_kurulu():
        raise AkilliKareKuruluDegil(KURULUM_IPUCU)
    from dublaj_hatti.bolum_10_kaynak_edinme.akilli_kare_yakalama import service

    return service


def apply_smart_frame_capture(*args: Any, **kwargs: Any) -> dict:
    return _servis().apply_smart_frame_capture(*args, **kwargs)


def analyze_video_content(*args: Any, **kwargs: Any):
    return _servis().analyze_video_content(*args, **kwargs)


def algorithm_version() -> str:
    return _servis().ALGORITHM_VERSION


__all__ = [
    "SMART_FRAME_CONFIG_KEY",
    "AkilliKareKuruluDegil",
    "akilli_kare_kurulu",
    "algorithm_version",
    "analyze_video_content",
    "apply_smart_frame_capture",
    "smart_frame_capture_enabled",
]
