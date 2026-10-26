# 4 GB GPU'da (ya da GPU olmadan) çalıştırma

English: [../engineering/low_vram.md](../engineering/low_vram.md)

Uygulamalı bir rehber. Buradaki her değer, 4 GB VRAM'li (ekran kartı belleği), Pascal sınıfı bir GPU'da (ekran kartı
işlemcisi; compute capability (hesaplama yeteneği sürümü) 6.1) ve 16 GB sistem RAM'iyle ölçüldü ya da üretimde
kullanıldı. Her değerin gerekçesi bağlantı verilen sayfalarda.

## 1. Kurulum

- torch'u CUDA dizininden kur (kurucu bunu yapar). `--index-url` olmadan `pip install torch` CPU sürümünü verir; bazı
  paketler kurulum sırasında torch'u CPU sürümüne geri çeker; her kurulumdan sonra yeniden kontrol et:
  `python -c "import torch; print(torch.__version__, torch.cuda.is_available())"`.
- Pascal'da CUDA 13 sürümlerini kullanma (sm_61 desteği kaldırıldı). Linux'ta cu126 torch sürümü kullan: Linux cu128
  paketlerinde (wheel) sm_61 çekirdekleri yok, ama `torch.cuda.is_available()` yine de True döner. Kurucunun `kontrol`
  adımı (`scripts/kur.ps1 -Adim kontrol`) bu yüzden gerçek bir 64×64 CUDA matris çarpımı (matmul) çalıştırır.
- Model önbelleğini (`runtime_assets/model_cache`) SSD'de tut: HDD'de soğuk başlangıçlar (ilk yükleme) ağırlıkların
  her GB'ı için ≈ 12 s daha yavaştı.
- İsteğe bağlı CrisperWhisper Turbo modelinin dönüştürülmesi ≈ 4,5 GB boş RAM ister.

## 2. 4 GB'a sığan ayarlar

