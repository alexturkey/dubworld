# TTS, zamanlama ve karışım

English: [../engineering/tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md)

Türkçe konuşmanın nasıl sentezlendiği (TTS: metinden konuşma üretimi), süresinin kaynakla nasıl eşleştirildiği ve arka
planla nasıl karıştırıldığı.
Karar kaydı: [ADR 0010](kararlar.md#0010).

## 1. TTS mimarisi (üç katman)

- **Motor kutusu:** metin → dalga biçimi + örnekleme hızı; kendi ses, tohum (seed: aynı sonucu yeniden üretmeyi sağlayan
  rastgelelik başlangıç değeri) ve hız mantığıyla. Asla aday seçmez, onarım kararı vermez ya da başka bir motorun
  ayarlarını ödünç almaz. Bir motor kutusunu silmek yalnız o motoru bozar.
- **Yürütme katmanı:** son sesi hazırlar, ortak son işlemeyi uygular ve kararlarda kullanılan tek süre olan
  `processed_duration` değerini **fiziksel olarak ölçer**. Bir motorun kendi süre tahmini yalnız motor onu gerçekten
  biliyorsa kaydedilir.
- **Zamanlama/onarım katmanı** (motordan bağımsız): kabul bandı, `too_short_audio` / `too_long_audio`, onarım turları,
  kabul edilmiş segmentlerin yeniden kullanımı. Bant: ima edilen video hızı **0,90–1,15** (1,15'in üzerinde ses çok kısa,
  0,90'ın altında çok uzun).

## 2. Supertonic

### 2.1 Ses başına sabit hız (dinamik hız kaldırıldı)

- **Sorun:** genel bir hız (1.20) ve daha sonra segment başına dinamik bir hız (0.85–1.45) yanlış ses üretti: düşen son
  kelimeler, yer değiştiren ya da tekrarlanan heceler, alakasız ifadeler. Çalışan bir hız yakın bir değerde başarısız
  olabiliyordu ve altyazı yine de metnin tamamını gösteriyordu.
- **Kök neden:** Supertonic `speed` sonradan yapılan zaman esnetmesi değil, model içi bir sentez parametresidir; onu
  değiştirmek modelin ne ürettiğini değiştirir. Zorlamalı hizalama (forced alignment: beklenen metni sese oturtma)
  beklenen metni sesin üzerine yerleştirir, bu yüzden eksik konuşmayı fark etmez.
- **Çözüm:** ses başına tek sabit hız:

| Ses | F1 | F2 | F3 | F4 | F5 | M1 | M2 | M3 | M4 | M5 |
|---|---|---|---|---|---|---|---|---|---|---|
| hız | 1.30 | 1.15 | 1.30 | 1.00 | 1.15 | 1.15 | 1.00 | 1.00 | 1.15 | 1.25 |

  Bilinmeyen bir ses hata fırlatır. Tohum dil + ses + adım + metnin SHA-256 özetidir; hız tohumun parçası değildir, bu
  yüzden testte onaylanan ses birebir yeniden üretilir.
- **Kabul testi:** her ses aynı 5 Türkçe metni ayrı dosyalara okur, her biri ayrı ayrı metne dökülür; bir hız yalnız
  normalleştirmeden sonra 5'inin de eşleşmesi halinde kabul edilir. Yeni bir hız ya da ses aynı 5/5'i geçmek zorundadır.
- Süre referansı (≈ 90 kelimelik paragraf, 1,00×): seslerin çoğu 44–47 sn; en kısalar F4 40,7 sn ve M3 39,0 sn, en uzun
  F3 48,2 sn; süre 1/hız oranına yakın ölçeklenir.

### 2.2 CPU hızı (ONNX Runtime)

Kısıtlar: hız, adım, ses, tohum ve aday sayısı değişmez; ses ve kelime sınırları bayt bayt aynı kalmalı.

Reddedilenler (ölçüldü): CUDA yürütme sağlayıcısı (tek uzun metinde çok daha yavaş ve paralel kullanım
`cudaErrorStreamCaptureUnsupported` ile başarısız oldu); DirectML (yeniden biçimlendirme (reshape) hatası); OpenVINO
(başarısız ya da daha yavaş, NumPy'nin sabitlenmesini gerektiriyor); elle toplu işleme (dalga biçimlerini değiştirdi);
`quantize_dynamic` (hiç nicemlenmiş işlem üretmedi, "kazanç" gürültüydü); 4'lü süreç havuzu (CPU çekişmesi).

Kabul edilenler, birikimli: 2 iş parçası içi (intra-op) iş parçacığıyla 2–4 paralel şerit (son: **4 şerit × 2 iş
parçacığı**, 192 gerçek sentezde hiç geçilemedi); şeritler başlamadan önce hazırlanan tek ortak dikkat (attention)
modeli; döngüde bekleme (spinning) kapalı; onarım turları arasında oturum yeniden kullanımı (2. tur: 8,27 → 1,39 sn);
besleme sözlüğü (feed-dict) yeniden kullanımı (1,17×); en iyileştirilmiş ORT model önbelleği (1,22–1,26×; oturum kurulumu
3,9 → 2,2 sn, tepe RSS ≈ 3,0 → 1,8 GB); bellek deseni seçenekleri kapalı (1,13×); vektörleştirilmiş kırpma. Windows süreç
havuzları `if __name__ == "__main__"` korumasına ihtiyaç duyar; bir onarım turunun içinde paralelleştir, turlar arasında
asla.

### 2.3 Geçerli sentez tarifi ("K15")

- Fabrika ayarı 8 adımlı örneklemenin kalite kusurları vardı; temiz 22 adımlı bir tarif pahalıydı. 16 tarif ASR (otomatik
  konuşma tanıma) WER'i (kelime hata oranı) ve dinlemeyle puanlandı; seçilen tarif temiz referanstan ≈ %52–54 daha ucuz
  ve test paragrafında %0 WER.
- Süre tahmincisi bir kez çalışır; hedef uzunluk = tahmin edilen uzunluk / profil hızı; normal uzunlukta 7 Euler adımı,
  gizil temsilin (latent) hedef uzunluğa doğrusal ara değerlemesi, sabit bir zaman ızgarasında 3 adım daha (toplam 10);
  CFG 5 (bellekte yamalı, diskteki ağırlıklara dokunulmadı, ayrı en iyileştirilmiş önbellek).
- Tarif kimliği çalışma zamanı, aday önbelleği ve ara kayıt (checkpoint) anahtarlarının parçasıdır; onu değiştirmek
  TTS'i yeniden üretir ama kaynak, ASR ve çeviriyi korur.
- Doğrulandı: daha önce kabul edilmiş kayıtlar 1.2e-7 içinde yeniden üretiliyor; 10 sesin tamamı sonlu, gerçek tepe
  −1,1 dBTP'nin altında.

### 2.4 Vokoderden önce kaldırılan sessizlik "gölgeleri"

- **Sorun:** konuşma sınırlarında konuşmadan 45–60 dB aşağıda, kulaklıkla duyulabilen hafif bir tıslama.
- **Kök neden (gizil kareleri tek tek çözerek ölçüldü):** kareler sessizlik (< −95 dB), konuşma (> −50 dB) ya da
  kararsız (−63 … −80 dB) oluyor. Model geçişlerde "ne konuşma ne sessizlik" karelerini yazıyor ve vokoder (gizil
  temsili dalga biçimine çeviren bölüm) onları sadakatle işliyor; vokoderin kendisinin suçsuz olduğu kanıtlandı.
- **Reddedilenler:** sonradan kare sıfırlama (kelime kuyruklarını kesme riski), CFG/tohum/gürültü/adım değişiklikleri
  (gölge yer değiştirdi), sessizliğe doğru harmanlama, sessizliği örnekleyicinin içinde sabitleme (tını kaybı), ortalamayı
  sessizlik olarak kullanma (uğultu).
- **Çözüm:** vokoder 1. geçiş → tepenin 20 dB altındaki kareler aday olur → tek toplu çözümde sınıflandır → sessizlik
  karelerini, çok sessiz kareleri ve sessizliğe komşu kararsız kareleri maskele (yayılımla) → tek bir kanonik sessizlik
  gizil temsiliyle değiştir (SHA-256 doğrulamalı) → yalnız bir şey değiştiyse vokoder 2. geçiş. Konuşma karelerine,
  süreye ve zamanlamaya asla dokunulmaz.
- **Ölçüldü:** temizlenen kareler −64…−84 dB → −85…−108 dB; bir kelimeden sonraki ilk 150 ms −67,6 → −82,9 dB; konuşma
  düzeyi değişimi ≤ 1,6 dB; bedel +%15–20.
- **Açık:** ünlülerde perdeye kilitli 5–11 kHz vızıltı.

### 2.5 Süreç yaşam döngüsü

- **Sorun:** 58 sn'lik bir video TTS'te 445 sn geçirdi. Sentez, uzun ömürlü bir sürecin bir iş parçacığında çalışıyordu;
  bu sürecin genel bağlamları önceki işlerden kalma ses × şerit başına tam bir ONNX oturumu tutuyordu; özel bellek fiziksel
  RAM'i aştı.
- **Çözüm:** istek başına (ses grubu başına) tek işçi alt süreci, genel havuz yok; sonuçlar SHA-256, biçim (shape), veri
  türü (dtype) ve sonluluk ile doğrulanan float32 NPY olarak döner; ebeveyni kaybolursa işçi kapanır.
- **Ölçüldü:** çıktılar bayt bayt aynı; ana süreç 54–59 MB; eşleştirilmiş yeniden çalıştırmalarda toplam 269 → 200 sn,
  398 → 307 sn ve 646 → 203 sn (çeviri de farklıydı, bu yüzden kazancın tamamı bu değişikliğe yazılmaz). Bedel: her istek
  model yüklemesini öder.

### 2.6 Emekliye ayrılan zaman kaynakları

Supertonic'in iç dikkat haritasından gelen kelime zamanları ve baştaki/sondaki sessizliğin RMS (ses yüksekliği) kırpması
başlangıçta kullanılıyordu. Kaydılar ve yapısal tokenların üzerine çökebildiler; kaldırıldılar. **Tek zaman kaynağı
zorlamalı hizalamadır.**

## 3. Aday hizalama (üretilen konuşmayı zamanlama)

- Adaylar gerçek sessizlik ayırıcılarıyla şeritlere birleştirilir, her şerit bir kez hizalanır ve sonuç segment başına
  geri bölünür. Doğrulanmış aday kelime zaman çizelgeleri video zaman çizelgesine eşlenir ve altyazı için yeniden
  kullanılır; bunlar varsa son yeniden hizalama atlanır.
- Aşırı hevesli bir değişiklik bir kez kesimleri bir sonraki hizalanmış kelimeye bağladı ve fiziksel sessizlik çitini
  düşürdü, bu yüzden komşu segmentlerin sesi birbirine taştı; geri alındı. Kural: tek segmentli ≤ 30 sn şeritler tek
  pencere kullanır; kısa çok segmentli şeritler ve > 30 sn şeritler fiziksel parça başına bir pencere alır (gerçek parça
  metninden ve örnek sayılarından kurulur).
- **Sınır toleransı (ölçüldü):** son kelimeler pencere sonunu ≈ 20 ms, ilk kelimeler 0,1–0,3 ms aştı. İlke: başlangıç
  toleransı 5 ms; yalnız son kelimenin bitişi en çok 25 ms aşabilir ve sıkıştırılır; başka her aşım adayı geçersiz kılar
  (asla sessizce kırpılmaz). Ayrıştırma (demux) tam sayı örneklerle çalışır; dışarıda > 1 örnek kesin hatadır.
- **Token toleransı:** 362 segmentlik bir iş, hizalayıcı harf harf okunan beklenen `P İ E C` kısaltması için `P E C`
  döndürdüğü için öldü. Kaynak sorunu değildi (620 MB ayrılmış, dönüş kodu 0). Kural: ilk olmayan, tam olarak bir eksik
  tek karakterli token, bütün kelimeler 1:1 eşlenmiş ve yerel boşluk pozitifse o boşluğa yerleştirilir; geri kalan her şey
  (eksik normal kelime, sıra değişimi, ≥ 2 eksik, negatif ya da çakışan zamanlar) ölümcül kalır.

## 4. Süre eşleştirme

### 4.1 İsteğe bağlı atempo (önerilen akışta bir ayar)

- Mono float32 üzerinde saf `atempo=<factor>` süzgeci (atempo: perdeyi değiştirmeden sesi hızlandırma/yavaşlatma): EQ,
  perde ya da ses yüksekliği süzgeci yok.
- `required = processed_duration / target_duration`; kapalı bant **0,90–1,25**; çarpan 6 ondalık basamağa yuvarlanır;
  1.0 işlem yapmaz.
- Onarımsız kipler: en iyi aday atempo kapalıymış gibi seçilir, sonra çarpan banda sıkıştırılır; yalnız seçilen aday
  işlenir. Onarımlı kipler: yalnız zaten bandın içindeki adaylar uygun sayılır, 1,00'a en yakın olan kazanır.
- İkinci hizalama yok: kelime zamanları `out_duration / pre_atempo_duration` ile doğrusal ölçeklenir.
- Varyantlar aday, segment, hedef örnek sayısı ve çarpana göre anahtarlanır; böylece farklı segmentlerdeki aynı metin
  asla birbirinin sesinin üzerine yazmaz.
- Bandı değiştirmek gerçek süre ve perde testlerinin yeniden çalıştırılmasını gerektirir.

### 4.2 Kalanı video emer

- `video_speed = original_duration / tts_duration`; video `trim` + `setpts` ile yeniden zamanlanır. Segmentler arasındaki
  boşluklar kendi zaman çizelgesi öğeleri olarak tutulur, böylece duraklamalar korunur.
- Kaynak ses (arka plan) yeniden zamanlandığında, 2.0'ın üzerindeki ya da 0.5'in altındaki atempo çarpanları zincirleme
  adımlara bölünür.
- Düzeltilen hata: toplam süre video akışından değil kapsayıcıdan (container) alınıyordu (195,05 ile 194,93 sn) ve bu
  yapay bir 1,5 sn'lik son toplu iş yaratıyordu. Her zaman `v:0` akış süresini kullan ve kısa bir son toplu işi bir
  öncekiyle birleştir.

## 5. Ses yüksekliği

- **Sorun:** son dublajlar sessizdi (bütünleşik −23 ile −26 LUFS arası; LUFS: algılanan ses yüksekliği ölçüsü).
- **Denenenler:** kazanç + sınırlayıcı (kulakla yetersiz); konuşma normalleştirme + loudnorm + sınırlayıcı (daha yüksek
  ama sıkıştırıcı/EQ varyantları çatırdadı).
- **Yolda bulunan:** Supertonic 44,1 kHz üretiyor ama hattın varsayılanı 24 kHz'ti, bu yüzden ses boş yere yeniden
  örnekleniyordu. Örnekleme hızı artık motoru izliyor.
- **Geçerli (karakteri koruyan):** loudnorm **yalnız ölçmek için** kullanılır; dosyanın tamamına tek bir sabit kazanç
  uygulanır: `gain_dB = min(−18 − LUFS, −1.3 − true_peak_dBTP)`. Hedef ≈ −18 LUFS, tasarım tavanı −1,3 dBTP, kabul
  −1,1 dBTP. EQ, sıkıştırıcı ya da sınırlayıcı yok. Ara dosyalar float WAV'dır, böylece kazançtan önce hiçbir şey kırpılmaz
  (clip). Her çıktı bir `.gain.json` alır.

## 6. Arka plan karışımı

- Ayrıştırılmış `no_vocals` izi yeni zaman çizelgesine yeniden zamanlanır ve dublajla
  `amix=inputs=2:duration=longest:normalize=0` kullanılarak karıştırılır (otomatik normalleştirme yok, konuşma sırasında
  arka planı kısma (ducking) yok). Supertonic için sınırlayıcı yok: float toplam yazılır ve §5'teki sabit kazanç uygulanır.
- **Bellek düzeltmesi (ölçüldü):** segment WAV'ları önbelleğe alınmak yerine gerektiğinde okunur ve tepe taraması
  65.536 örneklik bloklarla çalışır: 15 dakikalık ses 606 → 154 MiB tepe (−%75), çıktı SHA-256 değişmedi.
- **Açık:** tüm zaman çizelgesinin karışım dizisi hâlâ bellekte tutuluyor (akış halinde değil); ölçülmüş bir arka plan
  düzeyi ya da kısma hedefi yok.

## 7. Bu repoda VoxCPM2

VoxCPM2 buradaki ikinci TTS motorudur (Apache-2.0 kod ve ağırlıklar). Kendi ortamında tek oturumluk bir alt süreç olarak
çalışır ve sonuçları Supertonic ile aynı sözleşmede döndürür. Bu hattaki ölçümler: **henüz kayıt yok**.
VoxCPM2'yi aynı 4 GB kartta çalıştırmaktan çıkan ilgili bir ders: üretici artı ses VAE'si 4 GB'a yaklaştığında
≈ 1,2 GB paylaşılan belleğe taştı ve üretim hiçbir hata vermeden 70 sn'den 171 sn'ye yavaşladı; paylaşılan bellek kuralı
için bkz. [gpu_bellek_ve_yalitim.md](gpu_bellek_ve_yalitim.md).

## 8. Kaldırılmış bir motordan dersler (XTTS v2)

XTTS v2 daha sonra farklı bir bütünleştirmeyle isteğe bağlı motor olarak geri eklendi (ayrı alt süreç, isteğe bağlı
ayrı ortam, lisans onayı, kullanıcının referans sesi, aday ve `atempo` adımı yok): [ADR 0015](../adr/0015-tts-engine-set-and-default.md),
[motorlar/xtts.md](../motorlar/xtts.md). Aşağıdaki dersler önceki, aynı süreç içi bütünleştirmeden gelir.

- Her "bariz" GPU hızlandırması Pascal'da kaybetti: `cudnn.benchmark` 3,4 kat daha yavaş, `torch.compile` 3,1 kat daha
  yavaş, fp16 autocast %14,5 daha yavaş, `model.half()` vokoderi bozdu, INT8 yalnız CPU'da ve daha yavaş.
- İşe yarayan, "GPU verimli besleniyor mu?" diye sormaktı: çözme saniyede 25 token hızla çalışıyordu, bellek bant
  genişliği sınırı ise ≈ saniyede 64 token. Dikkat uygulamasını birleşik (fused) `scaled_dot_product_attention` ile
  değiştirmek (aynı matematik) bir kıyaslamada +%22,6, üretimde +%17,5 kazandırdı.
- Hat aday zaman çizelgelerine geçtikten sonra bir altyazı kapısı eski bir hizalama dosyasını istemeyi sürdürdü; eski bir
  test o dosyayı uydurarak hatayı gizledi. Ders: tüketiciler sürümlü bir sözleşmeyi okumalı ve testler ön koşulları
  uydurmamalı (bkz. [video_altyazi_ve_devam.md](video_altyazi_ve_devam.md)).

## 9. Açık maddeler

- Geçerli tarifle üç Supertonic şeridi hiç ölçülmedi.
- atempo varyantı yeniden kullanımı yalnız anahtarı ve hizalama başarısını denetliyor, temel adayların tam doğrulamasını
  değil.
- 5–11 kHz'de ünlü vızıltısı; akış halinde karışım; arka plan düzeyi hedefi.
