# EMA Lightning (Turkish TTS, GPU or CPU ONNX) (`ema_lightning`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed and which path `auto` would take now)

**What it does:** Small, fast Turkish-only TTS engine (8.6 M parameters, about 34 MB of weights, 48 kHz mono, one voice). The same weights run on an NVIDIA GPU (PyTorch) or on the CPU (ONNX Runtime, files exported locally from the official weights). Works in both dubbing modes (`segment_sync` and `full_text`) and in `dubla seslendir`.

| | |
|---|---|
| License | Apache-2.0 (code and weights; commercial use included) |
| Commercial use | yes |
| Source | https://huggingface.co/canberkkkkkk/ema-lightning @ `e7c96f2fc0ba843cd0f86e02786655bb56f50df8` (weights) · PyPI `ema-lightning==1.1.0` (code, https://github.com/canberk7/ema-lightning) |
| Install | `scripts/kur.ps1 -Adim tts-ema` (package from a hashed lock, weights by pinned commit + SHA-256, ONNX export with an equality check) |
| Hardware | GPU (4 GB Pascal-class card): about 10× real time on three sentences after a 5 s start-up, under 0.2 GB of GPU memory (measured) · CPU (ONNX, 4 threads): about 11× real time after a 12 s start-up (measured) |
| Languages | Turkish only (`tr`); any other target language is a settings error |
| Voice | one synthetic voice (`ema`); designed from a text description in VoxCPM2, not a recording of a real person (model card) |
| Default | off |

**Settings**

