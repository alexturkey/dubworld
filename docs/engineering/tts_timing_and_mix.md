# TTS, timing and mixing

How Turkish speech is synthesised, how its duration is matched to the source, and how it is mixed with the
background. Türkçe: [../muhendislik/tts_zamanlama_ve_karisim.md](../muhendislik/tts_zamanlama_ve_karisim.md).
Decision record: [ADR 0010](../adr/0010-real-tts-duration-is-canonical.md).

## 1. TTS architecture (three layers)

- **Engine box:** text → waveform + sample rate, with its own voice, seed and speed logic. It never selects candidates,
  decides repairs or borrows another engine's settings. Deleting one engine box breaks only that engine.
- **Execution layer:** prepares final audio, applies common post-processing and **physically measures**
  `processed_duration`, the only duration used in decisions. An engine's own duration estimate is recorded only when the
  engine really knows it.
- **Timing/repair layer** (engine-agnostic): acceptance band, `too_short_audio` / `too_long_audio`, repair rounds,
  reuse of accepted segments. Band: implied video speed **0.90–1.15** (above 1.15 the audio is too short, below 0.90 too
  long).

## 2. Supertonic

### 2.1 Fixed speed per voice (dynamic speed removed)

- **Problem:** a global speed (1.20) and later a dynamic per-segment speed (0.85–1.45) produced wrong audio: dropped
  final words, swapped or repeated syllables, unrelated phrases. A speed that worked could fail at a nearby value, and
  the subtitle still showed the full text.
- **Root cause:** Supertonic `speed` is an in-model synthesis parameter, not post-hoc time stretching; changing it
  changes what the model generates. Forced alignment places the expected text on the audio, so it does not notice
  missing speech.
- **Fix:** one fixed speed per voice:

| Voice | F1 | F2 | F3 | F4 | F5 | M1 | M2 | M3 | M4 | M5 |
|---|---|---|---|---|---|---|---|---|---|---|
| speed | 1.30 | 1.15 | 1.30 | 1.00 | 1.15 | 1.15 | 1.00 | 1.00 | 1.15 | 1.25 |

  An unknown voice raises an error. The seed is a SHA-256 of language + voice + steps + text; speed is not part of the
  seed, so audio approved in testing reproduces exactly.
- **Acceptance test:** each voice reads the same 5 Turkish texts into separate files, each transcribed on its own; a
  speed is accepted only if all 5 match after normalisation. A new speed or voice must pass the same 5/5.
- Duration reference (≈ 90-word paragraph, 1.00×): most voices 44–47 s; F4 40.7 s and M3 39.0 s shortest, F3 48.2 s
  longest; duration scales close to 1/speed.

### 2.2 CPU speed (ONNX Runtime)

Constraints: speed, steps, voice, seed and candidate count unchanged; audio and word boundaries must stay
byte-identical.

Rejected (measured): CUDA execution provider (much slower for one long text, and parallel use failed with
`cudaErrorStreamCaptureUnsupported`); DirectML (reshape error); OpenVINO (failed or slower, needs NumPy pinned);
manual batching (changed waveforms); `quantize_dynamic` (produced no quantized ops, the "gain" was noise); a process
pool of 4 (CPU contention).

Accepted, cumulative: 2–4 parallel lanes with 2 intra-op threads (final: **4 lanes × 2 threads**, never beaten across
192 real syntheses); one shared attention model prepared before lanes start; spinning off; session reuse across repair
rounds (round 2: 8.27 → 1.39 s); feed-dict reuse (1.17×); optimised ORT model cache (1.22–1.26×; session setup
3.9 → 2.2 s, peak RSS ≈ 3.0 → 1.8 GB); memory-pattern options off (1.13×); vectorised trimming. Windows process pools
need the `if __name__ == "__main__"` guard; parallelise within a repair round, never across rounds.

### 2.3 Current synthesis recipe ("K15")

- The factory 8-step sampling had quality defects; a clean 22-step recipe was expensive. 16 recipes were scored by ASR
  WER and listening; the chosen one costs ≈ 52–54 % less than the clean reference with 0 % WER on the test paragraph.
- Duration predictor once; target length = predicted length / profile speed; 7 Euler steps at normal length, linear
  interpolation of the latent to the target length, 3 more steps (10 total) on a fixed time grid; CFG 5 (patched in
  memory, weights on disk untouched, separate optimised cache).
