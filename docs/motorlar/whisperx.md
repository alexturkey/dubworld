# WhisperX (`whisperx`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** faster-whisper recognition plus WhisperX's own wav2vec2 alignment; optional pyannote speaker labels in the transcript.

| | |
|---|---|
| License | BSD-2-Clause (code); models MIT / CC-BY-4.0; pyannote models need accepted Hugging Face terms |
| Commercial use | yes (check pyannote model terms if you enable diarization) |
| Source | https://github.com/m-bain/whisperX |
| Install | base install (packages) |
| Hardware | GPU int8 1147 MiB / float32 3451 MiB VRAM (measured); batch 1, VAD on the CPU; CPU works |
| Languages | multilingual; alignment model chosen per language ([diller.md](../diller.md)) |
| Default | off |

**Settings**

- `transkripsiyon.motor = "whisperx"`
- `transkripsiyon.whisperx_profili`: `auto`, `whisperx_float32_quality_v1` (needs `hesap_tipi=float32`), `whisperx_engine_default_v1` (needs `int8`)
- `ileri.pyannote_konusmaci_ayrimi = true` → speaker labels; needs `HF_TOKEN` and accepted model terms

**Common errors**

- `CUDA out of memory` → close other GPU programs; a real OOM retries once in int8 ([low_vram.md](../engineering/low_vram.md)).
- Profile/compute-type mismatch → settings error; match the pair above.
- Diarization stops with 401/403 (gated model) → a token alone is not enough: accept the user conditions of
  `pyannote/speaker-diarization-community-1` on Hugging Face, set `HF_TOKEN` to a read token, run once with
  `DUBLAJ_CEVRIMICI=1`; or turn `ileri.pyannote_konusmaci_ayrimi` off (default 3D-Speaker separation needs no token).

**Related:** [transcription.md](../engineering/transcription.md) · [word_alignment.md](../engineering/word_alignment.md) · [donanim.md](../donanim.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** batched faster-whisper decoding over VAD chunks (pyannote VAD on the CPU), followed by WhisperX's own
  wav2vec2 forced alignment; optional pyannote speaker labels. The same WhisperX alignment code is the shared CTC box
  that the other local engines use.
- **Why this choice:** on the 10-file corpus it led on 9–22 minute files (int8 WER 4.67 %, word-start error ≈ 30 ms).
  Batch 1 was ≈ 41 % faster than batch 2 on this card; VAD runs on the CPU because pyannote on the GPU left 130 MiB free
  and caused an OOM. It is not the default because the default path already uses the same CTC alignment with
  faster-whisper or CrisperWhisper.
- **How it fits:** reads the 44.1 kHz clean source directly (identical text and times to 16 kHz mono were measured);
  a real CUDA OOM in float32 retries once in int8 in a fresh process
  ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)); output feeds the segmenter like every other engine.
- Details: [transcription.md](../engineering/transcription.md) §3 · [gpu_memory_and_isolation.md](../engineering/gpu_memory_and_isolation.md) §4
- Place in the end-to-end flow: [pipeline-flow.md, segmentation per engine](../engineering/pipeline-flow.md#7-segmentation-per-transcription-engine)

## Türkçe

**Ne yapar:** faster-whisper tanıma artı WhisperX'in kendi wav2vec2 hizalaması; transkriptte isteğe bağlı pyannote konuşmacı etiketleri.

| | |
|---|---|
| Lisans | BSD-2-Clause (kod); modeller MIT / CC-BY-4.0; pyannote modelleri Hugging Face şartlarının kabulünü ister |
| Ticari kullanım | evet (konuşmacı ayrımını açarsanız pyannote model şartlarını denetleyin) |
| Kaynak | https://github.com/m-bain/whisperX |
| Kurulum | temel kurulum (paketler) |
| Donanım | GPU int8 1147 MiB / float32 3451 MiB VRAM (ölçüldü); toplu iş 1, VAD işlemcide; işlemcide çalışır |
| Diller | çok dilli; hizalama modeli dile göre seçilir ([diller.md](../diller.md)) |
| Varsayılan | kapalı |

**Ayarlar**

- `transkripsiyon.motor = "whisperx"`
- `transkripsiyon.whisperx_profili`: `auto`, `whisperx_float32_quality_v1` (`hesap_tipi=float32` ister), `whisperx_engine_default_v1` (`int8` ister)
- `ileri.pyannote_konusmaci_ayrimi = true` → konuşmacı etiketleri; `HF_TOKEN` ve kabul edilmiş model şartları gerekir

**Sık hatalar**

- `CUDA out of memory` → diğer GPU programlarını kapatın; gerçek bir OOM bir kez int8 ile yeniden dener ([low_vram.md](../engineering/low_vram.md)).
- Profil/hesap tipi uyuşmazlığı → ayar hatası; yukarıdaki eşleşmeye uyun.
- Konuşmacı ayrımı 401/403 ile durur (kapılı model) → token tek başına yetmez: Hugging Face'te
  `pyannote/speaker-diarization-community-1` kullanım şartlarını kabul edin, `HF_TOKEN`'a okuma tokenı yazın, bir kez
  `DUBLAJ_CEVRIMICI=1` ile çalıştırın; ya da `ileri.pyannote_konusmaci_ayrimi`'nı kapatın (varsayılan 3D-Speaker ayrımı token istemez).

**İlgili:** [transcription.md](../engineering/transcription.md) · [word_alignment.md](../engineering/word_alignment.md) · [donanim.md](../donanim.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** VAD parçaları üzerinde toplu faster-whisper çözümü (pyannote VAD işlemcide), ardından WhisperX'in kendi
  wav2vec2 zorlamalı hizalaması; isteğe bağlı pyannote konuşmacı etiketleri. Aynı WhisperX hizalama kodu, diğer yerel
  motorların kullandığı ortak CTC kutusudur.
- **Neden bu seçim:** 10 dosyalık derlemde 9–22 dakikalık dosyalarda öndeydi (int8 WER 4.67 %, kelime başlangıcı hatası
  ≈ 30 ms). Bu kartta toplu iş 1, toplu iş 2'den ≈ 41 % daha hızlıydı; VAD işlemcide çalışır, çünkü GPU'daki pyannote
  130 MiB boş bıraktı ve OOM'a yol açtı. Varsayılan değildir, çünkü varsayılan yol aynı CTC hizalamasını zaten
  faster-whisper ya da CrisperWhisper ile kullanır.
- **Diğer parçalarla ahengi:** 44.1 kHz temiz kaynağı doğrudan okur (16 kHz mono ile aynı metin ve zamanlar ölçüldü);
  float32'deki gerçek bir CUDA OOM yeni bir süreçte bir kez int8 ile yeniden dener
  ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)); çıktı her motor gibi segmentleyiciyi besler.
- Ayrıntı: [transcription.md](../engineering/transcription.md) §3 · [gpu_memory_and_isolation.md](../engineering/gpu_memory_and_isolation.md) §4
- Uçtan uca akıştaki yeri: [hat_akisi.md, motora göre segmentleme](../muhendislik/hat_akisi.md#7-transkripsiyon-motoruna-göre-segmentleme)
