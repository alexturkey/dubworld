# faster-whisper + CTC alignment (`faster_whisper_ctc`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Text from faster-whisper (Whisper large-v3-turbo, CTranslate2); word times from the shared wav2vec2
CTC alignment box. This is what `transkripsiyon.motor = auto` uses when CrisperWhisper Turbo cannot run (no NVIDIA GPU,
or not installed).

| | |
|---|---|
| License | MIT (faster-whisper and the large-v3-turbo conversion); alignment weights: `tr` CC BY 4.0 (attribution, `NOTICE`), `en` MIT (fairseq) — see [THIRD_PARTY.md](../../THIRD_PARTY.md) |
| Commercial use | yes |
| Source | https://github.com/SYSTRAN/faster-whisper , https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo |
| Install | base install (`scripts/kur.ps1`, step `modeller`: model steps `stt` + `hizalama`) |
| Hardware | recognition and alignment run one after another in separate processes: recognition GPU int8 ≈ 1.15 GB VRAM, CTC 1.65–2.4 GB VRAM (measured); CPU works (timings below) |
| Languages | multilingual recognition; word times need a CTC model for the language: `en`, `tr` pinned; other languages only after a deliberate download (`DUBLAJ_CEVRIMICI=1`) |
| Default | fallback of `transkripsiyon.motor = auto` |

**Settings**

- `transkripsiyon.motor = "faster_whisper_ctc"` (or `auto`)
- `transkripsiyon.model`, `transkripsiyon.hesap_tipi`, `transkripsiyon.kaynak_dil`: as for [faster-whisper](faster-whisper.md)
- To keep Whisper's own word times on purpose, choose `transkripsiyon.motor = "faster-whisper"`.

**CPU timings (measured, one short run each, `genel.cihaz = cpu`)**

| Audio | Recognition (large-v3-turbo int8, incl. model load) | CTC alignment (whole step, incl. ≈ 10 s model load) |
|---|---:|---:|
| 23.8 s English | ≈ 140 s | 16.5 s (base-960h) |
| 60 s Turkish | ≈ 161 s | 42.9 s (xls-r-300m) |

**Common errors**

- `CTC hizalama modeli kurulu değil` → run `scripts/kur.ps1 -Adim modeller` (only the aligners:
  `python scripts/modelleri_indir.py --adim hizalama`). The job never falls back to Whisper's own times silently.
- Language without a pinned CTC model → the error says to run once with `DUBLAJ_CEVRIMICI=1`.
- Fewer CTC words than Whisper words → usually Whisper splitting `İstanbul'a` into two tokens; `report.json`
  `text_identical` tells whether the text really changed.

**Related:** [timing-sources.md](../engineering/timing-sources.md) · [word_alignment.md](../engineering/word_alignment.md) · [faster-whisper.md](faster-whisper.md) · [donanim.md](../donanim.md)

## How it works in this pipeline / Neden böyle

- **Principle:** faster-whisper produces segments and text; its segments become the alignment windows; the shared CTC
  box (`ctc_speech_bounded_v2`) measures every word. Whisper's own word times are kept only for diagnostics in
  `faster_whisper_ctc/whisper_dogal_kelimeler.json` of the job folder.
- **Why this choice:** on a 10-file English corpus, CTC-timed engines had word-start error 28–51 ms against 106–126 ms
  for Whisper's native timestamps ([transcription.md](../engineering/transcription.md) §1), and CTC is the project's
  time source ([ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)). The permissive fallback of `auto`
  therefore uses the same text + CTC binding as whisper.cpp and Parakeet ([ADR 0017](../adr/0017-defaults-and-licence-gate.md)).
  WhisperX was the alternative; the shared box was preferred because it applies the speech-bounding policy and
  runs on CPU at ≈ 0.2–0.5 × real time after loading (measured above).
- **How it fits:** 1.0 s leading pad (subtracted after alignment); a missing CTC model stops the job with the install
  step ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)); the checkpoint fingerprint includes the CTC
  boundary policy.
- Details: [timing-sources.md](../engineering/timing-sources.md) §2

## Türkçe

Kayıt satırı: `src/dublaj_hatti/kayit.py` (kurulu olup olmadığını `dubla kontrol` gösterir)

**Ne yapar:** Metin faster-whisper'dan (Whisper large-v3-turbo, CTranslate2); kelime zamanları ortak wav2vec2
CTC hizalama kutusundan. CrisperWhisper Turbo çalışamadığında (NVIDIA GPU yok ya da kurulu değil)
`transkripsiyon.motor = auto` bunu kullanır.

