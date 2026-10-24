# Translation stage

How the translation bridges work, why the order is Codex CLI → Claude Code CLI → local Opus-MT, and what was
learned from each provider. Türkçe: [../muhendislik/ceviri.md](../muhendislik/ceviri.md).
Decision records: [ADR 0007](../adr/0007-natural-blocks-translation-contract.md),
[ADR 0008](../adr/0008-translation-backend-order.md), [ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md).

Code: `bolum_40_ceviri/` — `bridge_motor_orkestratoru/` (grouping, context, parallel jobs, repair, usage report),
`llm_kopru/` (Codex and API backends sharing one worker), `claude_code_cli/`, `yerel_ceviri/` (Opus-MT),
`arka_uc_secimi.py` (backend selection). Settings: `[ceviri]` in `varsayilan.toml`.

## 1. Codex CLI (`codex exec`): isolation is the main lever

- **Problem:** translation calls started in the project root. Codex loaded the project's agent instructions plus tool
  and plugin schemas into every call: more tokens, slower and more variable output.
- **Root cause:** the working directory and enabled tools are part of the model context. A pure-text task was running in
  a coding environment. The user-level instruction file was suspected and cleared.
- **Fix:** one function builds the command:

```
codex exec --json --skip-git-repo-check --disable <19 features>
  -c model_reasoning_effort="<effort>" --model <model>
  --cd <empty temp dir> --sandbox read-only
  --output-schema <schema> --output-last-message <file> -
```

  - Disabled features include apps, browser use, computer use, hooks, image generation, multi-agent, plugins,
    shell tool, skill search and others.
  - Prompt, job JSON and full discourse go through stdin, never on the command line.
  - The result is read from `--output-last-message`; token telemetry from `turn.completed` events. A missing price
    is recorded as `null` ("not verified"), never as 0.
  - The session ID is read from stderr **and** from the JSON `thread.started` event (stderr alone missed it); the
    session file is deleted only on a unique exact match.
  - Worker timeout 900 s (+60 s margin in the orchestrator). Orchestrator defaults: groups of 10 segments, 2 segments
    of context, 7 parallel jobs; transient group retries with backoff 2, 4, 6, 8, 16, 32 s.
- **Measured (same 2-segment job):** input tokens 20,669 (isolated dir, tools on) → 16,861 (tools off) → 17,125 (final
  hardened prompt + schema). Hundreds of logged calls left 0 session files behind.

### 1.1 The missing reasoning flag (largest single win)

The configuration described a reasoning effort, but the worker never passed it. Adding `-c model_reasoning_effort=...`
took the translation stage from **411.1 s to 17.5 s** (≈ 23.5×) on the same input; end-to-end ≈ 8 m 48 s → 3 m 50 s
(measured). Lesson: verify that a setting actually reaches the subprocess command line.

### 1.2 Model and effort

- A/B on a replayed request: a smaller "nano" model was not available for this account type (hard fail); `minimal`
  effort hard-fails because tools cannot run at minimal effort (never use it); a faster coding model was ≈ 2× faster but
  reversed meaning and negation and damaged encoding (rejected for dubbing).
- Gate for any future default change: account support, no hard fail with `--output-schema`, ID/context/candidate
  contract passes, Turkish characters + meaning + negation + kept terms intact, faster on a real replay, cost recorded.
- Current defaults: Codex `gpt-5.6-luna` with `medium` effort; Claude `claude-sonnet-5-5` with `medium`. **No recorded
  A/B** justifies these two specific choices over alternatives; treat them as configurable.
- **Full-text mode switches to `high` above 6,000 source words.** A 10,497-word source returned `partial` three times at
  `medium` (38,743 input tokens; 9.0k / 14.8k / 11.4k output tokens; 119–183 s per call); the same input at `high`
  succeeded on the first call (measured). Same-request retries of a `partial` burn tokens without fixing anything.
  Known-good at `medium`: 3,000–5,250 words. The safe boundary is not established.
- No automatic model fallback inside a run: mixing models in one video mixes tone, JSON discipline and style.

### 1.3 Windows install and authentication problems

