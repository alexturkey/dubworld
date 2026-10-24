<#
.SYNOPSIS
  Kilit dosyalarını (requirements/*.txt) *.in dosyalarından yeniden üretir (hash'li, Python 3.11, Windows x64).

.DESCRIPTION
  Katkıcı yalnız requirements/*.in dosyasını değiştirir, bu betiği çalıştırır ve iki dosyayı birlikte gönderir.
  uv: $env:UV verilmişse o, yoksa runtime_assets\araclar\uv\uv.exe (kur.ps1 -Adim uv), yoksa PATH'teki uv.
  Var olan sürümler korunur (yalnız gerekeni değiştirir); hepsini yükseltmek için -Yukselt.
  İsteğe bağlı ek kilitleri (ek_*.txt) GPU kilidindeki sürümlere bağlıdır. torch'a bağlı ekler (demucs) torch +cu128
  taşır; onlar için işlemci kilidine bağlı ek_<ad>_cpu.txt da üretilir.
  XTTS v2 AYRI sanal ortamda koşar (kur.ps1 -Adim tts-xtts): onun tam kilidi torch dahil profil başına
  xtts_venv_gpu.txt / xtts_venv_cpu.txt (xtts_venv.in; sürümler ek_tts_xtts.txt + gpu/cpu kilidine bağlı).
  Yalnız bu iki kilit: -YalnizXtts.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kilitle.ps1
#>
[CmdletBinding()]
param([switch]$Yukselt, [switch]$YalnizXtts)
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Req = Join-Path $Repo "requirements"
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$Uv = $env:UV
if (-not $Uv) { $Uv = Join-Path $Repo "runtime_assets\araclar\uv\uv.exe" }
if (-not (Test-Path $Uv)) { $Uv = (Get-Command uv -ErrorAction Stop).Source }
$Ortak = @("--python-version", "3.11", "--python-platform", "x86_64-pc-windows-msvc", "--generate-hashes",
           "--index-strategy", "unsafe-best-match", "--no-header")
if ($Yukselt) { $Ortak += "--upgrade" }

function Surumler([string[]]$Kilitler) {
  # Kilitteki "ad==sürüm" satırları (hash'siz kısıt dosyası için).
  return @($Kilitler | ForEach-Object { Get-Content $_ } | Where-Object { $_ -match '^[A-Za-z0-9_.\-\[\]]+==\S+' } |
           ForEach-Object { ($_ -split ' ')[0] })
}

function Xtts-Kilitle {
  # XTTS ayrı sanal ortamı: coqui-tts + torch/torchaudio, hash'li ve profil başına tam kilit.
  foreach ($p in @(@("gpu", "cu128"), @("cpu", "cpu"))) {
    $cikti = "xtts_venv_$($p[0]).txt"
    $kisit = Join-Path $Req "_kisit_xtts.txt"
    [IO.File]::WriteAllLines($kisit, (Surumler @("$($p[0]).txt", "ek_tts_xtts.txt")), $Utf8)
    try {
      Write-Host "== $cikti"
      & $Uv pip compile "xtts_venv.in" -c "_kisit_xtts.txt" @Ortak --extra-index-url "https://download.pytorch.org/whl/$($p[1])" --emit-index-url -o $cikti
      if ($LASTEXITCODE -ne 0) { throw "kilit üretilemedi: $cikti" }
      $yol = Join-Path $Req $cikti
      [IO.File]::WriteAllLines($yol, @((Get-Content $yol -Encoding UTF8) -replace '-c _kisit_xtts\.txt', "-c $($p[0]).txt + ek_tts_xtts.txt (sürümler)"), $Utf8)
    } finally {
      Remove-Item -Force $kisit -ErrorAction SilentlyContinue
    }
  }
}

Push-Location $Req
try {
  if ($YalnizXtts) { Xtts-Kilitle; Write-Host "KILIT_OK"; return }
  foreach ($p in @(@("gpu", "cu128"), @("cpu", "cpu"))) {
    Write-Host "== $($p[0]).txt"
    & $Uv pip compile "$($p[0]).in" @Ortak --extra-index-url "https://download.pytorch.org/whl/$($p[1])" --emit-index-url -o "$($p[0]).txt"
    if ($LASTEXITCODE -ne 0) { throw "kilit üretilemedi: $($p[0])" }
  }
  # Ek kilitler GPU kilidindeki sürümlere bağlanır (hash'siz geçici kısıt dosyası).
  $kisit = Join-Path $Req "_kisit.txt"
  [IO.File]::WriteAllLines($kisit, (Surumler @("gpu.txt")), $Utf8)
  try {
    foreach ($in in Get-ChildItem "ek_*.in") {
      $cikti = [IO.Path]::ChangeExtension($in.Name, ".txt")
      Write-Host "== $cikti"
      & $Uv pip compile $in.Name -c "_kisit.txt" @Ortak --extra-index-url "https://download.pytorch.org/whl/cu128" -o $cikti
      if ($LASTEXITCODE -ne 0) { throw "kilit üretilemedi: $cikti" }
      $yol = Join-Path $Req $cikti
      [IO.File]::WriteAllLines($yol, @((Get-Content $yol -Encoding UTF8) -replace '-c _kisit\.txt', '-c gpu.txt (sürümler)'), $Utf8)
    }
  } finally {
    Remove-Item -Force $kisit -ErrorAction SilentlyContinue
  }
  # torch'a bağlı ek (ör. demucs) GPU kilidinde torch +cu128 taşır; işlemci profili onu kuramaz. Bu ekler için
  # işlemci kilidine bağlı ikinci kilit: ek_<ad>_cpu.txt (kur.ps1 işlemci profilinde onu seçer).
  $kisitCpu = Join-Path $Req "_kisit_cpu.txt"
  [IO.File]::WriteAllLines($kisitCpu, (Surumler @("cpu.txt")), $Utf8)
  try {
    foreach ($in in Get-ChildItem "ek_*.in") {
      $gpuKilit = [IO.Path]::ChangeExtension($in.Name, ".txt")
      if (-not (Select-String -Path $gpuKilit -Pattern '^torch==.*\+cu' -Quiet)) { continue }
      $cikti = [IO.Path]::GetFileNameWithoutExtension($in.Name) + "_cpu.txt"
      Write-Host "== $cikti"
      & $Uv pip compile $in.Name -c "_kisit_cpu.txt" @Ortak --extra-index-url "https://download.pytorch.org/whl/cpu" -o $cikti
      if ($LASTEXITCODE -ne 0) { throw "kilit üretilemedi: $cikti" }
      $yol = Join-Path $Req $cikti
      [IO.File]::WriteAllLines($yol, @((Get-Content $yol -Encoding UTF8) -replace '-c _kisit_cpu\.txt', '-c cpu.txt (sürümler)'), $Utf8)
    }
  } finally {
    Remove-Item -Force $kisitCpu -ErrorAction SilentlyContinue
  }
  Xtts-Kilitle
} finally {
  Pop-Location
}
Write-Host "KILIT_OK"
