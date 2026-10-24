# Pinned values: what they are and why

Türkçe: [../muhendislik/sabit_degerler.md](../muhendislik/sabit_degerler.md).

A **pinned value** is a number or choice fixed in code or in `src/dublaj_hatti/varsayilan.toml`: a voice id, a threshold,
a window length, a batch size, a timeout, a sample rate. Many of them look arbitrary; most are not. Each row below says
where the value lives, what it does, why it has this value and what breaks if it is changed. Engine- and stage-level
reasoning is in the other pages of this folder and in [../adr/](../adr/README.md); this page works one level lower, value
by value.

**"No record"** means the reason was searched for in the project's measurement notes and was not found. It does not mean
the value is free to change: treat it as "unknown risk" and measure before and after.

## Before changing a pinned value

1. Read its row and the linked page or ADR.
2. Re-run the measurement named in "If changed" on full-length inputs (several failures only showed on long files).
3. Change the value, this page (EN + TR) and `tests/test_sabit_degerler.py` in the same change.
4. If the value affects a stage's output, bump that stage's checkpoint contract version
   ([ADR 0012](../adr/0012-stage-checkpoints-and-resume.md)); never add a silent fallback
   ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)).

Paths are relative to `src/dublaj_hatti/`; line numbers were taken when this page was written and may drift.

## Supertonic voices

| Value | Where | What it does | Why | If changed | ADR |
|---|---|---|---|---|---|
| Per-voice speed F1 1.30, F2 1.15, F3 1.30, F4 1.00, F5 1.15, M1 1.15, M2 1.00, M3 1.00, M4 1.15, M5 1.25 | `bolum_50_seslendirme/supertonic_tts/speed_policy.py:11` | Supertonic's in-model synthesis speed, one fixed value per voice | Supertonic `speed` is a sampling parameter, not time stretching. A global 1.20 and a dynamic 0.85–1.45 speed dropped final words and swapped or repeated syllables, and a working value could fail at a nearby one. Each value was accepted only when that voice read the same 5 Turkish texts and all 5 transcripts matched (5/5). Why each voice got its particular number: no record | Missing or garbled words that forced alignment does not detect (it places the expected text on the audio). A new value must pass the same 5/5 test; TTS checkpoints regenerate | [0010](../adr/0010-real-tts-duration-is-canonical.md), [0015](../adr/0015-tts-engine-set-and-default.md) |
| Speed is not part of the seed | `speed_policy.py` (`fixed_voice_profile_v1`) | The seed is a hash of language + voice + steps + text | Audio approved in testing then reproduces exactly | Approved audio no longer reproduces | 0015 |
| Default voice F1; fallback voice F1 | `speed_policy.py:9`, `varsayilan.toml:95`, `supertonic_tts/konusmaci_secimi/router.py:487` | Voice when nothing else is chosen; voice for a segment with no usable speaker voice | Fallback to a female voice: the gender classifier has no "unknown" class, so a last resort is needed. Why F1 rather than another voice: no record | Output voice of default runs changes | [0017](../adr/0017-defaults-and-licence-gate.md) |
| Pools F1–F5 (female), M1–M5 (male); assignment order | `supertonic_tts/konusmaci_secimi/voice_assignment.py:6-7` | Explicit map first; then, in speaker-label order, the next free voice of the detected gender's pool (wrapping); unknown gender uses the female pool | Unknown → female pool: same reason as the fallback above. Why this rotation order: no record | Re-runs give speakers different voices; use `ses.konusmaci_sesleri` for a fixed mapping instead | 0017 |
| Segment-mode pair F1 / M1 | `varsayilan.toml:116,118` | Female / male voice when gender is decided per segment | No record | Default voices of segment mode change | 0017 |

## Supertonic synthesis

