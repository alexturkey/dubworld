# YouTube json3 captions + CTC (`youtube_translate`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** A transcription engine option. It runs no speech recognition: it takes the words of the video's
YouTube **automatic captions** (json3) as text and regenerates the word times from the audio with the pipeline's own
CTC (wav2vec2) alignment. The json3 times are only a hint for the alignment window. It is fast; accuracy depends on
the quality of the captions.

| | |
|---|---|
| License | code: yt-dlp Unlicense; text: the video's captions (YouTube terms); alignment weights same as the CTC engine |
| Install | `pip install .[youtube]` |
| Hardware | as much as CTC alignment: GPU or CPU, ~2 GB RAM (estimate) |
| Default | off (the recommended flow uses faster-whisper / CrisperWhisper) |

**Setting:** `transkripsiyon.motor = "youtube_translate"`; the input must be a YouTube link (a local file gives an
error). Output: `youtube_json3_transkripsiyon_kaynagi/` in the job folder (raw json3, clean words, alignment quality
report).

**Responsible use:** Only content you own or are permitted to use; the platform terms are the user's responsibility.

**Common errors**
- `yt-dlp kurulu değil` → `pip install .[youtube]`.
- `YouTube JSON3 otomatik altyazisi bulunamadi` → the video has no automatic captions; choose another STT engine.
- `zaman duzeltmesi guvenli siniri asti` → captions and audio are badly mismatched (e.g. music); choose another engine.

## How it works in this pipeline / Neden böyle

- **Principle:** No speech recognition runs. The words in the video's automatic captions (json3) are cleaned
  (non-speech tags such as `[music]` are not counted as words) and taken as text; the json3 times are only a hint for
  preparing the alignment window. The start and end of every word come from the shared CTC alignment
  ([ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)).
- **Why this choice:** it is a fast text source with no recognition cost. Caption times are not reliable at word
  level, so they are not used directly. If json3 is missing, no other caption format is tried and no missing words are
  generated; if the aligned word list does not match the clean list one to one, the job stops
  ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)).
- **How it fits:** the input is a YouTube link (a local file is an error); the 1.0 s leading pad is not applied; the
  output is the same transcript contract as the other engines and goes to the same segmenter. The timeout grows with
  the duration.
- Details: [transcription.md](../engineering/transcription.md) §8
- Timing sources and pre-check: [timing-sources.md](../engineering/timing-sources.md) §3 / [zaman_kaynaklari.md](../muhendislik/zaman_kaynaklari.md) §3
- Place in the end-to-end flow: [pipeline-flow.md, segmentation per engine](../engineering/pipeline-flow.md#7-segmentation-per-transcription-engine)

## Türkçe

**YouTube json3 altyazı + CTC (`youtube_translate`)**

**Ne yapar:** Transkripsiyon motoru seçeneği. Ses tanıma çalıştırmaz: videonun YouTube **otomatik altyazısının**
(json3) kelimelerini metin olarak alır, kelime zamanlarını hattın kendi CTC (wav2vec2) hizalamasıyla sesten yeniden
üretir. json3 zamanları yalnız hizalama penceresi ipucudur. Hızlıdır; doğruluk altyazının kalitesine bağlıdır.

| | |
|---|---|
| Lisans | kod: yt-dlp Unlicense; metin: videonun altyazısı (YouTube şartları); hizalama ağırlığı CTC motoruyla aynı |
| Kurulum | `pip install .[youtube]` |
| Donanım | CTC hizalama kadar: GPU ya da işlemci, ~2 GB RAM (tahmini) |
| Varsayılan | kapalı (Önerilen akış faster-whisper / CrisperWhisper kullanır) |

**Ayar:** `transkripsiyon.motor = "youtube_translate"`; girdi bir YouTube bağlantısı olmalı (yerel dosyada hata
verir). Çıktı: iş klasöründe `youtube_json3_transkripsiyon_kaynagi/` (ham json3, temiz kelimeler, hizalama
kalite raporu).

**Sorumlu kullanım:** Yalnız hakkınız olan ya da izinli içerik; platform şartları kullanıcıya aittir.

**Sık hata**
- `yt-dlp kurulu değil` → `pip install .[youtube]`.
- `YouTube JSON3 otomatik altyazisi bulunamadi` → videoda otomatik altyazı yok; başka STT motoru seçin.
- `zaman duzeltmesi guvenli siniri asti` → altyazı ile ses çok uyumsuz (ör. müzik); başka motor seçin.

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** Ses tanıma çalışmaz. Videonun otomatik altyazısındaki (json3) kelimeler temizlenir (`[music]` gibi konuşma dışı
  etiketler kelime sayılmaz) ve metin olarak alınır; json3 zamanları yalnız hizalama penceresini hazırlamak için ipucudur.
  Her kelimenin başlangıç ve bitişi ortak CTC hizalamasından gelir ([ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)).
- **Neden böyle:** tanıma maliyeti olmadan hızlı bir metin kaynağıdır. Altyazı zamanları kelime düzeyinde güvenilir
  olmadığı için doğrudan kullanılmaz. json3 yoksa başka altyazı biçimine geçilmez, eksik kelime üretilmez; hizalanan kelime
  listesi temiz listeyle bire bir eşleşmezse iş durur ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)).
- **Diğer parçalarla ahengi:** girdi bir YouTube bağlantısıdır (yerel dosya hatadır); baştaki 1,0 sn pay uygulanmaz;
  çıktı diğer motorlarla aynı transkript sözleşmesidir ve aynı segmentleyiciye gider. Zaman aşımı süreye göre büyür.
- Ayrıntı: [transcription.md](../engineering/transcription.md) §8
- Zaman kaynakları ve ön denetim: [timing-sources.md](../engineering/timing-sources.md) §3 / [zaman_kaynaklari.md](../muhendislik/zaman_kaynaklari.md) §3
- Uçtan uca akıştaki yeri: [hat_akisi.md, motora göre segmentleme](../muhendislik/hat_akisi.md#7-transkripsiyon-motoruna-göre-segmentleme)
