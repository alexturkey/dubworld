# CrisperWhisper engines ("engine 12" Medium and "engine 13" Turbo CT2)

The optional verbatim transcription engines: why they exist, how the Turbo engine was made to run in ≈ 1.4 GB of
VRAM, every long-form and multilingual failure that was fixed, and the speed work. Türkçe:
[../muhendislik/crisperwhisper_turbo_ct2.md](../muhendislik/crisperwhisper_turbo_ct2.md).
Evidence labels: see [gpu_memory_and_isolation.md](gpu_memory_and_isolation.md).

> **Licence.** CrisperWhisper 2.0 weights are released under the nyra health Non-Commercial Research License.
> Converted (CTranslate2 / int8) weights are a derivative work: they may not be redistributed under an open licence
> or served as an API. This repository ships **no** weights; `scripts/kur.ps1 -Adim crisper -TicariOlmayanKabul`
> downloads them at a pinned commit with SHA-256 and converts them locally. The code (CrisperWhisper package, the
> CTranslate2 fork) is MIT.

## 1. Identity

| | Engine 12: CrisperWhisper 2 Medium | Engine 13: CrisperWhisper 2 Turbo CT2 |
|---|---|---|
| Backend | Transformers, CUDA fp16 | CTranslate2 fork with CrisperWhisper alignment heads; fp16 storage, **int8 compute**; beam 1 |
| Runs in | its own Windows environment | WSL2 Ubuntu (one-shot subprocess per request) |
| Word times | the model's own attention times | **shared CTC forced alignment** (native times are kept only for diagnostics) |
| VRAM peak | 3.5–3.6 GB (fp32 does not fit) | ≈ 1.4 GB |
| Code | `bolum_20_transkripsiyon/crisperwhisper2_medium_motoru/` | `bolum_20_transkripsiyon/crisperwhisper_turbo_ct2_motoru/` |

The two engines share no environment, snapshot, artefact names or adapters; Turbo keeps a local copy of the
"dubbing-ready" text logic instead of importing it.

## 2. Decision: why CTranslate2, WSL2 and int8 (see also [ADR 0004](../adr/0004-crisperwhisper-turbo-ct2-int8.md))

