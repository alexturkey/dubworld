# faster-whisper (`faster-whisper`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Speech-to-text with Whisper large-v3-turbo on CTranslate2; word times are Whisper's own (cross-attention) timestamps, **no CTC**. Chosen only explicitly: the recommended flow (`auto`) uses [faster_whisper_ctc](faster_whisper_ctc.md) instead (same recogniser, CTC word times).

| | |
|---|---|
| License | MIT (code and the CTranslate2 conversion of large-v3-turbo) |
| Commercial use | yes |
| Source | https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo , https://github.com/SYSTRAN/faster-whisper |
| Install | base install (`scripts/kur.ps1`, step `modeller`) |
| Hardware | GPU int8 ~1.15 GB / float32 ~3.45 GB VRAM (measured); CPU int8 works (speed not measured) |
| Languages | multilingual; `distil-*` models are English only |
| Default | off (explicit choice); `auto` falls back to `faster_whisper_ctc` |

**Settings**

- `transkripsiyon.motor = "faster-whisper"`
- `transkripsiyon.model`: `large-v3-turbo` (installed), `large-v3`, `medium`, `small`, `distil-large-v3`, `distil-large-v3.5` (other models download only with `DUBLAJ_CEVRIMICI=1`)
- `transkripsiyon.hesap_tipi = auto` (older GPUs: int8 / float32; float16 is refused there)
- `transkripsiyon.kaynak_dil`, `transkripsiyon.vad`

**Common errors**

- `float16` refused → `hesap_tipi=auto` or `int8`.
- Different text on two runs → expected small timestamp jitter; text is made deterministic by the worker.
- `distil-*` with a non-English video → the pipeline switches to the multilingual model (warning).

