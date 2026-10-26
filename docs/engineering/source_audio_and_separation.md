# Source audio, phase repair and Demucs vocal separation

How the pipeline turns an input video into audio for speech recognition and dubbing, and how Demucs was made
to fit and run fast on a 4 GB card. Türkçe: [../muhendislik/kaynak_ses_ve_ayristirma.md](../muhendislik/kaynak_ses_ve_ayristirma.md).
Evidence labels (measured / documented / no record) are defined in [gpu_memory_and_isolation.md](gpu_memory_and_isolation.md).

Code: `src/dublaj_hatti/bolum_10_kaynak_edinme/adim_40_ses_cikarma/` (extraction) and
`.../adim_50_asr_sesi_hazirlama/` (`demucs_cleaner.py`, `demucs_batch_worker.py`, `arka_plan_sesi_olcumu.py`).
Setting: `[ses_temizligi] kip` = `original` | `clean` | `preserve_background` | `auto_background`.

## 1. Audio extraction and the inverted-phase fix

- **Problem:** some sources carry the left and right channels in opposite polarity. A mono downmix for speech
  recognition then cancels the speech.
- **Solution:**
  - ASR path (16 kHz mono): ffmpeg first extracts **stereo** to a temp WAV, the phase check runs, then the file is
    downmixed to mono. The temp file is removed in `finally`.
  - Demucs path (44.1 kHz stereo): extract, then the same phase check.
  - Phase check: read at most the first 60 s in 65,536-frame chunks; compute L/R correlation and mid/side RMS.
    Repair only if `corr ≤ −0.95` **and** `side − mid ≥ 12 dB` **and** `side ≥ −45 dB`. Repair is
    `pan=stereo|c0=FL|c1=-1*FR` written to a temp file and swapped in with `os.replace`; the result is re-analysed
    and logged.
- **Measurement:** no record (no before/after numbers were kept).
- **Still open:** if the analysis itself fails, the repair is skipped without an error.

## 2. How Demucs is used

- Model `htdemucs` (Demucs 4.0.1). On CUDA the project's own batch worker runs; on CPU (or any other model) the
  stock command `python -m demucs.separate --two-stems=vocals --jobs 1 --shifts 0` is used.
- Data flow: `demucs_source.wav` (44.1 kHz stereo PCM16) → worker → `vocals.wav`, `no_vocals.wav`,
  `demucs_batch_report.json`. `clean_source.wav` is a hard link to `vocals.wav` (copy if linking fails).
  `asr_ready.wav` (16 kHz mono) is produced for engines that need it. With background preservation, `no_vocals.wav`
  is put through the same trim/speed timeline as the video and mixed under the dub
  (see [tts_timing_and_mix.md](tts_timing_and_mix.md)).
- **Fail-closed:** a Demucs failure stops the job before transcription; it never silently continues with raw audio.
- **Success is verified, not assumed:** exit code 0 is not enough. The parent re-reads the worker report and checks
  input path, model, overlap 0.25, shifts 0, requested batch 4, actual batch ∈ {1, 4} consistent with the
  `oom_fallback` flag, both stem files present, `total_seconds > 0` and `peak_torch_cuda_memory_mb > 0`.

## 3. Evolution: how Demucs got from "slow" to "2× faster with less RAM"

| Step | Change | Measured effect |
|---|---|---|
| 1 | `--segment 12` tried | fails: htdemucs is a transformer trained on 7.8 s segments and rejects longer ones |
| 2 | `--segment 7` forced | worked, no OOM; became the baseline |
| 3 | forced segment removed (worker reads `model.segment` = 7.8 s) | 88-min input: wall time 654.8 → 620.2 s |
| 4 | `CUDA_LAUNCH_BLOCKING=1` removed | progress time 604 → 489 s (−19 %), VRAM unchanged (≈ 983 MB) |
| 5 | `cudnn.benchmark=True` trial | no gain; not adopted |
| 6 | own batch worker, batch 4 | 74-min audio: 498.7 → ≈ 397–401 s through the real app (−20 %), torch peak ≈ 1.69 GB |
| 7 | two-stem accumulation + early tensor release | worker 11 m 48 s → 5 m 52 s (2.01×); RAM peak 9.52 → 7.15 GB |

### 3.1 Batch worker with OOM fallback (step 6)

- **Problem:** stock Demucs sends one 7.8 s segment per GPU call, leaving the GPU underfed.
- **Solution:** `_split_batched()` reuses Demucs internals (chunking, centre trim, triangular overlap weight,
  valid-length padding). Groups of 4 padded chunks go through one `model(...)` call under `torch.inference_mode()`,
  `overlap=0.25`, `shifts=0`; output uses `prevent_clip(mode="rescale")` and PCM16.
- **OOM fallback:** only `torch.cuda.OutOfMemoryError` is caught. Then `gc.collect()`, `torch.cuda.empty_cache()`,
  `reset_peak_memory_stats()` and **one** retry with batch 1 in the same worker. Other errors are never relabelled
  as OOM. The report records requested batch, actual batch and `oom_fallback`.
- Bagged models are accepted only if they contain a single model with unit weight.
- **Equivalence:** two runs were byte-identical to each other. Against batch 1, 0.035 % (vocals) and 0.024 %
  (no_vocals) of samples changed by at most 1 int16 step (floating-point summation order). Accepted tolerance:
  at most 1 int16 step; byte identity with batch 1 is not promised.
