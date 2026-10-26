# DubWorld

English · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · [ไทย](README.th.md) · [বাংলা](README.bn.md) · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md) · [Azərbaycanca](README.az.md) · [Bahasa Melayu](README.ms.md)

> DubWorld dubs a video into another language on your own computer: speech to text with word timestamps, translation, synthetic voice kept in step with the original video (speech sped up at most 1.25×, the picture retimed for the rest), subtitles and a new video. Turkish by default; other languages per voice engine ([docs/diller.md](docs/diller.md)).

## Let your AI assistant install it

No programming needed. Open an AI assistant that can run commands on your computer (Claude Code, Codex,
Gemini CLI or similar) and paste this one sentence:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

The assistant measures your computer (graphics card, processor, memory, disk) and asks you once, in plain words, what
kind of setup you want: quick, recommended for your computer, or full. It explains each part (what it does, its disk
space, time and license) and asks whether you accept the terms of use of the parts you choose, starting with the
default voice. Then it installs, makes a sample dub and opens the program window. First steps, plain words and common
problems: **[docs/getting-started.md](docs/getting-started.md)**.

**License box:** code Apache-2.0. Default models: Supertonic 3 voice under OpenRAIL-M (use restrictions, accepted once); Opus-MT and the Turkish word-timing model under CC BY 4.0 (attribution, NOTICE); FFmpeg build GPL-3.0 (separate program). Non-commercial only and off by default: CrisperWhisper 2.0, XTTS-v2, WhisperX word-timing models for fr / de / es / it. No model weights are in this repository ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Quick install

Windows 10/11 x64; no Python, CUDA or ffmpeg needed beforehand. Double-click **`kur.cmd`** (or run
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); it picks the GPU or CPU profile by itself
(`-Cpu` forces CPU). Then double-click `arayuz.cmd` to open the app.
Everything goes inside the repository folder (`.venv`, `runtime_assets/`); every download is pinned and
sha256-verified. Free disk to start: 22 GB with the GPU profile, 14 GB CPU only; measured use after install ≈ 14.6 GB (GPU, hard-linked files counted once; a file explorer shows ≈ 22 GB). Check with `.venv\Scripts\dubla.exe kontrol`.

Requirements, step order, the map of Python environments, optional engines, offline use, update, uninstall and
common errors: **[docs/installation.md](docs/installation.md)**. Linux and macOS are not tested yet. Example: [product tour voiced in English, Turkish and Arabic on an Apple M4 Mac, CPU only](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Usage

Desktop app: double-click `arayuz.cmd` (local web app: `web.cmd`, 127.0.0.1 only). The app's screens are in English and Turkish: pick one at the top right (on a computer in another language it opens in English). From the command line:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Results go to `cikti/<video>_<time>/`: `dubbed_tr.mp4` (tagged `AI-dubbed`), the source subtitles `transcript_<lang>.srt` and the job's JSON files; the last line `dubbed_video:` prints the path. Every setting: [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## How it works

1. **Audio:** FFmpeg extracts the sound; optional Demucs (MIT) separates speech from background.
2. **Speech to text:** faster-whisper large-v3-turbo (MIT) plus wav2vec2 CTC word timing (English MIT, Turkish CC BY 4.0); optional CrisperWhisper 2.0 (non-commercial) and other engines.
3. **Speakers:** 3D-Speaker CAM++ (Apache-2.0) and a gender classifier (Apache-2.0) choose a synthetic voice per speaker.
4. **Translation:** Codex CLI or Claude Code CLI when installed and logged in, otherwise local Opus-MT English to Turkish (CC BY 4.0); API backends optional.
5. **Voice and timing:** Supertonic 3 (OpenRAIL-M) by default, VoxCPM2 (Apache-2.0) or XTTS-v2 (non-commercial) optional; each line is sped up at most 1.25× towards the original segment time and the video is retimed for the rest, so the dub can run longer than the source.
6. **Video:** FFmpeg writes the new audio, SRT / VTT / ASS subtitles and the `AI-dubbed` tag.

## Measurements

Reference machine: 4 GB Pascal GPU, Windows 10; method and all rows in [docs/olcumler.md](docs/olcumler.md).

| What | CPU profile | GPU profile |
|---|---|---|
| First install, default steps, end to end | ≈ 38 min | ≈ 44 min (packages 13.7 min) |
| Disk after install | ≈ 13.2 GB (folder sum) | ≈ 14.6 GB (hard links counted once) |
| 9 s sample dub, offline translation | 528 s | 376 s |
| 30 s English clip, Demucs, Claude Code translation | – | 744 s |

## Limits

- Without CrisperWhisper (optional engine 13), faster-whisper may skip speech or invent text in Chinese and Japanese (seen: the first ≈ 10 s of a Chinese clip skipped; shouting turned into a long "ああ…" line).
- CI tests the CPU only; the GPU path was run by hand on one 4 GB Pascal card. Newer cards (RTX 50), Linux and macOS were not tried; the installed GPU libraries carry kernels for Pascal to RTX 50 and Maxwell uses the CPU profile ([GPU runtime matrix](docs/installation.md#1-system-requirements)).
- The offline translator does English to Turkish only; other pairs need the Codex / Claude Code CLI or an API backend.
- Word timing for source languages other than English and Turkish: Japanese and Chinese with `scripts/kur.ps1 -Adim hizalama-diller`, others after one run with `DUBLAJ_CEVRIMICI=1`.
- Not tried end to end: XTTS-v2 real install, RVC, the Telegram bot against the real service. CrisperWhisper 2.0 Turbo (engine 13) is tested on real audio on a GTX 1050 Ti 4 GB (tr, en, ja; ≈ 1.4 GB VRAM).

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
| **DubWorld** (this repo) | end-to-end local video dubbing pipeline, every stage usable alone | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | verbatim speech-to-text with word timestamps (CrisperWhisper 2.0 Turbo + CTC alignment) | optional engine 13: `scripts/kur.ps1 -Adim crisper` installs its model through that repo at a pinned commit (weights **non-commercial**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | VoxCPM2 voice design and reading, 8 languages, ready-made voices | optional TTS engine `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` installs it at a pinned commit; this repo calls it through a thin adapter |

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
  The word-timing models for fr / de / es / it source audio (CC BY-NC 4.0) are non-commercial too and ask for consent on first use.

## Help and support

Questions, ideas and results: [Discussions](https://github.com/alexturkey/dubworld/discussions). Install problems: [install issue](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); bugs: [bug report](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(add your OS, GPU, the command and its last lines). Security issues: SECURITY.md, not public issues.

## License and credits

Code: Apache-2.0 (LICENSE). Third-party components and their licenses: THIRD_PARTY.md. Responsible use: ETHICS.md.
Privacy (what stays local, what a cloud backend receives): PRIVACY.md. Security reports: SECURITY.md. Changes: CHANGELOG.md.
