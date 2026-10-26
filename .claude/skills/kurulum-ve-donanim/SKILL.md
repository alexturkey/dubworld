---
name: kurulum-ve-donanim
description: "Install this dubbing pipeline on Windows (NVIDIA GPU or CPU only), pick the right hardware profile, add optional engines and verify the install with `dubla kontrol`. Use when the user says 'install', 'set up', 'kur', 'kurulum', 'I have no GPU', 'CPU only', 'which GPU do I need', 'is my GPU enough', 'install demucs / voxcpm2 / crisper', 'dubla kontrol says yok', or right after cloning the repo."
---

# Install and hardware / Kurulum ve donanım

Türkçe özet en altta. / Turkish summary at the end.

## When to use

- First run after cloning the repository.
- The user asks whether their machine can run it, or which engines fit their GPU / CPU.
- An optional engine (Demucs, VoxCPM2, CrisperWhisper, Parakeet, Telegram, XTTS ...) must be added later.
- `dubla kontrol` lists an engine as `yok` (missing) and the user wants it.

## Facts to know first

- Most users are not developers. Follow the deterministic flow in [AGENTS.md](../../../AGENTS.md) §0–§4 without
  technical questions; the only question is the default voice's license (§4). Done = `dubla kontrol` last line
  `READY` + the sample dub. Plain-language guide to hand over: [docs/getting-started.md](../../../docs/getting-started.md)
  (TR: [docs/baslarken.md](../../../docs/baslarken.md)).

- Full reference (requirements, step order, environment map, add-ons, offline, update, uninstall, 15 common errors):
  [docs/installation.md](../../../docs/installation.md) (TR: [docs/kurulum.md](../../../docs/kurulum.md)). Read
  its section 5 before installing any engine that needs its own environment.
- Everything installs **inside the repo folder** (`runtime_assets/`, `.venv/`); no system PATH, registry or global
  Python change. Every download is pinned (version / commit + sha256). Never relax a sha check.
- Python is fixed: CPython 3.11.14, installed by the script through `uv`.
- Two profiles: `requirements/gpu.txt` (CUDA torch) and `requirements/cpu.txt`. The script picks GPU when an NVIDIA
  driver is present; `-Cpu` forces the CPU profile.
- The recommended flow needs **no API key** and runs fully offline after install (`HF_HUB_OFFLINE=1` by default;
  `DUBLAJ_CEVRIMICI=1` allows run-time downloads).
- Reference hardware for every measured number: a 4 GB VRAM Pascal-class GPU (no fast fp16) plus its host CPU.

## Steps

1. **Prerequisites:** Windows 10/11 x64, PowerShell 5.1+, `git` only for the optional `crisper` / `voxcpm2` steps, free disk for the models (~5.3 GB) plus the
   Python environment (size not measured; keep several GB spare). NVIDIA: a recent driver (`nvidia-smi` works). WSL2 only for CrisperWhisper Turbo.
2. **Base install** (from the repo root):
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1          # auto: GPU if NVIDIA, else CPU
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Cpu     # force CPU profile
   ```
   Default steps: `uv, python, paketler, modeller, kontrol`. Each step prints a marker
   (`MODELLER_OK`, `KONTROL_OK`, final `KURULUM_OK`). The script is re-runnable: correct files are skipped.
   Windows shortcut: `kur.cmd` in the repo root.
3. **Verify:**
   ```powershell
   .venv\Scripts\dubla.exe kontrol            # hardware, ffmpeg, every engine: var (installed) / yok (missing)
   .venv\Scripts\dubla.exe kontrol --json     # machine-readable
   ```
   The `kontrol` step of `kur.ps1` also runs a real 64×64 CUDA matmul; `torch.cuda.is_available()` alone is not
   trusted (some torch builds report True without kernels for older GPUs).
4. **Optional engines** (add any time, comma separated):
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim demucs,youtube
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim voxcpm2
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim crisper -TicariOlmayanKabul
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim tts-xtts -TicariOlmayanKabul
   ```
   Valid optional steps: `demucs`, `youtube`, `parakeet`, `crisper`, `voxcpm2`, `akilli-kare`,
   `galeri`, `telegram`, `tts-xtts`. `crisper` and `tts-xtts` carry **non-commercial** weights and refuse to run
   without `-TicariOlmayanKabul`; tell the user before passing it. `voxcpm2` and `crisper` clone a sister repository
   at a fixed commit (URLs built in; for a fork set `DUBLAJ_TTS_REPO_URL` / `DUBLAJ_STT_REPO_URL`).
