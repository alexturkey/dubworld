# Dublaj hatti Src Haritasi

Bu klasor uygulamanin aktif akisindaki butun kodun kanonik kokudur. Ilk
seviyede yalniz akis sirasina gore numaralanmis bolumler ve `testler/`
bulunur; her bolum kendi kutularini tasir. Bolum ve kutu listesinin, siralama
kurallarinin ve yeni kutu yerlesiminin sahibi `docs/arac_katalogu.md`
belgesidir. Importlar `src` kokune goredir, ornegin
`from dublaj_hatti.bolum_00_omurga.core.dubber import ...`.

```text
src/
  bolum_00_omurga/              pipeline orkestrasyonu, secim grafigi ve motor sinir adapterleri
    core/                       Segment Senkron ve Full Metin ana akisi, checkpoint cekirdegi
    selection_graph/            menu/is sozlesmesi grafigi ve implementation registry
    runtime/                    output yolu, harici motor kutusu adapterleri, internet gateway
    full_metin_dublaji.py       Full Metin akisi
  bolum_10_kaynak_edinme/       URL/lokal video girdisinden ASR-ready ses uretimi
    adim_10_dosya_adi_guvenligi/
    adim_20_kaynak_alma/
    adim_30_video_bilgisi/
    adim_40_ses_cikarma/
    adim_50_asr_sesi_hazirlama/ Demucs ve ASR sesi
    akilli_kare_yakalama/       Instagram tasiyici karesinde gercek video alanini bulan kutu
  bolum_20_transkripsiyon/      ASR motor kutulari, Telegram presetleri ve YouTube JSON3 kaynagi
    ayarlar/
    whisperx_motoru/
    faster_whisper_motoru/
    whisper_cpp_cpu_align_motoru/
    parakeet_cpu_align_motoru/
    speechmatics_motoru/
    elevenlabs_scribe_v2_motoru/
    crisperwhisper2_medium_motoru/      kendi venv ve modeliyle Medium motor kutusu
    crisperwhisper_turbo_ct2_motoru/    WSL2 CUDA INT8 motor kutusu
    moonshine_medium_streaming_motoru/  CPU offline motor kutusu
    youtube_json3_kaynagi/
  bolum_30_hizalama_ve_segment/ nihai dublaj segmenti API'si ve konusmaci/cinsiyet
    nihai_dublaj_segmentleri.py
    konusmaci_ve_cinsiyet/
  bolum_40_ceviri/              ceviri motorlari, aday hazirlama ve backend bridge kutulari
  bolum_50_seslendirme/         TTS orkestratoru, Edge/Supertonic/XTTS kutulari, hizalayicilar
    dub_timing_profiler/        Edge TTS timing profiler kutusu
    metinden_seslendirme.py     metinden seslendirme akisi
  bolum_60_video_ve_encode/
    timeline_ve_final_encode/   dublaj sonrasi timeline, audio/video isleme ve final encode
  bolum_70_gorsel_uretim/
    kapak_gorseli/              tek transkript plani ve paralel Codex Exec/ImageGen kapak uretimi
  bolum_80_arayuz_ve_teslim/
    telegram_bot/               Telegram arayuzu, kuyruk isleyici ve is soy projeksiyonu
    telegram_control_bot/       bagimsiz kontrol botu
    gui/                        masaustu GUI girisleri
  testler/                      birim ve entegrasyon testleri
```

`src/bolum_20_transkripsiyon/moonshine_medium_streaming_motoru/`, deney çalıştırıcısının
bayt düzeyinde korunmuş kopyasını kendi ortamı ve modeliyle çalıştırır.
Ana giriş `src/bolum_00_omurga/runtime/moonshine_medium_streaming_runtime.py` adaptörüdür.
Telegram/GUI'de 14. seçenek bağlanmıştır; native zamanların ortak dublaj
kapılarıyla uyumu ve canlı teslim kabulü henüz tamamlanmamıştır. Güncel durumun
sahibi `docs/moonshine_medium_streaming_motoru.md` belgesidir.

`src/bolum_20_transkripsiyon/crisperwhisper_turbo_ct2_motoru/`, modelin dil kimliği
tablosundan otomatik kaynak dili seçen ayrı bir WSL2/CTranslate2 CUDA INT8
üretim kutusudur. Motorun süreç girişi `src/worker_entry.py`, native yürütme
sahibi `src/native_softmax.py`, model iş akışı `src/worker.py` dosyalarıdır.
Native kimlik ve yaşam döngüsü motorun `docs/motor_sozlesmesi.md` belgesinde
tanımlıdır. Ana akış kutudan implementation
import etmez; `src/bolum_00_omurga/runtime/crisperwhisper_turbo_ct2_runtime.py` atomik JSON
isteğini WSL subprocess worker'a verir ve tam ses metnini, doğal kelime
zamanlarını, runtime kimliğini ve hash doğrulamalı artefaktları geri alır.
Medium CrisperWhisper kutusunun venv'i, modeli, dil rotaları veya artefaktlarıyla
ortak sahipliği yoktur. `global_first_window` ilk konuşma bağlamından tek dil
seçer; `continuous_stream` 4 saniyelik hareketli bağlamı 1 saniyelik tıklarla
izler ve dil değişimini iki ardışık güvenilir tıkla doğrular. Tespit ve profil
kanıtları transkripsiyondan ayrı, hash doğrulamalı artefaktlardır.

