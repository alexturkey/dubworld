"""Gemini ailesi tek anahtar okur: algılama (arka_uc_secimi), köprü yapılandırması ve .env örneği aynı adı kullanır."""

from __future__ import annotations

import json
from pathlib import Path

from dublaj_hatti.bolum_40_ceviri import arka_uc_secimi

KOK = Path(__file__).resolve().parents[1]
GEMINI = ("gemini_2_5_flash", "gemini_3_1_flash_lite_tier_1", "gemma_4_26b")
ANAHTAR = "CODEX_BRIDGE_GEMINI_API_KEY"


def test_algilama_tek_anahtar(monkeypatch):
    for ad in GEMINI:
        assert arka_uc_secimi.API_ANAHTARI_DEGISKENLERI[ad] == (ANAHTAR,)
    monkeypatch.delenv(ANAHTAR, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY_" + "2", "eski")  # eski numaralı anahtar artık sayılmaz
    assert not arka_uc_secimi.api_anahtari_var("gemini_2_5_flash")
    monkeypatch.setenv(ANAHTAR, "x")
    assert arka_uc_secimi.api_anahtari_var("gemini_2_5_flash")


def test_kopru_ve_env_ornegi_ayni_ad():
    for ad in GEMINI:
        yol = KOK / "src/dublaj_hatti/bolum_40_ceviri/llm_kopru/backends" / ad / "backend_config.json"
        assert json.loads(yol.read_text(encoding="utf-8"))["api_key_env_names"] == [ANAHTAR]
    ornek = (KOK / ".env.example").read_text(encoding="utf-8")
    assert f"\n{ANAHTAR}=" in ornek and "GEMINI_API_KEY_" + "1" not in ornek
