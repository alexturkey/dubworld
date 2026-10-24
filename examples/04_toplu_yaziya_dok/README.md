# 04 · Batch transcription of a folder

Every video / audio file in a folder -> `<name>.transcript.json` + `<name>.srt`, plus `ozet.csv`.
Finished files are skipped, so an interrupted run continues where it stopped; a failing file is recorded and the
batch goes on.

```bash
python examples/04_toplu_yaziya_dok/toplu_yaziya_dok.py videos/ --cikti transcripts/ --dil en
```

Exit code 1 if any file failed (see the `error` column). Smoke test: `pytest tests/test_ornekler.py -k toplu`.

**TR:** Klasördeki bütün videoları yazıya döker; yarıda kalırsa kaldığı yerden sürer.