- The recipe id is part of the runtime, candidate-cache and checkpoint keys; changing it regenerates TTS but keeps
  source, ASR and translation.
- Verified: earlier accepted records reproduce within 1.2e-7; all 10 voices finite, true peak below −1.1 dBTP.

### 2.4 Silence "shadows" removed before the vocoder

- **Problem:** a faint hiss at speech boundaries, 45–60 dB below speech, audible on headphones.
- **Root cause (measured by decoding latent frames one at a time):** frames are silence (< −95 dB), speech (> −50 dB)
  or unstable (−63 … −80 dB). The model writes "neither speech nor silence" frames at transitions and the vocoder
  renders them faithfully; the vocoder itself was proven innocent.
- **Rejected:** post-hoc frame zeroing (risks cutting word tails), CFG/seed/noise/step changes (the shadow moved),
  blending toward silence, anchoring silence inside the sampler (timbre loss), using the mean as silence (hum).
- **Fix:** vocoder pass 1 → frames 20 dB below peak become candidates → classify in one batched decode → mask silence
  frames, very quiet frames and unstable frames next to silence (with propagation) → replace with one canonical silence
  latent (SHA-256 verified) → vocoder pass 2 only if something changed. Speech frames, duration and timing are never
  touched.
- **Measured:** cleaned frames −64…−84 dB → −85…−108 dB; first 150 ms after a word −67.6 → −82.9 dB; speech level change
  ≤ 1.6 dB; cost +15–20 %.
- **Open:** a pitch-locked 5–11 kHz buzz on vowels.

### 2.5 Process lifecycle

- **Problem:** a 58 s video spent 445 s in TTS. Synthesis ran in a thread of a long-lived process whose global contexts
  kept a full ONNX session per voice × lane from earlier jobs; private memory grew past physical RAM.
- **Fix:** one worker subprocess per request (per voice group), no global pool; results returned as float32 NPY verified
  by SHA-256, shape, dtype and finiteness; the worker exits if its parent disappears.
- **Measured:** outputs byte-identical; main process 54–59 MB; matched re-runs 269 → 200 s, 398 → 307 s and
  646 → 203 s total (translation also differed, so not all of the gain is credited to this change). Trade-off: each
  request pays model load.

### 2.6 Retired timing sources

Word times from Supertonic's internal attention and RMS trimming of leading/trailing silence were used early on. They
drifted and could collapse onto structural tokens, and were removed. **The only time source is forced alignment.**

## 3. Candidate alignment (timing the generated speech)

- Candidates are concatenated into lanes with real-silence separators, each lane is aligned once, and the result is
  split back per segment. Verified candidate word timelines are mapped to the video timeline and reused for subtitles;
  final re-alignment is skipped when they exist.
- An over-eager change once tied cuts to the next aligned word and dropped the physical silence fence, so neighbouring
  segments' audio bled together; it was reverted. Rule: lanes ≤ 30 s with a single segment use one window; short
  multi-segment lanes and lanes > 30 s get one window per physical chunk (built from real chunk text and sample counts).
- **Boundary tolerance (measured):** last words overshot the window end by ≈ 20 ms, first words by 0.1–0.3 ms. Policy:
  start tolerance 5 ms; only the terminal word's end may overshoot, by up to 25 ms, and is clamped; any other overshoot
  invalidates the candidate (never silently cropped). Demux works in integer samples; > 1 sample outside is a hard
  error.
- **Token tolerance:** a 362-segment job died because the aligner returned `P E C` for an expected spelled acronym
  `P İ E C`. Not a resource problem (620 MB allocated, return code 0). Rule: exactly one missing single-character token,
  not first, with all words mapped 1:1 and a positive local gap, is placed into that gap; everything else (missing
  normal word, reordering, ≥ 2 missing, negative or overlapping times) stays fatal.

## 4. Duration matching

### 4.1 Optional atempo (setting in the recommended flow)

- Pure `atempo=<factor>` filter on mono float32: no EQ, pitch or loudness filters.
- `required = processed_duration / target_duration`; closed band **0.90–1.25**; factor rounded to 6 decimals; 1.0 is a
  no-op.
- No-repair modes: choose the best candidate as if atempo were off, then clamp the factor to the band; only the chosen
  candidate is processed. Repair modes: only candidates already inside the band qualify, closest to 1.00 wins.
