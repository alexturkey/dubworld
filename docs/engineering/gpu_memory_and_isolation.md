# GPU memory, process isolation and the resource lock

This page explains how the pipeline fits every GPU model into a 4 GB card, how out-of-memory (OOM) errors were
diagnosed and fixed, and which rules came out of that work. Türkçe: [../muhendislik/gpu_bellek_ve_yalitim.md](../muhendislik/gpu_bellek_ve_yalitim.md).

Evidence labels used on every engineering page:

- **measured**: the project ran it and kept the numbers. Unless stated otherwise: a 4 GB VRAM,
  Pascal-class GPU (compute capability 6.1), Windows, 16 GB system RAM.
- **documented**: written down as a rule or finding, with no stored run behind the number.
- **no record**: nothing was found; treat it as unknown.

## 1. What the card can and cannot do (measured)

| Fact | Consequence |
|---|---|
| fp32 ≈ 1.86 TFLOPS, fp16 ≈ 1.77 TFLOPS (no Tensor Cores on Pascal) | fp16 gives **no speed-up**; use it only to make a model fit |
| bf16 is emulated (≈ 1.03 TFLOPS) | never use bf16 |
| int8 matmul (dp4a) ≈ 8.16 TOPS, ≈ 4.4× fp32 | int8 is the real speed lever |
| CTranslate2 has no `float16` compute on this card | CT2 engines use `int8`, `int8_float32` or `float32` |
| CUDA 11.8 and 12.x work; CUDA 13 wheels dropped sm_61 | do not install cu13x torch builds; the "CUDA 13.0" shown by `nvidia-smi` is only the driver ceiling |
| `torch.compile` / Triton do not work | do not enable them |
| Linux `torch 2.8.0+cu128` wheels carry no sm_61 kernels; `torch.cuda.is_available()` still returns True and the first matmul fails with "no kernel image is available" (the Windows cu128 wheel does carry sm_61) | on Linux pin a cu126 build; a health check must run a real CUDA matmul, not only `is_available()` |

## 2. Measured VRAM peaks per model

| Model / stage | Precision | Peak VRAM |
|---|---|---|
| Demucs `htdemucs`, batch 4 (75 min audio) | fp32 | ≈ 2.75 GB device, ≈ 1.69 GB allocated by torch |
| WhisperX large-v3-turbo | fp32 / int8 | 3451 MiB / 1147 MiB |
| faster-whisper distil-large-v3 | fp32 / int8 | 3427 MiB / 1283 MiB |
| CrisperWhisper Turbo (CTranslate2) | int8 | ≈ 1.4 GB |
| CrisperWhisper 2 Medium (Transformers) | fp16 | 3.5–3.6 GB (fp32 does not fit) |
| CTC word alignment (wav2vec2) | fp32 | up to ≈ 1.65–2.4 GB depending on language model |

Model file size is not VRAM need: one speech-enhancement model with 213 MB of weights reached 10.45 GB of
`max_memory_allocated` (measured). Always measure peak memory before adding a model.

## 3. Rules that came out of the OOM work

1. **One GPU job at a time.** Two CTranslate2 jobs do fit together, but each runs ≈ 1.95× longer and total
   throughput rises only ≈ 2.6 % (measured). Concurrency is not worth the OOM risk.
2. **Every heavy model runs in its own subprocess** (Demucs, WhisperX, faster-whisper, CTC alignment, gender
   classifier, TTS worker, CrisperWhisper). When the process exits the driver returns all of its memory.
   Inside a long-lived GUI/web process, fragmentation and leftover CUDA state accumulate, and `empty_cache()`
   does not reliably recover a process after an OOM (documented).
3. **Two models never share the card.** Where an engine needs two models (language ID + transcription,
   ASR + alignment) they run in sequential processes.
4. **`cudnn.benchmark = False` in every worker.** On this card benchmark mode made one model ≈ 200× slower
   and another ≈ 3.4× slower (measured); it gave no Demucs gain in a real trial.
5. **Never set `CUDA_LAUNCH_BLOCKING=1`.** Removing it made Demucs 19 % faster with identical VRAM (measured,
   88-minute input).
6. **Measure batch size, never assume it.** WhisperX fp32 was ≈ 41 % faster at batch 1 than at batch 2; the
   CT2 encoder gained nothing from batch 2 or 4; Demucs gained ≈ 23 % at batch 4 (all measured).
