"""`dubla kontrol` sonuç satırı ve arayüzün ilk açılış denetimi (docs/getting-started.md, AGENTS.md §3).

Geliştirici olmayan kullanıcı ve kurulumu yapan ajan aynı ölçütü okur: "SONUÇ / RESULT: ... HAZIR / READY".
"""

from __future__ import annotations

from dublaj_hatti import cli


def _rapor(**degis):
    rapor = {
        "ffmpeg": "x/ffmpeg.exe",
        "donanim": {"cuda": False, "torch": "2.8.0+cpu"},
        "stt": {"faster_whisper_ctc": True},
        "ceviri": {"yerel": True},
        "tts": {"supertonic": True},
        "ek": {"konusmaci_ayrimi": True},
    }
    rapor.update(degis)
    return rapor


def test_tam_kurulum_hazir(capsys):
    assert cli.onerilen_akis_eksikleri(_rapor()) == []
    cli._sonuc_yaz(_rapor(), "auto")
    cikti = capsys.readouterr().out
    assert "HAZIR / recommended flow READY" in cikti and "not / note" not in cikti


def test_eksik_parcalar_adlariyla(capsys):
    rapor = _rapor(ffmpeg="", tts={"supertonic": False}, ek={})
    assert cli.onerilen_akis_eksikleri(rapor) == ["ffmpeg", "supertonic", "konusmaci_ayrimi"]
    cli._sonuc_yaz(rapor, "auto")
    cikti = capsys.readouterr().out
    assert "EKSİK / MISSING: ffmpeg, supertonic, konusmaci_ayrimi" in cikti and "kur.cmd" in cikti
    assert cli.onerilen_akis_eksikleri(_rapor(ctc_modelleri={"en": True, "tr": False})) == ["CTC (tr)"]


def test_gpu_tekerlegi_calismiyorsa_not_cpu_seciminde_yok(capsys):
    rapor = _rapor(donanim={"cuda": False, "torch": "2.8.0+cu128"})
    cli._sonuc_yaz(rapor, "auto")
    assert "not / note" in capsys.readouterr().out
    cli._sonuc_yaz(rapor, "cpu")  # kullanıcı işlemciyi kendisi seçtiyse uyarı yok
    assert "not / note" not in capsys.readouterr().out


def test_arayuz_denetimi_ayni_olcutu_kullanir(monkeypatch):
    import pytest

    pytest.importorskip("tkinter")
    from dublaj_hatti import gui, kayit

    monkeypatch.setattr(kayit, "durum", lambda grup: {})
    eksik = gui.kurulum_eksikleri()
    assert {"faster_whisper_ctc", "yerel", "supertonic", "konusmaci_ayrimi"} <= set(eksik)
