# Languages

[Türkçe](#türkçe) · Code: `src/dublaj_hatti/kayit.py` (`SUPERTONIC_DILLERI`, `VOXCPM2_DENENEN_DILLER`,
`XTTS_DILLERI`, `tts_dil_suzgeci()`), rules: `yapilandirma.uyumluluk_denetle()`. Tests compare these lists with the
engine source (`tests/test_dil_ses_donanim.py`, `tests/test_kombinasyon.py`).

## Target language (dubbing) per speech engine

The target-language list in the desktop and web *Advanced* tab is **filtered by the selected `ses.motor`** (with `auto`, the languages that Supertonic or VoxCPM2 can read). A language
an engine cannot read is rejected when settings load (`ayar hatası ... dilini okuyamaz`), on the command line too.

| Code | Language | Supertonic 3 | VoxCPM2 | XTTS v2 | Local Opus-MT |
|---|---|---|---|---|---|
| `ar` | Arabic | yes | untested (warning) | yes | — |
| `bg` | Bulgarian | yes | untested (warning) | — | — |
| `cs` | Czech | yes | untested (warning) | yes | — |
| `da` | Danish | yes | untested (warning) | — | — |
| `de` | German | yes | tested | yes | — |
| `el` | Greek | yes | untested (warning) | — | — |
| `en` | English | yes | tested | yes | — |
| `es` | Spanish | yes | tested | yes | — |
| `et` | Estonian | yes | untested (warning) | — | — |
| `fi` | Finnish | yes | untested (warning) | — | — |
| `fr` | French | yes | tested | yes | — |
| `hi` | Hindi | yes | untested (warning) | yes | — |
| `hr` | Croatian | yes | untested (warning) | — | — |
| `hu` | Hungarian | yes | untested (warning) | yes | — |
| `id` | Indonesian | yes | untested (warning) | — | — |
| `it` | Italian | yes | untested (warning) | yes | — |
| `ja` | Japanese | yes | tested | yes | — |
| `ko` | Korean | yes | untested (warning) | yes | — |
| `lt` | Lithuanian | yes | untested (warning) | — | — |
| `lv` | Latvian | yes | untested (warning) | — | — |
| `nl` | Dutch | yes | untested (warning) | yes | — |
| `pl` | Polish | yes | untested (warning) | yes | — |
| `pt` | Portuguese | yes | untested (warning) | yes | — |
| `ro` | Romanian | yes | untested (warning) | — | — |
| `ru` | Russian | yes | tested | yes | — |
| `sk` | Slovak | yes | untested (warning) | — | — |
| `sl` | Slovenian | yes | untested (warning) | — | — |
| `sv` | Swedish | yes | untested (warning) | — | — |
| `tr` | Turkish | yes | tested | yes | en → tr |
| `uk` | Ukrainian | yes | untested (warning) | — | — |
| `vi` | Vietnamese | yes | untested (warning) | — | — |
| `zh` | Chinese | — | tested | yes (`zh-cn`) | — |

32 target languages in total. Sources:

