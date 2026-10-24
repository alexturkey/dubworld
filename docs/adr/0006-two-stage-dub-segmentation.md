# ADR 0006: Two-stage dub segmentation (1.0 s gap, then at most 150 words)

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0006)

## Context
Dub segments must follow speech pauses, not the recognizer's context windows, and must stay small enough for translation
calls. Earlier rules (punctuation only, every speaker change, a separate gate for unpunctuated transcripts, 25 s caps)
were inconsistent across engines.

## Decision
One segmenter for every source (`nihai_dublaj_segmentleri.py`): a new main segment at any gap > 1.0 s; a main segment of
≥ 151 words is split only internally at `.` → `?` → `!` → `,` (greedy up to 150), with a hard cut at 150 as the last
resort. Times come from each segment's own first and last word. Speaker is metadata; speaker splits happen later, inside a
main segment, with groups shorter than 0.40 s merged into a neighbour.

## Consequences
- 0 word loss, duplication or reordering (checked by invariants).
- No engine-specific segment path to maintain.
- No A/B record for 1.0 s vs the older 0.6 s gap.

## Alternatives considered
Engine segments; a 0.6 s gap; forced splits at speaker changes; fixed-size chunks; raising translator output caps instead
of sizing groups.