| Value | Where | What it does | Why | If changed | ADR |
|---|---|---|---|---|---|
| 10 steps, transition at step 7, CFG 5.0, fixed time grid (contract `supertonic_k15_cfg5_7plus3_silence_v2`) | `bolum_50_seslendirme/supertonic_tts/synthesis_profile.py:4-11` | Sampling recipe: 7 steps at predicted length, latent stretched to target length, 3 more steps | The factory 8-step sampling had audible defects; a clean 22-step recipe was expensive. 16 recipes were scored by ASR word error rate and listening; this one cost ≈ 52–54 % less than the clean reference with 0 % WER on the test paragraph (measured on one voice and the test texts) | The contract id is part of runtime, candidate-cache and checkpoint keys, so all TTS regenerates; quality must be re-scored the same way | [0012](../adr/0012-stage-checkpoints-and-resume.md), 0015 |
| Silence cleanup: candidate 20 dB below peak, frame silent 45 dB below peak, silence < −95 dB, speech > −50 dB, 8 repeat frames, neighbour radius 2, 3 propagation rounds | `supertonic_tts/silence_cleanup.py:13-19` | Finds "neither speech nor silence" latent frames before the vocoder and replaces them with one canonical silence latent | Frames decoded one at a time fell into three groups: silence (< −95 dB), speech (> −50 dB) and unstable (−63 … −80 dB), the audible hiss. Frames within 20 dB of the peak are never candidates, so speech is never touched. 3 rounds follow the reference order and are fixed by a test. Measured: cleaned frames −64…−84 → −85…−108 dB. Why radius 2 and 45 dB exactly: no record | Hiss returns at speech boundaries, or word tails are masked | 0015 |
| Loudness: target −18 LUFS, true-peak ceiling −1.3 dBTP, one constant gain, no limiter | `supertonic_tts/final_audio_profile.py:16-17` | `gain_dB = min(−18 − LUFS, −1.3 − true_peak)` on the whole file | Final dubs were quiet (−23 to −26 LUFS). Gain + limiter was not enough by ear and compressor/limiter variants crackled; a constant gain keeps the voice's character. −1.3 leaves margin under the −1.1 dBTP acceptance limit. Why −18 exactly: no record | Crackle (if a limiter/compressor returns) or clipping above −1.1 dBTP | 0015 |
| CPU parallelism: 4 lanes × 2 intra-op threads, inter-op 1; direct path 3 intra-op threads | `supertonic_tts/parallel.py:26-30` | ONNX Runtime threads per synthesis lane | Measured fastest with identical output (19.5 s vs 23.1 s for 2 lanes × 3); inter-op 2 gave no gain; intra-op 4/6/8 were faster but their outputs were not identical | Audio stops being byte-identical, or CPU contention slows TTS | 0015 |

## Duration matching

| Value | Where | What it does | Why | If changed | ADR |
|---|---|---|---|---|---|
| atempo band 0.90–1.25 | `bolum_50_seslendirme/supertonic_tts/atempo_sure_uyumu/policy.py:9-10` | Allowed pure `atempo` factor after synthesis | Fits duration without touching the in-model speed of the voice (a pure tempo filter, no EQ or pitch filter). Why these two bounds: no record | Requires re-running real duration and pitch tests; the voice speed table must not be changed instead | [0010](../adr/0010-real-tts-duration-is-canonical.md) |
| Real-TTS acceptance band: implied video speed 0.90–1.15 | `bolum_50_seslendirme/tts_orkestratoru/service.py:43-44` | Above 1.15 the audio is too short, below 0.90 too long; outside → repair | Canonical acceptance band; an older 0.70 threshold must not return. A warning outside the band is not evidence of missing words. Why these bounds: no record | More or fewer repair rounds; visibly sped-up or slowed video | 0010 |
| `ses.hiz = 1.2` | `varsayilan.toml:103`, `bolum_00_omurga/core/dubber.py:671` | Translation target duration = source duration × 1.2 | Kept from the original pipeline, where engines without in-model speed were sped up afterwards with pitch-preserving `atempo`. It is never passed to Supertonic, whose speed comes only from the per-voice table | Translation length targets change; does not change Supertonic speed | 0010 |
| Candidate alignment: start tolerance 5 ms, end tolerance 25 ms (terminal word only), cut buffers 0.05 / 0.08 s, pre/post gap 0.35 s | `bolum_50_seslendirme/candidate_alignment/aligner.py:19-25` | How far an aligned word may cross its window, and the silence fence between concatenated candidates | Measured: first words overshot by 0.1–0.3 ms (5 ms covers rounding without hiding a real shift), last words by ≈ 20 ms (25 ms, then clamped); any other overshoot invalidates the candidate. The 50/80 ms cut buffers came back with the fix that kept segment pauses. Why 0.35 s gap: no record | A looser tolerance hides window shifts; removing the fence let neighbouring segments' audio bleed together (seen and reverted) | 0010 |
| Long lane 30 s | `supertonic_tts/candidate_lanes.py:12` | Lanes longer than 30 s (or short multi-segment lanes) get one alignment window per physical chunk | Total-lane switch, not a per-window maximum; built from real chunk text and sample counts | Alignment windows no longer match physical chunks | 0010 |

