# AGENTS.tr.md — yapay zekâ kodlama ajanı için adım adım kurulum (Türkçe)

Bu dosya [AGENTS.md](AGENTS.md)'nin Türkçe karşılığıdır; ajanlar için bağlayıcı sürüm İngilizce AGENTS.md'dir. Her
adımda bir komut, beklenen işaret satırı ve bir denetim vardır. Hiçbir denetimi atlamayın. `CLAUDE.md` buraya değil
AGENTS.md'ye yönlendirir.

**Kimin için kuruyorsunuz.** Bu repoyu kullananların çoğu geliştirici değildir. Asistanlarına tek bir cümle
yapıştırmışlardır (README "Yapay zekâ asistanınıza kurdurun"). Kurulumun tamamını bu sırayla, teknik soru sormadan
kendiniz yapın: donanımı algılayın, profili seçin, hataları okuyun ve aşağıda adı geçen belgelerden düzeltin.
Kullanıcıyla sade sözcüklerle, kendi dilinde konuşun. Yalnız iki şey sorarsınız, bir kez, 1a. adımdaki kurulum
görüşmesinde: hangi kurulumu istediği (hızlı, bu makine için önerilen, tam) ve seçtiği parçaların lisans şartlarını
kabul edip etmediği. Disk yetmediğinde ya da sistem Windows olmadığında bunu sorarak değil, bildirerek söylersiniz.

Bu repodaki ajanlar için kesin kurallar:
- Lisansı, rıza bayrağını ya da girişi asla kullanıcı adına kabul etmeyin. İsteğe bağlı ticari olmayan motorlar
  (`crisper`, `tts-xtts`, `-TicariOlmayanKabul` bayrağı) yalnız kullanıcı adıyla isterse kurulur.
  Model ağırlıkları bu repoya asla eklenmez ve buradan dağıtılmaz.
- Her indirme sabittir (commit/etiket + sha256). Bir sha denetimini "çalışsın diye" asla gevşetmeyin.
- `.venv` içine tek tek paket `pip install` etmeyin; `requirements/*.txt` ya da `scripts/modeller.json` dosyalarını
  düzenlemeyin; yönetici olarak çalıştırmayın; sistem `PATH`'ini değiştirmeyin. `scripts\kur.ps1`'i yeniden çalıştırmak her zaman güvenlidir.
- Yerel ayarları, çıktıları, sanal ortamları, modelleri ya da önbellekleri commit etmeyin (`.gitignore`).
- Adım başına en çok 3 deneme. Üçüncü başarısızlıktan sonra durun, kullanıcıya çıktının son 30 satırını ve
  `docs/kurulum.md` 12. bölümdeki ilgili satırı gösterin.

## 0. Ön koşullar (kendiniz denetleyin)

PowerShell'de çalıştırın. Buradakilerin hiçbiri kullanıcıya sorulmaz.

