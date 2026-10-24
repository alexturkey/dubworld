# ADR 0008: Translation backend order Codex CLI → Claude Code CLI → local Opus-MT

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0008)

## Context
The best translation quality came from subscription-based coding CLIs used as isolated text workers. The repository must
also work with no account and no key, and may only ship components with an official, documented path.

## Decision
`ceviri.arka_uc = "auto"` resolves **at selection time**: Codex CLI if installed, else Claude Code CLI, else local Opus-MT
(English → Turkish only). An explicitly chosen backend that is missing, or an API backend without a key, is a hard error.
There is **no failover during a run**: a transient Codex error defers and retries on Codex.

## Consequences
- Codex carries the most evidence (schema enforced by the CLI; all prompt and contract measurements). Claude uses the
  same contract with an isolated 736-token envelope and prompt caching; it needed an extra rule against parenthesised
  glosses that TTS would read aloud.
- Opus-MT is keyless and offline but has no candidates, no ownership check and no spoken-form rules; its quality against
  the LLM backends is not measured.

## Alternatives considered
API providers first (keys, billing, provider-specific hardening); a free-tier provider (daily token cap); an unofficial
web endpoint (removed after a silent-fallback incident); local LLMs on 4 GB (≈ 13 minutes for a 66 s video, unstable
server); mid-run cross-engine failover (mixes tone and caused hidden-fallback bugs).
