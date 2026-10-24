# Cover image (Codex CLI image generation) (`kapak_gorseli`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Generates 1-9 (default 5) different vertical 9:16 cover images from the dub transcript; it uses the
Codex CLI's built-in image generation tool with your own Codex login. If Codex is not installed, the step is skipped.

| | |
|---|---|
| License / terms | OpenAI terms of service (cloud); the transcript is sent to the service (PRIVACY.md) |
| Source | https://github.com/openai/codex |
| Install | `npm i -g @openai/codex` ; `codex login` (or `CODEX_BRIDGE_CODEX_BIN`) |
| Hardware | no local load |
| Default | off (run manually) |

**Usage:** `python -m dublaj_hatti.bolum_70_gorsel_uretim.kapak_gorseli <transkript.txt> <çıktı klasörü> --dil tr --adet 5`
Output: `kapak_01_9x16.png ...` and `kapak_ozeti.json` (cover text, size, duration). Model/effort: `DUBLAJ_KAPAK_MODEL`,
`DUBLAJ_KAPAK_CABA` (default as in the source).

**Security:** Codex runs in a separate process, without opening a window, in a sandbox that can write only to the job
folder; shell, browser and plugin features are off, only image generation is on. Your login is copied to a temporary
job-specific folder and deleted when the job ends (even on error); API key variables are not passed to the
subprocess. Prompt: generating claims not in the transcript, likenesses of real people or brand logos is forbidden.
Every image is verified as PNG, 9:16, at least 800x1400.

**Common errors**
- `codex_yok` → Codex is not installed; the step is skipped (exit 0).
- `codex_giris` → `codex login`.
- `9:16 değil` / `çözünürlüğü yetersiz` → the model broke the rule; run again.

## How it works in this pipeline / Neden böyle

- **Principle:** the Codex CLI runs in a separate process, in a sandbox that can write only to the job folder; shell,
  browser and plugin features are off, only the built-in image generation is on. The saved Codex login is copied to a
  temporary job-specific folder and deleted at the end of the job.
- **Why this choice:** it generates images without installing an extra image model, using the Codex login that may
  already be installed for the translation backend. The isolation principle of the translation bridge applies here too
  ([translation.md](../engineering/translation.md) §1).
- **How it fits:** it is not connected to the dubbing pipeline; it is a separate tool run manually from a transcript
  file. Every image is verified as 9:16 and at least 800x1400; if Codex is missing the step is skipped.

## Türkçe

**Kapak görseli (`kapak_gorseli`)**

**Ne yapar:** Dublaj transkriptinden 1-9 (varsayılan 5) farklı dikey 9:16 kapak görseli üretir; Codex CLI'nin
yerleşik görsel üretim aracını sizin Codex girişinizle kullanır. Codex kurulu değilse adım atlanır.

| | |
|---|---|
| Lisans / şart | OpenAI hizmet şartları (bulut); transkript hizmete gönderilir (PRIVACY.md) |
| Kaynak | https://github.com/openai/codex |
| Kurulum | `npm i -g @openai/codex` ; `codex login` (ya da `CODEX_BRIDGE_CODEX_BIN`) |
| Donanım | yerel yük yok |
| Varsayılan | kapalı (elle çalıştırılır) |

**Kullanım:** `python -m dublaj_hatti.bolum_70_gorsel_uretim.kapak_gorseli <transkript.txt> <çıktı klasörü> --dil tr --adet 5`
Çıktı: `kapak_01_9x16.png ...` ve `kapak_ozeti.json` (kapak metni, boyut, süre). Model/çaba: `DUBLAJ_KAPAK_MODEL`,
`DUBLAJ_KAPAK_CABA` (varsayılan kaynaktaki gibi).

**Güvenlik:** Codex ayrı süreçte, pencere açmadan, yalnız iş klasörüne yazabilen kum havuzunda; kabuk, tarayıcı,
eklenti özellikleri kapalı, yalnız görsel üretim açık. Girişiniz işe özel geçici bir klasöre kopyalanır ve iş
bitince (hata olsa da) silinir; API anahtarı değişkenleri alt sürece geçmez. İstem: transkriptte olmayan iddia,
gerçek kişi benzerliği, marka logosu üretme yasak. Her görsel PNG, 9:16, en az 800x1400 olarak doğrulanır.

**Sık hata**
- `codex_yok` → Codex kurulu değil; adım atlanır (çıkış 0).
- `codex_giris` → `codex login`.
- `9:16 değil` / `çözünürlüğü yetersiz` → model kuralı çiğnedi; yeniden çalıştırın.

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** Codex CLI ayrı bir süreçte, yalnız iş klasörüne yazabilen kum havuzunda çalışır; kabuk, tarayıcı ve eklenti
  özellikleri kapalıdır, yalnız yerleşik görsel üretim açıktır. Kayıtlı Codex girişi işe özel geçici bir klasöre
  kopyalanır ve iş sonunda silinir.
- **Neden böyle:** ek bir görsel modeli kurmadan, çeviri arka ucu için zaten kurulu olabilen Codex girişiyle görsel
  üretir. Çeviri köprüsündeki yalıtım ilkesi burada da uygulanır ([translation.md](../engineering/translation.md) §1).
- **Diğer parçalarla ahengi:** dublaj hattına bağlı değildir; transkript dosyasından elle çalıştırılan ayrı bir
  araçtır. Her görsel 9:16 ve en az 800x1400 olarak doğrulanır; Codex yoksa adım atlanır.
