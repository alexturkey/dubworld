"""Moonshine deneysel: kayıtta etiketli, ayarda uyarı, geri kayan kelime zamanında açık hata.

Kök neden (docs/engineering/transcription.md §6): akış modelinin parça sınırında kelime başlangıçları geri kayıyor;
kurulu native sürümde çözümü kanıtlanmadı. Hat zamanları düzeltmez; merkezi kapı eskiden yalnız "Kelime sirasi
kronolojik degil" diyordu.
"""

from __future__ import annotations

import pytest

from dublaj_hatti import kayit, yapilandirma
from dublaj_hatti.cli import kontrol_raporu

AD = "moonshine_medium_streaming_en"


def test_kayitta_deneysel_ve_gerekceli():
    motor = kayit.motor(AD)
    assert motor.deneysel and "parakeet_cpu_align" in motor.deneysel
    assert "deneysel" in motor.gorunen_ad
    # yalnız gerçekten sınırı olan motor deneysel
    assert [m.ad for m in kayit.MOTORLAR if m.deneysel] == [AD]


def test_ayar_secilince_uyari_verir_ama_durdurmaz():
    ayar = yapilandirma.ayarlari_yukle()
    ayar["transkripsiyon.motor"] = AD
    bulgular = yapilandirma.uyumluluk_denetle(ayar)
    assert any(b.seviye == "uyari" and "DENEYSEL" in str(b) for b in bulgular)
    assert not [b for b in bulgular if b.seviye == "hata"]


def test_kontrol_raporu_deneyseli_gosterir():
    assert AD in kontrol_raporu()["deneysel"]


def test_kronolojik_olmayan_zaman_acik_hata():
    pytest.importorskip("soundfile")
    from dublaj_hatti.bolum_00_omurga.core import dubber

    iyi = [{"word": "a", "start": 0.0, "end": 0.2}, {"word": "b", "start": 0.3, "end": 0.5}]
    dubber.moonshine_kronoloji_denetle(iyi)  # sıralı: geçer
    geri = iyi + [{"word": "c", "start": 0.25, "end": 0.6}]
    with pytest.raises(dubber.MoonshineDeneyselHatasi) as hata:
        dubber.moonshine_kronoloji_denetle(geri)
    mesaj = str(hata.value)
    assert "parakeet_cpu_align" in mesaj and "deneysel" in mesaj and "transcription.md" in mesaj
    assert isinstance(hata.value, RuntimeError)