## Sample rates and other TTS engines

| Value | Where | What it does | Why | If changed | ADR |
|---|---|---|---|---|---|
| Supertonic native 44 100 Hz | `bolum_00_omurga/core/dubber.py:643` | The pipeline follows the engine's own rate | The engine outputs 44.1 kHz; a fixed pipeline rate resampled it for nothing | Needless resampling | 0015 |
| `ileri.ornekleme_hizi = 24000` | `varsayilan.toml:164`, `dubber.py:670` | Output rate for engines that do not set their own | Legacy shared default from earlier engines; Supertonic ignores it | Output rate of other engines changes | – |
| 16 000 Hz for gender model and speaker pipeline | `supertonic_tts/cinsiyet_secimi/gender_worker.py:14`, `gender_classifier.py:20` | Input rate of the classifier | Input rate of the gender model and the speaker pipeline | Classifier receives the wrong rate | – |
| 16 000 Hz, minimum window 400 samples for CTC speech bounds | `bolum_30_hizalama_ve_segment/ctc_kelime_hizalama/ctc_konusma_siniri.py:9-10` | Analysis rate and smallest analysed window | No record | – | [0005](../adr/0005-ctc-forced-alignment-only-time-source.md) |
| VoxCPM2 16 steps, CFG 2.0, 48 000 Hz (informational; the sibling TTS repository owns them) | `bolum_50_seslendirme/voxcpm2_tts/ayarlar.py:17-19` | Quality settings of the VoxCPM2 runner | 16 steps / CFG 2.0 is the model card's clean default; CFG 2.5 brought some samples too close to 0 dBFS. 48 kHz: no record | Quality changes in the sibling repository, not here | 0015 |
| XTTS inter-piece silence 0.05 s | `bolum_50_seslendirme/xtts_tts/kosucu.py:17` | Silence between joined XTTS pieces | No record | – | 0015 |
| Text-to-speech part gap 0.25 s | `api.py:76` | Silence between parts in the text-only TTS path | No record | – | – |

## Speakers and gender

| Value | Where | What it does | Why | If changed | ADR |
|---|---|---|---|---|---|
| Gender model `alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech` at a pinned revision | `supertonic_tts/cinsiyet_secimi/gender_classifier.py:18-19` | Classifies speaker gender, loaded offline | Apache-2.0 weights trained on LibriSpeech; the previously used classifier's training-data permission was unclear ([speakers_and_segments.md](speakers_and_segments.md) §3) | An unpinned revision can change results or licence silently | 0017 |
| Min segment 0.30 s, up to 30 s per speaker, short-group merge 0.40 s | `konusmaci_secimi/router.py:24-27`, `cinsiyet_secimi/segment_gender_router.py:14`, `gender_worker.py:15` | Shorter segments take a neighbour's voice; one decision per speaker from ≤ 30 s of audio; groups < 0.40 s merge into a neighbour (words are never deleted) | Behaviour documented; the exact numbers: no record (no A/B test) | Gender decisions on short segments change | – |
| Diarization timeout 3600 s | `konusmaci_secimi/diarization_adapter.py:14` | Upper bound for the diarization worker | No record | – | [0001](../adr/0001-one-gpu-job-and-process-per-model.md) |

## Translation

These values live in `bolum_40_ceviri/`; see [translation.md](translation.md) for the contract.

