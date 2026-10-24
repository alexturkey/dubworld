#!/usr/bin/env bash
# Resmî Telegram Bot API sunucusunu (tdlib/telegram-bot-api, Boost Software License 1.0) sabit commit'te derler.
# Kullanım: telegram_bot_api_derle.sh <commit> <kurulum_klasoru>
# Docker'sız yol içindir (Linux, macOS, Windows'ta WSL); Docker imajı da aynı adımları izler
# (scripts/telegram_bot_api.Dockerfile). Derleme araçları yoksa paket yöneticisiyle kurulur (sudo isteyebilir).
# Süre: ilk derleme 10-30 dk, ~2-3 GB geçici disk (kaynak + derleme klasörü, bitince silinir).
set -euo pipefail

COMMIT="${1:?commit gerekli}"
HEDEF="${2:?kurulum klasoru gerekli}"
HEDEF="${HEDEF/#\$HOME/$HOME}"
DEPO="https://github.com/tdlib/telegram-bot-api.git"

if [ -x "$HEDEF/bin/telegram-bot-api" ]; then
  echo "TELEGRAM_BOT_API_HAZIR $HEDEF/bin/telegram-bot-api"
  exit 0
fi

eksik=""
for arac in git cmake make gperf g++; do command -v "$arac" >/dev/null 2>&1 || eksik="$eksik $arac"; done
if [ -n "$eksik" ]; then
  echo "derleme araclari kuruluyor:$eksik"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y make git zlib1g-dev libssl-dev gperf cmake g++
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y gcc-c++ make git zlib-devel openssl-devel gperf cmake
  elif command -v brew >/dev/null 2>&1; then
    brew install gperf cmake openssl
  else
    echo "paket yoneticisi bulunamadi; kurun: git cmake make gperf g++ zlib openssl gelistirme paketleri" >&2
    exit 1
  fi
fi

CALISMA="$(mktemp -d)"
trap 'rm -rf "$CALISMA"' EXIT
git clone --recursive "$DEPO" "$CALISMA/kaynak"
cd "$CALISMA/kaynak"
git checkout "$COMMIT"
git submodule update --init --recursive
mkdir build && cd build
EK=""
if [ "$(uname)" = "Darwin" ]; then EK="-DOPENSSL_ROOT_DIR=$(brew --prefix openssl)"; fi
cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX:PATH="$HEDEF" $EK ..
cmake --build . --target install -j "$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)"
echo "TELEGRAM_BOT_API_HAZIR $HEDEF/bin/telegram-bot-api"
