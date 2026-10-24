# Build your own: examples

Each stage of the pipeline is a building block (`dublaj_hatti.api` in Python, `dubla <stage>` on the command line).
These small scripts show how to combine the blocks into different tools. Every script has a `main(argv)` function,
a `--help`, and a GPU-free smoke test in `tests/test_ornekler.py` (the model stages are replaced by fakes there).

| Example | What it builds | Stages used | Needs |
|---|---|---|---|
| [01_yalniz_altyazi](01_yalniz_altyazi/) | subtitle extractor: video -> SRT + VTT | yaziya_dok, altyazi | speech-to-text models |
| [02_podcast_cevir](02_podcast_cevir/) | podcast / audio translator: audio -> speech in another language | yaziya_dok, cevir, seslendir | STT + translation + TTS |
| [03_metni_oku](03_metni_oku/) | read a text aloud with the TTS engine and voice you pick | seslendir | Supertonic or VoxCPM2 |
| [04_toplu_yaziya_dok](04_toplu_yaziya_dok/) | transcribe every file in a folder (resumable) + summary CSV | yaziya_dok | speech-to-text models |
| [05_karaoke_altyazi](05_karaoke_altyazi/) | word-by-word karaoke subtitles burned into the video | yaziya_dok, altyazi, birlestir | STT models + ffmpeg |

Run from the repository root after installing (`scripts/kur.ps1`, or `pip install -e ".[onerilen,cpu]"`):

```bash
python examples/01_yalniz_altyazi/altyazi_cikar.py my_talk.mp4 --cikti out/
```

Stage file formats (transcript.json, translation.json, speech.json) and the stage map: [docs/mimari.md](../docs/mimari.md).
Use only material you own or may use: [ETHICS.md](../ETHICS.md).

---

**TR:** Her aşama bir yapı taşıdır. Bu betikler parçaları birleştirip başka araçlar kurmayı gösterir; her birinin
`--help`'i ve GPU'suz duman testi (`tests/test_ornekler.py`) var.
