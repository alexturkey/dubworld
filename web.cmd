@echo off
rem Yerel web arayuzu: yalniz bu bilgisayardan acilir (127.0.0.1). Kapatmak icin bu pencerede Ctrl+C.
chcp 65001 >nul
if not exist "%~dp0.venv\Scripts\dubla-web.exe" (
  echo Kurulum bulunamadi: once bu klasordeki kur.cmd dosyasina cift tiklayin.
  echo Not installed yet: double-click kur.cmd in this folder first.
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\dubla-web.exe" %*
