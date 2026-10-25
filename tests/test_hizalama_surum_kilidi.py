"""Hugging Face CTC hizalama modelleri sabit bir commit'ten yüklenir; Hub'daki değişen "main" hiç çözülmez (ağsız).

Tablo (HF_CTC_SURUMLERI) kurulum manifestiyle (scripts/modeller.json) ve WhisperX'in varsayılan tablosuyla eşleşir;
kapı (hizalama_modelini_yukle) modeli sabit klasörden verir, eksikse ve çevrimdışıysa indirmeden durur.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from dublaj_hatti.bolum_00_omurga.runtime import ctc_model_durumu as md

KOK = Path(__file__).resolve().parents[1]


def test_kurulum_manifestindeki_commitlerle_ayni():
    manifest = json.loads((KOK / "scripts" / "modeller.json").read_text(encoding="utf-8"))
    commitler: dict[str, set[str]] = {}
    for d in manifest["dosyalar"]:
        r = re.match(r"https://huggingface\.co/([^/]+/[^/]+)/resolve/([0-9a-f]{40})/", d["url"])
        if r and d["adim"].startswith("hizalama"):
            commitler.setdefault(r.group(1), set()).add(r.group(2))
    assert commitler, "manifestte hizalama modeli yok"
    for ad, sha in commitler.items():
        assert sha == {md.HF_CTC_SURUMLERI[ad]}, ad


def test_her_hf_modeli_sabit():
    for tur, ad in [*md.SABIT_CTC_MODELLERI.values(), *md.ISTEGE_BAGLI_CTC_MODELLERI.values()]:
        if tur == "hf":
            assert ad in md.HF_CTC_SURUMLERI
    for ad in md.KUTU_OZEL_MODELLER.values():
        assert ad in md.HF_CTC_SURUMLERI
    assert all(re.fullmatch(r"[0-9a-f]{40}", sha) for sha in md.HF_CTC_SURUMLERI.values())


def test_whisperx_varsayilan_tablosunun_hepsi_sabit():
    alignment = pytest.importorskip("whisperx.alignment")  # torch + transformers: GPU/tam kurulumda koşar
    assert set(alignment.DEFAULT_ALIGN_MODELS_HF.values()) <= set(md.HF_CTC_SURUMLERI)


class _SahteWhisperx:
    def __init__(self):
        self.cagrilar = []

    def load_align_model(self, **kw):
        self.cagrilar.append(kw)
        return object(), {}


def _sabit_klasor(hf: Path, ad: str) -> Path:
    klasor = hf / "hub" / ("models--" + ad.replace("/", "--")) / "snapshots" / md.HF_CTC_SURUMLERI[ad]
    klasor.mkdir(parents=True)
    (klasor / "pytorch_model.bin").write_bytes(b"x")
    return klasor


def test_kapi_sabit_klasoru_verir(tmp_path):
    hf = tmp_path / "huggingface"
    klasor = _sabit_klasor(hf, md.SABIT_CTC_MODELLERI["tr"][1])
    sahte = _SahteWhisperx()
    md.hizalama_modelini_yukle(sahte, "tr", "cpu", hf)
    assert sahte.cagrilar == [{"language_code": "tr", "device": "cpu", "model_name": str(klasor),
                               "model_cache_only": True}]


def test_baska_commit_sayilmaz_ve_cevrimdisi_indirmez(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.delenv(md.CEVRIMICI_DEGISKENI, raising=False)
    hf = tmp_path / "huggingface"
    eski = hf / "hub" / "models--mpoyraz--wav2vec2-xls-r-300m-cv7-turkish" / "snapshots" / ("0" * 40)
    eski.mkdir(parents=True)
    (eski / "pytorch_model.bin").write_bytes(b"x")
    assert md.ctc_modeli_durumu("tr", hf)["kurulu"] is False
    sahte = _SahteWhisperx()
    with pytest.raises(md.CtcModeliEksikHatasi):
        md.hizalama_modelini_yukle(sahte, "tr", "cpu", hf)
    assert sahte.cagrilar == []


def test_ozel_model_de_sabit_klasorden(tmp_path):
    hf = tmp_path / "huggingface"
    klasor = _sabit_klasor(hf, md.KUTU_OZEL_MODELLER["id"])
    sahte = _SahteWhisperx()
    md.hizalama_modelini_yukle(sahte, "id", "cpu", hf)
    assert sahte.cagrilar[0]["model_name"] == str(klasor)
