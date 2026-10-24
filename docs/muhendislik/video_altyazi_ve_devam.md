# Video kodlama, altyazılar, ara kayıtlar ve hata yönetimi

English: [../engineering/video_subtitles_and_resume.md](../engineering/video_subtitles_and_resume.md)

Karar kayıtları: [ADR 0011](kararlar.md#0011), [ADR 0012](kararlar.md#0012).

## 1. Kodlayıcı seçimi

- `bolum_60_video_ve_encode/kodlayici.py` süreç başına bir kez, 0,1 sn'lik bir deneme kodlamasıyla karar verir:
  çalışıyorsa `h264_nvenc` (NVENC: NVIDIA kartın donanım video kodlayıcısı), yoksa `libx264` (işlemcide çalışan yazılım
  kodlayıcı). `DUBLAJ_VIDEO_KODLAYICI = auto | nvenc | x264` ile geçersiz kılınır. CPU kipinde
  (`CUDA_VISIBLE_DEVICES=""`) doğrudan x264 kullanılır.
- **Neden deneme kodlaması:** sabitlenmiş FFmpeg derlemesi bazı sürücülerin sağladığından daha yeni bir NVENC API'si
  gerektiriyor ve yalnız CPU'lu makinelerde NVENC yok. Koda gömülü bir NVENC kodlayıcısı hattın bu makinelerde
  başarısız olmasına yol açtı (uçtan uca CPU duman testiyle (smoke test: temel çalışırlık sınaması) bulundu).
- **NVENC ile x264 arasındaki fark içeriğe bağlıdır (ölçüldü):**
  - Dublaj hattı, NVENC `p2`, CQ 23'e karşı 26: üç videoda SSIM (yapısal benzerlik ölçüsü) 0.997 / 0.995 / 0.996, dosyalar
    ≈ %28–30 küçüldü; `p1` daha hızlıydı ama daha büyük dosyalar üretti.
  - Kayıpsız bir referansa karşı çizilmiş, düz renkli video: x264 medium CRF 20 → SSIM 0.9868, 62 MB, 138 sn;
    NVENC `p7` CQ 19 → 0.9849, 138 MB, 88 sn; NVENC CQ'yu düşürmek kalite farkını kapatmadan dosyayı büyüttü (Pascal
    kuşağı NVENC sınırı). Orada x264 kazandı.
  - GPU ile işlenmiş bir sahne (5 sn): x264 CRF 18 VMAF 98.63 / SSIM 0.9918, NVENC CQ 19 VMAF 98.40 / SSIM 0.9923 —
    eşdeğer, NVENC genel olarak 6 kat daha hızlı.
  - Ders: içerik sınıfı başına ve daha yeni GPU'larda yeniden ölç (Turing ve sonrası NVENC B-karelerini destekler).
    Tarif: `ffmpeg -i x.mp4 -i lossless.mp4 -lavfi "[0:v]format=yuv444p[a];[a][1:v]ssim" -f null -`.
    x264 `-threads` değerinin çıktı baytlarını değiştirdiğine dikkat edin; bu yüzden bayt aynılığı testlerinde bedava bir
    hız düğmesi değildir.
- CUDA çıkarımı çalışırken NVENC çalıştırma: eşzamanlı CUDA yükü altında NVENC ≈ 3,6 kat daha yavaştı.

## 2. Kodlama hızı: güvenliği değil yinelenen işi kaldır

### 2.1 Darboğaz doğrulamaydı (ölçüldü)

Gerçek yeniden oynatmalarda yavaş kısım kodlama değil, `ffprobe -count_frames` doğrulamasıydı (uzun bir videoda
297 sn'nin 204'ü). Çözüm: toplu işler hızlı bir akış/süre/FPS denetiminden geçer; yalnız son dosya tam kare sayımı
alır. İki ağır iş: aynı çıktı özetleriyle (hash) 258 → 167 sn ve 418 → 281 sn. Doğrulamayı tamamen kaldırmak
reddedildi.

### 2.2 Tek geçiş ve sınırlı paralellik (ölçüldü)

