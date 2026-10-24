---
name: gelismis-ayarlar-ve-kombinasyonlar
description: "Change any pipeline setting (CLI --ayar, a .toml file, or the Advanced tab), build a custom recipe, and understand which choices work together and which are rejected. Use when the user says 'change the voice', 'keep background music', 'word-by-word subtitles', 'smaller file', 'better quality', 'mixed-language video', 'ayar', 'gelişmiş', 'kombinasyon', 'neden hata verdi', 'which settings work together', or a run stops with 'ayar hatası'."
---

# Advanced settings and combinations / Gelişmiş ayarlar ve kombinasyonlar

Türkçe özet en altta. / Turkish summary at the end.

## When to use

The recommended flow is not enough: the user wants a different engine, voice, subtitle style, quality, or a run
stopped with `ayar hatası` (setting error) / `uyarı` (warning).

## How settings work

- One source of truth: `src/dublaj_hatti/varsayilan.toml` (52 keys, each commented). Do not edit it.
- Layers (top wins): `--ayar section.key=value` → `--ayarlar file.toml` → `ayarlar/kullanici.toml` (git-ignored) →
  `DUBLAJ_AYARLAR` file → defaults. The desktop and web **Gelişmiş** (Advanced) tab shows the same keys.
- Validation: `yapilandirma.uyumluluk_denetle()` checks the combination when settings load. **Error** = the job does
  not start and says what to change. **Warning** = logged, the job runs, the choice has no effect.

## Steps

1. Show what is active now:
   ```powershell
   dubla ayarlar            # merged settings; warnings on stderr as "uyarı:"
   dubla ayarlar --json
   ```
2. Pick the change from the recipe table in [docs/tarifler/kombinasyonlar.md](../../../docs/tarifler/kombinasyonlar.md)
   (Turkish page; the keys are the same in every language). Frequent ones:

   | Goal | Setting |
   |---|---|
   | Keep music / effects under the dub | `ses_temizligi.kip=preserve_background` (needs Demucs: `kur.ps1 -Adim demucs`) |
   | Keep background only when present | `ses_temizligi.kip=auto_background` |
   | One fixed voice | `ses.konusmaci_cinsiyetine_gore_ses=false`, `ses.supertonic_ses=M2` |
   | Pin a voice to a speaker | `--ayar ses.konusmaci_sesleri.SPEAKER_00=M2` (names in the job's `speaker_voice_map.json`) |
   | Gender per sentence, no speaker separation | `ses.cinsiyet_kipi=segment`, `ses.kadin_ses=F2`, `ses.erkek_ses=M1` |
   | Word-by-word / rolling / no subtitles | `altyazi.mod=word` / `rollup` / `none` |
   | Smaller file | `video.politika=max_mb`, `video.max_mb=179` (1 MB = 1 000 000 bytes) |
   | Better picture | `video.cq=23` (lower = better, larger) |
   | Faster / slower speech | `ses.hiz` (0.5–2.0, same for every voice) |
   | Better fit to the original timing | `ses.akis=repair_3_light` (LLM backends only; more calls) |
   | Mixed-language speech | `transkripsiyon.motor=crisperwhisper_turbo_ct2`, `transkripsiyon.crisper_dil_tespiti=continuous_stream` |
   | Whole text as one block | `genel.dublaj_kipi=full_text` (Codex / Claude Code + Supertonic or EMA Lightning) |
   | Crop black bars | `video.akilli_kare=true` (`kur.ps1 -Adim akilli-kare`) |
3. Apply once on the command line, or save a recipe:
   ```powershell
   dubla video.mp4 --ayar ses_temizligi.kip=preserve_background --ayar altyazi.mod=word
   dubla video.mp4 --ayarlar my_recipe.toml       # only the changed keys, same [section] names
   ```
   Permanent: put the keys into `ayarlar/kullanici.toml`.
4. If the job already ran, change a setting and resume from the first stage it affects:
   `dubla devam <N> --ayar altyazi.mod=word` (skill `devam-ve-sorunlu-isler`).

## Rejected combinations (most frequent)

| Choice | With | Result |
|---|---|---|
| `ceviri.arka_uc=yerel` | target ≠ `tr` or source ≠ `en`/`auto` | error: Opus-MT is en→tr only |
| `ses.motor=supertonic` | `genel.hedef_dil` outside its 31 languages (e.g. `zh`) | error: use `voxcpm2` |
| `ses.motor=voxcpm2` | `genel.cihaz=cpu` | error: NVIDIA GPU needed |
| `genel.dublaj_kipi=full_text` | `ses.motor=voxcpm2` or a non-CLI backend | error |
| CrisperWhisper | CPU / no CUDA | error |
| English-only STT (moonshine, whisper.cpp, parakeet) | non-English `kaynak_dil` | error |
| `ses_temizligi.kip=clean`/`preserve_background` | Demucs missing | error at start |
| `video.politika=max_mb` | `video.max_mb=0` | error |

The full table (21 rules) and the tuning guide: [docs/tarifler/kombinasyonlar.md](../../../docs/tarifler/kombinasyonlar.md).
Language rules: [docs/diller.md](../../../docs/diller.md), [docs/tarifler/dil_tespiti.md](../../../docs/tarifler/dil_tespiti.md).

## Common errors

| Symptom | Fix |
|---|---|
| `ayar hatası: bilinmeyen ayar: <key>` | typo; list valid keys with `dubla ayarlar` |
| `... dilini okuyamaz` | target language not supported by the chosen TTS; see `docs/diller.md` |
| A setting "does nothing" | check `dubla ayarlar` stderr for `uyarı:` (ineffective in this combination) |
| Quotes lost in PowerShell | quote the whole pair: `--ayar "ses.konusmaci_sesleri=SPEAKER_00:M2, SPEAKER_01:F1"` |

## Related

[docs/tarifler/kombinasyonlar.md](../../../docs/tarifler/kombinasyonlar.md) ·
[src/dublaj_hatti/varsayilan.toml](../../../src/dublaj_hatti/varsayilan.toml) · [docs/donanim.md](../../../docs/donanim.md) ·
[docs/sesler.md](../../../docs/sesler.md) · [docs/engineering/tts_timing_and_mix.md](../../../docs/engineering/tts_timing_and_mix.md) ·
[docs/engineering/video_subtitles_and_resume.md](../../../docs/engineering/video_subtitles_and_resume.md)

## Türkçe özet

Bütün ayarlar `src/dublaj_hatti/varsayilan.toml`'da (değiştirilmez). Değiştirme: `--ayar bolum.anahtar=deger`,
`--ayarlar dosya.toml`, kalıcı `ayarlar/kullanici.toml` ya da arayüzde **Gelişmiş** sekmesi. `dubla ayarlar` geçerli
hâli ve uyarıları gösterir. Uyumsuz seçim yüklenirken açık hata verir (yerel çeviri yalnız en→tr, VoxCPM2 GPU ister,
Supertonic 31 dil, Demucs gerekiyorsa kurulmalı). Hazır tarifler ve 21 kuralın tamamı:
`docs/tarifler/kombinasyonlar.md`. Biten işte ayar değiştirip etkilediği aşamadan sürdürmek: `dubla devam <no> --ayar ...`.
