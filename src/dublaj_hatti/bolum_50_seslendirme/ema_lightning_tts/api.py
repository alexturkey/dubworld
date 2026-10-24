"""EMA Lightning ile segment ve tam metin seslendirme (Supertonic ile aynı sonuç sözleşmesi).

Cihaz seçimi (`ses.ema_cihaz`): auto | cuda | cpu. auto: NVIDIA GPU görünüyor ve en az EMA_GPU_BOS_MB boş bellek
varsa GPU (torch), yoksa işlemci; GPU koşusu bellek ya da CUDA hatasıyla düşerse aynı iş bir kez işlemcide tekrarlanır.
İşlemci yolu: yerelde dışa aktarılmış ONNX (onnx_aktar.py, eşitlik denetimi geçtiyse), değilse aynı ağırlıkla torch.
Model her işte ayrı süreçte bir kez yüklenir (kosucu.py); süreç bitince GPU belleği tamamen boşalır.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

from dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts.ayarlar import (
    EMA_AGIRLIK_SHA256,
    EMA_CIHAZLAR,
    EMA_ENGINE_ID,
    EMA_GPU_BOS_MB,
    EMA_HF_COMMIT,
    EMA_ONNX_DOSYALARI,
    EMA_ORNEKLEME,
    EMA_PAKET_SURUMU,
    EMA_VARSAYILAN_SES,
    agirlik_dizini,
    onnx_dizini,
)

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
CUMLE_SONU = re.compile(r"(?<=[.!?…])\s+")
CUMLE_ARASI_SN = 0.25  # tam metin ve düz metin kipinde cümleler arası sessizlik = paketin cümle sonu duraklaması
logger = logging.getLogger("dublaj_hatti")


class EMAHatasi(RuntimeError):
    pass


def _paket_var() -> bool:
    import importlib.util

    return importlib.util.find_spec("ema_lightning") is not None and importlib.util.find_spec("normalizer_tr") is not None


def _onnx_durumu() -> dict[str, Any]:
    kok = onnx_dizini()
    kayit = kok / "aktarim.json"
    dosyalar = all((kok / ad).is_file() for ad in EMA_ONNX_DOSYALARI) and (kok / "ema_meta.json").is_file()
    try:
        aktarim = json.loads(kayit.read_text(encoding="utf-8")) if kayit.is_file() else {}
    except (OSError, ValueError):
        aktarim = {}
    return {"hazir": bool(dosyalar and aktarim.get("gecti")), "kok": str(kok), "aktarim": aktarim}


def ema_durumu() -> dict[str, Any]:
    """`dubla kontrol` ve kayıt için: paket, ağırlık (boyut değil sha256 adı listesi), ONNX işlemci yolu."""
    agirlik = agirlik_dizini()
    agirlik_var = all((agirlik / ad).is_file() for ad in EMA_AGIRLIK_SHA256)
    onnx = _onnx_durumu()
    paket = _paket_var()
    return {
        "kurulu": paket and agirlik_var,
        "paket": paket,
        "paket_surumu": EMA_PAKET_SURUMU,
        "agirlik": agirlik_var,
        "agirlik_kok": str(agirlik),
        "hf_commit": EMA_HF_COMMIT,
        "onnx_cpu": onnx["hazir"],
        "onnx_kok": onnx["kok"],
        "onnx_fark": (onnx["aktarim"] or {}).get("en_buyuk_fark"),
    }


def gpu_bos_mb() -> int:
    """NVIDIA GPU'daki boş bellek (MB); GPU yoksa ya da okunamazsa -1. torch yüklemez (nvidia-smi)."""
    if os.environ.get("CUDA_VISIBLE_DEVICES", None) == "":
        return -1
    smi = shutil.which("nvidia-smi")
    if not smi:
        return -1
    try:
        cikti = subprocess.run([smi, "--query-gpu=memory.free", "--format=csv,noheader,nounits"], capture_output=True,
                               text=True, timeout=5, check=True, creationflags=NO_WINDOW).stdout
        return int(float(cikti.strip().splitlines()[0]))
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return -1


def cihaz_sec(istenen: str, genel_cihaz: str = "auto") -> tuple[str, str]:
    """(çalıştırma yolu, gerekçe). Yol: torch-cuda | onnx-cpu | torch-cpu."""
    if istenen not in EMA_CIHAZLAR:
        raise EMAHatasi(f"ses.ema_cihaz geçersiz: {istenen!r} ({', '.join(EMA_CIHAZLAR)})")
    cpu_yolu = "onnx-cpu" if _onnx_durumu()["hazir"] else "torch-cpu"
    if istenen == "cpu" or genel_cihaz == "cpu":
        return cpu_yolu, "işlemci seçildi"
    bos = gpu_bos_mb()
    if istenen == "cuda":
        if bos < 0:
            raise EMAHatasi("ses.ema_cihaz=cuda ama NVIDIA GPU bulunamadı; auto ya da cpu seçin")
        return "torch-cuda", f"GPU seçildi ({bos} MB boş)"
    if bos < 0:
        return cpu_yolu, "GPU yok: işlemci"
    if bos < EMA_GPU_BOS_MB:
        return cpu_yolu, f"GPU meşgul ({bos} MB boş < {EMA_GPU_BOS_MB} MB): işlemci"
    return "torch-cuda", f"GPU ({bos} MB boş)"