| Symptom | Root cause | Fix |
|---|---|---|
| `401 Unauthorized` although `codex login status` is OK | an invalid `OPENAI_API_KEY` in the environment pushed Codex onto API-key auth | remove `OPENAI_API_KEY` and `CODEX_API_KEY` from the **child** environment only; record `authentication_mode=saved_chatgpt_login` without values |
| `windows sandbox: helper_unknown_error: apply deny-read ACLs` | the sandbox ACL state file under `~/.codex/.sandbox/` was 22 zero bytes | with Codex closed, rename the file; Codex regenerates it |
| worker would not start | a non-UTF-8 file in the global skills tree | temporary `CODEX_HOME` containing only a copy of `auth.json` |
| `invalid_json_schema ... schema must have a 'type' key` | `const` fields without `type` | give every `const` an explicit `type` |
| `codex.ps1` blocked | PowerShell execution policy | call `codex.cmd` |

Troubleshooting ladder: `codex --version` → `codex login status` (`--device-auth` when headless) →
`codex exec --skip-git-repo-check "Reply only with OK."` → check key variables exist (never print values) → `codex doctor`.
Exit code 0 is not proof that the output file was written.

## 2. Claude Code CLI

```
claude --print --output-format json --model <m> --effort <e>
  --system-prompt-file <tmp> --disallowed-tools "*"
  --strict-mcp-config --no-chrome --no-session-persistence
  --permission-mode dontAsk --setting-sources ""
```

- Runs in an empty temp directory; job via stdin; auth is the saved CLI login (`claude auth login`). `--bare` is not used
  because it forces an API key and disables the saved login.
- There is no `--output-schema`: the schema is appended to the system prompt; JSON is extracted (code fence, then a
  balanced-brace scan) and passed through the same result gate as Codex.
- **Measured envelope cost on a trivial request:**

| Envelope | Context tokens | Reported cost |
|---|---|---|
| default | 23,815 | $0.101 |
| replaced system prompt only | 23,815 | $0.095 |
| restricted tools | 18,968 | $0.076 |
| **`--disallowed-tools "*"`** | **736** | **$0.003** |

  Replacing the system prompt alone does not help because tool schemas still load.
- Keep the mode prompt, ASR rules and schema in the **system prompt** so they are cached: the second call of a run cost
  ≈ ¼ of the first (cache read 5,996 tokens).
- **Retry contract:** missing IDs or empty candidates → up to 2 rounds asking only for those IDs; job ID mismatch → one
  full rerun; full-text `partial` → up to 2 review rounds; natural-blocks chain review → 1 round.

| error_type | retry | wait |
|---|---|---|
| usage limit | yes | 900 s |
| overloaded / temporary network / API error | yes | 120 s |
| timeout | yes | 300 s |
| envelope not JSON | yes | 60 s |
| result not JSON | no | – |
| not authenticated | no | – |

  HTTP codes match only in a status context (a bare "500" in text is not an error). Retries stay on the same backend.
- **Hidden fallbacks removed:** a Claude selection was silently overwritten to Codex in three places (job record, menu
  runtime, GUI lock). Now an invalid or missing backend raises `BridgeBackendSecimHatasi`; full-text mode supports exactly
  `{codex, claude_code}`.
- **Box lock:** API backends were copies of one worker that could run any provider; each box now carries its own
  backend id and stops with `bridge_backend_mismatch` before any call.
- **Reading rule for TTS:** with the same full-text prompt, Codex produced 0 parentheses in 20 translations, Claude added
  English glosses in parentheses that TTS reads aloud. A Claude-only rule bans parentheses, bilingual glosses and
  footnotes. Measured on a 2,843-character source: parentheses 5 → 0, 60.2 → 51.6 s.

## 3. Prompts, schemas and the natural-blocks contract

### 3.1 Prompt map (selected by mode)

| Mode | Schema |
|---|---|
| `full_text_translation` | `output_schema_full_text_translation.json` |
| segment modes with 2 or 10 candidates | `output_schema.json` |
| **`supertonic_natural_blocks_1` (recommended flow)** | `output_schema_natural_blocks_v2.json` |
| whole-chain master / candidates / repair | `output_schema_supertonic_whole_chain.json` |

- **ASR correction** is appended to every prompt (not a separate call): the source is the recognizer's guess; only
  high-confidence mishearings proven by context (names, acronyms, homophones, split words) may be corrected; sound
  similarity alone is not evidence; no summarising or moving meaning between segments.
