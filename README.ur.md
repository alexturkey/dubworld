# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · [ไทย](README.th.md) · [বাংলা](README.bn.md) · اردو · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md) · [Azərbaycanca](README.az.md) · [Bahasa Melayu](README.ms.md)

<div dir="rtl">

> DubWorld آپ کی ویڈیوز کو آپ کے اپنے کمپیوٹر پر، کسی آن لائن سروس پر اپ لوڈ کیے بغیر، دوسری زبان میں ڈب کرتا ہے: بولی کو ہر لفظ کے وقت کے ساتھ متن میں بدلتا ہے، اس کا ترجمہ کرتا ہے، پھر ایک مصنوعی (AI) آواز سے پڑھواتا ہے جو اصل ویڈیو کے ساتھ ہم آہنگ رہتی ہے (بولی زیادہ سے زیادہ 1.25 گنا تیز ہوتی ہے، باقی فرق ویڈیو کی رفتار میں ہلکی سی تبدیلی سے پورا ہوتا ہے)، سب ٹائٹل لگاتا ہے اور نئی ویڈیو بناتا ہے۔ ڈیفالٹ زبان ترکی ہے۔ سچ بات یہ ہے کہ اردو **میں** ڈبنگ ابھی ممکن نہیں، کیونکہ اس ریپوزٹری کا کوئی بھی آواز انجن فی الحال اردو نہیں بولتا؛ لیکن اردو ویڈیوز کو دوسری زبانوں میں ڈب کیا جا سکتا ہے ([docs/diller.md](docs/diller.md))۔

## اپنے AI اسسٹنٹ سے انسٹال کروائیں

پروگرامنگ آنا ضروری نہیں۔ کوئی ایسا AI اسسٹنٹ کھولیں جو آپ کے کمپیوٹر پر کمانڈ چلا سکے (Claude Code، Codex،
Gemini CLI یا اس جیسا کوئی) اور یہ ایک جملہ پیسٹ کر دیں:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

اسسٹنٹ آپ کا کمپیوٹر (گرافکس کارڈ، پروسیسر، میموری، ڈسک) دیکھتا ہے اور صرف ایک بار، آسان الفاظ میں، پوچھتا ہے کہ آپ کیسی
انسٹالیشن چاہتے ہیں: تیز، آپ کے کمپیوٹر کے لیے تجویز کردہ، یا مکمل۔ وہ ہر حصے کے بارے میں بتاتا ہے (کیا کرتا ہے، ڈسک پر کتنی
جگہ لیتا ہے، کتنا وقت لگتا ہے، لائسنس کیا ہے) اور ڈیفالٹ آواز سے شروع کر کے پوچھتا ہے کہ کیا آپ منتخب حصوں کی شرائطِ استعمال
مانتے ہیں۔ پھر انسٹال کرتا ہے، ایک نمونہ ڈب بناتا ہے اور پروگرام کی ونڈو کھول دیتا ہے۔
پہلے قدم اور عام مسائل، آسان زبان میں (انگریزی میں): **[docs/getting-started.md](docs/getting-started.md)**۔

**لائسنس ایک نظر میں:** کوڈ Apache-2.0۔ ڈیفالٹ ماڈل: Supertonic 3 آواز OpenRAIL-M کے تحت (استعمال کی پابندیاں، ایک بار ماننی ہوتی ہیں)؛ Opus-MT اور ترکی الفاظ کے وقت کا ماڈل CC BY 4.0 کے تحت (حوالہ دینا لازمی، NOTICE)؛ FFmpeg بلڈ GPL-3.0 (الگ پروگرام)۔ صرف غیر تجارتی استعمال کے لیے اور ڈیفالٹ میں بند: CrisperWhisper 2.0، XTTS-v2 اور fr / de / es / it کے لیے WhisperX الفاظ کے وقت کے ماڈل۔ اس ریپوزٹری میں کوئی ماڈل ویٹ شامل نہیں ([THIRD_PARTY.md](THIRD_PARTY.md))۔

## فوری انسٹالیشن

