---
name: sorun-giderme
description: "Diagnose and fix errors of this dubbing pipeline: CUDA out of memory and low VRAM, wrong torch build, ffmpeg missing or old, GPU lock / job stuck waiting, install and hash errors, translation login errors, slow runs. Use when the user says 'error', 'it crashed', 'out of memory', 'OOM', 'CUDA', 'ffmpeg', 'stuck', 'too slow', 'hata', 'çöktü', 'bellek yetmedi', 'kurulum hatası', 'neden yavaş', or pastes a traceback."
---

# Troubleshooting / Sorun giderme

Türkçe özet en altta. / Turkish summary at the end.

## When to use

Any failure or unexpected slowness. Start with facts, not guesses: collect the exact message, the exit code and
the job's own records before changing anything.

## First five checks

1. `dubla kontrol` — hardware, ffmpeg, which engines are installed.
2. `dubla sorunlu` — the failing stage and the error of the last jobs.
3. `dubla ayarlar` — the merged settings; `uyarı:` lines on stderr.
4. Re-run with a debug log: add `--ayrintili` (or `--ayar genel.gunluk_seviyesi=DEBUG`).
5. Exit code: `1` stage failed · `2` usage / setting / license acceptance · `75` GPU busy (deferred) · `130` stopped.

Rules that hold everywhere: no silent fallback (a failing engine stops with an error,
[ADR 0009](../../../docs/adr/0009-fail-closed-no-silent-fallback.md)); one GPU job at a time; every heavy model in its
own process ([ADR 0001](../../../docs/adr/0001-one-gpu-job-and-process-per-model.md)).

## Symptom table

| Symptom | Likely cause | Fix | Read |
|---|---|---|---|
| `CUDA out of memory` (WhisperX, Demucs) | another GPU program, long input, fp32 on a small card | close other GPU programs (`nvidia-smi`); jobs retry once (int8 / batch 1); `transkripsiyon.hesap_tipi=int8` | [low_vram.md](../../../docs/engineering/low_vram.md) §3 |
| Job 2–8× slower, no error | VRAM spilled into shared system memory | Task Manager → GPU → shared memory; close GPU programs; int8 | [low_vram.md](../../../docs/engineering/low_vram.md) |
| `no kernel image is available` | torch build without the GPU's architecture | reinstall the profile with `kur.ps1 -Adim paketler` | [low_vram.md](../../../docs/engineering/low_vram.md) §1 |
| `float16` refused | older GPU has no fast fp16 in CTranslate2 | `hesap_tipi=auto` (picks int8 / float32) | [gpu_memory_and_isolation.md](../../../docs/engineering/gpu_memory_and_isolation.md) |
| GPU-only engine on CPU machine | `crisperwhisper_*`, `voxcpm2` have no CPU path | choose a CPU engine (the error names it) | [donanim.md](../../../docs/donanim.md) |
| `ffmpeg: YOK` / ffmpeg not found | pinned FFmpeg not installed | `kur.ps1 -Adim modeller` (FFmpeg lives in `runtime_assets/ffmpeg/bin`, added to PATH by the CLI) | [video_subtitles_and_resume.md](../../../docs/engineering/video_subtitles_and_resume.md) |
| NVENC error on encode | driver too old for the NVENC API, or no NVIDIA | automatic switch to libx264 is built in; force with `DUBLAJ_VIDEO_KODLAYICI=x264` | [ADR 0011](../../../docs/adr/0011-video-encoder-selection.md) |
| `meşgul, sıra bekleniyor` / state `deferred` | machine-wide GPU lock held | `python -m dublaj_hatti.bolum_00_omurga.runtime.kaynak_kilidi durum` | [devam_ve_sorunlu_isler.md](../../../docs/tarifler/devam_ve_sorunlu_isler.md) |
| Job stays `processing` after a crash | process gone, record not updated | `dubla isler --kurtar`, then `dubla devam <N>` | skill `devam-ve-sorunlu-isler` |
| Hash mismatch / `model indirme başarısız` | interrupted or changed download | rerun the same `kur.ps1` step (partial `.part` files are discarded); never disable the sha check | [AGENTS.md](../../../AGENTS.md) |
| Model download attempted at run time and fails offline | run-time downloads are off by default | install with `kur.ps1`; only if intended: `DUBLAJ_CEVRIMICI=1` | [kurulum-ve-donanim](../kurulum-ve-donanim/SKILL.md) |
| `ayar hatası: ...` | unknown key or rejected combination | the message says what to change | [kombinasyonlar.md](../../../docs/tarifler/kombinasyonlar.md) |
| `lisans onayı yok` | non-commercial / conditional engine not yet accepted | ask the user; `--lisans-onay` only after they accept | [THIRD_PARTY.md](../../../THIRD_PARTY.md) |
| Translation: 401 / not authenticated | Codex or Claude Code not logged in, or a wrong `OPENAI_API_KEY` in the environment | skill `ceviri-arka-uclari` | [translation.md](../../../docs/engineering/translation.md) §1.3 |
| Dubbed speech longer than the original | long translation | `ses.atempo=true`, `ses.akis=repair_3_light` with an LLM backend | [tts_timing_and_mix.md](../../../docs/engineering/tts_timing_and_mix.md) |
| Words clipped / subtitles drift | timing source | every engine uses CTC word times; see the alignment page | [word_alignment.md](../../../docs/engineering/word_alignment.md) |
| Diarization: wrong speaker count | short or overlapping speech | pin voices with `ses.konusmaci_sesleri`; or `ses.cinsiyet_kipi=segment` | [speakers_and_segments.md](../../../docs/engineering/speakers_and_segments.md) |

## Collecting a good bug report

- Command, exit code, the last 30 lines of the debug log, `dubla kontrol --json`, OS and GPU class.
- Remove personal paths, names and keys before sharing (the issue template asks for this). Security problems go to
  [SECURITY.md](../../../SECURITY.md), not to a public issue.
- Each job folder keeps per-stage records (e.g. `gpu_diagnostics.jsonl` for GPU memory).

## Related

[docs/engineering/README.md](../../../docs/engineering/README.md) (per-stage history: problem → root cause → fix) ·
[docs/engineering/low_vram.md](../../../docs/engineering/low_vram.md) ·
[docs/engineering/gpu_memory_and_isolation.md](../../../docs/engineering/gpu_memory_and_isolation.md) ·
[docs/adr/README.md](../../../docs/adr/README.md) · Türkçe: [docs/muhendislik/README.md](../../../docs/muhendislik/README.md)

## Türkçe özet

Önce bilgi topla: `dubla kontrol`, `dubla sorunlu`, `dubla ayarlar`, `--ayrintili` ile hata ayıklama günlüğü ve çıkış
kodu (1 aşama hatası, 2 ayar/lisans, 75 GPU meşgul, 130 durduruldu). Sık durumlar: VRAM yetmedi → başka GPU
programını kapat, int8; ffmpeg yok → `kur.ps1 -Adim modeller`; iş takıldı → `kaynak_kilidi durum`,
`dubla isler --kurtar`; hash hatası → aynı adımı yeniden çalıştır, sha denetimi asla gevşetilmez; çeviri 401 →
`ceviri-arka-uclari`. Sessiz yedek yoktur. Ayrıntılı kök neden geçmişi: `docs/engineering/` (TR `docs/muhendislik/`).
