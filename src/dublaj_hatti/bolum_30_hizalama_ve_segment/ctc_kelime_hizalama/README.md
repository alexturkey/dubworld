# CTC Kelime Hizalama Kutusu

Bilinen metni sese hizalar ve her kelimenin gerçek başlangıç/bitiş zamanını
üretir. Metni kendisi duymaz; metin transkripsiyon motorundan gelir.

## Kullananlar

| Motor | Çağıran yer |
|---|---|
| CrisperWhisper Turbo CT2 (13. motor) | `bolum_00_omurga/runtime/crisperwhisper_turbo_ct2_runtime.py::align_dubbing_delivery` |
| Whisper.cpp CPU + Align | `whisper_cpp_cpu_align_motoru/ctc_alignment_runner.py` |
| Parakeet CPU + Align | `parakeet_cpu_align_motoru/alignment_runner.py` |
| faster-whisper + CTC (`faster_whisper_ctc`, `auto` yedeği) | `bolum_00_omurga/core/dubber.py::_faster_whisper_ctc_hizala` (model denetimi: `bolum_00_omurga/runtime/ctc_model_durumu.py`) |
| YouTube JSON3 | `youtube_json3_kaynagi/engine.py::_run_ctc_alignment` |

WhisperX motoru bu kutuyu kullanmaz; kendi kutusundaki hizalamayla çalışır.
Zamanı kendisi üreten motorlar (CrisperWhisper Medium, Moonshine, Speechmatics,
ElevenLabs) da bu kutuya girmez.

## Giriş

```python
from bolum_30_hizalama_ve_segment.ctc_kelime_hizalama import run_ctc_word_alignment

data = run_ctc_word_alignment(audio_path, segments_json, language, cache_dir, timeout_seconds,
                              device="cuda", debug_dir=None)
```

- `segments_json`: `[{"start", "end", "text"}]` listesi.
- Dönüş: `success`, `words` (`word`, `start`, `end`, `score`), `segments`,
  `profile_summary`, `alignment_subprocess_seconds`, `command`.
- Hata: `CtcHizalamaHatasi`; zaman aşımı ve bozuk çıktı özgün sebebiyle
  zincirlenir, worker'ın hata metni gizlenmez.
- `worker.py` WhisperX ortamında (`resolve_whisperx_python`) alt süreçte
  çalışır; model iş bitince bellekten bırakılır.

## Kelime sınırı politikası: `ctc_speech_bounded_v2`

`v2`, `v1` sınırlamasını aynen korur ve boşluksuz dillerde kaynak kelimeye
geri toplama ekler (aşağıda). Boşluklu dillerde zamanlar `v1` ile bit bit
aynıdır (bir İngilizce deneme kaydında 660/660 kelime).

1. WhisperX 3.8.6 `align` ile kelime zamanları üretilir (wav2vec2 CTC).
2. Aynı modelin kare kararları torchaudio `forced_align` + `merge_tokens` ile
   ikinci kez işlenir; bu API sessizlik (blank) karelerini token aralığının
   dışında bırakır ve kelimenin gerçek ses aralığını verir.
3. Kelime, gerçek ses aralığının en fazla 150 ms dışına taşabilir. Taşan kısım
   kesilir; iki aralık hiç örtüşmüyorsa kelime modelin sesi duyduğu yere
   taşınır.

Neden: WhisperX torchaudio'nun eski öğretici trellis'ini kullanır; "aynı
token'da kal" geçişi blank skoruyla hesaplandığından duraksama sessizliği
önceki harfe katılır. 100 dakikalık İngilizce seste 10 kelime 1,5 saniyeyi
aşıyor ve 13. motorun `silence-swallowing` kapısında iş duruyordu (başka bir uzun
kayıtta da aynı vaka). Kanıt ve yöntem karşılaştırması:
`deney/ctc_kelime_sonu_sessizlik/README.md`.

Sonuç (aynı ses): 1,5 sn'yi aşan kelime 10 → 0, 40 ms'den kısa kelime
488 → 414, medyan süre 180 ms değişmedi; kelimelerin %3'ü değişti. Kısa
örneklerde segment sayısı ve süreler korunur.

`profile_summary.speech_bounding` her çağrıda sınırlanan, taşınan ve
sınırlanamayan kelime sayısını yazar. Metin/kelime eşleşmezse sınırlama
uygulanmaz ve `status=word_mismatch_unbounded` açıkça raporlanır.

Worker sonucunda `words` ile aynı sırada `speech_spans` listesi döner: her
kelime için ölçülen gerçek ses aralığı `[başlangıç, bitiş]` veya ölçülemediyse
`null`. Kelime nesnelerinin biçimi değişmez; bu yüzden Whisper.cpp, Parakeet ve
YouTube JSON3 çıktıları etkilenmez. 13. motorun teslim kapısı uzun kelimeyi
süreye göre değil, bu ölçülmüş ses aralığına göre değerlendirir (bkz. Turbo
`docs/motor_sozlesmesi.md`).

