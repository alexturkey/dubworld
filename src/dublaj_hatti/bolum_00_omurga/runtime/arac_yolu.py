"""ffmpeg / ffprobe tam yolu (tek yer). Çıplak "ffmpeg" ile alt süreç başlatılmaz.

Neden: Windows'ta `subprocess.run(["ffmpeg", ...])` (CreateProcess) ve Python 3.11'in `shutil.which` işlevi programı
PATH'ten ÖNCE çalışma klasöründe arar; çalışma klasörüne (ör. işlenen videonun yanına) konmuş sahte `ffmpeg.exe`
çalışırdı. Burada arama sırası:

1. `DUBLAJ_FFMPEG_KLASORU` (isteğe bağlı, mutlak klasör; içinde ffmpeg ve ffprobe),
2. kurulumun indirdiği `runtime_assets/ffmpeg/bin/` (scripts/kur.ps1 -Adim modeller, sha256 doğrulamalı),
3. PATH'in yalnız MUTLAK klasörleri (boş, "." ve göreli girdiler atlanır: onlar çalışma klasörünü gösterir).

Bulunamazsa `AracBulunamadi` (FileNotFoundError alt sınıfı) yükselir; çağıranın eski "dosya yok" davranışı korunur.
Yalnız standart kütüphane.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import runtime_asset_root

KLASOR_ORTAMI = "DUBLAJ_FFMPEG_KLASORU"
KURULUM_ADIMI = "scripts/kur.ps1 -Adim modeller (FFmpeg bu adımla iner)"


class AracBulunamadi(FileNotFoundError):
    """ffmpeg / ffprobe güvenli bir yerde bulunamadı."""


def _dosya_adi(ad: str) -> str:
    return f"{ad}.exe" if sys.platform == "win32" else ad


def _calistirilabilir(yol: Path) -> bool:
    return yol.is_file() and (sys.platform == "win32" or os.access(yol, os.X_OK))


def arac_bul(ad: str) -> str | None:
    """`ad` ("ffmpeg" ya da "ffprobe") için mutlak yol; güvenli bir yerde yoksa None. Çalışma klasörüne bakmaz."""
    if ad not in ("ffmpeg", "ffprobe"):
        raise ValueError(f"bilinmeyen araç: {ad}")
    dosya = _dosya_adi(ad)
    klasorler: list[Path] = []
    acik = os.environ.get(KLASOR_ORTAMI, "").strip()
    if acik and Path(acik).is_absolute():
        klasorler.append(Path(acik))
    klasorler.append(runtime_asset_root() / "ffmpeg" / "bin")
    for parca in os.environ.get("PATH", "").split(os.pathsep):
        parca = parca.strip().strip('"')
        if parca and Path(parca).is_absolute():
            klasorler.append(Path(parca))
    for klasor in klasorler:
        aday = klasor / dosya
        if _calistirilabilir(aday):
            return str(aday.resolve())
    return None


def arac_yolu(ad: str) -> str:
    """`arac_bul` gibi, ama bulunamazsa kurulum adımını söyleyen `AracBulunamadi` yükseltir."""
    yol = arac_bul(ad)
    if yol is None:
        raise AracBulunamadi(f"{ad} bulunamadı (çalışma klasörüne bakılmaz). Kurulum: {KURULUM_ADIMI}; ya da PATH'e "
                             f"mutlak klasör olarak ekleyin / {KLASOR_ORTAMI} ile gösterin.")
    return yol


def ffmpeg_yolu() -> str:
    return arac_yolu("ffmpeg")


def ffprobe_yolu() -> str:
    return arac_yolu("ffprobe")