- **Supertonic 3** — 31 languages: `AVAILABLE_LANGS` in `bolum_50_seslendirme/supertonic_tts/runtime.py` (code
  constant of the official model; `na` is the engine's "unknown" fallback and is not offered). Per docs.
- **VoxCPM2** — "tested" = read end to end in the sister voice-design repository (docs/cok_dilli.md there): tr, en, fr,
  de, es, ru, zh, ja (measured). Other languages are allowed with a warning; listen to the result.
- **EMA Lightning** — Turkish only (`tr`, model card "Limitations"; `EMA_DILLERI` in `kayit.py`). Any other target
  language is a settings error. Per docs; Turkish measured end to end in this repository.
- **XTTS v2** — 17 languages from the model card (huggingface.co/coqui/XTTS-v2), `XTTS_DILLERI` in
  `bolum_50_seslendirme/xtts_tts/api.py`. Per docs.
- **Translation.** Local Opus-MT translates **English → Turkish only** (`yerel_ceviri`, model
  Helsinki-NLP/opus-mt-tc-big-en-tr). LLM back ends (Codex, Claude Code, API back ends) have no language whitelist in
  code; see the table below for their status. `full_text` mode needs Codex or Claude Code.

## Translation target language with LLM back ends

Prompts are language-independent templates with a per-language appendix
([ADR 0014](adr/0014-language-independent-translation-prompts.md)); the returned text is checked for the target language and a
mismatch is a retryable error.

| Target | Prompt rules | Speech-rate estimate | Status |
|---|---|---|---|
| `tr` | original Turkish prompts (byte-identical) | 0.43 s/word, measured | proven in production |
| `en`, `de`, `fr`, `es`, `it`, `pt`, `ru`, `ar` | general + own appendix | per-word estimate | not yet tried with a real LLM |
| `ja`, `zh` | general + own appendix | per-character estimate | not yet tried with a real LLM |
| `ko`, `th` | general appendix | per-character estimate | not yet tried with a real LLM |
| any other code | general appendix | 0.43 s/word (default) | not yet tried with a real LLM |

Regional codes are normalised (`pt-BR` → `pt`, `zh-TW` → `zh`); the appendix then uses the default variant
(Simplified Chinese for `zh`).

### Adding a language appendix

1. Create `src/dublaj_hatti/bolum_40_ceviri/dil_ekleri/<code>.md`. Text before the first `## ` heading is a comment for
   sources and status and is not sent to the model.
2. Write `## genel` (number and decimal reading, dates, technical IDs, forms of address, punctuation, script). The
   prompt language of the appendices is Turkish, like the prompt bodies; examples go in backticks and are synthetic.
3. Optional sections override `_genel.md` sections of the same name for prompt blocks marked `ek=KEY`
   (e.g. `## sayi_tarih_ornegi` with one valid and one forbidden example). An empty section removes the block.
4. Add a `KONUSMA_HIZI` row in `llm_kopru/scripts/hedef_dil.py` with its source, and copy the file byte-identically to
   `claude_code_cli/scripts/hedef_dil.py`. If the language uses its own function words or script, extend the
   output-language profiles there as well.
5. Run `pytest tests/test_ceviri_hedef_dil.py`: Turkish golden hashes, leftover placeholders, appendix selection and the
   output-language check for correct sample sentences of the new language.

## Source language (transcription)

| Engine | Source languages | Evidence |
|---|---|---|
| `faster-whisper`, `faster_whisper_ctc`, `whisperx` (large-v3-turbo) | multilingual (Whisper model card); `distil-*` models English only | per docs |
| `crisperwhisper_turbo_ct2` | Whisper languages; real audio run: tr, en, ja; production-accepted en, zh, ja | measured |
| `parakeet_cpu_align` | English only (settings error otherwise; Parakeet falls back to WhisperX) | per docs |
| `youtube_translate` | the video's caption track (its own language, then `en`) | per docs |

How the source language is detected (first window, per window, code-switching, change point, fixed):
[docs/tarifler/dil_tespiti.md](tarifler/dil_tespiti.md).

**Word alignment (CTC).** Engines that use CTC (see [engineering/timing-sources.md](engineering/timing-sources.md);
not plain `faster-whisper`) get word times from a wav2vec2 CTC
model chosen by language: `en` torchaudio WAV2VEC2_ASR_BASE_960H, `tr` mpoyraz/wav2vec2-xls-r-300m-cv7-turkish (pinned in
`scripts/modeller.json`), `id` Galuh/wav2vec2-large-xlsr-indonesian, others WhisperX defaults
(`bolum_30_hizalama_ve_segment/ctc_kelime_hizalama/worker.py`). A language without a CTC model cannot be aligned. Only `en` and `tr` are installed by `scripts/kur.ps1 -Adim modeller`; `ja` and `zh` by the optional `-Adim hizalama-diller`; for another language run once with `DUBLAJ_CEVRIMICI=1` (otherwise `faster_whisper_ctc`, the `auto` fallback, stops with this instruction right after language detection). Every Hugging Face CTC model loads from a pinned commit (`ctc_model_durumu.HF_CTC_SURUMLERI`), never from the Hub's moving "main". The WhisperX defaults for `fr`, `de`, `es`, `it` are VoxPopuli models under CC BY-NC 4.0 (non-commercial).

---

## Türkçe

Kod: `src/dublaj_hatti/kayit.py` (`SUPERTONIC_DILLERI`, `VOXCPM2_DENENEN_DILLER`, `XTTS_DILLERI`, `tts_dil_suzgeci()`),
kurallar: `yapilandirma.uyumluluk_denetle()`. Testler bu listeleri motor kaynağıyla karşılaştırır
(`tests/test_dil_ses_donanim.py`, `tests/test_kombinasyon.py`).

### Ses motoruna göre hedef dil (dublaj)

Masaüstü ve web *Gelişmiş* sekmesindeki hedef dil listesi **seçili `ses.motor`'a göre süzülür** (`auto` iken Supertonic ya da VoxCPM2'nin okuyabildiği diller). Motorun okuyamadığı
dil, ayarlar yüklenirken reddedilir (`ayar hatası ... dilini okuyamaz`); komut satırında da.

