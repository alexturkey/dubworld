import json
import os
import re
import shutil
import subprocess
import sys
from typing import Optional

import torch

from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import torch_home

# Neden: toplu 4, 74 dk seste -%20 sure, tepe ~1.69 GB; OOM'da bir kez toplu 1 (ADR 0002). bkz. docs/engineering/pinned-values.md#source-audio-and-separation
CUDA_BATCH_SIZE = 4
CUDA_BATCH_OVERLAP = 0.25


class DemucsPreparationError(RuntimeError):
    pass


# htdemucs ağırlığı kurulumda sabit adres + sha256 ile iner (scripts/modeller.json adım "demucs"; kur.ps1 -Adim demucs).
# Yoksa ve çalışma anı indirmesine izin verilmemişse (varsayılan çevrimdışı) iş Demucs başlamadan açık hatayla durur.
HTDEMUCS_AGIRLIK = "955717e8-8726e21a.th"
DEMUCS_KURULUM_ADIMI = "scripts/kur.ps1 -Adim demucs (yalnız model: python scripts/modelleri_indir.py --adim demucs)"


def demucs_modeli_gerekli(demucs_model_name: str = "htdemucs") -> None:
    """Raise DemucsPreparationError when the pinned htdemucs weight is missing and runtime downloads are off."""
    if demucs_model_name != "htdemucs":
        return
    agirlik = torch_home() / "hub" / "checkpoints" / HTDEMUCS_AGIRLIK
    if agirlik.is_file():
        return
    from dublaj_hatti.bolum_00_omurga.runtime.ctc_model_durumu import CEVRIMICI_DEGISKENI, cevrimici_mi

    if cevrimici_mi():
        return
    raise DemucsPreparationError(
        f"Demucs htdemucs modeli kurulu değil (beklenen yer {agirlik}). Kurulum: {DEMUCS_KURULUM_ADIMI}. "
        f"Çalışma anında denetimsiz indirme yapılmaz; bilerek indirmek için {CEVRIMICI_DEGISKENI}=1. "
        "Ayrıştırmasız çalışmak için: ses_temizligi.kip=original."
    )


def _validate_cuda_batch_report(
    batch_report: dict,
    audio_path: str,
    demucs_model_name: str,
    vocals_path: str,
) -> None:
    expected_no_vocals_path = os.path.join(os.path.dirname(vocals_path), "no_vocals.wav")
    expected_values = {
        "input": os.path.abspath(audio_path),
        "model": demucs_model_name,
        "overlap": CUDA_BATCH_OVERLAP,
        "shifts": 0,
        "requested_batch_size": CUDA_BATCH_SIZE,
    }
    for key, expected_value in expected_values.items():
        actual_value = batch_report.get(key)
        if key == "input":
            actual_value = os.path.abspath(str(actual_value))
        if actual_value != expected_value:
            raise ValueError(f"batch raporu uyusmuyor: alan={key} beklenen={expected_value} gercek={actual_value}")
    actual_batch_size = batch_report.get("actual_batch_size")
    oom_fallback = batch_report.get("oom_fallback")
    if actual_batch_size not in (1, CUDA_BATCH_SIZE):
        raise ValueError(f"gecersiz actual_batch_size: {actual_batch_size}")
    if (actual_batch_size == 1) != (oom_fallback is True):
        raise ValueError(
            f"batch ve OOM fallback uyusmuyor: batch={actual_batch_size} fallback={oom_fallback}"
        )
    outputs = batch_report.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("batch raporunda outputs yok")
    expected_outputs = {
        "vocals": os.path.abspath(vocals_path),
        "no_vocals": os.path.abspath(expected_no_vocals_path),
    }
    for key, expected_path in expected_outputs.items():
        actual_path = os.path.abspath(str(outputs.get(key)))
        if actual_path != expected_path or not os.path.isfile(expected_path):
            raise ValueError(f"batch ciktisi gecersiz: stem={key} yol={actual_path}")
    total_seconds = batch_report.get("timings", {}).get("total_seconds")
    if not isinstance(total_seconds, (int, float)) or total_seconds <= 0:
        raise ValueError(f"batch toplam suresi gecersiz: {total_seconds}")
    peak_memory_mb = batch_report.get("peak_torch_cuda_memory_mb")
    if not isinstance(peak_memory_mb, (int, float)) or peak_memory_mb <= 0:
        raise ValueError(f"batch peak VRAM gecersiz: {peak_memory_mb}")


