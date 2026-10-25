<#
.SYNOPSIS
  DubWorld kurulumu (Windows 10/11, NVIDIA GPU ya da yalnız işlemci).

.DESCRIPTION
  Her şey repo klasörünün içine kurulur (runtime_assets\, .venv\); sistem PATH'ine, kayıt defterine ve
  genel Python'a dokunulmaz. Her indirme sabit adres + sha256 ile doğrulanır; doğru dosya varsa atlanır,
  betik yeniden çalıştırılabilir. Hiçbir model ağırlığı repoda değildir; hepsi asıl kaynağından iner.

  Varsayılan adımlar (Önerilen akış için yeterli):
    uv        uv 0.13.5 (sabit sha256) -> runtime_assets\araclar\uv
    python    CPython 3.11.14 (uv, yalnız bu klasöre)
    paketler  .venv + requirements\gpu.txt ya da cpu.txt (hash zorunlu) + bu paket (dubla komutları)
    modeller  Supertonic 3, Opus-MT en-tr, faster-whisper large-v3-turbo, wav2vec2 CTC (en, tr),
              3D-Speaker + cinsiyet sınıflandırıcı, FFmpeg 9.0.2  (~5,3 GB)
    kontrol   gerçek CUDA çekirdeği (ya da işlemci) + dubla kontrol

  İsteğe bağlı adımlar (-Adim ile ayrıca):
    demucs    ses ayrıştırma (ses_temizligi.kip = clean / preserve_background) + htdemucs modeli (~84 MB, MIT)
    hizalama-diller  ja, zh kaynak dilleri için CTC kelime zamanı modelleri (~2,5 GB, Apache-2.0)
    youtube   yt-dlp (bağlantıdan indirme; yalnız hakkınız olan ya da izinli içerik)
    parakeet  sherpa-onnx + Parakeet Unified EN 0.6B INT8 modeli (~663 MB; İngilizce, işlemci)
    speechmatics  bulut STT istemcisi (kendi anahtarınız: .env)
    crisper   CrisperWhisper 2.0 Turbo (13. motor; TİCARİ OLMAYAN lisans; WSL2 + NVIDIA; -TicariOlmayanKabul gerekir)
    voxcpm2   VoxCPM2 TTS (NVIDIA GPU; kardeş repo sabit commit, kendi kurulum betiğiyle)
    tts-ema   EMA Lightning TTS (yalnız Türkçe, Apache-2.0): paket (hash'li kilit) + ağırlık (~34 MB, sabit commit +
              sha256) + işlemci yolu için ONNX dışa aktarımı (bu makinede, torch ile eşitlik denetimli). GPU ya da
              işlemci: ses.ema_cihaz = auto (GPU yoksa/meşgulse işlemci ONNX) | cuda | cpu
    akilli-kare  OpenCV (video.akilli_kare: kenar bandı kırpma)
    galeri    gallery-dl (galeri bağlantısı; yalnız ayrı süreç olarak çağrılır, GPL-2.0-only)
    telegram  python-telegram-bot (uzaktan kumanda botu; belirteç yalnız .env'de)
    telegram-sunucu  yerel Telegram Bot API sunucusu (2000 MB'a kadar teslim; bulut sınırı 50 MB). Docker varsa
              Docker (Docker Desktop gizli başlar), yoksa resmî kaynaktan derleme (WSL); .env'de TELEGRAM_API_ID,
              TELEGRAM_API_HASH gerekir (docs/tarifler/telegram_buyuk_dosya.md). telegram adımını da kurar.
    tts-xtts  XTTS v2 (coqui-tts) AYRI sanal ortamda, hash'li kilitle (requirements\xtts_venv_gpu|cpu.txt;
              runtime_assets\tts_motorlari\xtts\venv); ağırlık TİCARİ
              OLMAYAN CPML lisanslıdır: -TicariOlmayanKabul gerekir, ağırlık ilk kullanımda Coqui'den iner
  Kilit dosyası (requirements\ek_<ad>.txt) varsa hash zorunlu kurulur; yoksa sabit sürüm, taban kilidi kısıt (-c)
  olarak verilir (taban paketleri değişmez) ve hash doğrulaması olmadığı açıkça yazılır.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Cpu
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim demucs,youtube
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim akilli-kare,telegram
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim telegram-sunucu
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim tts-xtts -TicariOlmayanKabul
#>
[CmdletBinding()]
param(
  [string]$Adim = "uv,python,paketler,modeller,kontrol",
  [switch]$Cpu,
  [switch]$TicariOlmayanKabul
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Her durma, teknik bilgisi olmayan kullanıcıya da ne yapacağını söyler (docs/kurulum.md §12, docs/getting-started.md).
# Çıkış kodu eskisi gibi 1'dir; yalnız mesaj eklendi.
trap {
  Write-Host ""
  Write-Host "KURULUM DURDU / INSTALL STOPPED: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Ne yapmalı: aynı komutu (ya da kur.cmd) yeniden çalıştırın; doğru inmiş dosyalar atlanır, kurulum kaldığı yerden sürer."
  Write-Host "  Yine durursa: docs\kurulum.md bölüm 12'de yukarıdaki mesajın ilk kelimelerini arayın."
  Write-Host "  Yapay zekâ asistanı kullanıyorsanız bu penceredeki son 30 satırı ona yapıştırın."
  Write-Host "What to do: run the same command (or kur.cmd) again; correct files are skipped and the install resumes."
  Write-Host "  If it stops again: search docs\installation.md section 12 for the first words of the message above."
  exit 1
}

$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Varlik = Join-Path $Repo "runtime_assets"
$Araclar = Join-Path $Varlik "araclar"
$UvDir = Join-Path $Araclar "uv"
$Uv = Join-Path $UvDir "uv.exe"
$Venv = Join-Path $Repo ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"
$Adimlar = $Adim.Split(",") | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ }

# --- sabitler -------------------------------------------------------------------------------------------
$UV_URL = "https://github.com/astral-sh/uv/releases/download/0.13.5/uv-x86_64-pc-windows-msvc.zip"
$UV_SHA = "a38b8d1902b7cfbc76b423ba1bb456f623f42064cdc72628b6075b89afd1019a"
$PY_SURUM = "3.11.14"
# Kardeş repolar (README "Family"): adres yayında doldurulur; çatal (fork) için ortam değişkeniyle değiştirilebilir.
# Commit sabittir: başka adresten gelen kod da yalnız bu commit'le kurulur.
$VOX_REPO = if ($env:DUBLAJ_TTS_REPO_URL) { $env:DUBLAJ_TTS_REPO_URL } else { "https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi" }
$VOX_COMMIT = "2d74db1640675cb81965588c670ced4ebf05c32d"
$STT_REPO = if ($env:DUBLAJ_STT_REPO_URL) { $env:DUBLAJ_STT_REPO_URL } else { "https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani" }
$STT_COMMIT = "2ca4b160e4bf9254185df01b21b281db4b209c19"
# Kilidi henüz olmayan isteğe bağlı ekler: sabit sürüm (pyproject [project.optional-dependencies] alt sınırıyla aynı).
$EK_SABIT = @{
  "akilli-kare" = @("opencv-python-headless==5.0.0.93")
  "galeri"      = @("gallery-dl==1.32.17")
  "telegram"    = @("python-telegram-bot==22.8")
}
function Kardes-Repo-Denetle([string]$Adres, [string]$Degisken) {
  if ($Adres -like "*__*" -or $Adres -notmatch '^https://') {
    throw "Kardeş repo adresi ayarlı değil ($Adres). README 'Family' bölümündeki adresi $Degisken ortam değişkenine yazın."
  }
}

$env:UV_CACHE_DIR = Join-Path $Varlik "onbellek\uv"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Varlik "python"
$env:UV_NO_MODIFY_PATH = "1"
$env:PYTHONIOENCODING = "utf-8"

function Adim([string]$ad) { return $Adimlar -contains $ad }
function Bilgi([string]$m) { Write-Host $m }

function Indir([string]$Url, [string]$Hedef, [string]$Sha) {
  if ((Test-Path $Hedef) -and ((Get-FileHash $Hedef -Algorithm SHA256).Hash.ToLower() -eq $Sha)) {
    Bilgi "  var ve doğru: $(Split-Path $Hedef -Leaf)"; return
  }
  New-Item -ItemType Directory -Force -Path (Split-Path $Hedef) | Out-Null
  $part = "$Hedef.part"
  Invoke-WebRequest -Uri $Url -OutFile $part -UseBasicParsing
  $gelen = (Get-FileHash $part -Algorithm SHA256).Hash.ToLower()
  if ($gelen -ne $Sha) { Remove-Item $part -Force; throw "sha256 tutmadı: $Url`n  beklenen $Sha`n  gelen    $gelen" }
  Move-Item -Force $part $Hedef
  Bilgi "  indi, sha256 doğru: $(Split-Path $Hedef -Leaf)"
}

function NvidiaVar {
  $smi = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
  if (-not $smi) { return $false }
  $out = & $smi.Source --query-gpu=name,driver_version --format=csv,noheader 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $out) { return $false }
  Bilgi "  GPU: $out"
  return $true
}

