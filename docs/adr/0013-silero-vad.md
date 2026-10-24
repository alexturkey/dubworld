# ADR 0013: Silero VAD replaces FSMN VAD in speaker separation

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0013)

## Context
Speaker separation (3D-Speaker, CAM++ embeddings + clustering) found speech regions with the upstream FSMN VAD
(`iic/speech_fsmn_vad_zh-cn-16k-common-pytorch`). That model runs through `modelscope` → `funasr`, and `funasr` imports
`kaldiio` at module load. `kaldiio` 2.18.1 ships under an NTT evaluation agreement that allows internal evaluation only and
forbids redistribution, so it cannot be a dependency of an Apache-2.0 project. Installing `funasr` without `kaldiio` was
tried: `funasr` fails at import (`funasr/utils/load_utils.py` imports `kaldiio` at the top), so FSMN cannot run without it.

## Decision
Use **Silero VAD v6 (MIT)** as shipped inside `faster-whisper` (already a core dependency; no extra model download) in
the vendored `speakerlab/bin/infer_diarization.py` (`SileroVad`): threshold 0.5, minimum speech 250 ms, minimum silence
100 ms, padding 30 ms, 16 kHz mono input (other rates are refused). `funasr` and `kaldiio` are removed from `pyproject.toml`,
the requirement files and the model manifest (4 FSMN files); vendored scripts that imported them and were never called by
the pipeline were deleted (listed in the vendor's `VENDOR_NOTU.md`, Apache-2.0 §4b). CAM++ embeddings and the clustering
settings are unchanged.

## Consequences
- The dependency tree is redistributable; 26 packages left the GPU/CPU locks with no version change for the rest.
- Smoke test on the 22.8 s two-speaker sample: 2 speakers, 6 segments, same speaker count as with FSMN.
- Not yet measured: segment boundaries FSMN vs Silero on a longer, harder clip; if a long recording merges speakers,
  compare boundaries before changing the clustering thresholds.

## Alternatives considered
Keep FSMN and ship `kaldiio` (licence forbids redistribution); install `funasr --no-deps` without `kaldiio` (fails at
import, tried); pyannote segmentation (≈ 9.5 GB peak for the 4.x community pipeline, gated model; does not fit 4 GB);
energy-based VAD and WebRTC VAD (not tried: no learned speech model / extra native dependency, while Silero is
already installed).
