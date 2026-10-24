"""`auto` fallback = faster-whisper text + shared CTC word times (`faster_whisper_ctc`); offline, synthetic data only.

Covers: engine choice, timing-source table, CTC model presence check (pinned en/tr and unpinned languages),
`dubla kontrol` line, config-time check, and the dubber binding with a fake CTC box (no model, no audio model run).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dublaj_hatti import cli, kayit, yapilandirma
from dublaj_hatti.bolum_00_omurga.runtime import ctc_model_durumu as md
from dublaj_hatti.bolum_20_transkripsiyon import zaman_kaynaklari as zk
from dublaj_hatti.yapilandirma import ayarlari_yukle

KOK = Path(__file__).resolve().parents[1]


# --- engine choice ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(("ayar_motor", "cihaz", "turbo", "beklenen"), [
    ("auto", "cuda", True, "crisperwhisper_turbo_ct2"),
    ("auto", "cuda", False, "faster_whisper_ctc"),
    ("auto", "cpu", True, "faster_whisper_ctc"),
    ("auto", "cpu", False, "faster_whisper_ctc"),
    ("faster-whisper", "cpu", False, "faster-whisper"),  # explicit choice keeps Whisper's own times
    ("faster-whisper", "cuda", True, "faster-whisper"),
    ("faster_whisper_ctc", "cuda", True, "faster_whisper_ctc"),  # selectable explicitly as well
])
def test_motor_secimi(monkeypatch, ayar_motor, cihaz, turbo, beklenen):
    monkeypatch.setattr(yapilandirma, "crisper_turbo_kurulu", lambda: turbo)
    ayar = {"transkripsiyon.motor": ayar_motor, "transkripsiyon.model": "large-v3-turbo",
            "transkripsiyon.whisperx_profili": "auto"}
    assert yapilandirma.stt_secimi_coz(ayar, cihaz, "int8")[:2] == (beklenen, "large-v3-turbo"
                                                                     if beklenen != "crisperwhisper_turbo_ct2"
                                                                     else "CrisperWhisper2.0_turbo")


def test_auto_gerekcesi_ctc_der():
    for cihaz in ("cuda", "cpu"):
        metin = yapilandirma.stt_auto_gerekcesi("faster_whisper_ctc", cihaz)
        assert "faster_whisper_ctc" in metin and "CTC" in metin


def test_kayit_ve_sema():
    assert "faster_whisper_ctc" in kayit.adlar("stt")
    m = kayit.motor("faster_whisper_ctc")
    assert m.ticari == "evet" and m.cihaz == "gpu+cpu" and m.belge == "docs/motorlar/faster_whisper_ctc.md"
    assert (KOK / m.belge).is_file()
    ayarlari_yukle(ustune=["transkripsiyon.motor=faster_whisper_ctc"])  # schema accepts it


def test_zaman_tablosu():
    assert zk.zaman_kaynagi("faster_whisper_ctc").kaynak == "ctc_kutusu"
    assert zk.zaman_kaynagi("faster-whisper").kaynak == "whisper_dogal"


# --- CTC model presence -------------------------------------------------------------------------------------------
def _sahte_onbellek(tmp_path: Path, en: bool, tr: bool) -> Path:
    hf = tmp_path / "model_cache" / "huggingface"
    (hf / "hub").mkdir(parents=True)
    if en:
        yol = tmp_path / "model_cache" / "torch" / "hub" / "checkpoints" / md.SABIT_CTC_MODELLERI["en"][1]
        yol.parent.mkdir(parents=True)
        yol.write_bytes(b"x")
    if tr:
        snap = hf / "hub" / "models--mpoyraz--wav2vec2-xls-r-300m-cv7-turkish" / "snapshots" / "abc"
        snap.mkdir(parents=True)
        (snap / "pytorch_model.bin").write_bytes(b"x")
    return hf


def test_sabit_modeller_manifestle_ayni():
    manifest = json.loads((KOK / "scripts" / "modeller.json").read_text(encoding="utf-8"))
    hedefler = [d["hedef"] for d in manifest["dosyalar"] if d["adim"] == "hizalama"]
    assert any(h.endswith("/" + md.SABIT_CTC_MODELLERI["en"][1]) for h in hedefler)
    tr_klasor = "models--" + md.SABIT_CTC_MODELLERI["tr"][1].replace("/", "--")
    assert any(tr_klasor in h and h.endswith("/pytorch_model.bin") for h in hedefler)


@pytest.mark.parametrize(("en", "tr"), [(True, True), (True, False), (False, True), (False, False)])
def test_kontrol_ozeti(tmp_path, en, tr):
    assert md.kontrol_ozeti(_sahte_onbellek(tmp_path, en, tr)) == {"en": en, "tr": tr}


def test_sabit_model_eksikse_kurulum_adimini_soyler(tmp_path):
    hf = _sahte_onbellek(tmp_path, en=True, tr=False)
    assert md.ctc_modeli_gerekli("en-US", hf)["kurulu"] is True
    with pytest.raises(md.CtcModeliEksikHatasi) as hata:
        md.ctc_modeli_gerekli("tr", hf)
    metin = str(hata.value)
    assert md.KURULUM_ADIMI in metin and "transkripsiyon.motor=faster-whisper" in metin and "sessizce" in metin


def test_sabit_olmayan_dil_cevrimdisi_hata_cevrimici_gecer(tmp_path, monkeypatch):
    hf = _sahte_onbellek(tmp_path, en=True, tr=True)
    monkeypatch.setattr(md, "_varsayilan_model", lambda dil: ("hf", "ornek/wav2vec2-xx"))
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.delenv("DUBLAJ_CEVRIMICI", raising=False)
    with pytest.raises(md.CtcModeliEksikHatasi, match="DUBLAJ_CEVRIMICI=1"):
        md.ctc_modeli_gerekli("xx", hf)
    monkeypatch.setenv("DUBLAJ_CEVRIMICI", "1")
    assert md.ctc_modeli_gerekli("xx", hf)["kurulu"] is False  # the worker may download it


def test_bilinmeyen_dil_modeli(tmp_path, monkeypatch):
    monkeypatch.setattr(md, "_varsayilan_model", lambda dil: None)
    durum = md.ctc_modeli_durumu("xx", _sahte_onbellek(tmp_path, True, True))
    assert durum["kurulu"] is None and durum["sabit"] is False


# --- config-time check --------------------------------------------------------------------------------------------
def test_ayar_sabit_dilde_eksik_model_is_baslamadan_durur(tmp_path):
    hf = _sahte_onbellek(tmp_path, en=False, tr=True)
    ayar = ayarlari_yukle(ustune=["transkripsiyon.motor=faster_whisper_ctc", "transkripsiyon.kaynak_dil=en",
                                  f"genel.onbellek_klasoru={hf.as_posix()}"])
    with pytest.raises(yapilandirma.AyarHatasi, match="Kurulum"):
        yapilandirma._ctc_modeli_denetle(ayar, lambda metin: None)


def test_ayar_otomatik_dilde_eksik_model_uyarir(tmp_path):
    hf = _sahte_onbellek(tmp_path, en=True, tr=False)
    ayar = ayarlari_yukle(ustune=["transkripsiyon.motor=faster_whisper_ctc", f"genel.onbellek_klasoru={hf.as_posix()}"])
    gerekceler: list[str] = []
    yapilandirma._ctc_modeli_denetle(ayar, gerekceler.append)
    assert len(gerekceler) == 1 and "(tr)" in gerekceler[0] and md.KURULUM_ADIMI in gerekceler[0]


def test_kontrol_satiri(capsys):
    cli._kontrol_yaz({"surum": "0", "python": "3", "donanim": {}, "ffmpeg": "f", "stt": {}, "ceviri": {}, "tts": {},
                      "ek": {}, "ctc_modelleri": {"en": True, "tr": False}})
    cikti = capsys.readouterr().out
    assert "hizalama (CTC): en=var, tr=yok" in cikti and "UYARI" in cikti and "faster_whisper_ctc" in cikti


# --- dubber binding (fake CTC box) ---------------------------------------------------------------------------------
def _whisper_verisi() -> dict:
    kelimeler1 = [{"word": " İstanbul", "start": 1.0, "end": 1.4}, {"word": "'a", "start": 1.4, "end": 1.5},
                  {"word": " geldik.", "start": 1.5, "end": 2.0}]
    kelimeler2 = [{"word": " Sonra", "start": 3.0, "end": 3.3}, {"word": " gittik.", "start": 3.3, "end": 3.9}]
    return {"success": True, "detected_language": "tr", "total_words": 5, "segments": [
        {"index": 0, "start": 1.0, "end": 2.0, "text": " İstanbul'a geldik.", "words": kelimeler1},
        {"index": 1, "start": 2.5, "end": 2.5, "text": "  ", "words": []},
        {"index": 2, "start": 3.0, "end": 3.9, "text": " Sonra gittik.", "words": kelimeler2},
    ]}


def test_dubber_ctc_baglantisi(tmp_path, monkeypatch):
    dubber = pytest.importorskip("dublaj_hatti.bolum_00_omurga.core.dubber")
    from dublaj_hatti.bolum_30_hizalama_ve_segment import ctc_kelime_hizalama

    goren: dict = {}

    def sahte_ctc(audio, segments_json, language, cache_dir, timeout_seconds, device="cuda", debug_dir=None):
        pencereler = json.loads(Path(segments_json).read_text(encoding="utf-8"))
        goren.update(dil=language, cihaz=device, pencere=pencereler, zaman_asimi=timeout_seconds)
        kelimeler = [{"word": "İstanbul'a", "start": 1.12, "end": 1.48}, {"word": "geldik.", "start": 1.55, "end": 1.9},
                     {"word": "Sonra", "start": 3.05, "end": 3.28}, {"word": "gittik.", "start": 3.31, "end": 3.8}]
        return {"success": True, "words": kelimeler, "alignment_subprocess_seconds": 0.1, "profile_summary": {},
                "segments": [{"index": 0, "start": 1.12, "end": 1.9, "text": "İstanbul'a geldik.",
                              "words": kelimeler[:2], "speaker": ""},
                             {"index": 1, "start": 3.05, "end": 3.8, "text": "Sonra gittik.", "words": kelimeler[2:],
                              "speaker": ""}]}

    monkeypatch.setattr(ctc_kelime_hizalama, "run_ctc_word_alignment", sahte_ctc)
    monkeypatch.setattr(md, "ctc_modeli_gerekli", lambda dil, cache_dir=None, motor="": {"model": "sahte", "dil": dil})
    monkeypatch.setattr(dubber, "_audio_duration_seconds", lambda yol: 5.0)
    sonuc = dubber._faster_whisper_ctc_hizala(_whisper_verisi(), str(tmp_path / "a.wav"), str(tmp_path), None, "cpu",
                                              str(tmp_path / "hf"))
    assert goren["dil"] == "tr" and goren["cihaz"] == "cpu" and goren["zaman_asimi"] == 1800.0
    assert [p["text"] for p in goren["pencere"]] == ["İstanbul'a geldik.", "Sonra gittik."]  # empty window dropped
    assert sonuc["words"][0]["start"] == pytest.approx(1.12)  # CTC time, not Whisper's 1.0
    assert sonuc["word_timing_source"] == "ctc_kelime_hizalama" and sonuc["total_words"] == 4
    rapor = json.loads((tmp_path / "faster_whisper_ctc" / "report.json").read_text(encoding="utf-8"))
    assert rapor["text_identical"] is True and rapor["whisper_word_count"] == 5 and rapor["ctc_word_count"] == 4
    assert (tmp_path / "faster_whisper_ctc" / "whisper_dogal_kelimeler.json").is_file()


def test_dubber_model_yoksa_ctc_calismaz(tmp_path, monkeypatch):
    dubber = pytest.importorskip("dublaj_hatti.bolum_00_omurga.core.dubber")
    from dublaj_hatti.bolum_30_hizalama_ve_segment import ctc_kelime_hizalama

    def yasak(*a, **k):
        raise AssertionError("CTC must not run without its model")

    def eksik(dil, cache_dir=None, motor=""):
        raise md.CtcModeliEksikHatasi("eksik")

    monkeypatch.setattr(ctc_kelime_hizalama, "run_ctc_word_alignment", yasak)
    monkeypatch.setattr(md, "ctc_modeli_gerekli", eksik)
    with pytest.raises(md.CtcModeliEksikHatasi):
        dubber._faster_whisper_ctc_hizala(_whisper_verisi(), "a.wav", str(tmp_path), "tr", "cpu", str(tmp_path))


def test_dubber_yardimcilari():
    dubber = pytest.importorskip("dublaj_hatti.bolum_00_omurga.core.dubber")
    assert dubber.faster_whisper_ctc_metin_ayni([{"word": " 2"}, {"word": ",5"}], [{"word": "2,5"}])
    assert not dubber.faster_whisper_ctc_metin_ayni([{"word": "a"}, {"word": "b"}], [{"word": "a"}])
    with pytest.raises(RuntimeError, match="süresiz"):
        dubber.faster_whisper_ctc_pencereleri([{"start": 1.0, "end": 1.0, "text": "x"}])
    assert dubber.faster_whisper_ctc_zaman_asimi(3600, "cuda") == 1800.0
    assert dubber.faster_whisper_ctc_zaman_asimi(3600, "cpu") == 600.0 + 3600 * 3.0
    assert dubber._transcription_engine_contract_inputs("faster_whisper_ctc") == {
        "ctc_word_boundary_policy": dubber.CTC_WORD_BOUNDARY_POLICY}
    assert dubber._transcription_engine_contract_inputs("faster-whisper") == {}
    assert "faster_whisper_ctc" in dubber.ASR_LEADING_PAD_ENGINES
