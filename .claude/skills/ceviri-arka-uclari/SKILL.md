---
name: ceviri-arka-uclari
description: "Connect and choose the translation backend: Codex CLI or Claude Code CLI with the user's own login, offline Opus-MT (English to Turkish), or a cloud API with the user's own key (Gemini, Groq, Cerebras, Mistral). Use when the user says 'translation', 'çeviri', 'connect Codex', 'connect Claude', 'use my API key', 'offline translation', 'translate to German', 'çeviri arka ucu', or the translation stage fails with a login / key error."
---

# Translation backends / Çeviri arka uçları

Türkçe özet en altta. / Turkish summary at the end.

## When to use

Selecting `ceviri.arka_uc`, connecting an account, translating to a target other than Turkish, or fixing a failing
translation stage.

## Backends

| `ceviri.arka_uc` | Needs | Data leaves the machine | Notes |
|---|---|---|---|
| `auto` (default) | — | depends | Codex CLI if found → Claude Code CLI → local `yerel` |
| `codex` | Codex CLI + `codex login` (your account) | yes | default model `gpt-5.6-luna`, reasoning `medium` (`ceviri.codex.*`) |
| `claude_code` | Claude Code CLI + saved login | yes | default model `claude-sonnet-5-5`, effort `medium` (`ceviri.claude.*`); long full texts use `high` |
| `yerel` | nothing (installed model) | no | Opus-MT tc-big, **English → Turkish only**, no timing awareness |
| `gemini_2_5_flash`, `gemini_3_1_flash_lite_tier_1`, `gemma_4_26b` | `CODEX_BRIDGE_GEMINI_API_KEY` | yes | one key for all three |
| `groq_llama_4_scout` | `GROQ_API_KEY_1` (also read: `CODEX_BRIDGE_GROQ_API_KEY`, `GROQ_API_KEY`, `GROQ_API_KEY_2`) | yes | free tier limits tokens per day |
| `cerebras_llama_3_1_8b` | `CEREBRAS_API_KEY` | yes | |
| `mistral_nemo` | `MISTRAL_API_KEY` | yes | |

Variable names are the ones read by `src/dublaj_hatti/bolum_40_ceviri/arka_uc_secimi.py` and listed in `.env.example`.
Keys go only into the user's `.env` (git-ignored); never print, commit or paste them anywhere.
No silent fallback: a failing backend stops the stage with an error; it is not replaced by another backend
([ADR 0009](../../../docs/adr/0009-fail-closed-no-silent-fallback.md)).

## Steps

1. **Ask where the text may go.** LLM and API backends send the transcript to the provider (THIRD_PARTY.md §2). Offline only →
   `yerel` (English source, Turkish target).
2. **Codex CLI:**
   ```powershell
   npm i -g @openai/codex
   codex login                       # the user's own account, interactive; the agent does not log in for them
   codex login status
   dubla video.mp4 --ayar ceviri.arka_uc=codex
   ```
   If `codex` is not on PATH: `ceviri.codex.cli_yolu` or `CODEX_BRIDGE_CODEX_BIN` in `.env`.
3. **Claude Code CLI:**
   ```powershell
   npm i -g @anthropic-ai/claude-code
   claude                            # open once and sign in with the user's account
   dubla video.mp4 --ayar ceviri.arka_uc=claude_code
   ```
   Not on PATH: `ceviri.claude.cli_yolu` or `CODEX_BRIDGE_CLAUDE_CLI`.
4. **API key backend:** copy `.env.example` to `.env`, fill only the needed variable, then e.g.
   `dubla video.mp4 --ayar ceviri.arka_uc=mistral_nemo`.
5. **Other target languages:** `--ayar genel.hedef_dil=fr` with any backend except `yerel`; the TTS must read that
   language (`tts-motorlari`). Status per language and the appendix guide: see "Target languages" below.
6. **Translation only (one stage):** `dubla cevir transcript.json --hedef-dil tr --arka-uc codex -o translation.json`.
7. **Better timing fit:** `ses.akis=natural_blocks_1` (default) or `repair_*` flows; they work only with LLM backends.

## Target languages (LLM backends)

Prompts are templates rendered per target by `bolum_40_ceviri/llm_kopru/scripts/hedef_dil.py`
([ADR 0014](../../../docs/adr/0014-language-independent-translation-prompts.md)).

- `tr`: production-proven; rendered prompts are byte-identical to the original Turkish prompts (golden hashes in
  `tests/veri/ceviri_istem_tr_altin.json`).
