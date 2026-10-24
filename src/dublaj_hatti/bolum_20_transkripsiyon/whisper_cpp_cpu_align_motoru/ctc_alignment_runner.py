from __future__ import annotations

from pathlib import Path
from typing import Any

from dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama import run_ctc_word_alignment

from .config import WhisperCppCpuAlignConfig
from .debug_report import write_json


def run_ctc_alignment(
    audio_path: Path,
    segments_json: Path,
    debug_dir: Path,
    config: WhisperCppCpuAlignConfig,
) -> dict[str, Any]:
    cache_dir = config.cache_dir or str(debug_dir / "cache")
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    data = run_ctc_word_alignment(
        audio_path,
        segments_json,
        config.language,
        cache_dir,
        config.timeout_seconds,
        device=config.alignment_device,
        debug_dir=debug_dir,
    )
    write_json(debug_dir / "alignment_result_words.json", data)
    return data
