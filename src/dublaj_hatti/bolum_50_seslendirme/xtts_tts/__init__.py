"""XTTS v2 TTS kutusu (isteğe bağlı, varsayılan kapalı; extras `tts-xtts`).

Ağırlık lisansı CPML (ticari olmayan); ağırlık repoda yoktur, ilk kullanımda kullanıcının onayıyla Coqui'nin kendi
indiricisi indirir. Gerçek kişi referans sesi repoda yoktur: referans her zaman kullanıcının kendi (rızalı) sesidir.
"""

from dublaj_hatti.bolum_50_seslendirme.xtts_tts.api import (  # noqa: F401
    XTTS_ENGINE_ID,
    XttsHatasi,
    build_xtts_dubbed_audio,
    xtts_durumu,
)
