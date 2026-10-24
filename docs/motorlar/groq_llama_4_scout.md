# Llama 4 Scout (Groq API) (`groq_llama_4_scout`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Translation through the provider's HTTP API with your own key, using the shared LLM bridge (strict JSON schema, segment-ID checks, no silent fallback).

| | |
|---|---|
| License | provider terms |
| Commercial use | per provider terms |
| Source | https://console.groq.com |
| Install | your own key in `.env`: `GROQ_API_KEY_1` (also read: `CODEX_BRIDGE_GROQ_API_KEY`, `GROQ_API_KEY`, `GROQ_API_KEY_2`) |
| Hardware | no local load |
| Privacy | the transcript is sent to the provider ([THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)) |
| Default | off |

**Settings**

- `ceviri.arka_uc = "groq_llama_4_scout"`
- works with every `ses.akis` flow and every target language the TTS reads

**Common errors**

- `dubla kontrol` and the translation stage read the same variable names (single source: `arka_uc_secimi.API_ANAHTARI_DEGISKENLERI`, the names the bridge reads); a `yok` row means none of them is set in the environment or `.env` ([.env.example](../../.env.example)).
- Free tier limits tokens per day; long videos may hit it.

**Related:** [translation.md](../engineering/translation.md) · [.env.example](../../.env.example) · [THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** a self-contained backend box (its own config, prompt and model id) on the shared LLM-bridge worker; the worker sends the natural-blocks job over HTTPS with your key and every answer passes the same result gate as the CLI backends (expected IDs, non-empty candidates, coverage check, injection check). Runner: `openai_compatible_chat_completions`; `fallback = false`.
- **Why it exists and why it is not first:** it gives a translation path to users without a Codex or Claude Code login. API providers are not first in `auto` because they need keys, billing and provider-specific hardening ([ADR 0008](../adr/0008-translation-backend-order.md)). The recorded limit was the free tier's tokens per day, not cost; some models also rejected requests without a User-Agent header or above the per-minute token limit.
- **How it fits:** input is the segmented transcript, output is `translation.json` with one candidate per segment ID ([ADR 0007](../adr/0007-natural-blocks-translation-contract.md)); transient errors retry on the same backend, never on another one ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)). No local GPU or RAM budget.
- Details: [translation.md](../engineering/translation.md) §4, §6

## Türkçe

Kayıt satırı: `src/dublaj_hatti/kayit.py` (kurulu olup olmadığını `dubla kontrol` gösterir)

**Ne yapar:** Sağlayıcının HTTP API'si üzerinden kendi anahtarınızla, ortak LLM köprüsünü kullanarak çeviri (katı JSON şeması, segment kimliği denetimi, sessiz yedeğe geçiş yok). Model: Groq API üzerinden Llama 4 Scout.

| | |
|---|---|
| Lisans | sağlayıcı koşulları |
| Ticari kullanım | sağlayıcı koşullarına göre |
| Kaynak | https://console.groq.com |
| Kurulum | `.env` içinde kendi anahtarınız: `GROQ_API_KEY_1` (ayrıca okunur: `CODEX_BRIDGE_GROQ_API_KEY`, `GROQ_API_KEY`, `GROQ_API_KEY_2`) |
| Donanım | yerel yük yok |
| Gizlilik | transkript sağlayıcıya gönderilir ([THIRD_PARTY.md §2 çevrimiçi hizmetler](../../THIRD_PARTY.md)) |
| Varsayılan | kapalı |

**Ayarlar**

- `ceviri.arka_uc = "groq_llama_4_scout"`
- her `ses.akis` akışıyla ve TTS'in okuduğu her hedef dille çalışır

**Sık hatalar**

- `dubla kontrol` ve çeviri aşaması aynı değişken adlarını okur (tek kaynak: `arka_uc_secimi.API_ANAHTARI_DEGISKENLERI`, köprünün okuduğu adlar); `yok` satırı, bunlardan hiçbirinin ortamda ya da `.env` içinde tanımlı olmadığı anlamına gelir ([.env.example](../../.env.example)).
- Ücretsiz katman günlük jeton (token) sayısını sınırlar; uzun videolar bu sınıra takılabilir.

**İlgili:** [translation.md](../engineering/translation.md) · [.env.example](../../.env.example) · [THIRD_PARTY.md §2 çevrimiçi hizmetler](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** ortak LLM köprüsü işçisi (worker) üzerinde kendi içinde bütün bir arka uç kutusu (kendi yapılandırması, istemi ve model kimliği); işçi doğal bloklar (natural blocks) işini anahtarınızla HTTPS üzerinden gönderir ve her yanıt CLI arka uçlarıyla aynı sonuç kapısından geçer (beklenen kimlikler, boş olmayan adaylar, kapsama denetimi, enjeksiyon denetimi). Çalıştırıcı: `openai_compatible_chat_completions`; `fallback = false`.
- **Neden var, neden ilk sırada değil:** Codex ya da Claude Code oturumu olmayan kullanıcılara bir çeviri yolu verir. API sağlayıcıları `auto` içinde ilk sırada değildir, çünkü anahtar, faturalandırma ve sağlayıcıya özgü sağlamlaştırma gerektirir ([ADR 0008](../adr/0008-translation-backend-order.md)). Kayda geçen sınır maliyet değil, ücretsiz katmanın günlük jeton sınırıydı; bazı modeller User-Agent başlığı olmayan ya da dakikalık jeton sınırını aşan istekleri de reddetti.
- **Nasıl oturur:** girdi segmentlere ayrılmış transkript, çıktı her segment kimliği için bir aday taşıyan `translation.json` ([ADR 0007](../adr/0007-natural-blocks-translation-contract.md)); geçici hatalar aynı arka uçta yeniden denenir, asla başka bir arka uçta değil ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)). Yerel GPU ya da RAM bütçesi yok.
- Ayrıntılar: [translation.md](../engineering/translation.md) §4, §6
