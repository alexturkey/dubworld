# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Friendlier progress screen (desktop and web): six familiar stops (video, sound, writing down, translation, new
  voice, putting together), a moving striped bar, a ticking stopwatch, a rough "about N min left" once enough of the
  job is done, and a "What's happening" panel with short plain sentences in the interface language; the technical log
  stays behind a button. A finished job shows a small celebration. Animations stop when the system asks for reduced
  motion.
- Interface language: the desktop window and the web page are in English and Turkish, picked at the top right
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

- Target language names are shown in the interface language with their own name next to them ("German
  (Deutsch)", "Dub into German"); the job log, deep error messages and the command line stay in Turkish.
- CI: `actions/checkout` 7 and `actions/setup-python` 7.
- Optional English STT extra: `sherpa-onnx` 1.13.8.
- Dependabot ignores versions above an upstream cap (`coqui-tts-trainer >= 0.4.0`, `antlr4-python3-runtime >= 4.10`).
- Docs: CrisperWhisper 2.0 Turbo (engine 13) is listed as tested on real audio; CrisperWhisper 2 Medium stays untested.
  The sister repository URLs are built into `kur.ps1`; `DUBLAJ_TTS_REPO_URL` / `DUBLAJ_STT_REPO_URL` are only for forks.
- README (all 8 languages): first macOS example (product tour voiced in English, Turkish and Arabic on an Apple M4, CPU only).
- VoxCPM2: with the default single voice, a non-Turkish target language now reads with that language's ready narrator
  (`hazir/anlatici_<lang>`) instead of the Turkish default voice; a voice you set is never changed.
- Recommended NVIDIA 4–5 GB setup includes VoxCPM2. Sister repository pinned at `2d74db1` (example prompts; engine
  scratch files, about 3 MB of log per dubbed line, are deleted after each successful run).

### Fixed

- Tests that need numpy are skipped when numpy is not installed (plain CPU CI).
- On Linux and macOS a translation bridge timeout now stops the whole process group (no orphan child process).

### Security

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
