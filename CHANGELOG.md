# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Optional Turkish TTS engine EMA Lightning (`ses.motor = ema_lightning`, `kur.ps1 -Adim tts-ema`; Apache-2.0 code
  and weights, one synthetic voice): GPU path and a CPU path through ONNX files exported locally from the pinned
  weights; `ses.ema_cihaz = auto | cuda | cpu` with CPU fallback when the GPU is missing or busy; segment and
  `full_text` modes; shown by `dubla kontrol` (ADR 0019).
- README (all 8 languages): "Help and support" section with the Discussions link.
- Engineering docs: "Upstream-capped packages" in `docs/engineering/pinned-values.md` with a safe way to try a newer
  version without breaking the install.

### Changed

- CI: `actions/checkout` 7 and `actions/setup-python` 7.
- Optional English STT extra: `sherpa-onnx` 1.13.8.
- Dependabot ignores versions above an upstream cap (`coqui-tts-trainer >= 0.4.0`, `antlr4-python3-runtime >= 4.10`).
- Docs: CrisperWhisper 2.0 Turbo (engine 13) is listed as tested on real audio; CrisperWhisper 2 Medium stays untested.
  The sister repository URLs are built into `kur.ps1`; `DUBLAJ_TTS_REPO_URL` / `DUBLAJ_STT_REPO_URL` are only for forks.
- README (all 8 languages): first macOS example (product tour voiced in English, Turkish and Arabic on an Apple M4, CPU only).

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
