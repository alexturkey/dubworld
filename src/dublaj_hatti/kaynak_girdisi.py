"""Source input check shared by the CLI, the desktop and the web interface (standard library only).

A source is a local video file or an https link. Links are optional features:
  * gallery sites (gallery-dl, extras ``galeri``; separate process, never imported)
  * video sites supported by yt-dlp (extras ``youtube``)
Each link type checks only its own tool, and a missing tool gives a clear install hint instead of a stack trace.
Only content you own or are allowed to use; the site's terms are your responsibility.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

__all__ = ["VIDEO_UZANTILARI", "KaynakHatasi", "baglanti_mi", "baglanti_turu", "kaynak_dogrula"]

VIDEO_UZANTILARI = frozenset({".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"})
SORUMLULUK = "Yalnız hakkınız olan ya da izinli içerik kullanın; sitenin kullanım şartları size aittir."


class KaynakHatasi(ValueError):
    """The given source cannot be used (missing file, unsupported link, optional tool not installed)."""


def baglanti_mi(metin: str) -> bool:
    return (metin or "").strip().lower().startswith(("http://", "https://", "www."))


def baglanti_turu(metin: str) -> str:
    """'galeri', 'video' (yt-dlp site) or '' (not supported)."""
    from dublaj_hatti.bolum_10_kaynak_edinme.adim_20_kaynak_alma.galeri_indirici import galeri_adresi_mi
    from dublaj_hatti.bolum_10_kaynak_edinme.adim_20_kaynak_alma.youtube_downloader import is_url

    metin = (metin or "").strip()
    if galeri_adresi_mi(metin):
        return "galeri"
    if is_url(metin):
        return "video"
    return ""


def kaynak_dogrula(kaynak: str) -> str:
    """Returns the normalised source (absolute path or the link) or raises :class:`KaynakHatasi`."""
    kaynak = (kaynak or "").strip()
    if not kaynak:
        raise KaynakHatasi("kaynak boş: yerel video dosyası ya da bağlantı verin")
    if baglanti_mi(kaynak):
        if not kaynak.lower().startswith("https://") and not kaynak.lower().startswith("www."):
            raise KaynakHatasi("yalnız https bağlantısı kabul edilir")
        tur = baglanti_turu(kaynak)
        if tur == "galeri":
            from dublaj_hatti.bolum_10_kaynak_edinme.adim_20_kaynak_alma.galeri_indirici import (
                KURULUM_IPUCU,
                galeri_kurulu,
            )

            if not galeri_kurulu():
                raise KaynakHatasi(f"{KURULUM_IPUCU}. {SORUMLULUK}")
        elif tur == "video":
            if importlib.util.find_spec("yt_dlp") is None:
                raise KaynakHatasi("Bağlantıdan indirme isteğe bağlıdır ve yt-dlp kurulu değil: pip install .[youtube] "
                                   f"(ya da scripts/kur.ps1 -Adim youtube). Yerel video dosyası da verebilirsiniz. {SORUMLULUK}")
        else:
            raise KaynakHatasi("desteklenmeyen bağlantı: yalnız yt-dlp'nin izin listesindeki video siteleri ya da galeri "
                               "siteleri (gallery-dl) kabul edilir; yerel video dosyası verin")
        return kaynak
    yol = Path(kaynak).expanduser()
    if not yol.is_file():
        raise KaynakHatasi(f"video dosyası bulunamadı: {yol}")
    if yol.suffix.lower() not in VIDEO_UZANTILARI:
        raise KaynakHatasi(f"desteklenmeyen dosya türü: {yol.suffix} ({', '.join(sorted(VIDEO_UZANTILARI))})")
    return str(yol.resolve())
