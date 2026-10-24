# Bolum 50: Seslendirme

Bu bolum seslendirme adiminin kanonik catisidir. Her motor kendi kutusunda
durur; ortak yurutme ve trafik yonlendirme ise `tts_orkestratoru/` altindadir.
Motor listesinin ve lisanslarinin tek kaynagi `src/dublaj_hatti/kayit.py`'dir.

```text
bolum_50_seslendirme/
  tts_orkestratoru/        motor secimi, motor hazirlik hook'u, olcum, miks, real TTS aday secimi
  altyazili_dublaj/        segment TTS motorlari icin merkezi timing sozlesmesi ve ortak ASS duzeni
  supertonic_tts/          Supertonic ONNX motoru, API cephe kapisi, ic yurutme, paralel runtime, akis modlari
  voxcpm2_tts/             VoxCPM2 kardes repo ortaminda tek oturumluk alt surec
  ema_lightning_tts/       EMA Lightning (yalniz Turkce): GPU torch ya da yerelde disa aktarilan islemci ONNX
  xtts_tts/                XTTS v2 motoru (ayri ortam, CPML onayi), referans sesler ve kendi sure uyum mantigi
  rvc_ses_donusturme/      TTS sonrasi istege bagli RVC ses donusturme (sesin sahibinin rizasi)
  candidate_alignment/     gercek TTS aday sesleri icin forced alignment
  final_dub_alignment/     final dublaj sesi icin forced alignment
  metinden_seslendirme.py  metinden seslendirme akisi
```

## Sahiplik Kurali

- `tts_orkestratoru/` trafik polisidir; motorlara yonlendirir ve finalde
  kullanilacak sesi olcer.
- `altyazili_dublaj/` dogrulanmis forced-alignment zamanini sozlesmeye baglar
  ve segment TTS motorlari icin tek ortak ASS uygulamasini sahiplenir. Motor
  kutularinda yalniz ince adaptor bulunur.
- `supertonic_tts/` kendi API cephe kapisini, model, seed, speed, paralel
  runtime, flow mode ve debug kararlarini kendi icinde tutar.
- `xtts_tts/` kendi referans WAV, model, metin parcala ve hiz normalize
  kararlarini kendi icinde tutar.
- Motorlarin uretilen sesinden kelime zamani, konusma basi/sonu veya karar
  suresi RMS, boundary ya da internal attention ile tahmin edilmez. Bu
  bilgiler gerekli oldugunda forced alignment sonucundan gelir.

Bir motor kutusu silinirse sadece o motor zarar gormelidir. Baska motorun
promptu, ayari, runtime verisi veya ozel optimizasyonu bu kutunun disindan
gelmemelidir.

## Dis Giris

Uygulama disindan seslendirme icin kanonik giris:

```python
from dublaj_hatti.bolum_50_seslendirme.tts_orkestratoru.service import build_dubbed_audio
```
