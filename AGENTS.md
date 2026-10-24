# AGENTS.md — step-by-step install for an AI coding agent

Every step has a command, the expected marker and a check. Do not skip a check. `CLAUDE.md` points here. Türkçe: [AGENTS.tr.md](AGENTS.tr.md).

**Who you are installing for.** Most users of this repository are not developers. They pasted one sentence into
their assistant (README "Let your AI assistant install it"). Do the whole install yourself, in this order, without
asking technical questions: detect the hardware, pick the profile, read the errors and fix them from the documents
named below. Talk to the user in plain words, in their language. You ask only two things, once, in the setup
interview of step 1a: which setup they want (quick, recommended for this machine, full) and whether they accept
the license conditions of what they chose. You tell (not ask) when the disk is too small or the system is not
Windows.

Hard rules for agents in this repo:
- Never accept a license, a consent flag or a login on the user's behalf. Optional non-commercial engines
  (`crisper`, `tts-xtts`, flag `-TicariOlmayanKabul`) are installed only when the user asks for them by name.
  Model weights are never committed or served from this repository.
- Every download is pinned (commit/tag + sha256). Never relax a sha check to "make it work".
- Never `pip install` single packages into `.venv`, never edit `requirements/*.txt` or `scripts/modeller.json`,
  never run as administrator, never change the system `PATH`. Re-running `scripts\kur.ps1` is always safe.
- Do not commit local settings, outputs, virtualenvs, models or caches (`.gitignore`).
- At most 3 attempts per step. After the third failure stop, show the user the last 30 lines of output and the
  matching row of `docs/installation.md` section 12.

## 0. Prerequisites (check them yourself)

Run in PowerShell. Nothing here is a question for the user.

