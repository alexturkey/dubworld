# Engine × hardware matrix

[Türkçe](#türkçe) · Source of truth in code: `src/dublaj_hatti/kayit.py` (`cihaz`, `vram_mb`, `cpu`, `bellek`, `kanit`),
labels: `bolum_00_omurga/runtime/donanim.py` (`motor_etiketi`). A test (`tests/test_dil_ses_donanim.py`) fails if an
engine is missing from this page.

Measurements were taken on a **4 GB VRAM Pascal-class GPU** (no fast fp16, int8 ≈ 4.4× fp32) and its host CPU.
Every value carries its evidence level:

- **measured** — a real run record (the engineering page that holds it is in the *Source* column);
- **per docs** — model card, code constant or written rule, no stored run;
- **estimate** — not verified; please open a PR with a measurement.

## What the app does with this table

1. **Ready flow without a GPU.** `genel.cihaz = auto` runs a real CUDA kernel; if it fails the job runs on the CPU and
   picks CPU-friendly engines: transcription `faster_whisper_ctc` int8 (faster-whisper text + CTC word times; CrisperWhisper is GPU-only), speech `supertonic`
   (CPU-native), source cleaning `original`. The reason is written to the log (`Seçim gerekçesi: ...`) and shown on
   screen (CLI stderr; GUI/web job start event `secimler.gerekceler`).
2. **Explicit choice is never swapped silently.** If you pick a GPU-only engine (`crisperwhisper_*`, `voxcpm2`) and no
   working CUDA exists, loading stops with a clear error naming the CPU alternative.
3. **Interface labels, nothing hidden.** The engine lists in the desktop and web *Advanced* tab show every engine;
   unsuitable ones get a label: `CPU'da çalışmaz` (no CPU path), `CPU'da yavaş`, `VRAM yetmez (~N MB gerekir)` (needs
   more than 95 % of the detected VRAM), `bulut` (network + your own key). The interface reads the GPU with
   `nvidia-smi` (no torch import); the final decision is made when the job starts.

## Matrix

| Kind | Engine | Device | Peak VRAM MB | On CPU | Evidence | Notes | Source |
|---|---|---|---|---|---|---|---|
| stt | `faster-whisper` | gpu+cpu | 1150 (int8) / 3450 (fp32) | works (slower than GPU) | measured | Same large-v3-turbo model measured inside WhisperX; CPU uses int8; CPU speed not measured | docs/engineering/gpu_memory_and_isolation.md, transcription.md |
| stt | `faster_whisper_ctc` | gpu+cpu | 2400 (CTC step; recognition as `faster-whisper`) | works | measured | Recognition and CTC run one after another in separate processes. CPU, one run each: 23.8 s English → recognition ≈ 140 s + CTC 16.5 s; 60 s Turkish → ≈ 161 s + 42.9 s (CTC incl. ≈ 10 s load) | timing-sources.md §2.1, word_alignment.md |
| stt | `whisperx` | gpu+cpu | 1147 (int8) / 3451 (fp32) | works | measured | batch 1 + VAD on CPU removed an out-of-memory on 4 GB; 4.3–5.3× real time on GPU | transcription.md |
| stt | `crisperwhisper_turbo_ct2` | gpu | ~1450 | no | measured | int8, WSL2, one-shot subprocess; ~11× real time; 1435 MiB on 74 min audio | crisperwhisper_turbo_ct2.md |
| stt | `crisperwhisper2_medium` | gpu | ~3600 (fp16) | no | measured | fp32 does not fit 4 GB; tightest margin of all engines; CPU fallback refused by the engine | gpu_memory_and_isolation.md |
| stt | `moonshine_medium_streaming_en` | cpu | — | good | measured | 96.9 s audio: 75.4 s streaming; RAM not measured; English only | transcription.md |
| stt | `whisper_cpp_cpu_align` | cpu | — (CTC step may use GPU) | good | measured | 96.9 s audio: 32.4 s (12.7 recognition + 19.4 alignment) | transcription.md |
| stt | `parakeet_cpu_align` | cpu | — | good | measured | int8, ~1.9 GB RAM, 96.9 s audio in 11.9 s (8 threads); input capped below 400 s | transcription.md |
| stt | `speechmatics` | cloud | — | cloud | per docs | audio is sent to the service (PRIVACY.md) | provider docs |
| stt | `elevenlabs_scribe_v2` | cloud | — | cloud | measured | 41.9 min audio in 112 s | transcription.md |
| stt | `youtube_translate` | gpu+cpu | ~2400 (CTC only) | slow | measured | no speech model; CTC alignment: GPU 1.65–2.4 GB, CPU ~10 min for 3.5 min audio | word_alignment.md |
| — | wav2vec2 CTC word alignment (used by every engine except CrisperWhisper) | gpu+cpu | 1650–2400 | slow | measured | 3.5 min audio: GPU 66–71 s (mostly model load), CPU ~10 min | word_alignment.md |
| translate | `yerel` (Opus-MT) | gpu+cpu | ~1000 | works | estimate | VRAM/RAM not measured; the CPU end-to-end smoke test passed with it | low_vram.md |
| translate | `codex`, `claude_code`, `gemini_2_5_flash`, `gemini_3_1_flash_lite_tier_1`, `gemma_4_26b`, `groq_llama_4_scout`, `cerebras_llama_3_1_8b`, `mistral_nemo` | cloud | — | cloud | per docs | text is sent to the service | translation.md |
| tts | `supertonic` | cpu | — | good | measured | ONNX on CPU, 4 lanes × 2 threads, ~2.3× real time, ~1.8 GB RAM; the CUDA provider was slower and is not used | tts_timing_and_mix.md |
| tts | `voxcpm2` | gpu | ~3000 | no | measured | Q8_0 GGUF + 4 GB patch, 2.6–3.0 GB; ~2 s compute per 1 s audio; CPU took 535 s for 48.5 s so CPU is disabled here | sister VoxCPM2 repo docs/4gb.md |
| tts | `xtts` | gpu+cpu | ~2000 | slow | per docs | model load ~2 GB (source doc), peak not measured; CPU "very slow" is an estimate | tts_timing_and_mix.md, docs/motorlar/xtts.md |
| extra | `demucs` | gpu+cpu | 2749 | slow | measured | 75 min audio: process tree 7.15 GB RAM; batch 4 with one retry at batch 1 | source_audio_and_separation.md |
| extra | `konusmaci_ayrimi` (3D-Speaker CAM++) | gpu+cpu | < 1000 | works | per docs | ran on CPU in the end-to-end CPU smoke test | low_vram.md, speakers_and_segments.md |
| extra | `cinsiyet_siniflandirici` | gpu+cpu | < 1000 | works | per docs | 1.26 GB weights; ran on CPU in the smoke test | low_vram.md |
| extra | `segment_cinsiyet_kipi` | gpu+cpu | < 1000 | works | per docs | same classifier per sentence; ~3 GB RAM on CPU is an estimate | low_vram.md |
| extra | `akilli_kare` | cpu | — | good | estimate | OpenCV, ~500 MB RAM | — |
| extra | `rvc` | gpu+cpu | ~2000 | slow | estimate | your own model; runs in the official RVC WebUI environment | docs/motorlar/rvc.md |
| extra | `yt_dlp`, `gallery_dl` | cpu | — | good | estimate | network tools, < 100 MB RAM | — |
| extra | `kapak_gorseli` | cloud | — | cloud | per docs | Codex CLI image generation | docs/motorlar/kapak_gorseli.md |
| extra | `telegram_botu` | cpu | — | good | estimate | ~100 MB RAM | — |

**General 4 GB rules (measured, gpu_memory_and_isolation.md):** one GPU job at a time (two parallel jobs are each
~1.95× slower; the app uses a machine-wide GPU lock); every heavy model runs in its own process so VRAM is freed on
exit; fp16 gives no speed-up on Pascal (float16 / int8_float16 are refused, int8 or fp32 are used).

**Open measurements (estimate rows):** Opus-MT VRAM and speed, faster-whisper / WhisperX / Demucs CPU speed, XTTS peak
VRAM, RVC, Speechmatics speed, VoxCPM2 inside the dubbing pipeline.

---

## Türkçe

Koddaki tek doğruluk kaynağı: `src/dublaj_hatti/kayit.py` (`cihaz`, `vram_mb`, `cpu`, `bellek`, `kanit`), etiketler:
`bolum_00_omurga/runtime/donanim.py` (`motor_etiketi`). Bir motor bu sayfada yoksa bir test
(`tests/test_dil_ses_donanim.py`) başarısız olur.

Ölçümler **4 GB VRAM'li Pascal sınıfı bir GPU**'da (hızlı fp16 yok, int8 ≈ fp32'nin 4.4 katı) ve onun ana
işlemcisinde alındı. Her değer dayanağını taşır:

- **ölçüldü** — gerçek bir koşu kaydı (onu tutan mühendislik sayfası *Kaynak* sütunundadır);
- **belgeye göre** — model kartı, kod sabiti ya da yazılı kural; saklanmış koşu yok;
- **tahmin** — doğrulanmadı; lütfen ölçümle bir PR açın.

### Uygulama bu tabloyla ne yapar

1. **GPU yoksa hazır akış.** `genel.cihaz = auto` gerçek bir CUDA çekirdeği çalıştırır; başarısız olursa iş işlemcide
   yürür ve işlemci dostu motorlar seçilir: transkripsiyon `faster_whisper_ctc` int8 (metin faster-whisper, kelime
   zamanı CTC; CrisperWhisper yalnız GPU'dur), ses `supertonic` (işlemci için yazılmış), ses temizliği `original`.
   Gerekçe günlüğe yazılır (`Seçim gerekçesi: ...`) ve ekranda gösterilir (CLI stderr; GUI/web iş başlangıç olayı
   `secimler.gerekceler`).
2. **Elle seçim asla sessizce değiştirilmez.** Yalnız GPU'lu bir motor (`crisperwhisper_*`, `voxcpm2`) seçilir ve
   çalışan CUDA yoksa, yükleme işlemci seçeneğini adıyla söyleyen açık bir hatayla durur.
3. **Arayüzde etiket var, gizleme yok.** Masaüstü ve web *Gelişmiş* sekmesindeki motor listeleri her motoru gösterir;
   uygun olmayanlar bir etiket alır: `CPU'da çalışmaz` (işlemci yolu yok), `CPU'da yavaş`, `VRAM yetmez (~N MB gerekir)`
   (tespit edilen VRAM'in %95'inden fazlasını ister), `bulut` (ağ + kendi anahtarınız). Arayüz GPU'yu `nvidia-smi` ile
   okur (torch yüklenmez); kesin karar iş başlarken verilir.

### Matris

| Tür | Motor | Cihaz | Tepe VRAM MB | İşlemcide | Kanıt | Notlar | Kaynak |
|---|---|---|---|---|---|---|---|
| stt | `faster-whisper` | gpu+cpu | 1150 (int8) / 3450 (fp32) | çalışır (GPU'dan yavaş) | ölçüldü | Aynı large-v3-turbo modeli WhisperX içinde ölçüldü; işlemci int8 kullanır; işlemci hızı ölçülmedi | docs/engineering/gpu_memory_and_isolation.md, transcription.md |
| stt | `faster_whisper_ctc` | gpu+cpu | 2400 (CTC adımı; tanıma `faster-whisper` gibi) | çalışır | ölçüldü | Tanıma ve CTC ayrı süreçlerde art arda çalışır. İşlemci, birer koşu: 23.8 s İngilizce → tanıma ≈ 140 s + CTC 16.5 s; 60 s Türkçe → ≈ 161 s + 42.9 s (CTC, ≈ 10 s yükleme dahil) | timing-sources.md §2.1, word_alignment.md |
| stt | `whisperx` | gpu+cpu | 1147 (int8) / 3451 (fp32) | çalışır | ölçüldü | batch 1 + işlemcide VAD, 4 GB'ta bellek taşmasını giderdi; GPU'da gerçek zamanın 4.3–5.3 katı | transcription.md |
| stt | `crisperwhisper_turbo_ct2` | gpu | ~1450 | hayır | ölçüldü | int8, WSL2, tek seferlik alt süreç; gerçek zamanın ~11 katı; 74 dk seste 1435 MiB | crisperwhisper_turbo_ct2.md |
| stt | `crisperwhisper2_medium` | gpu | ~3600 (fp16) | hayır | ölçüldü | fp32 4 GB'a sığmaz; bütün motorlar içinde en dar pay; işlemci yedeğini motor reddeder | gpu_memory_and_isolation.md |
| stt | `moonshine_medium_streaming_en` | cpu | — | iyi | ölçüldü | 96.9 s ses: akışla 75.4 s; RAM ölçülmedi; yalnız İngilizce | transcription.md |
| stt | `whisper_cpp_cpu_align` | cpu | — (CTC adımı GPU kullanabilir) | iyi | ölçüldü | 96.9 s ses: 32.4 s (12.7 tanıma + 19.4 hizalama) | transcription.md |
| stt | `parakeet_cpu_align` | cpu | — | iyi | ölçüldü | int8, ~1.9 GB RAM, 96.9 s ses 11.9 s'de (8 iş parçacığı); girdi 400 s altıyla sınırlı | transcription.md |
| stt | `speechmatics` | bulut | — | bulut | belgeye göre | ses servise gönderilir (PRIVACY.md) | sağlayıcı belgeleri |
| stt | `elevenlabs_scribe_v2` | bulut | — | bulut | ölçüldü | 41.9 dk ses 112 s'de | transcription.md |
| stt | `youtube_translate` | gpu+cpu | ~2400 (yalnız CTC) | yavaş | ölçüldü | konuşma modeli yok; CTC hizalama: GPU 1.65–2.4 GB, 3.5 dk ses için işlemcide ~10 dk | word_alignment.md |
| — | wav2vec2 CTC kelime hizalama (CrisperWhisper dışındaki her motor kullanır) | gpu+cpu | 1650–2400 | yavaş | ölçüldü | 3.5 dk ses: GPU 66–71 s (çoğu model yükleme), işlemci ~10 dk | word_alignment.md |
| translate | `yerel` (Opus-MT) | gpu+cpu | ~1000 | çalışır | tahmin | VRAM/RAM ölçülmedi; işlemcide uçtan uca duman testi bununla geçti | low_vram.md |
| translate | `codex`, `claude_code`, `gemini_2_5_flash`, `gemini_3_1_flash_lite_tier_1`, `gemma_4_26b`, `groq_llama_4_scout`, `cerebras_llama_3_1_8b`, `mistral_nemo` | bulut | — | bulut | belgeye göre | metin servise gönderilir | translation.md |
| tts | `supertonic` | cpu | — | iyi | ölçüldü | İşlemcide ONNX, 4 şerit × 2 iş parçacığı, gerçek zamanın ~2.3 katı, ~1.8 GB RAM; CUDA sağlayıcısı daha yavaştı ve kullanılmaz | tts_timing_and_mix.md |
| tts | `voxcpm2` | gpu | ~3000 | hayır | ölçüldü | Q8_0 GGUF + 4 GB yaması, 2.6–3.0 GB; 1 s ses için ~2 s hesap; işlemcide 48.5 s için 535 s sürdü, bu yüzden burada işlemci kapalı | kardeş VoxCPM2 reposu docs/4gb.md |
| tts | `xtts` | gpu+cpu | ~2000 | yavaş | belgeye göre | model yükleme ~2 GB (kaynak belge), tepe ölçülmedi; işlemcide "çok yavaş" bir tahmindir | tts_timing_and_mix.md, docs/motorlar/xtts.md |
| extra | `demucs` | gpu+cpu | 2749 | yavaş | ölçüldü | 75 dk ses: süreç ağacı 7.15 GB RAM; batch 4, bir kez batch 1 ile yeniden deneme | source_audio_and_separation.md |
| extra | `konusmaci_ayrimi` (3D-Speaker CAM++) | gpu+cpu | < 1000 | çalışır | belgeye göre | uçtan uca işlemci duman testinde işlemcide çalıştı | low_vram.md, speakers_and_segments.md |
| extra | `cinsiyet_siniflandirici` | gpu+cpu | < 1000 | çalışır | belgeye göre | 1.26 GB ağırlık; duman testinde işlemcide çalıştı | low_vram.md |
| extra | `segment_cinsiyet_kipi` | gpu+cpu | < 1000 | çalışır | belgeye göre | cümle başına aynı sınıflandırıcı; işlemcide ~3 GB RAM bir tahmindir | low_vram.md |
| extra | `akilli_kare` | cpu | — | iyi | tahmin | OpenCV, ~500 MB RAM | — |
| extra | `rvc` | gpu+cpu | ~2000 | yavaş | tahmin | kendi modeliniz; resmî RVC WebUI ortamında çalışır | docs/motorlar/rvc.md |
| extra | `yt_dlp`, `gallery_dl` | cpu | — | iyi | tahmin | ağ araçları, < 100 MB RAM | — |
| extra | `kapak_gorseli` | bulut | — | bulut | belgeye göre | Codex CLI görsel üretimi | docs/motorlar/kapak_gorseli.md |
| extra | `telegram_botu` | cpu | — | iyi | tahmin | ~100 MB RAM | — |

**Genel 4 GB kuralları (ölçüldü, gpu_memory_and_isolation.md):** aynı anda tek GPU işi (iki paralel iş ayrı ayrı
~1.95 kat yavaşlar; uygulama makine geneli bir GPU kilidi kullanır); her ağır model kendi sürecinde çalışır, böylece
VRAM çıkışta boşalır; fp16 Pascal'da hız kazandırmaz (float16 / int8_float16 reddedilir, int8 ya da fp32 kullanılır).

**Açık ölçümler (tahmin satırları):** Opus-MT VRAM ve hızı, faster-whisper / WhisperX / Demucs işlemci hızı, XTTS tepe
VRAM'i, RVC, Speechmatics hızı, VoxCPM2'nin dublaj hattı içindeki ölçümü.
