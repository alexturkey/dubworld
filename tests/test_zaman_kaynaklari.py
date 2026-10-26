"""Timing sources: YouTube json3 caption parser / track choice and per-engine word-time source table.

Offline, no GPU. Every json3 payload below is synthetic (invented words, invented times); no real video content.
Tests that need numpy / soundfile / Pillow are skipped where those are not installed (CI venv is stdlib only).
Docs: docs/engineering/timing-sources.md (EN), docs/muhendislik/zaman_kaynaklari.md (TR).
"""

from __future__ import annotations

import ast
import json
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from dublaj_hatti import kayit
from dublaj_hatti.bolum_20_transkripsiyon import zaman_kaynaklari as zk
from dublaj_hatti.bolum_20_transkripsiyon.youtube_json3_kaynagi import engine as j3

PAKET = Path(__file__).resolve().parents[1] / "src" / "dublaj_hatti"

# Synthetic json3: two events with per-word offsets, one multi-word seg without offset, a non-speech cue,
# an HTML entity, a newline-only seg and an event without tStartMs (must be ignored).
SENTETIK_JSON3 = json.dumps({
    "wireMagic": "pb3",
    "events": [
        {"tStartMs": 500, "dDurationMs": 2000, "segs": [
            {"utf8": "alpha"}, {"utf8": " beta", "tOffsetMs": 300}, {"utf8": " gamma.", "tOffsetMs": 700}]},
        {"tStartMs": 1200, "segs": [{"utf8": "\n"}]},
        {"tStartMs": 3000, "dDurationMs": 1500, "segs": [{"utf8": "delta epsilon"}]},
        {"tStartMs": 4200, "segs": [{"utf8": "[Music]"}]},
        {"tStartMs": 4600, "segs": [{"utf8": "zeta &amp; eta", "tOffsetMs": 100}]},
        {"segs": [{"utf8": "orphan"}]},
        {"tStartMs": 6000, "segs": [{"utf8": "♪"}, {"utf8": "(laughs)"}, {"utf8": "theta!"}]},
    ],
})


def _bilgi(**izler):
    """Fake yt-dlp info dict: automatic_captions {lang: [{ext, url}]} plus manual subtitles that must be ignored."""
    return {
        "language": izler.pop("_dil", None),
        "subtitles": {"en": [{"ext": "json3", "url": "https://example.invalid/manual-en.json3"}]},
        "automatic_captions": {
            dil: [{"ext": ext, "url": f"https://example.invalid/{dil}.{ext}"} for ext in exts]
            for dil, exts in izler.items()
        },
    }


# --- json3 parser -------------------------------------------------------------------------------------------
def test_ayristirici_kelime_ve_ipucu():
    kelimeler = j3.parse_youtube_json3_words(SENTETIK_JSON3)
    assert [k["word"] for k in kelimeler] == [
        "alpha", "beta", "gamma.", "delta", "epsilon", "zeta", "&", "eta", "theta!"]
    assert [k["start_hint"] for k in kelimeler] == pytest.approx([0.5, 0.8, 1.2, 3.0, 3.0, 4.7, 4.7, 4.7, 6.0])
    assert [k["index"] for k in kelimeler] == list(range(1, 10))


def test_ayristirici_zamanlari_yalniz_ipucu_bitis_uretmez():
    for k in j3.parse_youtube_json3_words(SENTETIK_JSON3):
        assert "start" not in k and "end" not in k
        assert k["start_hint_role"] == "alignment_window_hint_only"
        assert k["official_boundary"] is False and k["source"] == "youtube_json3_text"


def test_ayristirici_konusma_disi_isaretleri_atar():
    metin = json.dumps({"events": [{"tStartMs": 0, "segs": [{"utf8": "[Applause]"}, {"utf8": "(sighs)"},
                                                          {"utf8": "♫"}, {"utf8": "   "}]}]})
    assert j3.parse_youtube_json3_words(metin) == []


