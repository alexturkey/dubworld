# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · עברית · [ไทย](README.th.md) · [বাংলা](README.bn.md) · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md) · [Azərbaycanca](README.az.md) · [Bahasa Melayu](README.ms.md)

<div dir="rtl">

> DubWorld מדבב את הסרטונים שלכם לשפה אחרת ישירות על המחשב שלכם, בלי להעלות אותם לשום שירות מקוון: הוא הופך דיבור לטקסט יחד עם הזמן של כל מילה, מתרגם אותו ומקריא אותו בקול מלאכותי (AI) שנשאר מתוזמן עם הסרטון המקורי (הדיבור מואץ לכל היותר פי 1.25, ואת שאר ההפרש סופג שינוי עדין בקצב הווידאו), מוסיף כתוביות ויוצר סרטון חדש. שפת ברירת המחדל היא טורקית. בכנות: דיבוב **לעברית** עדיין לא אפשרי, כי אף אחד ממנועי הקול במאגר הזה לא מדבר עברית כרגע; אבל סרטונים בעברית אפשר לדבב לשפות אחרות ([docs/diller.md](docs/diller.md)).

## תנו לעוזר ה-AI שלכם להתקין

לא צריך לדעת לתכנת. פתחו עוזר AI שיכול להריץ פקודות על המחשב שלכם (Claude Code, Codex,
Gemini CLI או דומה) והדביקו את המשפט האחד הזה:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

העוזר בודק את המחשב (כרטיס מסך, מעבד, זיכרון, דיסק) ושואל רק פעם אחת, בשפה פשוטה, איזו התקנה אתם רוצים: מהירה,
מומלצת למחשב שלכם או מלאה. הוא מסביר כל רכיב (מה הוא עושה, כמה מקום הוא תופס, כמה זמן ההתקנה לוקחת, מה הרישיון שלו),
ומתחיל מהקול של ברירת המחדל ושואל אם אתם מקבלים את תנאי השימוש של הרכיבים שבחרתם. אחר כך הוא מתקין, מכין דיבוב לדוגמה
ופותח את חלון התוכנה.
צעדים ראשונים ותקלות נפוצות, בשפה פשוטה (באנגלית): **[docs/getting-started.md](docs/getting-started.md)**.

**רישיונות במבט אחד:** הקוד Apache-2.0. מודלים כברירת מחדל: הקול Supertonic 3 תחת OpenRAIL-M (הגבלות שימוש, מאשרים פעם אחת); Opus-MT ומודל זמני המילים הטורקי תחת CC BY 4.0 (חובת ייחוס, NOTICE); בניית FFmpeg ב-GPL-3.0 (תוכנה נפרדת). רק לשימוש לא מסחרי וכבויים כברירת מחדל: CrisperWhisper 2.0, XTTS-v2 ומודלי זמני המילים של WhisperX ל-fr / de / es / it. המאגר לא מכיל אף משקל מודל ([THIRD_PARTY.md](THIRD_PARTY.md)).

## התקנה מהירה

Windows 10/11 x64; לא צריך Python, CUDA או ffmpeg מותקנים מראש. לחצו פעמיים על **`kur.cmd`** (או הריצו
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); פרופיל GPU או CPU נבחר לבד
(`-Cpu` מכריח CPU). אחר כך לחצו פעמיים על `arayuz.cmd` כדי לפתוח את התוכנה.
הכול נשאר בתוך תיקיית המאגר (`.venv`, `runtime_assets/`); לכל הורדה יש גרסה נעולה והיא
נבדקת ב-sha256. מקום פנוי להתחלה: 22 GB עם פרופיל GPU, 14 GB עם CPU בלבד; שימוש שנמדד אחרי ההתקנה ≈ 14.6 GB (GPU, קבצים עם hard link נספרו פעם אחת; סייר הקבצים מציג ≈ 22 GB). בדיקה: `.venv\Scripts\dubla.exe kontrol`.

