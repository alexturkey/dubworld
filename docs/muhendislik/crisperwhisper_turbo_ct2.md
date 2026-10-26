# CrisperWhisper motorları ("motor 12" Medium ve "motor 13" Turbo CT2)

English: [../engineering/crisperwhisper_turbo_ct2.md](../engineering/crisperwhisper_turbo_ct2.md)

İsteğe bağlı kelimesi kelimesine (verbatim: dolgu sözcükleri, tekrarlar ve yarım başlangıçlar dahil her şeyi yazan)
transkripsiyon motorları: neden var oldukları, Turbo motorunun ≈ 1,4 GB VRAM (ekran kartı belleği) ile nasıl
çalıştırıldığı, düzeltilen her uzun kayıt ve çok dilli hata ve hız çalışması.
Kanıt etiketleri: bkz. [gpu_bellek_ve_yalitim.md](gpu_bellek_ve_yalitim.md).

> **Lisans.** CrisperWhisper 2.0 ağırlıkları nyra health Non-Commercial Research License (ticari olmayan araştırma
> lisansı) altında yayımlanmıştır. Dönüştürülmüş (CTranslate2 / int8) ağırlıklar türev eserdir: açık bir lisansla yeniden
> dağıtılamaz ya da API olarak sunulamaz. Bu depo **hiçbir** ağırlık içermez; `scripts/kur.ps1 -Adim crisper -TicariOlmayanKabul`
> onları sabitlenmiş bir commit'ten SHA-256 ile indirir ve yerelde dönüştürür. Kod (CrisperWhisper paketi, CTranslate2
> çatalı (fork)) MIT lisanslıdır.

## 1. Kimlik

| | Motor 12: CrisperWhisper 2 Medium | Motor 13: CrisperWhisper 2 Turbo CT2 |
|---|---|---|
| Arka uç | Transformers, CUDA fp16 | CrisperWhisper hizalama başlıklı CTranslate2 çatalı; fp16 depolama, **int8 hesaplama**; beam 1 |
| Çalıştığı yer | kendi Windows ortamı | WSL2 Ubuntu (istek başına tek seferlik alt süreç) |
| Kelime zamanları | modelin kendi dikkat (attention) zamanları | **ortak CTC zorlamalı hizalama** (kendi zamanları yalnız teşhis için tutulur) |
| VRAM tepesi | 3.5–3.6 GB (fp32 sığmaz) | ≈ 1.4 GB |

İki motor hiçbir ortamı, anlık kopyayı, ürün dosyası adını ya da bağdaştırıcıyı paylaşmaz; Turbo, "dublaja hazır" metin
mantığını içe aktarmak yerine onun yerel bir kopyasını tutar.

## 2. Karar: neden CTranslate2, WSL2 ve int8 (ayrıca bkz. [ADR 0004](../adr/0004-crisperwhisper-turbo-ct2-int8.md))

- **Hedef:** kelimesi kelimesine transkripsiyonu korumak (dolgu sözcükleri, tekrarlar, yarım başlangıçlar dublajın
  zamanlamasının parçasıdır) ve 4 GB içinde uzun İngilizce seste ≥ 5× gerçek zamana ulaşmak.
- **Kısıt:** CrisperWhisper'ın hizalama başlıklarını ve kelime zamanlama kodunu taşıyan CTranslate2 çatalı **yalnız
  manylinux x86_64 paketleri (wheel)** yayımlar. Bu yüzden motor WSL2 içinde çalışır; Windows'tan atomik JSON istek/yanıt
  dosyalarıyla tek seferlik bir alt süreç olarak çağrılır: HTTP sunucusu yok, port yok, bellekte sürekli duran model yok.
- **Neden int8:** Pascal'da hızlı fp16 yok ve CTranslate2'nin bu kartta fp16 hesaplaması yok; hızlı yol int8.
- **Medium için reddedilen:** Medium'un CT2 float32 ve int8 dönüşümleri, Transformers referansına karşı katı bir kelime ve
  zaman eşitliği kapısını geçemedi; bu yüzden Medium Transformers fp16'da kalıyor. Kayda geçen dersler: "tek başına
  dönüştürme bir çözüm değildir"; "int8 kısa seste hızlı görünüp genelleşmeyebilir".
