---
name: stt-motorlari
description: "Choose and run a speech-to-text (transcription) engine and the right source-language detection mode: faster-whisper, WhisperX, CrisperWhisper Turbo/Medium, Moonshine, whisper.cpp, Parakeet, Speechmatics, ElevenLabs, YouTube captions. Use when the user says 'which transcription engine', 'better word timing', 'English only on CPU', 'language detection', 'mixed language', 'code-switching', 'kaynak dil', 'transkript motoru', 'dil tespiti', 'transcribe this', or transcription quality/timing is wrong."
---

# Speech-to-text engines and language detection / STT motorları ve dil tespiti

Türkçe özet en altta. / Turkish summary at the end.

## When to use

Picking or changing `transkripsiyon.motor`, fixing wrong language detection, or transcribing without dubbing.
Every engine has its own page: `docs/motorlar/<engine>.md` (name = setting value).

## Engines at a glance

| Setting value | Device | Languages | License (weights) | Install |
|---|---|---|---|---|
| `faster-whisper` | GPU or CPU | multilingual | MIT | base install |
| `whisperx` | GPU or CPU | multilingual (+ pyannote speakers, optional) | BSD-2 code; MIT / CC-BY-4.0 models | base install |
| `crisperwhisper_turbo_ct2` | NVIDIA GPU + WSL2 | Whisper languages | **non-commercial** | `kur.ps1 -Adim crisper -TicariOlmayanKabul` |
| `moonshine_medium_streaming_en` | CPU | English | MIT | manual (`stt-moonshine` extra + own venv) |
| `whisper_cpp_cpu_align` | CPU | English | MIT | manual (prebuilt binary + model) |
| `parakeet_cpu_align` | CPU | English | NVIDIA Open Model License (conditional) | `kur.ps1 -Adim parakeet` (package + model, sha256-pinned) |
| `speechmatics` | cloud | provider list | provider terms | `kur.ps1 -Adim speechmatics` + key |
| `elevenlabs_scribe_v2` | cloud | provider list | provider terms | key in `.env` |
| `youtube_translate` | GPU or CPU (CTC only) | caption track | YouTube terms | `kur.ps1 -Adim youtube` |
| `auto` (default) | — | — | — | CrisperWhisper Turbo if installed, else faster-whisper |

Every engine except CrisperWhisper gets its word times from wav2vec2 **CTC forced alignment** (one timing contract
for every engine; [ADR 0005](../../../docs/adr/0005-ctc-forced-alignment-only-time-source.md)).

## Steps

1. Check what is installed: `dubla kontrol` (line `stt:`).
2. Choose with this order of questions:
   - Non-commercial use allowed **and** NVIDIA GPU? → `crisperwhisper_turbo_ct2` (most accurate word times; `auto`
     picks it when installed). Tell the user about the non-commercial license first.
   - Commercial use or no WSL2 → `faster-whisper` (default fallback) or `whisperx` (if pyannote speaker labels in the
     transcript are needed: `ileri.pyannote_konusmaci_ayrimi=true`, needs `HF_TOKEN` and accepted model terms).
   - English source, CPU only → `parakeet_cpu_align` (fastest measured) or `whisper_cpp_cpu_align`.
   - Data may leave the machine and the user has a key → `speechmatics` / `elevenlabs_scribe_v2` (THIRD_PARTY.md §2).
3. Set the language mode ([docs/tarifler/dil_tespiti.md](../../../docs/tarifler/dil_tespiti.md)):
   - known single language → `transkripsiyon.kaynak_dil=en` (skips detection, safest);
   - unknown single language → `auto` (default);
   - speakers switch language → CrisperWhisper + `transkripsiyon.crisper_dil_tespiti=continuous_stream`;
   - long video, sections in different languages → `crisperwhisper2_medium` + `per_window`.
4. Run:
   ```powershell
   dubla video.mp4 --ayar transkripsiyon.motor=whisperx --ayar transkripsiyon.kaynak_dil=en
   dubla transkript video.mp4 --bicim srt                       # transcript only
   dubla yaziya-dok video.mp4 --motor faster-whisper --dil auto -o out\transcript.json
   ```
5. Model and precision (faster-whisper / whisperx only): `transkripsiyon.model` (`large-v3-turbo` default,
   `distil-*` English only) and `transkripsiyon.hesap_tipi=auto` (int8 or float32 on older GPUs; fp16 is refused there).

## Common errors

| Symptom | Fix |
|---|---|
| `CUDA out of memory` in WhisperX | close other GPU programs; the job retries once in int8; [low_vram.md](../../../docs/engineering/low_vram.md) |
| English-only engine with another language | settings error by design; pick a multilingual engine |
| CrisperWhisper on a CPU machine | error by design (no CPU path) |
| `SPEECHMATICS_API_KEY_1 .env dosyasinda bulunamadi` / `ELEVENLABS_API_KEY ...` | copy `.env.example` to `.env`, fill your own key |
| Manual engine shows `yok` | follow its `docs/motorlar/<engine>.md` install section |

## Related

[docs/tarifler/dil_tespiti.md](../../../docs/tarifler/dil_tespiti.md) · [docs/diller.md](../../../docs/diller.md) ·
[docs/donanim.md](../../../docs/donanim.md) · [docs/engineering/transcription.md](../../../docs/engineering/transcription.md) ·
[docs/engineering/crisperwhisper_turbo_ct2.md](../../../docs/engineering/crisperwhisper_turbo_ct2.md) ·
[docs/engineering/word_alignment.md](../../../docs/engineering/word_alignment.md) · engine pages:
[faster-whisper](../../../docs/motorlar/faster-whisper.md), [whisperx](../../../docs/motorlar/whisperx.md),
[crisperwhisper_turbo_ct2](../../../docs/motorlar/crisperwhisper_turbo_ct2.md),
[moonshine_medium_streaming_en](../../../docs/motorlar/moonshine_medium_streaming_en.md),
[whisper_cpp_cpu_align](../../../docs/motorlar/whisper_cpp_cpu_align.md),
[parakeet_cpu_align](../../../docs/motorlar/parakeet_cpu_align.md), [speechmatics](../../../docs/motorlar/speechmatics.md),
[elevenlabs_scribe_v2](../../../docs/motorlar/elevenlabs_scribe_v2.md), [youtube_translate](../../../docs/motorlar/youtube_translate.md)

## Türkçe özet

Motor `transkripsiyon.motor` ile seçilir; `auto` CrisperWhisper Turbo kuruluysa onu, değilse faster-whisper'ı alır.
Ticari olmayan kullanım + NVIDIA GPU → CrisperWhisper Turbo (en iyi kelime zamanı, lisans önce söylenir); ticari ya
da WSL2 yok → faster-whisper / whisperx; İngilizce + yalnız işlemci → parakeet / whisper.cpp; anahtarınız varsa bulut.
Dil: bilinen tek dil → `kaynak_dil=<kod>`, bilinmiyor → `auto`, karışık konuşma → CrisperWhisper +
`continuous_stream`, bölüm bölüm farklı dil → Medium + `per_window`. Her motorun sayfası `docs/motorlar/<ad>.md`.
