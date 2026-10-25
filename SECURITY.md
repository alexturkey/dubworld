# Güvenlik / Security

**TR**

Bir güvenlik açığı bulduysanız lütfen herkese açık bir issue açmayın. GitHub'ın özel bildirim yolunu kullanın: repo
sayfasında **Security → Report a vulnerability**. Yazarken: sürüm, nasıl tetiklendiği, etkisi. Hedef: 7 gün içinde ilk
cevap.

Kapsam: bu depodaki kod ve `scripts/` altındaki kurulum betikleri. Kapsam dışı (bildirimi ilgili projeye yapın):
bağımlı Python paketleri ve modeller; `vendor/` altında bayt bayt aynı tutulan üçüncü taraf kod; Codex CLI, Claude Code
CLI, bulut çeviri ve konuşma tanıma API'leri ile Telegram'ın kendisi; sizin seçip yüklediğiniz model dosyaları (RVC,
XTTS referansı) ve yapılandırmalar (ör. `DUBLAJ_GALLERY_DL_AYAR`) güvenilir girdi sayılır; web arayüzünü 127.0.0.1
dışına açan vekil ya da tünel kurulumları; model çıktısının içerik kalitesi ve kötüye kullanımı (bkz. `ETHICS.md`).

Tasarım sınırları:

- Yerel araçtır: sunucu işletilmez, telemetri ya da güncelleme denetimi yoktur (`PRIVACY.md`). Veri yalnız kullanıcı
  bir bulut arka ucu seçince, bağlantı verince, kurulum yapınca ya da Telegram botunu başlatınca dışarı çıkar.
- Web arayüzü (`dubla-web`) yalnız `127.0.0.1`'e bağlanır; Host başlığı `127.0.0.1`/`localhost` değilse istek
  reddedilir (DNS yeniden bağlama), her API isteği oturum belirteci ister (çerez + başlık), Origin aynı köken olmalı,
  JSON gövdesi ve yükleme boyutu sınırlıdır, dosya yolları çıktı klasörünün dışına çıkamaz.
- Web belirteci = yerel komut yürütme yetkisi: belirteci ele geçiren bu bilgisayarda iş başlatabilir (indirme, model,
  alt süreç). Belirteci paylaşmayın. Yerel program yolu ayarları (`ceviri.codex.cli_yolu`, `ceviri.claude.cli_yolu`)
  arayüzden (web ya da kendi penceresi) ve Telegram'dan değiştirilemez; yalnız ayar dosyası ya da komut satırı `--ayar` ile.
- Kurulum indirmeleri sabit adres + SHA-256 ile doğrulanır (`scripts/modeller.json`); model indirici yalnız https ve
  izinli alan adlarını kabul eder, https olmayan yönlendirmeyi reddeder. Python paketleri hash'li kilit dosyalarından
  `--require-hashes` ile kurulur. Çalışma anında model indirme kapalıdır (`HF_HUB_OFFLINE=1`).
- Çeviri köprüsü API'lere yalnız https ve izinli sağlayıcı alan adlarıyla gider; anahtarlar ortam değişkeninden okunur,
  günlüğe yalnız anahtarın adı yazılır.
- Altyazı ve transkript metni veri sayılır: istem veri/talimat ayrımı içerir, model çıktısında kaynakta olmayan
  bağlantı ya da açıklama satırı varsa iş hata verir (sessiz geçiş yok). Codex salt okunur sandbox'ta, Claude Code
  araçları kapalı ve oturum kaydı olmadan alt süreç olarak çalışır.
- Alt süreçler kabuk olmadan, argüman listesiyle başlatılır; ağır modeller ayrı süreçte ya da ayrı ortamda çalışır.
- Ticari olmayan ya da şartlı lisanslı motorlar ilk kullanımda açık onay ister (lisans kapısı; XTTS için CPML onayı,
  RVC için sesin sahibinin rızası). Bu bir lisans kapısıdır, güvenlik sınırı değildir.
- Telegram botu yalnız izinli kullanıcı kimliklerine cevap verir; belirteç hata mesajlarında maskelenir.
- **Kilitli bağımlılıklardaki bilinen kayıtlar:** CI'deki `audit` işi `pip-audit` ile `requirements/cpu.txt` ve
  `gpu.txt`'yi tarar ve yalnız raporlar. Bazı sürümler bilerek geride tutulur: `setuptools` 80.9 (`modelscope`
  `pkg_resources` ister), `datasets` 3.1 ve onun sınırladığı `fsspec` (3D-Speaker/`modelscope`), `transformers` 4.57
  (5.x büyük sürüm). Pillow ve onnx kayıtları güvenilmeyen görüntü/model dosyası açmayla ilgilidir; bu hat yalnız
  SHA-256 ile sabitlenmiş modelleri yükler. Kilit yenileme: `scripts/kilitle.ps1`, ardından tam duman testi.
