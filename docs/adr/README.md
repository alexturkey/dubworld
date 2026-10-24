# Architecture Decision Records

Format: Context / Decision / Consequences / Alternatives considered. Türkçe özetler: [../muhendislik/kararlar.md](../muhendislik/kararlar.md).
Background and measurements: [../engineering/README.md](../engineering/README.md).

| # | Decision |
|---|---|
| [0001](0001-one-gpu-job-and-process-per-model.md) | One GPU job at a time, one process per heavy model |
| [0002](0002-demucs-batched-two-stem-worker.md) | Demucs in a batched two-stem worker with a one-time OOM fallback |
| [0003](0003-automatic-background-detection.md) | Decide separation from a measured background level |
| [0004](0004-crisperwhisper-turbo-ct2-int8.md) | CrisperWhisper Turbo through CTranslate2 int8 in a one-shot WSL2 worker |
| [0005](0005-ctc-forced-alignment-only-time-source.md) | CTC forced alignment is the only source of word times |
| [0006](0006-two-stage-dub-segmentation.md) | Two-stage dub segmentation (1.0 s gap, ≤ 150 words) |
| [0007](0007-natural-blocks-translation-contract.md) | "Natural blocks" translation contract |
| [0008](0008-translation-backend-order.md) | Translation backend order Codex → Claude → Opus-MT |
| [0009](0009-fail-closed-no-silent-fallback.md) | Fail closed, no silent fallback |
| [0010](0010-real-tts-duration-is-canonical.md) | Real synthesized duration is canonical |
| [0011](0011-video-encoder-selection.md) | Encoder selection by trial encode, CQ 26 |
| [0012](0012-stage-checkpoints-and-resume.md) | Stage checkpoints and resume |
| [0013](0013-silero-vad.md) | Silero VAD replaces FSMN VAD in speaker separation (licence) |
| [0014](0014-language-independent-translation-prompts.md) | Language-independent translation prompts with per-language appendices and an output-language check |
| [0015](0015-tts-engine-set-and-default.md) | Supertonic default TTS; VoxCPM2 and XTTS v2 optional, each in its own process |
| [0016](0016-rvc-as-post-tts-conversion.md) | RVC voice conversion is a post-TTS layer on the timed mix |
| [0017](0017-defaults-and-licence-gate.md) | Defaults follow the proven flow within redistributable licences; the rest is opt-in |
| [0018](0018-local-bot-api-server-for-large-files.md) | Large Telegram deliveries go through a local Bot API server, as playable video |
| [0019](0019-ema-lightning-tts.md) | EMA Lightning as an optional Turkish TTS engine: GPU path and a locally exported CPU ONNX path |

New ADR: copy the format, take the next number, link it here and from the relevant `docs/engineering/` page.
