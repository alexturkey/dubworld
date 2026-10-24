from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from .config import WhisperCppCpuAlignConfig
from .debug_report import command_to_text, write_json, write_text


def validate_runtime(config: WhisperCppCpuAlignConfig) -> None:
    if not config.whisper_cli_path.exists() or not config.whisper_cli_path.is_file():
        raise FileNotFoundError(f"whisper-cli.exe not found: {config.whisper_cli_path}")
    if not config.model_path.exists() or not config.model_path.is_file():
        raise FileNotFoundError(f"whisper.cpp model not found: {config.model_path}")
    if config.language != "en":
        raise ValueError("whisper_cpp_cpu_align first version supports language=en only")


def build_command(audio_path: Path, output_stem: Path, config: WhisperCppCpuAlignConfig) -> list[str]:
    command = [
        str(config.whisper_cli_path),
        "-m",
        str(config.model_path),
        "-f",
        str(audio_path),
        "-l",
        config.language,
        "-t",
        str(config.threads),
        "-bs",
        str(config.beam_size),
        "-bo",
        str(config.best_of),
        "-nth",
        config.no_speech_thold,
    ]
    if config.no_gpu:
        command.append("-ng")
    command.extend(["-otxt", "-osrt", "-ovtt", "-oj", "-ojf", "-of", str(output_stem)])
    return command


def load_whisper_cpp_segments(json_path: Path) -> list[dict[str, Any]]:
    with open(json_path, "r", encoding="utf-8") as file:
        payload = json.load(file)
    segments = []
    for index, segment in enumerate(payload.get("transcription") or []):
        text = str(segment.get("text") or "").strip()
        offsets = segment.get("offsets") or {}
        start = float(offsets.get("from", 0)) / 1000.0
        end = float(offsets.get("to", 0)) / 1000.0
        if text and end >= start:
            segments.append({
                "start": start,
                "end": end,
                "text": text,
                "index": index,
            })
    if not segments:
        raise RuntimeError("whisper.cpp transcript.json did not contain usable segments")
    return segments


def run_whisper_cpp(audio_path: Path, debug_dir: Path, config: WhisperCppCpuAlignConfig) -> dict[str, Any]:
    validate_runtime(config)
    raw_dir = debug_dir / "whisper_cpp_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_stem = raw_dir / "transcript"
    command = build_command(audio_path, output_stem, config)
    write_text(debug_dir / "command_whisper_cpp.txt", command_to_text(command))
    started = time.monotonic()
    with open(debug_dir / "whisper_cpp_stdout.txt", "w", encoding="utf-8", errors="replace") as stdout_file:
        with open(debug_dir / "whisper_cpp_stderr.txt", "w", encoding="utf-8", errors="replace") as stderr_file:
            result = subprocess.run(
                command,
                cwd=str(config.whisper_cli_path.parent),
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
            )
    elapsed = round(time.monotonic() - started, 3)
    if result.returncode != 0:
        raise RuntimeError(f"whisper-cli failed with returncode={result.returncode}")

    transcript_txt = output_stem.with_suffix(".txt")
    transcript_json = output_stem.with_suffix(".json")
    if not transcript_txt.exists():
        raise RuntimeError(f"whisper.cpp txt output missing: {transcript_txt}")
    if not transcript_json.exists():
        raise RuntimeError(f"whisper.cpp json output missing: {transcript_json}")

    with open(transcript_txt, "r", encoding="utf-8", errors="replace") as file:
        text = file.read().strip()
    write_text(debug_dir / "whisper_cpp_transcript.txt", text)
    alignment_segments = load_whisper_cpp_segments(transcript_json)
    alignment_input_path = debug_dir / "alignment_input_segments.json"
    write_json(alignment_input_path, alignment_segments)

    return {
        "segments": alignment_segments,
        "alignment_input_path": str(alignment_input_path),
        "alignment_input_mode": "whisper_cpp_segments",
        "transcript_text": text,
        "transcript_json_path": str(transcript_json),
        "transcript_txt_path": str(transcript_txt),
        "whisper_cpp_segment_count": len(alignment_segments),
        "seconds": elapsed,
        "command": command,
    }
