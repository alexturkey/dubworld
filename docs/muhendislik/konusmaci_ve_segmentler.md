# Konuşmacılar, cinsiyet ve dublaj segmentleri

English: [../engineering/speakers_and_segments.md](../engineering/speakers_and_segments.md)

Kelime zamanlarının nasıl dublaj segmentlerine (dublajın birim aldığı konuşma parçaları) dönüştüğü, konuşmacıların
nasıl bulunduğu ve her konuşmacı için sesin nasıl seçildiği.
Karar kaydı: [ADR 0006](kararlar.md#0006).
Segmentlemenin bütün işteki yeri ve kelimelerin neden yeniden gruplandığı: [hat_akisi.md](hat_akisi.md#8-transkript-neden-kelime-zamanlarına-bölünüp-yeniden-gruplanır).

## 1. Nihai dublaj segmentleri (`bolum_30_hizalama_ve_segment/nihai_dublaj_segmentleri.py`)

### Gelişim

1. `. ? !` işaretlerinde (kısaltma istisnalarıyla) ya da her konuşmacı değişiminde bölme.
2. Virgül/duraklama/zorunlu kesimlerle bir "uzun segment" stratejisi (≥ 151 kelime, ≥ 25 sn, …); gerekçe, segment başına
   çok aday üretirken çıktı token sınırına takılan bir API çevirmeniydi. Aynı gün çıkan ders: token sınırını yükseltme;
   bunun yerine grupları ve aday sayısını boyutlandır.
3. Noktalamasız transkriptler için ayrı bir kapı (0,6 sn boşluk, zorunlu konuşmacı bölmeleri): kaldırıldı.
4. Bugün: tek kanonik (tek geçerli) segmentleyici; segment eşleme (segment-sync) kipinde her transkripsiyon kaynağı için
   zorunlu, yedek yol yok ve "motorun segmentlerini koru" yolu yok.

### Geçerli kural

- **1. aşama (zaman):** `gap = next.start − prev.end`; boşluk ≤ 1,0 sn ise kelimeler bir arada kalır, > 1,0 sn ise yeni
  bir ana segment başlar (sınandı: 1,0 sn bir arada, 1,001 sn bölünür). Ana segmentler asla birleştirilmez; kelimeler
  aralarında asla yer değiştirmez.
- **2. aşama (boyut):** ≤ 150 kelime kabul edilir. ≥ 151 kelime yalnız kendi içinde bölünür: parçalar önce `.`, sonra
  `?`, sonra `!`, sonra `,` işaretinde (daha zayıf işarete yalnız gerektiğinde inilir), açgözlü biçimde 150 kelimeye
  kadar biriktirilir; son çare 150 kelimede sert kesim. Örnek: 285 kelime → 130 / 95 / 60.
- Her segmentin başlangıcı ve bitişi kendi ilk ve son kelimesinden gelir.
- Denetlenen değişmezler: çıktı kelime sayısı = girdi; her segment ≤ 150; kayıp, çoğaltma ya da sıra değişimi yok.
- Konuşmacı burada üst veridir (metadata); konuşmacıya göre bölme sonradan ana segmentin **içinde** yapılır.
- Tam metin kipi bundan muaftır (tek mantıksal metin, tek pencere).

### Neden

| Alternatif | Neden reddedildi |
|---|---|
| Dublaj hedefi olarak motor segmentleri | ölçülen 27,4 sn'lik bir segmentte 10,2 sn boşluk vardı |
| 0,6 sn boşluk eşiği | noktalamasız kapıyla birlikte kaldırıldı; 1,0 sn hizalamadaki doğal boşluk kuralıyla örtüşür. 0,6 ile 1,0 sn arasında **A/B kaydı yok** |
| Her konuşmacı değişiminde bölme | artık ana segmentin içinde, 0,40 sn kısa grup birleştirmesiyle ele alınıyor |
| Sabit boyutlu parçalar | anlam birimlerini bozar; yalnız son çare |

## 2. Konuşmacı ayrıştırma (diarization: kimin ne zaman konuştuğunu bulma)

### Gelişim

1. Kelime düzeyinde konuşmacı etiketleriyle WhisperX + pyannote 3.3.2 (arşivlendi). O zamanki seçim (belgelendi):

| Seçenek | VRAM | Karar |
|---|---|---|
| pyannote 3.3.2 | 1,59 GB tepe (ölçüldü) | o zaman seçildi |
| pyannote 4.x topluluk modeli | ≈ 9,5 GB tepe (üst kaynak sorun bildirimi) | 4 GB'ta imkânsız |
| NVIDIA NeMo | 4–8 GB, ağır kurulum | reddedildi |
| yalnız konuşmacı gömmesi (embedding) modelleri | sınıflandırıcı değiller | yanlış araç |

   Modeller sırayla çalıştı (ASR → hizalama → ayrıştırma → cinsiyet), aralarında bellek bırakıldı; aynı anda asla
   ≈ 2 GB'tan fazla kullanılmadı.
2. Ayrıştırma olmadan segment başına bir cinsiyet yönlendiricisi (hafif, yalıtılmış). Bilinen sınır: iki kişi içeren bir
   segment tek cinsiyet alır.
3. **Geçerli: 3D-Speaker** (Silero VAD + CAM++ gömmeleri + kümeleme; üst kaynaktaki FSMN VAD lisans nedeniyle
   değiştirildi, [ADR 0013](../adr/0013-silero-vad.md)). pyannote yerine onu tercih etmenin nedeni
   **kaydedilmedi**. Bu yolda pyannote içe aktarılmaz; çakışan konuşma işleme kapalıdır.
4. Kelime düzeyinde konuşmacı döndüren bir bulut motoruyla onun etiketleri kullanılır ve 3D-Speaker çalışmaz.

### Geçerli 3D-Speaker ayarları

- Girdi: 16 kHz mono. VAD (konuşma etkinliği tespiti): `faster-whisper` içindeki Silero VAD v6 (eşik 0,5, en kısa konuşma
  250 ms, en kısa sessizlik 100 ms, pay 30 ms; [ADR 0013](../adr/0013-silero-vad.md), FSMN
  `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch` yerine); gömmeler
  CAM++ `iic/speech_campplus_sv_zh_en_16k-common_advanced` (v1.0.0), 80 kutulu FBank, 192 boyutlu.
- Kümeleme: önce spektral (`mer_cos=0.8`, 1–15 konuşmacı, `pval=0.012`). **Tek konuşmacı kurtarması:** spektral
  kümeleme tek konuşmacı döndürürse aynı gömmeler üzerinde aglomeratif (aşağıdan yukarı birleştirmeli) kümeleme
  (`fix_cos_thr=0.2`) çalışır (VAD ya da gömme tekrarlanmaz). Hiçbir kelimenin en büyük örtüşmesine sahip olmayan ham bir
  küme asla dublaj konuşmacısı olmaz.
- Kelime eşleme: her kelime, zaman örtüşmesi en büyük olan konuşmacıyı alır; 0,40 sn'den kısa gruplar bir komşuyla
  birleşir (baştaki → sonrakiyle, sondaki → öncekiyle, ortadaki → daha uzun komşuyla). Kelimeler asla silinmez; bir
  konuşmacı grubu asla başka bir ana segmente taşınmaz.
- Güvenlik: içe alınmış (vendored) kod ara kayıtları `torch.load(weights_only=True)` ile, YAML'ı `safe_load` ile yükler.
- Her çalıştırmada yazılan kanıt: komut, çalışma süresi, model tanı bilgisi, hata, ilerleme dosyaları.

### Ölçümler

| Adım | Önce | İçe aktarma/model yükleme temizliğinden sonra |
|---|---|---|
| Toplam konuşmacı + cinsiyet yönlendirme | 76,0 sn | 21,8 sn (aynı kararlar) |
| Alt süreç + üretici kodu içe aktarma | ≈ 30,4 sn | 6,3 sn |
| VAD / gömme / kümeleme | 2,0 / 1,4 / 2,1 sn | 1,0 / 1,0 / 2,6 sn |

- 95 sn'lik iki kişilik bir röportaj: spektral kümeleme 1 konuşmacı buldu; kurtarma 2 gerçek dublaj konuşmacısı buldu
  (güvenler 0,986 ve 0,974); işçi ≈ 37 sn, üreticinin komut satırı aracı (CLI) ≈ 107 sn.
- **Önbellek denetimi deneyi (reddedildi):** maliyetin ≈ 3 sn'si ModelScope önbellek çözücüsünün içe aktarılmasıydı;
  7 model dosyasının özetini (hash) almak ≈ 90 ms sürdü. Boyut/değiştirilme zamanı (mtime) makbuzu daha da hızlıydı ama
  mtime'ı geri yüklenmiş, aynı boyutlu bir içerik değişikliğini kaçırdı. Karar: önbellek kökünü doğrudan geçirmek
  (≈ 2,9 sn kazandırır, tam özet güvenini korur). Üretim artık modelleri ağ olmadan doğrudan yerel önbellekten yükler;
  yalnız yükleme başarısız olursa dosyalar doğrulanır (boyut + SHA-256) ve eksik ya da bozuk bir model bir kez yeniden
  indirilir. Dosyalar sağlamsa indirme değil, gerçek yükleme hatası bildirilir.
- Çakışan konuşmayı ayırma (birkaç ayırma modeli denendi, ≈ 0,8 GB tepe, 10 sn başına 1–2 sn) dinlenerek, sızıntı
  nedeniyle reddedildi.

## 3. Konuşmacı başına cinsiyet ve ses

- İş başına tek cinsiyet işçisi alt süreci: uygun bütün segmentler stdin üzerinden JSON olarak tek toplu işte gider,
  sonuç tek JSON olarak döner, sonra süreç kapanır (RAM ve VRAM tamamen bırakılır). En kısa segment 0,30 sn; konuşmacı
  kipi konuşmacı başına en çok 30 sn ses kullanır.
- Geçmiş: ilk sınıflandırıcı, bir konuşmacı tanıma derlemi üzerinde ince ayar yapılmış bir ECAPA modeliydi. **Bu repo
  `alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech`** (Apache-2.0, LibriSpeech üzerinde eğitilmiş)
  modelini sabitlenmiş bir revizyonda, çevrimdışı yükleyerek kullanır.
- Bilinen sınırlar: sınıflandırıcılarda "bilinmiyor" sınıfı yok; **güven eşiği** uygulanmadı; spektral kümeleme kısa
  röportajlarda konuşmacıları eksik sayar (kurtarmayla düzeltildi); bir bulut ayrıştırıcısı bir kez bir yetişkinle bir
  çocuğu tek konuşmacıda birleştirdi. Türkçe konuşmada doğruluk: henüz **kayıt yok**.
- Bu repoda ses atama: önce açık bir eşleme `{speaker: voice}` uygulanır; kalan konuşmacılar etiket sırasıyla
  algılanan cinsiyetin havuzundan sıradaki boş sesi alır (kadın F1→F5, erkek M1→M5, başa döner); cinsiyet bilinmiyorsa
  kadın havuzu ([sabit_degerler.md](sabit_degerler.md#supertonic-sesleri)). Tek bir TTS çalışma zamanı sesleri
  segment başına değiştirir.

## 4. Tam metin kipi (segment eşlemeye alternatif)

- İlk güvenilir konuşmadan sonuncusuna kadar tek konuşma penceresi; içteki duraklamalar ve konuşmacı değişimleri onu
  bölmez.
- Tek ses, ayrıştırma yok; tek çeviri çağrısı; metin TTS'e tek girdi olarak gider.
- Motor segmentlerinin yettiği yerde kaynak tarafı hizalama atlanır; Parakeet yine hizalanır (alt kelime tokenları
  kelime zamanı değildir).
- Süre uyumu: `audio_to_video` (sesi atempo ile pencereye göre hızlandırıp yavaşlatma) ya da `video_to_audio` (yalnız
  videonun zamanlamasını değiştirme).
- Tam metin için altyazı zamanlaması: pencereler son WAV'daki gerçek parça örnek sayılarından hesaplanır ve CTC ile
  hizalanır; TTS'in iç zamanlaması asla kullanılmaz.

## 5. Açık maddeler

- Cinsiyet güven eşiği; Türkçe konuşmada cinsiyet doğruluğu ölçümü.
- Konuşma süresi sırasının ötesinde cinsiyet başına birden fazla ses (F1/F2, M1/M2 dönüşümü).
- Geçerli iki alt süreçli konuşmacı + cinsiyet yolunun uçtan uca yeni bir ölçümü.
- 1,0 sn boşluk eşiği için A/B kaydı yok.
