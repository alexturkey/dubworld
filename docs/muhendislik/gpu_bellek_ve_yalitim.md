# GPU belleği, süreç yalıtımı ve kaynak kilidi

English: [../engineering/gpu_memory_and_isolation.md](../engineering/gpu_memory_and_isolation.md)

Bu sayfa, hattın her GPU (ekran kartı işlemcisi) modelini 4 GB'lık bir karta nasıl sığdırdığını, OOM (out-of-memory,
bellek yetmedi hatası) hatalarının nasıl teşhis edilip düzeltildiğini ve bu çalışmadan hangi kuralların çıktığını
anlatır.

Her mühendislik sayfasında kullanılan kanıt etiketleri:

- **ölçüldü**: proje bunu çalıştırdı ve sayıları sakladı. Aksi belirtilmedikçe: 4 GB VRAM'li (ekran kartı belleği),
  Pascal sınıfı GPU (compute capability (hesaplama yeteneği sürümü) 6.1), Windows, 16 GB sistem RAM'i.
- **belgelendi**: kural ya da bulgu olarak yazıldı, sayının arkasında saklanmış bir çalıştırma yok.
- **kayıt yok**: hiçbir şey bulunamadı; bilinmiyor say.

## 1. Kartın yapabildikleri ve yapamadıkları (ölçüldü)

| Olgu | Sonuç |
|---|---|
| fp32 ≈ 1,86 TFLOPS, fp16 ≈ 1,77 TFLOPS (Pascal'da Tensor Core yok) | fp16 **hızlanma sağlamaz**; yalnız bir modeli sığdırmak için kullan |
| bf16 öykünmeyle (emülasyon) çalışır (≈ 1,03 TFLOPS) | bf16'yı asla kullanma |
| int8 matris çarpımı (dp4a) ≈ 8,16 TOPS, ≈ 4,4× fp32 | asıl hız kaldıracı int8 |
| CTranslate2'nin bu kartta `float16` hesaplaması yok | CT2 motorları `int8`, `int8_float32` ya da `float32` kullanır |
| CUDA 11.8 ve 12.x çalışır; CUDA 13 paketleri (wheel) sm_61'i bıraktı | cu13x torch sürümleri kurma; `nvidia-smi`'nin gösterdiği "CUDA 13.0" yalnız sürücünün üst sınırıdır |
| `torch.compile` / Triton çalışmaz | bunları açma |
| Linux `torch 2.8.0+cu128` paketlerinde sm_61 çekirdeği yok; `torch.cuda.is_available()` yine de True döner ve ilk matris çarpımı "no kernel image is available" hatasıyla düşer (Windows cu128 paketi sm_61 içerir) | Linux'ta cu126 sürümüne sabitle; sağlık kontrolü yalnız `is_available()` değil, gerçek bir CUDA matris çarpımı çalıştırmalı |

## 2. Model başına ölçülen VRAM tepeleri

| Model / aşama | Hassasiyet | Tepe VRAM |
|---|---|---|
| Demucs `htdemucs`, batch 4 (75 dk ses) | fp32 | ≈ 2.75 GB cihaz, torch'un ayırdığı ≈ 1.69 GB |
| WhisperX large-v3-turbo | fp32 / int8 | 3451 MiB / 1147 MiB |
| faster-whisper distil-large-v3 | fp32 / int8 | 3427 MiB / 1283 MiB |
| CrisperWhisper Turbo (CTranslate2) | int8 | ≈ 1.4 GB |
| CTC kelime hizalama (wav2vec2) | fp32 | dil modeline göre ≈ 1.65–2.4 GB'a kadar |

Model dosya boyutu VRAM ihtiyacı değildir: 213 MB ağırlığı olan bir konuşma iyileştirme modeli 10,45 GB
`max_memory_allocated` değerine ulaştı (ölçüldü). Bir model eklemeden önce her zaman tepe belleği ölç.

## 3. OOM çalışmasından çıkan kurallar

1. **Aynı anda tek GPU işi.** İki CTranslate2 işi birlikte sığar, ama her biri ≈ 1,95× daha uzun sürer ve toplam
   işlem hacmi yalnız ≈ %2,6 artar (ölçüldü). Eşzamanlılık OOM riskine değmez.
2. **Her ağır model kendi alt sürecinde çalışır** (Demucs, WhisperX, faster-whisper, CTC hizalama, cinsiyet
   sınıflandırıcı, TTS işçisi, CrisperWhisper). Süreç çıkınca sürücü bütün belleğini geri verir.
   Uzun ömürlü bir GUI/web sürecinin içinde parçalanma ve geride kalan CUDA durumu birikir ve `empty_cache()`
   bir OOM'dan sonra süreci güvenilir biçimde toparlamaz (belgelendi).
3. **İki model kartı asla paylaşmaz.** Bir motorun iki modele ihtiyacı olduğunda (dil tanıma + transkripsiyon,
   ASR (otomatik konuşma tanıma) + hizalama) bunlar art arda gelen süreçlerde çalışır.
4. **Her işçide `cudnn.benchmark = False`.** Bu kartta benchmark kipi bir modeli ≈ 200× ve bir başkasını ≈ 3,4×
   yavaşlattı (ölçüldü); gerçek bir denemede Demucs'a kazanç sağlamadı.
5. **`CUDA_LAUNCH_BLOCKING=1` asla ayarlanmaz.** Kaldırılması Demucs'u aynı VRAM ile %19 hızlandırdı (ölçüldü,
   88 dakikalık girdi).
