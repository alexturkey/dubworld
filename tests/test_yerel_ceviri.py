"""Yerel Opus-MT: boş model çıktısı kaynak metne sessizce dönmez, açık hata verir (ADR 0009). Model ve torch sahte."""

from __future__ import annotations

import contextlib
import sys
import types

import pytest

from dublaj_hatti.bolum_40_ceviri.yerel_ceviri import engine


class _SahteTokenizer:
    def __init__(self, ciktilar):
        self.ciktilar = list(ciktilar)

    def __call__(self, metinler, **_):
        self.son = list(metinler)
        return {}

    def batch_decode(self, _uretilen, **_):
        cikti, self.ciktilar = self.ciktilar[: len(self.son)], self.ciktilar[len(self.son):]
        return cikti


class _SahteModel:
    def generate(self, **_):
        return None


@pytest.fixture()
def cevirmen(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(inference_mode=contextlib.nullcontext))

    def kur(ciktilar):
        c = engine.yerel_ceviri_translator("en", "tr", device="cpu")
        c._model, c._tokenizer = _SahteModel(), _SahteTokenizer(ciktilar)
        return c

    return kur


def test_ceviri_ciktisi_doner(cevirmen):
    assert cevirmen(["Merhaba", "Nasılsın"]).translate_texts(["Hello", "", "How are you"]) == ["Merhaba", "", "Nasılsın"]


def test_bos_cikti_kaynaga_donmez_acik_hata(cevirmen):
    with pytest.raises(engine.YerelCeviriHatasi, match="segment no: 2"):
        cevirmen(["Merhaba", "   "]).translate_texts(["Hello", "Untranslated sentence"])