- **Turbo için reddedilen:** kalıcı bir model sunucusu. Bellekte sürekli duran bir WSL işçisi kesinlik kapısını geçti ama
  transkripsiyon adımını **%16,9 yavaşlattı** (131.7 → 154.0 s); kurulum kazançları adımın dışında kaldı (ölçüldü).
- CPU yedeği yok: CUDA int8 desteklenmiyorsa motor hatayla durur.

## 3. Dönüştürme ve ortam tuzakları (ölçüldü)

1. **Pascal ve Linux torch paketleri.** Linux `torch 2.8.0+cu128` içinde sm_61 çekirdeği yok. `torch.cuda.is_available()`
   True döner, ilk matris çarpımı (matmul) "no kernel image is available" ile düşer. Linux'ta `torch==2.8.0+cu126`'ya
   sabitle; sağlık kontrolü gerçek bir 64×64 CUDA matris çarpımı çalıştırır.
2. **CT2 `config.json` üzerine yazılıyor.** CrisperWhisper 2.0.1 dönüştürücüsü, CTranslate2'nin `config.json`'ını
   Hugging Face yapılandırmasıyla ezer. CT2 `lang_ids`, `alignment_heads` ve `suppress_ids` bekler; ardından
   `detect_language` "type must be number, but is number" hatasıyla düşer. Çözüm: CT2 yapılandırmasını
   `generation_config.json` + `added_tokens.json`'dan yeniden kur; sonuç, doğru olduğu bilinen bir yapılandırmayla bayt
   düzeyinde aynıdır.
3. **Dönüştürücü `encoder_blank_head.*` öğelerini düşürür** (UNEXPECTED olarak bildirilir). Gelecekteki bir dönüştürücü
   bu tensörleri tutarsa kabul kapısını yeniden çalıştır; eski sonuçları varsayma.
