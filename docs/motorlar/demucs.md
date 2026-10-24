# Demucs (speech / background separation) (`demucs`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Separates speech from music and effects (`htdemucs`, two stems) so the dub can run on clean speech and keep the background under the new voice.

| | |
|---|---|
| License | MIT |
| Commercial use | yes |
| Source | https://github.com/facebookresearch/demucs |
| Install | `scripts/kur.ps1 -Adim demucs` (extra `separation`) |
| Hardware | GPU 2749 MiB VRAM, process tree 7.15 GB RAM on 75 min audio (measured); CPU slow |
| Default | off (`ses_temizligi.kip = original`) |

**Settings**

- `ses_temizligi.kip`: `clean` (speech only), `preserve_background` (background mixed under the dub), `auto_background` (keep it only when a background is detected)
- single stage: `dubla ayir video.mp4 -o dir`

**Common errors**

- `torch.cuda.OutOfMemoryError` → automatic one-time retry at batch 1 (`oom_fallback=true` in the report).
- Demucs missing with `clean` / `preserve_background` → error at start; install or use `original`.

**Related:** [source_audio_and_separation.md](../engineering/source_audio_and_separation.md) · [ADR 0002](../adr/0002-demucs-batched-two-stem-worker.md) · [ADR 0003](../adr/0003-automatic-background-detection.md)

## How it works in this pipeline / Neden böyle

- **Principle:** `htdemucs` (hybrid time/frequency transformer) separates the mix into stems; the pipeline keeps two:
  vocals and everything else (`no_vocals`). On CUDA the project's own worker processes 4 chunks per call and reduces
  each chunk to two stems on the GPU before accumulation.
- **Why this choice:** separation is needed to keep music and effects under the new voice. The two-stem worker halved
  worker time and cut 2.4 GB of RAM ([ADR 0002](../adr/0002-demucs-batched-two-stem-worker.md)). Separation can remove
  real speech, so recognition uses the raw audio when `auto_background` decides only the background is needed
  ([ADR 0003](../adr/0003-automatic-background-detection.md)).
- **How it fits:** runs before recognition in its own subprocess under the GPU lock (≈ 2.75 GB VRAM); `no_vocals` is
  retimed with the video and mixed under the dub without ducking; a Demucs failure stops the job before transcription
  ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)).
- Details: [source_audio_and_separation.md](../engineering/source_audio_and_separation.md) §2–§5 · [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) §6

## Türkçe

Kayıt satırı: `src/dublaj_hatti/kayit.py` (kurulu olup olmadığını `dubla kontrol` gösterir)

**Ne yapar:** Dublaj temiz konuşma üzerinde çalışabilsin ve arka plan yeni sesin altında kalsın diye konuşmayı müzik ve efektlerden ayırır (`htdemucs`, iki kanal/stem).

| | |
|---|---|
| Lisans | MIT |
| Ticari kullanım | evet |
| Kaynak | https://github.com/facebookresearch/demucs |
| Kurulum | `scripts/kur.ps1 -Adim demucs` (ek `separation`) |
| Donanım | GPU 2749 MiB VRAM, 75 dk seste süreç ağacı 7.15 GB RAM (ölçüldü); CPU'da yavaş |
| Varsayılan | kapalı (`ses_temizligi.kip = original`) |

**Ayarlar**

- `ses_temizligi.kip`: `clean` (yalnız konuşma), `preserve_background` (arka plan dublajın altına karıştırılır), `auto_background` (yalnız arka plan algılanırsa korunur)
- tek aşama: `dubla ayir video.mp4 -o dir`

**Sık hatalar**

- `torch.cuda.OutOfMemoryError` → batch 1 ile otomatik, tek seferlik yeniden deneme (raporda `oom_fallback=true`).
- `clean` / `preserve_background` seçiliyken Demucs yok → başlangıçta hata; kurun ya da `original` kullanın.

**İlgili:** [source_audio_and_separation.md](../engineering/source_audio_and_separation.md) · [ADR 0002](../adr/0002-demucs-batched-two-stem-worker.md) · [ADR 0003](../adr/0003-automatic-background-detection.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** `htdemucs` (karma zaman/frekans transformer'ı) karışımı kanallara ayırır; hat bunlardan ikisini tutar:
  vokaller ve geri kalan her şey (`no_vocals`). CUDA'da projenin kendi işçisi çağrı başına 4 parça işler ve her parçayı
  biriktirmeden önce GPU üzerinde iki kanala indirir.
- **Neden bu seçim:** müzik ve efektleri yeni sesin altında tutmak için ayırma gerekir. İki kanallı işçi işçi süresini
  yarıya indirdi ve 2.4 GB RAM kazandırdı ([ADR 0002](../adr/0002-demucs-batched-two-stem-worker.md)). Ayırma gerçek
  konuşmayı da silebilir; bu yüzden `auto_background` yalnız arka planın gerektiğine karar verdiğinde tanıma ham sesi
  kullanır ([ADR 0003](../adr/0003-automatic-background-detection.md)).
- **Nasıl oturur:** tanımadan önce, GPU kilidi altında kendi alt sürecinde çalışır (≈ 2.75 GB VRAM); `no_vocals` videoyla
  birlikte yeniden zamanlanır ve dublajın altına, konuşmada kısma (ducking) uygulanmadan karıştırılır; Demucs hatası işi
  transkripsiyondan önce durdurur ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)).
- Ayrıntılar: [source_audio_and_separation.md](../engineering/source_audio_and_separation.md) §2–§5 · [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) §6
