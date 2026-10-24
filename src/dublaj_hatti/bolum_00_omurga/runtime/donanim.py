"""Donanim algilama: cihaz (cuda/cpu) ve faster-whisper hesap tipi.

"auto" secildiginde gercek bir CUDA cekirdegi calistirilarak karar verilir; yalniz `torch.cuda.is_available()`
yetmez (kart surucu/mimari uyumsuzlugunda True deyip ilk cekirdekte duser).
"""

from __future__ import annotations

import os
from functools import lru_cache

CIHAZ_SECENEKLERI = ("auto", "cuda", "cpu")


class DonanimHatasi(RuntimeError):
    pass


@lru_cache(maxsize=1)
def cuda_calisiyor() -> bool:
    if os.environ.get("CUDA_VISIBLE_DEVICES", None) == "":
        return False
    try:
        import torch

        if not torch.cuda.is_available():
            return False
        probe = torch.ones((64, 64), device="cuda")
        return float((probe @ probe).sum().item()) == 64.0 * 64.0 * 64.0
    except Exception:
        return False


def cihaz_coz(secim: str = "auto") -> str:
    value = str(secim or "auto").strip().lower()
    if value not in CIHAZ_SECENEKLERI:
        raise DonanimHatasi(f"Bilinmeyen cihaz secimi: {secim!r} (auto, cuda, cpu)")
    if value == "cpu":
        return "cpu"
    if cuda_calisiyor():
        return "cuda"
    if value == "cuda":
        raise DonanimHatasi("GPU (cuda) secildi ama calisan NVIDIA CUDA bulunamadi; 'auto' ya da 'cpu' secin")
    return "cpu"


def hesap_tipi_coz(secim: str, cihaz: str) -> str:
    value = str(secim or "auto").strip().lower()
    if cihaz == "cpu":
        return value if value in ("int8", "float32") else "int8"
    if value != "auto":
        return value
    try:
        import ctranslate2

        desteklenen = set(ctranslate2.get_supported_compute_types("cuda"))
    except Exception:
        desteklenen = set()
    if "float16" in desteklenen:
        return "float16"
    if "int8" in desteklenen or "int8_float32" in desteklenen:
        return "int8"
    return "float32"


def donanim_ozeti() -> dict[str, object]:
    ozet: dict[str, object] = {"cuda": cuda_calisiyor()}
    try:
        import torch

        ozet["torch"] = torch.__version__
        if ozet["cuda"]:
            ozet["gpu"] = torch.cuda.get_device_name(0)
            ozet["mimari"] = "sm_{}{}".format(*torch.cuda.get_device_capability(0))
            ozet["vram_mb"] = int(torch.cuda.get_device_properties(0).total_memory // (1024 * 1024))
    except Exception as exc:
        ozet["torch_hata"] = str(exc)[:200]
    ozet["cihaz"] = cihaz_coz("auto")
    ozet["whisper_hesap_tipi"] = hesap_tipi_coz("auto", str(ozet["cihaz"]))
    return ozet


@lru_cache(maxsize=1)
def vram_mb() -> int:
    """Çalışan GPU'nun toplam VRAM'i (MB); CUDA yoksa 0."""
    if not cuda_calisiyor():
        return 0
    try:
        import torch

        return int(torch.cuda.get_device_properties(0).total_memory // (1024 * 1024))
    except Exception:
        return 0


def cihaz_gerekcesi(secim: str, cihaz: str) -> str:
    """`cihaz_coz` kararının kullanıcıya gösterilen gerekçesi (günlük + ekran)."""
    secim = str(secim or "auto").strip().lower()
    if secim == "cpu":
        return "cihaz=cpu (elle seçildi): bütün adımlar işlemcide; GPU'ya özel motorlar kapalı"
    if cihaz == "cuda":
        bellek = vram_mb()
        ek = f", {bellek} MB VRAM" if bellek else ""
        return f"cihaz={secim} → cuda: NVIDIA GPU deneme çekirdeğini çalıştırdı{ek}"
    neden = ("CUDA_VISIBLE_DEVICES boş" if os.environ.get("CUDA_VISIBLE_DEVICES", None) == ""
             else "çalışan NVIDIA CUDA yok (torch CUDA görmedi ya da deneme çekirdeği düştü)")
    return (f"cihaz=auto → cpu: {neden}; işlemci dostu motorlar seçilir (transkripsiyon faster-whisper int8, "
            "seslendirme Supertonic)")


def motor_etiketi(motor: object, cihaz: str, toplam_vram_mb: int) -> str:
    """Motor listesinde gösterilecek donanım etiketi; uygunsa boş. Motor gizlenmez, yalnız etiketlenir.

    `motor` bir `kayit.Motor` (cihaz, cpu, vram_mb alanları). docs/donanim.md "Arayüz etiketleri".
    """
    tur = str(getattr(motor, "cihaz", ""))
    cpu = str(getattr(motor, "cpu", ""))
    gerek = int(getattr(motor, "vram_mb", 0) or 0)
    if tur == "bulut":
        return "bulut: ağ + kendi anahtarınız"
    if cihaz != "cuda":
        if tur == "gpu" or cpu == "çalışmaz":
            return "CPU'da çalışmaz (NVIDIA GPU gerekir)"
        if cpu == "yavaş":
            return "CPU'da yavaş"
        return ""
    if gerek and toplam_vram_mb and gerek > toplam_vram_mb * 0.95:
        return f"VRAM yetmez (~{gerek} MB gerekir, {toplam_vram_mb} MB var)"
    return ""


@lru_cache(maxsize=1)
def gpu_bilgisi_hafif() -> tuple[bool, int]:
    """(NVIDIA GPU görünüyor mu, toplam VRAM MB): torch yüklemeden `nvidia-smi` ile; arayüz etiketleri için.

    Kesin karar (gerçek CUDA çekirdeği) iş başlarken `cihaz_coz` ile verilir; bu yalnız ön bilgidir.
    """
    import shutil
    import subprocess
    import sys

    if os.environ.get("CUDA_VISIBLE_DEVICES", None) == "":
        return False, 0
    smi = shutil.which("nvidia-smi")
    if not smi:
        return False, 0
    try:
        cikti = subprocess.run(
            [smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True,
            timeout=5, check=True, creationflags=0x08000000 if sys.platform == "win32" else 0,
        ).stdout
        return True, int(float(cikti.strip().splitlines()[0]))
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return False, 0