def test_ayristirici_zaman_sirasina_dizer():
    metin = json.dumps({"events": [{"tStartMs": 2000, "segs": [{"utf8": "later"}]},
                                   {"tStartMs": 1000, "segs": [{"utf8": "earlier"}]}]})
    assert [k["word"] for k in j3.parse_youtube_json3_words(metin)] == ["earlier", "later"]


def test_ayristirici_bozuk_json_acik_hata():
    with pytest.raises(j3.YouTubeJson3Error, match="JSON3 parse"):
        j3.parse_youtube_json3_words("{not json")


# --- track choice (yt-dlp metadata only, official options) ----------------------------------------------------
def test_iz_secimi_yalniz_otomatik_json3(monkeypatch):
    istenen = []
    monkeypatch.setattr(j3, "_download_track_text", lambda url: istenen.append(url) or SENTETIK_JSON3)
    iz, kelimeler, ham = j3._select_strict_json3_track(_bilgi(_dil="de", de=["vtt", "srv3", "json3"], en=["json3"]))
    assert (iz.language, iz.source, iz.ext) == ("de", "automatic", "json3")
    assert istenen == ["https://example.invalid/de.json3"]  # manual subtitles and vtt/srv3 never requested
    assert kelimeler and ham == SENTETIK_JSON3


@pytest.mark.parametrize(("dil", "izler", "beklenen"), [
    ("fr-FR", {"en": ["json3"], "fr": ["json3"], "ar": ["json3"]}, "fr"),  # video language first (region dropped)
    ("ja", {"ar": ["json3"], "en-US": ["json3"]}, "en"),  # then English
    (None, {"zz": ["json3"], "ar": ["json3"]}, "ar"),  # no language and no English: alphabetical
])
def test_iz_secim_sirasi(dil, izler, beklenen):
    adaylar = j3._iter_json3_tracks(_bilgi(_dil=dil, **izler))
    assert adaylar[0].language == beklenen


def test_iz_secimi_json3_yoksa_yedek_bicim_yok(monkeypatch):
    monkeypatch.setattr(j3, "_download_track_text", lambda url: pytest.fail("no download expected"))
    with pytest.raises(j3.YouTubeJson3Error, match="bulunamadi"):
        j3._select_strict_json3_track(_bilgi(_dil="en", en=["vtt", "srv1", "srv2", "srv3", "ttml"]))


def test_iz_secimi_bos_json3_hata(monkeypatch):
    monkeypatch.setattr(j3, "_download_track_text", lambda url: json.dumps({"events": []}))
    with pytest.raises(j3.YouTubeJson3Error, match="temiz kelime yok"):
        j3._select_strict_json3_track(_bilgi(_dil="en", en=["json3"]))


def test_yt_dlp_yalniz_resmi_secenekler(monkeypatch):
    """extract_info(download=False) with quiet options; caption text fetched through YoutubeDL.urlopen."""
    cagrilar = []

    class SahteYDL:
        def __init__(self, secenekler):
            cagrilar.append(("init", dict(secenekler)))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=True):
            cagrilar.append(("extract_info", url, download))
            return {}

        def urlopen(self, url):
            cagrilar.append(("urlopen", url))
            return SimpleNamespace(read=lambda: SENTETIK_JSON3.encode("utf-8"))

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=SahteYDL))
    j3._extract_info("https://www.youtube.com/watch?v=sentetik")
    assert j3._download_track_text("https://example.invalid/en.json3") == SENTETIK_JSON3
    assert cagrilar[0] == ("init", {"quiet": True, "no_warnings": True, "skip_download": True})
    assert cagrilar[1] == ("extract_info", "https://www.youtube.com/watch?v=sentetik", False)
    assert cagrilar[2] == ("init", {"quiet": True, "no_warnings": True})
    assert cagrilar[3][0] == "urlopen"


