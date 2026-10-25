# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · ไทย · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md)

> DubWorld พากย์วิดีโอของคุณเป็นภาษาอื่นได้บนคอมพิวเตอร์ของคุณเอง โดยไม่ต้องอัปโหลดขึ้นบริการออนไลน์ใด ๆ: แปลงเสียงพูดเป็นข้อความพร้อมเวลาของทุกคำ แปลข้อความ แล้วให้เสียงสังเคราะห์ (AI) อ่านออกมาให้ตรงจังหวะกับวิดีโอต้นฉบับ (เสียงพูดเร่งได้สูงสุด 1.25 เท่า ส่วนต่างที่เหลือชดเชยด้วยการปรับความเร็ววิดีโอเล็กน้อย) ใส่คำบรรยาย และสร้างวิดีโอใหม่ ภาษาตั้งต้นคือภาษาตุรกี บอกกันตรง ๆ: การพากย์ **เป็น** ภาษาไทยยังทำไม่ได้ เพราะเครื่องมือเสียงในรีโพนี้ยังไม่มีตัวไหนพูดภาษาไทยได้ แต่วิดีโอภาษาไทยสามารถพากย์เป็นภาษาอื่นได้ ([docs/diller.md](docs/diller.md))

## ให้ผู้ช่วย AI ของคุณติดตั้งให้

ไม่ต้องเขียนโปรแกรมเป็น เปิดผู้ช่วย AI ที่สั่งงานบนคอมพิวเตอร์ของคุณได้ (Claude Code, Codex,
Gemini CLI หรือตัวที่คล้ายกัน) แล้ววางประโยคนี้ประโยคเดียว:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

ผู้ช่วยจะตรวจคอมพิวเตอร์ของคุณ (การ์ดจอ ซีพียู หน่วยความจำ ดิสก์) และถามเพียงครั้งเดียวด้วยภาษาง่าย ๆ ว่าคุณอยากติดตั้งแบบไหน:
แบบเร็ว แบบที่แนะนำสำหรับเครื่องคุณ หรือแบบครบ มันจะอธิบายทุกส่วน (ทำอะไร ใช้พื้นที่เท่าไร ติดตั้งนานแค่ไหน ใช้สัญญาอนุญาตอะไร)
และเริ่มจากเสียงตั้งต้น ถามว่าคุณยอมรับเงื่อนไขการใช้งานของส่วนที่เลือกหรือไม่ จากนั้นจึงติดตั้ง ทำตัวอย่างการพากย์ และเปิดหน้าต่างโปรแกรมให้
ขั้นตอนแรกและปัญหาที่พบบ่อย อธิบายแบบเข้าใจง่าย (ภาษาอังกฤษ): **[docs/getting-started.md](docs/getting-started.md)**

**สรุปสัญญาอนุญาต:** โค้ด Apache-2.0 โมเดลตั้งต้น: เสียง Supertonic 3 ภายใต้ OpenRAIL-M (มีข้อจำกัดการใช้งาน ยอมรับครั้งเดียว); Opus-MT และโมเดลเวลาคำภาษาตุรกีภายใต้ CC BY 4.0 (ต้องให้เครดิต, NOTICE); FFmpeg build GPL-3.0 (โปรแกรมแยกต่างหาก) ใช้ได้เฉพาะงานที่ไม่ใช่เชิงพาณิชย์และปิดไว้ตั้งแต่ต้น: CrisperWhisper 2.0, XTTS-v2 และโมเดลเวลาคำ WhisperX สำหรับ fr / de / es / it รีโพนี้ไม่มีน้ำหนักโมเดลใด ๆ ([THIRD_PARTY.md](THIRD_PARTY.md))

## ติดตั้งแบบเร็ว

Windows 10/11 x64; ไม่ต้องมี Python, CUDA หรือ ffmpeg ติดตั้งไว้ก่อน ดับเบิลคลิก **`kur.cmd`** (หรือรัน
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); โปรไฟล์ GPU หรือ CPU จะถูกเลือกเอง
(`-Cpu` บังคับใช้ CPU) จากนั้นดับเบิลคลิก `arayuz.cmd` เพื่อเปิดแอป
ทุกอย่างอยู่ในโฟลเดอร์รีโพ (`.venv`, `runtime_assets/`); ไฟล์ที่ดาวน์โหลดทุกไฟล์ล็อกเวอร์ชันไว้และ
ตรวจด้วย sha256 พื้นที่ว่างที่ต้องใช้ตอนเริ่ม: 22 GB สำหรับโปรไฟล์ GPU, 14 GB ถ้าใช้ CPU อย่างเดียว; พื้นที่ที่วัดได้หลังติดตั้ง ≈ 14.6 GB (GPU, ไฟล์ hard link นับครั้งเดียว; File Explorer แสดง ≈ 22 GB) ตรวจสอบ: `.venv\Scripts\dubla.exe kontrol`

