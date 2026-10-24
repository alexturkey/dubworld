# Bolum 10: Kaynak Edinme

Bu bolum kullanici girdisinden ASR motorlarina verilecek ses dosyasi
hazirlanana kadar olan on katmani tasir. Bolum ve kutu listesinin sahibi
`docs/arac_katalogu.md` belgesidir.

```text
bolum_10_kaynak_edinme/
  adim_10_dosya_adi_guvenligi/
    filename_sanitizer.py
  adim_20_kaynak_alma/
    source_video.py
    youtube_downloader.py
  adim_30_video_bilgisi/
    video_metadata.py
  adim_40_ses_cikarma/
    audio_extractor.py
  adim_50_asr_sesi_hazirlama/
    demucs_cleaner.py
  akilli_kare_yakalama/
```

Girdi:

```text
URL veya lokal video dosyasi
```

Cikti:

```text
source_audio.wav veya asr_ready.wav
```

Anlam:

- `adim_10_dosya_adi_guvenligi/` dosya ve run klasoru adlarini Windows,
  FFmpeg ve Python icin guvenli hale getirir.
- `adim_20_kaynak_alma/` URL veya lokal video kaynagini run klasorune
  hazirlar.
- `adim_30_video_bilgisi/` ffprobe tabanli video metadata okuma ve loglama
  yardimcilarini tasir.
- `adim_40_ses_cikarma/` videodan ASR veya Demucs icin WAV cikarir.
- `adim_50_asr_sesi_hazirlama/` Demucs vokal izolasyonu ve 16 kHz mono
  ASR-ready ses uretimini tasir.
- `akilli_kare_yakalama/` Instagram tasiyici karesindeki gercek video alanini
  zaman profilleriyle bulan ve gerekirse kirpan izole kutudur.

Bu bolum transkripsiyon yapmaz. Transkripsiyon `src/bolum_20_transkripsiyon/`,
kelime hizalama ve dublaj segmenti `src/bolum_30_hizalama_ve_segment/`
bolumunun isidir.
