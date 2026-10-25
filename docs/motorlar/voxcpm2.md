# VoxCPM2 (voice design TTS) (`voxcpm2`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Second TTS engine for high-quality designed voices (strong in Turkish). Runs as a one-session subprocess in the sister VoxCPM2 repository's own environment and returns the same result contract as Supertonic.

| | |
|---|---|
| License | Apache-2.0 (code and weights) |
| Commercial use | yes |
| Source | https://github.com/OpenBMB/VoxCPM ; installer: sister repository at a fixed commit |
| Install | `scripts/kur.ps1 -Adim voxcpm2` (sister repository URL built in; for a fork set `DUBLAJ_TTS_REPO_URL`) |
| Hardware | NVIDIA GPU, 2.6–3.0 GB VRAM (Q8_0 GGUF + 4 GB patch, measured), ~2 s compute per 1 s audio; CPU disabled (48.5 s audio took 535 s) |
| Languages | tested: tr, en, fr, de, es, ru, zh, ja; others allowed with a warning |
| Default | off |

**Settings**

- `ses.motor = "voxcpm2"`
- `ses.voxcpm2_ses`: `hazir/<name>` (ready voices in [sesler.md](../sesler.md)), `<name>/<variant>` (your designed voice) or a voice folder path
- per speaker: `ses.konusmaci_sesleri.SPEAKER_00 = "hazir/<name>"` (gender prediction is skipped)

**Common errors**

- `genel.cihaz = cpu` → settings error by design.
- `full_text` mode → not supported (Supertonic or EMA Lightning only).
- Slows down without an error → VRAM spilled into shared memory; close other GPU programs.

