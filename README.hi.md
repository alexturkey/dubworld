# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · हिन्दी · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md)

> DubWorld आपके वीडियो को आपके अपने कंप्यूटर पर, किसी ऑनलाइन सेवा पर अपलोड किए बिना, दूसरी भाषा में डब करता है: बोली को हर शब्द के समय के साथ टेक्स्ट में बदलता है, उसका अनुवाद करता है, फिर एक कृत्रिम (AI) आवाज़ से बुलवाता है जो मूल वीडियो के साथ तालमेल में रहती है (बोली ज़्यादा से ज़्यादा 1.25 गुना तेज़ होती है, बाकी अंतर वीडियो की रफ़्तार हल्का-सा बदलकर पूरा होता है), सबटाइटल जोड़ता है और एक नया वीडियो तैयार करता है। डिफ़ॉल्ट भाषा तुर्की है; हिंदी और दूसरी भाषाएँ चुने गए आवाज़ इंजन पर निर्भर करती हैं ([docs/diller.md](docs/diller.md))।

## अपने AI असिस्टेंट से इंस्टॉल करवाइए

प्रोग्रामिंग आना ज़रूरी नहीं। कोई ऐसा AI असिस्टेंट खोलिए जो आपके कंप्यूटर पर कमांड चला सके (Claude Code, Codex,
Gemini CLI या ऐसा ही कोई) और यह एक वाक्य पेस्ट कर दीजिए:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

असिस्टेंट आपके कंप्यूटर (ग्राफ़िक्स कार्ड, प्रोसेसर, मेमोरी, डिस्क) की जाँच करता है और आसान शब्दों में सिर्फ़ एक बार पूछता
है कि आपको कैसा इंस्टॉलेशन चाहिए: तेज़, आपके कंप्यूटर के हिसाब से सुझाया गया, या पूरा। वह हर हिस्से के बारे में बताता है
(क्या करता है, डिस्क पर कितनी जगह लेता है, कितना समय लगता है, उसका लाइसेंस क्या है) और डिफ़ॉल्ट आवाज़ से शुरू करके पूछता
है कि क्या आप चुने गए हिस्सों की उपयोग-शर्तें मानते हैं। फिर इंस्टॉल करता है, एक सैंपल डब बनाता है और प्रोग्राम की विंडो खोल
देता है। शुरुआती कदम और आम दिक्कतें, आसान भाषा में (अंग्रेज़ी में): **[docs/getting-started.md](docs/getting-started.md)**।

**लाइसेंस एक नज़र में:** कोड Apache-2.0। डिफ़ॉल्ट मॉडल: Supertonic 3 आवाज़ OpenRAIL-M के तहत (उपयोग की पाबंदियाँ, एक बार स्वीकार करनी होती हैं); Opus-MT और तुर्की शब्द-समय मॉडल CC BY 4.0 के तहत (श्रेय देना ज़रूरी, NOTICE); FFmpeg बिल्ड GPL-3.0 (अलग प्रोग्राम)। सिर्फ़ गैर-व्यावसायिक उपयोग के लिए और डिफ़ॉल्ट रूप से बंद: CrisperWhisper 2.0, XTTS-v2, और fr / de / es / it के लिए WhisperX शब्द-समय मॉडल। इस रिपॉज़िटरी में कोई भी मॉडल वेट नहीं है ([THIRD_PARTY.md](THIRD_PARTY.md))।

## झटपट इंस्टॉलेशन