def _is_parcacigi() -> int:
    return max(1, min(8, (os.cpu_count() or 4) // 2))


def _kosucu_calistir(yol: str, parcalar: list[dict], hiz: float, tohum: int, calisma: Path) -> dict[str, Any]:
    calisma.mkdir(parents=True, exist_ok=True)
    is_dosyasi, sonuc_dosyasi = calisma / "is.json", calisma / "sonuc.json"
    sonuc_dosyasi.unlink(missing_ok=True)
    job = {"yol": yol, "agirlik": str(agirlik_dizini()), "onnx": str(onnx_dizini()), "hiz": float(hiz),
           "tohum": int(tohum), "is_parcacigi": _is_parcacigi(), "calisma": str(calisma), "parcalar": parcalar}
    is_dosyasi.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    komut = [sys.executable, "-B", str(Path(__file__).with_name("kosucu.py")), "--is", str(is_dosyasi),
             "--sonuc", str(sonuc_dosyasi)]
    ortam = dict(os.environ, PYTHONIOENCODING="utf-8")
    if yol != "torch-cuda":
        ortam["CUDA_VISIBLE_DEVICES"] = ""  # işlemci yolu GPU'ya hiç dokunmaz
    bitti = subprocess.run(komut, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=NO_WINDOW, env=ortam)
    if bitti.returncode != 0 or not sonuc_dosyasi.is_file():
        kuyruk = (bitti.stderr or bitti.stdout or "")[-1500:]
        raise EMAHatasi(f"EMA koşucusu başarısız (yol={yol}, rc={bitti.returncode}): {kuyruk}")
    return json.loads(sonuc_dosyasi.read_text(encoding="utf-8"))


def ema_oku(parcalar: list[dict], cfg_ya_da_ayar: Any, calisma: Path) -> dict[str, Any]:
    """Parçaları okur; GPU koşusu düşerse (auto) bir kez işlemcide tekrarlar. Dönüş: koşucu özeti + gerekce."""
    durum = ema_durumu()
    if not durum["kurulu"]:
        raise EMAHatasi("EMA Lightning kurulu değil. Kurulum: scripts/kur.ps1 -Adim tts-ema "
                        f"(paket: {durum['paket']}, ağırlık: {durum['agirlik']}, klasör {durum['agirlik_kok']})")
    istenen = str(_al(cfg_ya_da_ayar, "ema_cihaz", "ses.ema_cihaz", "auto"))
    genel = str(_al(cfg_ya_da_ayar, "device", "genel.cihaz", "auto"))
    hiz = float(_al(cfg_ya_da_ayar, "ema_hiz", "ses.ema_hiz", 1.0))
    tohum = int(_al(cfg_ya_da_ayar, "ema_tohum", "ses.ema_tohum", 0))
    yol, gerekce = cihaz_sec(istenen, genel)
    logger.info("[EMA] yol=%s (%s) parca=%d hiz=%.2f tohum=%d", yol, gerekce, len(parcalar), hiz, tohum)
    try:
        ozet = _kosucu_calistir(yol, parcalar, hiz, tohum, calisma)
    except EMAHatasi as hata:
        if yol != "torch-cuda" or istenen == "cuda":
            raise
        yedek = "onnx-cpu" if _onnx_durumu()["hazir"] else "torch-cpu"
        logger.warning("[EMA] GPU koşusu düştü, işlemcide tekrar (%s): %s", yedek, str(hata)[-300:])
        gerekce = f"GPU koşusu düştü, işlemci ({yedek})"
        ozet = _kosucu_calistir(yedek, parcalar, hiz, tohum, calisma)
    ozet["gerekce"] = gerekce
    logger.info("[EMA] bitti yol=%s yukleme=%.2fs okuma=%.2fs ses=%.2fs vram_tepe=%sMB", ozet.get("yol"),
                ozet.get("yukleme_sn", 0), ozet.get("sure_sn", 0), ozet.get("ses_sn", 0), ozet.get("vram_tepe_mb"))
    return ozet


def _al(kaynak: Any, cfg_adi: str, ayar_adi: str, varsayilan: Any) -> Any:
    if isinstance(kaynak, dict):
        deger = kaynak.get(ayar_adi)
    else:
        deger = getattr(kaynak, cfg_adi, None)
    return varsayilan if deger in (None, "") else deger


def _wav_oku(yol: str) -> np.ndarray:
    import soundfile as sf

    dalga, oran = sf.read(yol, dtype="float32")
    if int(oran) != EMA_ORNEKLEME:
        raise EMAHatasi(f"EMA çıktısı beklenmeyen örnekleme hızı: {oran}")
    return np.asarray(dalga, dtype=np.float32)


def cumlelere_bol(metin: str) -> list[str]:
    return [c.strip() for c in CUMLE_SONU.split(" ".join(str(metin).split())) if c.strip()]


def metni_oku(metin: str, cfg_ya_da_ayar: Any, calisma: Path) -> tuple[list[tuple[str, np.ndarray]], int]:
    """Düz metin → [(cümle, dalga)], cümle arası sessizlik örnek sayısı. Tam metin kipi ve `dubla seslendir` için."""
    cumleler = cumlelere_bol(metin)
    if not cumleler:
        raise EMAHatasi("seslendirilecek metin boş")
    ozet = ema_oku([{"index": i, "text": c} for i, c in enumerate(cumleler, 1)], cfg_ya_da_ayar, calisma)
    parcalar = [(c, _wav_oku(ozet["wavlar"][str(i)])) for i, c in enumerate(cumleler, 1)]
    return parcalar, int(round(CUMLE_ARASI_SN * EMA_ORNEKLEME))


def birlestir(parcalar: list[tuple[str, np.ndarray]], sessizlik: int) -> np.ndarray:
    dalgalar: list[np.ndarray] = []
    for i, (_, dalga) in enumerate(parcalar):
        if i:
            dalgalar.append(np.zeros(sessizlik, dtype=np.float32))
        dalgalar.append(dalga)
    return np.concatenate(dalgalar).astype(np.float32) if dalgalar else np.zeros(0, np.float32)


def synthesize_full_text_ema(text: str, cfg: Any, work_dir: str):
    """Tam metin kipi: Supertonic'in FullTextSynthesis sözleşmesiyle aynı (gerçek parça dalgaları + eşit sessizlik)."""
    from dublaj_hatti.bolum_00_omurga.full_metin_dublaji import FullTextAudioChunk, FullTextSynthesis

    parcalar, sessizlik = metni_oku(text, cfg, Path(work_dir) / "ema_tam_metin")
    ses = birlestir(parcalar, sessizlik)
    if ses.size == 0:
        raise EMAHatasi("EMA tam metin sentezi boş ses üretti")
    return FullTextSynthesis(
        audio=ses, sample_rate=EMA_ORNEKLEME, chunk_count=len(parcalar),
        actual_chunks=tuple(FullTextAudioChunk(text=c, audio=d) for c, d in parcalar),
        inter_chunk_silence_samples=sessizlik,
    )


def build_ema_dubbed_audio(segments, cfg, run_dir: str):
    """Segment kipi: her segment ayrı okunur, Supertonic ile aynı hazırlama (zaman uydurma) ve karışım."""
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.api import SupertonicDubResult, build_supertonic_audio_mix
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.execution import prepare_supertonic_result_for_segment

    ses_adi = str(getattr(cfg, "ema_ses", "") or EMA_VARSAYILAN_SES)
    parcalar = [{"index": seg.index, "text": seg.text} for seg in segments if str(seg.text or "").strip()]
    if not parcalar:
        raise EMAHatasi("EMA: okunacak segment yok")
    ozet = ema_oku(parcalar, cfg, Path(run_dir) / "ema_lightning")
    timing_infos, segment_audios, prepared = [], {}, {}
    for seg in segments:
        yol = ozet["wavlar"].get(str(seg.index))
        if yol is None:
            continue
        ham = {"wav_array": _wav_oku(yol), "sample_rate": EMA_ORNEKLEME,
               "debug": {"voice_id": ses_adi, "ema_yol": ozet.get("yol")}}
        idx, wav_array, timing_info, prepared_audio = prepare_supertonic_result_for_segment(seg, ham, cfg.sample_rate,
                                                                                          ses_adi)
        timing_info["engine"] = EMA_ENGINE_ID
        segment_audios[idx] = wav_array
        timing_infos.append(timing_info)
        prepared[idx] = prepared_audio
    eksik = [p["index"] for p in parcalar if p["index"] not in segment_audios]
    if eksik:
        raise EMAHatasi(f"EMA seslendirme eksik: {len(eksik)} segment (ilk: {eksik[:10]})")
    max_end = max((seg.end for seg in segments), default=0.0)
    mix = build_supertonic_audio_mix(prepared, max_end, cfg.sample_rate)
    return SupertonicDubResult(audio=mix, timing_infos=timing_infos, segment_audios=segment_audios,
                               prepared_audios=prepared)