| Value | Where | What it does | Why | If changed | ADR |
|---|---|---|---|---|---|
| Recommended flow `natural_blocks_1` (config default); code fallback `single_pass_2` | `varsayilan.toml:99`, `dubber.py:694`; `supertonic_tts/flow_modes.py:2` | One natural candidate per segment id with ownership check and code gates | Speech boundaries are not sentence boundaries: segment-by-segment translation sounds like subtitles, free translation then re-splitting moves meaning into the neighbouring id. The config default follows the flow that carried most measurements; `single_pass_2` is the earlier reference flow kept as code fallback | Needs an LLM backend; the local backend ignores it | [0007](../adr/0007-natural-blocks-translation-contract.md), 0017 |
| No Arabic digits in natural-blocks candidates | `bolum_40_ceviri/*/backends/*/output_schema_natural_blocks_v2.json` | The model writes the spoken form of numbers | A mechanical rule cannot tell "8K video" from "8K tokens"; rewriting later would split subtitle text from TTS text | TTS reads digits wrongly or subtitle and speech diverge | 0007 |
| Backend order `auto` = Codex → Claude Code → local Opus-MT | `varsayilan.toml:73` | Picks the first installed backend; never switches mid-run | Codex has the most measurements and a CLI-enforced schema; Claude uses the same contract; Opus-MT is the offline floor. Mixing backends mid-run mixes tone and caused hidden-fallback bugs | Mixed style; silent fallback | [0008](../adr/0008-translation-backend-order.md), 0009 |
| Default models `gpt-5.6-luna` / `claude-sonnet-5-5`, effort `medium` | `varsayilan.toml:77-87` | LLM model and effort | No record (no A/B) | – | 0008 |
| Full text: effort `high` above 6000 words | `llm_kopru/scripts/bridge_worker.py:71`, `claude_code_cli/scripts/bridge_worker.py:72` | Raises effort for very long single-call translations | A 10,497-word source returned `partial` at medium and passed at high; 3,000–5,250 words passed at medium. Conservative policy, not an official model limit | Long full-text jobs return partial output; retrying the same request did not help (measured) | 0007 |
| Coverage gate: source ≥ 8 words and candidate words × 4 < source words → reject | `*/scripts/natural_blocks_chain_contract.py:14-15` | Catches major meaning loss | The model's own "complete" claim is never trusted alone; less than a quarter of an 8+-word source is treated as major loss and the group is retried | Lost meaning passes silently, or short valid candidates are rejected | 0007, 0009 |
| Source-like threshold 0.90 | `bridge_motor_orkestratoru/quality.py:10` | Rejects a candidate ≥ 90 % similar to the source | An untranslated or barely changed output must not enter timing data as a success; normal technical words are not targeted | Untranslated text reaches TTS, or valid translations are rejected | 0009 |
| Protected identity ≤ 3 words | `quality.py:11` | Short source-identical spans allowed (names) | No record | – | – |
| Retry counts: contract 2, chain review 1, job-id mismatch 1, full-text partial 2 | `*/scripts/bridge_worker.py:63-70` | How often a bad answer is re-asked | Contract documented (only the bad ids are re-asked). Why these counts: no record. Re-sending an identical partial request burned tokens without fixing it (measured) | Cost rises without quality gain, or the job stops earlier | 0009 |
| Candidates 7, accepted cap 10 | `*/scripts/bridge_worker.py:67-73` | Candidate count of repair modes; upper cap | `repair_*` modes ask 7 per segment, `single_pass_10` asks 10. Why these caps: no record | – | – |
| Grouping: 10 segments, 2 context segments, 7 parallel jobs, backoff 2/4/6/8/16/32 s; repair 8 / 4 / 5 fast candidates / 12 s | `bridge_motor_orkestratoru/engine.py:35-43` | Request size and concurrency | No record | – | – |
| Timing-repair thresholds 0.70 / 1.35, min target 2.5 s, 1 round | `engine.py:30-33` | When a translation is sent back for length repair | No record. Note: these trigger repair only; acceptance stays 0.90–1.15 (above) | – | 0010 |
| Turkish speech rate 0.43 s/word (also the default for languages without a table) | `engine.py:34`, `*/scripts/hedef_dil.py:258` | Converts target seconds to a word budget | No record for the value; the default keeps the earlier behaviour for languages not in the table | Translation length targets change | – |
| Timeouts: timing repair 45 s; worker 900 s (+60 s) | `*/scripts/bridge_worker.py:73,118` | Upper bound per call | 45 s: a deliberately short timeout for repair calls. 900 s: no record | – | – |
| Gemini request spacing 2.0 s / 0.75 s; 503 retry delays 0.5–8 s | `llm_kopru/scripts/bridge_worker.py:119-121` | Rate pacing; retries for capacity errors | Spacing: no record. Retries only for 503 "high demand" (≈ 15–20 s total, same model and payload, then the group is deferred); 429/401/403/400 excluded | Silent model switching or very long waits | 0009 |
| Output-language check: ≥ 4 words, ≥ 8 letters, ≥ 3 traces, script share 0.5 | `*/scripts/hedef_dil.py:360-363` | Detects a candidate in the wrong language | Code comments only (avoid false alarms on short segments; names from the source excluded); no measurement record | – | – |
| Local Opus-MT batch 16, beams 4, `max_new_tokens` 256 | `bolum_40_ceviri/yerel_ceviri/engine.py:22-24` | Local English→Turkish translation | No record (quality, VRAM and speed not measured) | – | 0008 |

