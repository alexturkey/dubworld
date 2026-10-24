# ADR 0010: Real synthesized duration is the only duration used for timing

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0010)

## Context
Changing Supertonic's in-model speed changed what it generated (dropped or repeated words). Engine duration estimates,
internal attention boundaries and RMS trimming produced wrong cuts and subtitles.

## Decision
- One fixed speed per voice, accepted only after 5/5 exact ASR matches on fixed texts.
- The execution layer measures `processed_duration` of the real audio; acceptance band 0.90–1.15 implied video speed;
  optional pure `atempo` within 0.90–1.25; the video absorbs the remaining difference.
- Word times of generated audio come from forced alignment of the real candidate audio.

## Consequences
More synthesis and alignment work per candidate; repeatable output (the seed excludes speed).

## Alternatives considered
Global or dynamic in-model speed; engine duration estimates; attention/RMS timing; padding translations to fill time.
