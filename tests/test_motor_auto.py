"""ses.motor = "auto": VoxCPM2 kuruluysa ve NVIDIA GPU çalışıyorsa o, değilse Supertonic; açık seçim "auto"yu geçer."""

from __future__ import annotations

import logging

import pytest

from dublaj_hatti import kayit, lisans_onayi, yapilandirma
from dublaj_hatti.bolum_00_omurga.runtime import donanim


def _gpu(monkeypatch, var: bool):
    def cihaz_coz(secim="auto"):
        if secim == "cpu" or not var:
            return "cpu"
        return "cuda"

    monkeypatch.setattr(donanim, "cihaz_coz", cihaz_coz)


def _voxcpm2_kurulu(monkeypatch, kurulu: bool):
    ham = kayit.motor("voxcpm2")
    monkeypatch.setattr(kayit, "motor", lambda ad: ham.__class__(**{**ham.__dict__, "kurulu": lambda: kurulu})
                        if ad == "voxcpm2" else _asil(ad))


_asil = kayit.motor


def test_varsayilan_auto_ve_gecerli_deger():
    ayar = yapilandirma.ayarlari_yukle()
    assert ayar["ses.motor"] == "auto"
    assert kayit.adlar("tts")[0] == "auto"
    assert yapilandirma.ayarlari_yukle(ustune=["ses.motor=supertonic"])["ses.motor"] == "supertonic"


@pytest.mark.parametrize("gpu, kurulu, beklenen", [
    (True, True, "voxcpm2"),
    (True, False, "supertonic"),
    (False, True, "supertonic"),
    (False, False, "supertonic"),
])
def test_auto_coz_donanima_gore(monkeypatch, gpu, kurulu, beklenen):
    _gpu(monkeypatch, gpu)
    _voxcpm2_kurulu(monkeypatch, kurulu)
    ayar = yapilandirma.ayarlari_yukle()
    motor, neden = yapilandirma.tts_auto_coz(ayar)
    assert motor == beklenen
    assert neden.startswith("ses.motor=auto → " + beklenen)


def test_full_text_kipi_supertonic_secer(monkeypatch):
    _gpu(monkeypatch, True)
    _voxcpm2_kurulu(monkeypatch, True)
    ayar = yapilandirma.ayarlari_yukle(ustune=["genel.dublaj_kipi=full_text", "ceviri.arka_uc=codex"])
    assert yapilandirma.tts_auto_coz(ayar)[0] == "supertonic"


def test_acik_secim_auto_yu_gecer(monkeypatch):
    _gpu(monkeypatch, True)
    _voxcpm2_kurulu(monkeypatch, True)
    ayar = yapilandirma.ayarlari_yukle(ustune=["ses.motor=supertonic"])
    assert yapilandirma.tts_motoru_coz(ayar) == "supertonic"


def test_lisans_kapisi_cozulen_motoru_gorur(monkeypatch):
    _gpu(monkeypatch, False)
    ayar = yapilandirma.ayarlari_yukle()
    assert "supertonic" in lisans_onayi.secili_motorlar(ayar, "faster-whisper")
    assert "auto" not in lisans_onayi.secili_motorlar(ayar, "faster-whisper")


def test_auto_cozulunce_gunluge_nedeni_yazilir(monkeypatch):
    _gpu(monkeypatch, False)
    kayitlar: list[str] = []

    class _H(logging.Handler):
        def emit(self, k):
            kayitlar.append(k.getMessage())

    gunluk = logging.getLogger("dublaj_hatti")
    h = _H(logging.INFO)
    eski = gunluk.level
    gunluk.addHandler(h)
    gunluk.setLevel(logging.INFO)
    try:
        ayar = yapilandirma.ayarlari_yukle()
        assert yapilandirma.tts_motoru_coz(ayar, gunluk=True) == "supertonic"
    finally:
        gunluk.removeHandler(h)
        gunluk.setLevel(eski)
    assert any("ses.motor=auto → supertonic" in m for m in kayitlar)


def test_transkript_isinde_auto_gpu_sormaz(monkeypatch):
    def patla(*a, **k):
        raise AssertionError("transkript işinde GPU denetimi yapılmamalı")

    monkeypatch.setattr(donanim, "cihaz_coz", patla)
    ayar = yapilandirma.ayarlari_yukle(ustune=["genel.is_turu=transkript"])
    assert yapilandirma.tts_motoru_coz(ayar) == "supertonic"


def test_cozulen_supertonic_okuyamadigi_dili_acik_hatayla_reddeder(monkeypatch):
    pytest.importorskip("numpy")  # dubconfig_olustur DubConfig için dubber modülünü (numpy) içe aktarır
    _gpu(monkeypatch, False)
    ayar = yapilandirma.ayarlari_yukle(ustune=["genel.hedef_dil=zh", "ceviri.arka_uc=codex"])
    with pytest.raises(yapilandirma.AyarHatasi, match="Supertonic 'zh'"):
        yapilandirma.dubconfig_olustur(ayar)


def test_dil_suzgecinde_auto_var():
    s = kayit.tts_dil_suzgeci()["auto"]
    assert "zh" in s["izinli"] and "tr" in s["izinli"]
