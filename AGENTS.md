# AGENTS.md — step-by-step install for an AI coding agent

Every step has a command, the expected marker and a check. Do not skip a check. `CLAUDE.md` points here. Türkçe: [AGENTS.tr.md](AGENTS.tr.md).

**Who you are installing for.** Most users of this repository are not developers. They pasted one sentence into
their assistant (README "Let your AI assistant install it"). Do the whole install yourself, in this order, without
asking technical questions: detect the hardware, pick the profile, read the errors and fix them from the documents
named below. Talk to the user in plain words, in their language. The only thing you ask is the voice license
question in step 4; you tell (not ask) when the disk is too small or the system is not Windows.

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
| Disk space | `[math]::Floor((Get-PSDrive C).Free / 1GB)` (the drive you install to) | ≥ 22 with an NVIDIA GPU, ≥ 14 without | tell the user how many GB to free, or install on another drive |
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

## 2. Install (one command)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1
```

- Do **not** use `kur.cmd` yourself: it waits for a key press at the end (it is the double-click launcher for people).
- No arguments: the script detects the NVIDIA GPU itself (`nvidia-smi`), installs the GPU or the CPU profile and
  writes the choice to `.venv\dublaj_profil.txt`. `-ExecutionPolicy Bypass` affects this process only.
- A first install downloads ≈ 13 GB (GPU profile) or ≈ 9.5 GB (CPU only); a measured clean install took ≈ 14 min for the GPU packages and ≈ 38 min end to end for the CPU profile (slow model download), so plan for up to an hour. If your command
  tool has a time limit, start it hidden in the background and read the log:

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
to `docs/installation.md` section 12, rows 6–7. `dubla kontrol --json` gives the same data for scripts.

## 4. First dub (smoke test) and the one question

The default voice (Supertonic 3) has use conditions (OpenRAIL-M: no impersonation, no deceptive or unlawful use,
disclose that the audio is machine-made). Ask the user, in their language, whether they accept them. This is the
only question. If they say no, stop: the other voices need an NVIDIA GPU or are non-commercial (`docs/sesler.md`).

With a yes, make a short sample video (English speech over a test picture) and dub it into Turkish, offline:

```powershell
.venv\Scripts\dubla.exe seslendir "Hello and welcome. This short video checks that the dubbing pipeline works on this computer. Thank you for watching." --dil en --ses M1 -o cikti\ornek --lisans-onay
runtime_assets\ffmpeg\bin\ffmpeg.exe -hide_banner -loglevel error -y -f lavfi -i "testsrc2=size=1280x720:rate=25" -i cikti\ornek\speech.wav -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac cikti\ornek\ornek.mp4
.venv\Scripts\dubla.exe cikti\ornek\ornek.mp4 --ayar ceviri.arka_uc=yerel --lisans-onay
```

`--lisans-onay` records the user's answer once in `ayarlar/lisans_onaylari.json`; the desktop app reads the same
record and does not ask again. `ceviri.arka_uc=yerel` keeps the test offline and account-free. Done when the last
command exits with 0 and prints a `dubbed_video:` line whose file exists. Exit code 2 = a license or setting problem
(the message says which), 1 = the job failed (`.venv\Scripts\dubla.exe sorunlu` shows why;
`.claude/skills/sorun-giderme/SKILL.md`).

**The install is finished** when step 3 says `READY` and step 4 produced the video. Then:

1. Open the desktop app for the user: `Start-Process .venv\Scripts\dubla-gui.exe` (next time they double-click
   `arayuz.cmd`).
2. Tell them in plain words: where it is installed, GPU or CPU, how to start it (`arayuz.cmd`), where results go
   (the `cikti` folder) and that `docs/getting-started.md` (Turkish: `docs/baslarken.md`) explains the rest.
3. Translation: the default `ceviri.arka_uc = auto` uses the Codex CLI or the Claude Code CLI when one of them is
   installed and logged in (the text then goes to that service, PRIVACY.md); otherwise the built-in offline
   translator, which only does English to Turkish. Say this in one sentence; do not change the setting silently.
4. Optional, only if the user wants finished videos on their phone: the Telegram bot
   (`.claude/skills/telegram-botu-kurulumu/SKILL.md`), then large-file delivery up to 2000 MB with the local Bot API
   server (`.claude/skills/telegram-buyuk-dosya/SKILL.md`: the user only fetches `api_id` / `api_hash` from
   my.telegram.org into `.env`; you run `scripts\kur.ps1 -Adim telegram-sunucu` and check `dubla kontrol`).

## 5. Troubleshooting map

| Symptom | Where the fix is |
|---|---|
| `KURULUM DURDU` with `sha256 tutmadı`, `paket kurulumu başarısız`, `model indirme başarısız` or `Python kurulamadı` | network: re-run step 2; then `docs/installation.md` section 12, rows 4 and 10 |
| `running scripts is disabled on this system` | use the exact `-ExecutionPolicy Bypass -File` command of step 2 (row 15) |
| garbled Turkish text or a parser error in `kur.ps1` | run it with `-File`, never paste it into a console (row 5) |
| `torch denetimi başarısız`, `GPU profili kuruldu ama torch CUDA'sız` | `scripts\kur.ps1 -Adim paketler,kontrol` (row 6) |
| `no kernel image is available`, or the GPU note in `dubla kontrol` | row 7, `docs/engineering/low_vram.md` |
| `EKSİK / MISSING` in `dubla kontrol` | re-run step 2 |
| `lisans onayı yok` (exit code 2) | step 4: ask the user; never pass `--lisans-onay` without their yes |
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

How to re-measure (`docs/olcumler.md`), how to bump a pin, how to cut a release.

## 7. Engineering knowledge (read before changing a stage)

- `docs/engineering/README.md`: per-stage history (problem → root cause → tried → fix → measurement → open), Türkçe
  `docs/muhendislik/README.md`.
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
