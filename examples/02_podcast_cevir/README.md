# 02 · Podcast / audio translator

Audio in, translated speech out. Each segment is spoken at its original time, so the result lines up with the source.

```bash
python examples/02_podcast_cevir/podcast_cevir.py episode.mp3 --cikti out/ --hedef-dil tr
# edit out/translation.json by hand if you like, then only re-speak it:
python examples/02_podcast_cevir/podcast_cevir.py episode.mp3 --cikti out/ --ses-only --ses-adi M2
```

Output: `transcript.json`, `translation.json`, `subtitles.tr.srt`, `speech/speech.wav` (timed track),
`speech/speech.json` + `speech/parcalar/*.wav` (one file per segment).
The offline `yerel` backend translates English -> Turkish only; other pairs need an LLM backend
([docs/tarifler/kombinasyonlar.md](../../docs/tarifler/kombinasyonlar.md)). Smoke test: `pytest tests/test_ornekler.py -k podcast`.

**TR:** Podcast / ses dosyası çevirici; ara dosyalar elle düzeltilip yalnız seslendirme yeniden yapılabilir.
