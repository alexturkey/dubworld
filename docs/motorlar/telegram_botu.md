# Telegram bot (remote control) (`telegram_botu`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** A thin interface for driving the dubbing pipeline on your own computer from your phone: send a video
or type a link and the job starts; progress is updated in a single message, and when it finishes the video (if under
50 MB) arrives. The `/ayarlar` menu is generated from the settings layer's schema (the same options and the same
validation as CLI/GUI/web).

| | |
|---|---|
| License | code: python-telegram-bot LGPL-3.0-only (used as a library) |
| Source | https://github.com/python-telegram-bot/python-telegram-bot |
| Install | `pip install .[telegram]` ; start: `dubla-telegram` |
| Hardware | CPU, ~100 MB RAM; no open port (long polling to the Bot API) |
| Default | off (runs only when you start it, single instance) |

Step-by-step setup: [docs/tarifler/telegram_botu.md](../tarifler/telegram_botu.md).

**Security and privacy:** The token and the allowed user ids live only in `.env`; if the allow list is empty the bot
does not start. Unauthorised people get no answer and their id is not written to the log. An incoming video is saved
under a random name (the original name is not written to disk); selections are kept only in memory. Bot API limits:
a bot cannot download files over 20 MB or send files over 50 MB.

**Job backend:** The bot uses the `IsArkaUcu` interface (start, status, list, cancel). If the job-management core
provides `dublaj_hatti.is_yonetimi.telegram_arka_ucu()`, that is used (queue, history, resume); otherwise the same
single-job runner as desktop/web.

**Common errors**
- `python-telegram-bot kurulu değil` → extras.
- `TELEGRAM_IZINLI_KULLANICILAR boş` → write your own id (recipe).
- `bot zaten çalışıyor` → the second instance was refused (two bots with the same token conflict on Telegram).

## How it works in this pipeline / Neden böyle

- **Principle:** a thin interface that does long polling to the Bot API; it needs no open port. The `/ayarlar` menu is
  generated from the settings layer's schema; jobs go to the same job backend as the desktop and web interfaces.
- **Why this choice:** it is the narrowest way to drive the pipeline remotely without opening a server. Because two
  bots with the same token conflict on Telegram, a single instance runs; if the allow list is empty the bot does not
  start.
- **How it fits:** CLI, GUI, web and bot use the same settings schema and validation; the bot only starts the job,
  shows progress and sends the result. Bot API limits (20 MB download, 50 MB send) determine the delivery size.
- Details: [docs/tarifler/telegram_botu.md](../tarifler/telegram_botu.md)

## Türkçe

**Telegram botu (`telegram_botu`)**

**Ne yapar:** Kendi bilgisayarınızdaki dublaj hattını telefondan sürmek için ince bir arayüz: video gönderin ya da
bağlantı yazın, iş başlar; ilerleme tek mesajda güncellenir, bitince video (50 MB altıysa) gelir. `/ayarlar`
menüsü ayar katmanının şemasından üretilir (CLI/GUI/web ile aynı seçenekler, aynı doğrulama).

| | |
|---|---|
| Lisans | kod: python-telegram-bot LGPL-3.0-only (kütüphane olarak kullanılır) |
| Kaynak | https://github.com/python-telegram-bot/python-telegram-bot |
| Kurulum | `pip install .[telegram]` ; başlat: `dubla-telegram` |
| Donanım | işlemci, ~100 MB RAM; açık port yok (Bot API'ye uzun yoklama) |
| Varsayılan | kapalı (yalnız siz başlatınca çalışır, tek örnek) |

Adım adım kurulum: [docs/tarifler/telegram_botu.md](../tarifler/telegram_botu.md).

**Güvenlik ve gizlilik:** Belirteç ve izinli kullanıcı kimlikleri yalnız `.env`'de; izinli liste boşsa bot
başlamaz. İzinsiz kişiye cevap verilmez, kimliği günlüğe yazılmaz. Gelen video rastgele adla kaydedilir (özgün ad
diske yazılmaz); seçimler yalnız bellekte. Bot API sınırları: bot 20 MB üstü dosya indiremez, 50 MB üstü
gönderemez.

**İş arka ucu:** Bot `IsArkaUcu` arayüzünü kullanır (başlat, durum, liste, iptal). İş yönetimi çekirdeği
`dublaj_hatti.is_yonetimi.telegram_arka_ucu()` verirse o (kuyruk, geçmiş, devam); yoksa masaüstü/web ile aynı
tek-iş yürütücüsü.

**Sık hata**
- `python-telegram-bot kurulu değil` → extras.
- `TELEGRAM_IZINLI_KULLANICILAR boş` → kendi kimliğinizi yazın (tarif).
- `bot zaten çalışıyor` → ikinci örnek reddedildi (aynı belirteçle iki bot Telegram'da çakışır).

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** Bot API'ye uzun yoklama (long polling) yapan ince bir arayüzdür; açık port gerektirmez. `/ayarlar` menüsü ayar
  katmanının şemasından üretilir; işler masaüstü ve web arayüzüyle aynı iş arka ucuna gider.
- **Neden böyle:** hattı uzaktan sürmenin sunucu açmadan en dar yoludur. Aynı belirteçle iki bot Telegram'da çakıştığı
  için tek örnek çalışır; izinli liste boşsa bot başlamaz.
- **Diğer parçalarla ahengi:** CLI, GUI, web ve bot aynı ayar şemasını ve doğrulamasını kullanır; bot yalnız işi başlatır,
  ilerlemeyi gösterir ve sonucu gönderir. Bot API sınırları (20 MB indirme, 50 MB gönderme) teslim boyutunu belirler.
- Ayrıntı: [docs/tarifler/telegram_botu.md](../tarifler/telegram_botu.md)
