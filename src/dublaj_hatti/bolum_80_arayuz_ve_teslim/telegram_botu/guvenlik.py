"""Telegram botu erişim kuralları (saf işlevler, ağsız sınanır).

- Belirteç yalnız ortam değişkeninden (`TELEGRAM_BOT_TOKEN`, `.env` dahil); koda, ayara, günlüğe yazılmaz.
- İzinli kullanıcılar `TELEGRAM_IZINLI_KULLANICILAR` (virgülle sayısal Telegram kimlikleri). Liste boşsa bot
  BAŞLAMAZ (güvenli varsayılan: herkese açık bot olmaz).
- İzinsiz kişiye bilgi verilmez; kimliği günlüğe yazılmaz, yalnız sayaç artar.
"""

from __future__ import annotations

import os
import re

BELIRTEC_DEGISKENI = "TELEGRAM_BOT_TOKEN"
IZINLI_DEGISKENI = "TELEGRAM_IZINLI_KULLANICILAR"
_BELIRTEC_BICIMI = re.compile(r"^\d{5,15}:[A-Za-z0-9_-]{30,}$")


class TelegramAyarHatasi(RuntimeError):
    pass


def izinli_kullanicilar(deger: str | None = None) -> frozenset[int]:
    ham = os.environ.get(IZINLI_DEGISKENI, "") if deger is None else deger
    kimlikler = set()
    for parca in ham.replace(";", ",").split(","):
        parca = parca.strip()
        if not parca:
            continue
        if not parca.lstrip("-").isdigit():
            raise TelegramAyarHatasi(f"{IZINLI_DEGISKENI} yalnız sayısal kimlik içerir (virgülle ayrılmış)")
        kimlikler.add(int(parca))
    return frozenset(kimlikler)


def belirteci_al(deger: str | None = None) -> str:
    belirtec = (os.environ.get(BELIRTEC_DEGISKENI, "") if deger is None else deger).strip()
    if not belirtec:
        raise TelegramAyarHatasi(f"{BELIRTEC_DEGISKENI} boş: BotFather'dan aldığınız belirteci .env dosyasına yazın")
    if not _BELIRTEC_BICIMI.match(belirtec):
        raise TelegramAyarHatasi(f"{BELIRTEC_DEGISKENI} biçimi geçersiz (sayı:anahtar beklenir)")
    return belirtec


def yetkili_mi(kullanici_id: int | None, izinliler: frozenset[int]) -> bool:
    return kullanici_id is not None and kullanici_id in izinliler


def baslatma_denetimi() -> tuple[str, frozenset[int]]:
    belirtec = belirteci_al()
    izinliler = izinli_kullanicilar()
    if not izinliler:
        raise TelegramAyarHatasi(
            f"{IZINLI_DEGISKENI} boş: bot yalnız izinli kimliklere cevap verir; kendi kimliğinizi yazın "
            "(docs/tarifler/telegram_botu.md)"
        )
    return belirtec, izinliler


def gizle(metin: str) -> str:
    """Hata metinlerinde belirteç geçerse maskeler (günlüğe/sohbete sızmasın)."""
    return re.sub(r"\d{5,15}:[A-Za-z0-9_-]{30,}", "<belirtec>", str(metin))