6. **Batch boyutunu ölç, asla varsayma.** WhisperX fp32 batch 1'de batch 2'den ≈ %41 daha hızlıydı; CT2
   kodlayıcısı batch 2 ya da 4'ten hiçbir şey kazanmadı; Demucs batch 4'te ≈ %23 kazandı (hepsi ölçüldü).
7. **İkincil işi CPU'ya taşı.** pyannote VAD'ın (konuşma etkinliği algılama) CPU'ya alınması, fp32 bir ASR modelinin
   yanında ≈ 424 MiB boşalttı ve bir OOM'u aynı çıktıyla tamamlanan bir çalıştırmaya çevirdi (bkz.
   [transkripsiyon.md](transkripsiyon.md)).
8. **Sessiz paylaşılan bellek taşmasına dikkat.** VRAM taştığında Windows WDDM sürücüsü PCIe üzerinden sistem RAM'ine
   taşar; iş 2–8× yavaşlar ve `nvidia-smi` bunu göstermez. Belirti: `torch.cuda.max_memory_reserved()` ≈ 3,9 GB'ın
   üstünde ya da Görev Yöneticisi'nde büyüyen bir "Paylaşılan GPU belleği" sayacı. Belgelenmiş bir koruma
   `torch.cuda.set_per_process_memory_fraction(0.86)`; böylece iş taşmak yerine hata verir; henüz **koda
   bağlanmadı**.
9. **`nvidia-smi` bir sürecin CUDA bağlamını kaçırabilir** (≈ 700 MB). Gerçek boş bellek için
   `torch.cuda.mem_get_info()` kullan.
10. **Sık yüklenen modelleri SSD'de tut.** Soğuk `import torch` SSD'den ≈ 10 s, HDD'den 38–44 s sürdü; HDD'deki
    her 1 GB ağırlık soğuk başlangıca ≈ 12 s ekledi (ölçüldü).

## 4. Aralıklı WhisperX OOM'u: tahmin değil, teşhis

- **Sorun:** WhisperX dil algılaması (`detect_language → model.encode`, large-v3-turbo fp32, batch 1) zaman zaman
  `CUDA failed with error out of memory` ile düştü. Aynı ses ve ayarlar daha sonra taze bir işçide başarılı oldu.
- **Kök neden:** **kanıtlanmadı.** Video uzunluğu, dosya ve ayarlar tek neden olarak elendi. Geriye kalan
  hipotez, 4 GB sınırında geçici GPU durumu ya da ayırma sıçramaları.
- **Tahmin yerine kurulan:**
  - Üst süreç, çalıştırma klasörüne `before_worker`, `after_worker`, `worker_failure` ve `worker_timeout`
    olaylarıyla `gpu_diagnostics.jsonl` yazar (tam `nvidia-smi` çıktısı artı torch free/total/allocated/reserved;
    `nvidia-smi` yoksa da güvenli).
  - İşçi, başarısızlıkta bile `transcription_profile_whisperx.json` yazar: PID, üst süreç PID'i, düşen adım,
    CUDA anlık görüntüleri ve adım başına tepeler.
  - Ayıklama sırası: `profile_summary.failure_stage`/`failure_type` → düşen adımın `cuda_snapshot` değeri →
    `before_whisper_transcribe` ile karşılaştır → PID eşleşmesi → `nvidia-smi` süreç tablosuyla çapraz kontrol.
- **Toparlanma politikası:** float32 bir işçide gerçek bir CUDA OOM'u (mesajda hem "CUDA" hem "out of memory" geçer)
  işçiyi sonlandırır, işletim sistemi VRAM'i boşaltır ve aynı model **bir kez int8'de** yeniden dener. Üçüncü deneme
  yok. Zaman aşımları, JSON, hizalama ya da dosya hataları bu yeniden denemeyi asla tetiklemez. İlk OOM profili
  sonucun yanında tutulur ve çalıştırma üst verisi gerçekte kullanılan hassasiyeti kaydeder.
