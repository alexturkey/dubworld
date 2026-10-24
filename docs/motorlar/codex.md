# Codex CLI (OpenAI) (`codex`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Translation through the user's own Codex CLI login (`codex exec`), with the natural-blocks prompt and a strict JSON output schema. First choice of `ceviri.arka_uc = auto`.

| | |
|---|---|
| License | provider terms |
| Commercial use | per provider terms |
| Source | https://github.com/openai/codex |
| Install | `npm i -g @openai/codex`, then `codex login` (the user signs in; no key in this repo) |
| Hardware | no local load |
| Privacy | the transcript is sent to the provider ([THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)) |
| Default | first step of `auto` |

**Settings**

- `ceviri.arka_uc = "codex"`
- `ceviri.codex.model` (default `gpt-5.6-luna`), `ceviri.codex.akil_yurutme` (`low` / `medium` / `high`)
- `ceviri.codex.cli_yolu` or `CODEX_BRIDGE_CODEX_BIN` if `codex` is not on PATH
- `genel.dublaj_kipi = full_text` is supported (Codex and Claude Code only)

**Common errors**

- `401 Unauthorized` although logged in → an invalid `OPENAI_API_KEY` in your environment.
- `codex.ps1` blocked → use `codex.cmd`.
- Ladder: `codex --version` → `codex login status` → `codex exec --skip-git-repo-check "Reply only with OK."`.
- Usage quota used up → `codex exec` may wait without answering instead of failing. The bridge gives each translation job a fixed budget of 900 s (worker `--timeout 900`, orchestrator 960 s; not a setting); retries stay inside it, and on timeout the whole Codex process tree is closed and the job stops with `codex_timeout`. Check `codex login status` / your plan, or switch to `ceviri.arka_uc = claude_code` / `yerel`.

**Related:** [translation.md](../engineering/translation.md) · [ADR 0008](../adr/0008-translation-backend-order.md) · [THIRD_PARTY.md §2 online services](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** `codex exec` runs as a subprocess in an empty temporary folder with a read-only sandbox, 19 features
  disabled (tools, browser, plugins, hooks and others), the prompt and job JSON on stdin, a strict JSON output schema
  and an explicit reasoning-effort flag.
- **Why this choice:** it carries the most quality and contract evidence, and the CLI enforces the schema. Isolation is
  the main lever: the working folder and enabled tools are part of the model context. Passing the reasoning-effort flag
  that the worker had omitted cut the translation stage from 411.1 s to 17.5 s. First in `auto`
  ([ADR 0008](../adr/0008-translation-backend-order.md)); the default model and effort have no recorded A/B.
- **How it fits:** the orchestrator sends groups of 10 segments with 2 segments of context and up to 7 parallel jobs;
  each segment ID gets one natural candidate ([ADR 0007](../adr/0007-natural-blocks-translation-contract.md)); transient
  errors defer and retry on Codex, never on another backend ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)).
- Details: [translation.md](../engineering/translation.md) §1, §3

## Türkçe

Kayıt satırı: `src/dublaj_hatti/kayit.py` (kurulu olup olmadığını `dubla kontrol` gösterir)

**Ne yapar:** Kullanıcının kendi Codex CLI oturumuyla (`codex exec`), doğal bloklar istemi ve katı bir JSON çıktı şemasıyla çeviri. `ceviri.arka_uc = auto` için ilk seçenek.

| | |
|---|---|
| Lisans | sağlayıcı koşulları |
| Ticari kullanım | sağlayıcı koşullarına göre |
| Kaynak | https://github.com/openai/codex |
| Kurulum | `npm i -g @openai/codex`, ardından `codex login` (girişi kullanıcı yapar; bu repoda anahtar yok) |
| Donanım | yerel yük yok |
| Gizlilik | transkript sağlayıcıya gönderilir ([THIRD_PARTY.md §2 çevrimiçi hizmetler](../../THIRD_PARTY.md)) |
| Varsayılan | `auto` içinde ilk adım |

**Ayarlar**

- `ceviri.arka_uc = "codex"`
- `ceviri.codex.model` (varsayılan `gpt-5.6-luna`), `ceviri.codex.akil_yurutme` (`low` / `medium` / `high`)
- `codex` PATH üzerinde değilse `ceviri.codex.cli_yolu` ya da `CODEX_BRIDGE_CODEX_BIN`
- `genel.dublaj_kipi = full_text` desteklenir (yalnız Codex ve Claude Code)

**Sık hatalar**

- Oturum açık olduğu hâlde `401 Unauthorized` → ortamınızda geçersiz bir `OPENAI_API_KEY` var.
- `codex.ps1` engellendi → `codex.cmd` kullanın.
- Sıralı kontrol: `codex --version` → `codex login status` → `codex exec --skip-git-repo-check "Reply only with OK."`.
- Kullanım kotası bitti → `codex exec` hata vermek yerine cevapsız bekleyebilir. Köprü her çeviri işine 900 sn sabit bütçe verir (işçi `--timeout 900`, orkestratör 960 sn; ayar değildir); yeniden denemeler de bu bütçe içinde kalır, zaman aşımında Codex süreç ağacının tamamı kapatılır ve iş `codex_timeout` ile durur. `codex login status` / planınızı denetleyin ya da `ceviri.arka_uc = claude_code` / `yerel` seçin.

**İlgili:** [translation.md](../engineering/translation.md) · [ADR 0008](../adr/0008-translation-backend-order.md) · [THIRD_PARTY.md §2 çevrimiçi hizmetler](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** `codex exec`, boş bir geçici klasörde alt süreç olarak çalışır: salt okunur korumalı alan (sandbox), 19 özellik
  kapalı (araçlar, tarayıcı, eklentiler, kancalar ve diğerleri), istem ve iş JSON'u stdin üzerinden, katı bir JSON çıktı
  şeması ve açık bir akıl yürütme çabası (reasoning effort) bayrağı.
- **Neden bu seçim:** en çok kalite ve sözleşme kanıtını taşır ve şemayı CLI uygular. Asıl kaldıraç yalıtımdır: çalışma
  klasörü ve açık araçlar model bağlamının parçasıdır. İşçinin atladığı akıl yürütme çabası bayrağını geçirmek çeviri
  aşamasını 411.1 s'den 17.5 s'ye indirdi. `auto` içinde ilk
  ([ADR 0008](../adr/0008-translation-backend-order.md)); varsayılan model ve çaba için kayıtlı A/B karşılaştırması yok.
- **Nasıl oturur:** düzenleyici (orchestrator) 2 segment bağlamla 10 segmentlik gruplar ve en çok 7 paralel iş gönderir;
  her segment kimliği bir doğal aday alır ([ADR 0007](../adr/0007-natural-blocks-translation-contract.md)); geçici
  hatalar ertelenir ve Codex'te yeniden denenir, asla başka bir arka uçta değil ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)).
- Ayrıntılar: [translation.md](../engineering/translation.md) §1, §3
