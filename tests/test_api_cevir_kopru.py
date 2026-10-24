"""api.cevir her çevirmen türüyle çağrılabilir (yerel: run_dir, LLM köprüsü: output_dir; ağsız, GPU'suz).

Kök neden (H1 gerçek LLM denemesi): api.cevir köprü çevirmenine `run_dir=` anahtar adıyla gidiyordu, köprünün
parametresi `output_dir` olduğundan `dubla cevir --arka-uc codex` TypeError ile düşüyordu.
"""

from __future__ import annotations

import inspect

import pytest

from dublaj_hatti import api, lisans_onayi


class KopruGibi:
    """BridgeMotorOrkestratoruTranslator.translate_segments imzası."""

    def __init__(self):
        self.klasor = None

    def translate_segments(self, segments, output_dir=None):
        self.klasor = output_dir
        return [f"[fr] {s.text}" for s in segments]


def test_api_cevir_kopru_imzasiyla_calisir(tmp_path, monkeypatch):
    from dublaj_hatti.bicimler import json_yaz, transkript_olustur
    from dublaj_hatti.bolum_00_omurga.core import dubber

    monkeypatch.setenv(lisans_onayi.ONAY_DOSYASI_ORTAM, str(tmp_path / "onay.json"))
    sahte = KopruGibi()
    monkeypatch.setattr(dubber, "_create_segment_translator", lambda *a, **k: sahte)
    monkeypatch.setattr(api, "_hazirla", lambda ayar: None)
    girdi = tmp_path / "t.json"
    json_yaz(girdi, transkript_olustur([{"start": 0.0, "end": 1.0, "text": "Hello."},
                                        {"start": 1.2, "end": 2.0, "text": "Thanks."}], "en"))
    cikti = api.cevir(girdi, tmp_path / "fr.json", hedef_dil="fr", arka_uc="codex", lisans_onay=True)
    veri = cikti.read_text(encoding="utf-8")
    assert "[fr] Hello." in veri and "[fr] Thanks." in veri
    assert sahte.klasor


def test_iki_cevirmen_ikinci_parametreyi_konumsal_alir():
    pytest.importorskip("numpy")
    from dublaj_hatti.bolum_40_ceviri.bridge_motor_orkestratoru.engine import BridgeMotorOrkestratoruTranslator
    from dublaj_hatti.bolum_40_ceviri.yerel_ceviri.engine import yerel_ceviri_translator

    for sinif in (BridgeMotorOrkestratoruTranslator, yerel_ceviri_translator):
        parametreler = list(inspect.signature(sinif.translate_segments).parameters.values())
        assert parametreler[2].kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY)