- **Goal:** keep verbatim transcription (fillers, repetitions, false starts are part of a dub's timing) and reach
  ≥ 5× real time on long English audio within 4 GB.
- **Constraint:** the CTranslate2 fork that carries CrisperWhisper's alignment heads and word-timing code ships
  **only manylinux x86_64 wheels**. The engine therefore runs inside WSL2, called from Windows as a one-shot
  subprocess with atomic JSON request/response files: no HTTP server, no port, no resident model.
- **Why int8:** Pascal has no fast fp16 and CTranslate2 has no fp16 compute on this card; int8 is the fast path.
- **Rejected for Medium:** CT2 float32 and int8 conversions of Medium did not pass a strict word-and-time equality
  gate against the Transformers reference, so Medium stays on Transformers fp16. Recorded lessons: "conversion alone
  is not a solution"; "int8 can look fast on short audio and not generalise".
- **Rejected for Turbo:** a persistent model server. A resident WSL worker passed the exactness gate but made the
  transcription step **16.9 % slower** (131.7 → 154.0 s); setup savings fell outside the step (measured).
- No CPU fallback: if CUDA int8 is not supported the engine stops with an error.

## 3. Conversion and environment pitfalls (measured)

1. **Pascal and Linux torch wheels.** Linux `torch 2.8.0+cu128` has no sm_61 kernels. `torch.cuda.is_available()`
   is True, the first matmul fails with "no kernel image is available". Pin `torch==2.8.0+cu126` on Linux; the health
   check runs a real 64×64 CUDA matmul.
2. **CT2 `config.json` overwritten.** The CrisperWhisper 2.0.1 converter overwrites CTranslate2's `config.json` with
   the Hugging Face config. CT2 expects `lang_ids`, `alignment_heads` and `suppress_ids`; `detect_language` then
   fails with "type must be number, but is number". Fix: rebuild the CT2 config from `generation_config.json` +
   `added_tokens.json`; the result is byte-identical to a known-good config.
3. **The converter drops `encoder_blank_head.*`** (reported as UNEXPECTED). If a future converter keeps these
   tensors, rerun the acceptance gate; do not assume old results.
4. **Temp WAV with a `.part` suffix:** `soundfile` cannot infer the format from the extension; pass `format="WAV"`.
5. **Conversion needs ≈ 4.5 GB of free RAM.**
6. Storage type (fp16) and compute type (int8) are separate settings; do not confuse them.
7. The CTranslate2 fork's source could not be verified (metadata URL 404, no sdist); "fork = upstream" is not assumed.

## 4. Fixed decoding profile (Turbo)

- Verbatim mode, word timestamps on, temperature fallback on, `max_new_tokens=400`, speculative decoding off,
  hallucination mitigation on, early-end-of-text recovery on, beam 1.
- `suppress_tokens=null` means "use the model's own list", **not** "no suppression"; `[]` is a different setting.
- Beam 5 gave the same text on two test files and was slower; rejected.
- Coverage recovery `direct_0_8_first`: if the base decode is under-covered with ≤ 1 word, try temperature 0.8 first
  with seeds 7, 8, 6; otherwise the library fallback with temperatures (0.8, 0.4, 0.6, 1.0).
- VAD: Silero (ONNX, CPU) threshold 0.15, negative 0.01, min speech 0 ms, min silence 100 ms, pad 600 ms.
- Long-form windows: 29.5 s, overlap 1.0 s (up to 10 s), at least 2 context words.
- Quality invariant: never delete text, invent times or silently substitute "intended" (clean) text for verbatim.

## 5. Long-form failures and their fixes

Every fix below was proven on the failing input **and** on earlier inputs that had to stay byte-identical.

### 5.1 Window coverage recovery

- **Symptom:** `unvalidated transition` partway through a 31-minute file.
- **Root cause:** a window that returned at least one word was accepted, and the next window started from the
  *planned* end instead of the last real word, leaving a 14.9 s uncovered tail. The next window could rewind only
  10 s, so the overlap held no previous words and the two-word stitch anchor was impossible. The visible stitch error
  was a safety gate catching an earlier bad acceptance.
- **Fix:** `tail = planned_end − last_timed_word_end`; limit `min(5 s, max(3 s, 15 % of the window))`. Above the limit,
  do not advance: rewind to the last timed word, re-read with growing overlaps (1.5/3/5/7/10 s), require a ≥ 2-word
  anchor, fail closed if there is no progress. "Planned end" and "proven end" are kept as separate fields. The
  15 %/3–5 s formula was reused from an earlier gate validated on real English audio, not invented.
- **Measured:** the 31-minute file completed (68 windows, 1 recovery, 0 quality errors); 28 words that had never
  been produced came back. Two control files stayed byte-identical.

### 5.2 Stitch boundary overlap

- **Symptom:** `invalid_word_timing` (a word starting before the previous word ended) at three places in a
  25-minute Spanish file.
- **Root cause:** all three were the first word appended from a new window after a stitch. The text anchor was
  right, but two independent windows placed the boundary 100–220 ms apart; the stitch treated text validity as time
  validity and only repaired overlaps up to 50 ms.
- **Rejected:** raising the 50 ms limit to 250/500 ms (could hide false anchors on repeated phrases).
- **Fix:** validate the text anchor, then the time boundary. If only the two neighbouring intervals overlap, put one
  shared boundary at the **midpoint of the intersection** (only those two edges move); otherwise reject the candidate
  and try the next overlap. A later revision also keeps genuinely repeated words ("code code") when the second start is
  strictly later.
- **Measured:** 3,782 words, 41 stitches, 5 local repairs, 0 timing errors; control files unchanged except one
  boundary moved by 5 ms (exact midpoint of a 10 ms intersection).

### 5.3 Repetition acceptance

Five or more identical consecutive words/phrases are accepted as real speech only if every occurrence has a numeric
start and the starts are **strictly increasing** (no tolerance); otherwise they are treated as a decoder loop.

### 5.4 VAD tail

- **Symptom:** the job got stuck after the last word of a 27-minute file.
- **Root cause:** Silero raised speech probability for only 32 ms; with minimum speech 0 ms and two 600 ms pads, the
  speech band ran 3.5 s past the last real word; every overlap attempt returned no new word.
- **Rejected:** raising the VAD threshold or minimum speech duration (could cut real short words like "yes"), or
  blindly accepting the tail.
- **Fix:** a final VAD tail is excluded as unconfirmed speech **only** when it is the last language run, every attempt
  read to the end, each had a valid anchor and boundary, all returned "no appended word" and none advanced. Words and
  times are untouched; any conflicting evidence fails closed.

### 5.5 Failure diagnostics

- Every exception after a window is accepted writes a quality-failure JSON atomically (language run, local/global
  seconds, VAD span, all overlap candidates with both sides' words and times, anchor, reject reason, accepted windows).
  Before this, the evidence lived only in RAM and the user saw one line.
- Turbo writes its long-word check file **before** the gate decides, so it survives a rejection.
- Not guaranteed: import errors before the run starts, hard kills, native crashes.
- Lesson: an apparent rise in failures turned out to be failure + resume rows of the same inputs counted twice.

## 6. Word times: from native attention to mandatory CTC (runtime v6)

- **Problem:** on a 53 s clip, Turbo and a commercial reference agreed on all 117 words, but Turbo's native times were
  degenerate (a word lasting 0 ms, a final word lasting 40 ms). A 40 ms source slot against 578 ms of TTS would have
  slowed the video ≈ 14.5×.
- **Root cause:** native timing combines time-normalised attention with a mel-energy blank decision and can emit zero
  or very short placements. The custom Softmax kernel was ruled out (byte-identical attention with stock CT2).
- **Rejected:** raising the final-segment threshold (hides the error); a Turbo-only CTC worker (second engine-specific
  aligner).
- **Fix:** after the WSL worker exits, the same shared CTC alignment box used by other engines aligns Turbo's text
  (see [word_alignment.md](word_alignment.md)). Text bytes must be preserved exactly; words must be positive-length,
  inside the audio, ordered and non-overlapping; no fallback to native times. The change invalidated older
  transcription checkpoints but kept download, separation and ASR preparation.
- **Long-word gate:** a word longer than 1.5 s is accepted only if it lies inside its measured speech span (±150 ms,
  ≤ 300 ms repair) **and** an independent raw-energy check finds no silent run over 0.5 s inside it (20 ms frames,
  ±2 s context, threshold = floor + 35 % of floor-to-peak, veto if contrast < 6 dB). Energy only vetoes; it never
  moves times. Calibration on 7 voices: real words had at most 0.36 s internal silence; the veto caught 31 of 36
  synthetic "pause-swallowing" words, the rest are caught by the span check. A real 1.66 s spelled-out product name
  now passes.
- **Events and fillers:** 13 event tags validated against the tokenizer are removed from the dubbing text and kept with
  their times; `[UM]`/`[UH]` stay as words; unknown bracketed text is preserved and reported; raw output is always kept.

## 7. Languages

### 7.1 Language detection modes (setting `crisper_dil_tespiti`)

1. **`global_first_window`** (default): if a platform/user language is given and the model knows it, use it;
   otherwise detect once on the first ≤ 29.5 s of speech and process the whole file in that language.
2. **`per_window`** (Medium, legacy): score every window and merge adjacent same-language windows into runs.
   Cost ≈ 1.25 s per 29.5 s window, i.e. +4–5 % of runtime; 0 unstable decisions in 242 repeated inferences (measured).
3. **`continuous_stream`**: a 4 s moving context, 1 s ticks; each tick needs top probability ≥ 0.60 and margin ≥ 0.20;
   two consecutive confident ticks confirm a language or a change; the boundary is placed midway between the last
   stable and first confirmed tick. A given platform language is evidence only, never the decision.
   Measured on a concatenated Turkish + English + German file (17.9 s): switches found at 5.5 s and 11.0 s,
   10 / 13 / 12 words, unchanged after every later optimisation.

### 7.2 Per-language work

| Language | What was done | Status |
|---|---|---|
| English | int8 acceptance on 10 voices, coverage recovery, CTC times, long-word gate, speed work | production |
| Spanish | stitch midpoint fix (Medium) | Medium production; Turbo no separate record |
| Chinese | space-less "continuation" path from the first window; multi-byte tokens decoded as whole groups; content-token counting instead of `split()`; 448-position decoder budget (prompt capped at 192 + 256 reserved) | production |
| Japanese | per-token decoding produced U+FFFD → Unicode-safe regrouping; plain-transcribe sibling; reject if > 3 s of active audio remains after the last timed group; CTC character regroup | production |
| Thai, Lao, Burmese, Cantonese | share the space-less route | **no real-audio acceptance**, no CTC model |
| Turkish | mixed-language test; truncated-word probe | see the standalone STT repository's measurements |
| German | segment of the mixed-language test only | test only |

Lessons from the Chinese/Japanese work:

- The library counted words with `decode().split()`; for space-less scripts that is 0 or 1 word. Count content
  tokens instead.
- `context_words=1` could hold a 201-token "word" and overflow the 448-position decoder; `context_words=0` was
  rejected because a `[-0:]` slice selects *everything*.
- A fix that exists only in a probe script is not shipped; prove it through the real entry point.
- WhisperX alignment splits Chinese/Japanese into characters; regroup to source words (first timed character's start,
  last one's end) and raise on any mismatch.
- Out-of-the-box CrisperWhisper on an 85 s Chinese clip: default CT2 path failed with a float16 backend error before
  reading audio; the Transformers verbatim path produced 4 of 4 empty windows; the timestamped "intended" path hit
  the 448-position limit. The project's runtime produced timed output.
- Separation can remove real speech in these languages: compare direct audio before changing the decoder
  (see [source_audio_and_separation.md](source_audio_and_separation.md)).
- A truncated Turkish word was completed by the decoder ("oluş-" → "oluştur."). Disabling temperature fallback or
  early-end recovery changed nothing (4 combinations identical): the completion happens in the base decode.
  Untested ideas: token confidence or an acoustic end check.

## 8. Speed

### 8.1 Acceptance run (int8, single process, model loaded once)

10 English files, 6,678 s of audio in 605 s: **11.0× real time**, every file ≥ 5× (e.g. 30 s → 14.3×, 49 min → 10.7×).
Model load 17 s excluded. This is not the production lifecycle (one worker per request).

### 8.2 What did not help (measured)

| Idea | Result |
|---|---|
| Resident worker + resident model | transcription step 16.9 % slower |
| Speculative decoding with a small draft model | 1.92× slower, and not exact (punctuation lost, word times moved up to 400 ms) |
| Encoder batch 2 / 4 | 0.999× / 1.005×, noise |
| `cub_caching` allocator | 12.7 % slower than the default `cuda_malloc_async` |
| Decode window N while encoding N+1 (two streams) | 0.984× (contention on Pascal) |
| Batching windows | impossible: each window start depends on the previous decode |
| Two jobs at once | fit (2.9 GB peak) but each ≈ 1.95× slower; throughput +2.6 % |
| venv + model on the WSL ext4 disk | slower (80/73 s vs 59.8 s on the Windows mount): model load improved but hash, import and detection got slower on a cold virtual disk |
| Attention algorithm sweep | 0.05 % gain; one variant moved word boundaries; rejected |

### 8.3 What helped (measured, outputs identical)

- **End-to-end tweaks:** 8 MiB read buffer for full SHA-256; CPU VAD in parallel with CT2 model load; encoder output
  reuse inside the same window; for files ≥ 64 MiB on a Windows mount, hashing with the Windows host Python
  (1.6 GB model: 12.4 → 4.7 s); VAD with preallocated I/O binding. Results: −3.5 % (74-min English) to −24 %
  (short clips). Lesson: an uncontrolled ≈ 32 s difference was WSL start-up; always pair the WSL start state in A/B.
- **Custom CUDA Softmax for CT2 (compute capability 6.1 only):** profiling showed 32 Softmax calls costing ≈ 429 ms
  per encoder pass. A kernel with padded shared memory, register-held `exp`, warp-shuffle max and **the same float
  summation order** was byte-equal on 73 matrix cases and 8 real encoder outputs. Large-matrix median
  7.9 → 5.4 ms with 256 threads per block (512 and 128 were slower: fewer threads is not monotonically better).
  End-to-end on a 74-minute file ≈ 439 → 397 s. Loaded via `LD_PRELOAD` after verifying SHA-256 of the shim, PTX and
  the installed CT2 library; any other GPU or CT2 build falls back to stock kernels and needs a fresh acceptance.
  Note: renaming a source file changed only symbol-table bytes; the new pinned hash was justified by a binary diff
  instead of loosening the gate.

### 8.4 Where time goes (169 s clip, measured)

| Stage | s |
|---|---:|
| Total | 88.7 |
| ASR subprocess | 61.1 (model load + native prep 16.3, decode 13.6, imports 3.6, prechecks 4.7, language 1.4, start/write/exit 20.8) |
| CTC subprocess | 22.0 (model load 8.1, alignment 9.0, imports 3.2) |
| Glue | 5.6 |

Running CTC preparation in parallel with ASR was measured to hide ≈ 11–12 s (CTC 16.4 s alone vs 19.3 s concurrent,
engine not slower, output identical); **not integrated**.

### 8.5 Memory

- 74-minute English: peak 1,435 MiB of 4,096 (model loaded 911 MiB + 524 MiB working); GPU ≈ 74 % busy.
- ASR and alignment run in separate, sequential processes, so the card never holds both models.
- After every job: worker processes gone, ≈ 0 MiB VRAM.

### 8.6 Medium speed work

Language-routed optimisations (encoder caching and selective eager paths; for Chinese/Japanese an extra SDPA path and
3 consensus seeds in one GPU batch) gave 1.45–3.56× speed-ups with 19/19 test voices exactly equal on text, words,
times and language. A 5× target was closed as impossible for one file: two mandatory eager decoder windows alone
exceeded the time budget.

## 9. Open items

1. A 3-minute target for 74 minutes of English was never met (best ≈ 397 s).
2. Parallel CTC preparation (≈ −12 s) not integrated.
3. The custom Softmax covers compute capability 6.1 only.
4. Thai/Lao/Burmese/Cantonese have no real-audio acceptance.
5. Very weak fillers may attach to neighbouring sound; truncated words are completed by the decoder.
6. ≈ 500 normalised differences against a commercial reference on 10 English files are not yet classified by listening;
   only 2 were confirmed mishearings. The reference is treated as recall evidence, not ground truth.