`ctc_konusma_siniri.longest_silent_run_seconds` modelden bağımsız ham ses
enerjisi ölçümüdür: verilen ses penceresinde kelime içindeki en uzun sessiz
koşuyu saniye olarak, seviye farkı ölçülemiyorsa `None` döndürür. Yalnız
denetim içindir; kelime zamanı üretmez.

## Boşluksuz diller: Japonca ve Çince

WhisperX `ja` ve `zh` için metni boşluktan değil harf harf böler
(`whisperx.alignment.LANGUAGES_WITHOUT_SPACES`); her harf ayrı bir "kelime"
olarak döner ve boşluklar bile joker harf olarak ses karesi tüketir. Çağıran
motorlar ise kaynak kelime sayısının ve dizgelerinin birebir korunmasını
bekler. Bu yüzden worker bu dillerde:

1. WhisperX'e segment metnini boşluksuz verir
   (`ctc_konusma_siniri.no_space_alignment_segments`); segment zamanları aynı kalır.
2. Dönen harfleri sırayla tüketip kaynak kelimelere geri toplar
   (`regroup_character_words`): kelimenin başlangıcı ilk zamanlı harfin
   başlangıcı, bitişi son zamanlı harfin bitişi, skoru harf skorlarının
   ortalamasıdır. Harfler kaynak kelimeyi birebir oluşturmazsa, harf artar
   veya eksik kalırsa `CharacterRegroupError` ile durur. Zamanı olmayan
   kelime zamansız döner ve çağıranın sayı kapısında reddedilir.
3. Konuşma sınırı adımında kelimeler arasına `|` ayırıcısı koymaz
   (`speech_tokens_for_words`).

Kutunun dil kümesi WhisperX'inkinden farklılaşırsa worker açık hata verir.
`profile_summary.no_space_character_regrouping` ve `regrouped_source_words`
her çağrıda yazılır. Bu kural iki dille sınırlıdır; Tay, Lao, Myanmar gibi
diller WhisperX'te boşluklu kabul edilir ve bu yoldan geçmez.

Kök neden vakası: bir Japonca kayıt (13. motor) 23 kaynak kelimeyi harf düzeyine
genişleyen sonuç yüzünden `shared WhisperX alignment changed transcript` ile
durdu. Aynı ses ve kelimelerle düzeltilmiş üretim adaptörü: 23/23 kelime ve
metin birebir, 23 ölçülmüş ses aralığı, 0 sınırlanamayan, 2 uzun kelime
kabul ve 0 ret, onarım 0; worker 23,8 sn (model önbellekte).

## Canlı doğrulama (13. motor üretim adaptörü)

| Ses | Sonuç |
|---|---|
| 100 dk İngilizce | Tamamlandı (önce `silence-swallowing` ile duruyordu). 15.465 kelime, 571 sınırlanan, 177 taşınan, 0 sınırlanamayan; en uzun kelime 1,26 sn; 110 sn sessizlik kelimelerden çıktı. |
| 92 sn İngilizce | Metin birebir aynı; 239 kelimeden 4'ü 10–50 ms kısaldı, taşınan yok. |
| 13,2 dk İngilizce konuşma | Önce sabit 1,5 sn kapısında duruyordu (`ChatGPT-four,` gerçekten 1,662 sn). Ölçülmüş ses aralığı kapısıyla tamamlandı: 1890 kelime, 1890 ölçülmüş aralık, 16 sınırlanan, 8 taşınan, 0 sınırlanamayan. |

Taşınan kelimelerin %80'i `uh`/`um`. WhisperX bunları önceki kelimenin
arkasındaki sessizliğe 40 ms'lik saplama olarak koyuyordu. 10 örnekte kare
kararlarıyla çapraz kontrol: 7'sinde yeni konum sesin tam üstünde; 3'ünde
dolgu sesi çok zayıf olduğundan kelime en yakın sese bağlanıyor (eski konum da
sessizlikteydi).

Maliyet: sınırlama adımı modeli her pencere için bir kez daha çalıştırır;
100 dk seste +85 sn (hizalama 267 sn). WhisperX emisyonlarını dışarı vermediği
için bu tekrar bilinçli tercihtir; WhisperX iç koduna yama yapılmaz.

## Bilinen sınırlar

- Çok zayıf söylenmiş dolgu sesleri (`uh`/`um`) komşu sesin bir parçasına
  bağlanabilir; kelime yine gerçek sesin 150 ms içinde kalır.

- İngilizce torchaudio modelinin sözlüğünde `-` karakteri blank ile aynı
  indekstedir; WhisperX tireyi blank gibi hizalar. 100 dk seste 141 tireli
  kelimenin zamanları diğerlerinden kötü değildir; torchaudio adımı tireyi
  bilinmeyen karakter olarak işler.
- Checkpoint: politika adı Whisper.cpp, Parakeet ve YouTube JSON3'ün
  transkripsiyon girdisine (`ctc_word_boundary_policy`), kutunun dosya
  hash'leri 13. motorun parmak izine girer; politika değişirse transkripsiyon
  ve ardılları yeniden üretilir. `v1` → `v2` geçişi bu dört motorun eski
  transkripsiyon checkpoint'lerini yeniden kullanım dışı bırakır.