**Related:** [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) · [sesler.md](../sesler.md) · [diller.md](../diller.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** the VoxCPM2 model (quantised Q8_0 GGUF) runs inside the sister VoxCPM2 repository's own environment.
  One subprocess per job loads the model once and synthesises every segment with the selected designed voice; the
  runner imports nothing from this package and returns WAV paths, peak VRAM and the seed in a JSON file.
- **Why this choice:** designed voices with strong Turkish quality under Apache-2.0. It is optional, not default,
  because it needs an NVIDIA GPU (2.6–3.0 GB VRAM) and a separate install; the CPU path is refused because 48.5 s of
  audio took 535 s ([ADR 0015](../adr/0015-tts-engine-set-and-default.md)).
- **How it fits:** same result contract as Supertonic: the shared execution layer measures the real duration and the
  mixer places each segment at its start. There are no candidates, repair rounds or `atempo` for this engine, so
  `ses.akis` has no effect; the video retiming absorbs the difference. A per-speaker voice map skips gender prediction.
  Near the 4 GB limit, VRAM can spill into shared memory and slow generation without an error.
- **4 GB speed-ups (audio.cpp CUDA build, sm_61):** Q8_0 GGUF weights, a KV cache sized to the request, the AudioVAE encoder on the CPU, LM and decoder never in VRAM together, chunked decoding, zeroed CUDA buffers and an on-disk reference-embedding cache. Each change, its environment variable and its measurement are in the sister repository: [docs/4gb.md](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi/blob/main/docs/4gb.md). This repository installs that build at a pinned commit and does not modify it.
- Details: [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) §7 · [gpu_memory_and_isolation.md](../engineering/gpu_memory_and_isolation.md) §3
- Place in the end-to-end flow: [pipeline-flow.md, branch table](../engineering/pipeline-flow.md#5-branches-what-a-choice-changes)

## Türkçe

**Ne yapar:** Yüksek kaliteli tasarlanmış sesler için ikinci TTS motoru (Türkçede güçlü). Kardeş VoxCPM2 reposunun kendi ortamında tek oturumluk bir alt süreç olarak çalışır ve Supertonic ile aynı sonuç sözleşmesini döndürür.

| | |
|---|---|
| Lisans | Apache-2.0 (kod ve ağırlıklar) |
| Ticari kullanım | evet |
| Kaynak | https://github.com/OpenBMB/VoxCPM ; kurucu: sabit commit'teki kardeş repo |
| Kurulum | `scripts/kur.ps1 -Adim voxcpm2` (kardeş repo adresi hazırdır; çatal (fork) için `DUBLAJ_TTS_REPO_URL` ayarlanır) |
| Donanım | NVIDIA GPU, 2.6–3.0 GB VRAM (Q8_0 GGUF + 4 GB yaması, ölçüldü), 1 sn ses için ~2 sn hesap; işlemci kapalı (48.5 sn ses 535 sn sürdü) |
| Diller | denendi: tr, en, fr, de, es, ru, zh, ja; diğerlerine uyarıyla izin verilir |
| Varsayılan | kapalı |

**Ayarlar**

- `ses.motor = "voxcpm2"`
- `ses.voxcpm2_ses`: `hazir/<name>` ([sesler.md](../sesler.md) içindeki hazır sesler), `<name>/<variant>` (kendi tasarladığınız ses) ya da bir ses klasörü yolu
- konuşmacı başına: `ses.konusmaci_sesleri.SPEAKER_00 = "hazir/<name>"` (cinsiyet tahmini atlanır)

**Sık hatalar**

- `genel.cihaz = cpu` → tasarım gereği ayar hatası.
- `full_text` kipi → desteklenmez (yalnız Supertonic ya da EMA Lightning).
- Hata vermeden yavaşlar → VRAM paylaşılan belleğe taştı; diğer GPU programlarını kapatın.

**İlgili:** [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) · [sesler.md](../sesler.md) · [diller.md](../diller.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** VoxCPM2 modeli (nicemlenmiş Q8_0 GGUF) kardeş VoxCPM2 reposunun kendi ortamında çalışır. İş başına bir alt
  süreç modeli bir kez yükler ve her segmenti seçilen tasarlanmış sesle sentezler; koşucu bu paketten hiçbir şey içe
  aktarmaz ve WAV yollarını, en yüksek VRAM değerini ve tohumu bir JSON dosyasında döndürür.
- **Neden bu seçim:** Apache-2.0 altında, Türkçe kalitesi güçlü tasarlanmış sesler. Varsayılan değil isteğe bağlıdır,
  çünkü NVIDIA GPU (2.6–3.0 GB VRAM) ve ayrı bir kurulum ister; işlemci yolu reddedilir, çünkü 48.5 sn ses 535 sn
  sürdü ([ADR 0015](../adr/0015-tts-engine-set-and-default.md)).
- **Diğer parçalarla ahengi:** Supertonic ile aynı sonuç sözleşmesi: ortak yürütme katmanı gerçek süreyi ölçer ve
  karıştırıcı her segmenti başlangıcına yerleştirir. Bu motor için aday, onarım turu ya da `atempo` yoktur, bu yüzden
  `ses.akis` etkisizdir; farkı video yeniden zamanlaması karşılar. Konuşmacı başına ses haritası cinsiyet tahminini atlar.
  4 GB sınırına yakın VRAM paylaşılan belleğe taşabilir ve üretimi hata vermeden yavaşlatabilir.
- **4 GB hızlandırmaları (audio.cpp CUDA derlemesi, sm_61):** Q8_0 GGUF ağırlık, isteğe göre boyutlanan KV önbelleği, işlemcide AudioVAE kodlayıcı, LM ile kod çözücünün VRAM'de hiç birlikte durmaması, parçalı kod çözme, sıfırlanan CUDA arabellekleri ve diskte referans gömme önbelleği. Her değişiklik, ortam değişkeni ve ölçümü kardeş repoda: [docs/4gb.md](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi/blob/main/docs/4gb.md). Bu repo o derlemeyi sabit commit'te kurar ve değiştirmez.
- Ayrıntı: [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) §7 · [gpu_memory_and_isolation.md](../engineering/gpu_memory_and_isolation.md) §3
- Uçtan uca akıştaki yeri: [hat_akisi.md, dallanma tablosu](../muhendislik/hat_akisi.md#5-dallanmalar-bir-seçim-neyi-değiştirir)
