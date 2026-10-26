# Speakers, gender and dub segments

How word timings become dub segments, how speakers are found and how a voice is chosen per speaker. Türkçe:
[../muhendislik/konusmaci_ve_segmentler.md](../muhendislik/konusmaci_ve_segmentler.md).
Decision record: [ADR 0006](../adr/0006-two-stage-dub-segmentation.md).
Where segmentation sits in the whole job and why words are regrouped: [pipeline-flow.md](pipeline-flow.md#8-why-the-transcript-is-cut-into-word-times-and-grouped-again).

## 1. Final dub segments (`bolum_30_hizalama_ve_segment/nihai_dublaj_segmentleri.py`)

### Evolution

1. Split at `. ? !` (with abbreviation exceptions) or at every speaker change.
2. A "long segment" strategy (≥ 151 words, ≥ 25 s, …) with comma/pause/forced cuts, motivated by an API translator
   hitting its output-token cap with many candidates per segment. Same-day lesson: do not raise the token cap; size
   groups and candidates instead.
3. A separate gate for unpunctuated transcripts (0.6 s gap, forced speaker splits): removed.
4. Today: one canonical segmenter, mandatory for every transcription source in segment-sync mode, no fallback and no
   "keep the engine's segments" path.

### Current rule

- **Stage 1 (time):** `gap = next.start − prev.end`; gap ≤ 1.0 s keeps words together, > 1.0 s starts a new main
  segment (tested: 1.0 s together, 1.001 s split). Main segments are never merged; words never move between them.
- **Stage 2 (size):** ≤ 150 words is accepted. ≥ 151 words is split only internally: pieces at `.` then `?` then `!`
  then `,` (falling back to a weaker mark only when needed), accumulated greedily up to 150 words; last resort a hard
  cut at 150 words. Example: 285 words → 130 / 95 / 60.
- Each segment's start and end come from its own first and last word.
- Checked invariants: output word count = input; every segment ≤ 150; no loss, duplication or reordering.
- Speaker is metadata here; speaker splitting happens afterwards **inside** a main segment.
- Full-text mode is exempt (one logical text, one window).

### Why

| Alternative | Why rejected |
|---|---|
| Engine segments as dub targets | a measured 27.4 s segment contained 10.2 s of gaps |
| 0.6 s gap threshold | removed with the unpunctuated gate; 1.0 s matches the alignment natural-gap rule. **No A/B record** for 0.6 vs 1.0 s |
| Split at every speaker change | now handled inside the main segment with a 0.40 s short-group merge |
| Fixed-size chunks | destroy meaning units; last resort only |

## 2. Speaker diarization

### Evolution

1. WhisperX + pyannote 3.3.2 with word-level speaker labels (archived). Selection at the time (documented):

| Option | VRAM | Verdict |
|---|---|---|
| pyannote 3.3.2 | 1.59 GB peak (measured) | chosen then |
| pyannote 4.x community model | ≈ 9.5 GB peak (upstream issue report) | impossible on 4 GB |
| NVIDIA NeMo | 4–8 GB, heavy install | rejected |
| speaker-embedding-only models | not classifiers | wrong tool |

   Models ran in sequence (ASR → alignment → diarization → gender) with memory released between them; never more than
   ≈ 2 GB at once.
2. A per-segment gender router without diarization (light, isolated). Known limit: a segment containing two people
   gets one gender.
3. **Current: 3D-Speaker** (Silero VAD + CAM++ embeddings + clustering; the upstream FSMN VAD was replaced for licence
   reasons, [ADR 0013](../adr/0013-silero-vad.md)). The reason for preferring it over pyannote was
   **not recorded**. pyannote is not imported on this path; overlap handling is off.
4. `dubber.py` calls `konusmaci_seslerini_ata` without a speaker timeline, so 3D-Speaker always runs when
   per-speaker voices are on (`_supertonic_speaker_timeline_source` returns only `local_3d_speaker` or `disabled`).

### Current 3D-Speaker settings

- Input: 16 kHz mono. VAD: Silero VAD v6 from `faster-whisper` (threshold 0.5, min speech 250 ms, min silence 100 ms,
  pad 30 ms; [ADR 0013](../adr/0013-silero-vad.md), replaced FSMN `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch`); embeddings CAM++
  `iic/speech_campplus_sv_zh_en_16k-common_advanced` (v1.0.0), 80-bin FBank, 192-dim.
- Clustering: spectral first (`mer_cos=0.8`, 1–15 speakers, `pval=0.012`). **Single-speaker rescue:** if spectral
  returns one speaker, agglomerative clustering (`fix_cos_thr=0.2`) runs on the same embeddings (no repeated VAD or
  embedding). A raw cluster that owns no word's largest overlap never becomes a dub speaker.
- Word mapping: each word gets the speaker with the largest time overlap; groups shorter than 0.40 s merge into a
  neighbour (start → next, end → previous, middle → longer neighbour). Words are never deleted; a speaker group never
  moves to another main segment.
- Security: vendored code loads checkpoints with `torch.load(weights_only=True)` and YAML with `safe_load`.
- Evidence written per run: command, runtime, model diagnostic, failure, progress files.

### Measurements

| Step | Before | After import/model-loading clean-up |
|---|---|---|
| Total speaker + gender routing | 76.0 s | 21.8 s (identical decisions) |
| Subprocess + vendor import | ≈ 30.4 s | 6.3 s |
| VAD / embedding / clustering | 2.0 / 1.4 / 2.1 s | 1.0 / 1.0 / 2.6 s |

- A 95 s two-person interview: spectral found 1 speaker; the rescue found 2 real dub speakers (confidences 0.986 and
  0.974); worker ≈ 37 s vs ≈ 107 s for the vendor CLI.
- **Cache check experiment (rejected):** ≈ 3 s of the cost was the ModelScope cache resolver import; hashing 7 model
  files took ≈ 90 ms. A size/mtime receipt was faster still but missed a same-size content change with restored mtime.
  Decision: pass the cache root directly (saves ≈ 2.9 s, keeps full-hash trust). Production now loads models directly
  from the local cache with no network; only if loading fails are files validated (size + SHA-256) and a missing or
  corrupt model re-fetched once. If files are intact the real load error is reported, not a download.
- Overlapped-speech separation (several separation models tried, ≈ 0.8 GB peak, 1–2 s per 10 s) was rejected by
  listening because of leakage.

## 3. Gender and voice per speaker

- One gender worker subprocess per job: all eligible segments in one batch over stdin JSON, result as one JSON, then
  the process exits (RAM and VRAM fully released). Minimum segment length 0.30 s; speaker mode uses up to 30 s of
  audio per speaker.
- History: the first classifier was an ECAPA model fine-tuned on a speaker-recognition corpus. **This repository uses
  `alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech`** (Apache-2.0, trained on LibriSpeech) at a pinned
  revision, loaded offline.
- Known limits: the classifiers have no "unknown" class; **no confidence threshold** is implemented; spectral
  clustering under-counts speakers on short interviews (fixed by the rescue); a cloud diarizer once merged an adult
  and a child into one speaker. Accuracy on Turkish speech: **no record** yet.
- Voice assignment in this repository: an explicit map `{speaker: voice}` is applied first; remaining speakers, in
  speaker-label order, take the next free voice of their detected gender's pool (female F1→F5, male M1→M5, wrapping
  around); unknown gender uses the female pool ([pinned-values.md](pinned-values.md#supertonic-voices)). One TTS runtime switches
  voices per segment.

## 4. Full-text mode (alternative to segment sync)

- One speech window from the first to the last reliable speech; inner pauses and speaker changes do not split it.
- One voice, no diarization; one translation call; text goes to TTS as one input.
- Source-side alignment is skipped where engine segments suffice; Parakeet still aligns (sub-word tokens are not word
  times).
- Duration fit: `audio_to_video` (atempo the audio to the window) or `video_to_audio` (retime the video only).
- Subtitle timing for full text: windows computed from real chunk sample counts in the final WAV and aligned with CTC;
  TTS-internal timing is never used.

## 5. Open items

- Gender confidence threshold; gender accuracy measurement on Turkish speech.
- More than one voice per gender (F1/F2, M1/M2 rotation) beyond the speaking-time order.
- A fresh end-to-end measurement of the current two-subprocess speaker + gender path.
- No A/B record for the 1.0 s gap threshold.