@pytest.mark.parametrize(("adres", "beklenen"), [
    ("https://www.youtube.com/watch?v=x", True), ("https://youtu.be/x", True), ("https://m.youtube.com/x", True),
    ("https://youtube.com.example.invalid/x", False), ("https://notyoutube.com/x", False),
    ("https://example.invalid/youtube.com", False), ("", False),
])
def test_youtube_adresi_siki(adres, beklenen):
    assert j3.is_youtube_url(adres) is beklenen


def test_probe_youtube_degilse_ag_yok(monkeypatch):
    monkeypatch.setattr(j3, "_extract_info", lambda url: pytest.fail("no network expected"))
    assert j3.probe_youtube_json3("https://example.invalid/v") == {"ok": False, "reason": "not_youtube"}


def test_probe_uygun_iz(monkeypatch):
    monkeypatch.setattr(j3, "_extract_info", lambda url: _bilgi(_dil="en", en=["json3"]))
    monkeypatch.setattr(j3, "_download_track_text", lambda url: SENTETIK_JSON3)
    sonuc = j3.probe_youtube_json3("https://www.youtube.com/watch?v=sentetik")
    assert sonuc == {"ok": True, "reason": "ok", "language": "en", "source": "automatic", "format": "json3",
                     "word_count": 9}


# --- alignment windows, timeout, repair, 1:1 check -----------------------------------------------------------
def test_hizalama_pencereleri_ipucudan():
    kelimeler = j3.parse_youtube_json3_words(SENTETIK_JSON3)
    pencereler = j3._build_alignment_input_segments(kelimeler, audio_duration=8.0)
    assert [p["text"] for p in pencereler] == ["alpha beta gamma.", "delta epsilon zeta & eta theta!"]
    assert pencereler[0]["start"] == pytest.approx(0.25)  # first hint - 0.25 s
    assert pencereler[0]["end"] == pytest.approx(3.0)  # next window's first hint
    assert pencereler[-1]["end"] == pytest.approx(8.0)  # last window runs to the audio end


def test_hizalama_penceresi_uzun_boslukta_bolunur():
    kelimeler = [{"word": "one", "start_hint": 0.0}, {"word": "two", "start_hint": 3.0}]
    assert len(j3._build_alignment_input_segments(kelimeler, audio_duration=5.0)) == 2  # gap 3.0 s > 2.5 s


def test_hizalama_zaman_asimi_ses_suresine_gore():
    assert j3._calculate_alignment_timeout_seconds(30.0) == 120
    assert j3._calculate_alignment_timeout_seconds(60 * 60.0) == 90 + 60 * 8


def test_bire_bir_dogrulama_uyusmazlikta_durur():
    beklenen = [{"word": "alpha"}, {"word": "beta"}]
    with pytest.raises(j3.YouTubeJson3Error, match="uyusmadi"):
        j3._validate_aligned_words(beklenen, [{"word": "alpha", "start": 0.1, "end": 0.2}])
    with pytest.raises(j3.YouTubeJson3Error, match="eksik kelime zamani"):
        j3._validate_aligned_words(beklenen, [{"word": "Alpha,", "start": 0.1, "end": 0.2}, {"word": "beta"}])


def test_onarim_temiz_zamani_degistirmez_ve_bindirmeyi_ortadan_boler():
    temiz = [{"word": "a", "start": 1.0, "end": 1.1}, {"word": "b", "start": 1.2, "end": 1.4}]
    onarilmis, sayi = j3._repair_aligned_word_timeline(temiz)
    assert sayi == 0 and onarilmis == temiz
    onarilmis, sayi = j3._repair_aligned_word_timeline(
        [{"word": "l", "start": 2.0, "end": 2.8}, {"word": "r", "start": 2.6, "end": 3.0}])
    assert sayi == 1 and onarilmis[0]["end"] == onarilmis[1]["start"] == pytest.approx(2.7)