- **Hâlâ açık:** asıl tetikleyici bilinmiyor.

## 5. Python ortamları: neden birden fazla var

- **Sorun:** motorlar çakışan sürüm sabitlemeleri (pin) ister. Geçmişte ana ortam, kart yüzünden değil, bir TTS
  bağımlılığı yüzünden eski bir torch/numpy çiftinde tutuluyordu.
- **Kural:** yeni bir paket bir ortamın sabitlemelerini değiştirmek isterse kendi yalıtılmış ortamını alır ve
  alt süreç olarak çağrılır. Her kurulumdan sonra ortamı yeniden ölç (torch sürümü, CUDA, cuDNN, temel paketler).
- **Dersler (ölçüldü):**
  - "CUDA 12 bu kartta desteklenmiyor" yanlıştı; yalnızca hiç denenmemişti ve bu yanlış inanç elle yapılmış bir
    DLL geçici çözümüne yol açtı.
  - Windows'ta CTranslate2, paket klasöründeki **her** `*.dll` dosyasını yükler. Elle kopyalanan DLL'ler
    (`cublas64_12.dll` gibi davranan, adı değiştirilmiş bir CUDA 11 cuBLAS; kullanılmayan bir cuDNN 9 takımı) her
    sürece yüklendi. Bunları gerçek `nvidia-cublas-cu12` paketiyle değiştirmek aynı çözme süresini ve bit düzeyinde
    aynı çıktıyı verdi, klasör 2,03 GB'tan 0,61 GB'a küçüldü.
  - torch, sistem genelindekini değil, kendi paketlediği cuDNN'i yükler.
  - Eksik bir `cublas64_12.dll` sessizce ≈ 2× daha yavaş bir yola düşer.
  - CUDA `--index-url` olmadan `pip install torch` CPU sürümünü kurar; bazı paketler (pyannote ve diğerleri)
    kurulum sırasında torch'u CPU sürümüne geri çekti; pip `onnxruntime` yalnız CPU'dur.
  - Üretimdeki çözme ayarlarıyla ölç. faster-whisper varsayılanları sıcaklık yedeğini (temperature fallback)
    içerir; bu, aynı 92,8 s'lik klipte 242–268 kelime verdi (%2–10 metin kayması); üretim ayarları
    `temperature=0.0`, `condition_on_previous_text=False` 6/6 çalıştırmada aynı 241 kelimeyi verdi.
- Bu depo tek bir ana ortamı hedefler; CrisperWhisper Turbo motoru kendi WSL ortamını tutar
  (bkz. [crisperwhisper_turbo_ct2.md](crisperwhisper_turbo_ct2.md)).

## 6. Model önbelleği: tek kök

- **Sorun:** aynı ağırlıklar iki kez indirildi (ayrı bir `TRANSFORMERS_CACHE`, kullanıcı profilinde bir önbellek,
  proje kökünde başıboş bir kopya).
- **Çözüm:**
  - `huggingface/hub`, `torch/hub/checkpoints`, `modelscope/hub` içeren tek kök `runtime_assets/model_cache/`.
  - `HF_HOME`, `HF_HUB_CACHE` (= `TRANSFORMERS_CACHE`, aynı klasör) ve `TORCH_HOME`, torch/whisperx/faster-whisper
    içe aktarılmadan **önce** alt sürecin ortamında ayarlanır; bu kütüphaneler bunları içe aktarma anında okur.
  - Hızlı yol: yerel anlık kopyayı yükle (`local_files_only=True`). Başarısız olursa bildirim dosyasındaki (manifest)
    SHA-256 değerlerini doğrula, yalnız eksik ya da bozuk dosyaları yeniden indir, bir kez yeniden dene, sonra açık
    bir mesajla hata ver. Sonsuz onarım döngüsü yok.
  - Diskteki bir anlık kopya, bellekte duran bir model değildir; işçiler, işçiyle birlikte ölen süreç içi bir önbellek
    tutar.
  - Kopyalar ancak SHA-256 eşitlik kontrollerinden ve gerçek bir çevrimdışı yüklemeden sonra silindi.

## 7. Kaynak kilidi (GPU kuyruğu)

- **Sorun:** uygulamanın kendi iş kuyruğu ve dış araçlar aynı anda GPU işi başlatabiliyor, OOM'a ya da
  yavaşlamalara yol açıyordu.