## Transcription

| Value | Where | What it does | Why | If changed | ADR |
|---|---|---|---|---|---|
| ASR leading pad 1.0 s | `bolum_00_omurga/core/dubber.py:136` | Silence prepended before recognition for listed engines; the offset is removed once | Engines clipped the first words of tightly cut videos. Why it is off for CrisperWhisper Medium: no record | The subtracted offset must equal the pad, otherwise every timestamp shifts | [0005](../adr/0005-ctc-forced-alignment-only-time-source.md) |
| Distil gate 0.90 | `bolum_20_transkripsiyon/faster_whisper_motoru/worker.py:40` | Distil (English-only) stays only if the language is `en` with P(en) ≥ 0.90, else WhisperX turbo fp32 | Distil models are English-only. Measured: English P = 0.995 stayed; a non-English clip with P(en) = 0.767 switched and was detected correctly. Why 0.90: no record | Non-English audio transcribed by an English-only model | – |
| WhisperX batch: CUDA 1, CPU 4 | `whisperx_motoru/worker.py:66-67` | Transcription batch size | CUDA batch 1 was ≈ 41 % faster than 2 on two long fp32 files, batch 4 slowest, text identical. CPU 4: no record | Changing requires a 2 → 1 → 2 control on at least two long files | [0001](../adr/0001-one-gpu-job-and-process-per-model.md) |
| WhisperX VAD chunk 30, onset 0.500, offset 0.363 | `whisperx_motoru/worker.py:71-73` | pyannote VAD parameters (VAD runs on the CPU) | Values: no record. VAD on the CPU: on the GPU it caused a reproducible OOM on a 4 GB card | – | 0001 |
| Parakeet technical max 400 s, operational max 399 s | `parakeet_cpu_align_motoru/worker.py:24-25` | Longest input per encoder call | The encoder takes at most 5000 steps × 80 ms = 400 s: 400.000 s works, 400.080 s gives unstable text, 400.160 s a shape error; 399 s keeps a margin | Above 400 s ONNX asks for a ≈ 10 GB MatMul or fails | – |
| Parakeet boundary silence 600 ms, natural gap 1.0 s, frame 0.08 s | `worker.py:26-28` | Cut point search; gap that ends an alignment window; CTC window pad | 0.08 s is one encoder frame. 1.0 s: CTC handled ≈ 0.4 s gaps but pulled a 6.4 s silence into a word. 600 ms: no record | The 80 ms pad must not be copied to other engines | 0005 |
| Parakeet beam: 4 active paths, blank penalty 2.0 | `worker.py:30-31` | Decoder settings | On a 396 s file WER went 11.1 % (greedy) → 8.4 %; 8 paths gave the same WER and were 49 % slower; higher penalties invented repetitions (12.3 %) | Higher WER or slower decoding | – |
| CrisperWhisper Turbo window 29.5 s, overlap 1.0 s | `crisperwhisper_turbo_ct2_motoru/config/runtime_profile.json:63` | Long-form window | 29.5 s is the model-input upper bound, not a blind cut. Overlap 1.0 s: no record | See [crisperwhisper_turbo_ct2.md](crisperwhisper_turbo_ct2.md) §5 | [0004](../adr/0004-crisperwhisper-turbo-ct2-int8.md) |
| Shared alignment limits: long word 1.5 s, repair 0.3 s, raw silence 0.5 s | `bolum_00_omurga/runtime/crisperwhisper_turbo_ct2_runtime.py:25-27` | A word > 1.5 s is accepted only inside its measured speech span; at most 0.3 s timeline repair; internal silence limit | A fixed 1.5 s gate wrongly failed a real 1.662 s spelled-out word, hence the span check. 0.5 s: real words had ≤ 0.36 s internal silence | Silence swallowed into words, or valid long words rejected | 0005 |
| Coverage recovery candidates (0.8, seeds 7/8/6) | `crisperwhisper_turbo_ct2_motoru/src/coverage_recovery.py:17` | Retry settings when a window is not covered | No record (the 10-voice acceptance test used them) | – | 0004 |
| YouTube subtitle alignment timeout max(120, 90 + 8 × audio minutes) s; repair limit 0.3 s | `youtube_json3_kaynagi/engine.py:24-27` | Upper bound for the alignment-only call | Successful alignment cost ≈ 2.8–3.1 s per audio minute, so the limit scales instead of a fixed value. 0.3 s: no record | Long files time out | 0005 |

