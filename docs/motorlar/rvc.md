# RVC voice conversion (your own model) (`rvc`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Converts the synthesised dub audio (Supertonic, VoxCPM2 or XTTS output) into the voice of **your own
RVC model**. It is not TTS; it is applied to the mix audio as a final step. Silent ranges of the source audio are
silenced again (prevents RVC from producing hum/breath), and length and sample rate are kept.

| | |
|---|---|
| License | code: RVC WebUI MIT (official repository); model: yours. This repository contains no model, index or RVC code |
| Install | manual: the official RVC WebUI (github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI, `infer/cli.py` arguments read from commit 81eed5e8) into its own virtual environment |
| Hardware | GPU recommended (~2 GB VRAM, estimate); slow on the CPU |
| Default | off |

**Consent (mandatory):** An RVC model imitates a real person's voice. Use only a model trained on your own voice or
with the explicit written permission of the voice's owner; imitating a celebrity or a real person without permission
is forbidden (ETHICS.md). Without `rvc_riza_onayi = true`, conversion fails with an error.

**Install**
1. Clone the official repository and set up its virtual environment and the `assets/` (hubert, rmvpe) files as in its
   own README.
2. `.env`: `DUBLAJ_RVC_KOK=<clone folder>`; if python is not under `<root>/.venv` or `<root>/venv`,
   `DUBLAJ_RVC_PYTHON=<path to that environment's python.exe>`.
3. `dubla kontrol` → the `rvc` row shows as installed.

**Settings** (`varsayilan.toml` `[ses]`, also given with `--ayar`; DubConfig equivalent in parentheses): `ses.rvc_model`
(`rvc_model_yolu`; .pth, empty means RVC is off), `ses.rvc_index` (`rvc_index_yolu`; optional .index), `ses.rvc_perde`
(`rvc_perde`; semitones, -24..24, female→male ~ -12), `ses.rvc_riza_onayi` (`rvc_riza_onayi`; mandatory when a model is set).
Example: `dubla video.mp4 --ayar ses.rvc_model=<model.pth> --ayar ses.rvc_riza_onayi=true`. Constants: f0 rmvpe, index rate 0.75, rms 0.25, protect 0.33. Report: `rvc/rvc_rapor.json`
(file name, duration, number of preserved silent ranges; no full path is written).

**Common errors**
- `RVC kurulu değil` → `DUBLAJ_RVC_KOK` is missing or `infer/cli.py` / python was not found.
- `RVC rıza onayı yok` → see the consent section above.
- `RVC dönüştürme başarısız` → read the RVC error at the end of the message (usually a missing `assets/rmvpe`).

## How it works in this pipeline / Neden böyle

- **Principle:** RVC does not read text; it converts an existing recording into the model's voice character. The
  pipeline converts the timed dub track returned by the TTS stage once, with the official RVC WebUI command line.
- **Why after TTS:** translation, synthesis, placement and timing stay independent of RVC; the converted file is the
  same track that goes into the video. The speech/pause decision is taken from the clean audio entering RVC, not from
  the RVC output, because RVC can produce speech-like noise in pauses; these ranges are silenced again, with a 40 ms
  fade at the edges ([ADR 0016](../adr/0016-rvc-as-post-tts-conversion.md)).
- **Why a separate environment:** RVC's dependencies (its own torch build, fairseq, faiss, HuBERT, RMVPE) conflict
  with the main environment; so it is not imported and runs as a subprocess in the user's RVC environment.
- **How it fits:** the RVC settings are part of the TTS checkpoint fingerprint; when they change, only the TTS stage
  runs again. The consent declaration is mandatory; a failed conversion is an error
  ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)). There is no recorded A/B for the fixed parameters.
