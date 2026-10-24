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
MEDIUM_SRC = PAKET / "bolum_20_transkripsiyon" / "crisperwhisper2_medium_motoru" / "src"

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


# --- CrisperWhisper Medium (per_window + continuous_stream planlayıcıları) ------------------------------------
@pytest.fixture(scope="module")
def medium():
    pytest.importorskip("soundfile")
    return _modul(MEDIUM_SRC, "crisperwhisper_api_service")


@pytest.fixture(scope="module")
def medium_profil():
    return json.loads((MEDIUM_SRC / "configs" / "runtime_profile.json").read_text(encoding="utf-8"))


def test_medium_sabit_dil_kanit_uretir_puanlama_yok(medium):
    motor = SimpleNamespace(_lang_ids={"de": 1, "en": 2, "tr": 3},
                            get_language_id=lambda d: {"de": 1, "en": 2, "tr": 3}.get(d))
    adaylar, kabul = medium.platform_language_evidence(SimpleNamespace(_engine=motor), "en")
    assert adaylar == [{"language": "en", "token_id": 2, "probability": 1.0, "source": "platform_metadata"}]
    assert kabul == ["de", "en", "tr"]


def test_medium_surekli_planlayici_saniyede_bir(medium, medium_profil):
    tikler = medium.plan_continuous_language_ticks(np.zeros(10 * 16000, dtype=np.float32), medium_profil)
    assert [t["tick_center_seconds"] for t in tikler] == [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    assert tikler[0]["context_start_seconds"] == 0.0 and tikler[-1]["context_end_seconds"] == 10.0


def test_medium_surekli_son_kapsama_tiki(medium, medium_profil):
    tikler = medium.plan_continuous_language_ticks(np.zeros(round(17.928 * 16000), dtype=np.float32), medium_profil)
    assert tikler[-1]["tick_kind"] == "terminal_coverage"
    assert tikler[-1]["previous_tick_delta_seconds"] == pytest.approx(0.928)


def test_medium_degisim_noktasi_iki_ardisik_guvenli_tik_ister(medium, medium_profil):
    tespitler = [{"tick_index": i, "tick_center_seconds": float(i + 2), "detected_language": d, "confident": True}
                 for i, d in enumerate(["tr", "tr", "en", "en", "de"])]
    runs = medium.build_continuous_language_runs(tespitler, 8.0, medium_profil)
    assert [(r["detected_language"], r["start_seconds"], r["end_seconds"]) for r in runs] == [
        ("tr", 0.0, 3.5), ("en", 3.5, 8.0)]


def test_medium_ilk_dil_de_onay_ister(medium, medium_profil):
    tespitler = [
        {"tick_index": 0, "tick_center_seconds": 2.0, "detected_language": "tr", "confident": True},
        {"tick_index": 1, "tick_center_seconds": 3.0, "detected_language": "en", "confident": False},
    ]
    with pytest.raises(RuntimeError, match="no confirmed language sequence"):
        medium.build_continuous_language_runs(tespitler, 5.0, medium_profil)


def test_medium_pencere_basina_komsu_ayni_diller_birlesir(medium):
    tespitler = [
        {"window_index": 0, "start_seconds": 0.0, "end_seconds": 25.0, "detected_language": "tr", "selected_route": "a"},
        {"window_index": 1, "start_seconds": 25.0, "end_seconds": 50.0, "detected_language": "tr", "selected_route": "a"},
        {"window_index": 2, "start_seconds": 50.0, "end_seconds": 62.0, "detected_language": "en", "selected_route": "b"},
    ]
    runs = medium.build_language_runs(tespitler)
    assert [(r["detected_language"], r["start_seconds"], r["end_seconds"], r["window_count"]) for r in runs] == [
        ("tr", 0.0, 50.0, 2), ("en", 50.0, 62.0, 1)]


# --- elle sabit dil bütün motorlara ulaşır --------------------------------------------------------------------
def test_sabit_dil_platform_yolundan_iletilir():
    pytest.importorskip("soundfile")
    from dublaj_hatti.bolum_00_omurga.core.dubber import _sabit_dil_platform_yerine

    cfg = SimpleNamespace(whisper_language="tr")
    for motor in ("crisperwhisper_turbo_ct2", "crisperwhisper2_medium", "speechmatics", "elevenlabs_scribe_v2"):
        assert _sabit_dil_platform_yerine(motor, cfg, None) == "tr"
        assert _sabit_dil_platform_yerine(motor, cfg, "de") == "de"  # platform dili önceliklidir
    assert _sabit_dil_platform_yerine("faster-whisper", cfg, None) is None  # kendi yolu cfg.whisper_language
    assert _sabit_dil_platform_yerine("speechmatics", SimpleNamespace(whisper_language="auto"), None) is None
