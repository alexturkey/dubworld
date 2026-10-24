from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import parakeet_unified_en_int8_model_dir


ENGINE_ID = "parakeet_cpu_align"
ENGINE_DISPLAY_NAME = "Parakeet Unified EN INT8 CPU + CTC Align"


@dataclass(frozen=True)
class ParakeetCpuAlignConfig:
    engine_id: str
    engine_display_name: str
    model_dir: Path
    language: str
    threads: int
    alignment_device: str
    cache_dir: str
    timeout_seconds: int


def build_config(
    language: str = "en",
    cache_dir: str = "",
    alignment_device: str = "cuda",
) -> ParakeetCpuAlignConfig:
    return ParakeetCpuAlignConfig(
        engine_id=ENGINE_ID,
        engine_display_name=ENGINE_DISPLAY_NAME,
        model_dir=parakeet_unified_en_int8_model_dir(),
        language=language or "en",
        threads=8,
        alignment_device=alignment_device or "cuda",
        cache_dir=cache_dir,
        timeout_seconds=1800,
    )
