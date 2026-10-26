"""Seçenek kombinasyonu doğrulama katmanı: GPU'suz, ağsız, model indirmeyen testler.

Tablo ve tarifler: docs/tarifler/kombinasyonlar.md. Her "hata" kuralı için en az bir test vardır.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

from dublaj_hatti import yapilandirma
from dublaj_hatti.is_yurutucu import ayar_degisiklikleri, ayar_formu
from dublaj_hatti.yapilandirma import (
    SEMA,
    STT_SABIT_PROFIL,
    SUPERTONIC_DILLERI,
    AyarHatasi,
    ayarlari_yukle,
    stt_secimi_coz,
    uyumluluk_denetle,
)

PAKET = Path(yapilandirma.__file__).resolve().parent


def _bulgular(*ifadeler: str, seviye: str = "") -> list[str]:
    """Doğrulamayı atlayıp ham birleşimi denetler (hata kurallarını tek tek görmek için)."""
    ayar = ayarlari_yukle()
    for ifade in ifadeler:
        anahtar, ham = ifade.split("=", 1)
        ayar[anahtar] = yapilandirma._deger_dogrula(anahtar, yapilandirma._metin_degeri_coz(anahtar, ham))
    return [str(b) for b in uyumluluk_denetle(ayar) if not seviye or b.seviye == seviye]


def test_varsayilanlar_uyumlu_ve_uyarisiz():
    assert _bulgular() == []


def test_supertonic_dil_listesi_motorla_ayni():
    kaynak = (PAKET / "bolum_50_seslendirme" / "supertonic_tts" / "runtime.py").read_text(encoding="utf-8")
    for dugum in ast.walk(ast.parse(kaynak)):
        if isinstance(dugum, ast.Assign) and any(getattr(h, "id", "") == "AVAILABLE_LANGS" for h in dugum.targets):
            diller = set(ast.literal_eval(dugum.value))
            break
    else:
        pytest.fail("AVAILABLE_LANGS bulunamadı")
    assert diller - {"na"} == set(SUPERTONIC_DILLERI)


def test_toml_ve_sema_ayni_anahtarlar():
    with open(PAKET / "varsayilan.toml", "rb") as dosya:
        duz = yapilandirma._duzlestir(tomllib.load(dosya))
    assert set(duz) == set(SEMA)


def test_gelismis_formu_yeni_anahtarlari_gosterir():
    anahtarlar = {alan["anahtar"]: alan for alan in ayar_formu()}
    for anahtar in ("genel.transkript_bicimi", "transkripsiyon.whisperx_profili", "genel.hedef_dil"):
        assert anahtarlar[anahtar]["tur"] == "secim"
        assert anahtarlar[anahtar]["aciklama"], anahtar


@pytest.mark.parametrize(
    "ifadeler, beklenen",
    [
        (["genel.dublaj_kipi=full_text", "ses.motor=voxcpm2"], "full_text kipi yalnız Supertonic"),
        (["genel.dublaj_kipi=full_text", "ceviri.arka_uc=yerel"], "full_text kipi yalnız Codex"),
        (["genel.dublaj_kipi=full_text", "ceviri.arka_uc=groq_llama_4_scout"], "full_text kipi yalnız Codex"),
        (["ses.motor=supertonic", "genel.hedef_dil=zh"], "Supertonic 'zh' dilini okuyamaz"),
        (["ses.motor=voxcpm2", "genel.cihaz=cpu"], "VoxCPM2 NVIDIA GPU"),
        (["ceviri.arka_uc=yerel", "genel.hedef_dil=de"], "yalnız İngilizce → Türkçe"),
        (["ceviri.arka_uc=yerel", "transkripsiyon.kaynak_dil=ja"], "yalnız İngilizce kaynak"),
        (["transkripsiyon.motor=parakeet_cpu_align", "transkripsiyon.kaynak_dil=fr"], "yalnız İngilizce"),
        (["transkripsiyon.motor=crisperwhisper_turbo_ct2", "genel.cihaz=cpu"], "yalnız NVIDIA GPU"),
        (["transkripsiyon.motor=crisperwhisper_turbo_ct2", "ileri.pyannote_konusmaci_ayrimi=true"],
         "konuşmacı ayrımı yapmaz"),
        (["transkripsiyon.whisperx_profili=whisperx_engine_default_v1"], "yalnız transkripsiyon.motor=whisperx"),
        (["transkripsiyon.motor=whisperx", "transkripsiyon.hesap_tipi=float16",
          "transkripsiyon.whisperx_profili=whisperx_float32_quality_v1"], "hesap_tipi=float32"),
        (["video.politika=max_mb"], "1 ya da daha büyük"),
    ],
)
def test_uyumsuz_kombinasyon_acik_hata_verir(ifadeler, beklenen):
    hatalar = _bulgular(*ifadeler, seviye="hata")
    assert any(beklenen in h for h in hatalar), hatalar
    with pytest.raises(AyarHatasi, match="uyumsuz seçim"):
        ayarlari_yukle(ustune=ifadeler)


def test_arayuz_degisiklikleri_de_denetlenir():
    with pytest.raises(AyarHatasi, match="Supertonic"):
        ayar_degisiklikleri({"genel.hedef_dil": "zh", "ses.motor": "supertonic"})
    assert ayar_degisiklikleri({"genel.hedef_dil": "zh", "ses.motor": "voxcpm2"}) == [
        "genel.hedef_dil=zh", "ses.motor=voxcpm2"]


def test_supertonic_konusmaci_sesi_dogrulanir(tmp_path):
    dosya = tmp_path / "a.toml"
    dosya.write_text('[ses]\nmotor = "supertonic"\n[ses.konusmaci_sesleri]\nSPEAKER_00 = "hazir/haber_spikeri"\n',
                     encoding="utf-8")
    with pytest.raises(AyarHatasi, match="F1..F5"):
        ayarlari_yukle(dosya)
    dosya.write_text('[ses]\nmotor = "supertonic"\n[ses.konusmaci_sesleri]\nSPEAKER_00 = "M2"\n', encoding="utf-8")
    assert ayarlari_yukle(dosya)["ses.konusmaci_sesleri"] == {"SPEAKER_00": "M2"}


@pytest.mark.parametrize(
    "ifadeler, beklenen",
    [
        (["ceviri.arka_uc=yerel", "ses.akis=repair_3"], "ses.akis"),
        (["ileri.pyannote_konusmaci_ayrimi=true"], "yalnız whisperx"),
        (["transkripsiyon.motor=faster-whisper", "transkripsiyon.crisper_dil_tespiti=continuous_stream"],
         "yalnız CrisperWhisper"),
        (["transkripsiyon.model=distil-large-v3", "transkripsiyon.kaynak_dil=de"], "distil"),
        (["video.max_mb=100"], "video.politika=max_mb"),
        (["ses.motor=voxcpm2", "genel.hedef_dil=it"], "denenmedi"),
    ],
)
def test_etkisiz_secim_uyari_verir_ama_durdurmaz(ifadeler, beklenen):
    assert any(beklenen in u for u in _bulgular(*ifadeler, seviye="uyari"))
    ayarlari_yukle(ustune=ifadeler)


def test_transkript_isinde_dublaj_kurallari_uygulanmaz():
    ayarlari_yukle(ustune=["genel.is_turu=transkript", "genel.hedef_dil=zh", "ceviri.arka_uc=yerel"])


@pytest.mark.parametrize("motor", sorted(STT_SABIT_PROFIL))
def test_sabit_sozlesmeli_motor_kendi_modelini_alir(motor):
    ayar = ayarlari_yukle(ustune=[f"transkripsiyon.motor={motor}"])
    stt, model, hesap, profil = stt_secimi_coz(ayar, "cuda", "float16")
    assert (stt, (model, hesap), profil) == (motor, STT_SABIT_PROFIL[motor], "")


def test_auto_crisper_cozumu_sabit_modeli_kullanir(monkeypatch):
    # Önceki hata: auto -> crisperwhisper_turbo_ct2 seçiliyor ama model large-v3-turbo / float16 geçiyordu;
    # motor yalnız CrisperWhisper2.0_turbo + int8 kabul ettiği için GPU'da Önerilen akış düşüyordu.
    monkeypatch.setattr(yapilandirma, "crisper_turbo_kurulu", lambda: True)
    ayar = ayarlari_yukle()
    assert stt_secimi_coz(ayar, "cuda", "float16")[:3] == ("crisperwhisper_turbo_ct2", "CrisperWhisper2.0_turbo", "int8")
    assert stt_secimi_coz(ayar, "cpu", "int8")[:3] == ("faster_whisper_ctc", "large-v3-turbo", "int8")


def test_whisperx_profili_gecer():
    ayar = ayarlari_yukle(ustune=["transkripsiyon.motor=whisperx", "transkripsiyon.hesap_tipi=int8",
                                  "transkripsiyon.whisperx_profili=whisperx_engine_default_v1"])
    assert stt_secimi_coz(ayar, "cuda", "int8")[3] == "whisperx_engine_default_v1"


@pytest.mark.parametrize("ifade", ["transkripsiyon.kaynak_dil=English", "genel.transkript_bicimi=docx",
                                   "genel.hedef_dil=xx"])
def test_tekil_gecersiz_degerler(ifade):
    with pytest.raises(AyarHatasi):
        ayarlari_yukle(ustune=[ifade])


# Kaynak uygulamanın Telegram menüsündeki her seçim alanının (lisansı uygun olanlar) repo karşılığı.
# Bir seçenek kaynaktan gelip burada karşılığı yoksa test düşer (calisma/secenek_agaci.md ile aynı tablo).
KAYNAK_SECENEKLERI = {
    "genel.dublaj_kipi": ["segment_sync", "full_text"],
    "genel.transkript_bicimi": ["plain", "srt", "timestamped", "paragraph"],
    "genel.hedef_dil": ["tr", "en", "de", "fr", "es", "it", "pt", "ru", "ja", "ko", "zh", "ar"],
    "transkripsiyon.motor": ["whisperx", "faster-whisper", "parakeet_cpu_align",
                             "elevenlabs_scribe_v2",
                             "crisperwhisper_turbo_ct2"],
    "transkripsiyon.crisper_dil_tespiti": ["global_first_window", "continuous_stream"],
    "transkripsiyon.hesap_tipi": ["float32", "int8", "float16"],
    "transkripsiyon.whisperx_profili": ["auto", "whisperx_float32_quality_v1", "whisperx_engine_default_v1"],
    "ses_temizligi.kip": ["original", "clean", "preserve_background", "auto_background"],
    "ceviri.arka_uc": ["codex", "claude_code", "gemini_2_5_flash", "gemini_3_1_flash_lite_tier_1", "gemma_4_26b",
                       "groq_llama_4_scout", "mistral_nemo"],
    "ses.supertonic_ses": [f"F{i}" for i in range(1, 6)] + [f"M{i}" for i in range(1, 6)],
    "ses.akis": ["single_pass_10", "single_pass_2", "single_pass_1", "natural_blocks_1", "repair_3_light",
                 "repair_2_initial_1_repair_2", "repair_1", "repair_2", "repair_3", "repair_4", "repair_5",
                 "repair_6", "repair_7"],
    "altyazi.mod": ["none", "segment", "word", "rollup"],
    "video.politika": ["cq", "max_mb"],
    "video.tam_metin_sure_uyumu": ["audio_to_video", "video_to_audio"],
}
KAYNAK_TUR_ALANLARI = {"ses.atempo": bool, "ses.konusmaci_cinsiyetine_gore_ses": bool, "video.cq": int,
                       "video.max_mb": int, "transkripsiyon.model": str, "ileri.pyannote_konusmaci_ayrimi": bool}


@pytest.mark.parametrize("anahtar", sorted(KAYNAK_SECENEKLERI))
def test_kaynak_menu_secenekleri_eksiksiz(anahtar):
    assert set(KAYNAK_SECENEKLERI[anahtar]) <= set(SEMA[anahtar]), set(KAYNAK_SECENEKLERI[anahtar]) - set(SEMA[anahtar])


def test_kaynak_menu_tur_alanlari_var():
    for anahtar, tur in KAYNAK_TUR_ALANLARI.items():
        assert SEMA[anahtar] is tur, anahtar