| | |
|---|---|
| Lisans | MIT (faster-whisper ve large-v3-turbo dönüşümü); hizalama ağırlıkları: `tr` CC BY 4.0 (atıf, `NOTICE`), `en` MIT (fairseq) — bkz. [THIRD_PARTY.md](../../THIRD_PARTY.md) |
| Ticari kullanım | evet |
| Kaynak | https://github.com/SYSTRAN/faster-whisper , https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo |
| Kurulum | temel kurulum (`scripts/kur.ps1`, `modeller` adımı: model adımları `stt` + `hizalama`) |
| Donanım | tanıma ve hizalama ayrı süreçlerde art arda çalışır: tanıma GPU int8 ≈ 1.15 GB VRAM, CTC 1.65–2.4 GB VRAM (ölçüldü); CPU çalışır (süreler aşağıda) |
| Diller | çok dilli tanıma; kelime zamanları için dilin bir CTC modeli gerekir: `en`, `tr` sabitlenmiş; diğer diller yalnız bilinçli bir indirmeden sonra (`DUBLAJ_CEVRIMICI=1`) |
| Varsayılan | `transkripsiyon.motor = auto` için yedek |

**Ayarlar**

- `transkripsiyon.motor = "faster_whisper_ctc"` (ya da `auto`)
- `transkripsiyon.model`, `transkripsiyon.hesap_tipi`, `transkripsiyon.kaynak_dil`: [faster-whisper](faster-whisper.md) ile aynı
- Whisper'ın kendi kelime zamanlarını bilerek tutmak için `transkripsiyon.motor = "faster-whisper"` seçin.

**CPU süreleri (ölçüldü, her biri tek kısa çalıştırma, `genel.cihaz = cpu`)**

| Ses | Tanıma (large-v3-turbo int8, model yükleme dahil) | CTC hizalama (bütün adım, ≈ 10 s model yükleme dahil) |
|---|---:|---:|
| 23.8 s İngilizce | ≈ 140 s | 16.5 s (base-960h) |
| 60 s Türkçe | ≈ 161 s | 42.9 s (xls-r-300m) |

**Sık hatalar**

- `CTC hizalama modeli kurulu değil` → `scripts/kur.ps1 -Adim modeller` çalıştırın (yalnız hizalayıcılar:
  `python scripts/modelleri_indir.py --adim hizalama`). İş asla sessizce Whisper'ın kendi zamanlarına düşmez.
- Sabitlenmiş CTC modeli olmayan dil → hata, bir kez `DUBLAJ_CEVRIMICI=1` ile çalıştırmayı söyler.
- CTC kelimeleri Whisper kelimelerinden az → genellikle Whisper'ın `İstanbul'a` kelimesini iki jetona bölmesi;
  `report.json` içindeki `text_identical` metnin gerçekten değişip değişmediğini söyler.

**İlgili:** [timing-sources.md](../engineering/timing-sources.md) · [word_alignment.md](../engineering/word_alignment.md) · [faster-whisper.md](faster-whisper.md) · [donanim.md](../donanim.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** faster-whisper segmentleri ve metni üretir; segmentleri hizalama pencereleri olur; ortak CTC kutusu
  (`ctc_speech_bounded_v2`) her kelimeyi ölçer. Whisper'ın kendi kelime zamanları yalnız tanılama için, iş klasöründeki
  `faster_whisper_ctc/whisper_dogal_kelimeler.json` içinde tutulur.
- **Neden bu seçim:** 10 dosyalık bir İngilizce derlemde CTC zamanlı motorların kelime başlangıç hatası 28–51 ms iken
  Whisper'ın kendi zaman damgalarında 106–126 ms idi ([transcription.md](../engineering/transcription.md) §1) ve CTC
  projenin zaman kaynağıdır ([ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)). Bu yüzden `auto`'nun
  serbest lisanslı yedeği whisper.cpp ve Parakeet ile aynı metin + CTC bağlamasını kullanır ([ADR 0017](../adr/0017-defaults-and-licence-gate.md)).
  Alternatif WhisperX'ti; ortak kutu tercih edildi, çünkü konuşmayla sınırlama (speech-bounding) politikasını uygular ve
  yüklemeden sonra CPU'da ≈ 0.2–0.5 × gerçek zamanda çalışır (yukarıda ölçüldü).
- **Nasıl oturur:** 1.0 s başa dolgu (hizalamadan sonra çıkarılır); eksik CTC modeli işi kurulum adımını söyleyerek
  durdurur ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)); kontrol noktası (checkpoint) parmak izi CTC
  sınır politikasını içerir.
- Ayrıntılar: [timing-sources.md](../engineering/timing-sources.md) §2
