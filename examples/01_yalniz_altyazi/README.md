# 01 · Subtitle extractor

Video or audio in, subtitles out: `transcript.json` (segments + word times), `.srt` and `.vtt`. No translation, no TTS.

```bash
python examples/01_yalniz_altyazi/altyazi_cikar.py talk.mp4 --cikti out/ --dil en
```

Same with the CLI: `dubla yaziya-dok talk.mp4 -o out/talk.json`, then `dubla altyazi out/talk.json --bicim vtt`.

Building blocks: `api.yaziya_dok` (speech-to-text + CTC word timing) and `api.altyazi` (pure Python writer: SRT, VTT, ASS).
Runs on CPU (faster-whisper) or an NVIDIA GPU. Smoke test: `pytest tests/test_ornekler.py -k altyazi`.

**TR:** Yalnız altyazı çıkarıcı: dublaj yok, çeviri yok.
