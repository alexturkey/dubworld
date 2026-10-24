# Setting combinations: ready-made recipes and fine-tuning guide

[Türkçe](#türkçe) · All settings live in one file: `src/dublaj_hatti/varsayilan.toml` (annotated).

A setting can be changed in three ways; all three use the same key:

| Way | Example |
|---|---|
| Command line | `dubla video.mp4 --ayar ses_temizligi.kip=preserve_background` (several `--ayar` may be given) |
| Settings file | `dubla video.mp4 --ayarlar tarifim.toml` or permanently: `ayarlar/kullanici.toml` (not tracked by git) |
| Interface | `dubla-gui` and `dubla-web` → **Gelişmiş** (Advanced) tab: every key under the same name, with its description |

To see the effective settings and warnings: `dubla ayarlar` (warnings are written to stderr as `uyarı:`).

## Ready-made recipes

Each recipe can be put into a `.toml` file and passed with `--ayarlar`; only the changed keys are written.

### 1. Keep the background + voice by speaker gender

Music and effects stay under the dub; every speaker gets a Supertonic voice that matches their voice (female/male).

```toml
[ses_temizligi]
kip = "preserve_background"      # needs Demucs: pip install .[separation]

[ses]
motor = "supertonic"
konusmaci_cinsiyetine_gore_ses = true   # 3D-Speaker + gender classifier (kur.ps1 -Adim modeller)
```

To keep the background only when needed: `kip = "auto_background"` (the transcript is made from the raw audio).
To pin the voice of a specific speaker by hand (overrides the estimate):

```toml
[ses.konusmaci_sesleri]
SPEAKER_00 = "M2"    # speaker names are in speaker_voice_map.json in the job folder
```

### 2. Subtitles / text only (no speech)

```bash
dubla transkript video.mp4 --bicim srt      # srt | plain | timestamped | paragraph
```

In the interface: the "Yalnız altyazı / metin çıkar" (Extract subtitles / text only) button; the format is
`genel.transkript_bicimi` in the Advanced tab. In this job type the translation and speech rules are not checked.

### 3. Translation only

There is no separate "translation only" job type (translation is done in the middle of the dubbing pipeline, together
with the segment times). The translated text is ready in the folder of the dubbing job:
`translated_segments_<dil>.txt` (sentence by sentence) and `full_paragraf_<dil>.txt` (paragraph). If Turkish
subtitles should be burned into the video and the audio dubbed as well, `altyazi.mod = "segment"` is enough.

### 4. Mixed-language video (the language changes within the speech)

```toml
[transkripsiyon]
motor = "crisperwhisper_turbo_ct2"        # NVIDIA GPU + separate install (non-commercial licence)
crisper_dil_tespiti = "continuous_stream" # continuous language detection along the stream
kaynak_dil = "auto"

[ceviri]
arka_uc = "codex"                          # or claude_code / an API; local Opus-MT is en→tr only
```

Without a GPU: `motor = "faster_whisper_ctc"` (or `auto`; text from faster-whisper, word times from CTC),
`kaynak_dil = "auto"` (single language, detected from the first window) and an LLM translation back end. Local
translation gives an explicit error on a non-English source.

### 5. Fast on the processor (no GPU)

```toml
[genel]
cihaz = "cpu"

[transkripsiyon]
motor = "faster-whisper"        # fastest: Whisper's own word times; "faster_whisper_ctc" for CTC times
model = "large-v3-turbo"        # model that comes with the install; "small" is faster but is not downloaded by the install
hesap_tipi = "int8"             # (downloaded on the first run with DUBLAJ_CEVRIMICI=1)

[ses_temizligi]
kip = "original"                # Demucs is slow on the processor

[ceviri]
arka_uc = "yerel"               # en→tr, offline; an LLM back end for other languages

[ses]
motor = "supertonic"
konusmaci_cinsiyetine_gore_ses = false   # skips speaker separation (single voice: supertonic_ses)
```

For an English source, `motor = "whisper_cpp_cpu_align"` or `"parakeet_cpu_align"` are options written for the
processor (separate install, docs/motorlar/).

## Choices that do not work together (validation layer)

When the settings load (`dubla`, `dubla ayarlar`, Start in the interface) the combination is checked. An **error**
does not start the job and says what to change; a **warning** is written to the log and the job continues (the
choice has no effect in that combination). Rules: `src/dublaj_hatti/yapilandirma.py` → `uyumluluk_denetle()`, tests
`tests/test_kombinasyon.py`.

| Choice | With | Result | Reason / what to do |
|---|---|---|---|
| `genel.dublaj_kipi=full_text` | `ses.motor=voxcpm2` | error | full-text mode reads with a single Supertonic voice |
| `genel.dublaj_kipi=full_text` | `ceviri.arka_uc` local or API | error | full-text translation is Codex / Claude Code only |
| `ses.motor=supertonic` | `genel.hedef_dil` outside Supertonic (e.g. `zh`) | error | Supertonic reads 31 languages; choose `voxcpm2` |
| `ses.motor=voxcpm2` | `genel.hedef_dil` outside the 8 tested languages | warning | the model may read it but it was not tested |
| `ses.motor=voxcpm2` | `genel.cihaz=cpu` | error | VoxCPM2 needs an NVIDIA GPU |
| `ses.motor=supertonic` | a `ses.konusmaci_sesleri` value outside F1..M5 | error | Supertonic voice names are F1..F5, M1..M5 |
| `ceviri.arka_uc=yerel` | `genel.hedef_dil` ≠ `tr` | error | Opus-MT is English → Turkish only |
| `ceviri.arka_uc=yerel` | `transkripsiyon.kaynak_dil` ≠ `en`/`auto` | error | same |
| `ceviri.arka_uc=auto` | no Codex/Claude CLI + target ≠ `tr` | error (at start) | the automatic choice fell back to local |
| `ses.akis` ≠ `natural_blocks_1` | local translation or VoxCPM2 | warning | candidate/repair flows need an LLM + Supertonic |
| moonshine / whisper_cpp / parakeet | `kaynak_dil` ≠ `en`/`auto` | error | English-only engines |
| crisperwhisper (turbo, medium) | `genel.cihaz=cpu` or no CUDA | error | NVIDIA GPU only |
| crisper / moonshine / cpu_align | `ileri.pyannote_konusmaci_ayrimi=true` | error | these engines do not separate speakers |
| faster-whisper | `ileri.pyannote_konusmaci_ayrimi=true` | warning | separation only with whisperx / speechmatics / elevenlabs |
| `transkripsiyon.crisper_dil_tespiti` ≠ default | an engine other than CrisperWhisper | warning | no effect |
| `transkripsiyon.whisperx_profili` ≠ `auto` | motor ≠ `whisperx` | error | the profile is WhisperX only |
| `whisperx_float32_quality_v1` / `whisperx_engine_default_v1` | `hesap_tipi` ≠ float32 / int8 | error | the profile is tied to the compute type |
| `transkripsiyon.model=distil-*` | `kaynak_dil` other than English | warning | distil is English only; the pipeline switches to a multilingual model |
| `video.politika=max_mb` | `video.max_mb=0` | error | at least 1 MB |
| `video.politika=cq` | `video.max_mb>0` | warning | the size limit applies only to the max_mb policy |
| `ses_temizligi.kip=clean`/`preserve_background` | Demucs not installed | error (at start) | `pip install .[separation]` or `original` |

Corrected automatically (not errors): transcription engines with a fixed contract (crisperwhisper, moonshine,
whisper_cpp, parakeet, speechmatics, elevenlabs) use their own model and compute type; `transkripsiyon.model` /
`hesap_tipi` apply only to faster-whisper and whisperx; `ses.atempo` is not applied in `full_text` mode; no gender
estimate is made while `ses.motor=voxcpm2` (a voice per speaker is given with `ses.konusmaci_sesleri`).

## Fine-tuning guide

| What you want | Key | Note |
|---|---|---|
| More accurate word times | `transkripsiyon.motor=crisperwhisper_turbo_ct2` | GPU; `auto` picks it if installed |
| More natural translation | `ceviri.arka_uc=codex` or `claude_code`; `ses.akis=natural_blocks_1` | your own account |
| Translation fits the duration better | `ses.akis=repair_3_light` … `repair_7` | more LLM calls, takes longer |
| Slower/faster speech | `ses.hiz` (0.5–2.0) | Supertonic |
| Speech does not fit the source duration | `ses.atempo=true` | speeds up with ffmpeg |
| Subtitle format | `altyazi.mod` = segment / word / rollup / none | burned into the video |
| File size limit | `video.politika=max_mb`, `video.max_mb=179` | 1 MB = 1 000 000 bytes |
| Better image quality | `video.cq` (lower = better; 23 high, 26 balanced, 30 small) | `politika=cq` |
| Duration in full-text mode | `video.tam_metin_sure_uyumu` = audio_to_video / video_to_audio | full_text only |
| Detailed log | `genel.gunluk_seviyesi=DEBUG` or `--ayrintili` | |

---

## Türkçe

Bütün ayarlar tek dosyadadır: `src/dublaj_hatti/varsayilan.toml` (açıklamalı). Bir ayarı üç yoldan değiştirirsiniz;
üçü de aynı anahtarı kullanır:

| Yol | Örnek |
|---|---|
| Komut satırı | `dubla video.mp4 --ayar ses_temizligi.kip=preserve_background` (birden çok `--ayar` verilebilir) |
| Ayar dosyası | `dubla video.mp4 --ayarlar tarifim.toml` ya da kalıcı: `ayarlar/kullanici.toml` (git'e girmez) |
| Arayüz | `dubla-gui` ve `dubla-web` → **Gelişmiş** sekmesi: her anahtar aynı adla, açıklamasıyla |

Geçerli ayarları ve uyarıları görmek: `dubla ayarlar` (uyarılar stderr'e `uyarı:` diye yazılır).

### Hazır tarifler

Her tarifi bir `.toml` dosyasına koyup `--ayarlar` ile verebilirsiniz; yalnız değişen anahtarlar yazılır.

#### 1. Arka planı koru + konuşmacının cinsiyetine göre ses

Müzik ve efektler dublajın altında kalır; her konuşmacıya sesine uygun (kadın/erkek) bir Supertonic sesi verilir.

```toml
[ses_temizligi]
kip = "preserve_background"      # Demucs gerekir: pip install .[separation]

[ses]
motor = "supertonic"
konusmaci_cinsiyetine_gore_ses = true   # 3D-Speaker + cinsiyet sınıflandırıcı (kur.ps1 -Adim modeller)
```

Arka planı yalnız gerektiğinde korumak için `kip = "auto_background"` (transkript ham sesle yapılır).
Belirli bir konuşmacının sesini elle sabitlemek (tahmini ezer):

```toml
[ses.konusmaci_sesleri]
SPEAKER_00 = "M2"    # konuşmacı adları iş klasöründeki speaker_voice_map.json'da
```

#### 2. Yalnız altyazı / metin (seslendirme yok)

```bash
dubla transkript video.mp4 --bicim srt      # srt | plain | timestamped | paragraph
```

Arayüzde "Yalnız altyazı / metin çıkar" düğmesi; biçim Gelişmiş'te `genel.transkript_bicimi`.
Bu iş türünde çeviri ve seslendirme kuralları denetlenmez.

#### 3. Yalnız çeviri

Ayrı bir "yalnız çeviri" iş türü yoktur (çeviri, segment zamanlarıyla birlikte dublaj hattının ortasında yapılır).
Dublaj işinin klasöründe çeviri metni hazır bulunur: `translated_segments_<dil>.txt` (cümle cümle) ve
`full_paragraf_<dil>.txt` (paragraf). Videoya Türkçe altyazı yakılsın, ses de dublajlansın istiyorsanız
`altyazi.mod = "segment"` yeterlidir.

#### 4. Karışık dilli video (konuşma içinde dil değişiyor)

```toml
[transkripsiyon]
motor = "crisperwhisper_turbo_ct2"        # NVIDIA GPU + ayrı kurulum (ticari olmayan lisans)
crisper_dil_tespiti = "continuous_stream" # akış boyunca sürekli dil tespiti
kaynak_dil = "auto"

[ceviri]
arka_uc = "codex"                          # ya da claude_code / bir API; yerel Opus-MT yalnız en→tr
```

GPU'nuz yoksa: `motor = "faster_whisper_ctc"` (ya da `auto`; metin faster-whisper, kelime zamanı CTC), `kaynak_dil = "auto"` (tek dil, ilk pencereden tespit) ve bir LLM
çeviri arka ucu. Yerel çeviri İngilizce olmayan kaynakta açık hata verir.

#### 5. İşlemcide (GPU'suz) hızlı

```toml
[genel]
cihaz = "cpu"

[transkripsiyon]
motor = "faster-whisper"        # en hızlısı: Whisper'ın kendi kelime zamanı; CTC zamanı için "faster_whisper_ctc"
model = "large-v3-turbo"        # kurulumla gelen model; "small" daha hızlıdır ama kurulum indirmez
hesap_tipi = "int8"             # (ilk çalıştırmada DUBLAJ_CEVRIMICI=1 ile indirilir)

[ses_temizligi]
kip = "original"                # Demucs işlemcide yavaştır

[ceviri]
arka_uc = "yerel"               # en→tr, ağsız; başka dil için LLM arka ucu

[ses]
motor = "supertonic"
konusmaci_cinsiyetine_gore_ses = false   # konuşmacı ayrımını atlar (tek ses: supertonic_ses)
```

İngilizce kaynakta `motor = "whisper_cpp_cpu_align"` ya da `"parakeet_cpu_align"` işlemci için yazılmış
seçeneklerdir (ayrı kurulum, docs/motorlar/).

### Birlikte çalışmayan seçimler (doğrulama katmanı)

Ayarlar yüklenirken (`dubla`, `dubla ayarlar`, arayüzde Başlat) birleşim denetlenir. **Hata** işi başlatmaz ve
neyi değiştireceğinizi söyler; **uyarı** günlüğe yazılır, iş sürer (seçim o kombinasyonda etkisizdir).
Kurallar `src/dublaj_hatti/yapilandirma.py` → `uyumluluk_denetle()`, testleri `tests/test_kombinasyon.py`.

| Seçim | Şunla | Sonuç | Neden / ne yapmalı |
|---|---|---|---|
| `genel.dublaj_kipi=full_text` | `ses.motor=voxcpm2` | hata | tam metin kipi tek Supertonic sesiyle okur |
| `genel.dublaj_kipi=full_text` | `ceviri.arka_uc` yerel ya da API | hata | tam metin çevirisi yalnız Codex / Claude Code |
| `ses.motor=supertonic` | `genel.hedef_dil` Supertonic dışı (ör. `zh`) | hata | Supertonic 31 dil okur; `voxcpm2` seçin |
| `ses.motor=voxcpm2` | `genel.hedef_dil` denenen 8 dil dışı | uyarı | model okuyabilir ama denenmedi |
| `ses.motor=voxcpm2` | `genel.cihaz=cpu` | hata | VoxCPM2 NVIDIA GPU ister |
| `ses.motor=supertonic` | `ses.konusmaci_sesleri` değeri F1..M5 dışı | hata | Supertonic ses adları F1..F5, M1..M5 |
| `ceviri.arka_uc=yerel` | `genel.hedef_dil` ≠ `tr` | hata | Opus-MT yalnız İngilizce → Türkçe |
| `ceviri.arka_uc=yerel` | `transkripsiyon.kaynak_dil` ≠ `en`/`auto` | hata | aynı |
| `ceviri.arka_uc=auto` | Codex/Claude CLI yok + hedef ≠ `tr` | hata (başlarken) | otomatik seçim yerel'e düştü |
| `ses.akis` ≠ `natural_blocks_1` | yerel çeviri ya da VoxCPM2 | uyarı | aday/onarım akışları LLM + Supertonic ister |
| moonshine / whisper_cpp / parakeet | `kaynak_dil` ≠ `en`/`auto` | hata | yalnız İngilizce motorlar |
| crisperwhisper (turbo, medium) | `genel.cihaz=cpu` ya da CUDA yok | hata | yalnız NVIDIA GPU |
| crisper / moonshine / cpu_align | `ileri.pyannote_konusmaci_ayrimi=true` | hata | bu motorlar konuşmacı ayırmaz |
| faster-whisper | `ileri.pyannote_konusmaci_ayrimi=true` | uyarı | ayrım yalnız whisperx / speechmatics / elevenlabs |
| `transkripsiyon.crisper_dil_tespiti` ≠ varsayılan | CrisperWhisper dışı motor | uyarı | etkisiz |
| `transkripsiyon.whisperx_profili` ≠ `auto` | motor ≠ `whisperx` | hata | profil yalnız WhisperX |
| `whisperx_float32_quality_v1` / `whisperx_engine_default_v1` | `hesap_tipi` ≠ float32 / int8 | hata | profil hesap tipine bağlı |
| `transkripsiyon.model=distil-*` | `kaynak_dil` İngilizce dışı | uyarı | distil yalnız İngilizce; hat çok dilli modele geçer |
| `video.politika=max_mb` | `video.max_mb=0` | hata | en az 1 MB |
| `video.politika=cq` | `video.max_mb>0` | uyarı | boyut sınırı yalnız max_mb politikasında |
| `ses_temizligi.kip=clean`/`preserve_background` | Demucs kurulu değil | hata (başlarken) | `pip install .[separation]` ya da `original` |

Kendiliğinden düzeltilenler (hata değil): sabit sözleşmeli transkripsiyon motorları (crisperwhisper, moonshine,
whisper_cpp, parakeet, speechmatics, elevenlabs) kendi model ve hesap tipini kullanır, `transkripsiyon.model` /
`hesap_tipi` yalnız faster-whisper ve whisperx'te geçerlidir; `full_text` kipinde `ses.atempo` uygulanmaz;
`ses.motor=voxcpm2` iken cinsiyet tahmini yapılmaz (konuşmacı başına ses `ses.konusmaci_sesleri` ile verilir).

### İnce ayar rehberi

| Ne istiyorsunuz | Anahtar | Not |
|---|---|---|
| Daha doğru kelime zamanı | `transkripsiyon.motor=crisperwhisper_turbo_ct2` | GPU; `auto` kuruluysa bunu seçer |
| Daha doğal çeviri | `ceviri.arka_uc=codex` ya da `claude_code`; `ses.akis=natural_blocks_1` | kendi hesabınız |
| Çeviri süreye daha iyi sığsın | `ses.akis=repair_3_light` … `repair_7` | daha çok LLM çağrısı, daha uzun sürer |
| Konuşma daha yavaş/hızlı | `ses.hiz` (0.5–2.0) | Supertonic |
| Seslendirme kaynak süreye sığmıyor | `ses.atempo=true` | ffmpeg ile hızlandırır |
| Altyazı biçimi | `altyazi.mod` = segment / word / rollup / none | videoya yakılır |
| Dosya boyutu sınırı | `video.politika=max_mb`, `video.max_mb=179` | 1 MB = 1 000 000 bayt |
| Daha iyi görüntü kalitesi | `video.cq` (düşük = iyi; 23 yüksek, 26 dengeli, 30 küçük) | `politika=cq` |
| Tam metin kipinde süre | `video.tam_metin_sure_uyumu` = audio_to_video / video_to_audio | yalnız full_text |
| Ayrıntılı günlük | `genel.gunluk_seviyesi=DEBUG` ya da `--ayrintili` | |