5. **Pick engines that fit the hardware** with [docs/donanim.md](../../../docs/donanim.md):
   - No NVIDIA GPU: `--ayar genel.cihaz=cpu` (or leave `auto`). STT `faster-whisper` int8, TTS `supertonic`,
     `ses_temizligi.kip=original`. English sources on CPU: `parakeet_cpu_align`.
   - 4 GB GPU: defaults fit. One GPU job at a time. `crisperwhisper2_medium` (~3.6 GB) and `voxcpm2` (~3 GB) need the
     card alone. Details: [docs/engineering/low_vram.md](../../../docs/engineering/low_vram.md).
   - GPU-only engines (`crisperwhisper_*`, `voxcpm2`) stop with a clear error on a CPU machine; they are never swapped
     silently.
6. **Interfaces:** `.venv\Scripts\dubla-gui.exe` (the web UI in its own app window, no console) and `.venv\Scripts\dubla-web.exe`
   (local web UI on 127.0.0.1 only; `--port 7861 --tarayici-acma`). Shortcuts: `arayuz.cmd`, `web.cmd`.

## Common errors

| Symptom | Fix |
|---|---|
| `torch denetimi başarısız` / `GPU profili kuruldu ama torch CUDA'sız` | a CPU torch wheel landed in the GPU profile; rerun `-Adim paketler`; never `pip install torch` without the index |
| `no kernel image is available for execution on the device` | torch build lacks the GPU's architecture; see [low_vram.md](../../../docs/engineering/low_vram.md) §1 |
| `ffmpeg: YOK` in `dubla kontrol` | `kur.ps1 -Adim modeller` (FFmpeg is pinned inside `runtime_assets/ffmpeg/bin`) |
| `Kardeş repo adresi ayarlı değil` | set `DUBLAJ_TTS_REPO_URL` or `DUBLAJ_STT_REPO_URL` (README "Family") |
| `Önce taban kurulum: -Adim paketler` | install the base profile before an optional step |
| Script text garbled in PowerShell 5.1 | run exactly as above (`-File`), do not paste the script into a console |
| Hash mismatch | do not edit lock files; regenerate with `scripts\kilitle.ps1` (maintainers only) |

More symptoms: the `sorun-giderme` skill.

## Related

[docs/donanim.md](../../../docs/donanim.md) · [docs/engineering/low_vram.md](../../../docs/engineering/low_vram.md) ·
[docs/engineering/gpu_memory_and_isolation.md](../../../docs/engineering/gpu_memory_and_isolation.md) ·
[docs/mimari.md](../../../docs/mimari.md) (extras per stage) · [THIRD_PARTY.md](../../../THIRD_PARTY.md) ·
[AGENTS.md](../../../AGENTS.md)

## Türkçe özet

Kurulum `scripts\kur.ps1` ile repo klasörünün içine yapılır (Python 3.11.14, hash'li kilit, sabit commit + sha256
modeller). NVIDIA yoksa işlemci profili seçilir ya da `-Cpu` ile zorlanır. Doğrulama `dubla kontrol` (her motor
`var`/`yok`). İsteğe bağlı motorlar `-Adim demucs,voxcpm2,...`; ticari olmayan ağırlıklar (`crisper`, `tts-xtts`)
`-TicariOlmayanKabul` ister, kullanıcıya önce söylenir. GPU'suz makinede faster-whisper int8 + Supertonic +
`ses_temizligi.kip=original`; 4 GB GPU'da varsayılanlar sığar, aynı anda tek GPU işi. Tablo: `docs/donanim.md`. Tam kurulum belgesi ve ortam haritası:
`docs/kurulum.md` (EN: `docs/installation.md`).
