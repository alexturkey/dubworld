from __future__ import annotations

from dublaj_hatti.bolum_50_seslendirme.altyazili_dublaj.burnin import *
from dublaj_hatti.bolum_50_seslendirme.altyazili_dublaj.burnin import (
    SubtitleStyle as SupertonicSubtitleStyle,
    burn_subtitles_into_video,
    prepare_subtitle_burnin_assets,
)


def burn_supertonic_subtitles_into_video(
    input_video: str,
    output_video: str,
    run_dir: str,
    language: str,
    mode: str,
    timeline: list[dict] | None = None,
    timing_contract_path: str = "",
) -> dict:
    return burn_subtitles_into_video(
        input_video,
        output_video,
        run_dir,
        language,
        mode,
        timeline,
        engine="supertonic",
        debug_dir_name="supertonic_timing_debug",
        engine_label="Supertonic",
        timing_contract_path=timing_contract_path,
    )


def prepare_supertonic_subtitle_burnin_assets(
    input_video: str,
    output_video: str,
    run_dir: str,
    language: str,
    mode: str,
    timeline: list[dict] | None = None,
    burn_strategy: str = "one_pass_final_mux",
    timing_contract_path: str = "",
) -> dict:
    return prepare_subtitle_burnin_assets(
        input_video,
        output_video,
        run_dir,
        language,
        mode,
        timeline,
        burn_strategy,
        engine="supertonic",
        debug_dir_name="supertonic_timing_debug",
        engine_label="Supertonic",
        timing_contract_path=timing_contract_path,
    )
