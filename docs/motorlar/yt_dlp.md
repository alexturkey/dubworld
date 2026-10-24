# yt-dlp (download from a link) (`yt_dlp`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Downloads the source video from a link when the input is `https://...` (also used by `dubla indir`). Called only when the input is a link of a supported site.

| | |
|---|---|
| License | Unlicense |
| Commercial use | yes |
| Source | https://github.com/yt-dlp/yt-dlp |
| Install | `scripts/kur.ps1 -Adim youtube` (extra `youtube`) |
| Hardware | network tool, < 100 MB RAM (estimate) |
| Default | off; input is a local file |

**Settings**

- `dubla https://... ` or `dubla indir URL -o dir`
- **Only content you own or may use; the site's terms of service are your responsibility** ([ETHICS.md](../../ETHICS.md))

**Common errors**

- Link given but yt-dlp missing → install the extra; local files never need it.

**Related:** [youtube_translate](youtube_translate.md) · [gallery_dl](gallery_dl.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** the yt-dlp library is imported lazily only when the input is a link of a supported video site; it
  downloads one file with a size limit and no playlist expansion.
- **Why this choice:** Unlicense, so importing it is allowed (unlike GPL gallery-dl, which runs as a separate program).
  The extra options with known security advisories (`--exec`, link writing, external downloaders) are not used.
- **How it fits:** the link check (`kaynak_girdisi`) decides the tool before anything else runs; the downloaded file
  enters the pipeline like a local file; local files never need yt-dlp. Its version floor follows security fixes.
- Details: [mimari.md](../mimari.md) (Sources and links) · [ADR 0017](../adr/0017-defaults-and-licence-gate.md)
- Place in the end-to-end flow: [pipeline-flow.md, step 0 (entry)](../engineering/pipeline-flow.md#2-step-0-entry-job-and-job-folder)

## Türkçe

**Ne yapar:** Girdi `https://...` olduğunda kaynak videoyu bağlantıdan indirir (`dubla indir` de bunu kullanır). Yalnız girdi desteklenen bir sitenin bağlantısıysa çağrılır.

| | |
|---|---|
| Lisans | Unlicense |
| Ticari kullanım | evet |
| Kaynak | https://github.com/yt-dlp/yt-dlp |
| Kurulum | `scripts/kur.ps1 -Adim youtube` (ek `youtube`) |
| Donanım | ağ aracı, < 100 MB RAM (tahmin) |
| Varsayılan | kapalı; girdi yerel dosyadır |

**Ayarlar**

- `dubla https://... ` ya da `dubla indir URL -o dir`
- **Yalnız sahibi olduğunuz ya da kullanma izniniz olan içerik; sitenin kullanım şartlarına uymak sizin sorumluluğunuzdadır** ([ETHICS.md](../../ETHICS.md))

**Sık hatalar**

- Bağlantı verildi ama yt-dlp yok → eki kurun; yerel dosyalar buna hiç ihtiyaç duymaz.

**İlgili:** [youtube_translate](youtube_translate.md) · [gallery_dl](gallery_dl.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** yt-dlp kütüphanesi yalnız girdi desteklenen bir video sitesinin bağlantısı olduğunda, ihtiyaç anında içe
  aktarılır; boyut sınırıyla ve oynatma listesi açılmadan tek bir dosya indirir.
- **Neden bu seçim:** Unlicense olduğu için içe aktarılabilir (ayrı bir program olarak çalışan GPL lisanslı gallery-dl'in
  aksine). Bilinen güvenlik bildirimi olan ek seçenekler (`--exec`, bağlantı yazma, harici indiriciler) kullanılmaz.
- **Diğer parçalarla ahengi:** aracı, başka hiçbir şey çalışmadan önce bağlantı denetimi (`kaynak_girdisi`) belirler;
  indirilen dosya hatta yerel dosya gibi girer; yerel dosyalar yt-dlp'ye hiç ihtiyaç duymaz. Alt sürüm sınırı güvenlik
  düzeltmelerini izler.
- Ayrıntı: [mimari.md](../mimari.md) (Sources and links bölümü) · [ADR 0017](../adr/0017-defaults-and-licence-gate.md)
- Uçtan uca akıştaki yeri: [hat_akisi.md, adım 0 (giriş)](../muhendislik/hat_akisi.md#2-adım-0-giriş-iş-ve-iş-klasörü)