## Word alignment

| Value | Where | What it does | Why | If changed | ADR |
|---|---|---|---|---|---|
| Speech pad 0.15 s | `bolum_30_hizalama_ve_segment/ctc_kelime_hizalama/ctc_konusma_siniri.py:8` | Word times are clamped to the measured speech span ± 150 ms | On 100 min of audio: 0 words > 1.5 s, median 180 ms; results were stable for pads of 100–200 ms. Without clamping 1,457 words were < 40 ms | Changing the bounding policy invalidates transcription checkpoints of every engine | 0005, 0012 |
| Raw-silence check: frame 0.02 s, context 2.0 s, level ratio 0.35, minimum contrast 6 dB | `ctc_konusma_siniri.py:11-14` | Veto-only energy check against silence swallowed into a word | Calibrated on 7 voices: real words had ≤ 0.36 s internal silence; 31 of 36 synthetic swallowed pauses were caught. Contrast < 6 dB = not measurable | Swallowed pauses pass, or real words are vetoed | 0005 |
| Minimum repaired word duration 0.01 s | `ctc_kelime_hizalama/zaman_onarimi.py:5` | Floor after a timeline repair | No record | – | 0005 |

## Dub segmentation

| Value | Where | What it does | Why | If changed | ADR |
|---|---|---|---|---|---|
| Gap threshold 1.0 s | `bolum_30_hizalama_ve_segment/nihai_dublaj_segmentleri.py:6` | A gap > 1.0 s starts a new segment | Engine segments are not real pauses (one 27.4 s segment held 17.2 s of speech and 10.2 s of gaps). 1.0 s matches the alignment natural-gap rule. No A/B record for 0.6 vs 1.0 s | Different segments, translation and TTS for every job | [0006](../adr/0006-two-stage-dub-segmentation.md) |
| Maximum 150 words | `nihai_dublaj_segmentleri.py:7` | Longer segments are split internally | Oversized segments hit an API translator's output-token cap | Translation calls truncate | 0006 |
| Punctuation priority `.` `?` `!` `,` | `nihai_dublaj_segmentleri.py:8` | Order of split points | Keeps the largest meaningful pieces; weaker marks only when needed | Less natural splits | 0006 |

## Source audio and separation