- Place in the end-to-end flow: [pipeline-flow.md, stage table](../engineering/pipeline-flow.md#3-stage-table-segment-sync-the-default)

## Türkçe

**RVC ses dönüştürme (`rvc`)**

**Ne yapar:** Seslendirilmiş dublaj sesini (Supertonic, VoxCPM2 ya da XTTS çıktısı) **sizin kendi RVC modelinizin**
sesine çevirir. TTS değildir; karışım sesine son işlem olarak uygulanır. Kaynak sesteki sessiz aralıklar yeniden
susturulur (RVC'nin uğultu/nefes üretmesini önler), uzunluk ve örnekleme hızı korunur.

| | |
|---|---|
| Lisans | kod: RVC WebUI MIT (resmî depo); model: sizin. Bu repoda model, index ya da RVC kodu yoktur |
| Kurulum | elle: resmî RVC WebUI (github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI, `infer/cli.py` argümanları commit 81eed5e8'den okundu) kendi sanal ortamına |
| Donanım | GPU önerilir (~2 GB VRAM, tahmini); işlemcide yavaş |
| Varsayılan | kapalı |

**Rıza (zorunlu):** RVC modeli gerçek bir insanın sesini taklit eder. Yalnız kendi sesinizden ya da sesin
sahibinin açık yazılı izniyle eğitilmiş modeli kullanın; ünlü ya da gerçek kişiyi izinsiz taklit etmek yasaktır
(ETHICS.md). `rvc_riza_onayi = true` olmadan dönüştürme hata verir.

**Kurulum**
1. Resmî depoyu klonlayın, kendi README'sindeki gibi sanal ortamını ve `assets/` (hubert, rmvpe) dosyalarını kurun.
2. `.env`: `DUBLAJ_RVC_KOK=<klon klasörü>`; python `<kök>/.venv` ya da `<kök>/venv` altında değilse
   `DUBLAJ_RVC_PYTHON=<o ortamın python.exe yolu>`.
3. `dubla kontrol` → `rvc` satırı kurulu görünür.

**Ayarlar** (`varsayilan.toml` `[ses]`, `--ayar` ile de verilir; DubConfig karşılığı parantezde): `ses.rvc_model`
(`rvc_model_yolu`; .pth, boşsa RVC kapalı), `ses.rvc_index` (`rvc_index_yolu`; isteğe bağlı .index), `ses.rvc_perde`
(`rvc_perde`; yarım ton, -24..24, kadın→erkek ~ -12), `ses.rvc_riza_onayi` (`rvc_riza_onayi`; model doluyken zorunlu).
Örnek: `dubla video.mp4 --ayar ses.rvc_model=<model.pth> --ayar ses.rvc_riza_onayi=true`. Sabitler: f0 rmvpe, index oranı 0,75, rms 0,25, koruma 0,33. Rapor: `rvc/rvc_rapor.json`
(dosya adı, süre, korunan sessiz aralık sayısı; tam yol yazılmaz).

**Sık hata**
- `RVC kurulu değil` → `DUBLAJ_RVC_KOK` yok ya da `infer/cli.py` / python bulunamadı.
- `RVC rıza onayı yok` → yukarıdaki rıza bölümü.
- `RVC dönüştürme başarısız` → mesajın sonundaki RVC hatasına bakın (çoğunlukla eksik `assets/rmvpe`).

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** RVC metin okumaz; var olan kaydı modelin ses karakterine çevirir. Hat, TTS aşamasının döndürdüğü zamanlanmış
  dublaj izini resmî RVC WebUI komut satırıyla bir kez dönüştürür.
- **Neden TTS sonrası:** çeviri, seslendirme, yerleştirme ve zamanlama RVC'den bağımsız kalır; dönüştürülen dosya
  videoya giren iz ile aynıdır. Konuşma/duraklama kararı RVC çıktısından değil RVC'ye giren temiz sesten alınır, çünkü
  RVC duraklamalarda konuşmaya benzeyen cızırtı üretebilir; bu aralıklar yeniden susturulur, kenarlarda 40 ms yumuşatma
  uygulanır ([ADR 0016](../adr/0016-rvc-as-post-tts-conversion.md)).
- **Neden ayrı ortam:** RVC'nin bağımlılıkları (kendi torch yapısı, fairseq, faiss, HuBERT, RMVPE) ana ortamla çakışır;
  bu yüzden içe aktarılmaz, kullanıcının RVC ortamında alt süreç olarak çalışır.
- **Diğer parçalarla ahengi:** RVC ayarları TTS ara kaydının parmak izindedir; değişince yalnız TTS aşaması yeniden
  çalışır. Rıza beyanı zorunludur; başarısız dönüştürme hatadır ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)).
  Sabit parametreler için kayıtlı A/B yoktur.
- Uçtan uca akıştaki yeri: [hat_akisi.md, aşama tablosu](../muhendislik/hat_akisi.md#3-aşama-tablosu-segment-eşleme-varsayılan)
