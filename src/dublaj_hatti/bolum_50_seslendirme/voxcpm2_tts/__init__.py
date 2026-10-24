"""VoxCPM2 TTS kutusu (istege bagli, NVIDIA GPU).

Motor bu repoda degildir: kardes repo `voxcpm2-turkce-ses-tasarimi` sabit commit ile ayri klasore kurulur
(`scripts/kur.ps1 -Adim voxcpm2`). Bu kutu o reponun Python modullerini kendi sanal ortaminda alt surec olarak
calistirir; kalite ayarlari o repoda sabittir (16 adim, cfg 2.0).
"""

from dublaj_hatti.bolum_50_seslendirme.voxcpm2_tts.api import (  # noqa: F401
    VOXCPM2_ENGINE_ID,
    VoxCPM2Hatasi,
    build_voxcpm2_dubbed_audio,
    voxcpm2_durumu,
)