Windows 10/11 x64; पहले से Python, CUDA या ffmpeg की ज़रूरत नहीं। **`kur.cmd`** पर डबल-क्लिक कीजिए (या
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1` चलाइए); यह खुद GPU या CPU प्रोफ़ाइल चुन लेता है
(`-Cpu` से CPU ज़बरदस्ती चुना जाता है)। फिर ऐप खोलने के लिए `arayuz.cmd` पर डबल-क्लिक कीजिए।
सब कुछ रिपॉज़िटरी फ़ोल्डर के अंदर ही रहता है (`.venv`, `runtime_assets/`); हर डाउनलोड का वर्ज़न तय है और
sha256 से जाँचा जाता है। शुरू करने के लिए खाली जगह: GPU प्रोफ़ाइल के साथ 22 GB, सिर्फ़ CPU के साथ 14 GB; इंस्टॉल के बाद मापा गया उपयोग ≈ 14.6 GB (GPU, हार्ड-लिंक वाली फ़ाइलें एक बार गिनी गईं; फ़ाइल एक्सप्लोरर ≈ 22 GB दिखाता है)। जाँचने के लिए: `.venv\Scripts\dubla.exe kontrol`।

ज़रूरतें, कदमों का क्रम, Python एनवायरनमेंट का नक्शा, वैकल्पिक इंजन, ऑफ़लाइन उपयोग, अपडेट, अनइंस्टॉल और
आम एरर (अंग्रेज़ी में): **[docs/installation.md](docs/installation.md)**। Linux और macOS को हमने अभी तक टेस्ट नहीं किया है। उदाहरण: [Apple M4 Mac पर सिर्फ़ CPU से अंग्रेज़ी, तुर्की और अरबी में आवाज़ दिया गया प्रोडक्ट टूर](https://x.com/MihenkAIdotcom/status/2114345171571925363)।

## इस्तेमाल कैसे करें

डेस्कटॉप ऐप: `arayuz.cmd` पर डबल-क्लिक (लोकल वेब ऐप: `web.cmd`, सिर्फ़ 127.0.0.1 पर)। अभी ऐप का इंटरफ़ेस तुर्की में है। कमांड लाइन से:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

हिंदी में डब करने के लिए `--ayar genel.hedef_dil=hi` इस्तेमाल कीजिए (हिंदी अनुवाद के लिए Codex या Claude Code ज़रूरी है)। नतीजे `cikti/<video>_<time>/` में जाते हैं: `dubbed_tr.mp4` (`AI-dubbed` टैग के साथ), मूल सबटाइटल `transcript_<lang>.srt` और काम की JSON फ़ाइलें; आख़िरी लाइन `dubbed_video:` रास्ता बताती है। सारी सेटिंग्स (अंग्रेज़ी और तुर्की में): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md)।

## यह कैसे काम करता है

1. **ऑडियो:** FFmpeg आवाज़ निकालता है; वैकल्पिक Demucs (MIT) बोली को बैकग्राउंड से अलग करता है।
2. **बोली से टेक्स्ट:** faster-whisper large-v3-turbo (MIT) और wav2vec2 CTC से शब्द-समय (अंग्रेज़ी MIT, तुर्की CC BY 4.0); वैकल्पिक CrisperWhisper 2.0 (गैर-व्यावसायिक) और दूसरे इंजन।
3. **बोलने वाले:** 3D-Speaker CAM++ (Apache-2.0) और एक लिंग-पहचान मॉडल (Apache-2.0) हर बोलने वाले के लिए एक AI आवाज़ चुनते हैं।
4. **अनुवाद:** अगर Codex CLI या Claude Code CLI इंस्टॉल और लॉग-इन है तो वही, वरना लोकल Opus-MT से अंग्रेज़ी से तुर्की (CC BY 4.0); API बैकएंड वैकल्पिक हैं।
5. **आवाज़ और टाइमिंग:** डिफ़ॉल्ट Supertonic 3 (OpenRAIL-M), वैकल्पिक VoxCPM2 (Apache-2.0) या XTTS-v2 (गैर-व्यावसायिक); हर लाइन मूल हिस्से के समय की ओर ज़्यादा से ज़्यादा 1.25 गुना तेज़ होती है और बाकी के लिए वीडियो का समय बदला जाता है, इसलिए डब मूल से लंबा हो सकता है।
6. **वीडियो:** FFmpeg नई आवाज़, SRT / VTT / ASS सबटाइटल और `AI-dubbed` टैग लिखता है।

## माप

संदर्भ कंप्यूटर: 4 GB Pascal GPU, Windows 10; तरीका और सारी पंक्तियाँ [docs/olcumler.md](docs/olcumler.md) में।

| क्या | CPU प्रोफ़ाइल | GPU प्रोफ़ाइल |
|---|---|---|
| पहला इंस्टॉलेशन, डिफ़ॉल्ट कदम, शुरू से आख़िर तक | ≈ 38 मिनट | ≈ 44 मिनट (पैकेज 13.7 मिनट) |
| इंस्टॉल के बाद डिस्क | ≈ 13.2 GB (फ़ोल्डर का जोड़) | ≈ 14.6 GB (हार्ड लिंक एक बार गिने गए) |
| 9 सेकंड का सैंपल डब, ऑफ़लाइन अनुवाद | 528 सेकंड | 376 सेकंड |
| 30 सेकंड की अंग्रेज़ी क्लिप, Demucs, Claude Code अनुवाद | – | 744 सेकंड |

## सीमाएँ

- CrisperWhisper (वैकल्पिक इंजन 13) के बिना faster-whisper चीनी और जापानी में बोली छोड़ सकता है या ऐसा टेक्स्ट गढ़ सकता है जो बोला ही नहीं गया (देखा गया: एक चीनी क्लिप के पहले ≈ 10 सेकंड छूट गए; चीख एक लंबी "ああ…" लाइन बन गई)।
- CI सिर्फ़ CPU टेस्ट करता है; GPU रास्ता एक 4 GB Pascal कार्ड पर हाथ से चलाया गया। नए कार्ड (RTX 50), Linux और macOS आज़माए नहीं गए; इंस्टॉल होने वाली GPU लाइब्रेरी में Pascal से RTX 50 तक के कर्नेल हैं, और Maxwell CPU प्रोफ़ाइल इस्तेमाल करता है ([GPU सपोर्ट तालिका, अंग्रेज़ी में](docs/installation.md#1-system-requirements))।
- ऑफ़लाइन अनुवादक सिर्फ़ अंग्रेज़ी से तुर्की करता है; दूसरी भाषा-जोड़ियों के लिए Codex / Claude Code CLI या API बैकएंड चाहिए।
- अंग्रेज़ी और तुर्की के अलावा दूसरी स्रोत भाषाओं के लिए शब्द-समय: जापानी और चीनी के लिए `scripts/kur.ps1 -Adim hizalama-diller`, बाकी के लिए `DUBLAJ_CEVRIMICI=1` के साथ एक बार चलाने के बाद।
- अभी शुरू से आख़िर तक नहीं आज़माए गए: XTTS-v2 का असली इंस्टॉलेशन, RVC, असली सेवा से जुड़ा Telegram बॉट और CrisperWhisper 2 Medium; Moonshine प्रयोग के दौर में है। CrisperWhisper 2.0 Turbo (इंजन 13) को GTX 1050 Ti 4 GB पर असली ऑडियो से टेस्ट किया गया है (tr, en, ja; ≈ 1.4 GB VRAM)।

## बिल्डिंग ब्लॉक

हर चरण अकेले भी चलता है, कमांड लाइन से या Python से, और चरणों के बीच फ़ाइल फ़ॉर्मेट दस्तावेज़ में लिखे हैं
(चरणों का नक्शा और JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` यही चरण फ़ंक्शन के रूप में देता है। सिर्फ़ उतना इंस्टॉल कीजिए जितना उस चरण को चाहिए, जैसे
सबटाइटल के लिए `pip install -e ".[stt,hizalama,cpu]"`। इन ब्लॉकों से बने पाँच छोटे टूल: [examples/](examples/)।

## परिवार / जुड़े हुए प्रोजेक्ट

| रिपॉज़िटरी | क्या है | यह रिपॉज़िटरी इसे कैसे इस्तेमाल करती है |
|---|---|---|
| **DubWorld** (यही रिपॉज़िटरी) | पूरी तरह लोकल वीडियो डबिंग पाइपलाइन, हर चरण अलग से भी इस्तेमाल हो सकता है | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | शब्दशः बोली-से-टेक्स्ट, शब्द-समय के साथ (CrisperWhisper 2.0 Turbo + CTC अलाइनमेंट) | वैकल्पिक इंजन 13: `scripts/kur.ps1 -Adim crisper` उस रिपॉज़िटरी के ज़रिए तय commit पर मॉडल इंस्टॉल करता है (वेट **गैर-व्यावसायिक**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | VoxCPM2 से आवाज़ डिज़ाइन और पाठ, 8 भाषाएँ, तैयार आवाज़ें | वैकल्पिक आवाज़ इंजन `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` तय commit पर इंस्टॉल करता है; यह रिपॉज़िटरी एक पतले एडैप्टर से उसे बुलाती है |

हर सहयोगी रिपॉज़िटरी का अपना लाइसेंस, इंस्टॉलेशन और issues हैं; तय commit की वजह से यह जोड़ हर बार दोबारा वैसा ही बनाया जा सकता है।

## ज़िम्मेदारी से इस्तेमाल

> **कानूनी सूचना।** इस सॉफ़्टवेयर से आप जो सामग्री प्रोसेस और प्रकाशित करते हैं, और अपने देश के कानूनों तथा जिन
> साइटों और सेवाओं का आप इस्तेमाल करते हैं उनकी शर्तों का पालन करने की पूरी ज़िम्मेदारी आपकी है। सॉफ़्टवेयर "जैसा है"
> वैसा, बिना किसी वारंटी के दिया जाता है (Apache-2.0)। पूरा पाठ: [ETHICS.md](ETHICS.md)।

- **अधिकार और सहमति।** सिर्फ़ वही सामग्री प्रोसेस कीजिए जो आपकी है या जिसका अनुवाद और दोबारा डब करने की अनुमति आपके पास है,
  और उसमें पहचाने जा सकने वाले लोगों की सहमति लीजिए।
- **आवाज़ें।** किसी की नक़ल नहीं। संदर्भ आवाज़ सिर्फ़ आपकी अपनी हो सकती है या उस व्यक्ति की जिसने साफ़ अनुमति दी हो।
- **लेबल लगाइए।** आउटपुट में `AI-dubbed` मेटाडेटा टैग होता है; उसे बने रहने दीजिए और अपने दर्शकों को भी साफ़ दिखने वाले
  तरीके से बताइए कि डबिंग AI से की गई है (EU AI Act अनुच्छेद 50; Supertonic लाइसेंस)।
- **डाउनलोड।** वैकल्पिक `youtube` (yt-dlp) और `galeri` (gallery-dl) एक्स्ट्रा सिर्फ़ उस सामग्री के लिए हैं जो आपकी है या जिसे डाउनलोड करने का आपको हक़ है; साइट की शर्तें और
  आपके स्थानीय कानून लागू होते हैं।
- **गैर-व्यावसायिक इंजन।** CrisperWhisper 2.0 और XTTS-v2 सिर्फ़ गैर-व्यावसायिक उपयोग के लिए हैं (डिफ़ॉल्ट रूप से बंद)। किसी भी पेड या क्लाइंट काम से पहले
  [THIRD_PARTY.md](THIRD_PARTY.md) का **Commercial?** कॉलम ज़रूर देखिए।
  fr / de / es / it स्रोत ऑडियो के शब्द-समय मॉडल (CC BY-NC 4.0) भी गैर-व्यावसायिक हैं और पहली बार इस्तेमाल पर सहमति माँगते हैं।

## मदद और सहायता

सवाल, सुझाव और अपने नतीजे: [चर्चा मंच](https://github.com/alexturkey/dubworld/discussions)। इंस्टॉलेशन की दिक्कत: [इंस्टॉलेशन समस्या बताइए](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); बग: [बग रिपोर्ट कीजिए](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(ऑपरेटिंग सिस्टम, GPU, चलाई गई कमांड और आउटपुट की आख़िरी लाइनें लिखिए)। सुरक्षा से जुड़ी समस्याएँ: SECURITY.md देखिए, सार्वजनिक issue में मत लिखिए।

## लाइसेंस और श्रेय

कोड: Apache-2.0 (LICENSE)। बाहरी हिस्से और उनके लाइसेंस: THIRD_PARTY.md। ज़िम्मेदारी से इस्तेमाल: ETHICS.md।
निजता (क्या आपके कंप्यूटर पर रहता है, क्लाउड बैकएंड को क्या मिलता है): PRIVACY.md। सुरक्षा रिपोर्ट: SECURITY.md। बदलाव: CHANGELOG.md।

<!-- i18n-source: README.md sha256:2e512198d98b -->
