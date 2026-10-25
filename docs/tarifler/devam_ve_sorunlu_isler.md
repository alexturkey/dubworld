# Jobs: resume, failed jobs, re-running

[Türkçe](#türkçe) · Every dubbing and transcript job is stored as a **job record**.

No job that is interrupted, fails or finishes is ever lost; the same job can be managed from the command line, the
interface (`dubla-gui` in its own window, `dubla-web` in the browser) or the Telegram bot (`dubla-telegram`). All
of them see the same records.

## Where it is stored

| What | Location |
|---|---|
| Job records (SQLite) | `<output root>/_is_deposu/isler.sqlite3`; for another location the environment variable `DUBLAJ_IS_DEPOSU=<file path>` |
| Stage records of each job (checkpoint) | `pipeline_state.json` and `checkpoints/` in the job folder |
| Report of settings changed on resume | `secim_denetimi.json` and `secim_denetimi.txt` in the job folder |

The output root is the `genel.cikti_klasoru` setting (`--cikti`, or `DUBLAJ_OUTPUT_DIR`). The record file is opened
in WAL mode; the command line, the desktop and the web interface can read and write it at the same time.

## Job states

| State | Meaning |
|---|---|
| `queued` | waiting in the queue |
| `deferred` | the resource (GPU) was busy; it will be retried shortly |
| `preparing` | the stages of the previous job are being copied for a resume |
| `processing` | running |
| `completed` | finished |
| `failed` | failed or was interrupted; can be resumed |
| `cancelled` | stopped by the user, or a stale job was cancelled; can be resumed |

**Archive** is a separate flag: an archived job is hidden from the list; its file and folder are not deleted and it
can be restored.

## Two ways to resume

1. **Resume in place:** same job, same folder. Finished stages do not run again; the job continues from the stage
   where it stopped. This is what happens with `dubla devam <job>` without changing any setting.
2. **Copy into a new job:** the results of the previous job up to the selected stage are copied into a new job
   folder, the old job stays as it is, and the new job is linked to the old one in the "lineage". This is what
   happens when a stage is selected, a setting is changed, `--yeni-is` is given or a finished job is re-run.

**Resume with changed settings:** the first stage each setting affects is known (e.g. `altyazi.mod` → subtitle
preparation, `genel.hedef_dil` → translation, `transkripsiyon.model` → transcription). Everything before the earliest
stage affected by the changed settings is kept; that stage and the following ones run again. Settings that do not
change the result (`genel.cihaz`, cache, log, TTS retries) roll back no stage. `genel.is_turu` cannot be
changed on resume (start a new job). The input of every stage is also recorded: a stage whose input changed runs
again, whatever the table says.

## Command line

```powershell
dubla video.mp4 --cikti D:\dublajlar            # new job; prints "İş #7" on screen
dubla isler                                      # recent jobs (archive excluded)
dubla isler --hepsi                              # archive included
dubla sorunlu                                    # failed / interrupted jobs and resume options
dubla devam 7                                    # from where it stopped, in the same folder
dubla devam 7 --asama ceviri                     # again from translation (copied into a new job)
dubla devam 7 --ayar altyazi.mod=word            # change a setting; again from the stage it affects
dubla devam 7 --yeni-is                          # continue with a copy, the old job untouched
dubla isler --soyagaci 9                         # which job job 9 was derived from
dubla isler --arsivle 7                          # hide from the list (does not delete)
dubla isler --arsivden-cikar 7
dubla isler --iptal 7                            # cancel a queued or stale job
dubla isler --kurtar                             # move jobs left "running" after a shutdown to failed
dubla isler --bayat-iptal 720                    # cancel jobs with no progress for 12 hours and a dead process
```

`--asama` takes the stage id (`ceviri`), its Turkish name or its sequence number; `dubla sorunlu` lists the valid
options. All of them give machine-readable output with `--json`. The old form `dubla video.mp4 --devam <job folder>`
also works: the job of the folder is found and resumed in place.

Exit codes: `0` finished, `1` error, `2` invalid usage, `75` resource busy (job deferred), `130` stopped by the user.

## Interface (`dubla-gui`, `dubla-web`)

There is one interface. `dubla-gui` (double-click `arayuz.cmd`) opens it in its own app window; `dubla-web`
(`web.cmd`) opens the same page in your browser. It listens only on `127.0.0.1` and is protected by a session token
(another computer or tab cannot access it).

1. Open the **Jobs** tab: jobs with problems on top, the history below; **Show archived too** adds the hidden ones.
2. For each job:
   - **Continue**: continues a failed or stopped job from where it stopped.
   - **From a stage…**: pick a stage and **Copy to a new job and run from this stage**. If **With what I changed in
     Settings** is checked, the changes in the Settings drawer are applied as well.
   - **Play video** (finished job): plays the result in the **Dub** tab, with Original / Dubbed and the subtitles.
   - **Open folder**, **Archive** (only hides the record from the list, no file is deleted), **Cancel**.
3. Progress is shown in the **Dub** tab; if the GPU is busy with another job it says so and starts when its turn
   comes.

Endpoints for calling from your own tool (the same session cookie and the `X-Dublaj-Belirtec` header are required):

| Endpoint | Purpose |
|---|---|
| `GET /api/isler` (`?hepsi=1`) | job list |
| `GET /api/sorunlu` | failed jobs and resume options |
| `GET /api/is?no=7` | one job, its resume and re-run options |
| `POST /api/devam` `{"is": 7, "asama": "ceviri", "yeni_is": true, "ayarlar": {"altyazi.mod": "word"}}` | resume / re-run |
| `POST /api/is_arsivle` `{"is": 7}` | archive |
| `POST /api/is_iptal` `{"is": 7}` | cancel |

An invalid setting returns `400`; a job that is not found or cannot be resumed returns `409`.

## Telegram bot (`dubla-telegram`)

`/sorunlu`, `/biten`, `/isler` → tap a job → **Kaldığı yerden devam et** (Resume from where it stopped), **Aşama
seçip yeniden çalıştır** (Pick a stage and re-run), **/ayarlar seçimlerimle devam** (Resume with my /ayarlar
choices), **İptal et** (Cancel), **Sil (kaydı arşivle)** (Delete, archive the record). Setup and details:
`docs/tarifler/telegram_botu.md` §7.

## GPU queue (resource lock)

So that several jobs on the same computer (command line, desktop, web, other programs) do not use the GPU at the same
time, there is a machine-wide lock: one job at a time on the GPU, two jobs on heavy CPU work. A job whose turn has not
come waits (at most `DUBLAJ_KILIT_BEKLEME_SN`, default 6 hours); when the time runs out it becomes `deferred` and is
retried automatically. Locks are bound to the process id: the lock of a crashed program is released automatically.

```powershell
python -m dublaj_hatti.bolum_00_omurga.runtime.kaynak_kilidi durum         # who is using it
python -m dublaj_hatti.bolum_00_omurga.runtime.kaynak_kilidi calistir --kaynak gpu --sahip kullanici:ad --amac deneme -- <komut>
```

The lock folder is in the temporary folder; for another location use `DUBLAJ_KILIT_KLASORU`.

## If the computer shuts down

When the program is opened again (desktop or web), jobs that look "running" but whose process no longer exists
automatically become `failed` and appear as failed in the **İşler** (Jobs) tab; **Devam et** (Resume) continues from
the stage where they stopped. The same on the command line: `dubla isler --kurtar`.

---

## Türkçe

Her dublaj ve transkript işi bir **iş kaydı** olarak saklanır. Kesilen, hata alan ya da biten hiçbir iş kaybolmaz;
aynı işi komut satırından, arayüzden (`dubla-gui` kendi penceresinde, `dubla-web` tarayıcıda) ya da Telegram
botundan (`dubla-telegram`) yönetirsiniz. Hepsi aynı kayıtları görür.

### Nerede saklanır

| Ne | Yer |
|---|---|
| İş kayıtları (SQLite) | `<çıktı kökü>/_is_deposu/isler.sqlite3`; başka yer için ortam değişkeni `DUBLAJ_IS_DEPOSU=<dosya yolu>` |
| Her işin aşama kayıtları (checkpoint) | işin klasöründe `pipeline_state.json` ve `checkpoints/` |
| Devamda değişen ayarların dökümü | işin klasöründe `secim_denetimi.json` ve `secim_denetimi.txt` |

Çıktı kökü `genel.cikti_klasoru` ayarıdır (`--cikti`, ya da `DUBLAJ_OUTPUT_DIR`). Kayıt dosyası WAL kipinde açılır;
komut satırı, masaüstü ve web aynı anda okuyup yazabilir.

### İş durumları

| Durum | Anlamı |
|---|---|
| `queued` | sırada bekliyor |
| `deferred` | kaynak (GPU) meşguldü; kısa süre sonra yeniden denenecek |
| `preparing` | devam için önceki işin aşamaları kopyalanıyor |
| `processing` | çalışıyor |
| `completed` | bitti |
| `failed` | hata aldı ya da yarıda kesildi; devam ettirilebilir |
| `cancelled` | kullanıcı durdurdu ya da bayat iş iptal edildi; devam ettirilebilir |

**Arşiv** ayrı bir işarettir: arşivlenen iş listeden gizlenir; dosyası ve klasörü silinmez, geri alınabilir.

### Devamın iki biçimi

1. **Yerinde devam:** aynı iş, aynı klasör. Biten aşamalar yeniden çalışmaz, kesildiği aşamadan sürer.
   Ayar değiştirmeden `dubla devam <iş>` dediğinizde olan budur.
2. **Yeni işe kopyalayarak:** önceki işin seçtiğiniz aşamaya kadarki sonuçları yeni bir iş klasörüne kopyalanır,
   eski iş olduğu gibi kalır, yeni iş "soyağacı"nda eskisine bağlanır. Aşama seçtiğinizde, ayar değiştirdiğinizde,
   `--yeni-is` verdiğinizde ya da biten bir işi yeniden çalıştırdığınızda olan budur.

**Ayar değiştirerek devam:** her ayarın ilk etkilediği aşama bilinir (ör. `altyazi.mod` → altyazı hazırlama,
`genel.hedef_dil` → çeviri, `transkripsiyon.model` → transkripsiyon). Değişen ayarların en erken etkilediği
aşamadan öncesi korunur, o aşama ve sonrası yeniden çalışır. Sonucu değiştirmeyen ayarlar (`genel.cihaz`,
önbellek, günlük, TTS yeniden denemeleri) hiçbir aşamayı geri almaz. `genel.is_turu` devamda değiştirilemez (yeni iş açın).
Ayrıca her aşamanın girdisi kaydedilmiştir: girdisi değişen aşama, tablo ne derse desin yeniden çalışır.

### Komut satırı

```powershell
dubla video.mp4 --cikti D:\dublajlar            # yeni iş; ekranda "İş #7" yazar
dubla isler                                      # son işler (arşiv hariç)
dubla isler --hepsi                              # arşiv dahil
dubla sorunlu                                    # hata alan / kesilen işler ve devam seçenekleri
dubla devam 7                                    # kaldığı yerden, aynı klasörde
dubla devam 7 --asama ceviri                     # çeviriden yeniden (yeni işe kopyalayarak)
dubla devam 7 --ayar altyazi.mod=word            # ayar değiştir; etkilediği aşamadan yeniden
dubla devam 7 --yeni-is                          # eski işe dokunmadan kopyasıyla sürdür
dubla isler --soyagaci 9                         # 9 numaralı iş hangi işten türedi
dubla isler --arsivle 7                          # listeden gizle (silmez)
dubla isler --arsivden-cikar 7
dubla isler --iptal 7                            # sıradaki ya da bayat işi iptal et
dubla isler --kurtar                             # bilgisayar kapanınca "çalışıyor" kalan işleri sorunluya al
dubla isler --bayat-iptal 720                    # 12 saattir ilerlemeyen ve süreci ölmüş işleri iptal et
```

`--asama` aşamanın kimliğini (`ceviri`), Türkçe adını ya da sıra numarasını alır; `dubla sorunlu` geçerli
seçenekleri listeler. Hepsi `--json` ile makine okunur çıktı verir. Eski biçim `dubla video.mp4 --devam <iş klasörü>`
de çalışır: klasörün işi bulunur ve yerinde devam edilir.

Çıkış kodları: `0` bitti, `1` hata, `2` geçersiz kullanım, `75` kaynak meşgul (iş ertelendi), `130` kullanıcı durdurdu.

### Arayüz (`dubla-gui`, `dubla-web`)

Tek arayüz vardır. `dubla-gui` (`arayuz.cmd`'ye çift tıklama) onu kendi uygulama penceresinde, `dubla-web`
(`web.cmd`) aynı sayfayı tarayıcıda açar. Yalnız `127.0.0.1`'de dinler ve oturum belirteciyle korunur (başka
bilgisayar ya da sekme erişemez).

1. **İşler** sekmesini açın: sorunlu işler üstte, geçmiş altta; **Arşivi de göster** gizlenenleri ekler.
2. Her işte:
   - **Devam et**: hata alan ya da kesilen işi kaldığı yerden sürdürür.
   - **Aşamadan…**: bir aşama seçip **Bu aşamadan yeni işe kopyalayarak çalıştır**. **Ayarlar'da
     değiştirdiklerimle** işaretliyse Ayarlar çekmecesindeki değişiklikler de uygulanır.
   - **Videoyu aç** (biten iş): sonucu **Dublaj** sekmesinde oynatır; Orijinal / Dublajlı ve altyazıyla.
   - **Klasörü aç**, **Arşivle** (yalnız kaydı listeden gizler, dosya silinmez), **İptal**.
3. İlerleme **Dublaj** sekmesinde görünür; GPU başka bir işteyse bunu yazar ve sırası gelince başlar.

Kendi aracınızdan çağırmak için uç noktalar (aynı oturum çerezi ve `X-Dublaj-Belirtec` başlığı gerekir):

| Uç nokta | İş |
|---|---|
| `GET /api/isler` (`?hepsi=1`) | iş listesi |
| `GET /api/sorunlu` | sorunlu işler ve devam seçenekleri |
| `GET /api/is?no=7` | tek iş, devam ve yeniden çalıştırma seçenekleri |
| `POST /api/devam` `{"is": 7, "asama": "ceviri", "yeni_is": true, "ayarlar": {"altyazi.mod": "word"}}` | devam / yeniden çalıştırma |
| `POST /api/is_arsivle` `{"is": 7}` | arşivle |
| `POST /api/is_iptal` `{"is": 7}` | iptal |

Geçersiz ayar `400`, bulunamayan ya da devam edilemeyen iş `409` döner.

### Telegram botu (`dubla-telegram`)

`/sorunlu`, `/biten`, `/isler` → işe dokunun → **Kaldığı yerden devam et**, **Aşama seçip yeniden çalıştır**,
**/ayarlar seçimlerimle devam**, **İptal et**, **Sil (kaydı arşivle)**. Kurulum ve ayrıntı: `docs/tarifler/telegram_botu.md` §7.

### GPU sırası (kaynak kilidi)

Aynı bilgisayarda birden çok iş (komut satırı, masaüstü, web, başka programlar) GPU'yu aynı anda kullanmasın diye
makine geneli bir kilit vardır: GPU'ya aynı anda tek iş, ağır CPU işine iki iş girer. Sırası gelmeyen iş bekler
(en çok `DUBLAJ_KILIT_BEKLEME_SN`, varsayılan 6 saat), süre dolarsa `deferred` olur ve kendiliğinden yeniden denenir.
Kilitler süreç numarasına bağlıdır: çöken programın kilidi kendiliğinden düşer.

```powershell
python -m dublaj_hatti.bolum_00_omurga.runtime.kaynak_kilidi durum         # kim kullanıyor
python -m dublaj_hatti.bolum_00_omurga.runtime.kaynak_kilidi calistir --kaynak gpu --sahip kullanici:ad --amac deneme -- <komut>
```

Kilit klasörü geçici klasördedir; başka yer için `DUBLAJ_KILIT_KLASORU`.

### Bilgisayar kapanırsa

Program yeniden açıldığında (masaüstü ya da web) "çalışıyor" görünüp süreci artık yaşamayan işler kendiliğinden
`failed` olur ve **İşler** sekmesinde sorunlu olarak görünür; **Devam et** ile kaldığı aşamadan sürer.
Komut satırında aynısı: `dubla isler --kurtar`.
