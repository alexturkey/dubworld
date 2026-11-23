# Troubleshooting: error codes

Every installer or first-run problem has a stable code `DW-E-...`. Find the code or the text you see, do the first step, and if it does not help open a **Bug report** or **Install problem** issue with the code and the last 30 lines of output (remove personal paths). The same list is in machine form in [hata_imzalari.json](hata_imzalari.json); `scripts/tani.ps1` reads it and names the code for you. Details per row: [installation.md](installation.md) section 12. Turkish: [sorun_giderme.md](sorun_giderme.md).

## What to do first

1. Run the same command again once: downloads resume and correct files are skipped.
2. Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/tani.ps1 -Log kur.log` (it only prints; nothing is sent anywhere).
3. Same error twice: stop and report it; do not try a third time.

## Codes

| Code | What you see | First step |
|---|---|---|
| `DW-E-DISK` | `GB boş yer var` | Free disk space on the drive that holds the folder (about 22 GB for the GPU profile, 14 GB for CPU only), or move the folder to a bigger drive, then run the same command again. |
| `DW-E-SHA` | `sha256 tutmadı` | Run the same step again (the partial file is deleted and fetched again). If it fails twice, the pinned source changed: report it; never edit the hash. |
| `DW-E-PAKET` | `paket kurulumu başarısız` | Usually a network interruption: run the same command again. Do not pip install single packages into .venv. |
| `DW-E-MODEL` | `model indirme başarısız` | Run the same command again: downloaded files are kept and correct files are skipped. |
| `DW-E-PYTHON` | `Python kurulamadı` | Check the internet connection and run the same command again. |
| `DW-E-TORCH` | `torch denetimi başarısız` | Run scripts/kur.ps1 -Adim paketler,kontrol. Never install PyTorch without the CUDA index. |
| `DW-E-TORCH-CPU` | `torch CUDA'sız` | A CPU PyTorch wheel was installed into the GPU profile: run scripts/kur.ps1 -Adim paketler,kontrol. |
| `DW-E-GPU-CEKIRDEK` | `no kernel image is available` | The PyTorch build has no kernels for this GPU architecture. On Windows use the locked cu128 build; update the NVIDIA driver (R570 or newer). The program still works on the CPU. |
| `DW-E-POLITIKA` | `running scripts is disabled` | Use kur.cmd, or the exact form powershell -NoProfile -ExecutionPolicy Bypass -File scripts/kur.ps1 (affects only that process). |
| `DW-E-LISANS` | `-TicariOlmayanKabul ile yeniden çalıştırın` | This step needs the human to read the licence and accept it. An AI agent never types the acceptance for the user: ask the user, then add -TicariOlmayanKabul. |
| `DW-E-LISANS-DUBLA` | `lisans onayı yok` | The licence answer is not recorded yet. Ask the user; only with their yes run the command again with --lisans-onay. Never pass it on your own. |
| `DW-E-ADIM` | `bilinmeyen adım` | The -Adim list has a step name the installer does not know (typo?). The message lists the valid names; fix the list and run -Kuru again. |
| `DW-E-ONCE-TABAN` | `Önce taban kurulum` | An optional step was run before the main environment exists: run the default install first (scripts/kur.ps1). |
| `DW-E-KARDES-ADRES` | `Kardeş repo adresi ayarlı değil` | Fix or unset DUBLAJ_TTS_REPO_URL / DUBLAJ_STT_REPO_URL (it must be an https:// address). |
| `DW-E-GIT` | `VoxCPM2 adımı git ister` | Install Git (winget install Git.Git), open a new PowerShell and run the step again. |
| `DW-E-WSL` | `wsl.exe yok` | The crisper step needs WSL2: wsl --install -d Ubuntu (Ubuntu 24.04), then run the step again. |
| `DW-E-NVENC` | `Driver does not support the required nvenc API version` | Nothing to do: the video step falls back to libx264 by itself. Updating the NVIDIA driver re-enables NVENC. |
| `DW-E-FP16` | `Requested float16 compute type` | Leave transkripsiyon.hesap_tipi = auto; Pascal GPUs have no fast fp16 and the program chooses int8 or fp32. |
| `DW-E-PKGRES` | `No module named pkg_resources` | Do not upgrade setuptools inside .venv (the lock pins 80.9.0); re-run -Adim paketler. |

A line `UYARI` / `WARNING` is information, not a failure.