def test_onarim_butcesi_asilinca_olcu_buyuk():
    once = [{"word": "x", "start": 1.0, "end": 2.0}, {"word": "y", "start": 1.1, "end": 1.2}]
    sonra, _ = j3._repair_aligned_word_timeline(once)
    assert j3._calculate_max_timing_adjustment_seconds(once, sonra) > j3.MAX_AUTO_REPAIR_ADJUSTMENT_SECONDS


def test_onarim_json3_ve_ortak_kopya_ayni():
    """json3 keeps its own copy (stdlib import path); CrisperWhisper Turbo uses ctc_kelime_hizalama.zaman_onarimi."""
    pytest.importorskip("numpy")  # the ctc_kelime_hizalama package __init__ imports numpy
    from dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama import zaman_onarimi as ortak

    vakalar = [
        [{"word": "a", "start": 1.0, "end": 1.1}, {"word": "b", "start": 1.2, "end": 1.4}],
        [{"word": "a", "start": 5.0, "end": 5.3}, {"word": "b", "start": 5.6, "end": 5.4},
         {"word": "c", "start": 5.5, "end": 5.9}, {"word": "d", "start": 5.85, "end": 6.1}],
        [{"word": "a", "start": 1.0, "end": 2.0}, {"word": "b", "start": 1.1, "end": 1.2}],
        [{"word": "a", "start": 9.0, "end": 9.2}, {"word": "b", "start": 9.5, "end": 9.45}],
    ]
    for vaka in vakalar:
        assert j3._repair_aligned_word_timeline(vaka) == ortak.repair_aligned_word_timeline(vaka)
        onarilmis, _ = ortak.repair_aligned_word_timeline(vaka)
        assert j3._calculate_max_timing_adjustment_seconds(vaka, onarilmis) == pytest.approx(
            ortak.max_timing_adjustment_seconds(vaka, onarilmis))


def test_crisper_turbo_sozlesmesi_calisan_onarim_dosyasini_izler():
    kaynak = (PAKET / "bolum_00_omurga" / "runtime" / "crisperwhisper_turbo_ct2_runtime.py").read_text(encoding="utf-8")
    assert 'timeline_repair_source = ctc_box / "zaman_onarimi.py"' in kaynak
    assert "ctc_kelime_hizalama.zaman_onarimi import" in kaynak


def _wav_yaz(yol: Path, saniye: float) -> None:
    with wave.open(str(yol), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * saniye))


def test_json3_ucdan_uca_sahte_ctc(monkeypatch, tmp_path):
    """Full box offline: fake yt-dlp + fake CTC worker; final times come from the aligner, never from json3."""
    pytest.importorskip("soundfile")
    pytest.importorskip("numpy")
    from dublaj_hatti.bolum_30_hizalama_ve_segment import ctc_kelime_hizalama

    wav = tmp_path / "audio.wav"
    _wav_yaz(wav, 8.0)
    monkeypatch.setattr(j3, "_extract_info", lambda url: _bilgi(_dil="en", en=["json3"]))
    monkeypatch.setattr(j3, "_download_track_text", lambda url: SENTETIK_JSON3)
    goren = {}

    def sahte_ctc(audio_path, segments_json_path, language, cache_dir, timeout_seconds, device="cuda"):
        pencereler = json.loads(Path(segments_json_path).read_text(encoding="utf-8"))
        goren.update(dil=language, zaman_asimi=timeout_seconds, cihaz=device, pencere=len(pencereler))
        kelimeler, segmentler, t = [], [], 0.1
        for i, p in enumerate(pencereler):
            sw = []
            for metin in p["text"].split():
                sw.append({"word": metin, "start": round(t, 3), "end": round(t + 0.2, 3), "score": 0.9})
                t += 0.5
            kelimeler += sw
            segmentler.append({"index": i, "start": sw[0]["start"], "end": sw[-1]["end"], "text": p["text"], "words": sw})
        kelimeler[3]["end"] = kelimeler[4]["start"] + 0.05  # one small overlap the box must repair
        return {"success": True, "words": kelimeler, "segments": segmentler}

    monkeypatch.setattr(ctc_kelime_hizalama, "run_ctc_word_alignment", sahte_ctc)
    sonuc = j3.build_youtube_json3_transcript("https://www.youtube.com/watch?v=sentetik", str(tmp_path), str(wav),
                                              device="cpu", cache_dir=str(tmp_path / "cache"))
    assert goren == {"dil": "en", "zaman_asimi": 120, "cihaz": "cpu", "pencere": 2}
    rapor = sonuc["report"]
    assert rapor["word_timing_source"] == "ctc_kelime_hizalama"
    assert rapor["json3_timing_role"] == "alignment_window_hint_only"
    assert rapor["timing_repair_count"] == 1
    kelimeler = sonuc["words"]
    assert kelimeler[0]["start"] == pytest.approx(0.1)  # aligner time, not the 0.5 s json3 hint
    assert all(a["end"] <= b["start"] for a, b in zip(kelimeler, kelimeler[1:], strict=False))
    segment_kelimeleri = [k for s in sonuc["segments"] for k in s["words"]]
    assert segment_kelimeleri == kelimeler