| Value | Where | What it does | Why | If changed | ADR |
|---|---|---|---|---|---|
| Demucs `htdemucs`, two stems | `bolum_00_omurga/core/dubber.py:133` | Separation model | Hybrid transformer model; no comparison record against other Demucs models | Separation quality and timing change | [0002](../adr/0002-demucs-batched-two-stem-worker.md) |
| CUDA batch 4, overlap 0.25, shifts 0, segment = model default | `bolum_10_kaynak_edinme/adim_50_asr_sesi_hazirlama/demucs_cleaner.py:14-15` | Batched separation | Batch 4: 74 min of audio 498.7 → ≈ 397–401 s (−20 %), torch peak ≈ 1.69 GB. Overlap 0.25 and shifts 0 keep the earlier flow's quality (more shifts are slower). htdemucs is trained on 7.8 s and rejects longer segments | Batch 4 vs 1 differs by ≤ 1 int16 step on 0.035 % of samples; other batch sizes are unmeasured; a longer segment fails | 0002 |
| One OOM retry at batch 1 | `demucs_batch_worker.py` | Recovers from a real CUDA OOM only | Other errors are never relabelled as OOM | A silent fallback on non-OOM errors | 0002, 0009 |
| Demucs environment: `PYTHONHASHSEED=0`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, OMP/MKL threads 1, below-normal priority | `demucs_cleaner.py:128-137` | Determinism and keeping the computer responsive | Below-normal priority keeps the computer usable during long WAV writes. Determinism variables for Demucs: no record | – | 0001 |
| Demucs → ASR hand-off delay 3 s | `dubber.py:152` | Pause between separation and recognition | No record; kept as a safety layer because it was never proven unnecessary | Possible native/OOM errors on the next GPU job (unmeasured) | 0001 |
| Background detection: frame 0.05 s, percentiles 5 / 95, dynamic range < 32 dB = background, peak < −60 dB = silent | `adim_50_asr_sesi_hazirlama/arka_plan_sesi_olcumu.py:10-14` | Decides whether to run separation | Calibrated on earlier runs with separated stems: 0 clear-background cases missed, precision ≈ 90 %; 30 s windows separated worse. Limits: clips ≤ 4 min, English only | Separation runs on clean speech (cost, speech loss) or skips noisy audio | [0003](../adr/0003-automatic-background-detection.md) |

## Video and output

| Value | Where | What it does | Why | If changed | ADR |
|---|---|---|---|---|---|
| CQ 26 | `varsayilan.toml:149`, `bolum_60_video_ve_encode/timeline_ve_final_encode/video_processor.py:68`, `dubber.py:336,703` | Constant-quality target of the final encode | Against CQ 23 on three videos: SSIM 0.997 / 0.995 / 0.996 while files shrank ≈ 28–30 %; the video stage also got faster (smaller files validate and mux faster). SSIM does not replace a visual check of text-heavy or fine-line video | Larger files and slower stage (lower CQ) or visible loss (higher CQ) | [0011](../adr/0011-video-encoder-selection.md) |
| NVENC preset `p2` | `video_processor.py:67` | Encoder speed/size trade-off | `p1` was faster but produced larger files | Larger files | 0011 |
| Batch size by segment count: ≤ 40 → one batch, then 40 / 35 / 30 | `video_processor.py:544-563` | Timeline items per encode batch | Code comment only ("larger batch, less concat overhead", replacing 30/25/20); no measurement record | – | 0011 |
| At most 3 parallel batches (subtitled multi-batch jobs); a short last batch is merged | `video_processor.py:1237` | Bounded parallel encoding | Bounded parallelism with the longest batch first cut a 54-minute reference from 1602 to 668 s with timeline difference 0; a batch failing in parallel is retried alone (encoder session limits). A 1–2 s last batch could not reach its expected duration and failed. Why 3: no record | Unbounded parallelism is a known regression | 0011 |
| x264 fallback: `medium` with CRF = CQ; second fallback `veryfast` CRF 23 | `video_processor.py:708,722` | Encoding without NVENC | The CPU fallback must exist; preset/CRF values: no record | – | 0011 |
| `max_mb`: AAC 96 kbps actually encoded and measured; 1 MB = 1 000 000 bytes | `video_processor.py:643`, `yapilandirma.py:88` | Size-limited output | The budget uses the real AAC byte size, not a nominal bitrate; decimal MB matches sharing-service limits. Why 96 kbps: no record | Going back to a nominal audio estimate overshoots the size limit | 0011 |
| AI-dubbed metadata label on | `varsayilan.toml:153` | Marks output as AI-dubbed | Disclosure, see [../../ETHICS.md](../../ETHICS.md) (EU AI Act Art. 50) | Turning it off goes against the ethics guidance | 0017 |

