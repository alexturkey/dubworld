# ADR 0002: Demucs in a batched two-stem worker with a one-time OOM fallback

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0002)

## Context
Stock Demucs (`htdemucs`) sends one 7.8 s segment per GPU call, and the first custom worker accumulated all four stems
in CPU RAM. On 75 minutes of audio this meant ≈ 12 minutes of worker time and a RAM peak that pushed a 16 GB system to 93 %.

## Decision
- Own worker: groups of 4 padded chunks per model call (`overlap=0.25`, `shifts=0`, the model's own segment length,
  never forced).
- Reduce each chunk on the GPU to `[vocals, drums+bass+other]` before accumulation; free reference, input and model
  tensors as early as possible; preserve the maths (`no_vocals*std + 3*mean`).
- On a real `torch.cuda.OutOfMemoryError` only: free memory and retry once at batch 1; record it in the report.
- The parent validates the worker report; exit code 0 alone is not success. A Demucs failure stops the job.

## Consequences
- Measured: worker 11 m 48 s → 5 m 52 s; RAM peak 9.52 → 7.15 GB; VRAM peak ≈ 2.75 GB device.
- Output is not byte-identical to batch 1: up to 1 int16 step on ≈ 0.03 % of samples (accepted tolerance).
- One Demucs worker at a time; concurrent runs are untested.

## Alternatives considered
- `--segment 12` (rejected by the model) / forced `--segment 7` (slower than the default).
- `CUDA_LAUNCH_BLOCKING=1`, `cudnn.benchmark=True`: slower or no gain.
- CPU separation: correct but far too slow for long inputs.
