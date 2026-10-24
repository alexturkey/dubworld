"""Is the CTC alignment model for a language on disk? (stdlib only; heavy imports are lazy and optional.)

Used before the shared CTC box runs for `faster_whisper_ctc` (the `auto` fallback) and by `dubla kontrol`, so a missing
model stops the job with the install step instead of silently keeping Whisper's own word times (ADR 0009).

Pinned models (`scripts/modeller.json`, step `hizalama`; `scripts/kur.ps1 -Adim modeller`): `en`, `tr`. Optional pinned
models (step `hizalama-diller`; `scripts/kur.ps1 -Adim hizalama-diller`): `ja`, `zh`. Every other language uses the
WhisperX default model, which is not pinned; it can be fetched only on purpose with `DUBLAJ_CEVRIMICI=1` (the runtime
is offline by default, `cli.ortami_hazirla`). The WhisperX defaults for fr, de, es, it are VoxPopuli models under
CC BY-NC 4.0 (non-commercial); the message says so.
"""

from __future__ import annotations

import os
from pathlib import Path

KURULUM_ADIMI = "scripts/kur.ps1 -Adim modeller (yalnız hizalama: python scripts/modelleri_indir.py --adim hizalama)"
CEVRIMICI_DEGISKENI = "DUBLAJ_CEVRIMICI"

# dil -> (kaynak türü, ad). "torch": torchaudio checkpoint file under <torch>/hub/checkpoints;
# "hf": Hugging Face repo id under <hf>/hub. Must match scripts/modeller.json step "hizalama" (test checks).
SABIT_CTC_MODELLERI: dict[str, tuple[str, str]] = {
    "en": ("torch", "wav2vec2_fairseq_base_ls960_asr_ls960.pth"),
    "tr": ("hf", "mpoyraz/wav2vec2-xls-r-300m-cv7-turkish"),
}
# The CTC box's own override (worker.ALIGN_MODEL_BY_LANGUAGE); WhisperX's default table has no "id".
# Optional, pinned the same way (scripts/modeller.json step "hizalama-diller"; test checks). Names = WhisperX defaults.
ISTEGE_BAGLI_CTC_MODELLERI: dict[str, tuple[str, str]] = {
    "ja": ("hf", "jonatasgrosman/wav2vec2-large-xlsr-53-japanese"),
    "zh": ("hf", "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn"),
}
ISTEGE_BAGLI_KURULUM_ADIMI = (
    "scripts/kur.ps1 -Adim hizalama-diller (yalnız model: python scripts/modelleri_indir.py --adim hizalama-diller)"
)
# WhisperX default CTC models that are VoxPopuli checkpoints (torchaudio: CC BY-NC 4.0).
TICARI_OLMAYAN_VARSAYILAN_DILLER = frozenset({"fr", "de", "es", "it"})
KUTU_OZEL_MODELLER: dict[str, str] = {"id": "Galuh/wav2vec2-large-xlsr-indonesian"}
AGIRLIK_DOSYALARI = ("pytorch_model.bin", "model.safetensors")


class CtcModeliEksikHatasi(RuntimeError):
    """The CTC model for the language is not installed; the message names the install step."""


def _dil(kod: str) -> str:
    return str(kod or "").strip().lower().split("-", 1)[0].split("_", 1)[0]


def _hf_ve_torch_kokleri(cache_dir: str | Path | None) -> tuple[Path, Path]:
    """Same roots the CTC worker uses: HF hub = <cache_dir>/hub, torch = <cache_dir>/../torch."""
    if cache_dir:
        kok = Path(cache_dir).expanduser().resolve()
    else:
        from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import huggingface_home

        kok = huggingface_home()
    return kok / "hub", kok.parent / "torch"


def _varsayilan_model(dil: str) -> tuple[str, str] | None:
    """Model the CTC box would load for a language that is not pinned (lazy WhisperX/torchaudio lookup)."""
    if dil in KUTU_OZEL_MODELLER:
        return "hf", KUTU_OZEL_MODELLER[dil]
    try:
        from whisperx.alignment import DEFAULT_ALIGN_MODELS_HF, DEFAULT_ALIGN_MODELS_TORCH
    except Exception:  # whisperx missing or broken: reported by the caller as "unknown"
        return None
    if dil in DEFAULT_ALIGN_MODELS_TORCH:
        try:
            import torchaudio

            paket = getattr(torchaudio.pipelines, DEFAULT_ALIGN_MODELS_TORCH[dil])
            return "torch", Path(str(paket._path)).name
        except Exception:
            return None
    if dil in DEFAULT_ALIGN_MODELS_HF:
        return "hf", DEFAULT_ALIGN_MODELS_HF[dil]
    return None


