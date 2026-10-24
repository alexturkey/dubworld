# Measurements / Ölçümler

[Türkçe](#türkçe) · Machine: 4 GB Pascal-class NVIDIA GPU (sm_61), 4-core laptop CPU, 16 GB RAM, HDD, Windows 10
64-bit, Python 3.11.14 (installed by `kur.ps1`). Date: before the first public release. Everything below was produced on this machine; nothing is quoted from papers or other READMEs.

## Method

- **Install:** a clean copy of the repository (only the files git tracks; no `.venv`, no caches, no models) in a new
  folder, installed with `scripts\kur.ps1` exactly as [installation.md](installation.md) describes, started hidden with
  its output in a log file. Time = wall clock between the first and the last marker line; disk = file sizes after the install, counted with a
  tool that counts a hard-linked file once (`du`). The uv download cache shares most of its files with `.venv` through
  hard links, so a file explorer that counts every link shows a larger total (≈ 22 GB for the GPU profile).
- **Dubs:** `dubla <video> --lisans-onay` with the settings shown in the table; time = wall clock of the whole command;
  every output checked with `ffprobe` (streams, duration, AI-dubbed tag) and a frame grab.
- **CI does not test the GPU.** GitHub Actions runs the test suite on CPU only (no NVIDIA runner). The GPU rows below
  were run by hand on the machine above.

## Results

| What | Profile | Result |
|---|---|---|
| Clean install, all default steps | CPU (`-Cpu`) | ≈ 38 min (packages ≈ 7 min; most of the rest was a slow model download); `dubla kontrol` READY |
| Clean install, all default steps (acceptance test, unattended assistant following AGENTS.md) | GPU | ≈ 44 min (`uv,python,paketler` ≈ 13.7 min; model download at ≈ 1 MB/s took most of the rest); `torch 2.8.0+cu128`, real CUDA kernel OK, READY; whole assistant session incl. sample dub 52.6 min |
| Disk after install | CPU | per-folder sum: `.venv` 3.8 GB, models and tools 5.5 GB, uv cache 3.9 GB → 13.2 GB (hard links counted per folder; the unique size was not measured) |
| Disk after install | GPU | hard links counted once: `.venv` 8.0 GB + `runtime_assets` 6.3 GB (models 4.7 GB, FFmpeg 0.2 GB, the rest of the uv cache) = ≈ 14.6 GB; the uv cache alone is 7.9 GB, most of it shared with `.venv` |
| AGENTS.md §4 sample: `seslendir` (3 sentences) | CPU / GPU | 27 s / 18 s |
| AGENTS.md §4 sample: dub of the 9 s sample, `ceviri.arka_uc=yerel` | CPU / GPU | 528 s / 376 s, exit 0, AI-dubbed tag present |
| 30 s English clip, `segment_sync`, `preserve_background` (Demucs), speaker gender voices, segment subtitles, Claude Code translation | GPU | 744 s, exit 0 (ran in parallel with the next row) |
| 45 s English clip, `full_text`, `preserve_background`, one manual voice (M1), `single_pass_2`, segment subtitles, Claude Code translation | CPU | ≈ 1390 s, completed (ran in parallel with the previous row) |
| Short LLM translation test, 3 segments to French / Japanese, Codex CLI | – | 16.9 s / 12.8 s, output language check passed |
| 40 s Japanese clip (shouting, little speech), `segment_sync`, automatic source language, Claude Code translation | GPU | 426 s, exit 0 (language detected as Japanese; the Japanese CTC model was downloaded once with `DUBLAJ_CEVRIMICI=1`) |
| 35 s Chinese clip, `segment_sync`, automatic source language, Claude Code translation | CPU | 383 s, exit 0 (Chinese CTC model downloaded once; Whisper returned only part of the speech, see the limits below) |
| Short LLM translation test, 2 segments to French / Japanese, Claude Code CLI | – | 8 s / 8 s, output language check passed |

## Reading the numbers

- The first-install time is dominated by downloads (≈ 9.5 GB CPU, ≈ 13 GB GPU); on a fast connection expect well
  under the figures above.
- Dub times on this 4 GB Pascal card are several times the clip length; most of it is transcription, Demucs and
  model loading, not speech synthesis. Two jobs running at the same time share the CPU and slow each other down.
- The dub can be longer than its source: in the acceptance test the AGENTS.md §4 sample (7.38 s source) became a
  9.27 s dub (+25.6 %, `Sure Farki` line of the job log). Speech is sped up at most 1.25× towards the segment time and
  the picture is retimed for the rest ([engineering/pipeline-flow.md](engineering/pipeline-flow.md)).
- The uv download cache (`runtime_assets/onbellek/uv`) is only needed for reinstalling; it can be deleted, but because
  it shares most files with `.venv` through hard links, deleting it frees much less than its own size.
- Limits seen: on the Chinese clip with burned-in subtitles faster-whisper (large-v3-turbo) returned two segments for ≈ 35 s of continuous speech and skipped the first ≈ 10 s; on the Japanese clip it turned shouting into a long "ああ…" line. Languages other than English and Turkish need their CTC model: Japanese and Chinese are pinned in the optional step `kur.ps1 -Adim hizalama-diller`, other languages need one deliberate run with `DUBLAJ_CEVRIMICI=1`; a missing model now stops the job right after language detection, before transcription (it used to cost the whole transcription, 185 s on the Japanese clip).

---

## Türkçe

Makine: 4 GB Pascal sınıfı NVIDIA GPU (sm_61), 4 çekirdekli dizüstü işlemcisi, 16 GB RAM, HDD, Windows 10 64 bit,
Python 3.11.14 (`kur.ps1` kurar). Tarih: ilk açık sürümden önce.
Aşağıdaki her şey bu makinede üretildi; makalelerden ya da başka README'lerden hiçbir şey aktarılmadı.

### Yöntem

- **Kurulum:** reponun temiz kopyası (yalnız git'in izlediği dosyalar; `.venv`, önbellek, model yok) yeni bir klasöre,
  [kurulum.md](kurulum.md)'de anlatıldığı gibi `scripts\kur.ps1` ile, gizli başlatılıp çıktısı günlük dosyasına yazılarak
  kuruldu. Süre = ilk ve son işaret satırı arasındaki duvar saati; disk = kurulumdan sonra dosya boyutları, sabit bağlı
  (hard link) dosyayı bir kez sayan bir araçla (`du`). uv indirme önbelleği dosyalarının çoğunu `.venv` ile sabit
  bağla paylaşır; her bağı ayrı sayan bir dosya gezgini daha büyük toplam gösterir (GPU profilinde ≈ 22 GB).
- **Dublajlar:** tabloda yazan ayarlarla `dubla <video> --lisans-onay`; süre = komutun tamamının duvar saati; her çıktı
  `ffprobe` (akışlar, süre, AI-dubbed etiketi) ve bir kare görüntüsüyle denetlendi.
- **CI GPU'yu sınamaz.** GitHub Actions testleri yalnız işlemcide koşar (NVIDIA koşucusu yok). Aşağıdaki GPU satırları
  yukarıdaki makinede elle koşuldu.

### Sonuçlar

| Ne | Profil | Sonuç |
|---|---|---|
| Temiz kurulum, tüm varsayılan adımlar | İşlemci (`-Cpu`) | ≈ 38 dk (paketler ≈ 7 dk; kalanın çoğu yavaş model indirmesi); `dubla kontrol` READY |
| Temiz kurulum, tüm varsayılan adımlar (kabul testi, AGENTS.md'yi izleyen gözetimsiz asistan) | GPU | ≈ 44 dk (`uv,python,paketler` ≈ 13,7 dk; kalanın çoğu ≈ 1 MB/sn model indirmesi); `torch 2.8.0+cu128`, gerçek CUDA çekirdeği tamam, READY; örnek dublaj dahil asistan oturumu 52,6 dk |
| Kurulum sonrası disk | İşlemci | klasör başına toplam: `.venv` 3,8 GB, modeller ve araçlar 5,5 GB, uv önbelleği 3,9 GB → 13,2 GB (sabit bağlar klasör başına sayıldı; tekil boyut ölçülmedi) |
| Kurulum sonrası disk | GPU | sabit bağlar bir kez sayılarak: `.venv` 8,0 GB + `runtime_assets` 6,3 GB (modeller 4,7 GB, FFmpeg 0,2 GB, uv önbelleğinin kalanı) = ≈ 14,6 GB; uv önbelleği tek başına 7,9 GB, çoğu `.venv` ile ortak |
| AGENTS.md §4 örneği: `seslendir` (3 cümle) | İşlemci / GPU | 27 sn / 18 sn |
| AGENTS.md §4 örneği: 9 sn örneğin dublajı, `ceviri.arka_uc=yerel` | İşlemci / GPU | 528 sn / 376 sn, çıkış 0, AI-dubbed etiketi var |
| 30 sn İngilizce parça, `segment_sync`, `preserve_background` (Demucs), konuşmacı cinsiyetine göre ses, segment altyazı, Claude Code çevirisi | GPU | 744 sn, çıkış 0 (sonraki satırla aynı anda koştu) |
| 45 sn İngilizce parça, `full_text`, `preserve_background`, tek elle seçilmiş ses (M1), `single_pass_2`, segment altyazı, Claude Code çevirisi | İşlemci | ≈ 1390 sn, tamamlandı (önceki satırla aynı anda koştu) |
| Kısa LLM çeviri denemesi, 3 segment Fransızca / Japonca, Codex CLI | – | 16,9 sn / 12,8 sn, çıktı dili denetimi geçti |
| 40 sn Japonca parça (bağırma, az konuşma), `segment_sync`, otomatik kaynak dili, Claude Code çevirisi | GPU | 426 sn, çıkış 0 (dil Japonca tespit edildi; Japonca CTC modeli bir kez `DUBLAJ_CEVRIMICI=1` ile indi) |
| 35 sn Çince parça, `segment_sync`, otomatik kaynak dili, Claude Code çevirisi | İşlemci | 383 sn, çıkış 0 (Çince CTC modeli bir kez indi; Whisper konuşmanın yalnız bir kısmını döndürdü, aşağıdaki sınırlara bakın) |
| Kısa LLM çeviri denemesi, 2 segment Fransızca / Japonca, Claude Code CLI | – | 8 sn / 8 sn, çıktı dili denetimi geçti |

### Sayıları okumak

- İlk kurulum süresini indirmeler belirler (işlemci ≈ 9,5 GB, GPU ≈ 13 GB); hızlı bağlantıda yukarıdakinin epey altında kalır.
- Bu 4 GB Pascal kartta dublaj süresi parça süresinin birkaç katıdır; çoğu konuşma sentezi değil, yazıya dökme, Demucs ve
  model yüklemedir. Aynı anda koşan iki iş işlemciyi paylaşır ve birbirini yavaşlatır.
- Dublaj kaynağından uzun olabilir: kabul testinde AGENTS.md §4 örneği (7,38 sn kaynak) 9,27 sn dublaj oldu (%+25,6,
  iş günlüğünde `Sure Farki` satırı). Konuşma segment süresine doğru en çok 1,25× hızlandırılır, kalanı için görüntünün
  süresi uzatılır ([muhendislik/hat_akisi.md](muhendislik/hat_akisi.md)).
- uv indirme önbelleği (`runtime_assets/onbellek/uv`) yalnız yeniden kurulum içindir; silinebilir, ama dosyalarının
  çoğunu `.venv` ile sabit bağla paylaştığı için silmek kendi boyutundan çok daha az yer açar.
- Görülen sınırlar: yakılmış altyazılı Çince parçada faster-whisper (large-v3-turbo) ≈ 35 sn kesintisiz konuşma için iki segment döndürdü ve ilk ≈ 10 sn'yi atladı; Japonca parçada bağırmayı uzun bir "ああ…" satırına çevirdi. İngilizce ve Türkçe dışındaki dillerin CTC modeli gerekir: Japonca ve Çince isteğe bağlı `kur.ps1 -Adim hizalama-diller` adımında sabitlidir, diğer diller bir kez bilerek `DUBLAJ_CEVRIMICI=1` ile çalıştırılır; eksik model artık işi dil tespitinden hemen sonra, yazıya dökmeden önce durdurur (eskiden bütün yazıya dökme süresi kaybediliyordu, Japonca parçada 185 sn).