function Paketle([string]$Kilit) {
  # Kilit iki indeks yazar (PyPI + PyTorch); her paket hash ile sabit olduğundan en iyi eşleşme güvenlidir.
  & $Uv pip install --python $Py --require-hashes --index-strategy unsafe-best-match -r (Join-Path $Repo "requirements\$Kilit")
  if ($LASTEXITCODE -ne 0) { throw "paket kurulumu başarısız: $Kilit (çoğunlukla internet kesintisi; yeniden çalıştırın)" }
}

Bilgi "DubWorld kurulumu · repo: $Repo · adımlar: $($Adimlar -join ', ')"

# İlk kurulumda disk yeri (yalnız uyarı; kurulum sürer). Rakamlar: docs/kurulum.md §1.
if (((Adim "paketler") -or (Adim "modeller")) -and -not (Test-Path $Py)) {
  $bosGb = -1
  try { $bosGb = [math]::Floor((Get-Item $Repo).PSDrive.Free / 1GB) } catch { $bosGb = -1 }
  # Ölçülen (temiz kök, indirme önbelleği dahil): GPU profili ≈ 22 GB, yalnız işlemci ≈ 13,2 GB.
  $gerekGb = 22
  if ($Cpu -or -not (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue)) { $gerekGb = 14 }
  if ($bosGb -ge 0 -and $bosGb -lt $gerekGb) {
    Bilgi "  UYARI: bu sürücüde $bosGb GB boş yer var; ilk kurulum ≈ 22 GB (NVIDIA GPU) ya da ≈ 14 GB (yalnız işlemci) ister (indirme önbelleği kurulumdan sonra silinebilir: GPU ≈ 7,8 GB, işlemci ≈ 3,9 GB)."
    Bilgi "  WARNING: $bosGb GB free on this drive; a first install needs ≈ 22 GB (NVIDIA GPU) or ≈ 14 GB (CPU only) (the download cache can be deleted afterwards: GPU ≈ 7.8 GB, CPU ≈ 3.9 GB)."
  }
}

