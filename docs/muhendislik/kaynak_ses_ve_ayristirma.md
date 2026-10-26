# Kaynak ses, faz onarımı ve Demucs ile vokal ayrıştırma

English: [../engineering/source_audio_and_separation.md](../engineering/source_audio_and_separation.md)

Hattın bir girdi videosunu konuşma tanıma ve dublaj için sese nasıl çevirdiği ve Demucs'un (sesi vokal ve arka plan
katmanlarına ayıran model) 4 GB'lık bir karta nasıl sığdırılıp hızlı çalıştırıldığı.
Kanıt etiketleri (ölçüldü / belgelendi / kayıt yok) [gpu_bellek_ve_yalitim.md](gpu_bellek_ve_yalitim.md) sayfasında
tanımlıdır.

Kod: `src/dublaj_hatti/bolum_10_kaynak_edinme/adim_40_ses_cikarma/` (çıkarma) ve
`.../adim_50_asr_sesi_hazirlama/` (`demucs_cleaner.py`, `demucs_batch_worker.py`, `arka_plan_sesi_olcumu.py`).
Ayar: `[ses_temizligi] kip` = `original` | `clean` | `preserve_background` | `auto_background`.

## 1. Ses çıkarma ve ters faz düzeltmesi

- **Sorun:** bazı kaynaklar sol ve sağ kanalları ters kutuplulukla (polarite) taşır. Konuşma tanıma için yapılan mono
  indirgeme (iki kanalı tek kanala karıştırma) bu durumda konuşmayı yok eder.
- **Çözüm:**
  - ASR (otomatik konuşma tanıma) yolu (16 kHz mono): ffmpeg önce **stereo** sesi geçici bir WAV'a çıkarır, faz
    kontrolü çalışır, sonra dosya mono'ya indirgenir. Geçici dosya `finally` içinde silinir.
  - Demucs yolu (44.1 kHz stereo): çıkar, sonra aynı faz kontrolü.
  - Faz kontrolü: en fazla ilk 60 s'yi 65.536 karelik parçalarla oku; sol/sağ korelasyonunu ve orta/yan (mid/side) RMS'i
    (ortalama güç) hesapla. Yalnız `corr ≤ −0.95` **ve** `side − mid ≥ 12 dB` **ve** `side ≥ −45 dB` ise onar. Onarım,
    geçici bir dosyaya yazılan ve `os.replace` ile yerine konan `pan=stereo|c0=FL|c1=-1*FR` işlemidir; sonuç yeniden
    çözümlenir ve günlüğe yazılır.
- **Ölçüm:** kayıt yok (öncesi/sonrası sayıları saklanmadı).
- **Hâlâ açık:** çözümlemenin kendisi başarısız olursa onarım hata vermeden atlanır.

## 2. Demucs nasıl kullanılıyor

- Model `htdemucs` (Demucs 4.0.1). CUDA'da projenin kendi toplu iş (batch) işçisi çalışır; CPU'da (ya da başka herhangi
  bir modelde) hazır komut `python -m demucs.separate --two-stems=vocals --jobs 1 --shifts 0` kullanılır.
- Veri akışı: `demucs_source.wav` (44.1 kHz stereo PCM16) → işçi → `vocals.wav`, `no_vocals.wav`,
  `demucs_batch_report.json`. `clean_source.wav`, `vocals.wav`'a sabit bağlantıdır (hard link; bağlama başarısız
  olursa kopya). İhtiyaç duyan motorlar için `asr_ready.wav` (16 kHz mono) üretilir. Arka plan korunuyorsa
  `no_vocals.wav` videoyla aynı kırpma/hız zaman çizelgesinden geçirilir ve dublajın altına karıştırılır
  (bkz. [tts_zamanlama_ve_karisim.md](tts_zamanlama_ve_karisim.md)).
- **Kapalı başarısızlık (fail-closed):** bir Demucs hatası işi transkripsiyondan önce durdurur; asla sessizce ham sesle
  devam etmez.
- **Başarı varsayılmaz, doğrulanır:** çıkış kodu 0 yetmez. Üst süreç işçi raporunu yeniden okur ve şunları kontrol eder:
  girdi yolu, model, overlap 0.25, shifts 0, istenen batch 4, `oom_fallback` bayrağıyla tutarlı gerçek batch ∈ {1, 4},
  iki katman (stem) dosyasının da var olması, `total_seconds > 0` ve `peak_torch_cuda_memory_mb > 0`.

## 3. Gelişim: Demucs "yavaş"tan "daha az RAM'le 2× hızlı"ya nasıl geldi