| Need | Check | Expected | If not |
|---|---|---|---|
| Windows 10/11, 64-bit | `[Environment]::Is64BitOperatingSystem; (Get-CimInstance Win32_OperatingSystem).Caption` | `True` and a Windows 10 or 11 name | Linux / macOS have no installer and are not tested: tell the user; follow `docs/installation.md` section 11 only if they still want to try |
| Disk space | `[math]::Floor((Get-Item .).PSDrive.Free / 1GB)` run in the install folder (for a new folder: its parent, for example `C:\`) | ≥ 22 with an NVIDIA GPU, ≥ 14 without (the same thresholds `kur.ps1` warns at) | tell the user how many GB to free, or install on another drive |
| Hardware profile | `nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader` | one line = GPU profile; an error = CPU profile | nothing to do: `kur.ps1` makes the same decision. Never ask the user which profile |
| Internet | `Test-NetConnection huggingface.co -Port 443 -InformationLevel Quiet` | `True` | needed only during install; ask the user to connect |
| git | `git --version` | a version | not needed: use the ZIP route in step 1 |

## 1. Get the code

Install folder: a short path without spaces or non-ASCII letters, for example `C:\dublaj`. If you are already
inside a copy of this repository, use it.

```powershell
git clone https://github.com/alexturkey/DubWorld.git C:\dublaj
# without git:
Invoke-WebRequest https://github.com/alexturkey/DubWorld/archive/HEAD.zip -OutFile $env:TEMP\dublaj.zip
Expand-Archive $env:TEMP\dublaj.zip $env:TEMP\dublaj_zip -Force
Move-Item (Get-ChildItem $env:TEMP\dublaj_zip -Directory)[0].FullName C:\dublaj
```

Check: `Test-Path C:\dublaj\scripts\kur.ps1` gives `True`. All further commands run in the repository folder.

## 1a. Setup interview (ask once, in plain words)

Before step 2, tell the user what you measured in step 0 (GPU and its memory, CPU cores, RAM, free disk on the install
drive) in one or two sentences, then ask: **"What kind of setup do you want?"** Offer the three ready-made setups
below and name the one you recommend for this machine. Explain any part the user asks about with the options table:
what it does, the disk and time it costs and its license class. Never ask about GPU or CPU profile: the hardware
decides that.

Extra measurements for the recommendation (nothing to ask):

```powershell
(Get-CimInstance Win32_Processor | Measure-Object NumberOfCores -Sum).Sum           # CPU cores
[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)      # RAM, GB
(Get-PhysicalDisk | Select-Object FriendlyName, MediaType)                            # SSD or HDD
```

License classes: **commercial OK** (permissive license), **attribution** (allowed, the author must be credited),
**conditions** (use conditions to accept, for example no impersonation), **NC** (non-commercial only),
**service terms** (a cloud service: the data leaves the computer, the user's own account and key).

| Part | What it does | `-Adim` step | Disk | Time | License |
|---|---|---|---|---|---|
| Base (always) | speech-to-text (faster-whisper large-v3-turbo + CTC word times en, tr), offline English→Turkish translation (Opus-MT), the default voice Supertonic 3, speaker and gender detection, FFmpeg | default steps | start with 22 GB free (GPU) / 14 GB (CPU); measured use ≈ 14.6 GB (GPU) | ≈ 44 min GPU, ≈ 38 min CPU, measured | Supertonic: **conditions** (OpenRAIL-M); Opus-MT and the tr CTC model: **attribution** (CC BY 4.0); the rest commercial OK |
| Voice cleanup | separates speech from music and noise before transcription | `demucs` | ≈ 84 MB weight | no record | commercial OK (MIT) |
| EMA Lightning voice | second voice, Turkish only, one synthetic speaker, GPU or CPU | `tts-ema` | ≈ 0.12 GB | no record | commercial OK (Apache-2.0) |
| VoxCPM2 voice | multilingual voice with voice design and cloning; NVIDIA GPU, needs git | `voxcpm2` | ≈ 3.7 GB download | no record | commercial OK (Apache-2.0) |
| XTTS v2 voice | multilingual voice cloning, separate environment | `tts-xtts` + `-TicariOlmayanKabul` | 3–8 GB (estimate, not measured) | no record | **NC** (CPML) |
| Extra source languages ja, zh | word times for Japanese and Chinese sources | `hizalama-diller` | ≈ 2.5 GB | no record | commercial OK (Apache-2.0) |
| Source languages fr, de, es, it | word-time models downloaded on first use (`DUBLAJ_CEVRIMICI=1` once) | none | per language | no record | **NC** (CC BY-NC 4.0) |
| Parakeet | English speech-to-text on the CPU | `parakeet` | ≈ 0.7 GB | no record | **conditions** (NVIDIA Open Model License) |
| CrisperWhisper Turbo | verbatim speech-to-text; WSL2 + NVIDIA, needs git | `crisper` + `-TicariOlmayanKabul` | ≈ 7 GB | no record | **NC** |
| Speechmatics / ElevenLabs | cloud speech-to-text with the user's own key | `speechmatics` (ElevenLabs needs no step) | small | no record | **service terms** |
| Codex / Claude Code / API translation | better translation and other language pairs | none (`ceviri.arka_uc = auto` uses an installed, logged-in CLI) | none | none | **service terms** |
| Smart frame | crops black bars from the video | `akilli-kare` | small | no record | commercial OK (Apache-2.0) |
| Link download | downloads a video from a link (only content the user has rights to) | `youtube` | small | no record | yt-dlp Unlicense + the site's terms |
| Telegram bot | remote control and delivery to the phone (cloud limit 50 MB) | `telegram` | small | no record | commercial OK (LGPL-3.0, library unmodified) |
| Telegram up to 2 GB | local Bot API server; needs `api_id` / `api_hash` from my.telegram.org | `telegram-sunucu` | Docker image or a local build | a few minutes with Docker, 10–30 min building without (per the recipe) | commercial OK (BSL-1.0) |

Sizes and licenses: [docs/installation.md](docs/installation.md) section 1, [THIRD_PARTY.md](THIRD_PARTY.md),
`src/dublaj_hatti/kayit.py`. "No record" means the time was not measured.

The three setups (one command each; steps run in the script's fixed order):

| Setup | Contents | Command |
|---|---|---|
| Quick (minimum) | base only | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1` |
| Recommended, no NVIDIA GPU | base + EMA Lightning (CPU) | `... scripts\kur.ps1 -Adim uv,python,paketler,modeller,tts-ema,kontrol` |
| Recommended, NVIDIA 4–5 GB | base + voice cleanup + EMA Lightning (VoxCPM2 fits in 4 GB too, measured in the [sister repository](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi/blob/main/docs/4gb.md); add it if the user wants a second multilingual voice) | `... scripts\kur.ps1 -Adim uv,python,paketler,modeller,demucs,tts-ema,kontrol` |
| Recommended, NVIDIA 6 GB or more | base + voice cleanup + EMA Lightning + VoxCPM2 | `... scripts\kur.ps1 -Adim uv,python,paketler,modeller,demucs,tts-ema,voxcpm2,kontrol` |
| Full | recommended + `hizalama-diller,parakeet,akilli-kare,youtube,telegram`; the NC parts (`crisper`, `tts-xtts`) only after the user says yes to "non-commercial use only" | `... scripts\kur.ps1 -Adim uv,python,paketler,modeller,demucs,tts-ema,hizalama-diller,parakeet,akilli-kare,youtube,telegram,kontrol` (+ `,crisper,tts-xtts -TicariOlmayanKabul`) |

The recommended setups contain no NC part and no cloud service. Cloud services and `telegram-sunucu` are added only
when the user asks for them (they need the user's own accounts).

**Record the choice and the license answer** (once, before step 2):

1. The setup: create `ayarlar\kullanici.toml` if it does not exist and put the choice at the top as comment lines
   (the settings loader rejects unknown keys, so the record is a comment), for example
   `# kurulum: onerilen (NVIDIA 4 GB) · -Adim uv,python,paketler,modeller,demucs,tts-ema,kontrol · 2026-10-25`.
   Add real settings only for what the user chose, for example `[ses]` / `ema_cihaz = "cpu"` (step 4 item 5).
2. The license answer: the default voice Supertonic has use conditions (OpenRAIL-M: no impersonation, no deceptive
   or unlawful use, disclose that the audio is machine-made). Ask once whether the user accepts them, together with
   the conditions of any other chosen part of class **conditions** (Parakeet). Only after a clear yes, record it
   through the program's single license gate, after step 2 (it needs `.venv`):

   ```powershell
   .venv\Scripts\python.exe -c "from dublaj_hatti.lisans_onayi import kapi_adlar; print(kapi_adlar(['supertonic'], onay=True))"
   ```

   Add `'parakeet_cpu_align'` to the list when Parakeet was chosen and accepted. The record lands in
   `ayarlar/lisans_onaylari.json`; the command line and the desktop app read it and do not ask again. NC parts
   are accepted by passing `-TicariOlmayanKabul` to `kur.ps1` only after the user's yes; XTTS also asks for its own
   consent at first use (`ses.xtts_lisans_onayi`).
3. If the user says no to the Supertonic conditions: install the setup anyway, record nothing, and say that the
   default voice cannot be used; EMA Lightning (Turkish, commercial OK) or VoxCPM2 (NVIDIA GPU) can be chosen instead
   (`docs/sesler.md`).

Hardware tiers (what changes with the machine; every cell with its evidence: [docs/donanim.md](docs/donanim.md)):

| Machine | Speech-to-text | Voice | Parallel work |
|---|---|---|---|
| No NVIDIA GPU | CPU, `int8` (code: CPU resolves to int8) | Supertonic (CPU); EMA Lightning with `ses.ema_cihaz = cpu` | no GPU lock; the CPU-heavy lock allows 2 jobs |
| NVIDIA 4 GB (Pascal sm_61, measured) | GPU; `auto` resolves to `int8` on this card (measured); WhisperX batch 1 | Supertonic; EMA Lightning `auto`; VoxCPM2 fits (sister repository) | 1 GPU job at a time (lock capacity 1) |
| NVIDIA 6 GB or more | GPU; `auto` gives `float16` only where the card reports it (Volta and newer), Pascal stays `int8` | all voices | still 1 GPU job; larger batches: no record |

The 4 GB choices are what the code does on a small card, not a rule for bigger ones.

## 2. Install (one command)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1
```

This is the quick setup. For the setup chosen in step 1a, add its `-Adim` list from the table there.

- Do **not** use `kur.cmd` yourself: it waits for a key press at the end (it is the double-click launcher for people).
- Without `-Cpu` the script detects the NVIDIA GPU itself (`nvidia-smi`), installs the GPU or the CPU profile and
  writes the choice to `.venv\dublaj_profil.txt`. `-ExecutionPolicy Bypass` affects this process only.
- A first install downloads ≈ 13 GB (GPU profile) or ≈ 9.5 GB (CPU only). Measured clean installs of the quick setup:
  GPU profile ≈ 44 min end to end (packages 13.7 min, the rest is the model download at ≈ 1 MB/s), CPU profile
  ≈ 38 min; add-ons add their own download. Plan for up to an hour. If your command tool has a time limit, start it
  hidden in the background and read the log (add the `-Adim` list of the chosen setup to `-ArgumentList`):

  ```powershell
  Start-Process powershell -WindowStyle Hidden -RedirectStandardOutput kur.log -RedirectStandardError kur.err.log -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','scripts\kur.ps1'
  Select-String -Path kur.log -Encoding UTF8 -Pattern 'KURULUM_OK|KURULUM DURDU' | Select-Object -Last 1   # repeat every few minutes
  ```

Marker lines, in order (each one proves its step):

| Step | Does | Marker | Check |
|---|---|---|---|
| `uv` | pinned uv 0.13.5 into `runtime_assets\araclar\uv` | `UV_OK` | – |
| `python` | CPython 3.11.14 into `runtime_assets\python` | `PYTHON_OK` | – |
| `paketler` | `.venv` + hash-locked `requirements\gpu.txt` or `cpu.txt` + this package | `PAKETLER_OK` | `Get-Content .venv\dublaj_profil.txt` |
| `modeller` | models + FFmpeg, every file sha256-checked (`scripts\modeller.json`) | `MODELLER_OK` | – |
| `kontrol` | real CUDA kernel (GPU profile) + `dubla kontrol` | `KONTROL_OK` | step 3 |
| end | – | `KURULUM_OK` | – |

On failure the script prints `KURULUM DURDU / INSTALL STOPPED: <message>` and exits with code 1. Re-run the same
command once (downloads resume, correct files are skipped). If it stops again, find the message in
`docs/installation.md` section 12 and apply that row's fix. A line `UYARI` / `WARNING` is information, not a failure.

## 3. Verify

```powershell
.venv\Scripts\dubla.exe kontrol
```

Done when the last line is `SONUÇ / RESULT: Önerilen akış HAZIR / recommended flow READY` (match the word `READY`).
If it says `EKSİK / MISSING: <parts>`, re-run step 2. A line `not / note: ...` about the GPU means the GPU profile is
installed but the GPU cannot run (usually an old driver): the program still works on the CPU; tell the user and point
to `docs/installation.md` section 12, rows 6–7. `dubla kontrol --json` gives the same data for scripts. The first
run after an install can take a few minutes because the libraries are read from disk cold; later runs are faster.

## 4. First dub (smoke test)

The license question was asked once in step 1a and recorded with `kapi_adlar` after step 2; do not ask it again.
If the user said no to the Supertonic conditions, skip this step (the sample uses Supertonic) and say so; step 3
already proved the install.

With a yes, make a short sample video (English speech over a test picture) and dub it into Turkish, offline:

```powershell
.venv\Scripts\dubla.exe seslendir "Hello and welcome. This short video checks that the dubbing pipeline works on this computer. Thank you for watching." --dil en --ses M1 -o cikti\ornek --lisans-onay
runtime_assets\ffmpeg\bin\ffmpeg.exe -hide_banner -loglevel error -y -f lavfi -i "testsrc2=size=1280x720:rate=25" -i cikti\ornek\speech.wav -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac cikti\ornek\ornek.mp4
.venv\Scripts\dubla.exe cikti\ornek\ornek.mp4 --ayar ceviri.arka_uc=yerel --lisans-onay
```

`--lisans-onay` only repeats the recorded yes (`ayarlar/lisans_onaylari.json`); never pass it without that yes. The
desktop app reads the same record and does not ask again. `ceviri.arka_uc=yerel` keeps the test offline and account-free. Done when the last
command exits with 0 and prints a `dubbed_video:` line whose file exists. Exit code 2 = a license or setting problem
(the message says which), 1 = the job failed (`.venv\Scripts\dubla.exe sorunlu` shows why;
`.claude/skills/sorun-giderme/SKILL.md`).
The dubbed video can be longer than the sample: each line is sped up at most 1.25× and the picture is retimed
for the rest (acceptance test: 7.38 s source, 9.27 s dub, +25.6 %, `Sure Farki` line in the job log). This is expected.

**The install is finished** when step 3 says `READY` and step 4 produced the video. Then:

1. Open the desktop app for the user: `Start-Process .venv\Scripts\dubla-gui.exe` (next time they double-click
   `arayuz.cmd`). Known limit: in the acceptance test the app did not close within 4 s on a window close message
   (WM_CLOSE; cause not measured). If you opened it only for a check and must close it, end its process tree
   (`taskkill /PID <pid> /T`) instead of waiting.
2. Tell them in plain words: where it is installed, GPU or CPU, how to start it (`arayuz.cmd`), where results go
   (the `cikti` folder) and that `docs/getting-started.md` (Turkish: `docs/baslarken.md`) explains the rest.
3. Translation: the default `ceviri.arka_uc = auto` uses the Codex CLI or the Claude Code CLI when one of them is
   installed and logged in (the text then goes to that service, PRIVACY.md); otherwise the built-in offline
   translator, which only does English to Turkish. Say this in one sentence; do not change the setting silently.
4. Optional, only if the user wants finished videos on their phone: the Telegram bot
   (`.claude/skills/telegram-botu-kurulumu/SKILL.md`), then large-file delivery up to 2000 MB with the local Bot API
   server (`.claude/skills/telegram-buyuk-dosya/SKILL.md`: the user only fetches `api_id` / `api_hash` from
   my.telegram.org into `.env`; you run `scripts\kur.ps1 -Adim telegram-sunucu` and check `dubla kontrol`).

5. Optional, only if the user wants a Turkish-only alternative voice: EMA Lightning (one synthetic voice,
   Apache-2.0, `docs/motorlar/ema_lightning.md`). Run `scripts\kur.ps1 -Adim tts-ema` on either profile; the step
   installs the package from the hashed lock, downloads the pinned weights and exports the CPU ONNX files locally
   (`TTS_EMA_OK`). Pick the device from the hardware you already checked, do not ask: NVIDIA GPU with at least 1 GB
   free memory → keep `ses.ema_cihaz = auto` (it uses the GPU and falls back to the CPU when the GPU is busy); no
   NVIDIA GPU or CPU profile → `ses.ema_cihaz = cpu` (ONNX). `dubla kontrol` shows `tts ema_lightning` and what `auto`
   would pick right now. It reads Turkish only; for other target languages keep Supertonic.

## 5. Troubleshooting map

| Symptom | Where the fix is |
|---|---|
| `KURULUM DURDU` with `sha256 tutmadı`, `paket kurulumu başarısız`, `model indirme başarısız` or `Python kurulamadı` | network: re-run step 2; then `docs/installation.md` section 12, rows 4 and 10 |
| `running scripts is disabled on this system` | use the exact `-ExecutionPolicy Bypass -File` command of step 2 (row 15) |
| garbled Turkish text or a parser error in `kur.ps1` | run it with `-File`, never paste it into a console (row 5) |
| `torch denetimi başarısız`, `GPU profili kuruldu ama torch CUDA'sız` | `scripts\kur.ps1 -Adim paketler,kontrol` (row 6) |
| `no kernel image is available`, or the GPU note in `dubla kontrol` | row 7, `docs/engineering/low_vram.md` |
| `EKSİK / MISSING` in `dubla kontrol` | re-run step 2 |
| `lisans onayı yok` (exit code 2) | step 1a: the answer is not recorded; ask the user; never pass `--lisans-onay` without their yes |
| a dub job fails or stops | `.venv\Scripts\dubla.exe sorunlu`, then `.venv\Scripts\dubla.exe devam <id>`; `.claude/skills/sorun-giderme/SKILL.md` |
| out of memory on a 4 GB GPU | `docs/engineering/low_vram.md` |

## 5a. Layout

```
kur.cmd, arayuz.cmd, web.cmd    double-click launchers: install, desktop app, local web app
scripts\kur.ps1                 installer (steps above); scripts\modeller.json = pinned models
.venv\                          main Python environment (created by the installer)
runtime_assets\                 Python, uv, models, FFmpeg, optional engines (created by the installer)
cikti\                          outputs and the job database (default output folder)
ayarlar\                        personal settings (kullanici.toml) and license records; not in git
src\dublaj_hatti\               the package (commands dubla, dubla-gui, dubla-web)
docs\                           getting-started / baslarken (users), installation / kurulum (full reference)
```

## 6. Maintainer notes

- **Re-measure.** Every number in the documents comes from [docs/olcumler.md](docs/olcumler.md): it names the machine
  class, the method (for example disk size counted with hard links once, `du`) and the date. Re-run the same
  procedure on a clean folder and update that page first, then the pages that quote it.
- **Refresh a package lock.** Edit only the `requirements/*.in` source, then run `scripts\kilitle.ps1` (it rebuilds
  the hashed `*.txt` locks with the pinned uv; `-Yukselt` allows newer versions, `-YalnizXtts` rebuilds only the XTTS
  locks). Commit the `.in` and the `.txt` together. Never hand-edit a `.txt` lock.
- **Change a model pin.** Edit the entry in `scripts/modeller.json` (URL with commit or tag, size, sha256), then check
  it with `python scripts/modelleri_indir.py --liste` and download it once with
  `python scripts/modelleri_indir.py --adim <step>`. Code-side pins (`VOXCPM2_COMMIT` in
  `voxcpm2_tts/ayarlar.py`, `$VOX_COMMIT` / `$STT_COMMIT` in `scripts/kur.ps1`) change together with their pages.
  Run `pytest` (it includes `tests/test_sabit_degerler.py` and `tests/test_kurulum_kilitleri.py`) and, before a
  pinned value, read [docs/engineering/pinned-values.md](docs/engineering/pinned-values.md).
- **Cut a release.** Move the `## [Unreleased]` notes in `CHANGELOG.md` under a new version and date (SemVer), set
  `__version__` in `src/dublaj_hatti/__init__.py` to the same version, commit, then tag `v<version>`. Pushing the tag
  and publishing the release is the maintainer's decision; an agent never pushes on its own.

## 7. Engineering knowledge (read before changing a stage)

- `docs/engineering/README.md`: per-stage history (problem → root cause → tried → fix → measurement → open), Türkçe
  `docs/muhendislik/README.md`.
- `docs/engineering/pipeline-flow.md`: the whole flow from source to delivered video (stage → input file → output file → what changes, branches by setting, why segments are rebuilt from word times); TR `docs/muhendislik/hat_akisi.md`.
- `docs/engineering/low_vram.md`: 4 GB GPU / CPU-only settings and OOM troubleshooting.
- `docs/adr/README.md`: architecture decisions. Changing a stage's behaviour means bumping its checkpoint contract
  version (ADR 0012) and never adding a silent fallback (ADR 0009).
- Before changing a pinned value, read `docs/engineering/pinned-values.md` (TR `docs/muhendislik/sabit_degerler.md`); `tests/test_sabit_degerler.py` guards the critical ones.

## 8. Task → skill / document

Claude Code loads these skills from `.claude/skills/`; other agents (Codex, Cursor, ...) read the same `SKILL.md`
files as runbooks. Index with engine pages: `docs/beceriler/README.md`.

| Task | Skill | Documents |
|---|---|---|
| Install, GPU / CPU profile, optional engines, `dubla kontrol` | `.claude/skills/kurulum-ve-donanim/SKILL.md` | `docs/donanim.md`, `docs/engineering/low_vram.md` |
| Dub a video (recommended flow), subtitles only | `.claude/skills/dublaj-onerilen-akis/SKILL.md` | `src/dublaj_hatti/varsayilan.toml` |
| Settings, recipes, rejected combinations | `.claude/skills/gelismis-ayarlar-ve-kombinasyonlar/SKILL.md` | `docs/tarifler/kombinasyonlar.md` |
| Speech-to-text engine, language detection | `.claude/skills/stt-motorlari/SKILL.md` | `docs/tarifler/dil_tespiti.md`, `docs/motorlar/` |
| TTS engine, target language, voices, XTTS / RVC consent | `.claude/skills/tts-motorlari/SKILL.md` | `docs/diller.md`, `docs/sesler.md`, `ETHICS.md` |
| Translation backend (Codex, Claude Code, Opus-MT, API keys) | `.claude/skills/ceviri-arka-uclari/SKILL.md` | `docs/engineering/translation.md`, `.env.example` |
| Resume, failed jobs, GPU queue | `.claude/skills/devam-ve-sorunlu-isler/SKILL.md` | `docs/tarifler/devam_ve_sorunlu_isler.md` |
| Telegram bot setup | `.claude/skills/telegram-botu-kurulumu/SKILL.md` | `docs/tarifler/telegram_botu.md` |
| Telegram large files (2000 MB, local Bot API server) | `.claude/skills/telegram-buyuk-dosya/SKILL.md` | `docs/tarifler/telegram_buyuk_dosya.md` |
| Single stage, Python API, own tool | `.claude/skills/tek-asama-kullanimi-ve-api/SKILL.md` | `docs/mimari.md`, `examples/README.md` |
| Errors, OOM, ffmpeg, lock, install | `.claude/skills/sorun-giderme/SKILL.md` | `docs/engineering/README.md`, `docs/adr/README.md` |
| Contribute, add an engine, tests, legal audit | `.claude/skills/katki-ve-motor-ekleme/SKILL.md` | `CONTRIBUTING.md`, `src/dublaj_hatti/kayit.py`, `THIRD_PARTY.md` |

Never accept a license, a consent flag or a login on the user's behalf; never print or commit keys.
