# Recipe: large files over Telegram (up to 2000 MB, local Bot API server)

[Türkçe](#türkçe) · Goal: the Telegram bot and `dubla-telegram gonder` deliver finished videos up to 2000 MB instead
of 50 MB. Decision record: [ADR 0018](../adr/0018-local-bot-api-server-for-large-files.md).

Time: about 10 minutes of your own work (two values from a Telegram web page) plus an automatic install (a few
minutes with Docker, 10-30 minutes without Docker). You never need to know what Docker or a server is: one command
does everything and `dubla kontrol` tells you whether it works.

## 1. Why a local server

| | Cloud Bot API (`api.telegram.org`) | Local Bot API server |
|---|---|---|
| Send a file (bot → you) | at most 50 MB | at most 2000 MB |
| Download a file (you → bot) | at most 20 MB | at most 2000 MB |
| Where it runs | Telegram | your computer, port only on `127.0.0.1` |
| What you need | bot token | bot token + `api_id` + `api_hash` |

A dubbed 10-minute video is easily 100-300 MB, so the cloud limit stops delivery. Raising timeouts or retrying does
not help: the cloud endpoint rejects the file, often as a plain connection error. The local server is Telegram's
own open-source Bot API server (`tdlib/telegram-bot-api`); it talks to Telegram's data centres itself and lifts the
limit to 2000 MB. Files above 2000 MB are not accepted by Telegram at all.

## 2. Get `api_id` and `api_hash` (screen by screen)

These two values identify an "application" on your Telegram account. They are free and take a few minutes.
1. On a computer, open **https://my.telegram.org** in a browser.
2. Type your phone number **with the country code** (for example `+44...`) and press **Next**.
3. Telegram sends a **code inside the Telegram app** (not an SMS). Open Telegram on your phone, copy the code, type it
   on the web page and press **Sign In**.
4. Click **API development tools**.
5. A form called "Create new application" opens. Fill only these:
   - **App title:** any name, for example `My dubbing bot`
   - **Short name:** 5-32 letters or digits, no spaces, for example `mydubbing`
   - **Platform:** `Desktop`
   - Leave URL and Description empty.
6. Press **Create application**. (If it says "ERROR", wait a minute, change the short name and try again.)
7. The page now shows **App api_id** (a number) and **App api_hash** (32 letters and digits).
8. Open the `.env` file in the repository folder (copy `.env.example` to `.env` if it does not exist) and fill in:
   ```
   TELEGRAM_API_ID=1234567
   TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef
   ```
   These are sample formats. Your real values go **only into your own `.env`**: never into a chat, an issue, a
   screenshot or a commit. If they leak, delete the application on the same page and create a new one.

The bot token (`TELEGRAM_BOT_TOKEN`) and your user id come from the bot recipe: [telegram_botu.md](telegram_botu.md).

## 3. Install with one command

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim telegram-sunucu
```

On Linux/macOS, or inside an existing environment: `dubla-telegram sunucu kur`. The command:
1. checks `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` in `.env`;
2. checks port 8081: if a Bot API server already answers there, it is reused; if another program uses the port, the
   next free port (8082-8090) is taken;
3. chooses the path (section 4), starts the server hidden (no window) and waits up to 60 s for a **real** `getMe`
   answer through it;
4. writes `TELEGRAM_YEREL_SUNUCU=http://127.0.0.1:<port>` into `.env`.

Running it again is safe. Check: `dubla kontrol` prints `telegram yerel sunucu: HAZIR ... (en çok 2000 MB)`.

## 4. Docker path and no-Docker path

| Path | When | What happens | Time |
|---|---|---|---|
| `docker` | Docker is installed | Docker Desktop is started hidden if needed; one container `dubworld-telegram-bot-api` on its own IPv4+IPv6 bridge network, port only on `127.0.0.1`, restart policy `unless-stopped` | 1-3 min |
| `docker --kaynaktan` | you want the image built from the official source | `scripts/telegram_bot_api.Dockerfile` builds the pinned commit | 10-30 min |
| `derleme` | no Docker | `scripts/telegram_bot_api_derle.sh` builds the pinned commit: directly on Linux/macOS, inside WSL on Windows (as root, no password prompt); the server runs hidden | 10-30 min |

Force a path: `dubla-telegram sunucu kur --kip docker|derleme [--kaynaktan]`. Preview without changing anything:
`dubla-telegram sunucu kur --kuru`. With neither Docker nor WSL the command stops and names the two install
commands (`winget install -e --id Docker.DockerDesktop` or `wsl --install -d Ubuntu`); both may need a restart.

The ready-made image is a community build of the official source, pulled by a fixed digest (not a moving tag); the
source build uses the official repository at a fixed commit. Both run the same server with `--local`.
Supply-chain note: the community image is built by a third party and is not verified against the source; the digest
only guarantees identical bytes on every pull. If that matters for you, install with
`dubla-telegram sunucu kur --kaynaktan` (official source, pinned commit, 10-30 min build).

## 5. Use

```
dubla-telegram gonder cikti\<job>\video.mp4 --metin "Dubbed video"
dubla-telegram
```

The first line sends one file to the first id in `TELEGRAM_IZINLI_KULLANICILAR` (exit 0 = Telegram confirmed it);
the second starts the bot, which now sends results up to 2000 MB and accepts incoming videos up to 2000 MB.
Videos of every size up to the limit go as a **playable video with preview** (`sendVideo`). To send a video as a
plain file instead, add `--belge` (or set `TELEGRAM_TESLIM_BICIMI=belge` in `.env` for the bot); files that are not
videos always go as a document.

## 6. Situations that are handled

| Situation | Behaviour |
|---|---|
| No local server and file over 50 MB | not attempted; clear message with the install command (`needs_local_server`) |
| File over 2000 MB | not attempted on any path (`too_large`); encode smaller or split |
| Server configured but not running | `dubla kontrol`: "AYARLI AMA ÇALIŞMIYOR"; `gonder` and the bot stop before uploading (real `getMe` first); start: `dubla-telegram sunucu baslat` |
| Port open but Telegram unreachable | readiness is a real `getMe`, never an open port; message points to `dubla-telegram sunucu durum` |
| Port 8081 used by another program | next free port 8082-8090; an existing Bot API server on the port is reused |
| Network drop before the whole file was read | retried after 15, 30, 60 s (at most 3 attempts), with longer timeouts each time |
| Timeout or drop after the whole file was sent | not re-uploaded (Telegram may have received it; a retry could deliver twice); status `unknown` / `manual_review`, check the chat |
| Local server disk too small for the upload copy | checked before upload (Docker path); message names `dubla-telegram sunucu temizle` |
| Server keeps downloaded files | incoming videos are copied out of the container and the server copy is deleted at once; `temizle` removes leftovers older than 24 h |
| Docker Desktop not running | started hidden, up to 90 s wait; otherwise the no-Docker path is suggested |
| Host reaches Telegram only over IPv6 | the container network has IPv6 enabled; the default Docker bridge has no IPv6 route |
| Video should arrive with a preview | sent with `sendVideo`, not as a document: a document shows only a file icon and must be downloaded before it plays. Preview conditions are met before upload: `supports_streaming`, width / height / duration from ffprobe, a thumbnail made with ffmpeg (JPEG, at most 320 px, under 200 KB), MP4 container with the `moov` atom at the start (faststart). A file without faststart is copied once with `-c copy -movflags +faststart` (no re-encoding, same quality) next to the original and deleted after sending |
| Video was sent but arrived as a file | the Telegram answer is checked: the result records `telegram_turu` = `video` or `document` |

Every attempt is written to `telegram_teslim_raporu.json` next to the file (size, attempts, result, Telegram message
number; no chat or user id).

## 7. Disk and cleanup

The server writes each upload to its own temporary folder before passing it to Telegram, so it needs free space of
about the file size (+10 %) while sending; uploads leave nothing behind. Downloads (`getFile` in local mode) are kept
by the server until deleted. The bot removes its own downloads right after copying them; other leftovers:

```
dubla-telegram sunucu temizle --kuru
dubla-telegram sunucu temizle --saat 24
```

Only download sub-folders are cleaned; the server's bot database is never touched.

## 8. Stop, remove, go back to the cloud

`dubla-telegram sunucu durdur` stops it; `baslat` starts it again; `kaldir` removes the container and the network
and empties `TELEGRAM_YEREL_SUNUCU` (the bot is back on the 50 MB cloud endpoint; the image stays for a fast
reinstall). Optional: `dubla-telegram sunucu bulut-cikis` logs the bot out of the cloud server (`logOut`), which the
official documentation recommends so that every incoming update reaches the local server; sending files does not
need it, and the bot cannot return to the cloud endpoint for 10 minutes afterwards.

## 9. Security

- `api_id`, `api_hash` and the token live only in `.env`. They are passed to the container by variable name and to
  WSL through `WSLENV`, never on a command line, and are never printed.
- The port is published only on `127.0.0.1`; plain `http` to any other host is refused (the token travels in the
  request path).
- The server's data folder contains a sub-folder named after the bot token: treat the container and its folders as
  secret; do not copy them into issues or screenshots.

## Türkçe

**Tarif: Telegram'dan büyük dosya (2000 MB'a kadar, yerel Bot API sunucusu)**

