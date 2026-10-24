"""PRIVACY.md: var, iki dilli, koddaki gerçek adlarla eşit (bulut motorları, anahtar adları, yerel kayıt dosyaları)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dublaj_hatti import kayit
from dublaj_hatti.bolum_40_ceviri import arka_uc_secimi

KOK = Path(__file__).resolve().parents[1]
METIN = (KOK / "PRIVACY.md").read_text(encoding="utf-8")
EN = METIN[METIN.index("## EN"):METIN.index("## TR")]
TR = METIN[METIN.index("## TR"):]


def test_iki_dil_ayni_basliklar():
    assert EN.count("\n### ") == TR.count("\n### ") >= 5
    assert EN.count("\n| ") == TR.count("\n| ")  # tablolar satır satır çevrilmiş


@pytest.mark.parametrize("motor", [m for m in kayit.MOTORLAR if m.cihaz == "bulut"], ids=lambda m: m.ad)
def test_her_bulut_motoru_ve_anahtari_yazili(motor):
    for bolum in (EN, TR):
        assert re.search(rf"(?<![\w-]){re.escape(motor.ad)}(?![\w-])", bolum), motor.ad
    adlar = arka_uc_secimi.API_ANAHTARI_DEGISKENLERI.get(motor.ad) or kayit.STT_API_ANAHTARLARI.get(motor.ad)
    if adlar:
        assert any(f"`{ad}`" in EN for ad in adlar), motor.ad


def test_yerel_kayit_dosyalari_kodla_ayni():
    from dublaj_hatti import lisans_onayi
    from dublaj_hatti.bolum_50_seslendirme.xtts_tts import lisans as xtts_lisans
    from dublaj_hatti.is_yonetimi import depo

    for bolum in (EN, TR):
        assert depo.DEPO_DOSYA_ADI in bolum
        assert "ayarlar/lisans_onaylari.json" in bolum and lisans_onayi.ONAY_DOSYASI_ORTAM in bolum
        assert xtts_lisans.onay_dosyasi().name in bolum


def test_atif_yapan_dosyalar_var():
    atif = [p for p in (KOK / "src").rglob("*.py") if "PRIVACY.md" in p.read_text(encoding="utf-8", errors="replace")]
    atif += [p for p in (KOK / "docs").rglob("*.md") if "PRIVACY.md" in p.read_text(encoding="utf-8")]
    assert atif, "PRIVACY.md'ye atıf beklenirdi"
    assert (KOK / "PRIVACY.md").is_file()
