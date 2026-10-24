from __future__ import annotations

from pathlib import Path
from typing import Any

from dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama import run_ctc_word_alignment

from .config import ParakeetCpuAlignConfig


def run_alignment(
    audio_path: Path,
    segments_path: Path,
    debug_dir: Path,
    config: ParakeetCpuAlignConfig,
) -> dict[str, Any]:
    cache_dir = config.cache_dir or str(debug_dir / "cache")
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    return run_ctc_word_alignment(
        audio_path,
        segments_path,
        config.language,
        cache_dir,
        config.timeout_seconds,
        device=config.alignment_device,
        debug_dir=debug_dir,
    )