Amaç: Telegram botu ve `dubla-telegram gonder` biten videoyu 50 MB yerine 2000 MB'a kadar teslim eder. Karar kaydı:
[ADR 0018](../muhendislik/kararlar.md#0018).

Süre: sizin işiniz yaklaşık 10 dakika (Telegram'ın bir web sayfasından iki değer) + kendiliğinden kurulum (Docker
ile birkaç dakika, Docker'sız 10-30 dakika). Docker'ın ya da sunucunun ne olduğunu bilmeniz gerekmez: tek komut her
şeyi yapar, çalışıp çalışmadığını `dubla kontrol` söyler.

## 1. Neden yerel sunucu

| | Bulut Bot API (`api.telegram.org`) | Yerel Bot API sunucusu |
|---|---|---|
| Dosya gönderme (bot → siz) | en çok 50 MB | en çok 2000 MB |
| Dosya indirme (siz → bot) | en çok 20 MB | en çok 2000 MB |
| Nerede çalışır | Telegram'da | bilgisayarınızda, port yalnız `127.0.0.1` |
| Ne gerekir | bot belirteci | bot belirteci + `api_id` + `api_hash` |

Dublajlı 10 dakikalık bir video kolayca 100-300 MB olur; bulut sınırı teslimi durdurur. Zaman aşımını büyütmek ya da
yeniden denemek işe yaramaz: bulut uç noktası dosyayı reddeder, çoğu zaman yalnız bir bağlantı hatası olarak görünür.
Yerel sunucu Telegram'ın kendi açık kaynak Bot API sunucusudur (`tdlib/telegram-bot-api`); Telegram veri merkezleriyle
kendisi konuşur ve sınırı 2000 MB'a çıkarır. 2000 MB üstünü Telegram hiçbir yolla kabul etmez.

## 2. `api_id` ve `api_hash` alma (ekran ekran)

Bu iki değer Telegram hesabınızdaki bir "uygulamayı" tanıtır. Ücretsizdir, birkaç dakika sürer.
1. Bilgisayarda tarayıcıyla **https://my.telegram.org** adresini açın.
2. Telefon numaranızı **ülke koduyla** yazın (örneğin `+90...`) ve **Next**'e basın.
3. Telegram, **Telegram uygulamasının içine bir kod** gönderir (SMS değil). Telefonda Telegram'ı açın, kodu web
   sayfasına yazın ve **Sign In**'e basın.
4. **API development tools** bağlantısına tıklayın.
5. "Create new application" adlı bir form açılır. Yalnız şunları doldurun:
   - **App title:** herhangi bir ad, örneğin `Dublaj botum`
   - **Short name:** 5-32 harf ya da rakam, boşluksuz, örneğin `dublajbotum`
   - **Platform:** `Desktop`
   - URL ve Description boş kalsın.
6. **Create application**'a basın. ("ERROR" yazarsa bir dakika bekleyin, kısa adı değiştirip yeniden deneyin.)
7. Sayfada artık **App api_id** (bir sayı) ve **App api_hash** (32 harf ve rakam) görünür.
8. Repo klasöründeki `.env` dosyasını açın (yoksa `.env.example`'ı `.env` adıyla kopyalayın) ve doldurun:
   ```
   TELEGRAM_API_ID=1234567
   TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef
   ```
   Bunlar örnek biçimdir. Gerçek değerleriniz **yalnız kendi `.env` dosyanıza** girer: sohbete, issue'ya, ekran
   görüntüsüne ya da commit'e asla. Sızarsa aynı sayfada uygulamayı silip yenisini oluşturun.

Bot belirteci (`TELEGRAM_BOT_TOKEN`) ve kullanıcı kimliğiniz bot tarifinden gelir: [telegram_botu.md](telegram_botu.md).

## 3. Tek komutla kurulum

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Adim telegram-sunucu
```

Linux/macOS'ta ya da kurulu bir ortamda: `dubla-telegram sunucu kur`. Komut:
1. `.env`'de `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` değerlerine bakar;
2. 8081 portuna bakar: orada zaten bir Bot API sunucusu cevap veriyorsa onu kullanır; port başka programdaysa sıradaki
   boş portu (8082-8090) alır;
3. yolu seçer (bölüm 4), sunucuyu gizli (pencere açmadan) başlatır ve onun üzerinden **gerçek** bir `getMe` cevabını
   en çok 60 sn bekler;
4. `.env`'ye `TELEGRAM_YEREL_SUNUCU=http://127.0.0.1:<port>` yazar.

Yeniden çalıştırmak güvenlidir. Denetim: `dubla kontrol` → `telegram yerel sunucu: HAZIR ... (en çok 2000 MB)`.

## 4. Docker yolu ve Docker'sız yol

| Yol | Ne zaman | Ne olur | Süre |
|---|---|---|---|
| `docker` | Docker kuruluysa | Docker Desktop gerekirse gizli başlar; kendi IPv4+IPv6 köprü ağında tek kapsayıcı `dubworld-telegram-bot-api`, port yalnız `127.0.0.1`, yeniden başlama kuralı `unless-stopped` | 1-3 dk |
| `docker --kaynaktan` | imajın resmî kaynaktan derlenmesi istenirse | `scripts/telegram_bot_api.Dockerfile` sabit commit'i derler | 10-30 dk |
| `derleme` | Docker yoksa | `scripts/telegram_bot_api_derle.sh` sabit commit'i derler: Linux/macOS'ta doğrudan, Windows'ta WSL içinde (root, parola sorulmaz); sunucu gizli çalışır | 10-30 dk |

Yolu zorlamak: `dubla-telegram sunucu kur --kip docker|derleme [--kaynaktan]`. Hiçbir şeyi değiştirmeden plan:
`dubla-telegram sunucu kur --kuru`. Ne Docker ne WSL varsa komut durur ve iki kurulum komutunu söyler
(`winget install -e --id Docker.DockerDesktop` ya da `wsl --install -d Ubuntu`); ikisi de yeniden başlatma isteyebilir.

Hazır imaj, resmî kaynağın topluluk derlemesidir ve sabit özetle (digest; kayan etiket değil) çekilir; kaynaktan
derleme resmî depoyu sabit commit'te kullanır. İkisi de aynı sunucuyu `--local` ile çalıştırır.
Tedarik zinciri notu: topluluk imajını üçüncü taraf derler ve kaynağa karşı doğrulanmaz; özet yalnız her çekişte aynı
baytları garanti eder. Bu sizin için önemliyse `dubla-telegram sunucu kur --kaynaktan` ile kurun (resmî kaynak, sabit
commit, 10-30 dk derleme).

## 5. Kullanım

```
dubla-telegram gonder cikti\<iş>\video.mp4 --metin "Dublajlı video"
dubla-telegram
```

İlk satır tek dosyayı `TELEGRAM_IZINLI_KULLANICILAR`'daki ilk kimliğe gönderir (çıkış 0 = Telegram onayladı); ikinci
satır botu başlatır; bot artık 2000 MB'a kadar sonuç gönderir ve 2000 MB'a kadar gelen videoyu alır. Sınıra kadar
her boyuttaki video **önizlemeli, oynatılabilir video** (`sendVideo`) olarak gider. Videoyu düz dosya olarak göndermek
için `--belge` ekleyin (bot için `.env`'de `TELEGRAM_TESLIM_BICIMI=belge`); video olmayan dosyalar her zaman belge
olarak gider.

## 6. Ele alınan durumlar

| Durum | Davranış |
|---|---|
| Yerel sunucu yok ve dosya 50 MB üstü | denenmez; kurulum komutunu söyleyen açık mesaj (`needs_local_server`) |
| Dosya 2000 MB üstü | hiçbir yolda denenmez (`too_large`); daha küçük kodlayın ya da bölün |
| Sunucu ayarlı ama çalışmıyor | `dubla kontrol`: "AYARLI AMA ÇALIŞMIYOR"; `gonder` ve bot yüklemeden önce durur (önce gerçek `getMe`); başlatma: `dubla-telegram sunucu baslat` |
| Port açık ama Telegram'a ulaşılamıyor | hazırlık gerçek `getMe`'dir, açık port asla değil; mesaj `dubla-telegram sunucu durum`'u gösterir |
| 8081 başka programda | sıradaki boş port 8082-8090; portta çalışan bir Bot API sunucusu varsa o kullanılır |
| Dosyanın tamamı okunmadan ağ koptu | 15, 30, 60 sn sonra yeniden denenir (en çok 3 deneme), her seferinde süreler uzar |
| Dosyanın tamamı gittikten sonra zaman aşımı ya da kopma | yeniden yüklenmez (Telegram almış olabilir; yeniden deneme iki kez teslim edebilir); durum `unknown` / `manual_review`, sohbete bakın |
| Yerel sunucunun diski yükleme kopyasına yetmiyor | yüklemeden önce denetlenir (Docker yolu); mesaj `dubla-telegram sunucu temizle`'yi söyler |
| Sunucu indirdiği dosyaları saklıyor | gelen video kapsayıcıdan kopyalanır, sunucudaki kopya hemen silinir; `temizle` 24 saatten eski artıkları siler |
| Docker Desktop çalışmıyor | gizli başlatılır, en çok 90 sn beklenir; olmazsa Docker'sız yol önerilir |
| Bilgisayar Telegram'a yalnız IPv6 ile çıkıyor | kapsayıcı ağında IPv6 açıktır; varsayılan Docker köprüsünde IPv6 rotası yoktur |
| Video önizlemeli gelmeli | belge değil `sendVideo` ile gider: belge yalnız dosya simgesi gösterir, oynatmak için önce indirilmesi gerekir. Önizleme koşulları yüklemeden önce sağlanır: `supports_streaming`, ffprobe'dan genişlik / yükseklik / süre, ffmpeg ile küçük resim (JPEG, en çok 320 px, 200 KB altı), `moov` atomu başta olan MP4 (faststart). Faststart'sız dosya bir kez `-c copy -movflags +faststart` ile (yeniden kodlama yok, kalite aynı) özgün dosyanın yanına kopyalanır, gönderimden sonra silinir |
| Video gönderildi ama dosya olarak geldi | Telegram cevabına bakılır: sonuç `telegram_turu` = `video` ya da `document` olarak kaydedilir |

Her deneme dosyanın yanındaki `telegram_teslim_raporu.json`'a yazılır (boyut, denemeler, sonuç, Telegram mesaj
numarası; sohbet ya da kullanıcı kimliği yazılmaz).

## 7. Disk ve temizlik

Sunucu her yüklemeyi Telegram'a geçirmeden önce kendi geçici klasörüne yazar; gönderim sırasında dosya boyu kadar
(+%10) boş yer gerekir, yükleme iz bırakmaz. İndirmeleri (yerel kipte `getFile`) sunucu silinene kadar saklar. Bot
kendi indirdiğini kopyaladıktan hemen sonra siler; kalan artıklar için:

```
dubla-telegram sunucu temizle --kuru
dubla-telegram sunucu temizle --saat 24
```

Yalnız indirme alt klasörleri temizlenir; sunucunun bot veritabanına dokunulmaz.

## 8. Durdurma, kaldırma, buluta dönüş

`dubla-telegram sunucu durdur` durdurur; `baslat` yeniden başlatır; `kaldir` kapsayıcıyı ve ağı siler,
`TELEGRAM_YEREL_SUNUCU`'yu boşaltır (bot 50 MB'lık bulut uç noktasına döner; imaj hızlı yeniden kurulum için kalır).
İsteğe bağlı: `dubla-telegram sunucu bulut-cikis` botu bulut sunucusundan çıkarır (`logOut`); resmî belge, gelen her
güncellemenin yerel sunucuya ulaşması için bunu önerir; dosya göndermek için gerekmez ve bot sonraki 10 dakika bulut
uç noktasına dönemez.

## 9. Güvenlik

- `api_id`, `api_hash` ve belirteç yalnız `.env`'de durur. Kapsayıcıya değişken adıyla, WSL'ye `WSLENV` ile geçer;
  komut satırına asla yazılmaz ve hiçbir yerde basılmaz.
- Port yalnız `127.0.0.1`'de yayımlanır; başka bir adrese düz `http` reddedilir (belirteç istek yolunda taşınır).
- Sunucunun veri klasöründe bot belirteci adlı bir alt klasör vardır: kapsayıcıyı ve klasörlerini gizli sayın;
  issue'ya ya da ekran görüntüsüne koymayın.
