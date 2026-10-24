"""pyannote kapılı (gated) model 401/403 hatası anlamlı, yol gösteren mesaja çevrilir."""
import pytest

worker = pytest.importorskip("dublaj_hatti.bolum_20_transkripsiyon.whisperx_motoru.worker")


@pytest.mark.parametrize("hata", [
    OSError("401 Client Error: Unauthorized for url: https://huggingface.co/api/models/x"),
    RuntimeError("403 Forbidden: Access to model x is restricted. You must accept the user conditions"),
    type("GatedRepoError", (Exception,), {})("Cannot access gated repo"),
])
def test_kapili_hata_anlamli_mesaj(hata):
    mesaj = worker.kapili_model_hatasi(hata)
    assert worker.DIARIZASYON_MODELI in mesaj
    assert "HF_TOKEN" in mesaj
    assert "ileri.pyannote_konusmaci_ayrimi=false" in mesaj


def test_baska_hata_dokunulmaz():
    assert worker.kapili_model_hatasi(ValueError("CUDA out of memory")) == ""