7. **Move secondary work to the CPU.** pyannote VAD on the CPU freed ≈ 424 MiB next to an fp32 ASR model and
   turned an OOM into a completed run with identical output (see [transcription.md](transcription.md)).
8. **Watch for silent shared-memory spill.** When VRAM overflows, the Windows WDDM driver spills to system RAM
   over PCIe; work becomes 2–8× slower and `nvidia-smi` does not show it. Symptom: `torch.cuda.max_memory_reserved()`
   above ≈ 3.9 GB, or a growing "Shared GPU memory" counter in Task Manager. A documented guard is
   `torch.cuda.set_per_process_memory_fraction(0.86)` so a job fails instead of spilling; it is **not wired into
   the code** yet.
9. **`nvidia-smi` can miss a process's CUDA context** (≈ 700 MB). Use `torch.cuda.mem_get_info()` for true
   free memory.
10. **Keep frequently loaded models on an SSD.** Cold `import torch` took ≈ 10 s from SSD and 38–44 s from HDD;
    every 1 GB of weights on HDD added ≈ 12 s to a cold start (measured).

## 4. Intermittent WhisperX OOM: diagnosis, not guesswork

- **Problem:** WhisperX language detection (`detect_language → model.encode`, large-v3-turbo fp32, batch 1)
  occasionally failed with `CUDA failed with error out of memory`. The same audio and settings later succeeded
  in a fresh worker.
- **Root cause:** **not proven.** Video length, file and settings were ruled out as the sole cause. The
  remaining hypothesis is transient GPU state or allocation spikes at the 4 GB edge.
- **What was built instead of a guess:**
  - The parent writes `gpu_diagnostics.jsonl` in the run folder with `before_worker`, `after_worker`,
    `worker_failure` and `worker_timeout` events (full `nvidia-smi` output plus torch free/total/allocated/reserved;
    safe when `nvidia-smi` is missing).
  - The worker writes `transcription_profile_whisperx.json` even on failure: PID, parent PID, the failing step,
    CUDA snapshots and per-step peaks.
  - Triage order: `profile_summary.failure_stage`/`failure_type` → failing step's `cuda_snapshot` → compare with
    `before_whisper_transcribe` → PID match → cross-check the `nvidia-smi` process table.
- **Recovery policy:** a real CUDA OOM (message contains both "CUDA" and "out of memory") in a float32 worker
  ends the worker, the OS frees VRAM, and the same model retries **once in int8**. No third attempt. Timeouts,
  JSON, alignment or file errors never trigger this retry. The first OOM profile is kept next to the result and
  the run metadata records the precision actually used.
- **Still open:** the original trigger is unknown.

## 5. Python environments: why there is more than one

- **Problem:** engines need conflicting pins. Historically the main environment was held at an old torch/numpy
  pair by one TTS dependency, not by the card.
- **Rule:** if a new package wants to change an environment's pins, it gets its own isolated environment and is
  called as a subprocess. After any install, re-measure the environment (torch build, CUDA, cuDNN, key packages).
- **Lessons (measured):**
  - "CUDA 12 is unsupported on this card" was false; it had simply never been tried, and the false belief led to
    a hand-made DLL workaround.
  - On Windows, CTranslate2 loads **every** `*.dll` in its package folder. Hand-copied DLLs (a renamed CUDA 11
    cuBLAS posing as `cublas64_12.dll`, an unused cuDNN 9 set) were loaded into every process. Replacing them
    with the real `nvidia-cublas-cu12` wheel gave identical decode time and bit-identical output, and the folder
    shrank from 2.03 GB to 0.61 GB.
  - torch loads its own bundled cuDNN, not a system-wide one.
  - A missing `cublas64_12.dll` silently drops to a ≈ 2× slower path.
  - `pip install torch` without the CUDA `--index-url` installs the CPU build; some packages (pyannote and
    others) pulled torch back to CPU during install; pip `onnxruntime` is CPU-only.
  - Measure with production decode settings. faster-whisper defaults include temperature fallback, which gave
    242–268 words on the same 92.8 s clip (2–10 % text drift); production settings `temperature=0.0`,
    `condition_on_previous_text=False` gave the same 241 words in 6/6 runs.
- This repository targets one main environment; the CrisperWhisper Turbo engine keeps its own WSL environment
  (see [crisperwhisper_turbo_ct2.md](crisperwhisper_turbo_ct2.md)).

