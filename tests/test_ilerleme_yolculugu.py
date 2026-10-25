"""İlerleme ekranı (duraklı yol, "şimdi ne oluyor" panosu, kalan süre): her aşama bir durakta ve her dilde
cümlesi var, durak durumları ve kalan süre doğru, web arayüzü aynı veriyi kendi dilinde çizer."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from dublaj_hatti import arayuz_dili
from dublaj_hatti.bolum_00_omurga.core.asama_sozlesmesi import PIPELINE_STAGES
from dublaj_hatti.is_yonetimi import yolculuk
from dublaj_hatti.is_yurutucu import IsDurumu

STATIK = Path(__file__).resolve().parents[1] / "src" / "dublaj_hatti" / "web_statik"
TUM_ASAMALAR = {a for liste in PIPELINE_STAGES.values() for a, _, _ in liste}
ANLATI_SABIT = ("basla", "hazirdi", "bekliyor", "bitti_dubla", "bitti_transkript", "hata", "durduruldu")


@pytest.fixture(autouse=True)
def _turkce(monkeypatch):
    monkeypatch.setattr(arayuz_dili, "_secili", "tr")


def test_her_asama_tek_durakta_ve_her_dilde_cumlesi_var():
    for asama in TUM_ASAMALAR:
        assert sum(asama in uyeler for _, _, uyeler in yolculuk.DURAKLAR) == 1, asama
    for kod in arayuz_dili.mevcut_diller():
        s = arayuz_dili.sozluk(kod)
        assert sorted(a for a in TUM_ASAMALAR if f"anlati.basladi.{a}" not in s) == [], kod
        assert [d for d, _, _ in yolculuk.DURAKLAR if f"durak.{d}" not in s] == [], kod
        assert [a for a in ANLATI_SABIT if f"anlati.{a}" not in s] == [], kod


def test_durak_durumlari():
    kimlikler = [a for a, _, _ in PIPELINE_STAGES["segment_sync"]]
    tamam = kimlikler[:4]  # video + ses durakları bitti, yazıya dökme başladı
    d = yolculuk.duraklar(kimlikler, "dubla", tamam, "transkripsiyon", "calisiyor")
    assert [o["id"] for o in d] == ["video", "ses", "yazi", "ceviri", "seslendirme", "birlestirme"]
    assert [o["durum"] for o in d] == ["bitti", "bitti", "suruyor", "bekliyor", "bekliyor", "bekliyor"]
    # aşamalar arası boşlukta sıradaki durak sürüyor görünür
    d = yolculuk.duraklar(kimlikler, "dubla", tamam, "", "calisiyor")
    assert [o["durum"] for o in d][2] == "suruyor"
    assert {o["durum"] for o in yolculuk.duraklar(kimlikler, "dubla", [], "", "bitti")} == {"bitti"}
    assert {o["durum"] for o in yolculuk.duraklar(kimlikler, "dubla", [], "", "bos")} == {"bekliyor"}
    assert [o["id"] for o in yolculuk.duraklar(kimlikler, "transkript", [], "", "bos")] == ["video", "ses", "yazi"]


def test_kalan_sure_erken_tahmin_etmez():
    assert yolculuk.kalan_sn(10, 300, "calisiyor") is None
    assert yolculuk.kalan_sn(50, 10, "calisiyor") is None
    assert yolculuk.kalan_sn(50, 120, "bitti") is None
    assert yolculuk.kalan_sn(25, 120, "calisiyor") == 360


def test_ozet_ve_anlati_olaylari():
    durum = IsDurumu(durum="calisiyor", baslangic=time.time() - 5, anlati=yolculuk.Anlati(time.time() - 5))
    durum.anlati.ekle("basla")
    for olay in ({"event": "stage_started", "stage_id": "transkripsiyon"},
                 {"event": "stage_restored", "stage_id": "kaynak_ses_cikarma"},
                 {"event": "kaynak_bekleniyor", "kaynak": "gpu"},
                 {"event": "stage_completed", "stage_id": "transkripsiyon"}):  # bitiş satır üretmez
        durum.anlati.olaydan(olay)
    ozet = durum.ozet()
    assert [s["anahtar"] for s in ozet["anlati"]] == ["basla", "basladi.transkripsiyon", "hazirdi", "bekliyor"]
    assert ozet["anlati"][2]["asama"] == "kaynak_ses_cikarma" and ozet["anlati"][1]["sn"] >= 4
    assert len(ozet["duraklar"]) == 6 and ozet["kalan_sn"] is None and ozet["komut"] == "dubla"


def test_web_ilerleme_bolumu_erisilebilir():
    html = (STATIK / "index.html").read_text(encoding="utf-8")
    assert 'role="progressbar"' in html and 'id="anlati"' in html and 'role="status"' in html
    css = (STATIK / "app.css").read_text(encoding="utf-8")
    hareket = css[css.index("prefers-reduced-motion: reduce) {"):]
    assert ".cubuk.canli > div" in hareket and "animation: none" in hareket
    js = (STATIK / "app.js").read_text(encoding="utf-8")
    assert '"anlati." + s.anahtar' in js and '"durak." + o.id' in js
