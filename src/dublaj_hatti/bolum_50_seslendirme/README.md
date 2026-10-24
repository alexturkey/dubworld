# Bolum 50: Seslendirme

Bu bolum seslendirme adiminin kanonik catisidir. Her motor kendi kutusunda
durur; ortak yurutme ve trafik yonlendirme ise `tts_orkestratoru/` altindadir.
Bolum ve kutu listesinin sahibi `docs/arac_katalogu.md` belgesidir.

```text
bolum_50_seslendirme/
  tts_orkestratoru/        motor secimi, fallback, motor hazirlik hook'u, olcum, miks, real TTS aday secimi
  altyazili_dublaj/        Edge, Supertonic ve XTTS icin merkezi timing sozlesmesi ve ortak ASS duzeni
  edge_tts_motoru/         Edge TTS motoru, fonetik learner ve RVC ses donusturme
  supertonic_tts/          Supertonic ONNX motoru, API cephe kapisi, ic yurutme, paralel runtime, akis modlari
  xtts/                    XTTS v2 motoru, referans sesler ve kendi sure uyum mantigi
  candidate_alignment/     gercek TTS aday sesleri icin forced alignment
  final_dub_alignment/     final dublaj sesi icin forced alignment
  dub_timing_profiler/     Edge TTS timing profiler kutusu
  metinden_seslendirme.py  metinden seslendirme akisi
```

## Sahiplik Kurali

- `tts_orkestratoru/` trafik polisidir; motorlara yonlendirir ve finalde
  kullanilacak sesi olcer.
- `altyazili_dublaj/` dogrulanmis forced-alignment zamanini sozlesmeye baglar
  ve Edge, Supertonic, XTTS icin tek ortak ASS uygulamasini sahiplenir. Motor
  kutularinda yalniz ince adaptor bulunur.
- `edge_tts_motoru/` sadece Edge davranisindan sorumludur. Fonetik learner bu
  kutunun icindedir ve Supertonic veya XTTS kutularina ait degildir.
- `supertonic_tts/` kendi API cephe kapisini, model, seed, speed, paralel
  runtime, flow mode ve debug kararlarini kendi icinde tutar.
- `xtts/` kendi referans WAV, model, metin parcala ve hiz normalize
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
from bolum_50_seslendirme.tts_orkestratoru.service import build_dubbed_audio
```
