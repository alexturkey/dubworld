# Transkripsiyon motorları (CrisperWhisper hariç)

English: [../engineering/transcription.md](../engineering/transcription.md)

Her konuşmadan metne (transkripsiyon, konuşmayı yazıya dökme) motoru hakkında öğrenilenler: 4 GB'lık bir kartta ayarlar,
hatalar, hız ve doğruluk. CrisperWhisper'ın kendi sayfası var: [crisperwhisper_turbo_ct2.md](crisperwhisper_turbo_ct2.md).

Kod: `src/dublaj_hatti/bolum_20_transkripsiyon/<engine>/`. Ayar: `[transkripsiyon] motor`.

## 0. Motor etiketleri

Eski belgeler ve günlükler motorlara menü numarasıyla atıf yapar. Burada önemli olanlar: **12** = CrisperWhisper 2 Medium (kaldırıldı),
**13** = CrisperWhisper 2 Turbo CT2, **14** = Moonshine Medium Streaming (kaldırıldı). Numaralandırma bir sunum sırasıdır, kalite
sıralaması değildir.

## 1. 10 dosyalık İngilizce derlemde karşılaştırma (ölçüldü)

3,9 saat ses; referans transkriptler ticari bir motordan (insan değil; onda da sıfır uzunluklu kelimeler var). WER
(kelime hata oranı) derlem düzeyindedir; "start MAE", kelime başlangıç zamanlarının referansa göre ortalama mutlak
hatasıdır.

| Motor | WER | × gerçek zaman | Start MAE | p95 sınır hatası | sıfır uzunluklu kelimeler |
|---|---:|---:|---:|---:|---:|
| Parakeet INT8 (CPU) + CTC | **4.49 %** | 3.8 | 28 ms | 266 ms | 0 |
| WhisperX large-v3-turbo int8 + CTC | 4.67 % | 5.3 | 30 ms | 295 ms | 0 |
| WhisperX large-v3-turbo fp32 + CTC | 4.76 % | 4.3 | 30 ms | 297 ms | 0 |
| faster-whisper distil-large-v3 fp32 | 5.05 % | 6.7 | 123 ms | 501 ms | 899 |
| faster-whisper distil-large-v3 int8 | 5.11 % | 8.9 | 126 ms | 514 ms | 889 |
| distil-large-v3.5 fp32 | 5.64 % | 6.9 | 107 ms | 461 ms | 611 |
| distil-large-v3.5 int8 | 5.84 % | **9.2** | 106 ms | 453 ms | 664 |

- Kısa dosyalar: distil int8, fp32'ye eşit ve daha hızlı. 9–22 dakika: WhisperX int8 önde. ≈ 70 dakika: en iyisi Parakeet.
- Kelime zamanları CTC hizalamasından (CTC zorlamalı hizalama: bilinen metni sesteki zamanlara oturtma) gelen motorlar,
  kelime başlangıçlarında distil'in kendi zaman damgalarından ≈ 4× daha doğrudur.
- Her motor Demucs ile ayrıştırılmış seste daha kötü puan aldı (betimleyici, kontrollü bir test değil).
- VRAM (ekran kartı belleği): distil fp32 3427 / int8 1283 MiB; WhisperX fp32 3451 / int8 1147 MiB; Parakeet VRAM
  kullanmaz (≈ 1,9 GB RAM).
- Bu deneyin ham çıktıları yazıya geçirildikten sonra silindi; yalnız sayılar kaldı.

## 2. faster-whisper

- **Belirlenimsizlik (non-determinism, aynı girdiden farklı çıktı):** aynı ses her çalıştırmada farklı metin verdi (her
  alt süreçte yeni rastgele durum; belirlenimci olmayan CUDA çekirdekleri). Tohumlar + `cudnn.deterministic` segment
  sayılarını sabitledi ama metni sabitlemedi. Çözüm: `torch.use_deterministic_algorithms(True, warn_only=True)` +
  `CUBLAS_WORKSPACE_CONFIG=:4096:8` → kelimesi kelimesine aynı metin; 0,02–0,08 s zaman damgası oynaması kalır ve kabul
  edilir.
