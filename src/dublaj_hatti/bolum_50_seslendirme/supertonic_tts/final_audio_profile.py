# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
import subprocess
import json
import math
import re
from pathlib import Path
from typing import Dict


SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER = "supertonic_constant_gain_v1"
# Neden: sinirlayici/sikistirici cizirdadi; tek sabit kazanc karakteri korur, -1.3 dBTP -1.1 kabul sinirina pay birakir. bkz. docs/engineering/pinned-values.md#supertonic-synthesis
SUPERTONIC_TARGET_LUFS = -18.0
SUPERTONIC_TRUE_PEAK_CEILING = -1.3


def constant_gain_from_measurements(integrated_lufs, true_peak_dbtp):
    if math.isnan(integrated_lufs) or math.isnan(true_peak_dbtp):
        raise ValueError("Invalid Supertonic loudness measurement")
    if true_peak_dbtp == -math.inf:
        return 0.0, "silence"
    if not math.isfinite(true_peak_dbtp) or integrated_lufs == math.inf:
        raise ValueError("Invalid Supertonic loudness measurement")
    peak_gain = SUPERTONIC_TRUE_PEAK_CEILING - true_peak_dbtp
    if integrated_lufs == -math.inf:
        return min(0.0, peak_gain), "ungated_short_or_quiet_audio"
    loudness_gain = SUPERTONIC_TARGET_LUFS - integrated_lufs
    return min(loudness_gain, peak_gain), "peak_ceiling" if peak_gain < loudness_gain else "loudness_target"


def resolve_supertonic_final_audio_profile(source_path):
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostdin", "-i", str(source_path),
            "-af", "loudnorm=I=-18:TP=-1.3:LRA=7:print_format=json",
            "-f", "null", "-",
        ],
        check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    measurements = []
    for candidate in re.findall(r"\{[^{}]*\}", result.stderr):
        value = json.loads(candidate)
        if "input_i" in value and "input_tp" in value:
            measurements.append(value)
    if len(measurements) != 1:
        raise RuntimeError("Supertonic loudness measurement missing or ambiguous")
    integrated = float(measurements[0]["input_i"])
    peak = float(measurements[0]["input_tp"])
    gain_db, reason = constant_gain_from_measurements(integrated, peak)
    audio_filter = f"volume={gain_db:.8f}dB:precision=double"
    return {
        "contract": SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER,
        "target_lufs": SUPERTONIC_TARGET_LUFS,
        "true_peak_ceiling_dbtp": SUPERTONIC_TRUE_PEAK_CEILING,
        "source_integrated_lufs": integrated if math.isfinite(integrated) else None,
        "source_true_peak_dbtp": peak if math.isfinite(peak) else None,
        "gain_db": gain_db,
        "reason": reason,
        "filter": audio_filter,
        "source_audio": str(source_path),
    }


def render_supertonic_constant_gain(source_path, output_path):
    profile = resolve_supertonic_final_audio_profile(source_path)
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
         "-i", str(source_path), "-af", profile["filter"], "-c:a", "pcm_s24le", str(output_path)],
        check=True, capture_output=True,
    )
    Path(output_path).with_suffix(".gain.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n",
    )
    return profile


def apply_supertonic_final_audio_profile(run_dir: str, output_video: str, sample_rate: int, logger=None) -> Dict[str, str]:
    timeline_audio = os.path.join(run_dir, "audio_new_timeline.wav")
    raw_audio = os.path.join(run_dir, "audio_new_timeline_supertonic_raw.wav")
    profiled_audio = os.path.join(run_dir, "audio_new_timeline_supertonic_profile_13.wav")
    remuxed_video = os.path.join(run_dir, "dubbed_supertonic_profile_tmp.mp4")
    if not os.path.exists(timeline_audio):
        raise FileNotFoundError(f"Supertonic timeline audio bulunamadi: {timeline_audio}")
    if not os.path.exists(output_video):
        raise FileNotFoundError(f"Supertonic output video bulunamadi: {output_video}")
    shutil.copy2(timeline_audio, raw_audio)
    profile = resolve_supertonic_final_audio_profile(raw_audio)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", raw_audio,
            "-af", profile["filter"],
            "-ar", str(sample_rate),
            "-ac", "1",
            "-c:a", "pcm_s24le",
            profiled_audio,
        ],
        check=True,
    )
    shutil.copy2(profiled_audio, timeline_audio)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", output_video,
            "-i", timeline_audio,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            remuxed_video,
        ],
        check=True,
    )
    os.replace(remuxed_video, output_video)
    if logger:
        logger.info("Supertonic final audio profile uygulandi: %s", SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER)
    return {
        "raw_audio": raw_audio,
        "profiled_audio": profiled_audio,
        "timeline_audio": timeline_audio,
        **profile,
    }