# --- per-engine timing source table ---------------------------------------------------------------------------
def test_tablo_kayittaki_her_stt_motorunu_kapsar():
    assert set(zk.ZAMAN_KAYNAKLARI) == set(kayit.adlar("stt", auto=False))


@pytest.mark.parametrize("motor", sorted(zk.ZAMAN_KAYNAKLARI))
def test_tablo_koddaki_hizalayiciyla_eslesir(motor):
    """CTC-box engines call run_ctc_word_alignment in their timing code; native/provider engines never do."""
    z = zk.zaman_kaynagi(motor)
    metin = "".join((PAKET / yol).read_text(encoding="utf-8") for yol in z.kod)
    assert ("run_ctc_word_alignment" in metin) is (z.kaynak == "ctc_kutusu")
    assert ("whisperx_module.align(" in metin or "whisperx.align(" in metin) is (z.kaynak == "whisperx_hizalama")
    assert z.ctc is (z.kaynak in ("ctc_kutusu", "whisperx_hizalama"))


def test_ctc_disi_motorlar():
    ctc_disi = {m for m, z in zk.ZAMAN_KAYNAKLARI.items() if not z.ctc}
    assert ctc_disi == {"faster-whisper", "moonshine_medium_streaming_en",
                        "speechmatics", "elevenlabs_scribe_v2"}


def test_bilinmeyen_motor_acik_hata():
    with pytest.raises(KeyError, match="resolve 'auto' first"):
        zk.zaman_kaynagi("auto")


@pytest.mark.parametrize(("cihaz", "kurulu", "motor", "kaynak"), [
    ("cuda", True, "crisperwhisper_turbo_ct2", "ctc_kutusu"),
    ("cuda", False, "faster_whisper_ctc", "ctc_kutusu"),  # K24: auto fallback = faster-whisper text + CTC times
    ("cpu", True, "faster_whisper_ctc", "ctc_kutusu"),  # CrisperWhisper is GPU only
])
def test_auto_secimi_zaman_kaynagi(monkeypatch, cihaz, kurulu, motor, kaynak):
    from dublaj_hatti import yapilandirma

    monkeypatch.setattr(yapilandirma, "crisper_turbo_kurulu", lambda: kurulu)
    ayar = {"transkripsiyon.motor": "auto", "transkripsiyon.model": "large-v3-turbo",
            "transkripsiyon.whisperx_profili": "auto"}
    secilen = yapilandirma.stt_secimi_coz(ayar, cihaz, "int8")[0]
    assert secilen == motor and zk.zaman_kaynagi(secilen).kaynak == kaynak


