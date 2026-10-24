# ADR 0012: Stage checkpoints with input fingerprints and contract versions

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0012)

## Context
Long jobs fail late (TTS, encoding). Re-running recognition and translation after a late failure wastes most of the time,
but reusing an output produced under different settings silently corrupts the result.

## Decision
`pipeline_state.json` per run: each stage stores its contract version, a SHA-256 fingerprint of its inputs and settings,
status, attempts and artefacts (size, mtime, sampled digest). A changed fingerprint or contract version invalidates that
stage and everything after it. Resume never modifies the source run; a new folder is built and moved into place atomically.

## Consequences
A TTS failure does not re-run recognition or translation. Every change to a stage's behaviour must bump its contract
version (new TTS recipe, new alignment policy, new prompt).

## Alternatives considered
Re-run everything (slow); reuse by file existence only (unsafe); pickled state (not portable, unsafe to load).
