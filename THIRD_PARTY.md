# Third-party components / Üçüncü taraf bileşenler

This project's own code is licensed under **Apache-2.0** (`LICENSE`). It builds on the components below; each keeps
its own license, and **your use of each component is governed by that component's license, not by this repository's license**.
The binding text is this English file. Türkçe özet: `README.tr.md` "Sorumlu kullanım" ve `ETHICS.md`.

**What is in this repository:** only this project's code, plus the vendored 3D-Speaker inference code (Apache-2.0, modified,
see below) and a few CUDA kernel files derived from CTranslate2 (MIT). **No model weights, no audio, no binaries.**
Models are downloaded by `scripts/kur.ps1` / `scripts/modelleri_indir.py` from their official source at a fixed
commit with a SHA-256 check (`scripts/modeller.json`); Python packages come from PyPI at the hash-locked versions in
`requirements/*.txt`.

Licenses below were read on 2026-10-24 from the primary source named in each row (model card / `LICENSE` file /
Hugging Face API tag / GitHub API / PyPI metadata). They can change upstream; **check the linked source before
relying on a row, especially for commercial use.** This file is information, not legal advice.

Legend for **Commercial?**: **Yes** = the license allows it · **No** = non-commercial only · **Conditional** = allowed
with use restrictions or obligations listed in the last column · **Provider terms** = a paid/online service; its
terms of service decide (not reviewed for this repository; read them before use).

## 1. Models and engines