if (Adim "uv") {
  Bilgi "== uv 0.13.5"
  $zip = Join-Path $Araclar "uv-0.13.5.zip"
  Indir $UV_URL $zip $UV_SHA
  if (-not (Test-Path $Uv)) { Expand-Archive -Force $zip $UvDir }
  & $Uv --version
  Bilgi "UV_OK"
}

if (Adim "python") {
  Bilgi "== Python $PY_SURUM (yalnız $env:UV_PYTHON_INSTALL_DIR)"
  & $Uv python install $PY_SURUM --no-bin
  if ($LASTEXITCODE -ne 0) { throw "Python kurulamadı (internet bağlantısını denetleyip yeniden çalıştırın)" }
  Bilgi "PYTHON_OK"
}

if (Adim "paketler") {
  $profil = "gpu.txt"
  if ($Cpu) { $profil = "cpu.txt" }
  elseif (-not (NvidiaVar)) {
    Bilgi "  NVIDIA GPU bulunamadı: işlemci profili kurulacak (sorun değil; dublaj işlemciyle çalışır, daha yavaştır)"
    Bilgi "  No NVIDIA GPU found: installing the CPU profile (works, only slower)"
    $profil = "cpu.txt"
  }
  Bilgi "== paketler ($profil; torch ~3 GB GPU, ~0,3 GB işlemci)"
  if (-not (Test-Path $Py)) { & $Uv venv $Venv --python $PY_SURUM; if ($LASTEXITCODE -ne 0) { throw "venv kurulamadı" } }
  Paketle $profil
  & $Uv pip install --python $Py --no-deps -e $Repo
  if ($LASTEXITCODE -ne 0) { throw "DubWorld paketi kurulamadı" }
  Set-Content -Path (Join-Path $Venv "dublaj_profil.txt") -Value $profil -Encoding UTF8
  Bilgi "PAKETLER_OK"
}

