"""Is the CTC alignment model for a language on disk? (stdlib only; heavy imports are lazy and optional.)

Used before the shared CTC box runs for `faster_whisper_ctc` (the `auto` fallback) and by `dubla kontrol`, so a missing
model stops the job with the install step instead of silently keeping Whisper's own word times (ADR 0009).

Pinned models (`scripts/modeller.json`, step `hizalama`; `scripts/kur.ps1 -Adim modeller`): `en`, `tr`. Optional pinned
models (step `hizalama-diller`; `scripts/kur.ps1 -Adim hizalama-diller`): `ja`, `zh`. Every other language uses the
WhisperX default model, which no install step fetches; it can be fetched only on purpose with `DUBLAJ_CEVRIMICI=1`
(the runtime is offline by default, `cli.ortami_hazirla`). Every Hugging Face model, installed or fetched, is loaded
from its pinned commit (`HF_CTC_SURUMLERI`, `hizalama_modelini_yukle`). The WhisperX defaults for fr, de, es, it are VoxPopuli models under
CC BY-NC 4.0 (non-commercial): loading one needs the license acceptance `whisperx_ctc_<lang>` (`lisans_onayi`, the one
license gate); `ctc_lisans_denetle` is called right before every WhisperX default-model load.
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
# Every Hugging Face CTC model at a fixed commit: a load never resolves the Hub's moving "main", so a changed or
# hijacked repo cannot slip in new weights or code. Covers WhisperX's Hugging Face default table and
# KUTU_OZEL_MODELLER (en, fr, de, es, it are torchaudio checkpoints, not Hugging Face). Commits = the Hub's "main" on
# 2026-10-26, the weights every earlier download got; tr, ja, zh = scripts/modeller.json (tests check both).
HF_CTC_SURUMLERI: dict[str, str] = {
    "mpoyraz/wav2vec2-xls-r-300m-cv7-turkish": "708639f50559d7970f462e13ec64d3f059ca89f6",
    "jonatasgrosman/wav2vec2-large-xlsr-53-japanese": "cf031e020336460d15a417eba710bbc5bb43be9a",
    "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn": "99ccb2737be22b8bb50dcfcc39ad4d567fb90cfd",
    "jonatasgrosman/wav2vec2-large-xlsr-53-dutch": "46f221381d200f7bef268309b3f02023ccf11fcc",
    "Yehor/wav2vec2-xls-r-300m-uk-with-small-lm": "e3ced4def0d70be3aab0f2db598a59961fe9ab3b",
    "jonatasgrosman/wav2vec2-large-xlsr-53-portuguese": "634ac655299bcdc46c83bc01da9bab52d2987e4f",
    "jonatasgrosman/wav2vec2-large-xlsr-53-arabic": "af46c2d8531b8dcbb5e23b952f739b372c2e5d2d",
    "comodoro/wav2vec2-xls-r-300m-cs-250": "73e2b9004f35d3ca79316a624e7edc3cdaa45d40",
    "jonatasgrosman/wav2vec2-large-xlsr-53-russian": "2329100508896c6d9b157019803ab5601e6f3406",
    "jonatasgrosman/wav2vec2-large-xlsr-53-polish": "6b1cea36bd8bc5f65ec8081667cd9c0207d51970",
    "jonatasgrosman/wav2vec2-large-xlsr-53-hungarian": "2bd0786e71cad097c4e6ce9b3e45b40c74ad8f37",
    "jonatasgrosman/wav2vec2-large-xlsr-53-finnish": "a497f86c265cffe9f5d6f0162bc7862dc3e11c00",
    "jonatasgrosman/wav2vec2-large-xlsr-53-persian": "234714078a1398a9db88194c5a40fefe6f376dc1",
    "jonatasgrosman/wav2vec2-large-xlsr-53-greek": "489b34fb35fc5876af6193d419772cb9d6d1d531",
    "saattrupdan/wav2vec2-xls-r-300m-ftspeech": "7a60985d596e7a9e26b01a0707fe59daac6ffe84",
    "imvladikon/wav2vec2-xls-r-300m-hebrew": "b2e683004903f1b11bee2c6092a7c323ed858d82",
    "nguyenvulebinh/wav2vec2-base-vi-vlsp2020": "50a30dadb3ec98a0d4cdb1eb1ea315aff538f7c2",
    "kresnik/wav2vec2-large-xlsr-korean": "629c9a3501c10ba128bf3fa1eebb12af3be03f61",
    "kingabzpro/wav2vec2-large-xls-r-300m-Urdu": "18a6595fc0cc4d9c63fc8d0407b5596f09c49edb",
    "anuragshas/wav2vec2-large-xlsr-53-telugu": "102b87629072c9e8562f43a1864fb3ede8df11fa",
    "theainerd/Wav2Vec2-large-xlsr-hindi": "3020b7d543a987afd986f1a5a241d47c588fe865",
    "softcatala/wav2vec2-large-xlsr-catala": "4e8ceed125344298e04a2a5d9ce1645f7fc3d4b9",
    "gvs/wav2vec2-large-xlsr-malayalam": "b073beb93616a83d26933e1aa98d9299a5f4af23",
    "NbAiLab/nb-wav2vec2-1b-bokmaal-v2": "58a6eb5d7927c378f5d2785bc865756c9ae273ae",
    "NbAiLab/nb-wav2vec2-1b-nynorsk": "37107327f6af742c008042d8cfdba4276de18f82",
    "comodoro/wav2vec2-xls-r-300m-sk-cv8": "caba6c9c8800778823ce75d96bed9ee2eb56ea3a",
    "anton-l/wav2vec2-large-xlsr-53-slovenian": "9801c0c603f87bd0f2ad0504ba16966f2984571e",
    "classla/wav2vec2-xls-r-parlaspeech-hr": "a6075e0c9e0c49a533dc61876b1eafc6bc78de92",
    "gigant/romanian-wav2vec2": "79cf603aac59501d02bfeb37f615efc3ac4ce1b3",
    "stefan-it/wav2vec2-large-xlsr-53-basque": "ac4e27d2d376a5ed919b381ec99d7a86b37c0a6b",
    "ifrz/wav2vec2-large-xlsr-galician": "70b3bfad73c9cec3b2c638c655bc6dc7ceef2c9e",
    "xsway/wav2vec2-large-xlsr-georgian": "b29b81945f5fa2e35fbb05da5256815d8cc71e20",
    "jimregan/wav2vec2-large-xlsr-latvian-cv": "ca99957784deb8ffadf4b782db3e96dde797d164",
    "Khalsuu/filipino-wav2vec2-l-xls-r-300m-official": "06e33a5630c543cffb68a011fef6eea64dcc09d8",
    "KBLab/wav2vec2-large-voxrex-swedish": "ca70e31c06a2617bf7fe3b4fb5d387d2b19b2983",
    "cahya/wav2vec2-large-xlsr-indonesian": "fe66c9f1114e958d0c08de5dcc7e82bb8001d4a1",
    "Galuh/wav2vec2-large-xlsr-indonesian": "82bbac6b4566ca3f6f5fc3ca5d083cf63a3754d3",
}


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
    if ad in HF_CTC_SURUMLERI:  # only the pinned commit counts; another snapshot is never loaded
        yol = yol / HF_CTC_SURUMLERI[ad]
        return any((yol / f).is_file() for f in AGIRLIK_DOSYALARI), yol
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


def ctc_lisans_denetle(dil: str, onay: bool = False) -> None:
    """Raise `lisans_onayi.LisansOnayiGerekli` before a non-commercial WhisperX default CTC model (fr/de/es/it) is
    loaded without acceptance. Accepted once (`--lisans-onay`, GUI/web dialog, or DUBLAJ_LISANS_ONAY=1) it passes."""
    from dublaj_hatti.lisans_onayi import ctc_lisans_adi, kapi_adlar

    ad = ctc_lisans_adi(dil)
    if ad:
        kapi_adlar([ad], onay)


def sabit_hf_klasoru(dil: str, cache_dir: str | Path | None = None) -> Path | None:
    """Local folder of the language's Hugging Face CTC model at its pinned commit (HF_CTC_SURUMLERI); fetched at that
    commit when missing and downloads are allowed. None: torchaudio checkpoint or no model known (WhisperX decides)."""
    kod = _dil(dil)
    secim = SABIT_CTC_MODELLERI.get(kod) or ISTEGE_BAGLI_CTC_MODELLERI.get(kod) or _varsayilan_model(kod)
    if not secim or secim[0] != "hf":
        return None
    ad = secim[1]
    if ad not in HF_CTC_SURUMLERI:
        raise CtcModeliEksikHatasi(f"'{kod}' dilinin CTC modeli {ad} için sabit sürüm yok (HF_CTC_SURUMLERI).")
    hf_hub, torch_kok = _hf_ve_torch_kokleri(cache_dir)
    var, yol = _var_mi("hf", ad, hf_hub, torch_kok)
    if var:
        return yol
    if not cevrimici_mi():
        ctc_modeli_gerekli(kod, cache_dir)  # raises with the install step (pinned) or the DUBLAJ_CEVRIMICI hint
    from huggingface_hub import HfApi, snapshot_download

    surum = HF_CTC_SURUMLERI[ad]
    dosyalar = {s.rfilename for s in HfApi().model_info(ad, revision=surum).siblings or []}
    # The same weight file transformers would pick from the repo (safetensors first), plus the small json files.
    agirlik = "model.safetensors" if "model.safetensors" in dosyalar else "pytorch_model.bin"
    return Path(snapshot_download(ad, revision=surum, cache_dir=str(hf_hub), allow_patterns=["*.json", agirlik]))


def hizalama_modelini_yukle(whisperx, dil: str, device: str, cache_dir: str | Path | None = None):
    """The one way a worker loads a CTC alignment model: license gate first (fr/de/es/it), then
    `whisperx.load_align_model` from the pinned local folder (Hugging Face) or WhisperX's own torchaudio default
    (checkpoint file checked by sha256 at install). Returns (model, metadata)."""
    ctc_lisans_denetle(dil)
    klasor = sabit_hf_klasoru(dil, cache_dir)
    if klasor is None:
        return whisperx.load_align_model(language_code=dil, device=device)
    return whisperx.load_align_model(language_code=dil, device=device, model_name=str(klasor), model_cache_only=True)


def kontrol_ozeti(cache_dir: str | Path | None = None) -> dict[str, bool]:
    """Pinned languages only (no heavy imports): {"en": True, "tr": False}."""
    hf_hub, torch_kok = _hf_ve_torch_kokleri(cache_dir)
    return {dil: _var_mi(tur, ad, hf_hub, torch_kok)[0] for dil, (tur, ad) in SABIT_CTC_MODELLERI.items()}
