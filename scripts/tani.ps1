<#
.SYNOPSIS
  Yerel teshis raporu / Local diagnosis report (Windows). Offline, leak-proof, sends nothing.

.DESCRIPTION
  Prints a short report you can paste into an issue or give to your AI assistant: system, GPU, free disk, install
  profile and, if you give a log, the DW-E-... error code it recognises with its first step (docs\hata_imzalari.json).
  It sends NOTHING anywhere, uses no network, writes no file and changes nothing: the output only goes to this window.
  Personal data is removed before printing: the repository folder becomes <ROOT>, your user profile folder <HOME>,
  your user name <USER>, e-mail addresses <EMAIL>, token-like strings <TOKEN>. The filter is a best effort, not a
  guarantee: read the report once before you paste it.
  This file is ASCII on purpose (Windows PowerShell 5.1 reads UTF-8 without BOM as ANSI).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\tani.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\tani.ps1 -Log kur.log -Son 30
#>
[CmdletBinding()]
param(
  [string]$Log = "",
  [int]$Son = 30
)
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Kullanici = "$env:USERNAME"
$Ev = "$env:USERPROFILE"

function Temizle([string]$Satir) {
  # Order matters: longest personal strings first.
  if ($Repo) { $Satir = $Satir.Replace($Repo, "<ROOT>") }
  if ($Ev) { $Satir = $Satir.Replace($Ev, "<HOME>") }
  $Satir = [regex]::Replace($Satir, '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '<EMAIL>')
  $Satir = [regex]::Replace($Satir, '\b(?:hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|gsk_[A-Za-z0-9]{30,})\b', '<TOKEN>')
  if ($Kullanici.Length -ge 3) { $Satir = [regex]::Replace($Satir, [regex]::Escape($Kullanici), '<USER>', 'IgnoreCase') }
  return $Satir
}
function Yaz([string]$Satir) { Write-Host (Temizle $Satir) }

Yaz "== DubWorld tani / diagnosis (offline; nothing is sent, nothing is written)"
try { $os = (Get-CimInstance Win32_OperatingSystem -ErrorAction Stop); Yaz "OS: $($os.Caption) $($os.Version)" } catch { Yaz "OS: unknown" }
Yaz "PowerShell: $($PSVersionTable.PSVersion)"
try {
  $ram = [math]::Round((Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).TotalPhysicalMemory / 1GB)
  Yaz "RAM: $ram GB"
} catch { Yaz "RAM: unknown" }
$smi = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
if ($smi) {
  $g = & $smi.Source --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>$null
  if ($LASTEXITCODE -eq 0 -and $g) { Yaz "GPU: $(($g | Select-Object -First 1))" } else { Yaz "GPU: nvidia-smi present but did not answer" }
} else { Yaz "GPU: no NVIDIA GPU found (CPU profile works, only slower)" }
try { Yaz ("Disk free (repo drive): " + [math]::Floor((Get-Item $Repo).PSDrive.Free / 1GB) + " GB") } catch { Yaz "Disk free: unknown" }
$profil = Join-Path $Repo ".venv\dublaj_profil.txt"
if (Test-Path $profil) { Yaz ("Install profile: " + ((Get-Content $profil -ErrorAction SilentlyContinue | Select-Object -First 1))) } else { Yaz "Install profile: not installed yet (.venv missing)" }
Yaz ("Folders: .venv=" + (Test-Path (Join-Path $Repo ".venv")) + " runtime_assets=" + (Test-Path (Join-Path $Repo "runtime_assets")))

if (-not $Log) {
  $varsayilan = Join-Path $Repo "kur.log"
  if (Test-Path $varsayilan) { $Log = $varsayilan }
}
if ($Log -and (Test-Path $Log)) {
  $satirlar = @(Get-Content -Path $Log -Encoding UTF8 -ErrorAction SilentlyContinue)
  Yaz ""
  Yaz "== Log: last $Son lines (personal data removed)"
  foreach ($s in ($satirlar | Select-Object -Last $Son)) {
    Yaz $s
  }
  $imzaDosyasi = Join-Path $Repo "docs\hata_imzalari.json"
  if (Test-Path $imzaDosyasi) {
    $imzalar = (Get-Content -Raw -Encoding UTF8 $imzaDosyasi | ConvertFrom-Json).kodlar
    $metin = ($satirlar -join "`n")
    $bulunan = @($imzalar | Where-Object { $metin.Contains($_.imza) })
    Yaz ""
    if ($bulunan.Count -eq 0) {
      Yaz "== Error code: none of the known signatures is in this log (docs\troubleshooting.md lists them)."
    } else {
      Yaz "== Error code(s) recognised in the log"
      foreach ($b in $bulunan) {
        Yaz "[$($b.kod)] $($b.imza)"
        Yaz "  EN: $($b.ilk_adim_en)"
        Yaz "  TR: $($b.ilk_adim_tr)"
      }
    }
  }
} else {
  Yaz ""
  Yaz "No log given. To read a log: scripts\tani.ps1 -Log kur.log"
}
Yaz ""
Yaz "== DEVIATIONS / SAPMA (read-only / salt okur)"
$pc = @(Get-Command python -All -ErrorAction SilentlyContinue | Select-Object -First 3)
if ($pc.Count -gt 0) {
  if ($pc[0].Source -match 'WindowsApps') { Yaz "  first python on PATH: Microsoft Store shortcut (not a real Python) / PATH'te ilk python: Store kisayolu" }
  else { Yaz ("  first python on PATH: " + ((& $pc[0].Source --version 2>&1) -join " ")) }
} else { Yaz "  no python on PATH (the installer uses its own) / PATH'te python yok" }
$gitK = Get-Command git -ErrorAction SilentlyContinue
if ($gitK -and (Test-Path -LiteralPath (Join-Path $Repo ".git"))) {
  $gs = @(& $gitK.Source --no-optional-locks -C $Repo status --short -uno 2>$null | ForEach-Object { "$_".Trim() } | Where-Object { $_ } | Select-Object -First 40)
  if ($gs.Count -eq 0) { Yaz "  git: tracked files unchanged / izlenen dosyalar degismemis" }
  else { Yaz "  git: $($gs.Count) tracked file(s) changed (names only) / izlenen dosya degismis (yalniz adlar):"; foreach ($g in $gs) { Yaz "    $g" } }
} else { Yaz "  git: not a git copy or git missing / kopya degil ya da git yok" }
$dEnv = @(Get-ChildItem Env: | Where-Object { $_.Name -like 'DUBLAJ_*' } | Sort-Object Name | ForEach-Object { "$($_.Name)" })
if ($dEnv.Count) { Yaz ("  DUBLAJ_* variables set (names only) / DUBLAJ_* degiskenleri (yalniz adlar): " + ($dEnv -join " ")) } else { Yaz "  DUBLAJ_* variables: none / yok" }
Yaz ""
Yaz "Paste this report into an issue (Bug report / Install problem). Check it once: remove anything private that is left."
exit 0