## Subtitles

| Value | Where | What it does | Why | If changed | ADR |
|---|---|---|---|---|---|
| Burned-in layout: font 72; 1920×1080 width 0.74 / box 104 / margin 70; 1080×1920 0.82 / 108 / 210; 1080×1080 0.78 / 104 / 110 | `bolum_50_seslendirme/altyazili_dublaj/burnin.py:16-31` | Fixed subtitle box per canvas | Copied unchanged from the renderer that was already in use; byte-identical ASS output was checked on real jobs. Individual numbers: no record | Affects every engine; re-run the real engine regressions | – |
| Roll-up profile: width 0.44, 2 rows, font 62, scroll 0.25 s, pause 1.0 s, tail 0.65 s, min font 16 | `altyazili_dublaj/rollup_profile.json` | Rolling subtitles on a 1080-unit canvas | Approved defaults from a reference subtitle experiment; no measurement explains the exact numbers | If the longest word does not fit at 16 the job errors; changes re-run the subtitle stage | 0012 |

## Smart frame, checkpoints, runtime limits

| Value | Where | What it does | Why | If changed | ADR |
|---|---|---|---|---|---|
| Smart frame: 24 samples, 540 px analysis width, 16 consensus samples, outside ratios 0.05 / 0.72 | `bolum_10_kaynak_edinme/akilli_kare_yakalama/service.py:24-26`, `detector.py:6-7` | Detects black/blurred side bands | No record | – | – |
| Checkpoint hashing: full hash up to 32 MiB (and all audio), else size + first/last 1 MiB | `bolum_00_omurga/core/pipeline_checkpoint.py:30-31` | Input fingerprints for resume | No record | Changing invalidates existing checkpoints | 0012 |
| Resource lock busy exit code 75 | `bolum_00_omurga/runtime/kaynak_kilidi.py:46` | Exit code when the GPU is busy | The lock itself is measured (two parallel jobs each ran ≈ 1.95× longer, throughput +2.6 %); the code number: no record | Callers that check 75 break | 0001 |
| Timeouts: gallery download 900 s, RVC 7200 s, cover generation 900 s (first run) | `adim_20_kaynak_alma/galeri_indirici.py:24`, `rvc_ses_donusturme/donusturucu.py:27`, `bolum_70_gorsel_uretim/kapak_gorseli/codex_kapak.py:28` | Upper bounds for external tools | Cover: 900 s only until a successful run exists, then average × 1.20. Others: no record | – | – |
| Error message ≤ 300 characters | `bolum_00_omurga/runtime/hata_aciklama.py:8` | One-line user error, secrets masked | User-facing error contract | Long or multi-line errors | – |
| YouTube download max 4 GiB, retry once after 5 s | `adim_20_kaynak_alma/youtube_downloader.py:25-26` | Download limits | No record | – | – |
| TTS workers 4, retries 3, retry wait 2.0 s | `varsayilan.toml:159-162` | Parallel TTS requests and retries | No record | – | – |

## Version pins

Package versions are locked with hashes in `requirements/*.txt` and model files with commit + SHA-256 in
`scripts/modeller.json`; the reasons for the risky ones (torch builds and Pascal kernels, Demucs 4.0.1, FFmpeg) are in
[gpu_memory_and_isolation.md](gpu_memory_and_isolation.md), [low_vram.md](low_vram.md) and
[../installation.md](../installation.md). Lock checks: `tests/test_kurulum_kilitleri.py`.

## Guard test

`tests/test_sabit_degerler.py` reads the critical values above from the source (no imports, no models) and fails with a
pointer to the matching section of this page when one changes.