| Adım | Değişiklik | Ölçülen etki |
|---|---|---|
| 1 | `--segment 12` denendi | başarısız: htdemucs 7.8 s'lik segmentlerle eğitilmiş bir transformer ve daha uzunlarını reddeder |
| 2 | `--segment 7` zorlandı | çalıştı, OOM (bellek yetmedi hatası) yok; taban oldu |
| 3 | zorlanmış segment kaldırıldı (işçi `model.segment` = 7.8 s okur) | 88 dk girdi: duvar saati süresi 654.8 → 620.2 s |
| 4 | `CUDA_LAUNCH_BLOCKING=1` kaldırıldı | ilerleme süresi 604 → 489 s (−%19), VRAM değişmedi (≈ 983 MB) |
| 5 | `cudnn.benchmark=True` denemesi | kazanç yok; benimsenmedi |
| 6 | kendi batch işçisi, batch 4 | 74 dk ses: gerçek uygulama üzerinden 498.7 → ≈ 397–401 s (−%20), torch tepesi ≈ 1.69 GB |
| 7 | iki katmanlı biriktirme + tensörün erken bırakılması | işçi 11 dk 48 s → 5 dk 52 s (2.01×); RAM tepesi 9.52 → 7.15 GB |

### 3.1 OOM yedekli batch işçisi (6. adım)

- **Sorun:** hazır Demucs her GPU çağrısında tek bir 7,8 s'lik segment gönderir ve GPU'yu aç bırakır.
- **Çözüm:** `_split_batched()`, Demucs'un iç parçalarını (parçalama, ortadan kırpma, üçgen örtüşme ağırlığı, geçerli
  uzunluğa dolgu) yeniden kullanır. Dolgulu 4 parçalık gruplar `torch.inference_mode()` altında tek bir `model(...)`
  çağrısından geçer, `overlap=0.25`, `shifts=0`; çıktı `prevent_clip(mode="rescale")` ve PCM16 kullanır.
- **OOM yedeği:** yalnız `torch.cuda.OutOfMemoryError` yakalanır. Ardından `gc.collect()`, `torch.cuda.empty_cache()`,
  `reset_peak_memory_stats()` ve aynı işçide batch 1 ile **bir** yeniden deneme. Başka hatalar asla OOM diye yeniden
  etiketlenmez. Rapor istenen batch'i, gerçek batch'i ve `oom_fallback` değerini kaydeder.
- Torbalanmış (bagged) modeller yalnız birim ağırlıklı tek bir model içeriyorsa kabul edilir.
- **Eşdeğerlik:** iki çalıştırma birbirinin bayt düzeyinde aynısıydı. Batch 1'e göre örneklerin %0,035'i (vocals) ve
  %0,024'ü (no_vocals) en fazla 1 int16 adımı değişti (kayan nokta toplama sırası). Kabul edilen tolerans: en fazla
  1 int16 adımı; batch 1 ile bayt eşliği vaat edilmez.
- Demucs için batch 2 ya da 8: kayıt yok.

### 3.2 İki katmanlı RAM mimarisi (7. adım, en büyük kazanç)

- **Sorun:** ilk batch işçisi dört tam uzunluklu katmanın hepsini CPU RAM'inde biriktiriyordu (75 dk'lık bir dosya için
  ≈ 5,9 GiB, tensör şeklinden hesaplandı); buna normalleştirme referansı, girdi tensörü, örtüşme ağırlıkları ve yeni
  kurulan uzun bir `no_vocals` tensörü ekleniyordu. "Kaydetme" evresi (5 dk 36 s) disk süresi değildi: katman toplama,
  iki yeniden ölçekleme geçişi, PCM16 dönüşümü ve iki WAV yazımıydı.
- **Kök neden:** verinin bellekte kalma süresi. Uzun tensörler süreç çıkışına kadar yaşıyordu ve katman indirgemesi parça
  başına değil, biriktirmeden sonra yapılıyordu.
- **Çözüm:**
  - Model hâlâ 4 kaynak tahmin eder, ama her parça biriktirmeden önce GPU'da `[vocals, drums+bass+other]`'a indirgenir;
    CPU biriktiricisi 2 katman tutar (≈ 2,95 GiB).
  - Referans tensör ortalama/standart sapma alınır alınmaz bırakılır; girdi çıkarımdan (inference) sonra bırakılır; CPU
    örtüşme ağırlığı bir kez kurulur; yazmadan sonra `del sources, model`, `gc.collect()`, `torch.cuda.empty_cache()`.
  - Matematik korundu: `no_vocals = no_vocals * std + 3 * mean`, çünkü vokal olmayan üç katmanın her biri ortalamayı
    eskiden ayrı ayrı alıyordu.
