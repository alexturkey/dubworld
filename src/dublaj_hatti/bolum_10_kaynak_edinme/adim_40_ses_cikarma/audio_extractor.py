import math
import os
import subprocess
import wave
from typing import Optional

import numpy as np


def _rms_db(sum_square: float, sample_count: int) -> float:
    if sample_count <= 0:
        return -120.0
    rms = math.sqrt(max(sum_square, 0.0) / sample_count) / 32768.0
    return 20.0 * math.log10(max(rms, 1e-12))


def _analyze_stereo_phase(wav_path: str) -> Optional[dict]:
    try:
        with wave.open(wav_path, "rb") as wav_file:
            if wav_file.getnchannels() != 2 or wav_file.getsampwidth() != 2:
                return None
            frame_count = wav_file.getnframes()
            max_frames = min(frame_count, wav_file.getframerate() * 60)
            chunk_size = 65536
            left_square = 0.0
            right_square = 0.0
            mid_square = 0.0
            side_square = 0.0
            cross = 0.0
            sample_count = 0
            while sample_count < max_frames:
                frames_to_read = min(chunk_size, max_frames - sample_count)
                data = wav_file.readframes(frames_to_read)
                samples = np.frombuffer(data, dtype="<i2").reshape(-1, 2).astype(np.float64)
                left = samples[:, 0]
                right = samples[:, 1]
                mid = (left + right) * 0.5
                side = (left - right) * 0.5
                left_square += float(np.dot(left, left))
                right_square += float(np.dot(right, right))
                mid_square += float(np.dot(mid, mid))
                side_square += float(np.dot(side, side))
                cross += float(np.dot(left, right))
                sample_count += frames_to_read
            if sample_count <= 0 or left_square <= 0 or right_square <= 0:
                return None
            correlation = cross / math.sqrt(left_square * right_square)
            mid_db = _rms_db(mid_square, sample_count)
            side_db = _rms_db(side_square, sample_count)
            return {
                "correlation": correlation,
                "mid_db": mid_db,
                "side_db": side_db,
                "side_minus_mid_db": side_db - mid_db,
            }
    except (OSError, wave.Error):
        return None


def _should_fix_inverted_phase(phase_info: Optional[dict]) -> bool:
    if not phase_info:
        return False
    return (
        phase_info["correlation"] <= -0.95
        and phase_info["side_minus_mid_db"] >= 12.0
        and phase_info["side_db"] >= -45.0
    )


def _fix_inverted_stereo_phase(wav_path: str, logger: Optional[object] = None) -> None:
    phase_info = _analyze_stereo_phase(wav_path)
    if not _should_fix_inverted_phase(phase_info):
        if logger and phase_info:
            logger.info(
                "Stereo phase check: corr=%.6f mid=%.2fdB side=%.2fdB diff=%.2fdB action=none",
                phase_info["correlation"],
                phase_info["mid_db"],
                phase_info["side_db"],
                phase_info["side_minus_mid_db"],
            )
        return

    temp_path = f"{wav_path}.phasefix.tmp.wav"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        wav_path,
        "-af",
        "pan=stereo|c0=FL|c1=-1*FR",
        "-acodec",
        "pcm_s16le",
        temp_path,
    ]
    try:
        subprocess.run(cmd, check=True)
        os.replace(temp_path, wav_path)
        fixed_info = _analyze_stereo_phase(wav_path)
        if logger:
            logger.warning(
                "Stereo phase fixed: before corr=%.6f mid=%.2fdB side=%.2fdB diff=%.2fdB",
                phase_info["correlation"],
                phase_info["mid_db"],
                phase_info["side_db"],
                phase_info["side_minus_mid_db"],
            )
            if fixed_info:
                logger.info(
                    "Stereo phase fixed: after corr=%.6f mid=%.2fdB side=%.2fdB diff=%.2fdB",
                    fixed_info["correlation"],
                    fixed_info["mid_db"],
                    fixed_info["side_db"],
                    fixed_info["side_minus_mid_db"],
                )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def extract_audio(
    video_path: str,
    wav_path: str,
    sample_rate: int = 16000,
    channels: int = 1,
    logger: Optional[object] = None,
) -> None:
    if logger:
        logger.info("Videodan ses cikariliyor: %s", video_path)
    if channels == 1:
        stereo_path = f"{wav_path}.stereo.tmp.wav"
        try:
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                video_path,
                "-vn",
                "-ac",
                "2",
                "-ar",
                str(sample_rate),
                "-acodec",
                "pcm_s16le",
                stereo_path,
            ]
            subprocess.run(cmd, check=True)
            _fix_inverted_stereo_phase(stereo_path, logger=logger)
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                stereo_path,
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-acodec",
                "pcm_s16le",
                wav_path,
            ]
            subprocess.run(cmd, check=True)
        finally:
            if os.path.exists(stereo_path):
                os.remove(stereo_path)
    else:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            video_path,
            "-vn",
            "-ac",
            str(channels),
            "-ar",
            str(sample_rate),
            "-acodec",
            "pcm_s16le",
            wav_path,
        ]
        subprocess.run(cmd, check=True)
        if channels == 2:
            _fix_inverted_stereo_phase(wav_path, logger=logger)
    if logger:
        logger.info("Ses dosyasi hazir: %s", wav_path)
