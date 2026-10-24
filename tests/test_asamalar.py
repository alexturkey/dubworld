"""Stage building blocks (K8): file formats, subtitle writers, source check, CLI stage commands. GPU-free, offline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from dublaj_hatti import api, bicimler, kaynak_girdisi
from dublaj_hatti.asama_komutlari import ASAMA_KOMUTLARI
from dublaj_hatti.bicimler import BicimHatasi
from dublaj_hatti.cli import main as cli_main

ORNEK = {
    "schema": "dublaj-hatti/transcript@1",
    "language": "en",
    "segments": [
        {"start": 0.5, "end": 2.0, "text": "Welcome to the workshop.", "speaker": "SPEAKER_00",
         "words": [{"word": "Welcome", "start": 0.5, "end": 0.9, "score": 0.98},
                   {"word": "to", "start": 0.9, "end": 1.0}, {"word": "the", "start": 1.0, "end": 1.2},
                   {"word": "workshop.", "start": 1.3, "end": 2.0}]},
        {"start": 2.4, "end": 3.1, "text": "Let us begin."},
    ],
}


def test_dogrula_kabul_ve_ret():
    assert bicimler.dogrula(json.loads(json.dumps(ORNEK)))["language"] == "en"
    bozuk = json.loads(json.dumps(ORNEK))
    bozuk["segments"][0]["end"] = 0.1
    with pytest.raises(BicimHatasi, match=r"segments\[0\]"):
        bicimler.dogrula(bozuk)
    with pytest.raises(BicimHatasi, match="schema"):
        bicimler.dogrula({"segments": []})
    ceviri = {**ORNEK, "schema": "dublaj-hatti/translation@1"}
    with pytest.raises(BicimHatasi, match="source_language"):
        bicimler.dogrula(ceviri)


def test_whisperx_json_okunur(tmp_path: Path):
    yol = tmp_path / "wx.json"
    yol.write_text(json.dumps({"segments": [{"start": 0, "end": 1, "text": " hi ", "words": [
        {"word": "hi", "start": 0.1, "end": 0.4, "score": 0.9}]}], "language": "en"}), encoding="utf-8")
    veri = bicimler.transkript_oku(yol)
    assert veri["schema"] == bicimler.SEMA_TRANSKRIPT and veri["segments"][0]["text"] == "hi"


def test_sema_dosyalari_dogrulayici_ile_uyumlu():
    for ad, sema_id in (("transcript", bicimler.SEMA_TRANSKRIPT), ("translation", bicimler.SEMA_CEVIRI),
                        ("speech", bicimler.SEMA_SESLENDIRME)):
        sema = json.loads((bicimler.SEMA_KLASORU / f"{ad}.schema.json").read_text(encoding="utf-8"))
        assert sema["properties"]["schema"]["const"] == sema_id
    jsonschema = pytest.importorskip("jsonschema")
    sema = json.loads((bicimler.SEMA_KLASORU / "transcript.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(ORNEK, sema)


def test_srt_vtt_ass_ve_karaoke():
    srt = bicimler.altyazi_metni(ORNEK, "srt")
    assert srt.startswith("1\n00:00:00,500 --> 00:00:02,000\nWelcome to the workshop.\n")
    vtt = bicimler.altyazi_metni(ORNEK, "vtt", "karaoke")
    assert vtt.startswith("WEBVTT") and "Welcome <00:00:00.900>to" in vtt
    kelime = bicimler.altyazi_metni(ORNEK, "srt", "kelime")
    assert kelime.count("-->") == 5  # 4 words + the segment without word times
    ass = bicimler.altyazi_metni(ORNEK, "ass", "karaoke")
    satir = next(s for s in ass.splitlines() if s.startswith("Dialogue") and "Welcome" in s)
    assert satir.startswith("Dialogue: 0,0:00:00.50,0:00:02.00,Karaoke,") and "{\\k40}Welcome" in satir
    assert "{\\k10}" in satir  # the 0.1 s gap before "workshop." is kept as an empty karaoke step


def test_uzun_satir_iki_satira_bolunur():
    veri = {**ORNEK, "segments": [{"start": 0, "end": 3, "text": "This sentence is clearly longer than the usual "
                                                                 "forty two character subtitle line"}]}
    govde = bicimler.altyazi_metni(veri, "srt").split("\n")[2:4]
    assert all(govde) and abs(len(govde[0]) - len(govde[1])) < 12


def test_altyazi_yaz_atomik(tmp_path: Path):
    hedef = bicimler.altyazi_yaz(ORNEK, tmp_path / "a" / "b.vtt")
    assert hedef.read_text(encoding="utf-8").startswith("WEBVTT") and not list(tmp_path.rglob("*.part"))


def test_transkript_olustur_yol_sizdirmaz():
    veri = bicimler.transkript_olustur([], "tr", kaynak=str(Path("gizli") / "klasor" / "video.mp4"))
    assert veri["source"] == "video.mp4"


def test_kaynak_dogrula(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"\0")
    assert kaynak_girdisi.kaynak_dogrula(str(video)) == str(video.resolve())
    with pytest.raises(kaynak_girdisi.KaynakHatasi, match="bulunamadı"):
        kaynak_girdisi.kaynak_dogrula(str(tmp_path / "yok.mp4"))
    (tmp_path / "x.txt").write_text("a")
    with pytest.raises(kaynak_girdisi.KaynakHatasi, match="dosya türü"):
        kaynak_girdisi.kaynak_dogrula(str(tmp_path / "x.txt"))
    with pytest.raises(kaynak_girdisi.KaynakHatasi, match="https"):
        kaynak_girdisi.kaynak_dogrula("http://example.com/v.mp4")
    with pytest.raises(kaynak_girdisi.KaynakHatasi, match="desteklenmeyen bağlantı"):
        kaynak_girdisi.kaynak_dogrula("https://example.com/v.mp4")


def test_galeri_baglantisi_yt_dlp_istemez(monkeypatch: pytest.MonkeyPatch):
    """Gallery links need gallery-dl only; video-site links need yt-dlp only (inventory gap, fixed)."""
    from dublaj_hatti.bolum_10_kaynak_edinme.adim_20_kaynak_alma import galeri_indirici

    monkeypatch.setattr(kaynak_girdisi.importlib.util, "find_spec", lambda ad: None)  # yt-dlp "missing"
    monkeypatch.setattr(galeri_indirici, "galeri_kurulu", lambda: True)
    url = "https://www.instagram.com/reel/ornek/"
    assert kaynak_girdisi.kaynak_dogrula(url) == url
    with pytest.raises(kaynak_girdisi.KaynakHatasi, match="yt-dlp"):
        kaynak_girdisi.kaynak_dogrula("https://vimeo.com/123")
    monkeypatch.setattr(galeri_indirici, "galeri_kurulu", lambda: False)
    with pytest.raises(kaynak_girdisi.KaynakHatasi, match="gallery-dl"):
        kaynak_girdisi.kaynak_dogrula(url)


def test_api_sozlesmesi():
    for ad in api.__all__:
        assert hasattr(api, ad), ad
    assert {v["komut"] for v in api.ASAMALAR.values()} - {"dubla"} == set(ASAMA_KOMUTLARI)
    # importing the API must stay cheap: no torch / numpy at import time
    assert "torch" not in sys.modules or "dublaj_hatti.bolum_00_omurga.core.dubber" in sys.modules


def test_ayarlarla_katmani():
    with api.ayarlarla(ifadeler=["genel.cihaz=cpu"]):
        assert api._ayar(None)["genel.cihaz"] == "cpu"
        assert api._ayar(None, genel__cihaz="cuda")["genel.cihaz"] == "cuda"  # explicit stage argument wins
    assert api._KATMAN.get() == (None, ())  # the layer is gone after the block


def test_cli_altyazi_uctan_uca(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    girdi = tmp_path / "t.transcript.json"
    girdi.write_text(json.dumps(ORNEK), encoding="utf-8")
    assert cli_main(["altyazi", str(girdi), "--bicim", "ass", "--kip", "karaoke", "--json"]) == 0
    sonuc = json.loads(capsys.readouterr().out)
    assert sonuc["komut"] == "altyazi" and Path(sonuc["cikti"]).name == "t.transcript.ass"
    assert "\\k" in Path(sonuc["cikti"]).read_text(encoding="utf-8-sig")


def test_cli_asama_hata_kodlari(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    bozuk = tmp_path / "b.json"
    bozuk.write_text('{"schema": "x"}', encoding="utf-8")
    assert cli_main(["altyazi", str(bozuk)]) == 2
    assert cli_main(["birlestir", str(tmp_path / "yok.mp4"), "-o", str(tmp_path / "o.mp4"), "--ses", "a.wav"]) == 2
    assert "hata:" in capsys.readouterr().err


def test_ffmpeg_filtre_yolu_kacisi():
    yol = api._ffmpeg_filtre_yolu(Path("C:/a b/it's.ass"))
    assert yol.startswith("'") and "\\:" in yol and "\\'" in yol