- **Full discourse context:** the whole ordered transcript is sent as context; `main_segment_ids` mark what this call
  translates.
- **Terms:** an over-broad "keep technical terms in source spelling" rule left English words inside Turkish sentences.
  Fix: established Turkish equivalents are mandatory (e.g. AI → yapay zeka); a translated term may not appear in
  `kept_terms`; a code filter drops kept terms not present in both source and candidate.

### 3.2 Spoken forms of numbers and symbols

- **Decision:** the model writes the spoken form; there is no mechanical post-processing. A rule like `K → "ka"`
  cannot tell "8K video" (read as the letter) from "8K tokens" (eight thousand). Rewriting after validation would also
  split subtitle text from TTS text.
- One validated text feeds both subtitles and TTS.
- The natural-blocks schema forbids Arabic digits in candidates (`^[^0-9]*[^\s0-9][^0-9]*$`).
- The prompt's spoken-form section: decide the role of a number or symbol from context, write the spoken form,
  silently back-translate to check value, sign, unit and identity; decimal separator → "virgül", version separator →
  "nokta". Examples cover years, percentages, currency, units, versions, resolutions, frame rates and codecs.

### 3.3 Natural blocks (one natural candidate, meaning locked to its segment ID)

- **Problem:** segment boundaries come from speech, not sentences. Segment-by-segment translation sounds like
  subtitles; translating freely and re-splitting moves meaning into the neighbouring ID. Example kept in the prompt:
  "I am testing the code to ensure that | the right value is set." must become
  "Şundan emin olmak için kodu test ediyorum:" | "doğru değer ayarlanmış." — not a version where the purpose clause
  jumps into the other ID.
- **Prompt evolution:** v2 "imagine the group as one Turkish utterance and distribute it at clause boundaries" → v3
  "grasp intent, emotion and emphasis; think in Turkish" → **v4 priority order**: (1) meaning stays in its ID, (2)
  complete, nothing added, facts preserved, (3) the concatenation sounds natural, (4) numbers/symbols in spoken form.
  An ID ending in an open connective ("that", "because") ends with a neutral bridge; punctuation-only candidates are
  forbidden; the model checks each ID against its source before answering.
- **Schema v2:** strict (`additionalProperties: false`); per ID exactly one candidate plus `ownership_check`
  {`status`, `source_coverage`, `neighbor_meaning_imported`, `neighbor_meaning_exported`}.
- **Code gates:** expected IDs equal; a candidate must contain a letter or digit; catastrophic coverage: if the source
  has ≥ 8 words and candidate words × 4 < source words, reject. The model's own "complete" claim is never trusted
  alone. One chain-review retry grounded in the real source and target.
- **Timing is advisory here**, never a validity gate: natural Turkish is never padded to fill time; the final timing
  decision is made on real synthesized audio (see [tts_timing_and_mix.md](tts_timing_and_mix.md)).
- **Tried and removed:** requiring verbatim source/target span evidence covering every word (replaced by the boolean
  flags plus the coverage ratio; the reason was not recorded). A second-pass LLM audit (61–97 s extra for 98 segments,
  9–10 corrections, one run failed its own validation): never integrated, costs about one extra translation pass.
- **Target languages other than Turkish** ([ADR 0014](../adr/0014-language-independent-translation-prompts.md)): prompts and
  schemas carry template markers rendered by `llm_kopru/scripts/hedef_dil.py`. For `tr` the rendered text is
  byte-identical to the earlier Turkish prompts (110 golden hashes in `tests/veri/ceviri_istem_tr_altin.json`). Other
  targets get the general appendix `dil_ekleri/_genel.md` plus `dil_ekleri/<code>.md` when it exists (en, de, fr, es,
  it, pt, ru, ar, ja, zh). Word-count gates and timing estimates use a per-language rate table (`tr` 0.43 s per word,
  measured; others estimated; ja/zh/ko/th counted in characters). A result in the wrong language raises the retryable
  `translation_result_wrong_language` error (0 false alarms on 192 correct texts). Not yet validated with a real LLM.

## 4. API providers (optional backends, your own key)

