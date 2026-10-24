# ADR 0003: Decide whether to run separation from a measured background level

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0003)

## Context
Separation costs minutes and can remove real speech (measured on a Chinese clip: the vocal stem lost words that the raw
audio kept). Most clean-speech inputs do not need it, but music under speech should be preserved in the dub.

## Decision
`auto_background` mode: measure the dynamic range of 50 ms frames (95th − 5th percentile). Below 32 dB = background
present; peak below −60 dB = silence, not background. If background is present, Demucs runs only to produce the
`no_vocals` track for the mix, while recognition uses the **raw** 16 kHz mono audio.

## Consequences
- Calibration on earlier runs: no clear-background case missed, ≈ 90 % precision; measuring ≈ 15 hours of audio took 24 s.
- Limits: calibration clips ≤ 4 minutes, English, one recognizer, no ground truth; long inputs can mix clean and music
  windows.

## Alternatives considered
- Always separate: slower and sometimes harms recognition.
- Never separate: background music is lost from the dub.
- A decision per 30 s window: separated the groups worse (85–89 %).
