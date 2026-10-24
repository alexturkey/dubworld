from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile

BACKGROUND_DETECTION_CONTRACT = "konusma_arasi_sessizlik_v1"
# Neden: 32 dB / -60 dB esikleri onceki ayristirilmis islerle ayarlandi, kesinlik ~%90 (ADR 0003). bkz. docs/engineering/pinned-values.md#source-audio-and-separation
FRAME_SECONDS = 0.05
QUIET_PERCENTILE = 5
LOUD_PERCENTILE = 95
DYNAMIC_RANGE_THRESHOLD_DB = 32.0
SILENT_AUDIO_PEAK_DB = -60.0
READ_BLOCK_FRAMES = 1200


class ArkaPlanOlcumHatasi(RuntimeError):
    pass


def _frame_levels_db(audio_path: Path) -> tuple[np.ndarray, float]:
    info = soundfile.info(str(audio_path))
    if int(info.frames) <= 0 or int(info.samplerate) <= 0:
        raise ArkaPlanOlcumHatasi(f"ses dosyasi bos veya okunamiyor: {audio_path}")
    hop = max(1, int(info.samplerate * FRAME_SECONDS))
    levels = []
    for block in soundfile.blocks(str(audio_path), blocksize=hop * READ_BLOCK_FRAMES, dtype="float32", always_2d=True):
        mono = block.mean(axis=1)
        count = len(mono) // hop
        if count:
            frames = mono[: count * hop].reshape(count, hop).astype("float64")
            levels.append(10.0 * np.log10(np.mean(frames * frames, axis=1) + 1e-12))
    if not levels:
        raise ArkaPlanOlcumHatasi(f"ses dosyasi olcum icin cok kisa: {audio_path}")
    return np.concatenate(levels), int(info.frames) / int(info.samplerate)


def measure_background(audio_path: str | Path) -> dict:
    path = Path(audio_path)
    try:
        levels, audio_seconds = _frame_levels_db(path)
    except (OSError, soundfile.SoundFileError) as error:
        raise ArkaPlanOlcumHatasi(f"arka plan olcumu icin ses okunamadi: {path}") from error
    quiet_db, loud_db = np.percentile(levels, [QUIET_PERCENTILE, LOUD_PERCENTILE])
    dynamic_range_db = round(float(loud_db - quiet_db), 2)
    silent_audio = float(loud_db) < SILENT_AUDIO_PEAK_DB
    has_background = not silent_audio and dynamic_range_db < DYNAMIC_RANGE_THRESHOLD_DB
    return {
        "contract": BACKGROUND_DETECTION_CONTRACT,
        "audio_seconds": round(audio_seconds, 3),
        "frame_seconds": FRAME_SECONDS,
        "quiet_level_db": round(float(quiet_db), 2),
        "loud_level_db": round(float(loud_db), 2),
        "dynamic_range_db": dynamic_range_db,
        "threshold_db": DYNAMIC_RANGE_THRESHOLD_DB,
        "silent_audio": silent_audio,
        "has_background": has_background,
    }
