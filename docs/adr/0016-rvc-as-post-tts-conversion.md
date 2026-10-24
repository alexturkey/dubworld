# ADR 0016: RVC voice conversion is a post-TTS layer on the timed mix

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0016)

## Context
An RVC model can carry the dub into a specific voice. RVC does not read text: it converts an existing recording
into another voice character. Its dependencies (its own torch build, fairseq, faiss, HuBERT and RMVPE assets) conflict
with the main environment. In an earlier version of the pipeline the converted output also contained hiss and hum inside pauses.

## Decision
- RVC is not a TTS engine. Translation, TTS, segment placement and timing are completed first; RVC converts the final
  timed dub track (the mix returned by the TTS stage) once, after synthesis
  (`tts_orkestratoru/service.py`, `rvc_ses_donusturme/donusturucu.py`).
- It runs the official RVC WebUI command line (`infer/cli.py`) as a subprocess in the user's own RVC environment
  (`DUBLAJ_RVC_KOK`, `DUBLAJ_RVC_PYTHON`); nothing from RVC is imported or shipped.
- Speech / pause decisions are taken from the **clean input** to RVC, never from the RVC output: pauses detected in the
  source (−45 dB, at least 0.15 s) are silenced again in the output, with 40 ms ramps at the edges to avoid clicks.
  Length and sample rate are restored to the pipeline's values.
- Consent is mandatory (`ses.rvc_riza_onayi = true`); a failed conversion is an error, never a silent return to the
  unconverted audio ([ADR 0009](0009-fail-closed-no-silent-fallback.md)).

## Consequences
- Timing, subtitles and candidate selection are identical with or without RVC. RVC settings are part of the TTS
  checkpoint fingerprint (`dubber.py`, `tts_inputs["rvc"]`): changing them re-runs the TTS stage and keeps
  transcription and translation ([ADR 0012](0012-stage-checkpoints-and-resume.md)).
- One conversion per job instead of one per segment.
- The fixed conversion parameters (index ratio 0.75, RMS mix 0.25, protect 0.33) have **no recorded A/B** in this
  repository; an earlier version used different values tuned for a single model.

## Alternatives considered
- Converting each segment separately: more process starts and model loads, same result for the timeline (documented for an
  earlier version, where each per-voice stem is converted once).
- Converting the un-timed concatenated TTS output: the converted file would not match the track that enters the video.
- Gating pauses on the RVC output energy: hiss in the output can look like speech and defeats the gate.
- Installing RVC into the main environment: dependency conflicts.