- **Pascal'da hesap tipleri:** `int8`, `float32`, `auto` (→ float32) çalışır; `float16` ve `int8_float16` reddedilir.
- medium + int8 bir test dosyasında 29 s konuşmayı düşürdü (medium fp32'nin 219 kelimesine karşı 118 kelime); Türkçede
  large-v3-turbo int8 bir bulut referansının 284 kelimesine karşı 286 kelime verdi, bir medium model ise ilk 15 s
  boyunca bir altyazı jeneriği uydurdu (halüsinasyon). large-v3-turbo çok dilli model oldu.
- **Distil 128 mel bandı ister:** `preprocessor_config.json` içermeyen bir anlık kopya faster-whisper'ı 80 banda düşürdü
  (şekil hatası). Distil modeller için işçi `FeatureExtractor(feature_size=128)` değerini zorlar.
- **Distil çözücü ayarları:** VAD (konuşma etkinliği algılama) kapalı, `condition_on_previous_text=False`, temperature 0,
  beam 5, best_of 5, `word_timestamps=True`, boş başlangıç istemi. Beam 10 aynı metni verdi ve daha yavaştı.
- **Kısa testler yanıltır:** 90 s'de önceki metne koşullama en iyisi gibi göründü; 67 dakikada bir tekrar döngüsüne düştü
  (yerel WER %29); kapatmak genelde %7,9'a karşı %6,0 WER verdi. **Kararı uzun dosyalar verir.**
- fp32'ye karşı int8: 6 dosyanın 4'ünde farklı kelime dizileri; iki ayrı seçenek olarak tutuldu (kaliteye karşı hız).

## 3. WhisperX

- **Ayrı ortam:** kendi torch'u (Windows'ta cu128), pyannote ve TorchCodec ile WhisperX 3.8.6. Kurulumdan dersler:
  karışık paket dizinleri pip'i kilitledi (torch `--no-deps` ile kuruldu); TorchCodec 0.15'te DLL hatası vardı (0.7.0'a
  sabitlendi); TorchCodec 0.7, FFmpeg 8 ile çalışmaz (FFmpeg 7.1 paylaşımlı sürümü kullanıldı).
- **Geçici çözümden önce yükseltme:** WhisperX 3.8.2, hizalamada rakam/simge içeren belirteçleri (token) düşürüyordu; bir
  LLM (büyük dil modeli) ile sözcüğe çevirme katmanı kuruldu, sonra 3.8.6 bunları kendiliğinden hizalayınca kaldırıldı
  (bkz. [kelime_hizalama.md](kelime_hizalama.md)).
- **Batch boyutu (ölçüldü, fp32):** iki uzun dosyada batch 1, batch 2'den **≈ %41 daha hızlıydı** (416.7 → 242.9 s ve
  235.7 → 140.1 s); batch 4 en yavaştı; tekrarlanan bir batch-2 kontrolü ısınma etkilerini eledi; metin aynı. Kural:
  batch boyutunu değiştirmek en az iki uzun dosyada 2 → 1 → 2 kontrolü gerektirir.
- **Çözücü profili (ölçüldü):** `suppress_tokens=[]` ile fp32, 106 s'lik bir klipte WER'i %3,93'ten %0,91'e düşürdü;
  int8 değişmedi. Adlandırma tuzağı: `[]` varsayılan konuşma dışı bastırmayı **kapatır**; `[-1]` varsayılan kümeye açılır.
  İşçi, yüklenen modelin gerçekte kullandığı seçenekleri geri okur ve profilden farklıysa durur. İki çalıştırma bayt
  düzeyinde aynı JSON verdi.
- **OOM (bellek yetmedi hatası):** bkz. [gpu_bellek_ve_yalitim.md](gpu_bellek_ve_yalitim.md) §4. 42 dakikalık bir
  dosyada tekrarlanabilir bir OOM'un açık bir nedeni vardı: GPU'daki pyannote VAD 130 MiB boş bırakıyordu. VAD CPU'ya
  taşındı (onset 0.500, offset 0.363, chunk 30), ≈ 424 MiB boşaldı; dosya aynı metinle tamamlandı (539,6 s, 7.228 kelime).
  Gerçek bir CUDA OOM'u bir kez int8'de yeniden dener.
- **Hizalama hız yamaları:** bir trellis yaması 3.8.2 altında 67 dakikada ≈ 20 s kazandırdı ama 3.8.6 altında bozuldu ve
  kapalı; asıl maliyet hizalama değil, transkripsiyondur.
- 10 kısa videoda fp32'ye karşı int8: 6'sı aynı, 4'ünde küçük değişiklikler; int8 ≈ %11 daha hızlı. Varsayılan fp32.
- **Açık:** aynı dosya için iki farklı ölçüm düzeneğinde açıklanamayan 85 s'ye karşı 416 s farkı.

## 4. Parakeet (CPU) + CTC

