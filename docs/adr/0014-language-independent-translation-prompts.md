# ADR 0014: Language-independent translation prompts with per-language appendices

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0014)

## Context
The LLM translation backends (`llm_kopru/`, `claude_code_cli/`, the bridge orchestrator) accept any target language,
but every prompt, the output schema descriptions, the repair instructions and the timing estimate were written for
Turkish:

- Prompt bodies named the target as "Turkish" and contained Turkish-only spoken-form rules (number reading, suffixes,
  date order). A French or Japanese job therefore received instructions to write Turkish.
- The words-per-second estimate was a single constant, 0.43 s per word, measured on Turkish dubbing. Languages written
  without spaces (Chinese, Japanese, Korean, Thai) were counted by `split()`, which returns one "word" per sentence.
- Nothing checked that the returned text was in the requested language. A response in the source language or in Turkish
  passed every structural check.

Constraint: Turkish is the production-proven path. Any change must leave every Turkish prompt, schema and repair text
byte-identical, because the measured Turkish quality depends on those exact texts.

## Decision
- **Template markers inside the existing prompt files**, rendered by `llm_kopru/scripts/hedef_dil.py`
  (`istem_isle`, byte-identical copy in `claude_code_cli/scripts/`):
  - inline placeholders `{target_lang_name}`, `{target_lang_name+SUFFIX}`, `{target_lang_name_ascii}`,
    `{target_lang_name_en}`, `{target_lang_code}`;
  - line blocks `<!-- dil:tr -->` … `<!-- dil:diger -->` … `<!-- /dil -->` or `<!-- dil:tr ek=KEY -->`.
  For `tr` only the Turkish part of each block is kept and the placeholders resolve to the original words, so the
  rendered text equals the original file. For any other target a block resolves to its `diger` text, else to section
  `KEY` of `dil_ekleri/<code>.md`, else to the same section of `dil_ekleri/_genel.md`; an empty section removes the block.
- **Per-language appendices** in `bolum_40_ceviri/dil_ekleri/`: `_genel.md` (rules valid for every non-Turkish target)
  and `en, de, fr, es, it, pt, ru, ar, ja, zh`. For a non-Turkish target, section `genel` of `_genel.md` and of the
  language file is appended to the prompt. A language without its own file still receives the general appendix.
- **Schema descriptions** use `{target_lang_name_ascii}`; Python repair and retry texts name the target through
  `dil_adi` / `dil_adi_en`.
- **Speech-rate table** `KONUSMA_HIZI`: `tr` stays at the measured 0.43 s per word. Other values are estimates and are
  labelled as such in the table. `ja`, `zh`, `ko` and `th` are counted in characters and converted to word-equivalents
  (`kelime_esdegeri`); a language not in the table keeps 0.43.
- **Output-language check** (`metin_dili_sorunu`, no new dependency). Words that also appear in the source text or in
  `kept_terms` are removed first. A result is flagged when one of these holds:
  - the expected script covers less than 50 % of the remaining letters (checked only with ≥ 8 letters);
  - a Japanese target contains ≥ 8 Han characters and no kana, or a Chinese target contains kana;
  - a non-Turkish Latin-script target contains ≥ 3 of the letters ı, ğ, ş (Romanian is exempt from ş);
  - a Latin-script text of ≥ 4 words scores 0 on the target's function-word profile and ≥ 3 on another profile.
  A flagged result raises `BridgeError` `translation_result_wrong_language`, retryable with retry reason
  `output_language_mismatch`. Mock mode skips the check. There is no fallback to another text
  ([ADR 0009](0009-fail-closed-no-silent-fallback.md)).

## Consequences
- Turkish output is unchanged. A golden file (`tests/veri/ceviri_istem_tr_altin.json`) stores SHA-256 hashes of 110
  rendered Turkish artifacts taken before the change: every backend and mode prompt, codex schemas, Claude system and
  stdin texts, Python retry texts and orchestrator jobs. All 110 match.
- Template rendering is tested for all 85 language codes: no placeholder or marker remains, every `ek=` key exists in
  `_genel.md`, and a French prompt body contains no Turkish language name.
- Output-language check, measured on 192 correct texts (144 Turkish dubbing lines from the prompts, appendix examples
  and synthetic sentences): 0 false alarms. The same texts checked against a different target are flagged in
  661 of 960 cases (68.9 %) for texts of ≥ 4 words or CJK text; script-level mismatches (Cyrillic, Han, kana, Arabic
  against another script) are flagged in every case. Texts shorter than 4 words are flagged in 25 % of cases;
  this is intentional to avoid false alarms on names and interjections.
- The appendices and the non-Turkish rate values have not been validated with a real LLM or a real dubbing run.
  Open items:
  - a real-backend trial for French and Japanese;
  - prompts still assume an English source in places;
  - `pt-BR` and `zh-TW` are normalised to `pt` and `zh`, so regional variants are not inferred;
  - rate values need measurement.

## Alternatives considered
- **Separate prompt files per language:** 31 prompt files × N languages; Turkish fixes would have to be copied by hand
  and would drift.
- **Rewriting the prompts in neutral English:** changes the Turkish prompts and therefore the measured Turkish output.
- **A language-identification library (fastText, lingua, langdetect):** a new dependency and model download for a check
  that, on dubbing-length texts, needs only script ranges and a short function-word list. Short-text accuracy of such
  libraries is also low, which is the false-alarm case that matters here.
- **Silent acceptance or re-translation with another backend on mismatch:** violates ADR 0009.
