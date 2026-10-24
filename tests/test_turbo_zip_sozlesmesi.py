"""CrisperWhisper Turbo CT2 runtime: zip(strict=...) sözleşmeleri (ruff B905).

- kelime ↔ ölçülmüş konuşma aralığı: boylar eşit olmalı (strict=True)
- ardışık kelime çiftleri: words[1:] bilerek bir kısa (strict=False)
- kaynak ↔ hizalanmış kelime: boy eşitliği zip'ten önce RuntimeError ile denetlenir (strict=True)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dublaj_hatti.bolum_00_omurga.runtime import crisperwhisper_turbo_ct2_runtime as turbo


def _kelimeler(n: int) -> list[dict]:
    # Kısa kelimeler (uzun kelime sınırı altında): yalnız boy ve sıra denetimi çalışır.
    return [{"word": f"k{i}", "start": i * 0.5, "end": i * 0.5 + 0.3} for i in range(n)]


def test_esit_boy_aralik_gecer():
    kelimeler = _kelimeler(3)
    turbo._validate_shared_alignment_words(kelimeler, 5.0, [None, (0.0, 0.4), None], {})


def test_aralik_verilmezse_her_kelimeye_none():
    turbo._validate_shared_alignment_words(_kelimeler(4), 5.0)


def test_eksik_aralik_listesi_sessizce_gecmez():
    # Eskiden kısa liste son kelimelerin denetimini sessizce atlardı; artık açık hata.
    with pytest.raises(ValueError):
        turbo._validate_shared_alignment_words(_kelimeler(3), 5.0, [None, None], {})


def test_tek_kelime_ardisik_cift_yok():
    turbo._validate_shared_alignment_words(_kelimeler(1), 5.0)


def test_son_ciftte_cakisma_yakalanir():
    kelimeler = _kelimeler(3)
    kelimeler[1]["end"] = kelimeler[2]["start"] + 0.1
    with pytest.raises(RuntimeError, match="overlap: 1"):
        turbo._validate_shared_alignment_words(kelimeler, 5.0)


def test_hizalama_kelime_sayisi_degisirse_zip_oncesi_durur(tmp_path: Path, monkeypatch):
    ctc = pytest.importorskip("dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama")

    def sahte_isci(*_args, **_kwargs):
        return {"words": _kelimeler(2), "command": ["sahte"]}

    monkeypatch.setattr(ctc, "run_ctc_word_alignment", sahte_isci)
    yanit = {"words": _kelimeler(3), "text": "k0 k1 k2", "physical_audio_seconds": 5.0, "language": "en"}
    with pytest.raises(RuntimeError, match="changed transcript"):
        turbo.align_dubbing_delivery(tmp_path / "yok.wav", tmp_path, yanit, 10)
