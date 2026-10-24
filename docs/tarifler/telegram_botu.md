# Recipe: setting up the Telegram bot

[Türkçe](#türkçe) · Goal: drive the dubbing pipeline from a phone with a bot of your own that only you can use.

Time ~10 min. All values below are sample formats; write your real value only into your own `.env` file and never
put it anywhere else (issue, screenshot, commit).

## 1. Create the bot (BotFather)
1. Open the official **@BotFather** account in Telegram (with the blue verification mark).
2. Type `/newbot`; give the bot a display name, then a unique username ending in `bot`.
3. BotFather gives a **token**; its format is like `1234567890:AAE...` (digits, a colon, a long key).
   This token is the bot's password: if it leaks, renew it in BotFather with `/revoke`.
4. Optional hardening: `/setjoingroups` → **Disable** (the bot cannot be added to groups).

## 2. Install
```
pip install .[telegram]
```
(If you installed with `scripts/kur.ps1`, run it in the same virtual environment.)

## 3. Write the token into `.env`
Copy `.env.example` in the repository root to `.env` and fill it in:
```
TELEGRAM_BOT_TOKEN=1234567890:ORNEK_BELIRTEC_BURAYA
TELEGRAM_IZINLI_KULLANICILAR=
```
`.env` is outside git (`.gitignore`).

## 4. Find your own user id and restrict the bot to yourself
The bot answers only the numeric ids in the `TELEGRAM_IZINLI_KULLANICILAR` list; if the list is empty it does not
start at all. Find your id with the official Bot API (no third-party bot needed):
1. Send any message to your new bot in Telegram (e.g. `merhaba`).
2. Open this address in a browser (with your token inserted; do not share the address with anyone):
   `https://api.telegram.org/bot<BELIRTEC>/getUpdates`
3. The number in `"from":{"id": 123456789, ...}` in the response is your id.
4. `.env`: `TELEGRAM_IZINLI_KULLANICILAR=123456789` (several people: comma-separated `111,222`).

## 5. Start
```
dubla-telegram
```
It opens no window; stop it with Ctrl+C. Only one instance runs at a time. Send `/start` to your bot.

## 6. Usage
- Send a video (at most 20 MB, Bot API limit) or write an `https://` link (a link needs the extras `youtube` or
  `galeri`) → the job starts and its progress is updated in the same message.
- `/ayarlar`: voice, translation, subtitle and other choices (this session only, in memory); `Varsayılana dön`
  (Back to defaults) resets them.
- `/isler`, `/durum [no]`, `/iptal [no]`, `/kontrol` (which engines are installed).
- When finished, a video under 50 MB comes to the chat; if larger, the output folder is reported.

## 7. Job management: failed jobs, resume, re-run
The bot uses **the same job store** as the command line (`dubla isler/sorunlu/devam`), the desktop and the web
interface: a job started from the phone also appears in the **İşler** (Jobs) tab of the desktop, and a job
interrupted on the computer can be continued from the phone. Details: `docs/tarifler/devam_ve_sorunlu_isler.md`.

| Command | What it does |
|---|---|
| `/sorunlu` | the last 10 failed or interrupted jobs (newest on top) |
| `/biten` | the last 15 finished jobs |
| `/isler` | recent jobs (all) |

Tap a job in the list; depending on its state the details show these buttons:
1. **Kaldığı yerden devam et** (Resume from where it stopped; failed / cancelled job): same job, same folder;
   finished stages do not run again.
2. **/ayarlar seçimlerimle devam (yeni iş)** (Resume with my /ayarlar choices, new job): first make the choices to
   change with `/ayarlar` (e.g. subtitle mode, voice). The old job stays as it is; the new job re-runs only the
   stages from the one affected by the changed choice.
3. **Aşama seçip yeniden çalıştır** (Pick a stage and re-run): again from the listed stage (e.g. "Çeviri
   aşamasından", from the translation stage), copied into a new job; the `+ seçimlerim` (+ my choices) buttons do the
   same with your `/ayarlar` choices.
4. **İptal et** (Cancel): a queued job or the job this bot is running stops; its checkpoint remains and it can be
   resumed later.
5. **Sil (kaydı arşivle)** (Delete, archive the record): asks for confirmation; only hides the record from the list,
   the video and the job folder are not deleted.

The progress of a new or resumed job is updated in a separate message. If the GPU is busy with another job (desktop,
web, command line) the job waits for its turn (machine-wide resource lock). On first start the bot moves jobs left
"running" because of a shutdown to failed. Neither the Telegram id nor chat information is written to the job store.

## Troubleshooting
| Symptom | Cause / fix |
|---|---|
| `TELEGRAM_BOT_TOKEN biçimi geçersiz` | the token was copied incompletely; get it again from BotFather |
| `TELEGRAM_IZINLI_KULLANICILAR boş` | step 4 |
| The bot does not answer | your id is not in the list or the bot is not running; check the console log |
| `bot zaten çalışıyor` | it is open in another window/process; close that one |
| `Conflict: terminated by other getUpdates` | the same token is running on another machine as well; close one of them |

Privacy: the bot writes neither your id nor message text to disk or log; the video is processed only on your own
computer (except the cloud translation/STT back end you choose, PRIVACY.md).

---

## Türkçe

Amaç: dublaj hattını telefondan, yalnız sizin kullanabildiğiniz kendi botunuzla sürmek. Süre ~10 dk.
Aşağıdaki bütün değerler örnek biçimdir; gerçek değerinizi yalnız kendi `.env` dosyanıza yazın, hiçbir yere
(issue, ekran görüntüsü, commit) koymayın.

### 1. Botu oluşturun (BotFather)
1. Telegram'da resmî **@BotFather** hesabını açın (mavi onay işaretli).
2. `/newbot` yazın; bota bir görünen ad, sonra `bot` ile biten benzersiz bir kullanıcı adı verin.
3. BotFather bir **belirteç** (token) verir; biçimi `1234567890:AAE...` gibidir (sayı, iki nokta, uzun anahtar).
   Bu belirteç botun şifresidir: sızarsa BotFather'da `/revoke` ile yenileyin.
4. İsteğe bağlı güvenlik: `/setjoingroups` → **Disable** (bot gruplara eklenemesin).

### 2. Kurulum
```
pip install .[telegram]
```
(`scripts/kur.ps1` ile kurduysanız aynı sanal ortamda çalıştırın.)

### 3. Belirteci `.env` dosyasına yazın
Repo kökündeki `.env.example` dosyasını `.env` olarak kopyalayın ve doldurun:
```
TELEGRAM_BOT_TOKEN=1234567890:ORNEK_BELIRTEC_BURAYA
TELEGRAM_IZINLI_KULLANICILAR=
```
`.env` git dışıdır (`.gitignore`).

### 4. Kendi kullanıcı kimliğinizi bulun ve botu kendinize kısıtlayın
Bot yalnız `TELEGRAM_IZINLI_KULLANICILAR` listesindeki sayısal kimliklere cevap verir; liste boşsa hiç başlamaz.
Kimliğinizi resmî Bot API ile bulun (üçüncü taraf bot gerekmez):
1. Telegram'da yeni botunuza herhangi bir mesaj yazın (ör. `merhaba`).
2. Tarayıcıda şu adresi açın (belirtecinizi yerleştirerek; adresi kimseyle paylaşmayın):
   `https://api.telegram.org/bot<BELIRTEC>/getUpdates`
3. Cevaptaki `"from":{"id": 123456789, ...}` sayısı sizin kimliğinizdir.
4. `.env`: `TELEGRAM_IZINLI_KULLANICILAR=123456789` (birden çok kişi: virgülle `111,222`).

### 5. Başlatın
```
dubla-telegram
```
Pencere açmaz; durdurmak için Ctrl+C. Aynı anda tek örnek çalışır. Botunuza `/start` yazın.

### 6. Kullanım
- Video gönderin (en çok 20 MB, Bot API sınırı) ya da `https://` bağlantısı yazın (bağlantı için extras `youtube`
  ya da `galeri` gerekir) → iş başlar, ilerleme aynı mesajda güncellenir.
- `/ayarlar`: ses, çeviri, altyazı vb. seçimler (yalnız bu oturum, bellekte); `Varsayılana dön` ile sıfırlanır.
- `/isler`, `/durum [no]`, `/iptal [no]`, `/kontrol` (hangi motorlar kurulu).
- Bitince 50 MB altındaki video sohbete gelir; büyükse çıktı klasörü bildirilir.

### 7. İş yönetimi: sorunlu işler, kaldığı yerden devam, yeniden çalıştırma
Bot, komut satırı (`dubla isler/sorunlu/devam`), masaüstü ve web arayüzüyle **aynı iş deposunu** kullanır:
telefondan başlattığınız iş masaüstünün **İşler** sekmesinde de görünür, bilgisayarda kesilen işi telefondan
sürdürebilirsiniz. Ayrıntı: `docs/tarifler/devam_ve_sorunlu_isler.md`.

| Komut | Ne yapar |
|---|---|
| `/sorunlu` | hata alan ya da kesilen son 10 iş (en yeni üstte) |
| `/biten` | biten son 15 iş |
| `/isler` | son işler (hepsi) |

Listeden bir işe dokunun; ayrıntıda duruma göre şu düğmeler çıkar:
1. **Kaldığı yerden devam et** (hata alan / iptal edilen iş): aynı iş, aynı klasör; biten aşamalar yeniden çalışmaz.
2. **/ayarlar seçimlerimle devam (yeni iş)**: önce `/ayarlar` ile değiştirmek istediğiniz seçimleri yapın (ör. altyazı
   kipi, ses). Eski iş olduğu gibi kalır; yeni iş yalnız değişen seçimin etkilediği aşamadan sonrasını yeniden çalıştırır.
3. **Aşama seçip yeniden çalıştır**: listedeki aşamadan (ör. "Çeviri aşamasından") yeni işe kopyalayarak yeniden;
   `+ seçimlerim` düğmeleri aynı şeyi `/ayarlar` seçimlerinizle yapar.
4. **İptal et**: sıradaki ya da bu botun çalıştırdığı iş durur; checkpoint'i kalır, sonra devam ettirilebilir.
5. **Sil (kaydı arşivle)**: onay sorar; yalnız kaydı listeden gizler, video ve iş klasörü silinmez.

Yeni ya da devam ettirilen işin ilerlemesi ayrı bir mesajda güncellenir. GPU başka bir işteyse (masaüstü, web,
komut satırı) iş sırasını bekler (makine geneli kaynak kilidi). Bot ilk açılışta, kapanan bilgisayar yüzünden
"çalışıyor" kalmış işleri sorunluya alır. İş deposuna Telegram kimliğiniz ya da sohbet bilgisi yazılmaz.

### Sorun giderme
| Belirti | Neden / çözüm |
|---|---|
| `TELEGRAM_BOT_TOKEN biçimi geçersiz` | belirteci eksik kopyaladınız; BotFather'dan yeniden alın |
| `TELEGRAM_IZINLI_KULLANICILAR boş` | 4. adım |
| Bot cevap vermiyor | kimliğiniz listede değil ya da bot kapalı; konsol günlüğüne bakın |
| `bot zaten çalışıyor` | başka bir pencerede/süreçte açık; onu kapatın |
| `Conflict: terminated by other getUpdates` | aynı belirteç başka bir makinede de çalışıyor; birini kapatın |

Gizlilik: bot kimliğinizi ya da mesaj metnini diske/günlüğe yazmaz; video yalnız sizin bilgisayarınızda işlenir
(seçtiğiniz bulut çeviri/STT arka ucu hariç, PRIVACY.md).