- `ses.motor = "ema_lightning"`
- `ses.ema_cihaz`: `auto` (default: GPU when an NVIDIA GPU has at least 1 GB free, otherwise CPU ONNX; a GPU run that fails with a CUDA or memory error is repeated once on the CPU) · `cuda` (GPU only, error if there is none) · `cpu` (never touches the GPU)
- `ses.ema_hiz`: speaking speed 0.5–2.0 (1.0 = the model's natural pace). Not the same as `ses.hiz`, which sets the translation length target.
- `ses.ema_tohum`: seed (default 0). The same text with the same seed gives the same audio on the same path; another seed gives a different reading of the same voice.
- `dubla seslendir "metin" --motor ema_lightning [--cihaz auto|cuda|cpu] [--hiz 1.0]`

**Common errors**

- `genel.hedef_dil` other than `tr` → settings error ("dilini okuyamaz"); choose Supertonic or VoxCPM2 for other languages.
- `ses.ema_cihaz = cuda` together with `genel.cihaz = cpu` → settings error (contradiction).
- "kurulu değil" → run `scripts/kur.ps1 -Adim tts-ema`.
- `dubla kontrol` says the CPU path is torch, not ONNX → the export or its equality check failed; rerun the step. CPU still works, only slower for long texts.

**Related:** [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) · [donanim.md](../donanim.md) · [diller.md](../diller.md) · [ADR 0019](../adr/0019-ema-lightning-tts.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** one subprocess per job (`ema_lightning_tts/kosucu.py`) loads the model once, reads every segment and
  exits, so GPU memory is fully released for the next stage. The package's own engine does the work in three stages:
  text stage (letters → features and durations), sound stage (aligner + four sampling steps) and decoder (latents →
  48 kHz audio). Long text is cut by the package at sentence and clause marks, with its own pauses.
- **GPU and CPU paths run the same code.** Only the place where the three stages are computed changes: PyTorch on
  CUDA, or ONNX Runtime on the CPU. The text normalisation, chunking, frame timeline and seeded noise stay in the
  package's Python code.
- **Why ONNX files are exported locally:** the model publisher ships PyTorch weights only. Instead of downloading a
  third party's converted files, the install step exports the three stages from the same SHA-256-checked official
  weights on the user's machine and compares them with PyTorch on a sentence of a different length. If the largest
  difference exceeds 1e-3 the CPU path falls back to PyTorch.
- **Why it fits:** same result contract as Supertonic (segment WAVs, measured duration, the shared mixer and video
  retiming). In `full_text` mode each sentence is read separately and joined with 0.25 s silence (the package's own
  sentence pause), so the full-text alignment windows come from real per-sentence audio.
- **Responsible use:** the model card asks deployers to tell listeners that the voice is AI-generated; the pipeline's
  AI label (`video.yapay_zeka_etiketi`, on by default) does this for videos.

## Acceleration history and rationale

The engine was first used outside this repository on the reference machine (4 GB Pascal-class GPU, 4-core laptop CPU)
for short spoken answers; the settings below come from that history. Every figure is "seconds of audio per second
of compute". Records without a measurement say so.

| Step | Change | Why | Measured result | Status |
|---|---|---|---|---|
| 1 | PyTorch on CPU (first try) | baseline | 30.3 s of audio in 55.7 s (0.5×) | replaced |
| 2 | CUDA with cuDNN autotuning on (package default inside `lightning()`) | default | 30.3 s of audio in 202 s (0.1×), slower than the CPU | rejected |
| 3 | `torch.backends.cudnn.benchmark = False` | autotuning re-searches algorithms for every new input length; on this card the search costs more than the generation | same 30.3 s in about 1.1 s warm (17–29×) | kept, set in `kosucu.py` |
| 4 | Pinned revision + SHA-256 check before `torch.load` | the package downloads without a pinned revision | identical audio, load time unchanged (1.4 s) | kept (security) |
| 5 | Model kept warm in GPU memory between calls | would save 8–15 s per call | rejected: the 4 GB card is shared with other stages | rejected |
| 6 | CPU path through ONNX Runtime, same engine code, three stage calls exported | serve speech on the CPU while the GPU renders | 8.5–9.5× vs PyTorch CPU 6.2× warm and 0.7× on the first pass of a new text length; SNR 80–96 dB against PyTorch | kept |
| 7 | Browser build (WebAssembly / WebGPU) | portable path | 2.8–4.9× WASM; WebGPU picked the integrated GPU (1.2×) | rejected |
| 8 | `lightning()` (torch.compile + CUDA graphs) | publisher's fast path | no record: never measured on this card; the publisher's 440× figure is for a much larger GPU | not used |
| 9 | Half precision, ONNX GPU providers, thread sweep | — | no record | not used |

### Tools

- PyTorch 2.8 (`torch.onnx.export`, TorchScript exporter, opset 17, dynamic batch/length axes). ONNX has no `expm1`
  operator; it is exported as `exp(x) - 1` (log-durations are clamped to at most 6 first, so nothing is lost).
- ONNX Runtime 1.31 `CPUExecutionProvider`, intra-op threads = half the logical CPUs (at most 8), inter-op 1.
- The package's own `Engine`, `Frontend` and `chunk` (`ema-lightning` 1.1.0) for both paths.
- `nvidia-smi` (free GPU memory for `auto`), the pipeline's subprocess runner with a hidden window.

### Measurements

Reference machine, this repository's code path (`kosucu.py`), three Turkish sentences, 9.08 s of audio:

| Path | Start-up (process start → model ready) | Synthesis | Speed | Peak GPU memory |
|---|---|---|---|---|
| `onnx-cpu` (4 threads), two runs | 12.3 s | 0.86 s / 0.75 s | 10.6× / 12.1× | 0 |
| `torch-cpu`, first pass | 3.7 s | 3.72 s | 2.4× | 0 |
| `torch-cuda`, second of two runs | 5.3 s | 0.93 s | 9.8× | 94 MB allocated by PyTorch, 191 MB on the device |
| `torch-cuda`, first of two runs (another install was loading the machine) | 36.7 s | 37.9 s | 0.24× | same |

ONNX vs PyTorch on the same text and seed: equal length, SNR 85.8 dB. Export on the CPU: 10.8 s, largest stage
difference 3.2e-5. ONNX start-up does not depend on the graph optimisation level (8.5–9.1 s for all four levels);
for one short sentence PyTorch on the CPU finishes first, from about half a minute of audio upwards ONNX wins.
End to end: `dubla seslendir` (two sentences, 5.4 s of audio) and an 8 s synthetic-video dub both completed on the
CPU path; in the dub the EMA stage took 21.3 s start-up and 3.9 s reading for 4.6 s of Turkish speech (the whole
job, with transcription, translation, alignment and encoding on the CPU, 6 min 40 s); output 48 kHz with the AI label.
`dubla seslendir` on the GPU (same two sentences, 5.4 s of audio): 3.7 s start-up, 3.7 s reading, 94 MB allocated.
On texts this short the GPU is not faster than ONNX on the CPU; it starts sooner and leaves the CPU free, and the
history table (step 3) shows its lead on longer text. The slow first GPU run was not repeated under a quiet machine:
the cause (another install running, or a cold CUDA kernel cache) is a guess.

### Reproduce

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim tts-ema
.venv\Scripts\dubla.exe kontrol
.venv\Scripts\dubla.exe seslendir "Merhaba, bu kısa bir deneme cümlesidir." --motor ema_lightning --cihaz cpu -o ema_cpu
.venv\Scripts\dubla.exe seslendir "Merhaba, bu kısa bir deneme cümlesidir." --motor ema_lightning --cihaz cuda -o ema_gpu
```

Each run logs `[EMA] bitti yol=... yukleme=...s okuma=...s ses=...s vram_tepe=...MB`; speed = `ses / okuma`.
`python -m dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts aktar` repeats the export and writes the equality
figures to `runtime_assets/tts_motorlari/ema_lightning/onnx/aktarim.json`.

## Türkçe

**Ne yapar:** Küçük ve hızlı, yalnız Türkçe okuyan TTS motoru (8,6 M parametre, yaklaşık 34 MB ağırlık, 48 kHz mono, tek ses). Aynı ağırlık NVIDIA GPU'da (PyTorch) ya da işlemcide (ONNX Runtime; dosyalar resmî ağırlıktan yerelde dışa aktarılır) çalışır. İki dublaj kipinde (`segment_sync` ve `full_text`) ve `dubla seslendir`'de çalışır.

| | |
|---|---|
| Lisans | Apache-2.0 (kod ve ağırlık; ticari kullanım dahil) |
| Ticari kullanım | evet |
| Kaynak | https://huggingface.co/canberkkkkkk/ema-lightning @ `e7c96f2fc0ba843cd0f86e02786655bb56f50df8` (ağırlık) · PyPI `ema-lightning==1.1.0` (kod, https://github.com/canberk7/ema-lightning) |
| Kurulum | `scripts/kur.ps1 -Adim tts-ema` (hash'li kilitten paket, sabit commit + SHA-256 ile ağırlık, eşitlik denetimli ONNX dışa aktarımı) |
| Donanım | GPU (4 GB Pascal sınıfı kart): üç cümlede 5 sn açılıştan sonra gerçek zamanın yaklaşık 10 katı, 0,2 GB'ın altında GPU belleği (ölçüldü) · İşlemci (ONNX, 4 iş parçacığı): 12 sn açılıştan sonra gerçek zamanın yaklaşık 11 katı (ölçüldü) |
| Diller | yalnız Türkçe (`tr`); başka hedef dil ayar hatasıdır |
| Ses | tek sentetik ses (`ema`); VoxCPM2'de metin tarifinden tasarlanmış, gerçek bir kişinin kaydı değil (model kartı) |
| Varsayılan | kapalı |

**Ayarlar**

- `ses.motor = "ema_lightning"`
- `ses.ema_cihaz`: `auto` (varsayılan: NVIDIA GPU'da en az 1 GB boş bellek varsa GPU, yoksa işlemci ONNX; CUDA ya da bellek hatasıyla düşen GPU koşusu bir kez işlemcide tekrarlanır) · `cuda` (yalnız GPU, yoksa hata) · `cpu` (GPU'ya hiç dokunmaz)
- `ses.ema_hiz`: okuma hızı 0,5–2,0 (1,0 = modelin doğal hızı). Çeviri uzunluk hedefini belirleyen `ses.hiz` ile aynı şey değildir.
- `ses.ema_tohum`: tohum (varsayılan 0). Aynı metin aynı tohumla aynı yolda aynı sesi verir; başka tohum aynı sesin başka bir okumasını verir.
- `dubla seslendir "metin" --motor ema_lightning [--cihaz auto|cuda|cpu] [--hiz 1.0]`

**Sık hatalar**

- `genel.hedef_dil` `tr` dışında → ayar hatası ("dilini okuyamaz"); başka diller için Supertonic ya da VoxCPM2 seçin.
- `ses.ema_cihaz = cuda` ile `genel.cihaz = cpu` birlikte → ayar hatası (çelişki).
- "kurulu değil" → `scripts/kur.ps1 -Adim tts-ema` çalıştırın.
- `dubla kontrol` işlemci yolunu ONNX değil torch gösteriyor → dışa aktarım ya da eşitlik denetimi geçmedi; adımı yeniden çalıştırın. İşlemci yine çalışır, yalnız uzun metinde daha yavaştır.

**İlgili:** [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) · [donanim.md](../donanim.md) · [diller.md](../diller.md) · [ADR 0019](../adr/0019-ema-lightning-tts.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** iş başına bir alt süreç (`ema_lightning_tts/kosucu.py`) modeli bir kez yükler, her segmenti okur ve
  kapanır; GPU belleği sonraki aşama için tamamen boşalır. İşi paketin kendi motoru üç aşamada yapar: metin aşaması
  (harf → öznitelik ve süre), ses aşaması (hizalayıcı + dört örnekleme adımı) ve çözücü (gizil → 48 kHz ses). Uzun
  metni paket cümle ve yan cümle işaretlerinden, kendi duraklamalarıyla böler.
- **GPU ve işlemci yolu aynı kodu izler.** Yalnız üç aşamanın hesaplandığı yer değişir: CUDA'da PyTorch ya da
  işlemcide ONNX Runtime. Metin düzenleme, bölme, kare zaman çizelgesi ve tohumlu gürültü paketin Python kodunda kalır.
- **ONNX dosyaları neden yerelde üretilir:** model yayıncısı yalnız PyTorch ağırlığı yayımlar. Üçüncü kişinin
  dönüştürdüğü dosyayı indirmek yerine kurulum adımı üç aşamayı aynı SHA-256 denetimli resmî ağırlıktan kullanıcının
  makinesinde dışa aktarır ve farklı uzunlukta bir cümlede PyTorch ile karşılaştırır. En büyük fark 1e-3'ü aşarsa
  işlemci yolu PyTorch'a döner.
- **Diğer parçalarla ahengi:** Supertonic ile aynı sonuç sözleşmesi (segment WAV'leri, ölçülen süre, ortak
  karıştırıcı ve video yeniden zamanlaması). `full_text` kipinde her cümle ayrı okunur ve 0,25 sn sessizlikle
  (paketin kendi cümle duraklaması) birleştirilir; tam metin hizalama pencereleri gerçek cümle seslerinden gelir.
- **Sorumlu kullanım:** model kartı, dinleyene sesin yapay zekâ ile üretildiğinin söylenmesini ister; hattın yapay
  zekâ etiketi (`video.yapay_zeka_etiketi`, varsayılan açık) bunu videolarda yapar.

## Hızlandırma geçmişi ve gerekçe

Motor bu repodan önce başvuru makinesinde (4 GB Pascal sınıfı GPU, 4 çekirdekli dizüstü işlemcisi) kısa sesli cevaplar
için kullanıldı; aşağıdaki ayarlar o geçmişten gelir. Her sayı "hesap saniyesi başına ses saniyesi"dir. Ölçümü
olmayan kayıt bunu açıkça yazar.

| Adım | Değişiklik | Neden | Ölçülen sonuç | Durum |
|---|---|---|---|---|
| 1 | İşlemcide PyTorch (ilk deneme) | taban | 30,3 sn ses 55,7 sn'de (0,5×) | yerine başkası geldi |
| 2 | cuDNN kendi kendini ayarlaması açık CUDA (paketin `lightning()` içi varsayılanı) | varsayılan | 30,3 sn ses 202 sn'de (0,1×), işlemciden yavaş | reddedildi |
| 3 | `torch.backends.cudnn.benchmark = False` | ayarlama her yeni girdi uzunluğunda algoritmayı yeniden arar; bu kartta arama üretimden pahalı | aynı 30,3 sn sıcakta yaklaşık 1,1 sn'de (17–29×) | tutuldu, `kosucu.py` içinde |
| 4 | `torch.load`'dan önce sabit revizyon + SHA-256 denetimi | paket revizyonsuz indirir | ses aynı, yükleme süresi değişmedi (1,4 sn) | tutuldu (güvenlik) |
| 5 | Modeli çağrılar arasında GPU belleğinde sıcak tutmak | çağrı başına 8–15 sn kazanırdı | reddedildi: 4 GB kart diğer aşamalarla paylaşılır | reddedildi |
| 6 | ONNX Runtime ile işlemci yolu; aynı motor kodu, üç aşama çağrısı dışa aktarıldı | GPU görüntü işlerken işlemcide ses | 8,5–9,5×; PyTorch işlemci sıcakta 6,2×, yeni metin uzunluğunun ilk geçişinde 0,7×; PyTorch'a göre SNR 80–96 dB | tutuldu |
| 7 | Tarayıcı derlemesi (WebAssembly / WebGPU) | taşınabilir yol | WASM 2,8–4,9×; WebGPU tümleşik GPU'yu seçti (1,2×) | reddedildi |
| 8 | `lightning()` (torch.compile + CUDA grafikleri) | yayıncının hızlı yolu | kayıt yok: bu kartta hiç ölçülmedi; yayıncının 440× sayısı çok daha büyük bir GPU içindir | kullanılmıyor |
| 9 | Yarım hassasiyet, ONNX GPU sağlayıcıları, iş parçacığı taraması | — | kayıt yok | kullanılmıyor |

### Araçlar

- PyTorch 2.8 (`torch.onnx.export`, TorchScript dışa aktarıcı, opset 17, dinamik toplu iş/uzunluk eksenleri). ONNX'te
  `expm1` işlemi yoktur; `exp(x) - 1` olarak aktarılır (log süreler önce en çok 6'ya kırpıldığı için kayıp yoktur).
- ONNX Runtime 1.31 `CPUExecutionProvider`, iş içi iş parçacığı = mantıksal işlemcinin yarısı (en çok 8), işler arası 1.
- Her iki yol için paketin kendi `Engine`, `Frontend` ve `chunk` kodu (`ema-lightning` 1.1.0).
- `nvidia-smi` (`auto` için boş GPU belleği), hattın gizli pencereli alt süreç koşucusu.

### Ölçümler

Başvuru makinesi, bu reponun kod yolu (`kosucu.py`), üç Türkçe cümle, 9,08 sn ses:

| Yol | Açılış (süreç başı → model hazır) | Sentez | Hız | GPU bellek tepesi |
|---|---|---|---|---|
| `onnx-cpu` (4 iş parçacığı), iki koşu | 12,3 sn | 0,86 sn / 0,75 sn | 10,6× / 12,1× | 0 |
| `torch-cpu`, ilk geçiş | 3,7 sn | 3,72 sn | 2,4× | 0 |
| `torch-cuda`, iki koşunun ikincisi | 5,3 sn | 0,93 sn | 9,8× | PyTorch'un ayırdığı 94 MB, cihazda 191 MB |
| `torch-cuda`, iki koşunun ilki (makinede başka bir kurulum çalışıyordu) | 36,7 sn | 37,9 sn | 0,24× | aynı |

Aynı metin ve tohumda ONNX ile PyTorch: uzunluk eşit, SNR 85,8 dB. İşlemcide dışa aktarım: 10,8 sn, aşamalar arası en
büyük fark 3,2e-5. ONNX açılışı grafik iyileştirme düzeyine bağlı değil (dört düzeyde 8,5–9,1 sn); tek kısa cümlede
işlemcide PyTorch önce biter, yaklaşık yarım dakikalık sesten sonra ONNX kazanır. Uçtan uca: `dubla seslendir` (iki
cümle, 5,4 sn ses) ve 8 sn'lik sentetik video dublajı işlemci yolunda tamamlandı; dublajda EMA aşaması 4,6 sn Türkçe
konuşma için 21,3 sn açılış ve 3,9 sn okuma sürdü (yazıya dökme, çeviri, hizalama ve kodlama dahil bütün iş işlemcide
6 dk 40 sn); çıktı 48 kHz, YZ etiketli.
GPU'da `dubla seslendir` (aynı iki cümle, 5,4 sn ses): 3,7 sn açılış, 3,7 sn okuma, 94 MB ayrıldı. Bu kadar kısa
metinde GPU işlemcideki ONNX'ten hızlı değildir; daha erken başlar ve işlemciyi boş bırakır, uzun metindeki üstünlüğünü
geçmiş tablosu (3. adım) gösterir. Yavaş ilk GPU koşusu sakin makinede tekrarlanmadı: nedeni (çalışan başka bir kurulum
ya da soğuk CUDA çekirdek önbelleği) tahmindir.

### Yeniden üretme

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim tts-ema
.venv\Scripts\dubla.exe kontrol
.venv\Scripts\dubla.exe seslendir "Merhaba, bu kısa bir deneme cümlesidir." --motor ema_lightning --cihaz cpu -o ema_cpu
.venv\Scripts\dubla.exe seslendir "Merhaba, bu kısa bir deneme cümlesidir." --motor ema_lightning --cihaz cuda -o ema_gpu
```

Her koşu `[EMA] bitti yol=... yukleme=...s okuma=...s ses=...s vram_tepe=...MB` satırını yazar; hız = `ses / okuma`.
`python -m dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts aktar` dışa aktarımı tekrarlar ve eşitlik sayılarını
`runtime_assets/tts_motorlari/ema_lightning/onnx/aktarim.json` dosyasına yazar.
