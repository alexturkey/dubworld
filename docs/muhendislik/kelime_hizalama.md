# Kelime hizalama (CTC zorlamalı hizalama)

English: [../engineering/word_alignment.md](../engineering/word_alignment.md)

Hattaki her kelime zamanının neden CTC zorlamalı hizalamadan (CTC forced alignment: bilinen metni sesin üzerine
kelime kelime oturtma) geldiği, pencerelerin nasıl hazırlanması gerektiği ve "kelimenin içine yutulan sessizlik"
sorununun nasıl çözüldüğü.
Karar kaydı: [ADR 0005](kararlar.md#0005).

## 1. Mimari

- **WhisperX motoru:** kendi işçi sürecinin (worker: işi ayrı süreçte yapan program) içinde yerleşik `whisperx.align()`
  işlevini kullanır.
- **Ortak CTC kutusu** `bolum_30_hizalama_ve_segment/ctc_kelime_hizalama/` (`client.py`, `worker.py`,
  `ctc_konusma_siniri.py`): kendi zamanlarına güvenilmeyen motorlar için: CrisperWhisper Turbo, faster-whisper + CTC
  (`faster_whisper_ctc`, `auto`'nun yedeği), Parakeet + hizalama, altyazı dosyası kaynakları.
- Kendi zamanlarını üreten ve kutuya girmeyen motorlar: elle seçilen `faster-whisper` (yerel kelime zaman damgaları, distil olsun olmasın).
- **API:** `run_ctc_word_alignment(audio_path, segments_json, language, cache_dir, timeout_seconds, device="cuda", debug_dir=None)`;
  girdi `[{start, end, text}]`; dönüş `words{word,start,end,score}`, `segments`, `profile_summary`, `speech_spans`.
  Hatalar, işçinin kendi mesajıyla `CtcHizalamaHatasi` fırlatır.
- Bir alt süreçte çalışır (WhisperX 3.8.6); süreç kapanınca model bellekten bırakılır.
- Aynı hizalayıcı **üretilen** tarafta da kullanılır: TTS (metinden konuşma sentezi) adayları ve son dublaj izi yeniden
  hizalanır (bkz. [tts_zamanlama_ve_karisim.md](tts_zamanlama_ve_karisim.md)).

### Hizalama modelleri (wav2vec2)

| Dil | Model |
|---|---|
| en | torchaudio `WAV2VEC2_ASR_BASE_960H` |
| tr | `mpoyraz/wav2vec2-xls-r-300m-cv7-turkish` (CC BY 4.0, atıf gerekir) |
| id | `Galuh/wav2vec2-large-xlsr-indonesian` (proje eşlemesi; WhisperX'in varsayılan tablosunda `id` yok) |
| pt, ko, el, zh | WhisperX varsayılan modelleri |

İngilizce için reddedilenler (ölçüldü): tensörleri GPU'ya önceden yüklemek (aynı çıktı, %1,4–1,9 daha yavaş);
`WAV2VEC2_ASR_BASE_10M` (kelime zamanları farklı çıktı, hız kazancı yok).

## 2. Neden CTC, neden başka bir şey değil

| Alternatif | Neden reddedildi |
|---|---|
| Motorun segment sınırları | Konuşmadaki duraklamaları değil, modelin bağlam penceresini izler. Ölçüldü: 27,4 sn'lik bir motor segmentinde 60 kelime vardı ama yalnız 17,2 sn konuşma ve 10,2 sn boşluk vardı; TTS 17 sn'lik konuşmayı 27 sn'ye yayacaktı |
| RMS kırpma (ses yüksekliğine göre kesme), TTS motorunun kelime sınırı olayları, TTS'in iç dikkat (attention) haritası, süre oranıyla ölçekleme | Gerçek sesin ölçümü değil, tahmin; altyazıda, aday seçiminde ve kesimlerde kaymaya ve sahte güvene yol açtı. Zaman kaynağı olarak yasaklandı; eksik hizalama yedeğe düşmek yerine açıkça hata verir |
| Hassas yol için Whisper'ın yerel kelime zaman damgaları | Yalnız distil hız seçeneği için tutuldu. 42 dk İngilizcede ticari bir referansa karşı ölçüldü: WhisperX + CTC WER (kelime hata oranı) %12,1, distil yerel %16,2 |
| Her motora ayrı hizalayıcı | Yerine tek ortak girdi hazırlama katmanı + tek CTC kutusu geldi; motorlar yalnız elindeki zaman kanıtını bildirir (kelime, token, segment ya da hiç) |
| Hız için CTC modelini değiştirmek | Kapsam dışı: yalnız aracın çalıştırılma biçimi değişebilir, aracın kendisi değil |

## 3. Pencere hazırlığı önemlidir (Parakeet vakası)

- **Sorun:** hazırlık katmanı A konuşmasını, ≈ 6,4 sn konuşma olmayan bölümü ve B konuşmasını tek CTC penceresinde
  birleştirdi. CTC, B'deki doğru kelimeyi buldu ama sessizliği o kelimenin başlangıcına çekti. Metin doğruydu; süreler
  şişti ve bu da dublajda olağan dışı hızlanmalara yol açtı. Boşluğu motorun kendisi de bildirmişti (son token ≈ 16,0 sn,
  sonraki ≈ 22,4 sn).
- **Kök neden:** yanlış bir zihinsel model ("CTC'ye metni ve geniş bir pencere ver, sessizliği kendisi atlar"). CTC kısa
  boşlukları (≈ 0,4 sn) iyi işler; uzun ve belirsiz boşluklarda sessizliği ya da müziği komşu kelimeye ekleyebilir.
- **Çözüm:** yeni bir kelime başlatan ≥ 1,0 sn'lik token boşluğu doğal boşluktur. Sol pencere önceki tokendan 80 ms sonra
  kapanır, sağ pencere sonraki tokendan 80 ms önce açılır (80 ms = bir Parakeet kodlayıcı (encoder) karesi). Uzun bir
  sessizliğin ortası hiçbir pencereye girmez. Hizalama girdisi sözleşmesine sürüm verildi; böylece eski pencereler bir
  ara kayıttan (checkpoint) asla yeniden kullanılmaz.
- **Genel kural:** dolgu payı her motorun kendi zaman çözünürlüğünden gelir; 80 ms asla başka bir motora kopyalanmaz.
- **Zorunlu son denetimler:** her kelime zamanlanmış; hiçbiri düşmemiş; sıra korunmuş; aşırı uzun kelime yok; yutulmuş
  sessizlik yok; başlangıç ve bitişler tekdüze artan (monoton); çakışma yok; ses sonunun ötesinde hiçbir şey yok.

## 4. Kelime sonlarında yutulan sessizlik: `ctc_speech_bounded_v2`

- **Sorun:** 100 dakikalık bir İngilizce dosyada 15.465 kelimeden 10'u 1,5 sn'den uzundu (8'i "uh"/"um") ve
  CrisperWhisper uzun kelime kapısı işi doğru biçimde durdurdu.
- **Kök neden (kare kare ölçüldü):** uzamış kelimelerin içindeki karelerin %79–98'i boştu (blank: CTC'nin "burada
  karakter yok" durumu). WhisperX 3.8.6 eski öğretici (tutorial) kafesini (trellis: olası hizalamaların puan tablosu)
  kullanıyor; burada "aynı tokenda kal" adımı blank puanıyla puanlanıyor, bu yüzden tekrarlı birleştirme boş kareleri
  önceki karaktere katlıyor. torchaudio'nun daha yeni `forced_align` + `merge_tokens` ikilisi blank'i ayrı bir durum
  olarak ele alır. (Daha önceki motora özel bir hizalayıcı bunu düzeltmişti; motorlar ortak kutuya taşınınca bu düzeltme
  kayboldu.)
- **100 dakikalık dosyada ölçülen varyantlar:**

| Varyant | > 1,5 sn kelime | < 40 ms kelime | ortanca | en uzun |
|---|---|---|---|---|
| WhisperX olduğu gibi | 10 | 488 | 180 ms | 2,24 sn |
| argmax karelerine göre kırpma | 9 | 805 | 180 ms | 2,12 sn |
| yalnız torchaudio `forced_align` | 0 | 1.457 | 140 ms | 1,18 sn |
| **WhisperX, torchaudio aralığı ± 150 ms'ye sıkıştırılmış** | **0** | **414** | **180 ms** | **1,26 sn** |

  - Yalnız torchaudio reddedildi: sivri (spiky) çıktısı kelimelerin %9'unu 40 ms'nin altına itti ve 40 ms'lik bir kelime
    sonraki adımlarda ≈ 14 kat video yavaşlamasına yol açabilir.
  - argmax kırpma reddedildi: kelime ayırıcısı ses olarak sayılıyor.
  - İki bağımsız yöntem kelime başlangıçlarında 20 ms içinde (p95) uyuştu; sonuç 100–200 ms dolgu paylarında kararlıydı.
- **Yayınlanan:** WhisperX zamanları korunur; aynı modelin kare kararları torchaudio'dan yeniden geçirilerek her
  kelimenin gerçek konuşma aralığı bulunur; bir kelime bu aralığın en çok 150 ms ötesine uzanabilir; hiç çakışma yoksa
  kelime sesin duyulduğu yere taşınır. `speech_spans` kelime sırasıyla döndürülür; metin uyuşmazlığında hiçbir şey
  sınırlanmaz ve bu durum bildirilir.
- **Sonrasında ölçülen:** 100 dakikalık dosya tamamlanıyor (571 kelime kırpıldı, 177'si taşındı, 0 sınırsız, en uzun
  kelime 1,26 sn, kelimelerden toplam 110 sn sessizlik çıkarıldı, kelimelerin %3'ü değişti). 92 sn'lik bir dosya: metin
  aynı, 239 kelimeden 4'ü 10–50 ms kısaldı. Taşınan kelimelerin örnek denetimi: 10'dan 7'si tam sesin üzerine düşüyor;
  çok zayıf 3 dolgu sözcüğü (filler) en yakın sese bağlanıyor.
- **Bedel:** 100 dakikada ≈ +85 sn (model her pencerede iki kez çalışıyor); WhisperX emisyonları (karelerin olasılık
  çıktısı) dışarı vermediği ve iç kodu yamanmadığı için kabul edildi.

## 5. Boşluksuz yazı sistemleri (Japonca, Çince)

WhisperX `ja`/`zh` metnini karakterlere böler ve boşluklar kare tüketir. Bir Japonca iş "alignment changed transcript"
hatasıyla durdu. Çözüm: segment metni boşluksuz gönderilir, dönen karakterler kaynak kelimelere yeniden gruplanır (ilk
karakterin başlangıcı, son karakterin bitişi, ortalama puan), fazla ya da eksik her karakterde hata fırlatılır.
Ölçüldü: 23/23 kelime, 0 onarım. Tayca, Laoca ve Birmanca WhisperX tarafından boşluklu sayılır ve bu yoldan geçmez.
Sonraki adımlarda `ja, zh, yue, th, lo, my` için segment metni boşluksuz birleştirilir ve tam genişlikli noktalama ASCII
noktalama gibi sayılır.

## 6. Sayılar ve semboller (WhisperX 3.8.2 → 3.8.6)

- WhisperX 3.8.2'nin temiz hizalamasında rakam ve sembol içeren tokenlar (`31%`, `10604`, para birimi) **düşürülüyordu**.
- İlk çözüm: bir LLM (büyük dil modeli) çağrısı sayıları hizalamadan önce yazıya döktü ve hizalanan kelimeleri asıl
  tokenların üzerine geri izdüşürdü (her eşleme uyuşmazlığında hemen hata). Çalıştı (174 normalleştirilmiş token, 168
  asıl tokena kayıpsız eşlendi).
- Son çözüm: bu tokenları yerel olarak hizalayan **WhisperX 3.8.6**'ya yükseltme (`$50`, `31%`, `10,604`, `+ - / =`
  içeren gerileme (regression) örneklerinde 124/124 ve 91/91 kelime). LLM normalleştirici kaldırıldı; artık hizalamadan
  önce metni hiçbir şey yeniden yazmıyor.
- Bir "hızlı joker" (fast wildcard) kafes yaması (67 dakikalık dosyada hizalama 204 → 184 sn, 3.8.2 altında aynı çıktı)
  3.8.6 altında bir eksik/fazla bir (off-by-one) `IndexError` üretti ve varsayılan olarak kapalı. Geri izleme (backtrack)
  ışın genişliği 1, uzun referansta 4 kelime zamanını kaydırdı; varsayılan 2 olarak kalıyor.

## 7. GPU ve CPU

Varsayılan `device="cuda"`. `device="cpu"` geçiren bir alt araç 3,5 dakikalık ses için ≈ 10 dakika sürdü; GPU'da aynı
iş 66–71 sn sürdü, çoğu model yüklemesiydi (ölçüldü). Çok uzun girdiler için parçalı hizalama gerekir (işçi zaman aşımı
900 sn).

## 8. Açık maddeler

- Hiç zaman kanıtı olmayan motorlar için pencere hazırlığı (VAD yedeği; VAD: konuşma etkinliği tespiti) kural olarak
  tanımlı ama hiç ölçülmedi.
- Çok zayıf dolgu sözcükleri komşu sese bağlanabilir (150 ms içinde).
- Sınırlama politikasının adını değiştirmek, kutuyu kullanan tüm motorların transkripsiyon ara kayıtlarını geçersiz
  kılar (bilerek böyle tasarlandı).