if (Adim "modeller") {
  Bilgi "== modeller (sabit commit + sha256)"
  & $Py -B (Join-Path $Repo "scripts\modelleri_indir.py") --adim "supertonic,ceviri,stt,hizalama,konusmaci,ffmpeg"
  if ($LASTEXITCODE -ne 0) { throw "model indirme başarısız (inen dosyalar korunur; yeniden çalıştırın)" }
  Bilgi "MODELLER_OK"
}

foreach ($ek in @("demucs", "youtube", "parakeet", "speechmatics")) {
  if (Adim $ek) {
    Bilgi "== isteğe bağlı: $ek"
    # torch'a bağlı ekin işlemci profili için ayrı kilidi var (ek_<ad>_cpu.txt; GPU kilidindeki torch +cu128 kurulamaz).
    $ekKilit = "ek_$ek.txt"
    $profilNe = (Get-Content (Join-Path $Venv "dublaj_profil.txt") -ErrorAction SilentlyContinue)
    if ($profilNe -eq "cpu.txt" -and (Test-Path (Join-Path $Repo "requirements\ek_$($ek)_cpu.txt"))) { $ekKilit = "ek_$($ek)_cpu.txt" }
    Paketle $ekKilit
    if ($ek -eq "demucs") {
      # Model: htdemucs ağırlığı (MIT), sabit adres + sha256; çalışma anında torch.hub indirmesi olmaz.
      & $Py -B (Join-Path $Repo "scripts\modelleri_indir.py") --adim demucs
      if ($LASTEXITCODE -ne 0) { throw "Demucs modeli indirilemedi" }
    }
    if ($ek -eq "parakeet") {
      # Model: nvidia/parakeet-unified-en-0.6b'nin sherpa-onnx INT8 dönüşümü (k2-fsa), sabit commit + sha256.
      Bilgi "  Model lisansı: NVIDIA Open Model License (ticari kullanım şartlı; model kartı modelle birlikte iner)."
      & $Py -B (Join-Path $Repo "scripts\modelleri_indir.py") --adim parakeet
      if ($LASTEXITCODE -ne 0) { throw "Parakeet modeli indirilemedi" }
    }
    Bilgi "$($ek.ToUpper())_OK"
  }
}

function Ek-Kur([string]$Ad) {
  # Kilit varsa hash zorunlu; yoksa sabit sürüm + taban kilidi kısıt (taban paket sürümleri değişmez).
  $kilit = Join-Path $Repo "requirements\ek_$($Ad.Replace('-', '_')).txt"
  if (Test-Path $kilit) { Paketle (Split-Path $kilit -Leaf); return }
  $profil = (Get-Content (Join-Path $Venv "dublaj_profil.txt") -ErrorAction SilentlyContinue)
  if (-not $profil) { throw "Önce taban kurulum: -Adim paketler" }
  Bilgi "  kilit dosyası yok ($(Split-Path $kilit -Leaf)): sabit sürüm, hash doğrulaması YOK; kilit: scripts\kilitle.ps1"
  & $Uv pip install --python $Py --index-strategy unsafe-best-match -c (Join-Path $Repo "requirements\$profil") @($EK_SABIT[$Ad])
  if ($LASTEXITCODE -ne 0) { throw "isteğe bağlı paket kurulamadı: $Ad" }
}

