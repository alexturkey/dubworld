"""WhisperX'in fr/de/es/it varsayılan CTC modelleri (torchaudio VoxPopuli, CC BY-NC 4.0) lisans kapısından geçer.

Dil ayarda sabitse tek kapı (`lisans_onayi.kapi`) iş başında sorar; dil otomatikse modeli yükleyen her işçi
`ctc_lisans_denetle` ile onaysız yüklemeyi durdurur (Düzeltme A, O3). Ağsız, GPU'suz.
"""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

import pytest

from dublaj_hatti import lisans_onayi
from dublaj_hatti.bolum_00_omurga.runtime import ctc_model_durumu as md

SRC = Path(__file__).resolve().parents[1] / "src" / "dublaj_hatti"


@pytest.fixture(autouse=True)
def onay_dosyasi(tmp_path, monkeypatch):
    yol = tmp_path / "ayarlar" / "lisans_onaylari.json"
    monkeypatch.setenv(lisans_onayi.ONAY_DOSYASI_ORTAM, str(yol))
    monkeypatch.delenv(lisans_onayi.ONAY_ORTAM, raising=False)
    return yol


def _ayar(**ust):
    ayar = {"genel.is_turu": "dublaj", "genel.hedef_dil": "tr", "transkripsiyon.motor": "faster_whisper_ctc",
            "transkripsiyon.kaynak_dil": "auto", "ses.motor": "voxcpm2"}
    ayar.update(ust)
    return ayar


def test_ticari_olmayan_diller_ctc_modul_listesiyle_ayni():
    assert set(lisans_onayi.CTC_NC_DILLERI) == set(md.TICARI_OLMAYAN_VARSAYILAN_DILLER)
    for dil in lisans_onayi.CTC_NC_DILLERI:
        assert dil not in md.SABIT_CTC_MODELLERI and dil not in md.ISTEGE_BAGLI_CTC_MODELLERI


@pytest.mark.parametrize("dil,ad", [("fr", "whisperx_ctc_fr"), ("de-DE", "whisperx_ctc_de"), ("ES", "whisperx_ctc_es"),
                                    ("it_IT", "whisperx_ctc_it"), ("en", None), ("tr", None), ("ja", None), ("", None)])
def test_ctc_lisans_adi(dil, ad):
    assert lisans_onayi.ctc_lisans_adi(dil) == ad


def test_sabit_kaynak_dil_is_basinda_sorulur(onay_dosyasi):
    ayar = _ayar(**{"transkripsiyon.kaynak_dil": "fr"})
    with pytest.raises(lisans_onayi.LisansOnayiGerekli) as hata:
        lisans_onayi.kapi(ayar)
    assert [ad for ad, _ in hata.value.bekleyen] == ["whisperx_ctc_fr"]
    metin = hata.value.bekleyen[0][1]
    assert "CC BY-NC 4.0" in metin and "LİSANS" in metin and "LICENSE" in metin
    assert lisans_onayi.kapi(ayar, onay=True) == ["whisperx_ctc_fr"]
    assert lisans_onayi.kapi(ayar) == []
    veri = json.loads(onay_dosyasi.read_text(encoding="utf-8"))
    assert veri["whisperx_ctc_fr"]["lisans"] == lisans_onayi.CTC_NC_LISANSI


def test_hedef_dil_dublajda_sorulur_transkriptte_sorulmaz():
    assert "whisperx_ctc_de" in lisans_onayi.secili_motorlar(_ayar(**{"genel.hedef_dil": "de"}))
    ayar = _ayar(**{"genel.hedef_dil": "de", "genel.is_turu": "transkript"})
    assert "whisperx_ctc_de" not in lisans_onayi.secili_motorlar(ayar)


def test_ctc_kullanmayan_stt_kaynak_dil_icin_sormaz():
    ayar = _ayar(**{"transkripsiyon.motor": "faster-whisper", "transkripsiyon.kaynak_dil": "fr"})
    assert not any(a.startswith("whisperx_ctc_") for a in lisans_onayi.secili_motorlar(ayar))
    assert "whisperx_ctc_fr" in lisans_onayi.secili_motorlar(ayar, stt_motoru="whisperx")


def test_lisansli_dil_onaysiz_yuklenmez():
    with pytest.raises(lisans_onayi.LisansOnayiGerekli):
        md.ctc_lisans_denetle("fr")
    for dil in ("en", "tr", "ja", "zh", "id", "ru"):
        md.ctc_lisans_denetle(dil)  # temiz ya da sabitli: sormaz


def test_ortam_ve_kayitli_onay_gecer(monkeypatch):
    monkeypatch.setenv(lisans_onayi.ONAY_ORTAM, "1")
    md.ctc_lisans_denetle("it")
    monkeypatch.delenv(lisans_onayi.ONAY_ORTAM)
    md.ctc_lisans_denetle("it")  # kayda yazıldı


class _SahteWhisperx:
    def __init__(self):
        self.cagrilar = []

    def load_align_model(self, **kw):
        self.cagrilar.append(kw)
        return object(), {}


def test_ctc_iscisi_onaysiz_modeli_yuklemez():
    pytest.importorskip("numpy")  # worker imports numpy at module level; not installed in the CPU smoke CI
    isci = importlib.import_module("dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama.worker")
    sahte = _SahteWhisperx()
    with pytest.raises(lisans_onayi.LisansOnayiGerekli):
        isci.load_alignment_model(sahte, "fr", "cpu", "onbellek")
    assert sahte.cagrilar == []
    isci.load_alignment_model(sahte, "en", "cpu", "onbellek")
    assert sahte.cagrilar == [{"language_code": "en", "device": "cpu"}]


def test_her_varsayilan_model_yuklemesi_kapidan_gecer():
    """Statik: model_name'siz her whisperx load_align_model çağrısından hemen önce _ctc_lisans_denetle var."""
    bulunan = 0
    for yol in SRC.rglob("*.py"):
        satirlar = yol.read_text(encoding="utf-8").splitlines()
        for i, satir in enumerate(satirlar):
            if not re.search(r"\.load_align_model\(", satir):
                continue
            cagri = " ".join(satirlar[i:i + 6])
            if "model_name=" in cagri.split(")")[0]:
                continue
            bulunan += 1
            assert "_ctc_lisans_denetle(" in satirlar[i - 1], f"{yol.relative_to(SRC)}:{i + 1}"
    assert bulunan >= 5
