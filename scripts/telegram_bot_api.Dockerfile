# Resmî Telegram Bot API sunucusu (tdlib/telegram-bot-api, Boost Software License 1.0) resmî kaynaktan, sabit
# commit'te derlenir. Kullanım: dubla-telegram sunucu kur --kaynaktan (hazır imaj yerine).
# Çalışma: --local (2000 MB), iş klasörü /var/lib/telegram-bot-api, geçici klasör /tmp/telegram-bot-api.
# Kimlik değerleri imaja girmez; çalışırken ortam değişkeni olarak verilir (TELEGRAM_API_ID, TELEGRAM_API_HASH).
FROM debian:bookworm-slim AS derleme
ARG COMMIT
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates make git zlib1g-dev libssl-dev \
    gperf cmake g++ && rm -rf /var/lib/apt/lists/*
RUN git clone --recursive https://github.com/tdlib/telegram-bot-api.git /kaynak && cd /kaynak \
    && git checkout "${COMMIT}" && git submodule update --init --recursive \
    && mkdir build && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX:PATH=/usr/local .. \
    && cmake --build . --target install -j "$(nproc)"

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates zlib1g libssl3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --home /var/lib/telegram-bot-api telegram-bot-api \
    && mkdir -p /var/lib/telegram-bot-api /tmp/telegram-bot-api \
    && chown telegram-bot-api /var/lib/telegram-bot-api /tmp/telegram-bot-api
COPY --from=derleme /usr/local/bin/telegram-bot-api /usr/local/bin/telegram-bot-api
USER telegram-bot-api
EXPOSE 8081
ENTRYPOINT ["/bin/sh", "-c", "exec telegram-bot-api --http-port=8081 --dir=/var/lib/telegram-bot-api --temp-dir=/tmp/telegram-bot-api ${TELEGRAM_LOCAL:+--local}"]
