"""Dil tespiti kipleri (docs/tarifler/dil_tespiti.md): GPU'suz, model indirmeyen, sahte modelli testler.

Kaynak uygulamanın dil tespiti testlerinden taşındı (CrisperWhisper Turbo CT2 `language_detection`, CrisperWhisper
Medium pencere/akış planlayıcıları) + elle sabit dilin platform yolundan iletilmesi.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

np = pytest.importorskip("numpy")

PAKET = Path(__file__).resolve().parents[1] / "src" / "dublaj_hatti"
TURBO_SRC = PAKET / "bolum_20_transkripsiyon" / "crisperwhisper_turbo_ct2_motoru" / "src"

PROFIL = {
    "global_first_window_seconds": 29.5,
    "context_seconds": 4.0,
    "tick_seconds": 1.0,
    "confirmation_ticks": 2,
    "minimum_top_probability": 0.6,
    "minimum_margin": 0.2,
}


def _modul(klasor: Path, ad: str):
    if str(klasor) not in sys.path:
        sys.path.insert(0, str(klasor))
    return importlib.import_module(ad)


class _DilModeli:
    """CT2 Whisper'ın detect_language arayüzünü taklit eder (sırayla verilen olasılık listeleri)."""

    def __init__(self, sonuclar):
        self._sonuclar = iter(sonuclar)
        self._engine = self
        self.model = self

    def extract_features(self, ses):
        return ses

    def detect_language(self, _ozellik):
        return [next(self._sonuclar)]

    def get_language_id(self, dil):
        return {"de": 1, "en": 2, "tr": 3}.get(dil)


def _sonuc(dil: str, olasilik: float = 0.9):
    ikinci = "en" if dil != "en" else "de"
    return [(f"<|{dil}|>", olasilik), (f"<|{ikinci}|>", 1.0 - olasilik)]


# --- CrisperWhisper Turbo CT2 ---------------------------------------------------------------------------
def test_turbo_global_ilk_pencere_tek_dil():
    ld = _modul(TURBO_SRC, "language_detection")
    runs, tespitler = ld.detect_language_runs(_DilModeli([_sonuc("tr")]), np.zeros(16000 * 8, dtype=np.float32),
                                              16000, "global_first_window", PROFIL)
    assert runs[0]["detected_language"] == "tr"
    assert (runs[0]["start_seconds"], runs[0]["end_seconds"]) == (0.0, 8.0)
    assert tespitler[0]["candidates"][0]["language"] == "tr"


def test_turbo_sabit_dil_tespiti_atlar():
    ld = _modul(TURBO_SRC, "language_detection")
    runs, tespitler = ld.platform_language_runs(_DilModeli([]), np.zeros(16000 * 8, dtype=np.float32), 16000, "en")
    assert runs[0]["detected_language"] == "en"
    assert runs[0]["language_source"] == "platform_metadata"
    assert tespitler[0]["detection_skipped"] is True
    assert tespitler[0]["processing_seconds"] == 0.0


def test_turbo_surekli_akis_kod_degisimi_orta_nokta_sinirlari():
    ld = _modul(TURBO_SRC, "language_detection")
    sirasi = ["tr"] * 4 + ["en"] * 4 + ["de"] * 5
    runs, tespitler = ld.detect_language_runs(_DilModeli([_sonuc(d) for d in sirasi]),
                                              np.zeros(16000 * 16, dtype=np.float32), 16000, "continuous_stream", PROFIL)
    assert [r["detected_language"] for r in runs] == ["tr", "en", "de"]
    assert [r["end_seconds"] for r in runs] == [5.5, 9.5, 16.0]
    assert len(tespitler) == 13
    assert all(r["decision_validated"] for r in runs)


# --- elle sabit dil bütün motorlara ulaşır --------------------------------------------------------------------
def test_sabit_dil_platform_yolundan_iletilir():
    pytest.importorskip("soundfile")
    from dublaj_hatti.bolum_00_omurga.core.dubber import _sabit_dil_platform_yerine

    cfg = SimpleNamespace(whisper_language="tr")
    for motor in ("crisperwhisper_turbo_ct2", "speechmatics", "elevenlabs_scribe_v2"):
        assert _sabit_dil_platform_yerine(motor, cfg, None) == "tr"
        assert _sabit_dil_platform_yerine(motor, cfg, "de") == "de"  # platform dili önceliklidir
    assert _sabit_dil_platform_yerine("faster-whisper", cfg, None) is None  # kendi yolu cfg.whisper_language
    assert _sabit_dil_platform_yerine("speechmatics", SimpleNamespace(whisper_language="auto"), None) is None
