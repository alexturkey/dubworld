"""XTTS v2 ile segment seslendirme (Supertonic ile aynı sonuç sözleşmesi; isteğe bağlı, extras `tts-xtts`)."""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from dublaj_hatti.bolum_50_seslendirme.xtts_tts.lisans import LISANS_METNI, lisans_onayli, xtts_kok
from dublaj_hatti.bolum_50_seslendirme.xtts_tts.metin import xtts_metin_parcala

XTTS_ENGINE_ID = "xtts"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
# XTTS v2'nin desteklediği diller (model kartı: huggingface.co/coqui/XTTS-v2)
XTTS_DILLERI = {"en": "en", "es": "es", "fr": "fr", "de": "de", "it": "it", "pt": "pt", "pl": "pl", "tr": "tr",
                "ru": "ru", "nl": "nl", "cs": "cs", "ar": "ar", "zh": "zh-cn", "ja": "ja", "hu": "hu", "ko": "ko",
                "hi": "hi"}
KURULUM_IPUCU = (
    "XTTS v2 kurulu değil: pip install .[tts-xtts]  (coqui-tts; ya da ayrı ortam için DUBLAJ_XTTS_PYTHON); "
    "ayrıntı docs/motorlar/xtts.md"
)
logger = logging.getLogger("dublaj_hatti")


class XttsHatasi(RuntimeError):
    pass


def xtts_python() -> str | None:
    ozel = os.environ.get("DUBLAJ_XTTS_PYTHON", "").strip()
    if ozel:
        return ozel if Path(ozel).is_file() else None
    return sys.executable if importlib.util.find_spec("TTS") is not None else None


def xtts_durumu() -> dict[str, Any]:
    python = xtts_python()
    return {"kurulu": python is not None, "python": python or "", "lisans_onayi": lisans_onayli(),
            "model_klasoru": str(xtts_kok())}


def xtts_dil_kodu(dil: str) -> str:
    kod = XTTS_DILLERI.get(str(dil or "").strip().lower())
    if not kod:
        raise XttsHatasi(f"XTTS v2 bu hedef dili desteklemiyor: {dil} (desteklenen: {', '.join(sorted(XTTS_DILLERI))})")
    return kod


def on_denetim(cfg: Any) -> str:
    """Çalıştırmadan önceki bütün denetimler; referans sesin tam yolunu döndürür."""
    if xtts_python() is None:
        raise XttsHatasi(KURULUM_IPUCU)
    if not lisans_onayli():
        raise XttsHatasi(
            LISANS_METNI + " Onay için: python -m dublaj_hatti.bolum_50_seslendirme.xtts_tts onay"
        )
    referans = str(getattr(cfg, "xtts_referans_ses", "") or "").strip()
    if not referans:
        raise XttsHatasi("XTTS için referans ses gerekli (ses.xtts_referans_ses): kendi sesiniz ya da izinli bir ses")
    yol = Path(referans).expanduser().resolve()
    if not yol.is_file():
        raise XttsHatasi(f"XTTS referans sesi bulunamadı: {yol.name}")
    xtts_dil_kodu(getattr(cfg, "target_lang", "tr"))
    return str(yol)


def _kosucu_ortami() -> dict[str, str]:
    ortam = dict(os.environ)
    ortam["COQUI_TOS_AGREED"] = "1"  # onay dosyası on_denetim'de doğrulandı
    ortam.setdefault("TTS_HOME", str(xtts_kok()))
    return ortam


def build_xtts_dubbed_audio(segments, cfg, run_dir: str):
    import soundfile as sf

    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.api import SupertonicDubResult, build_supertonic_audio_mix
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.execution import prepare_supertonic_result_for_segment

    referans = on_denetim(cfg)
    dil = xtts_dil_kodu(cfg.target_lang)
    calisma = Path(run_dir) / "xtts"
    calisma.mkdir(parents=True, exist_ok=True)
    parcalar = [{"index": seg.index, "metin": xtts_metin_parcala(seg.text)} for seg in segments if seg.text.strip()]
    is_dosyasi, sonuc_dosyasi = calisma / "is.json", calisma / "sonuc.json"
    is_dosyasi.write_text(json.dumps({"referans": referans, "dil": dil, "calisma": str(calisma), "parcalar": parcalar},
                                     ensure_ascii=False), encoding="utf-8")
    logger.info("[XTTS] %d segment seslendiriliyor (dil=%s)", len(parcalar), dil)
    tamam = subprocess.run(
        [str(xtts_python()), "-B", str(Path(__file__).with_name("kosucu.py")), "--is", str(is_dosyasi),
         "--sonuc", str(sonuc_dosyasi)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=_kosucu_ortami(),
        stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
    )
    if tamam.returncode != 0 or not sonuc_dosyasi.is_file():
        raise XttsHatasi(f"XTTS koşucusu başarısız (çıkış {tamam.returncode}): {(tamam.stderr or tamam.stdout)[-1500:]}")
    ozet = json.loads(sonuc_dosyasi.read_text(encoding="utf-8"))
    if ozet.get("hatali"):
        raise XttsHatasi(f"XTTS şu segmentleri seslendiremedi: {ozet['hatali'][:10]}")

    timing_infos, segment_audios, prepared = [], {}, {}
    for seg in segments:
        yol = ozet["wavlar"].get(str(seg.index))
        if not yol:
            continue
        ses, sr = sf.read(yol, dtype="float32")
        idx, wav, timing, hazir = prepare_supertonic_result_for_segment(
            seg, {"wav_array": ses, "sample_rate": sr, "debug": {"voice_id": "xtts_referans"}}, cfg.sample_rate,
            "xtts_referans",
        )
        timing["engine"] = XTTS_ENGINE_ID
        segment_audios[idx] = wav
        timing_infos.append(timing)
        prepared[idx] = hazir
    mix = build_supertonic_audio_mix(prepared, max((s.end for s in segments), default=0.0), cfg.sample_rate)
    return SupertonicDubResult(audio=mix, timing_infos=timing_infos, segment_audios=segment_audios, prepared_audios=prepared)
