# ElevenLabs Scribe v2 (cloud) (`elevenlabs_scribe_v2`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Cloud speech-to-text with word times and optional speaker labels; raw responses are cached by audio fingerprint so a retry never pays twice.

| | |
|---|---|
| License | provider terms |
| Commercial use | per provider terms |
| Source | https://elevenlabs.io |
| Install | your own key `ELEVENLABS_API_KEY` in `.env` (uses `requests`, already in the base install) |
| Hardware | no local load; 41.9 min audio in 112 s (measured) |
| Privacy | the audio is sent to the provider ([THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)) |
| Default | off |

**Settings**

- `transkripsiyon.motor = "elevenlabs_scribe_v2"`
- `transkripsiyon.kaynak_dil` (sent only when fixed)

**Common errors**

- `ELEVENLABS_API_KEY .env dosyasinda bulunamadi` → fill the key in `.env`.
- Capacity / 5xx → one automatic retry; then the stage fails (no silent fallback).

**Related:** [transcription.md](../engineering/transcription.md) · [dil_tespiti.md](../tarifler/dil_tespiti.md) · [THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** the audio is uploaded to the provider; the response carries word times and optional word-level speaker
  labels. Raw responses are cached by a fingerprint (audio SHA-256, model, language, diarization) so a retry or a
  resumed job does not pay twice.
- **Why this choice:** a cloud option with word-level speakers; when it returns them, local speaker separation does
  not run. The upload timeout scales with file size because a fixed 30 s timeout failed on long files.
- **How it fits:** provider word times are kept (a documented exception to the CTC rule,
  [ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)); one retry on capacity or 5xx only
  ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)); same transcript contract.
- Details: [transcription.md](../engineering/transcription.md) §7 · [speakers_and_segments.md](../engineering/speakers_and_segments.md) §2

## Türkçe

Kayıt satırı: `src/dublaj_hatti/kayit.py` (kurulu olup olmadığını `dubla kontrol` gösterir)

**Ne yapar:** Kelime zamanları ve isteğe bağlı konuşmacı etiketleriyle bulut tabanlı konuşmadan metne (speech-to-text) dönüştürme; ham yanıtlar ses parmak iziyle önbelleğe alınır, böylece yeniden deneme asla iki kez ödenmez.

| | |
|---|---|
| Lisans | sağlayıcı koşulları |
| Ticari kullanım | sağlayıcı koşullarına göre |
| Kaynak | https://elevenlabs.io |
| Kurulum | `.env` içinde kendi anahtarınız `ELEVENLABS_API_KEY` (temel kurulumda zaten bulunan `requests`'i kullanır) |
| Donanım | yerel yük yok; 41.9 dk ses 112 s'de (ölçüldü) |
| Gizlilik | ses sağlayıcıya gönderilir ([THIRD_PARTY.md §2 çevrimiçi hizmetler](../../THIRD_PARTY.md)) |
| Varsayılan | kapalı |

**Ayarlar**

- `transkripsiyon.motor = "elevenlabs_scribe_v2"`
- `transkripsiyon.kaynak_dil` (yalnız sabitlendiğinde gönderilir)

**Sık hatalar**

- `ELEVENLABS_API_KEY .env dosyasinda bulunamadi` → anahtarı `.env` içine yazın.
- Kapasite / 5xx → bir otomatik yeniden deneme; sonra aşama başarısız olur (sessiz yedeğe geçiş yok).

**İlgili:** [transcription.md](../engineering/transcription.md) · [dil_tespiti.md](../tarifler/dil_tespiti.md) · [THIRD_PARTY.md §2 çevrimiçi hizmetler](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** ses sağlayıcıya yüklenir; yanıt kelime zamanlarını ve isteğe bağlı kelime düzeyinde konuşmacı etiketlerini
  taşır. Ham yanıtlar bir parmak iziyle (ses SHA-256, model, dil, konuşmacı ayrımı/diarization) önbelleğe alınır; böylece
  yeniden deneme ya da sürdürülen iş iki kez ödemez.
- **Neden bu seçim:** kelime düzeyinde konuşmacı veren bir bulut seçeneği; bunları döndürdüğünde yerel konuşmacı ayrımı
  çalışmaz. Sabit 30 s zaman aşımı uzun dosyalarda başarısız olduğu için yükleme zaman aşımı dosya boyutuyla ölçeklenir.
- **Nasıl oturur:** sağlayıcının kelime zamanları korunur (CTC kuralının belgelenmiş bir istisnası,
  [ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)); yalnız kapasite ya da 5xx durumunda bir yeniden deneme
  ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)); aynı transkript sözleşmesi.
- Ayrıntılar: [transcription.md](../engineering/transcription.md) §7 · [speakers_and_segments.md](../engineering/speakers_and_segments.md) §2
