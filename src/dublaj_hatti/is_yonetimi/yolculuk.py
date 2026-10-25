"""İlerleme ekranının dilden bağımsız verisi: aşamaları altı duraklı yola toplar, "şimdi ne oluyor" satırlarını
anahtar olarak tutar, kalan süreyi tahmin eder. Yazıları arayüz kendi dilinde çizer (`durak.*`, `anlati.*`).

Hat aşama içi sayı vermez (yalnız aşama başladı/bitti); yüzde aşama ağırlığından gelir, uydurma ara değer yok.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any

# (durak, simge, aşamalar): çocuk ve yaşlı biri için on beş aşama yerine altı tanıdık adım
DURAKLAR: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("video", "🎬", frozenset({"video_indirme_veya_kopyalama"})),
    ("ses", "🎧", frozenset({"kaynak_ses_cikarma", "demucs_vokal_ayirma", "asr_sesi_hazirlama"})),
    ("yazi", "✍️", frozenset({"transkripsiyon", "forced_alignment_ve_nihai_segmentler", "konusmaci_yonlendirme",
                             "full_text_konusma_penceresi"})),
    ("ceviri", "🌍", frozenset({"ceviri", "full_text_ceviri"})),
    ("seslendirme", "🗣️", frozenset({"ses_yonlendirme", "tts_ve_segment_sesleri", "full_text_tek_ses_tts"})),
    ("birlestirme", "🎞️", frozenset({"altyazi_hazirlama", "video_timeline_ve_final_mux", "arka_plan_miksi",
                                     "final_altyazi_yakma", "final_dogrulama_ve_meta",
                                     "full_text_final_altyazi_alignment",
                                     "full_text_video_sure_uyumu_ve_final_mux"})),
)
TRANSKRIPT_DURAKLARI = frozenset({"video", "ses", "yazi"})  # transkript işi çeviri ve seslendirme yapmaz
KALAN_ESIGI_YUZDE = 15  # daha erken tahmin oynak olur: gösterilmez
KALAN_ESIGI_SN = 30.0


def duraklar(asama_kimlikleri: list[str], komut: str, tamamlanan: list[str], asama: str,
             durum: str) -> list[dict[str, str]]:
    """Bu işin yolundaki duraklar: bitti | suruyor | bekliyor (iş bittiyse hepsi bitti)."""
    sonuc = []
    for kimlik, simge, uyeler in DURAKLAR:
        if komut == "transkript" and kimlik not in TRANSKRIPT_DURAKLARI:
            continue
        bu_is = [a for a in asama_kimlikleri if a in uyeler]
        if not bu_is:
            continue
        if durum == "bitti" or all(a in tamamlanan for a in bu_is):
            hal = "bitti"
        elif asama in uyeler or any(a in tamamlanan for a in bu_is):
            hal = "suruyor"
        else:
            hal = "bekliyor"
        sonuc.append({"id": kimlik, "simge": simge, "durum": hal})
    if durum == "calisiyor" and not any(d["durum"] == "suruyor" for d in sonuc):
        ilk = next((d for d in sonuc if d["durum"] == "bekliyor"), None)
        if ilk:
            ilk["durum"] = "suruyor"  # aşamalar arası boşlukta bir sonraki durak sürüyor görünür
    return sonuc


def kalan_sn(yuzde: int, gecen_sn: float, durum: str) -> int | None:
    """Kaba kalan süre (sn): geçen süre × kalan/biten ağırlık. Erken ve iş dışı None."""
    if durum != "calisiyor" or yuzde < KALAN_ESIGI_YUZDE or gecen_sn < KALAN_ESIGI_SN or yuzde >= 100:
        return None
    return int(gecen_sn * (100 - yuzde) / yuzde)


class Anlati:
    """"Şimdi ne oluyor" satırları: {sn, anahtar, ...değerler}; arayüz `anlati.<anahtar>` ile kendi dilinde yazar."""

    def __init__(self, baslangic: float, uzunluk: int = 60) -> None:
        self.baslangic = baslangic
        self.satirlar: deque[dict[str, Any]] = deque(maxlen=uzunluk)

    def ekle(self, anahtar: str, **degerler: str) -> None:
        sn = round(time.time() - self.baslangic, 1) if self.baslangic else 0.0
        self.satirlar.append({"sn": sn, "anahtar": anahtar, **degerler})

    def olaydan(self, olay: dict[str, Any]) -> None:
        """Hat olayından satır: aşama başladı, önceki çalışmadan hazır geldi, kaynak bekleniyor."""
        tur, asama = olay.get("event"), str(olay.get("stage_id") or "")
        if tur == "stage_started" and asama:
            self.ekle(f"basladi.{asama}")
        elif tur == "stage_restored" and asama:
            self.ekle("hazirdi", asama=asama)
        elif tur == "kaynak_bekleniyor":
            self.ekle("bekliyor")

    def liste(self) -> list[dict[str, Any]]:
        return list(self.satirlar)
