# Measurements / Ölçümler

[Türkçe](#türkçe) · Machine: NVIDIA GeForce GTX 1050 Ti 4 GB (Pascal, sm_61), driver 581.29, Intel Core i7-7700HQ,
16 GB RAM, Windows 10 64-bit, Python 3.11.14 (installed by `kur.ps1`), install folder on a 5400 rpm HDD. Date: before
the first public release. Everything below was produced on this machine; nothing is quoted from papers or other READMEs.

## Method

- **Install:** a clean copy of the repository (only the files git tracks; no `.venv`, no caches, no models) in a new
  folder, installed with `scripts\kur.ps1` exactly as [installation.md](installation.md) describes, started hidden with
  its output in a log file. Time = wall clock between the first and the last marker line; disk = sum of file sizes per
  folder after the install.
- **Dubs:** `dubla <video> --lisans-onay` with the settings shown in the table; time = wall clock of the whole command;
  every output checked with `ffprobe` (streams, duration, AI-dubbed tag) and a frame grab.
- **CI does not test the GPU.** GitHub Actions runs the test suite on CPU only (no NVIDIA runner). The GPU rows below
  were run by hand on the machine above.

## Results

| What | Profile | Result |
|---|---|---|
| Clean install, all default steps | CPU (`-Cpu`) | ≈ 38 min (packages ≈ 7 min; most of the rest was a slow model download); `dubla kontrol` READY |
| Clean install, `uv,python,paketler` | GPU | ≈ 13.5 min; `torch 2.8.0+cu128`, real CUDA kernel OK, READY |
| Disk after install | CPU | `.venv` 3.8 GB, models and tools 5.5 GB, uv cache 3.9 GB → 13.2 GB (9.3 GB without the cache) |
| Disk after install | GPU | `.venv` 7.8 GB, models and tools 5.5 GB, uv cache 7.8 GB → ≈ 22 GB (≈ 14 GB without the cache) |
| AGENTS.md §4 sample: `seslendir` (3 sentences) | CPU / GPU | 27 s / 18 s |
| AGENTS.md §4 sample: dub of the 9 s sample, `ceviri.arka_uc=yerel` | CPU / GPU | 528 s / 376 s, exit 0, AI-dubbed tag present |
| 30 s English clip, `segment_sync`, `preserve_background` (Demucs), speaker gender voices, segment subtitles, Claude Code translation | GPU | 744 s, exit 0 (ran in parallel with the next row) |
| 45 s English clip, `full_text`, `preserve_background`, one manual voice (M1), `single_pass_2`, segment subtitles, Claude Code translation | CPU | ≈ 1390 s, completed (ran in parallel with the previous row) |
| Short LLM translation test, 3 segments to French / Japanese, Codex CLI | – | 16.9 s / 12.8 s, output language check passed |

## Reading the numbers

- The first-install time is dominated by downloads (≈ 9.5 GB CPU, ≈ 13 GB GPU); on a fast connection expect well
  under the figures above.
- Dub times on this 4 GB Pascal card are several times the clip length; most of it is transcription, Demucs and
  model loading, not speech synthesis. Two jobs running at the same time share the CPU and slow each other down.
- The uv download cache (`runtime_assets/onbellek/uv`) is only needed for reinstalling; it can be deleted.

---

## Türkçe

Makine: NVIDIA GeForce GTX 1050 Ti 4 GB (Pascal, sm_61), sürücü 581.29, Intel Core i7-7700HQ, 16 GB RAM, Windows 10
64 bit, Python 3.11.14 (`kur.ps1` kurar), kurulum klasörü 5400 dev/dk HDD üzerinde. Tarih: ilk açık sürümden önce.
Aşağıdaki her şey bu makinede üretildi; makalelerden ya da başka README'lerden hiçbir şey aktarılmadı.

### Yöntem

- **Kurulum:** reponun temiz kopyası (yalnız git'in izlediği dosyalar; `.venv`, önbellek, model yok) yeni bir klasöre,
  [kurulum.md](kurulum.md)'de anlatıldığı gibi `scripts\kur.ps1` ile, gizli başlatılıp çıktısı günlük dosyasına yazılarak
  kuruldu. Süre = ilk ve son işaret satırı arasındaki duvar saati; disk = kurulumdan sonra klasör başına dosya boyutu toplamı.
- **Dublajlar:** tabloda yazan ayarlarla `dubla <video> --lisans-onay`; süre = komutun tamamının duvar saati; her çıktı
  `ffprobe` (akışlar, süre, AI-dubbed etiketi) ve bir kare görüntüsüyle denetlendi.
- **CI GPU'yu sınamaz.** GitHub Actions testleri yalnız işlemcide koşar (NVIDIA koşucusu yok). Aşağıdaki GPU satırları
  yukarıdaki makinede elle koşuldu.

### Sonuçlar

| Ne | Profil | Sonuç |
|---|---|---|
| Temiz kurulum, tüm varsayılan adımlar | İşlemci (`-Cpu`) | ≈ 38 dk (paketler ≈ 7 dk; kalanın çoğu yavaş model indirmesi); `dubla kontrol` READY |
| Temiz kurulum, `uv,python,paketler` | GPU | ≈ 13,5 dk; `torch 2.8.0+cu128`, gerçek CUDA çekirdeği tamam, READY |
| Kurulum sonrası disk | İşlemci | `.venv` 3,8 GB, modeller ve araçlar 5,5 GB, uv önbelleği 3,9 GB → 13,2 GB (önbelleksiz 9,3 GB) |
| Kurulum sonrası disk | GPU | `.venv` 7,8 GB, modeller ve araçlar 5,5 GB, uv önbelleği 7,8 GB → ≈ 22 GB (önbelleksiz ≈ 14 GB) |
| AGENTS.md §4 örneği: `seslendir` (3 cümle) | İşlemci / GPU | 27 sn / 18 sn |
| AGENTS.md §4 örneği: 9 sn örneğin dublajı, `ceviri.arka_uc=yerel` | İşlemci / GPU | 528 sn / 376 sn, çıkış 0, AI-dubbed etiketi var |
| 30 sn İngilizce parça, `segment_sync`, `preserve_background` (Demucs), konuşmacı cinsiyetine göre ses, segment altyazı, Claude Code çevirisi | GPU | 744 sn, çıkış 0 (sonraki satırla aynı anda koştu) |
| 45 sn İngilizce parça, `full_text`, `preserve_background`, tek elle seçilmiş ses (M1), `single_pass_2`, segment altyazı, Claude Code çevirisi | İşlemci | ≈ 1390 sn, tamamlandı (önceki satırla aynı anda koştu) |
| Kısa LLM çeviri denemesi, 3 segment Fransızca / Japonca, Codex CLI | – | 16,9 sn / 12,8 sn, çıktı dili denetimi geçti |

### Sayıları okumak

- İlk kurulum süresini indirmeler belirler (işlemci ≈ 9,5 GB, GPU ≈ 13 GB); hızlı bağlantıda yukarıdakinin epey altında kalır.
- Bu 4 GB Pascal kartta dublaj süresi parça süresinin birkaç katıdır; çoğu konuşma sentezi değil, yazıya dökme, Demucs ve
  model yüklemedir. Aynı anda koşan iki iş işlemciyi paylaşır ve birbirini yavaşlatır.
- uv indirme önbelleği (`runtime_assets/onbellek/uv`) yalnız yeniden kurulum içindir; silinebilir.