def _var_mi(tur: str, ad: str, hf_hub: Path, torch_kok: Path) -> tuple[bool, Path]:
    if tur == "torch":
        yol = torch_kok / "hub" / "checkpoints" / ad
        return yol.is_file(), yol
    yol = hf_hub / ("models--" + ad.replace("/", "--")) / "snapshots"
    var = yol.is_dir() and any((s / f).is_file() for s in yol.iterdir() if s.is_dir() for f in AGIRLIK_DOSYALARI)
    return var, yol


def ctc_modeli_durumu(dil: str, cache_dir: str | Path | None = None) -> dict[str, object]:
    """{"dil", "model", "sabit", "kurulu" (True/False/None = unknown), "yol"} for one language."""
    kod = _dil(dil) or "en"
    sabit = kod in SABIT_CTC_MODELLERI
    istege_bagli = kod in ISTEGE_BAGLI_CTC_MODELLERI
    secim = SABIT_CTC_MODELLERI.get(kod) or ISTEGE_BAGLI_CTC_MODELLERI.get(kod) or _varsayilan_model(kod)
    if secim is None:
        return {"dil": kod, "model": "", "sabit": False, "istege_bagli": False, "kurulu": None, "yol": ""}
    hf_hub, torch_kok = _hf_ve_torch_kokleri(cache_dir)
    var, yol = _var_mi(secim[0], secim[1], hf_hub, torch_kok)
    return {"dil": kod, "model": secim[1], "sabit": sabit, "istege_bagli": istege_bagli, "kurulu": var, "yol": str(yol)}


def cevrimici_mi() -> bool:
    """Runtime downloads allowed: DUBLAJ_CEVRIMICI=1, or HF offline mode was never switched on."""
    return os.environ.get(CEVRIMICI_DEGISKENI) == "1" or os.environ.get("HF_HUB_OFFLINE") != "1"


def ctc_modeli_gerekli(dil: str, cache_dir: str | Path | None = None, motor: str = "faster_whisper_ctc") -> dict:
    """Raise `CtcModeliEksikHatasi` when the language's CTC model is missing and nothing may download it."""
    durum = ctc_modeli_durumu(dil, cache_dir)
    if durum["kurulu"]:
        return durum
    if durum["sabit"]:
        raise CtcModeliEksikHatasi(
            f"{motor}: '{durum['dil']}' dili için CTC hizalama modeli kurulu değil ({durum['model']}; beklenen yer "
            f"{durum['yol']}). Kelime zamanı CTC'den gelir; Whisper'ın kendi zamanına sessizce düşülmez. Kurulum: "
            f"{KURULUM_ADIMI}. Bilerek Whisper zamanı için: transkripsiyon.motor=faster-whisper."
        )
    if cevrimici_mi():
        return durum  # not pinned, but the user allowed downloads: the CTC worker fetches it
    if durum["istege_bagli"]:
        raise CtcModeliEksikHatasi(
            f"{motor}: '{durum['dil']}' dili için CTC hizalama modeli kurulu değil ({durum['model']}; beklenen yer "
            f"{durum['yol']}). Bu dilin modeli isteğe bağlı kurulum adımında sabitlidir: {ISTEGE_BAGLI_KURULUM_ADIMI}. "
            "Bilerek Whisper zamanı için: transkripsiyon.motor=faster-whisper."
        )
    model = durum["model"] or "bilinmiyor (WhisperX bulunamadı)"
    lisans = ""
    if durum["dil"] in TICARI_OLMAYAN_VARSAYILAN_DILLER:
        lisans = " Not: bu dilin WhisperX varsayılan modeli VoxPopuli, CC BY-NC 4.0 (ticari olmayan) lisanslıdır."
    raise CtcModeliEksikHatasi(
        f"{motor}: '{durum['dil']}' dili için CTC hizalama modeli diskte yok ({model}). Bu dilin modeli kurulum "
        f"betiğinde sabitlenmiş değil (en, tr: {KURULUM_ADIMI}; ja, zh: {ISTEGE_BAGLI_KURULUM_ADIMI}); bir kez "
        f"{CEVRIMICI_DEGISKENI}=1 ile çalıştırıp WhisperX'in varsayılan modelini indirin. Bilerek Whisper zamanı için: "
        f"transkripsiyon.motor=faster-whisper.{lisans}"
    )


def kontrol_ozeti(cache_dir: str | Path | None = None) -> dict[str, bool]:
    """Pinned languages only (no heavy imports): {"en": True, "tr": False}."""
    hf_hub, torch_kok = _hf_ve_torch_kokleri(cache_dir)
    return {dil: _var_mi(tur, ad, hf_hub, torch_kok)[0] for dil, (tur, ad) in SABIT_CTC_MODELLERI.items()}
