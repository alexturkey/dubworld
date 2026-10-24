@echo off
rem Masaustu arayuzu (Onerilen akis + Gelismis). / Desktop app.
if not exist "%~dp0.venv\Scripts\dubla-gui.exe" (
  echo Kurulum bulunamadi: once bu klasordeki kur.cmd dosyasina cift tiklayin.
  echo Not installed yet: double-click kur.cmd in this folder first.
  pause
  exit /b 1
)
start "" "%~dp0.venv\Scripts\dubla-gui.exe"
