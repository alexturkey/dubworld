# ADR 0007: "Natural blocks" translation contract

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0007)

## Context
Segment IDs are timeline keys. Segment-by-segment translation sounds like subtitles; free translation followed by
re-splitting moves meaning into the neighbouring ID and desynchronises speech and subtitles. Prompt wording alone or
JSON mode alone did not hold the contract (measured with an API provider: IDs dropped, fragments merged, meaning padded).

## Decision
- Per segment exactly one natural Turkish candidate whose meaning stays in its own ID; the model writes spoken forms of
  numbers and symbols (no digits in candidates).
- A strict schema with an ownership self-check; independent code gates (expected IDs, non-empty, catastrophic coverage:
  source ≥ 8 words and candidate words × 4 < source words → reject); at most one targeted chain-review retry.
- Timing is advisory here; the final timing decision uses real synthesized audio ([ADR 0010](0010-real-tts-duration-is-canonical.md)).

## Consequences
- One validated text feeds both subtitles and TTS.
- Requires an LLM backend; the local Opus-MT fallback cannot provide this contract.

## Alternatives considered
Literal per-segment translation; merge and re-split; verbatim span evidence for every word (removed); a second LLM audit
pass (≈ one extra translation pass, its own failures, not integrated); many candidates + TTS selection (kept as other modes).
