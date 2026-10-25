"""`dubla ayir` / api.ayir iki stemi Demucs'un kendi klasöründen alır (ağsız, GPU'suz).

clean_audio_with_demucs ASR'ye hazır kopyayı (clean_source.wav) döndürür; arka plan onun yanında değil,
<iş>/demucs/htdemucs/<kaynak adı>/no_vocals.wav içindedir. Eskiden dönüş değerinin yanına bakılıyordu ve
iki stem varken "Demucs çıktısı eksik" hatası veriliyordu.
"""
import importlib.util
from pathlib import Path

import pytest

from dublaj_hatti import api

demucs_cleaner = pytest.importorskip(
    "dublaj_hatti.bolum_10_kaynak_edinme.adim_50_asr_sesi_hazirlama.demucs_cleaner"
)


def _sahte_demucs(audio_path, run_dir, demucs_model_name="htdemucs", **_):
    # Gerçek düzen: stemler model klasöründe, dönen dosya vokalin kopyası
    stemler = Path(run_dir) / "demucs" / demucs_model_name / Path(audio_path).stem
    stemler.mkdir(parents=True)
    (stemler / "vocals.wav").write_bytes(b"vokal")
    (stemler / "no_vocals.wav").write_bytes(b"arka")
    kopya = Path(run_dir) / "clean_source.wav"
    kopya.write_bytes(b"vokal")
    return str(kopya)


def test_ayir_iki_stemi_hedefe_tasir(monkeypatch, tmp_path):
    gercek_find_spec = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda ad, *a: object() if ad == "demucs" else gercek_find_spec(ad, *a))
    monkeypatch.setattr(api, "_lisans", lambda adlar, onay: None)
    monkeypatch.setattr(api, "_hazirla", lambda ayar: None)

    def sahte_ses_cikar(medya, hedef, **_):
        Path(hedef).write_bytes(b"kaynak")
        return Path(hedef)

    monkeypatch.setattr(api, "ses_cikar", sahte_ses_cikar)
    monkeypatch.setattr(demucs_cleaner, "clean_audio_with_demucs", _sahte_demucs)

    hedef = tmp_path / "is"
    sonuc = api.ayir(tmp_path / "v.mp4", hedef, cihaz="cpu")

    assert sonuc == {"vokal": hedef / "vocals.wav", "arka_plan": hedef / "background.wav"}
    assert sonuc["vokal"].read_bytes() == b"vokal"
    assert sonuc["arka_plan"].read_bytes() == b"arka"
    assert not list(hedef.glob(".ayir_*"))  # başarıda geçici klasör kalmaz
