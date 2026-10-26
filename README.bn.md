# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · [ไทย](README.th.md) · বাংলা · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md) · [Azərbaycanca](README.az.md) · [Bahasa Melayu](README.ms.md)

> DubWorld আপনার ভিডিও আপনার নিজের কম্পিউটারেই অন্য ভাষায় ডাব করে, কোনো অনলাইন সেবায় আপলোড না করেই: কথাকে প্রতিটি শব্দের সময়সহ লেখায় রূপান্তর করে, অনুবাদ করে, তারপর একটি কৃত্রিম (AI) কণ্ঠ দিয়ে পড়ায় যা মূল ভিডিওর সঙ্গে তাল মিলিয়ে চলে (কথা সর্বোচ্চ ১.২৫ গুণ দ্রুত হয়, বাকি পার্থক্য ভিডিওর গতি সামান্য বদলে পূরণ হয়), সাবটাইটেল যোগ করে এবং নতুন একটি ভিডিও তৈরি করে। ডিফল্ট ভাষা তুর্কি। সত্যি কথা বলি: বাংলা **ভাষায়** ডাবিং এখনো সম্ভব নয়, কারণ এই রিপোজিটরির কোনো কণ্ঠ ইঞ্জিন এখনো বাংলা বলতে পারে না; তবে বাংলা ভিডিওকে অন্য ভাষায় ডাব করা যায় ([docs/diller.md](docs/diller.md))।

## আপনার AI সহকারীকে দিয়ে ইনস্টল করান

প্রোগ্রামিং জানার দরকার নেই। এমন একটি AI সহকারী খুলুন যে আপনার কম্পিউটারে কমান্ড চালাতে পারে (Claude Code, Codex,
Gemini CLI বা এ রকম কিছু) এবং শুধু এই বাক্যটি পেস্ট করুন:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

সহকারী আপনার কম্পিউটার (গ্রাফিক্স কার্ড, প্রসেসর, মেমরি, ডিস্ক) দেখে নেয় এবং মাত্র একবার, সহজ ভাষায়, জিজ্ঞেস করে আপনি কেমন
ইনস্টলেশন চান: দ্রুত, আপনার কম্পিউটারের জন্য প্রস্তাবিত, নাকি সম্পূর্ণ। প্রতিটি অংশের কথা বুঝিয়ে বলে (কী করে, কত জায়গা
নেয়, কত সময় লাগে, লাইসেন্স কী) এবং ডিফল্ট কণ্ঠ দিয়ে শুরু করে জিজ্ঞেস করে আপনি বেছে নেওয়া অংশগুলোর ব্যবহারের শর্ত মানেন কি না।
তারপর ইনস্টল করে, একটি নমুনা ডাব বানায় এবং প্রোগ্রামের উইন্ডো খুলে দেয়।
প্রথম ধাপ আর সাধারণ সমস্যা, সহজ ভাষায় (ইংরেজিতে): **[docs/getting-started.md](docs/getting-started.md)**।

**লাইসেন্স এক নজরে:** কোড Apache-2.0। ডিফল্ট মডেল: Supertonic 3 কণ্ঠ OpenRAIL-M-এর অধীনে (ব্যবহারের সীমাবদ্ধতা, একবার মেনে নিতে হয়); Opus-MT ও তুর্কি শব্দ-সময় মডেল CC BY 4.0-এর অধীনে (কৃতিত্ব দেওয়া বাধ্যতামূলক, NOTICE); FFmpeg বিল্ড GPL-3.0 (আলাদা প্রোগ্রাম)। শুধু অবাণিজ্যিক ব্যবহারের জন্য এবং ডিফল্টে বন্ধ: CrisperWhisper 2.0, XTTS-v2 এবং fr / de / es / it-এর জন্য WhisperX শব্দ-সময় মডেল। এই রিপোজিটরিতে কোনো মডেল ওয়েট নেই ([THIRD_PARTY.md](THIRD_PARTY.md))।

## দ্রুত ইনস্টলেশন

Windows 10/11 x64; আগে থেকে Python, CUDA বা ffmpeg লাগবে না। **`kur.cmd`**-এ ডাবল-ক্লিক করুন (অথবা চালান
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); GPU বা CPU প্রোফাইল নিজেই বেছে নেওয়া হয়
(`-Cpu` দিলে জোর করে CPU)। তারপর অ্যাপ খুলতে `arayuz.cmd`-এ ডাবল-ক্লিক করুন।
সবকিছু রিপোজিটরি ফোল্ডারের ভেতরেই থাকে (`.venv`, `runtime_assets/`); প্রতিটি ডাউনলোডের সংস্করণ নির্দিষ্ট এবং
sha256 দিয়ে যাচাই করা হয়। শুরু করতে খালি জায়গা: GPU প্রোফাইলে 22 GB, শুধু CPU-তে 14 GB; ইনস্টলের পর মাপা ব্যবহার ≈ 14.6 GB (GPU, হার্ড-লিংক ফাইল একবার গোনা; File Explorer ≈ 22 GB দেখায়)। যাচাই: `.venv\Scripts\dubla.exe kontrol`।

