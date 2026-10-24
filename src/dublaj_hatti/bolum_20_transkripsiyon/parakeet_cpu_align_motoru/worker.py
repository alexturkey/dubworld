from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
import wave
from pathlib import Path

import numpy as np
import sherpa_onnx

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from dublaj_hatti.bolum_20_transkripsiyon.parakeet_cpu_align_motoru.alignment_runner import run_alignment
    from dublaj_hatti.bolum_20_transkripsiyon.parakeet_cpu_align_motoru.config import build_config
else:
    from .alignment_runner import run_alignment
    from .config import build_config


# Neden: kodlayici en cok 5000 x 80 ms = 400 sn alir; 400.08 sn kararsiz, 399 sn pay. Isin 4 / ceza 2.0 WER %11.1 -> %8.4. bkz. docs/engineering/pinned-values.md#transcription
PARAKEET_TECHNICAL_MAX_SECONDS = 400.0
PARAKEET_OPERATIONAL_MAX_SECONDS = 399.0
BOUNDARY_MIN_SILENCE_MS = 600
ALIGNMENT_NATURAL_GAP_SECONDS = 1.0
PARAKEET_TIMESTAMP_FRAME_SECONDS = 0.08
PARAKEET_DECODING_METHOD = "modified_beam_search"
PARAKEET_MAX_ACTIVE_PATHS = 4
PARAKEET_BLANK_PENALTY = 2.0


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def load_wave(audio_path: Path) -> tuple[np.ndarray, int, float]:
    with wave.open(str(audio_path), "rb") as source:
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        sample_rate = source.getframerate()
        frame_count = source.getnframes()
        if channels != 1:
            raise ValueError(f"Parakeet input must be mono, got {channels} channels")
        if sample_width != 2:
            raise ValueError(f"Parakeet input must be 16-bit PCM, got {sample_width * 8} bit")
        samples = np.frombuffer(source.readframes(frame_count), dtype=np.int16).astype(np.float32)
    samples /= 32768.0
    return samples, sample_rate, frame_count / sample_rate


def build_alignment_segments(tokens: list[str], timestamps: list[float], audio_duration: float) -> list[dict]:
    if not tokens or len(tokens) != len(timestamps):
        raise RuntimeError("Parakeet token timestamps are missing or inconsistent")
    normalized_timestamps = [float(value) for value in timestamps]
    if not all(np.isfinite(value) for value in normalized_timestamps):
        raise RuntimeError("Parakeet token timestamps contain non-finite values")
    if any(left > right for left, right in zip(normalized_timestamps, normalized_timestamps[1:])):
        raise RuntimeError("Parakeet token timestamps are not monotonic")
    if normalized_timestamps[0] < 0.0 or normalized_timestamps[-1] > audio_duration:
        raise RuntimeError("Parakeet token timestamps are outside the audio duration")

    breaks = []
    group_start = 0
    for index, token in enumerate(tokens[:-1]):
        elapsed = normalized_timestamps[index] - normalized_timestamps[group_start]
        sentence_end = token.rstrip().endswith((".", "?", "!"))
        next_word_starts = tokens[index + 1].startswith(" ")
        token_gap = normalized_timestamps[index + 1] - normalized_timestamps[index]
        natural_gap = next_word_starts and token_gap >= ALIGNMENT_NATURAL_GAP_SECONDS
        if natural_gap or (elapsed >= 8.0 and sentence_end) or (elapsed >= 25.0 and next_word_starts):
            breaks.append({"end_index": index, "natural_gap": natural_gap})
            group_start = index + 1
    breaks.append({"end_index": len(tokens) - 1, "natural_gap": False})

    segments = []
    start_index = 0
    segment_start = 0.0
    for segment_index, break_record in enumerate(breaks):
        end_index = break_record["end_index"]
        text = "".join(tokens[start_index:end_index + 1]).strip()
        if end_index + 1 < len(tokens):
            current_timestamp = normalized_timestamps[end_index]
            next_timestamp = normalized_timestamps[end_index + 1]
            if break_record["natural_gap"]:
                segment_end = min(current_timestamp + PARAKEET_TIMESTAMP_FRAME_SECONDS, next_timestamp)
                next_segment_start = max(segment_end, next_timestamp - PARAKEET_TIMESTAMP_FRAME_SECONDS)
            else:
                segment_end = (current_timestamp + next_timestamp) / 2.0
                next_segment_start = segment_end
        else:
            segment_end = audio_duration
            next_segment_start = audio_duration
        segment_end = max(segment_start, min(segment_end, audio_duration))
        next_segment_start = max(segment_end, min(next_segment_start, audio_duration))
        if text:
            segments.append({
                "index": segment_index,
                "start": round(segment_start, 3),
                "end": round(segment_end, 3),
                "text": text,
            })
        segment_start = next_segment_start
        start_index = end_index + 1
    if not segments:
        raise RuntimeError("Parakeet did not produce alignment text")
    segments[-1]["end"] = round(audio_duration, 3)
    return segments


