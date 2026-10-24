# ADR 0009: Fail closed, no silent fallback

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0009)

## Context
A rate-limited translator once fell back to the source text; an untranslated video was voiced and reported as
"completed". Elsewhere a backend selection was silently overwritten in three places, and a separation failure could have
continued with raw audio.

## Decision
- A stage either produces its validated output or the job stops with a clear, masked error message
  (`runtime/hata_aciklama.py`).
- Allowed: an explicitly documented equivalent path (NVENC → x264) and one bounded retry inside the same engine for a
  classified transient error (WhisperX OOM → int8 once, Demucs OOM → batch 1 once, API 503 → backoff then defer).
- Not allowed: switching to another engine, model or to the source text without the user's choice.

## Consequences
More visible failures, no silently wrong deliverables. Every retry is recorded in the run metadata.

## Resolved exception
The local Opus-MT engine previously returned the source text when the model output was empty. It now raises
`YerelCeviriHatasi` with the affected segment numbers.
