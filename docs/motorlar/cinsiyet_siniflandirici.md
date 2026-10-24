# Voice gender classifier (wav2vec2 XLSR-53) (`cinsiyet_siniflandirici`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Predicts female / male per speaker (or per sentence in segment mode) to pick a matching Supertonic voice.

| | |
|---|---|
| License | Apache-2.0 (model); training data LibriSpeech CC BY 4.0 |
| Commercial use | yes |
| Source | https://huggingface.co/alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech (pinned revision) |
| Install | base install (step `modeller`) |
| Hardware | 1.26 GB weights; < 1 GB VRAM (per docs); works on CPU |
| Default | on with speaker separation |

**Settings**

- used by `ses.konusmaci_cinsiyetine_gore_ses` and `ses.cinsiyet_kipi = segment`

**Common errors**

- No "unknown" class and no confidence threshold: a wrong guess is possible; pin the voice with `ses.konusmaci_sesleri`.
- Accuracy on Turkish speech: no measurement yet.

**Related:** [speakers_and_segments.md](../engineering/speakers_and_segments.md) · [segment_cinsiyet_kipi](segment_cinsiyet_kipi.md)

## How it works in this pipeline / Neden böyle

- **Principle:** a wav2vec2 XLSR-53 encoder fine-tuned as a two-class (female/male) audio classifier. One worker
  subprocess per job receives all eligible clips over stdin JSON (minimum 0.30 s; up to 30 s per speaker in speaker
  mode) and exits after one JSON answer.
- **Why this choice:** the earlier classifier was dropped because the permission status of its training data was
  unclear; this model is Apache-2.0 with LibriSpeech (CC BY 4.0) training data, pinned and loaded offline
  ([ADR 0017](../adr/0017-defaults-and-licence-gate.md)). It has no "unknown" class and no confidence threshold; accuracy on
  Turkish speech: no record.
- **How it fits:** after speaker separation; the predicted gender picks a Supertonic voice for each speaker (or each
  sentence in segment mode); an explicit `ses.konusmaci_sesleri` map overrides it. Process exit releases RAM and VRAM
  ([ADR 0001](../adr/0001-one-gpu-job-and-process-per-model.md)).
- Details: [speakers_and_segments.md](../engineering/speakers_and_segments.md) §3
- Place in the end-to-end flow: [pipeline-flow.md, stage table](../engineering/pipeline-flow.md#3-stage-table-segment-sync-the-default)

## Türkçe

Kayıt satırı: `src/dublaj_hatti/kayit.py` (kurulu olup olmadığını `dubla kontrol` gösterir)

**Ne yapar:** Uygun bir Supertonic sesi seçmek için konuşmacı başına (segment kipinde cümle başına) kadın / erkek tahmini yapar.

| | |
|---|---|
| Lisans | Apache-2.0 (model); eğitim verisi LibriSpeech CC BY 4.0 |
| Ticari kullanım | evet |
| Kaynak | https://huggingface.co/alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech (sabitlenmiş sürüm) |
| Kurulum | temel kurulum (`modeller` adımı) |
| Donanım | 1.26 GB ağırlık; < 1 GB VRAM (belgeye göre); CPU'da çalışır |
| Varsayılan | konuşmacı ayrımıyla birlikte açık |

**Ayarlar**

- `ses.konusmaci_cinsiyetine_gore_ses` ve `ses.cinsiyet_kipi = segment` tarafından kullanılır

**Sık hatalar**

- "Bilinmeyen" sınıfı ve güven eşiği yok: yanlış tahmin olabilir; sesi `ses.konusmaci_sesleri` ile elle sabitleyin.
- Türkçe konuşmada doğruluk: henüz ölçüm yok.

**İlgili:** [speakers_and_segments.md](../engineering/speakers_and_segments.md) · [segment_cinsiyet_kipi](segment_cinsiyet_kipi.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** iki sınıflı (kadın/erkek) ses sınıflandırıcısı olarak ince ayarlanmış (fine-tuned) bir wav2vec2 XLSR-53
  kodlayıcısı. İş başına bir işçi alt süreci uygun bütün klipleri stdin JSON üzerinden alır (en az 0.30 s; konuşmacı
  kipinde konuşmacı başına en çok 30 s) ve tek bir JSON yanıttan sonra kapanır.
- **Neden bu seçim:** önceki sınıflandırıcı, eğitim verisinin izin durumu belirsiz olduğu için bırakıldı; bu model
  Apache-2.0 lisanslı, eğitim verisi LibriSpeech (CC BY 4.0), sabitlenmiş ve çevrimdışı yüklenir
  ([ADR 0017](../adr/0017-defaults-and-licence-gate.md)). "Bilinmeyen" sınıfı ve güven eşiği yoktur; Türkçe konuşmada
  doğruluk: kayıt yok.
- **Nasıl oturur:** konuşmacı ayrımından sonra çalışır; tahmin edilen cinsiyet her konuşmacı (segment kipinde her
  cümle) için bir Supertonic sesi seçer; açıkça verilen bir `ses.konusmaci_sesleri` eşlemesi tahmini ezer. Sürecin
  kapanması RAM ve VRAM'i serbest bırakır ([ADR 0001](../adr/0001-one-gpu-job-and-process-per-model.md)).
- Ayrıntılar: [speakers_and_segments.md](../engineering/speakers_and_segments.md) §3
- Uçtan uca akıştaki yeri: [hat_akisi.md, aşama tablosu](../muhendislik/hat_akisi.md#3-aşama-tablosu-segment-eşleme-varsayılan)
