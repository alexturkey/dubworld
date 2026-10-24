# 03 · Read a text aloud

Text or a `.txt` file in, `speech.wav` out. Pick the engine and the voice.

```bash
python examples/03_metni_oku/metni_oku.py "Merhaba, bu bir deneme." --ses M1
python examples/03_metni_oku/metni_oku.py chapter.txt --motor voxcpm2 --ses hazir/haber_spikeri
```

CLI equivalent: `dubla seslendir chapter.txt -o out/ --motor supertonic --ses F2`.
Supertonic runs on CPU or GPU. VoxCPM2 needs an NVIDIA GPU and its own install (`scripts/kur.ps1 -Adim voxcpm2`;
see "Family" in the main README). Only use voices you have the right to use ([ETHICS.md](../../ETHICS.md)).
Smoke test: `pytest tests/test_ornekler.py -k metni_oku`.

**TR:** Metni seçilen TTS motoru ve sesle okutur.
