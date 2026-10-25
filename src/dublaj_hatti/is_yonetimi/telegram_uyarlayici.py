"""Telegram botunun iş yönetimi çekirdeğine uyarlayıcısı (`telegram_botu.arka_uc.IsArkaUcu` sözleşmesi).

Bot bu nesneyi `dublaj_hatti.is_yonetimi.telegram_arka_ucu()` fabrikasıyla alır. Komut satırı, masaüstü ve web ile
aynı SQLite iş deposunu kullanır: telefondan başlatılan iş masaüstünün İşler sekmesinde de görünür, tersi de.
Telegram'a özgü bir kayıt tutulmaz (sohbet ya da kullanıcı kimliği depoya yazılmaz).

Temel sözleşme: `baslat`, `durum`, `liste`, `iptal`. Ek (iş yönetimi menüsü): `sorunlu`, `biten`, `secenekler`,
`devam`, `arsivle`. İş kimlikleri bot tarafında metindir (`"7"`), depoda tam sayıdır.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from dublaj_hatti.is_yonetimi.asamalar import asama_adi, asamalar
from dublaj_hatti.is_yonetimi.depo import IsHatasi, _json, is_ozeti

# Depo durumu → botun kullandığı durum adı (bot "calisiyor"/"kuyrukta" iken izlemeyi sürdürür).
BOT_DURUMU = {
    "queued": "kuyrukta", "deferred": "kuyrukta", "preparing": "kuyrukta", "processing": "calisiyor",
    "completed": "bitti", "failed": "hata", "cancelled": "iptal", "inceleme_bekliyor": "inceleme_bekliyor",
}
CIKTI_ANAHTARLARI = ("dubbed_video", "output_video", "srt_path", "transcript_path")


def _utc(deger: Any) -> float | None:
    if not deger:
        return None
    try:
        return datetime.strptime(str(deger), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()
    except ValueError:
        return None


def _no(is_id: str | int) -> int:
    try:
        return int(str(is_id).strip().lstrip("#"))
    except ValueError:
        raise IsHatasi(f"geçersiz iş numarası: {is_id!r}") from None


def ayar_ifadeleri(ayarlar: dict[str, Any] | None) -> list[str]:
    """Botun oturum seçimleri ({anahtar: değer}) → `a.b=c` ifadeleri (işin kendi değeriyle aynı olanı depo eler)."""
    cikti = []
    for anahtar, deger in (ayarlar or {}).items():
        metin = ("true" if deger else "false") if isinstance(deger, bool) else str(deger)
        if any(c in metin for c in "\r\n\x00"):
            raise ValueError(f"{anahtar}: geçersiz karakter")
        cikti.append(f"{anahtar}={metin}")
    return cikti


class TelegramArkaUcu:
    def __init__(self, yurutucu: Any | None = None) -> None:
        if yurutucu is None:
            from dublaj_hatti.is_yurutucu import IsYurutucu

            yurutucu = IsYurutucu(arayuz="telegram")  # kendi kuyruğunu (telegram'dan gelen işler) işler
        self._y = yurutucu
        self.depo = yurutucu.depo

    # ---- temel sözleşme ----------------------------------------------------------------------------------
    def baslat(self, kaynak: str, ayarlar: dict[str, Any]) -> str:
        return str(self._y.baslat(kaynak, dict(ayarlar or {})))

    def durum(self, is_id: str) -> dict[str, Any]:
        try:
            kayit = self.depo.getir(_no(is_id))
        except IsHatasi:
            kayit = None
        if not kayit:
            return {"is_id": str(is_id), "durum": "yok"}
        return self._ozet(kayit)

    def liste(self, limit: int = 10) -> list[dict[str, Any]]:
        return [self._ozet(k) for k in self.depo.listele(limit)]

    def iptal(self, is_id: str) -> bool:
        no = _no(is_id)
        canli = self._y.durum
        if canli.is_no == no and self._y.calisiyor():
            self._y.durdur()  # bu süreçte çalışan iş: alt süreç durur, iş "iptal" olur (devam ettirilebilir)
            return True
        return self.depo.iptal(no)  # sıradaki / ertelenen iş; başka arayüzde çalışan işe dokunulmaz

    # ---- iş yönetimi menüsü ------------------------------------------------------------------------------
    def sorunlu(self, limit: int = 10) -> list[dict[str, Any]]:
        return [self._ozet(k) for k in self.depo.son_sorunlu(limit)]

    def biten(self, limit: int = 15) -> list[dict[str, Any]]:
        return [self._ozet(k) for k in self.depo.son_biten(limit)]

    def secenekler(self, is_id: str) -> dict[str, Any]:
        kayit = self.depo.getir(_no(is_id))
        if not kayit:
            raise IsHatasi(f"iş bulunamadı: #{is_id}")
        devam = self.depo.devam_secenekleri(kayit)
        return {
            **self._ozet(kayit),
            "yerinde_devam": kayit["status"] in ("failed", "cancelled", "inceleme_bekliyor") and bool(devam),
            "yeniden": [{"sira": s["restart_stage_order"], "ad": s["ad"]}
                        for s in self.depo.yeniden_calistirma_secenekleri(kayit)],
            "iptal_edilebilir": kayit["status"] in ("queued", "deferred", "preparing", "processing"),
            "arsivlenebilir": kayit["status"] in ("completed", "failed", "cancelled", "inceleme_bekliyor") and not kayit["archived"],
        }

    def devam(self, is_id: str, asama: str | int | None = None, yeni_is: bool = False,
              ayarlar: dict[str, Any] | None = None) -> str:
        """Asama verilmezse kaldığı yerden; `asama` yeniden çalışacak ilk aşama (sıra, kimlik ya da ad)."""
        hedef = self._y.devam(_no(is_id), str(asama) if asama not in (None, "") else None, yeni_is,
                              ayar_ifadeleri(ayarlar) or None)
        return str(hedef)

    def arsivle(self, is_id: str) -> bool:
        return self.depo.arsivle(_no(is_id))

    # ---- özet --------------------------------------------------------------------------------------------
    def _ozet(self, kayit: dict[str, Any]) -> dict[str, Any]:
        ozet = is_ozeti(kayit)
        kip = str(kayit.get("dubbing_mode") or "segment_sync")
        liste = asamalar(kip)
        son = kayit.get("last_completed_stage") or ""
        son_sira = next((o for a, o, _ in liste if a == son), 0)
        toplam = sum(a[2] for a in liste) or 1
        yuzde = int(100 * sum(a[2] for a in liste if a[1] <= son_sira) / toplam)
        durum = BOT_DURUMU.get(kayit["status"], kayit["status"])
        asama = kayit.get("failed_stage") if durum == "hata" else ""
        bekleme = ""
        canli = self._y.durum
        if canli.is_no == int(kayit["job_id"]) and durum == "calisiyor":
            c = canli.ozet()
            yuzde, asama, bekleme = c["yuzde"], c["asama"], c.get("bekleme", "")
        baslangic, bitis = _utc(kayit.get("started_at")), _utc(kayit.get("completed_at"))
        gecen = ((bitis or time.time()) - baslangic) if baslangic else 0.0
        sonuc = _json(kayit.get("result_json"))
        return {
            **ozet,
            "is_id": str(kayit["job_id"]),
            "durum": durum,
            "yuzde": 100 if durum == "bitti" else min(99, yuzde),
            "asama": asama or "",
            "asama_adi": asama_adi(asama) if asama else (ozet.get("son_asama_adi") or ""),
            "bekleme": bekleme,
            "gecen_sn": round(max(0.0, gecen), 1),
            "ciktilar": [{"tur": k, "yol": str(sonuc[k])} for k in CIKTI_ANAHTARLARI if sonuc.get(k)],
        }