def find_long_audio_partitions(samples: np.ndarray, sample_rate: int) -> tuple[list[dict], float]:
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    vad_started = time.monotonic()
    speech_chunks = get_speech_timestamps(
        samples,
        vad_options=VadOptions(
            threshold=0.5,
            min_speech_duration_ms=0,
            min_silence_duration_ms=BOUNDARY_MIN_SILENCE_MS,
            speech_pad_ms=0,
        ),
        sampling_rate=sample_rate,
    )
    sample_count = len(samples)
    speech_ranges = []
    for chunk in speech_chunks:
        start = max(0, min(int(chunk["start"]), sample_count))
        end = max(start, min(int(chunk["end"]), sample_count))
        if end > start:
            speech_ranges.append((start, end))
    silence_ranges = []
    for left, right in zip(speech_ranges, speech_ranges[1:]):
        silence_start = left[1]
        silence_end = right[0]
        if silence_end - silence_start >= int(round(BOUNDARY_MIN_SILENCE_MS * sample_rate / 1000.0)):
            silence_ranges.append((silence_start, silence_end))
    operational_max_samples = int(round(PARAKEET_OPERATIONAL_MAX_SECONDS * sample_rate))
    partitions = []
    partition_start = 0
    while partition_start < sample_count:
        hard_end = min(sample_count, partition_start + operational_max_samples)
        if hard_end == sample_count:
            partition_end = sample_count
            boundary_kind = "audio_end"
            silence_duration = 0.0
        else:
            candidates = []
            for silence_start, silence_end in silence_ranges:
                midpoint = (silence_start + silence_end) // 2
                if partition_start < midpoint <= hard_end:
                    candidates.append((midpoint, silence_start, silence_end))
            if candidates:
                partition_end, silence_start, silence_end = max(candidates, key=lambda item: item[0])
                boundary_kind = "silence_midpoint"
                silence_duration = (silence_end - silence_start) / sample_rate
            else:
                partition_end = hard_end
                boundary_kind = "hard_limit_no_silence"
                silence_duration = 0.0
        if partition_end <= partition_start:
            raise RuntimeError("Parakeet partition planner did not advance")
        partitions.append({
            "index": len(partitions),
            "start_sample": partition_start,
            "end_sample": partition_end,
            "start": round(partition_start / sample_rate, 6),
            "end": round(partition_end / sample_rate, 6),
            "duration": round((partition_end - partition_start) / sample_rate, 6),
            "boundary_kind": boundary_kind,
            "silence_duration": round(silence_duration, 6),
        })
        partition_start = partition_end
    if partitions:
        covered_samples = sum(item["end_sample"] - item["start_sample"] for item in partitions)
        if partitions[0]["start_sample"] != 0 or partitions[-1]["end_sample"] != sample_count:
            raise RuntimeError("Parakeet partition plan does not cover the complete audio")
        if covered_samples != sample_count:
            raise RuntimeError("Parakeet partition plan dropped or duplicated audio samples")
        for left, right in zip(partitions, partitions[1:]):
            if left["end_sample"] != right["start_sample"]:
                raise RuntimeError("Parakeet partition plan is not contiguous")
    return partitions, round(time.monotonic() - vad_started, 3)


def decode_samples(recognizer, sample_rate: int, samples: np.ndarray):
    stream = recognizer.create_stream()
    stream.accept_waveform(sample_rate, samples)
    recognizer.decode_stream(stream)
    return stream.result


