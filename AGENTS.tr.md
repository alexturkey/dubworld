# AGENTS.tr.md — yapay zekâ kodlama ajanı için adım adım kurulum (Türkçe)

Bu dosya [AGENTS.md](AGENTS.md)'nin Türkçe karşılığıdır; ajanlar için bağlayıcı sürüm İngilizce AGENTS.md'dir. Her
adımda bir komut, beklenen işaret satırı ve bir denetim vardır. Hiçbir denetimi atlamayın. `CLAUDE.md` buraya değil
AGENTS.md'ye yönlendirir.

**Kimin için kuruyorsunuz.** Bu repoyu kullananların çoğu geliştirici değildir. Asistanlarına tek bir cümle
yapıştırmışlardır (README "Yapay zekâ asistanınıza kurdurun"). Kurulumun tamamını bu sırayla, teknik soru sormadan
kendiniz yapın: donanımı algılayın, profili seçin, hataları okuyun ve aşağıda adı geçen belgelerden düzeltin.
Kullanıcıyla sade sözcüklerle, kendi dilinde konuşun. Sorduğunuz tek şey 4. adımdaki ses lisansı sorusudur; disk
yetmediğinde ya da sistem Windows olmadığında bunu sorarak değil, bildirerek söylersiniz.

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
| Disk alanı | `[math]::Floor((Get-PSDrive C).Free / 1GB)` (kurulacak sürücü) | NVIDIA GPU ile ≥ 22, GPU'suz ≥ 14 | kullanıcıya kaç GB boşaltması gerektiğini söyleyin ya da başka sürücüye kurun |
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

