# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · العربية · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md)

<div dir="rtl">

> يدبلج DubWorld الفيديو إلى لغة أخرى على حاسوبك أنت، دون رفعه إلى أي خدمة: يحوّل الكلام إلى نص ويعرف توقيت كل كلمة، ثم يترجمه، ثم ينطقه بصوت اصطناعي يبقى متزامناً مع الفيديو الأصلي (يُسرَّع الكلام بحدّ أقصى 1.25×، وما يتبقى من فرق تتكفّل به الصورة بإبطاء أو تسريع خفيف)، وفي النهاية ترجمة مكتوبة على الشاشة وفيديو جديد جاهز. اللغة الافتراضية هي التركية، والعربية واللغات الأخرى متاحة حسب محرك الصوت الذي تختاره ([docs/diller.md](docs/diller.md)).

## دع مساعد الذكاء الاصطناعي يثبّته لك

لا تحتاج إلى أي خبرة في البرمجة. افتح مساعد ذكاء اصطناعي يستطيع تشغيل الأوامر على حاسوبك (Claude Code أو Codex أو
Gemini CLI أو ما يشبهها) والصق هذه الجملة الواحدة:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

يقيس المساعد حاسوبك (بطاقة الرسوميات، المعالج، الذاكرة، القرص) ويسألك مرة واحدة وبكلمات بسيطة عن نوع التثبيت الذي
تريده: سريع، أو موصى به لحاسوبك، أو كامل. ويشرح كل جزء (ماذا يفعل، ومساحته على القرص، ومدته، وترخيصه) ويسألك هل
تقبل شروط استخدام الأجزاء التي تختارها، بدءاً بالصوت الافتراضي. ثم يثبّت البرنامج، وينفّذ دبلجة تجريبية، ويفتح نافذة
البرنامج. الخطوات الأولى والمشكلات الشائعة بلغة بسيطة (بالإنجليزية): **[docs/getting-started.md](docs/getting-started.md)**.

**ملخّص التراخيص:** الشيفرة Apache-2.0. النماذج الافتراضية: صوت Supertonic 3 بترخيص OpenRAIL-M (قيود استخدام، تُقبل مرة واحدة)؛ Opus-MT ونموذج توقيت الكلمات التركي بترخيص CC BY 4.0 (نسب الفضل، NOTICE)؛ نسخة FFmpeg بترخيص GPL-3.0 (برنامج منفصل). لغير الأغراض التجارية فقط ومعطّلة افتراضياً: CrisperWhisper 2.0 وXTTS-v2 ونماذج توقيت الكلمات WhisperX للغات fr / de / es / it. لا توجد أي أوزان نماذج في هذا المستودع ([THIRD_PARTY.md](THIRD_PARTY.md)).

## التثبيت السريع

