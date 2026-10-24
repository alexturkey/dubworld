"""Smoke tests of examples/ (GPU-free, offline): model stages are replaced by fakes that write synthetic stage files,
so the glue of every example (argument handling, file names, stage order, formats) is exercised for real."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from dublaj_hatti import api, bicimler

ORNEKLER = Path(__file__).resolve().parents[1] / "examples"


def _yukle(goreli: str) -> ModuleType:
    yol = ORNEKLER / goreli
    spec = importlib.util.spec_from_file_location(yol.stem, yol)
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _sahte_transkript(medya, hedef, motor=None, dil=None, cihaz=None, srt=True, ayarlar=None):
    veri = bicimler.transkript_olustur(
        [{"start": 0.0, "end": 1.6, "text": "Hello there friend.",
          "words": [{"word": "Hello", "start": 0.0, "end": 0.4}, {"word": "there", "start": 0.5, "end": 0.9},
                    {"word": "friend.", "start": 1.0, "end": 1.6}]}],
        dil or "en", motor="sahte", kaynak=str(medya))
    hedef = bicimler.json_yaz(hedef, veri)
    if srt:
        bicimler.altyazi_yaz(veri, Path(hedef).with_suffix(".srt"))
    return hedef


@pytest.fixture
def sahte_api(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    cagrilar: dict[str, list] = {"seslendir": [], "birlestir": [], "cevir": []}

    def cevir(transkript, hedef, hedef_dil="tr", arka_uc="yerel", kaynak_dil=None, cihaz=None):
        girdi = bicimler.transkript_oku(transkript)
        segmentler = [{**s, "source_text": s["text"], "text": "Merhaba dostum."} for s in girdi["segments"]]
        cagrilar["cevir"].append(arka_uc)
        return bicimler.json_yaz(hedef, bicimler.transkript_olustur(
            segmentler, hedef_dil, sema=bicimler.SEMA_CEVIRI, kaynak_dil=girdi["language"]))

    def seslendir(girdi, hedef_klasor, motor="supertonic", ses=None, dil="tr", ayarlar=None):
        cagrilar["seslendir"].append((str(girdi), motor, ses))
        Path(hedef_klasor).mkdir(parents=True, exist_ok=True)
        return Path(hedef_klasor) / "speech.wav"

    def birlestir(video, hedef, **kw):
        cagrilar["birlestir"].append(kw)
        return Path(hedef)

    monkeypatch.setattr(api, "yaziya_dok", _sahte_transkript)
    monkeypatch.setattr(api, "cevir", cevir)
    monkeypatch.setattr(api, "seslendir", seslendir)
    monkeypatch.setattr(api, "birlestir", birlestir)
    return cagrilar


def test_ornek_01_altyazi(tmp_path: Path, sahte_api):
    assert _yukle("01_yalniz_altyazi/altyazi_cikar.py").main(["konusma.mp4", "--cikti", str(tmp_path)]) == 0
    assert (tmp_path / "konusma.srt").read_text(encoding="utf-8").startswith("1\n00:00:00,000 -->")
    assert (tmp_path / "konusma.vtt").read_text(encoding="utf-8").startswith("WEBVTT")


def test_ornek_02_podcast(tmp_path: Path, sahte_api):
    modul = _yukle("02_podcast_cevir/podcast_cevir.py")
    assert modul.main(["bolum.mp3", "--cikti", str(tmp_path), "--ses-adi", "M2"]) == 0
    ceviri = bicimler.transkript_oku(tmp_path / "translation.json")
    assert ceviri["source_language"] == "en" and ceviri["segments"][0]["source_text"] == "Hello there friend."
    assert "Merhaba" in (tmp_path / "subtitles.tr.srt").read_text(encoding="utf-8")
    assert sahte_api["seslendir"][-1][1:] == ("supertonic", "M2")
    assert modul.main(["bolum.mp3", "--cikti", str(tmp_path), "--ses-only"]) == 0  # reuses translation.json
    assert len(sahte_api["cevir"]) == 1


def test_ornek_03_metni_oku(tmp_path: Path, sahte_api):
    assert _yukle("03_metni_oku/metni_oku.py").main(["Merhaba.", "--cikti", str(tmp_path), "--ses", "F2"]) == 0
    assert sahte_api["seslendir"] == [("Merhaba.", "supertonic", "F2")]


def test_ornek_04_toplu(tmp_path: Path, sahte_api, monkeypatch: pytest.MonkeyPatch):
    klasor = tmp_path / "videolar"
    klasor.mkdir()
    for ad in ("a.mp4", "b.mkv", "c.wav", "not.txt"):
        (klasor / ad).write_bytes(b"\0")
    modul = _yukle("04_toplu_yaziya_dok/toplu_yaziya_dok.py")
    cikti = tmp_path / "out"
    assert modul.main([str(klasor), "--cikti", str(cikti)]) == 0
    assert sorted(p.name for p in cikti.glob("*.transcript.json")) == ["a.transcript.json", "b.transcript.json",
                                                                       "c.transcript.json"]

    def bozuk(medya, hedef, **kw):
        raise RuntimeError("model yok")

    (cikti / "b.transcript.json").unlink()
    monkeypatch.setattr(api, "yaziya_dok", bozuk)
    assert modul.main([str(klasor), "--cikti", str(cikti)]) == 1  # b fails, a and c are skipped, batch goes on
    satirlar = (cikti / "ozet.csv").read_text(encoding="utf-8").splitlines()
    assert satirlar[0].startswith("file,status") and any(",hata," in s for s in satirlar)
    assert sum(",atlandi," in s for s in satirlar) == 2


def test_ornek_05_karaoke(tmp_path: Path, sahte_api):
    assert _yukle("05_karaoke_altyazi/karaoke.py").main(["klip.mp4", "--cikti", str(tmp_path)]) == 0
    ass = (tmp_path / "klip.karaoke.ass").read_text(encoding="utf-8-sig")
    assert "{\\k40}Hello" in ass
    assert sahte_api["birlestir"][0]["yak"] is True


def test_ornek_readme_ve_yardim(capsys: pytest.CaptureFixture[str]):
    betikler = sorted(ORNEKLER.glob("0*/*.py"))
    assert len(betikler) == 5
    for betik in betikler:
        assert (betik.parent / "README.md").is_file()
        with pytest.raises(SystemExit) as cikis:
            _yukle(str(betik.relative_to(ORNEKLER))).main(["--help"])
        assert cikis.value.code == 0
    assert json.dumps(capsys.readouterr().out)  # help text printed