## 2. Kurulum (tek komut)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1
```

- `kur.cmd`'yi kendiniz **kullanmayın**: sonunda bir tuşa basılmasını bekler (insanlar için çift tıklama başlatıcısıdır).
- Argüman yok: betik NVIDIA GPU'yu kendisi algılar (`nvidia-smi`), GPU ya da CPU profilini kurar ve seçimi
  `.venv\dublaj_profil.txt` dosyasına yazar. `-ExecutionPolicy Bypass` yalnız bu süreci etkiler.
- İlk kurulum ≈ 13 GB (GPU profili) ya da ≈ 9,5 GB (yalnız işlemci) indirir; ölçülen temiz kurulumda GPU paketleri ≈ 14 dk, işlemci profili baştan sona ≈ 38 dk sürdü (model indirmesi yavaştı); bir saate kadar ayırın. Komut aracınızın zaman sınırı varsa betiği
  arka planda gizli başlatın ve günlüğü okuyun:

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
veriyi betikler için verir.

## 4. İlk dublaj (duman testi) ve tek soru

Varsayılan sesin (Supertonic 3) kullanım şartları vardır (OpenRAIL-M: taklit yok, aldatıcı ya da yasa dışı kullanım
yok, sesin makine üretimi olduğunu açıklayın). Kullanıcıya kendi dilinde bunları kabul edip etmediğini sorun. Tek
soru budur. Hayır derse durun: diğer sesler NVIDIA GPU ister ya da ticari olmayan lisanslıdır (`docs/sesler.md`).

Evet derse kısa bir örnek video yapın (test görüntüsü üstünde İngilizce konuşma) ve çevrimdışı Türkçeye dublajlayın:

```powershell
.venv\Scripts\dubla.exe seslendir "Hello and welcome. This short video checks that the dubbing pipeline works on this computer. Thank you for watching." --dil en --ses M1 -o cikti\ornek --lisans-onay
runtime_assets\ffmpeg\bin\ffmpeg.exe -hide_banner -loglevel error -y -f lavfi -i "testsrc2=size=1280x720:rate=25" -i cikti\ornek\speech.wav -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac cikti\ornek\ornek.mp4
.venv\Scripts\dubla.exe cikti\ornek\ornek.mp4 --ayar ceviri.arka_uc=yerel --lisans-onay
```

`--lisans-onay` kullanıcının cevabını bir kez `ayarlar/lisans_onaylari.json` dosyasına kaydeder; masaüstü uygulaması
aynı kaydı okur ve yeniden sormaz. `ceviri.arka_uc=yerel` testi çevrimdışı ve hesapsız tutar. Son komut 0 koduyla
çıkıp dosyası var olan bir `dubbed_video:` satırı yazdığında biter. Çıkış kodu 2 = lisans ya da ayar sorunu (mesaj
hangisi olduğunu söyler), 1 = iş başarısız (`.venv\Scripts\dubla.exe sorunlu` nedenini gösterir;
`.claude/skills/sorun-giderme/SKILL.md`).

**Kurulum biter**: 3. adım `READY` dediğinde ve 4. adım videoyu ürettiğinde. Sonra:

1. Masaüstü uygulamasını kullanıcı için açın: `Start-Process .venv\Scripts\dubla-gui.exe` (sonraki seferlerde
   `arayuz.cmd`'ye çift tıklar).
2. Sade sözcüklerle anlatın: nereye kuruldu, GPU mu CPU mu, nasıl başlatılır (`arayuz.cmd`), sonuçlar nereye gider
   (`cikti` klasörü) ve gerisini `docs/baslarken.md`'nin (İngilizce: `docs/getting-started.md`) anlattığını.
3. Çeviri: varsayılan `ceviri.arka_uc = auto`, Codex CLI ya da Claude Code CLI kurulu ve girişli ise onu kullanır
   (metin o hizmete gider, PRIVACY.md); değilse yalnız İngilizceden Türkçeye çeviren yerleşik çevrimdışı çevirmeni.
   Bunu tek cümleyle söyleyin; ayarı sessizce değiştirmeyin.

## 5. Sorun giderme haritası

| Belirti | Düzeltme nerede |
|---|---|
| `KURULUM DURDU` ile `sha256 tutmadı`, `paket kurulumu başarısız`, `model indirme başarısız` ya da `Python kurulamadı` | ağ: 2. adımı yeniden çalıştırın; sonra `docs/kurulum.md` 12. bölüm, 4. ve 10. satırlar |
| `running scripts is disabled on this system` | 2. adımdaki `-ExecutionPolicy Bypass -File` komutunu aynen kullanın (15. satır) |
| `kur.ps1`'de bozuk Türkçe metin ya da ayrıştırıcı hatası | `-File` ile çalıştırın, konsola asla yapıştırmayın (5. satır) |
| `torch denetimi başarısız`, `GPU profili kuruldu ama torch CUDA'sız` | `scripts\kur.ps1 -Adim paketler,kontrol` (6. satır) |
| `no kernel image is available` ya da `dubla kontrol`'deki GPU notu | 7. satır, `docs/muhendislik/dusuk_vram.md` |
| `dubla kontrol`'de `EKSİK / MISSING` | 2. adımı yeniden çalıştırın |
| `lisans onayı yok` (çıkış kodu 2) | 4. adım: kullanıcıya sorun; onun evet'i olmadan `--lisans-onay` asla vermeyin |
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

Yeniden ölçme (`docs/olcumler.md`), bir sabit sürümü yükseltme, sürüm çıkarma.

## 7. Mühendislik bilgisi (bir aşamayı değiştirmeden önce okuyun)

- `docs/muhendislik/README.md`: aşama başına geçmiş (sorun → kök neden → denenen → çözüm → ölçüm → açık), İngilizcesi
  `docs/engineering/README.md`.
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
| Tek aşama, Python API, kendi aracınız | `.claude/skills/tek-asama-kullanimi-ve-api/SKILL.md` | `docs/mimari.md`, `examples/README.md` |
| Hatalar, bellek yetmezliği, ffmpeg, kilit, kurulum | `.claude/skills/sorun-giderme/SKILL.md` | `docs/muhendislik/README.md`, `docs/muhendislik/kararlar.md` |
| Katkı, motor ekleme, testler, yasal denetim | `.claude/skills/katki-ve-motor-ekleme/SKILL.md` | `CONTRIBUTING.md`, `src/dublaj_hatti/kayit.py`, `THIRD_PARTY.md` |

Lisansı, rıza bayrağını ya da girişi asla kullanıcı adına kabul etmeyin; anahtarları asla yazdırmayın ya da commit etmeyin.
