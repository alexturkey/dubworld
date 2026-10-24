# Claude Code CLI (Anthropic) (`claude_code`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Translation through the user's own Claude Code CLI login, tools disabled, schema in the system prompt. Second choice of `ceviri.arka_uc = auto`.

| | |
|---|---|
| License | provider terms |
| Commercial use | per provider terms |
| Source | https://docs.anthropic.com/en/docs/claude-code |
| Install | `npm i -g @anthropic-ai/claude-code`, then run `claude` once and sign in (the user does this) |
| Hardware | no local load |
| Privacy | the transcript is sent to the provider ([THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)) |
| Default | second step of `auto` |

**Settings**

- `ceviri.arka_uc = "claude_code"`
- `ceviri.claude.model` (default `claude-sonnet-5-5`), `ceviri.claude.caba` (`low` / `medium` / `high`; full texts above 6000 words use `high`)
- `ceviri.claude.cli_yolu` or `CODEX_BRIDGE_CLAUDE_CLI` if `claude` is not on PATH

**Common errors**

- Not authenticated → sign in with `claude`; auth errors are not retried.
- Usage limit → retried after a wait on the same backend; never switched silently.

**Related:** [translation.md](../engineering/translation.md) · [THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** `claude --print` as a subprocess in an empty temporary folder with all tools disallowed, no MCP, no
  session persistence and no setting sources; the schema is appended to the system prompt and the JSON answer passes the
  same result gate as Codex.
- **Why this choice:** the same contract as Codex with a 736-token envelope (the default envelope loaded ≈ 23.8k tokens
  of tool schemas); keeping prompt and schema in the system prompt lets the second call of a run hit the cache.
  A dedicated rule forbids parenthesised glosses because TTS would read them aloud. Second in `auto`
  ([ADR 0008](../adr/0008-translation-backend-order.md)).
- **How it fits:** same input and output as Codex; retries stay on this backend with fixed waits per error type;
  authentication errors are not retried.
- Details: [translation.md](../engineering/translation.md) §2

## Türkçe

Kayıt satırı: `src/dublaj_hatti/kayit.py` (kurulu olup olmadığını `dubla kontrol` gösterir)

**Ne yapar:** Kullanıcının kendi Claude Code CLI oturumuyla, araçlar kapalı ve şema sistem isteminde olacak şekilde çeviri. `ceviri.arka_uc = auto` için ikinci seçenek.

| | |
|---|---|
| Lisans | sağlayıcı koşulları |
| Ticari kullanım | sağlayıcı koşullarına göre |
| Kaynak | https://docs.anthropic.com/en/docs/claude-code |
| Kurulum | `npm i -g @anthropic-ai/claude-code`, ardından bir kez `claude` çalıştırılıp oturum açılır (bunu kullanıcı yapar) |
| Donanım | yerel yük yok |
| Gizlilik | transkript sağlayıcıya gönderilir ([THIRD_PARTY.md §2 çevrimiçi hizmetler](../../THIRD_PARTY.md)) |
| Varsayılan | `auto` içinde ikinci adım |

**Ayarlar**

- `ceviri.arka_uc = "claude_code"`
- `ceviri.claude.model` (varsayılan `claude-sonnet-5-5`), `ceviri.claude.caba` (`low` / `medium` / `high`; 6000 kelimeyi aşan tam metinler `high` kullanır)
- `claude` PATH üzerinde değilse `ceviri.claude.cli_yolu` ya da `CODEX_BRIDGE_CLAUDE_CLI`

**Sık hatalar**

- Kimlik doğrulanmamış → `claude` ile oturum açın; kimlik doğrulama hataları yeniden denenmez.
- Kullanım sınırı → aynı arka uçta bir beklemeden sonra yeniden denenir; asla sessizce başka arka uca geçilmez.

**İlgili:** [translation.md](../engineering/translation.md) · [THIRD_PARTY.md §2 çevrimiçi hizmetler](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** `claude --print`, boş bir geçici klasörde alt süreç olarak çalışır: bütün araçlar yasak, MCP yok, oturum
  kalıcılığı yok, ayar kaynağı yok; şema sistem istemine eklenir ve JSON yanıt Codex ile aynı sonuç kapısından geçer.
- **Neden bu seçim:** Codex ile aynı sözleşme, 736 jetonluk bir zarfla (varsayılan zarf ≈ 23.8k jetonluk araç şeması
  yüklüyordu); istemi ve şemayı sistem isteminde tutmak, bir çalıştırmadaki ikinci çağrının önbelleğe isabet etmesini
  sağlar. Ayrı bir kural parantez içi açıklamaları yasaklar, çünkü TTS onları sesli okurdu. `auto` içinde ikinci
  ([ADR 0008](../adr/0008-translation-backend-order.md)).
- **Nasıl oturur:** Codex ile aynı girdi ve çıktı; yeniden denemeler hata türüne göre sabit beklemelerle bu arka uçta
  kalır; kimlik doğrulama hataları yeniden denenmez.
- Ayrıntılar: [translation.md](../engineering/translation.md) §2
