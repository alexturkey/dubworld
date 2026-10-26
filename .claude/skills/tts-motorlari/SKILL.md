---
name: tts-motorlari
description: "Choose the text-to-speech engine, target language and voices (Supertonic 3, VoxCPM2, XTTS v2, optional RVC voice conversion), assign voices per speaker, and handle the license and consent gates. Use when the user says 'change the voice', 'male/female voice', 'which languages can it speak', 'VoxCPM2', 'XTTS', 'RVC', 'my own voice', 'ses', 'seslendirme motoru', 'hedef dil', 'konuşmacı başına ses', or a run says 'dilini okuyamaz'."
---

# Text-to-speech engines, languages and voices / TTS motorları, diller ve sesler

Türkçe özet en altta. / Turkish summary at the end.

## When to use

Changing `ses.motor`, the target language (`genel.hedef_dil`), a voice, per-speaker voices, or enabling XTTS / RVC.

## Engines

| `ses.motor` | Device | Target languages | License | Install |
|---|---|---|---|---|
| `auto` (default) | VoxCPM2 if installed + NVIDIA GPU, else Supertonic | – | – | – |
| `supertonic` | CPU (fast) | 31 (no `zh`) | BigScience Open RAIL-M (use restrictions, conditional) | base install |
| `voxcpm2` | NVIDIA GPU (~3 GB) | tested: tr en fr de es ru zh ja; others with a warning | Apache-2.0 | `kur.ps1 -Adim voxcpm2` |
| `xtts` | GPU or CPU (slow) | 17 | **weights non-commercial (CPML)** | `kur.ps1 -Adim tts-xtts -TicariOlmayanKabul` |
| RVC (post-processing, not a TTS) | GPU or CPU | any | your own model; code MIT | manual, `.env` `DUBLAJ_RVC_KOK` |

Language matrix: [docs/diller.md](../../../docs/diller.md). Voices: [docs/sesler.md](../../../docs/sesler.md).
The target-language list in the interfaces is filtered by the selected engine; an unsupported language is a settings
error, never a silent switch.

## Steps

1. **Ethics first.** Only synthetic voices ship with the project. XTTS reference audio and RVC models must be the
   user's own voice or used with the owner's explicit consent; never imitate a real or famous person
   ([ETHICS.md](../../../ETHICS.md)). Ask the user to confirm this before enabling XTTS or RVC.
2. **Pick the engine:**
   - default (`auto`) → VoxCPM2 when installed and an NVIDIA GPU works, otherwise `supertonic`; CPU / most languages → `supertonic`;
   - Turkish voice design quality, NVIDIA GPU → `voxcpm2` (`ses.voxcpm2_ses = "hazir/haber_spikeri"` or another
     ready voice from `docs/sesler.md`, or a voice designed with the sister VoxCPM2 repository);
   - a voice from a short reference recording, non-commercial use only → `xtts`.
3. **Pick voices:**
   ```powershell
   dubla video.mp4 --ayar ses.konusmaci_cinsiyetine_gore_ses=false --ayar ses.supertonic_ses=M3   # one voice
   dubla video.mp4 --ayar ses.konusmaci_sesleri.SPEAKER_01=F2                                    # pin one speaker
   dubla video.mp4 --ayar ses.cinsiyet_kipi=segment --ayar ses.kadin_ses=F2 --ayar ses.erkek_ses=M1
   dubla video.mp4 --ayar ses.motor=voxcpm2 --ayar ses.voxcpm2_ses=hazir/belgesel_hanim
   ```
   Speaker names (`SPEAKER_00`, ...) are in the job folder's `speaker_voice_map.json`. With `voxcpm2`, gender
   prediction is skipped; use `ses.konusmaci_sesleri`.
4. **Other target language:** `--ayar genel.hedef_dil=de` plus an LLM translation backend (local Opus-MT is en→tr only).
5. **XTTS v2** (only after the user accepted the CPML non-commercial license):
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim tts-xtts -TicariOlmayanKabul
   dubla video.mp4 --ayar ses.motor=xtts --ayar ses.xtts_referans_ses=my_voice.wav
   ```
   License state: `python -m dublaj_hatti.bolum_50_seslendirme.xtts_tts durum`. Page: [xtts](../../../docs/motorlar/xtts.md).
6. **RVC** (own model, consent flag mandatory): install the official RVC WebUI yourself, set `DUBLAJ_RVC_KOK` in
   `.env`, then `--ayar ses.rvc_model=model.pth --ayar ses.rvc_riza_onayi=true`. Page: [rvc](../../../docs/motorlar/rvc.md).
7. **Read a text without a video:** `dubla seslendir "Merhaba dünya." --motor supertonic --ses F1 --dil tr -o out\`.
8. **Licenses at run time:** non-commercial / conditional engines show a bilingual notice on first use and need an
   explicit acceptance (`--lisans-onay`, GUI dialog, web confirm). Do not accept for the user.

## Common errors

| Symptom | Fix |
|---|---|
| `Supertonic '<x>' dilini okuyamaz` | choose `voxcpm2` or a supported language |
| VoxCPM2 + `genel.cihaz=cpu` error | VoxCPM2 needs an NVIDIA GPU (CPU path disabled: far slower than real time) |
| `XTTS v2 kurulu değil` / CPML error | step 5; accept the license with the `onay` command |
| `RVC rıza onayı yok` | consent flag; only after the owner's explicit permission |
| Dub longer than the original | keep `ses.atempo=true`; try `ses.akis=repair_3_light` with an LLM backend |
| Unknown Supertonic voice name | voices are `F1`..`F5`, `M1`..`M5` |

## Related

[docs/sesler.md](../../../docs/sesler.md) · [docs/diller.md](../../../docs/diller.md) ·
[docs/engineering/tts_timing_and_mix.md](../../../docs/engineering/tts_timing_and_mix.md) ·
[docs/engineering/speakers_and_segments.md](../../../docs/engineering/speakers_and_segments.md) · engine pages:
[supertonic](../../../docs/motorlar/supertonic.md), [voxcpm2](../../../docs/motorlar/voxcpm2.md),
[xtts](../../../docs/motorlar/xtts.md), [rvc](../../../docs/motorlar/rvc.md),
[segment_cinsiyet_kipi](../../../docs/motorlar/segment_cinsiyet_kipi.md),
[konusmaci_ayrimi](../../../docs/motorlar/konusmaci_ayrimi.md),
[cinsiyet_siniflandirici](../../../docs/motorlar/cinsiyet_siniflandirici.md) · [THIRD_PARTY.md](../../../THIRD_PARTY.md) ·
[ETHICS.md](../../../ETHICS.md)

## Türkçe özet

Varsayılan `auto` (VoxCPM2 kuruluysa ve NVIDIA GPU çalışıyorsa o, değilse `supertonic`: işlemcide hızlı, 31 dil, zh yok); `voxcpm2` NVIDIA GPU ister (denenen 8 dil, hazır sesler
`docs/sesler.md`); `xtts` ticari olmayan CPML lisanslı, kurulumda `-TicariOlmayanKabul`; RVC kendi modelinizle ve
`ses.rvc_riza_onayi=true` olmadan çalışmaz. Referans ses/model yalnız kendi sesiniz ya da sahibinin açık izniyle;
gerçek kişi taklidi yok. Tek ses, konuşmacıya ses sabitleme ve segment cinsiyet kipi `--ayar` ile. Başka hedef dil
için LLM çeviri arka ucu gerekir. Lisans onayı kullanıcıya sorulur, ajan kendisi kabul etmez.