def validate_model(model_dir: Path) -> dict[str, Path]:
    required = {
        "encoder": model_dir / "encoder.int8.onnx",
        "decoder": model_dir / "decoder.int8.onnx",
        "joiner": model_dir / "joiner.int8.onnx",
        "tokens": model_dir / "tokens.txt",
    }
    for label, path in required.items():
        if not path.is_file():
            raise FileNotFoundError(f"Parakeet {label} file not found: {path}")
    return required


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parakeet Unified EN INT8 CPU transcribe + CTC kelime hizalama worker")
    parser.add_argument("--audio_path", required=True)
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--language", default="en")
    parser.add_argument("--cache_dir", default="")
    parser.add_argument("--alignment_device", default="cuda")
    return parser.parse_args()


def run_worker(args: argparse.Namespace) -> dict:
    started = time.monotonic()
    audio_path = Path(args.audio_path).expanduser().resolve()
    run_dir = Path(args.run_dir).expanduser().resolve()
    debug_dir = run_dir / "parakeet_cpu_align_motoru"
    debug_dir.mkdir(parents=True, exist_ok=True)
    config = build_config(
        language=args.language,
        cache_dir=args.cache_dir,
        alignment_device=args.alignment_device,
    )
    if config.language != "en":
        raise ValueError("Parakeet Unified EN supports language=en only")
    model_files = validate_model(config.model_dir)
    samples, sample_rate, audio_duration = load_wave(audio_path)
    load_started = time.monotonic()
    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(model_files["encoder"]),
        decoder=str(model_files["decoder"]),
        joiner=str(model_files["joiner"]),
        tokens=str(model_files["tokens"]),
        num_threads=config.threads,
        sample_rate=16000,
        feature_dim=80,
        decoding_method=PARAKEET_DECODING_METHOD,
        max_active_paths=PARAKEET_MAX_ACTIVE_PATHS,
        blank_penalty=PARAKEET_BLANK_PENALTY,
        provider="cpu",
        model_type="nemo_transducer",
    )
    model_load_seconds = round(time.monotonic() - load_started, 3)
    transcribe_started = time.monotonic()
    transcription_mode = "single_stream"
    vad_seconds = 0.0
    chunk_records = []
    if audio_duration <= PARAKEET_OPERATIONAL_MAX_SECONDS:
        parakeet_result = decode_samples(recognizer, sample_rate, samples)
        transcript = str(parakeet_result.text or "").strip()
        tokens = list(parakeet_result.tokens)
        timestamps = [float(value) for value in parakeet_result.timestamps]
        alignment_segments = build_alignment_segments(tokens, timestamps, audio_duration)
        chunk_records.append({
            "index": 0,
            "start_sample": 0,
            "end_sample": len(samples),
            "start": 0.0,
            "end": round(audio_duration, 3),
            "duration": round(audio_duration, 6),
            "boundary_kind": "audio_end",
            "silence_duration": 0.0,
            "text": transcript,
            "token_count": len(tokens),
        })
    else:
        transcription_mode = "silence_boundary_chunked"
        partitions, vad_seconds = find_long_audio_partitions(samples, sample_rate)
        transcripts = []
        tokens = []
        timestamps = []
        alignment_segments = []
        for partition in partitions:
            start_sample = partition["start_sample"]
            end_sample = partition["end_sample"]
            parakeet_result = decode_samples(recognizer, sample_rate, samples[start_sample:end_sample])
            text = str(parakeet_result.text or "").strip()
            local_tokens = list(parakeet_result.tokens)
            local_timestamps = [float(value) for value in parakeet_result.timestamps]
            if len(local_tokens) != len(local_timestamps):
                raise RuntimeError("Parakeet token timestamps are missing or inconsistent")
            if not text or not any(character.isalnum() for character in text):
                raise RuntimeError(
                    "Parakeet returned no lexical text for contiguous audio partition "
                    f'{partition["start"]:.3f}-{partition["end"]:.3f}s'
                )
            start_seconds = start_sample / sample_rate
            absolute_timestamps = [round(start_seconds + value, 6) for value in local_timestamps]
            local_segments = build_alignment_segments(local_tokens, local_timestamps, partition["duration"])
            chunk_record = {
                **partition,
                "text": text,
                "token_count": len(local_tokens),
            }
            chunk_records.append(chunk_record)
            transcripts.append(text)
            tokens.extend(local_tokens)
            timestamps.extend(absolute_timestamps)
            for local_segment_index, segment in enumerate(local_segments):
                segment_start = round(start_sample / sample_rate, 3) if local_segment_index == 0 else round(start_seconds + segment["start"], 3)
                segment_end = round(end_sample / sample_rate, 3) if local_segment_index == len(local_segments) - 1 else round(start_seconds + segment["end"], 3)
                alignment_segments.append({
                    "index": len(alignment_segments),
                    "start": segment_start,
                    "end": segment_end,
                    "text": segment["text"],
                })
        transcript = " ".join(transcripts)
    transcription_seconds = round(time.monotonic() - transcribe_started, 3)
    alignment_input_path = debug_dir / "alignment_input_segments.json"
    write_json(alignment_input_path, alignment_segments)
    write_json(debug_dir / "parakeet_raw_result.json", {
        "transcript": transcript,
        "tokens": tokens,
        "timestamps": timestamps,
        "segments": alignment_segments,
        "decoder_settings": {
            "decoding_method": PARAKEET_DECODING_METHOD,
            "max_active_paths": PARAKEET_MAX_ACTIVE_PATHS,
            "blank_penalty": PARAKEET_BLANK_PENALTY,
        },
        "transcription_mode": transcription_mode,
        "vad_seconds": vad_seconds,
        "chunks": chunk_records,
        "audio_samples": len(samples),
        "covered_samples": sum(item.get("end_sample", 0) - item.get("start_sample", 0) for item in chunk_records),
    })
    alignment_result = run_alignment(audio_path, alignment_input_path, debug_dir, config)
    words = alignment_result.get("words") or []
    if not words:
        for segment in alignment_result.get("segments") or []:
            words.extend(segment.get("words") or [])
    if not words:
        raise RuntimeError("CTC kelime hizalama Parakeet transkripti icin kelime dondurmedi")
    total_seconds = round(time.monotonic() - started, 3)
    profile_steps = [
        {"step": "parakeet_cpu_transcribe", "seconds": transcription_seconds, "segment_count": len(alignment_segments)},
        {"step": "ctc_kelime_hizalama", "seconds": alignment_result.get("alignment_subprocess_seconds", 0), "word_count": len(words)},
    ]
    result = {
        "success": True,
        "engine": config.engine_id,
        "words": words,
        "segments": alignment_result.get("segments") or [],
        "detected_language": "en",
        "total_words": len(words),
        "total_segments": len(alignment_result.get("segments") or []),
        "profile_steps": profile_steps,
        "profile_summary": {
            "engine": config.engine_id,
            "engine_display_name": config.engine_display_name,
            "transcribe_engine": "sherpa-onnx",
            "transcribe_model": "nvidia/parakeet-unified-en-0.6b",
            "transcribe_runtime": "int8_non_streaming_cpu",
            "sherpa_onnx_version": sherpa_onnx.__version__,
            "threads": config.threads,
            "decoding_method": PARAKEET_DECODING_METHOD,
            "max_active_paths": PARAKEET_MAX_ACTIVE_PATHS,
            "blank_penalty": PARAKEET_BLANK_PENALTY,
            "model_dir": str(config.model_dir),
            "model_load_seconds": model_load_seconds,
            "transcription_seconds": transcription_seconds,
            "transcription_mode": transcription_mode,
            "vad_seconds": vad_seconds,
            "transcription_chunk_count": len(chunk_records),
            "parakeet_technical_max_seconds": PARAKEET_TECHNICAL_MAX_SECONDS,
            "parakeet_operational_max_seconds": PARAKEET_OPERATIONAL_MAX_SECONDS,
            "boundary_min_silence_ms": BOUNDARY_MIN_SILENCE_MS,
            "hard_boundary_count": sum(item.get("boundary_kind") == "hard_limit_no_silence" for item in chunk_records),
            "covered_audio_samples": sum(item.get("end_sample", 0) - item.get("start_sample", 0) for item in chunk_records),
            "alignment_seconds": alignment_result.get("alignment_subprocess_seconds", 0),
            "total_worker_seconds": total_seconds,
            "total_words": len(words),
            "total_segments": len(alignment_result.get("segments") or []),
        },
        "raw_transcript": transcript,
    }
    write_json(debug_dir / "profile.json", result["profile_summary"])
    return result


def main() -> int:
    args = parse_args()
    try:
        result = run_worker(args)
    except Exception as exc:
        result = {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        try:
            write_json(Path(args.run_dir).expanduser().resolve() / "parakeet_cpu_align_motoru" / "error.json", result)
        except Exception:
            pass
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
