# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · فارسی · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md)

<div dir="rtl">

> DubWorld ویدیوهای شما را روی همان کامپیوتر خودتان، بدون آپلود در هیچ سرویس آنلاینی، به زبانی دیگر دوبله می‌کند: گفتار را همراه با زمان دقیق هر کلمه به متن تبدیل می‌کند، ترجمه می‌کند و بعد با یک صدای مصنوعی (هوش مصنوعی) می‌خواند که با تصویر اصلی هماهنگ می‌ماند (گفتار حداکثر ۱٫۲۵ برابر تند می‌شود و باقی اختلاف با کمی تغییر در سرعت ویدیو جبران می‌شود)، زیرنویس اضافه می‌کند و ویدیوی تازه‌ای می‌سازد. زبان پیش‌فرض ترکی است. صادقانه بگوییم: دوبله **به** فارسی هنوز ممکن نیست، چون هیچ‌کدام از موتورهای صدای این مخزن فعلاً فارسی حرف نمی‌زنند؛ اما ویدیوهای فارسی را می‌توانید به زبان‌های دیگر دوبله کنید ([docs/diller.md](docs/diller.md)).

## بگذارید دستیار هوش مصنوعی‌تان نصبش کند

لازم نیست برنامه‌نویسی بلد باشید. یک دستیار هوش مصنوعی باز کنید که بتواند روی کامپیوترتان فرمان اجرا کند (Claude Code، Codex،
Gemini CLI یا مشابه آن) و همین یک جمله را در آن بچسبانید:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

دستیار کامپیوتر شما را بررسی می‌کند (کارت گرافیک، پردازنده، حافظه، دیسک) و فقط یک بار، به زبان ساده، می‌پرسد چه نوع
نصبی می‌خواهید: سریع، پیشنهادی برای کامپیوتر شما، یا کامل. درباره‌ی هر بخش توضیح می‌دهد (چه کار می‌کند، چقدر جا می‌گیرد،
نصبش چقدر طول می‌کشد، مجوزش چیست) و از صدای پیش‌فرض شروع می‌کند و می‌پرسد آیا شرایط استفاده از بخش‌های انتخاب‌شده را
می‌پذیرید. بعد نصب می‌کند، یک دوبله‌ی نمونه می‌سازد و پنجره‌ی برنامه را باز می‌کند.
قدم‌های اول و مشکلات رایج، به زبان ساده (به انگلیسی): **[docs/getting-started.md](docs/getting-started.md)**.

**مجوزها در یک نگاه:** کد Apache-2.0. مدل‌های پیش‌فرض: صدای Supertonic 3 با مجوز OpenRAIL-M (محدودیت‌های استفاده، یک بار پذیرفته می‌شود)؛ Opus-MT و مدل زمان کلمات ترکی با CC BY 4.0 (ذکر منبع الزامی است، NOTICE)؛ نسخه‌ی FFmpeg با GPL-3.0 (برنامه‌ای جداگانه). فقط برای استفاده‌ی غیرتجاری و به‌طور پیش‌فرض خاموش: CrisperWhisper 2.0، XTTS-v2 و مدل‌های زمان کلمات WhisperX برای fr / de / es / it. این مخزن هیچ وزن مدلی ندارد ([THIRD_PARTY.md](THIRD_PARTY.md)).

## نصب سریع