| Aşama | Ayar | Tepe |
|---|---|---|
| Ayrıştırma (isteğe bağlı) | `ses_temizligi.kip = "auto_background"` ya da `"original"`; Demucs `htdemucs`, batch 4, OOM'da (bellek yetmedi hatası) otomatik tek seferlik batch 1 yeniden denemesi, overlap 0.25, shifts 0, zorlanmış segment yok | 75 dk ses için ≈ 2,75 GB VRAM, ≈ 7,2 GB RAM |
| Transkripsiyon (konuşmayı yazıya dökme) | `transkripsiyon.motor = "auto"`; `hesap_tipi = "auto"` (kod `hesap_tipi_coz`: GPU'da CTranslate2 bildiriyorsa `float16`, değilse `int8`, değilse `float32`; bu Pascal kartta CTranslate2 4.8.3 `float16` bildirmez, yani `auto` = `int8`, ölçüldü). `float32` yalnız elle seçilince ve GPU'yu başka iş kullanmıyorken sığar | WhisperX turbo fp32 3.45 GB / int8 1.15 GB; CrisperWhisper Turbo int8 ≈ 1.4 GB |
| WhisperX | batch 1; VAD (konuşma etkinliği algılama) **CPU**'da; gerçek bir CUDA OOM'u otomatik olarak bir kez int8'de yeniden dener | – |
| Kelime hizalama | tanımadan sonra kendi sürecinde çalışır | dile göre ≈ 1.6–2.4 GB |
| Konuşmacı + cinsiyet | ayrı alt süreçler, art arda | her biri < 1 GB |
| TTS (metinden sese) | Supertonic **CPU**'da çalışır (4 şerit × 2 iş parçacığı); VoxCPM2 GPU'yu tek başına ister; 4 GB derlemesi kardeş reponun [docs/4gb.md](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi/blob/main/docs/4gb.md) sayfasında | – |
| Video | `video.cq = 26`; kodlayıcı otomatik seçilir (çalışıyorsa NVENC, yoksa x264) | – |

Bunu mümkün kılan kurallar:

1. **Aynı anda tek GPU işi.** Dublaj sırasında başka bir GPU programı çalıştırma; iki iş sığabilir ama her biri ≈ 2× yavaşlar.
2. **Her model ayrı bir süreçtir** ve çıkışta belleğini bırakır. Modelleri "hız için" bellekte sürekli tutmaya çalışma:
   sürekli açık bir CrisperWhisper işçisi %17 daha yavaş ölçüldü.
3. **Pascal'da fp16 daha hızlı değildir** (Tensor Core yok); int8 hızlıdır (≈ 4,4× fp32 işlem hacmi). bf16 öykünmeyle
   (emülasyon) çalışır: kaçın.
4. **Asla ayarlama:** `CUDA_LAUNCH_BLOCKING=1` ya da `torch.backends.cudnn.benchmark = True` (ölçümlerde her biri %19
   ile 200× arası maliyet getirdi).
5. **Ölçmeden batch boyutunu artırma:** WhisperX fp32'de batch 1, batch 2'den ≈ %41 daha hızlıydı.
6. **CUDA çıkarımı (inference, modelin çalıştırılması) sürerken NVENC ile kodlama yapma** (≈ 3,6× yavaş).

## 3. Belirtiler ve çözümler

| Belirti | Olası neden | Ne yapmalı |
|---|---|---|
| WhisperX'te `CUDA out of memory` | GPU'da başka bir bileşen (VAD) ya da başka bir program | başka süreçler için `nvidia-smi`'ye bak; iş bir kez int8'de yeniden dener; çalıştırma klasöründeki `gpu_diagnostics.jsonl` öncesi/sonrası belleği gösterir |
| Demucs'ta `torch.cuda.OutOfMemoryError` | batch 4'te uzun girdi | batch 1'de otomatik yeniden deneme; rapor `oom_fallback=true` gösterir |
| İş birden 2–8× yavaşladı, hata yok | VRAM paylaşılan sistem belleğine taştı (Windows) | Görev Yöneticisi → GPU → "Paylaşılan GPU belleği" büyüyor; diğer GPU programlarını kapat; int8 kullan |
| `no kernel image is available for execution on the device` | sm_61 içermeyen torch sürümü | cu118/cu126 sürümü kur (Linux: cu126) |
| CTranslate2 / faster-whisper `float16`'yı reddediyor | Pascal'da CT2 için fp16 hesaplama yok | `int8` ya da `float32` kullan (`hesap_tipi = "auto"` bunu yapar) |
| Uzun seste bir ONNX MatMul ≈ 10 GB istiyor (Parakeet) | bellek değil, 400 s'lik kodlayıcı girdi sınırı | motor zaten ≤ 399 s'de keser; bunu artırma |
| TTS sırasında birkaç iş boyunca bellek büyümeye devam ediyor | uzun ömürlü bir sürecin tuttuğu oturumlar | TTS her istek için bir alt süreç çalıştırır; kütüphaneyi gömüyorsan aynısını yap |
| `nvidia-smi` boş bellek gösteriyor ama ayırma başarısız | `nvidia-smi` bir sürecin CUDA bağlamını (≈ 700 MB) kaçırabilir | `torch.cuda.mem_get_info()` ile ölç |

## 4. NVIDIA GPU yok

- `--ayar genel.cihaz=cpu` (ya da CUDA olmayan makinede `auto`). CLI, torch içe aktarılmadan önce CUDA'yı gizler.
- Transkripsiyon: faster-whisper int8 (ya da İngilizce için Parakeet); Supertonic TTS zaten CPU'da
  çalışır; video libx264 kullanır. CPU'da ayrıştırma yavaştır; `ses_temizligi.kip = "original"` tercih et.
- Bu deponun uçtan uca CPU duman testi (temel çalışırlık testi) yerel Opus-MT çevirmeniyle tamamlandı
  (bulduğu sorunlar için bkz. [video_altyazi_ve_devam.md](video_altyazi_ve_devam.md) §7).

## 5. Çalıştırmadan önce ve sonra

- Önce: başka GPU süreci yok; boş RAM ≥ en büyük model tepesi + 1,5 GB.
- Sırasında: `torch.cuda.max_memory_reserved()` < 3.9 GB; paylaşılan GPU belleği büyümüyor.
- Sonra: `nvidia-smi` ≈ 0 MiB'ye döndü; geride kalmış python/ffmpeg süreci yok.

Daha fazlası: [gpu_bellek_ve_yalitim.md](gpu_bellek_ve_yalitim.md) ·
[kaynak_ses_ve_ayristirma.md](kaynak_ses_ve_ayristirma.md) · [transkripsiyon.md](transkripsiyon.md) ·
[crisperwhisper_turbo_ct2.md](crisperwhisper_turbo_ct2.md).
