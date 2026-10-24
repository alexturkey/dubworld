# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import soundfile as sf


def prepare_speaker_input_audio(audio_path: str, work_dir: Path) -> Path:
    source_path = Path(audio_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Speaker audio not found: {audio_path}")
    work_dir.mkdir(parents=True, exist_ok=True)
    output_path = work_dir / "speaker_input_16k_mono.wav"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found in PATH")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-sample_fmt",
        "s16",
        str(output_path),
    ]
    subprocess.run(command, check=True)
    info = sf.info(str(output_path))
    if int(info.samplerate) != 16000 or int(info.channels) != 1:
        raise RuntimeError(
            f"Speaker audio normalization failed: samplerate={info.samplerate}, channels={info.channels}"
        )
    probe = {
        "source_audio_path": str(source_path),
        "speaker_input_path": str(output_path),
        "samplerate": int(info.samplerate),
        "channels": int(info.channels),
        "duration": round(float(info.duration), 3),
        "format": str(info.format),
        "subtype": str(info.subtype),
    }
    (work_dir / "speaker_input_probe.json").write_text(
        json.dumps(probe, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