- en, de, fr, es, it, pt, ru, ar, ja, zh: general appendix `dil_ekleri/_genel.md` + own `dil_ekleri/<code>.md`.
  Any other code: general appendix only. None of these has been tried with a real LLM yet.
- Speech rate: `KONUSMA_HIZI` in `hedef_dil.py` (`tr` 0.43 s/word measured; others estimated; ja/zh/ko/th per character).
- Output language is checked after validation; a mismatch raises retryable `translation_result_wrong_language`.

**Adding a language appendix:** create `dil_ekleri/<code>.md` (preamble before the first `## ` = source notes, not
sent), write `## genel` and optional sections that override `_genel.md` keys used by `ek=KEY` blocks, add a
`KONUSMA_HIZI` row with its source, copy `hedef_dil.py` byte-identically to `claude_code_cli/scripts/`, then run
`pytest tests/test_ceviri_hedef_dil.py`. Full steps: [docs/diller.md](../../../docs/diller.md#adding-a-language-appendix).

## Common errors

| Symptom | Fix |
|---|---|
| `401 Unauthorized` with Codex although logged in | an invalid `OPENAI_API_KEY` in the environment; the app removes it for the child process, check your shell profile |
| `codex.ps1` blocked by execution policy | call `codex.cmd` or set `CODEX_BRIDGE_CODEX_BIN` to it |
| Claude: not authenticated | open `claude` once and sign in; no retry is done for auth errors |
| `yerel` + target ≠ `tr` or non-English source | settings error by design; choose an LLM backend |
| `auto` fell back to `yerel` and the target is not `tr` | install / log in to a CLI or pick an API backend |
| API backend shows `yok` in `dubla kontrol` although the key is set | check the variable name against `.env.example` (see note in [docs/motorlar/gemini_2_5_flash.md](../../../docs/motorlar/gemini_2_5_flash.md)) |
| `translation_result_wrong_language` | the model answered in another language (often the source or Turkish); the error is marked retryable; if it repeats, check the target code and the language appendix |
| 503 "high demand" (Gemini) | provider capacity; the group is retried with backoff, then deferred |

Codex troubleshooting ladder: `codex --version` → `codex login status` → `codex exec --skip-git-repo-check "Reply only with OK."`.

## Related

[docs/engineering/translation.md](../../../docs/engineering/translation.md) ·
[docs/adr/0007-natural-blocks-translation-contract.md](../../../docs/adr/0007-natural-blocks-translation-contract.md) ·
[docs/adr/0008-translation-backend-order.md](../../../docs/adr/0008-translation-backend-order.md) · [.env.example](../../../.env.example) ·
engine pages: [yerel](../../../docs/motorlar/yerel.md), [codex](../../../docs/motorlar/codex.md),
[claude_code](../../../docs/motorlar/claude_code.md), [gemini_2_5_flash](../../../docs/motorlar/gemini_2_5_flash.md),
[gemini_3_1_flash_lite_tier_1](../../../docs/motorlar/gemini_3_1_flash_lite_tier_1.md),
[gemma_4_26b](../../../docs/motorlar/gemma_4_26b.md), [groq_llama_4_scout](../../../docs/motorlar/groq_llama_4_scout.md),
[cerebras_llama_3_1_8b](../../../docs/motorlar/cerebras_llama_3_1_8b.md), [mistral_nemo](../../../docs/motorlar/mistral_nemo.md)

## Türkçe özet

`ceviri.arka_uc=auto`: Codex CLI → Claude Code CLI → yerel Opus-MT (yalnız İngilizce → Türkçe, ağsız). Codex için
`npm i -g @openai/codex` + `codex login`; Claude için `npm i -g @anthropic-ai/claude-code` + `claude` ile bir kez
oturum açma (hesap kullanıcının, giriş kullanıcı yapar). Bulut API'leri kendi anahtarınızla `.env`'de
(`.env.example`'daki adlar). LLM ve API arka uçları metni hizmete gönderir (THIRD_PARTY.md §2). Sessiz yedek yok: arka uç
hata verirse aşama durur. Türkçe dışı hedef dil yalnız LLM/API arka ucuyla; istemler dilden bağımsız şablon + dil eki
(`dil_ekleri/`, ADR 0014), `tr` bayt bayt aynı ve kanıtlı, diğer diller gerçek LLM ile henüz denenmedi; yanlış dilde
dönen çıktı yeniden denenebilir hatadır.
