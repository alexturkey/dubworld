@echo off
rem DubWorld kurulumu: her sey bu klasore kurulur (Python, paketler, modeller, ffmpeg).
rem NVIDIA GPU varsa GPU profili, yoksa islemci profili kendiliginden secilir. Islemciyi zorlamak icin: kur.cmd -Cpu
rem Install: everything goes into this folder; GPU or CPU profile is chosen automatically.
chcp 65001 >nul
echo DubWorld kuruluyor. Ilk kurulum yaklasik 9-13 GB indirir ve uzun surebilir; bu pencereyi kapatmayin.
echo Installing DubWorld. A first install downloads about 9-13 GB and can take a while; keep this window open.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\kur.ps1" %*
echo.
pause