- **Ölçüldü (75 dk'lık dosya):**

| Ölçüt | Eski işçi | İki katmanlı işçi | Uygulamaya entegre |
|---|---|---|---|
| İşçi toplamı | 11 dk 48.5 s | 5 dk 52.1 s | 6 dk 2.2 s |
| Çıkarım | 6 dk 1.4 s | 5 dk 18.8 s | 5 dk 22.9 s |
| Çıktı hazırlama + yazma | 5 dk 36.5 s | 24.9 s | 30.1 s |
| Torch CUDA tepesi | 1689 MiB | 1670 MiB | 1694 MiB |

  - Süreç ağacı RAM tepesi: ilk iki katmanlı deneme 9,52 GB (sistem %93'te); erken bırakmayla 7,15 GB (sistem %80'de,
    yeni takas (swap) yok). Eski işçide süreç ağacı RAM telemetrisi (ölçüm verisi) yoktu, bu yüzden onun için sayı
    iddia edilmiyor.
  - GPU ortalaması %87; cihaz VRAM'i (ekran kartı belleği) ortalaması 2628 MiB, tepe 2749 / 4096 MiB.
  - 395 milyon PCM16 örneğinin hepsi karşılaştırıldı: vocals aynı; no_vocals'ta 534 örnek 1 adım farklıydı.
- **Hâlâ açık:** eşzamanlı iki uzun Demucs çalıştırması hiç test edilmedi; politika aynı anda tek Demucs işçisi.

### 3.3 Süre nereye gidiyor (7. adımdan önceki profil)

Model yükleme 0,7 s, ses yükleme 10,5 s, çıkarım 8 dk 8,5 s, iki katmanı yazma 5 dk 25 s; rapordan sonra sürecin
kapanması ≈ 58 s; `asr_ready` dönüşümü ≈ 25 s. GPU, WAV yazımı sırasında boşta beklediği için çağrının tamamında ortalama
%49'da kaldı. Ders: işçi süresi ve uygulama süresi farklı sayılardır; ikisini de ölç.

## 4. İşçi süreci ayarları

- Aynı ortamın `sys.executable`'ı ve mutlak bir betik yoluyla başlatılır.
- Ortam: `PYTHONHASHSEED=0`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`,
  `TORCH_HOME=<model cache>`.
- Uzun yazımlar sırasında masaüstü kullanılabilir kalsın diye Windows önceliği `BELOW_NORMAL` (matematiğe etkisi yok).
- İlerleme işçinin stdout'undan ayrıştırılır; zaman aşımı 1800 s, sonra süreç sonlandırılır ve iş başarısız olur.
- Hatta Demucs ile transkripsiyon arasında sabit bir 3 s bekleme var. Bunun için gerekçe ya da ölçüm kaydedilmedi.

## 5. Demucs hiç çalışmalı mı? Otomatik arka plan algılama

- **Sorun 1:** Demucs uzun girdilerde dakikalar alır ve temiz konuşma için gereksizdir.
- **Sorun 2:** Demucs tanımaya **zarar verebilir**. 85 s'lik bir Çince klipte vokal katmanı gerçek konuşmayı kaybetti ve
  transkript olay etiketlerine indirgendi; doğrudan 16 kHz mono ses içeriği geri getirdi (ölçüldü).
- **Sorun 2'den çıkan kural:** Demucs'tan sonra kelimeler eksikse, tanıyıcıyı ya da modeli değiştirmeden önce aynı
  videonun doğrudan sesini aynı tanıma ayarlarıyla karşılaştır.
- **Çözüm (`auto_background`, `arka_plan_sesi_olcumu.py`):**
  - 50 ms'lik kareler; dinamik aralık = 95. − 5. yüzdelik dilim seviyesi. 32 dB'in altı → arka plan var; −60 dB'in
    altındaki tepe → arka plan değil, sessiz ses.
  - Arka plan varsa Demucs yalnız karışım için `no_vocals` üretmek üzere çalışır; tanıma **ham** 16 kHz mono sesi kullanır.
- **Kalibrasyon (ölçüldü):** Demucs katmanları olan önceki çalıştırmalardan oluşan bir kümede, belirgin arka planlı
  durumların 0'ı kaçırıldı ve kesinlik ≈ %90'dı. ≈ 917 dakikalık sesin ölçülmesi 24 s sürdü. 12 İngilizce klipte ham ve
  Demucs transkriptleri %0–3,2 farklıydı. 30 s'lik pencerelere bölmek grupları daha kötü ayırdı (%85–89) ve bazı uzun
  girdilerde hem temiz hem müzikli pencereler vardı; bu yüzden tek bir sayı uzun videolarda yanıltabilir.
- **Sınırlar:** kalibrasyon klipleri en fazla 4 dk, yalnız İngilizce, tek tanıyıcı, doğruluğu bilinen (ground-truth)
  transkript yok.

## 6. ASR girdi biçimi

- WhisperX için 44.1 kHz stereo `clean_source.wav` ve 16 kHz mono `asr_ready.wav`, 4 çalıştırmada aynı metni, segment ve
  kelime sayılarını ve aynı zaman damgalarını verdi (ölçüldü); bu yüzden WhisperX temiz kaynağı doğrudan okur. Diğer
  motorlar hâlâ 16 kHz mono alır.
- Listelenen motorlar için başa 1,0 s'lik dolgu eklenir; altyazı dosyası kaynakları için kapalıdır.

## 7. Düşük VRAM ayarları özeti

| Ayar | Değer |
|---|---|
| Model | `htdemucs` |
| Batch | 4, gerçek bir CUDA OOM'undan sonra 1 ile tek yeniden deneme |
| Overlap / shifts | 0.25 / 0 |
| Segment | verilmez (model varsayılanı 7.8 s) |
| Asla ayarlanmaz | `CUDA_LAUNCH_BLOCKING`, `cudnn.benchmark=True` |
| Bütçe | 75 dk ses için ≈ 2.75 GB VRAM cihaz tepesi, ≈ 7.2 GB süreç ağacı RAM'i |
