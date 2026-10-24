# -*- coding: utf-8 -*-
from __future__ import annotations

from functools import lru_cache

import torch
import torchaudio
from torchaudio.transforms import Resample


TARGET_SAMPLE_RATE = 16000


@lru_cache(maxsize=4)
def load_mono_audio_16k(audio_path: str) -> torch.Tensor:
    audio, sample_rate = torchaudio.load(audio_path)
    if audio.ndim == 2 and audio.shape[0] > 1:
        audio = audio.mean(dim=0, keepdim=True)
    if sample_rate != TARGET_SAMPLE_RATE:
        audio = Resample(orig_freq=sample_rate, new_freq=TARGET_SAMPLE_RATE)(audio)
    return audio.mean(dim=0)


def slice_segment_audio(audio_path: str, start_seconds: float, end_seconds: float) -> torch.Tensor:
    audio = load_mono_audio_16k(audio_path)
    start_index = max(int(float(start_seconds) * TARGET_SAMPLE_RATE), 0)
    end_index = max(int(float(end_seconds) * TARGET_SAMPLE_RATE), start_index)
    return audio[start_index:end_index].unsqueeze(0)
