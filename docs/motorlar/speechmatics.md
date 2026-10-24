# Speechmatics (cloud) (`speechmatics`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Cloud speech-to-text with word times and the provider's own speaker labels.

| | |
|---|---|
| License | provider terms (read them before use) |
| Commercial use | per provider terms |
| Source | https://www.speechmatics.com |
| Install | `scripts/kur.ps1 -Adim speechmatics` + your own key `SPEECHMATICS_API_KEY_1` in `.env` |
| Hardware | no local load (cloud) |
| Privacy | the audio is sent to the provider ([THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)) |
| Default | off |

**Settings**

- `transkripsiyon.motor = "speechmatics"`
- `transkripsiyon.kaynak_dil`: ISO code or `auto`
- `ileri.pyannote_konusmaci_ayrimi = true` uses the provider's speaker labels

**Common errors**

- `SPEECHMATICS_API_KEY_1 .env dosyasinda bulunamadi` → copy [.env.example](../../.env.example) to `.env` and fill your key.
- Language detected from the first word: on short clips set `kaynak_dil` explicitly.

**Related:** [transcription.md](../engineering/transcription.md) · [dil_tespiti.md](../tarifler/dil_tespiti.md) · [THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** the audio is uploaded to the provider; the response carries words with times, punctuation as separate
  items (attached to the previous word) and provider speaker labels.
- **Why this choice:** it was added when a local diarizer under-counted speakers; the provider labels can be used
  instead of local speaker separation. Language is detected from the first word, which is risky on short clips.
- **How it fits:** word times come from the provider (a documented exception to the CTC rule,
  [ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)); 1.0 s leading pad; no local GPU use; same transcript
  contract. Data leaves the machine only when this engine is selected.
- Details: [transcription.md](../engineering/transcription.md) §7, §9
- Place in the end-to-end flow: [pipeline-flow.md, segmentation per engine](../engineering/pipeline-flow.md#7-segmentation-per-transcription-engine)

## Türkçe

**Ne yapar:** Kelime zamanları ve hizmet sağlayıcının kendi konuşmacı etiketleriyle bulutta konuşmayı metne çevirir.

| | |
|---|---|
| Lisans | sağlayıcı şartları (kullanmadan önce okuyun) |
| Ticari kullanım | sağlayıcı şartlarına göre |
| Kaynak | https://www.speechmatics.com |
| Kurulum | `scripts/kur.ps1 -Adim speechmatics` + `.env` içinde kendi anahtarınız `SPEECHMATICS_API_KEY_1` |
| Donanım | yerel yük yok (bulut) |
| Gizlilik | ses sağlayıcıya gönderilir ([THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)) |
| Varsayılan | kapalı |

**Ayarlar**

- `transkripsiyon.motor = "speechmatics"`
- `transkripsiyon.kaynak_dil`: ISO kodu ya da `auto`
- `ileri.pyannote_konusmaci_ayrimi = true` sağlayıcının konuşmacı etiketlerini kullanır

**Sık hatalar**

- `SPEECHMATICS_API_KEY_1 .env dosyasinda bulunamadi` → [.env.example](../../.env.example) dosyasını `.env` olarak kopyalayın ve anahtarınızı yazın.
- Dil ilk kelimeden tespit edilir: kısa kliplerde `kaynak_dil`'i açıkça verin.

**İlgili:** [transcription.md](../engineering/transcription.md) · [dil_tespiti.md](../tarifler/dil_tespiti.md) · [THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** ses sağlayıcıya yüklenir; cevap zamanlı kelimeleri, ayrı öğeler olarak noktalamayı (önceki kelimeye
  eklenir) ve sağlayıcının konuşmacı etiketlerini taşır.
- **Neden bu seçim:** yerel bir konuşmacı ayrıştırıcının konuşmacıları eksik saydığı durumda eklendi; yerel konuşmacı
  ayrımı yerine sağlayıcının etiketleri kullanılabilir. Dil ilk kelimeden tespit edilir; bu kısa kliplerde risklidir.
- **Diğer parçalarla ahengi:** kelime zamanları sağlayıcıdan gelir (CTC kuralının belgelenmiş bir istisnası,
  [ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)); baştaki 1.0 sn pay; yerel GPU kullanımı yok; aynı
  transkript sözleşmesi. Veri makineden yalnız bu motor seçildiğinde çıkar.
- Ayrıntı: [transcription.md](../engineering/transcription.md) §7, §9
- Uçtan uca akıştaki yeri: [hat_akisi.md, motora göre segmentleme](../muhendislik/hat_akisi.md#7-transkripsiyon-motoruna-göre-segmentleme)
