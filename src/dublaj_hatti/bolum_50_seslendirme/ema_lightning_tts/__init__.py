"""EMA Lightning TTS kutusu (isteğe bağlı; yalnız Türkçe; NVIDIA GPU ya da işlemci).

Paket PyPI'dan sabit sürümle (requirements/ek_tts_ema*.txt), ağırlık resmî model deposundan sabit commit + sha256 ile
iner (`scripts/kur.ps1 -Adim tts-ema`); işlemci yolu için ONNX dosyaları aynı ağırlıktan yerelde dışa aktarılır.
Ayrıntı ve gerekçe: docs/motorlar/ema_lightning.md, docs/adr/0019-ema-lightning-tts.md.
"""

from dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts.api import (  # noqa: F401
    EMA_ENGINE_ID,
    EMAHatasi,
    build_ema_dubbed_audio,
    cihaz_sec,
    ema_durumu,
    synthesize_full_text_ema,
)
