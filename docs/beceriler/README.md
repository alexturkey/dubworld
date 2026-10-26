# Skills for AI coding agents / Yapay zekâ ajanları için beceriler

[Türkçe](#türkçe) · Claude Code loads these automatically from `.claude/skills/<name>/SKILL.md`. Codex, Cursor,
Copilot, Gemini CLI and other agents: read the matching `SKILL.md` as a plain Markdown runbook before the task; the
steps, commands and checks are the same for every agent. Start every session with [AGENTS.md](../../AGENTS.md).

| Task | Skill (runbook) | Main documents |
|---|---|---|
| Install, choose GPU / CPU profile, add optional engines, verify with `dubla kontrol` | [kurulum-ve-donanim](../../.claude/skills/kurulum-ve-donanim/SKILL.md) | [donanim.md](../donanim.md), [engineering/low_vram.md](../engineering/low_vram.md) |
| Dub a video with the recommended flow; subtitles only | [dublaj-onerilen-akis](../../.claude/skills/dublaj-onerilen-akis/SKILL.md) | `src/dublaj_hatti/varsayilan.toml`, [mimari.md](../mimari.md) |
| Change settings, build a recipe, understand rejected combinations | [gelismis-ayarlar-ve-kombinasyonlar](../../.claude/skills/gelismis-ayarlar-ve-kombinasyonlar/SKILL.md) | [tarifler/kombinasyonlar.md](../tarifler/kombinasyonlar.md) |
| Pick a speech-to-text engine and language-detection mode | [stt-motorlari](../../.claude/skills/stt-motorlari/SKILL.md) | [tarifler/dil_tespiti.md](../tarifler/dil_tespiti.md), [engineering/transcription.md](../engineering/transcription.md) |
| Pick TTS engine, target language and voices; XTTS / RVC consent and license | [tts-motorlari](../../.claude/skills/tts-motorlari/SKILL.md) | [diller.md](../diller.md), [sesler.md](../sesler.md), [../ETHICS.md](../../ETHICS.md) |
| Connect Codex / Claude Code, offline Opus-MT, cloud API with your own key | [ceviri-arka-uclari](../../.claude/skills/ceviri-arka-uclari/SKILL.md) | [engineering/translation.md](../engineering/translation.md), [../.env.example](../../.env.example) |
| Resume, failed jobs, crash recovery, GPU queue | [devam-ve-sorunlu-isler](../../.claude/skills/devam-ve-sorunlu-isler/SKILL.md) | [tarifler/devam_ve_sorunlu_isler.md](../tarifler/devam_ve_sorunlu_isler.md) |
| Telegram bot: BotFather, `.env`, allowed ids | [telegram-botu-kurulumu](../../.claude/skills/telegram-botu-kurulumu/SKILL.md) | [tarifler/telegram_botu.md](../tarifler/telegram_botu.md) |
| Large files over Telegram (2000 MB): local Bot API server, `api_id` / `api_hash` | [telegram-buyuk-dosya](../../.claude/skills/telegram-buyuk-dosya/SKILL.md) | [tarifler/telegram_buyuk_dosya.md](../tarifler/telegram_buyuk_dosya.md) |
| One stage alone, Python API, build your own tool | [tek-asama-kullanimi-ve-api](../../.claude/skills/tek-asama-kullanimi-ve-api/SKILL.md) | [mimari.md](../mimari.md), [../examples/README.md](../../examples/README.md) |
| Errors: OOM / low VRAM, ffmpeg, lock, install, login | [sorun-giderme](../../.claude/skills/sorun-giderme/SKILL.md) | [engineering/README.md](../engineering/README.md), [adr/README.md](../adr/README.md) |
| Contribute, add an engine (`kayit.py`), tests, legal audit | [katki-ve-motor-ekleme](../../.claude/skills/katki-ve-motor-ekleme/SKILL.md) | [../CONTRIBUTING.md](../../CONTRIBUTING.md), [../THIRD_PARTY.md](../../THIRD_PARTY.md) |
| Change the web interface: tokens, icons, confirm dialog, no layout shift, motion, checks | [arayuz-tasarimi](../../.claude/skills/arayuz-tasarimi/SKILL.md) | `src/dublaj_hatti/web_statik/`, [arayuz_dili.md](../arayuz_dili.md) |

## Engine pages

Every engine in the registry (`src/dublaj_hatti/kayit.py`) has a page `docs/motorlar/<setting value>.md` (license,
hardware, install, settings, common errors). Skills link to them instead of repeating them.

- Speech-to-text: [faster-whisper](../motorlar/faster-whisper.md) · [faster_whisper_ctc](../motorlar/faster_whisper_ctc.md) · [whisperx](../motorlar/whisperx.md) ·
  [crisperwhisper_turbo_ct2](../motorlar/crisperwhisper_turbo_ct2.md) ·
  [whisper_cpp_cpu_align](../motorlar/whisper_cpp_cpu_align.md) ·
  [parakeet_cpu_align](../motorlar/parakeet_cpu_align.md) · [speechmatics](../motorlar/speechmatics.md) ·
  [elevenlabs_scribe_v2](../motorlar/elevenlabs_scribe_v2.md) · [youtube_translate](../motorlar/youtube_translate.md)
- Translation: [yerel](../motorlar/yerel.md) · [codex](../motorlar/codex.md) · [claude_code](../motorlar/claude_code.md) ·
  [gemini_2_5_flash](../motorlar/gemini_2_5_flash.md) · [gemini_3_1_flash_lite_tier_1](../motorlar/gemini_3_1_flash_lite_tier_1.md) ·
  [gemma_4_26b](../motorlar/gemma_4_26b.md) · [groq_llama_4_scout](../motorlar/groq_llama_4_scout.md) ·
  [cerebras_llama_3_1_8b](../motorlar/cerebras_llama_3_1_8b.md) · [mistral_nemo](../motorlar/mistral_nemo.md)
- Text-to-speech: [supertonic](../motorlar/supertonic.md) · [voxcpm2](../motorlar/voxcpm2.md) · [xtts](../motorlar/xtts.md)
- Extras: [demucs](../motorlar/demucs.md) · [yt_dlp](../motorlar/yt_dlp.md) · [konusmaci_ayrimi](../motorlar/konusmaci_ayrimi.md) ·
  [cinsiyet_siniflandirici](../motorlar/cinsiyet_siniflandirici.md) · [segment_cinsiyet_kipi](../motorlar/segment_cinsiyet_kipi.md) ·
  [akilli_kare](../motorlar/akilli_kare.md) · [rvc](../motorlar/rvc.md) · [gallery_dl](../motorlar/gallery_dl.md) ·
  [kapak_gorseli](../motorlar/kapak_gorseli.md) · [telegram_botu](../motorlar/telegram_botu.md)

## Rules every agent follows here

- Never accept a non-commercial or conditional license, a consent flag (`ses.rvc_riza_onayi`) or a login on the
  user's behalf; show the notice and ask.
- Never print, commit or paste keys and tokens; they live only in the user's `.env`.
- Never relax a sha256 check or add a silent fallback; no weights, media or personal data in the repository.
- Only content the user owns or may use; no imitation of real people ([ETHICS.md](../../ETHICS.md)).

---

## Türkçe

Claude Code bu becerileri `.claude/skills/<name>/SKILL.md` içinden kendiliğinden yükler. Codex, Cursor, Copilot,
Gemini CLI ve diğer ajanlar: işe başlamadan önce ilgili `SKILL.md` dosyasını düz Markdown çalışma kılavuzu olarak
okuyun; adımlar, komutlar ve denetimler her ajan için aynıdır. Her oturum [AGENTS.md](../../AGENTS.md) ile başlar.

| Görev | Beceri (çalışma kılavuzu) | Ana belgeler |
|---|---|---|
| Kurulum, GPU / CPU profili seçimi, isteğe bağlı motor ekleme, `dubla kontrol` ile doğrulama | [kurulum-ve-donanim](../../.claude/skills/kurulum-ve-donanim/SKILL.md) | [donanim.md](../donanim.md), [engineering/low_vram.md](../engineering/low_vram.md) |
| Önerilen akışla video dublajı; yalnız altyazı | [dublaj-onerilen-akis](../../.claude/skills/dublaj-onerilen-akis/SKILL.md) | `src/dublaj_hatti/varsayilan.toml`, [mimari.md](../mimari.md) |
| Ayar değiştirme, tarif kurma, reddedilen birleşimleri anlama | [gelismis-ayarlar-ve-kombinasyonlar](../../.claude/skills/gelismis-ayarlar-ve-kombinasyonlar/SKILL.md) | [tarifler/kombinasyonlar.md](../tarifler/kombinasyonlar.md) |
| Konuşmadan metne motoru ve dil tespiti kipi seçme | [stt-motorlari](../../.claude/skills/stt-motorlari/SKILL.md) | [tarifler/dil_tespiti.md](../tarifler/dil_tespiti.md), [engineering/transcription.md](../engineering/transcription.md) |
| TTS motoru, hedef dil ve ses seçme; XTTS / RVC rızası ve lisansı | [tts-motorlari](../../.claude/skills/tts-motorlari/SKILL.md) | [diller.md](../diller.md), [sesler.md](../sesler.md), [../ETHICS.md](../../ETHICS.md) |
| Codex / Claude Code bağlama, çevrimdışı Opus-MT, kendi anahtarınızla bulut API | [ceviri-arka-uclari](../../.claude/skills/ceviri-arka-uclari/SKILL.md) | [engineering/translation.md](../engineering/translation.md), [../.env.example](../../.env.example) |
| Devam, sorunlu işler, çökme sonrası kurtarma, GPU sırası | [devam-ve-sorunlu-isler](../../.claude/skills/devam-ve-sorunlu-isler/SKILL.md) | [tarifler/devam_ve_sorunlu_isler.md](../tarifler/devam_ve_sorunlu_isler.md) |
| Telegram botu: BotFather, `.env`, izinli kimlikler | [telegram-botu-kurulumu](../../.claude/skills/telegram-botu-kurulumu/SKILL.md) | [tarifler/telegram_botu.md](../tarifler/telegram_botu.md) |
| Telegram ile büyük dosya (2000 MB): yerel Bot API sunucusu, `api_id` / `api_hash` | [telegram-buyuk-dosya](../../.claude/skills/telegram-buyuk-dosya/SKILL.md) | [tarifler/telegram_buyuk_dosya.md](../tarifler/telegram_buyuk_dosya.md) |
| Tek aşamayı tek başına kullanma, Python API, kendi aracını kurma | [tek-asama-kullanimi-ve-api](../../.claude/skills/tek-asama-kullanimi-ve-api/SKILL.md) | [mimari.md](../mimari.md), [../examples/README.md](../../examples/README.md) |
| Hatalar: bellek taşması / düşük VRAM, ffmpeg, kilit, kurulum, giriş | [sorun-giderme](../../.claude/skills/sorun-giderme/SKILL.md) | [engineering/README.md](../engineering/README.md), [adr/README.md](../adr/README.md) |
| Katkı, motor ekleme (`kayit.py`), testler, yasal denetim | [katki-ve-motor-ekleme](../../.claude/skills/katki-ve-motor-ekleme/SKILL.md) | [../CONTRIBUTING.md](../../CONTRIBUTING.md), [../THIRD_PARTY.md](../../THIRD_PARTY.md) |
| Web arayüzünü değiştirme: belirteçler, simgeler, onay penceresi, kaymasız yerleşim, hareket, denetim | [arayuz-tasarimi](../../.claude/skills/arayuz-tasarimi/SKILL.md) | `src/dublaj_hatti/web_statik/`, [arayuz_dili.md](../arayuz_dili.md) |

### Motor sayfaları

Kayıttaki (`src/dublaj_hatti/kayit.py`) her motorun bir `docs/motorlar/<ayar değeri>.md` sayfası vardır (lisans,
donanım, kurulum, ayarlar, sık hatalar). Beceriler bunları tekrarlamak yerine bu sayfalara bağlantı verir.

- Konuşmadan metne: [faster-whisper](../motorlar/faster-whisper.md) · [faster_whisper_ctc](../motorlar/faster_whisper_ctc.md) · [whisperx](../motorlar/whisperx.md) ·
  [crisperwhisper_turbo_ct2](../motorlar/crisperwhisper_turbo_ct2.md) ·
  [whisper_cpp_cpu_align](../motorlar/whisper_cpp_cpu_align.md) ·
  [parakeet_cpu_align](../motorlar/parakeet_cpu_align.md) · [speechmatics](../motorlar/speechmatics.md) ·
  [elevenlabs_scribe_v2](../motorlar/elevenlabs_scribe_v2.md) · [youtube_translate](../motorlar/youtube_translate.md)
- Çeviri: [yerel](../motorlar/yerel.md) · [codex](../motorlar/codex.md) · [claude_code](../motorlar/claude_code.md) ·
  [gemini_2_5_flash](../motorlar/gemini_2_5_flash.md) · [gemini_3_1_flash_lite_tier_1](../motorlar/gemini_3_1_flash_lite_tier_1.md) ·
  [gemma_4_26b](../motorlar/gemma_4_26b.md) · [groq_llama_4_scout](../motorlar/groq_llama_4_scout.md) ·
  [cerebras_llama_3_1_8b](../motorlar/cerebras_llama_3_1_8b.md) · [mistral_nemo](../motorlar/mistral_nemo.md)
- Metinden konuşmaya: [supertonic](../motorlar/supertonic.md) · [voxcpm2](../motorlar/voxcpm2.md) · [xtts](../motorlar/xtts.md)
- Ekler: [demucs](../motorlar/demucs.md) · [yt_dlp](../motorlar/yt_dlp.md) · [konusmaci_ayrimi](../motorlar/konusmaci_ayrimi.md) ·
  [cinsiyet_siniflandirici](../motorlar/cinsiyet_siniflandirici.md) · [segment_cinsiyet_kipi](../motorlar/segment_cinsiyet_kipi.md) ·
  [akilli_kare](../motorlar/akilli_kare.md) · [rvc](../motorlar/rvc.md) · [gallery_dl](../motorlar/gallery_dl.md) ·
  [kapak_gorseli](../motorlar/kapak_gorseli.md) · [telegram_botu](../motorlar/telegram_botu.md)

### Burada her ajanın uyduğu kurallar

- Ticari olmayan ya da koşullu bir lisansı, bir rıza bayrağını (`ses.rvc_riza_onayi`) ya da bir hesap girişini asla
  kullanıcı adına kabul etmeyin; bildirimi gösterin ve sorun.
- Anahtar ve belirteçleri asla yazdırmayın, commit etmeyin, yapıştırmayın; yalnız kullanıcının `.env` dosyasında
  dururlar.
- sha256 denetimini asla gevşetmeyin ve sessiz yedek eklemeyin; repoda ağırlık, medya ya da kişisel veri olmaz.
- Yalnız kullanıcının sahibi olduğu ya da kullanma hakkı olan içerik; gerçek kişi taklidi yok
  ([ETHICS.md](../../ETHICS.md)).
