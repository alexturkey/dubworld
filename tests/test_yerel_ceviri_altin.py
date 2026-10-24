"""Gerçek Opus-MT ile: Düzeltme A'nın (O2) sıralı / bütçeli toplu işi kısa girdide çeviriyi değiştirmedi.

Altın dosya eski motorla (sabit 16'lık toplu iş, sırasız) üretilen çevirilerle byte-aynıdır (dosyadaki açıklama).
Model diskte yoksa atlanır (CI model indirmez); işlemcide ≈ 10-20 sn.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ALTIN = Path(__file__).with_name("veri") / "opus_mt_kisa_girdi_altin.json"


@pytest.mark.slow
def test_kisa_girdide_ceviri_byte_ayni():
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    from dublaj_hatti.bolum_40_ceviri.yerel_ceviri import engine

    if not (engine.yerel_model_dizini("en", "tr") / "config.json").is_file():
        pytest.skip("Opus-MT en-tr modeli kurulu değil (scripts/kur.ps1 -Adim modeller)")
    veri = json.loads(ALTIN.read_text(encoding="utf-8"))
    cevirmen = engine.yerel_ceviri_translator("en", "tr", device="cpu")
    cikti = cevirmen.translate_texts(veri["girdiler"])
    assert [c.encode("utf-8") for c in cikti] == [c.encode("utf-8") for c in veri["ceviriler"]]
    assert max(cevirmen._token_sayisi(m) for m in veri["girdiler"]) <= engine.BOLME_ESIGI