Windows 10/11 x64؛ لا حاجة مسبقاً إلى Python أو CUDA أو ffmpeg. انقر نقراً مزدوجاً على **`kur.cmd`** (أو شغّل
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`)؛ فهو يختار ملف تعريف GPU أو CPU بنفسه
(`-Cpu` يفرض CPU). ثم انقر نقراً مزدوجاً على `arayuz.cmd` لفتح التطبيق.
كل شيء يُثبَّت داخل مجلد المستودع (`.venv`، `runtime_assets/`)؛ وكل تنزيل مثبّت الإصدار ويُتحقق منه عبر
sha256. المساحة الحرة اللازمة للبدء: 22 GB مع ملف تعريف GPU، و14 GB مع CPU فقط؛ الاستخدام المقاس بعد التثبيت ≈ 14.6 GB (GPU، الملفات المرتبطة ارتباطاً صلباً تُحسب مرة واحدة؛ مستكشف الملفات يُظهر ≈ 22 GB). تحقّق بالأمر `.venv\Scripts\dubla.exe kontrol`.

المتطلبات، وترتيب الخطوات، وخريطة بيئات Python، والمحركات الاختيارية، والاستخدام دون اتصال، والتحديث، وإلغاء التثبيت،
والأخطاء الشائعة (بالإنجليزية): **[docs/installation.md](docs/installation.md)**. لم يُختبر Linux وmacOS بعد. مثال: [جولة تعريفية بمنتج بصوت إنجليزي وتركي وعربي على Apple M4 Mac، باستخدام CPU فقط](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## الاستخدام

تطبيق سطح المكتب: انقر نقراً مزدوجاً على `arayuz.cmd` (تطبيق الويب المحلي: `web.cmd`، على 127.0.0.1 فقط). واجهة التطبيق بالتركية حالياً، ويمكنك اختيار العربية لغةً للدبلجة (`--ayar genel.hedef_dil=ar`؛ تحتاج الترجمة إلى العربية إلى Codex أو Claude Code). من سطر الأوامر:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

تذهب النتائج إلى `cikti/<video>_<time>/`: الملف `dubbed_tr.mp4` (موسوم بـ `AI-dubbed`)، وترجمة المصدر النصية `transcript_<lang>.srt` وملفات JSON الخاصة بالمهمة؛ ويطبع السطر الأخير `dubbed_video:` المسار. كل الإعدادات (بالإنجليزية والتركية): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## كيف يعمل

1. **الصوت:** يستخرج FFmpeg الصوت؛ ويفصل Demucs (MIT) الاختياري الكلام عن الخلفية.
2. **تحويل الكلام إلى نص:** faster-whisper large-v3-turbo (MIT) مع توقيت الكلمات wav2vec2 CTC (الإنجليزية MIT، التركية CC BY 4.0)؛ واختيارياً CrisperWhisper 2.0 (غير تجاري) ومحركات أخرى.
3. **المتحدثون:** يختار 3D-Speaker CAM++ (Apache-2.0) ومصنّف للجنس (Apache-2.0) صوتاً اصطناعياً لكل متحدث.
4. **الترجمة:** Codex CLI أو Claude Code CLI عند تثبيتهما وتسجيل الدخول، وإلا فـ Opus-MT المحلي من الإنجليزية إلى التركية (CC BY 4.0)؛ واجهات API اختيارية.
5. **الصوت والتوقيت:** Supertonic 3 (OpenRAIL-M) افتراضياً، وVoxCPM2 (Apache-2.0) أو XTTS-v2 (غير تجاري) اختيارياً؛ تُسرَّع كل جملة بحدّ أقصى 1.25× نحو مدة المقطع الأصلي ويُعاد توقيت الفيديو للباقي، لذا قد تكون الدبلجة أطول من المصدر.
6. **الفيديو:** يكتب FFmpeg الصوت الجديد، والترجمات النصية SRT / VTT / ASS، ووسم `AI-dubbed`.

## القياسات

الجهاز المرجعي: بطاقة Pascal بذاكرة 4 GB، Windows 10؛ الطريقة وكل الصفوف في [docs/olcumler.md](docs/olcumler.md).

| ماذا | ملف تعريف CPU | ملف تعريف GPU |
|---|---|---|
| التثبيت الأول، الخطوات الافتراضية، من البداية إلى النهاية | ≈ 38 دقيقة | ≈ 44 دقيقة (الحزم 13.7 دقيقة) |
| القرص بعد التثبيت | ≈ 13.2 GB (مجموع المجلد) | ≈ 14.6 GB (الروابط الصلبة تُحسب مرة واحدة) |
| دبلجة تجريبية مدتها 9 ثوانٍ، ترجمة دون اتصال | 528 ث | 376 ث |
| مقطع إنجليزي مدته 30 ثانية، Demucs، ترجمة Claude Code | – | 744 ث |

## الحدود

- بدون CrisperWhisper (المحرك الاختياري 13)، قد يتخطى faster-whisper الكلام أو يختلق نصاً في الصينية واليابانية (لوحظ: تُخطّيت أول ≈ 10 ثوانٍ من مقطع صيني؛ وتحوّل الصراخ إلى سطر طويل "ああ…").
- يختبر التكامل المستمر (CI) المعالج فقط؛ شُغّل مسار GPU يدوياً على بطاقة Pascal واحدة بذاكرة 4 GB. لم تُجرَّب البطاقات الأحدث (RTX 50) ولا Linux ولا macOS؛ مكتبات GPU المثبّتة تحمل نوى من Pascal إلى RTX 50، وMaxwell يستخدم ملف تعريف CPU ([جدول دعم بطاقات الرسوميات، بالإنجليزية](docs/installation.md#1-system-requirements)).
- المترجم دون اتصال يترجم من الإنجليزية إلى التركية فقط؛ الأزواج الأخرى تحتاج Codex / Claude Code CLI أو واجهة API.
- توقيت الكلمات للغات مصدر غير الإنجليزية والتركية: اليابانية والصينية عبر `scripts/kur.ps1 -Adim hizalama-diller`، والأخرى بعد تشغيل واحد مع `DUBLAJ_CEVRIMICI=1`.
- لم يُجرَّب من البداية إلى النهاية: التثبيت الفعلي لـ XTTS-v2، وRVC، وبوت Telegram مع الخدمة الحقيقية، وCrisperWhisper 2 Medium؛ وMoonshine تجريبي. اختُبر CrisperWhisper 2.0 Turbo (المحرك 13) على صوت حقيقي ببطاقة GTX 1050 Ti 4 GB (tr، en، ja؛ ≈ 1.4 GB VRAM).

## اللبنات الأساسية

كل مرحلة تعمل وحدها، من سطر الأوامر أو من Python، مع صيغ ملفات موثّقة بين المراحل
(خريطة المراحل ومخططات JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

يوفّر `from dublaj_hatti import api` المراحل نفسها على شكل دوال. ثبّت فقط ما تحتاجه المرحلة، مثلاً
`pip install -e ".[stt,hizalama,cpu]"` للترجمات النصية. خمس أدوات صغيرة مبنية من هذه اللبنات: [examples/](examples/).

## العائلة / مشاريع ذات صلة

| المستودع | ما هو | كيف يستخدمه هذا المستودع |
|---|---|---|
| **DubWorld** (هذا المستودع) | خط دبلجة فيديو محلي متكامل، كل مرحلة قابلة للاستخدام وحدها | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | تحويل الكلام إلى نص حرفياً مع توقيت الكلمات (CrisperWhisper 2.0 Turbo + محاذاة CTC) | المحرك الاختياري 13: يثبّت `scripts/kur.ps1 -Adim crisper` نموذجه عبر ذلك المستودع عند commit مثبّت (الأوزان **غير تجارية**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | تصميم الأصوات والقراءة بـ VoxCPM2، 8 لغات، أصوات جاهزة | محرك الصوت الاختياري `voxcpm2`: يثبّته `scripts/kur.ps1 -Adim voxcpm2` عند commit مثبّت؛ ويستدعيه هذا المستودع عبر مُحوِّل رفيع |

يحتفظ كل مستودع شقيق بترخيصه وتثبيته وقضاياه الخاصة؛ والـ commits المثبّتة تجعل هذا التجميع قابلاً لإعادة الإنتاج.

## الاستخدام المسؤول

> **إخلاء مسؤولية قانوني.** أنت وحدك المسؤول عن المحتوى الذي تعالجه وتنشره بهذا البرنامج وعن الالتزام
> بقوانين بلدك وشروط المواقع والخدمات التي تستخدمها. يُقدَّم البرنامج "كما هو"، دون أي ضمان
> (Apache-2.0). النص الكامل: [ETHICS.md](ETHICS.md).

- **الحقوق والموافقة.** عالج فقط المواد التي تملكها أو لديك إذن بترجمتها وإعادة تسجيل صوتها، واحصل على
  موافقة الأشخاص الذين يمكن التعرف عليهم فيها.
- **الأصوات.** لا انتحال للشخصيات. لا يجوز أن يكون الصوت المرجعي إلا صوتك أو صوت شخص أعطى موافقة صريحة.
- **ضع العلامة.** تحمل المخرجات وسم البيانات الوصفية `AI-dubbed`؛ احتفظ به وأفصح أيضاً لجمهورك بوضوح عن أن
  الدبلجة تمت بالذكاء الاصطناعي (قانون الذكاء الاصطناعي الأوروبي، المادة 50؛ ترخيص Supertonic).
- **التنزيل.** الإضافات الاختيارية `youtube` (yt-dlp) و`galeri` (gallery-dl) مخصّصة للمحتوى الذي تملكه أو يحق لك تنزيله؛ وتنطبق شروط المواقع
  وقانونك المحلي.
- **المحركات غير التجارية.** CrisperWhisper 2.0 وXTTS-v2 لغير الأغراض التجارية فقط (معطّلة افتراضياً). راجع
  عمود **Commercial?** في [THIRD_PARTY.md](THIRD_PARTY.md) قبل أي عمل مدفوع أو لعميل.
  نماذج توقيت الكلمات لصوت المصدر بلغات fr / de / es / it (CC BY-NC 4.0) غير تجارية أيضاً وتطلب الموافقة عند أول استخدام.

## المساعدة والدعم

للأسئلة والأفكار ومشاركة نتائجك: [صفحة النقاشات](https://github.com/alexturkey/dubworld/discussions). مشكلات التثبيت: [أبلغ عن مشكلة تثبيت](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml)؛ الأخطاء: [أبلغ عن خطأ](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(أضف نظام التشغيل، وبطاقة الرسوميات، والأمر، وآخر أسطر مخرجاته). المشكلات الأمنية: SECURITY.md، وليس عبر القضايا العامة.

## الترخيص والشكر

الشيفرة: Apache-2.0 (LICENSE). المكونات الخارجية وتراخيصها: THIRD_PARTY.md. الاستخدام المسؤول: ETHICS.md.
الخصوصية (ما يبقى محلياً، وما تتلقاه واجهة سحابية): PRIVACY.md. تقارير الأمان: SECURITY.md. التغييرات: CHANGELOG.md.

</div>

<!-- i18n-source: README.md sha256:9622edb95c84 -->
