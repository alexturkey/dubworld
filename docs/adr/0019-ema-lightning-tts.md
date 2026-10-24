# ADR 0019: EMA Lightning as an optional Turkish TTS engine with a GPU path and a locally exported CPU ONNX path

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0019)

## Context
Turkish is the main target language. Supertonic reads it on the CPU but its voices are tuned for many languages;
VoxCPM2 gives designed Turkish voices but needs an NVIDIA GPU and about 3 GB of VRAM. A small Turkish-only model,
EMA Lightning (8.6 M parameters, Apache-2.0 code and weights), reads Turkish numbers, dates and units itself and is
fast on both a GPU and a CPU. Before adding it, three conditions were checked against the official sources: the code
licence (PyPI package metadata and repository: Apache-2.0), the weight licence (model card: Apache-2.0, commercial use
included) and the voice (model card: a single synthetic voice designed in VoxCPM2 from a text description, trained on
about 1,000 hours of synthetic speech generated with VoxCPM2, Apache-2.0; no recording of a real person). The model
publisher ships PyTorch weights only; ONNX files exist only as third-party conversions.

## Decision
- Add `ses.motor = ema_lightning`, opt-in (`scripts/kur.ps1 -Adim tts-ema`): the package from a hashed lock into the
  main environment (PyTorch is already there; a CPU-profile lock exists), the weights from the official model
  repository at a pinned commit with SHA-256, checked again before every `torch.load`.
- The CPU path uses ONNX Runtime with files **exported on the user's machine from the same checked weights**, not
  downloaded third-party conversions. The export is compared with PyTorch on a sentence of a different length; if the
  largest difference exceeds 1e-3 the CPU path uses PyTorch instead.
- Device choice `ses.ema_cihaz = auto | cuda | cpu`. `auto` takes the GPU when it has at least 1 GB free and falls
  back to the CPU when there is no GPU, when it is busy, or when a GPU run fails with a CUDA or memory error (one
  retry). An explicit `cuda` never falls back.
- One subprocess per job, model loaded once, GPU memory released at exit. `cudnn.benchmark` is off (on a 4 GB
  Pascal-class card autotuning made a 30 s text take 202 s instead of about 1 s).
- Turkish only: any other target language is a settings error. Both dubbing modes are supported; `full_text` reads
  sentence by sentence so the alignment windows come from real audio.

## Consequences
- Turkish dubs can run fully on the CPU at about 11× real time after a 12 s start-up, or on the GPU.
- The install exports ONNX once (about 11 s on the reference CPU); a different PyTorch version can produce
  byte-different but numerically equal files, so the files are verified by output, not by hash.
- For a single short sentence PyTorch on the CPU finishes before ONNX (shorter start-up); dubs are long enough for
  ONNX to win.
- One voice only; variety comes from the seed (`ses.ema_tohum`), not from voice choice.

## Alternatives considered
- Downloading a third-party ONNX conversion: faster to set up, but not from the publisher; its weights could not be
  matched to the official checksum.
- PyTorch on the CPU only: no export step, but 2.4× on a new text and as low as 0.7× on the first pass of new input
  lengths in earlier records, against about 11× with ONNX.
- `lightning()` (torch.compile + CUDA graphs): the publisher's fastest path, never measured on a 4 GB Pascal-class
  card and it turns cuDNN autotuning on; left out until measured.
- Keeping the model warm between jobs: saves seconds per call but holds GPU memory that other stages need.
