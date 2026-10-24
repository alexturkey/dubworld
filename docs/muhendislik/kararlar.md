# Mimari kararlar (ADR) — Türkçe

İngilizce asıl metinler: [../adr/README.md](../adr/README.md)

ADR (Architecture Decision Record: mimari karar kaydı), bir tasarım kararını bağlamı, gerekçesi, sonuçları ve
değerlendirilen alternatifleriyle birlikte kayda geçiren kısa belgedir. Biçim: Bağlam / Karar / Sonuçlar /
Değerlendirilen alternatifler. Arka plan ve ölçümler: [../engineering/README.md](../engineering/README.md).

<a id="0001"></a>
## 0001 — Aynı anda tek GPU işi, her ağır model için tek süreç

İngilizce: [../adr/0001-one-gpu-job-and-process-per-model.md](../adr/0001-one-gpu-job-and-process-per-model.md)

Durum: kabul edildi

### Bağlam
Hat 4 GB VRAM'li (ekran kartı belleği) bir kartta çalışmak zorunda. Ayrıştırma, tanıma, hizalama, konuşmacı ayrıştırma
(diarization), cinsiyet sınıflandırma ve TTS (metinden konuşma) tepe noktasında her biri ≈ 0,5 ile ≈ 3,6 GB arası bellek
ister. Uzun ömürlü bir arayüz/web sürecinin içinde bellek parçalanır ve artık CUDA durumu birikir; bir OOM (bellek
yetmezliği) sonrasında `empty_cache()` yeniden yer açmayı güvenilir biçimde sağlamadı.

### Karar
- Her ağır model, aynı yorumlayıcıyla başlatılan kendi alt sürecinde çalışır; süreç işini bitirince kapanır ve sürücü
  onun bütün belleğini geri alır.
- Bir aşamanın birlikte ihtiyaç duyduğu modeller (dil tanıma + transkripsiyon, tanıma + hizalama) asla aynı anda değil,
  sıralı süreçlerde çalışır.
- Aynı anda yalnız bir GPU işi çalışır; bunu kaynak kilidi uygular (`runtime/kaynak_kilidi.py`, `gpu` kapasitesi 1).

### Sonuçlar
- Her aşama süreç başlatma ve model yükleme bedelini öder. Kabul edildi: sürekli açık (resident) bir CrisperWhisper
  işçisi transkripsiyon adımında zaten %17 daha yavaş ölçüldü.
- Hatalar yalıtılır: çöken bir işçi bir sonraki aşamayı zehirleyemez.
- İşçiler tepe belleği ve bir hata profilini bildirir; bu da OOM'ları teşhis edilebilir kıldı.

### Değerlendirilen alternatifler
- **Sürekli açık model sunucusu:** VRAM işler arasında tutulur, OOM sonrası toparlanma daha zor; CT2 motoru için daha
  yavaş ölçüldü.
- **Paralel iki GPU işi:** küçük modeller için sığar ama her iş ≈ 1,95 kat yavaşlar ve toplam iş hacmi +%2,6; OOM riski.
- **`del` + `empty_cache()` ile tek süreç:** gerçek bir OOM sonrasında yetersiz.

<a id="0002"></a>
## 0002 — Demucs, tek seferlik OOM yedeğiyle toplu çalışan iki parçalı (stem) bir işçide

İngilizce: [../adr/0002-demucs-batched-two-stem-worker.md](../adr/0002-demucs-batched-two-stem-worker.md)

Durum: kabul edildi

### Bağlam
Hazır Demucs (`htdemucs`; sesi vokal ve müzik gibi parçalara (stem) ayıran model) her GPU çağrısına 7,8 sn'lik tek bir
segment gönderir ve ilk özel işçi dört parçanın (stem) tamamını CPU RAM'inde biriktiriyordu. 75 dakikalık seste bu, ≈ 12 dakika
işçi süresi ve 16 GB'lık bir sistemi %93'e iten bir RAM tepesi demekti.

### Karar
- Kendi işçimiz: model çağrısı başına 4 dolgulu parçadan oluşan gruplar (`overlap=0.25`, `shifts=0`, modelin kendi
  segment uzunluğu, asla zorlanmaz).
- Her parça biriktirilmeden önce GPU'da `[vocals, drums+bass+other]` biçimine indirilir; referans, girdi ve model
  tensörleri olabildiğince erken serbest bırakılır; matematik korunur (`no_vocals*std + 3*mean`).
- Yalnız gerçek bir `torch.cuda.OutOfMemoryError` durumunda: bellek serbest bırakılır ve toplu iş boyutu 1 ile bir kez
  yeniden denenir; bu, rapora kaydedilir.
- Ana süreç işçi raporunu doğrular; tek başına çıkış kodu 0 başarı değildir. Bir Demucs hatası işi durdurur.

### Sonuçlar
- Ölçüldü: işçi 11 dk 48 sn → 5 dk 52 sn; RAM tepesi 9,52 → 7,15 GB; VRAM tepesi ≈ 2,75 GB (cihaz).
- Çıktı, toplu iş boyutu 1 ile bayt bayt aynı değil: örneklerin ≈ %0,03'ünde en çok 1 int16 adımı fark (kabul edilen
  tolerans).
- Aynı anda tek Demucs işçisi; eşzamanlı çalıştırmalar sınanmadı.

### Değerlendirilen alternatifler
- `--segment 12` (model tarafından reddedildi) / zorlanmış `--segment 7` (varsayılandan daha yavaş).
- `CUDA_LAUNCH_BLOCKING=1`, `cudnn.benchmark=True`: daha yavaş ya da kazanç yok.
- CPU ile ayrıştırma: doğru ama uzun girdiler için çok fazla yavaş.

<a id="0003"></a>
## 0003 — Ayrıştırmanın çalışıp çalışmayacağına ölçülmüş arka plan düzeyiyle karar vermek

İngilizce: [../adr/0003-automatic-background-detection.md](../adr/0003-automatic-background-detection.md)

Durum: kabul edildi

### Bağlam
Ayrıştırma (konuşmayı arka plandan ayırma) dakikalar sürer ve gerçek konuşmayı silebilir (Çince bir klipte ölçüldü:
vokal parçası, ham seste korunan kelimeleri kaybetti). Temiz konuşma içeren girdilerin çoğunun buna ihtiyacı yok, ama
konuşmanın altındaki müzik dublajda korunmalı.