| Component | Code license | Weights license | Output use | Commercial? | Source / pin | Your obligations |
|---|---|---|---|---|---|---|
| **Supertonic 3** TTS (Supertone) — default voice | MIT (`supertone-inc/supertonic`; the runner is this project's code) | **BigScience Open RAIL-M** | Bound by the license's Attachment A use restrictions (no unlawful use, no impersonation without consent, no deceptive content, **must disclose that content is machine-generated**, etc.) | Conditional | HF `Supertone/supertonic-3` @ `3cadd1ee6394adea1bd021217a0e650ede09a323` (license file downloaded next to the model) | Follow Attachment A; pass the same restrictions on if you redistribute the model or a derivative; keep the AI-generated label on outputs |
| **VoxCPM2** TTS (OpenBMB / ModelBest) — optional | Apache-2.0 (`OpenBMB/VoxCPM`) | Apache-2.0 (HF tag `license:apache-2.0`, `openbmb/VoxCPM2` @ `32279effe8…`) | Model card: impersonation, fraud and disinformation are forbidden; AI-generated content should be labeled | Yes | Installed through the sibling repo `voxcpm2-turkce-ses-tasarimi` (pinned commit + SHA-256) | Keep the label; voices only from text descriptions or with the speaker's consent |
| **EMA Lightning** TTS (Turkish, one synthetic voice) — optional, `kur.ps1 -Adim tts-ema` | Apache-2.0 (PyPI `ema-lightning` 1.1.0, https://github.com/canberk7/ema-lightning) | Apache-2.0, commercial use included (model card) | Model card: the voice is synthetic (designed in VoxCPM2 from a text description, trained on ~1,000 h of VoxCPM2-generated speech, Apache-2.0), not a real person; tell listeners the audio is AI-generated; no impersonation or scams | Yes | HF `canberkkkkkk/ema-lightning` @ `e7c96f2fc0ba843cd0f86e02786655bb56f50df8`, `ema.pt` / `decoder.pt` SHA-256 pinned (scripts/modeller.json); CPU ONNX files are exported locally from these weights (not downloaded) | Keep the AI-generated label on outputs; keep the Apache-2.0 notice if you redistribute the weights or the exported ONNX files |
| **faster-whisper** large-v3-turbo (CTranslate2 conversion) — default STT | MIT (`SYSTRAN/faster-whisper`) | MIT (HF tag; OpenAI Whisper weights MIT) | No restriction from the license | Yes | HF `dropbox-dash/faster-whisper-large-v3-turbo` @ `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf` | Keep the MIT notice if you redistribute |
| **WhisperX** (alignment / optional diarization glue) | BSD-2-Clause (`m-bain/whisperX`, PyPI 3.8.6) | uses the models below | No restriction from the license | Yes | PyPI `whisperx==3.8.6` | Keep the BSD notice if you redistribute |
| **wav2vec2 XLS-R 300m Turkish** (Mehmet Poyraz) — Turkish word timing | — | **CC BY 4.0** | No restriction | Yes | HF `mpoyraz/wav2vec2-xls-r-300m-cv7-turkish` @ `708639f50559d7970f462e13ec64d3f059ca89f6` | **Attribution** (see `NOTICE`) when you redistribute the model or publish results that build on it |
| torchaudio `WAV2VEC2_ASR_BASE_960H` (fairseq, Meta) — English word timing | BSD-2-Clause (torchaudio) | MIT (fairseq) | No restriction | Yes | https://pytorch.org/audio/stable/pipelines.html | Keep notices if you redistribute |
| **Silero VAD** v6.2.3 | MIT | MIT | No restriction | Yes | `snakers4/silero-vad` tag `v6.2.3` | Keep the MIT notice if you redistribute |
| **CrisperWhisper 2.0 Turbo** (Nyra Health) — optional, off by default | MIT (`nyrahealth/CrisperWhisper`; this project's CT2 runner and kernels: Apache-2.0 / MIT) | **nyra health Non-Commercial Research License** | **Non-commercial only**; outputs may not be used to train commercial models | **No** | HF `nyralabs/CrisperWhisper2.0_turbo` @ `de0369c8a6…`, converted on your machine by the installer of the sister STT repository; installer step refuses to run without `-TicariOlmayanKabul` | Non-commercial use only; converted weights are a derivative under the same license — do not redistribute them under an open license |
| **CrisperWhisper 2.0 Medium** (Nyra Health) — optional, manual | MIT | **nyra health Non-Commercial Research License** | Non-commercial only | **No** | HF `nyralabs/CrisperWhisper2.0_medium` (manual install, `docs/motorlar/`) | Same as above |
| **Moonshine Medium Streaming (English)** (Moonshine AI) — optional, manual | MIT | **MIT** (the upstream `LICENSE` lists the only non-MIT models: legacy non-streaming non-English Base/Tiny, under the non-commercial Moonshine Community License — **we do not use those**) | No restriction | Yes | https://github.com/moonshine-ai/moonshine (`LICENSE`, read 2026-10-24) | Do not swap in a model from the non-commercial list for commercial work |
| **whisper.cpp** + `ggml-base.en` — optional, manual CPU path | MIT (`ggml-org/whisper.cpp`) | MIT (HF `ggerganov/whisper.cpp`) | No restriction | Yes | official prebuilt binary + HF model (manual) | Keep notices if you redistribute |
| **Parakeet unified EN 0.6B** (NVIDIA), sherpa-onnx int8 export — optional CPU path (`kur.ps1 -Adim parakeet`, HF `csukuangfj2/sherpa-onnx-nemo-parakeet-unified-en-0.6b-int8-non-streaming` @8c3a10fb + sha256) | Apache-2.0 (`k2-fsa/sherpa-onnx`) | **NVIDIA Open Model License** (HF `nvidia/parakeet-unified-en-0.6b`, tag `license:other`) | NVIDIA claims no ownership of outputs | Conditional (license says "commercially usable") | https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/ | If you redistribute the model: include the agreement and the notice "Licensed by NVIDIA Corporation under the NVIDIA Open Model License"; do not bypass guardrails; follow NVIDIA Trustworthy AI terms |
| **Opus-MT tc-big en→tr** (Helsinki-NLP) — default local translation | MIT (Marian via `transformers`, Apache-2.0) | **CC BY 4.0** | No restriction | Yes | HF `Helsinki-NLP/opus-mt-tc-big-en-tr` @ `e539fc16a8a1a0ea5950eb339b595bfcce990e90` | **Attribution** (see `NOTICE`) |
| **3D-Speaker** CAM++ speaker embedding (Alibaba / ModelScope) + **Silero VAD** v6 — speaker separation | Apache-2.0 (vendored, modified; see §4); Silero VAD runs from `faster-whisper` (MIT) | Apache-2.0 (CAM++, ModelScope model page); MIT (Silero VAD model, bundled inside the `faster-whisper` wheel) | No restriction | Yes | ModelScope `iic/speech_campplus_sv_zh_en_16k-common_advanced` v1.0.0 (SHA-256 in `scripts/modeller.json`); Silero VAD v6 from PyPI `faster-whisper` | Keep the Apache notice; see the training-data note in §5. The upstream FSMN VAD was replaced because it needs `funasr`, which hard-depends on `kaldiio` (§7) |
| **wav2vec2 XLSR-53 gender recognition** (alefiury) — voice per speaker | — | Apache-2.0 (training data LibriSpeech, CC BY 4.0) | Used only to choose a synthetic voice; no person is identified | Yes | HF `alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech` @ `7a28165f33e1dbb37adbce09c0a9afcd6095dd4d` | Do not use the label to make decisions about people (it is a voice-pitch heuristic, not an identity claim) |
| **pyannote** speaker-diarization-community-1 — optional (WhisperX diarization), gated | MIT (`pyannote-audio` 4.0.7) | **CC BY 4.0**, gated on Hugging Face (accept conditions with your own HF account) | No restriction | Yes | HF `pyannote/speaker-diarization-community-1` (not downloaded by our installer) | Accept the model's conditions yourself; attribution if you redistribute |
| **Demucs** v4 (Meta) — optional background separation | MIT | MIT | No restriction | Yes | PyPI `demucs==4.0.1` (extra `separation`); weight `htdemucs` `955717e8-8726e21a.th` from `dl.fbaipublicfiles.com`, sha256 pinned in `scripts/modeller.json` (`kur.ps1 -Adim demucs`) | Keep notices if you redistribute |
| **wav2vec2 XLSR-53 Japanese / Chinese (zh-CN)** (Jonatas Grosman) — optional word timing for ja / zh sources | — | Apache-2.0 | No restriction | Yes | HF `jonatasgrosman/wav2vec2-large-xlsr-53-japanese` @ `cf031e020336460d15a417eba710bbc5bb43be9a`, `...-chinese-zh-cn` @ `99ccb2737be22b8bb50dcfcc39ad4d567fb90cfd` (`kur.ps1 -Adim hizalama-diller`) | Keep notices if you redistribute |
| WhisperX default CTC models for other source languages (not pinned; downloaded only with `DUBLAJ_CEVRIMICI=1`) | — | per model; **fr, de, es, it = VoxPopuli, CC BY-NC 4.0** (torchaudio) | fr/de/es/it: non-commercial | fr/de/es/it: **No** | WhisperX `DEFAULT_ALIGN_MODELS_TORCH` / `_HF` | Check the model card before use |
| **Coqui XTTS-v2** — optional extra `tts-xtts`, off by default | MPL-2.0 (`coqui-tts` 0.27.5, maintained fork `idiap/coqui-ai-TTS`) | **Coqui Public Model License (CPML)** — non-commercial (HF tag `license:other`); Coqui has shut down, so no commercial license can be obtained | Non-commercial only (CPML) | **No** | HF `coqui/XTTS-v2` (you download it and accept the CPML yourself; not fetched by our installer) | Non-commercial use only; reference voice must be your own or used with the speaker's explicit consent; no real-person reference clips are provided |
| **RVC** voice conversion — optional, manual, off by default | MIT (`RVC-Project/Retrieval-based-Voice-Conversion-WebUI`) | **your own model**; RVC's base pretrained weights: MIT (HF `lj1995/VoiceConversionWebUI`, the download source named by the RVC project; card tag `license:mit`, read 2026-10-25) | Depends on the model you supply | Conditional | https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI (manual, `DUBLAJ_RVC_KOK`) | Use only a model of your own voice or of a voice whose owner consented; the run is blocked unless `ses.rvc_riza_onayi = true` |
| **OpenCV** (smart crop) — optional extra `akilli-kare` | Apache-2.0 (`opencv-python-headless`, PyPI) | — | No restriction | Yes | PyPI `opencv-python-headless` | The wheel bundles FFmpeg libraries; keep notices if you redistribute |

## 2. Online services (optional; your own account and key)

Nothing is sent anywhere unless you select one of these. When you do, your audio or text goes to that provider.

| Service | What is sent | Commercial? | Source | Your obligations |
|---|---|---|---|---|
| Codex CLI (OpenAI) | transcript text for translation | Provider terms | https://github.com/openai/codex | Your OpenAI account and its terms; do not send content you may not share |
| Claude Code CLI (Anthropic) | transcript text for translation | Provider terms | https://docs.anthropic.com/en/docs/claude-code | Your Anthropic account and its terms |
| Gemini / Gemma API (Google) | transcript text | Provider terms | https://ai.google.dev | Your key and Google's API terms |
| Groq API | transcript text | Provider terms | https://console.groq.com | Your key and Groq's terms |
| Cerebras API | transcript text | Provider terms | https://cloud.cerebras.ai | Your key and Cerebras' terms |
| Mistral API | transcript text | Provider terms | https://console.mistral.ai | Your key and Mistral's terms |
| Speechmatics (batch STT) | the audio file | Provider terms | https://www.speechmatics.com | Your key and their terms; consent of people in the audio |
| Codex CLI image generation (optional cover image) | transcript text | Provider terms | https://github.com/openai/codex | Your OpenAI account and its terms; check rights before publishing a generated image |
| ElevenLabs Scribe v2 (STT) | the audio file | Provider terms | https://elevenlabs.io | Your key and their terms; consent of people in the audio |

## 3. Tools and binaries (downloaded or called, never bundled)

| Component | License | How it is used | Source / pin | Your obligations |
|---|---|---|---|---|
| **FFmpeg** 9.0.2 "essentials" build (gyan.dev) | **GPL-3.0** (this build enables GPL parts such as libx264) | separate program, called as a subprocess; downloaded by the installer to `runtime_assets/` | https://www.gyan.dev/ffmpeg/builds/ (linked from ffmpeg.org), SHA-256 in `scripts/modeller.json` | If you redistribute this binary, you must comply with the GPL-3.0 (offer the corresponding source) |
| **yt-dlp** — optional extra `youtube` | Unlicense | URL input, only when you install the extra | PyPI `yt-dlp==2026.8.19` (security floor 2026.7.4; keep it updated) | **Download only content you own or are permitted to download, and follow the site's terms and your local law** (see `ETHICS.md`) |
| **gallery-dl** — optional extra `galeri` | **GPL-2.0-only** | run **only as a separate command-line process**, never imported, never copied into this repository | PyPI `gallery-dl` (>=1.32.17) | Same as yt-dlp: only content you own or may download; login cookies stay in your own gallery-dl config |
| **python-telegram-bot** — optional extra `telegram` (remote-control bot, off by default) | **LGPL-3.0-only** (PyPI) | used unmodified as a library | PyPI `python-telegram-bot` (>=22.8) | Your bot token and allowed chat id only in your local `.env`; Telegram's terms apply |
| **Telegram Bot API server** (`tdlib/telegram-bot-api`) — optional, `dubla-telegram sunucu kur` (large-file delivery up to 2000 MB) | **BSL-1.0** | separate program (container or own build); not imported, not shipped | https://github.com/tdlib/telegram-bot-api at a pinned commit; ready-made image `aiogram/telegram-bot-api` (community build of the same source) pinned by digest | Your own `api_id` / `api_hash` from my.telegram.org only in your local `.env`; Telegram's terms apply |
| **uv** 0.13.5 (Astral) | MIT OR Apache-2.0 (both license files in `astral-sh/uv`) | installer: creates the virtual environment | GitHub release `astral-sh/uv` 0.13.5 | — |
| PyTorch CUDA wheels → NVIDIA CUDA runtime libraries (`nvidia-*` wheels) | NVIDIA CUDA EULA | GPU profile only, pulled by `torch` | https://download.pytorch.org/whl/cu128 | Do not redistribute the CUDA libraries outside the EULA's terms |

## 4. Code from other projects included in this repository

| Path | Upstream | License | Changes |
|---|---|---|---|
| `src/dublaj_hatti/bolum_50_seslendirme/supertonic_tts/konusmaci_secimi/vendor/3D-Speaker/` | `modelscope/3D-Speaker` @ `065629c313eaf1a01c65c640c46d77e61e9607b4` (only `speakerlab` inference path) | Apache-2.0 (original `LICENSE` kept) | 2026-10-24: `torch.load(..., weights_only=True)`, `yaml.safe_load`; training examples removed; FSMN VAD (modelscope → funasr → kaldiio) replaced by Silero VAD from `faster-whisper`; the unused scripts that imported `kaldiio`/`funasr` (`compute_score_metrics.py`, `extract.py`, `extract_ssl.py`, `infer_sv_batch.py`, `train_para.py`) removed. Listed in `VENDOR_NOTU.md` there (Apache-2.0 §4b). |
| `src/dublaj_hatti/bolum_20_transkripsiyon/crisperwhisper_turbo_ct2_motoru/src/native/` | CUDA softmax kernels derived from CTranslate2 (SYSTRAN, OpenNMT) | MIT (original `LICENSE` kept) | adapted for the CrisperWhisper runner |

## 5. Training-data note (sector practice, stated openly)

Some downloaded models were trained on large speech datasets collected by their authors: the 3D-Speaker CAM++
model on a large-scale Chinese–English speaker dataset (per its ModelScope card), pyannote on public diarization
benchmarks, the gender classifier on LibriSpeech (CC BY 4.0), the Turkish alignment model on Common Voice /
MediaSpeech. The model licenses above are what their authors grant; dataset terms are described on each model card.
**No training audio is distributed by this project.**

## 6. Deliberately not included

These are **not** in this repository and are not installed by it:

- **edge-tts** and any other unofficial client for a non-public Microsoft speech endpoint.
- **Unofficial Google Translate endpoints** (`googletrans`, `deep-translator`'s Google path and similar).
- **Voice samples of real people** (celebrity / public-figure reference clips and similar). Bundled or example
  audio, where present, is synthetic or made for this project.

## 7. Review items

No open item blocks a release. Resolved items stay here for the record.

| Item | Finding (primary source) | Status |
|---|---|---|
| `kaldiio` 2.18.1 (was transitive, required by `funasr`) | The `LICENSE` in both the PyPI wheel and `nttcslab-sp/kaldiio` on GitHub (added 2018-08-30) is an **NTT "Software License Agreement for Evaluation"**: internal evaluation only, no redistribution. | **Resolved 2026-10-24**: `funasr` and `kaldiio` removed from `pyproject.toml` and every lock file; the speaker-separation VAD is Silero (MIT) from `faster-whisper`; vendored scripts that imported `kaldiio` deleted. CPU smoke test: 2 speakers found on the sample video. A test (`tests/test_lisans_bagimliliklari.py`) keeps them out. |
| `Unidecode` 1.4.0 (GPL-2.0-or-later) | Was imported optionally by the file-name sanitizer. | **Resolved 2026-10-24**: removed from the dependencies and from the code; the sanitizer uses its own transliteration table (deterministic, tested). |
| Model-card comparison (every Hugging Face model in §1) | The Hugging Face API `license` field of each model, at the revision pinned in `scripts/modeller.json` for the models our installer downloads (current revision for the others), was read on 2026-10-25 and matches the weights-license column: Supertonic 3 `openrail` (the pinned `LICENSE` file is BigScience Open RAIL-M), VoxCPM2 / EMA Lightning / gender model / ja + zh CTC `apache-2.0`, faster-whisper and whisper.cpp `mit`, Turkish CTC / Opus-MT / pyannote community-1 `cc-by-4.0` (pyannote gated), CrisperWhisper 2.0 turbo + medium `nyra-health-non-commercial-research`, Parakeet `nvidia-open-model-license` (the sherpa-onnx export card has no license field; the upstream NVIDIA license applies), XTTS-v2 `coqui-public-model-license`. Non-Hugging-Face sources (torchaudio, Silero VAD, Demucs, CAM++ on ModelScope) are listed with their own pages. | **Resolved 2026-10-25** |

## 8. Python packages (from the hash-locked requirement files)

All packages installed by `requirements/gpu.txt` / `cpu.txt` (profile **core**) and by the optional extras
(`requirements/ek_*.txt`). Every extra is locked (`requirements/ek_*.txt`) except `stt-moonshine` (manual install, listed in §1 at its top-level package). License = SPDX expression from the installed package metadata or its bundled `LICENSE`
file; packages not installed on the test machine (extras) were read from PyPI JSON. Read 2026-10-24.
Copyleft entries are libraries called through their public API and do not modify; they are installed by pip from
PyPI, never copied into this repository.

| Package | Version | License | Profile | Note |
|---|---|---|---|---|
| absl-py | 2.5.1 | Apache-2.0 | extra:tts-xtts |  |
| addict | 2.4.0 | MIT | core |  |
| aiofiles | 25.1.0 | Apache-2.0 | extra:speechmatics |  |
| aiohappyeyeballs | 2.7.1 | PSF-2.0 | core/extra:speechmatics/extra:tts-xtts |  |
| aiohttp | 3.14.5 | Apache-2.0 AND MIT | core/extra:speechmatics/extra:tts-xtts |  |
| aiosignal | 1.4.0 | Apache-2.0 | core/extra:speechmatics/extra:tts-xtts |  |
| alembic | 1.20.1 | MIT | core |  |
| antlr4-python3-runtime | 4.9.3 | BSD-3-Clause | core/extra:demucs |  |
| anyascii | 0.3.3 | ISC | extra:tts-xtts |  |
| anyio | 4.15.1 | MIT | extra:telegram |  |
| asteroid-filterbanks | 0.4.0 | MIT | core |  |
| attrs | 26.1.0 | MIT | core/extra:speechmatics/extra:tts-xtts |  |
| audioread | 3.1.0 | MIT | extra:tts-xtts |  |
| av | 18.1.0 | BSD-3-Clause | core | pulled in by faster-whisper (audio decoding); not imported by this package. The Windows wheel bundles FFmpeg shared libraries that report **LGPL version 3 or later** (`av._core.library_meta[...]['license']`, read from the installed wheel); its build configuration has `--enable-version3`, no `--enable-gpl` / `--enable-nonfree`, and lists external libraries (libmp3lame, dav1d, SVT-AV1, libvpx, opus, libx264, libx265 among others) whose own licenses apply to those parts; redistributing the wheel follows PyAV's and FFmpeg's terms |
| certifi | 2026.10.23 | MPL-2.0 | core/extra:galeri/extra:telegram/extra:tts-xtts | file-level copyleft; used unmodified |
| cffi | 2.1.1 | MIT-0 | core/extra:tts-xtts |  |
| charset-normalizer | 3.5.2 | MIT | core/extra:galeri/extra:tts-xtts |  |
| click | 8.5.0 | BSD-3-Clause | core |  |
| cloudpickle | 3.1.2 | BSD-3-Clause | core/extra:demucs/extra:tts-xtts |  |
| colorama | 0.4.6 | BSD-3-Clause | core/extra:demucs/extra:tts-xtts |  |
| colorlog | 6.12.0 | MIT | core |  |
| contourpy | 1.3.3 | BSD-3-Clause | core/extra:tts-xtts |  |
| coqpit-config | 0.2.5 | MIT | extra:tts-xtts |  |
| coqui-tts | 0.27.5 | MPL-2.0 | extra:tts-xtts | file-level copyleft; used unmodified. XTTS v2 weights: CPML, non-commercial (§1) |
| coqui-tts-trainer | 0.3.3 | Apache-2.0 | extra:tts-xtts |  |
| ctranslate2 | 4.8.3 | MIT | core |  |
| cycler | 0.12.1 | BSD-3-Clause | core/extra:tts-xtts |  |
| datasets | 3.1.0 | Apache-2.0 | core |  |
| decorator | 5.3.1 | BSD-2-Clause | extra:tts-xtts |  |
| defusedxml | 0.7.1 | PSF-2.0 | core |  |
| demucs | 4.0.1 | MIT | extra:demucs |  |
| dill | 0.3.8 | BSD-3-Clause | core |  |
| docopt | 0.6.2 | MIT | extra:tts-xtts |  |
| dora-search | 0.1.13 | MIT | extra:demucs |  |
| einops | 0.8.2 | MIT | core/extra:demucs/extra:tts-xtts |  |
| ema-lightning | 1.1.0 | Apache-2.0 | extra:tts-ema | EMA Lightning TTS code (§1) |
| fastcluster | 1.3.0 | BSD-2-Clause OR GPL-2.0-or-later | core | dual-licensed; used under BSD-2-Clause |
| faster-whisper | 1.2.1 | MIT | core |  |
| filelock | 4.2.4 | MIT | core/extra:demucs/extra:tts-xtts |  |
| flatbuffers | 25.12.19 | Apache-2.0 | core |  |
| fonttools | 4.67.0 | MIT | core/extra:tts-xtts |  |
| frozenlist | 1.8.0 | Apache-2.0 | core/extra:speechmatics/extra:tts-xtts |  |
| fsspec | 2024.9.0 | BSD-3-Clause | core/extra:demucs/extra:tts-xtts |  |
| gallery-dl | 1.32.17 | GPL-2.0-only | extra:galeri | run only as a separate CLI process, never imported |
| googleapis-common-protos | 1.76.0 | Apache-2.0 | core |  |
| grpcio | 1.84.1 | Apache-2.0 | core/extra:tts-xtts |  |
| h11 | 0.16.0 | MIT | extra:telegram |  |
| hdbscan | 0.8.44 | BSD-3-Clause | core |  |
| hf-xet | 1.7.0 | Apache-2.0 | core/extra:tts-xtts |  |
| httpcore | 1.0.9 | BSD-3-Clause | extra:telegram |  |
| httpx | 0.28.1 | BSD-3-Clause | extra:telegram |  |
| huggingface-hub | 0.36.2 | Apache-2.0 | core/extra:tts-xtts |  |
| idna | 3.20 | BSD-3-Clause | core/extra:galeri/extra:speechmatics/extra:telegram/extra:tts-xtts |  |
| inflect | 7.6.0 | MIT | extra:tts-xtts |  |
| jaraco-functools | 4.6.0 | MIT | extra:tts-xtts |  |
| jinja2 | 3.1.6 | BSD-3-Clause | core/extra:demucs |  |
| joblib | 1.6.0 | BSD-3-Clause | core/extra:tts-xtts |  |
| julius | 0.2.8 | MIT | core/extra:demucs |  |
| kiwisolver | 1.5.1 | BSD-3-Clause | core/extra:tts-xtts |  |
| ko-speech-tools | 0.1.0 | Apache-2.0 | extra:tts-xtts |  |
| lameenc | 1.9.0 | LGPL-3.0-or-later | extra:demucs | dynamic library; LGPL (separately replaceable) |
| lazy-loader | 0.6 | BSD-3-Clause | extra:tts-xtts |  |
| librosa | 0.11.0 | ISC | extra:tts-xtts |  |
| lightning | 2.6.6 | Apache-2.0 | core |  |
| lightning-utilities | 0.15.3 | Apache-2.0 | core |  |
| llvmlite | 0.50.0 | BSD-2-Clause | core/extra:tts-xtts |  |
| mako | 1.4.3 | MIT | core |  |
| markdown | 3.11.2 | BSD-3-Clause | extra:tts-xtts |  |
| markdown-it-py | 4.2.0 | MIT | core |  |
| markupsafe | 3.0.4 | BSD-3-Clause | core/extra:demucs/extra:tts-xtts |  |
| matplotlib | 3.11.2 | PSF-based (matplotlib license) | core/extra:tts-xtts |  |
| mdurl | 0.1.2 | MIT | core |  |
| ml-dtypes | 0.6.0 | Apache-2.0 | core |  |
| modelscope | 1.33.0 | Apache-2.0 | core |  |
| monotonic-alignment-search | 0.2.1 | MIT | extra:tts-xtts |  |
| more-itertools | 11.2.1 | MIT | extra:tts-xtts |  |
| mpmath | 1.3.0 | BSD-3-Clause | core/extra:demucs |  |
| msgpack | 1.2.3 | Apache-2.0 | extra:tts-xtts |  |
| multidict | 7.2.0 | Apache-2.0 | core/extra:speechmatics/extra:tts-xtts |  |
| multiprocess | 0.70.16 | BSD-3-Clause | core |  |
| narwhals | 2.27.1 | MIT | core/extra:tts-xtts |  |
| networkx | 3.6.1 | BSD-3-Clause | core/extra:demucs |  |
| nltk | 3.10.4 | Apache-2.0 | core |  |
| normalizer-tr | 0.5.0 | Apache-2.0 | extra:tts-ema | Turkish text normaliser used by EMA Lightning; native wheel, bundled Rust crates under MIT / Apache-2.0 (licences shipped in the wheel) |
| num2words | 0.5.14 | LGPL-2.1-or-later (`COPYING` at tag `v0.5.14` is LGPL 2.1; source headers say "version 2.1 of the License, or (at your option) any later version"; PyPI classifier only "LGPL") | extra:tts-xtts | library, used unmodified (LGPL) |
| numba | 0.68.0 | BSD-2-Clause | core/extra:tts-xtts |  |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | core/extra:akilli-kare/extra:demucs/extra:tts-xtts |  |
| omegaconf | 2.3.1 | BSD-3-Clause | core/extra:demucs |  |
| onnx | 1.21.0 | Apache-2.0 | core |  |
| onnxruntime | 1.31.0 | MIT | core |  |
| opencv-python-headless | 5.0.0.93 | Apache-2.0 | extra:akilli-kare |  |
| opentelemetry-api | 1.45.1 | Apache-2.0 | core |  |
| opentelemetry-exporter-http-transport | 0.66b1 | Apache-2.0 | core |  |
| opentelemetry-exporter-otlp | 1.45.1 | Apache-2.0 | core |  |
| opentelemetry-exporter-otlp-common | 0.66b1 | Apache-2.0 | core |  |
| opentelemetry-exporter-otlp-proto-common | 1.45.1 | Apache-2.0 | core |  |
| opentelemetry-exporter-otlp-proto-grpc | 1.45.1 | Apache-2.0 | core |  |
| opentelemetry-exporter-otlp-proto-http | 1.45.1 | Apache-2.0 | core |  |
| opentelemetry-proto | 1.45.1 | Apache-2.0 | core |  |
| opentelemetry-sdk | 1.45.1 | Apache-2.0 | core |  |
| opentelemetry-semantic-conventions | 0.66b1 | Apache-2.0 | core |  |
| openunmix | 1.3.0 | MIT | extra:demucs |  |
| optuna | 5.0.0 | MIT | core |  |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | core/extra:tts-xtts |  |
| pandas | 3.1.0 | BSD-3-Clause | core |  |
| pillow | 13.0.0 | MIT-CMU | core/extra:tts-xtts |  |
| platformdirs | 4.13.5 | MIT | extra:tts-xtts |  |
| pooch | 1.9.0 | BSD-3-Clause | extra:tts-xtts |  |
| primepy | 1.3 | MIT | core |  |
| propcache | 0.5.4 | Apache-2.0 | core/extra:speechmatics/extra:tts-xtts |  |
| protobuf | 7.36.2 | BSD-3-Clause | core/extra:tts-xtts |  |
| psutil | 7.2.2 | BSD-3-Clause | core/extra:tts-xtts |  |
| pyannote-audio | 4.0.7 | MIT | core |  |
| pyannote-core | 6.1.0 | MIT | core |  |
| pyannote-database | 6.1.1 | MIT | core |  |
| pyannote-metrics | 4.2.0 | MIT | core |  |
| pyannote-pipeline | 4.1.0 | MIT | core |  |
| pyannoteai-sdk | 0.4.0 | MIT | core |  |
| pyarrow | 26.0.0 | Apache-2.0 | core |  |
| pycparser | 3.12 | BSD-3-Clause | core/extra:tts-xtts |  |
| pygments | 2.21.0 | BSD-2-Clause | core |  |
| pynndescent | 0.6.0 | BSD-2-Clause | core |  |
| pyparsing | 3.3.3 | MIT | core/extra:tts-xtts |  |
| pysbd | 0.3.4 | MIT | extra:tts-xtts |  |
| python-dateutil | 3.0.0 | Apache-2.0 OR BSD-3-Clause | core/extra:tts-xtts |  |
| python-dotenv | 1.2.4 | BSD-3-Clause | core |  |
| python-telegram-bot | 22.8 | LGPL-3.0-only | extra:telegram | library, used unmodified (LGPL) |
| pytorch-lightning | 2.6.6 | Apache-2.0 | core |  |
| pytorch-metric-learning | 2.9.0 | MIT | core |  |
| pyyaml | 6.0.3 | MIT | core/extra:demucs/extra:tts-xtts |  |
| regex | 2026.9.29 | Apache-2.0 AND CNRI-Python | core/extra:tts-xtts |  |
| requests | 2.34.2 | Apache-2.0 | core/extra:galeri/extra:tts-xtts |  |
| retrying | 1.4.2 | Apache-2.0 | extra:demucs |  |
| rich | 15.0.0 | MIT | core |  |
| safetensors | 0.8.0 | Apache-2.0 | core/extra:tts-xtts |  |
| scikit-learn | 1.9.1 | BSD-3-Clause | core/extra:tts-xtts |  |
| scipy | 1.17.1 | BSD-3-Clause | core/extra:tts-xtts |  |
| sentencepiece | 0.2.2 | Apache-2.0 | core |  |
| setuptools | 80.9.0 | MIT | core/extra:tts-xtts |  |
| sherpa-onnx | 1.13.4 | Apache-2.0 | extra:parakeet |  |
| sherpa-onnx-core | 1.13.4 | Apache-2.0 | extra:parakeet |  |
| simplejson | 4.1.1 | MIT OR AFL-2.1 | core | dual-licensed; used under MIT |
| six | 1.17.0 | MIT | core/extra:tts-xtts |  |
| sortedcontainers | 2.4.0 | Apache-2.0 | core |  |
| soundfile | 0.14.0 | BSD-3-Clause | core/extra:tts-xtts |  |
| soxr | 1.1.0 | LGPL-2.1-or-later | extra:tts-xtts | dynamic library; LGPL (separately replaceable) |
| speechmatics-batch | 0.4.7 | MIT | extra:speechmatics |  |
| sqlalchemy | 2.1.6 | MIT | core |  |
| submitit | 1.5.4 | MIT | extra:demucs |  |
| sympy | 1.14.0 | BSD-3-Clause | core/extra:demucs |  |
| tensorboard | 2.21.0 | Apache-2.0 | extra:tts-xtts |  |
| tensorboard-data-server | 0.7.2 | Apache-2.0 | extra:tts-xtts |  |
| threadpoolctl | 3.7.0 | BSD-3-Clause | core/extra:tts-xtts |  |
| tokenizers | 0.22.2 | Apache-2.0 | core/extra:tts-xtts |  |
| torch | 2.8.0+cu128 | BSD-3-Clause | core/extra:demucs | CUDA profile pulls NVIDIA CUDA runtime wheels (NVIDIA EULA) |
| torch-audiomentations | 0.12.0 | MIT | core |  |
| torch-pitch-shift | 1.2.5 | MIT | core |  |
| torchaudio | 2.8.0+cu128 | BSD-2-Clause | core/extra:demucs |  |
| torchcodec | 0.7.0 | BSD-3-Clause | core |  |
| torchmetrics | 1.9.0 | Apache-2.0 | core |  |
| torchvision | 0.23.0+cu128 | BSD-3-Clause | core |  |
| tqdm | 4.70.1 | MPL-2.0 AND MIT | core/extra:demucs/extra:tts-xtts | file-level copyleft; used unmodified |
| transformers | 4.57.6 | Apache-2.0 | core/extra:tts-xtts |  |
| treetable | 0.2.6 | Unlicense | extra:demucs |  |
| typeguard | 4.6.0 | MIT | extra:tts-xtts |  |
| typing-extensions | 4.16.0 | PSF-2.0 | core/extra:demucs/extra:speechmatics/extra:telegram/extra:tts-xtts |  |
| tzdata | 2026.5 | Apache-2.0 | core/extra:tts-xtts |  |
| umap-learn | 0.5.7 | BSD-3-Clause | core |  |
| urllib3 | 2.8.0 | MIT | core/extra:galeri/extra:tts-xtts |  |
| werkzeug | 3.1.9 | BSD-3-Clause | extra:tts-xtts |  |
| whisperx | 3.8.6 | BSD-2-Clause | core |  |
| xxhash | 4.0.2 | BSD-2-Clause | core |  |
| yarl | 1.25.1 | Apache-2.0 | core/extra:speechmatics/extra:tts-xtts |  |
| yt-dlp | 2026.8.19 | Unlicense | extra:youtube |  |

Counts: 172 packages (core + locked extras). Non-permissive: 1 GPL (gallery-dl; separate process only), 4 LGPL (lameenc, num2words, python-telegram-bot, soxr), 3 MPL-2.0 (certifi, coqui-tts, tqdm); no proprietary or evaluation-only license; all others MIT / BSD / Apache-2.0 / ISC / PSF / Unlicense family.
