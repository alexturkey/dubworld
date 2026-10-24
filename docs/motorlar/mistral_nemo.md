# Mistral Nemo (Mistral API) (`mistral_nemo`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Translation through the provider's HTTP API with your own key, using the shared LLM bridge (strict JSON schema, segment-ID checks, no silent fallback).

| | |
|---|---|
| License | provider terms |
| Commercial use | per provider terms |
| Source | https://console.mistral.ai |
| Install | your own key in `.env`: `MISTRAL_API_KEY` |
| Hardware | no local load |
| Privacy | the transcript is sent to the provider ([THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)) |
| Default | off |

**Settings**

- `ceviri.arka_uc = "mistral_nemo"`
- works with every `ses.akis` flow and every target language the TTS reads

**Common errors**

- Missing or wrong key → the stage stops with an error naming the backend (no silent fallback); check the variable name against `.env.example`.
- Rate or quota limit → transient errors are retried on the same backend, then the job fails; resume with `dubla devam <N>`.

**Related:** [translation.md](../engineering/translation.md) · [.env.example](../../.env.example) · [THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** a self-contained backend box (its own config, prompt and model id) on the shared LLM-bridge worker; the worker sends the natural-blocks job over HTTPS with your key and every answer passes the same result gate as the CLI backends (expected IDs, non-empty candidates, coverage check, injection check). Runner: `openai_compatible_chat_completions`; `fallback = false`.
- **Why it exists and why it is not first:** it gives a translation path to users without a Codex or Claude Code login. API providers are not first in `auto` because they need keys, billing and provider-specific hardening ([ADR 0008](../adr/0008-translation-backend-order.md)). Selection rationale and quality measurement: no record; rate-limit and retry behaviour is not yet documented against the provider's official limits.
- **How it fits:** input is the segmented transcript, output is `translation.json` with one candidate per segment ID ([ADR 0007](../adr/0007-natural-blocks-translation-contract.md)); transient errors retry on the same backend, never on another one ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)). No local GPU or RAM budget.
- Details: [translation.md](../engineering/translation.md) §4, §6

## Türkçe

Kayıt satırı: `src/dublaj_hatti/kayit.py` (kurulu olup olmadığını `dubla kontrol` gösterir)

**Ne yapar:** Sağlayıcının HTTP API'si üzerinden kendi anahtarınızla, ortak LLM köprüsünü kullanarak çeviri (katı JSON şeması, segment kimliği denetimi, sessiz yedeğe geçiş yok). Model: Mistral API üzerinden Mistral Nemo.

| | |
|---|---|
| Lisans | sağlayıcı koşulları |
| Ticari kullanım | sağlayıcı koşullarına göre |
| Kaynak | https://console.mistral.ai |
| Kurulum | `.env` içinde kendi anahtarınız: `MISTRAL_API_KEY` |
| Donanım | yerel yük yok |
| Gizlilik | transkript sağlayıcıya gönderilir ([THIRD_PARTY.md §2 çevrimiçi hizmetler](../../THIRD_PARTY.md)) |
| Varsayılan | kapalı |

**Ayarlar**

- `ceviri.arka_uc = "mistral_nemo"`
- her `ses.akis` akışıyla ve TTS'in okuduğu her hedef dille çalışır

**Sık hatalar**

- Eksik ya da yanlış anahtar → aşama, arka ucun adını veren bir hatayla durur (sessiz yedeğe geçiş yok); değişken adını `.env.example` ile karşılaştırın.
- Hız ya da kota sınırı → geçici hatalar aynı arka uçta yeniden denenir, sonra iş başarısız olur; `dubla devam <N>` ile sürdürün.

**İlgili:** [translation.md](../engineering/translation.md) · [.env.example](../../.env.example) · [THIRD_PARTY.md §2 çevrimiçi hizmetler](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** ortak LLM köprüsü işçisi (worker) üzerinde kendi içinde bütün bir arka uç kutusu (kendi yapılandırması, istemi ve model kimliği); işçi doğal bloklar (natural blocks) işini anahtarınızla HTTPS üzerinden gönderir ve her yanıt CLI arka uçlarıyla aynı sonuç kapısından geçer (beklenen kimlikler, boş olmayan adaylar, kapsama denetimi, enjeksiyon denetimi). Çalıştırıcı: `openai_compatible_chat_completions`; `fallback = false`.
- **Neden var, neden ilk sırada değil:** Codex ya da Claude Code oturumu olmayan kullanıcılara bir çeviri yolu verir. API sağlayıcıları `auto` içinde ilk sırada değildir, çünkü anahtar, faturalandırma ve sağlayıcıya özgü sağlamlaştırma gerektirir ([ADR 0008](../adr/0008-translation-backend-order.md)). Seçim gerekçesi ve kalite ölçümü: kayıt yok; hız sınırı ve yeniden deneme davranışı henüz sağlayıcının resmi sınırlarına göre belgelenmedi.
- **Nasıl oturur:** girdi segmentlere ayrılmış transkript, çıktı her segment kimliği için bir aday taşıyan `translation.json` ([ADR 0007](../adr/0007-natural-blocks-translation-contract.md)); geçici hatalar aynı arka uçta yeniden denenir, asla başka bir arka uçta değil ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)). Yerel GPU ya da RAM bütçesi yok.
- Ayrıntılar: [translation.md](../engineering/translation.md) §4, §6