Windows 10/11 x64؛ پہلے سے Python، CUDA یا ffmpeg کی ضرورت نہیں۔ **`kur.cmd`** پر ڈبل کلک کریں (یا یہ چلائیں:
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`)؛ GPU یا CPU پروفائل خود منتخب ہو جاتا ہے
(`-Cpu` سے CPU زبردستی چنا جاتا ہے)۔ پھر ایپ کھولنے کے لیے `arayuz.cmd` پر ڈبل کلک کریں۔
سب کچھ ریپوزٹری فولڈر کے اندر رہتا ہے (`.venv`، `runtime_assets/`)؛ ہر ڈاؤن لوڈ کا ورژن طے ہے اور
sha256 سے جانچا جاتا ہے۔ شروع کرنے کے لیے خالی جگہ: GPU پروفائل کے ساتھ 22 GB، صرف CPU کے ساتھ 14 GB؛ انسٹال کے بعد ناپا گیا استعمال ≈ 14.6 GB (GPU، ہارڈ لنک فائلیں ایک بار گنی گئیں؛ File Explorer ≈ 22 GB دکھاتا ہے)۔ جانچ: `.venv\Scripts\dubla.exe kontrol`۔

ضروریات، قدموں کی ترتیب، Python ماحول کا نقشہ، اختیاری انجن، آف لائن استعمال، اپ ڈیٹ، ان انسٹال اور
عام غلطیاں (انگریزی میں): **[docs/installation.md](docs/installation.md)**۔ Linux اور macOS ہم نے ابھی ٹیسٹ نہیں کیے۔ مثال: [Apple M4 والے Mac پر صرف CPU سے انگریزی، ترکی اور عربی میں ڈب کیا گیا پروڈکٹ ٹور](https://x.com/MihenkAIdotcom/status/2114345171571925363)۔

## استعمال کا طریقہ

ڈیسک ٹاپ ایپ: `arayuz.cmd` پر ڈبل کلک (لوکل ویب ایپ: `web.cmd`، صرف 127.0.0.1 پر)۔ ایپ کا انٹرفیس انگریزی اور ترکی میں ہے: زبان اوپر دائیں کونے سے چنیں (کمپیوٹر کسی اور زبان میں ہو تو ایپ انگریزی میں کھلتی ہے)۔ کمانڈ لائن سے:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

اردو میں ڈبنگ ابھی دستیاب نہیں، کیونکہ آواز انجن اردو نہیں پڑھتے؛ لیکن اردو ویڈیو کو مثلاً `--ayar genel.hedef_dil=en` سے انگریزی میں یا عام کمانڈ سے ترکی میں ڈب کیا جا سکتا ہے (اردو سے ترجمے کے لیے Codex یا Claude Code ضروری ہے)۔ نتائج `cikti/<video>_<time>/` میں جاتے ہیں: `dubbed_tr.mp4` (`AI-dubbed` ٹیگ کے ساتھ)، اصل سب ٹائٹل `transcript_<lang>.srt` اور کام کی JSON فائلیں؛ آخری لائن `dubbed_video:` راستہ بتاتی ہے۔ تمام سیٹنگز (انگریزی اور ترکی میں): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md)۔

## یہ کیسے کام کرتا ہے

1. **آڈیو:** FFmpeg آواز نکالتا ہے؛ اختیاری Demucs (MIT) بولی کو پس منظر سے الگ کرتا ہے۔
2. **بولی سے متن:** faster-whisper large-v3-turbo (MIT) اور wav2vec2 CTC سے الفاظ کا وقت (انگریزی MIT، ترکی CC BY 4.0)؛ اختیاری CrisperWhisper 2.0 (غیر تجارتی) اور دوسرے انجن۔
3. **بولنے والے:** 3D-Speaker CAM++ (Apache-2.0) اور جنس پہچاننے والا ایک ماڈل (Apache-2.0) ہر بولنے والے کے لیے ایک AI آواز چنتے ہیں۔
4. **ترجمہ:** اگر Codex CLI یا Claude Code CLI انسٹال اور لاگ اِن ہو تو وہی، ورنہ لوکل Opus-MT انگریزی سے ترکی (CC BY 4.0)؛ API بیک اینڈ اختیاری ہیں۔
5. **آواز اور ٹائمنگ:** ڈیفالٹ Supertonic 3 (OpenRAIL-M)، اختیاری VoxCPM2 (Apache-2.0) یا XTTS-v2 (غیر تجارتی)؛ ہر جملہ اصل حصے کے وقت کی طرف زیادہ سے زیادہ 1.25 گنا تیز ہوتا ہے اور باقی ویڈیو کے وقت سے پورا ہوتا ہے، اس لیے ڈب اصل سے لمبا ہو سکتا ہے۔
6. **ویڈیو:** FFmpeg نئی آواز، SRT / VTT / ASS سب ٹائٹل اور `AI-dubbed` ٹیگ لکھتا ہے۔

## پیمائش

حوالہ کمپیوٹر: 4 GB پاسکل GPU، Windows 10؛ طریقہ اور تمام قطاریں [docs/olcumler.md](docs/olcumler.md) میں۔

| کیا | CPU پروفائل | GPU پروفائل |
|---|---|---|
| پہلی انسٹالیشن، ڈیفالٹ قدم، شروع سے آخر تک | ≈ 38 منٹ | ≈ 44 منٹ (پیکیج 13.7 منٹ) |
| انسٹال کے بعد ڈسک | ≈ 13.2 GB (فولڈرز کا مجموعہ) | ≈ 14.6 GB (ہارڈ لنک ایک بار) |
| 9 سیکنڈ کا نمونہ ڈب، آف لائن ترجمہ | 528 سیکنڈ | 376 سیکنڈ |
| 30 سیکنڈ کی انگریزی کلپ، Demucs، Claude Code ترجمہ | – | 744 سیکنڈ |

## حدود

- CrisperWhisper (اختیاری انجن 13) کے بغیر faster-whisper چینی اور جاپانی میں بولی چھوڑ سکتا ہے یا ایسا متن گھڑ سکتا ہے جو کہا ہی نہیں گیا (دیکھا گیا: ایک چینی کلپ کے پہلے ≈ 10 سیکنڈ غائب ہو گئے؛ ایک چیخ لمبی "ああ…" لائن بن گئی)۔
- CI صرف CPU ٹیسٹ کرتا ہے؛ GPU راستہ 4 GB پاسکل کارڈ پر ہاتھ سے چلایا گیا۔ نئے کارڈ (RTX 50)، Linux اور macOS آزمائے نہیں گئے؛ انسٹال ہونے والی GPU لائبریریوں میں پاسکل سے RTX 50 تک کے کرنل ہیں، اور Maxwell CPU پروفائل استعمال کرتا ہے ([GPU سپورٹ ٹیبل، انگریزی میں](docs/installation.md#1-system-requirements))۔
- آف لائن مترجم صرف انگریزی سے ترکی کرتا ہے؛ دوسرے زبانوں کے جوڑوں کے لیے Codex / Claude Code CLI یا API بیک اینڈ چاہیے۔
- انگریزی اور ترکی کے علاوہ ماخذ زبانوں کے لیے الفاظ کا وقت: جاپانی اور چینی کے لیے `scripts/kur.ps1 -Adim hizalama-diller`، باقی کے لیے `DUBLAJ_CEVRIMICI=1` کے ساتھ ایک بار چلانے کے بعد۔
- ابھی شروع سے آخر تک نہیں آزمایا گیا: XTTS-v2 کی اصل انسٹالیشن، RVC اور اصل سروس سے جڑا Telegram بوٹ۔ CrisperWhisper 2.0 Turbo (انجن 13) اصل آڈیو کے ساتھ GTX 1050 Ti 4 GB پر آزمایا گیا ہے (tr، en، ja؛ ≈ 1.4 GB VRAM)۔

## بنیادی اینٹیں

ہر مرحلہ اکیلا بھی چلتا ہے، کمانڈ لائن سے یا Python سے، اور مراحل کے درمیان فائل فارمیٹ دستاویز میں لکھے ہیں
(مراحل کا نقشہ اور JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` یہی مراحل فنکشن کی شکل میں دیتا ہے۔ صرف وہی انسٹال کریں جو کسی مرحلے کو چاہیے، مثلاً
سب ٹائٹل کے لیے `pip install -e ".[stt,hizalama,cpu]"`۔ ان اینٹوں سے بنے پانچ چھوٹے ٹول: [examples/](examples/)۔

## خاندان / متعلقہ منصوبے

| ریپوزٹری | کیا ہے | یہ ریپوزٹری اسے کیسے استعمال کرتی ہے |
|---|---|---|
| **DubWorld** (یہی ریپوزٹری) | مکمل طور پر لوکل ویڈیو ڈبنگ پائپ لائن، ہر مرحلہ الگ سے بھی استعمال ہو سکتا ہے | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | لفظ بہ لفظ بولی سے متن، الفاظ کے وقت کے ساتھ (CrisperWhisper 2.0 Turbo + CTC الائنمنٹ) | اختیاری انجن 13: `scripts/kur.ps1 -Adim crisper` اس ریپوزٹری کے ذریعے طے شدہ commit پر ماڈل انسٹال کرتا ہے (ویٹ **غیر تجارتی**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | VoxCPM2 سے آواز کا ڈیزائن اور پڑھائی، 8 زبانیں، تیار آوازیں | اختیاری آواز انجن `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` طے شدہ commit پر انسٹال کرتا ہے؛ یہ ریپوزٹری اسے ایک پتلے اڈاپٹر سے بلاتی ہے |

ہر ساتھی ریپوزٹری کا اپنا لائسنس، انسٹالیشن اور issues ہیں؛ طے شدہ commit کی وجہ سے یہ جوڑ ہر بار اسی نتیجے کے ساتھ دوبارہ بنایا جا سکتا ہے۔

## ذمہ دارانہ استعمال

> **قانونی نوٹس۔** اس سافٹ ویئر سے آپ جو مواد پروسیس اور شائع کرتے ہیں، اور اپنے ملک کے قوانین اور جن سائٹس اور
> سروسز کو آپ استعمال کرتے ہیں ان کی شرائط کی پابندی، اس کی پوری ذمہ داری آپ کی ہے۔ سافٹ ویئر "جیسا ہے" کی بنیاد پر،
> بغیر کسی وارنٹی کے دیا جاتا ہے (Apache-2.0)۔ مکمل متن: [ETHICS.md](ETHICS.md)۔

- **حقوق اور رضامندی۔** صرف وہی مواد پروسیس کریں جو آپ کا ہو یا جس کے ترجمے اور دوبارہ ڈبنگ کا آپ کو حق ہو،
  اور اس میں پہچانے جا سکنے والے لوگوں سے رضامندی لیں۔
- **آوازیں۔** کسی کی نقل نہیں۔ حوالہ آواز صرف آپ کی اپنی ہو سکتی ہے یا اس شخص کی جس نے واضح اجازت دی ہو۔
- **لیبل لگائیں۔** آؤٹ پٹ میں `AI-dubbed` میٹا ڈیٹا ٹیگ ہوتا ہے؛ اسے رہنے دیں اور اپنے ناظرین کو نمایاں طور پر بتائیں
  کہ ڈبنگ AI سے کی گئی ہے (EU AI Act آرٹیکل 50؛ Supertonic لائسنس)۔
- **ڈاؤن لوڈ۔** اختیاری `youtube` (yt-dlp) اور `galeri` (gallery-dl) ایکسٹرا صرف اس مواد کے لیے ہیں جو آپ کا ہو یا جسے ڈاؤن لوڈ کرنے کا آپ کو حق ہو؛ سائٹ کی شرائط اور
  آپ کے مقامی قوانین لاگو ہوتے ہیں۔
- **غیر تجارتی انجن۔** CrisperWhisper 2.0 اور XTTS-v2 صرف غیر تجارتی استعمال کے لیے ہیں (ڈیفالٹ میں بند)۔ کسی بھی معاوضے والے یا کلائنٹ کے کام سے پہلے
  [THIRD_PARTY.md](THIRD_PARTY.md) کا **Commercial?** کالم دیکھیں۔
  fr / de / es / it ماخذ آڈیو کے الفاظ کے وقت کے ماڈل (CC BY-NC 4.0) بھی غیر تجارتی ہیں اور پہلی بار استعمال پر رضامندی مانگتے ہیں۔

## مدد اور سپورٹ

سوال، خیالات اور آپ کے نتائج: [بحث کا فورم](https://github.com/alexturkey/dubworld/discussions)۔ انسٹالیشن کا مسئلہ: [انسٹالیشن مسئلہ رپورٹ کریں](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml)؛ خرابیاں: [خرابی رپورٹ کریں](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(آپریٹنگ سسٹم، GPU، چلائی گئی کمانڈ اور آؤٹ پٹ کی آخری لائنیں لکھیں)۔ سیکیورٹی کے مسائل: SECURITY.md دیکھیں، عوامی issue میں نہ لکھیں۔

## لائسنس اور اعتراف

کوڈ: Apache-2.0 (LICENSE)۔ بیرونی حصے اور ان کے لائسنس: THIRD_PARTY.md۔ ذمہ دارانہ استعمال: ETHICS.md۔
رازداری (کیا آپ کے کمپیوٹر پر رہتا ہے، کلاؤڈ بیک اینڈ کو کیا ملتا ہے): PRIVACY.md۔ سیکیورٹی رپورٹ: SECURITY.md۔ تبدیلیاں: CHANGELOG.md۔

</div>

<!-- i18n-source: README.md sha256:cdd2c731c59f -->