## 6. Model cache: one root

- **Problem:** the same weights were downloaded twice (a separate `TRANSFORMERS_CACHE`, a user-profile cache,
  a stray copy in the project root).
- **Solution:**
  - Single root `runtime_assets/model_cache/` with `huggingface/hub`, `torch/hub/checkpoints`, `modelscope/hub`.
  - `HF_HOME`, `HF_HUB_CACHE` (= `TRANSFORMERS_CACHE`, same folder) and `TORCH_HOME` are set in the child
    environment **before** torch/whisperx/faster-whisper are imported; these libraries read them at import time.
  - Fast path: load the local snapshot (`local_files_only=True`). On failure, verify manifest SHA-256 values,
    re-download only missing or corrupt files, retry once, then fail with a clear message. No endless repair loop.
  - A disk snapshot is not a resident model; workers keep a process-local cache that dies with the worker.
  - Duplicates were deleted only after SHA-256 equality checks and a real offline load.

## 7. Resource lock (GPU queue)

- **Problem:** the app's own job queue and outside tools could start GPU jobs at the same time, causing OOM or
  slowdowns.
- **Solution:** `bolum_00_omurga/runtime/kaynak_kilidi.py`.
  - Resources and capacities: `gpu` 1, `cpu_agir` (heavy CPU) 2, `ag` (network) 3, `ucretli_api` (paid API) 2.
  - Leases are JSON files created atomically with `O_CREAT | O_EXCL`; after writing, the holder count is re-checked
    and the lease backs out if capacity is exceeded. A lease is valid while its PID lives and before its optional
    expiry; dead or expired leases are removed lazily.
  - CLI: `calistir --kaynak gpu --sahip <owner> --amac <purpose> --bekle N -- <command>` runs one command under the
    lock (polls every 5 s up to N s) and returns the child's exit code, or **75** if the resource stayed busy.
    `al --sure <min>` takes a timed lease, `birak` releases it, `durum [--json]` shows the state.
- **Lessons:**
  - On Windows, process liveness is checked with `OpenProcess` + `GetExitCodeProcess`; "access denied" counts as
    alive. `os.kill(pid, 0)` must not be used on Windows: it sends `CTRL_C_EVENT` to the console group.
  - A script that already takes the lock must not be wrapped in a second lock, or it waits for itself.
  - After `--` pass a single command, not a `cmd /c a && b` chain (that broke repeatedly).
- **Still open:** NVENC encoding also uses the GPU; NVENC was measured ≈ 3.6× slower while CUDA work ran at the
  same time, so do not overlap encoding with GPU inference.

## 8. Checklist for a GPU run

- Before: lock state shows `gpu 0/1`; no other compute process; free RAM ≥ the model's peak + 1.5 GB.
- During: `max_memory_reserved` < 3.9 GB; shared GPU memory not growing.
- After: lock released; `nvidia-smi` back to ≈ 0 MiB; no orphaned ffmpeg or python processes.

## 9. Open items

1. The main pipeline module still sets `cudnn.benchmark = True` and `torch.set_num_threads(4)`, contradicting
   rule 4. Workers are unaffected because they are separate processes; anything run in-process inherits it.
2. `PYTORCH_CUDA_ALLOC_CONF` (`expandable_segments`), hardware-accelerated GPU scheduling and the
   memory-fraction guard were never tried in code.
3. The trigger of the intermittent WhisperX OOM is unknown.

## 10. How we measure (applies to every page)

- Each change is tested in an isolated experiment folder with a manifest; accepting an experiment does not
  integrate it; integration needs a second proof through the real application entry point.
- Baseline the **current** implementation, change one variable, keep the same input hash.
- Compare outputs sample by sample (audio) or word by word with times (transcripts); accept only stated
  tolerances.
- Time the worker and the outer application call separately; they differ (process start, imports, CUDA context,
  report validation).
- Collect telemetry from outside the process (`nvidia-smi` ≈ every 1 s, process-tree RAM ≈ every 0.5 s); no
  profiler hooks inside inference. Keep the CPU idle while timing GPU work; cross the order of A/B runs because
  the same path varied by ≈ 10 % between runs.
- RAM pressure, GPU compute saturation and VRAM exhaustion are three different failures; call something an OOM
  only with real CUDA evidence. A useful kill switch for long CPU experiments is a free-RAM floor (1.5 GiB was used).
