# Transcription engines (except CrisperWhisper)

What was learned about each speech-to-text engine: settings, failures, speed and accuracy on a 4 GB card.
CrisperWhisper has its own page: [crisperwhisper_turbo_ct2.md](crisperwhisper_turbo_ct2.md). Türkçe:
[../muhendislik/transkripsiyon.md](../muhendislik/transkripsiyon.md).

Code: `src/dublaj_hatti/bolum_20_transkripsiyon/<engine>/`. Setting: `[transkripsiyon] motor`.

## 0. Engine labels

Older documents and logs refer to engines by menu number. The ones that matter here: **12** = CrisperWhisper 2 Medium (removed),
**13** = CrisperWhisper 2 Turbo CT2, **14** = Moonshine Medium Streaming (removed). The numbering is a presentation order, not a
quality ranking.

## 1. Comparison on a 10-file English corpus (measured)

3.9 hours of audio; reference transcripts from a commercial engine (not human; it also has zero-length words). WER is
corpus-level; "start MAE" is the mean absolute error of word start times against the reference.

| Engine | WER | × real time | Start MAE | p95 boundary error | zero-length words |
|---|---:|---:|---:|---:|---:|
| Parakeet INT8 (CPU) + CTC | **4.49 %** | 3.8 | 28 ms | 266 ms | 0 |
| WhisperX large-v3-turbo int8 + CTC | 4.67 % | 5.3 | 30 ms | 295 ms | 0 |
| WhisperX large-v3-turbo fp32 + CTC | 4.76 % | 4.3 | 30 ms | 297 ms | 0 |
| faster-whisper distil-large-v3 fp32 | 5.05 % | 6.7 | 123 ms | 501 ms | 899 |
| faster-whisper distil-large-v3 int8 | 5.11 % | 8.9 | 126 ms | 514 ms | 889 |
| distil-large-v3.5 fp32 | 5.64 % | 6.9 | 107 ms | 461 ms | 611 |
| distil-large-v3.5 int8 | 5.84 % | **9.2** | 106 ms | 453 ms | 664 |

- Short files: distil int8 equals fp32 and is faster. 9–22 minutes: WhisperX int8 leads. ≈ 70 minutes: Parakeet best.
- Engines whose word times come from CTC alignment are ≈ 4× more accurate at word starts than native distil timestamps.
- Every engine scored worse on Demucs-separated audio (descriptive, not a controlled test).
- VRAM: distil fp32 3427 / int8 1283 MiB; WhisperX fp32 3451 / int8 1147 MiB; Parakeet uses no VRAM (≈ 1.9 GB RAM).
- Raw outputs of this experiment were deleted after the write-up; only the numbers remain.

## 2. faster-whisper

- **Non-determinism:** the same audio gave different text on every run (new random state per subprocess;
  non-deterministic CUDA kernels). Seeds + `cudnn.deterministic` fixed segment counts but not text. Fix:
  `torch.use_deterministic_algorithms(True, warn_only=True)` + `CUBLAS_WORKSPACE_CONFIG=:4096:8` → word-identical text;
  0.02–0.08 s timestamp jitter remains and is accepted.
- **Compute types on Pascal:** `int8`, `float32`, `auto` (→ float32) work; `float16` and `int8_float16` are refused.
- medium + int8 dropped 29 s of speech (118 words vs 219 for medium fp32) on a test file; on Turkish, large-v3-turbo int8
  gave 286 words vs 284 for a cloud reference, while a medium model hallucinated a caption credit over the first 15 s.
  large-v3-turbo became the multilingual model.
- **Distil needs 128 mel bins:** a snapshot without `preprocessor_config.json` made faster-whisper fall back to 80 bins
  (shape error). For distil models the worker forces `FeatureExtractor(feature_size=128)`.
- **Distil decoder settings:** VAD off, `condition_on_previous_text=False`, temperature 0, beam 5, best_of 5,
  `word_timestamps=True`, empty initial prompt. Beam 10 gave the same text and was slower.
- **Short tests mislead:** on 90 s, previous-text conditioning looked best; on 67 minutes it fell into a repetition loop
  (local WER 29 %); turning it off gave 6.0 % vs 7.9 % WER overall. **Long files decide.**
- fp32 vs int8: different word sequences on 4 of 6 files; kept as two separate options (quality vs speed).

## 3. WhisperX

- **Separate environment:** WhisperX 3.8.6 with its own torch (cu128 on Windows), pyannote and TorchCodec. Lessons from
  building it: mixed package indexes hung pip (torch installed `--no-deps`); TorchCodec 0.15 had a DLL error (pinned
  0.7.0); TorchCodec 0.7 does not work with FFmpeg 8 (FFmpeg 7.1 shared build used).
- **Upgrade before workaround:** WhisperX 3.8.2 dropped tokens with digits/symbols in alignment; an LLM verbalisation
  layer was built, then removed when 3.8.6 aligned them natively (see [word_alignment.md](word_alignment.md)).