Windows 10/11 x64؛ نیازی نیست Python، CUDA یا ffmpeg از قبل نصب باشد. روی **`kur.cmd`** دوبار کلیک کنید (یا اجرا کنید:
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`)؛ پروفایل GPU یا CPU خودش انتخاب می‌شود
(`-Cpu` استفاده از CPU را اجباری می‌کند). بعد روی `arayuz.cmd` دوبار کلیک کنید تا برنامه باز شود.
همه‌چیز داخل پوشه‌ی مخزن می‌ماند (`.venv`، `runtime_assets/`)؛ نسخه‌ی هر دانلود ثابت است و
با sha256 بررسی می‌شود. فضای خالی لازم برای شروع: ۲۲ گیگابایت با پروفایل GPU، ۱۴ گیگابایت فقط با CPU؛ مصرف اندازه‌گیری‌شده پس از نصب ≈ ۱۴٫۶ گیگابایت (GPU، فایل‌های هاردلینک یک بار شمرده شده‌اند؛ File Explorer ≈ ۲۲ گیگابایت نشان می‌دهد). بررسی: `.venv\Scripts\dubla.exe kontrol`.

پیش‌نیازها، ترتیب مراحل، نقشه‌ی محیط‌های Python، موتورهای اختیاری، استفاده‌ی آفلاین، به‌روزرسانی، حذف و
خطاهای رایج (به انگلیسی): **[docs/installation.md](docs/installation.md)**. روی Linux و macOS هنوز آزمایش نکرده‌ایم. نمونه: [معرفی محصول که روی یک Mac با Apple M4 و فقط با CPU به انگلیسی، ترکی و عربی دوبله شده](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## نحوه‌ی استفاده

برنامه‌ی دسکتاپ: دوبار کلیک روی `arayuz.cmd` (برنامه‌ی وب محلی: `web.cmd`، فقط روی 127.0.0.1). رابط برنامه فعلاً ترکی است. از خط فرمان:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

دوبله به فارسی هنوز در دسترس نیست، چون موتورهای صدا فارسی نمی‌خوانند؛ اما یک ویدیوی فارسی را می‌توانید مثلاً با `--ayar genel.hedef_dil=en` به انگلیسی یا با فرمان پیش‌فرض به ترکی دوبله کنید (ترجمه از فارسی به Codex یا Claude Code نیاز دارد). نتیجه‌ها در `cikti/<video>_<time>/` ذخیره می‌شوند: `dubbed_tr.mp4` (با برچسب `AI-dubbed`)، زیرنویس اصلی `transcript_<lang>.srt` و فایل‌های کاری JSON؛ آخرین خط `dubbed_video:` مسیر را نشان می‌دهد. همه‌ی تنظیمات (به انگلیسی و ترکی): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## چطور کار می‌کند

1. **صدا:** FFmpeg صدا را جدا می‌کند؛ Demucs (MIT) اختیاری، گفتار را از صدای پس‌زمینه جدا می‌کند.
2. **گفتار به متن:** faster-whisper large-v3-turbo (MIT) با زمان کلمات از wav2vec2 CTC (انگلیسی MIT، ترکی CC BY 4.0)؛ CrisperWhisper 2.0 اختیاری (غیرتجاری) و موتورهای دیگر.
3. **گوینده‌ها:** 3D-Speaker CAM++ (Apache-2.0) و یک مدل تشخیص جنسیت (Apache-2.0) برای هر گوینده یک صدای هوش مصنوعی انتخاب می‌کنند.
4. **ترجمه:** اگر Codex CLI یا Claude Code CLI نصب و وارد حساب شده باشد همان، وگرنه Opus-MT محلی از انگلیسی به ترکی (CC BY 4.0)؛ بک‌اندهای API اختیاری‌اند.
5. **صدا و زمان‌بندی:** پیش‌فرض Supertonic 3 (OpenRAIL-M)، اختیاری VoxCPM2 (Apache-2.0) یا XTTS-v2 (غیرتجاری)؛ هر جمله حداکثر ۱٫۲۵ برابر به سمت زمان بخش اصلی تند می‌شود و باقی‌اش با زمان ویدیو تنظیم می‌شود، پس دوبله ممکن است از اصل بلندتر شود.
6. **ویدیو:** FFmpeg صدای تازه، زیرنویس SRT / VTT / ASS و برچسب `AI-dubbed` را می‌نویسد.

## اندازه‌گیری‌ها

کامپیوتر مرجع: GPU پاسکال ۴ گیگابایتی، Windows 10؛ روش و همه‌ی ردیف‌ها در [docs/olcumler.md](docs/olcumler.md).

| چه چیزی | پروفایل CPU | پروفایل GPU |
|---|---|---|
| نصب اول، مراحل پیش‌فرض، از اول تا آخر | ≈ ۳۸ دقیقه | ≈ ۴۴ دقیقه (بسته‌ها ۱۳٫۷ دقیقه) |
| دیسک پس از نصب | ≈ ۱۳٫۲ گیگابایت (جمع پوشه‌ها) | ≈ ۱۴٫۶ گیگابایت (هاردلینک‌ها یک بار) |
| دوبله‌ی نمونه‌ی ۹ ثانیه‌ای، ترجمه‌ی آفلاین | ۵۲۸ ثانیه | ۳۷۶ ثانیه |
| کلیپ انگلیسی ۳۰ ثانیه‌ای، Demucs، ترجمه با Claude Code | – | ۷۴۴ ثانیه |

## محدودیت‌ها

- بدون CrisperWhisper (موتور اختیاری ۱۳)، faster-whisper ممکن است در چینی و ژاپنی بخشی از گفتار را جا بیندازد یا متنی بسازد که گفته نشده (دیده‌شده: ≈ ۱۰ ثانیه‌ی اول یک کلیپ چینی از دست رفت؛ یک فریاد به خط بلند «ああ…» تبدیل شد).
- CI فقط CPU را آزمایش می‌کند؛ مسیر GPU دستی روی یک کارت پاسکال ۴ گیگابایتی اجرا شده. کارت‌های جدید (RTX 50)، Linux و macOS آزمایش نشده‌اند؛ کتابخانه‌های GPU نصب‌شده کرنل‌هایی از پاسکال تا RTX 50 دارند و Maxwell از پروفایل CPU استفاده می‌کند ([جدول پشتیبانی GPU، به انگلیسی](docs/installation.md#1-system-requirements)).
- مترجم آفلاین فقط انگلیسی به ترکی است؛ جفت‌زبان‌های دیگر به Codex / Claude Code CLI یا یک بک‌اند API نیاز دارند.
- زمان کلمات برای زبان‌های مبدأ غیر از انگلیسی و ترکی: ژاپنی و چینی با `scripts/kur.ps1 -Adim hizalama-diller`، بقیه پس از یک بار اجرا با `DUBLAJ_CEVRIMICI=1`.
- هنوز از اول تا آخر آزمایش نشده: نصب واقعی XTTS-v2، RVC، ربات تلگرام وصل به سرویس واقعی و CrisperWhisper 2 Medium؛ Moonshine آزمایشی است. CrisperWhisper 2.0 Turbo (موتور ۱۳) با صدای واقعی روی GTX 1050 Ti 4 GB آزمایش شده (tr، en، ja؛ ≈ ۱٫۴ گیگابایت VRAM).

## قطعه‌های سازنده

هر مرحله جداگانه هم اجرا می‌شود، از خط فرمان یا از Python، و قالب فایل‌های بین مراحل مستند شده است
(نقشه‌ی مراحل و JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` همین مراحل را به‌صورت تابع در اختیار می‌گذارد. فقط آنچه یک مرحله لازم دارد نصب کنید، مثلاً
`pip install -e ".[stt,hizalama,cpu]"` برای زیرنویس. پنج ابزار کوچک ساخته‌شده از این قطعه‌ها: [examples/](examples/).

## خانواده / پروژه‌های مرتبط

| مخزن | چیست | این مخزن چطور از آن استفاده می‌کند |
|---|---|---|
| **DubWorld** (همین مخزن) | زنجیره‌ی دوبله‌ی ویدیوی کاملاً محلی، هر مرحله جداگانه هم قابل استفاده است | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | تبدیل کلمه‌به‌کلمه‌ی گفتار به متن با زمان کلمات (CrisperWhisper 2.0 Turbo + هم‌ترازی CTC) | موتور اختیاری ۱۳: `scripts/kur.ps1 -Adim crisper` مدل را از طریق آن مخزن روی یک commit ثابت نصب می‌کند (وزن‌ها **غیرتجاری**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | طراحی صدا و خواندن متن با VoxCPM2، ۸ زبان، صداهای آماده | موتور صدای اختیاری `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` روی یک commit ثابت نصب می‌کند؛ این مخزن آن را با یک آداپتور نازک صدا می‌زند |

هر مخزن خواهر مجوز، نصب و issueهای خودش را دارد؛ به لطف commit ثابت، این ترکیب هر بار با همان نتیجه دوباره ساخته می‌شود.

## استفاده‌ی مسئولانه

> **یادداشت حقوقی.** مسئولیت کامل محتوایی که با این نرم‌افزار پردازش و منتشر می‌کنید، و رعایت قوانین کشورتان و شرایط
> سایت‌ها و سرویس‌هایی که استفاده می‌کنید، با خود شماست. نرم‌افزار «همان‌طور که هست» و بدون هیچ ضمانتی ارائه می‌شود
> (Apache-2.0). متن کامل: [ETHICS.md](ETHICS.md).

- **حقوق و رضایت.** فقط محتوایی را پردازش کنید که مال شماست یا حق ترجمه و دوبله‌ی دوباره‌اش را دارید،
  و از کسانی که در آن قابل شناسایی‌اند رضایت بگیرید.
- **صداها.** تقلید صدای هیچ‌کس ممنوع. صدای مرجع فقط می‌تواند صدای خودتان یا کسی باشد که به‌روشنی اجازه داده است.
- **برچسب بزنید.** خروجی برچسب فراداده‌ی `AI-dubbed` دارد؛ آن را نگه دارید و به‌شکلی آشکار به بینندگان بگویید
  که دوبله با هوش مصنوعی ساخته شده (ماده‌ی ۵۰ قانون هوش مصنوعی اتحادیه‌ی اروپا؛ مجوز Supertonic).
- **دانلودها.** افزونه‌های اختیاری `youtube` (yt-dlp) و `galeri` (gallery-dl) فقط برای محتوایی است که مال شماست یا اجازه‌ی دانلودش را دارید؛ شرایط سایت و
  قوانین محلی شما برقرار است.
- **موتورهای غیرتجاری.** CrisperWhisper 2.0 و XTTS-v2 فقط برای استفاده‌ی غیرتجاری‌اند (به‌طور پیش‌فرض خاموش). پیش از هر کار پولی یا برای مشتری،
  ستون **Commercial?** را در [THIRD_PARTY.md](THIRD_PARTY.md) ببینید.
  مدل‌های زمان کلمات برای صدای مبدأ fr / de / es / it (CC BY-NC 4.0) هم غیرتجاری‌اند و در اولین استفاده رضایت می‌خواهند.

## کمک و پشتیبانی

پرسش‌ها، ایده‌ها و نتیجه‌های شما: [انجمن گفت‌وگو](https://github.com/alexturkey/dubworld/discussions). مشکل نصب: [گزارش مشکل نصب](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml)؛ خطاها: [گزارش خطا](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(سیستم‌عامل، GPU، فرمانی که اجرا کردید و چند خط آخر خروجی را بنویسید). مسائل امنیتی: SECURITY.md را ببینید، در issue عمومی ننویسید.

## مجوز و قدردانی

کد: Apache-2.0 (LICENSE). بخش‌های بیرونی و مجوزهایشان: THIRD_PARTY.md. استفاده‌ی مسئولانه: ETHICS.md.
حریم خصوصی (چه چیزی روی کامپیوتر شما می‌ماند، بک‌اند ابری چه می‌گیرد): PRIVACY.md. گزارش امنیتی: SECURITY.md. تغییرات: CHANGELOG.md.

</div>

<!-- i18n-source: README.md sha256:48bbf9594411 -->
