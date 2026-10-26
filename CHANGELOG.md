# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Voice library: a new **Voices** tab lets you add your own voice from a short recording (3 to 30 seconds), name it, give it a
  category, and say whose voice it is (your own, or with the owner's permission). Dubbing can then speak in that voice:
  pick it on the Dub card ("3. Voice") or press "Use in dubbing" on its card. The voice is cloned with VoxCPM2 from the
  recording alone, or more closely if you also type what the recording says. Search, filter by category, rename,
  play and delete (with one confirmation) are on the page; recordings stay on your computer. Setting:
  `ses.voxcpm2_ses = "kitaplik/<id>"`.
- Review panel: the notice and the find-and-replace row now stay in view while the lines scroll, a one-line job status
  stays visible on wider screens, and "Replace all" no longer makes the page jump on narrow screens.
- Review before voicing (optional): tick "Review the text before voicing" on the dubbing card (also the setting
  `genel.gozden_gecir`, `dubla <video> --ayar genel.gozden_gecir=true`). Dubbing pauses right after the translation
  ("Waiting for review", not an error) and a side panel opens next to the video (a sheet from the bottom on narrow
  screens, full screen on phones). Fix the original or the translation line by line (changes save by themselves),
  jump the video to a line by its time, find and replace a word everywhere (with Undo), translate a single line
  again, and see which lines may be too long for their time. "Continue dubbing" shows how many lines will be voiced and
  keeps your text; `dubla devam <job>` does the same from the command line.
- Video player: the picture area always shows the video of the running or finished job (also after a page reload and
  for jobs started from the command line); tall 9:16 and wide 16:9 clips both fit in the same fixed box with no page
  jump. A clear full-screen icon sits at the top right of the video (and an exit icon in full screen; Esc and double
  click work too). The controls bar lies over the bottom of the picture, fades in and out by itself while playing,
  and keeps 44 px touch targets. New: loading spinner, "Replay" at the end, remembered volume, keyboard shortcuts
  (Space or K, arrows, M, F).
- A finished job shows a "Done" card with Download and "Dub into another language" (starts from the saved
  translation, so transcription is not repeated).
- Interface rules for a clear, phone-like screen (big, obvious, always helping) in the `arayuz-tasarimi` skill: visible
  controls, visible close icons, readable numbers, example text in fields, guidance instead of errors, undo.
- Modern interface: the chosen video plays right away in a built-in player (timeline with sentence marks, volume,
  speed, subtitles, full screen, keyboard shortcuts); a finished dub plays in the same place with an Original /
  Dubbed switch that keeps the moment. Day and night colours (follows the computer, switch at the top right; calm,
  readable contrast checked by tests), familiar icons, large touch targets, a Settings drawer with search and a short
  help window. In a half-screen window the running job and the result move up so they stay in view.
- Friendlier progress screen: six familiar stops (video, sound, writing down, translation, new
  voice, putting together), a moving striped bar, a ticking stopwatch, a rough "about N min left" once enough of the
  job is done, and a "What's happening" panel with short plain sentences in the interface language; the technical log
  stays behind a button. A finished job shows a small celebration. Animations stop when the system asks for reduced
  motion.
- Interface language: the interface is in English and Turkish, picked at the top right
  (`genel.arayuz_dili = auto | tr | en`; `auto` follows the computer, otherwise English). Texts live in
  `src/dublaj_hatti/arayuz_dilleri/<code>.json`, so a new language is one new file; tests check every file on their
  own (`docs/arayuz_dili.md`).
- Optional Turkish TTS engine EMA Lightning (`ses.motor = ema_lightning`, `kur.ps1 -Adim tts-ema`; Apache-2.0 code
  and weights, one synthetic voice): GPU path and a CPU path through ONNX files exported locally from the pinned
  weights; `ses.ema_cihaz = auto | cuda | cpu` with CPU fallback when the GPU is missing or busy; segment and
  `full_text` modes; shown by `dubla kontrol` (ADR 0019).
- README in 30 languages (was 8): natively written translations with a shared language menu; Arabic, Persian,
  Hebrew and Urdu right-to-left; the seven languages no speech engine reads yet (fa, he, ur, th, bn, az, ms) say so
  plainly and explain that videos in them can still be dubbed into other languages.
- README (all languages): "Help and support" section with the Discussions link.
- Engineering docs: "Upstream-capped packages" in `docs/engineering/pinned-values.md` with a safe way to try a newer
  version without breaking the install.
- VoxCPM2 favorite voices by gender: `ses.voxcpm2_kadin_sesleri` / `ses.voxcpm2_erkek_sesleri` (comma-separated,
  handed out in speaker order) with the same speaker separation and gender estimate as Supertonic; empty lists use
  the target language's ready voices; `ses.konusmaci_sesleri` still wins; segment mode uses the first voice of each
  list. Checks: unknown `hazir/<id>` is an error, a ready voice of the other gender or a missing female voice is a
  warning (`docs/sesler.md`).
- `scripts/varsayilan_motor.py --motor voxcpm2 --ses <voice>`: makes a designed or chosen voice this computer's
  default (user settings layer only).
- AGENTS: on an NVIDIA GPU VoxCPM2 is the featured voice; design your own voice from the sister repository's 144
  example prompts and dub with it.

### Changed

- Web interface is calmer and more consistent: stopping a job, cancelling a queued job, archiving and accepting a
  licence all use the same in-page confirmation window (no more browser pop-ups); job buttons have icons with words;
  a small notice confirms what happened; error and progress areas keep their place so the page no longer jumps; small
  buttons are now large enough to tap; the pulsing animation is gone and all motion stops when the system asks for
  reduced motion; colours come from one set of day and night tokens.
- One interface: `dubla-gui` (and `arayuz.cmd`) now opens the web interface in its own app window (Microsoft Edge,
  else Chrome or Chromium, with a separate profile; else the default browser) and stops by itself after the window
  is closed. The old Tk desktop window is removed. Tabs are now **Dub**, **Settings** and **Jobs**.
- Target language names are shown in the interface language with their own name next to them ("German
  (Deutsch)", "Dub into German"); the job log, deep error messages and the command line stay in Turkish.
- CI: `actions/checkout` 7 and `actions/setup-python` 7.
- Optional English STT extra: `sherpa-onnx` 1.13.8.
- Dependabot ignores versions above an upstream cap (`coqui-tts-trainer >= 0.4.0`, `antlr4-python3-runtime >= 4.10`).
- Docs: CrisperWhisper 2.0 Turbo (engine 13) is listed as tested on real audio.
  The sister repository URLs are built into `kur.ps1`; `DUBLAJ_TTS_REPO_URL` / `DUBLAJ_STT_REPO_URL` are only for forks.
- README (all 8 languages): first macOS example (product tour voiced in English, Turkish and Arabic on an Apple M4, CPU only).
- VoxCPM2: with the default single voice, a non-Turkish target language now reads with that language's ready narrator
  (`hazir/anlatici_<lang>`) instead of the Turkish default voice; a voice you set is never changed.
- Recommended NVIDIA 4–5 GB setup includes VoxCPM2. Sister repository pinned at `2d74db1` (example prompts; engine
  scratch files, about 3 MB of log per dubbed line, are deleted after each successful run).
- The voice engine now chooses itself: `ses.motor` defaults to `auto`. It uses VoxCPM2 when VoxCPM2 is installed and an
  NVIDIA graphics card works, and Supertonic otherwise (always Supertonic in `full_text` mode). The choice is written
  to the job log. A value you set yourself (`supertonic`, `voxcpm2`, ...) keeps working and wins over `auto`.
- Each remaining speech-to-text and voice engine now states its commercial-use status, hardware, languages and
  strengths (English and Turkish) in one place, available to tools as `kayit.motor_bilgileri()`.
- The installer (`kur.cmd`) asks one last question at the end of an interactive default install on a machine with an
  NVIDIA card and WSL2: add CrisperWhisper Turbo? It prints the non-commercial licence summary and the size (about
  7 GB) first; answer E or h. Nothing is asked with `-Adim`, in CI or when input is redirected.
- A saved setting that names a removed engine no longer stops the program: it prints a warning in Turkish and
  English and falls back to `auto`.

### Deprecated

- XTTS v2 voice engine: it still works, and now prints a warning when you select it (non-commercial CPML licence;
  VoxCPM2 clones a voice without a reference transcript).

### Removed

- Five speech-to-text engines: CrisperWhisper 2 Medium, Moonshine Medium Streaming, whisper.cpp (CPU), Speechmatics
  and ElevenLabs Scribe v2. None was ever the default, none had been tested on real audio, and each overlapped
  faster-whisper, Parakeet or CrisperWhisper Turbo. Their code, install steps (`speechmatics` extra and lock files),
  documentation pages and API-key lines in `.env.example` are gone. `transkripsiyon.motor = auto` is unchanged
  (CrisperWhisper Turbo when installed, otherwise faster-whisper). The setting `crisper_dil_tespiti = per_window`
  belonged to the removed Medium engine and is read as `global_first_window`.

### Fixed

- `dubla ayir` (and `api.ayir`) no longer stops with "Demucs output missing" after a successful separation: the
  speech and background tracks are now taken from Demucs's own output folder.
- Tests that need numpy are skipped when numpy is not installed (plain CPU CI).
- On Linux and macOS a translation bridge timeout now stops the whole process group (no orphan child process).

### Security

- Word alignment models from Hugging Face are loaded from a fixed commit (37 models), never from whatever the model
  page holds today; a changed or hijacked model page can no longer slip in new files. The weights are the same ones
  earlier downloads got, so word times do not change.
- Open Dependabot alerts on `transformers` and `torch` are explained in `SECURITY.md` (low practical risk; the update
  waits for a stable `whisperx` that allows `huggingface-hub` 1.x).
- `onnx` 1.22.0.
- CrisperWhisper WSL runtime lock: `certifi` 2026.10.23, `filelock` 4.2.4, `pip` 26.2.2, `setuptools` 84.1.0.

## [0.1.0] - YYYY-MM-DD (release date is written on release day)

First public release of DubWorld (draft until release day).

### Changed

- Product name DubWorld (distribution `dubworld`); the `dubla*` commands and the import package `dublaj_hatti` keep
  their names.
- The Demucs `htdemucs` weight is pinned (URL + sha256) and fetched by `kur.ps1 -Adim demucs`; a missing weight stops
  the job before Demucs starts instead of downloading at run time.
- Optional pinned word-timing models for Japanese and Chinese sources (`kur.ps1 -Adim hizalama-diller`); with an
  automatic source language a missing CTC model now stops the job right after language detection.

### Added

- End-to-end local dubbing pipeline: source → transcript → word timing → translation → TTS → timing fit →
  subtitles → video; NVIDIA GPU and CPU paths with automatic detection.
- Package layout (`src/dublaj_hatti`), `pyproject.toml` (PEP 621) with optional dependency groups per engine and
  profile (`cpu`, `gpu`, `gui`, `web`, `stt-*`, `tts-*`, `dev`); entry points `dubla`, `dubla-web`, `dubla-gui`.
- Development tooling: ruff and mypy configuration, pre-commit hooks, CI (lint + CPU tests), issue and pull request
  templates, Dependabot, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `.editorconfig`.
- Every stage on its own: CLI subcommands `dubla indir | ses-cikar | ayir | yaziya-dok | hizala | cevir | seslendir |
  altyazi | birlestir`, the stable Python API `dublaj_hatti.api`, stage file formats with JSON Schemas
  (`transcript@1`, `translation@1`, `speech@1`, WhisperX-compatible), SRT / WebVTT / ASS writer with word and karaoke
  modes, per-stage extras (`stt`, `hizalama`, `ceviri`, `tts`, `konusmaci`, `video`, `onerilen`), `docs/mimari.md`.
- Link input in the desktop and web interfaces; each link type checks only its own optional tool (gallery links no
  longer require yt-dlp).
- `examples/`: five small tools built from the stages (subtitle extractor, podcast translator, text reader, batch
  transcription, karaoke subtitles), each with a GPU-free smoke test.