ความต้องการของระบบ ลำดับขั้นตอน แผนผังสภาพแวดล้อม Python เครื่องมือเสริม การใช้งานออฟไลน์ การอัปเดต การถอนการติดตั้ง และ
ข้อผิดพลาดที่พบบ่อย (ภาษาอังกฤษ): **[docs/installation.md](docs/installation.md)** เรายังไม่ได้ทดสอบบน Linux และ macOS ตัวอย่าง: [วิดีโอแนะนำผลิตภัณฑ์ที่พากย์เป็นภาษาอังกฤษ ตุรกี และอาหรับ บน Mac ชิป Apple M4 ด้วย CPU อย่างเดียว](https://x.com/MihenkAIdotcom/status/2114345171571925363)

## วิธีใช้

แอปเดสก์ท็อป: ดับเบิลคลิก `arayuz.cmd` (เว็บแอปในเครื่อง: `web.cmd` เฉพาะ 127.0.0.1) หน้าตาแอปตอนนี้เป็นภาษาตุรกี จากบรรทัดคำสั่ง:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

การพากย์เป็นภาษาไทยยังไม่พร้อมใช้ เพราะเครื่องมือเสียงยังอ่านภาษาไทยไม่ได้ แต่วิดีโอภาษาไทยพากย์เป็นภาษาอังกฤษได้ด้วย `--ayar genel.hedef_dil=en` หรือเป็นภาษาตุรกีด้วยคำสั่งปกติ (การแปลจากภาษาไทยต้องใช้ Codex หรือ Claude Code) ผลลัพธ์อยู่ใน `cikti/<video>_<time>/`: `dubbed_tr.mp4` (มีแท็ก `AI-dubbed`), คำบรรยายต้นฉบับ `transcript_<lang>.srt` และไฟล์งาน JSON; บรรทัดสุดท้าย `dubbed_video:` บอกตำแหน่งไฟล์ การตั้งค่าทั้งหมด (ภาษาอังกฤษและตุรกี): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md)

## ทำงานอย่างไร

1. **เสียง:** FFmpeg ดึงเสียงออกมา; Demucs (MIT) ซึ่งเป็นตัวเลือกเสริม แยกเสียงพูดออกจากเสียงพื้นหลัง
2. **เสียงพูดเป็นข้อความ:** faster-whisper large-v3-turbo (MIT) พร้อมเวลาคำจาก wav2vec2 CTC (อังกฤษ MIT, ตุรกี CC BY 4.0); CrisperWhisper 2.0 เสริม (ไม่ใช่เชิงพาณิชย์) และเครื่องมืออื่น ๆ
3. **ผู้พูด:** 3D-Speaker CAM++ (Apache-2.0) และโมเดลจำแนกเพศ (Apache-2.0) เลือกเสียง AI หนึ่งเสียงให้ผู้พูดแต่ละคน
4. **การแปล:** ใช้ Codex CLI หรือ Claude Code CLI ถ้าติดตั้งและล็อกอินไว้ ไม่เช่นนั้นใช้ Opus-MT ในเครื่อง แปลอังกฤษเป็นตุรกี (CC BY 4.0); แบ็กเอนด์ API เป็นตัวเลือกเสริม
5. **เสียงและจังหวะ:** ตั้งต้น Supertonic 3 (OpenRAIL-M), เสริม VoxCPM2 (Apache-2.0) หรือ XTTS-v2 (ไม่ใช่เชิงพาณิชย์); แต่ละประโยคเร่งได้สูงสุด 1.25 เท่าเข้าหาความยาวช่วงต้นฉบับ ที่เหลือปรับด้วยเวลาของวิดีโอ จึงอาจยาวกว่าต้นฉบับได้
6. **วิดีโอ:** FFmpeg เขียนเสียงใหม่ คำบรรยาย SRT / VTT / ASS และแท็ก `AI-dubbed`

## ผลการวัด

เครื่องอ้างอิง: GPU Pascal 4 GB, Windows 10; วิธีวัดและทุกแถวอยู่ใน [docs/olcumler.md](docs/olcumler.md)

