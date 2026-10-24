"""İsteğe bağlı galeri indirici: gallery-dl'i yalnız AYRI SÜREÇ olarak çağırır (extras `galeri`).

Lisans: gallery-dl GPL-2.0-only. Bu modül onu asla `import` etmez; komut satırı aracını alt süreçte çalıştırır
(bağımsız program olarak kullanım), böylece bu repo Apache-2.0 kalır. Kurulu değilse açık hata verir.

Yalnız hakkınız olan ya da izinli içerik; sitenin kullanım şartları size aittir. Giriş gerektiren siteler için
çerez/oturum bilgisi bu repoda tutulmaz: gallery-dl'in kendi ayar dosyasını kullanın (kendi makinenizde,
`DUBLAJ_GALLERY_DL_AYAR` ile yolunu verin). Ayar ve çerez değerleri günlüğe yazılmaz.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# gallery-dl'in yt-dlp'den iyi çalıştığı, kısa video paylaşılan siteler (yt-dlp listesiyle çakışmaz)
GALERI_ALAN_ADLARI = ("instagram.com", "instagr.am")
VIDEO_UZANTILARI = (".mp4", ".mkv", ".webm", ".mov")
ZAMAN_ASIMI_SN = 900
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
KURULUM_IPUCU = (
    "gallery-dl kurulu değil: pip install .[galeri]  (ya da gallery-dl'i PATH'e koyun / DUBLAJ_GALLERY_DL ile yolunu verin)"
)


class GaleriIndiriciHatasi(RuntimeError):
    pass


def galeri_adresi_mi(metin: str) -> bool:
    metin = (metin or "").strip()
    if not metin.startswith("https://"):
        return False
    host = (urlparse(metin).hostname or "").lower().strip(".")
    return any(host == alan or host.endswith("." + alan) for alan in GALERI_ALAN_ADLARI)


def galeri_komutu() -> list[str] | None:
    """gallery-dl'i çalıştıracak komutun başı; bulunamazsa None. Sıra: ortam değişkeni, PATH, bu Python'un modülü."""
    ozel = os.environ.get("DUBLAJ_GALLERY_DL", "").strip()
    if ozel:
        return [ozel] if Path(ozel).is_file() else None
    yol = shutil.which("gallery-dl")
    if yol:
        return [yol]
    import importlib.util

    if importlib.util.find_spec("gallery_dl") is not None:  # yalnız var mı diye bakılır, import edilmez
        return [sys.executable, "-m", "gallery_dl"]
    return None


def galeri_kurulu() -> bool:
    return galeri_komutu() is not None


def komut_olustur(bas: list[str], url: str, hedef: Path, ayar_dosyasi: str = "") -> list[str]:
    komut = [*bas, "--destination", str(hedef), "--filter", "extension in ('mp4', 'mkv', 'webm', 'mov')"]
    if ayar_dosyasi:
        komut += ["--config", ayar_dosyasi]
    return [*komut, "--", url]


def indir(url: str, hedef_klasor: str | Path, logger: Any = None) -> Path:
    if not galeri_adresi_mi(url):
        raise ValueError("gallery-dl yalnız https galeri bağlantıları için kullanılır")
    bas = galeri_komutu()
    if bas is None:
        raise GaleriIndiriciHatasi(KURULUM_IPUCU)
    hedef = Path(hedef_klasor).resolve() / "galeri_indirme"
    hedef.mkdir(parents=True, exist_ok=True)
    ayar = os.environ.get("DUBLAJ_GALLERY_DL_AYAR", "").strip()
    if ayar and not Path(ayar).is_file():
        raise GaleriIndiriciHatasi("DUBLAJ_GALLERY_DL_AYAR dosyası bulunamadı")
    once = set(hedef.rglob("*"))
    try:
        tamam = subprocess.run(
            komut_olustur(bas, url, hedef, ayar), capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=ZAMAN_ASIMI_SN, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
        )
    except subprocess.TimeoutExpired as hata:
        raise GaleriIndiriciHatasi(f"gallery-dl {ZAMAN_ASIMI_SN} sn içinde bitmedi") from hata
    if tamam.returncode != 0:
        son = (tamam.stderr or tamam.stdout or "").strip().splitlines()[-3:]
        raise GaleriIndiriciHatasi(f"gallery-dl başarısız (çıkış {tamam.returncode}): {' | '.join(son)}")
    yeni = [p for p in set(hedef.rglob("*")) - once if p.is_file() and p.suffix.lower() in VIDEO_UZANTILARI]
    if not yeni:
        raise GaleriIndiriciHatasi("gallery-dl video dosyası indirmedi (bağlantıda video yok ya da giriş gerekiyor)")
    video = max(yeni, key=lambda p: p.stat().st_mtime)
    if logger:
        logger.info("[GALERI] indirildi: %s", video.name)
    return video
