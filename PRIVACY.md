# Privacy / Gizlilik

The English text is binding; the Turkish section below is a full translation. / Bağlayıcı metin İngilizcedir; aşağıdaki
Türkçe bölüm tam çevirisidir.

## EN

### Summary

- This is a local tool. It runs on your computer and has **no telemetry, analytics, crash reporting or update check**.
  The authors receive nothing from your use of it.
- The **recommended flow** (Supertonic, faster-whisper / CrisperWhisper, wav2vec2 CTC, local Opus-MT or your own
  Codex/Claude CLI, FFmpeg) processes video, audio and text on your machine. The only exception in that flow is the
  translation step when Codex CLI or Claude Code CLI is selected or detected (see "Cloud backends").
- Data leaves your computer **only** when you choose a cloud backend, give a link to download, install components, or
  start the Telegram bot. Each case is listed below. You use your own account or key; this project operates no server.

### Network use by component

| Component (setting) | What is sent | To whom | Your credential |
|---|---|---|---|
| Codex CLI (`ceviri.arka_uc = codex`, or `auto` when Codex is installed) | transcript text of the video (segments) and the translation instructions | OpenAI, through your own Codex CLI | your Codex login |
| Claude Code CLI (`claude_code`, or `auto` when Codex is missing and Claude is installed) | the same transcript text | Anthropic, through your own Claude Code CLI | your Claude login |
| Gemini / Gemma (`gemini_2_5_flash`, `gemini_3_1_flash_lite_tier_1`, `gemma_4_26b`) | transcript text | Google (Gemini API) | `CODEX_BRIDGE_GEMINI_API_KEY` |
| Groq (`groq_llama_4_scout`) | transcript text | Groq | `GROQ_API_KEY_1` (or the other names in `.env.example`) |
| Cerebras (`cerebras_llama_3_1_8b`) | transcript text | Cerebras | `CEREBRAS_API_KEY` |
| Mistral (`mistral_nemo`) | transcript text | Mistral AI | `MISTRAL_API_KEY` |
| Cover image (`python -m ...kapak_gorseli`, never automatic) | the transcript, from which a neutral English image prompt is written | OpenAI, through your Codex CLI | your Codex login |
| Link input (`indir`, yt-dlp / gallery-dl) | an ordinary download request for the link you gave | the site of that link | none added by this project (a gallery-dl config you point to with `DUBLAJ_GALLERY_DL_AYAR` is used as you wrote it) |
| Install (`scripts/kur.ps1`, `scripts/modelleri_indir.py`) | file download requests | Hugging Face, GitHub, PyPI, PyTorch, ModelScope, `dl.fbaipublicfiles.com` (Meta, Demucs weight, `-Adim demucs`); Docker Hub only for the optional `-Adim telegram-sunucu` image (fixed addresses + SHA-256 in `scripts/modeller.json` and the lock files; the image by digest) | none |
| Telegram bot (`dubla-telegram`, optional) | messages and files you exchange with **your own** bot | Telegram | your `TELEGRAM_BOT_TOKEN` |

What the providers do with the data is governed by **their** terms and privacy policies, which you accept with your
account. Read them before sending content you do not own or that contains personal data. Codex and Claude Code run as
child processes with their tools restricted (Claude Code: tools disabled, no session persistence; Codex: read-only
sandbox); the job text above is passed on standard input.

At run time model downloads are off (`HF_HUB_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`); set `DUBLAJ_CEVRIMICI=1` only
if you want a missing model fetched. The web interface (`dubla-web`) listens on `127.0.0.1` only, with a per-session
token; it is not reachable from other machines.

### What is stored on your computer

Everything stays under folders you control; nothing is uploaded by the project itself.

| Item | Where | Contents |
|---|---|---|
| Job outputs | `cikti/` in the repo, or `DUBLAJ_OUTPUT_DIR` | per job: extracted audio, transcript, translation, synthesized speech, subtitles, final video, `pipeline_state.json` (stage status, input fingerprints), logs. Delete a job folder to remove it. |
| Job store | `<output folder>/_is_deposu/isler.sqlite3` (or `DUBLAJ_IS_DEPOSU`) | one row per job: source path or link, chosen settings, status, timestamps, failed stage, error message, output folder, process id. Used for the job list, resume and retry. No account data. |
| Licence acceptances | `ayarlar/lisans_onaylari.json` (or `DUBLAJ_LISANS_ONAY_DOSYASI`), git-ignored | engine name, the licence text you accepted, UTC date. No personal data. Written by the one licence gate that every entry point uses (app, web, `dubla`, stage commands such as `dubla seslendir`, `dubla devam`, Python API `lisans_onay=True`); only engines the command really runs are asked. XTTS keeps its own CPML acceptance in `runtime_assets/tts_motorlari/xtts/CPML_ONAYI.json`. |
| Settings and keys | `ayarlar/kullanici.toml`, `.env` (both git-ignored) | your settings; your API keys and bot token. Never logged; never written anywhere else by the project. |
| Translation usage logs | `runtime/usage/` inside the translation bridge folder (`src/dublaj_hatti/bolum_40_ceviri/<bridge>/runtime/`, git-ignored) | per request: time, provider, model, status, token counts, estimated cost, the **name** (never the value) of the key used; on errors the first 1000 characters of the provider's error text, which may echo part of the input. The transcript itself is not written there. |
| Translation bridge working files | `runtime/{inbox,outbox,logs,tmp}/` and `runtime/status.json` in the same folder (git-ignored) | the job sent to the CLI or API (segment texts), the model's answer and the CLI's own output: **this contains the transcript and the translation**. Safe to delete when no job is running. |
| Models | `runtime_assets/` (git-ignored) | downloaded model files only. |

