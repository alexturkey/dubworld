---
name: telegram-buyuk-dosya
description: "Set up large-file delivery over Telegram (up to 2000 MB instead of 50 MB) with the local Bot API server, for a user who knows nothing about Docker or servers: get api_id/api_hash from my.telegram.org with them screen by screen, run one install command, verify with dubla kontrol, send a test video. Use when the user says 'video too big for Telegram', '50 MB', '2 GB', 'large file', 'büyük dosya', 'Telegram'a gelmedi', 'yerel sunucu', 'local Bot API', 'api_id', 'api_hash', 'my.telegram.org', or when dubla kontrol shows 'telegram yerel sunucu'."
---

# Large files over Telegram / Telegram ile büyük dosya

Türkçe özet en altta. / Turkish summary at the end.

## When to use

The optional Telegram bot works ([telegram-botu-kurulumu](../telegram-botu-kurulumu/SKILL.md)) but finished videos
over 50 MB do not arrive, or the user wants 2 GB delivery from the start. The cloud Bot API caps a bot at 50 MB per
sent file and 20 MB per downloaded file; Telegram's local Bot API server lifts both to 2000 MB. Why this design:
[ADR 0018](../../../docs/adr/0018-local-bot-api-server-for-large-files.md).

## Rules for the agent

- The user does **not** need to understand Docker, WSL or servers. Do every technical step yourself; ask the user only
  for what only they can do: log in to my.telegram.org with their phone and put two values into `.env`.
- `api_id`, `api_hash` and the bot token are secrets. They go **only into the user's `.env`**. Never ask the user to
  paste them into the chat, never print them, never put them in a command line, issue, commit or screenshot. Check
  `git check-ignore .env` before editing `.env`.
- Never open visible windows for the user: the install starts Docker Desktop hidden and the server hidden.
- Do not delete containers, images or folders that the install did not create. `dubla-telegram sunucu kaldir` removes
  only `dubworld-telegram-bot-api` and its network.
- Do not run `dubla-telegram sunucu bulut-cikis` (logOut) unless the user wants incoming updates through the local
  server and understands that the bot cannot return to the cloud endpoint for 10 minutes.

## Steps

1. **Check the state:** `dubla kontrol` → the line `telegram yerel sunucu:`. `HAZIR` = done (go to step 6).
2. **Bot first:** if `TELEGRAM_BOT_TOKEN` or `TELEGRAM_IZINLI_KULLANICILAR` is empty, follow
   [telegram-botu-kurulumu](../telegram-botu-kurulumu/SKILL.md) first.
3. **api_id / api_hash (the user, guided screen by screen):** read
   [docs/tarifler/telegram_buyuk_dosya.md](../../../docs/tarifler/telegram_buyuk_dosya.md) §2 aloud step by step:
   my.telegram.org → phone number with country code → the code arrives **inside the Telegram app** → API development
   tools → App title (any), Short name (5-32 letters/digits), Platform Desktop → Create application → copy
   `App api_id` and `App api_hash` into `.env` as `TELEGRAM_API_ID=` and `TELEGRAM_API_HASH=`. Wait for "done" after
   each step. If the form says "ERROR", wait a minute and change the short name.
4. **Install (you):**
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim telegram-sunucu
   ```
   (Linux/macOS or an existing environment: `dubla-telegram sunucu kur`.) Marker: `TELEGRAM_SUNUCU_OK`. Preview
   without changes: `dubla-telegram sunucu kur --kuru`. It picks Docker if installed, otherwise builds the official
   source (inside WSL on Windows, 10-30 min), checks the port, waits for a real `getMe` and writes
   `TELEGRAM_YEREL_SUNUCU` into `.env`.
5. **Verify:** `dubla kontrol` → `telegram yerel sunucu: HAZIR http://127.0.0.1:<port> (en çok 2000 MB)`.
6. **Test delivery:** make a synthetic video (no real content) and send it:
   ```powershell
   ffmpeg -nostdin -v error -f lavfi -i testsrc2=s=1280x720:r=30:d=60 -f lavfi -i sine=d=60 -c:v libx264 -b:v 11M -minrate 11M -maxrate 11M -bufsize 11M -x264-params nal-hrd=cbr -c:a aac -shortest test_buyuk.mp4
   dubla-telegram gonder test_buyuk.mp4 --metin "Large file test"
   ```
   Expected: `CONFIRMED: ... tur=video` and the video arrives with a preview. Then delete `test_buyuk.mp4`.
7. **Use:** restart the bot (`dubla-telegram`); results up to 2000 MB now arrive as playable videos. For a plain file
   instead of a video: `--belge` or `TELEGRAM_TESLIM_BICIMI=belge`.

## Common errors

| Symptom | Fix |
|---|---|
| `TELEGRAM_API_ID ve TELEGRAM_API_HASH .env'de boş` | step 3 |
| `Ne Docker ne WSL bulundu` | install one: `winget install -e --id Docker.DockerDesktop` or `wsl --install -d Ubuntu` (both may ask for a restart), then step 4 again |
| `Docker hizmeti 90 sn'de hazır olmadı` | restart the computer and run step 4 again, or `dubla-telegram sunucu kur --kip derleme` |
| `getMe cevabı vermedi` | `dubla-telegram sunucu durum`: wrong token/api values, or the server cannot reach Telegram (network, firewall) |
| `AYARLI AMA ÇALIŞMIYOR` | `dubla-telegram sunucu baslat` |
| `NEEDS_LOCAL_SERVER` | the file is over 50 MB and no local server is configured: steps 3-5 |
| `TOO_LARGE` | over 2000 MB: Telegram never accepts it; encode smaller |
| `UNKNOWN` / `MANUAL_REVIEW` | the file was sent but no answer came; it was not re-sent on purpose (no duplicate). Look at the chat |
| server disk full | `dubla-telegram sunucu temizle` |

## Related

[docs/tarifler/telegram_buyuk_dosya.md](../../../docs/tarifler/telegram_buyuk_dosya.md) ·
[ADR 0018](../../../docs/adr/0018-local-bot-api-server-for-large-files.md) ·
[docs/motorlar/telegram_botu.md](../../../docs/motorlar/telegram_botu.md) · [.env.example](../../../.env.example)

## Türkçe özet

Bulut Bot API botu 50 MB göndermeyle, 20 MB indirmeyle sınırlar; yerel Bot API sunucusu ikisini de 2000 MB yapar.
Kullanıcı Docker'ı bilmek zorunda değildir: asistan her teknik adımı kendisi yapar, kullanıcıdan yalnız
my.telegram.org'a telefonuyla girip `api_id` / `api_hash`'i kendi `.env`'sine yazmasını ister (tarif §2, ekran ekran).
Sonra: `kur.ps1 -Adim telegram-sunucu` (Docker varsa Docker, yoksa WSL'de derleme; gizli başlatma, gerçek `getMe`,
`.env`'ye adres) → `dubla kontrol` HAZIR → sentetik test videosu `dubla-telegram gonder` (beklenen `tur=video`).
Video her boyutta önizlemeli video olarak gider; düz dosya için `--belge`. Gizli değerler sohbete, komut satırına,
commit'e asla girmez.