প্রয়োজনীয়তা, ধাপের ক্রম, Python পরিবেশের মানচিত্র, ঐচ্ছিক ইঞ্জিন, অফলাইন ব্যবহার, আপডেট, আনইনস্টল এবং
সাধারণ ত্রুটি (ইংরেজিতে): **[docs/installation.md](docs/installation.md)**। Linux আর macOS আমরা এখনো পরীক্ষা করিনি। উদাহরণ: [Apple M4 চিপের Mac-এ শুধু CPU দিয়ে ইংরেজি, তুর্কি ও আরবিতে ডাব করা পণ্য-পরিচিতি](https://x.com/MihenkAIdotcom/status/2114345171571925363)।

## ব্যবহারের নিয়ম

ডেস্কটপ অ্যাপ: `arayuz.cmd`-এ ডাবল-ক্লিক (লোকাল ওয়েব অ্যাপ: `web.cmd`, শুধু 127.0.0.1-এ)। অ্যাপের ইন্টারফেস ইংরেজি ও তুর্কিতে: ওপরে ডান দিক থেকে ভাষা বেছে নিন (কম্পিউটার অন্য ভাষায় থাকলে অ্যাপ ইংরেজিতে খোলে)। কমান্ড লাইন থেকে:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

বাংলায় ডাবিং এখনো পাওয়া যায় না, কারণ কণ্ঠ ইঞ্জিনগুলো বাংলা পড়তে পারে না; তবে বাংলা ভিডিওকে যেমন `--ayar genel.hedef_dil=en` দিয়ে ইংরেজিতে বা সাধারণ কমান্ডে তুর্কিতে ডাব করা যায় (বাংলা থেকে অনুবাদে Codex বা Claude Code লাগে)। ফলাফল যায় `cikti/<video>_<time>/`-এ: `dubbed_tr.mp4` (`AI-dubbed` ট্যাগসহ), মূল সাবটাইটেল `transcript_<lang>.srt` এবং কাজের JSON ফাইল; শেষ লাইন `dubbed_video:` পথ দেখায়। সব সেটিং (ইংরেজি ও তুর্কিতে): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md)।

## কীভাবে কাজ করে

1. **অডিও:** FFmpeg শব্দ বের করে; ঐচ্ছিক Demucs (MIT) কথাকে পটভূমি থেকে আলাদা করে।
2. **কথা থেকে লেখা:** faster-whisper large-v3-turbo (MIT) এবং wav2vec2 CTC থেকে শব্দ-সময় (ইংরেজি MIT, তুর্কি CC BY 4.0); ঐচ্ছিক CrisperWhisper 2.0 (অবাণিজ্যিক) ও অন্যান্য ইঞ্জিন।
3. **বক্তা:** 3D-Speaker CAM++ (Apache-2.0) এবং একটি লিঙ্গ-শনাক্তকরণ মডেল (Apache-2.0) প্রতিটি বক্তার জন্য একটি AI কণ্ঠ বেছে নেয়।
4. **অনুবাদ:** Codex CLI বা Claude Code CLI ইনস্টল ও লগ-ইন থাকলে সেটি, না হলে লোকাল Opus-MT ইংরেজি থেকে তুর্কি (CC BY 4.0); API ব্যাকএন্ড ঐচ্ছিক।
5. **কণ্ঠ ও সময়:** ডিফল্ট Supertonic 3 (OpenRAIL-M), ঐচ্ছিক VoxCPM2 (Apache-2.0) বা XTTS-v2 (অবাণিজ্যিক); প্রতিটি বাক্য মূল অংশের সময়ের দিকে সর্বোচ্চ ১.২৫ গুণ দ্রুত হয়, বাকিটা ভিডিওর সময় দিয়ে মেলানো হয়, তাই ডাব মূলের চেয়ে লম্বা হতে পারে।
6. **ভিডিও:** FFmpeg নতুন কণ্ঠ, SRT / VTT / ASS সাবটাইটেল এবং `AI-dubbed` ট্যাগ লেখে।

## পরিমাপ

