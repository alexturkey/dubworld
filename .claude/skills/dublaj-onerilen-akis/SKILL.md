---
name: dublaj-onerilen-akis
description: "Dub a local video into Turkish (or another target language) with the recommended flow: one command, sensible defaults, AI-dubbed label. Use when the user says 'dub this video', 'Turkish dubbing', 'dublajla', 'videoyu Türkçe yap', 'translate and voice this video', 'make a dubbed copy', 'only subtitles', 'yalnız altyazı', or gives a video file and wants the default result."
---

# Recommended dubbing flow / Önerilen akış

Türkçe özet en altta. / Turkish summary at the end.

## When to use

The user has a video (or audio) they own or may use and wants the dubbed result without tuning. For tuning use
`gelismis-ayarlar-ve-kombinasyonlar`; for a single stage use `tek-asama-kullanimi-ve-api`.

## What the recommended flow does

Defaults live in one commented file, `src/dublaj_hatti/varsayilan.toml` (never edit it; override instead):

| Stage | Default | Setting |
|---|---|---|
| Source audio | used as is | `ses_temizligi.kip = "original"` |
| Speech-to-text | `auto`: CrisperWhisper Turbo if installed, else faster-whisper large-v3-turbo + CTC word times | `transkripsiyon.motor` |
| Source language | detected automatically | `transkripsiyon.kaynak_dil = "auto"` |
| Translation | `auto`: Codex CLI → Claude Code CLI → local Opus-MT (en→tr only) | `ceviri.arka_uc` |
| Speech | Supertonic 3 (CPU), natural blocks flow, rate 1.2, atempo on | `ses.motor`, `ses.akis`, `ses.hiz`, `ses.atempo` |
| Voices | speaker separation + gender → female F1..F5 / male M1..M5 | `ses.konusmaci_cinsiyetine_gore_ses` |
| Subtitles | sentence subtitles burned in | `altyazi.mod = "segment"` |
| Video | constant quality 26, encoder chosen automatically (NVENC if it works, else x264) | `video.cq` |
| Label | `AI-dubbed` metadata tag in the output | `video.yapay_zeka_etiketi` (keep on) |

## Steps

1. **Check consent and rights.** Only content the user owns or may use; no imitation of real people
   ([ETHICS.md](../../../ETHICS.md)). Links (`https://...`) work only with the `youtube` / `galeri` extras.
2. **Check the install:** `dubla kontrol`. If `stt`/`tts` show `yok`, run the `kurulum-ve-donanim` skill first.
3. **Run:**
   ```powershell
   dubla video.mp4                               # same as: dubla dubla video.mp4
   dubla video.mp4 --cikti out\                  # choose the output folder
   dubla video.mp4 --ayar genel.cihaz=cpu        # force CPU
   dubla video.mp4 --ayar ceviri.arka_uc=yerel   # fully offline translation (English source only)
   ```
   From a fresh shell without activating the venv: `.venv\Scripts\dubla.exe video.mp4`.
4. **License prompt:** if the chosen engines include a non-commercial or conditional one (e.g. CrisperWhisper),
   the first run prints a bilingual notice and asks for acceptance. Non-interactive: add `--lisans-onay`
   (or `DUBLAJ_LISANS_ONAY=1`). Acceptance is remembered in `ayarlar/lisans_onaylari.json`. Ask the user; never
   accept on their behalf.
5. **Watch progress:** the CLI prints `iş #N`; `--olaylar-json` prints one JSON line per stage event (the GUI and web
   UI read this). Exit codes: `0` done, `1` job failed, `2` usage / setting error, `75` GPU busy (job deferred),
   `130` stopped.
6. **Result:** the job folder under the output root (default `cikti/`) holds the dubbed MP4 (`dubbed_<lang>.mp4`),
   transcript, translation (`translated_segments_<lang>.txt`) and every intermediate file. The final lines of the CLI
   print the paths.
7. **If it fails or is stopped:** `dubla sorunlu`, then `dubla devam <N>` (skill `devam-ve-sorunlu-isler`).

## Variants

```powershell
dubla transkript video.mp4 --bicim srt       # subtitles / text only: srt | plain | timestamped | paragraph
dubla video.mp4 --ayar genel.hedef_dil=de    # other target language: needs an LLM translation backend
dubla video.mp4 --ayar ses.motor=voxcpm2     # Turkish voice design engine (NVIDIA GPU, separate install)
```

Interface: `dubla-gui` (own window) or `dubla-web` (browser; both 127.0.0.1 only) → **Dub** (Dublaj) tab: drop
the video, pick the language, one click; the result plays in place (Original / Dubbed, subtitles).

## Common errors

| Symptom | Fix |
|---|---|
| `hata: ... yerel ... yalnız İngilizce` | local Opus-MT translates en→tr only; install/log in to Codex or Claude Code, or set an API backend (`ceviri-arka-uclari`) |
| `lisans onayı yok` (exit 2) | read the notice, then rerun with `--lisans-onay` if the user accepts |
| `meşgul, sıra bekleniyor` | another GPU job runs; it waits (machine-wide lock), or `dubla isler --kuyruk` |
| Translation step fails with Codex/Claude | not logged in: run `codex login` / open `claude` once; see `ceviri-arka-uclari` |
| Output too large | `--ayar video.politika=max_mb --ayar video.max_mb=179` |

## Related

[src/dublaj_hatti/varsayilan.toml](../../../src/dublaj_hatti/varsayilan.toml) ·
[docs/tarifler/kombinasyonlar.md](../../../docs/tarifler/kombinasyonlar.md) · [docs/mimari.md](../../../docs/mimari.md) ·
[docs/diller.md](../../../docs/diller.md) · [docs/sesler.md](../../../docs/sesler.md) ·
[docs/engineering/README.md](../../../docs/engineering/README.md) · [ETHICS.md](../../../ETHICS.md)

## Türkçe özet

`dubla video.mp4` önerilen akışı çalıştırır: kaynak ses olduğu gibi, STT `auto` (CrisperWhisper kuruluysa o, yoksa
faster-whisper + CTC), çeviri `auto` (Codex → Claude Code → yerel Opus-MT), Supertonic sesi, konuşmacı cinsiyetine göre
ses, cümle altyazısı, cq 26, `AI-dubbed` etiketi. Yalnız hakkınız olan içerik. Ticari olmayan motor seçiliyse ilk
çalıştırmada lisans onayı istenir (`--lisans-onay`, kullanıcıya sorulur). Çıktı `cikti/` altındaki iş klasöründe;
hata/kesilmede `dubla sorunlu` ve `dubla devam <no>`. Yalnız altyazı: `dubla transkript video.mp4 --bicim srt`.