def print_progress_bar(percent: float, width: int = 40, prefix: str = "Demucs") -> None:
    filled = int(width * percent / 100)
    bar = "#" * filled + "-" * (width - filled)
    print(f"\r{prefix}: [{bar}] {percent:5.1f}%", end="", flush=True)


def clean_audio_with_demucs(
    audio_path: str,
    run_dir: str,
    demucs_model_name: str = "htdemucs",
    prefer_device: Optional[str] = None,
    logger: Optional[object] = None,
    prepare_asr_ready: bool = True,
) -> str:
    demucs_modeli_gerekli(demucs_model_name)
    if logger:
        logger.info("Demucs ile vokal izolasyonu baslatiliyor.")
    demucs_root = os.path.join(run_dir, "demucs")
    os.makedirs(demucs_root, exist_ok=True)
    device = prefer_device
    if not device or device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    jobs = 1
    use_cuda_batch_worker = device == "cuda" and demucs_model_name == "htdemucs"
    if use_cuda_batch_worker:
        worker_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demucs_batch_worker.py")
        cmd = [
            sys.executable,
            worker_path,
            "--input",
            audio_path,
            "--output-root",
            demucs_root,
            "--model",
            demucs_model_name,
            "--batch-size",
            str(CUDA_BATCH_SIZE),
            "--overlap",
            str(CUDA_BATCH_OVERLAP),
        ]
    else:
        cmd = [
            sys.executable,
            "-m",
            "demucs.separate",
            "--two-stems=vocals",
            "-n",
            demucs_model_name,
            "--out",
            demucs_root,
            "--jobs",
            str(jobs),
            "--device",
            device,
            "--shifts",
            "0",
            audio_path,
        ]

    demucs_env = os.environ.copy()
    demucs_env["PYTHONHASHSEED"] = "0"
    demucs_env["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    demucs_env["OMP_NUM_THREADS"] = "1"
    demucs_env["MKL_NUM_THREADS"] = "1"
    demucs_env["TORCH_HOME"] = str(torch_home())
    demucs_env["PYTHONIOENCODING"] = "utf-8"

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)

    if logger:
        if use_cuda_batch_worker:
            logger.info(
                "Demucs optimized mode: cuda_batch=4, overlap=0.25, segment=model_default, shifts=0, below-normal priority=%s",
                bool(creationflags),
            )
        else:
            logger.info(
                "Demucs optimized mode: jobs=1, segment=model_default, shifts=0, below-normal priority=%s",
                bool(creationflags),
            )

    process = None
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            # Alt süreç UTF-8 yazar (PYTHONIOENCODING aşağıda); Windows yerel kod sayfası (cp1254 vb.) ilerleme
            # çubuğu karakterinde UnicodeDecodeError verip işi düşürüyordu.
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=demucs_env,
            creationflags=creationflags,
        )
        percent_pattern = re.compile(r"(\d+)%")
        last_percent = -1
        print_progress_bar(0)
        if process.stdout:
            for line in process.stdout:
                line_stripped = line.strip()
                match = percent_pattern.search(line_stripped)
                if match:
                    percent = int(match.group(1))
                    if percent != last_percent:
                        print_progress_bar(percent)
                        last_percent = percent
                elif line_stripped and logger:
                    lowered = line_stripped.lower()
                    if any(kw in lowered for kw in ("error", "exception", "traceback", "hata")):
                        logger.error("[DEMUCS] %s", line_stripped)
                    elif any(kw in lowered for kw in ("warning", "warn", "uyari")):
                        logger.warning("[DEMUCS] %s", line_stripped)
                    else:
                        logger.debug("[DEMUCS] %s", line_stripped)
        process.wait(timeout=1800)
        print_progress_bar(100)
        print()
        if process.returncode != 0:
            if logger:
                logger.error("Demucs hata dondurdu (kod=%s).", process.returncode)
            raise DemucsPreparationError(f"Demucs hata dondurdu: cikis_kodu={process.returncode}")
    except subprocess.TimeoutExpired:
        if logger:
            logger.error("Demucs timeout (30 dakika) - process sonlandiriliyor")
        if process:
            process.kill()
            process.wait()
        raise DemucsPreparationError("Demucs zaman asimina ugradi: sure=1800s")
    except FileNotFoundError as exc:
        if logger:
            logger.error("Demucs calistirilamadi (bulunamadi): %s", exc)
        raise DemucsPreparationError(f"Demucs calistirilamadi: {exc}") from exc

    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    vocals_path = os.path.join(demucs_root, demucs_model_name, base_name, "vocals.wav")
    if not os.path.exists(vocals_path):
        if logger:
            logger.error("Demucs ciktisinda vocals.wav bulunamadi: %s", vocals_path)
        raise DemucsPreparationError(f"Demucs vocals.wav uretmedi: {vocals_path}")

    if use_cuda_batch_worker:
        report_path = os.path.join(demucs_root, "demucs_batch_report.json")
        try:
            with open(report_path, "r", encoding="utf-8") as report_file:
                batch_report = json.load(report_file)
            _validate_cuda_batch_report(
                batch_report,
                audio_path,
                demucs_model_name,
                vocals_path,
            )
            if logger:
                logger.info(
                    "Demucs CUDA batch tamamlandi: requested=%s actual=%s oom_fallback=%s total=%.3fs peak_vram=%.1fMB",
                    batch_report["requested_batch_size"],
                    batch_report["actual_batch_size"],
                    batch_report["oom_fallback"],
                    batch_report["timings"]["total_seconds"],
                    batch_report["peak_torch_cuda_memory_mb"],
                )
        except (OSError, KeyError, TypeError, ValueError) as exc:
            if logger:
                logger.error("Demucs CUDA batch raporu okunamadi: %s", exc)
            raise DemucsPreparationError(f"Demucs CUDA batch raporu gecersiz: {exc}") from exc

    cleaned_path = os.path.join(run_dir, "clean_source.wav")
    if os.path.exists(cleaned_path):
        os.remove(cleaned_path)
    try:
        os.link(vocals_path, cleaned_path)
        if logger:
            logger.info("Demucs clean_source hardlink hazir: %s", cleaned_path)
    except OSError as exc:
        if logger:
            logger.warning("Demucs hardlink kullanilamadi, kopyalama yapiliyor: %s", exc)
        try:
            shutil.copy2(vocals_path, cleaned_path)
        except OSError as copy_exc:
            if logger:
                logger.error("Demucs temiz ses kopyalanamadi: %s", copy_exc)
            raise DemucsPreparationError(f"Demucs temiz sesi hazirlanamadi: {copy_exc}") from copy_exc
    if logger:
        logger.info("Demucs temizligi tamamlandi: %s", cleaned_path)

    if not prepare_asr_ready:
        if logger:
            logger.info("Demucs clean_source dogrudan ASR girdisi olarak kullanilacak: %s", cleaned_path)
        return cleaned_path

    asr_ready_path = os.path.join(run_dir, "asr_ready.wav")
    try:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            cleaned_path,
            "-ac",
            "1",
            "-ar",
            "16000",
            "-acodec",
            "pcm_s16le",
            asr_ready_path,
        ]
        subprocess.run(cmd, check=True)
        if logger:
            logger.info("Demucs ASR hazir ses olusturuldu: %s", asr_ready_path)
        return asr_ready_path
    except subprocess.CalledProcessError as exc:
        if logger:
            logger.error("Demucs ASR hazir ses olusturulamadi: %s", exc)
        raise DemucsPreparationError(f"Demucs ASR sesi hazirlanamadi: {exc}") from exc
