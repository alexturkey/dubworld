# ADR 0015: Supertonic is the default TTS; VoxCPM2 and XTTS v2 are optional engines in their own process

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0015)

## Context
The pipeline needs one text-to-speech engine that works on every machine, including machines without an NVIDIA GPU,
whose licence allows redistribution of the weights' download path, and whose duration behaviour is predictable enough
for the timing layer ([ADR 0010](0010-real-tts-duration-is-canonical.md)). Two capabilities are outside Supertonic's
scope: designed voices with strong Turkish quality, and speech in the timbre of a reference recording.

An earlier version of the pipeline ran XTTS v2 inside the main application; that version established the rules below:

- The Coqui TTS package pinned the main environment to an old torch / CUDA 11.8 / numpy 1.22 combination; the GPU itself
  did not require that (documented, [gpu_memory_and_isolation.md](../engineering/gpu_memory_and_isolation.md) §5).
- It ran in a thread of the long-lived application process and released memory only with `del` + `empty_cache()`,
  which is not equivalent to a process exit ([ADR 0001](0001-one-gpu-job-and-process-per-model.md)).
- Its weights are under the Coqui Public Model License (non-commercial).

## Decision
- **Default `ses.motor = "supertonic"`.** ONNX on the CPU (4 lanes × 2 threads), ten built-in voices, fixed speed per
  voice, a measured synthesis recipe and silence clean-up ([tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md)
  §2). The candidate / repair flows and the optional `atempo` step of the timing layer were built and measured on this
  engine.
- **VoxCPM2 (optional):** runs in the sister VoxCPM2 repository's own environment as one subprocess per job (the model
  is loaded once for all segments). NVIDIA GPU only; the CPU path is refused because it was far slower than real time.
- **XTTS v2 (optional):** coqui-tts is installed as an extra (`tts-xtts`) or in a separate environment named by
  `DUBLAJ_XTTS_PYTHON`; synthesis always runs in a separate subprocess (`xtts_tts/kosucu.py`) that imports nothing from
  this package, so its memory is fully released when it exits. It requires a recorded CPML acceptance and a reference
  recording supplied by the user (own voice or the owner's explicit permission).
- **One result contract for every engine.** Each engine returns per-segment WAVs; the shared execution layer trims,
  resamples and physically measures `processed_duration`, and the shared mixer places each segment at its start time.
  Subtitles, background mix, loudness, checkpoints and the optional RVC layer do not depend on which engine spoke.
- **Timing differences are explicit:** real-TTS candidate selection, repair rounds and `atempo` run only for
  Supertonic with an LLM translation backend (`dubber.should_use_real_tts_candidate_selection`). VoxCPM2 and XTTS
  produce one take per segment; the video retiming step absorbs the measured difference.
- No engine falls back to another engine ([ADR 0009](0009-fail-closed-no-silent-fallback.md)); a missing install,
  missing licence acceptance, missing reference or unsupported language is an error before synthesis starts.

## Consequences
- The default install synthesises on any machine without a GPU and without a non-commercial licence step.
- The main environment no longer carries the Coqui pins; installing XTTS cannot change the versions other stages use
  when a separate environment is used.
- VoxCPM2 and XTTS pay model load once per job and give no per-segment duration repair.
- XTTS has no measurement in this repository (speed, VRAM); the earlier version recorded ≈ 2 GB VRAM for model load
  and a ≈ 17.5 % gain from a fused-attention patch that this repository does not apply (documented).

## Alternatives considered
- **XTTS as default:** non-commercial weights, requires a reference voice and a GPU for usable speed, and pinned the
  main environment.
- **VoxCPM2 as default:** needs an NVIDIA GPU (2.6–3.0 GB VRAM) and a separate install.
- **Cloud TTS services used in the earlier version:** no offline path, results not reproducible, and one of them fell
  back to another service silently; not carried over.
- **Importing XTTS in-process:** rejected by ADR 0001 and by the dependency pins above.
