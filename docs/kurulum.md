# Kurulum ve ortam haritası

[English](installation.md) (birincil sürüm) · Donanım matrisi: [donanim.md](donanim.md) · Düşük VRAM rehberi:
[muhendislik/dusuk_vram.md](muhendislik/dusuk_vram.md) · Ajan becerisi: `.claude/skills/kurulum-ve-donanim/SKILL.md`

Bu sayfa kurulumun tek başvuru belgesidir: makinenin ne istediği, hangi Python ortamlarının hangi sırayla kurulduğu,
her dosyanın nereye gittiği, kurulumun nasıl doğrulanıp güncellendiği ve kaldırıldığı. Aşağıdaki her komut
`scripts/kur.ps1` içinde ya da onun çağırdığı dosyalarda vardır. İfadelerin dayanağı yazılıdır: **denendi** (test
edilen yapılandırmada çalıştırıldı), **belgeye göre** (betikten, kilit dosyasından ya da model kartından okundu,
burada çalıştırılmadı), **denenmedi**.

Test edilen yapılandırma (bu sayfadaki bütün ölçümler): Windows 10 x64, 4 GB VRAM'li Pascal sınıfı NVIDIA GPU
(hesaplama yeteneği 6.1), 4 çekirdekli dizüstü işlemcisi, 16 GB RAM, HDD.

## 0. Yapay zekâ asistanınıza kurdurun

En kısa yol, programlama bilmeyenler için de: bilgisayarda komut çalıştırabilen bir yapay zekâ asistanını (Claude
Code, Codex, Gemini CLI ya da benzeri) açın ve şunu yapıştırın:

```text
https://github.com/alexturkey/DubWorld adresindeki video dublaj programını bu bilgisayara kur. Depodaki AGENTS.md dosyasını adım adım uygula, donanımımı kendin algıla, bana teknik soru sorma. `dubla kontrol` HAZIR deyip örnek dublaj çalışınca programın penceresini benim için aç.
```

Asistan [../AGENTS.tr.md](../AGENTS.tr.md)'deki akışı izler: makineyi ölçer (GPU ve VRAM, işlemci, RAM, disk), düz
dille kısa bir kurulum görüşmesi yapar (her parçanın ne işe yaradığı, disk ve süre bedeli, lisansı; hazır kurulumlar:
hızlı, bu makine için önerilen, tam), seçimi ve lisans onayını `ayarlar/` altına kaydeder, uygun `kur.ps1` adımlarını
çalıştırır, `dubla kontrol`'ü denetler (son satır `HAZIR / READY`), örnek dublaj yapar ve masaüstü arayüzünü açar. Kullanıcı için sade rehber: [baslarken.md](baslarken.md).

## 1. Sistem gereksinimleri

