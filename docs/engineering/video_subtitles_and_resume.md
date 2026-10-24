# Video encoding, subtitles, checkpoints and error handling

Türkçe: [../muhendislik/video_altyazi_ve_devam.md](../muhendislik/video_altyazi_ve_devam.md).
Decision records: [ADR 0011](../adr/0011-video-encoder-selection.md), [ADR 0012](../adr/0012-stage-checkpoints-and-resume.md).

## 1. Encoder choice

- `bolum_60_video_ve_encode/kodlayici.py` decides once per process with a 0.1 s trial encode: `h264_nvenc` if it works,
  otherwise `libx264`. Override with `DUBLAJ_VIDEO_KODLAYICI = auto | nvenc | x264`. In CPU mode
  (`CUDA_VISIBLE_DEVICES=""`) x264 is used directly.
- **Why a trial encode:** the pinned FFmpeg build requires a newer NVENC API than some drivers provide, and NVENC does
  not exist on CPU-only machines. A hard-coded NVENC encoder made the pipeline fail on those machines (found by the
  end-to-end CPU smoke test).
- **NVENC vs x264 is content-dependent (measured):**
  - Dub pipeline, NVENC `p2` at CQ 23 vs 26: SSIM 0.997 / 0.995 / 0.996 on three videos while files shrank ≈ 28–30 %;
    `p1` was faster but produced larger files.
  - Drawn, flat-colour video against a lossless reference: x264 medium CRF 20 → SSIM 0.9868, 62 MB, 138 s;
    NVENC `p7` CQ 19 → 0.9849, 138 MB, 88 s; lowering NVENC CQ grew the file without closing the quality gap
    (a Pascal-generation NVENC limit). x264 won there.
  - A GPU-rendered scene (5 s): x264 CRF 18 VMAF 98.63 / SSIM 0.9918 vs NVENC CQ 19 VMAF 98.40 / SSIM 0.9923 —
    equivalent, NVENC 6× faster overall.
  - Lesson: re-measure per content class and on newer GPUs (Turing and later NVENC supports B-frames).
    Recipe: `ffmpeg -i x.mp4 -i lossless.mp4 -lavfi "[0:v]format=yuv444p[a];[a][1:v]ssim" -f null -`.
    Note that the x264 `-threads` value changes output bytes, so it is not a free speed knob in byte-identity tests.
- Do not run NVENC while CUDA inference runs: NVENC was ≈ 3.6× slower under concurrent CUDA load.

## 2. Encoding speed: remove duplicate work, not safety

### 2.1 Validation was the bottleneck (measured)

On real replays the slow part was not encoding but `ffprobe -count_frames` validation (204 of 297 s on a long video).
Fix: batches get a fast stream/duration/FPS check; only the final file gets a full frame count. Two heavy jobs:
258 → 167 s and 418 → 281 s with identical output hashes. Removing validation entirely was rejected.

### 2.2 Single pass and bounded parallelism (measured)

- **Problem:** batches were encoded, concatenated, then the **whole video was re-encoded** to burn subtitles and enforce
  the size limit (13 of 27 minutes on a 54-minute 1080p60 reference). The second encode also hid a defect: the video
  stream could end a few frames before the new audio timeline.
- **Fix:** subtitles are burned in the first and only batch encode using a global offset
  (`setpts=PTS+offset/TB` → `subtitles` → `setpts=PTS-STARTPTS`); short batches are completed with
  `tpad=stop_mode=clone` + exact `trim=duration`; up to 3 parallel workers for subtitled multi-batch jobs, longest batch
  first, concatenation always in index order; a batch that fails under parallelism is retried sequentially afterwards
  (handles NVENC session limits); final mux copies the video stream; the measured AAC and the profiled PCM come out of
  one filter graph.
- **Result:** 35 s video 15.0 → 12.4 s; 15-minute class 114 → 67 s; 54-minute reference 1602 → 668 s (2.4×). Timeline
  difference 0 on every job; audio PCM hash identical.
- **Forbidden regressions:** a second full encode, unbounded parallelism, completion-order concatenation, loosened
  duration tolerance, nominal (unmeasured) audio size, per-video exceptions.
- **Open:** a 4–5 minute target for the 54-minute reference was not reached without lowering quality, FPS, resolution
  or subtitles.

## 3. Output size policy

- `cq` (default, CQ 26) or `max_mb`. In `max_mb` mode the audio (AAC 96 kbps) is **actually encoded and measured**
  first; container reserve = max(1 MB, 1 %); the remaining budget becomes a constant video bitrate; one corrective
  re-encode lowering only the video bitrate if the file is still too large, then a hard error.