- `sherpa-onnx` Parakeet Unified EN 0.6B INT8, yalnız CPU, İngilizce. En iyisi 8 iş parçacığı (96,9 s, 11,9 s'de).
- **Çözücü (ölçüldü, 396 s):** greedy (açgözlü) %11,1 WER; modified beam, 4 yol, blank penalty 2.0 → **%8,4** (seçildi);
  daha yüksek cezalar tekrar uydurur (3.5 → %12,3). 8 yol: aynı WER, %49 daha yavaş. FP32: daha kötü ve 2× yavaş.
- **Aslında girdi sınırı olan "OOM":** tek akış olarak 43 dakika, ONNX'ten 10,4 GB'lık bir MatMul istedi. Kodlayıcı en
  fazla 5000 adım × 80 ms = **400 s** kabul eder: 400.000 s çalışır, 400.080 s kararsız metin verir, 400.160 s şekil
  hatası verir. Mevcut yöntem: tek parçada ≤ 399 s; daha uzun ses 399 s'den önceki son ≥ 600 ms'lik sessizliğin orta
  noktasından kesilir (yoksa sert kesim günlüğe yazılır); parçaların toplamı girdi örnek sayısına eşit olmalıdır. Ders:
  belleği suçlamadan önce tensör şekillerini oku ve tam sınırı test et.
- CTC pencere dersi (tek pencere içinde 6,4 s'lik bir boşluk) [kelime_hizalama.md](kelime_hizalama.md) §3'te.
- **Açık:** dil `auto` olduğunda otomatik dil yoklaması yok; zor, yavaşlatılmış bir klip hâlâ kapalı başarısızlıkla
  (fail-closed) düşüyor.

## 5–7. Kaldırılan motorlar

whisper.cpp (CPU) + CTC, Moonshine Medium Streaming, CrisperWhisper 2 Medium, Speechmatics ve ElevenLabs Scribe v2 üründen kaldırıldı: hiçbiri varsayılan değildi, hiçbiri gerçek sesle uçtan uca denenmemişti ve her biri faster-whisper, Parakeet ya da CrisperWhisper Turbo ile örtüşüyordu. Bölümleri bu sayfadan çıkarıldı; geçmişi git günlüğünde ve `CHANGELOG.md` içindedir. Kayıtlı bir ayar bunlardan birini söylüyorsa yine yüklenir: uyarır ve `auto`ya döner.

## 8. Altyazı dosyası kaynağı (json3)

Altyazı zamanları yalnız pencere ipucu olarak kullanılır; son kelime zamanları CTC'den gelir; kelime listesi 1:1
eşleşmelidir; başta dolgu yok. Zaman aşımı `max(120, 90 + minutes × 8)` s.

## 9. Ortak ayarlar

- **Baştaki dolgu:** ilk kelime kırpılmasın diye faster-whisper, WhisperX ve Parakeet için
  tanımadan önce 1,0 s sessizlik; tam olarak bir kez çıkarılır.
- **Motor başına VAD:** faster-whisper (distil olmayan) Silero 0.5 / 500 ms / pad 300 ms; distil kapalı; WhisperX
  pyannote CPU'da; Parakeet yalnız 399 s üstünde kesim noktası önermek için; CrisperWhisper Silero CPU'da.
- **Dil algılama sırası:** platform/kullanıcı dili → yapılandırılmış dil → motorun otomatik algılaması. Distil (yalnız
  İngilizce) kapısı: `auto` ile 3 VAD segmentinde algıla; distil yalnız dil `en` ve P(en) ≥ 0.90 ise kalır,
  değilse WhisperX turbo fp32'ye geçer (günlüğe yazılır). Ölçüldü: P(en)=0.995 olan İngilizce distil'de kaldı; bir Endonezce klip (P(en)=0.767) geçti ve
  doğru algılandı.
- **Profil çıkarma:** her çalıştırma başarısızlıkta bile `transcription_profile_<engine>.json` yazar (adım başına süre ve
  tepe CUDA belleği, çözücü profili, VAD sağlayıcısı/cihazı).

## 10. Motorlar arası dersler

1. Önceki metni çözücüye geri besleme (`condition_on_previous_text=False`, `max_context=0`): bu, üç motorda tekrar
   döngülerini ortadan kaldırdı.
2. 4 GB'lık Pascal kartta: daha küçük batch'ler, VAD CPU'da, fp16 yok ve int8, fp32'ye eşdeğer değildir.
3. Bir "OOM", bir girdi uzunluğu sınırı ya da GPU'yu paylaşan iki bileşen olabilir.
4. Metin doğruluğunu ve zamanlama doğruluğunu ayrı ölç; hiçbir kelimenin kaybolmadığını doğrula.
5. Sürümleri sabitle ve bir yükseltmeden sonra her yamayı yeniden kontrol et.
6. Kendi zaman damgalarını asla yerinde onarma; kapının onları reddetmesine izin ver.
7. Kabul tam uzunlukta ses ister: döngüler, zamanlama ters dönmeleri ve 400 s sınırı yalnız uzun dosyalarda ortaya çıktı.
