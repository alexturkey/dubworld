# Engineering notes

How each part of the pipeline got to its current shape: the problems hit, their root causes, what was tried and
rejected, the fix, the measurements before and after, and what is still open. Written for contributors and for AI
coding agents (see `AGENTS.md`). Türkçe: [../muhendislik/README.md](../muhendislik/README.md).

Evidence labels used on every page: **measured** (the project ran it and kept the numbers; reference machine: 4 GB VRAM
Pascal-class GPU, compute capability 6.1, Windows, 16 GB RAM, unless stated), **documented** (recorded rule or finding
without a stored run), **no record** (unknown; do not assume).

| Page | Covers |
|---|---|
| [pipeline-flow.md](pipeline-flow.md) | **The whole job, from a link or file to the delivered video**: stages, the files between them, branches by setting, why the transcript is regrouped from word times |
| [low_vram.md](low_vram.md) | **Start here on a 4 GB card or CPU-only machine**: settings, symptoms, fixes |
| [gpu_memory_and_isolation.md](gpu_memory_and_isolation.md) | VRAM budget per model, OOM diagnosis, one process per model, environments, model cache, resource lock, measurement method |
| [source_audio_and_separation.md](source_audio_and_separation.md) | Audio extraction, inverted-phase fix, Demucs (batching, two-stem RAM work, OOM fallback), automatic background detection |
| [transcription.md](transcription.md) | faster-whisper, WhisperX, Parakeet, whisper.cpp, Moonshine, cloud engines, VAD, language detection, engine comparison |
| [crisperwhisper_turbo_ct2.md](crisperwhisper_turbo_ct2.md) | The optional verbatim engines (12 and 13): CT2/int8/WSL2, long-form fixes, multilingual work, speed |
| [word_alignment.md](word_alignment.md) | CTC forced alignment: why, window preparation, silence at word ends, space-less scripts, numbers |
| [timing-sources.md](timing-sources.md) | Where every word time comes from: per-engine source, YouTube json3 captions, where CTC is skipped, decision flow |
| [speakers_and_segments.md](speakers_and_segments.md) | Dub segmentation, diarization (3D-Speaker), gender, voice per speaker, full-text mode |
| [translation.md](translation.md) | Codex / Claude CLI bridges, natural-blocks contract, spoken forms, API providers, Opus-MT, error contract |
| [tts_timing_and_mix.md](tts_timing_and_mix.md) | Supertonic (fixed speed, CPU speed, recipe, silence clean-up, lifecycle), candidate alignment, atempo, loudness, background mix, VoxCPM2 |
| [video_subtitles_and_resume.md](video_subtitles_and_resume.md) | Encoder choice, single-pass encoding, size policy, subtitle contract, checkpoints/resume, user errors, smoke-test findings |
| [pinned-values.md](pinned-values.md) | Every pinned value (voice ids and speeds, thresholds, windows, batch sizes, timeouts, sample rates): where, why, what breaks if changed |

Decisions are recorded as ADRs in [../adr/](../adr/README.md).

## Ten things worth knowing before changing anything

1. Every heavy model runs in its own process; one GPU job at a time ([ADR 0001](../adr/0001-one-gpu-job-and-process-per-model.md)).
2. fp16 is not faster on Pascal; int8 is. Never enable `cudnn.benchmark` or `CUDA_LAUNCH_BLOCKING`.
3. Batch sizes were measured, not guessed (WhisperX: batch 1 ≈ 41 % faster than 2; Demucs: batch 4 ≈ 20 % faster than 1).
4. Demucs' biggest cost was RAM and data lifetime, not the GPU (two-stem worker: 2× faster, −2.4 GB RAM).
5. An "OOM" may be another component sharing the GPU or an input-length limit; diagnose before changing precision.
6. Word times of the recommended flow (`auto`: CrisperWhisper Turbo or `faster_whisper_ctc`) come from CTC forced alignment, with silence bounded to the measured speech span; engines that keep their own times are listed in [timing-sources.md](timing-sources.md) §4.
7. Translation runs in isolated CLI envelopes; a single missing flag once cost 23× in translation time.
8. Real synthesized duration decides timing; TTS in-model speed is fixed per voice.
9. Nothing falls back silently; retries stay inside the same engine and are recorded.
10. Every stage is checkpointed with an input fingerprint and a contract version; bump the version when behaviour changes.

## How changes were accepted

Isolated experiment → same input hash, one variable changed → outputs compared sample-by-sample or word-by-word with
times → worker time and application time measured separately → a second proof through the real entry point before
integration. Short tests are not enough: several failures (decoder loops, timing reversals, the 400 s input limit) only
appeared on long files.