- No second alignment: word times are scaled linearly by `out_duration / pre_atempo_duration`.
- Variants are keyed by candidate, segment, target sample count and factor so identical text in different segments never
  overwrites another's audio.
- Changing the band requires re-running real duration and pitch tests.

### 4.2 The video absorbs the rest

- `video_speed = original_duration / tts_duration`; the video is retimed with `trim` + `setpts`. Gaps between segments
  are kept as their own timeline items, so pauses survive.
- When source audio (the background) is retimed, atempo factors above 2.0 or below 0.5 are split into chained steps.
- Bug fixed: total duration was taken from the container instead of the video stream (195.05 vs 194.93 s), creating an
  artificial 1.5 s last batch. Always use the `v:0` stream duration and merge a short last batch into the previous one.

## 5. Loudness

- **Problem:** final dubs were quiet (−23 to −26 LUFS integrated).
- **Tried:** gain + limiter (not enough by ear); speech normalisation + loudnorm + limiter (louder, but compressor/EQ
  variants crackled).
- **Found on the way:** Supertonic outputs 44.1 kHz but the pipeline default was 24 kHz, so audio was resampled for
  nothing. The sample rate now follows the engine.
- **Current (character-preserving):** loudnorm is used **only to measure**; one constant gain is applied to the whole
  file: `gain_dB = min(−18 − LUFS, −1.3 − true_peak_dBTP)`. Target ≈ −18 LUFS, design ceiling −1.3 dBTP, acceptance
  −1.1 dBTP. No EQ, compressor or limiter. Intermediate files are float WAV so nothing clips before the gain. Each output
  gets a `.gain.json`.

## 6. Background mix

- The separated `no_vocals` track is retimed onto the new timeline and mixed with the dub using
  `amix=inputs=2:duration=longest:normalize=0` (no automatic normalisation, no ducking). For Supertonic there is no
  limiter: the float sum is written and the constant gain from §5 is applied.
- **Memory fix (measured):** segment WAVs are read lazily instead of cached, and peak scanning works in 65,536-sample
  blocks: 15 minutes of audio 606 → 154 MiB peak (−75 %), output SHA-256 unchanged.
- **Open:** the full-timeline mix array is still held in memory (not streamed); no measured background level or ducking
  target.

## 7. VoxCPM2 in this repository

VoxCPM2 is the second TTS engine here (Apache-2.0 code and weights). It runs as a one-session subprocess in its own
environment and returns results in the same contract as Supertonic. Measurements in this pipeline: **no record yet**.
A related lesson from running VoxCPM2 on the same 4 GB card: when the generator plus the audio VAE approached 4 GB,
≈ 1.2 GB spilled into shared memory and generation slowed from 70 to 171 s without any error; see the shared-memory rule
in [gpu_memory_and_isolation.md](gpu_memory_and_isolation.md).

## 8. Lessons from a removed engine (XTTS v2)

XTTS v2 was later re-added as an optional engine with a different integration (own subprocess, optional own
environment, licence acceptance, user reference voice, no candidate or `atempo` step): [ADR 0015](../adr/0015-tts-engine-set-and-default.md),
[motorlar/xtts.md](../motorlar/xtts.md). The lessons below come from the earlier in-process integration.

- Every "obvious" GPU speed-up lost on Pascal: `cudnn.benchmark` 3.4× slower, `torch.compile` 3.1× slower, fp16
  autocast 14.5 % slower, `model.half()` broke the vocoder, INT8 CPU-only and slower.
- What worked was asking "is the GPU fed efficiently?": decoding ran at 25 tokens/s against a ≈ 64 tokens/s memory
  bandwidth limit. Replacing the attention implementation with fused `scaled_dot_product_attention` (same maths) gave
  +22.6 % in a benchmark and +17.5 % in production.
- A subtitle gate kept requiring an old alignment file after the pipeline switched to candidate timelines; an old test
  fabricated that file and hid the bug. Lesson: consumers must read a versioned contract, and tests must not fabricate
  prerequisites (see [video_subtitles_and_resume.md](video_subtitles_and_resume.md)).

## 9. Open items

- Three Supertonic lanes under the current recipe were never measured.
- Atempo-variant reuse checks only the key and alignment success, not the full validation of base candidates.
- Vowel buzz at 5–11 kHz; streaming mix; background level target.
