from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import soundfile as sf
from dublaj_hatti.bolum_00_omurga.runtime.arac_yolu import ffmpeg_yolu


@dataclass(frozen=True)
class FullTextSpeechWindow:
    source_text: str
    speech_start: float
    speech_end: float

    @property
    def duration(self) -> float:
        return self.speech_end - self.speech_start


@dataclass(frozen=True)
class FullTextSynthesis:
    audio: np.ndarray
    sample_rate: int
    chunk_count: int
    actual_chunks: tuple["FullTextAudioChunk", ...]
    inter_chunk_silence_samples: int


@dataclass(frozen=True)
class FullTextAudioChunk:
    text: str
    audio: np.ndarray


def build_full_text_speech_window(segments: Iterable[Any]) -> FullTextSpeechWindow:
    ordered_segments = sorted(list(segments), key=lambda segment: float(getattr(segment, "start", 0.0)))
    source_text = " ".join(str(getattr(segment, "text", "") or "").strip() for segment in ordered_segments).strip()
    if not source_text:
        raise ValueError("Full Metin Dublaji icin kaynak metin bos olamaz")
    if not ordered_segments:
        raise ValueError("Full Metin Dublaji icin konusma segmenti bulunamadi")
    speech_start = float(getattr(ordered_segments[0], "start", 0.0))
    speech_end = float(getattr(ordered_segments[-1], "end", 0.0))
    if not math.isfinite(speech_start) or not math.isfinite(speech_end) or speech_start < 0 or speech_end <= speech_start:
        raise ValueError("Full Metin Dublaji konusma penceresi gecersiz")
    return FullTextSpeechWindow(
        source_text=source_text,
        speech_start=speech_start,
        speech_end=speech_end,
    )


def synthesize_full_text_supertonic(
    text: str,
    voice_id: str,
    language: str,
    work_dir: str,
) -> FullTextSynthesis:
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.process import synthesize_single_request

    source_text = str(text or "").strip()
    if not source_text:
        raise ValueError("Supertonic full metin girdisi bos olamaz")
    results, records, successful, failed = synthesize_single_request(
        [{"index": 1, "text": source_text, "duration": 0.0}],
        voice_id=voice_id,
        language=language,
        work_dir=work_dir,
        return_actual_chunks=True,
    )
    if successful != 1 or failed != 0 or 1 not in results:
        raise RuntimeError(f"Supertonic full metin sentezi basarisiz: {records}")
    result = results[1]
    audio = np.asarray(result["wav_array"], dtype=np.float32)
    sample_rate = int(result["sample_rate"])
    if audio.size == 0 or sample_rate <= 0:
        raise RuntimeError("Supertonic full metin sentezi gecersiz WAV uretti")
    debug = result.get("debug") if isinstance(result.get("debug"), dict) else {}
    actual_chunks = tuple(
        FullTextAudioChunk(
            text=str(chunk.get("text") or "").strip(),
            audio=np.asarray(chunk.get("wav_array"), dtype=np.float32),
        )
        for chunk in result.get("actual_chunks", [])
        if str(chunk.get("text") or "").strip() and np.asarray(chunk.get("wav_array")).size > 0
    )
    if not actual_chunks:
        raise RuntimeError("Supertonic full metin gercek parca WAV bilgisi uretmedi")
    silence_samples = int(round(float(result.get("inter_chunk_silence_seconds") or 0.0) * sample_rate))
    if silence_samples < 0:
        raise RuntimeError("Supertonic full metin parca sessizligi gecersiz")
    return FullTextSynthesis(
        audio=audio,
        sample_rate=sample_rate,
        chunk_count=int(debug.get("chunk_count") or 0),
        actual_chunks=actual_chunks,
        inter_chunk_silence_samples=silence_samples,
    )


def build_full_text_alignment_windows(
    synthesis: FullTextSynthesis,
    final_audio: np.ndarray,
) -> tuple[dict[str, float | int | str], ...]:
    raw_samples = len(synthesis.audio)
    final_samples = len(final_audio)
    if raw_samples <= 0 or final_samples <= 0:
        raise RuntimeError("Full metin alignment WAV suresi gecersiz")
    cursor = 0
    windows = []
    for index, chunk in enumerate(synthesis.actual_chunks, start=1):
        if index > 1:
            cursor += synthesis.inter_chunk_silence_samples
        start_sample = cursor
        cursor += len(chunk.audio)
        end_sample = cursor
        if end_sample > raw_samples:
            raise RuntimeError("Full metin gercek parca WAV siniri nihai sesten tasiyor")
        final_start = int(round(start_sample * final_samples / raw_samples))
        final_end = int(round(end_sample * final_samples / raw_samples))
        final_end = max(final_end, final_start + 1)
        windows.append({
            "index": index,
            "text": chunk.text,
            "start": final_start / synthesis.sample_rate,
            "end": min(final_end / synthesis.sample_rate, final_samples / synthesis.sample_rate),
        })
    if cursor != raw_samples:
        raise RuntimeError("Full metin gercek parca WAV toplami nihai sesle uyusmuyor")
    return tuple(windows)


def atempo_filter_chain(speed: float) -> str:
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError("Atempo hizi pozitif sonlu bir sayi olmali")
    factors = []
    remaining = float(speed)
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def fit_audio_to_speech_window(
    audio: np.ndarray,
    sample_rate: int,
    target_duration: float,
    work_dir: str,
) -> np.ndarray:
    if target_duration <= 0 or not math.isfinite(target_duration):
        raise ValueError("Hedef konusma suresi gecersiz")
    source_audio = np.asarray(audio, dtype=np.float32)
    if source_audio.size == 0 or sample_rate <= 0:
        raise ValueError("Full metin sesi gecersiz")
    source_duration = len(source_audio) / sample_rate
    speed = source_duration / target_duration
    if math.isclose(speed, 1.0, rel_tol=0.0, abs_tol=0.0001):
        return source_audio
    output_root = Path(work_dir)
    input_path = output_root / "full_text_before_atempo.wav"
    output_path = output_root / "full_text_after_atempo.wav"
    sf.write(input_path, source_audio, sample_rate, subtype="FLOAT")
    subprocess.run(
        [
            ffmpeg_yolu(),
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", str(input_path),
            "-af", atempo_filter_chain(speed),
            "-ar", str(sample_rate),
            "-ac", "1",
            "-c:a", "pcm_f32le",
            str(output_path),
        ],
        check=True,
    )
    stretched_audio, output_rate = sf.read(output_path, dtype="float32")
    if int(output_rate) != int(sample_rate):
        raise RuntimeError("FFmpeg full metin atempo sample rate degistirdi")
    return np.asarray(stretched_audio, dtype=np.float32)
