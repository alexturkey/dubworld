"""VoxCPM2 cinsiyete göre favori sesler, hat tarafı: liste → konuşmacı ataması → cümle sesi (GPU'suz).

Akış: ses.voxcpm2_kadin_sesleri / ses.voxcpm2_erkek_sesleri (boşsa hedef dilin hazır sesleri) → DubConfig →
konuşmacı yönlendirme (Supertonic ile aynı 3D-Speaker + cinsiyet yolu) → seg.voxcpm2_voice → VoxCPM2 okuma.
Ayar tarafı: tests/test_voxcpm2_favori_ayarlar.py.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("numpy")  # hat modülleri numpy ister; yalın CI'da ayar testleri ayrı dosyada koşar

from dublaj_hatti import kayit  # noqa: E402
from dublaj_hatti.bolum_00_omurga.core import dubber  # noqa: E402
from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.konusmaci_secimi import router  # noqa: E402
from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.konusmaci_secimi.voice_assignment import (  # noqa: E402
    assign_voice_ids_to_speakers,
)
from dublaj_hatti.bolum_50_seslendirme.voxcpm2_tts import api as voxcpm2_api  # noqa: E402

CINSIYET = {
    "SPEAKER_00": {"gender": "female"},
    "SPEAKER_01": {"gender": "male"},
    "SPEAKER_02": {"gender": "female"},
    "SPEAKER_03": {"gender": "male"},
    "SPEAKER_04": {"gender": "male"},
    "SPEAKER_05": {"gender": "unknown"},
}


def _sesler(sonuc: dict) -> dict[str, str]:
    return {k: v["voice_id"] for k, v in sonuc.items()}


# --- atama: liste sırayla dağıtılır, elle harita önce gelir ----------------------------------------------------

def test_favori_listeler_sirayla_dagitilir():
    sonuc = _sesler(assign_voice_ids_to_speakers(CINSIYET, female_pool=["ayse/2", "hazir/belgesel_hanim"],
                                                 male_pool=["ali/1", "hazir/haber_spikeri"]))
    assert sonuc == {"SPEAKER_00": "ayse/2", "SPEAKER_01": "ali/1", "SPEAKER_02": "hazir/belgesel_hanim",
                     "SPEAKER_03": "hazir/haber_spikeri", "SPEAKER_04": "ali/1",  # liste bitti, başa döndü
                     "SPEAKER_05": "ayse/2"}  # bilinmeyen cinsiyet kadın listesinden (Supertonic ile aynı kural)


def test_tek_kadin_tek_erkek_sesi():
    sonuc = _sesler(assign_voice_ids_to_speakers(CINSIYET, female_pool=["ayse/2"], male_pool=["ali/1"]))
    assert {sonuc[k] for k, v in CINSIYET.items() if v["gender"] == "male"} == {"ali/1"}
    assert {sonuc[k] for k, v in CINSIYET.items() if v["gender"] != "male"} == {"ayse/2"}


def test_elle_harita_once_gelir_ve_buyuk_harfe_cevrilmez():
    sonuc = assign_voice_ids_to_speakers(CINSIYET, {"SPEAKER_01": "Benim_Sesim/3"},
                                         female_pool=["ayse/2"], male_pool=["ali/1", "hazir/tok_anlatici"])
    assert sonuc["SPEAKER_01"]["voice_id"] == "Benim_Sesim/3"
    assert sonuc["SPEAKER_01"]["decision_source"] == "manual"
    assert sonuc["SPEAKER_03"]["voice_id"] == "ali/1"  # elle atanan konuşmacı sırayı kaydırmaz


def test_elle_atanan_ses_havuzdan_dusulur():
    sonuc = _sesler(assign_voice_ids_to_speakers({"A": {"gender": "male"}, "B": {"gender": "male"}}, {"A": "ali/1"},
                                                 female_pool=["ayse/2"], male_pool=["ali/1", "veli/1"]))
    assert sonuc == {"A": "ali/1", "B": "veli/1"}  # iki konuşmacı aynı sesi almaz


def test_bos_cinsiyet_listesi_obur_listeyi_kullanir():
    assert set(_sesler(assign_voice_ids_to_speakers(CINSIYET, female_pool=[], male_pool=["ali/1"])).values()) == {"ali/1"}
    with pytest.raises(ValueError):
        assign_voice_ids_to_speakers(CINSIYET, female_pool=[], male_pool=[])


def test_supertonic_davranisi_degismedi():
    sonuc = _sesler(assign_voice_ids_to_speakers(CINSIYET, {"SPEAKER_00": "m3", "SPEAKER_01": "yok"}))
    assert sonuc["SPEAKER_00"] == "M3"  # büyük harfe çevrilir
    assert sonuc["SPEAKER_01"] == "M1"  # geçersiz elle ses yok sayılır, havuzdan
    assert set(sonuc.values()) <= set(kayit.SUPERTONIC_SESLER)


def test_cumleye_voxcpm2_sesi_yazilir():
    segler = [SimpleNamespace(index=i, start=i, end=i + 1, speaker=k) for i, k in enumerate(["A", "B", "?"])]
    harita = {"A": {"voice_id": "ayse/2", "gender": "female"}, "B": {"voice_id": "ali/1", "gender": "male"}}
    plan = router.apply_voice_map_to_segments(segler, harita, voice_attr="voxcpm2_voice", fallback_voice_id="ayse/2")
    assert [s.voxcpm2_voice for s in segler] == ["ayse/2", "ali/1", "ali/1"]  # konuşmacısız cümle en yakından
    assert not any(hasattr(s, "supertonic_voice_id") for s in segler)
    assert plan[0]["voxcpm2_voice"] == "ayse/2"


# --- hat: konuşmacı aşaması VoxCPM2'de açılır, doğru listeler gider ------------------------------------------

def _cfg(**alanlar) -> dubber.DubConfig:
    cfg = dubber.DubConfig()
    cfg.tts_engine = "voxcpm2"
    cfg.konusmaci_basina_ses = True
    cfg.konusmaci_ses_yolu = "kaynak.wav"
    for ad, deger in alanlar.items():
        setattr(cfg, ad, deger)
    return cfg


def test_konusmaci_asamasi_voxcpm2de_acik():
    assert dubber._konusmaci_motoru(_cfg())
    assert not dubber._konusmaci_motoru(_cfg(tts_engine="ema_lightning"))
    assert not dubber._konusmaci_motoru(_cfg(konusmaci_basina_ses=False))


def test_konusmaci_kipi_listeleri_ve_alani_iletir(monkeypatch, tmp_path):
    gelen = {}
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts import konusmaci_secimi

    monkeypatch.setattr(konusmaci_secimi, "konusmaci_seslerini_ata", lambda **kw: gelen.update(kw))
    cfg = _cfg(voxcpm2_kadin_sesleri=["ayse/2"], voxcpm2_erkek_sesleri=["ali/1", "veli/1"],
               voxcpm2_konusmaci_sesleri={"SPEAKER_00": "can/1"})
    dubber._apply_konusmaci_basina_ses_if_needed([], cfg, str(tmp_path))
    assert gelen["female_pool"] == ["ayse/2"] and gelen["male_pool"] == ["ali/1", "veli/1"]
    assert gelen["voice_attr"] == "voxcpm2_voice"
    assert gelen["manual_voice_map"] == {"SPEAKER_00": "can/1"}


def test_segment_kipi_listenin_ilk_sesini_verir(monkeypatch, tmp_path):
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts import cinsiyet_secimi

    def sahte(segments, *_):
        for seg, cinsiyet in zip(segments, ["female", "male", "unknown"]):
            seg.gender = cinsiyet

    monkeypatch.setattr(cinsiyet_secimi, "apply_supertonic_segment_gender_routing", sahte)
    segler = [SimpleNamespace(index=i) for i in range(3)]
    cfg = _cfg(cinsiyet_kipi="segment", voxcpm2_kadin_sesleri=["ayse/2", "x/1"], voxcpm2_erkek_sesleri=["ali/1"])
    dubber._apply_konusmaci_basina_ses_if_needed(segler, cfg, str(tmp_path))
    assert [s.voxcpm2_voice for s in segler] == ["ayse/2", "ali/1", "ayse/2"]


def test_okuma_sesi_sirasi():
    cfg = SimpleNamespace(voxcpm2_konusmaci_sesleri={"A": "elle/1"}, voxcpm2_ses="tek/1")
    assert voxcpm2_api._segment_voice(SimpleNamespace(speaker="A", voxcpm2_voice="liste/1"), cfg) == "elle/1"
    assert voxcpm2_api._segment_voice(SimpleNamespace(speaker="B", voxcpm2_voice="liste/1"), cfg) == "liste/1"
    assert voxcpm2_api._segment_voice(SimpleNamespace(speaker="B"), cfg) == "tek/1"


def test_cumle_sesi_ara_kayittan_geri_gelir(tmp_path):
    seg = dubber.Segment(index=0, start=0.0, end=1.0, text="merhaba", speaker="SPEAKER_00")
    seg.voxcpm2_voice = "ayse/2"
    yol = dubber._write_transcription_checkpoint(str(tmp_path), [seg], "en", {})
    geri, _, _ = dubber._read_transcription_checkpoint(yol)
    assert geri[0].voxcpm2_voice == "ayse/2"  # devam ettirilen iş aynı sesle okur