- Every output is labelled as AI-dubbed in its metadata (see the repository's ETHICS document).

## 4. Subtitles

### 4.1 One timing contract for every engine

- **Problem:** after the pipeline switched to verified candidate word timelines, one engine's subtitle step still
  required the old final-alignment file and failed even though valid timing existed. An old test had fabricated that
  file and masked the drift.
- **Fix:** the producer writes `subtitle_timing_contract.json` (schema version, engine, language, timing source and
  method, word and segment counts, relative paths, evidence paths). Consumers validate fail-closed: no paths outside the
  run folder, counts and engine must match, times finite, ordered, non-negative, `end > start`. The visual renderer is
  shared (`altyazili_dublaj/burnin.py`) with thin per-engine adapters. If subtitles are not ready before the final mux
  the job fails; it never continues without subtitles. Byte-identical ASS output for the existing engines before/after.

### 4.2 Where subtitle timing comes from

Earlier, Turkish subtitle times came from TTS-engine signals (word boundary events, internal attention, RMS). Now they
come from verified candidate timelines mapped to the video timeline; forced alignment of the final dub track
(`audio_new_timeline.wav` + final segment texts) is the fallback. Missing alignment fails the job instead of falling
back.

### 4.3 Multi-line scrolling style

Single settings owner `rollup_profile.json` on a 1080-unit-high canvas: width ratio 0.44, 2 rows (1–8), font 62,
scroll 0.25 s, a pause ≥ 1.0 s opens a new line, tail 0.65 s, minimum font 16. Words are never split; if the longest
word does not fit, the font shrinks for the whole render, and below the minimum the job errors. The checkpoint key
includes the profile, the renderer's SHA-256 and the font file's SHA-256.

### 4.4 Source subtitle preview

Each run can write an HTML preview with segment and word SRTs built from the pipeline's processed segments (not raw
ASR), for inspection only.

## 5. Checkpoints and resume

- **Stage graph (segment sync):** source → audio extraction → separation (optional) → ASR preparation → transcription →
  alignment & final segments → speaker routing → translation → voice/gender routing → TTS & segment audio → subtitle
  preparation → video timeline & mux → background mix → burn-in → final validation. Full-text mode has its own shorter
  branch. Canonical lists live in `bolum_00_omurga/core/pipeline_checkpoint.py`.
- **Manifest** `<run>/pipeline_state.json`, written atomically. Per stage: id, order, contract version, status
  (`pending/running/completed/skipped/failed`), input SHA-256 fingerprint, attempts, last error, a JSON rebuild payload
  (never pickle), and artefacts with size, mtime and a sampled content digest.
- **Invalidation:** a changed input hash or contract version invalidates that stage and everything after it; a missing,
  empty or changed artefact means "not completed"; a stage left `running` re-runs after a crash.
- **Resume** never modifies the source run: a new sibling folder is built in a hidden temp location and moved into place
  atomically. On Windows, antivirus/indexer `PermissionError`s get 5 short retries.
- **Proof matrix:** a TTS failure does not re-run ASR or translation; an alignment failure re-runs alignment only.
- **Contract bumps on record:** translation stages were versioned when their prompts changed; a new TTS recipe
  regenerates TTS and everything after it; the CTC bounding policy invalidates transcription.
- Replay rule: segment files may already carry new-timeline times; for honest replays rebuild the original boundaries
  from the stored original start/end values.

## 6. Errors the user sees

- `runtime/hata_aciklama.py`: one message format (title, stage, root class + masked message ≤ 300 characters, and an
  explanation from a rule table). Keys and tokens are masked; absolute paths reduced to `<yol>/file`.
- Rules: no silent fallback (NVENC → x264 counts as an equivalent path, not a fallback); `raise … from`; one failed TTS
  segment or a translation count mismatch stops the job.
- The trigger incident: a rate-limited translator fell back to the source text and an untranslated video was delivered
  as "completed".

## 7. Lessons from the end-to-end CPU smoke test of this repository

| Finding | Root cause | Fix |
|---|---|---|
| `No module named pkg_resources` | a model hub library still needs it; the locked setuptools version removed it | pin `setuptools==80.9.0` |
| `No module named datasets` | the diarization pipeline imports it | pin `datasets==3.1.0` |
| `_ARRAY_API not found` in fastcluster | wheel built against NumPy 1.x, lock has NumPy 2 | `fastcluster==1.3.0` |
| installer could not resolve the lock | two package indexes; uv locks onto the first | `--index-strategy unsafe-best-match` (hashes still mandatory) |
| `-filter_complex_script` not recognised | FFmpeg 7+ removed the option | use `-/filter_complex` |
| NVENC used in CPU mode / old driver | encoder was hard-coded | trial-encode selection (§1) |
| Turkish text garbled in the PowerShell installer | Windows PowerShell 5.1 reads BOM-less UTF-8 as ANSI | save scripts as UTF-8 with BOM |
| translation backend names in the settings schema unknown to the bridge | two separate name lists | one list + aliases + a test |
