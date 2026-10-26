"""Emekli motor değerleri: eski ayar bir sürüm boyunca uyarıyla "auto"ya eşlenir; XTTS kullanımdan kalkıyor uyarısı verir."""

from __future__ import annotations

import logging

import pytest

from dublaj_hatti import yapilandirma



class _Toplayici(logging.Handler):
    """Günlükçü başka testlerde propagate=False olabilir; caplog yerine doğrudan işleyici."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.metinler: list[str] = []

    def emit(self, kayit):
        self.metinler.append(kayit.getMessage())

    @property
    def text(self):
        return " ".join(self.metinler)


@pytest.fixture
def caplog():
    gunluk = logging.getLogger("dublaj_hatti")
    h = _Toplayici()
    eski = gunluk.level
    gunluk.addHandler(h)
    gunluk.setLevel(logging.WARNING)
    try:
        yield h
    finally:
        gunluk.removeHandler(h)
        gunluk.setLevel(eski)


# Bu sürümde kaldırılan transkripsiyon motorları (her kaldırma commit'i listeye bir satır ekler)
KALDIRILAN_STT: list[str] = ["crisperwhisper2_medium"]


def test_emekli_deger_auto_ya_eslenir_ve_iki_dilli_uyari_yazar(monkeypatch, caplog):
    monkeypatch.setitem(yapilandirma.EMEKLI_DEGERLER, "transkripsiyon.motor", {"eski_motor": "auto"})
    assert yapilandirma._deger_dogrula("transkripsiyon.motor", "eski_motor") == "auto"
    mesaj = caplog.text
    assert "'eski_motor' bu sürümde kaldırıldı; 'auto' kullanılıyor" in mesaj
    assert "CrisperWhisper Turbo kuruluysa o, değilse faster-whisper" in mesaj
    assert "'eski_motor' was removed in this version; using 'auto'" in mesaj


def test_emekli_olmayan_gecersiz_deger_hala_hata(monkeypatch):
    monkeypatch.setitem(yapilandirma.EMEKLI_DEGERLER, "transkripsiyon.motor", {})
    with pytest.raises(yapilandirma.AyarHatasi):
        yapilandirma._deger_dogrula("transkripsiyon.motor", "hic_yok")
    assert yapilandirma._deger_dogrula("transkripsiyon.motor", "faster-whisper") == "faster-whisper"


@pytest.mark.parametrize("eski", KALDIRILAN_STT)
def test_kaldirilan_stt_motoru_auto_olur(eski, caplog):
    assert yapilandirma._deger_dogrula("transkripsiyon.motor", eski) == "auto"
    assert "kaldırıldı" in caplog.text and "was removed" in caplog.text


@pytest.mark.parametrize("eski", KALDIRILAN_STT)
def test_kaldirilan_stt_ayar_dosyasindan_yuklenir(eski, tmp_path, caplog):
    dosya = tmp_path / "eski.toml"
    dosya.write_text(f'[transkripsiyon]\nmotor = "{eski}"\n', encoding="utf-8")
    ayar = yapilandirma.ayarlari_yukle(dosya)
    assert ayar["transkripsiyon.motor"] == "auto"


def test_xtts_secilince_kullanimdan_kalkiyor_uyarisi():
    ayar = yapilandirma.ayarlari_yukle(None, ["ses.motor=xtts", "ses.xtts_referans_ses=ornek.wav"])
    bulgular = [b for b in yapilandirma.uyumluluk_denetle(ayar) if b.seviye == "uyari"]
    metin = " ".join(b.mesaj for b in bulgular)
    assert "XTTS kullanımdan kalkıyor (ticari olmayan CPML lisansı); VoxCPM2 metinsiz ses klonlamayı destekliyor." in metin
    assert "XTTS is being deprecated" in metin
    assert ayar["ses.motor"] == "xtts"  # çalışmaya devam eder


def test_xtts_secili_degilken_uyari_yok():
    ayar = yapilandirma.ayarlari_yukle()
    assert not any("XTTS" in b.mesaj for b in yapilandirma.uyumluluk_denetle(ayar))


def test_kaldirilan_per_window_dil_tespiti_global_first_windowa_eslenir(caplog):
    assert yapilandirma._deger_dogrula("transkripsiyon.crisper_dil_tespiti", "per_window") == "global_first_window"
    assert "kaldırıldı" in caplog.text and "was removed" in caplog.text
