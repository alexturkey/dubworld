"""Konuşmacı sesinden kadın/erkek tahmini (wav2vec2 XLSR-53, ses sınıflandırma).

Model: alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech (Apache-2.0; eğitim verisi
LibriSpeech, CC BY 4.0). Ağırlık repoda değildir; `scripts/kur.ps1 -Adim modeller` sabit commit + sha256
ile Hugging Face önbelleğine indirir. Çalışma anında ağdan indirme yapılmaz (local_files_only).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from time import perf_counter

import torch
import torch.nn.functional as F

MODEL_ID = "alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech"
MODEL_REVISION = "7a28165f33e1dbb37adbce09c0a9afcd6095dd4d"
SAMPLE_RATE = 16000


@dataclass(frozen=True)
class GenderPrediction:
    gender: str
    confidence: float


def get_gender_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _local_snapshot() -> Path:
    from huggingface_hub import snapshot_download

    try:
        path = Path(snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_files_only=True))
    except Exception as exc:
        raise FileNotFoundError(
            "Cinsiyet sınıflandırıcı modeli yok; kurulum: scripts/kur.ps1 -Adim modeller"
        ) from exc
    for name in ("config.json", "preprocessor_config.json", "model.safetensors"):
        if not (path / name).is_file():
            raise FileNotFoundError(f"Cinsiyet sınıflandırıcı dosyası eksik: {path / name}")
    return path


@lru_cache(maxsize=1)
def load_supertonic_gender_model():
    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

    path = _local_snapshot()
    extractor = AutoFeatureExtractor.from_pretrained(str(path), local_files_only=True)
    model = AutoModelForAudioClassification.from_pretrained(str(path), local_files_only=True, use_safetensors=True)
    model.eval()
    model.to(get_gender_device())
    return extractor, model


def _synchronize_device(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def predict_segment_gender(audio: torch.Tensor, timing_callback=None) -> GenderPrediction:
    """audio: [kanal, örnek] 16 kHz tensör."""
    if audio.ndim != 2:
        raise ValueError("Gender audio tensor sekli [channel, samples] olmali")
    device = get_gender_device()
    cache_before = load_supertonic_gender_model.cache_info()
    started = perf_counter()
    if timing_callback is not None:
        timing_callback("gender_model_load_started")
    extractor, model = load_supertonic_gender_model()
    cache_after = load_supertonic_gender_model.cache_info()
    if timing_callback is not None:
        timing_callback(
            "gender_model_load_completed",
            elapsed_seconds=round(perf_counter() - started, 6),
            cache_hit=cache_after.hits > cache_before.hits,
        )
    mono = audio.mean(dim=0).detach().cpu().numpy()
    inputs = extractor(mono, sampling_rate=SAMPLE_RATE, return_tensors="pt", padding=True)
    inputs = {key: value.to(device) for key, value in inputs.items()}
    started = perf_counter()
    if timing_callback is not None:
        timing_callback("gender_inference_started", sample_count=int(audio.shape[-1]))
    with torch.no_grad():
        logits = model(**inputs).logits
        probabilities = F.softmax(logits, dim=-1)[0]
        confidence_tensor, pred_tensor = probabilities.max(dim=-1)
    _synchronize_device(device)
    if timing_callback is not None:
        timing_callback(
            "gender_inference_completed",
            elapsed_seconds=round(perf_counter() - started, 6),
            sample_count=int(audio.shape[-1]),
        )
    label = str(model.config.id2label[int(pred_tensor.item())]).strip().lower()
    gender = label if label in {"female", "male"} else "unknown"
    return GenderPrediction(gender=gender, confidence=float(confidence_tensor.item()))
