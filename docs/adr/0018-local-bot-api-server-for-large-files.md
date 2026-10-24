# ADR 0018: Large Telegram deliveries go through a local Bot API server, as playable video

Status: accepted · Türkçe özet: [../muhendislik/kararlar.md](../muhendislik/kararlar.md#0018)

## Context
The optional Telegram bot delivers finished videos. The cloud Bot API (`api.telegram.org`) accepts at most 50 MB per
file from a bot and lets a bot download at most 20 MB; a dubbed video of a few minutes is usually larger. Above the
limit the cloud endpoint rejects the upload, and the client often sees only a generic network error after a delay.
Longer timeouts and retries therefore do not help; they only waste time and bandwidth. A file sent as a document
shows a file icon and has to be downloaded before it plays, which is a poor result for a video.

## Decision
- An optional **local Bot API server** (Telegram's open-source `tdlib/telegram-bot-api`, Boost Software License,
  `--local` mode) raises both limits to 2000 MB. The bot, `dubla-telegram gonder` and the readiness checks use it
  when `TELEGRAM_YEREL_SUNUCU` is set; otherwise everything stays on the cloud endpoint.
- **One command installs it** (`dubla-telegram sunucu kur`, `kur.ps1 -Adim telegram-sunucu`): Docker when available
  (Docker Desktop started hidden; ready-made image pinned by digest, or `--kaynaktan` to build the official source at a
  pinned commit), otherwise a build of the official source at the same commit (natively, or inside WSL on Windows).
  The user only provides `api_id` / `api_hash` from my.telegram.org and the bot token.
- **Network contract:** one named container on its own bridge network with IPv6 enabled, port published only on
  `127.0.0.1`, restart policy `unless-stopped`; a container whose network, port binding or local mode differs is
  recreated once, a matching one is never touched. Readiness is a real `getMe` through the local server within 60 s,
  never an open port or a running process.
- **Delivery rules** (`telegram_botu/teslim.py`): size checked before upload (above 2000 MB never attempted; above
  50 MB without a local server never attempted, with the install command in the message); videos go with
  `sendVideo` and `supports_streaming`, width/height/duration from ffprobe, an ffmpeg thumbnail and a faststart MP4
  (stream copy, no re-encoding); a document only on explicit request. Timeouts scale with file size; at most 3
  attempts with 15/30/60 s pauses; a timeout or a drop after the whole file was sent is never retried (the file may
  have arrived; a retry would deliver twice). Delivery counts only when Telegram returns the message; the answer's
  `video`/`document` field is recorded.
- **Ready-made image:** the default Docker path pulls `aiogram/telegram-bot-api`, a community build of the official
  BSL-1.0 source, pinned by digest (`image@sha256:...`), because it is one step for a first-time user and has been run
  in practice under this exact network contract; `--kaynaktan` builds the official `tdlib/telegram-bot-api` source at a
  pinned commit instead. Supply-chain risk: the image is built by a third party, so its contents are not verified
  against the source; the digest pin only guarantees that the same bytes are pulled every time, and a new digest is
  adopted only after review. The project's "no unofficial endpoints" rule targets unofficial API endpoints (for
  example scraped translation endpoints); this is a packaged build of an official open-source server, not an
  unofficial endpoint.
- **Secrets:** `api_id`, `api_hash` and the token live only in `.env`; they reach the container by variable name
  (`-e NAME`) and WSL through `WSLENV`, never on a command line.

## Consequences
- Results up to 2000 MB reach the phone as playable videos; nothing changes for users who do not install the server.
- A local server keeps downloaded files (`getFile` in local mode) until they are deleted; the bot deletes its own
  copies right after use and `dubla-telegram sunucu temizle` removes leftovers. Uploads need temporary space on the
  server of about the file size.
- The server's data folder contains a sub-folder named after the bot token; it is treated as secret.
- Docker-less installs compile C++ for 10-30 minutes and may need build tools; on Windows they need WSL.

## Alternatives considered
- Splitting files into 50 MB parts: the receiver must join them; no preview.
- Compressing below 50 MB: visible quality loss, against the pipeline's quality rules.
- Sending a link to cloud storage: an external account and a third party for every file.
- Telegram Premium on a user account: paid and not available to bots.
- Retrying or raising timeouts on the cloud endpoint: does not move the 50 MB limit.
- Choosing IPv4 or IPv6 in application code with sequential long waits: slows every network change and does not fix a
  container network that has no IPv6 route.
