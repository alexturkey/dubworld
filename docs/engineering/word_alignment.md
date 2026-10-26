# Word alignment (CTC forced alignment)

Why every word time in the pipeline comes from CTC forced alignment, how windows must be prepared, and how the
"silence swallowed into a word" problem was solved. Türkçe: [../muhendislik/kelime_hizalama.md](../muhendislik/kelime_hizalama.md).
Decision record: [ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md).

## 1. Architecture

- **WhisperX engine:** uses its built-in `whisperx.align()` inside its worker.
- **Shared CTC box** `bolum_30_hizalama_ve_segment/ctc_kelime_hizalama/` (`client.py`, `worker.py`,
  `ctc_konusma_siniri.py`) for engines whose own timings are not trusted: CrisperWhisper Turbo, faster-whisper + CTC
  (`faster_whisper_ctc`, the `auto` fallback), Parakeet + align, subtitle-file sources.
- Engines that produce their own timings and do not enter the box: `faster-whisper` when chosen explicitly (native word timestamps, distil or not).
- **API:** `run_ctc_word_alignment(audio_path, segments_json, language, cache_dir, timeout_seconds, device="cuda", debug_dir=None)`;
  input `[{start, end, text}]`; returns `words{word,start,end,score}`, `segments`, `profile_summary`, `speech_spans`.
  Errors raise `CtcHizalamaHatasi` with the worker's own message.
- Runs in a subprocess (WhisperX 3.8.6); the model is released when the process exits.
- The same aligner is also used on the **generated** side: TTS candidates and the final dub track are re-aligned
  (see [tts_timing_and_mix.md](tts_timing_and_mix.md)).

### Alignment models (wav2vec2)