4. **`.part` uzantılı geçici WAV:** `soundfile` biçimi uzantıdan çıkaramaz; `format="WAV"` ver.
5. **Dönüştürme ≈ 4,5 GB boş RAM ister.**
6. Depolama tipi (fp16) ve hesap tipi (int8) ayrı ayarlardır; karıştırma.
7. CTranslate2 çatalının kaynağı doğrulanamadı (üst veri URL'si 404, sdist yok); "çatal = üst kaynak (upstream)"
   varsayılmaz.

## 4. Sabit çözme profili (Turbo)

- Kelimesi kelimesine kip, kelime zaman damgaları açık, sıcaklık yedeği (temperature fallback) açık,
  `max_new_tokens=400`, spekülatif çözme kapalı, halüsinasyon (uydurma) azaltma açık, erken metin sonu toparlaması açık,
  beam 1.
- `suppress_tokens=null` "bastırma yok" değil, "modelin kendi listesini kullan" demektir; `[]` farklı bir ayardır.
- Beam 5 iki test dosyasında aynı metni verdi ve daha yavaştı; reddedildi.
- Kapsama toparlaması `direct_0_8_first`: temel çözme ≤ 1 kelimeyle eksik kapsıyorsa önce 7, 8, 6 tohumlarıyla sıcaklık
  0.8'i dene; aksi halde (0.8, 0.4, 0.6, 1.0) sıcaklıklarıyla kütüphanenin yedeği.
- VAD (konuşma etkinliği algılama): Silero (ONNX, CPU) eşik 0.15, negatif 0.01, en kısa konuşma 0 ms, en kısa sessizlik
  100 ms, dolgu 600 ms.
- Uzun kayıt pencereleri: 29,5 s, örtüşme 1,0 s (10 s'ye kadar), en az 2 bağlam kelimesi.
- Kalite değişmezi: asla metin silme, zaman uydurma ya da kelimesi kelimesine metnin yerine sessizce "amaçlanan" (temiz)
  metni koyma.

## 5. Uzun kayıt hataları ve düzeltmeleri

Aşağıdaki her düzeltme, hata veren girdide **ve** bayt düzeyinde aynı kalması gereken önceki girdilerde kanıtlandı.

### 5.1 Pencere kapsama toparlaması

- **Belirti:** 31 dakikalık bir dosyanın ortasında `unvalidated transition`.
- **Kök neden:** en az bir kelime döndüren bir pencere kabul ediliyordu ve sonraki pencere son gerçek kelimeden değil
  *planlanan* sondan başlıyordu; geride 14,9 s'lik kapsanmamış bir kuyruk kalıyordu. Sonraki pencere yalnız 10 s geri
  sarabildiği için örtüşmede önceki kelime yoktu ve iki kelimelik dikiş çapası imkânsızdı. Görünen dikiş hatası, daha
  önceki kötü bir kabulü yakalayan bir güvenlik kapısıydı.
- **Çözüm:** `tail = planned_end − last_timed_word_end`; sınır `min(5 s, max(3 s, 15 % of the window))`. Sınırın üstünde
  ilerleme: zamanı bilinen son kelimeye geri sar, büyüyen örtüşmelerle (1.5/3/5/7/10 s) yeniden oku, ≥ 2 kelimelik çapa
  iste, ilerleme yoksa kapalı başarısızlıkla (fail-closed) dur. "Planlanan son" ve "kanıtlanmış son" ayrı alanlar olarak
  tutulur. %15/3–5 s formülü uydurulmadı, gerçek İngilizce seste doğrulanmış daha önceki bir kapıdan yeniden kullanıldı.
- **Ölçüldü:** 31 dakikalık dosya tamamlandı (68 pencere, 1 toparlama, 0 kalite hatası); hiç üretilmemiş 28 kelime geri
  geldi. İki kontrol dosyası bayt düzeyinde aynı kaldı.

### 5.2 Dikiş sınırı örtüşmesi

- **Belirti:** 25 dakikalık bir İspanyolca dosyada üç yerde `invalid_word_timing` (bir kelime önceki kelime bitmeden
  başlıyor).
- **Kök neden:** üçü de bir dikişten sonra yeni bir pencereden eklenen ilk kelimeydi. Metin çapası doğruydu, ama iki
  bağımsız pencere sınırı 100–220 ms ayrı yerleştirmişti; dikiş, metin geçerliliğini zaman geçerliliği saydı ve yalnız
  50 ms'ye kadar örtüşmeleri onardı.
- **Reddedilen:** 50 ms sınırını 250/500 ms'ye çıkarmak (tekrarlanan ifadelerde sahte çapaları gizleyebilirdi).
- **Çözüm:** önce metin çapasını, sonra zaman sınırını doğrula. Yalnız iki komşu aralık örtüşüyorsa, ortak tek bir sınırı
  **kesişimin orta noktasına** koy (yalnız o iki kenar hareket eder); aksi halde adayı reddet ve sonraki örtüşmeyi dene.
  Sonraki bir revizyon, ikinci başlangıç kesin olarak daha sonraysa gerçekten tekrarlanan kelimeleri de ("code code")
  korur.
- **Ölçüldü:** 3.782 kelime, 41 dikiş, 5 yerel onarım, 0 zamanlama hatası; kontrol dosyaları, 5 ms kayan tek bir sınır
  dışında değişmedi (10 ms'lik bir kesişimin tam orta noktası).

### 5.3 Tekrar kabulü

Art arda beş ya da daha fazla aynı kelime/ifade, yalnız her geçişin sayısal bir başlangıcı varsa ve başlangıçlar **kesin
olarak artıyorsa** (tolerans yok) gerçek konuşma olarak kabul edilir; aksi halde çözücü döngüsü sayılır.

### 5.4 VAD kuyruğu

- **Belirti:** iş, 27 dakikalık bir dosyanın son kelimesinden sonra takıldı.
- **Kök neden:** Silero konuşma olasılığını yalnız 32 ms boyunca yükseltti; en kısa konuşma 0 ms ve iki 600 ms'lik
  dolguyla konuşma bandı son gerçek kelimenin 3,5 s ötesine uzandı; her örtüşme denemesi yeni kelime döndürmedi.
- **Reddedilen:** VAD eşiğini ya da en kısa konuşma süresini yükseltmek ("yes" gibi gerçek kısa kelimeleri kesebilirdi) ya
  da kuyruğu körü körüne kabul etmek.
- **Çözüm:** son bir VAD kuyruğu, **yalnız** son dil koşusuysa, her deneme sona kadar okuduysa, her birinin geçerli çapası
  ve sınırı varsa, hepsi "eklenen kelime yok" döndürdüyse ve hiçbiri ilerlemediyse doğrulanmamış konuşma olarak dışarıda
  bırakılır. Kelimelere ve zamanlara dokunulmaz; çelişen herhangi bir kanıt kapalı başarısızlıkla durur.

### 5.5 Hata teşhisi

- Bir pencere kabul edildikten sonraki her istisna, atomik olarak bir kalite hatası JSON'u yazar (dil koşusu, yerel/genel
  saniyeler, VAD aralığı, iki tarafın kelimeleri ve zamanlarıyla bütün örtüşme adayları, çapa, ret nedeni, kabul edilen
  pencereler). Bundan önce kanıt yalnız RAM'de yaşıyordu ve kullanıcı tek satır görüyordu.
- Turbo uzun kelime kontrol dosyasını kapı karar vermeden **önce** yazar, böylece dosya bir retten sonra da kalır.
- Garanti edilmeyen: çalıştırma başlamadan önceki içe aktarma hataları, zorla sonlandırmalar, yerel (native) çökmeler.
- Ders: hatalarda görünen bir artışın, aynı girdilerin hata + devam satırlarının iki kez sayılmasından kaynaklandığı
  ortaya çıktı.

## 6. Kelime zamanları: kendi dikkat zamanlarından zorunlu CTC'ye (çalışma zamanı v6)

- **Sorun:** 53 s'lik bir klipte Turbo ve ticari bir referans 117 kelimenin hepsinde uyuştu, ama Turbo'nun kendi zamanları
  bozuktu (0 ms süren bir kelime, 40 ms süren son kelime). 578 ms'lik TTS'e (metinden sese) karşı 40 ms'lik bir kaynak
  yuvası videoyu ≈ 14,5× yavaşlatırdı.
- **Kök neden:** kendi zamanlaması, zamana göre normalleştirilmiş dikkati mel enerjisine dayalı bir boşluk kararıyla
  birleştirir ve sıfır ya da çok kısa yerleşimler üretebilir. Özel Softmax çekirdeği elendi (hazır CT2 ile bayt düzeyinde
  aynı dikkat).
- **Reddedilen:** son segment eşiğini yükseltmek (hatayı gizler); yalnız Turbo'ya özel bir CTC işçisi (motora özel ikinci
  bir hizalayıcı).
- **Çözüm:** WSL işçisi çıktıktan sonra, diğer motorların kullandığı aynı ortak CTC hizalama kutusu Turbo'nun metnini
  hizalar (bkz. [kelime_hizalama.md](kelime_hizalama.md)). Metin baytları tam olarak korunmalıdır; kelimeler pozitif
  uzunlukta, sesin içinde, sıralı ve örtüşmesiz olmalıdır; kendi zamanlarına yedek dönüş yok. Değişiklik eski
  transkripsiyon kontrol noktalarını geçersiz kıldı ama indirme, ayrıştırma ve ASR (otomatik konuşma tanıma) hazırlığını
  korudu.
- **Uzun kelime kapısı:** 1,5 s'den uzun bir kelime yalnız ölçülen konuşma aralığının içindeyse (±150 ms, ≤ 300 ms onarım)
  **ve** bağımsız bir ham enerji kontrolü içinde 0,5 s'yi aşan sessiz bir bölüm bulmazsa kabul edilir (20 ms kareler,
  ±2 s bağlam, eşik = taban + tabandan tepeye farkın %35'i, karşıtlık < 6 dB ise veto). Enerji yalnız veto eder; zamanları
  asla kaydırmaz. 7 seste kalibrasyon: gerçek kelimelerde en fazla 0,36 s iç sessizlik vardı; veto 36 yapay "duraklamayı
  yutan" kelimenin 31'ini yakaladı, kalanları aralık kontrolü yakalar. Harf harf söylenen gerçek bir 1,66 s'lik ürün adı
  artık geçiyor.
- **Olaylar ve dolgu sözcükleri:** belirteçleyiciye (tokenizer) karşı doğrulanmış 13 olay etiketi dublaj metninden çıkarılır
  ve zamanlarıyla tutulur; `[UM]`/`[UH]` kelime olarak kalır; bilinmeyen köşeli parantezli metin korunur ve bildirilir; ham
  çıktı her zaman tutulur.

## 7. Diller

### 7.1 Dil algılama kipleri (ayar `crisper_dil_tespiti`)

1. **`global_first_window`** (varsayılan): bir platform/kullanıcı dili verildiyse ve model onu biliyorsa onu kullan; aksi
   halde konuşmanın ilk ≤ 29,5 s'sinde bir kez algıla ve bütün dosyayı o dilde işle.
2. **`per_window`** (Medium, eski): her pencereyi puanla ve bitişik aynı dilli pencereleri koşulara birleştir.
   Maliyet 29,5 s'lik pencere başına ≈ 1,25 s, yani çalışma süresinin +%4–5'i; tekrarlanan 242 çıkarımda 0 kararsız karar
   (ölçüldü).
3. **`continuous_stream`**: 4 s'lik kayan bağlam, 1 s'lik tikler; her tik en yüksek olasılık ≥ 0.60 ve fark ≥ 0.20 ister;
   art arda iki emin tik bir dili ya da bir değişimi doğrular; sınır, son kararlı tik ile ilk doğrulanmış tikin ortasına
   konur. Verilen bir platform dili yalnız kanıttır, asla karar değildir.
   Birleştirilmiş Türkçe + İngilizce + Almanca bir dosyada (17,9 s) ölçüldü: geçişler 5,5 s ve 11,0 s'de bulundu,
   10 / 13 / 12 kelime, sonraki her iyileştirmeden sonra değişmedi.

### 7.2 Dil başına çalışma

| Dil | Yapılan | Durum |
|---|---|---|
| İngilizce | 10 seste int8 kabulü, kapsama toparlaması, CTC zamanları, uzun kelime kapısı, hız çalışması | üretimde |
| İspanyolca | dikiş orta noktası düzeltmesi (Medium) | Medium üretimde; Turbo için ayrı kayıt yok |
| Çince | ilk pencereden itibaren boşluksuz "devam" yolu; çok baytlı belirteçler bütün gruplar halinde çözülür; `split()` yerine içerik belirteci sayımı; 448 konumluk çözücü bütçesi (istem 192 ile sınırlı + 256 ayrılmış) | üretimde |
| Japonca | belirteç başına çözme U+FFFD üretti → Unicode güvenli yeniden gruplama; düz transkripsiyon kardeş yolu; zamanı bilinen son gruptan sonra > 3 s etkin ses kalırsa ret; CTC karakter yeniden gruplama | üretimde |
| Tayca, Laoca, Birmanca, Kantonca | boşluksuz yolu paylaşır | **gerçek seste kabul yok**, CTC modeli yok |
| Türkçe | karışık dil testi; kesik kelime yoklaması | bağımsız STT deposunun ölçümlerine bakın |
| Almanca | yalnız karışık dil testinin bir segmenti | yalnız test |

Çince/Japonca çalışmasından dersler:

- Kütüphane kelimeleri `decode().split()` ile sayıyordu; boşluksuz yazı sistemlerinde bu 0 ya da 1 kelimedir. Bunun yerine
  içerik belirteçlerini say.
- `context_words=1`, 201 belirteçlik bir "kelime" tutabiliyor ve 448 konumluk çözücüyü taşırabiliyordu; `context_words=0`
  reddedildi çünkü `[-0:]` dilimi *her şeyi* seçer.
- Yalnız bir yoklama betiğinde var olan bir düzeltme gönderilmez; gerçek giriş noktasından kanıtla.
- WhisperX hizalaması Çince/Japoncayı karakterlere böler; kaynak kelimelere yeniden grupla (zamanı bilinen ilk karakterin
  başlangıcı, sonuncunun sonu) ve herhangi bir uyuşmazlıkta hata fırlat.
- 85 s'lik bir Çince klipte kutudan çıktığı haliyle CrisperWhisper: varsayılan CT2 yolu sesi okumadan önce bir float16 arka
  uç hatasıyla düştü; Transformers kelimesi kelimesine yolu 4 pencerenin 4'ünü boş üretti; zaman damgalı "amaçlanan" yol
  448 konum sınırına takıldı. Projenin çalışma zamanı zamanlı çıktı üretti.
- Ayrıştırma bu dillerde gerçek konuşmayı silebilir: çözücüyü değiştirmeden önce doğrudan sesi karşılaştır
  (bkz. [kaynak_ses_ve_ayristirma.md](kaynak_ses_ve_ayristirma.md)).
- Kesik bir Türkçe kelime çözücü tarafından tamamlandı ("oluş-" → "oluştur."). Sıcaklık yedeğini ya da erken son
  toparlamasını kapatmak hiçbir şeyi değiştirmedi (4 kombinasyon aynı): tamamlama temel çözmede oluyor. Denenmemiş
  fikirler: belirteç güveni ya da akustik bir son kontrolü.

## 8. Hız

### 8.1 Kabul çalıştırması (int8, tek süreç, model bir kez yüklenmiş)

10 İngilizce dosya, 605 s'de 6.678 s ses: **11,0× gerçek zaman**, her dosya ≥ 5× (ör. 30 s → 14,3×, 49 dk → 10,7×).
17 s'lik model yükleme hariç. Bu, üretimdeki yaşam döngüsü değildir (istek başına bir işçi).

### 8.2 İşe yaramayanlar (ölçüldü)

| Fikir | Sonuç |
|---|---|
| Bellekte duran işçi + bellekte duran model | transkripsiyon adımı %16.9 daha yavaş |
| Küçük bir taslak modelle spekülatif çözme | 1.92× daha yavaş ve kesin değil (noktalama kayboldu, kelime zamanları 400 ms'ye kadar kaydı) |
| Kodlayıcı batch 2 / 4 | 0.999× / 1.005×, gürültü |
| `cub_caching` ayırıcısı | varsayılan `cuda_malloc_async`'ten %12.7 daha yavaş |
| N+1'i kodlarken N penceresini çözmek (iki akış) | 0.984× (Pascal'da çekişme) |
| Pencereleri toplu işlemek | imkânsız: her pencerenin başlangıcı bir önceki çözmeye bağlı |
| Aynı anda iki iş | sığar (2.9 GB tepe) ama her biri ≈ 1.95× daha yavaş; işlem hacmi +%2.6 |
| WSL ext4 diskinde venv + model | daha yavaş (Windows bağlama noktasındaki 59.8 s'ye karşı 80/73 s): model yükleme iyileşti ama soğuk sanal diskte özet (hash), içe aktarma ve algılama yavaşladı |
| Dikkat algoritması taraması | %0.05 kazanç; bir varyant kelime sınırlarını kaydırdı; reddedildi |

### 8.3 İşe yarayanlar (ölçüldü, çıktılar aynı)

- **Uçtan uca ince ayarlar:** tam SHA-256 için 8 MiB okuma tamponu; CT2 model yüklemesiyle paralel CPU VAD; aynı pencere
  içinde kodlayıcı çıktısının yeniden kullanımı; Windows bağlama noktasındaki ≥ 64 MiB dosyalar için Windows ana makine
  Python'uyla özet alma (1,6 GB model: 12.4 → 4.7 s); önceden ayrılmış G/Ç bağlamalı (I/O binding) VAD. Sonuçlar: −%3,5
  (74 dk İngilizce) ile −%24 (kısa klipler) arası. Ders: denetimsiz ≈ 32 s'lik bir fark WSL açılışıydı; A/B'de WSL başlangıç
  durumunu her zaman eşle.
- **CT2 için özel CUDA Softmax (yalnız compute capability (hesaplama yeteneği sürümü) 6.1):** profil çıkarma, kodlayıcı
  geçişi başına ≈ 429 ms tutan 32 Softmax çağrısı gösterdi. Dolgulu paylaşımlı bellek, yazmaçta tutulan `exp`, warp-shuffle
  maksimum ve **aynı kayan nokta toplama sırası** kullanan bir çekirdek, 73 matris durumunda ve 8 gerçek kodlayıcı
  çıktısında bayt düzeyinde eşitti. Büyük matris medyanı blok başına 256 iş parçacığıyla 7,9 → 5,4 ms (512 ve 128 daha
  yavaştı: daha az iş parçacığı tekdüze biçimde daha iyi değildir). 74 dakikalık bir dosyada uçtan uca ≈ 439 → 397 s.
  Ara katmanın (shim), PTX'in ve kurulu CT2 kütüphanesinin SHA-256'sı doğrulandıktan sonra `LD_PRELOAD` ile yüklenir; başka
  herhangi bir GPU ya da CT2 sürümü hazır çekirdeklere geri döner ve yeni bir kabul ister.
  Not: bir kaynak dosyasının adını değiştirmek yalnız sembol tablosu baytlarını değiştirdi; yeni sabitlenmiş özet, kapıyı
  gevşetmek yerine ikili bir farkla (binary diff) gerekçelendirildi.

### 8.4 Süre nereye gidiyor (169 s'lik klip, ölçüldü)

| Aşama | s |
|---|---:|
| Toplam | 88.7 |
| ASR alt süreci | 61.1 (model yükleme + yerel hazırlık 16.3, çözme 13.6, içe aktarmalar 3.6, ön kontroller 4.7, dil 1.4, başlatma/yazma/çıkış 20.8) |
| CTC alt süreci | 22.0 (model yükleme 8.1, hizalama 9.0, içe aktarmalar 3.2) |
| Yapıştırıcı kod | 5.6 |

CTC hazırlığını ASR ile paralel çalıştırmanın ≈ 11–12 s gizlediği ölçüldü (CTC tek başına 16,4 s, eşzamanlı 19,3 s; motor
yavaşlamadı, çıktı aynı); **entegre edilmedi**.

### 8.5 Bellek

- 74 dakikalık İngilizce: 4.096 MiB'nin 1.435 MiB'i tepe (yüklenmiş model 911 MiB + 524 MiB çalışma); GPU ≈ %74 meşgul.
- ASR ve hizalama ayrı, art arda gelen süreçlerde çalışır, böylece kart iki modeli asla birlikte tutmaz.
- Her işten sonra: işçi süreçleri gitmiş, ≈ 0 MiB VRAM.

### 8.6 Medium hız çalışması

Dile göre yönlendirilmiş iyileştirmeler (kodlayıcı önbelleği ve seçici eager (anında çalıştırma) yollar; Çince/Japonca için
ek bir SDPA yolu ve tek GPU batch'inde 3 uzlaşı tohumu), metin, kelimeler, zamanlar ve dilde 19/19 test sesi tam eşitken
1,45–3,56× hızlanma verdi. 5× hedefi bir dosya için imkânsız olarak kapatıldı: zorunlu iki eager çözücü penceresi tek
başına zaman bütçesini aştı.

## 9. Açık maddeler

1. 74 dakikalık İngilizce için 3 dakikalık hedefe hiç ulaşılmadı (en iyi ≈ 397 s).
2. Paralel CTC hazırlığı (≈ −12 s) entegre edilmedi.
3. Özel Softmax yalnız compute capability 6.1'i kapsıyor.
4. Tayca/Laoca/Birmanca/Kantonca için gerçek seste kabul yok.
5. Çok zayıf dolgu sözcükleri komşu sese yapışabilir; kesik kelimeler çözücü tarafından tamamlanır.
6. 10 İngilizce dosyada ticari bir referansa karşı ≈ 500 normalleştirilmiş fark henüz dinlenerek sınıflandırılmadı;
   yalnız 2'sinin yanlış duyma olduğu doğrulandı. Referans doğruluğu bilinen (ground-truth) veri değil, geri çağırma
   (recall) kanıtı olarak ele alınır.
