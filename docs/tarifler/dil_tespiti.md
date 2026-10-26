# Recipe: source-language detection

[Türkçe](#türkçe) · Settings: `transkripsiyon.kaynak_dil` (`auto` or an ISO code) and
`transkripsiyon.crisper_dil_tespiti`. Rules: `yapilandirma.uyumluluk_denetle()`; tests: `tests/test_dil_tespiti.py`
(GPU-free, with fake models) and `tests/test_dil_ses_donanim.py`.

## Which mode when

| Your video | Engine | Settings |
|---|---|---|
| One language, unknown | any multilingual engine | `kaynak_dil = "auto"` (default) |
| One language, known | faster-whisper, whisperx, CrisperWhisper, cloud | `kaynak_dil = "en"` (skips detection; safest) |
| Several languages / code-switching (speakers switch language mid-video) | CrisperWhisper Turbo or Medium | `crisper_dil_tespiti = "continuous_stream"`, `kaynak_dil = "auto"` |
| Long video, language changes between sections | CrisperWhisper Medium | `crisper_dil_tespiti = "per_window"` |
| English only, CPU | parakeet | `kaynak_dil = "auto"` or `"en"` |
| Fast English on GPU | faster-whisper with `distil-large-v3` | `kaynak_dil = "auto"`: a non-English video automatically switches to a multilingual model |
| YouTube link with captions | `youtube_translate` | language comes from the caption track; `kaynak_dil` is ignored (warning) |

Priority (same as the original application): **platform language** (the video site's metadata, only for links) >
**fixed language** (`kaynak_dil`) > **automatic detection**.

## All modes (inventory of the source code)

| # | Engine | Mode | What it does | Setting | Constants |
|---|---|---|---|---|---|
| 1 | faster-whisper | automatic | the library's own detection on the first window inside `transcribe` | `kaynak_dil = "auto"` | library defaults |
| 2 | faster-whisper, whisperx | fixed | language passed straight to the model | `kaynak_dil = "<iso>"` | — |
| 3 | faster-whisper `distil-*` | English gate | `detect_language` over 3 VAD segments; not `en` or P(en) < 0.90 → fallback | automatic with distil + `auto` | threshold 0.90 |
| 4 | faster-whisper `distil-*` | pre-check | a known non-English language skips distil entirely | distil + fixed non-`en` | — |
| 5 | distil / parakeet | multilingual fallback | re-runs with WhisperX large-v3-turbo float32 (int8 once on CUDA out-of-memory); record `transcription_<family>_language_fallback.json` | automatic | — |
| 6 | whisperx | automatic / fixed | `transcribe(language=None or code)`; detected language also selects the CTC alignment model | `kaynak_dil` | library defaults |
| 7 | CrisperWhisper Turbo / Medium | `global_first_window` | one detection on the first 29.5 s, applied to the whole file | `crisper_dil_tespiti = "global_first_window"` | 29.5 s window |
| 8 | CrisperWhisper Turbo / Medium | fixed / platform | detection skipped, probability 1.0 (only in `global_first_window`) | `kaynak_dil = "<iso>"` or link metadata | — |
| 9 | CrisperWhisper Turbo / Medium | `continuous_stream` (code-switching, change point) | a tick every 1 s over a 4 s context (+ a final coverage tick); a tick counts only if top probability ≥ 0.6 and margin ≥ 0.2; a new language needs 2 consecutive confident ticks; the boundary is the midpoint between the last stable and first confirmed tick; main language = longest total duration | `crisper_dil_tespiti = "continuous_stream"` | 4.0 s / 1.0 s / 2 ticks / 0.6 / 0.2 |
| 10 | CrisperWhisper **Medium only** | `per_window` | VAD-planned windows (target 25 s, max 29.5 s, min 5 s), language per window, equal neighbours merged into runs | `crisper_dil_tespiti = "per_window"` | 25 / 29.5 / 5 s |
| 12 | parakeet | English only + fallback | non-English → mode 5 | — | — |
| 15 | youtube_translate | caption track | track in the video's language, else `en`, else any | — | — |

Notes:

- **Fixed language now reaches every engine.** In the original application CrisperWhisper, Speechmatics and
  ElevenLabs read only the platform language, so `kaynak_dil` was silently ignored for local files. Here a fixed
  `kaynak_dil` is passed through the same platform-language route (`dubber._sabit_dil_platform_yerine`); in the job
  record it appears as `language_source = platform_metadata`.
- **Rejected combinations (settings error):** `per_window` with `crisperwhisper_turbo_ct2` or `auto` (the Turbo
  engine supports only `global_first_window` and `continuous_stream`); `whisperx` + `distil-*` + fixed non-English
  language (the multilingual fallback exists only for faster-whisper); English-only engines with a non-English
  `kaynak_dil`.
- **Warnings:** fixed `kaynak_dil` with `continuous_stream` / `per_window` (detection still runs);
  `youtube_translate` with a fixed `kaynak_dil` (ignored); `crisper_dil_tespiti` with a non-Crisper engine (ignored).

Examples:

```
dubla video.mp4 --ayar transkripsiyon.kaynak_dil=en
dubla video.mp4 --ayar transkripsiyon.motor=crisperwhisper_turbo_ct2 --ayar transkripsiyon.crisper_dil_tespiti=continuous_stream
dubla video.mp4 --ayar transkripsiyon.motor=crisperwhisper2_medium --ayar transkripsiyon.crisper_dil_tespiti=per_window
```

---

## Türkçe

Ayarlar: `transkripsiyon.kaynak_dil` (`auto` ya da bir ISO kodu) ve `transkripsiyon.crisper_dil_tespiti`. Kurallar:
`yapilandirma.uyumluluk_denetle()`; testler: `tests/test_dil_tespiti.py` (GPU'suz, sahte modellerle) ve
`tests/test_dil_ses_donanim.py`.

### Hangi durumda hangi kip

| Videonuz | Motor | Ayarlar |
|---|---|---|
| Tek dil, bilinmiyor | herhangi bir çok dilli motor | `kaynak_dil = "auto"` (varsayılan) |
| Tek dil, biliniyor | faster-whisper, whisperx, CrisperWhisper, bulut | `kaynak_dil = "en"` (tespit atlanır; en güvenlisi) |
| Birden çok dil / kod değişimi (konuşmacılar video içinde dil değiştiriyor) | CrisperWhisper Turbo ya da Medium | `crisper_dil_tespiti = "continuous_stream"`, `kaynak_dil = "auto"` |
| Uzun video, bölümler arasında dil değişiyor | CrisperWhisper Medium | `crisper_dil_tespiti = "per_window"` |
| Yalnız İngilizce, işlemci | parakeet | `kaynak_dil = "auto"` ya da `"en"` |
| GPU'da hızlı İngilizce | `distil-large-v3` ile faster-whisper | `kaynak_dil = "auto"`: İngilizce olmayan video kendiliğinden çok dilli modele geçer |
| Altyazılı YouTube bağlantısı | `youtube_translate` | dil altyazı izinden gelir; `kaynak_dil` yok sayılır (uyarı) |

Öncelik (kaynak uygulamadaki gibi): **platform dili** (video sitesinin üst verisi, yalnız bağlantılarda) >
**sabit dil** (`kaynak_dil`) > **otomatik tespit**.

### Bütün kipler (kaynak kodun envanteri)

| # | Motor | Kip | Ne yapar | Ayar | Sabitler |
|---|---|---|---|---|---|
| 1 | faster-whisper | otomatik | kütüphanenin `transcribe` içindeki kendi tespiti, ilk pencerede | `kaynak_dil = "auto"` | kütüphane varsayılanları |
| 2 | faster-whisper, whisperx | sabit | dil doğrudan modele verilir | `kaynak_dil = "<iso>"` | — |
| 3 | faster-whisper `distil-*` | İngilizce kapısı | 3 VAD segmenti üzerinde `detect_language`; `en` değilse ya da P(en) < 0.90 ise → yedek | distil + `auto` ile otomatik | eşik 0.90 |
| 4 | faster-whisper `distil-*` | ön denetim | bilinen İngilizce dışı dil distil'i tamamen atlar | distil + `en` dışı sabit dil | — |
| 5 | distil / parakeet | çok dilli yedek | WhisperX large-v3-turbo float32 ile yeniden çalışır (CUDA bellek taşmasında bir kez int8); kayıt `transcription_<family>_language_fallback.json` | otomatik | — |
| 6 | whisperx | otomatik / sabit | `transcribe(language=None ya da kod)`; tespit edilen dil CTC hizalama modelini de seçer | `kaynak_dil` | kütüphane varsayılanları |
| 7 | CrisperWhisper Turbo / Medium | `global_first_window` | ilk 29.5 s üzerinde tek tespit, bütün dosyaya uygulanır | `crisper_dil_tespiti = "global_first_window"` | 29.5 s pencere |
| 8 | CrisperWhisper Turbo / Medium | sabit / platform | tespit atlanır, olasılık 1.0 (yalnız `global_first_window` içinde) | `kaynak_dil = "<iso>"` ya da bağlantı üst verisi | — |
| 9 | CrisperWhisper Turbo / Medium | `continuous_stream` (kod değişimi, değişim noktası) | 4 s bağlam üzerinde her 1 s'de bir tık (+ son kapsama tıkı); bir tık yalnız en yüksek olasılık ≥ 0.6 ve fark ≥ 0.2 ise sayılır; yeni dil için art arda 2 emin tık gerekir; sınır, son kararlı tık ile ilk onaylanan tıkın orta noktasıdır; ana dil = toplam süresi en uzun dil | `crisper_dil_tespiti = "continuous_stream"` | 4.0 s / 1.0 s / 2 tık / 0.6 / 0.2 |
| 10 | **Yalnız** CrisperWhisper **Medium** | `per_window` | VAD ile planlanan pencereler (hedef 25 s, en çok 29.5 s, en az 5 s), pencere başına dil, eşit komşular dizilere birleştirilir | `crisper_dil_tespiti = "per_window"` | 25 / 29.5 / 5 s |
| 12 | parakeet | yalnız İngilizce + yedek | İngilizce dışı → kip 5 | — | — |
| 15 | youtube_translate | altyazı izi | videonun dilindeki iz, yoksa `en`, yoksa herhangi biri | — | — |

Notlar:

- **Sabit dil artık her motora ulaşır.** Kaynak uygulamada CrisperWhisper, Speechmatics ve ElevenLabs yalnız
  platform dilini okuyordu; bu yüzden yerel dosyalarda `kaynak_dil` sessizce yok sayılıyordu. Burada sabit
  `kaynak_dil` aynı platform dili yolundan iletilir (`dubber._sabit_dil_platform_yerine`); iş kaydında
  `language_source = platform_metadata` olarak görünür.
- **Reddedilen birleşimler (ayar hatası):** `crisperwhisper_turbo_ct2` ya da `auto` ile `per_window` (Turbo motoru
  yalnız `global_first_window` ve `continuous_stream` destekler); `whisperx` + `distil-*` + İngilizce olmayan sabit
  dil (çok dilli yedek yalnız faster-whisper'da var); İngilizce dışı `kaynak_dil` ile yalnız İngilizce motorlar.
- **Uyarılar:** `continuous_stream` / `per_window` ile sabit `kaynak_dil` (tespit yine çalışır); sabit `kaynak_dil`
  ile `youtube_translate` (yok sayılır); Crisper dışı motorla `crisper_dil_tespiti` (yok sayılır).

Örnekler:

```
dubla video.mp4 --ayar transkripsiyon.kaynak_dil=en
dubla video.mp4 --ayar transkripsiyon.motor=crisperwhisper_turbo_ct2 --ayar transkripsiyon.crisper_dil_tespiti=continuous_stream
dubla video.mp4 --ayar transkripsiyon.motor=crisperwhisper2_medium --ayar transkripsiyon.crisper_dil_tespiti=per_window
```