- Batch 2 or 8 for Demucs: no record.

### 3.2 Two-stem RAM architecture (step 7, the largest win)

- **Problem:** the first batch worker accumulated all four full-length stems in CPU RAM (≈ 5.9 GiB for a 75-min
  file, computed from tensor shape), plus the normalisation reference, the input tensor, overlap weights and a newly
  built long `no_vocals` tensor. The "save" phase (5 m 36 s) was not disk time: it was stem summing, two rescale
  passes, PCM16 conversion and two WAV writes.
- **Root cause:** data lifetime. Long tensors lived until process exit and the stem reduction happened after
  accumulation instead of per chunk.
- **Solution:**
  - The model still predicts 4 sources, but each chunk is reduced on the GPU to `[vocals, drums+bass+other]`
    before accumulation; the CPU accumulator holds 2 stems (≈ 2.95 GiB).
  - The reference tensor is freed once mean/std are taken; the input is freed after inference; the CPU overlap weight
    is built once; after writing, `del sources, model`, `gc.collect()`, `torch.cuda.empty_cache()`.
  - Maths preserved: `no_vocals = no_vocals * std + 3 * mean`, because each of the three non-vocal stems used to
    receive the mean separately.
- **Measured (75-min file):**

| Metric | Old worker | Two-stem worker | Integrated in app |
|---|---|---|---|
| Worker total | 11 m 48.5 s | 5 m 52.1 s | 6 m 2.2 s |
| Inference | 6 m 1.4 s | 5 m 18.8 s | 5 m 22.9 s |
| Output prepare + write | 5 m 36.5 s | 24.9 s | 30.1 s |
| Torch CUDA peak | 1689 MiB | 1670 MiB | 1694 MiB |

  - Process-tree RAM peak: first two-stem attempt 9.52 GB (system at 93 %); with early release 7.15 GB (system at
    80 %, no new swap). The old worker had no process-tree RAM telemetry, so no number is claimed for it.
  - GPU average 87 %; device VRAM average 2628 MiB, peak 2749 / 4096 MiB.
  - All 395 million PCM16 samples compared: vocals identical; no_vocals 534 samples differed by 1 step.
- **Still open:** two concurrent long Demucs runs were never tested; policy is one Demucs worker at a time.

### 3.3 Where time goes (profile before step 7)

Model load 0.7 s, audio load 10.5 s, inference 8 m 8.5 s, writing two stems 5 m 25 s; process shutdown after the
report ≈ 58 s; `asr_ready` conversion ≈ 25 s. GPU averaged 49 % over the whole call because it sat idle during WAV
writing. Lesson: worker time and application time are different numbers; measure both.

## 4. Worker process settings

- Launched with the same environment's `sys.executable` and an absolute script path.
- Environment: `PYTHONHASHSEED=0`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`,
  `TORCH_HOME=<model cache>`.
- Windows priority `BELOW_NORMAL` so the desktop stays usable during long writes (no effect on the maths).
- Progress is parsed from the worker's stdout; timeout 1800 s, then the process is killed and the job fails.
- A fixed 3 s pause between Demucs and transcription exists in the pipeline. No rationale or measurement was
  recorded for it.

## 5. Should Demucs run at all? Automatic background detection

- **Problem 1:** Demucs costs minutes on long inputs and is unnecessary for clean speech.
- **Problem 2:** Demucs can **hurt** recognition. On an 85 s Chinese clip the vocal stem lost real speech and the
  transcript degraded to event tags; the direct 16 kHz mono audio recovered the content (measured).
- **Rule from problem 2:** when words are missing after Demucs, first compare the same video's direct audio with
  the same recognition settings before changing the recognizer or the model.
- **Solution (`auto_background`, `arka_plan_sesi_olcumu.py`):**
  - 50 ms frames; dynamic range = 95th − 5th percentile level. Below 32 dB → background present; peak under −60 dB
    → silent audio, not background.
  - If background is present, Demucs runs only to produce `no_vocals` for the mix; recognition uses the **raw**
    16 kHz mono audio.
- **Calibration (measured):** on a set of earlier runs that had Demucs stems, 0 of the clear-background cases were
  missed and precision was ≈ 90 %. Measuring ≈ 917 minutes of audio took 24 s. On 12 English clips, raw and
  Demucs transcripts differed by 0–3.2 %. Splitting into 30 s windows separated the groups worse (85–89 %), and some
  long inputs had both clean and music windows, so one number can mislead on long videos.
- **Limits:** calibration clips were at most 4 min, English only, one recognizer, no ground-truth transcripts.

## 6. ASR input format

- For WhisperX, 44.1 kHz stereo `clean_source.wav` and 16 kHz mono `asr_ready.wav` gave identical text, segment and
  word counts and identical timestamps on 4 runs (measured), so WhisperX reads the clean source directly. Other
  engines still get 16 kHz mono.
- A 1.0 s leading pad is added for listed engines; it is disabled for subtitle-file
  sources.

## 7. Low-VRAM settings summary

| Setting | Value |
|---|---|
| Model | `htdemucs` |
| Batch | 4, one retry at 1 after a real CUDA OOM |
| Overlap / shifts | 0.25 / 0 |
| Segment | not passed (model default 7.8 s) |
| Never set | `CUDA_LAUNCH_BLOCKING`, `cudnn.benchmark=True` |
| Budget | ≈ 2.75 GB VRAM device peak, ≈ 7.2 GB process-tree RAM for 75 min of audio |
