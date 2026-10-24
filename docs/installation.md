# Installation and environment map

[Türkçe](kurulum.md) · Hardware matrix: [donanim.md](donanim.md) · Low-VRAM guide:
[engineering/low_vram.md](engineering/low_vram.md) · Agent skill: `.claude/skills/kurulum-ve-donanim/SKILL.md`

This page is the single reference for installing the pipeline: what the machine needs, which Python environments
are created, in which order, where every file goes and how to verify, update and remove the installation. Every
command below exists in `scripts/kur.ps1` or in the files it calls. Statements carry their evidence level:
**tested** (run on the test configuration), **per docs** (read from a script, lock file or model card, not run here),
**not tested**.

Test configuration (all measured numbers on this page): Windows 10 x64, a 4 GB VRAM Pascal-class NVIDIA GPU
(compute capability 6.1), 16 GB RAM, NVIDIA driver from the R580 series.

## 0. Let your AI assistant install it

The shortest route, also for people who do not program: open an AI assistant that can run commands on the computer
(Claude Code, Codex, Gemini CLI or similar) and paste:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

The assistant follows the deterministic flow in [../AGENTS.md](../AGENTS.md): prerequisite checks, one install
command, `dubla kontrol` (last line `READY`), one question (acceptance of the default voice's use conditions), a
sample dub, then it opens the desktop app. Plain-language guide for the user: [getting-started.md](getting-started.md).

## 1. System requirements

| Item | Requirement | Notes |
|---|---|---|
| Operating system | Windows 10 or 11, x64 | The installer is PowerShell 5.1+ (built into Windows). Linux / macOS: section 11. |
| Python | **none needed beforehand** | `kur.ps1` installs CPython **3.11.14** with a pinned `uv` 0.13.5 into the repository folder. The package requires Python 3.11. The optional `voxcpm2` step runs the sister repository's installer with this Python put on `PATH` for that process only (section 7); the system `PATH` is not changed. |
| git | needed for the optional `crisper` and `voxcpm2` steps | The base install works from a ZIP download of the repository. |
| NVIDIA driver (GPU profile) | R570 or newer (CUDA 12.8 runtime), `nvidia-smi` must run | CUDA comes inside the PyTorch wheel (`torch 2.8.0+cu128`); **no CUDA Toolkit, cuDNN or PATH change is required**. R580 is announced as the last driver series with Pascal support; check support before upgrading the driver on an older card. |
| GPU | optional; NVIDIA with 4 GB VRAM is enough for the recommended flow | Pascal (sm_61) and newer. CUDA 13 builds do not support Pascal (section 12). AMD / Intel GPUs: the CPU profile is used. |
| RAM | 8 GB minimum (estimate), 16 GB tested | Peaks measured on the test configuration: Supertonic ≈ 1.8 GB, Demucs ≈ 7.2 GB for 75 min of audio, CrisperWhisper Turbo model conversion ≈ 4.5 GB free RAM. |
| ffmpeg | none needed beforehand | FFmpeg **9.0.2** (pinned build, sha256-verified) is installed to `runtime_assets/ffmpeg/bin`; the CLI puts it first on `PATH` for its own process. |
| Disk | see the table below; SSD recommended | Cold model loads were ≈ 12 s slower per GB of weights on an HDD (engineering/low_vram.md). |
| WSL2 + Ubuntu 24.04 | only for the optional `crisper` step | Section 7. |

Disk space per profile:

| Profile / add-on | Size | Evidence |
|---|---|---|
| Models and tools of the default steps (`runtime_assets/` without the uv cache) | ≈ 5.5 GB (manifest sum); ≈ 5.5 GB measured after a clean install | per docs (`scripts/modeller.json`) / tested (clean root) |
| Main environment `.venv`, GPU profile | ≈ 7.8 GB | tested (clean root) |
| Main environment `.venv`, CPU profile | ≈ 3.8 GB | tested (clean root) |
| uv download cache `runtime_assets/onbellek/uv` | ≈ 7.8 GB (GPU) / ≈ 3.9 GB (CPU); can be deleted after install | tested (clean root) |
| **Total, GPU profile** | **≈ 22 GB** (≈ 14 GB after deleting the uv cache); download ≈ 13 GB | tested (clean root) |
| **Total, CPU profile** | **≈ 13.2 GB** (≈ 9.3 GB after deleting the uv cache); download ≈ 9.5 GB | tested (clean root) |
| `crisper` add-on | ≈ 7 GB (torch cu126 ≈ 3 GB, model 1.6 GB + converted 1.6 GB) | per docs (sister STT repository) |
| `voxcpm2` add-on | ≈ 3.7 GB download (model 2.95 GB + CUDA runtime DLLs + engine) | per docs (sister TTS repository) |
| `tts-xtts` add-on | separate environment with its own PyTorch (≈ 3–8 GB) + weights downloaded on first use | estimate |
| `parakeet` add-on | ≈ 0.7 GB model | per docs (`kur.ps1`) |

## 2. Quick install

1. Download or clone the repository to a short path without spaces (for example `C:\dublaj`).
2. Double-click **`kur.cmd`** in the repository root (or run it from a terminal). It calls `scripts\kur.ps1` with the
   default steps and keeps the window open at the end.
3. Wait for the last line `KURULUM_OK`. A first install downloads ≈ 9 GB (GPU profile); later runs skip every file
   whose sha256 is already correct.
4. Start: double-click `arayuz.cmd` (desktop interface); local web interface `web.cmd`; command line
   `.venv\Scripts\dubla.exe <video.mp4>`. If the install stops, the window shows `KURULUM DURDU / INSTALL STOPPED`
   and what to do; run `kur.cmd` again (section 12).

Equivalent commands:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1          # automatic: GPU if NVIDIA works, else CPU
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Cpu     # force the CPU profile
kur.cmd -Cpu                                                                 # same, through the launcher
```

`-ExecutionPolicy Bypass` applies to this one process only; the system policy is not changed. Read `scripts\kur.ps1`
before running it, as with any installer.

What the installer does **not** do: it does not change the system `PATH`, the registry, the global Python, the
NVIDIA driver or WSL; it does not need administrator rights (except the one-time `wsl --install` for the optional
`crisper` step, which the user runs).

## 3. Profiles

| Profile | Lock file | PyTorch | Chosen when | Recommended flow engines |
|---|---|---|---|---|
| `gpu` | `requirements/gpu.txt` (hash-locked, generated from `gpu.in`) | `2.8.0+cu128` from the PyTorch index | `nvidia-smi` runs and reports a GPU | faster-whisper large-v3-turbo + CTC on GPU, Opus-MT, Supertonic (CPU by design), NVENC if available |
| `cpu` | `requirements/cpu.txt` (generated from `cpu.in`) | `2.8.0+cpu` | `-Cpu`, or no working `nvidia-smi` | faster-whisper int8 on CPU, Supertonic, `ses_temizligi.kip=original`, libx264 |

Both lock files share the same direct dependencies (`requirements/temel.in`) and differ only in the PyTorch build.
The chosen profile is written to `.venv/dublaj_profil.txt`; optional steps read it. At run time
`genel.cihaz = auto` runs a real CUDA kernel and falls back to the CPU with a logged reason (donanim.md).

## 4. Step order

`kur.ps1 -Adim <list>` runs any subset; the order inside the script is fixed and is shown here. Each step prints a
marker line on success.

| # | Step (`-Adim`) | Default | What it does | Needs before | Marker |
|---|---|---|---|---|---|
| 1 | `uv` | yes | downloads uv 0.13.5 (sha256-pinned ZIP) to `runtime_assets/araclar/uv` | network | `UV_OK` |
| 2 | `python` | yes | `uv python install 3.11.14 --no-bin` into `runtime_assets/python` | 1 | `PYTHON_OK` |
| 3 | `paketler` | yes | detects the profile, creates `.venv`, installs `requirements/gpu.txt` or `cpu.txt` with `--require-hashes`, then this package with `--no-deps -e .` (commands `dubla`, `dubla-gui`, `dubla-web`, `dubla-telegram`) | 2 | `PAKETLER_OK` |
| 4 | `modeller` | yes | `scripts/modelleri_indir.py --adim supertonic,ceviri,stt,hizalama,konusmaci,ffmpeg` (section 6) | 3 | `MODELLER_OK` |
| 5 | `demucs`, `youtube`, `parakeet`, `speechmatics` | no | hash-locked add-ons into `.venv` (`requirements/ek_<name>.txt`; on the CPU profile `ek_<name>_cpu.txt` when present); `demucs` also downloads the `htdemucs` weight (≈ 84 MB, sha256), `parakeet` its model | 3 | `<NAME>_OK` |
| 5b | `hizalama-diller` | no | CTC word-timing models for Japanese and Chinese sources (`modelleri_indir.py --adim hizalama-diller`, ≈ 2.5 GB, Apache-2.0) | 3 | `HIZALAMA-DILLER_OK` |
| 6 | `akilli-kare`, `galeri`, `telegram` | no | add-ons into `.venv` from `requirements/ek_<name>.txt` (hash-locked) | 3 | `<NAME>_OK` |
| 7 | `tts-xtts` | no | separate environment for XTTS v2 (section 5), requires `-TicariOlmayanKabul` | 3 | `XTTS_OK` |
| 8 | `crisper` | no | CrisperWhisper 2.0 Turbo through the sister STT repository + WSL environment, requires `-TicariOlmayanKabul` | 3, git, WSL2 | `CRISPER_MOTOR_OK`, `CRISPER_OK` |
| 9 | `voxcpm2` | no | clones the sister TTS repository at a pinned commit and runs its own installer | git, NVIDIA (uses the repository's Python 3.11.14) | `VOXCPM2_OK` |
| 10 | `kontrol` | yes | real 64×64 CUDA matmul (GPU profile must report a CUDA build), then `dubla kontrol` | 3 | `KONTROL_OK` |

The script always ends with `KURULUM_OK`. Optional steps can be added later in any combination, for example
`-Adim demucs,youtube`. Steps are idempotent: a re-run after a failure continues where files are missing.

## 5. Environment map

The application runs every heavy model in its own process; some engines also need their **own Python
environment** because their pinned dependencies cannot coexist with the main lock. The main pipeline needs exactly
one environment.

| Environment | Location | Python | Lock / pin | Used by | Why separate | Size | Created by |
|---|---|---|---|---|---|---|---|
| **Main** | `.venv/` | 3.11.14 (uv) | `requirements/gpu.txt` or `cpu.txt` (hash), add-ons `requirements/ek_*.txt` | CLI, GUI, web, Telegram bot, faster-whisper, WhisperX, CTC word alignment, Opus-MT, Supertonic, 3D-Speaker, gender classifier, Demucs, Parakeet, Speechmatics/ElevenLabs clients, yt-dlp, gallery-dl, OpenCV | – (base) | ≈ 7.8 GB GPU, ≈ 3.8 GB CPU | `-Adim paketler` |
| **XTTS v2** | `runtime_assets/tts_motorlari/xtts/venv/` | 3.11.14 (uv) | `requirements/xtts_venv_gpu.txt` / `xtts_venv_cpu.txt` (hash, PyTorch included) | `ses.motor = xtts` (called as a subprocess through `DUBLAJ_XTTS_PYTHON`, written to `.env`) | keeps `coqui-tts` and its ≈ 80-package dependency tree, and the non-commercial engine, out of the locked main environment | not measured | `-Adim tts-xtts -TicariOlmayanKabul` |
| **CrisperWhisper Turbo runtime (WSL)** | `runtime_assets/transkripsiyon_motorlari/crisperwhisper_turbo_ct2/.venv_wsl_ct2/` (Linux venv inside WSL2) | 3.12 (Ubuntu 24.04 system Python) | `src/dublaj_hatti/bolum_20_transkripsiyon/crisperwhisper_turbo_ct2_motoru/requirements/requirements_wsl_ct2.lock.txt` (pinned versions, no hashes; `pip check` must pass) | `transkripsiyon.motor = crisperwhisper_turbo_ct2` | the CTranslate2 fork `ctranslate2-crisperwhisper` ships Linux wheels only; CUDA comes from pip `nvidia-cublas-cu12` 12.9 | ≈ 1 GB (estimate) | `-Adim crisper` |
| **CrisperWhisper conversion (WSL)** | `runtime_assets/transkripsiyon_motorlari/stt_repo/.venv/` | Ubuntu Python (3.10–3.12 per sister repo) | sister STT repository `requirements.txt` + PyTorch cu126 | one-time download and CTranslate2 conversion of the model; not used at run time | conversion needs PyTorch + Transformers; Linux cu128 wheels lack Pascal kernels, so cu126 is used | ≈ 3 GB + model 3.2 GB | `-Adim crisper` (sister installer) |
| **VoxCPM2** | `runtime_assets/tts_motorlari/voxcpm2/repo/.venv/` (+ engine, model, CUDA DLLs under `.../voxcpm2/kok/`) | the repository's Python 3.11.14 (put on `PATH` for the step) | sister TTS repository `requirements.txt` (numpy, soundfile); the model runs in a C++ engine (audio.cpp), not in Python | `ses.motor = voxcpm2` | separate project with its own engine binary and CUDA 12.8 runtime DLLs | ≈ 3.7 GB | `-Adim voxcpm2` |
| **Moonshine** (manual) | `src/dublaj_hatti/bolum_20_transkripsiyon/moonshine_medium_streaming_motoru/.venv/` or `DUBLAJ_MOONSHINE_ROOT` / `DUBLAJ_MOONSHINE_PYTHON` | 3.10+ | `moonshine-voice==0.0.73` (the engine verifies the sha256 of the bundled `moonshine.dll` and `onnxruntime.dll`) | `moonshine_medium_streaming_en` (experimental) | ships its own native runtime and pins numpy independently of the main lock | ≈ 0.15 GB | manual, docs/motorlar/moonshine_medium_streaming_en.md |
| **CrisperWhisper 2.0 Medium** (manual) | `src/dublaj_hatti/bolum_20_transkripsiyon/crisperwhisper2_medium_motoru/.venv/` or `DUBLAJ_CRISPERWHISPER_ROOT` / `DUBLAJ_CRISPERWHISPER_PYTHON` | 3.10+ | reference combination: `crisperwhisper==2.0.1`, `transformers==5.14.1`, `torch 2.6.0+cu118`, numpy 2.2.6, model snapshot `ca981a99…` | `crisperwhisper2_medium` | Transformers 5.x conflicts with the main lock (Transformers 4.57.6) | not measured | manual, docs/motorlar/crisperwhisper2_medium.md |
| **RVC** (manual) | the official RVC WebUI clone, `DUBLAJ_RVC_KOK` (+ `DUBLAJ_RVC_PYTHON`) | as required by RVC WebUI | its own requirements | `ses.rvc_model` post-processing | separate upstream project with its own PyTorch and numpy | – | manual, docs/motorlar/rvc.md |

Not Python environments: **whisper.cpp** (`whisper_cpp_cpu_align`) is the official prebuilt `whisper-cli.exe` placed
under `runtime_assets/transkripsiyon_motorlari/whisper_cpp_cpu_align/` (or `DUBLAJ_WHISPER_CPP_CPU_ROOT`);
**FFmpeg** is a binary in `runtime_assets/ffmpeg/bin`. The Codex and Claude Code CLIs used by the translation
backends are installed by the user and found on `PATH` (or `CODEX_BRIDGE_CODEX_BIN`, `CODEX_BRIDGE_CLAUDE_CLI`).

Design rule behind the map: a new engine whose pins (PyTorch, numpy, Transformers, ONNX Runtime) differ from the
main lock gets its own environment and is called as a subprocess through a `DUBLAJ_*_PYTHON` variable; it is never
forced into `.venv`. `DUBLAJ_WHISPERX_PYTHON` exists for the same reason but defaults to the main interpreter,
because WhisperX 3.8.6 fits the main lock.

Recommended order when several are wanted: main (`paketler`, `modeller`) → `kontrol` → hash-locked add-ons
(`demucs`, `parakeet`, …) → separate environments (`tts-xtts`, `voxcpm2`, `crisper`) → manual engines. Each separate
environment can be removed alone without touching `.venv`.

## 6. Models and offline use

- **Source of truth:** `scripts/modeller.json` (URL pinned to a commit or release, target path, size, sha256,
  license, source). `python scripts/modelleri_indir.py --liste` prints it. No weights are stored in the repository.
- **Default steps:** `supertonic` (≈ 0.40 GB), `ceviri` Opus-MT en→tr (≈ 0.47 GB), `stt` faster-whisper
  large-v3-turbo (≈ 1.62 GB), `hizalama` wav2vec2 CTC en + tr (≈ 1.64 GB), `konusmaci` 3D-Speaker + gender classifier
  (≈ 1.29 GB), `ffmpeg` (≈ 0.12 GB ZIP). Optional: `parakeet`, `crisper` (configuration file only; the weights come
  through the sister repository).
- **Where:** `runtime_assets/model_cache/` (Hugging Face cache layout with `refs/main` written for offline lookup),
  `runtime_assets/tts_motorlari/`, `runtime_assets/ffmpeg/`, `runtime_assets/indirilen/`. The downloader refuses a
  target outside `runtime_assets/`.
- **Verification:** HTTPS only, host allow-list (Hugging Face, PyTorch, GitHub, ModelScope); each file downloads to
  `<name>.part`, size and sha256 are checked, then it is moved into place. A mismatch deletes the partial file and
  stops with the expected and received hash. Correct existing files are skipped.
- **Offline at run time:** the CLI sets `HF_HUB_OFFLINE=1` and points `HF_HOME` / `TORCH_HOME` to
  `runtime_assets/model_cache`; nothing is downloaded during a job. `DUBLAJ_CEVRIMICI=1` allows run-time downloads
  (needed only for engines whose models are not in the manifest). A missing Demucs weight or CTC model stops the job
  before that stage starts, with the install step in the message (for an automatic source language: right after
  language detection, before transcription).
- **Air-gapped machine (not tested):** install on a connected machine at the same absolute path, then copy the whole
  repository folder. The environment stores absolute paths (`.venv/pyvenv.cfg`); a different path requires re-running
  `-Adim python,paketler`, which needs the wheel cache (`runtime_assets/onbellek/uv`) and `UV_OFFLINE=1` without
  network.

## 7. Optional add-ons

| `-Adim` | Installs | Into | License note | Confirmation flag |
|---|---|---|---|---|
| `demucs` | Demucs 4.0.1 (`ses_temizligi.kip = clean / preserve_background`) + pinned `htdemucs` weight | `.venv`, `runtime_assets/model_cache/torch/` | MIT (code and weight) | – |
| `hizalama-diller` | wav2vec2 CTC models for Japanese and Chinese sources (other source languages: `DUBLAJ_CEVRIMICI=1`; WhisperX's fr/de/es/it defaults are CC BY-NC 4.0) | `runtime_assets/model_cache/huggingface/` | Apache-2.0 | – |
| `youtube` | yt-dlp (URL input) | `.venv` | Unlicense; only content you own or may download (ETHICS.md) | – |
| `parakeet` | sherpa-onnx + Parakeet Unified EN 0.6B INT8 (English, CPU) | `.venv`, `runtime_assets/model_cache/` | NVIDIA Open Model License (commercial use with conditions) | – |
| `speechmatics` | Speechmatics batch client | `.venv` | cloud service, your own key in `.env`; audio leaves the machine | – |
| `akilli-kare` | OpenCV headless (`video.akilli_kare`) | `.venv` | Apache-2.0 | – |
| `galeri` | gallery-dl (called only as a separate process) | `.venv` | GPL-2.0-only; never imported | – |
| `telegram` | python-telegram-bot (remote control bot, token only in `.env`) | `.venv` | LGPL-3.0-only, used unmodified as a library | – |
| `tts-xtts` | coqui-tts + PyTorch in a separate environment; writes `DUBLAJ_XTTS_PYTHON` to `.env` and records the license acceptance | `runtime_assets/tts_motorlari/xtts/venv` | XTTS v2 weights: Coqui Public Model License, **non-commercial**; weights download from Coqui on first use | `-TicariOlmayanKabul` |
| `crisper` | CrisperWhisper 2.0 Turbo (engine 13) via the sister STT repository at a pinned commit; CTranslate2 conversion; WSL runtime environment | `runtime_assets/transkripsiyon_motorlari/` | weights **non-commercial** (model card) | `-TicariOlmayanKabul` |
| `voxcpm2` | sister TTS repository at a pinned commit and its installer (model, CUDA 12.8 runtime DLLs, prebuilt engine, Python packages) | `runtime_assets/tts_motorlari/voxcpm2/` | per THIRD_PARTY.md | – |

Prerequisites of the steps that use other repositories:

- `crisper`: WSL2 with **Ubuntu 24.04** (`wsl --install -d Ubuntu`, once, administrator; then open Ubuntu once to
  create the user), NVIDIA driver R570+ on Windows (`nvidia-smi` must work inside WSL), git. The runtime lock pins
  numpy 2.5.2, which needs Python ≥ 3.12 (PyPI `Requires-Python`); Ubuntu 22.04 ships Python 3.10 and is therefore not suitable for the
  runtime environment. `scripts/crisper_kur.py` checks WSL and the distribution's `python3` version before any download
  and stops with a clear message. The distribution name is passed with `--dagitim` (default `Ubuntu`).
- `voxcpm2` and `crisper`: if the repository URL placeholders are not filled, set `DUBLAJ_TTS_REPO_URL` /
  `DUBLAJ_STT_REPO_URL` (README "Family"). The commit is fixed in `kur.ps1`; any URL is checked out at that commit.
- `voxcpm2`: needs git and an NVIDIA GPU. The sister installer looks for `py -3`, `python` or `python3` (64-bit, 3.10+);
  `kur.ps1` puts its own Python 3.11.14 first on `PATH` for this step only, so no system Python is needed.

Engines without an installer step (manual, see their pages in `docs/motorlar/`): `moonshine_medium_streaming_en`,
`crisperwhisper2_medium`, `whisper_cpp_cpu_align`, `rvc`; cloud engines need only a key in `.env`
(`.env.example` lists the names).

## 8. Verify the installation

The `kontrol` step runs automatically at the end of the default install. It can be run any time:

```powershell
.venv\Scripts\dubla.exe kontrol            # human-readable
.venv\Scripts\dubla.exe kontrol --json     # machine-readable
```

Example output on the test configuration (CPU forced with `--ayar genel.cihaz=cpu`; lines shortened):

```text
DubWorld 0.1.0 · Python 3.11.14
  donanım.cuda: False
  donanım.torch: 2.8.0+cu128
  donanım.cihaz: cpu
  donanım.whisper_hesap_tipi: int8
  ffmpeg: <repo>\runtime_assets\ffmpeg\bin\ffmpeg.EXE
  stt: faster-whisper=var, whisperx=var, crisperwhisper_turbo_ct2=yok, ...
  ceviri: yerel=var, codex=var, claude_code=var, gemini_2_5_flash=yok, ...
  tts: supertonic=var, voxcpm2=yok, xtts=yok
  ek: demucs=yok, yt_dlp=yok, konusmaci_ayrimi=var, cinsiyet_siniflandirici=var, ...
  deneysel / experimental: moonshine_medium_streaming_en (...)
```

How to read it:

| Line | Expected after the default install | If not |
|---|---|---|
| `Python` | `3.11.14` | a different interpreter runs the command; use `.venv\Scripts\dubla.exe` |
| `donanım.torch` | `2.8.0+cu128` (GPU profile) or `2.8.0+cpu` | wrong wheel: section 12, row 6 |
| `donanım.cuda` / `donanım.cihaz` | `True` / `cuda` on a working NVIDIA GPU, otherwise `False` / `cpu` | GPU present but `False`: driver, or a CPU wheel |
| `ffmpeg` | a path inside `runtime_assets\ffmpeg\bin` | `-Adim modeller` (FFmpeg is part of the model step) |
| `stt` / `ceviri` / `tts` / `ek` | `var` = installed, `yok` = not installed; recommended flow: `faster-whisper`, `whisperx`, `yerel`, `supertonic`, `konusmaci_ayrimi`, `cinsiyet_siniflandirici` are `var` | install the add-on (section 7); cloud engines show `var` only when their key is set |
| `deneysel` | informational | – |
| `SONUÇ / RESULT` (last line) | `Önerilen akış HAZIR / recommended flow READY` | `EKSİK / MISSING: <parts>`: re-run the installer (`kur.cmd`); a `not / note` line above it means a GPU install whose GPU does not run (rows 6–7 of section 12) |

`codex` / `claude_code` show `var` when the respective CLI is found on `PATH`. The GPU check in `kur.ps1` does not
trust `torch.cuda.is_available()` alone: some builds report `True` without kernels for older GPUs, so a real matmul
is executed.

## 9. Update

```powershell
git pull                                                                      # or replace the files from a new ZIP
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1          # re-runs the default steps
```

New or changed models and locks are applied; unchanged files are skipped. `uv pip install -r` adds and changes
packages but does not remove packages that a new lock no longer lists; for an exact match delete `.venv` and run
`-Adim paketler,kontrol`. Repeat the optional steps that were installed before (for example `-Adim demucs`).
Maintainers regenerate lock files only with `scripts\kilitle.ps1` (never by hand).

## 10. Uninstall

Everything lives inside the repository folder, so deleting the folder removes the installation. Parts that can be
removed separately:

| Folder / file | Contains | Safe to delete |
|---|---|---|
| `.venv/` | main environment | yes; reinstall with `-Adim paketler` |
| `runtime_assets/onbellek/` | uv download cache | yes, any time after install |
| `runtime_assets/model_cache/`, `runtime_assets/indirilen/`, `runtime_assets/ffmpeg/` | models, FFmpeg | yes; reinstall with `-Adim modeller` |
| `runtime_assets/python/`, `runtime_assets/araclar/` | CPython 3.11.14, uv | yes, together with `.venv` |
| `runtime_assets/tts_motorlari/xtts/` | XTTS environment | yes; also remove `DUBLAJ_XTTS_PYTHON` from `.env` |
| `runtime_assets/tts_motorlari/voxcpm2/` | VoxCPM2 repository, environment, engine and model | yes |
| `runtime_assets/transkripsiyon_motorlari/` (`stt_repo`, `stt_kok`, `crisperwhisper_turbo_ct2`) | CrisperWhisper sources, conversion and runtime environments, model | yes; the WSL distribution itself is not touched |
| `cikti/` (or `DUBLAJ_OUTPUT_DIR`) | **your outputs** and the job database `_is_deposu/isler.sqlite3` | only if the outputs are no longer needed |
| `.env`, `ayarlar/kullanici.toml`, `ayarlar/lisans_onaylari.json` | keys, personal settings, license acceptances | only on purpose |

Outside the folder: the machine-wide GPU lock directory `dublaj_hatti_kaynak_kilitleri` in the system temporary
folder (or `DUBLAJ_KILIT_KLASORU`) contains only small lock files. Manually installed engines (RVC WebUI, a
Moonshine or CrisperWhisper Medium environment outside the repository) and WSL are removed by their own means.

## 11. Linux and macOS

| Platform | Status |
|---|---|
| Windows 10/11 x64 | supported and tested (CPU profile end to end; GPU profile on a Pascal-class GPU) |
| Linux x64 | **not tested**, no installer and no Linux lock file. The package itself is plain Python 3.11 (`pyproject.toml` lists Linux). |
| macOS | **not tested**, no installer; no CUDA, so CPU only. |

Manual steps for Linux (not tested; the commands follow `pyproject.toml` extras, versions are not locked):

```bash
python3.11 -m venv .venv
.venv/bin/pip install --index-url https://download.pytorch.org/whl/cu126 torch==2.8.0 torchaudio==2.8.0   # Pascal: cu126; CPU: /whl/cpu
.venv/bin/pip install -e ".[onerilen]"
.venv/bin/python scripts/modelleri_indir.py --adim supertonic,ceviri,stt,hizalama,konusmaci
# ffmpeg from the distribution (the manifest FFmpeg build is a Windows binary): sudo apt install ffmpeg
.venv/bin/dubla kontrol
```

On Linux use a **cu126** PyTorch build on Pascal GPUs: Linux cu128 wheels carry no sm_61 kernels although
`torch.cuda.is_available()` returns `True` (engineering/gpu_memory_and_isolation.md). Reports and a Linux lock file
are welcome as pull requests.

## 12. Common installation errors

All entries come from real failures recorded during development (engineering pages and the debt log).

| # | Symptom | Cause | Fix |
|---|---|---|---|
| 1 | `No module named pkg_resources` when speaker separation starts | ModelScope 1.33 imports `pkg_resources`; setuptools 81+ removed it | the lock pins `setuptools==80.9.0`; do not upgrade setuptools inside `.venv` |
| 2 | `No module named datasets` from ModelScope | `modelscope.pipelines` needs `MsDataset` | the lock pins `datasets==3.1.0`; reinstall with `-Adim paketler` |
| 3 | fastcluster: `_ARRAY_API not found` / numpy ABI error | fastcluster 1.2.6 wheels were built against numpy 1.x; the lock uses numpy 2.4.6 | the lock pins `fastcluster==1.3.0`; do not `pip install` single packages into `.venv` without the lock |
| 4 | uv cannot resolve a package (for example `filelock`) from the lock | the lock lists two indexes (PyPI + PyTorch) and uv stops at the first index that has the name | `kur.ps1` passes `--index-strategy unsafe-best-match`; hashes stay mandatory, so this is safe. Use the same flag for manual `uv pip install -r requirements\...` |
| 5 | Garbled Turkish text or parser errors when running `kur.ps1` | Windows PowerShell 5.1 reads UTF-8 without BOM as ANSI | the script is saved as UTF-8 with BOM; run it with `-File` as shown, do not paste it into a console, and keep the BOM when editing |
| 6 | `torch denetimi başarısız` or `GPU profili kuruldu ama torch CUDA'sız` | a CPU PyTorch wheel was installed into the GPU profile (for example by a plain `pip install torch`) | re-run `-Adim paketler,kontrol`; never install PyTorch without the CUDA index |
| 7 | `no kernel image is available for execution on the device` / `sm_61 is not compatible` | the PyTorch build has no kernels for the GPU architecture: CUDA 13 builds dropped Pascal; Linux cu128 wheels lack sm_61 | Windows: the locked `cu128` build (tested on Pascal); Linux: `cu126`. Check with `torch.cuda.get_arch_list()` and `torch.cuda.get_device_capability(0)`; the `CUDA Version` shown by `nvidia-smi` is the driver's maximum, not the card's |
| 8 | Video encoding: `Driver does not support the required nvenc API version` / NVENC unavailable | the driver's NVENC API is older than the one FFmpeg 9.0.2 requests, or the GPU has no NVENC | automatic: one trial encode, then libx264 with the reason in the log. Force with `DUBLAJ_VIDEO_KODLAYICI=x264` (or `nvenc`, `auto`); updating the driver re-enables NVENC |
| 9 | `Requested float16 compute type, but the target device or backend do not support efficient float16 computation` | Pascal has no fast fp16; CTranslate2 offers `float32`, `int8`, `int8_float32` there | leave `transkripsiyon.hesap_tipi = auto` (int8 / fp32 are chosen); do not force `float16` |
| 10 | `sha256 tutmadı` (hash mismatch) during download | interrupted download, proxy rewriting, or the remote file changed | re-run the same step (the partial file is deleted); if it persists the pinned source changed: report it, never edit the hash |
| 11 | `Kardeş repo adresi ayarlı değil` | URL placeholder of a sister repository is not filled | set `DUBLAJ_TTS_REPO_URL` or `DUBLAJ_STT_REPO_URL` (README "Family") |
| 12 | `crisper`: `wsl.exe yok`, or the WSL environment fails on numpy / Python version | WSL2 is missing, or the distribution's Python is older than 3.12 | `wsl --install -d Ubuntu` (Ubuntu 24.04); pass another distribution with `scripts/crisper_kur.py --dagitim <name>` |
| 13 | `voxcpm2`: `64-bit Python 3.10+ bulunamadı` | the repository's own Python is missing (the step puts it on `PATH` itself) | `scripts\kur.ps1 -Adim uv,python,voxcpm2` |
| 14 | `Önce taban kurulum: -Adim paketler` | an optional step was run before the main environment exists | run the default install first |
| 15 | `running scripts is disabled on this system` | the execution policy blocks `.ps1` files | use `kur.cmd` or the `-ExecutionPolicy Bypass -File` form (process-only) |

More run-time symptoms: `.claude/skills/sorun-giderme/SKILL.md`, [engineering/low_vram.md](engineering/low_vram.md).

## 13. Related files

`scripts/kur.ps1` (installer) · `kur.cmd` · `scripts/modelleri_indir.py` + `scripts/modeller.json` (models) ·
`scripts/crisper_kur.py` · `scripts/kilitle.ps1` (lock generation) · `requirements/` (`temel.in`, `gpu.*`, `cpu.*`,
`ek_*`, `xtts_venv*`) · `pyproject.toml` (extras per stage) · `.env.example` · [donanim.md](donanim.md) ·
[mimari.md](mimari.md) · [../THIRD_PARTY.md](../THIRD_PARTY.md)