- **Batch size (measured, fp32):** batch 1 was **≈ 41 % faster** than batch 2 on two long files (416.7 → 242.9 s and
  235.7 → 140.1 s); batch 4 was slowest; a repeated batch-2 control ruled out warm-up effects; text identical. Rule:
  changing batch size requires a 2 → 1 → 2 control on at least two long files.
- **Decoder profile (measured):** fp32 with `suppress_tokens=[]` cut WER on a 106 s clip from 3.93 % to 0.91 %; int8 did
  not change. Naming trap: `[]` turns **off** the default non-speech suppression; `[-1]` expands to the default set.
  The worker reads back the options the loaded model actually uses and stops if they differ from the profile. Two runs
  gave byte-identical JSON.
- **OOM:** see [gpu_memory_and_isolation.md](gpu_memory_and_isolation.md) §4. A reproducible OOM on a 42-minute file had a
  clear cause: pyannote VAD on the GPU left 130 MiB free. VAD moved to the CPU (onset 0.500, offset 0.363, chunk 30),
  freeing ≈ 424 MiB; the file completed (539.6 s, 7,228 words) with identical text. A real CUDA OOM retries once in int8.
- **Alignment speed patches:** a trellis patch saved ≈ 20 s on 67 minutes under 3.8.2 but broke under 3.8.6 and is off;
  the main cost is transcription, not alignment.
- fp32 vs int8 on 10 short videos: 6 identical, 4 with small changes; int8 ≈ 11 % faster. fp32 is the default.
- **Open:** an unexplained 85 s vs 416 s difference for the same file in two different measurement harnesses.

## 4. Parakeet (CPU) + CTC

- `sherpa-onnx` Parakeet Unified EN 0.6B INT8, CPU only, English. 8 threads best (96.9 s in 11.9 s).
- **Decoder (measured, 396 s):** greedy 11.1 % WER; modified beam, 4 paths, blank penalty 2.0 → **8.4 %** (chosen); higher
  penalties invent repetitions (3.5 → 12.3 %). 8 paths: same WER, 49 % slower. FP32: worse and 2× slower.
- **The "OOM" that was an input limit:** 43 minutes as one stream asked ONNX for a 10.4 GB MatMul. The encoder accepts at
  most 5000 steps × 80 ms = **400 s**: 400.000 s works, 400.080 s gives unstable text, 400.160 s a shape error. Current
  method: ≤ 399 s in one piece; longer audio is cut at the midpoint of the last ≥ 600 ms silence before 399 s (hard cut
  logged if none); pieces must add up to the input sample count. Lesson: read tensor shapes and test the exact boundary
  before blaming memory.
- The CTC window lesson (a 6.4 s gap inside one window) is in [word_alignment.md](word_alignment.md) §3.
- **Open:** no automatic language probe when the language is `auto`; one hard slowed-down clip still fails closed.

## 5–7. Removed engines

whisper.cpp (CPU) + CTC, Moonshine Medium Streaming, CrisperWhisper 2 Medium, Speechmatics and ElevenLabs Scribe v2 were removed from the product: none was a default, none had been tested end to end on real audio, and each overlapped faster-whisper, Parakeet or CrisperWhisper Turbo. Their sections are gone from this page; the history is in the git log and in `CHANGELOG.md`. A saved setting that names one of them still loads: it warns and falls back to `auto`.

## 8. Subtitle-file source (json3)

Caption times are used only as window hints; final word times come from CTC; the word list must match 1:1; no leading
pad. Timeout `max(120, 90 + minutes × 8)` s.

## 9. Common settings

- **Leading pad:** 1.0 s of silence before recognition for faster-whisper, WhisperX and
  Parakeet so the first word is not clipped; subtracted exactly once.
- **VAD per engine:** faster-whisper (non-distil) Silero 0.5 / 500 ms / pad 300 ms; distil off; WhisperX pyannote on CPU;
  Parakeet only to propose cut points above 399 s; CrisperWhisper Silero on CPU.
- **Language detection order:** platform/user language → configured language → engine auto-detect. The distil (English
  only) gate: with `auto`, detect on 3 VAD segments; distil stays only if the language is `en` with P(en) ≥ 0.90,
  otherwise switch to WhisperX turbo fp32 (logged). Measured: English P(en)=0.995 stayed on distil; an Indonesian clip (P(en)=0.767) switched and was
  detected correctly.
- **Profiling:** each run writes `transcription_profile_<engine>.json` (per-step time and peak CUDA memory, decoder
  profile, VAD provider/device) even on failure.

## 10. Cross-engine lessons

1. Do not feed previous text back into the decoder (`condition_on_previous_text=False`, `max_context=0`): it removed
   repetition loops in three engines.
2. On a 4 GB Pascal card: smaller batches, VAD on the CPU, no fp16, and int8 is not equivalent to fp32.
3. An "OOM" can be an input-length limit or two components sharing the GPU.
4. Measure text accuracy and timing accuracy separately; verify that no words are lost.
5. Pin versions and re-check every patch after an upgrade.
6. Never repair native timestamps in place; let the gate reject them.
7. Acceptance needs full-length audio: loops, timing reversals and the 400 s limit only appeared on long files.