| Kod | Dil | Supertonic 3 | VoxCPM2 | XTTS v2 | Yerel Opus-MT |
|---|---|---|---|---|---|
| `ar` | Arapça | evet | denenmedi (uyarı) | evet | — |
| `bg` | Bulgarca | evet | denenmedi (uyarı) | — | — |
| `cs` | Çekçe | evet | denenmedi (uyarı) | evet | — |
| `da` | Danca | evet | denenmedi (uyarı) | — | — |
| `de` | Almanca | evet | denendi | evet | — |
| `el` | Yunanca | evet | denenmedi (uyarı) | — | — |
| `en` | İngilizce | evet | denendi | evet | — |
| `es` | İspanyolca | evet | denendi | evet | — |
| `et` | Estonca | evet | denenmedi (uyarı) | — | — |
| `fi` | Fince | evet | denenmedi (uyarı) | — | — |
| `fr` | Fransızca | evet | denendi | evet | — |
| `hi` | Hintçe | evet | denenmedi (uyarı) | evet | — |
| `hr` | Hırvatça | evet | denenmedi (uyarı) | — | — |
| `hu` | Macarca | evet | denenmedi (uyarı) | evet | — |
| `id` | Endonezce | evet | denenmedi (uyarı) | — | — |
| `it` | İtalyanca | evet | denenmedi (uyarı) | evet | — |
| `ja` | Japonca | evet | denendi | evet | — |
| `ko` | Korece | evet | denenmedi (uyarı) | evet | — |
| `lt` | Litvanca | evet | denenmedi (uyarı) | — | — |
| `lv` | Letonca | evet | denenmedi (uyarı) | — | — |
| `nl` | Felemenkçe | evet | denenmedi (uyarı) | evet | — |
| `pl` | Lehçe | evet | denenmedi (uyarı) | evet | — |
| `pt` | Portekizce | evet | denenmedi (uyarı) | evet | — |
| `ro` | Rumence | evet | denenmedi (uyarı) | — | — |
| `ru` | Rusça | evet | denendi | evet | — |
| `sk` | Slovakça | evet | denenmedi (uyarı) | — | — |
| `sl` | Slovence | evet | denenmedi (uyarı) | — | — |
| `sv` | İsveççe | evet | denenmedi (uyarı) | — | — |
| `tr` | Türkçe | evet | denendi | evet | en → tr |
| `uk` | Ukraynaca | evet | denenmedi (uyarı) | — | — |
| `vi` | Vietnamca | evet | denenmedi (uyarı) | — | — |
| `zh` | Çince | — | denendi | evet (`zh-cn`) | — |

Toplam 32 hedef dil. Kaynaklar:

- **Supertonic 3** — 31 dil (`zh` yok): `bolum_50_seslendirme/supertonic_tts/runtime.py` içindeki `AVAILABLE_LANGS`
  (resmî modelin kod sabiti; `na` motorun "bilinmeyen" yedeğidir ve sunulmaz). Belgeye göre.
- **VoxCPM2** — "denendi" = kardeş ses tasarımı reposunda baştan sona okutuldu (oradaki docs/cok_dilli.md): tr, en,
  fr, de, es, ru, zh, ja (ölçüldü). Diğer diller uyarıyla seçilebilir; sonucu dinleyin.
- **EMA Lightning** — yalnız Türkçe (`tr`, model kartı "Limitations"; `kayit.py` içinde `EMA_DILLERI`). Başka hedef
  dil ayar hatasıdır. Belgeye göre; Türkçe bu repoda uçtan uca ölçüldü.
- **XTTS v2** — model kartındaki 17 dil (huggingface.co/coqui/XTTS-v2), `bolum_50_seslendirme/xtts_tts/api.py`
  içinde `XTTS_DILLERI`. Belgeye göre.
- **Çeviri.** Yerel Opus-MT **yalnız İngilizce → Türkçe** çevirir (`yerel_ceviri`, model
  Helsinki-NLP/opus-mt-tc-big-en-tr). LLM arka uçlarının (Codex, Claude Code, API arka uçları) kodda dil beyaz
  listesi yoktur; durumları için aşağıdaki tabloya bakın. `full_text` kipi Codex ya da Claude Code ister.

### LLM arka uçlarıyla çeviri hedef dili

İstemler, dile özgü bir ek alan dilden bağımsız şablonlardır
([ADR 0014](adr/0014-language-independent-translation-prompts.md)); dönen metnin hedef dilde olduğu denetlenir,
uyuşmazlık yeniden denenebilir bir hatadır.

