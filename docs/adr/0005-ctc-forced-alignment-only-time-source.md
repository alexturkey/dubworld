# ADR 0005: CTC forced alignment is the only source of word times

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0005)

## Context
Segment length, TTS duration targets, candidate choice, video retiming and subtitles all derive from word times.
Engine segments, TTS-engine boundary events, internal attention and RMS trimming each produced drift: e.g. a 27.4 s
engine segment that contained 10.2 s of gaps, or a 40 ms word that would have slowed the video ≈ 14×.

## Decision
- Source side: WhisperX 3.8.6 alignment (built-in for WhisperX, a shared CTC box for other engines) in its own
  subprocess, with `ctc_speech_bounded_v2` (each word clamped to the torchaudio-measured speech span ± 150 ms).
- Generated side: TTS candidates and the final dub are re-aligned the same way.
- No fallback: a missing alignment fails the job. Windows are prepared per engine (natural gaps excluded).

## Consequences
- ≈ +85 s per 100 minutes for speech bounding (the model runs twice per window).
- Integrity checks are mandatory (every word timed, ordered, non-overlapping, inside the audio).
- Changing the policy invalidates transcription checkpoints by design.

## Known exceptions
- `faster-whisper` chosen explicitly keeps Whisper's own word times (a deliberate speed/compatibility choice). `auto`
  never resolves to it: its permissive fallback is `faster_whisper_ctc` (same recogniser, shared CTC box).
- Cloud engines (`speechmatics`, `elevenlabs_scribe_v2`) keep the provider's word times; no CTC pass runs on them in
  the current code, and no comparison against CTC times is recorded.
- `crisperwhisper2_medium` keeps the model's own attention word times
  ([crisperwhisper_turbo_ct2.md](../engineering/crisperwhisper_turbo_ct2.md) §1).
- Generated-side alignment applies to Supertonic candidates and the final dub; VoxCPM2 and XTTS output is placed by
  its measured duration and aligned for subtitles only when subtitles are requested.

## Alternatives considered
- Native word timestamps (≈ 4× worse word starts on the test corpus), engine segments, RMS/attention timing: rejected.
- torchaudio `forced_align` alone: 9 % of words under 40 ms.
- LLM verbalisation of numbers before alignment: replaced by the WhisperX 3.8.6 upgrade.
- A different CTC model for speed: out of scope (the tool stays, only how it runs may change).