### Karar
`auto_background` kipi: 50 ms'lik karelerin dinamik aralığı ölçülür (95. − 5. yüzdelik). 32 dB'in altı = arka plan var;
−60 dB'in altındaki tepe = arka plan değil, sessizlik. Arka plan varsa Demucs yalnız karışım için `no_vocals` izini
üretmek üzere çalışır; tanıma ise **ham** 16 kHz mono sesi kullanır.

### Sonuçlar
- Önceki çalıştırmalar üzerinde kalibrasyon: açık arka planlı hiçbir vaka kaçırılmadı, ≈ %90 kesinlik (precision);
  ≈ 15 saatlik sesi ölçmek 24 sn sürdü.
- Sınırlar: kalibrasyon klipleri ≤ 4 dakika, İngilizce, tek tanıyıcı, kesin doğru (ground truth) yok; uzun girdiler
  temiz ve müzikli pencereleri karıştırabilir.

### Değerlendirilen alternatifler
- Her zaman ayrıştır: daha yavaş ve bazen tanımaya zarar veriyor.
- Hiç ayrıştırma: arka plan müziği dublajdan kaybolur.
- 30 sn'lik pencere başına karar: grupları daha kötü ayırdı (%85–89).

<a id="0004"></a>
## 0004 — CrisperWhisper Turbo, tek seferlik bir WSL2 işçisinde CTranslate2 int8 ile

İngilizce: [../adr/0004-crisperwhisper-turbo-ct2-int8.md](../adr/0004-crisperwhisper-turbo-ct2-int8.md)

Durum: kabul edildi (isteğe bağlı motor, ticari olmayan ağırlıklar)

### Bağlam
Birebir (verbatim) transkripsiyon (dolgu sözcükleri, tekrarlar) dublaj zamanlaması için önemlidir. Transformers fp16
üzerinde CrisperWhisper 2 Medium 3,5–3,6 GB ister ve yavaştı. CrisperWhisper'ın hizalama başlarını (alignment heads)
taşıyan CTranslate2 çatalı (fork) yalnız Linux tekerlekleri (wheel: hazır derlenmiş Python paketi) yayımlıyor. Pascal'da
hızlı fp16 yok.

### Karar
- Turbo modeli CTranslate2'ye dönüştürüldü (fp16 depolama), **int8 hesaplama**, ışın (beam) 1 ve birebir kipte
  çalıştırılır.
- WSL2 içinde, atomik JSON istek/yanıt dosyalarıyla tek seferlik bir alt süreç olarak çalışır; sunucu yok, port yok,
  sürekli açık model yok.