if ((Adim "telegram-sunucu") -and -not (Adim "telegram")) { $Adimlar = @($Adimlar) + "telegram" }
foreach ($ek in @("akilli-kare", "galeri", "telegram")) {
  if (Adim $ek) {
    Bilgi "== isteğe bağlı: $ek"
    Ek-Kur $ek
    Bilgi "$($ek.ToUpper().Replace('-', '_'))_OK"
  }
}

if (Adim "telegram-sunucu") {
  # Yerel Bot API sunucusu: tek komut; Docker/WSL seçimi, gizli başlatma, gerçek getMe ve .env adresi Python'da
  # (src\dublaj_hatti\bolum_80_arayuz_ve_teslim\telegram_botu\yerel_sunucu.py). Tekrar çalıştırmak güvenlidir.
  Bilgi "== isteğe bağlı: telegram-sunucu (yerel Bot API sunucusu, 2000 MB)"
  & (Join-Path $Venv "Scripts\dubla-telegram.exe") sunucu kur
  if ($LASTEXITCODE -ne 0) { throw "Telegram yerel sunucusu kurulamadı (yukarıdaki satır; docs\tarifler\telegram_buyuk_dosya.md §6)" }
  Bilgi "TELEGRAM_SUNUCU_OK"
}

if (Adim "tts-xtts") {
  Bilgi "== XTTS v2 (coqui-tts, ayrı sanal ortam)"
  Bilgi "  UYARI: XTTS v2 ağırlıkları Coqui Public Model License altındadır: yalnız TİCARİ OLMAYAN kullanım (https://coqui.ai/cpml)."
  Bilgi "  Referans ses yalnız kendi sesiniz ya da sahibinin açık izin verdiği ses olabilir (ETHICS.md)."
  if (-not $TicariOlmayanKabul) { throw "Bu adım için lisansı okuyup -TicariOlmayanKabul ile yeniden çalıştırın" }
  if (-not (Test-Path $Py)) { throw "Önce taban kurulum: -Adim paketler" }
  $xKok = Join-Path $Varlik "tts_motorlari\xtts"
  $xVenv = Join-Path $xKok "venv"
  $xPy = Join-Path $xVenv "Scripts\python.exe"
  if (-not (Test-Path $xPy)) { & $Uv venv $xVenv --python $PY_SURUM; if ($LASTEXITCODE -ne 0) { throw "XTTS venv kurulamadı" } }
  $profil = (Get-Content (Join-Path $Venv "dublaj_profil.txt") -ErrorAction SilentlyContinue)
  # Ayrı ortamın tam kilidi (torch dahil, hash zorunlu; scripts\kilitle.ps1 -YalnizXtts üretir).
  $xKilit = if ($profil -eq "gpu.txt") { "xtts_venv_gpu.txt" } else { "xtts_venv_cpu.txt" }
  & $Uv pip install --python $xPy --require-hashes --index-strategy unsafe-best-match -r (Join-Path $Repo "requirements\$xKilit")
  if ($LASTEXITCODE -ne 0) { throw "XTTS (coqui-tts) kurulamadı: $xKilit" }
  # Lisans onayı yerel dosyaya yazılır (ses.xtts_lisans_onayi ile aynı kayıt); ağırlık ilk kullanımda iner.
  & $Py -m dublaj_hatti.bolum_50_seslendirme.xtts_tts onay --kabul
  if ($LASTEXITCODE -ne 0) { throw "XTTS lisans onayı kaydedilemedi" }
  $envDosya = Join-Path $Repo ".env"
  $satir = "DUBLAJ_XTTS_PYTHON=$xPy"
  if (-not ((Test-Path $envDosya) -and (Select-String -Path $envDosya -Pattern '^DUBLAJ_XTTS_PYTHON=' -Quiet))) {
    Add-Content -Path $envDosya -Value $satir -Encoding UTF8
    Bilgi "  .env: $satir"
  }
  Bilgi "XTTS_OK (kullanım: --ayar ses.motor=xtts --ayar ses.xtts_referans_ses=<kendi sesiniz.wav>)"
}

