"""Arayüz dili: masaüstü ve web arayüzünün yazıları `arayuz_dilleri/<dil>.json` sözlüklerinden gelir.

Yeni dil = yeni bir JSON dosyası (kod değişmez; `genel.arayuz_dili` seçenekleri dosyalardan okunur). Kurallar:
  * düz anahtar → metin; değişken kısım yer tutucuyla (`"Dub into {hedef}"`), cümle parçalardan yapıştırılmaz
    (her dilin kelime sırası farklıdır; çeviri o dili konuşan birinin yazacağı gibi yazılır)
  * eksik anahtar İngilizceye, o da yoksa Türkçeye düşer; hiçbir yazı boş kalmaz
  * "auto": işletim sisteminin arayüz dili sözlüklerde varsa o, yoksa İngilizce
Kapsam: arayüz yazıları, ayar açıklamaları, aşama ve durum adları, donanım etiketleri. Komut satırı, iş günlüğü
ve hattın hata mesajları Türkçedir (docs/arayuz_dili.md).
"""

from __future__ import annotations

import json
import locale
import os
import sys
from functools import lru_cache
from pathlib import Path

KLASOR = Path(__file__).with_name("arayuz_dilleri")
YEDEK = ("en", "tr")  # eksik anahtarın düştüğü sıra
_secili = "tr"  # komut satırı ve testler için; arayüzler açılışta ayarla() çağırır


@lru_cache(maxsize=None)
def sozluk(dil: str) -> dict[str, str]:
    """Tek dilin kendi dosyası (yedeksiz); dosya yoksa boş."""
    yol = KLASOR / f"{dil}.json"
    if not yol.is_file():
        return {}
    veri = json.loads(yol.read_text(encoding="utf-8"))
    return {k: v for k, v in veri.items() if not k.startswith("_")}


@lru_cache(maxsize=None)
def mevcut_diller() -> tuple[str, ...]:
    """Sözlüğü olan diller: önce tr ve en, sonra alfabe sırası."""
    kodlar = {p.stem for p in KLASOR.glob("*.json")}
    return tuple([k for k in ("tr", "en") if k in kodlar] + sorted(kodlar - {"tr", "en"}))


def tam_sozluk(dil: str) -> dict[str, str]:
    """Yedekleri birleşmiş sözlük (web sayfasına giden): tr < en < dil."""
    birlesik: dict[str, str] = {}
    for kod in (*reversed(YEDEK), dil):
        birlesik.update(sozluk(kod))
    return birlesik


def sistem_dili() -> str:
    """İşletim sisteminin arayüz dili, iki harfli kod ("tr", "en", ...); bulunamazsa ""."""
    if sys.platform == "win32":
        try:
            import ctypes

            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined]
            ad = locale.windows_locale.get(lcid, "")
            if ad:
                return ad.split("_")[0].lower()
        except (AttributeError, OSError):
            pass
    for degisken in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        deger = os.environ.get(degisken, "")
        if deger and deger not in ("C", "POSIX") and not deger.startswith("C."):
            return deger.split(":")[0].split("_")[0].split(".")[0].lower()
    try:
        ad = locale.getlocale()[0] or ""
    except ValueError:
        ad = ""
    return ad.split("_")[0].lower() if "_" in ad and len(ad.split("_")[0]) == 2 else ""


def cozumle(deger: str | None) -> str:
    """Ayar değeri ("auto", "tr", "en", ...) → kullanılacak dil."""
    deger = (deger or "auto").strip().lower()
    if deger in mevcut_diller():
        return deger
    sistem = sistem_dili()
    return sistem if sistem in mevcut_diller() else "en"


def ayarla(dil: str) -> str:
    global _secili
    _secili = cozumle(dil)
    return _secili


def secili() -> str:
    return _secili


def t(anahtar: str, dil: str | None = None, /, **degerler: object) -> str:
    """Anahtarın seçili (ya da verilen) dildeki metni; yer tutucular doldurulur."""
    for kod in (dil or _secili, *YEDEK):
        metin = sozluk(kod).get(anahtar)
        if metin is not None:
            return metin.format(**degerler) if degerler else metin
    return anahtar


def var_mi(anahtar: str, dil: str | None = None) -> bool:
    """Anahtar bu dilin kendi dosyasında var mı (yedeğe düşmeden)."""
    return anahtar in sozluk(dil or _secili)


@lru_cache(maxsize=None)
def _ust_bilgi(dil: str) -> dict[str, str]:
    yol = KLASOR / f"{dil}.json"
    veri = json.loads(yol.read_text(encoding="utf-8")) if yol.is_file() else {}
    return {k: v for k, v in veri.items() if k.startswith("_")}


def kendi_adi(dil: str) -> str:
    """Arayüz dilinin kendi dilindeki adı (dil seçicide görünen: "Türkçe", "English")."""
    return _ust_bilgi(dil).get("_ad", dil)


def yon(dil: str | None = None) -> str:
    """Yazı yönü: "ltr" ya da "rtl" (Arapça, Farsça ... sözlüğünde "_yon": "rtl")."""
    return _ust_bilgi(dil or _secili).get("_yon", "ltr")


def dil_adi(kod: str, dil: str | None = None) -> str:
    """Hedef dilin arayüz dilindeki adı ("de" → "Almanca" / "German"); sözlükte yoksa dilin kendi adı."""
    from dublaj_hatti import kayit

    return sozluk(dil or _secili).get(f"dil.{kod}") or kayit.dil_kendi_adi(kod)


def dil_secenegi(kod: str, dil: str | None = None) -> str:
    """Dublaj dili listesindeki yazı: arayüz dilindeki ad, farklıysa yanında dilin kendi adı ("Almanca (Deutsch)")."""
    from dublaj_hatti import kayit

    ad, kendi = dil_adi(kod, dil), kayit.dil_kendi_adi(kod)
    return ad if ad == kendi else t("dil.iki_ad", dil, ad=ad, kendi=kendi)
