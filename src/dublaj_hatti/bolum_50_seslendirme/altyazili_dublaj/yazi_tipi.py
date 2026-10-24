"""Yakılmış altyazı yazı tipi: yedek zinciri (Düzeltme A, D6).

Önce Arial (Windows'ta önceki çıktı birebir aynı kalır), yoksa DejaVu Sans / Liberation Sans (Linux dağıtımlarının
çoğunda kurulu, Arial ile aynı ölçülere yakın), en sonda Pillow'un gömülü yazı tipi (`ImageFont.load_default`).
Hangi yazı tipinin seçildiği günlüğe bir kez yazılır.
"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

logger = logging.getLogger("dublaj_hatti")

ADAYLAR = (
    "arial.ttf",
    "Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
)


@lru_cache(maxsize=1)
def yazi_tipi_yolu() -> str | None:
    """İlk açılabilen aday (Pillow'un kendi arama yoluyla); hiçbiri yoksa None (gömülü yazı tipi kullanılır)."""
    for aday in ADAYLAR:
        try:
            ImageFont.truetype(aday, 12)
        except OSError:
            continue
        logger.info("Altyazı yazı tipi: %s", aday)
        return aday
    logger.warning("Altyazı yazı tipi: Arial / DejaVu Sans / Liberation Sans bulunamadı; Pillow gömülü yazı tipi")
    return None


@lru_cache(maxsize=128)
def yazi_tipi(boyut: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    yol = yazi_tipi_yolu()
    if yol is not None:
        return ImageFont.truetype(yol, int(boyut))
    return ImageFont.load_default(size=int(boyut))


def yazi_tipi_ozeti() -> str:
    """Kayıt için seçilen yazı tipi dosyasının sha256'sı (gömülü yazı tipinde sabit bir ad)."""
    yol = getattr(yazi_tipi(62), "path", None)
    if isinstance(yol, str) and Path(yol).is_file():
        return hashlib.sha256(Path(yol).read_bytes()).hexdigest()
    return "pillow_load_default"
