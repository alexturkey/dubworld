from .silence_cleanup import get_silence_cleanup_profile

# Neden: 16 tarif WER + dinlemeyle olculdu; bu tarif temiz 22 adimdan ~%52-54 ucuz, %0 WER. Kimlik ara kayit anahtarinda. bkz. docs/engineering/pinned-values.md#supertonic-synthesis
SUPERTONIC_SYNTHESIS_CONTRACT = "supertonic_k15_cfg5_7plus3_silence_v2"
SUPERTONIC_TOTAL_STEPS = 10
SUPERTONIC_TRANSITION_STEP = 7
SUPERTONIC_CFG_SCALE = 5.0
SUPERTONIC_TIME_GRID = (
    0.0, 0.10, 0.16, 0.22, 0.36, 0.50,
    (0.50 + 14 / 22) / 2, 14 / 22, 0.78, 0.90, 1.0,
)


def get_supertonic_synthesis_profile():
    return {
        "contract": SUPERTONIC_SYNTHESIS_CONTRACT,
        "cfg_scale": SUPERTONIC_CFG_SCALE,
        "total_steps": SUPERTONIC_TOTAL_STEPS,
        "transition_step": SUPERTONIC_TRANSITION_STEP,
        "time_grid": list(SUPERTONIC_TIME_GRID),
        "seed_policy": "text_language_voice_steps_sha256_then_chunk_offset",
        "silence_cleanup": get_silence_cleanup_profile(),
    }