דרישות, סדר השלבים, מפת סביבות Python, מנועים אופציונליים, עבודה בלי אינטרנט, עדכון, הסרה ו
שגיאות נפוצות (באנגלית): **[docs/installation.md](docs/installation.md)**. על Linux ו-macOS עוד לא בדקנו. דוגמה: [סיור מוצר שדובב לאנגלית, טורקית וערבית על Mac עם Apple M4, רק עם CPU](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## איך משתמשים

אפליקציה לשולחן העבודה: לחיצה כפולה על `arayuz.cmd` (אפליקציית ווב מקומית: `web.cmd`, רק על 127.0.0.1). הממשק זמין באנגלית ובטורקית: בוחרים שפה בפינה הימנית העליונה (אם המחשב בשפה אחרת, הוא נפתח באנגלית). משורת הפקודה:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

דיבוב לעברית עדיין לא זמין, כי מנועי הקול לא קוראים עברית; אבל סרטון בעברית אפשר לדבב, למשל, לאנגלית עם `--ayar genel.hedef_dil=en` או לטורקית עם הפקודה הרגילה (תרגום מעברית דורש Codex או Claude Code). התוצאות נשמרות ב-`cikti/<video>_<time>/`: `dubbed_tr.mp4` (עם התג `AI-dubbed`), הכתוביות המקוריות `transcript_<lang>.srt` וקובצי העבודה ב-JSON; השורה האחרונה `dubbed_video:` מראה את הנתיב. כל ההגדרות (באנגלית ובטורקית): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## איך זה עובד

1. **שמע:** FFmpeg מחלץ את הקול; Demucs (MIT) האופציונלי מפריד דיבור מרקע.
2. **דיבור לטקסט:** faster-whisper large-v3-turbo (MIT) עם זמני מילים מ-wav2vec2 CTC (אנגלית MIT, טורקית CC BY 4.0); CrisperWhisper 2.0 אופציונלי (לא מסחרי) ומנועים נוספים.
3. **דוברים:** 3D-Speaker CAM++ (Apache-2.0) ומודל לזיהוי מגדר (Apache-2.0) בוחרים קול AI אחד לכל דובר.
4. **תרגום:** Codex CLI או Claude Code CLI אם הם מותקנים ומחוברים, אחרת Opus-MT מקומי מאנגלית לטורקית (CC BY 4.0); ממשקי API הם אופציונליים.
5. **קול ותזמון:** ברירת מחדל Supertonic 3 (OpenRAIL-M), אופציונלי VoxCPM2 (Apache-2.0) או XTTS-v2 (לא מסחרי); כל משפט מואץ לכל היותר פי 1.25 לעבר אורך הקטע המקורי, ואת השאר מכסה זמן הווידאו, כך שהדיבוב יכול לצאת ארוך מהמקור.
6. **וידאו:** FFmpeg כותב את הקול החדש, כתוביות SRT / VTT / ASS והתג `AI-dubbed`.

## מדידות

מחשב ייחוס: GPU פסקל 4 GB, Windows 10; השיטה וכל השורות ב-[docs/olcumler.md](docs/olcumler.md).

| מה | פרופיל CPU | פרופיל GPU |
|---|---|---|
| התקנה ראשונה, שלבי ברירת מחדל, מההתחלה עד הסוף | ≈ 38 דק' | ≈ 44 דק' (חבילות 13.7 דק') |
| דיסק אחרי ההתקנה | ≈ 13.2 GB (סכום תיקיות) | ≈ 14.6 GB (hard links פעם אחת) |
| דיבוב לדוגמה של 9 שנ', תרגום בלי אינטרנט | 528 שנ' | 376 שנ' |
| קליפ באנגלית של 30 שנ', Demucs, תרגום Claude Code | – | 744 שנ' |

## מגבלות

- בלי CrisperWhisper (מנוע אופציונלי 13), faster-whisper עלול בסינית וביפנית לדלג על דיבור או להמציא טקסט שלא נאמר (נצפה: אבדו ≈ 10 השניות הראשונות של קליפ בסינית; צעקה הפכה לשורה ארוכה "ああ…").
- ה-CI בודק רק CPU; מסלול ה-GPU הורץ ידנית על כרטיס פסקל 4 GB. כרטיסים חדשים (RTX 50), Linux ו-macOS לא נבדקו; ספריות ה-GPU המותקנות כוללות קרנלים מפסקל עד RTX 50, ו-Maxwell משתמש בפרופיל CPU ([טבלת תמיכת GPU, באנגלית](docs/installation.md#1-system-requirements)).
- המתרגם הלא-מקוון יודע רק אנגלית לטורקית; צמדי שפות אחרים דורשים Codex / Claude Code CLI או ממשק API.
- זמני מילים לשפות מקור מלבד אנגלית וטורקית: יפנית וסינית דרך `scripts/kur.ps1 -Adim hizalama-diller`, האחרות אחרי הרצה אחת עם `DUBLAJ_CEVRIMICI=1`.
- עוד לא נבדק מההתחלה עד הסוף: התקנה אמיתית של XTTS-v2, RVC, בוט טלגרם מחובר לשירות אמיתי ו-CrisperWhisper 2 Medium; Moonshine ניסיוני. CrisperWhisper 2.0 Turbo (מנוע 13) נבדק עם שמע אמיתי על GTX 1050 Ti 4 GB (tr, en, ja; ≈ 1.4 GB VRAM).

## אבני בניין

כל שלב רץ גם לבד, משורת הפקודה או מ-Python, ותבניות הקבצים בין השלבים מתועדות
(מפת שלבים ו-JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` מספק את אותם שלבים כפונקציות. התקינו רק את מה ששלב מסוים צריך, למשל
`pip install -e ".[stt,hizalama,cpu]"` לכתוביות. חמישה כלים קטנים שנבנו מאבני הבניין האלה: [examples/](examples/).

## משפחה / פרויקטים קשורים

| מאגר | מה זה | איך המאגר הזה משתמש בו |
|---|---|---|
| **DubWorld** (המאגר הזה) | שרשרת דיבוב וידאו מקומית לגמרי, כל שלב שמיש גם בנפרד | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | המרת דיבור לטקסט מילה במילה עם זמני מילים (CrisperWhisper 2.0 Turbo + יישור CTC) | מנוע אופציונלי 13: `scripts/kur.ps1 -Adim crisper` מתקין את המודל דרך המאגר ההוא ב-commit נעול (משקלים **לא מסחריים**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | עיצוב קול והקראה עם VoxCPM2, 8 שפות, קולות מוכנים | מנוע קול אופציונלי `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` מתקין ב-commit נעול; המאגר הזה קורא לו דרך מתאם דק |

לכל מאגר אח יש רישיון, התקנה ו-issues משלו; בזכות ה-commit הנעול אפשר לבנות את השילוב מחדש עם אותה תוצאה.

## שימוש אחראי

> **הודעה משפטית.** האחריות המלאה לתוכן שאתם מעבדים ומפרסמים עם התוכנה הזו, ולעמידה בחוקי המדינה שלכם ובתנאי האתרים
> והשירותים שבהם אתם משתמשים, היא שלכם. התוכנה ניתנת "כמות שהיא", בלי שום אחריות (Apache-2.0). הנוסח המלא:
> [ETHICS.md](ETHICS.md).

- **זכויות והסכמה.** עבדו רק תוכן ששייך לכם או שיש לכם זכות לתרגם ולדבב מחדש,
  ובקשו הסכמה מאנשים שאפשר לזהות בו.
- **קולות.** בלי התחזות לאף אחד. קול ייחוס יכול להיות רק שלכם או של מי שנתן הסכמה ברורה.
- **סמנו.** בתוצר יש תג מטא-דאטה `AI-dubbed`; השאירו אותו, וספרו לצופים באופן גלוי
  שהדיבוב נעשה עם AI (סעיף 50 לחוק ה-AI של האיחוד האירופי; רישיון Supertonic).
- **הורדות.** התוספים האופציונליים `youtube` (yt-dlp) ו-`galeri` (gallery-dl) מיועדים רק לתוכן ששייך לכם או שמותר לכם להוריד; תנאי האתר ו
  החוק המקומי שלכם חלים.
- **מנועים לא מסחריים.** CrisperWhisper 2.0 ו-XTTS-v2 מיועדים לשימוש לא מסחרי בלבד (כבויים כברירת מחדל). לפני עבודה בתשלום או עבור לקוח,
  בדקו את העמודה **Commercial?** ב-[THIRD_PARTY.md](THIRD_PARTY.md).
  גם מודלי זמני המילים לשמע מקור ב-fr / de / es / it (CC BY-NC 4.0) הם לא מסחריים ומבקשים הסכמה בשימוש הראשון.

## עזרה ותמיכה

שאלות, רעיונות והתוצאות שלכם: [פורום הדיונים](https://github.com/alexturkey/dubworld/discussions). בעיה בהתקנה: [דיווח על בעיית התקנה](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); באגים: [דיווח על באג](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(כתבו מערכת הפעלה, GPU, הפקודה שהרצתם והשורות האחרונות של הפלט). בעיות אבטחה: ראו SECURITY.md, לא ב-issue ציבורי.

## רישיון וקרדיטים

קוד: Apache-2.0 (LICENSE). רכיבי צד שלישי ורישיונותיהם: THIRD_PARTY.md. שימוש אחראי: ETHICS.md.
פרטיות (מה נשאר על המחשב שלכם, מה מקבל שרת בענן): PRIVACY.md. דיווחי אבטחה: SECURITY.md. שינויים: CHANGELOG.md.

</div>

<!-- i18n-source: README.md sha256:bb424df69aff -->