### Gemini

| Problem | Root cause | Fix | Measured |
|---|---|---|---|
| "Unterminated string" JSON errors | `finishReason=MAX_TOKENS` (≈ 8,180 tokens against the app's own 8,192 cap) | send no output cap; size groups instead | – |
| IDs missing, fragments merged into earlier IDs | prompt alone and JSON mode alone do not enforce IDs; old retry regenerated IDs | strict mode: JSON schema with an **ID enum**, temperature 0.15 (retry 0.05), required/read-only/forbidden ID lists in the job, code rejects duplicates/extras, retry asks only for missing IDs | 40/40 IDs, 0 violations |
| hard schema rejected with 400 | unsupported keywords (`additionalProperties`, `minItems`…), `mimeType` must be `APPLICATION_JSON` | minimal schema | – |
| correct IDs but meaning drift | the request ranked timing above fidelity, so short segments were padded with neighbour meaning | `meaning_safety_contract` in the request; meaning-safe minimum ratios 0.35/0.40/0.55 by length | 464/464 segments, 0 violations; cost $0.443 → $0.294 |
| 503 "high demand" | provider capacity | model-specific retry only for 503 capacity messages, 0.5 → 8 s backoff with jitter (≈ 15–20 s), then defer the group; 429/401/403/400 excluded | success rate: no record |
| one of 32 parallel groups failed with `Resource deadlock avoided` | Windows byte-range lock on the request-spacing lock file | classified as retryable; only that group reruns | – |

Repair-prompt lessons: hard "too long" or "compress" instructions made results worse under real TTS and were rolled
back; deterministic duplicate removal cut TTS measurements ≈ 18 %; repair candidates are capped at the candidate count;
the loop counts repairs, not rounds (an off-by-one had allowed only 4 of 5 repairs). Per-video cost is taken from the
output folder's usage report (the canonical record); a central ledger is only an index.

### Groq, local LLMs, unofficial Google endpoint (history)

- **Groq:** the bottleneck was free-tier tokens per day, not money; some models were blocked without a User-Agent
  header or rejected requests above their per-minute token limit. Optional backend only.
- **Local LLMs via llama.cpp (4 GB card, Q4 models):** small models made meaning errors (durations, numbers), mixed
  context or broke Turkish words; the best one was usable but ≈ 13 minutes for a 66 s video, and the server process died
  silently on its first request. Lessons: JSON schema fixes shape, not meaning; merge-then-split breaks meaning. Not
  carried over; replaced by Opus-MT as the keyless floor.
- **Unofficial Google endpoint:** on a rate-limit response the engine fell back to the **source text**, so an English
  text was voiced and delivered as "completed". This incident produced the no-silent-fallback rule. Removed: no official
  documented path.

## 5. Local Opus-MT

`Helsinki-NLP/opus-mt-tc-big-en-tr` (MarianMT, CC BY 4.0), pinned commit + SHA-256, offline (`local_files_only`),
batch 16, beams 4, `max_new_tokens` 256, GPU or CPU. English → Turkish only; other pairs and full-text mode are blocked
by configuration. No candidates, no ownership check, no ASR correction, no spoken-form rules, no timing awareness.
Quality versus the LLM backends: **no record**.

**Empty output:** when the model returns an empty translation for any non-empty segment, the engine raises
`YerelCeviriHatasi` and lists the affected segment numbers. Returning the source text in that case would be the same
silent-fallback pattern as the Google incident (ADR 0009), so it is not done.

## 6. Error contract (all backends)

- No silent fallback; errors chained with `raise … from`.
- Transient errors move the group to `deferred` only where the backend's contract allows it; retries stay on the same
  backend.
- A segment without a candidate raises `CeviriEksikSegmentError`; a count mismatch stops the job.
- One user-message generator masks keys and absolute paths.

## 7. Open items

1. Chunked full-text translation for when `high` effort also returns `partial` (designed, not implemented).
2. Opus-MT quality measurement.
3. A real-video Codex-vs-Claude quality comparison; the TTS reading rule for Claude's segment prompts.
4. Remove `minimal` from the accepted Codex efforts.
5. A timing-aware translation memory (store candidates with real TTS durations, reuse above a confidence threshold) is
   designed only.