**Related:** [transcription.md](../engineering/transcription.md) · [dil_tespiti.md](../tarifler/dil_tespiti.md) · [donanim.md](../donanim.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** Whisper (encoder-decoder) converted to CTranslate2 and decoded with int8 or float32 kernels. The text is
  decoded with `temperature=0` and `condition_on_previous_text=False`. With this engine name the word times are
  Whisper's native timestamps (`word_timestamps=True`); the same recogniser with CTC word times is
  [faster_whisper_ctc](faster_whisper_ctc.md).
- **Why this choice:** permissive weights (MIT) and a multilingual model; int8 needs ≈ 1.15 GB VRAM and fits the 4 GB
  budget. Native timestamps were ≈ 4× worse at word starts than CTC on the test corpus
  ([ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)), so the permissive fallback of `auto` is
  `faster_whisper_ctc`, not this engine ([ADR 0017](../adr/0017-defaults-and-licence-gate.md)). This name stays for users
  who want the faster path without the alignment step, or a language without a CTC model.
  Deterministic-algorithm settings were added because the same audio produced different text on repeated runs.
- **How it fits:** input is 16 kHz mono audio with a 1.0 s leading pad (subtracted once); output is `transcript.json`,
  which the single segmenter turns into dub segments ([ADR 0006](../adr/0006-two-stage-dub-segmentation.md)). Recognition
  and alignment never share the GPU ([ADR 0001](../adr/0001-one-gpu-job-and-process-per-model.md)).
- Details: [transcription.md](../engineering/transcription.md) §2, §9 · [word_alignment.md](../engineering/word_alignment.md)
- Place in the end-to-end flow: [pipeline-flow.md, segmentation per engine](../engineering/pipeline-flow.md#7-segmentation-per-transcription-engine)

## Türkçe

Kayıt satırı: `src/dublaj_hatti/kayit.py` (kurulu olup olmadığını `dubla kontrol` gösterir)

**Ne yapar:** CTranslate2 üzerinde Whisper large-v3-turbo ile konuşmadan metne dönüştürme; kelime zamanları Whisper'ın kendi (çapraz dikkat, cross-attention) zaman damgalarıdır, **CTC yok**. Yalnız açıkça seçilir: önerilen akış (`auto`), CrisperWhisper yoksa bunun yerine [faster_whisper_ctc](faster_whisper_ctc.md) kullanır (aynı tanıyıcı, CTC kelime zamanları).

| | |
|---|---|
| Lisans | MIT (kod ve large-v3-turbo'nun CTranslate2 dönüşümü) |
| Ticari kullanım | evet |
| Kaynak | https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo , https://github.com/SYSTRAN/faster-whisper |
| Kurulum | temel kurulum (`scripts/kur.ps1`, `modeller` adımı) |
| Donanım | GPU int8 ~1.15 GB / float32 ~3.45 GB VRAM (ölçüldü); CPU int8 çalışır (hız ölçülmedi) |
| Diller | çok dilli; `distil-*` modelleri yalnız İngilizce |
| Varsayılan | kapalı (açık seçim); `auto` `faster_whisper_ctc`'ye düşer |

**Ayarlar**

- `transkripsiyon.motor = "faster-whisper"`
- `transkripsiyon.model`: `large-v3-turbo` (kurulu), `large-v3`, `medium`, `small`, `distil-large-v3`, `distil-large-v3.5` (diğer modeller yalnız `DUBLAJ_CEVRIMICI=1` ile indirilir)
- `transkripsiyon.hesap_tipi = auto` (eski GPU'lar: int8 / float32; float16 orada reddedilir)
- `transkripsiyon.kaynak_dil`, `transkripsiyon.vad`

**Sık hatalar**

- `float16` reddedildi → `hesap_tipi=auto` ya da `int8`.
- İki çalıştırmada farklı metin → zaman damgasında beklenen küçük oynama; metni işçi belirlenimci (deterministic) yapar.
- İngilizce olmayan videoda `distil-*` → hat çok dilli modele geçer (uyarı).

**İlgili:** [transcription.md](../engineering/transcription.md) · [dil_tespiti.md](../tarifler/dil_tespiti.md) · [donanim.md](../donanim.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** CTranslate2'ye dönüştürülmüş ve int8 ya da float32 çekirdekleriyle çözülen Whisper (kodlayıcı-çözücü,
  encoder-decoder). Metin `temperature=0` ve `condition_on_previous_text=False` ile çözülür. Bu motor adıyla kelime
  zamanları Whisper'ın kendi zaman damgalarıdır (`word_timestamps=True`); aynı tanıyıcının CTC kelime zamanlı hâli
  [faster_whisper_ctc](faster_whisper_ctc.md).
- **Neden bu seçim:** serbest lisanslı (MIT) ağırlıklar ve çok dilli model; int8 ≈ 1.15 GB VRAM ister ve 4 GB bütçeye
  sığar. Test derleminde kendi zaman damgaları kelime başlangıçlarında CTC'den ≈ 4× daha kötüydü
  ([ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)); bu yüzden `auto`'nun serbest lisanslı yedeği bu motor
  değil, `faster_whisper_ctc` ([ADR 0017](../adr/0017-defaults-and-licence-gate.md)). Bu ad, hizalama adımı olmadan daha
  hızlı yolu isteyen ya da CTC modeli olmayan bir dili kullanan kullanıcılar için kalır.
  Aynı ses tekrarlanan çalıştırmalarda farklı metin ürettiği için belirlenimci algoritma ayarları eklendi.
- **Nasıl oturur:** girdi 1.0 s başa dolgulu (bir kez çıkarılır) 16 kHz mono ses; çıktı `transcript.json`, tek
  segmentleyici bunu dublaj segmentlerine çevirir ([ADR 0006](../adr/0006-two-stage-dub-segmentation.md)). Tanıma ve
  hizalama GPU'yu asla paylaşmaz ([ADR 0001](../adr/0001-one-gpu-job-and-process-per-model.md)).
- Ayrıntılar: [transcription.md](../engineering/transcription.md) §2, §9 · [word_alignment.md](../engineering/word_alignment.md)
- Uçtan uca akıştaki yeri: [hat_akisi.md, motora göre segmentleme](../muhendislik/hat_akisi.md#7-transkripsiyon-motoruna-göre-segmentleme)
