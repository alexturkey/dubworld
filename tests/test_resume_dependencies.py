"""Devamda seçim değiştirme → aşama bağımlılığı (kaynak projedeki test_resume_dependencies karşılığı)."""

from __future__ import annotations

import itertools

import pytest

from dublaj_hatti.bolum_00_omurga.core.asama_sozlesmesi import PIPELINE_STAGES
from dublaj_hatti.is_yonetimi.bagimlilik import DEGISTIRILEMEZ, ETKI, ETKISIZ, devam_bagimliligi, etki_asamasi
from dublaj_hatti.yapilandirma import SEMA, ayarlari_yukle

SON = {kip: max(o for _, o, _ in asamalar) for kip, asamalar in PIPELINE_STAGES.items()}


def _onceki(kip: str, asama: str) -> int:
    sira = next(o for a, o, _ in PIPELINE_STAGES[kip] if a == asama)
    return max((o for _, o, _ in PIPELINE_STAGES[kip] if o < sira), default=0)


def _farkli_deger(anahtar: str, eski):
    kural = SEMA[anahtar]
    if isinstance(kural, list):
        return next(s for s in kural if s != eski)
    if kural is bool:
        return not eski
    if kural is int:
        return int(eski or 0) + 1
    if kural is float:
        return round(float(eski or 1.0) + 0.1, 3)
    if kural is dict:
        return {"SPEAKER_00": "baska"}
    return f"{eski}_degisik"


def test_her_ayar_anahtari_siniflandirilmis():
    """Şemaya yeni anahtar eklenince bu tablo da güncellenmeli (yoksa temkinli yol: kaynak videodan sonrası)."""
    for kip, tablo in ETKI.items():
        bilinen = set(tablo) | ETKISIZ | DEGISTIRILEMEZ | {"genel.dublaj_kipi", "ses_temizligi.kip"}
        eksik = [k for k in SEMA if k not in bilinen and not (k.startswith("ceviri.") and "ceviri.*" in tablo)]
        assert not eksik, f"{kip}: aşama etkisi tanımsız anahtarlar: {eksik}"
        for asama in tablo.values():
            assert asama == "" or any(a == asama for a, _, _ in PIPELINE_STAGES[kip]), asama


@pytest.mark.parametrize("kip", ["segment_sync", "full_text"])
def test_her_secim_kendi_bagimlilik_sinirina_geri_ceker(kip):
    eski = {**ayarlari_yukle(), "genel.dublaj_kipi": kip}
    for anahtar in SEMA:
        if anahtar in DEGISTIRILEMEZ or anahtar == "genel.dublaj_kipi":
            continue
        yeni = _farkli_deger(anahtar, eski.get(anahtar))
        plan = devam_bagimliligi(eski, {anahtar: yeni}, SON[kip])
        asama = etki_asamasi(anahtar, eski, {**eski, anahtar: yeni}, kip)
        beklenen = _onceki(kip, asama) if asama and any(a == asama for a, _, _ in PIPELINE_STAGES[kip]) else SON[kip]
        assert plan["effective_stage_order"] == beklenen, anahtar


@pytest.mark.parametrize("kip", ["segment_sync", "full_text"])
def test_iki_secimde_en_erken_bagimlilik_kazanir(kip):
    eski = {**ayarlari_yukle(), "genel.dublaj_kipi": kip}
    adaylar = ["genel.hedef_dil", "altyazi.mod", "video.cq", "transkripsiyon.model", "ses.atempo"]
    tek = {a: devam_bagimliligi(eski, {a: _farkli_deger(a, eski.get(a))}, SON[kip])["effective_stage_order"]
           for a in adaylar}
    for a, b in itertools.combinations(adaylar, 2):
        plan = devam_bagimliligi(eski, {a: _farkli_deger(a, eski.get(a)), b: _farkli_deger(b, eski.get(b))}, SON[kip])
        assert plan["effective_stage_order"] == min(tek[a], tek[b])


def test_degisiklik_yoksa_istenen_sinir_korunur_ve_etkisiz_ayar_geri_cekmez():
    eski = ayarlari_yukle()
    assert devam_bagimliligi(eski, {}, 12)["effective_stage_order"] == 12
    for anahtar in ETKISIZ:
        plan = devam_bagimliligi(eski, {anahtar: _farkli_deger(anahtar, eski.get(anahtar))}, 12)
        assert plan["effective_stage_order"] == 12, anahtar


def test_ses_temizligi_acilinca_kaynak_ses_yeniden_cikarilir_arka_plan_degisince_yalniz_miks():
    eski = {**ayarlari_yukle(), "ses_temizligi.kip": "original"}
    assert etki_asamasi("ses_temizligi.kip", eski, {**eski, "ses_temizligi.kip": "preserve_background"},
                        "segment_sync") == "kaynak_ses_cikarma"
    temiz = {**eski, "ses_temizligi.kip": "clean"}
    assert etki_asamasi("ses_temizligi.kip", temiz, {**temiz, "ses_temizligi.kip": "preserve_background"},
                        "segment_sync") == "arka_plan_miksi"


def test_transkripsiyon_motoru_ses_ayristirmayi_yalniz_hazirlik_sinifi_degisince_geri_ceker():
    acik = {**ayarlari_yukle(), "ses_temizligi.kip": "clean", "transkripsiyon.motor": "faster-whisper"}
    assert etki_asamasi("transkripsiyon.motor", acik, {**acik, "transkripsiyon.motor": "whisperx"},
                        "segment_sync") == "demucs_vokal_ayirma"
    kapali = {**acik, "ses_temizligi.kip": "original"}
    assert etki_asamasi("transkripsiyon.motor", kapali, {**kapali, "transkripsiyon.motor": "whisperx"},
                        "segment_sync") == "asr_sesi_hazirlama"


def test_kip_degisince_yalniz_ortak_kaynak_hazirlik_asamalari_korunur():
    eski = {**ayarlari_yukle(), "genel.dublaj_kipi": "segment_sync"}
    plan = devam_bagimliligi(eski, {"genel.dublaj_kipi": "full_text"}, 13)
    assert plan["effective_stage_order"] == 6  # transkripsiyon dahil ortak
    assert plan["target_pipeline_kind"] == "full_text"


def test_is_turu_devamda_degistirilemez():
    with pytest.raises(ValueError, match="değiştirilemez"):
        devam_bagimliligi(ayarlari_yukle(), {"genel.is_turu": "transkript"}, 9)


def test_bu_kipte_olmayan_asamayi_etkileyen_ayar_geri_cekmez():
    eski = {**ayarlari_yukle(), "genel.dublaj_kipi": "segment_sync"}
    deger = _farkli_deger("video.tam_metin_sure_uyumu", eski.get("video.tam_metin_sure_uyumu"))
    assert devam_bagimliligi(eski, {"video.tam_metin_sure_uyumu": deger}, 13)["effective_stage_order"] == 13