| Konu | Gereksinim | Not |
|---|---|---|
| İşletim sistemi | Windows 10 ya da 11, x64 | Kurulum betiği PowerShell 5.1+ ile çalışır (Windows'ta yerleşik). Linux / macOS: bölüm 11. |
| Python | **önceden gerekmez** | `kur.ps1`, sabit sürümlü `uv` 0.13.5 ile CPython **3.11.14**'ü repo klasörünün içine kurar. Paket Python 3.11 ister. İsteğe bağlı `voxcpm2` adımı kardeş reponun kurulum betiğini bu Python'u yalnız o süreç için `PATH` başına koyarak çalıştırır (bölüm 7); sistem `PATH`'i değişmez. |
| git | yalnız isteğe bağlı `crisper` ve `voxcpm2` adımları için | Taban kurulum reponun ZIP indirmesiyle de çalışır. |
| NVIDIA sürücüsü (GPU profili) | R570 ya da daha yeni (CUDA 12.8 çalışma zamanı); `nvidia-smi` çalışmalı | CUDA, PyTorch tekerleğinin içinde gelir (`torch 2.8.0+cu128`); **CUDA Toolkit, cuDNN ya da PATH değişikliği gerekmez**. NVIDIA'nın [Unix grafik sürücüsü kullanımdan kaldırma takvimi](https://forums.developer.nvidia.com/t/unix-graphics-feature-deprecation-schedule/60588) R580'i Maxwell, Pascal ve Volta için son sürücü serisi olarak adlandırır; Windows desteği orada yazmaz, bu yüzden eski kartta sürücü yükseltmeden önce NVIDIA sürüm notlarına bakın. |
| GPU | isteğe bağlı; Önerilen akış için 4 GB VRAM'li NVIDIA yeterli | Pascal (sm_61) ve sonrası. CUDA 13 derlemeleri Pascal'ı desteklemez (bölüm 12). AMD / Intel GPU'da işlemci profili kullanılır. |
| RAM | en az 8 GB (tahmin), 16 GB ile denendi | Test edilen yapılandırmada ölçülen tepeler: Supertonic ≈ 1,8 GB, Demucs 75 dk seste ≈ 7,2 GB, CrisperWhisper Turbo model dönüşümü ≈ 4,5 GB boş RAM. |
| ffmpeg | önceden gerekmez | FFmpeg **9.0.2** (sabit derleme, sha256 doğrulamalı) `runtime_assets/ffmpeg/bin` altına kurulur; CLI kendi süreci için onu `PATH`'in başına koyar. |
| Disk | aşağıdaki tablo; SSD önerilir | HDD'de soğuk model yüklemesi ağırlığın GB'ı başına ≈ 12 sn daha yavaş ölçüldü (muhendislik/dusuk_vram.md). |
| WSL2 + Ubuntu 24.04 | yalnız isteğe bağlı `crisper` adımı için | Bölüm 7. |

GPU çalışma matrisi (GPU profili; sürümler `requirements/gpu.txt` içinde özetle kilitli). 2026-10-25'te temiz kök
kurulumunda ve geliştirme ortamında `torch.backends.cudnn.version()`, `torch.cuda.get_arch_list()`, DLL dosya sürümleri ve
`cuobjdump --list-elf / --list-ptx` ile ölçüldü:

| Bileşen | Sabit sürüm | Kullandığı CUDA / cuDNN | Tekerlekteki GPU kodu |
|---|---|---|---|
| PyTorch + torchaudio | `2.8.0+cu128` | CUDA 12.8, cuDNN 9.10.2 (`torch/lib` içinde `cudnn64_9.dll`) | doğal çekirdek sm_61, 70, 75, 80, 86, 90, 100, 120 |
| CTranslate2 (faster-whisper 1.2.1) | `4.8.3` | CUDA 12, kendi `cudnn64_9.dll` 9.10.2.21 dosyası (PyTorch'unkiyle aynı yapı) | doğal sm_53–86 + sm_86 için PTX; yeni kartlar (sm_89, 90, 100, 120) sürücünün PTX JIT derlemesiyle çalışır, ilk koşu daha yavaştır |
| onnxruntime (Supertonic, EMA Lightning ONNX) | `1.31.0` | işlemci yapısı, CUDA yok | – |

Sonuç: Pascal'dan (GTX 10xx) Blackwell'e (RTX 50, sm_120) kadar PyTorch'un doğal çekirdeği var; RTX 50 elle koşulmadı
(kart yok), tablo kurulu tekerleklerden okundu. Maxwell ve öncesi (sm_5x) için PyTorch çekirdeği yok: işlemci profili
kullanılır (`kur.ps1 -Cpu`). Temiz kök GPU kurulumu faster-whisper'ı (CTranslate2) ve örnek dublajın tamamını Pascal
kartta çıkış kodu 0 ile koştu. Bu sabitlerden birini değiştirirken bütün satırları yeniden denetleyin: CTranslate2 4.x
CUDA 12 ve cuDNN 9 ister (yukarıda ölçüldü; CTranslate2 4.0 bunlara geçince Windows GPU kurulumları bozuldu, CTranslate2 issue #1630).

Profillere göre disk alanı:

| Profil / ek | Boyut | Dayanak |
|---|---|---|
| Varsayılan adımların modelleri ve araçları (`runtime_assets/`, uv önbelleği hariç) | ≈ 5,5 GB (manifest toplamı); temiz kurulumdan sonra ≈ 5,5 GB ölçüldü | belgeye göre (`scripts/modeller.json`) / denendi (temiz kök) |
| Ana ortam `.venv`, GPU profili | ≈ 7,8–8,0 GB | denendi (temiz kök, iki kurulum) |
| Ana ortam `.venv`, işlemci profili | ≈ 3,8 GB | denendi (temiz kök) |
| uv indirme önbelleği `runtime_assets/onbellek/uv` | tek başına ≈ 7,9 GB (GPU) / ≈ 3,9 GB (işlemci); dosyaların çoğu `.venv` ile ortak sabit bağdır (hard link), kurulumdan sonra silmek çok daha az yer açar | denendi (temiz kök) |
| **Toplam, GPU profili** | **başlamak için boş yer: 22 GB** (kurucu bunun altında uyarır); kurulumdan sonra kullanılan **≈ 14,6 GB**, sabit bağlar bir kez sayılarak (`du`; dosya gezgini ortak uv önbelleği dosyalarını iki kez saydığı için ≈ 22 GB gösterir); indirme ≈ 13 GB | denendi (temiz kök, kabul testi) |
| **Toplam, işlemci profili** | **başlamak için boş yer: 14 GB** (kurucu bunun altında uyarır); kurulumdan sonra klasör başına toplam ≈ 13,2 GB (tekil boyut ölçülmedi); indirme ≈ 9,5 GB | denendi (temiz kök) |
| `crisper` eki | ≈ 7 GB (torch cu126 ≈ 3 GB, model 1,6 GB + dönüştürülmüş 1,6 GB) | belgeye göre (kardeş STT reposu) |
| `voxcpm2` eki | ≈ 3,7 GB indirme (model 2,95 GB + CUDA çalışma DLL'leri + motor) | belgeye göre (kardeş TTS reposu) |
| `tts-ema` eki | ≈ 0,12 GB (ağırlık 34 MB, yerelde dışa aktarılan ONNX 79 MB, paketler ≈ 4 MB; PyTorch zaten `.venv`'de) | ölçüldü |
| `tts-xtts` eki | kendi PyTorch'u olan ayrı ortam (≈ 3–8 GB) + ilk kullanımda inen ağırlık | tahmin |
| `parakeet` eki | ≈ 0,7 GB model | belgeye göre (`kur.ps1`) |

## 2. Hızlı kurulum

1. Repoyu kısa ve boşluksuz bir yola indirin ya da klonlayın (ör. `C:\dublaj`).
2. Repo kökündeki **`kur.cmd`** dosyasına çift tıklayın (ya da terminalden çalıştırın). Varsayılan adımlarla
   `scripts\kur.ps1`'i çağırır ve sonda pencereyi açık tutar.
3. Son satır `KURULUM_OK` olana kadar bekleyin. İlk kurulum ≈ 13 GB (GPU profili) ya da ≈ 9,5 GB (işlemci profili) indirir; sonraki
   çalıştırmalar sha256'sı doğru olan her dosyayı atlar.
4. Başlatma: `arayuz.cmd`'ye çift tıklayın (masaüstü arayüzü); yerel web arayüzü `web.cmd`; komut satırı
   `.venv\Scripts\dubla.exe <video.mp4>`. Kurulum durursa pencerede `KURULUM DURDU / INSTALL STOPPED` ve ne
   yapılacağı yazar; `kur.cmd`'yi yeniden çalıştırın (bölüm 12).

Eşdeğer komutlar:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1          # otomatik: NVIDIA çalışıyorsa GPU, yoksa işlemci
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Cpu     # işlemci profilini zorla
kur.cmd -Cpu                                                                 # aynısı, başlatıcı üzerinden
```

`-ExecutionPolicy Bypass` yalnız bu süreç için geçerlidir; sistem ilkesi değişmez. Her kurulum betiğinde olduğu gibi
`scripts\kur.ps1` çalıştırılmadan önce okunabilir.

Kurulum betiğinin **yapmadıkları**: sistem `PATH`'ine, kayıt defterine, genel Python'a, NVIDIA sürücüsüne ya da
WSL'e dokunmaz; yönetici izni istemez (isteğe bağlı `crisper` adımı için kullanıcının bir kez çalıştırdığı
`wsl --install` hariç).

## 3. Profiller

| Profil | Kilit dosyası | PyTorch | Ne zaman seçilir | Önerilen akış motorları |
|---|---|---|---|---|
| `gpu` | `requirements/gpu.txt` (hash'li, `gpu.in`'den üretilir) | PyTorch indeksinden `2.8.0+cu128` | `nvidia-smi` çalışır ve GPU bildirirse | GPU'da faster-whisper large-v3-turbo + CTC, Opus-MT, Supertonic (tasarım gereği işlemcide), varsa NVENC |
| `cpu` | `requirements/cpu.txt` (`cpu.in`'den üretilir) | `2.8.0+cpu` | `-Cpu` verilirse ya da çalışan `nvidia-smi` yoksa | işlemcide faster-whisper int8, Supertonic, `ses_temizligi.kip=original`, libx264 |

İki kilit aynı doğrudan bağımlılıkları paylaşır (`requirements/temel.in`), yalnız PyTorch derlemesi farklıdır.
Seçilen profil `.venv/dublaj_profil.txt` dosyasına yazılır; isteğe bağlı adımlar onu okur. Çalışma anında
`genel.cihaz = auto` gerçek bir CUDA çekirdeği çalıştırır, düşerse gerekçesini günlüğe yazarak işlemciye geçer
(donanim.md).

## 4. Adım sırası

`kur.ps1 -Adim <liste>` adımların herhangi bir alt kümesini çalıştırır; betik içindeki sıra sabittir ve aşağıdaki
gibidir. Her adım başarıda bir işaret satırı yazar.

| # | Adım (`-Adim`) | Varsayılan | Ne yapar | Önce gereken | İşaret |
|---|---|---|---|---|---|
| 1 | `uv` | evet | uv 0.13.5'i (sha256 sabit ZIP) `runtime_assets/araclar/uv` altına indirir | ağ | `UV_OK` |
| 2 | `python` | evet | `uv python install 3.11.14 --no-bin` ile `runtime_assets/python` altına kurar | 1 | `PYTHON_OK` |
| 3 | `paketler` | evet | profili algılar, `.venv`'i kurar, `requirements/gpu.txt` ya da `cpu.txt`'yi `--require-hashes` ile, ardından bu paketi `--no-deps -e .` ile kurar (`dubla`, `dubla-gui`, `dubla-web`, `dubla-telegram` komutları) | 2 | `PAKETLER_OK` |
| 4 | `modeller` | evet | `scripts/modelleri_indir.py --adim supertonic,ceviri,stt,hizalama,konusmaci,ffmpeg` (bölüm 6) | 3 | `MODELLER_OK` |
| 5 | `demucs`, `youtube`, `parakeet`, `speechmatics` | hayır | `.venv`'e hash'li ekler (`requirements/ek_<ad>.txt`; işlemci profilinde varsa `ek_<ad>_cpu.txt`); `demucs` `htdemucs` ağırlığını da indirir (≈ 84 MB, sha256), `parakeet` modelini | 3 | `<AD>_OK` |
| 5b | `hizalama-diller` | hayır | Japonca ve Çince kaynaklar için CTC kelime zamanı modelleri (`modelleri_indir.py --adim hizalama-diller`, ≈ 2,5 GB, Apache-2.0) | 3 | `HIZALAMA-DILLER_OK` |
| 6 | `akilli-kare`, `galeri`, `telegram` | hayır | `.venv`'e `requirements/ek_<ad>.txt`'den ekler (hash'li) | 3 | `<AD>_OK` |
| 6b | `telegram-sunucu` | hayır | 2000 MB'a kadar teslim için yerel Telegram Bot API sunucusu (`dubla-telegram sunucu kur`: Docker kuruluysa Docker, yoksa resmî kaynağın derlemesi, Windows'ta WSL içinde); `.env`'de `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` gerekir ([tarif](tarifler/telegram_buyuk_dosya.md)); `telegram` adımını da çalıştırır | 6, Docker ya da WSL | `TELEGRAM_SUNUCU_OK` |
| 7 | `tts-xtts` | hayır | XTTS v2 için ayrı ortam (bölüm 5); `-TicariOlmayanKabul` ister | 3 | `XTTS_OK` |
| 8 | `crisper` | hayır | kardeş STT reposu üzerinden CrisperWhisper 2.0 Turbo + WSL ortamı; `-TicariOlmayanKabul` ister | 3, git, WSL2 | `CRISPER_MOTOR_OK`, `CRISPER_OK` |
| 9 | `voxcpm2` | hayır | kardeş TTS reposunu sabit commit'le klonlar ve kendi kurulum betiğini çalıştırır | git, NVIDIA (reponun Python 3.11.14'ünü kullanır) | `VOXCPM2_OK` |
| 9b | `tts-ema` | hayır | EMA Lightning (Türkçe TTS, GPU ya da işlemci): `requirements/ek_tts_ema.txt` (CPU profilinde `ek_tts_ema_cpu.txt`) `.venv`'e, `modelleri_indir.py --adim tts-ema` (sabit commit, sha256), ardından PyTorch ile karşılaştırılan yerel ONNX dışa aktarımı | 3 | `TTS_EMA_OK` |
| 10 | `kontrol` | evet | gerçek 64×64 CUDA matris çarpımı (GPU profilinde CUDA'lı derleme şart), ardından `dubla kontrol` | 3 | `KONTROL_OK` |

Betik her zaman `KURULUM_OK` ile biter. İsteğe bağlı adımlar sonradan istenen birleşimle eklenebilir, ör.
`-Adim demucs,youtube`. Adımlar yeniden çalıştırılabilir: hata sonrası yeniden çalıştırma eksik dosyalardan devam eder.

## 5. Ortam haritası

Uygulama her ağır modeli kendi sürecinde çalıştırır; bazı motorlar ayrıca **kendi Python ortamını** ister, çünkü sabit
bağımlılıkları ana kilitle bir arada bulunamaz. Ana hat tek ortamla çalışır.

| Ortam | Yer | Python | Kilit / sabit | Kullanan | Neden ayrı | Boyut | Kuran |
|---|---|---|---|---|---|---|---|
| **Ana** | `.venv/` | 3.11.14 (uv) | `requirements/gpu.txt` ya da `cpu.txt` (hash), ekler `requirements/ek_*.txt` | CLI, GUI, web, Telegram botu, faster-whisper, WhisperX, CTC kelime hizalama, Opus-MT, Supertonic, 3D-Speaker, cinsiyet sınıflandırıcı, Demucs, Parakeet, Speechmatics/ElevenLabs istemcileri, yt-dlp, gallery-dl, OpenCV | – (taban) | GPU'da ≈ 7,8 GB, işlemcide ≈ 3,8 GB | `-Adim paketler` |
| **XTTS v2** | `runtime_assets/tts_motorlari/xtts/venv/` | 3.11.14 (uv) | `requirements/xtts_venv_gpu.txt` / `xtts_venv_cpu.txt` (hash, PyTorch dahil) | `ses.motor = xtts` (`.env`'e yazılan `DUBLAJ_XTTS_PYTHON` üzerinden alt süreç) | `coqui-tts`'i ve ≈ 80 paketlik bağımlılık ağacını, ayrıca ticari olmayan motoru kilitli ana ortamın dışında tutar | ölçülmedi | `-Adim tts-xtts -TicariOlmayanKabul` |
| **CrisperWhisper Turbo çalışma ortamı (WSL)** | `runtime_assets/transkripsiyon_motorlari/crisperwhisper_turbo_ct2/.venv_wsl_ct2/` (WSL2 içinde Linux venv) | 3.12 (Ubuntu 24.04 sistem Python'u) | `src/dublaj_hatti/bolum_20_transkripsiyon/crisperwhisper_turbo_ct2_motoru/requirements/requirements_wsl_ct2.lock.txt` (sabit sürüm, hash yok; `pip check` geçmeli) | `transkripsiyon.motor = crisperwhisper_turbo_ct2` | CTranslate2 çatalı `ctranslate2-crisperwhisper` yalnız Linux tekerleği yayımlar; CUDA pip `nvidia-cublas-cu12` 12.9'dan gelir | ≈ 1 GB (tahmin) | `-Adim crisper` |
| **CrisperWhisper dönüşüm ortamı (WSL)** | `runtime_assets/transkripsiyon_motorlari/stt_repo/.venv/` | Ubuntu Python'u (kardeş repoya göre 3.10–3.12) | kardeş STT reposunun `requirements.txt`'si + PyTorch cu126 | modelin bir kerelik indirilmesi ve CTranslate2'ye dönüştürülmesi; çalışma anında kullanılmaz | dönüşüm PyTorch + Transformers ister; Linux cu128 tekerleklerinde Pascal çekirdeği olmadığından cu126 kullanılır | ≈ 3 GB + model 3,2 GB | `-Adim crisper` (kardeş kurulum betiği) |
| **VoxCPM2** | `runtime_assets/tts_motorlari/voxcpm2/repo/.venv/` (+ motor, model, CUDA DLL'leri `.../voxcpm2/kok/` altında) | reponun Python 3.11.14'ü (adım için `PATH` başına konur) | kardeş TTS reposunun `requirements.txt`'si (numpy, soundfile); model Python'da değil C++ motorunda (audio.cpp) çalışır | `ses.motor = voxcpm2` | kendi motor ikilisi ve CUDA 12.8 çalışma DLL'leri olan ayrı proje | ≈ 3,7 GB | `-Adim voxcpm2` |
| **Moonshine** (elle) | `src/dublaj_hatti/bolum_20_transkripsiyon/moonshine_medium_streaming_motoru/.venv/` ya da `DUBLAJ_MOONSHINE_ROOT` / `DUBLAJ_MOONSHINE_PYTHON` | 3.10+ | `moonshine-voice==0.0.73` (motor, paketle gelen `moonshine.dll` ve `onnxruntime.dll`'nin sha256'sını doğrular) | `moonshine_medium_streaming_en` (deneysel) | kendi yerel çalışma zamanını taşır, numpy'ı ana kilitten bağımsız sabitler | ≈ 0,15 GB | elle, docs/motorlar/moonshine_medium_streaming_en.md |
| **CrisperWhisper 2.0 Medium** (elle) | `src/dublaj_hatti/bolum_20_transkripsiyon/crisperwhisper2_medium_motoru/.venv/` ya da `DUBLAJ_CRISPERWHISPER_ROOT` / `DUBLAJ_CRISPERWHISPER_PYTHON` | 3.10+ | başvuru birleşimi: `crisperwhisper==2.0.1`, `transformers==5.14.1`, `torch 2.6.0+cu118`, numpy 2.2.6, model anlık görüntüsü `ca981a99…` | `crisperwhisper2_medium` | Transformers 5.x ana kilitle (Transformers 4.57.6) çakışır | ölçülmedi | elle, docs/motorlar/crisperwhisper2_medium.md |
| **RVC** (elle) | resmî RVC WebUI klonu, `DUBLAJ_RVC_KOK` (+ `DUBLAJ_RVC_PYTHON`) | RVC WebUI'nin istediği | kendi gereksinimleri | `ses.rvc_model` son işlemi | kendi PyTorch'u ve numpy'ı olan ayrı üst kaynak proje | – | elle, docs/motorlar/rvc.md |

Python ortamı olmayanlar: **whisper.cpp** (`whisper_cpp_cpu_align`) resmî hazır `whisper-cli.exe` ikilisidir ve
`runtime_assets/transkripsiyon_motorlari/whisper_cpp_cpu_align/` altına konur (ya da `DUBLAJ_WHISPER_CPP_CPU_ROOT`);
**FFmpeg** `runtime_assets/ffmpeg/bin` altındaki ikilidir. Çeviri arka uçlarının kullandığı Codex ve Claude Code
CLI'larını kullanıcı kurar; `PATH` üzerinden bulunur (ya da `CODEX_BRIDGE_CODEX_BIN`, `CODEX_BRIDGE_CLAUDE_CLI`).

Haritanın kuralı: sabitleri (PyTorch, numpy, Transformers, ONNX Runtime) ana kilitten farklı olan yeni bir motor kendi
ortamını alır ve bir `DUBLAJ_*_PYTHON` değişkeni üzerinden alt süreç olarak çağrılır; `.venv`'e zorla kurulmaz.
`DUBLAJ_WHISPERX_PYTHON` aynı nedenle vardır, ama WhisperX 3.8.6 ana kilide sığdığı için varsayılanı ana yorumlayıcıdır.

Birden fazlası isteniyorsa önerilen sıra: ana (`paketler`, `modeller`) → `kontrol` → hash'li ekler (`demucs`,
`parakeet`, …) → ayrı ortamlar (`tts-xtts`, `voxcpm2`, `crisper`) → elle kurulan motorlar. Her ayrı ortam `.venv`'e
dokunmadan tek başına kaldırılabilir.

## 6. Modeller ve çevrimdışı kullanım

- **Tek kaynak:** `scripts/modeller.json` (commit'e ya da sürüme sabit adres, hedef yol, boyut, sha256, lisans,
  kaynak). `python scripts/modelleri_indir.py --liste` listeyi yazar. Repoda hiçbir ağırlık yoktur.
- **Varsayılan adımlar:** `supertonic` (≈ 0,40 GB), `ceviri` Opus-MT en→tr (≈ 0,47 GB), `stt` faster-whisper
  large-v3-turbo (≈ 1,62 GB), `hizalama` wav2vec2 CTC en + tr (≈ 1,64 GB), `konusmaci` 3D-Speaker + cinsiyet
  sınıflandırıcı (≈ 1,29 GB), `ffmpeg` (≈ 0,12 GB ZIP). İsteğe bağlı: `parakeet`, `crisper` (yalnız yapılandırma
  dosyası; ağırlık kardeş repo üzerinden gelir).
- **Nereye:** `runtime_assets/model_cache/` (çevrimdışı çözüm için `refs/main` yazılmış Hugging Face önbellek düzeni),
  `runtime_assets/tts_motorlari/`, `runtime_assets/ffmpeg/`, `runtime_assets/indirilen/`. İndirici
  `runtime_assets/` dışına hedefi reddeder.
- **Doğrulama:** yalnız HTTPS, `scripts/modelleri_indir.py` alan adı izin listesi: `huggingface.co`, `github.com`, `objects.githubusercontent.com`, `raw.githubusercontent.com`, `download.pytorch.org`, `www.modelscope.cn`, `dl.fbaipublicfiles.com` (Meta, Demucs ağırlığı); Python paketleri hash kilitli `requirements/*.txt` ile PyPI'dan ve PyTorch dizininden gelir; her dosya önce
  `<ad>.part` olarak iner, boyut ve sha256 denetlenir, sonra yerine taşınır. Uyuşmazlıkta yarım dosya silinir ve
  beklenen ile gelen özet yazılarak durulur. Doğru olan mevcut dosya atlanır.
- **Çalışma anında çevrimdışı:** CLI `HF_HUB_OFFLINE=1` ayarlar, `HF_HOME` / `TORCH_HOME`'u
  `runtime_assets/model_cache`'e yöneltir; iş sırasında hiçbir şey inmez. `DUBLAJ_CEVRIMICI=1` çalışma anı indirmesine
  izin verir (yalnız modeli manifestte olmayan motorlar için gerekir). Demucs ağırlığı ya da CTC modeli eksikse iş o aşama
  başlamadan, mesajda kurulum adımıyla durur (kaynak dil otomatikse dil tespitinden hemen sonra, yazıya dökmeden önce).
- **Ağsız makine (denenmedi):** bağlantılı bir makinede aynı mutlak yola kurulur, ardından repo klasörünün tamamı
  kopyalanır. Ortam mutlak yol saklar (`.venv/pyvenv.cfg`); farklı yolda `-Adim python,paketler` yeniden çalıştırılır,
  bu da ağ olmadan tekerlek önbelleğini (`runtime_assets/onbellek/uv`) ve `UV_OFFLINE=1`'i gerektirir.

## 7. İsteğe bağlı ekler

| `-Adim` | Ne kurar | Nereye | Lisans notu | Onay bayrağı |
|---|---|---|---|---|
| `demucs` | Demucs 4.0.1 (`ses_temizligi.kip = clean / preserve_background`) + sabit `htdemucs` ağırlığı | `.venv`, `runtime_assets/model_cache/torch/` | MIT (kod ve ağırlık) | – |
| `hizalama-diller` | Japonca ve Çince kaynaklar için wav2vec2 CTC modelleri (diğer kaynak diller: `DUBLAJ_CEVRIMICI=1`; WhisperX'in fr/de/es/it varsayılanları CC BY-NC 4.0) | `runtime_assets/model_cache/huggingface/` | Apache-2.0 | – |
| `youtube` | yt-dlp (bağlantı girişi) | `.venv` | Unlicense; yalnız sahibi olunan ya da indirme izni olan içerik (ETHICS.md) | – |
| `parakeet` | sherpa-onnx + Parakeet Unified EN 0.6B INT8 (İngilizce, işlemci) | `.venv`, `runtime_assets/model_cache/` | NVIDIA Open Model License (şartlı ticari kullanım) | – |
| `speechmatics` | Speechmatics toplu istemcisi | `.venv` | bulut hizmeti, `.env`'de kullanıcının kendi anahtarı; ses makineden çıkar | – |
| `akilli-kare` | OpenCV headless (`video.akilli_kare`) | `.venv` | Apache-2.0 | – |
| `galeri` | gallery-dl (yalnız ayrı süreç olarak çağrılır) | `.venv` | GPL-2.0-only; içe aktarılmaz | – |
| `telegram` | python-telegram-bot (uzaktan kumanda botu, belirteç yalnız `.env`'de) | `.venv` | LGPL-3.0-only, değiştirilmeden kütüphane olarak | – |
| `telegram-sunucu` | yerel Telegram Bot API sunucusu (`tdlib/telegram-bot-api`, sabit commit; hazır imaj sabit özetle) | Docker kapsayıcısı `dubworld-telegram-bot-api` ya da `runtime_assets/araclar/telegram-bot-api` (WSL: `/opt/dubworld-telegram-bot-api`) | BSL-1.0; kendi `api_id` / `api_hash` değerleriniz `.env`'de | – |
| `tts-xtts` | ayrı ortamda coqui-tts + PyTorch; `.env`'e `DUBLAJ_XTTS_PYTHON` yazar ve lisans onayını kaydeder | `runtime_assets/tts_motorlari/xtts/venv` | XTTS v2 ağırlıkları: Coqui Public Model License, **ticari olmayan**; ağırlık ilk kullanımda Coqui'den iner | `-TicariOlmayanKabul` |
| `crisper` | kardeş STT reposu üzerinden sabit commit'le CrisperWhisper 2.0 Turbo (13. motor); CTranslate2 dönüşümü; WSL çalışma ortamı | `runtime_assets/transkripsiyon_motorlari/` | ağırlık **ticari olmayan** (model kartı) | `-TicariOlmayanKabul` |
| `voxcpm2` | sabit commit'le kardeş TTS reposu ve kurulum betiği (model, CUDA 12.8 çalışma DLL'leri, hazır motor, Python paketleri) | `runtime_assets/tts_motorlari/voxcpm2/` | THIRD_PARTY.md'ye göre | – |
| `tts-ema` | EMA Lightning 1.1.0 + normalizer-tr, sabit ağırlık, yerelde dışa aktarılan ONNX (`ses.motor = ema_lightning`) | `.venv`, `runtime_assets/tts_motorlari/ema_lightning/` | Apache-2.0 (kod ve ağırlık); tek sentetik ses, YZ etiketi kalır | – |

Başka repo kullanan adımların ön koşulları:

- `crisper`: **Ubuntu 24.04**'lü WSL2 (`wsl --install -d Ubuntu`, bir kez, yönetici; ardından kullanıcıyı oluşturmak
  için Ubuntu bir kez açılır), Windows'ta R570+ NVIDIA sürücüsü (`nvidia-smi` WSL içinde çalışmalı), git. Çalışma
  kilidi numpy 2.5.2'yi sabitler, bu sürüm Python ≥ 3.12 ister (PyPI `Requires-Python`); Ubuntu 22.04 Python 3.10 ile geldiği için çalışma
  ortamına uygun değildir. `scripts/crisper_kur.py` indirmeden önce WSL'i ve dağıtımın `python3` sürümünü denetler, uymuyorsa
  açık mesajla durur. Dağıtım adı `--dagitim` ile verilir (varsayılan `Ubuntu`).
- `voxcpm2` ve `crisper`: repo adresi yer tutucuları doldurulmamışsa `DUBLAJ_TTS_REPO_URL` / `DUBLAJ_STT_REPO_URL`
  ayarlanır (README "Aile"). Commit `kur.ps1` içinde sabittir; hangi adres verilirse verilsin o commit kurulur.
- `voxcpm2`: git ve NVIDIA GPU ister. Kardeş kurulum betiği `py -3`, `python` ya da `python3` arar (64 bit, 3.10+);
  `kur.ps1` yalnız bu adım için kendi Python 3.11.14'ünü `PATH` başına koyar, sistem Python'u gerekmez.

Kurulum adımı olmayan motorlar (elle; `docs/motorlar/` altındaki sayfalarına bakın): `moonshine_medium_streaming_en`,
`crisperwhisper2_medium`, `whisper_cpp_cpu_align`, `rvc`. Bulut motorları yalnız `.env`'de anahtar ister
(`.env.example` adları listeler).

## 8. Kurulumu doğrulama

`kontrol` adımı varsayılan kurulumun sonunda kendiliğinden çalışır. İstenildiği zaman da çalıştırılabilir:

```powershell
.venv\Scripts\dubla.exe kontrol            # okunur çıktı
.venv\Scripts\dubla.exe kontrol --json     # makine okur
```

Test edilen yapılandırmada, EMA Lightning eki kuruluyken örnek çıktı (`--ayar genel.cihaz=cpu` ile işlemci zorlandı;
uzun satırlar `...` ile kısaltıldı). Kurulumdan sonraki ilk çalıştırma sonrakilerden belirgin uzun sürebilir, çünkü
kütüphaneler diskten soğuk okunur (HDD'den soğuk `import torch` 38–44 sn ölçüldü,
[muhendislik/gpu_bellek_ve_yalitim.md](muhendislik/gpu_bellek_ve_yalitim.md)):

```text
DubWorld 0.1.0 · Python 3.11.14
  donanım.cuda: False
  donanım.torch: 2.8.0+cu128
  donanım.cihaz: cpu
  donanım.whisper_hesap_tipi: int8
  ffmpeg: <repo>\runtime_assets\ffmpeg\bin\ffmpeg.exe
  stt: faster-whisper=var, faster_whisper_ctc=var, whisperx=var, crisperwhisper_turbo_ct2=yok, ...
  ceviri: yerel=var, codex=var, claude_code=var, gemini_2_5_flash=yok, ...
  tts: supertonic=var, voxcpm2=yok, ema_lightning=var, xtts=yok
  ek: demucs=yok, yt_dlp=yok, konusmaci_ayrimi=var, cinsiyet_siniflandirici=var, segment_cinsiyet_kipi=var, ...
  deneysel / experimental: moonshine_medium_streaming_en (...)
  telegram yerel sunucu: kapalı (bulut Bot API, en çok 50 MB; 2 GB için: dubla-telegram sunucu kur)
  tts ema_lightning: GPU (torch) + işlemci ONNX; auto şimdi: onnx-cpu (GPU yok: işlemci)
  hizalama (CTC): en=var, tr=var
SONUÇ / RESULT: Önerilen akış HAZIR / recommended flow READY · arayüz / app: arayuz.cmd
```

Nasıl okunur:

| Satır | Varsayılan kurulumdan sonra beklenen | Değilse |
|---|---|---|
| `Python` | `3.11.14` | komutu başka bir yorumlayıcı çalıştırıyor; `.venv\Scripts\dubla.exe` kullanın |
| `donanım.torch` | `2.8.0+cu128` (GPU profili) ya da `2.8.0+cpu` | yanlış tekerlek: bölüm 12, satır 6 |
| `donanım.cuda` / `donanım.cihaz` | çalışan NVIDIA GPU'da `True` / `cuda`, aksi halde `False` / `cpu` | GPU var ama `False`: sürücü ya da işlemci tekerleği |
| `ffmpeg` | `runtime_assets\ffmpeg\bin` içinde bir yol | `-Adim modeller` (FFmpeg model adımının parçasıdır) |
| `stt` / `ceviri` / `tts` / `ek` | `var` = kurulu, `yok` = kurulu değil; Önerilen akış için `faster-whisper`, `whisperx`, `yerel`, `supertonic`, `konusmaci_ayrimi`, `cinsiyet_siniflandirici` `var` olmalı | eki kurun (bölüm 7); bulut motorları yalnız anahtarları ayarlıysa `var` gösterir |
| `deneysel` | bilgi | – |
| `SONUÇ / RESULT` (son satır) | `Önerilen akış HAZIR / recommended flow READY` | `EKSİK / MISSING: <parçalar>`: kurulumu yeniden çalıştırın (`kur.cmd`); üstünde `not / note` satırı varsa GPU için kurulmuş ama GPU çalışmıyor (bölüm 12, satır 6–7) |

`codex` / `claude_code`, ilgili CLI `PATH`'te bulunursa `var` gösterir. `kur.ps1` içindeki GPU denetimi tek başına
`torch.cuda.is_available()`'a güvenmez: bazı derlemeler eski GPU'lar için çekirdek taşımadan `True` döndürür; bu
yüzden gerçek bir matris çarpımı yapılır.

## 9. Güncelleme

```powershell
git pull                                                                      # ya da yeni ZIP'teki dosyalarla değiştirin
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1          # varsayılan adımları yeniden çalıştırır
```

Yeni ya da değişen modeller ve kilitler uygulanır; değişmeyen dosyalar atlanır. `uv pip install -r` paket ekler ve
sürüm değiştirir, ama yeni kilitte artık olmayan paketleri kaldırmaz; birebir eşleşme için `.venv` silinip
`-Adim paketler,kontrol` çalıştırılır. Daha önce kurulan isteğe bağlı adımlar tekrarlanır (ör. `-Adim demucs`).
Bakımcılar kilit dosyalarını yalnız `scripts\kilitle.ps1` ile yeniden üretir (elle düzenlenmez).

## 10. Kaldırma

Her şey repo klasörünün içindedir; klasörü silmek kurulumu kaldırır. Ayrı ayrı kaldırılabilen parçalar:

| Klasör / dosya | İçerik | Silmek güvenli mi |
|---|---|---|
| `.venv/` | ana ortam | evet; `-Adim paketler` ile yeniden kurulur |
| `runtime_assets/onbellek/` | uv indirme önbelleği | evet, kurulumdan sonra istenildiği zaman |
| `runtime_assets/model_cache/`, `runtime_assets/indirilen/`, `runtime_assets/ffmpeg/` | modeller, FFmpeg | evet; `-Adim modeller` ile yeniden kurulur |
| `runtime_assets/python/`, `runtime_assets/araclar/` | CPython 3.11.14, uv | evet, `.venv` ile birlikte |
| `runtime_assets/tts_motorlari/xtts/` | XTTS ortamı | evet; `.env`'den `DUBLAJ_XTTS_PYTHON` da silinir |
| `runtime_assets/tts_motorlari/voxcpm2/` | VoxCPM2 reposu, ortamı, motoru ve modeli | evet |
| `runtime_assets/transkripsiyon_motorlari/` (`stt_repo`, `stt_kok`, `crisperwhisper_turbo_ct2`) | CrisperWhisper kaynakları, dönüşüm ve çalışma ortamları, model | evet; WSL dağıtımının kendisine dokunulmaz |
| `cikti/` (ya da `DUBLAJ_OUTPUT_DIR`) | **üretilen çıktılar** ve iş veritabanı `_is_deposu/isler.sqlite3` | yalnız çıktılara artık gerek yoksa |
| `.env`, `ayarlar/kullanici.toml`, `ayarlar/lisans_onaylari.json` | anahtarlar, kişisel ayarlar, lisans onayları | yalnız bilerek |

Klasör dışında: sistem geçici klasöründeki makine geneli GPU kilit klasörü `dublaj_hatti_kaynak_kilitleri` (ya da
`DUBLAJ_KILIT_KLASORU`) yalnız küçük kilit dosyaları içerir. Elle kurulan motorlar (RVC WebUI, repo dışındaki
Moonshine ya da CrisperWhisper Medium ortamı) ve WSL kendi yollarıyla kaldırılır.

## 11. Linux ve macOS

| Platform | Durum |
|---|---|
| Windows 10/11 x64 | destekleniyor ve denendi (işlemci profili uçtan uca; GPU profili Pascal sınıfı GPU'da) |
| Linux x64 | **denenmedi**; kurulum betiği ve Linux kilit dosyası yok. Paketin kendisi düz Python 3.11'dir (`pyproject.toml` Linux'u listeler). |
| macOS | **denenmedi**; kurulum betiği yok. CUDA olmadığından yalnız işlemci. |

Linux için elle adımlar (denenmedi; komutlar `pyproject.toml` eklerini izler, sürümler kilitli değildir):

```bash
python3.11 -m venv .venv
.venv/bin/pip install --index-url https://download.pytorch.org/whl/cu126 torch==2.8.0 torchaudio==2.8.0   # Pascal: cu126; işlemci: /whl/cpu
.venv/bin/pip install -e ".[onerilen]"
.venv/bin/python scripts/modelleri_indir.py --adim supertonic,ceviri,stt,hizalama,konusmaci
# ffmpeg dağıtımdan (manifestteki FFmpeg Windows ikilisidir): sudo apt install ffmpeg
.venv/bin/dubla kontrol
```

Linux'ta Pascal GPU için **cu126** PyTorch derlemesi kullanılır: Linux cu128 tekerlekleri sm_61 çekirdeği taşımaz,
yine de `torch.cuda.is_available()` `True` döndürür (muhendislik/gpu_bellek_ve_yalitim.md). Raporlar ve Linux kilit
dosyası çekme isteği (PR) olarak kabul edilir.

## 12. Sık kurulum hataları

Bütün satırlar geliştirme sırasında kaydedilmiş gerçek hatalardan gelir (mühendislik sayfaları ve borç günlüğü).

| # | Belirti | Neden | Çözüm |
|---|---|---|---|
| 1 | Konuşmacı ayrımı başlarken `No module named pkg_resources` | ModelScope 1.33 `pkg_resources` içe aktarır; setuptools 81+ onu kaldırdı | kilit `setuptools==80.9.0` sabitler; `.venv` içinde setuptools yükseltilmez |
| 2 | ModelScope'tan `No module named datasets` | `modelscope.pipelines` `MsDataset` ister | kilit `datasets==3.1.0` sabitler; `-Adim paketler` ile yeniden kurulur |
| 3 | fastcluster: `_ARRAY_API not found` / numpy ABI hatası | fastcluster 1.2.6 tekerlekleri numpy 1.x'e göre derlenmiş; kilit numpy 2.4.6 kullanır | kilit `fastcluster==1.3.0` sabitler; `.venv`'e kilitsiz tek paket `pip install` edilmez |
| 4 | uv kilitteki bir paketi çözemiyor (ör. `filelock`) | kilit iki indeks yazar (PyPI + PyTorch), uv adı bulduğu ilk indekste durur | `kur.ps1` `--index-strategy unsafe-best-match` verir; hash zorunlu kaldığı için güvenlidir. Elle `uv pip install -r requirements\...` yaparken aynı bayrak kullanılır |
| 5 | `kur.ps1` çalışırken bozuk Türkçe harf ya da ayrıştırma hatası | Windows PowerShell 5.1 BOM'suz UTF-8'i ANSI okur | betik BOM'lu UTF-8 kaydedilmiştir; gösterildiği gibi `-File` ile çalıştırılır, konsola yapıştırılmaz, düzenlenirken BOM korunur |
| 6 | `torch denetimi başarısız` ya da `GPU profili kuruldu ama torch CUDA'sız` | GPU profiline işlemci PyTorch tekerleği kurulmuş (ör. düz `pip install torch`) | `-Adim paketler,kontrol` yeniden çalıştırılır; PyTorch CUDA indeksi olmadan kurulmaz |
| 7 | `no kernel image is available for execution on the device` / `sm_61 is not compatible` | PyTorch derlemesinde GPU mimarisinin çekirdeği yok: CUDA 13 derlemeleri Pascal'ı bıraktı; Linux cu128 tekerleklerinde sm_61 yok | Windows: kilitteki `cu128` derlemesi (Pascal'da denendi); Linux: `cu126`. Denetim `torch.cuda.get_arch_list()` ve `torch.cuda.get_device_capability(0)` ile; `nvidia-smi`'nin gösterdiği `CUDA Version` kartın değil sürücünün üst sınırıdır |
| 8 | Video kodlama: `Driver does not support the required nvenc API version` / NVENC yok | sürücünün NVENC API'si FFmpeg 9.0.2'nin istediğinden eski ya da GPU'da NVENC yok | kendiliğinden: tek deneme kodlaması, ardından gerekçesi günlüğe yazılarak libx264. Zorlamak için `DUBLAJ_VIDEO_KODLAYICI=x264` (ya da `nvenc`, `auto`); sürücü güncellemesi NVENC'i geri açar |
| 9 | `Requested float16 compute type, but the target device or backend do not support efficient float16 computation` | Pascal'da hızlı fp16 yok; CTranslate2 orada `float32`, `int8`, `int8_float32` sunar | `transkripsiyon.hesap_tipi = auto` bırakılır (int8 / fp32 seçilir); `float16` zorlanmaz |
| 10 | İndirmede `sha256 tutmadı` | yarım kalan indirme, araya giren vekil sunucu ya da uzak dosya değişmiş | aynı adım yeniden çalıştırılır (yarım dosya silinir); sürerse sabit kaynak değişmiştir: bildirilir, hash asla elle değiştirilmez |
| 11 | `Kardeş repo adresi ayarlı değil` | kardeş reponun adres yer tutucusu doldurulmamış | `DUBLAJ_TTS_REPO_URL` ya da `DUBLAJ_STT_REPO_URL` ayarlanır (README "Aile") |
| 12 | `crisper`: `wsl.exe yok` ya da WSL ortamı numpy / Python sürümünde düşüyor | WSL2 yok ya da dağıtımın Python'u 3.12'den eski | `wsl --install -d Ubuntu` (Ubuntu 24.04); başka dağıtım `scripts/crisper_kur.py --dagitim <ad>` ile verilir |
| 13 | `voxcpm2`: `64-bit Python 3.10+ bulunamadı` | reponun kendi Python'u kurulu değil (adım onu kendisi `PATH`'e koyar) | `scripts\kur.ps1 -Adim uv,python,voxcpm2` |
| 14 | `Önce taban kurulum: -Adim paketler` | isteğe bağlı adım ana ortamdan önce çalıştırılmış | önce varsayılan kurulum |
| 15 | `running scripts is disabled on this system` | yürütme ilkesi `.ps1` dosyalarını engelliyor | `kur.cmd` ya da `-ExecutionPolicy Bypass -File` biçimi (yalnız o süreç) |

Diğer çalışma anı belirtileri: `.claude/skills/sorun-giderme/SKILL.md`, [muhendislik/dusuk_vram.md](muhendislik/dusuk_vram.md).

## 13. İlgili dosyalar

`scripts/kur.ps1` (kurulum) · `kur.cmd` · `scripts/modelleri_indir.py` + `scripts/modeller.json` (modeller) ·
`scripts/crisper_kur.py` · `scripts/kilitle.ps1` (kilit üretimi) · `requirements/` (`temel.in`, `gpu.*`, `cpu.*`,
`ek_*`, `xtts_venv*`) · `pyproject.toml` (aşama başına ekler) · `.env.example` · [donanim.md](donanim.md) ·
[mimari.md](mimari.md) · [../THIRD_PARTY.md](../THIRD_PARTY.md)