- Kelime zamanları motordan değil, ortak CTC hizalayıcıdan gelir ([ADR 0005](#0005)).
- CPU yedeği yok. Ağırlıklar asla dağıtılmaz; sabitlenmiş bir commit + SHA-256 ile indirilir ve yerelde dönüştürülür.

### Sonuçlar
- ≈ 1,4 GB VRAM; model bir kez yüklenmişken 10 İngilizce dosyada gerçek zamanın 11 katı hız; 74 dakika için uçtan uca
  ≈ 397 sn.
- WSL2 gerektirir; küçük işlerde süreyi WSL başlatma belirler.
- Ticari olmayan lisans: isteğe bağlı, açık bir kurucu bayrağının arkasında.

### Değerlendirilen alternatifler
- CT2'ye dönüştürülmüş Medium (fp32 ya da int8): katı bir kelime ve zaman eşitliği kapısını geçemedi.
- Sürekli açık WSL işçisi: transkripsiyon adımında %16,9 daha yavaş.
- Küçük bir taslak modelle spekülatif çözme (speculative decoding): 1,92 kat daha yavaş ve birebir değil.

<a id="0005"></a>
## 0005 — Kelime zamanlarının tek kaynağı CTC zorlamalı hizalamadır

İngilizce: [../adr/0005-ctc-forced-alignment-only-time-source.md](../adr/0005-ctc-forced-alignment-only-time-source.md)

Durum: kabul edildi

### Bağlam
Segment uzunluğu, TTS süre hedefleri, aday seçimi, videonun yeniden zamanlanması ve altyazıların hepsi kelime
zamanlarından türetilir. Motor segmentleri, TTS motoru sınır olayları, iç dikkat (attention) haritası ve RMS (ses
yüksekliği) kırpmasının her biri kaymaya yol açtı: ör. 10,2 sn boşluk içeren 27,4 sn'lik bir motor segmenti ya da videoyu
≈ 14 kat yavaşlatacak 40 ms'lik bir kelime.

### Karar
- Kaynak tarafı: kendi alt sürecinde WhisperX 3.8.6 hizalaması (CTC zorlamalı hizalama: bilinen metni sese kelime kelime
  oturtma; WhisperX için yerleşik, diğer motorlar için ortak bir CTC kutusu), `ctc_speech_bounded_v2` ile (her kelime,
  torchaudio ile ölçülen konuşma aralığı ± 150 ms'ye sıkıştırılır).
- Üretilen taraf: TTS adayları ve son dublaj aynı yolla yeniden hizalanır.
- Yedek yok: eksik bir hizalama işi başarısız kılar. Pencereler motor başına hazırlanır (doğal boşluklar dışarıda
  bırakılır).

### Sonuçlar
- Konuşma sınırlaması için 100 dakikada ≈ +85 sn (model her pencerede iki kez çalışır).
- Bütünlük denetimleri zorunludur (her kelime zamanlanmış, sıralı, çakışmasız, sesin içinde).
- Politikayı değiştirmek, bilerek böyle tasarlandığı için transkripsiyon ara kayıtlarını (checkpoint) geçersiz kılar.

### Bilinen istisnalar
- Açıkça seçilen `faster-whisper` Whisper'ın kendi kelime zamanlarını korur (bilinçli bir hız/uyumluluk seçimi). `auto`
  hiçbir zaman ona çözülmez: izin verici yedeği `faster_whisper_ctc`'dir (aynı tanıyıcı, ortak CTC kutusu).
- Bulut motorları (`speechmatics`, `elevenlabs_scribe_v2`) sağlayıcının kelime zamanlarını korur; şimdiki kodda bunların
  üzerinde CTC geçişi çalışmaz ve CTC zamanlarıyla bir karşılaştırma kayıtlı değildir.
- `crisperwhisper2_medium` modelin kendi dikkat (attention) kelime zamanlarını korur
  ([crisperwhisper_turbo_ct2.md](crisperwhisper_turbo_ct2.md) §1).
- Üretilen taraftaki hizalama Supertonic adaylarına ve son dublaja uygulanır; VoxCPM2 ve XTTS çıktısı ölçülen süresine
  göre yerleştirilir ve yalnız altyazı istendiğinde altyazı için hizalanır.

### Değerlendirilen alternatifler
- Yerel kelime zaman damgaları (test derleminde kelime başlangıçları ≈ 4 kat daha kötü), motor segmentleri, RMS/dikkat
  zamanlaması: reddedildi.
- Yalnız torchaudio `forced_align`: kelimelerin %9'u 40 ms'nin altında.
- Hizalamadan önce sayıların LLM (büyük dil modeli) ile yazıya dökülmesi: yerini WhisperX 3.8.6 yükseltmesi aldı.
- Hız için farklı bir CTC modeli: kapsam dışı (araç kalır, yalnız nasıl çalıştığı değişebilir).

<a id="0006"></a>
## 0006 — İki aşamalı dublaj segmentleme (1,0 sn boşluk, sonra en çok 150 kelime)

İngilizce: [../adr/0006-two-stage-dub-segmentation.md](../adr/0006-two-stage-dub-segmentation.md)

Durum: kabul edildi

### Bağlam
Dublaj segmentleri (dublajın birim aldığı konuşma parçaları) tanıyıcının bağlam pencerelerini değil konuşmadaki
duraklamaları izlemeli ve çeviri çağrıları için yeterince küçük kalmalı. Önceki kurallar (yalnız noktalama, her konuşmacı
değişimi, noktalamasız transkriptler için ayrı bir kapı, 25 sn sınırları) motorlar arasında tutarsızdı.

### Karar
Her kaynak için tek segmentleyici (`nihai_dublaj_segmentleri.py`): > 1,0 sn'lik her boşlukta yeni bir ana segment;
≥ 151 kelimelik bir ana segment yalnız kendi içinde `.` → `?` → `!` → `,` sırasıyla bölünür (açgözlü biçimde 150'ye
kadar), son çare olarak 150'de sert kesim. Zamanlar her segmentin kendi ilk ve son kelimesinden gelir. Konuşmacı üst
veridir (metadata); konuşmacı bölmeleri sonradan, bir ana segmentin içinde yapılır ve 0,40 sn'den kısa gruplar bir
komşuyla birleştirilir.

### Sonuçlar
- 0 kelime kaybı, çoğaltma ya da sıra değişimi (değişmezlerle denetlenir).
- Bakımı gereken motora özel bir segment yolu yok.
- 1,0 sn ile eski 0,6 sn boşluk arasında A/B kaydı yok.

### Değerlendirilen alternatifler
Motor segmentleri; 0,6 sn boşluk; konuşmacı değişimlerinde zorunlu bölmeler; sabit boyutlu parçalar; grupları
boyutlandırmak yerine çevirmen çıktı sınırlarını yükseltmek.

<a id="0007"></a>
## 0007 — "Doğal bloklar" çeviri sözleşmesi

İngilizce: [../adr/0007-natural-blocks-translation-contract.md](../adr/0007-natural-blocks-translation-contract.md)

Durum: kabul edildi

### Bağlam
Segment kimlikleri (ID) zaman çizelgesi anahtarlarıdır. Segment segment çeviri altyazı gibi duyulur; serbest çeviri
ardından yeniden bölme anlamı komşu kimliğe taşır ve konuşma ile altyazının eşzamanlılığını bozar. Tek başına istem
(prompt) ifadesi ya da tek başına JSON kipi sözleşmeyi tutmadı (bir API sağlayıcısıyla ölçüldü: kimlikler düştü,
parçalar birleşti, anlam dolguyla şişirildi).

### Karar
- Segment başına tam olarak bir doğal Türkçe aday; anlamı kendi kimliğinde kalır; sayıların ve sembollerin okunuş
  biçimlerini model yazar (adaylarda rakam yok).
- Sahiplik öz denetimi içeren katı bir şema; bağımsız kod kapıları (beklenen kimlikler, boş olmama, felaket düzeyinde
  kapsama: kaynak ≥ 8 kelime ve aday kelime sayısı × 4 < kaynak kelime sayısı → reddet); en çok bir hedefli zincir
  gözden geçirme yeniden denemesi.
- Zamanlama burada yalnız öneridir; son zamanlama kararı gerçek sentezlenmiş sesi kullanır ([ADR 0010](#0010)).

### Sonuçlar
- Doğrulanmış tek bir metin hem altyazıyı hem TTS'i besler.
- Bir LLM arka ucu gerektirir; yerel Opus-MT yedeği bu sözleşmeyi sağlayamaz.

### Değerlendirilen alternatifler
Segment başına harfi harfine çeviri; birleştirip yeniden bölme; her kelime için birebir aralık kanıtı (kaldırıldı);
ikinci bir LLM denetim geçişi (≈ bir ek çeviri geçişi, kendi hataları, bütünleştirilmedi); çok aday + TTS ile seçim
(başka kipler olarak tutuldu).

<a id="0008"></a>
## 0008 — Çeviri arka uç sırası: Codex CLI → Claude Code CLI → yerel Opus-MT

İngilizce: [../adr/0008-translation-backend-order.md](../adr/0008-translation-backend-order.md)

Durum: kabul edildi

### Bağlam
En iyi çeviri kalitesi, yalıtılmış metin işçileri olarak kullanılan abonelik tabanlı kodlama CLI'larından (komut satırı
araçları) geldi. Repo hesap ve anahtar olmadan da çalışmalı ve yalnız resmi, belgelenmiş bir yolu olan bileşenleri
dağıtabilir.

### Karar
`ceviri.arka_uc = "auto"` **seçim anında** çözülür: kuruluysa Codex CLI, değilse Claude Code CLI, o da değilse yerel
Opus-MT (yalnız İngilizce → Türkçe). Açıkça seçilmiş ama eksik bir arka uç ya da anahtarsız bir API arka ucu kesin
hatadır. **Çalıştırma sırasında başka arka uca geçiş (failover) yoktur**: geçici bir Codex hatası grubu erteler ve
Codex'te yeniden dener.

### Sonuçlar
- En çok kanıtı Codex taşıyor (şemayı CLI uyguluyor; bütün istem ve sözleşme ölçümleri). Claude aynı sözleşmeyi
  yalıtılmış 736 tokenlık bir zarf (envelope: her çağrıda yüklenen sabit bağlam) ve istem önbelleğiyle kullanır; TTS'in
  yüksek sesle okuyacağı parantez içi açıklamalara karşı ek bir kurala ihtiyaç duydu.
- Opus-MT anahtarsız ve çevrimdışıdır ama aday, sahiplik denetimi ve okunuş biçimi kuralları yoktur; LLM arka uçlarına
  göre kalitesi ölçülmedi.

### Değerlendirilen alternatifler
Önce API sağlayıcıları (anahtarlar, faturalama, sağlayıcıya özel sertleştirme); ücretsiz katmanlı bir sağlayıcı (günlük
token sınırı); resmi olmayan bir web uç noktası (sessiz yedek olayından sonra kaldırıldı); 4 GB'ta yerel LLM'ler
(66 sn'lik bir video için ≈ 13 dakika, kararsız sunucu); çalıştırma ortasında motorlar arası geçiş (tonu karıştırır ve
gizli yedek hatalarına yol açtı).

<a id="0009"></a>
## 0009 — Kapalı-hata (fail closed), sessiz yedek yok

İngilizce: [../adr/0009-fail-closed-no-silent-fallback.md](../adr/0009-fail-closed-no-silent-fallback.md)

Durum: kabul edildi

### Bağlam
Hız sınırına takılan bir çevirmen bir kez kaynak metne geri düştü; çevrilmemiş bir video seslendirildi ve "tamamlandı"
olarak bildirildi. Başka bir yerde bir arka uç seçimi üç yerde sessizce üzerine yazıldı ve bir ayrıştırma hatası ham
sesle devam edebilirdi.

### Karar
- Bir aşama ya doğrulanmış çıktısını üretir ya da iş açık, maskelenmiş bir hata mesajıyla durur
  (`runtime/hata_aciklama.py`).
- İzin verilenler: açıkça belgelenmiş eşdeğer bir yol (NVENC → x264) ve sınıflandırılmış geçici bir hata için aynı motor
  içinde tek, sınırlı bir yeniden deneme (WhisperX OOM → bir kez int8, Demucs OOM → bir kez toplu iş boyutu 1, API 503 →
  geri çekilme (backoff) sonra erteleme).
- İzin verilmeyen: kullanıcının seçimi olmadan başka bir motora, modele ya da kaynak metne geçmek.

### Sonuçlar
Daha görünür hatalar, sessizce yanlış teslimat yok. Her yeniden deneme çalıştırma üst verisine kaydedilir.

### Giderilen istisna
Yerel Opus-MT motoru önceden model çıktısı boş olduğunda kaynak metni döndürüyordu. Artık etkilenen segment
numaralarıyla `YerelCeviriHatasi` fırlatır.

<a id="0010"></a>
## 0010 — Zamanlamada kullanılan tek süre, gerçek sentezlenmiş süredir

İngilizce: [../adr/0010-real-tts-duration-is-canonical.md](../adr/0010-real-tts-duration-is-canonical.md)

Durum: kabul edildi

### Bağlam
Supertonic'in model içi hızını değiştirmek onun ne ürettiğini değiştirdi (düşen ya da tekrarlanan kelimeler). Motor süre
tahminleri, iç dikkat sınırları ve RMS kırpması yanlış kesimlere ve altyazılara yol açtı.

### Karar
- Ses başına tek sabit hız; yalnız sabit metinlerde 5/5 tam ASR (otomatik konuşma tanıma) eşleşmesinden sonra kabul
  edilir.
- Yürütme katmanı gerçek sesin `processed_duration` değerini ölçer; kabul bandı ima edilen video hızı olarak 0,90–1,15;
  isteğe bağlı saf `atempo` (perdeyi değiştirmeden hız ayarı) 0,90–1,25 içinde; kalan farkı video emer.
- Üretilen sesin kelime zamanları, gerçek aday sesinin zorlamalı hizalamasından gelir.

### Sonuçlar
Aday başına daha fazla sentez ve hizalama işi; tekrarlanabilir çıktı (tohum hızı içermez).

### Değerlendirilen alternatifler
Genel ya da dinamik model içi hız; motor süre tahminleri; dikkat/RMS zamanlaması; süreyi doldurmak için çevirileri
şişirmek.

<a id="0011"></a>
## 0011 — Deneme kodlamasıyla otomatik kodlayıcı seçimi; varsayılan CQ 26

İngilizce: [../adr/0011-video-encoder-selection.md](../adr/0011-video-encoder-selection.md)

Durum: kabul edildi

### Bağlam
NVENC (NVIDIA kartın donanım video kodlayıcısı) hızlıdır ama yalnız CPU'lu makinelerde ve sabitlenmiş FFmpeg'in NVENC
API'sinden eski sürücülerde kullanılamaz. Pascal'da bayt başına kalitesi içeriğe bağlıdır: GPU ile işlenmiş sahnelerde
eşdeğer, düz çizilmiş videoda x264'ten kötü.

### Karar
0,1 sn'lik bir deneme kodlaması süreç başına bir kez karar verir: çalışıyorsa `h264_nvenc`, yoksa `libx264`;
`DUBLAJ_VIDEO_KODLAYICI` ile geçersiz kılınır. Varsayılan çıktı ilkesi CQ 26 (CQ 23'e karşı ölçülen SSIM ≈ 0,995–0,997,
dosyalar ≈ %28–30 daha küçük). Altyazılar tek toplu kodlamada yakılır; ikinci bir tam kodlama yoktur.

### Sonuçlar
Her makinede çalışır; düz ya da çizilmiş içeriği olan kullanıcılar `x264` tercih edebilir. Daha yeni GPU'larda yeniden
ölçülmeli.

### Değerlendirilen alternatifler
Koda gömülü NVENC (CPU makinelerinde başarısız oldu); her zaman x264 (uzun videolarda daha yavaş); altyazı ve boyut için
ikinci bir kodlama (uzun bir videoda 27 dakikanın 13'ü ve bir kare eksikliği kusurunu gizledi).

<a id="0012"></a>
## 0012 — Girdi parmak izleri ve sözleşme sürümleriyle aşama ara kayıtları

İngilizce: [../adr/0012-stage-checkpoints-and-resume.md](../adr/0012-stage-checkpoints-and-resume.md)

Durum: kabul edildi

### Bağlam
Uzun işler geç aşamada başarısız olur (TTS, kodlama). Geç bir hatadan sonra tanıma ve çeviriyi yeniden çalıştırmak
sürenin çoğunu boşa harcar; ama farklı ayarlarla üretilmiş bir çıktıyı yeniden kullanmak sonucu sessizce bozar.

### Karar
Çalıştırma başına `pipeline_state.json`: her aşama sözleşme sürümünü, girdilerinin ve ayarlarının SHA-256 parmak izini,
durumunu, deneme sayısını ve ürünlerini (artefact: boyut, mtime, örneklenmiş özet) saklar. Değişmiş bir parmak izi ya da
sözleşme sürümü o aşamayı ve ondan sonraki her şeyi geçersiz kılar. Devam etme kaynak çalıştırmayı asla değiştirmez; yeni
bir klasör kurulur ve atomik olarak (yarım kalmadan, tek seferde) yerine taşınır.

### Sonuçlar
Bir TTS hatası tanımayı ya da çeviriyi yeniden çalıştırmaz. Bir aşamanın davranışındaki her değişiklik sözleşme sürümünü
yükseltmelidir (yeni TTS tarifi, yeni hizalama politikası, yeni istem).

### Değerlendirilen alternatifler
Her şeyi yeniden çalıştırmak (yavaş); yalnız dosyanın varlığına göre yeniden kullanmak (güvensiz); pickle ile saklanan
durum (taşınabilir değil, yüklemesi güvensiz).

<a id="0013"></a>
## 0013 — Konuşmacı ayrımında FSMN VAD yerine Silero VAD

İngilizce: [../adr/0013-silero-vad.md](../adr/0013-silero-vad.md)

Durum: kabul edildi

### Bağlam
Konuşmacı ayrımı (3D-Speaker, CAM++ gömmeleri + kümeleme) konuşma bölgelerini üst kaynaktaki FSMN VAD ile buluyordu. Bu
model `modelscope` → `funasr` üzerinden çalışır; `funasr` yüklenirken `kaldiio` ister. `kaldiio` 2.18.1 NTT değerlendirme
sözleşmesiyle gelir (yalnız iç değerlendirme, yeniden dağıtım yasak); Apache-2.0 bir projenin bağımlılığı olamaz.
`funasr` `kaldiio`'suz kurulup denendi: içe aktarmada düşüyor, FSMN onsuz çalışmıyor.

### Karar
`faster-whisper` içinde gelen **Silero VAD v6 (MIT)** (zaten çekirdek bağımlılık, ek model indirmesi yok), vendor
`speakerlab/bin/infer_diarization.py` içinde `SileroVad`: eşik 0,5, en kısa konuşma 250 ms, en kısa sessizlik 100 ms,
pay 30 ms, 16 kHz mono (başka örnekleme reddedilir). `funasr` ve `kaldiio` pyproject'ten, kilitlerden ve model
manifestinden (4 FSMN dosyası) çıktı; onları içe aktaran ve hattın hiç çağırmadığı vendor betikleri silindi
(`VENDOR_NOTU.md`, Apache-2.0 §4b). CAM++ ve kümeleme ayarları değişmedi.

### Sonuçlar
Bağımlılık ağacı yeniden dağıtılabilir; GPU/CPU kilitlerinden 26 paket düştü, kalanların sürümü değişmedi. 22,8 sn iki
konuşmacılı örnekte duman testi: 2 konuşmacı, 6 segment (FSMN ile aynı konuşmacı sayısı). Ölçülmedi: uzun ve zor bir
klipte FSMN ile Silero segment sınırları karşılaştırması; uzun kayıtta konuşmacılar birleşirse önce sınırları karşılaştır.

### Değerlendirilen alternatifler
FSMN'i tutup `kaldiio`'yu dağıtmak (lisans yasaklar); `funasr --no-deps` (içe aktarmada düşüyor, denendi); pyannote
segmentasyonu (4.x topluluk hattı ≈ 9,5 GB tepe, kapılı model; 4 GB'a sığmaz); enerji tabanlı VAD ve WebRTC VAD
(denenmedi: öğrenilmiş konuşma modeli yok / ek yerel bağımlılık; Silero zaten kurulu).

<a id="0014"></a>
## 0014 — Dilden bağımsız çeviri istemleri, dil ekleri ve çıktı dili denetimi

İngilizce: [../adr/0014-language-independent-translation-prompts.md](../adr/0014-language-independent-translation-prompts.md)

Durum: kabul edildi

### Bağlam
LLM çeviri arka uçları her hedef dili kabul ediyordu ama istemler, şema açıklamaları, onarım metinleri ve süre tahmini
Türkçe için yazılmıştı: Fransızca bir işe "Türkçe yaz" kuralları gidiyordu, kelime başına süre tek sabitti (0,43 sn,
Türkçe ölçüm), boşluksuz yazılan diller `split()` ile cümle başına tek kelime sayılıyordu ve dönen metnin dili
denetlenmiyordu. Kısıt: Türkçe üretimde kanıtlanmış yoldur; Türkçe istemlerin tamamı bayt bayt aynı kalmalıdır.

### Karar
Var olan istem dosyalarına şablon işaretleri (`{target_lang_name}` ve türevleri, `<!-- dil:tr -->` blokları) eklendi;
`hedef_dil.istem_isle` `tr` için özgün metni, diğer diller için `dil_ekleri/_genel.md` ve `dil_ekleri/<kod>.md`
bölümlerini üretir. Hız tablosu `KONUSMA_HIZI`: `tr` 0,43 (ölçüm), diğerleri tahmin; ja/zh/ko/th karakterle sayılır.
Çıktı dili denetimi bağımlılıksızdır: yazı sistemi oranı (≥ 8 harf), kana/Han kuralı, Latin hedefte ı/ğ/ş (≥ 3) ve
işlev sözcüğü profili (≥ 4 kelime). Uyuşmazlık yeniden denenebilir `translation_result_wrong_language` hatasıdır; sessiz
yedek yok (ADR 0009).

### Sonuçlar
110 Türkçe çıktının SHA-256 özeti değişiklik öncesiyle aynı (altın dosya testte). 85 dil kodunda kalan işaret yok.
192 doğru metinde 0 yanlış alarm; başka hedefe karşı ≥ 4 kelimelik ya da CJK metinde yakalama %68,9 (661/960), yazı
sistemi farkında %100; 4 kelimeden kısa metinde %25 (yanlış alarmı önlemek için bilinçli). Açık: gerçek LLM denemesi
(fr, ja), istemlerdeki İngilizce kaynak varsayımı, bölge varyantı (`pt-BR`, `zh-TW`) ayrımı, tahmini hız değerlerinin
ölçümü. Veri/talimat ayrımı paragrafı (`VERI_TALIMAT_AYRIMI`, `istem_guvenligi.py`) şablonlara değil, köprü ve Claude
arka uçlarının sabit sistem kısmına eklenir; şablonlar ve 110 altın özet değişmez. `tests/test_istem_veri_ayrimi.py`
her şablon × arka uç × kipte paragrafın iş JSON'undan önce geldiğini denetler.

### Değerlendirilen alternatifler
Dil başına ayrı istem dosyası (elle kopyalanan düzeltmeler kayar); istemleri nötr İngilizceye çevirmek (Türkçe çıktıyı
değiştirir); dil tanıma kütüphanesi (yeni bağımlılık, kısa metinde düşük doğruluk); uyuşmazlıkta sessiz kabul ya da
başka arka uçla yeniden çeviri (ADR 0009'a aykırı).

<a id="0015"></a>
## 0015 — Varsayılan TTS Supertonic; VoxCPM2 ve XTTS v2 kendi süreçlerinde isteğe bağlı

İngilizce: [../adr/0015-tts-engine-set-and-default.md](../adr/0015-tts-engine-set-and-default.md)

Durum: kabul edildi

### Bağlam
Varsayılan TTS motoru GPU'suz makinede de çalışmalı, lisansı indirme yolunun dağıtılmasına izin vermeli ve süre
davranışı zamanlama katmanı için öngörülebilir olmalıdır. Tasarlanmış Türkçe ses ve referans kaydın tınısıyla konuşma
Supertonic'in kapsamı dışındadır. Hattın önceki bir sürümünde XTTS v2 ana uygulamanın içinde çalışıyordu: Coqui TTS
paketi ana ortamı eski bir torch / CUDA 11.8 / numpy 1.22 birleşimine sabitliyordu (kartın gereği değildi), model uzun
yaşayan sürecin bir iş parçacığında çalışıp belleği yalnız `del` + `empty_cache()` ile bırakıyordu; ağırlıklar CPML
(ticari olmayan) lisanslıdır.

### Karar
- Varsayılan `ses.motor = "supertonic"`: işlemcide ONNX (4 hat × 2 iş parçacığı), 10 hazır ses, ses başına sabit hız,
  ölçülmüş sentez reçetesi. Aday/onarım akışları ve isteğe bağlı `atempo` bu motor üzerinde kuruldu ve ölçüldü.
- VoxCPM2: kardeş VoxCPM2 reposunun kendi ortamında, iş başına tek alt süreç (model bir kez yüklenir); yalnız NVIDIA GPU.
- XTTS v2: coqui-tts bir ek (`tts-xtts`) ya da `DUBLAJ_XTTS_PYTHON` ile ayrı ortam; sentez her zaman bu paketi içe
  aktarmayan ayrı bir alt süreçte (`xtts_tts/kosucu.py`); CPML onayı ve kullanıcının verdiği referans kayıt zorunlu.
- Tüm motorlar aynı sonuç sözleşmesini döndürür; ortak yürütme katmanı gerçek `processed_duration`'ı ölçer, ortak
  karıştırıcı her segmenti başlangıç zamanına yerleştirir.
- Gerçek TTS aday seçimi, onarım turları ve `atempo` yalnız Supertonic + LLM çeviri arka ucunda çalışır; VoxCPM2 ve
  XTTS segment başına tek üretim yapar, kalan süre farkını video yeniden zamanlaması karşılar.
- Hiçbir motor başka motora düşmez (0009).

### Sonuçlar
Varsayılan kurulum GPU'suz ve ticari-olmayan lisans adımı olmadan seslendirir; ana ortam Coqui sabitlerini taşımaz.
VoxCPM2 ve XTTS'te segment başına süre onarımı yoktur. XTTS için bu repoda ölçüm yoktur.

### Değerlendirilen alternatifler
XTTS varsayılan (ticari olmayan ağırlık, referans ses ve GPU gereği, ortam sabitleri); VoxCPM2 varsayılan (NVIDIA GPU ve
ayrı kurulum); bulut TTS hizmetleri (çevrimdışı yol yok, tekrarlanamaz, sessiz geçiş yaşandı); XTTS'i aynı süreçte
içe aktarmak (0001).

<a id="0016"></a>
## 0016 — RVC ses dönüştürme, zamanlanmış karışım üzerinde TTS sonrası katmandır

İngilizce: [../adr/0016-rvc-as-post-tts-conversion.md](../adr/0016-rvc-as-post-tts-conversion.md)

Durum: kabul edildi

### Bağlam
RVC metin okumaz; var olan bir kaydı başka bir ses karakterine çevirir. Bağımlılıkları (kendi torch yapısı, fairseq,
faiss, HuBERT, RMVPE) ana ortamla çakışır. Önceki sürümde dönüştürülmüş çıktıda duraklamalar içinde cızırtı ve uğultu
görülmüştü.

### Karar
Çeviri, TTS, yerleştirme ve zamanlama önce tamamlanır; RVC, TTS aşamasının döndürdüğü zamanlanmış dublaj izini bir kez
dönüştürür. Resmî RVC WebUI komut satırı kullanıcının kendi RVC ortamında alt süreç olarak çalışır; RVC'den hiçbir şey
içe aktarılmaz ya da dağıtılmaz. Konuşma/duraklama kararı RVC çıktısından değil, RVC'ye giren temiz sesten alınır
(−45 dB, en az 0,15 sn); bu aralıklar çıktıda yeniden susturulur, kenarlarda 40 ms yumuşatma uygulanır. Rıza beyanı
zorunludur; başarısız dönüştürme hatadır, dönüştürülmemiş sese sessizce dönülmez.

### Sonuçlar
Zamanlama ve altyazı RVC'den bağımsızdır. RVC ayarları TTS ara kaydının parmak izindedir: değişince TTS aşaması yeniden
çalışır, transkripsiyon ve çeviri korunur. Sabit dönüştürme parametreleri için kayıtlı A/B yoktur.

### Değerlendirilen alternatifler
Segment segment dönüştürme; zamanlanmamış TTS birleşimini dönüştürme; duraklamayı RVC çıktısının enerjisinden ölçme;
RVC'yi ana ortama kurma.

<a id="0017"></a>
## 0017 — Varsayılanlar dağıtılabilir lisanslar içinde kanıtlanmış akışı izler; gerisi isteğe bağlıdır

İngilizce: [../adr/0017-defaults-and-licence-gate.md](../adr/0017-defaults-and-licence-gate.md)

Durum: kabul edildi

### Bağlam
Motor lisansları serbestten (MIT, Apache-2.0) şartlıya (Open RAIL-M, NVIDIA Open Model License), ticari olmayana
(CrisperWhisper, CPML) ve sağlayıcı şartlarına kadar uzanır; iki özellik gerçek bir sesi taklit eder (XTTS, RVC).

### Karar
Varsayılanlar, önceki sürümde ölçüm ve ayar çalışmasının en çok yapıldığı akışı, repo tarafından gösterilmesine lisansı
izin veren bileşenlerle sınırlayarak yeniden üretir. En çok kanıtlanmış bileşen ticari olmayan lisanslıysa `auto` onu
yalnız açık kabul bayrağıyla kurulmuşsa seçer; yoksa en yakın serbest alternatif kullanılır (CrisperWhisper Turbo →
`faster_whisper_ctc`: metin faster-whisper, kelime zamanı ortak CTC kutusu). Elle seçilen `faster-whisper` Whisper'ın
kendi zamanını korur; CTC modeli yoksa iş kurulum adımını söyleyerek durur, Whisper zamanına düşmez. Ağırlıklar repoda tutulmaz; sabit commit ve SHA-256 ile indirilir. Ticari olmayan ya da şartlı
motorun ilk kullanımı açık onay ister (`lisans_onayi.py`; kayıt yalnız motor adı, lisans metni, UTC tarih); her giriş yolu için tek kapı `kapi_adlar`: `dubla <video>`, `dubla transkript`, her aşama komutu (`dubla seslendir`, `dubla yaziya-dok` …), `dubla devam`, Python API (`lisans_onay=True`), GUI, web ve son savunma olarak iş çalıştırıcı (onaysız kuyruk/devam işi soru sormadan çıkış 2 ile durur). Yalnız komutun gerçekten çalıştırdığı motor sorulur (`dubla transkript` ses motorunu sormaz). XTTS'in
kendi CPML onayı, RVC'nin rıza beyanı vardır. GPL araçlar içe aktarılmaz (gallery-dl ayrı program).

### Sonuçlar
Taze kurulum yalnız serbest bileşenlerle uçtan uca çalışır. Bazı varsayılanların alternatiflere karşı kayıtlı A/B'si
yoktur (1,0 sn segment boşluğu, LLM model adları); bunlar ayarlanabilir olarak belgelenir.

### Değerlendirilen alternatifler
Yalnız lisansa göre seçim (ölçümsüz motorlar varsayılan olurdu); lisansa bakmadan en kanıtlanmış akış (ticari olmayan
model sessizce varsayılan olurdu); ağırlıkları repoda taşımak.

<a id="0018"></a>
## 0018 — Büyük Telegram teslimi yerel Bot API sunucusundan, oynatılabilir video olarak gider

İngilizce: [../adr/0018-local-bot-api-server-for-large-files.md](../adr/0018-local-bot-api-server-for-large-files.md)

Durum: kabul edildi

### Bağlam
Bulut Bot API bir botun en çok 50 MB göndermesine, 20 MB indirmesine izin verir; birkaç dakikalık dublajlı video
çoğu zaman daha büyüktür. Sınırın üstünde yükleme reddedilir ve istemci çoğu zaman yalnız gecikmeli bir ağ hatası
görür; bu yüzden zaman aşımını büyütmek ya da yeniden denemek işe yaramaz. Belge olarak giden video yalnız dosya
simgesi gösterir, oynatmak için önce indirilmesi gerekir.

### Karar
İsteğe bağlı yerel Bot API sunucusu (Telegram'ın açık kaynak `tdlib/telegram-bot-api`'si, Boost lisansı, `--local`)
iki sınırı da 2000 MB'a çıkarır; `TELEGRAM_YEREL_SUNUCU` ayarlıysa bot, `dubla-telegram gonder` ve hazırlık denetimi
onu kullanır. Kurulum tek komuttur (`dubla-telegram sunucu kur`, `kur.ps1 -Adim telegram-sunucu`): Docker varsa
Docker (Docker Desktop gizli başlar; hazır imaj sabit özetle ya da `--kaynaktan` resmî kaynak sabit commit'te),
yoksa aynı commit'in derlemesi (doğrudan ya da Windows'ta WSL içinde); kullanıcıdan yalnız my.telegram.org'dan
`api_id` / `api_hash` ve bot belirteci istenir. Hazır imaj `aiogram/telegram-bot-api`, resmî BSL-1.0 kaynağın
topluluk derlemesidir ve özetle (`imaj@sha256:...`) sabitlenir; acemi kullanıcı için tek adımdır ve bu ağ
sözleşmesiyle uygulamada çalıştırılmıştır; resmî kaynaktan derleme `--kaynaktan` ile yapılır. Tedarik zinciri riski:
imajı üçüncü taraf derler, içeriği kaynağa karşı doğrulanmaz; özet sabitlemesi yalnız her seferinde aynı baytların
çekilmesini garanti eder, yeni özet ancak incelemeden sonra alınır. "Resmî olmayan uç yok" kuralı resmî olmayan API
uçları içindir (ör. resmî olmayan çeviri uçları); bu, resmî açık kaynak sunucunun derlenmiş paketidir. Ağ sözleşmesi: IPv6 açık kendi köprü ağında tek adlı kapsayıcı, port
yalnız `127.0.0.1`, `unless-stopped`; uyuşmayan kapsayıcı bir kez yeniden kurulur, uyan kapsayıcıya dokunulmaz;
hazırlık 60 sn içinde gerçek `getMe`'dir, açık port ya da çalışan süreç değil. Teslim kuralları (`teslim.py`): boyut
yüklemeden önce denetlenir; video `sendVideo` + `supports_streaming`, ffprobe'dan boyut ve süre, ffmpeg küçük resmi ve
faststart MP4 (akış kopyası, yeniden kodlama yok) ile gider, belge yalnız açık istekle; zaman aşımı boyuttan
hesaplanır; en çok 3 deneme (15/30/60 sn); dosyanın tamamı gittikten sonraki zaman aşımı ya da kopma yeniden
denenmez (çift teslim olmasın); teslim yalnız Telegram mesaj döndürünce sayılır, cevaptaki `video`/`document`
alanı kaydedilir. Kimlik değerleri yalnız `.env`'de; kapsayıcıya değişken adıyla, WSL'ye `WSLENV` ile geçer.

### Sonuçlar
2000 MB'a kadar sonuç telefona oynatılabilir video olarak gelir; sunucuyu kurmayan için hiçbir şey değişmez. Yerel
sunucu indirdiği dosyaları silinene kadar saklar (bot kendi kopyasını hemen siler, `temizle` artıkları siler);
yükleme sırasında sunucuda dosya boyu kadar geçici yer gerekir. Sunucu veri klasöründe bot belirteci adlı alt klasör
vardır, gizli sayılır. Docker'sız kurulum 10-30 dk C++ derler; Windows'ta WSL gerekir.

### Değerlendirilen alternatifler
Dosyayı 50 MB parçalara bölmek (alıcı birleştirir, önizleme yok); 50 MB altına sıkıştırmak (görünür kalite kaybı);
bulut depolama bağlantısı (her dosya için dış hesap ve üçüncü taraf); Telegram Premium (ücretli, botlara açık değil);
bulut uç noktasında yeniden deneme ya da uzun zaman aşımı (50 MB sınırını kaldırmaz); IPv4/IPv6 seçimini uygulama
kodunda sıralı uzun beklemelerle yapmak (her ağ değişiminde yavaşlatır, IPv6 rotası olmayan kapsayıcı ağını düzeltmez).

<a id="0019"></a>
## 0019 — EMA Lightning: GPU yolu ve yerelde dışa aktarılan işlemci ONNX yoluyla isteğe bağlı Türkçe TTS

İngilizce: [../adr/0019-ema-lightning-tts.md](../adr/0019-ema-lightning-tts.md)

Durum: kabul edildi

### Bağlam
Ana hedef dil Türkçedir. Supertonic Türkçeyi işlemcide okur ama sesleri çok dil için ayarlıdır; VoxCPM2 tasarlanmış
Türkçe sesler verir ama NVIDIA GPU ve yaklaşık 3 GB VRAM ister. Küçük, yalnız Türkçe okuyan EMA Lightning (8,6 M
parametre, kod ve ağırlık Apache-2.0) sayı, tarih ve birimleri kendisi okur, GPU'da da işlemcide de hızlıdır.
Eklemeden önce üç koşul resmî kaynaktan denetlendi: kod lisansı (PyPI paket bilgisi ve depo: Apache-2.0), ağırlık
lisansı (model kartı: Apache-2.0, ticari kullanım dahil) ve ses (model kartı: VoxCPM2'de metin tarifinden tasarlanmış
tek sentetik ses; VoxCPM2 ile üretilmiş yaklaşık 1000 saat sentetik konuşmayla eğitildi, Apache-2.0; gerçek kişi kaydı
yok). Yayıncı yalnız PyTorch ağırlığı yayımlar; ONNX dosyaları yalnız üçüncü kişi dönüşümü olarak vardır.

### Karar
`ses.motor = ema_lightning` isteğe bağlı eklenir (`scripts/kur.ps1 -Adim tts-ema`): paket hash'li kilitle ana ortama
(PyTorch zaten orada; işlemci profili için ayrı kilit var), ağırlık resmî model deposundan sabit commit ve SHA-256 ile;
özet her `torch.load`'dan önce yeniden denetlenir. İşlemci yolu ONNX Runtime'dır; dosyalar indirilen üçüncü kişi
dönüşümü değil, **aynı denetimli ağırlıktan kullanıcının makinesinde dışa aktarılır** ve farklı uzunlukta bir cümlede
PyTorch ile karşılaştırılır; en büyük fark 1e-3'ü aşarsa işlemci yolu PyTorch'u kullanır. Cihaz seçimi
`ses.ema_cihaz = auto | cuda | cpu`: `auto` GPU'da en az 1 GB boş bellek varsa GPU'yu alır; GPU yoksa, meşgulse ya
da GPU koşusu CUDA veya bellek hatasıyla düşerse (bir tekrar) işlemciye geçer; açık `cuda` hiç düşmez. İş başına bir
alt süreç, model bir kez yüklenir, çıkışta GPU belleği boşalır. `cudnn.benchmark` kapalıdır (4 GB Pascal sınıfı kartta
kendi kendini ayarlama 30 sn'lik metni yaklaşık 1 sn yerine 202 sn'de okuttu). Yalnız Türkçe: başka hedef dil ayar
hatasıdır. İki dublaj kipi de desteklenir; `full_text` cümle cümle okur, hizalama pencereleri gerçek sesten gelir.

### Sonuçlar
Türkçe dublaj tamamen işlemcide, 12 sn açılıştan sonra gerçek zamanın yaklaşık 11 katı hızla ya da GPU'da çalışabilir.
Kurulum ONNX'i bir kez üretir (başvuru işlemcisinde yaklaşık 11 sn); farklı PyTorch sürümü bayt olarak farklı ama
sayısal olarak eşit dosya üretebilir, bu yüzden dosyalar özetle değil çıktıyla doğrulanır. Tek kısa cümlede işlemcide
PyTorch ONNX'ten önce biter (açılışı kısa); dublajlar ONNX'in kazanacağı kadar uzundur. Tek ses vardır; çeşit ses
seçiminden değil tohumdan (`ses.ema_tohum`) gelir.

### Değerlendirilen alternatifler
Üçüncü kişinin ONNX dönüşümünü indirmek (kurulumu kısa ama yayıncıdan değil, ağırlığı resmî özetle eşlenemez);
yalnız işlemcide PyTorch (dışa aktarım yok ama yeni metinde 2,4×, eski kayıtlarda yeni girdi uzunluğunun ilk
geçişinde 0,7×'e kadar; ONNX ile yaklaşık 11×); `lightning()` (torch.compile + CUDA grafikleri; yayıncının en hızlı
yolu, 4 GB Pascal sınıfı kartta hiç ölçülmedi ve cuDNN ayarlamasını açar; ölçülene kadar dışarıda); modeli işler
arasında sıcak tutmak (çağrı başına saniye kazandırır ama diğer aşamaların ihtiyaç duyduğu GPU belleğini tutar).