- **Çözüm:** `bolum_00_omurga/runtime/kaynak_kilidi.py`.
  - Kaynaklar ve kapasiteleri: `gpu` 1, `cpu_agir` (ağır CPU) 2, `ag` (ağ) 3, `ucretli_api` (ücretli API) 2.
  - Kiralar (lease), `O_CREAT | O_EXCL` ile atomik olarak oluşturulan JSON dosyalarıdır; yazdıktan sonra tutucu
    sayısı yeniden kontrol edilir ve kapasite aşılırsa kira geri çekilir. Kira, PID'i yaşadığı sürece ve isteğe bağlı
    bitiş süresinden önce geçerlidir; ölü ya da süresi dolmuş kiralar tembel biçimde (ihtiyaç anında) silinir.
  - CLI: `calistir --kaynak gpu --sahip <owner> --amac <purpose> --bekle N -- <command>` tek bir komutu kilit
    altında çalıştırır (N s'ye kadar her 5 s'de bir yoklar) ve alt sürecin çıkış kodunu, kaynak meşgul kaldıysa
    **75** döndürür. `al --sure <min>` süreli bir kira alır, `birak` onu bırakır, `durum [--json]` durumu gösterir.
- **Dersler:**
  - Windows'ta süreç canlılığı `OpenProcess` + `GetExitCodeProcess` ile kontrol edilir; "access denied" (erişim
    reddedildi) canlı sayılır. Windows'ta `os.kill(pid, 0)` kullanılmamalı: konsol grubuna `CTRL_C_EVENT` gönderir.
  - Kilidi zaten alan bir betik ikinci bir kilide sarılmamalı, yoksa kendini bekler.
  - `--` sonrasına `cmd /c a && b` zinciri değil, tek bir komut ver (o zincir defalarca bozuldu).
- **Hâlâ açık:** NVENC kodlaması da GPU'yu kullanır; aynı anda CUDA işi çalışırken NVENC ≈ 3,6× daha yavaş ölçüldü,
  bu yüzden kodlamayı GPU çıkarımıyla (inference) çakıştırma.

## 8. GPU çalıştırması için kontrol listesi

- Önce: kilit durumu `gpu 0/1` gösteriyor; başka hesaplama süreci yok; boş RAM ≥ modelin tepesi + 1,5 GB.
- Sırasında: `max_memory_reserved` < 3.9 GB; paylaşılan GPU belleği büyümüyor.
- Sonra: kilit bırakıldı; `nvidia-smi` ≈ 0 MiB'ye döndü; sahipsiz kalmış ffmpeg ya da python süreci yok.

## 9. Açık maddeler

1. Kapandı: ana hat modülü artık işçiler gibi `cudnn.benchmark = False` ayarlıyor (4. kural; `dubber.py:21-26`).
   `torch.set_num_threads(4)` duruyor; süreç içindeki tek GPU modeli (Opus-MT) evrişimli değildir.
2. `PYTORCH_CUDA_ALLOC_CONF` (`expandable_segments`), donanım hızlandırmalı GPU zamanlaması ve bellek oranı koruması
   kodda hiç denenmedi.
3. Aralıklı WhisperX OOM'unun tetikleyicisi bilinmiyor.

## 10. Ölçüm yöntemi (her sayfa için geçerli)

- Her değişiklik, bildirim dosyası (manifest) olan yalıtılmış bir deney klasöründe test edilir; bir deneyin kabulü
  onu birleştirmek demek değildir; birleştirme gerçek uygulama giriş noktasından ikinci bir kanıt ister.
- **Mevcut** uygulamanın taban ölçümünü al, tek bir değişkeni değiştir, aynı girdi özetini (hash) koru.
- Çıktıları örnek örnek (ses) ya da zamanlarıyla kelime kelime (transkript) karşılaştır; yalnız belirtilmiş
  toleransları kabul et.
- İşçiyi ve dıştaki uygulama çağrısını ayrı ayrı zamanla; farklıdırlar (süreç başlatma, içe aktarmalar, CUDA bağlamı,
  rapor doğrulama).
- Telemetriyi (ölçüm verisini) sürecin dışından topla (`nvidia-smi` ≈ her 1 s'de bir, süreç ağacı RAM'i ≈ her
  0,5 s'de bir); çıkarımın içinde profil oluşturucu kancası yok. GPU işini zamanlarken CPU'yu boşta tut; A/B
  çalıştırmalarının sırasını çaprazla, çünkü aynı yol çalıştırmalar arasında ≈ %10 değişti.
- RAM baskısı, GPU hesaplama doygunluğu ve VRAM tükenmesi üç farklı arızadır; bir şeye ancak gerçek CUDA kanıtıyla
  OOM de. Uzun CPU deneyleri için kullanışlı bir acil durdurma anahtarı bir boş RAM tabanıdır (1,5 GiB kullanıldı).
