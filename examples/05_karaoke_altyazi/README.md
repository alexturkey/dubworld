# 05 · Karaoke subtitles

Each word lights up while it is spoken (ASS `\k` karaoke tags built from the CTC word times), burned into the
video with ffmpeg.

```bash
python examples/05_karaoke_altyazi/karaoke.py clip.mp4 --cikti out/ --dil en
python examples/05_karaoke_altyazi/karaoke.py clip.mp4 --transkript clip.transcript.json --yalniz-ass
```

Colours and font: edit the `Style:` line of the `.ass` file. WebVTT karaoke instead:
`dubla altyazi clip.transcript.json --bicim vtt --kip karaoke`.
Smoke test: `pytest tests/test_ornekler.py -k karaoke` (builds a real `.ass` from synthetic word times; ffmpeg is
not called).

**TR:** Kelime kelime yanan karaoke altyazı; video ffmpeg ile yeniden kodlanır.
