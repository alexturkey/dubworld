# DubWorld src haritası

Bu klasor uygulamanin aktif akisindaki butun kodun kanonik kokudur (`dublaj_hatti` paketi). Ilk seviyede
akis sirasina gore numaralanmis bolumler ve ortak giris dosyalari (CLI, GUI, web, ayar, motor kaydi) bulunur; her
bolum kendi kutularini tasir. Uctan uca akis ve dosya:satir haritasi: `docs/engineering/pipeline-flow.md`.
Importlar paket adiyladir, ornegin `from dublaj_hatti.bolum_00_omurga.core.dubber import ...`.

```text
src/dublaj_hatti/
  cli.py, masaustu.py, web.py   dubla, dubla-gui (web arayuzu kendi penceresinde), dubla-web girisleri; asama_komutlari.py tek asama komutlari
  api.py                        Python API (asama islevleri)
  yapilandirma.py, varsayilan.toml  ayar katmanlari ve "Onerilen akis" varsayilanlari
  kayit.py, lisans_onayi.py     motor kaydi (lisans, donanim) ve tek lisans kapisi
  is_yonetimi/, is_yurutucu.py  is kuyrugu, devam, arayuz alt sureci
  semalar/                      asama dosyalarinin JSON Schema'lari
  bolum_00_omurga/              pipeline orkestrasyonu ve motor sinir adapterleri
    core/                       Segment Senkron ana akisi (dubber.py), checkpoint cekirdegi
    runtime/                    donanim, kaynak kilidi, cikti yollari, harici motor adapterleri, internet gateway
    full_metin_dublaji.py       Full Metin akisi
  bolum_10_kaynak_edinme/       URL/lokal video girdisinden ASR-ready ses uretimi
    adim_10_dosya_adi_guvenligi/
    adim_20_kaynak_alma/
    adim_30_video_bilgisi/
    adim_40_ses_cikarma/
    adim_50_asr_sesi_hazirlama/ Demucs ve ASR sesi
    akilli_kare_yakalama/       video kenar bantlarini kirpan istege bagli kutu
  bolum_20_transkripsiyon/      ASR motor kutulari ve YouTube JSON3 kaynagi
    whisperx_motoru/
    faster_whisper_motoru/
    parakeet_cpu_align_motoru/
    crisperwhisper_turbo_ct2_motoru/    WSL2 CUDA INT8 motor kutusu
    youtube_json3_kaynagi/
    zaman_kaynaklari.py
  bolum_30_hizalama_ve_segment/ nihai dublaj segmenti API'si ve CTC kelime hizalama
    nihai_dublaj_segmentleri.py
    ctc_kelime_hizalama/
  bolum_40_ceviri/              yerel ceviri, arka uc secimi, LLM kopru kutulari, dil ekleri
  bolum_50_seslendirme/         TTS orkestratoru, Supertonic / VoxCPM2 / EMA Lightning / XTTS kutulari, RVC, hizalayicilar
    metinden_seslendirme.py     metinden seslendirme akisi
  bolum_60_video_ve_encode/
    kodlayici.py                NVENC / x264 secimi
    timeline_ve_final_encode/   dublaj sonrasi timeline, audio/video isleme ve final encode
  bolum_70_gorsel_uretim/
    kapak_gorseli/              tek transkript plani ve paralel Codex Exec/ImageGen kapak uretimi
  bolum_80_arayuz_ve_teslim/
    telegram_botu/              Telegram uzaktan kumanda botu, yerel Bot API sunucusu, teslim
```

`src/bolum_20_transkripsiyon/crisperwhisper_turbo_ct2_motoru/`, modelin dil kimliği
tablosundan otomatik kaynak dili seçen ayrı bir WSL2/CTranslate2 CUDA INT8
üretim kutusudur. Motorun süreç girişi `src/worker_entry.py`, native yürütme
sahibi `src/native_softmax.py`, model iş akışı `src/worker.py` dosyalarıdır.
Native kimlik ve yaşam döngüsü motorun `docs/motor_sozlesmesi.md` belgesinde
tanımlıdır. Ana akış kutudan implementation
import etmez; `src/bolum_00_omurga/runtime/crisperwhisper_turbo_ct2_runtime.py` atomik JSON
isteğini WSL subprocess worker'a verir ve tam ses metnini, doğal kelime
zamanlarını, runtime kimliğini ve hash doğrulamalı artefaktları geri alır.
`global_first_window` ilk konuşma bağlamından tek dil
seçer; `continuous_stream` 4 saniyelik hareketli bağlamı 1 saniyelik tıklarla
izler ve dil değişimini iki ardışık güvenilir tıkla doğrular. Tespit ve profil
kanıtları transkripsiyondan ayrı, hash doğrulamalı artefaktlardır.

Yeni uygulama kodu `src/dublaj_hatti/` disina eklenmez. Yeni motor once `kayit.py`'ye bir satir olarak
girer (CONTRIBUTING.md "Add an engine"); testler repo kokundeki `tests/` altindadir.
