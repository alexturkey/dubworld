"""GPU'suz, ağsız, model indirmeyen birim testleri (CI ile aynı): `python -m pytest -m "not gpu and not slow"`."""

from __future__ import annotations

import pytest

from dublaj_hatti import kayit
from dublaj_hatti.yapilandirma import SEMA, AyarHatasi, ayarlari_ic_ice, ayarlari_yukle


def test_varsayilan_ayarlar_semaya_uyar():
    ayar = ayarlari_yukle()
    assert set(ayar) <= set(SEMA)
    assert ayar["genel.cihaz"] == "auto"
    assert ayar["ses.motor"] in kayit.adlar("tts")


def test_ust_katman_ezer_ve_tur_cevirir():
    ayar = ayarlari_yukle(ustune=["video.cq=30", "ses.atempo=false", "ses.hiz=1.1"])
    assert ayar["video.cq"] == 30
    assert ayar["ses.atempo"] is False
    assert ayar["ses.hiz"] == pytest.approx(1.1)


@pytest.mark.parametrize("ifade", ["video.cq=99", "genel.cihaz=tpu", "yok.boyle=1", "ses.hiz=hizli"])
def test_gecersiz_ayar_reddedilir(ifade):
    with pytest.raises((AyarHatasi, ValueError)):
        ayarlari_yukle(ustune=[ifade])


def test_ic_ice_donusum():
    ic = ayarlari_ic_ice(ayarlari_yukle())
    assert ic["ceviri"]["codex"]["akil_yurutme"] in ("low", "medium", "high")


def test_kayit_adlari_essiz_ve_bilgileri_dolu():
    adlar = [m.ad for m in kayit.MOTORLAR]
    assert len(adlar) == len(set(adlar))
    for motor in kayit.MOTORLAR:
        assert motor.tur in ("stt", "ceviri", "tts", "ek")
        assert motor.lisans and motor.kaynak.startswith("https://")
        assert motor.belge == f"docs/motorlar/{motor.ad}.md"


def test_sema_secenekleri_kayittan_gelir():
    assert SEMA["transkripsiyon.motor"] == kayit.adlar("stt")
    assert SEMA["ceviri.arka_uc"] == kayit.adlar("ceviri")


def test_her_ceviri_secenegi_kopruye_baglanir():
    from dublaj_hatti.bolum_40_ceviri.arka_uc_secimi import KOPRU_ADI, SECENEKLER
    from dublaj_hatti.bolum_40_ceviri.gorunum_adlari import bridge_backend_normalize

    assert set(SECENEKLER) == set(kayit.adlar("ceviri"))
    for ad, kopru in KOPRU_ADI.items():
        assert bridge_backend_normalize(ad) == kopru
        assert bridge_backend_normalize(kopru) == kopru


def test_arayuz_yalniz_degisenleri_gonderir():
    from dublaj_hatti.is_yurutucu import ARAYUZ_DISI_AYARLAR, FORM_DISI_AYARLAR, ayar_degisiklikleri, ayar_formu

    assert ayar_degisiklikleri({"video.cq": ayarlari_yukle()["video.cq"]}) == []
    assert ayar_degisiklikleri({"video.cq": 30, "ses.atempo": False}) == ["video.cq=30", "ses.atempo=false"]
    with pytest.raises(ValueError):
        ayar_degisiklikleri({"genel.cikti_klasoru": "a\nb"})
    form = ayar_formu()
    # eşleme (konuşmacı başına ses) dahil; yerel program yolları arayüzde yok (Düzeltme A, D2)
    assert {alan["anahtar"] for alan in form} == set(SEMA) - ARAYUZ_DISI_AYARLAR - FORM_DISI_AYARLAR
    esleme = next(alan for alan in form if alan["anahtar"] == "ses.konusmaci_sesleri")
    assert esleme["tur"] == "esleme" and esleme["deger"] == ""
    assert ayar_degisiklikleri({"ses.konusmaci_sesleri": ""}) == []  # boş eşleme = değişiklik yok
