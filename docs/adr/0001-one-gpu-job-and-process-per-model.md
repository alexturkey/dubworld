# ADR 0001: One GPU job at a time, one process per heavy model

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0001)

## Context
The pipeline must run on a 4 GB VRAM card. Separation, recognition, alignment, diarization, gender classification and
TTS each need between ≈ 0.5 and ≈ 3.6 GB at peak. Inside a long-lived GUI/web process, memory fragments and leftover
CUDA state accumulate; after an OOM, `empty_cache()` did not reliably make room again.

## Decision
- Every heavy model runs in its own subprocess started with the same interpreter; the process exits after its job and
  the driver returns all of its memory.
- Models a stage needs together (language ID + transcription, recognition + alignment) run in sequential processes,
  never at the same time.
- Only one GPU job runs at a time, enforced by the resource lock (`runtime/kaynak_kilidi.py`, `gpu` capacity 1).

## Consequences
- Each stage pays process start-up and model load. Accepted: a resident CrisperWhisper worker was measured 17 % slower
  on the transcription step anyway.
- Failures are isolated: a crashed worker cannot poison the next stage.
- Workers report peak memory and a failure profile, which made OOMs diagnosable.

## Alternatives considered
- **Resident model server:** VRAM held between jobs, harder recovery after OOM; measured slower for the CT2 engine.
- **Two GPU jobs in parallel:** fits for small models, but each job ≈ 1.95× slower and total throughput +2.6 %; OOM risk.
- **Single process with `del` + `empty_cache()`:** insufficient after a real OOM.
