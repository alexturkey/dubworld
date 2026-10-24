# Running on a 4 GB GPU (or no GPU)

A practical guide. Every value here was measured or used in production on a 4 GB VRAM, Pascal-class GPU
(compute capability 6.1) with 16 GB of system RAM. The reasons behind each value are on the linked pages.
Türkçe: [../muhendislik/dusuk_vram.md](../muhendislik/dusuk_vram.md).

## 1. Install

- Install torch from the CUDA index (the installer does this). `pip install torch` without `--index-url` gives a CPU
  build; some packages pull torch back to CPU during install — re-check after every install:
  `python -c "import torch; print(torch.__version__, torch.cuda.is_available())"`.
- Do not use CUDA 13 builds on Pascal (sm_61 was dropped). On Linux, use a cu126 torch build: Linux cu128 wheels have no
  sm_61 kernels, yet `torch.cuda.is_available()` still returns True. The installer's `kontrol` step
  (`scripts/kur.ps1 -Adim kontrol`) runs a real 64×64 CUDA matmul for this reason.
- Keep the model cache (`runtime_assets/model_cache`) on an SSD: cold starts were ≈ 12 s slower per GB of weights on an
  HDD.
- Conversion of the optional CrisperWhisper Turbo model needs ≈ 4.5 GB of free RAM.

## 2. Settings that fit 4 GB

| Stage | Setting | Peak |
|---|---|---|
| Separation (optional) | `ses_temizligi.kip = "auto_background"` or `"original"`; Demucs `htdemucs`, batch 4 with automatic one-time retry at batch 1 on OOM, overlap 0.25, shifts 0, no forced segment | ≈ 2.75 GB VRAM, ≈ 7.2 GB RAM for 75 min audio |
| Transcription | `transkripsiyon.motor = "auto"`; `hesap_tipi = "auto"` (code `hesap_tipi_coz`: on the GPU `float16` if CTranslate2 reports it, else `int8`, else `float32`; on this Pascal card CTranslate2 4.8.3 reports no `float16`, so `auto` = `int8`, measured). `float32` fits only when set by hand and nothing else uses the GPU | WhisperX turbo fp32 3.45 GB / int8 1.15 GB; CrisperWhisper Turbo int8 ≈ 1.4 GB |
| WhisperX | batch 1; VAD on the **CPU**; a real CUDA OOM retries once in int8 automatically | – |
| Word alignment | runs in its own process after recognition | ≈ 1.6–2.4 GB depending on language |
| Speakers + gender | separate subprocesses, one after another | < 1 GB each |
| TTS | Supertonic runs on the **CPU** (4 lanes × 2 threads); VoxCPM2 needs the GPU alone; its 4 GB build is described in the sister repository's [docs/4gb.md](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi/blob/main/docs/4gb.md) | – |
| Video | `video.cq = 26`; encoder chosen automatically (NVENC if it works, else x264) | – |

Rules that make this work:

1. **One GPU job at a time.** Do not run another GPU program while dubbing; two jobs can fit but each becomes ≈ 2× slower.
2. **Every model is a separate process** and frees its memory on exit. Do not try to keep models resident "for speed":
   a resident CrisperWhisper worker was measured 17 % slower.
3. **fp16 is not faster on Pascal** (no Tensor Cores); int8 is (≈ 4.4× fp32 throughput). bf16 is emulated: avoid it.
4. **Never set** `CUDA_LAUNCH_BLOCKING=1` or `torch.backends.cudnn.benchmark = True` (each cost 19 % to 200× in
   measurements).
5. **Do not raise batch sizes** without measuring: batch 1 was ≈ 41 % faster than batch 2 for WhisperX fp32.
6. **Do not encode with NVENC while CUDA inference runs** (≈ 3.6× slower).

## 3. Symptoms and fixes

| Symptom | Likely cause | What to do |
|---|---|---|
| `CUDA out of memory` in WhisperX | another component (VAD) or another program on the GPU | check `nvidia-smi` for other processes; the job retries once in int8; `gpu_diagnostics.jsonl` in the run folder shows memory before/after |
| `torch.cuda.OutOfMemoryError` in Demucs | long input at batch 4 | automatic retry at batch 1; the report shows `oom_fallback=true` |
| Job suddenly 2–8× slower, no error | VRAM overflowed into shared system memory (Windows) | Task Manager → GPU → "Shared GPU memory" growing; close other GPU programs; use int8 |
| `no kernel image is available for execution on the device` | torch build without sm_61 | install a cu118/cu126 build (Linux: cu126) |
| `float16` refused by CTranslate2 / faster-whisper | Pascal has no fp16 compute in CT2 | use `int8` or `float32` (`hesap_tipi = "auto"` does this) |
| An ONNX MatMul asks for ≈ 10 GB on long audio (Parakeet) | encoder input limit of 400 s, not memory | the engine already cuts at ≤ 399 s; do not raise it |
| Memory keeps growing during TTS over several jobs | sessions held by a long-lived process | TTS runs one subprocess per request; if you embed the library, do the same |
| `nvidia-smi` shows free memory but allocation fails | `nvidia-smi` can miss a process's CUDA context (≈ 700 MB) | measure with `torch.cuda.mem_get_info()` |

## 4. No NVIDIA GPU

- `--ayar genel.cihaz=cpu` (or `auto` on a machine without CUDA). The CLI hides CUDA before torch is imported.
- Transcription: faster-whisper int8 (or Parakeet / whisper.cpp for English); Supertonic TTS already runs on the CPU;
  video uses libx264. Separation on CPU is slow; prefer `ses_temizligi.kip = "original"`.
- The end-to-end CPU smoke test of this repository completed with the local Opus-MT translator
  (see [video_subtitles_and_resume.md](video_subtitles_and_resume.md) §7 for the problems it found).

## 5. Before and after a run

- Before: no other GPU process; free RAM ≥ largest model peak + 1.5 GB.
- During: `torch.cuda.max_memory_reserved()` < 3.9 GB; shared GPU memory not growing.
- After: `nvidia-smi` back to ≈ 0 MiB; no leftover python/ffmpeg processes.

More: [gpu_memory_and_isolation.md](gpu_memory_and_isolation.md) ·
[source_audio_and_separation.md](source_audio_and_separation.md) · [transcription.md](transcription.md) ·
[crisperwhisper_turbo_ct2.md](crisperwhisper_turbo_ct2.md).