রেফারেন্স কম্পিউটার: 4 GB Pascal GPU, Windows 10; পদ্ধতি ও সব সারি [docs/olcumler.md](docs/olcumler.md)-এ।

| কী | CPU প্রোফাইল | GPU প্রোফাইল |
|---|---|---|
| প্রথম ইনস্টলেশন, ডিফল্ট ধাপ, শুরু থেকে শেষ | ≈ 38 মিনিট | ≈ 44 মিনিট (প্যাকেজ 13.7 মিনিট) |
| ইনস্টলের পর ডিস্ক | ≈ 13.2 GB (ফোল্ডারের যোগফল) | ≈ 14.6 GB (হার্ড লিংক একবার) |
| 9 সেকেন্ডের নমুনা ডাব, অফলাইন অনুবাদ | 528 সেকেন্ড | 376 সেকেন্ড |
| 30 সেকেন্ডের ইংরেজি ক্লিপ, Demucs, Claude Code অনুবাদ | – | 744 সেকেন্ড |

## সীমাবদ্ধতা

- CrisperWhisper (ঐচ্ছিক ইঞ্জিন 13) ছাড়া faster-whisper চীনা ও জাপানিতে কথা বাদ দিতে পারে বা না-বলা লেখা বানিয়ে ফেলতে পারে (দেখা গেছে: একটি চীনা ক্লিপের প্রথম ≈ 10 সেকেন্ড হারিয়ে গেছে; একটি চিৎকার লম্বা "ああ…" লাইনে পরিণত হয়েছে)।
- CI শুধু CPU পরীক্ষা করে; GPU পথ হাতে চালানো হয়েছে একটি 4 GB Pascal কার্ডে। নতুন কার্ড (RTX 50), Linux ও macOS পরীক্ষিত নয়; ইনস্টল হওয়া GPU লাইব্রেরিতে Pascal থেকে RTX 50 পর্যন্ত কার্নেল আছে, আর Maxwell CPU প্রোফাইল ব্যবহার করে ([GPU সমর্থন তালিকা, ইংরেজিতে](docs/installation.md#1-system-requirements))।
- অফলাইন অনুবাদক শুধু ইংরেজি থেকে তুর্কি করে; অন্য ভাষা-জোড়ার জন্য Codex / Claude Code CLI বা API ব্যাকএন্ড লাগে।
- ইংরেজি ও তুর্কি ছাড়া অন্য উৎস-ভাষার শব্দ-সময়: জাপানি ও চীনা `scripts/kur.ps1 -Adim hizalama-diller` দিয়ে, বাকিগুলো `DUBLAJ_CEVRIMICI=1` দিয়ে একবার চালানোর পর।
- এখনো শুরু থেকে শেষ পর্যন্ত পরীক্ষা হয়নি: XTTS-v2-এর আসল ইনস্টলেশন, RVC এবং আসল সেবায় যুক্ত Telegram বট। CrisperWhisper 2.0 Turbo (ইঞ্জিন 13) আসল অডিও দিয়ে GTX 1050 Ti 4 GB-তে পরীক্ষা করা হয়েছে (tr, en, ja; ≈ 1.4 GB VRAM)।

## গঠনের খণ্ড

প্রতিটি ধাপ আলাদাভাবেও চলে, কমান্ড লাইন বা Python থেকে, এবং ধাপগুলোর মাঝের ফাইল ফরম্যাট নথিভুক্ত
(ধাপের মানচিত্র ও JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` একই ধাপগুলো ফাংশন হিসেবে দেয়। একটি ধাপের যা লাগে শুধু সেটুকু ইনস্টল করুন, যেমন
সাবটাইটেলের জন্য `pip install -e ".[stt,hizalama,cpu]"`। এই খণ্ড দিয়ে বানানো পাঁচটি ছোট টুল: [examples/](examples/)।

## পরিবার / সম্পর্কিত প্রকল্প

| রিপোজিটরি | কী | এই রিপোজিটরি কীভাবে ব্যবহার করে |
|---|---|---|
| **DubWorld** (এই রিপোজিটরি) | সম্পূর্ণ লোকাল ভিডিও ডাবিং পাইপলাইন, প্রতিটি ধাপ আলাদাভাবেও ব্যবহারযোগ্য | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | শব্দে শব্দে কথা থেকে লেখা, শব্দ-সময়সহ (CrisperWhisper 2.0 Turbo + CTC অ্যালাইনমেন্ট) | ঐচ্ছিক ইঞ্জিন 13: `scripts/kur.ps1 -Adim crisper` ওই রিপোজিটরির মাধ্যমে নির্দিষ্ট commit-এ মডেল ইনস্টল করে (ওয়েট **অবাণিজ্যিক**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | VoxCPM2 দিয়ে কণ্ঠ নকশা ও পাঠ, 8 ভাষা, তৈরি কণ্ঠ | ঐচ্ছিক কণ্ঠ ইঞ্জিন `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` নির্দিষ্ট commit-এ ইনস্টল করে; এই রিপোজিটরি একটি পাতলা অ্যাডাপ্টার দিয়ে সেটিকে ডাকে |

প্রতিটি সহযোগী রিপোজিটরির নিজস্ব লাইসেন্স, ইনস্টলেশন ও issue আছে; নির্দিষ্ট commit-এর কারণে এই জোড় প্রতিবার একই ফলাফলে আবার বানানো যায়।

## দায়িত্বশীল ব্যবহার

> **আইনি বিজ্ঞপ্তি।** এই সফটওয়্যার দিয়ে আপনি যে কনটেন্ট প্রক্রিয়া ও প্রকাশ করেন, এবং আপনার দেশের আইন ও যে সাইট আর
> সেবা ব্যবহার করেন তাদের শর্ত মেনে চলার পুরো দায়িত্ব আপনার। সফটওয়্যারটি "যেমন আছে" অবস্থায়, কোনো ওয়ারেন্টি ছাড়াই
> দেওয়া হয় (Apache-2.0)। পূর্ণ লেখা: [ETHICS.md](ETHICS.md)।

- **অধিকার ও সম্মতি।** শুধু সেই কনটেন্ট প্রক্রিয়া করুন যা আপনার, বা যা অনুবাদ ও নতুন করে ডাব করার অধিকার আপনার আছে,
  এবং তাতে চেনা যায় এমন মানুষদের সম্মতি নিন।
- **কণ্ঠ।** কারও নকল নয়। রেফারেন্স কণ্ঠ শুধু আপনার নিজের, বা এমন কারও হতে পারে যিনি স্পষ্ট অনুমতি দিয়েছেন।
- **চিহ্ন দিন।** আউটপুটে `AI-dubbed` মেটাডেটা ট্যাগ থাকে; সেটি রেখে দিন এবং দর্শকদের স্পষ্টভাবে জানান
  যে ডাবিং AI দিয়ে করা (EU AI Act অনুচ্ছেদ 50; Supertonic লাইসেন্স)।
- **ডাউনলোড।** ঐচ্ছিক `youtube` (yt-dlp) ও `galeri` (gallery-dl) এক্সট্রা শুধু আপনার নিজের বা ডাউনলোডের অধিকার আছে এমন কনটেন্টের জন্য; সাইটের শর্ত ও
  আপনার স্থানীয় আইন প্রযোজ্য।
- **অবাণিজ্যিক ইঞ্জিন।** CrisperWhisper 2.0 ও XTTS-v2 শুধু অবাণিজ্যিক ব্যবহারের জন্য (ডিফল্টে বন্ধ)। কোনো টাকার বা ক্লায়েন্টের কাজের আগে
  [THIRD_PARTY.md](THIRD_PARTY.md)-এর **Commercial?** কলাম দেখে নিন।
  fr / de / es / it উৎস-অডিওর শব্দ-সময় মডেল (CC BY-NC 4.0)-ও অবাণিজ্যিক এবং প্রথম ব্যবহারে সম্মতি চায়।

## সাহায্য ও সহায়তা

প্রশ্ন, ভাবনা আর আপনার ফলাফল: [আলোচনা ফোরাম](https://github.com/alexturkey/dubworld/discussions)। ইনস্টলেশনের সমস্যা: [ইনস্টলেশন সমস্যা জানান](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); বাগ: [বাগ রিপোর্ট করুন](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(অপারেটিং সিস্টেম, GPU, চালানো কমান্ড আর আউটপুটের শেষ কয়েক লাইন লিখুন)। নিরাপত্তা সমস্যা: SECURITY.md দেখুন, প্রকাশ্য issue-তে লিখবেন না।

## লাইসেন্স ও কৃতজ্ঞতা

কোড: Apache-2.0 (LICENSE)। বাইরের অংশ ও তাদের লাইসেন্স: THIRD_PARTY.md। দায়িত্বশীল ব্যবহার: ETHICS.md।
গোপনীয়তা (কী আপনার কম্পিউটারে থাকে, ক্লাউড ব্যাকএন্ড কী পায়): PRIVACY.md। নিরাপত্তা রিপোর্ট: SECURITY.md। পরিবর্তন: CHANGELOG.md।

<!-- i18n-source: README.md sha256:cdd2c731c59f -->