if (Adim "hizalama-diller") {
  # en/tr dışındaki kaynak diller için CTC kelime zamanı modelleri (ja, zh; Apache-2.0), sabit commit + sha256 (~2,5 GB).
  Bilgi "== isteğe bağlı: hizalama-diller (ja, zh)"
  & $Py -B (Join-Path $Repo "scripts\modelleri_indir.py") --adim hizalama-diller
  if ($LASTEXITCODE -ne 0) { throw "CTC dil modelleri indirilemedi (inen dosyalar korunur; yeniden çalıştırın)" }
  Bilgi "HIZALAMA-DILLER_OK"
}

if (Adim "crisper") {
  Bilgi "== CrisperWhisper 2.0 Turbo (13. motor)"
  Bilgi "  UYARI: model ağırlığı TİCARİ OLMAYAN kullanım lisanslıdır (nyralabs/CrisperWhisper2.0_turbo model kartı)."
  if (-not $TicariOlmayanKabul) { throw "Bu adım için lisansı okuyup -TicariOlmayanKabul ile yeniden çalıştırın" }
  Kardes-Repo-Denetle $STT_REPO "DUBLAJ_STT_REPO_URL"
  & $Py -B (Join-Path $Repo "scripts\crisper_kur.py") --stt-repo $STT_REPO --stt-commit $STT_COMMIT
  if ($LASTEXITCODE -ne 0) { throw "CrisperWhisper kurulumu başarısız" }
  & $Py -B (Join-Path $Repo "scripts\modelleri_indir.py") --adim crisper
  Bilgi "CRISPER_OK"
}

if (Adim "voxcpm2") {
  Bilgi "== VoxCPM2 (kardeş repo $VOX_COMMIT)"
  # Ön denetim: kardeş kurulum git ile alınır ve PATH'te 64-bit Python 3.10+ arar. Bu kurulumun kendi Python'u
  # (uv, runtime_assets\python) sistem PATH'ine yazılmaz; yalnız bu süreç ve alt süreçleri için PATH başına eklenir.
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "VoxCPM2 adımı git ister: winget install Git.Git (ya da git-scm.com), yeni bir PowerShell açıp yeniden çalıştırın"
  }
  $uvPy = (& $Uv python find $PY_SURUM 2>$null | Select-Object -First 1)
  if ($LASTEXITCODE -ne 0 -or -not $uvPy -or -not (Test-Path $uvPy)) { throw "Python $PY_SURUM bulunamadı (önce: -Adim uv,python)" }
  $env:PATH = (Split-Path $uvPy) + ";" + $env:PATH
  Bilgi "  kardeş kurulum için Python: $uvPy"
  $vox = Join-Path $Varlik "tts_motorlari\voxcpm2\repo"
  if (-not (Test-Path (Join-Path $vox ".git"))) {
    Kardes-Repo-Denetle $VOX_REPO "DUBLAJ_TTS_REPO_URL"
    git clone --quiet $VOX_REPO $vox
    if ($LASTEXITCODE -ne 0) { throw "VoxCPM2 reposu alınamadı" }
  }
  git -C $vox fetch --quiet origin $VOX_COMMIT
  git -C $vox checkout --quiet $VOX_COMMIT
  if ((git -C $vox rev-parse HEAD) -ne $VOX_COMMIT) { throw "VoxCPM2 commit doğrulanamadı" }
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $vox "scripts\kur.ps1") -Kok (Join-Path $Varlik "tts_motorlari\voxcpm2\kok")
  if ($LASTEXITCODE -ne 0) { throw "VoxCPM2 kurulumu başarısız" }
  Bilgi "VOXCPM2_OK"
}