- **Açık Dependabot uyarıları (`transformers`, `torch`):** ana bağımlılık dosyalarında `transformers` 4.57.6'ya
  sabit; hem `transformers` hem `torch` için açık uyarılar var. Pratik risk düşük: model ağırlıkları sabittir ve
  commit/SHA-256 ile sabitlenir (hizalama modelleri artık commit ile; konuşma tanıma ve ses üretimi ağırlıkları
  `scripts/modeller.json`'da), çalışma anı varsayılan olarak çevrimdışıdır (`DUBLAJ_CEVRIMICI=1` verilmedikçe
  `HF_HUB_OFFLINE`), uyarıların dayandığı yollar (güvenilmeyen model dosyası yükleme, uzak özel üretim kodu,
  güvenilmeyen girdiyle `save_pretrained`, LightGlue, `Trainer`) DubWorld'de kullanıcı girdisiyle çalışmaz.
  Şimdi güncellenmemesinin nedeni: her `transformers` 5.x `huggingface-hub >= 1.3` ister, son kararlı `whisperx`
  (3.8.6) ise `huggingface-hub < 1.0` ister; `whisperx` 3.8.7rc1 bu sınırı kaldırıyor ama ön sürümdür. Yeniden
  denenecek an: `whisperx` 3.8.7 kararlı (ya da sonrası) çıkınca. İsteğe bağlı XTTS motorunun ayrı ortamı
  `transformers` 4.57.6'da kalır (`coqui-tts` ister); oradaki uyarılar gözden geçirildi, tolere edilebilir risk
  olarak kabul edildi.

**EN**

Please do not open a public issue for a vulnerability. Use **Security → Report a vulnerability** on the repo page.
Include the version, how to trigger it and the impact. Target: first reply within 7 days.

Scope: code in this repo and the install scripts under `scripts/`. Out of scope (report upstream): dependencies and
models; third-party code kept byte-identical under `vendor/`; Codex CLI, Claude Code CLI, the cloud translation and
speech-recognition APIs and Telegram themselves; model files and configuration you choose and load yourself (RVC models,
XTTS reference audio, a gallery-dl config set with `DUBLAJ_GALLERY_DL_AYAR`) are treated as trusted input; proxy or
tunnel setups that expose the web interface beyond 127.0.0.1; content quality and misuse of model output (see
`ETHICS.md`).

Design limits:

- Local tool: no server is operated, no telemetry or update check (`PRIVACY.md`). Data leaves the machine only when
  the user selects a cloud backend, gives a link, runs the installer or starts the Telegram bot.
- The web interface (`dubla-web`) binds to `127.0.0.1` only; requests whose Host header is not `127.0.0.1`/`localhost`
  are rejected (DNS rebinding), every API request needs the session token (cookie + header), Origin must be same-origin,
  JSON bodies and uploads are size-limited, and file paths cannot leave the output folder.
- Web token = local command execution: whoever obtains the token can start jobs on this computer (downloads, models,
  child processes). Do not share it. The local program path settings (`ceviri.codex.cli_yolu`, `ceviri.claude.cli_yolu`)
  cannot be changed from the interface (browser or its own window) or Telegram; only from a settings file or the command-line `--ayar`.
- Install downloads use fixed addresses verified by SHA-256 (`scripts/modeller.json`); the model downloader accepts
  only https and allow-listed hosts and refuses non-https redirects. Python packages install from hashed lock files with
  `--require-hashes`. Model downloads are off at run time (`HF_HUB_OFFLINE=1`).
- The translation bridge calls APIs only over https on allow-listed provider hosts; keys come from environment variables
  and only the key's name is logged.
- Subtitle and transcript text is treated as data: the prompt separates data from instructions, and output containing
  links or commentary not present in the source fails the job (no silent pass). Codex runs in a read-only sandbox and
  Claude Code with tools disabled and no session persistence, both as child processes.
- Subprocesses are started without a shell, from argument lists; heavy models run in their own process or environment.
- Non-commercial or conditionally licensed engines require explicit acceptance on first use (licence gate; CPML
  acceptance for XTTS, speaker consent for RVC). This is a licence gate, not a security boundary.
- The Telegram bot answers allow-listed user ids only; its token is masked in error messages.
- **Known advisories in pinned dependencies:** the CI `audit` job runs `pip-audit` on `requirements/cpu.txt` and
  `gpu.txt` and reports only. Some pins are held back on purpose: `setuptools` 80.9 (`modelscope` needs
  `pkg_resources`), `datasets` 3.1 and the `fsspec` it caps (3D-Speaker/`modelscope`), `transformers` 4.57 (5.x is a
  major release). The Pillow and onnx advisories concern opening untrusted image/model files; this pipeline loads only
  SHA-256-pinned models. Lock refresh: `scripts/kilitle.ps1`, then a full smoke test.
- **Open Dependabot alerts (`transformers`, `torch`):** `transformers` is pinned to 4.57.6 in the main dependency
  files, and there are open alerts on both `transformers` and `torch`. Practical risk is low: model weights are fixed
  and pinned by commit/SHA-256 (alignment models are now pinned by commit; speech-recognition and TTS weights are
  pinned in `scripts/modeller.json`), the runtime is offline by default (`HF_HUB_OFFLINE` unless
  `DUBLAJ_CEVRIMICI=1`), and the code paths the alerts rely on (loading untrusted checkpoints, remote custom
  generation code, `save_pretrained` on untrusted input, LightGlue, `Trainer`) are not run by DubWorld on user input.
  Why it is not updated now: every `transformers` 5.x needs `huggingface-hub >= 1.3`, while the latest stable
  `whisperx` (3.8.6) requires `huggingface-hub < 1.0`; `whisperx` 3.8.7rc1 lifts that cap but is a prerelease. It
  will be retried when `whisperx` 3.8.7 final (or later) is released. The optional XTTS engine's separate
  environment stays on `transformers` 4.57.6 (`coqui-tts` needs it); those alerts were reviewed and accepted as
  tolerable risk.