| Hedef | İstem kuralları | Konuşma hızı tahmini | Durum |
|---|---|---|---|
| `tr` | özgün Türkçe istemler (bayt bayt aynı) | 0.43 s/kelime, ölçüldü | üretimde kanıtlı |
| `en`, `de`, `fr`, `es`, `it`, `pt`, `ru`, `ar` | genel + kendi eki | kelime başına tahmin | gerçek bir LLM ile henüz denenmedi |
| `ja`, `zh` | genel + kendi eki | karakter başına tahmin | gerçek bir LLM ile henüz denenmedi |
| `ko`, `th` | genel ek | karakter başına tahmin | gerçek bir LLM ile henüz denenmedi |
| başka herhangi bir kod | genel ek | 0.43 s/kelime (varsayılan) | gerçek bir LLM ile henüz denenmedi |

Bölgesel kodlar sadeleştirilir (`pt-BR` → `pt`, `zh-TW` → `zh`); ek bu durumda varsayılan türü kullanır
(`zh` için Basitleştirilmiş Çince).

#### Dil eki ekleme

1. `src/dublaj_hatti/bolum_40_ceviri/dil_ekleri/<code>.md` dosyasını oluşturun. İlk `## ` başlığından önceki metin
   kaynak ve durum için bir yorumdur, modele gönderilmez.
2. `## genel` yazın (sayı ve ondalık okunuşu, tarihler, teknik kimlikler, hitap biçimleri, noktalama, yazı sistemi).
   Eklerin istem dili, istem gövdeleri gibi Türkçedir; örnekler ters tırnak içinde ve sentetiktir.
3. İsteğe bağlı bölümler, `ek=KEY` ile işaretli istem blokları için `_genel.md` içindeki aynı adlı bölümlerin yerine
   geçer (ör. bir geçerli ve bir yasak örnekle `## sayi_tarih_ornegi`). Boş bölüm bloğu kaldırır.
4. `llm_kopru/scripts/hedef_dil.py` içine kaynağıyla birlikte bir `KONUSMA_HIZI` satırı ekleyin ve dosyayı bayt bayt
   `claude_code_cli/scripts/hedef_dil.py` içine kopyalayın. Dil kendine özgü işlev sözcükleri ya da yazı sistemi
   kullanıyorsa oradaki çıktı dili profillerini de genişletin.
5. `pytest tests/test_ceviri_hedef_dil.py` çalıştırın: Türkçe altın özetler, kalan yer tutucular, ek seçimi ve yeni
   dilin doğru örnek cümleleri için çıktı dili denetimi.

### Kaynak dil (transkripsiyon)

| Motor | Kaynak diller | Kanıt |
|---|---|---|
| `faster-whisper`, `faster_whisper_ctc`, `whisperx` (large-v3-turbo) | çok dilli (Whisper model kartı); `distil-*` modelleri yalnız İngilizce | belgeye göre |
| `crisperwhisper_turbo_ct2` | Whisper dilleri; gerçek ses koşusu: tr, en, ja; üretimde kabul edilen en, zh, ja | ölçüldü |
| `parakeet_cpu_align` | yalnız İngilizce (aksi ayar hatası; Parakeet WhisperX'e geçer) | belgeye göre |
| `youtube_translate` | videonun altyazı izi (kendi dili, sonra `en`) | belgeye göre |

Kaynak dilin nasıl tespit edildiği (ilk pencere, pencere başına, kod değişimi, değişim noktası, sabit):
[docs/tarifler/dil_tespiti.md](tarifler/dil_tespiti.md).

**Kelime hizalama (CTC).** CTC kullanan motorlar ([engineering/timing-sources.md](engineering/timing-sources.md);
düz `faster-whisper` değil) kelime zamanlarını dile göre seçilen
bir wav2vec2 CTC modelinden alır: `en` torchaudio WAV2VEC2_ASR_BASE_960H, `tr` mpoyraz/wav2vec2-xls-r-300m-cv7-turkish
(`scripts/modeller.json` içinde sabitlenmiş), `id` Galuh/wav2vec2-large-xlsr-indonesian, diğerleri WhisperX
varsayılanları (`bolum_30_hizalama_ve_segment/ctc_kelime_hizalama/worker.py`). CTC modeli olmayan dil hizalanamaz.
`scripts/kur.ps1 -Adim modeller` yalnız `en` ve `tr` modellerini kurar; `ja` ve `zh` isteğe bağlı `-Adim hizalama-diller`
ile kurulur; başka dil için bir kez `DUBLAJ_CEVRIMICI=1` ile çalıştırın (yoksa `auto`'nun yedeği `faster_whisper_ctc`
bu talimatla dil tespitinden hemen sonra durur). Her Hugging Face CTC modeli sabit bir commit'ten yüklenir
(`ctc_model_durumu.HF_CTC_SURUMLERI`), Hub'daki değişen "main"den asla. WhisperX'in `fr`, `de`, `es`, `it` varsayılanları VoxPopuli modelleridir,
CC BY-NC 4.0 (ticari olmayan).