# --- dub-side subtitle timing contract (every segment TTS engine) ---------------------------------------------
def _ast_sabiti(yol: Path, ad: str):
    for dugum in ast.parse(yol.read_text(encoding="utf-8")).body:
        if isinstance(dugum, ast.Assign) and any(getattr(h, "id", None) == ad for h in dugum.targets):
            return ast.literal_eval(dugum.value)
    raise AssertionError(f"{ad} not found in {yol}")


def test_her_segment_tts_motoru_altyazi_sozlesmesinde():
    dubber = PAKET / "bolum_00_omurga" / "core" / "dubber.py"
    motorlar = _ast_sabiti(dubber, "SEGMENT_TTS_ENGINES")
    desteklenen = _ast_sabiti(PAKET / "bolum_50_seslendirme" / "altyazili_dublaj" / "timing_contract.py",
                              "SUPPORTED_ENGINES")
    klasorler = _ast_sabiti(PAKET / "bolum_50_seslendirme" / "final_dub_alignment" / "writer.py", "ENGINE_DEBUG_DIRS")
    etiketler = _ast_sabiti(dubber, "ALTYAZI_MOTOR_ETIKETI")
    assert motorlar <= desteklenen and motorlar <= set(klasorler) and motorlar == set(etiketler)
    # Sözleşme ve hata ayıklama klasörü yalnız hattın çalıştırdığı motorları tanır (kaldırılan motor anahtarı yok).
    assert desteklenen == motorlar and set(klasorler) == motorlar
    assert "prepare_supertonic_subtitle_burnin_assets" not in dubber.read_text(encoding="utf-8")


@pytest.mark.parametrize("motor", ["supertonic", "voxcpm2", "xtts"])
def test_altyazi_sozlesmesi_motor_adiyla_yazilir_ve_okunur(monkeypatch, tmp_path, motor):
    pytest.importorskip("PIL")
    from dublaj_hatti.bolum_50_seslendirme.altyazili_dublaj import burnin, timing_contract
    from dublaj_hatti.bolum_50_seslendirme.final_dub_alignment.writer import (
        ENGINE_DEBUG_DIRS,
        write_final_dub_alignment_debug,
    )

    run = tmp_path / "run"
    (run / "final_dub_alignment").mkdir(parents=True)
    kanit = run / "final_dub_alignment" / "alignment_result.json"
    kanit.write_text("{}", encoding="utf-8")
    segmentler = [SimpleNamespace(index=1, start=0.0, end=1.2, text="alpha beta", speaker="", gender="")]
    kelimeler = [{"word": "alpha", "start": 0.1, "end": 0.5, "segment_index": 1},
                 {"word": "beta", "start": 0.6, "end": 1.1, "segment_index": 1}]
    yollar = write_final_dub_alignment_debug(str(run), "tr", segmentler, kelimeler, engine=motor)
    sozlesme = timing_contract.write_subtitle_timing_contract(
        run_dir=str(run), language="tr", engine=motor, timing_source="final_dub_audio_forced_alignment",
        timing_method="final_timeline_clean_dub_audio_forced_alignment",
        word_timeline_path=yollar["engine_word_timeline_path"], timing_report_path=yollar["engine_timing_report_path"],
        verification_evidence_paths=[str(kanit)])
    monkeypatch.setattr(burnin, "probe_video_size", lambda yol: (1920, 1080))
    rapor = burnin.prepare_subtitle_burnin_assets(
        str(tmp_path / "in.mp4"), str(tmp_path / "out.mp4"), str(run), "tr", "segment", [], "one_pass_final_mux",
        engine=motor, debug_dir_name=ENGINE_DEBUG_DIRS[motor], engine_label=motor, timing_contract_path=sozlesme)
    assert rapor["enabled"] and Path(rapor["ass_path"]).is_file()
    assert rapor["timing_source"] == "final_dub_audio_forced_alignment"
