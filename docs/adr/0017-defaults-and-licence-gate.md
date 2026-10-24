# ADR 0017: Defaults follow the proven flow within redistributable licences; everything else is opt-in

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0017)

## Context
The pipeline grew with many interchangeable engines (registry: `src/dublaj_hatti/kayit.py`). Their licences range from
permissive (MIT, Apache-2.0) through conditional (Open RAIL-M use restrictions, NVIDIA Open Model License) and
non-commercial (CrisperWhisper weights, Coqui CPML) to provider terms (cloud APIs, subscription CLIs). Two optional
features imitate a real voice (XTTS reference voice, RVC model). A repository must not ship weights it may not
redistribute and must not let a user cross a licence line without noticing.

## Decision
- **Defaults** (`src/dublaj_hatti/varsayilan.toml`) reproduce the flow that carried most of the measurement and tuning
  work in the earlier version of the pipeline, restricted to components whose licence allows this repository to point
  to them: `transkripsiyon.motor = "auto"`, `ceviri.arka_uc = "auto"` ([ADR 0008](0008-translation-backend-order.md)),
  `ses.motor = "supertonic"` ([ADR 0015](0015-tts-engine-set-and-default.md)), `ses.akis = "natural_blocks_1"`
  ([ADR 0007](0007-natural-blocks-translation-contract.md)), `ses.atempo = true`, `ses_temizligi.kip = "original"`,
  segment subtitles, CQ 26 ([ADR 0011](0011-video-encoder-selection.md)).
- Where the most-proven component has a non-commercial licence, `auto` prefers it **only when the user installed it
  with an explicit acceptance flag**; otherwise the nearest permissive alternative is used (CrisperWhisper Turbo →
  `faster_whisper_ctc`: faster-whisper text + shared CTC word times, [ADR 0005](0005-ctc-forced-alignment-only-time-source.md)).
  An explicitly chosen `faster-whisper` keeps Whisper's own word times; a missing CTC model stops the job with the
  install step instead of falling back to them ([timing-sources.md](../engineering/timing-sources.md) §2).
- Weights are never stored in the repository. Models are downloaded at pinned commits with SHA-256 checks
  (`scripts/modelleri_indir.py`, `scripts/modeller.json`).
- First use of a non-commercial or conditional engine requires an explicit acceptance (`lisans_onayi.py`: CLI flag,
  interactive prompt, GUI checkbox, web confirmation or `DUBLAJ_LISANS_ONAY=1`). One gate (`kapi_adlar`) for every
  entry point: `dubla <video>`, `dubla transkript`, every stage command (`dubla seslendir`, `dubla yaziya-dok` …),
  `dubla devam`, the Python API (`lisans_onay=True`), GUI, web, and the job runner as the last check (a queued or
  resumed job without acceptance stops with exit 2, it never asks). Only engines that the command really runs are
  asked (`dubla transkript` never asks for the voice). The record holds only the engine name,
  the accepted licence text and a UTC date; a changed licence text asks again. XTTS has its own CPML acceptance; RVC
  requires a consent statement for the voice owner (`ses.rvc_riza_onayi`).
- GPL tools are never imported: gallery-dl runs as a separate program. Cloud and CLI backends send data to the
  provider only when explicitly selected or found by `auto`; every such page states what is sent.

## Consequences
- A fresh install runs end to end on permissive components only.
- Users who accept a non-commercial engine get the most-measured path; the registry warning tells them the limit.
- Some defaults have no recorded A/B against alternatives (for example the 1.0 s segment gap, the LLM model names);
  they are documented as configurable, not as proven optima.

## Alternatives considered
- Defaults chosen only by licence, ignoring the measured flow: would select engines with no measurement behind them.
- Defaults equal to the most-proven flow regardless of licence: would make a non-commercial model the silent default.
- Shipping weights in the repository: not permitted for several models and inflates the repository.
