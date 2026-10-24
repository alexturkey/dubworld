"""İş yönetimi menüsü (saf işlevler; Telegram kütüphanesi gerekmez): sorunlu / biten / son işler, iş ayrıntısı,
kaldığı yerden devam, aşama seçip yeni işe kopyalayarak yeniden çalıştırma (isteğe bağlı /ayarlar seçimleriyle),
iptal, arşivle. Arka uç: `is_yonetimi.telegram_arka_ucu()` (komut satırı, masaüstü ve web ile aynı iş deposu).

Geri çağırma verisi (64 bayt sınırı içinde): `j:<eylem>[:<iş no>[:<aşama sırası>]]`
  s sorunlu · b biten · l son işler · v ayrıntı · d yerinde devam · y seçimlerimle yeni işe devam
  a aşama listesi · r aşamadan yeniden · R aşamadan yeniden (seçimlerimle) · x iptal · z arşiv sor · Z arşivle
"""

from __future__ import annotations

from typing import Any

ONEK = "j:"
LISTELER = {"s": "Sorunlu işler (son 10)", "b": "Biten işler (son 15)", "l": "Son işler"}
LISTE_SINIRI = {"s": 10, "b": 15, "l": 10}
IS_EYLEMLERI = frozenset("vdyarRxzZ")
DURUM_ETIKETI = {"kuyrukta": "sırada", "calisiyor": "çalışıyor", "bitti": "bitti", "hata": "hata", "iptal": "iptal"}


def is_menusu_mu(veri: str | None) -> bool:
    return str(veri or "").startswith(ONEK)


def coz(veri: str) -> tuple[str, int | None, int | None] | None:
    """('s'|'b'|'l', None, None) | (eylem, iş no, aşama sırası|None); geçersizse None."""
    parcalar = str(veri or "").split(":")
    if len(parcalar) < 2 or parcalar[0] != "j":
        return None
    eylem = parcalar[1]
    if eylem in LISTELER and len(parcalar) == 2:
        return eylem, None, None
    if eylem not in IS_EYLEMLERI or len(parcalar) not in (3, 4) or not parcalar[2].isdigit():
        return None
    sira = None
    if eylem in ("r", "R"):
        if len(parcalar) != 4 or not parcalar[3].isdigit():
            return None
        sira = int(parcalar[3])
    elif len(parcalar) != 3:
        return None
    return eylem, int(parcalar[2]), sira


def _kisa(metin: Any, sinir: int = 28) -> str:
    duz = " ".join(str(metin or "").split())
    return duz if len(duz) <= sinir else duz[: sinir - 1] + "…"


def is_satiri(o: dict[str, Any]) -> str:
    durum = DURUM_ETIKETI.get(o.get("durum", ""), o.get("durum", ""))
    asama = o.get("asama_adi") or ""
    return f"#{o.get('is_id')} {durum} · {_kisa(o.get('kaynak_adi'))}" + (f" · {asama}" if asama else "")


def liste_metni(tur: str, isler: list[dict[str, Any]]) -> str:
    baslik = LISTELER.get(tur, "İşler")
    if not isler:
        bos = {"s": "Devam ettirilecek sorunlu iş yok.", "b": "Biten iş yok."}.get(tur, "Henüz iş yok.")
        return f"{baslik}\n\n{bos}"
    ek = "\nEn yeni üstte. Bir işi seçin: devam, aşamadan yeniden, iptal, arşiv." if tur in ("s", "b") else ""
    return f"{baslik}{ek}\n\n" + "\n".join(is_satiri(o) for o in isler)


def liste_dugmeleri(tur: str, isler: list[dict[str, Any]]) -> list[tuple[str, str]]:
    dugmeler = [(_kisa(is_satiri(o), 60), f"j:v:{o['is_id']}") for o in isler]
    diger = [(LISTELER[t].split(" (")[0], f"j:{t}") for t in LISTELER if t != tur]
    return dugmeler + [("Yenile", f"j:{tur}"), *diger, ("Kapat", "k")]


def ayrinti_metni(s: dict[str, Any]) -> str:
    satirlar = [f"İş #{s['is_id']} · {DURUM_ETIKETI.get(s.get('durum', ''), s.get('durum', ''))}",
                f"Kaynak: {_kisa(s.get('kaynak_adi'), 60)}", f"Kip: {s.get('kip') or 'segment_sync'}"]
    if s.get("son_asama_adi"):
        satirlar.append(f"Son biten aşama: {s['son_asama_adi']}")
    if s.get("durum") == "hata":
        satirlar.append(f"Kesildiği aşama: {s.get('asama_adi') or '?'}")
        satirlar.append(f"Hata: {_kisa(s.get('hata'), 300)}")
    if s.get("ebeveyn"):
        satirlar.append(f"Türediği iş: #{s['ebeveyn']}")
    if s.get("durum") == "bitti" and s.get("video"):
        satirlar.append(f"Video: {_kisa(s['video'], 80)}")
    satirlar.append("")
    satirlar.append("Devamda geçerli aşamalar yeniden üretilmez; ayar değişirse yalnız etkilediği aşamadan sonrası "
                    "yeniden çalışır. Arşiv yalnız kaydı gizler, dosya silinmez.")
    return "\n".join(satirlar)


def ayrinti_dugmeleri(s: dict[str, Any], secim_var: bool) -> list[tuple[str, str]]:
    no = s["is_id"]
    d: list[tuple[str, str]] = []
    if s.get("yerinde_devam"):
        d.append(("Kaldığı yerden devam et", f"j:d:{no}"))
        if secim_var:
            d.append(("/ayarlar seçimlerimle devam (yeni iş)", f"j:y:{no}"))
    if s.get("yeniden"):
        d.append(("Aşama seçip yeniden çalıştır", f"j:a:{no}"))
    if s.get("iptal_edilebilir"):
        d.append(("İptal et", f"j:x:{no}"))
    if s.get("arsivlenebilir"):
        d.append(("Sil (kaydı arşivle)", f"j:z:{no}"))
    return d + [("Geri", "j:s" if s.get("durum") in ("hata", "iptal") else "j:l"), ("Kapat", "k")]


def asama_dugmeleri(s: dict[str, Any], secim_var: bool) -> list[tuple[str, str]]:
    no = s["is_id"]
    d = [(f"{y['ad']} aşamasından", f"j:r:{no}:{y['sira']}") for y in s.get("yeniden") or []]
    if secim_var:
        d += [(f"{y['ad']} + seçimlerim", f"j:R:{no}:{y['sira']}") for y in s.get("yeniden") or []]
    return d + [("Geri", f"j:v:{no}")]


def arsiv_onay_dugmeleri(no: str | int) -> list[tuple[str, str]]:
    return [("Evet, arşivle (dosya silinmez)", f"j:Z:{no}"), ("Vazgeç", f"j:v:{no}")]