`src/bolum_20_transkripsiyon/crisperwhisper2_medium_motoru/` ana repo tarafindan
izlenen entegre CrisperWhisper motor kutusudur; eski adi `crisperwhisperdenemleri`
idi. Ana akis
bu kutudan implementation import etmez: `src/bolum_00_omurga/core/dubber.py`,
`src/bolum_00_omurga/runtime/crisperwhisper_runtime.py` araciligiyla sesi ve run klasorunu JSON
istegi olarak `src/bolum_20_transkripsiyon/crisperwhisper2_medium_motoru/src/crisperwhisper_api_service.py`
giris noktasina verir. Istek `crisper_language_detection_mode` alaninda ya ilk
dogal pencereden tek kaynak dil (`global_first_window`) ya da mevcut dogal
pencerelerin her birinde dil tespiti (`per_window`) ister. Guncel gorunur
cok-dilli secenek `continuous_stream`, 4 saniyelik hareketli baglami nominal 1
saniyelik tiklarla izler; gerekirse kisa terminal kapsam tiki ekler ve ilk dil
dahil kararlarini iki ardisik guvenilir tikla kurar. Pencere-bazli mod
komsu ayni dilleri tek inference run'inda birlestirerek mevcut continuation veya
dinamik pencere/Stitch yolunu yeniden kullanir; ana uygulama ayri bir ASR katmani
calistirmaz. Alt surec VAD compact timeline ve kelime zamanlarini uretir.
Degistirilmemis model gercegi `crisperwhisper2_medium_raw.json`, ceviri
ve dublaj girdisi ise `crisperwhisper2_medium_dubbing_ready.json` olarak ayni
run klasorunde saklanir. Raw, dubbing-ready, dil tespit ve dil profil
artefaktlarinin hash'leri ana runtime tarafindan dogrulanir. Tek donusum sahibi
`src/bolum_20_transkripsiyon/crisperwhisper2_medium_motoru/src/crisperwhisper_dubbing_ready.py` dosyasidir; ana
uygulama donen temiz kelimeleri `src/bolum_30_hizalama_ve_segment/nihai_dublaj_segmentleri.py` kanonik
segment API'sine verir. Bosluksuz dil route'u ve Unicode-guvenli zaman gruplari
`src/bolum_20_transkripsiyon/crisperwhisper2_medium_motoru/src/crisperwhisper_no_space_languages.py` sahibindedir.
Runtime 23 hızlandırmasının inference mode, encoder cache, seçici eager attention,
birim ölçek atlama ve boşluksuz dillerdeki tek-batch intended consensus sahibi
`src/bolum_20_transkripsiyon/crisperwhisper2_medium_motoru/src/crisperwhisper_runtime_optimization.py` dosyasıdır.
Hız route'u yalnız motorun kendi tespit ettiği dil koduyla seçilir; ses adı,
süre veya içerik istisnası kullanmaz.
Bu kutu coken `verbatim` pencereleri boslukla ayrilmis kelime sayisiyla degil
icerik tokenlariyla olcer; token sayisi yeterli olsa bile son aktif ses
kuyrugunda 3 saniyeden fazla zaman boslugu birakan ciktisini kabul etmez.
Gerekirse ayni pencerenin zamanlanmis `intended` veya ayni snapshot'in dil kodlu
duz transcribe kardes ciktisini kullanir.
Continuation promptu ayni kutuda canli model kapasitesiyle butcelenir; 256 yeni
token korunurken son onayli grubun yalniz sigan Unicode-guvenli token suffix'i
kullanilir. Zamanlanmis bosluksuz continuation sonucu model dongusune duserse
satir silinmez; ayni gercek compact ses bir kez `intended` continuation ile
yeniden zamanlanir. Nihai besli tekrar adayinda her ornegin ilk kelime
baslangici eksiksiz ve kesin artiyorsa gercek zamanli tekrar korunur; baslangic
  eksik, esit veya geriye gidiyorsa kalite kapisi reddeder. Kalite kapisi
  reddederse basarili raw/dublaja-hazir cifti uretilmez;
  Stitch sinirindaki ayni normalize kelime, ikinci baslangic kesin ilerideyse
  ayri tekrar olarak mevcut yerel orta-nokta kontrolune girer; esit veya geriye
  giden baslangic fail-closed kalir.
`crisperwhisper2_medium_quality_failure.json` son kalite reddinin yanında erken
model, dil-route, pencere ve Stitch exception'larini da asama/neden/traceback ile
saklar. Stitch reddinde iki overlap tarafinin gercek kelime ve zamanlari, yerel
ve global compact saniye ile ozgun ses saniyesi kaybolmaz. Tekrar bulgusu ozgun
kelime indisleri, saniyeler, okunabilir zaman damgalari ve kisa baglamla saklanir.
Global compact bandin sonunda butun overlap ve bridge denemeleri gecerli
ankrajla ayni son kelimede kalir ve yeni zamanli kelime uretemezse yalniz
kelimesel olarak dogrulanmayan VAD kuyrugu transkripsiyon kapsamindan cikarilir;
kelime ve segment zamanlari Crisper kelime zamanlarindan uretilmeye devam eder.
Bu kosullu dosya debug kanitidir ve tamamlanmis transkripsiyon checkpoint'i
sayilmaz.

Kokte Python dosyasi tutulmaz. Gecis shim'i gerekiyorsa once cagiran kod
kanonik kutu yoluna alinir, sonra kok shim kaldirilir.

Yeni uygulama kodu kok `src` altina veya proje kokune eklenmez. Once
`docs/arac_katalogu.md` kurallarina gore bolum ve kutu secilir; kutu yoksa
yeni kutu, katalog satiri ve README haritasi birlikte olusturulur. Uyum
`src/testler/test_arac_katalogu.py` ile denetlenir.
