# Speaker separation (3D-Speaker CAM++) (`konusmaci_ayrimi`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Finds who speaks when (Silero VAD from faster-whisper + CAM++ embeddings + clustering) so each speaker gets their own voice; includes a single-speaker rescue for short interviews.

| | |
|---|---|
| License | Apache-2.0 (3D-Speaker models) / MIT (Silero VAD) |
| Commercial use | yes |
| Source | https://github.com/modelscope/3D-Speaker (CAM++ v1.0.0, pinned); VAD: Silero, already part of the faster-whisper install |
| Install | base install (step `modeller`, `konusmaci` group) |
| Hardware | < 1 GB VRAM (per docs); ran on the CPU in the end-to-end smoke test |
| Default | on in the recommended flow (`ses.konusmaci_cinsiyetine_gore_ses = true`) |

**Settings**

- `ses.konusmaci_cinsiyetine_gore_ses = false` skips it (one voice)
- `ses.konusmaci_sesleri.<SPEAKER> = <voice>` overrides the automatic choice

**Common errors**

- Wrong speaker count on short or overlapping speech → pin voices manually or use `ses.cinsiyet_kipi = segment`.
- Models missing in offline mode → `kur.ps1 -Adim modeller`.

**Related:** [speakers_and_segments.md](../engineering/speakers_and_segments.md) · [cinsiyet_siniflandirici](cinsiyet_siniflandirici.md)

## How it works in this pipeline / Neden böyle

- **Principle:** Silero VAD finds speech regions, CAM++ turns them into 192-dimensional speaker embeddings, spectral
  clustering groups them; if spectral clustering returns one speaker, agglomerative clustering runs on the same
  embeddings (single-speaker rescue). Each word gets the speaker with the largest time overlap.
- **Why this choice:** it fits the 4 GB budget (< 1 GB VRAM) under Apache-2.0 / MIT. The pyannote 4.x community
  pipeline was reported at ≈ 9.5 GB peak, which cannot fit. Why 3D-Speaker was preferred over the earlier pyannote 3.3.2
  setup: **no record**. FSMN VAD was replaced by Silero for licence reasons ([ADR 0013](../adr/0013-silero-vad.md)).
- **How it fits:** runs after transcription as its own subprocess; speaker is metadata on words and segments; speaker
  splits happen inside a main segment, with groups shorter than 0.40 s merged into a neighbour
  ([ADR 0006](../adr/0006-two-stage-dub-segmentation.md)); the result drives the voice per speaker. It does not run when a
  cloud engine already returned word-level speakers.
- Details: [speakers_and_segments.md](../engineering/speakers_and_segments.md) §2

## Türkçe

Kayıt satırı: `src/dublaj_hatti/kayit.py` (kurulu olup olmadığını `dubla kontrol` gösterir)

**Ne yapar:** Her konuşmacı kendi sesini alsın diye kimin ne zaman konuştuğunu bulur (faster-whisper'dan Silero VAD + CAM++ gömmeleri + kümeleme); kısa röportajlar için tek konuşmacı kurtarması içerir.

| | |
|---|---|
| Lisans | Apache-2.0 (3D-Speaker modelleri) / MIT (Silero VAD) |
| Ticari kullanım | evet |
| Kaynak | https://github.com/modelscope/3D-Speaker (CAM++ v1.0.0, sabitlenmiş); VAD: Silero, zaten faster-whisper kurulumunun parçası |
| Kurulum | temel kurulum (`modeller` adımı, `konusmaci` grubu) |
| Donanım | < 1 GB VRAM (belgeye göre); uçtan uca duman testinde (smoke test) CPU'da çalıştı |
| Varsayılan | önerilen akışta açık (`ses.konusmaci_cinsiyetine_gore_ses = true`) |

**Ayarlar**

- `ses.konusmaci_cinsiyetine_gore_ses = false` bunu atlar (tek ses)
- `ses.konusmaci_sesleri.<SPEAKER> = <voice>` otomatik seçimi ezer

**Sık hatalar**

- Kısa ya da üst üste binen konuşmada yanlış konuşmacı sayısı → sesleri elle sabitleyin ya da `ses.cinsiyet_kipi = segment` kullanın.
- Çevrimdışı kipte modeller eksik → `kur.ps1 -Adim modeller`.

**İlgili:** [speakers_and_segments.md](../engineering/speakers_and_segments.md) · [cinsiyet_siniflandirici](cinsiyet_siniflandirici.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** Silero VAD konuşma bölgelerini bulur, CAM++ bunları 192 boyutlu konuşmacı gömmelerine (embedding) çevirir,
  spektral kümeleme bunları gruplar; spektral kümeleme tek konuşmacı döndürürse aynı gömmeler üzerinde aglomeratif
  kümeleme çalışır (tek konuşmacı kurtarması). Her kelime, zaman örtüşmesi en büyük olan konuşmacıyı alır.
- **Neden bu seçim:** Apache-2.0 / MIT lisansıyla 4 GB bütçeye sığar (< 1 GB VRAM). pyannote 4.x topluluk hattının
  tepe kullanımı ≈ 9.5 GB olarak bildirildi; sığamaz. 3D-Speaker'ın önceki pyannote 3.3.2 kurulumuna neden tercih
  edildiği: **kayıt yok**. FSMN VAD, lisans nedeniyle Silero ile değiştirildi ([ADR 0013](../adr/0013-silero-vad.md)).
- **Nasıl oturur:** transkripsiyondan sonra kendi alt süreci olarak çalışır; konuşmacı, kelime ve segmentler üzerinde
  üst veridir; konuşmacı bölünmeleri bir ana segmentin içinde olur, 0.40 s'den kısa gruplar bir komşuya birleştirilir
  ([ADR 0006](../adr/0006-two-stage-dub-segmentation.md)); sonuç konuşmacı başına sesi belirler. Bir bulut motoru kelime
  düzeyinde konuşmacıları zaten döndürdüyse çalışmaz.
- Ayrıntılar: [speakers_and_segments.md](../engineering/speakers_and_segments.md) §2
