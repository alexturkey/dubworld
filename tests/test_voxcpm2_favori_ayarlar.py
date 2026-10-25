"""VoxCPM2 favori ses ayarları: liste ayrıştırma, dil varsayılanı, tek ses, doğrulama (numpy'siz; CI'da da koşar).

Hat tarafı (atama, cümle sesi, ara kayıt): tests/test_voxcpm2_favori_sesler.py.
"""

from __future__ import annotations

import pytest

from dublaj_hatti import kayit, yapilandirma
from dublaj_hatti.yapilandirma import ayarlari_yukle, uyumluluk_denetle


def _ayar(*ifadeler: str) -> dict:
    ayar = ayarlari_yukle()
    ayar["ses.voxcpm2_kadin_sesleri"] = ayar["ses.voxcpm2_erkek_sesleri"] = ""  # yerel kullanici.toml etkilemesin
    ayar["ses.voxcpm2_ses"] = yapilandirma.VOXCPM2_VARSAYILAN_SES
    ayar["ses.konusmaci_sesleri"] = {}
    for ifade in ["ses.motor=voxcpm2", "genel.hedef_dil=tr", "ses.konusmaci_cinsiyetine_gore_ses=true", *ifadeler]:
        anahtar, ham = ifade.split("=", 1)
        ayar[anahtar] = yapilandirma._deger_dogrula(anahtar, yapilandirma._metin_degeri_coz(anahtar, ham))
    return ayar


# --- ayarlar: boş liste = hedef dilin hazır sesleri; kullanıcının listesi önce -----------------------------------

def test_turkce_varsayilan_listeler_hazir_seslerden():
    kadin, erkek, kaynak = yapilandirma.voxcpm2_havuzlari(_ayar())
    assert kaynak == "varsayilan"
    assert kadin == ["hazir/belgesel_hanim", "hazir/cekici_spiker"]
    assert erkek == ["hazir/haber_spikeri", "hazir/tok_anlatici", "hazir/gizemli_bilge"]
    for ses in kadin + erkek:  # liste cinsiyet tablosuyla tutarlı
        assert kayit.VOXCPM2_HAZIR_CINSIYET[ses[6:]] == ("female" if ses in kadin else "male")


def test_kullanici_listesi_virgulle_ayrilir():
    ayar = _ayar("ses.voxcpm2_kadin_sesleri=ayse/2,  hazir/belgesel_hanim", "ses.voxcpm2_erkek_sesleri=ali/1")
    assert yapilandirma.voxcpm2_havuzlari(ayar) == (["ayse/2", "hazir/belgesel_hanim"], ["ali/1"], "kullanici")
    yalniz_kadin = _ayar("ses.voxcpm2_kadin_sesleri=ayse/2")
    assert yapilandirma.voxcpm2_havuzlari(yalniz_kadin) == (["ayse/2"], ["ayse/2"], "kullanici")


@pytest.mark.parametrize("dil", ["en", "fr", "de", "es", "ru", "zh", "ja"])
def test_obur_dillerde_o_dilin_anlaticisi(dil):
    ayar = _ayar(f"genel.hedef_dil={dil}")
    assert yapilandirma.voxcpm2_tek_ses(ayar) == f"hazir/anlatici_{dil}"
    kadin, erkek, _ = yapilandirma.voxcpm2_havuzlari({**ayar, "ses.voxcpm2_ses": yapilandirma.voxcpm2_tek_ses(ayar)})
    assert erkek == [f"hazir/anlatici_{dil}"] and kadin == erkek
    uyarilar = [str(b) for b in uyumluluk_denetle(ayar) if b.seviye == "uyari"]
    assert any("hazır kadın sesi yok" in u and f"{dil}_belgesel_kadin" in u for u in uyarilar), uyarilar


def test_kullanicinin_tek_sesi_dile_gore_degismez():
    assert yapilandirma.voxcpm2_tek_ses(_ayar("genel.hedef_dil=en", "ses.voxcpm2_ses=ayse/2")) == "ayse/2"


def test_hazir_seslerin_cinsiyeti_tam():
    assert set(kayit.VOXCPM2_HAZIR_CINSIYET) == set(kayit.VOXCPM2_HAZIR_SESLER)


# --- doğrulama -----------------------------------------------------------------------------------------------

def _bul(ayar: dict, seviye: str) -> list[str]:
    return [str(b) for b in uyumluluk_denetle(ayar) if b.seviye == seviye]


def test_bilinmeyen_hazir_ses_hata():
    for anahtar in ("ses.voxcpm2_kadin_sesleri", "ses.voxcpm2_erkek_sesleri"):
        assert any("bilinmeyen hazır ses hazir/yok" in h for h in _bul(_ayar(f"{anahtar}=hazir/yok"), "hata"))
    harita = _ayar("ses.konusmaci_sesleri=SPEAKER_00:hazir/yok")
    assert any("ses.konusmaci_sesleri" in h for h in _bul(harita, "hata"))


def test_kendi_tasarlanan_ses_gecerli():
    ayar = _ayar("ses.voxcpm2_kadin_sesleri=ayse/2", "ses.voxcpm2_erkek_sesleri=ali/1",
                 "ses.konusmaci_sesleri=SPEAKER_00:veli/3")
    assert _bul(ayar, "hata") == []


def test_ters_cinsiyetli_hazir_ses_uyarir():
    uyarilar = _bul(_ayar("ses.voxcpm2_kadin_sesleri=hazir/haber_spikeri"), "uyari")
    assert any("öbür cinsiyetin" in u for u in uyarilar), uyarilar


def test_liste_baska_motorda_uyarir():
    uyarilar = _bul(_ayar("ses.motor=supertonic", "ses.voxcpm2_kadin_sesleri=ayse/2"), "uyari")
    assert any("yalnız ses.motor=voxcpm2" in u for u in uyarilar), uyarilar


def test_turkce_varsayilanda_uyari_yok():
    assert not [u for u in _bul(_ayar(), "uyari") if "VoxCPM2" in u]
