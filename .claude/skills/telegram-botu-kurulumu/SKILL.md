---
name: telegram-botu-kurulumu
description: "Set up the optional Telegram remote-control bot step by step: create a bot with BotFather, put the token into .env, restrict it to the user's own numeric Telegram id, install the extra and start it. Use when the user says 'Telegram bot', 'control from my phone', 'BotFather', 'telegram botu kur', 'telefondan dublaj', 'bot does not answer', or 'TELEGRAM_BOT_TOKEN'."
---

# Telegram bot setup / Telegram botu kurulumu

Türkçe özet en altta. / Turkish summary at the end.

## When to use

The user wants to start dubbing jobs from their phone with their **own private bot**. The bot is optional and off by
default; it runs on the user's computer and talks only to the ids listed in `.env`.

## Safety rules for the agent

- The bot token is a password. The user creates and pastes it **into their own `.env` only**. Never ask the user to
  paste it into chat, an issue, a screenshot or a commit; never print it.
- The agent must not log in to Telegram or create the bot for the user: BotFather is an interactive chat in the
  user's own Telegram account. Guide each step and wait for the user to confirm it.
- `.env` is git-ignored; check with `git check-ignore .env` before writing anything into it.

## Steps

1. **Create the bot (user, in Telegram):** open the official **BotFather** account (blue check mark), send `/newbot`,
   give a display name and a unique username ending in `bot`. BotFather replies with a token shaped like
   `<digits>:<long key>`. Optional: `/setjoingroups` → Disable.
2. **Install the extra:**
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim telegram
   ```
   (or `pip install .[telegram]` in the same environment). Marker: `TELEGRAM_OK`.
3. **Fill `.env`:** copy `.env.example` to `.env` (if not done) and let the user fill:
   ```
   TELEGRAM_BOT_TOKEN=<token from BotFather>
   TELEGRAM_IZINLI_KULLANICILAR=
   ```
4. **Find the user's numeric id** with the official Bot API (no third-party bot): the user writes any message to the
   new bot, then opens `https://api.telegram.org/bot<TOKEN>/getUpdates` in their own browser and reads
   `"from":{"id": ...}`. Put that number into `TELEGRAM_IZINLI_KULLANICILAR` (several: comma separated). An empty
   list means the bot refuses to start.
5. **Start:**
   ```powershell
   dubla-telegram          # no window; Ctrl+C to stop; one instance at a time
   ```
   The user sends `/start` to the bot.
6. **Use:** send a video (up to 20 MB, Bot API limit) or an `https://` link (needs the `youtube` or `galeri` extra);
   `/ayarlar` (session-only choices), `/isler`, `/durum [no]`, `/iptal [no]`, `/kontrol`. Results under 50 MB come
   back to the chat; larger ones stay in the output folder.

## Common errors

| Symptom | Fix |
|---|---|
| `TELEGRAM_BOT_TOKEN biçimi geçersiz` | token copied incompletely; get it again from BotFather |
| `TELEGRAM_IZINLI_KULLANICILAR boş` | step 4 |
| Bot does not answer | the id is not in the list, or the bot is not running; read the console log |
| `bot zaten çalışıyor` | another instance is open; close it |
| `Conflict: terminated by other getUpdates` | the same token runs on another machine; stop one |
| Token leaked | BotFather `/revoke`, put the new token into `.env` |

## Related

[docs/tarifler/telegram_botu.md](../../../docs/tarifler/telegram_botu.md) (full recipe, Turkish) ·
[docs/motorlar/telegram_botu.md](../../../docs/motorlar/telegram_botu.md) · [.env.example](../../../.env.example) ·
[SECURITY.md](../../../SECURITY.md)

## Türkçe özet

Bot isteğe bağlı ve kapalıdır; kullanıcının bilgisayarında çalışır, yalnız `.env`'deki sayısal kimliklere cevap verir.
Adımlar: BotFather'da `/newbot` (kullanıcı kendisi yapar) → `kur.ps1 -Adim telegram` → `.env`'ye
`TELEGRAM_BOT_TOKEN` → kendi kimliğini resmî `getUpdates` adresiyle bulup `TELEGRAM_IZINLI_KULLANICILAR`'a yaz →
`dubla-telegram`. Belirteç şifredir: sohbete, issue'ya, commit'e girmez; sızarsa `/revoke`. Ayrıntı:
`docs/tarifler/telegram_botu.md`.