if (Adim "tts-ema") {
  # EMA Lightning: paket ana sanal ortama (torch zaten taban kilidinde; işlemci profilinde ayrı kilit), ağırlık
  # resmî model deposundan sabit commit + sha256 (scripts\modeller.json adım tts-ema). ONNX dosyaları yayımlanmadığı
  # için aynı ağırlıktan bu makinede üretilir ve torch ile karşılaştırılır (docs\motorlar\ema_lightning.md).
  Bilgi "== isteğe bağlı: tts-ema (EMA Lightning, yalnız Türkçe)"
  if (-not (Test-Path $Py)) { throw "Önce taban kurulum: -Adim paketler" }
  $profilEma = (Get-Content (Join-Path $Venv "dublaj_profil.txt") -ErrorAction SilentlyContinue)
  if ($profilEma -eq "cpu.txt") { Paketle "ek_tts_ema_cpu.txt" } else { Paketle "ek_tts_ema.txt" }
  & $Py -B (Join-Path $Repo "scripts\modelleri_indir.py") --adim tts-ema
  if ($LASTEXITCODE -ne 0) { throw "EMA ağırlığı indirilemedi (inen dosyalar korunur; yeniden çalıştırın)" }
  & $Py -B -m dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts aktar
  if ($LASTEXITCODE -eq 2) {
    Bilgi "  UYARI: ONNX eşitlik denetimi geçmedi; EMA işlemcide torch ile çalışır (daha yavaş). GPU yolu etkilenmez."
  } elseif ($LASTEXITCODE -ne 0) { throw "EMA ONNX dışa aktarımı başarısız" }
  Bilgi "TTS_EMA_OK (kullanım: --ayar ses.motor=ema_lightning [--ayar ses.ema_cihaz=cpu])"
}

if (Adim "kontrol") {
  Bilgi "== kontrol"
  $profil = (Get-Content (Join-Path $Venv "dublaj_profil.txt") -ErrorAction SilentlyContinue)
  $kod = "import torch; print('torch', torch.__version__); ok = torch.cuda.is_available()`n" +
         "if ok:`n    x = torch.ones((64, 64), device='cuda'); ok = float((x @ x).sum()) == 64.0**3`n" +
         "print('cuda_cekirdek', ok, torch.cuda.get_device_name(0) if ok else '-')"
  $torchCikti = & $Py -c $kod
  $torchCikti | ForEach-Object { Write-Host $_ }
  if ($LASTEXITCODE -ne 0) { throw "torch denetimi başarısız (onarım: -Adim paketler,kontrol; docs\kurulum.md §12 madde 6)" }
  if ($profil -eq "gpu.txt") {
    $tv = & $Py -c "import torch; print(torch.version.cuda or '')"
    if (-not $tv) { throw "GPU profili kuruldu ama torch CUDA'sız (yanlış tekerlek; onarım: -Adim paketler,kontrol)" }
    if ("$torchCikti" -match "cuda_cekirdek False") {
      Bilgi "  UYARI: NVIDIA kartı bulundu ama GPU çalıştırılamadı; dublaj işlemciyle (daha yavaş) çalışır."
      Bilgi "  Çoğunlukla sürücü eskidir (R570 ya da yenisi gerekir); docs\kurulum.md §1 ve §12 madde 7."
      Bilgi "  WARNING: NVIDIA card found but the GPU could not run; dubbing will use the CPU (slower). Usually an old driver."
    }
  }
  & (Join-Path $Venv "Scripts\dubla.exe") kontrol
  if ($LASTEXITCODE -ne 0) { throw "dubla kontrol başarısız" }
  Bilgi "KONTROL_OK"
}

Bilgi "KURULUM_OK"
Bilgi ""
Bilgi "Kurulum bitti. Arayüzü açmak için repo klasöründeki arayuz.cmd dosyasına çift tıklayın."
Bilgi "Install finished. To open the app, double-click arayuz.cmd in the repository folder."
Bilgi "Komut satırı / command line: .venv\Scripts\dubla.exe <video.mp4>   (web: web.cmd)"