| Gerek | Denetim | Beklenen | Değilse |
|---|---|---|---|
| Windows 10/11, 64 bit | `[Environment]::Is64BitOperatingSystem; (Get-CimInstance Win32_OperatingSystem).Caption` | `True` ve bir Windows 10 ya da 11 adı | Linux / macOS için kurulum betiği yok ve denenmedi: kullanıcıya söyleyin; yine de denemek isterse yalnız `docs/kurulum.md` 11. bölümü izleyin |
| Disk alanı | kurulum klasöründe `[math]::Floor((Get-Item .).PSDrive.Free / 1GB)` (yeni klasör için üst klasörde, ör. `C:\`) | NVIDIA GPU ile ≥ 22, GPU'suz ≥ 14 (`kur.ps1`'in uyardığı eşiklerle aynı) | kullanıcıya kaç GB boşaltması gerektiğini söyleyin ya da başka sürücüye kurun |
| Donanım profili | `nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader` | bir satır = GPU profili; hata = CPU profili | yapılacak bir şey yok: `kur.ps1` aynı kararı verir. Kullanıcıya hangi profili istediğini asla sormayın |
| İnternet | `Test-NetConnection huggingface.co -Port 443 -InformationLevel Quiet` | `True` | yalnız kurulum sırasında gerekir; kullanıcıdan bağlanmasını isteyin |
| git | `git --version` | bir sürüm | gerekmez: 1. adımdaki ZIP yolunu kullanın |

## 1. Kodu alın

Kurulum klasörü: boşluk ve ASCII dışı harf içermeyen kısa bir yol, örneğin `C:\dublaj`. Zaten bu reponun bir
kopyasının içindeyseniz onu kullanın.

```powershell
git clone https://github.com/alexturkey/DubWorld.git C:\dublaj
# without git:
Invoke-WebRequest https://github.com/alexturkey/DubWorld/archive/HEAD.zip -OutFile $env:TEMP\dublaj.zip
Expand-Archive $env:TEMP\dublaj.zip $env:TEMP\dublaj_zip -Force
Move-Item (Get-ChildItem $env:TEMP\dublaj_zip -Directory)[0].FullName C:\dublaj
```

Denetim: `Test-Path C:\dublaj\scripts\kur.ps1` `True` verir. Sonraki bütün komutlar repo klasöründe çalışır.

## 1a. Kurulum görüşmesi (bir kez, sade sözcüklerle)

2. adımdan önce 0. adımda ölçtüklerinizi (GPU ve belleği, işlemci çekirdeği, RAM, kurulum sürücüsündeki boş disk)
kullanıcıya bir iki cümleyle söyleyin, sonra sorun: **"Nasıl bir kurulum istiyorsunuz?"** Aşağıdaki üç hazır kurulumu
sunun ve bu makine için önerdiğinizi adıyla söyleyin. Kullanıcının sorduğu parçayı seçenek tablosuyla anlatın: ne
yapar, ne kadar disk ve zaman tutar, lisans sınıfı ne. GPU ya da CPU profilini asla sormayın: onu donanım belirler.

Öneri için ek ölçümler (soru yok):

```powershell
(Get-CimInstance Win32_Processor | Measure-Object NumberOfCores -Sum).Sum           # CPU cores
[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)      # RAM, GB
(Get-PhysicalDisk | Select-Object FriendlyName, MediaType)                            # SSD or HDD
```

Lisans sınıfları: **ticari serbest** (serbest lisans), **atıf** (serbest, yazarın adı anılır), **şartlı** (kabul
edilecek kullanım şartları, ör. taklit yok), **NC** (yalnız ticari olmayan kullanım), **hizmet şartları** (bulut
hizmeti: veri bilgisayardan çıkar, kullanıcının kendi hesabı ve anahtarı).

| Parça | Ne yapar | `-Adim` adımı | Disk | Süre | Lisans |
|---|---|---|---|---|---|
| Temel (her zaman) | konuşmadan metne (faster-whisper large-v3-turbo + CTC kelime zamanı en, tr), çevrimdışı İngilizce→Türkçe çeviri (Opus-MT), varsayılan ses Supertonic 3, konuşmacı ve cinsiyet tespiti, FFmpeg | varsayılan adımlar | başlamak için 22 GB boş (GPU) / 14 GB (CPU); ölçülen kullanım ≈ 14,6 GB (GPU) | ≈ 44 dk GPU, ≈ 38 dk CPU, ölçüldü | Supertonic: **şartlı** (OpenRAIL-M); Opus-MT ve tr CTC modeli: **atıf** (CC BY 4.0); gerisi ticari serbest |
| Ses temizliği | yazıya dökmeden önce konuşmayı müzik ve gürültüden ayırır | `demucs` | ≈ 84 MB ağırlık | kayıt yok | ticari serbest (MIT) |
| EMA Lightning sesi | ikinci ses, yalnız Türkçe, tek sentetik konuşmacı, GPU ya da işlemci | `tts-ema` | ≈ 0,12 GB | kayıt yok | ticari serbest (Apache-2.0) |
| VoxCPM2 sesi | ses tasarımı ve klonlamalı çok dilli ses; NVIDIA GPU, git ister | `voxcpm2` | ≈ 3,7 GB indirme | kayıt yok | ticari serbest (Apache-2.0) |
| XTTS v2 sesi | çok dilli ses klonlama, ayrı ortam | `tts-xtts` + `-TicariOlmayanKabul` | 3–8 GB (tahmin, ölçülmedi) | kayıt yok | **NC** (CPML) |
| Ek kaynak dilleri ja, zh | Japonca ve Çince kaynak için kelime zamanı | `hizalama-diller` | ≈ 2,5 GB | kayıt yok | ticari serbest (Apache-2.0) |
| Kaynak dilleri fr, de, es, it | kelime zamanı modelleri ilk kullanımda iner (bir kez `DUBLAJ_CEVRIMICI=1`) | yok | dil başına | kayıt yok | **NC** (CC BY-NC 4.0) |
| Parakeet | işlemcide İngilizce konuşmadan metne | `parakeet` | ≈ 0,7 GB | kayıt yok | **şartlı** (NVIDIA Open Model License) |
| CrisperWhisper Turbo | birebir (verbatim) konuşmadan metne; WSL2 + NVIDIA, git ister | `crisper` + `-TicariOlmayanKabul` | ≈ 7 GB | kayıt yok | **NC** |
| Speechmatics / ElevenLabs | kullanıcının kendi anahtarıyla bulut konuşmadan metne | `speechmatics` (ElevenLabs adım istemez) | küçük | kayıt yok | **hizmet şartları** |
| Codex / Claude Code / API çevirisi | daha iyi çeviri ve başka dil çiftleri | yok (`ceviri.arka_uc = auto` kurulu ve girişli CLI'yi kullanır) | yok | yok | **hizmet şartları** |
| Akıllı kare | videodaki siyah bantları kırpar | `akilli-kare` | küçük | kayıt yok | ticari serbest (Apache-2.0) |
| Bağlantıdan indirme | bağlantıdan video indirir (yalnız kullanıcının hakkı olan içerik) | `youtube` | küçük | kayıt yok | yt-dlp Unlicense + sitenin şartları |
| Telegram botu | uzaktan kumanda ve telefona teslim (bulut sınırı 50 MB) | `telegram` | küçük | kayıt yok | ticari serbest (LGPL-3.0, kütüphane değiştirilmeden) |
| Telegram ile 2 GB'a kadar | yerel Bot API sunucusu; my.telegram.org'dan `api_id` / `api_hash` ister | `telegram-sunucu` | Docker kalıbı ya da yerel derleme | Docker ile birkaç dakika, Docker'sız derleme 10–30 dk (tarife göre) | ticari serbest (BSL-1.0) |

Boyut ve lisanslar: [docs/kurulum.md](docs/kurulum.md) 1. bölüm, [THIRD_PARTY.md](THIRD_PARTY.md),
`src/dublaj_hatti/kayit.py`. "Kayıt yok" süre ölçülmedi demektir.

Üç kurulum (her biri tek komut; adımlar betiğin sabit sırasıyla çalışır):

| Kurulum | İçerik | Komut |
|---|---|---|
| Hızlı (en az) | yalnız temel | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1` |
| Önerilen, NVIDIA GPU yok | temel + EMA Lightning (işlemci) | `... scripts\kur.ps1 -Adim uv,python,paketler,modeller,tts-ema,kontrol` |
| Önerilen, NVIDIA 4–5 GB | temel + ses temizliği + EMA Lightning (VoxCPM2 de 4 GB'a sığar, [kardeş repoda](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi/blob/main/docs/4gb.md) ölçüldü; kullanıcı ikinci bir çok dilli ses isterse ekleyin) | `... scripts\kur.ps1 -Adim uv,python,paketler,modeller,demucs,tts-ema,kontrol` |
| Önerilen, NVIDIA 6 GB ve üstü | temel + ses temizliği + EMA Lightning + VoxCPM2 | `... scripts\kur.ps1 -Adim uv,python,paketler,modeller,demucs,tts-ema,voxcpm2,kontrol` |
| Tam | önerilen + `hizalama-diller,parakeet,akilli-kare,youtube,telegram`; NC parçalar (`crisper`, `tts-xtts`) yalnız kullanıcı "yalnız ticari olmayan kullanım"a evet dedikten sonra | `... scripts\kur.ps1 -Adim uv,python,paketler,modeller,demucs,tts-ema,hizalama-diller,parakeet,akilli-kare,youtube,telegram,kontrol` (+ `,crisper,tts-xtts -TicariOlmayanKabul`) |

Önerilen kurulumlarda NC parça ve bulut hizmeti yoktur. Bulut hizmetleri ve `telegram-sunucu` yalnız kullanıcı
isterse eklenir (kullanıcının kendi hesaplarını ister).

**Seçimi ve lisans cevabını kaydedin** (bir kez, 2. adımdan önce):

1. Kurulum: `ayarlar\kullanici.toml` yoksa oluşturun ve seçimi en üste yorum satırı olarak yazın (ayar yükleyicisi
   bilinmeyen anahtarı reddeder, kayıt bu yüzden yorumdur), örneğin
   `# kurulum: onerilen (NVIDIA 4 GB) · -Adim uv,python,paketler,modeller,demucs,tts-ema,kontrol · 2026-10-25`.
   Gerçek ayarı yalnız kullanıcının seçtiği şey için ekleyin, örneğin `[ses]` / `ema_cihaz = "cpu"` (4. adım 5. madde).
2. Lisans cevabı: varsayılan ses Supertonic'in kullanım şartları vardır (OpenRAIL-M: taklit yok, aldatıcı ya da yasa
   dışı kullanım yok, sesin makine üretimi olduğunu açıklayın). Kullanıcıya bunları kabul edip etmediğini bir kez,
   seçilen öteki **şartlı** parçaların (Parakeet) şartlarıyla birlikte sorun. Yalnız açık bir evet'ten sonra,
   programın tek lisans kapısından kaydedin; 2. adımdan sonra (`.venv` gerekir):

   ```powershell
   .venv\Scripts\python.exe -c "from dublaj_hatti.lisans_onayi import kapi_adlar; print(kapi_adlar(['supertonic'], onay=True))"
   ```

   Parakeet seçilip kabul edildiyse listeye `'parakeet_cpu_align'` ekleyin. Kayıt `ayarlar/lisans_onaylari.json`
   dosyasına düşer; komut satırı ve masaüstü uygulaması onu okur ve yeniden sormaz. NC parçalar yalnız kullanıcının
   evet'inden sonra `kur.ps1`'e `-TicariOlmayanKabul` verilerek kabul edilir; XTTS ilk kullanımda kendi rızasını da
   ister (`ses.xtts_lisans_onayi`).
3. Kullanıcı Supertonic şartlarına hayır derse: kurulumu yine yapın, hiçbir şey kaydetmeyin ve varsayılan sesin
   kullanılamayacağını söyleyin; yerine EMA Lightning (Türkçe, ticari serbest) ya da VoxCPM2 (NVIDIA GPU) seçilebilir
   (`docs/sesler.md`).

Donanım kademeleri (makineyle ne değişir; her hücre kanıtıyla: [docs/donanim.md](docs/donanim.md)):

| Makine | Konuşmadan metne | Ses | Paralel iş |
|---|---|---|---|
| NVIDIA GPU yok | işlemci, `int8` (kod: işlemcide int8'e çözülür) | Supertonic (işlemci); EMA Lightning `ses.ema_cihaz = cpu` ile | GPU kilidi yok; işlemci-ağır kilit 2 işe izin verir |
| NVIDIA 4 GB (Pascal sm_61, ölçüldü) | GPU; `auto` bu kartta `int8`'e çözülür (ölçüldü); WhisperX batch 1 | Supertonic; EMA Lightning `auto`; VoxCPM2 sığar (kardeş repo) | aynı anda 1 GPU işi (kilit kapasitesi 1) |
| NVIDIA 6 GB ve üstü | GPU; `auto` yalnız kart bildiriyorsa `float16` verir (Volta ve sonrası), Pascal `int8` kalır | bütün sesler | yine 1 GPU işi; daha büyük batch: kayıt yok |

4 GB seçimleri kodun küçük kartta yaptığıdır, büyük kartlar için kural değildir.

## 2. Kurulum (tek komut)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1
```

Bu hızlı kurulumdur. 1a. adımda seçilen kurulum için oradaki tablodan `-Adim` listesini ekleyin.

- `kur.cmd`'yi kendiniz **kullanmayın**: sonunda bir tuşa basılmasını bekler (insanlar için çift tıklama başlatıcısıdır).
- `-Cpu` verilmezse betik NVIDIA GPU'yu kendisi algılar (`nvidia-smi`), GPU ya da CPU profilini kurar ve seçimi
  `.venv\dublaj_profil.txt` dosyasına yazar. `-ExecutionPolicy Bypass` yalnız bu süreci etkiler.
- İlk kurulum ≈ 13 GB (GPU profili) ya da ≈ 9,5 GB (yalnız işlemci) indirir. Hızlı kurulumun ölçülen temiz
  kurulumları: GPU profili baştan sona ≈ 44 dk (paketler 13,7 dk, gerisi ≈ 1 MB/s model indirmesi), işlemci profili
  ≈ 38 dk; ek parçalar kendi indirmelerini ekler. Bir saate kadar ayırın. Komut aracınızın zaman sınırı varsa betiği
  arka planda gizli başlatın ve günlüğü okuyun (seçilen kurulumun `-Adim` listesini `-ArgumentList`'e ekleyin):

  ```powershell
  Start-Process powershell -WindowStyle Hidden -RedirectStandardOutput kur.log -RedirectStandardError kur.err.log -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','scripts\kur.ps1'
  Select-String -Path kur.log -Encoding UTF8 -Pattern 'KURULUM_OK|KURULUM DURDU' | Select-Object -Last 1   # repeat every few minutes
  ```

Sırasıyla işaret satırları (her biri kendi adımını kanıtlar):

| Adım | Ne yapar | İşaret | Denetim |
|---|---|---|---|
| `uv` | sabit uv 0.13.5'i `runtime_assets\araclar\uv` içine | `UV_OK` | – |
| `python` | CPython 3.11.14'ü `runtime_assets\python` içine | `PYTHON_OK` | – |
| `paketler` | `.venv` + hash kilitli `requirements\gpu.txt` ya da `cpu.txt` + bu paket | `PAKETLER_OK` | `Get-Content .venv\dublaj_profil.txt` |
| `modeller` | modeller + FFmpeg, her dosya sha256 denetimli (`scripts\modeller.json`) | `MODELLER_OK` | – |
| `kontrol` | gerçek CUDA çekirdeği (GPU profili) + `dubla kontrol` | `KONTROL_OK` | 3. adım |
| son | – | `KURULUM_OK` | – |

Hata olursa betik `KURULUM DURDU / INSTALL STOPPED: <mesaj>` yazar ve 1 koduyla çıkar. Aynı komutu bir kez daha
çalıştırın (indirmeler kaldığı yerden sürer, doğru dosyalar atlanır). Yine durursa mesajı `docs/kurulum.md` 12.
bölümde bulun ve o satırdaki düzeltmeyi uygulayın. `UYARI` / `WARNING` satırı bilgidir, hata değildir.

## 3. Doğrulama

```powershell
.venv\Scripts\dubla.exe kontrol
```

Son satır `SONUÇ / RESULT: Önerilen akış HAZIR / recommended flow READY` olduğunda biter (`READY` kelimesine bakın).
`EKSİK / MISSING: <parçalar>` derse 2. adımı yeniden çalıştırın. GPU hakkında bir `not / note: ...` satırı, GPU
profilinin kurulu olduğu ama GPU'nun çalışamadığı anlamına gelir (genellikle eski sürücü): program yine işlemcide
çalışır; kullanıcıya söyleyin ve `docs/kurulum.md` 12. bölüm, 6–7. satırları gösterin. `dubla kontrol --json` aynı
veriyi betikler için verir. Kurulumdan sonraki ilk çalıştırma birkaç dakika sürebilir, çünkü kütüphaneler diskten
soğuk okunur; sonraki çalıştırmalar daha hızlıdır.

## 4. İlk dublaj (duman testi)

Lisans sorusu 1a. adımda bir kez soruldu ve 2. adımdan sonra `kapi_adlar` ile kaydedildi; yeniden sormayın.
Kullanıcı Supertonic şartlarına hayır dediyse bu adımı atlayın (örnek Supertonic kullanır) ve bunu söyleyin;
kurulumu 3. adım zaten kanıtladı.

Evet derse kısa bir örnek video yapın (test görüntüsü üstünde İngilizce konuşma) ve çevrimdışı Türkçeye dublajlayın:

```powershell
.venv\Scripts\dubla.exe seslendir "Hello and welcome. This short video checks that the dubbing pipeline works on this computer. Thank you for watching." --dil en --ses M1 -o cikti\ornek --lisans-onay
runtime_assets\ffmpeg\bin\ffmpeg.exe -hide_banner -loglevel error -y -f lavfi -i "testsrc2=size=1280x720:rate=25" -i cikti\ornek\speech.wav -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac cikti\ornek\ornek.mp4
.venv\Scripts\dubla.exe cikti\ornek\ornek.mp4 --ayar ceviri.arka_uc=yerel --lisans-onay
```

`--lisans-onay` yalnız kaydedilmiş evet'i yineler (`ayarlar/lisans_onaylari.json`); o evet olmadan asla vermeyin.
Masaüstü uygulaması aynı kaydı okur ve yeniden sormaz. `ceviri.arka_uc=yerel` testi çevrimdışı ve hesapsız tutar. Son komut 0 koduyla
çıkıp dosyası var olan bir `dubbed_video:` satırı yazdığında biter. Çıkış kodu 2 = lisans ya da ayar sorunu (mesaj
hangisi olduğunu söyler), 1 = iş başarısız (`.venv\Scripts\dubla.exe sorunlu` nedenini gösterir;
`.claude/skills/sorun-giderme/SKILL.md`).
Dublajlı video örnekten uzun çıkabilir: her satır en çok 1,25× hızlandırılır, kalanı için görüntünün süresi
uzatılır (kabul testi: 7,38 sn kaynak, 9,27 sn dublaj, %+25,6, iş günlüğünde `Sure Farki` satırı). Bu beklenen davranıştır.

**Kurulum biter**: 3. adım `READY` dediğinde ve 4. adım videoyu ürettiğinde. Sonra:

1. Masaüstü uygulamasını kullanıcı için açın: `Start-Process .venv\Scripts\dubla-gui.exe` (sonraki seferlerde
   `arayuz.cmd`'ye çift tıklar). Bilinen sınır: kabul testinde uygulama pencere kapatma iletisiyle (WM_CLOSE) 4 sn
   içinde kapanmadı (nedeni ölçülmedi). Yalnız denetim için açtıysanız ve kapatmanız gerekiyorsa beklemeyin, süreç
   ağacını kapatın (`taskkill /PID <pid> /T`).
2. Sade sözcüklerle anlatın: nereye kuruldu, GPU mu CPU mu, nasıl başlatılır (`arayuz.cmd`), sonuçlar nereye gider
   (`cikti` klasörü) ve gerisini `docs/baslarken.md`'nin (İngilizce: `docs/getting-started.md`) anlattığını.
3. Çeviri: varsayılan `ceviri.arka_uc = auto`, Codex CLI ya da Claude Code CLI kurulu ve girişli ise onu kullanır
   (metin o hizmete gider, PRIVACY.md); değilse yalnız İngilizceden Türkçeye çeviren yerleşik çevrimdışı çevirmeni.
   Bunu tek cümleyle söyleyin; ayarı sessizce değiştirmeyin.
4. İsteğe bağlı, yalnız kullanıcı biten videoları telefonunda isterse: Telegram botu
   (`.claude/skills/telegram-botu-kurulumu/SKILL.md`), ardından yerel Bot API sunucusuyla 2000 MB'a kadar teslim
   (`.claude/skills/telegram-buyuk-dosya/SKILL.md`: kullanıcı yalnız my.telegram.org'dan `api_id` / `api_hash`'i
   `.env`'ye yazar; `scripts\kur.ps1 -Adim telegram-sunucu`'yu siz çalıştırır, `dubla kontrol`'e bakarsınız).

5. İsteğe bağlı, yalnız kullanıcı yalnız Türkçe okuyan ikinci bir ses isterse: EMA Lightning (tek sentetik ses,
   Apache-2.0, `docs/motorlar/ema_lightning.md`). İki profilde de `scripts\kur.ps1 -Adim tts-ema` çalıştırın; adım
   paketi hash'li kilitten kurar, sabit ağırlığı indirir ve işlemci ONNX dosyalarını yerelde dışa aktarır
   (`TTS_EMA_OK`). Cihazı zaten denetlediğiniz donanıma göre seçin, sormayın: en az 1 GB boş belleği olan NVIDIA GPU →
   `ses.ema_cihaz = auto` kalsın (GPU'yu kullanır, GPU meşgulse işlemciye düşer); NVIDIA GPU yok ya da CPU profili →
   `ses.ema_cihaz = cpu` (ONNX). `dubla kontrol`, `tts ema_lightning` satırını ve `auto`'nun şu an neyi seçeceğini
   gösterir. Yalnız Türkçe okur; başka hedef diller için Supertonic kalsın.

## 5. Sorun giderme haritası

| Belirti | Düzeltme nerede |
|---|---|
| `KURULUM DURDU` ile `sha256 tutmadı`, `paket kurulumu başarısız`, `model indirme başarısız` ya da `Python kurulamadı` | ağ: 2. adımı yeniden çalıştırın; sonra `docs/kurulum.md` 12. bölüm, 4. ve 10. satırlar |
| `running scripts is disabled on this system` | 2. adımdaki `-ExecutionPolicy Bypass -File` komutunu aynen kullanın (15. satır) |
| `kur.ps1`'de bozuk Türkçe metin ya da ayrıştırıcı hatası | `-File` ile çalıştırın, konsola asla yapıştırmayın (5. satır) |
| `torch denetimi başarısız`, `GPU profili kuruldu ama torch CUDA'sız` | `scripts\kur.ps1 -Adim paketler,kontrol` (6. satır) |
| `no kernel image is available` ya da `dubla kontrol`'deki GPU notu | 7. satır, `docs/muhendislik/dusuk_vram.md` |
| `dubla kontrol`'de `EKSİK / MISSING` | 2. adımı yeniden çalıştırın |
| `lisans onayı yok` (çıkış kodu 2) | 1a. adım: cevap kaydedilmemiş; kullanıcıya sorun; onun evet'i olmadan `--lisans-onay` asla vermeyin |
| bir dublaj işi başarısız olur ya da durur | `.venv\Scripts\dubla.exe sorunlu`, sonra `.venv\Scripts\dubla.exe devam <id>`; `.claude/skills/sorun-giderme/SKILL.md` |
| 4 GB GPU'da bellek yetmezliği | `docs/muhendislik/dusuk_vram.md` |

## 5a. Yerleşim

```
kur.cmd, arayuz.cmd, web.cmd    double-click launchers: install, desktop app, local web app
scripts\kur.ps1                 installer (steps above); scripts\modeller.json = pinned models
.venv\                          main Python environment (created by the installer)
runtime_assets\                 Python, uv, models, FFmpeg, optional engines (created by the installer)
cikti\                          outputs and the job database (default output folder)
ayarlar\                        personal settings (kullanici.toml) and license records; not in git
src\dublaj_hatti\               the package (commands dubla, dubla-gui, dubla-web)
docs\                           getting-started / baslarken (users), installation / kurulum (full reference)
```

Kısaca: üç çift tıklama başlatıcısı (kurulum, masaüstü, yerel web), kurulum betiği ve sabit model listesi, kurulumun
oluşturduğu `.venv\` ve `runtime_assets\`, çıktılar ve iş veritabanı `cikti\`, kişisel ayar ve lisans kayıtları
`ayarlar\` (git dışı), paket `src\dublaj_hatti\`, belgeler `docs\`.

## 6. Bakımcı notları

- **Yeniden ölçme.** Belgelerdeki her sayı [docs/olcumler.md](docs/olcumler.md)'den gelir: makine sınıfını, yöntemi
  (ör. disk boyutu sabit bağlar bir kez sayılarak, `du`) ve tarihi yazar. Aynı yordamı temiz bir klasörde yeniden
  çalıştırın, önce o sayfayı, sonra ondan alıntı yapan sayfaları güncelleyin.
- **Paket kilidini yenileme.** Yalnız `requirements/*.in` kaynağını düzenleyin, sonra `scripts\kilitle.ps1`'i
  çalıştırın (hash'li `*.txt` kilitlerini sabit uv ile yeniden kurar; `-Yukselt` daha yeni sürümlere izin verir,
  `-YalnizXtts` yalnız XTTS kilitlerini kurar). `.in` ile `.txt`'yi birlikte commit edin. `.txt` kilidini elle
  düzenlemeyin.
- **Model sabitini değiştirme.** `scripts/modeller.json`'daki girdiyi düzenleyin (commit ya da etiketli adres, boyut,
  sha256), sonra `python scripts/modelleri_indir.py --liste` ile denetleyin ve
  `python scripts/modelleri_indir.py --adim <adım>` ile bir kez indirin. Kod tarafındaki sabitler
  (`voxcpm2_tts/ayarlar.py` içinde `VOXCPM2_COMMIT`, `scripts/kur.ps1` içinde `$VOX_COMMIT` / `$STT_COMMIT`) kendi
  sayfalarıyla birlikte değişir. `pytest` çalıştırın (`tests/test_sabit_degerler.py` ve
  `tests/test_kurulum_kilitleri.py` dahil); sabitlenmiş bir değerden önce
  [docs/muhendislik/sabit_degerler.md](docs/muhendislik/sabit_degerler.md)'yi okuyun.
- **Sürüm çıkarma.** `CHANGELOG.md`'deki `## [Unreleased]` notlarını yeni sürüm ve tarih altına taşıyın (SemVer),
  `src/dublaj_hatti/__init__.py` içindeki `__version__`'ı aynı sürüme getirin, commit edin, sonra `v<sürüm>` etiketi
  koyun. Etiketi gönderme (push) ve sürümü yayınlama bakımcının kararıdır; ajan kendi başına asla push etmez.

## 7. Mühendislik bilgisi (bir aşamayı değiştirmeden önce okuyun)

- `docs/muhendislik/README.md`: aşama başına geçmiş (sorun → kök neden → denenen → çözüm → ölçüm → açık), İngilizcesi
  `docs/engineering/README.md`.
- `docs/muhendislik/hat_akisi.md`: kaynaktan teslim edilen videoya bütün akış (aşama → girdi dosyası → çıktı dosyası → ne değişir, ayara göre dallanmalar, segmentlerin neden kelime zamanlarından yeniden kurulduğu); EN `docs/engineering/pipeline-flow.md`.
- `docs/muhendislik/dusuk_vram.md`: 4 GB GPU / yalnız CPU ayarları ve bellek yetmezliği sorun giderme.
- `docs/muhendislik/kararlar.md` (İngilizce `docs/adr/README.md`): mimari kararlar. Bir aşamanın davranışını değiştirmek,
  onun ara kayıt sözleşme sürümünü artırmak demektir (ADR 0012); sessiz yedek asla eklenmez (ADR 0009).
- Sabitlenmiş bir değeri değiştirmeden önce `docs/muhendislik/sabit_degerler.md`'yi (EN `docs/engineering/pinned-values.md`) okuyun; kritik olanları `tests/test_sabit_degerler.py` korur.

## 8. Görev → beceri / belge

Claude Code bu becerileri `.claude/skills/` klasöründen yükler; diğer ajanlar (Codex, Cursor, ...) aynı `SKILL.md`
dosyalarını çalışma kılavuzu olarak okur. Motor sayfalarıyla fihrist: `docs/beceriler/README.md`.

| Görev | Beceri | Belgeler |
|---|---|---|
| Kurulum, GPU / CPU profili, isteğe bağlı motorlar, `dubla kontrol` | `.claude/skills/kurulum-ve-donanim/SKILL.md` | `docs/donanim.md`, `docs/muhendislik/dusuk_vram.md` |
| Video dublajı (önerilen akış), yalnız altyazı | `.claude/skills/dublaj-onerilen-akis/SKILL.md` | `src/dublaj_hatti/varsayilan.toml` |
| Ayarlar, tarifler, reddedilen kombinasyonlar | `.claude/skills/gelismis-ayarlar-ve-kombinasyonlar/SKILL.md` | `docs/tarifler/kombinasyonlar.md` |
| Konuşmadan metne motoru, dil tespiti | `.claude/skills/stt-motorlari/SKILL.md` | `docs/tarifler/dil_tespiti.md`, `docs/motorlar/` |
| TTS motoru, hedef dil, sesler, XTTS / RVC rızası | `.claude/skills/tts-motorlari/SKILL.md` | `docs/diller.md`, `docs/sesler.md`, `ETHICS.md` |
| Çeviri arka ucu (Codex, Claude Code, Opus-MT, API anahtarları) | `.claude/skills/ceviri-arka-uclari/SKILL.md` | `docs/muhendislik/ceviri.md`, `.env.example` |
| Devam, sorunlu işler, GPU kuyruğu | `.claude/skills/devam-ve-sorunlu-isler/SKILL.md` | `docs/tarifler/devam_ve_sorunlu_isler.md` |
| Telegram botu kurulumu | `.claude/skills/telegram-botu-kurulumu/SKILL.md` | `docs/tarifler/telegram_botu.md` |
| Telegram ile büyük dosya (2000 MB, yerel Bot API sunucusu) | `.claude/skills/telegram-buyuk-dosya/SKILL.md` | `docs/tarifler/telegram_buyuk_dosya.md` |
| Tek aşama, Python API, kendi aracınız | `.claude/skills/tek-asama-kullanimi-ve-api/SKILL.md` | `docs/mimari.md`, `examples/README.md` |
| Hatalar, bellek yetmezliği, ffmpeg, kilit, kurulum | `.claude/skills/sorun-giderme/SKILL.md` | `docs/muhendislik/README.md`, `docs/muhendislik/kararlar.md` |
| Katkı, motor ekleme, testler, yasal denetim | `.claude/skills/katki-ve-motor-ekleme/SKILL.md` | `CONTRIBUTING.md`, `src/dublaj_hatti/kayit.py`, `THIRD_PARTY.md` |

Lisansı, rıza bayrağını ya da girişi asla kullanıcı adına kabul etmeyin; anahtarları asla yazdırmayın ya da commit etmeyin.
