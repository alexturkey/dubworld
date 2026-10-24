# gallery-dl (download from a gallery link) (`gallery_dl`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** When a gallery link (currently Instagram) is given as the source, downloads the video with
gallery-dl. YouTube/Vimeo/Dailymotion links stay with yt-dlp.

| | |
|---|---|
| License | **GPL-2.0-only**. This repository **never imports** it; it only runs the command-line tool in a separate process (independent program), and the repository stays Apache-2.0 |
| Source | https://github.com/mikf/gallery-dl |
| Install | `pip install .[galeri]` or put gallery-dl on PATH / `DUBLAJ_GALLERY_DL=<exe path>` |
| Hardware | CPU, <100 MB RAM |
| Default | off (runs only when a gallery link is given) |

**Login/cookies:** Cookies for content that needs a login are not kept in this repository. Prepare gallery-dl's own
configuration file on your own machine (gallery-dl documentation) and give its path in `.env` with
`DUBLAJ_GALLERY_DL_AYAR`.
Command: `gallery-dl --destination <iş>/galeri_indirme --filter "extension in (video uzantıları)" [--config] -- <url>`.

**Responsible use:** Only content you own or are permitted to use; the site's terms of use are your responsibility.

**Common errors**
- `gallery-dl kurulu değil` → extras or PATH.
- `video dosyası indirmedi` → the link has no video or needs a login (configuration file).

## How it works in this pipeline / Neden böyle

- **Principle:** when a gallery link is given, gallery-dl runs as a separate program; only video extensions are
  downloaded into the job folder, and the link is passed after the `--` separator.
- **Why this choice:** on gallery sites of this kind yt-dlp was detected as a bot and browser-cookie attempts failed;
  gallery-dl worked with its own session configuration file. Because it is GPL-2.0 it is not imported and runs in a
  separate process ([ADR 0017](../adr/0017-defaults-and-licence-gate.md)). Session data is not kept in the repository.
- **How it fits:** `kaynak_girdisi` decides the link type; the downloaded file enters the pipeline like a local file.
- Place in the end-to-end flow: [pipeline-flow.md, step 0 (entry)](../engineering/pipeline-flow.md#2-step-0-entry-job-and-job-folder)

## Türkçe

**gallery-dl (`gallery_dl`)**

**Ne yapar:** Kaynak olarak bir galeri bağlantısı (şu an Instagram) verildiğinde videoyu gallery-dl ile indirir.
YouTube/Vimeo/Dailymotion bağlantıları yt-dlp ile kalır.

| | |
|---|---|
| Lisans | **GPL-2.0-only**. Bu repo onu **asla içe aktarmaz**; yalnız komut satırı aracını ayrı süreçte çalıştırır (bağımsız program), repo Apache-2.0 kalır |
| Kaynak | https://github.com/mikf/gallery-dl |
| Kurulum | `pip install .[galeri]` ya da gallery-dl'i PATH'e koyun / `DUBLAJ_GALLERY_DL=<exe yolu>` |
| Donanım | işlemci, <100 MB RAM |
| Varsayılan | kapalı (yalnız galeri bağlantısı verilince çalışır) |

**Giriş/çerez:** Giriş isteyen içerik için çerez bu repoda tutulmaz. gallery-dl'in kendi ayar dosyasını kendi
makinenizde hazırlayın (gallery-dl belgeleri) ve yolunu `.env` içinde `DUBLAJ_GALLERY_DL_AYAR` ile verin.
Komut: `gallery-dl --destination <iş>/galeri_indirme --filter "extension in (video uzantıları)" [--config] -- <url>`.

**Sorumlu kullanım:** Yalnız hakkınız olan ya da izinli içerik; sitenin kullanım şartları size aittir.

**Sık hata**
- `gallery-dl kurulu değil` → extras ya da PATH.
- `video dosyası indirmedi` → bağlantıda video yok ya da giriş gerekiyor (ayar dosyası).

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** galeri bağlantısı verildiğinde gallery-dl ayrı bir program olarak çalışır; yalnız video uzantıları iş
  klasörüne indirilir, bağlantı `--` ayırıcısından sonra verilir.
- **Neden böyle:** bu tür galeri sitelerinde yt-dlp bot olarak algılandı ve tarayıcı çerezi denemeleri başarısız oldu;
  gallery-dl kendi oturum ayar dosyasıyla çalıştı. GPL-2.0 olduğu için içe aktarılmaz, ayrı süreçte çalışır
  ([ADR 0017](../adr/0017-defaults-and-licence-gate.md)). Oturum bilgisi repoda tutulmaz.
- **Diğer parçalarla ahengi:** bağlantı türünü `kaynak_girdisi` belirler; indirilen dosya yerel dosya gibi hatta girer.
- Uçtan uca akıştaki yeri: [hat_akisi.md, adım 0 (giriş)](../muhendislik/hat_akisi.md#2-adım-0-giriş-iş-ve-iş-klasörü)
