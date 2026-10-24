"""K2 ayar anahtarları, K5 dil/ses süzgeci, K7 motor × donanım: GPU'suz, ağsız, model indirmeyen testler.

Kurallar: docs/tarifler/kombinasyonlar.md, docs/diller.md, docs/sesler.md, docs/donanim.md.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from dublaj_hatti import kayit, yapilandirma
from dublaj_hatti.bolum_00_omurga.runtime import donanim
from dublaj_hatti.is_yurutucu import ayar_degisiklikleri
from dublaj_hatti.yapilandirma import AyarHatasi, ayarlari_yukle, uyumluluk_denetle

PAKET = Path(yapilandirma.__file__).resolve().parent
KOK = PAKET.parents[1]


def _bulgular(*ifadeler: str, seviye: str = "") -> list[str]:
    ayar = ayarlari_yukle()
    for ifade in ifadeler:
        anahtar, ham = ifade.split("=", 1)
        ayar[anahtar] = yapilandirma._deger_dogrula(anahtar, yapilandirma._metin_degeri_coz(anahtar, ham))
    return [str(b) for b in uyumluluk_denetle(ayar) if not seviye or b.seviye == seviye]


def _sabit(dosya: Path, ad: str):
    for dugum in ast.walk(ast.parse(dosya.read_text(encoding="utf-8"))):
        if isinstance(dugum, ast.Assign) and any(getattr(h, "id", "") == ad for h in dugum.targets):
            return ast.literal_eval(dugum.value)
    pytest.fail(f"{ad} bulunamadı: {dosya.name}")


# --- K2: yeni ayar anahtarları -----------------------------------------------------------------------------
def test_k2_anahtarlari_varsayilan_kapali_ve_semada():
    ayar = ayarlari_yukle()
    assert ayar["video.akilli_kare"] is False
    assert ayar["ses.cinsiyet_kipi"] == "konusmaci"
    assert (ayar["ses.kadin_ses"], ayar["ses.erkek_ses"]) == ("F1", "M1")
    assert ayar["ses.rvc_model"] == "" and ayar["ses.rvc_riza_onayi"] is False and ayar["ses.rvc_perde"] == 0
    assert ayar["ses.xtts_referans_ses"] == "" and ayar["ses.xtts_lisans_onayi"] is False


@pytest.mark.parametrize("ifade, beklenen", [
    ("ses.kadin_ses=M2", "ses.kadin_ses"),
    ("ses.erkek_ses=F1", "ses.erkek_ses"),
    ("ses.cinsiyet_kipi=cumle", "ses.cinsiyet_kipi"),
    ("ses.rvc_perde=30", "aralık dışı"),
    ("video.akilli_kare=belki", "true/false"),
])
def test_k2_tek_anahtar_dogrulamasi(ifade, beklenen):
    with pytest.raises(AyarHatasi, match=beklenen):
        ayarlari_yukle(ustune=[ifade])


@pytest.mark.parametrize("ifadeler, beklenen", [
    (["ses.rvc_model=model.pth"], "rıza onayı yok"),
    (["ses.motor=xtts"], "XTTS referans ses ister"),
    (["ses.motor=xtts", "ses.xtts_referans_ses=ben.wav", "genel.hedef_dil=sv"], "XTTS v2 'sv' dilini okuyamaz"),
    (["transkripsiyon.motor=crisperwhisper_turbo_ct2", "transkripsiyon.crisper_dil_tespiti=per_window"],
     "per_window' dil tespiti kipini desteklemez"),
    (["transkripsiyon.crisper_dil_tespiti=per_window"], "auto 'per_window'"),
    (["transkripsiyon.motor=whisperx", "transkripsiyon.model=distil-large-v3", "transkripsiyon.kaynak_dil=de"],
     "çok dilli yedeği yoktur"),
    (["transkripsiyon.motor=youtube_translate", "ileri.pyannote_konusmaci_ayrimi=true"], "konuşmacı ayrımı yapmaz"),
])
def test_yeni_hata_kurallari(ifadeler, beklenen):
    hatalar = _bulgular(*ifadeler, seviye="hata")
    assert any(beklenen in h for h in hatalar), hatalar
    with pytest.raises(AyarHatasi):
        ayarlari_yukle(ustune=ifadeler)


@pytest.mark.parametrize("ifadeler, beklenen", [
    (["ses.cinsiyet_kipi=segment", "ses.motor=voxcpm2"], "segment yalnız ses.motor=supertonic"),
    (["ses.cinsiyet_kipi=segment", "ses.konusmaci_sesleri=SPEAKER_00:M2"], "segment kipinde konuşmacı ayrımı yapılmaz"),
    (["ses.rvc_perde=3"], "yalnız ses.rvc_model doluyken"),
    (["ses.xtts_referans_ses=ben.wav"], "yalnız ses.motor=xtts"),
    (["video.akilli_kare=true", "genel.is_turu=transkript"], "transkript işinde yok sayılır"),
    (["transkripsiyon.motor=youtube_translate", "transkripsiyon.kaynak_dil=de"], "altyazı izinden gelir"),
    (["transkripsiyon.motor=crisperwhisper2_medium", "transkripsiyon.crisper_dil_tespiti=continuous_stream",
      "transkripsiyon.kaynak_dil=tr"], "yalnız global_first_window kipinde"),
])
def test_yeni_uyari_kurallari(ifadeler, beklenen):
    uyarilar = _bulgular(*ifadeler, seviye="uyari")
    assert any(beklenen in u for u in uyarilar), uyarilar
    assert not _bulgular(*ifadeler, seviye="hata")


def test_rizali_rvc_ve_onayli_xtts_saf_denetimden_gecer():
    assert not _bulgular("ses.rvc_model=model.pth", "ses.rvc_riza_onayi=true", seviye="hata")
    assert not _bulgular("ses.motor=xtts", "ses.xtts_referans_ses=ben.wav", "genel.hedef_dil=de", seviye="hata")


def test_konusmaci_sesleri_komut_satirindan():
    ayar = ayarlari_yukle(ustune=["ses.konusmaci_sesleri=SPEAKER_00:M2, SPEAKER_01:F3"])
    assert ayar["ses.konusmaci_sesleri"] == {"SPEAKER_00": "M2", "SPEAKER_01": "F3"}
    ayar = ayarlari_yukle(ustune=["ses.konusmaci_sesleri.SPEAKER_02=M4"])
    assert ayar["ses.konusmaci_sesleri"] == {"SPEAKER_02": "M4"}
    with pytest.raises(AyarHatasi, match="F1..F5 / M1..M5"):
        ayarlari_yukle(ustune=["ses.konusmaci_sesleri=SPEAKER_00:X9"])
    with pytest.raises(AyarHatasi, match="KONUSMACI:SES"):
        ayarlari_yukle(ustune=["ses.konusmaci_sesleri=SPEAKER_00"])
    assert yapilandirma.esleme_metni({"B": "M1", "A": "F2"}) == "A:F2, B:M1"


def test_arayuz_konusmaci_eslemesini_ayar_ifadesine_cevirir():
    ifadeler = ayar_degisiklikleri({"ses.konusmaci_sesleri": {"SPEAKER_00": "M2"}})
    assert ifadeler == ["ses.konusmaci_sesleri=SPEAKER_00:M2"]


def test_youtube_baglantisi_kurali():
    assert yapilandirma.youtube_baglantisi_mi("https://www.youtube.com/watch?v=x")
    assert yapilandirma.youtube_baglantisi_mi("https://youtu.be/x")
    assert not yapilandirma.youtube_baglantisi_mi("https://example.com/youtube.com")
    assert not yapilandirma.youtube_baglantisi_mi("C:/videolar/a.mp4")


def test_youtube_translate_yerel_dosyada_acik_hata(monkeypatch):
    ayar = ayarlari_yukle(ustune=["transkripsiyon.motor=youtube_translate"])
    with pytest.raises(AyarHatasi, match="yalnız YouTube bağlantısıyla"):
        yapilandirma._kurulum_denetle(ayar, "video.mp4", lambda _m: None)


def test_rvc_kurulu_degilse_ve_xtts_onaysizsa_acik_hata(monkeypatch):
    monkeypatch.delenv("DUBLAJ_RVC_KOK", raising=False)
    ayar = ayarlari_yukle(ustune=["ses.rvc_model=model.pth", "ses.rvc_riza_onayi=true"])
    with pytest.raises(AyarHatasi, match="RVC kurulu değil"):
        yapilandirma._kurulum_denetle(ayar, None, lambda _m: None)


def test_dubconfig_yeni_alanlari_tasir(monkeypatch):
    pytest.importorskip("numpy")
    pytest.importorskip("soundfile")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    donanim.cuda_calisiyor.cache_clear()
    ayar = ayarlari_yukle(ustune=["genel.cihaz=cpu", "ceviri.arka_uc=yerel", "ses.cinsiyet_kipi=segment",
                                  "ses.kadin_ses=F3", "ses.erkek_ses=M4", "video.akilli_kare=true"])
    cfg, cozum = yapilandirma.dubconfig_olustur(ayar)
    assert (cfg.cinsiyet_kipi, cfg.supertonic_kadin_ses, cfg.supertonic_erkek_ses) == ("segment", "F3", "M4")
    assert cfg.rvc_model_yolu == "" and cfg.xtts_referans_ses == ""
    assert any("cihaz=cpu" in g for g in cozum.gerekceler)
    assert any("faster_whisper_ctc (işlemci" in g for g in cozum.gerekceler)


# --- K5: dil ve ses matrisi ----------------------------------------------------------------------------
def test_dil_listeleri_motor_kodlariyla_ayni():
    xtts = _sabit(PAKET / "bolum_50_seslendirme" / "xtts_tts" / "api.py", "XTTS_DILLERI")
    assert set(xtts) == set(kayit.XTTS_DILLERI)
    supertonic = _sabit(PAKET / "bolum_50_seslendirme" / "supertonic_tts" / "runtime.py", "AVAILABLE_LANGS")
    assert set(supertonic) - {"na"} == set(kayit.SUPERTONIC_DILLERI)


def test_hedef_dil_suzgeci_her_tts_icin_tutarli():
    suzgec = kayit.tts_dil_suzgeci()
    assert set(suzgec) == set(kayit.adlar("tts", auto=False))
    for tts, v in suzgec.items():
        for dil in v["izinli"]:
            hatalar = _bulgular(f"ses.motor={tts}", "ses.xtts_referans_ses=ben.wav", f"genel.hedef_dil={dil}",
                                "ceviri.arka_uc=codex", seviye="hata")
            assert not [h for h in hatalar if "dilini okuyamaz" in h], (tts, dil, hatalar)
        disarida = sorted(set(kayit.tts_hedef_dilleri()) - set(v["izinli"]))
        for dil in disarida:
            hatalar = _bulgular(f"ses.motor={tts}", "ses.xtts_referans_ses=ben.wav", f"genel.hedef_dil={dil}",
                                "ceviri.arka_uc=codex", seviye="hata")
            assert any("dilini okuyamaz" in h for h in hatalar), (tts, dil)
    assert "zh" in suzgec["voxcpm2"]["izinli"] and "zh" not in suzgec["supertonic"]["izinli"]
    assert "tr" not in suzgec["voxcpm2"]["denenmemis"] and "sv" in suzgec["voxcpm2"]["denenmemis"]


def test_voxcpm2_hazir_sesleri_ve_belge_ayni():
    sesler_md = (KOK / "docs" / "sesler.md").read_text(encoding="utf-8")
    for ad in kayit.VOXCPM2_HAZIR_SESLER:
        assert f"hazir/{ad}" in sesler_md, ad
    assert yapilandirma.ayarlari_yukle()["ses.voxcpm2_ses"].split("/", 1)[1] in kayit.VOXCPM2_HAZIR_SESLER


def test_diller_belgesi_her_tts_dilini_listeler():
    diller_md = (KOK / "docs" / "diller.md").read_text(encoding="utf-8")
    for dil in kayit.tts_hedef_dilleri():
        assert f"| `{dil}` |" in diller_md, dil


# --- K7: motor × donanım -------------------------------------------------------------------------------
def test_her_motorun_donanim_alani_dolu():
    for m in kayit.MOTORLAR:
        assert m.cihaz in ("gpu", "cpu", "gpu+cpu", "bulut"), m.ad
        assert m.cpu in ("iyi", "çalışır", "yavaş", "çalışmaz", "bulut"), m.ad
        assert m.kanit in ("ölçüldü", "belgeye göre", "tahmin"), m.ad
        assert m.bellek, m.ad
        if m.cihaz == "gpu":
            assert m.cpu == "çalışmaz", m.ad


def test_donanim_belgesi_her_motoru_listeler():
    donanim_md = (KOK / "docs" / "donanim.md").read_text(encoding="utf-8")
    for m in kayit.MOTORLAR:
        assert f"`{m.ad}`" in donanim_md, m.ad


def test_motor_etiketleri():
    turbo, supertonic = kayit.motor("crisperwhisper_turbo_ct2"), kayit.motor("supertonic")
    assert donanim.motor_etiketi(turbo, "cpu", 0) == "CPU'da çalışmaz (NVIDIA GPU gerekir)"
    assert donanim.motor_etiketi(kayit.motor("demucs"), "cpu", 0) == "CPU'da yavaş"
    assert donanim.motor_etiketi(supertonic, "cpu", 0) == ""
    assert donanim.motor_etiketi(kayit.motor("crisperwhisper2_medium"), "cuda", 2048).startswith("VRAM yetmez")
    assert donanim.motor_etiketi(kayit.motor("crisperwhisper2_medium"), "cuda", 4096) == ""
    assert donanim.motor_etiketi(kayit.motor("codex"), "cuda", 4096).startswith("bulut")


def test_form_ek_bilgisi_motorlari_gizlemez(monkeypatch):
    monkeypatch.setattr(donanim, "gpu_bilgisi_hafif", lambda: (False, 0))
    ek = yapilandirma.form_ek_bilgisi()
    assert ek["transkripsiyon.motor"]["etiketler"]["crisperwhisper_turbo_ct2"].startswith("CPU'da çalışmaz")
    assert "supertonic" not in ek["ses.motor"]["etiketler"]
    assert ek["genel.hedef_dil"]["suzgec"]["anahtar"] == "ses.motor"
    assert "hazir/haber_spikeri" in ek["ses.konusmaci_sesleri"]["ses_secenekleri"]["voxcpm2"]


def test_cpu_gerekcesi_ve_auto_stt():
    assert "cpu" in donanim.cihaz_gerekcesi("cpu", "cpu")
    assert "GPU yok" in yapilandirma.stt_auto_gerekcesi("faster_whisper_ctc", "cpu")
    assert yapilandirma.stt_secimi_coz(ayarlari_yukle(), "cpu", "int8")[0] == "faster_whisper_ctc"
