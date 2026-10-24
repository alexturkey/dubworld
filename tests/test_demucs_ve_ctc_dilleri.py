"""Pinned Demucs weight and optional CTC language models; early stop when a CTC model is missing (GPU-free, offline).

- Demucs htdemucs used to download at run time through torch.hub (no sha256 pin). It is now in scripts/modeller.json
  (step "demucs", fetched by `kur.ps1 -Adim demucs`); a missing weight stops the job before Demucs starts.
- ja / zh CTC models are pinned in the optional step "hizalama-diller".
- With auto language, the faster-whisper worker checks the CTC model right after language detection, before any
  decoding (a missing model used to cost the whole transcription first).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import types
from pathlib import Path

import pytest

from dublaj_hatti.bolum_00_omurga.runtime import ctc_model_durumu as md

KOK = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((KOK / "scripts" / "modeller.json").read_text(encoding="utf-8"))["dosyalar"]
WORKER = KOK / "src" / "dublaj_hatti" / "bolum_20_transkripsiyon" / "faster_whisper_motoru" / "worker.py"
HTDEMUCS = "955717e8-8726e21a.th"  # demucs 4.0.1 remote/files.txt: hybrid_transformer/955717e8-8726e21a.th


def _indirici():
    spec = importlib.util.spec_from_file_location("modelleri_indir_test", KOK / "scripts" / "modelleri_indir.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_demucs_agirligi_manifestte_sabit():
    kayitlar = [k for k in MANIFEST if k["adim"] == "demucs"]
    assert len(kayitlar) == 1
    kayit = kayitlar[0]
    assert kayit["hedef"] == f"runtime_assets/model_cache/torch/hub/checkpoints/{HTDEMUCS}"
    assert re.fullmatch(r"[0-9a-f]{64}", kayit["sha256"])
    # torch.hub check_hash: the file name suffix is the sha256 prefix
    assert kayit["sha256"].startswith(HTDEMUCS.split("-")[1].split(".")[0])
    assert kayit["boyut"] > 50_000_000
    assert _indirici().https_dogrula(kayit["url"]) == kayit["url"]


def test_istege_bagli_ctc_modelleri_manifestle_ayni():
    hedefler = [k["hedef"] for k in MANIFEST if k["adim"] == "hizalama-diller"]
    for dil, (tur, ad) in md.ISTEGE_BAGLI_CTC_MODELLERI.items():
        assert tur == "hf", dil
        klasor = "models--" + ad.replace("/", "--")
        assert any(klasor in h and h.endswith("/pytorch_model.bin") for h in hedefler), dil
        assert any(klasor in h and h.endswith("/config.json") for h in hedefler), dil
    for kayit in (k for k in MANIFEST if k["adim"] == "hizalama-diller"):
        assert re.fullmatch(r"[0-9a-f]{64}", kayit["sha256"])
        assert "/resolve/" in kayit["url"] and "/main/" not in kayit["url"]


def test_kur_betigi_adimlari():
    metin = (KOK / "scripts" / "kur.ps1").read_text(encoding="utf-8-sig")
    assert "--adim demucs" in metin
    assert 'Adim "hizalama-diller"' in metin and "--adim hizalama-diller" in metin


def test_istege_bagli_dil_eksikse_adimi_soyler(tmp_path, monkeypatch):
    hf = tmp_path / "model_cache" / "huggingface"
    (hf / "hub").mkdir(parents=True)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.delenv("DUBLAJ_CEVRIMICI", raising=False)
    with pytest.raises(md.CtcModeliEksikHatasi) as hata:
        md.ctc_modeli_gerekli("ja", hf)
    assert "hizalama-diller" in str(hata.value)
    snap = hf / "hub" / ("models--" + md.ISTEGE_BAGLI_CTC_MODELLERI["zh"][1].replace("/", "--")) / "snapshots" / "c"
    snap.mkdir(parents=True)
    (snap / "pytorch_model.bin").write_bytes(b"x")
    assert md.ctc_modeli_gerekli("zh-CN", hf)["kurulu"] is True


def test_ticari_olmayan_varsayilan_model_notu(tmp_path, monkeypatch):
    hf = tmp_path / "hf"
    (hf / "hub").mkdir(parents=True)
    monkeypatch.setattr(md, "_varsayilan_model", lambda dil: ("torch", "wav2vec2_voxpopuli_base_10k_asr_fr.pt"))
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.delenv("DUBLAJ_CEVRIMICI", raising=False)
    with pytest.raises(md.CtcModeliEksikHatasi, match="CC BY-NC 4.0"):
        md.ctc_modeli_gerekli("fr", hf)


def test_demucs_modeli_yoksa_baslamadan_durur(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    from dublaj_hatti.bolum_10_kaynak_edinme.adim_50_asr_sesi_hazirlama import demucs_cleaner as dc

    monkeypatch.setattr(dc, "torch_home", lambda: tmp_path / "torch")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.delenv("DUBLAJ_CEVRIMICI", raising=False)
    with pytest.raises(dc.DemucsPreparationError, match="-Adim demucs"):
        dc.clean_audio_with_demucs(str(tmp_path / "yok.wav"), str(tmp_path / "is"))
    assert not (tmp_path / "is" / "demucs").exists()  # stopped before any work
    agirlik = tmp_path / "torch" / "hub" / "checkpoints" / dc.HTDEMUCS_AGIRLIK
    agirlik.parent.mkdir(parents=True)
    agirlik.write_bytes(b"x")
    dc.demucs_modeli_gerekli("htdemucs")  # present: no error
    monkeypatch.setenv("DUBLAJ_CEVRIMICI", "1")
    agirlik.unlink()
    dc.demucs_modeli_gerekli("htdemucs")  # downloads allowed on purpose: no error


def _sahte_moduller(monkeypatch, dil: str) -> dict:
    durum = {"cozuldu": False}

    def segmentler():
        durum["cozuldu"] = True
        raise AssertionError("decoding must not start when the CTC model is missing")
        yield  # pragma: no cover

    class SahteModel:
        feature_extractor = types.SimpleNamespace(mel_filters=types.SimpleNamespace(shape=(128,)))

        def __init__(self, *a, **k):
            pass

        def transcribe(self, *a, **k):
            return segmentler(), types.SimpleNamespace(language=dil)

    fw = types.ModuleType("faster_whisper")
    fw.WhisperModel = SahteModel
    fw.audio = types.SimpleNamespace(decode_audio=lambda *a, **k: [0.0])
    torch = types.ModuleType("torch")
    torch.manual_seed = lambda *_: None
    torch.cuda = types.SimpleNamespace(is_available=lambda: False, manual_seed_all=lambda *_: None)
    torch.backends = types.SimpleNamespace(cudnn=types.SimpleNamespace())
    torch.use_deterministic_algorithms = lambda *a, **k: None
    numpy = types.ModuleType("numpy")
    numpy.random = types.SimpleNamespace(seed=lambda *_: None)
    for ad, modul in (("faster_whisper", fw), ("torch", torch), ("numpy", numpy)):
        monkeypatch.setitem(sys.modules, ad, modul)
    return durum


def test_isci_dil_tespitinden_hemen_sonra_durur(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("fw_isci_test", WORKER)
    isci = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(isci)
    durum = _sahte_moduller(monkeypatch, "ja")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.delenv("DUBLAJ_CEVRIMICI", raising=False)
    cache = tmp_path / "hf"
    (cache / "hub").mkdir(parents=True)
    sonuc = isci.transcribe_audio("a.wav", "large-v3-turbo", "cpu", "int8", "auto", str(cache), ctc_denetimi=True)
    assert sonuc["success"] is False and sonuc["hata_turu"] == "ctc_modeli_eksik"
    assert sonuc["detected_language"] == "ja" and "hizalama-diller" in sonuc["error"]
    assert durum["cozuldu"] is False
