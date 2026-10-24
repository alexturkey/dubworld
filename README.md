# Türkçe video dublaj hattı

English · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md)

> __TEK_CUMLE__ (what it does, in one line)

## Let your AI assistant install it

No programming needed. Open an AI assistant that can run commands on your computer (Claude Code, Codex,
Gemini CLI or similar) and paste this one sentence:

```text
Install the video dubbing program from __REPO_URL__ on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

The assistant checks your computer, picks the graphics card (GPU) or processor-only (CPU) setup by itself and asks
you one question: whether you accept the voice's terms of use. Then the program window opens. First steps, plain
words and common problems: **[docs/getting-started.md](docs/getting-started.md)**.

**License box:** code Apache-2.0. __LISANS_KUTUSU__ (model/data licenses that differ from the code; "none" if all Apache-compatible)

## Quick install

Windows 10/11 x64; no Python, CUDA or ffmpeg needed beforehand. Double-click **`kur.cmd`** (or run
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); it picks the GPU or CPU profile by itself
(`-Cpu` forces CPU). Then double-click `arayuz.cmd` to open the app.
Everything goes inside the repository folder (`.venv`, `runtime_assets/`); every download is pinned and
sha256-verified. Disk: ≈ 22 GB with the GPU profile, ≈ 13 GB CPU only. Check with `.venv\Scripts\dubla.exe kontrol`.

Requirements, step order, the map of Python environments, optional engines, offline use, update, uninstall and
common errors: **[docs/installation.md](docs/installation.md)**. Linux and macOS are not tested yet.

## Usage

__KULLANIM__ (one example command + what the output files are)

## How it works

__NASIL__ (pipeline in 4-6 bullets; name every external model with its license)

## Measurements

__OLCUM_TABLOSU__ (measured on the reference machine, method in docs/olcumler.md; never copy numbers from elsewhere)

## Limits

__SINIRLAR__ (what was not measured, what is experimental, what hardware was not tried)

## Building blocks

Every stage works on its own, from the command line or from Python, with documented file formats in between
(stage map and JSON Schemas: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` gives the same stages as functions. Install only what a stage needs, e.g.
`pip install -e ".[stt,hizalama,cpu]"` for subtitles. Five small tools built from these blocks: [examples/](examples/).

## Family / Related projects

| Repository | What it is | How this repo uses it |
|---|---|---|
| **turkce-video-dublaj-hatti** (this repo) | end-to-end local video dubbing pipeline, every stage usable alone | - |
| [crisperwhisper-turkce-kelime-zamani](__STT_REPO_URL__) | verbatim speech-to-text with word timestamps (CrisperWhisper 2.0 Turbo + CTC alignment) | optional engine 13: `scripts/kur.ps1 -Adim crisper` installs its model through that repo at a pinned commit (weights **non-commercial**) |
| [voxcpm2-turkce-ses-tasarimi](__TTS_REPO_URL__) | VoxCPM2 voice design and reading, 8 languages, ready-made voices | optional TTS engine `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` installs it at a pinned commit; this repo calls it through a thin adapter |

Each sibling keeps its own license, install and issues; pinned commits make the combination reproducible.

## Responsible use

> **Legal disclaimer.** You are solely responsible for the content you process and publish with this software and
> for complying with the laws of your jurisdiction and the terms of the sites and services you use. The software is
> provided "as is", without warranty (Apache-2.0). Full text: [ETHICS.md](ETHICS.md).

- **Rights and consent.** Process only material you own or have permission to translate and re-voice, and get the
  consent of identifiable people in it.
- **Voices.** No impersonation. A reference voice may only be your own or one whose owner gave explicit consent.
- **Label it.** Outputs carry an `AI-dubbed` metadata tag; keep it and also disclose AI dubbing visibly to your
  audience (EU AI Act Art. 50; Supertonic license).
- **Downloading.** The optional `youtube` (yt-dlp) and `galeri` (gallery-dl) extras are for content you own or may download; site terms and
  your local law apply.
- **Non-commercial engines.** CrisperWhisper 2.0 and XTTS-v2 are non-commercial only (off by default). Check the
  **Commercial?** column of [THIRD_PARTY.md](THIRD_PARTY.md) before any paid or client work.

## License and credits

Code: Apache-2.0 (LICENSE). Third-party components and their licenses: THIRD_PARTY.md. Responsible use: ETHICS.md.
Privacy (what stays local, what a cloud backend receives): PRIVACY.md. Security reports: SECURITY.md. Changes: CHANGELOG.md.
