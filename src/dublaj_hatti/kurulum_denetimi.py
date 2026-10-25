"""İlk açılış denetimi (torch yüklemez): Önerilen akışın eksik parçaları; `dubla kontrol` ile aynı ölçüt.
Web arayüzü sayfanın üstünde gösterir (`/api/kurulum`)."""

from __future__ import annotations

from typing import Any


def kurulum_eksikleri() -> list[str]:
    from dublaj_hatti import kayit
    from dublaj_hatti.bolum_00_omurga.runtime.arac_yolu import arac_bul
    from dublaj_hatti.cli import onerilen_akis_eksikleri

    ffmpeg = arac_bul("ffmpeg")  # kurulu kopya ya da PATH'in mutlak klasörleri; çalışma klasörüne bakılmaz
    rapor: dict[str, Any] = {"ffmpeg": "var" if ffmpeg else ""}
    rapor.update({grup: kayit.durum(grup) for grup in ("stt", "ceviri", "tts", "ek")})
    return onerilen_akis_eksikleri(rapor)
