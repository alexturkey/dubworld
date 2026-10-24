# Gemini 2.5 Flash (API) (`gemini_2_5_flash`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Translation through the provider's HTTP API with your own key, using the shared LLM bridge (strict JSON schema, segment-ID checks, no silent fallback).

| | |
|---|---|
| License | provider terms |
| Commercial use | per provider terms |
| Source | https://ai.google.dev |
| Install | your own key in `.env`: `CODEX_BRIDGE_GEMINI_API_KEY` |
| Hardware | no local load |
| Privacy | the transcript is sent to the provider ([THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)) |
| Default | off |

**Settings**

- `ceviri.arka_uc = "gemini_2_5_flash"`
- works with every `ses.akis` flow and every target language the TTS reads

**Common errors**

- `dubla kontrol` and the translation stage read the same variable names (single source: `arka_uc_secimi.API_ANAHTARI_DEGISKENLERI`, the names the bridge reads); a `yok` row means none of them is set in the environment or `.env` ([.env.example](../../.env.example)).
- 503 "high demand" → provider capacity; retried with backoff, then the group is deferred.

**Related:** [translation.md](../engineering/translation.md) · [.env.example](../../.env.example) · [THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** a self-contained backend box (its own config, prompt and model id) on the shared LLM-bridge worker; the worker sends the natural-blocks job over HTTPS with your key and every answer passes the same result gate as the CLI backends (expected IDs, non-empty candidates, coverage check, injection check). Runner: `gemini_generate_content`; `fallback = false`.
- **Why it exists and why it is not first:** it gives a translation path to users without a Codex or Claude Code login. API providers are not first in `auto` because they need keys, billing and provider-specific hardening ([ADR 0008](../adr/0008-translation-backend-order.md)). Gemini-specific hardening came from measured failures: an ID enum in the schema and ID lists in the job (40/40 IDs), no output-token cap (it truncated JSON), a meaning-safety contract against padding short segments with neighbour meaning, and a capacity-only 503 retry with backoff.
- **How it fits:** input is the segmented transcript, output is `translation.json` with one candidate per segment ID ([ADR 0007](../adr/0007-natural-blocks-translation-contract.md)); transient errors retry on the same backend, never on another one ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)). No local GPU or RAM budget.
- Details: [translation.md](../engineering/translation.md) §4, §6

## Türkçe

Kayıt satırı: `src/dublaj_hatti/kayit.py` (kurulu olup olmadığını `dubla kontrol` gösterir)

**Ne yapar:** Sağlayıcının HTTP API'si üzerinden kendi anahtarınızla, ortak LLM köprüsünü kullanarak çeviri (katı JSON şeması, segment kimliği denetimi, sessiz yedeğe geçiş yok).

| | |
|---|---|
| Lisans | sağlayıcı koşulları |
| Ticari kullanım | sağlayıcı koşullarına göre |
| Kaynak | https://ai.google.dev |
| Kurulum | `.env` içinde kendi anahtarınız: `CODEX_BRIDGE_GEMINI_API_KEY` |
| Donanım | yerel yük yok |
| Gizlilik | transkript sağlayıcıya gönderilir ([THIRD_PARTY.md §2 çevrimiçi hizmetler](../../THIRD_PARTY.md)) |
| Varsayılan | kapalı |

**Ayarlar**

- `ceviri.arka_uc = "gemini_2_5_flash"`
- her `ses.akis` akışıyla ve TTS'in okuduğu her hedef dille çalışır

**Sık hatalar**

- `dubla kontrol` ve çeviri aşaması aynı değişken adlarını okur (tek kaynak: `arka_uc_secimi.API_ANAHTARI_DEGISKENLERI`, köprünün okuduğu adlar); `yok` satırı, bunlardan hiçbirinin ortamda ya da `.env` içinde tanımlı olmadığı anlamına gelir ([.env.example](../../.env.example)).
- 503 "high demand" → sağlayıcı kapasitesi; artan beklemeyle (backoff) yeniden denenir, sonra grup ertelenir.

**İlgili:** [translation.md](../engineering/translation.md) · [.env.example](../../.env.example) · [THIRD_PARTY.md §2 çevrimiçi hizmetler](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** ortak LLM köprüsü işçisi (worker) üzerinde kendi içinde bütün bir arka uç kutusu (kendi yapılandırması, istemi ve model kimliği); işçi doğal bloklar (natural blocks) işini anahtarınızla HTTPS üzerinden gönderir ve her yanıt CLI arka uçlarıyla aynı sonuç kapısından geçer (beklenen kimlikler, boş olmayan adaylar, kapsama denetimi, enjeksiyon denetimi). Çalıştırıcı: `gemini_generate_content`; `fallback = false`.
- **Neden var, neden ilk sırada değil:** Codex ya da Claude Code oturumu olmayan kullanıcılara bir çeviri yolu verir. API sağlayıcıları `auto` içinde ilk sırada değildir, çünkü anahtar, faturalandırma ve sağlayıcıya özgü sağlamlaştırma gerektirir ([ADR 0008](../adr/0008-translation-backend-order.md)). Gemini'ye özgü sağlamlaştırma ölçülmüş hatalardan doğdu: şemada kimlik listesi (enum) ve işte kimlik listeleri (40/40 kimlik), çıktı jetonu sınırı yok (JSON'u yarıda kesiyordu), kısa segmentleri komşu segmentin anlamıyla doldurmaya karşı bir anlam güvenliği sözleşmesi ve yalnız kapasite kaynaklı 503 için artan beklemeyle yeniden deneme.
- **Nasıl oturur:** girdi segmentlere ayrılmış transkript, çıktı her segment kimliği için bir aday taşıyan `translation.json` ([ADR 0007](../adr/0007-natural-blocks-translation-contract.md)); geçici hatalar aynı arka uçta yeniden denenir, asla başka bir arka uçta değil ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)). Yerel GPU ya da RAM bütçesi yok.
- Ayrıntılar: [translation.md](../engineering/translation.md) §4, §6
