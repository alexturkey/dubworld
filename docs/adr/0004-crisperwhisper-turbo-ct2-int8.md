# ADR 0004: CrisperWhisper Turbo through CTranslate2 int8 in a one-shot WSL2 worker

Status: accepted (optional engine, non-commercial weights) · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0004)

## Context
Verbatim transcription (fillers, repetitions) matters for dub timing. CrisperWhisper 2 Medium on Transformers fp16 needs
3.5–3.6 GB and was slow. The CTranslate2 fork that carries CrisperWhisper's alignment heads ships only Linux wheels.
Pascal has no fast fp16.

## Decision
- Turbo model converted to CTranslate2 (fp16 storage), run with **int8 compute**, beam 1, verbatim mode.
- Runs in WSL2 as a one-shot subprocess with atomic JSON request/response files; no server, no port, no resident model.
- Word times come from the shared CTC aligner, not from the engine ([ADR 0005](0005-ctc-forced-alignment-only-time-source.md)).
- No CPU fallback. Weights are never shipped; they are downloaded at a pinned commit + SHA-256 and converted locally.

## Consequences
- ≈ 1.4 GB VRAM; 11× real time on 10 English files with the model loaded once; ≈ 397 s end-to-end for 74 minutes.
- Requires WSL2; WSL start-up dominates small jobs.
- Non-commercial licence: optional, behind an explicit installer flag.

## Alternatives considered
- Medium converted to CT2 (fp32 or int8): failed a strict word-and-time equality gate.
- Resident WSL worker: 16.9 % slower on the transcription step.
- Speculative decoding with a small draft model: 1.92× slower and not exact.
