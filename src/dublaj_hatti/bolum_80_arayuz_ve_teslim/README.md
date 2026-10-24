# Bolum 80: Arayuz ve Teslim

Bu bolum, hatti uzaktan suren isteğe bagli arayuzleri tasir. Ana arayuzler paket kokundedir:
`dublaj_hatti/cli.py` (`dubla`), `gui.py` (`dubla-gui`, tkinter), `web.py` (`dubla-web`, yalniz 127.0.0.1);
ucu de ayni is yurutucuyu (`is_yurutucu.py`) ve ayar katmanini (`yapilandirma.py`) kullanir.

```text
bolum_80_arayuz_ve_teslim/
  telegram_botu/          isteğe bagli Telegram botu (extras `telegram`, varsayilan kapali)
    bot.py                komutlar ve giris noktasi (`dubla-telegram`)
    arka_uc.py            ince is arka ucu: is yonetimi cekirdegi varsa onu, yoksa is_yurutucu'yu kullanir
    menuler.py            ayar menusu (secenekler ayar semasindan gelir; ayri liste tutulmaz)
    guvenlik.py           erisim kurallari: belirtec yalniz ortam degiskeninde, izinli kimlik listesi bossa bot baslamaz
    __main__.py           `python -m dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu`
```

Kural: CLI, GUI, web ve Telegram ayni yetenek ve is sozlesmesini paylasir; arayuz farki
backend davranisini sessizce degistirmez. Telegram kurulumu: `docs/tarifler/telegram_botu.md` (motor notu: `docs/motorlar/telegram_botu.md`).
Belirtec (`TELEGRAM_BOT_TOKEN`) ve izinli kimlikler (`TELEGRAM_IZINLI_KULLANICILAR`) yalniz `.env`'de durur.