- **Sorun:** toplu işler kodlanıyor, birleştiriliyor, sonra altyazıları yakmak (burn-in: altyazıyı görüntüye kalıcı
  basmak) ve boyut sınırını uygulamak için **bütün video yeniden kodlanıyordu** (54 dakikalık 1080p60 referansta 27
  dakikanın 13'ü). İkinci kodlama bir kusuru da gizliyordu: video akışı yeni ses zaman çizelgesinden birkaç kare önce
  bitebiliyordu.
- **Çözüm:** altyazılar genel bir kaydırma ile ilk ve tek toplu kodlamada yakılır
  (`setpts=PTS+offset/TB` → `subtitles` → `setpts=PTS-STARTPTS`); kısa toplu işler `tpad=stop_mode=clone` + tam
  `trim=duration` ile tamamlanır; altyazılı çok toplu işli işlerde en çok 3 paralel işçi, en uzun toplu iş önce,
  birleştirme her zaman sıra numarası düzeninde; paralellik altında başarısız olan bir toplu iş sonradan sırayla yeniden
  denenir (NVENC oturum sınırlarını karşılar); son birleştirme (mux) video akışını kopyalar; ölçülen AAC ve profillenmiş
  PCM tek bir süzgeç grafiğinden çıkar.
- **Sonuç:** 35 sn'lik video 15,0 → 12,4 sn; 15 dakikalık sınıf 114 → 67 sn; 54 dakikalık referans 1602 → 668 sn
  (2,4 kat). Her işte zaman çizelgesi farkı 0; ses PCM özeti aynı.
- **Yasak gerilemeler:** ikinci bir tam kodlama, sınırsız paralellik, tamamlanma sırasıyla birleştirme, gevşetilmiş süre
  toleransı, nominal (ölçülmemiş) ses boyutu, video başına istisnalar.
- **Açık:** 54 dakikalık referans için 4–5 dakikalık hedefe kaliteyi, FPS'i, çözünürlüğü ya da altyazıları düşürmeden
  ulaşılamadı.

## 3. Çıktı boyutu ilkesi

- `cq` (varsayılan, CQ 26) ya da `max_mb`. `max_mb` kipinde önce ses (AAC 96 kbps) **gerçekten kodlanır ve ölçülür**;
  kapsayıcı payı = max(1 MB, %1); kalan bütçe sabit bir video bit hızına dönüşür; dosya hâlâ çok büyükse yalnız video bit
  hızını düşüren bir düzeltici yeniden kodlama, sonra kesin hata.
- Her çıktı üst verisinde yapay zekayla dublajlanmış olarak etiketlenir (bkz. reponun ETHICS belgesi).

## 4. Altyazılar

### 4.1 Her motor için tek zamanlama sözleşmesi

- **Sorun:** hat doğrulanmış aday kelime zaman çizelgelerine geçtikten sonra bir motorun altyazı adımı hâlâ eski son
  hizalama dosyasını istiyordu ve geçerli zamanlama var olduğu halde başarısız oluyordu. Eski bir test o dosyayı uydurmuş
  ve kaymayı gizlemişti.
- **Çözüm:** üretici `subtitle_timing_contract.json` yazar (şema sürümü, motor, dil, zamanlama kaynağı ve yöntemi,
  kelime ve segment sayıları, göreli yollar, kanıt yolları). Tüketiciler kapalı-hata (fail-closed: şüphede durma)
  biçiminde doğrular: çalıştırma klasörünün dışında yol yok, sayılar ve motor eşleşmeli, zamanlar sonlu, sıralı, negatif
  olmayan, `end > start`. Görsel işleyici ortaktır (`altyazili_dublaj/burnin.py`), motor başına ince bağdaştırıcılar
  vardır. Altyazılar son birleştirmeden önce hazır değilse iş başarısız olur; asla altyazısız devam etmez. Var olan
  motorlar için öncesi/sonrası bayt bayt aynı ASS çıktısı.

### 4.2 Altyazı zamanlaması nereden gelir

Önceden Türkçe altyazı zamanları TTS motoru sinyallerinden (kelime sınırı olayları, iç dikkat haritası, RMS) geliyordu.
Artık video zaman çizelgesine eşlenmiş doğrulanmış aday zaman çizelgelerinden geliyor; son dublaj izinin
(`audio_new_timeline.wav` + son segment metinleri) zorlamalı hizalaması (forced alignment: metni sese oturtma) yedek
yoldur. Eksik hizalama başka bir yola düşmek yerine işi başarısız kılar.

### 4.3 Çok satırlı kayan stil

Tek ayar sahibi `rollup_profile.json`, 1080 birim yüksekliğinde bir tuval üzerinde: genişlik oranı 0.44, 2 satır (1–8),
yazı tipi boyutu 62, kaydırma 0,25 sn, ≥ 1,0 sn'lik bir duraklama yeni bir satır açar, kuyruk 0,65 sn, en küçük yazı
tipi boyutu 16. Kelimeler asla bölünmez; en uzun kelime sığmazsa yazı tipi bütün işleme için küçülür, en küçük boyutun
altında iş hata verir. Ara kayıt anahtarı profili, işleyicinin SHA-256'sını ve yazı tipi dosyasının SHA-256'sını içerir.

### 4.4 Kaynak altyazı önizlemesi

Her çalıştırma, hattın işlenmiş segmentlerinden (ham ASR'den değil) kurulan segment ve kelime SRT'leriyle bir HTML
önizlemesi yazabilir; yalnız inceleme içindir.

## 5. Ara kayıtlar ve devam etme

- **Aşama grafiği (segment eşleme):** kaynak → ses çıkarma → ayrıştırma (isteğe bağlı) → ASR hazırlığı → transkripsiyon →
  hizalama ve son segmentler → konuşmacı yönlendirme → çeviri → ses/cinsiyet yönlendirme → TTS ve segment sesi → altyazı
  hazırlığı → video zaman çizelgesi ve birleştirme → arka plan karışımı → altyazı yakma → son doğrulama. Tam metin kipinin
  kendi daha kısa dalı vardır. Kanonik listeler `bolum_00_omurga/core/pipeline_checkpoint.py` içindedir.
- **Manifest** `<run>/pipeline_state.json`, atomik olarak (yarım kalmadan, tek seferde) yazılır. Aşama başına: kimlik,
  sıra, sözleşme sürümü, durum (`pending/running/completed/skipped/failed`), girdi SHA-256 parmak izi, deneme sayısı, son
  hata, bir JSON yeniden kurma yükü (asla pickle değil) ve boyut, mtime ve örneklenmiş içerik özetiyle ürünler
  (artefact).
- **Geçersiz kılma:** değişmiş bir girdi özeti ya da sözleşme sürümü o aşamayı ve ondan sonraki her şeyi geçersiz kılar;
  eksik, boş ya da değişmiş bir ürün "tamamlanmadı" demektir; `running` durumunda kalmış bir aşama çökmeden sonra yeniden
  çalışır.
- **Devam etme** kaynak çalıştırmayı asla değiştirmez: gizli bir geçici konumda yeni bir kardeş klasör kurulur ve atomik
  olarak yerine taşınır. Windows'ta virüs koruması/dizinleyici kaynaklı `PermissionError` hataları 5 kısa yeniden deneme
  alır.
- **Kanıt matrisi:** bir TTS hatası ASR ya da çeviriyi yeniden çalıştırmaz; bir hizalama hatası yalnız hizalamayı yeniden
  çalıştırır.
- **Kayıtlı sözleşme yükseltmeleri:** çeviri aşamalarının istemleri değiştiğinde sürümleri yükseltildi; yeni bir TTS
  tarifi TTS'i ve ondan sonraki her şeyi yeniden üretir; CTC sınırlama politikası transkripsiyonu geçersiz kılar.
- Yeniden oynatma kuralı: segment dosyaları zaten yeni zaman çizelgesi zamanlarını taşıyor olabilir; dürüst yeniden
  oynatmalar için özgün sınırları saklanan özgün başlangıç/bitiş değerlerinden yeniden kur.

## 6. Kullanıcının gördüğü hatalar

- `runtime/hata_aciklama.py`: tek mesaj biçimi (başlık, aşama, kök sınıf + ≤ 300 karakterlik maskelenmiş mesaj ve bir
  kural tablosundan açıklama). Anahtarlar ve tokenlar maskelenir; mutlak yollar `<yol>/file` biçimine indirilir.
- Kurallar: sessiz yedek yok (NVENC → x264 yedek değil, eşdeğer bir yol sayılır); `raise … from`; tek bir başarısız TTS
  segmenti ya da çeviri sayısı uyuşmazlığı işi durdurur.
- Tetikleyen olay: hız sınırına takılan bir çevirmen kaynak metne geri düştü ve çevrilmemiş bir video "tamamlandı"
  olarak teslim edildi.

## 7. Bu reponun uçtan uca CPU duman testinden dersler

| Bulgu | Kök neden | Çözüm |
|---|---|---|
| `No module named pkg_resources` | bir model merkezi kütüphanesi hâlâ ona ihtiyaç duyuyor; kilitlenmiş setuptools sürümü onu kaldırdı | `setuptools==80.9.0` sabitle |
| `No module named datasets` | konuşmacı ayrıştırma hattı onu içe aktarıyor | `datasets==3.1.0` sabitle |
| fastcluster içinde `_ARRAY_API not found` | tekerlek (wheel) NumPy 1.x'e karşı derlenmiş, kilitte NumPy 2 var | `fastcluster==1.3.0` |
| kurucu kilidi çözemedi | iki paket dizini; uv ilkine kilitleniyor | `--index-strategy unsafe-best-match` (özetler yine zorunlu) |
| `-filter_complex_script` tanınmadı | FFmpeg 7+ bu seçeneği kaldırdı | `-/filter_complex` kullan |
| CPU kipinde / eski sürücüde NVENC kullanıldı | kodlayıcı koda gömülüydü | deneme kodlamasıyla seçim (§1) |
| PowerShell kurucusunda Türkçe metin bozuk | Windows PowerShell 5.1 BOM'suz UTF-8'i ANSI olarak okur | betikleri BOM'lu UTF-8 olarak kaydet |
| ayar şemasındaki çeviri arka uç adları köprü tarafından bilinmiyordu | iki ayrı ad listesi | tek liste + takma adlar + bir test |
