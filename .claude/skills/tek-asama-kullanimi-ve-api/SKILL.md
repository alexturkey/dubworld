---
name: tek-asama-kullanimi-ve-api
description: "Run a single pipeline stage (download, extract audio, separate, transcribe, align, translate, speak, subtitles, mux) from the CLI or the Python API, and build your own tool from the stages (subtitle extractor, podcast translator, text reader, batch transcriber, karaoke subtitles). Use when the user says 'only transcribe', 'only translate this JSON', 'read this text aloud', 'burn subtitles', 'karaoke subtitles', 'Python API', 'use it as a library', 'tek aşama', 'kendi aracımı yapayım', 'batch transcribe a folder'."
---

# Single stages and the Python API / Tek aşama ve Python API

Türkçe özet en altta. / Turkish summary at the end.

## When to use

The user needs one stage, a different order of stages, or wants to call the pipeline from Python. For the full
default flow use `dublaj-onerilen-akis`.

## Stage map

| Stage | CLI | Python (`dublaj_hatti.api`) | Output |
|---|---|---|---|
| download | `dubla indir URL -o dir\` | `indir(url, dir)` | video (needs `youtube` or `galeri` extra) |
| audio | `dubla ses-cikar v.mp4 -o a.wav` | `ses_cikar(v, wav, ornekleme=16000, kanal=1)` | WAV |
| separation | `dubla ayir v.mp4 -o dir\` | `ayir(v, dir)` | `vocals.wav`, `background.wav` (Demucs) |
| speech-to-text | `dubla yaziya-dok v.mp4 -o t.json` | `yaziya_dok(v, json, motor=None, dil=None)` | `transcript.json` + `.srt` |
| word alignment | `dubla hizala a.wav t.txt --dil en -o t.json` | `hizala(wav, txt, json, dil="en")` | transcript with `words` |
| translation | `dubla cevir t.json --hedef-dil tr --arka-uc yerel -o tr.json` | `cevir(json, out, hedef_dil="tr", arka_uc="yerel")` | `translation.json` |
| text to speech | `dubla seslendir IN --motor supertonic --ses F1 -o dir\` | `seslendir(in, dir, motor="supertonic", ses=None, dil="tr")` | `speech.wav` (+ `speech.json`) |
| subtitles | `dubla altyazi t.json --bicim srt --kip karaoke -o out.ass` | `altyazi(json, out, bicim=None, kip="segment")` | SRT / VTT / ASS |
| mux | `dubla birlestir v.mp4 --ses s.wav --altyazi s.srt -o o.mp4` | `birlestir(v, out, ses=.., altyazi=.., yak=False)` | MP4 (AI-dubbed tag on) |
| full flow | `dubla v.mp4` | `dubla(v, hedef_klasor=None, ayarlar=None)` | dubbed MP4 + all files |

`dubla <stage> --help` lists every option; every stage accepts `--ayar`, `--ayarlar` and `--json`.
File formats (`transcript@1`, `translation@1`, `speech@1`, WhisperX-compatible) and JSON Schemas:
[docs/mimari.md](../../../docs/mimari.md), `src/dublaj_hatti/semalar/`.

## Steps

1. Check the needed extras are installed (`dubla kontrol`; extras per stage in [docs/mimari.md](../../../docs/mimari.md)).
   The package core is standard library only; models load inside the stage that needs them.
2. Run the stage from the CLI, e.g. subtitles only:
   ```powershell
   dubla yaziya-dok talk.mp4 -o out\transcript.json
   dubla altyazi out\transcript.json --bicim vtt -o out\talk.vtt
   ```
3. Or call it from Python:
   ```python
   from dublaj_hatti import api

   with api.ayarlarla(ifadeler=["genel.cihaz=cpu"]):          # settings layer for every call in the block
       t = api.yaziya_dok("talk.mp4", "out/transcript.json", dil="en")
       tr = api.cevir(t, "out/translation.json", hedef_dil="tr", arka_uc="yerel")
       api.seslendir(tr, "out/speech", motor="supertonic", ses="F1")   # JSON input -> returns speech.json
       api.birlestir("talk.mp4", "out/dubbed.mp4", ses="out/speech/speech.wav")
   ```
   `seslendir` returns `speech.json` for a transcript / translation input (timed track `speech.wav` next to it) and
   the WAV itself for plain text.
   Errors: `AyarHatasi` (setting, CLI exit 2), `KaynakHatasi` (source), `BicimHatasi` (stage file does not match its
   schema), `AsamaHatasi` (stage failed). Outputs are written atomically; a failed stage keeps its scratch folder next
   to the output for diagnosis.
4. Start from a ready example (each has `--help` and a GPU-free test in `tests/test_ornekler.py`):
   - `examples/01_yalniz_altyazi/altyazi_cikar.py` — video → SRT + VTT
   - `examples/02_podcast_cevir/podcast_cevir.py` — audio → speech in another language
   - `examples/03_metni_oku/metni_oku.py` — read a text aloud
   - `examples/04_toplu_yaziya_dok/toplu_yaziya_dok.py` — transcribe a whole folder, resumable, summary CSV
   - `examples/05_karaoke_altyazi/karaoke.py` — word-by-word karaoke subtitles burned in
   ```powershell
   python examples/01_yalniz_altyazi/altyazi_cikar.py my_talk.mp4 --cikti out\
   ```
5. The API runs in the caller's process without the job store; use the CLI (`dubla ...`) when resume and history are
   needed.

## Common errors

| Symptom | Fix |
|---|---|
| `BicimHatasi` | the input JSON is not a stage file; produce it with the previous stage or match the schema in `semalar/` |
| `hizala` on a `.txt` without `--dil` | the language is required for plain text |
| `indir` says yt-dlp / gallery-dl missing | `kur.ps1 -Adim youtube` or `-Adim galeri`; only content you may use |
| `ayir` fails: Demucs missing | `kur.ps1 -Adim demucs` |
| No `AI-dubbed` tag wanted | `--ai-etiketi-yok` exists, but keeping the label is strongly recommended (ETHICS.md) |

## Related

[docs/mimari.md](../../../docs/mimari.md) · [examples/README.md](../../../examples/README.md) ·
[src/dublaj_hatti/api.py](../../../src/dublaj_hatti/api.py) · [src/dublaj_hatti/bicimler.py](../../../src/dublaj_hatti/bicimler.py) ·
[docs/engineering/word_alignment.md](../../../docs/engineering/word_alignment.md)

## Türkçe özet

Her aşama tek başına çalışır: `dubla indir | ses-cikar | ayir | yaziya-dok | hizala | cevir | seslendir | altyazi |
birlestir` ve Python'da aynı adlı `dublaj_hatti.api` işlevleri (`api.ayarlarla(...)` ile ayar katmanı). Dosya
biçimleri ve şemalar `docs/mimari.md` ve `src/dublaj_hatti/semalar/`. `examples/` altında 5 hazır araç (yalnız
altyazı, podcast çevirisi, metin okuma, toplu transkript, karaoke altyazı). API iş deposu tutmaz; devam ve geçmiş
gerekiyorsa CLI kullanılır.
