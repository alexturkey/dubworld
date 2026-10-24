from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ENGINE_ID = "whisper_cpp_cpu_align"
ENGINE_DISPLAY_NAME = "Whisper.cpp CPU + CTC Align"


@dataclass(frozen=True)
class WhisperCppCpuAlignConfig:
    engine_id: str
    engine_display_name: str
    experiment_root: Path
    whisper_cli_path: Path
    model_path: Path
    model_filename: str
    language: str
    threads: int
    beam_size: int
    best_of: int
    no_speech_thold: str
    no_gpu: bool
    alignment_device: str
    cache_dir: str
    timeout_seconds: int


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def default_experiment_root() -> Path:
    env_path = os.environ.get("DUBLAJ_WHISPER_CPP_CPU_ROOT", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    return project_root() / "runtime_assets" / "transkripsiyon_motorlari" / "whisper_cpp_cpu_align"


def build_config(
    language: str = "en",
    cache_dir: str = "",
    alignment_device: str = "cuda",
) -> WhisperCppCpuAlignConfig:
    experiment_root = default_experiment_root()
    model_filename = "ggml-base.en.bin"
    return WhisperCppCpuAlignConfig(
        engine_id=ENGINE_ID,
        engine_display_name=ENGINE_DISPLAY_NAME,
        experiment_root=experiment_root,
        whisper_cli_path=experiment_root / "engines" / "whisper_cpp" / "bin" / "whisper-cli.exe",
        model_path=experiment_root / "models" / "whisper" / model_filename,
        model_filename=model_filename,
        language=language or "en",
        threads=4,
        beam_size=1,
        best_of=1,
        no_speech_thold="1.00",
        no_gpu=True,
        alignment_device=alignment_device or "cuda",
        cache_dir=cache_dir,
        timeout_seconds=1800,
    )