| อะไร | โปรไฟล์ CPU | โปรไฟล์ GPU |
|---|---|---|
| ติดตั้งครั้งแรก ขั้นตอนตั้งต้น ตั้งแต่ต้นจนจบ | ≈ 38 นาที | ≈ 44 นาที (แพ็กเกจ 13.7 นาที) |
| ดิสก์หลังติดตั้ง | ≈ 13.2 GB (ผลรวมโฟลเดอร์) | ≈ 14.6 GB (hard link นับครั้งเดียว) |
| ตัวอย่างพากย์ 9 วินาที แปลแบบออฟไลน์ | 528 วินาที | 376 วินาที |
| คลิปภาษาอังกฤษ 30 วินาที, Demucs, แปลด้วย Claude Code | – | 744 วินาที |

## ข้อจำกัด

- ถ้าไม่มี CrisperWhisper (เครื่องมือเสริมหมายเลข 13) faster-whisper อาจข้ามเสียงพูดหรือแต่งข้อความที่ไม่มีใครพูดขึ้นมาในภาษาจีนและญี่ปุ่น (พบจริง: ≈ 10 วินาทีแรกของคลิปภาษาจีนหายไป; เสียงตะโกนกลายเป็นบรรทัด "ああ…" ยาว ๆ)
- CI ทดสอบเฉพาะ CPU; เส้นทาง GPU รันด้วยมือบนการ์ด Pascal 4 GB การ์ดใหม่ (RTX 50), Linux และ macOS ยังไม่ได้ทดสอบ; ไลบรารี GPU ที่ติดตั้งมีเคอร์เนลตั้งแต่ Pascal ถึง RTX 50 ส่วน Maxwell ใช้โปรไฟล์ CPU ([ตารางรองรับ GPU ภาษาอังกฤษ](docs/installation.md#1-system-requirements))
- ตัวแปลออฟไลน์แปลได้แค่อังกฤษเป็นตุรกี; คู่ภาษาอื่นต้องใช้ Codex / Claude Code CLI หรือแบ็กเอนด์ API
- เวลาคำสำหรับภาษาต้นทางนอกจากอังกฤษและตุรกี: ญี่ปุ่นและจีนผ่าน `scripts/kur.ps1 -Adim hizalama-diller` ภาษาอื่นหลังรันหนึ่งครั้งด้วย `DUBLAJ_CEVRIMICI=1`
- ยังไม่ได้ทดสอบตั้งแต่ต้นจนจบ: การติดตั้ง XTTS-v2 จริง, RVC, บอท Telegram ที่ต่อกับบริการจริง และ CrisperWhisper 2 Medium; Moonshine ยังเป็นรุ่นทดลอง CrisperWhisper 2.0 Turbo (เครื่องมือ 13) ทดสอบกับเสียงจริงบน GTX 1050 Ti 4 GB แล้ว (tr, en, ja; ≈ 1.4 GB VRAM)

## ชิ้นส่วนประกอบ

ทุกขั้นตอนรันแยกได้ ทั้งจากบรรทัดคำสั่งหรือจาก Python และรูปแบบไฟล์ระหว่างขั้นตอนมีเอกสารกำกับ
(แผนผังขั้นตอนและ JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` ให้ขั้นตอนเดียวกันในรูปฟังก์ชัน ติดตั้งเฉพาะสิ่งที่ขั้นตอนนั้นต้องใช้ เช่น
`pip install -e ".[stt,hizalama,cpu]"` สำหรับคำบรรยาย เครื่องมือเล็ก ๆ ห้าตัวที่สร้างจากชิ้นส่วนเหล่านี้: [examples/](examples/)

## ครอบครัว / โปรเจกต์ที่เกี่ยวข้อง

| รีโพ | คืออะไร | รีโพนี้ใช้อย่างไร |
|---|---|---|
| **DubWorld** (รีโพนี้) | สายการพากย์วิดีโอที่ทำงานในเครื่องทั้งหมด แต่ละขั้นตอนใช้แยกได้ | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | แปลงเสียงพูดเป็นข้อความแบบคำต่อคำ พร้อมเวลาคำ (CrisperWhisper 2.0 Turbo + การจัดแนว CTC) | เครื่องมือเสริม 13: `scripts/kur.ps1 -Adim crisper` ติดตั้งโมเดลผ่านรีโพนั้นที่ commit ที่ล็อกไว้ (น้ำหนัก **ไม่ใช่เชิงพาณิชย์**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | ออกแบบเสียงและอ่านข้อความด้วย VoxCPM2, 8 ภาษา, มีเสียงสำเร็จรูป | เครื่องมือเสียงเสริม `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` ติดตั้งที่ commit ที่ล็อกไว้; รีโพนี้เรียกใช้ผ่านอะแดปเตอร์บาง ๆ |

รีโพพี่น้องแต่ละตัวมีสัญญาอนุญาต การติดตั้ง และ issue ของตัวเอง; เพราะล็อก commit ไว้ จึงสร้างชุดนี้ใหม่ได้ผลเหมือนเดิมทุกครั้ง

## การใช้งานอย่างรับผิดชอบ

> **ประกาศทางกฎหมาย** คุณรับผิดชอบเต็มที่ต่อเนื้อหาที่คุณประมวลผลและเผยแพร่ด้วยซอฟต์แวร์นี้ รวมถึงการปฏิบัติตามกฎหมาย
> ของประเทศคุณและเงื่อนไขของเว็บไซต์และบริการที่คุณใช้ ซอฟต์แวร์นี้ให้มา "ตามสภาพ" โดยไม่มีการรับประกันใด ๆ
> (Apache-2.0) ข้อความเต็ม: [ETHICS.md](ETHICS.md)

- **สิทธิ์และความยินยอม** ประมวลผลเฉพาะเนื้อหาที่เป็นของคุณหรือที่คุณมีสิทธิ์แปลและพากย์ใหม่
  และขอความยินยอมจากบุคคลที่ระบุตัวตนได้ในเนื้อหานั้น
- **เสียง** ห้ามเลียนแบบใคร เสียงอ้างอิงต้องเป็นเสียงของคุณเอง หรือของคนที่อนุญาตอย่างชัดเจนเท่านั้น
- **ติดป้าย** ผลลัพธ์มีแท็กเมทาดาทา `AI-dubbed`; อย่าลบออก และบอกผู้ชมให้เห็นชัด ๆ
  ว่าการพากย์ทำด้วย AI (มาตรา 50 ของกฎหมาย AI ของสหภาพยุโรป; สัญญาอนุญาต Supertonic)
- **การดาวน์โหลด** ส่วนเสริม `youtube` (yt-dlp) และ `galeri` (gallery-dl) ใช้ได้เฉพาะกับเนื้อหาที่เป็นของคุณหรือที่คุณมีสิทธิ์ดาวน์โหลด; เงื่อนไขของเว็บไซต์และ
  กฎหมายท้องถิ่นของคุณยังมีผลบังคับ
- **เครื่องมือที่ไม่ใช่เชิงพาณิชย์** CrisperWhisper 2.0 และ XTTS-v2 ใช้ได้เฉพาะงานที่ไม่ใช่เชิงพาณิชย์ (ปิดไว้ตั้งแต่ต้น) ก่อนรับงานที่ได้ค่าตอบแทนหรืองานลูกค้า
  ให้ดูคอลัมน์ **Commercial?** ใน [THIRD_PARTY.md](THIRD_PARTY.md)
  โมเดลเวลาคำสำหรับเสียงต้นทาง fr / de / es / it (CC BY-NC 4.0) ก็ไม่ใช่เชิงพาณิชย์เช่นกัน และจะขอความยินยอมเมื่อใช้ครั้งแรก

## ความช่วยเหลือและการสนับสนุน

คำถาม ไอเดีย และผลงานของคุณ: [กระดานสนทนา](https://github.com/alexturkey/dubworld/discussions) ปัญหาการติดตั้ง: [แจ้งปัญหาการติดตั้ง](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); บั๊ก: [แจ้งบั๊ก](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(เขียนระบบปฏิบัติการ GPU คำสั่งที่รัน และบรรทัดท้าย ๆ ของผลลัพธ์) ปัญหาด้านความปลอดภัย: ดู SECURITY.md อย่าเขียนใน issue สาธารณะ

## สัญญาอนุญาตและเครดิต

โค้ด: Apache-2.0 (LICENSE) ส่วนประกอบภายนอกและสัญญาอนุญาต: THIRD_PARTY.md การใช้งานอย่างรับผิดชอบ: ETHICS.md
ความเป็นส่วนตัว (อะไรอยู่ในเครื่องคุณ แบ็กเอนด์คลาวด์ได้รับอะไร): PRIVACY.md รายงานความปลอดภัย: SECURITY.md การเปลี่ยนแปลง: CHANGELOG.md

<!-- i18n-source: README.md sha256:2750a34df58c -->
