from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from .policy import SUPERTONIC_ATEMPO_MAX_FACTOR, SUPERTONIC_ATEMPO_MIN_FACTOR
from dublaj_hatti.bolum_00_omurga.runtime.arac_yolu import ffmpeg_yolu


def _validate_audio(wav_array: np.ndarray, sample_rate: int) -> None:
    if not isinstance(wav_array, np.ndarray):
        raise TypeError("Supertonic atempo sesi numpy.ndarray olmali")
    if wav_array.dtype != np.float32:
        raise TypeError("Supertonic atempo sesi float32 olmali")
    if wav_array.ndim != 1:
        raise ValueError("Supertonic atempo sesi mono olmali")
    if wav_array.size == 0:
        raise ValueError("Supertonic atempo sesi bos olamaz")
    if not np.isfinite(wav_array).all():
        raise ValueError("Supertonic atempo sesi sonlu orneklerden olusmali")
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate <= 0:
        raise ValueError("Supertonic atempo sample_rate pozitif int olmali")


def _validate_factor(factor: float) -> float:
    numeric_factor = float(factor)
    if not math.isfinite(numeric_factor):
        raise ValueError("Supertonic atempo faktoru sonlu olmali")
    if numeric_factor < SUPERTONIC_ATEMPO_MIN_FACTOR or numeric_factor > SUPERTONIC_ATEMPO_MAX_FACTOR:
        raise ValueError(
            "Supertonic atempo faktoru "
            f"{SUPERTONIC_ATEMPO_MIN_FACTOR:.2f}-{SUPERTONIC_ATEMPO_MAX_FACTOR:.2f} araliginda olmali"
        )
    return round(numeric_factor, 6)


def process_supertonic_atempo_audio(
    wav_array: np.ndarray,
    sample_rate: int,
    factor: float,
) -> np.ndarray:
    _validate_audio(wav_array, sample_rate)
    requested_factor = _validate_factor(factor)
    if requested_factor == 1.0:
        return wav_array.copy()

    with tempfile.TemporaryDirectory(prefix="supertonic_atempo_") as temporary_directory:
        temporary_path = Path(temporary_directory)
        input_path = temporary_path / "input.wav"
        output_path = temporary_path / "output.wav"
        sf.write(str(input_path), wav_array, sample_rate, subtype="FLOAT")
        command = [
            ffmpeg_yolu(),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(input_path),
            "-filter:a",
            f"atempo={requested_factor:.6f}",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-c:a",
            "pcm_f32le",
            str(output_path),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except FileNotFoundError as error:
            raise RuntimeError("Supertonic atempo FFmpeg bulunamadi") from error
        if completed.returncode != 0:
            error_text = (completed.stderr or completed.stdout or "bilinmeyen FFmpeg hatasi").strip()
            raise RuntimeError(f"Supertonic atempo FFmpeg hatasi: {error_text}")
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("Supertonic atempo FFmpeg cikti WAV dosyasi uretmedi")
        processed_audio, output_sample_rate = sf.read(
            str(output_path),
            dtype="float32",
            always_2d=False,
        )

    if output_sample_rate != sample_rate:
        raise RuntimeError("Supertonic atempo FFmpeg sample rate degerini korumadi")
    if processed_audio.ndim != 1:
        raise RuntimeError("Supertonic atempo FFmpeg mono cikti uretmedi")
    if processed_audio.size == 0:
        return wav_array.copy()
    return np.asarray(processed_audio, dtype=np.float32)
