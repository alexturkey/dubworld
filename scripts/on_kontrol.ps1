<#
.SYNOPSIS
  Pull request oncesi tek komut / One command before you open a pull request (Windows).

.DESCRIPTION
  Runs scripts\denetim.py (the same gates CI runs, no downloads, no GPU, nothing is written) and prints one
  SONUC line. If Python is missing it says so plainly instead of failing with a cryptic error.
  Python is looked for in this order: .venv (created by kur.cmd), the py launcher, python on PATH.
  Default is the quick set (about a minute); -Tam adds the CPU test suite (what CI's test-cpu job runs).
  Exit code is denetim.py's: 0 all passed, 1 a gate is red, 3 input/environment problem, 6 a gate did not run.
  This file is ASCII on purpose (Windows PowerShell 5.1 reads UTF-8 without BOM as ANSI).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\on_kontrol.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\on_kontrol.ps1 -Tam
#>
[CmdletBinding()]
param([switch]$Tam)
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Denetim = Join-Path $Repo "scripts\denetim.py"

$Py = $null
$Onek = @()
$venvPy = Join-Path $Repo ".venv\Scripts\python.exe"
if (Test-Path $venvPy) { $Py = $venvPy }
elseif (Get-Command py.exe -ErrorAction SilentlyContinue) { $Py = (Get-Command py.exe).Source; $Onek = @("-3") }
elseif (Get-Command python.exe -ErrorAction SilentlyContinue) { $Py = (Get-Command python.exe).Source }

if (-not $Py) {
  Write-Host "PYTHON YOK / PYTHON NOT FOUND: the pre-PR check needs Python 3.10 or newer."
  Write-Host "  Easiest: double-click kur.cmd (it installs a private Python inside this folder), then run this again."
  Write-Host "  Or install Python from python.org and run this again."
  Write-Host "  Python yok: kur.cmd dosyasina cift tiklayin (Python bu klasore kurulur), sonra bunu yeniden calistirin."
  Write-Host "SONUC: GIRDI HATALI (3)"
  exit 3
}

$mod = "--hizli"
if ($Tam) { $mod = "--tam" }
& $Py @Onek -I -X utf8 $Denetim $mod
exit $LASTEXITCODE
