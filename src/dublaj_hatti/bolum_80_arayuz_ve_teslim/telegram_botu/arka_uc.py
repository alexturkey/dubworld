"""Telegram botunun iş arka ucu: bot yalnız bu ince arayüzü bilir (iş başlat, durum, liste, iptal).

Sözleşme (`IsArkaUcu`): iş yönetimi çekirdeği (`dublaj_hatti.is_yonetimi`) hazır olduğunda kendi uyarlayıcısını
`dublaj_hatti.is_yonetimi.telegram_arka_ucu()` adıyla verir; `arka_uc_sec()` önce onu dener. Yoksa masaüstü/web
arayüzlerinin ortak tek-iş yürütücüsü (`is_yurutucu.IsYurutucu`) kullanılır.
"""

from __future__ import annotations

import importlib
import itertools
import threading
from typing import Any, Protocol


class IsArkaUcu(Protocol):
    def baslat(self, kaynak: str, ayarlar: dict[str, Any]) -> str: ...

    def durum(self, is_id: str) -> dict[str, Any]: ...

    def liste(self, limit: int = 10) -> list[dict[str, Any]]: ...

    def iptal(self, is_id: str) -> bool: ...


class YurutucuArkaUcu:
    """`IsYurutucu` üstünde (aynı anda tek iş). Durum sözlüğü `IsDurumu.ozet()` alanlarını taşır."""

    def __init__(self, yurutucu: Any | None = None) -> None:
        if yurutucu is None:
            from dublaj_hatti.is_yurutucu import IsYurutucu

            yurutucu = IsYurutucu()
        self._y = yurutucu
        self._sayac = itertools.count(1)
        self._gecmis: list[tuple[str, Any]] = []  # (is_id, IsDurumu) — süreç ömrü boyunca, en çok 20
        self._kilit = threading.Lock()

    def baslat(self, kaynak: str, ayarlar: dict[str, Any]) -> str:
        with self._kilit:
            if self._y.calisiyor():
                raise RuntimeError("bir iş zaten çalışıyor; bitince yeniden deneyin")
            self._y.baslat(kaynak, ayarlar)
            is_id = str(next(self._sayac))
            self._gecmis = [*self._gecmis[-19:], (is_id, self._y.durum)]
            return is_id

    def _bul(self, is_id: str) -> Any | None:
        return next((d for i, d in self._gecmis if i == str(is_id)), None)

    def durum(self, is_id: str) -> dict[str, Any]:
        d = self._bul(is_id)
        return {"is_id": str(is_id), **d.ozet()} if d is not None else {"is_id": str(is_id), "durum": "yok"}

    def liste(self, limit: int = 10) -> list[dict[str, Any]]:
        return [{"is_id": i, **d.ozet()} for i, d in reversed(self._gecmis[-limit:])]

    def iptal(self, is_id: str) -> bool:
        if not self._gecmis or self._gecmis[-1][0] != str(is_id) or not self._y.calisiyor():
            return False
        self._y.durdur()
        return True


def arka_uc_sec() -> IsArkaUcu:
    try:
        cekirdek = importlib.import_module("dublaj_hatti.is_yonetimi")
        fabrika = getattr(cekirdek, "telegram_arka_ucu", None)
        if callable(fabrika):
            return fabrika()
    except ImportError:
        pass
    return YurutucuArkaUcu()
