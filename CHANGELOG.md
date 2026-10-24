# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