| Language | Model |
|---|---|
| en | torchaudio `WAV2VEC2_ASR_BASE_960H` |
| tr | `mpoyraz/wav2vec2-xls-r-300m-cv7-turkish` (CC BY 4.0, attribution) |
| id | `Galuh/wav2vec2-large-xlsr-indonesian` (project map; WhisperX's default table has no `id`) |
| pt, ko, el, zh | WhisperX default models |

Rejected for English (measured): preloading tensors on the GPU (same output, 1.4–1.9 % slower);
`WAV2VEC2_ASR_BASE_10M` (word times differed, no speed gain).

## 2. Why CTC and not something else

| Alternative | Why it was rejected |
|---|---|
| Engine segment boundaries | Follow the model's context window, not speech pauses. Measured: one 27.4 s engine segment held 60 words but only 17.2 s of speech and 10.2 s of gaps; TTS would have stretched 17 s of speech into 27 s |
| RMS trimming, TTS-engine word boundary events, TTS internal attention, duration-ratio scaling | Estimates, not measurements of the real audio; caused drift and false confidence in subtitles, candidate choice and cuts. Banned as time sources; a missing alignment fails loudly instead of falling back |
| Native Whisper word timestamps for the precise path | Kept only for the distil speed option. Measured on 42 min English against a commercial reference: WhisperX + CTC WER 12.1 % vs distil native 16.2 % |
| One aligner per engine | Replaced by one shared input-preparation layer + one CTC box; engines only report what time evidence they have (word, token, segment or none) |
| Swapping the CTC model for speed | Out of scope: only the way the tool runs may change, not the tool |

## 3. Window preparation matters (the Parakeet case)

- **Problem:** the preparation layer merged speech A, ≈ 6.4 s of non-speech and speech B into one CTC window. CTC found
  the right word in B but pulled the silence into that word's start. The text was right; durations were inflated, which
  caused abnormal dub speed-ups. The engine had itself reported the gap (last token ≈ 16.0 s, next ≈ 22.4 s).
- **Root cause:** a wrong mental model ("give CTC text and a wide window and it skips silence by itself"). CTC handles
  short gaps (≈ 0.4 s) well; long ambiguous gaps let it attach silence or music to a neighbouring word.
- **Fix:** a token gap ≥ 1.0 s that starts a new word is a natural gap. The left window closes 80 ms after the previous
  token and the right window opens 80 ms before the next (80 ms = one Parakeet encoder frame). The middle of a long
  silence goes into no window. The alignment-input contract was versioned so old windows are never reused from a
  checkpoint.
- **General rule:** padding comes from each engine's own time resolution; never copy 80 ms to another engine.
- **Mandatory post-checks:** every word timed; none dropped; order preserved; no over-long word; no absorbed silence;
  monotonic starts/ends; no overlaps; nothing beyond the audio end.

## 4. Silence swallowed at word ends: `ctc_speech_bounded_v2`

- **Problem:** on a 100-minute English file, 10 of 15,465 words were longer than 1.5 s (8 of them "uh"/"um") and the
  CrisperWhisper long-word gate correctly stopped the job.
- **Root cause (measured frame by frame):** 79–98 % of frames inside the stretched words were blank. WhisperX 3.8.6
  uses the older tutorial trellis, where "stay on the same token" is scored with the blank score, so repeated merging
  folds blank frames into the previous character. torchaudio's newer `forced_align` + `merge_tokens` treats blank as
  its own state. (An earlier engine-specific aligner had fixed this; the fix was lost when engines moved to the shared
  box.)
- **Variants measured on the 100-minute file:**

| Variant | words > 1.5 s | words < 40 ms | median | longest |
|---|---|---|---|---|
| WhisperX as is | 10 | 488 | 180 ms | 2.24 s |
| trim by argmax frames | 9 | 805 | 180 ms | 2.12 s |
| torchaudio `forced_align` only | 0 | 1,457 | 140 ms | 1.18 s |
| **WhisperX clamped to torchaudio span ± 150 ms** | **0** | **414** | **180 ms** | **1.26 s** |

  - torchaudio alone was rejected: its spiky output pushed 9 % of words under 40 ms, and a 40 ms word can cause a
    ≈ 14× video slow-down downstream.
  - Argmax trimming was rejected: the word separator counts as sound.
  - Two independent methods agreed on word starts within 20 ms (p95); the result was stable for pads of 100–200 ms.
- **Shipped:** keep WhisperX times; re-run the same model's frame decisions through torchaudio to get each word's real
  speech span; a word may extend at most 150 ms beyond it; with no overlap the word is moved to where sound was heard.
  `speech_spans` is returned in word order; a text mismatch leaves everything unbounded and reports it.
- **Measured after:** 100-minute file completes (571 words clipped, 177 moved, 0 unbounded, longest word 1.26 s,
  110 s of silence removed from words, 3 % of words changed). A 92 s file: text identical, 4 of 239 words shortened by
  10–50 ms. Spot check of moved words: 7 of 10 land exactly on the sound; 3 very weak fillers attach to the nearest
  sound.
- **Cost:** ≈ +85 s per 100 minutes (the model runs twice per window), accepted because WhisperX does not expose
  emissions and its internals are not patched.

## 5. Space-less scripts (Japanese, Chinese)

WhisperX splits `ja`/`zh` into characters and spaces consume frames. A Japanese job stopped with "alignment changed
transcript". Fix: send segment text without spaces, regroup the returned characters into source words (start of first
character, end of last, mean score), raise on any extra or missing character. Measured: 23/23 words, 0 repairs.
Thai, Lao and Burmese are treated as spaced by WhisperX and do not take this path. Downstream, segment text for
`ja, zh, yue, th, lo, my` is joined without spaces and full-width punctuation counts like ASCII punctuation.

## 6. Numbers and symbols (WhisperX 3.8.2 → 3.8.6)

- With WhisperX 3.8.2 clean alignment, tokens containing digits and symbols (`31%`, `10604`, currency) were **dropped**.
- First fix: an LLM call verbalised numbers before alignment and projected the aligned words back onto the original
  tokens (fail-fast on any mapping mismatch). It worked (174 normalised tokens mapped to 168 originals losslessly).
- Final fix: upgrading to **WhisperX 3.8.6**, which aligns these tokens natively (124/124 and 91/91 words on regression
  samples with `$50`, `31%`, `10,604`, `+ - / =`). The LLM normaliser was removed; nothing rewrites text before
  alignment any more.
- A "fast wildcard" trellis patch (align 204 → 184 s on a 67-minute file, identical output under 3.8.2) produced an
  off-by-one `IndexError` under 3.8.6 and is off by default. Backtrack beam width 1 moved 4 word times on the long
  reference; default stays 2.

## 7. GPU vs CPU

Default `device="cuda"`. A downstream tool that passed `device="cpu"` took ≈ 10 minutes for 3.5 minutes of audio;
on the GPU the same job took 66–71 s, most of it model load (measured). For very long inputs, chunked alignment is
needed (worker timeout 900 s).

## 8. Open items

- Window preparation for engines with no time evidence (VAD fallback) is defined as a rule but never measured.
- Very weak fillers can bind to neighbouring sound (within 150 ms).
- Changing the bounding policy name invalidates transcription checkpoints for all engines that use the box (by design).