The Telegram bot does not write your user id or message text to disk or to logs; unauthorised users are counted, not
recorded. Its token is masked in error messages.

### Output marking

Dubbed videos carry an "AI-dubbed" note in their metadata (`comment`, `description`) and the tool name in `encoded_by`
(transparency for synthetic speech; see ETHICS.md). No user, machine or path information is written into the file.

### Your responsibilities

You decide what you process. Only use content you have the right to use, and do not send personal data of others to a
cloud backend without a legal basis (GDPR / KVKK). Voice cloning (XTTS, RVC) requires the speaker's explicit consent
(ETHICS.md).

### Contact

Privacy questions about this code: open an issue (no personal data in it). Security problems: SECURITY.md.

## TR

### Özet

- Bu yerel bir araçtır. Bilgisayarınızda çalışır; **telemetri, analiz, çökme raporu ya da güncelleme denetimi yoktur**.
  Yazarlar kullanımınızdan hiçbir veri almaz.
- **Önerilen akış** (Supertonic, faster-whisper / CrisperWhisper, wav2vec2 CTC, yerel Opus-MT ya da kendi Codex/Claude
  CLI'niz, FFmpeg) videoyu, sesi ve metni bilgisayarınızda işler. Bu akıştaki tek istisna, Codex CLI ya da Claude Code CLI
  seçildiğinde ya da algılandığında çeviri adımıdır ("Bulut arka uçları").
- Veri bilgisayarınızdan **yalnız** bir bulut arka ucu seçtiğinizde, indirilecek bir bağlantı verdiğinizde, bileşen
  kurduğunuzda ya da Telegram botunu başlattığınızda çıkar. Her durum aşağıda. Kendi hesabınızı ya da anahtarınızı
  kullanırsınız; bu proje hiçbir sunucu işletmez.

### Bileşenlere göre ağ kullanımı

| Bileşen (ayar) | Ne gönderilir | Kime | Sizin kimlik bilginiz |
|---|---|---|---|
| Codex CLI (`ceviri.arka_uc = codex`, ya da Codex kuruluysa `auto`) | videonun transkript metni (segmentler) ve çeviri talimatları | OpenAI, kendi Codex CLI'niz üzerinden | Codex oturumunuz |
| Claude Code CLI (`claude_code`, ya da Codex yok Claude kuruluysa `auto`) | aynı transkript metni | Anthropic, kendi Claude Code CLI'niz üzerinden | Claude oturumunuz |
| Gemini / Gemma (`gemini_2_5_flash`, `gemini_3_1_flash_lite_tier_1`, `gemma_4_26b`) | transkript metni | Google (Gemini API) | `CODEX_BRIDGE_GEMINI_API_KEY` |
| Groq (`groq_llama_4_scout`) | transkript metni | Groq | `GROQ_API_KEY_1` (ya da `.env.example`'daki diğer adlar) |
| Cerebras (`cerebras_llama_3_1_8b`) | transkript metni | Cerebras | `CEREBRAS_API_KEY` |
| Mistral (`mistral_nemo`) | transkript metni | Mistral AI | `MISTRAL_API_KEY` |
| Kapak görseli (`python -m ...kapak_gorseli`, hiçbir zaman otomatik değil) | transkript (ondan nötr İngilizce görsel istemi yazılır) | OpenAI, Codex CLI'niz üzerinden | Codex oturumunuz |
| Bağlantı girdisi (`indir`, yt-dlp / gallery-dl) | verdiğiniz bağlantı için olağan indirme isteği | o bağlantının sitesi | proje eklemez (`DUBLAJ_GALLERY_DL_AYAR` ile gösterdiğiniz gallery-dl ayar dosyası yazdığınız gibi kullanılır) |
| Kurulum (`scripts/kur.ps1`, `scripts/modelleri_indir.py`) | dosya indirme istekleri | Hugging Face, GitHub, PyPI, PyTorch, ModelScope, `dl.fbaipublicfiles.com` (Meta, Demucs ağırlığı, `-Adim demucs`); Docker Hub yalnız isteğe bağlı `-Adim telegram-sunucu` imajı için (sabit adres + SHA-256: `scripts/modeller.json` ve kilit dosyaları; imaj özetle) | yok |
| Telegram botu (`dubla-telegram`, isteğe bağlı) | **kendi** botunuzla alıp verdiğiniz mesaj ve dosyalar | Telegram | `TELEGRAM_BOT_TOKEN`'ınız |

Sağlayıcıların veriyle ne yaptığı, hesabınızla kabul ettiğiniz **onların** şartları ve gizlilik politikalarıyla
belirlenir. Sahibi olmadığınız ya da kişisel veri içeren içeriği göndermeden önce okuyun. Codex ve Claude Code alt süreç
olarak araçları kısıtlı çalışır (Claude Code: araçlar kapalı, oturum kalıcılığı yok; Codex: salt okunur kum havuzu);
yukarıdaki iş metni standart girdiden verilir.

Çalışma anında model indirme kapalıdır (`HF_HUB_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`); eksik bir modelin inmesini
istiyorsanız yalnız o zaman `DUBLAJ_CEVRIMICI=1` verin. Web arayüzü (`dubla-web`) yalnız `127.0.0.1`'de, oturum
belirteciyle dinler; başka makinelerden erişilemez.

### Bilgisayarınızda ne saklanır

Her şey sizin denetlediğiniz klasörlerde kalır; proje kendiliğinden hiçbir şey yüklemez.

| Öğe | Yer | İçerik |
|---|---|---|
| İş çıktıları | repodaki `cikti/` ya da `DUBLAJ_OUTPUT_DIR` | iş başına: çıkarılan ses, transkript, çeviri, sentezlenen konuşma, altyazı, son video, `pipeline_state.json` (aşama durumu, girdi parmak izleri), günlükler. Silmek için iş klasörünü silin. |
| İş deposu | `<çıktı klasörü>/_is_deposu/isler.sqlite3` (ya da `DUBLAJ_IS_DEPOSU`) | iş başına bir satır: kaynak yolu ya da bağlantı, seçilen ayarlar, durum, zaman damgaları, başarısız aşama, hata mesajı, çıktı klasörü, süreç kimliği. İş listesi, devam ve yeniden deneme için. Hesap verisi yok. |
| Lisans onayları | `ayarlar/lisans_onaylari.json` (ya da `DUBLAJ_LISANS_ONAY_DOSYASI`), git dışı | motor adı, onayladığınız lisans metni, UTC tarih. Kişisel veri yok. Her giriş yolunun kullandığı tek lisans kapısı yazar (uygulama, web, `dubla`, `dubla seslendir` gibi aşama komutları, `dubla devam`, Python API `lisans_onay=True`); yalnız komutun gerçekten çalıştırdığı motor sorulur. XTTS kendi CPML onayını `runtime_assets/tts_motorlari/xtts/CPML_ONAYI.json` içinde tutar. |
| Ayarlar ve anahtarlar | `ayarlar/kullanici.toml`, `.env` (ikisi de git dışı) | ayarlarınız; API anahtarlarınız ve bot belirteciniz. Günlüğe yazılmaz; proje başka bir yere yazmaz. |
| Çeviri kullanım günlükleri | çeviri köprüsü klasöründeki `runtime/usage/` (`src/dublaj_hatti/bolum_40_ceviri/<köprü>/runtime/`, git dışı) | istek başına: zaman, sağlayıcı, model, durum, jeton sayısı, tahmini maliyet, kullanılan anahtarın **adı** (değeri asla); hatada sağlayıcı hata metninin ilk 1000 karakteri (girdinin bir kısmını yansıtabilir). Transkriptin kendisi oraya yazılmaz. |
| Çeviri köprüsü çalışma dosyaları | aynı klasörde `runtime/{inbox,outbox,logs,tmp}/` ve `runtime/status.json` (git dışı) | CLI'ya ya da API'ye giden iş (segment metinleri), modelin cevabı ve CLI'nın kendi çıktısı: **transkripti ve çeviriyi içerir**. İş çalışmıyorken silinebilir. |
| Modeller | `runtime_assets/` (git dışı) | yalnız indirilen model dosyaları. |

Telegram botu kullanıcı kimliğinizi ya da mesaj metninizi diske ya da günlüğe yazmaz; izinsiz kullanıcılar kaydedilmez,
yalnız sayılır. Belirteç hata mesajlarında maskelenir.

### Çıktı işareti

Dublajlı videoların üst verisinde "AI-dubbed" notu (`comment`, `description`) ve `encoded_by` alanında araç adı bulunur
(sentetik konuşma için şeffaflık; ETHICS.md). Dosyaya kullanıcı, makine ya da yol bilgisi yazılmaz.

### Sizin sorumluluğunuz

Neyi işleyeceğinize siz karar verirsiniz. Yalnız kullanma hakkınız olan içeriği kullanın; başkalarının kişisel verisini
hukuki dayanak olmadan bulut arka ucuna göndermeyin (GDPR / KVKK). Ses klonlama (XTTS, RVC) konuşmacının açık rızasını
gerektirir (ETHICS.md).

### İletişim

Bu kodla ilgili gizlilik soruları: bir issue açın (içine kişisel veri koymayın). Güvenlik sorunları: SECURITY.md.
