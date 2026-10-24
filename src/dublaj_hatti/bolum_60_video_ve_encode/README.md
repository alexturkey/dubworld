# Bolum 60: Video ve Encode

Bu bolum dublaj sesi hazirlandiktan sonra timeline, audio/video isleme ve
final encode katmanini tasir. Bolum ve kutu listesinin sahibi
`docs/arac_katalogu.md` belgesidir.

```text
bolum_60_video_ve_encode/
  timeline_ve_final_encode/
    audio_files.py
    video_processor.py
    video_processor_worker.py
```

Kural: Final videoda altyazi ikinci tam encode ile yakilmaz; final mux/encode
tek gecis sozlesmesi korunur. Ayrinti `docs/final_video_cikti_politikasi.md`
ve `docs/video_encoding_tek_gecis_ve_batch_paralellik_raporu.md`
belgelerindedir.
