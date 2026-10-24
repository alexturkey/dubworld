# XTTS v2 (reference-voice TTS) (`xtts`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** A TTS engine option: speaks in 17 languages (tr included) with the timbre of the short **reference
voice** you provide. Each sentence is generated in 150-character pieces in a separate process (coqui-tts); when the
job ends, the model memory is released.

| | |
|---|---|
| License | code: coqui-tts MPL-2.0; **weights: Coqui Public Model License (CPML) — non-commercial use only**; output is subject to the CPML |
| Source | https://huggingface.co/coqui/XTTS-v2 , license https://coqui.ai/cpml |
| Install | recommended: `scripts/kur.ps1 -Adim tts-xtts -TicariOlmayanKabul` (separate virtual environment, hash-locked lock files including torch `requirements/xtts_venv_gpu.txt` / `xtts_venv_cpu.txt`, writes `DUBLAJ_XTTS_PYTHON` to `.env`); or `pip install .[tts-xtts]` into the same environment + licence acceptance |
| Hardware | NVIDIA GPU recommended (~4 GB VRAM, estimate); works on the CPU but very slowly |
| Default | off |

**Licence acceptance:** The weights are not in the repository and are not downloaded automatically. Acceptance:
`python -m dublaj_hatti.bolum_50_seslendirme.xtts_tts onay` (read the text and type `kabul ediyorum`). The acceptance is
written to the local `runtime_assets/tts_motorlari/xtts/CPML_ONAYI.json` file with only the date and the licence
address; the weights are downloaded on first use by Coqui's own downloader into the same folder. Status: `... xtts_tts durum`.

**Reference voice:** Only your own voice or a voice used with its owner's explicit permission (6-15 s, clean
recording). The repository contains no real person's voice; imitating a celebrity or a real person without permission
is forbidden (ETHICS.md).

**Setting:** `ses.motor = "xtts"`, `DubConfig.xtts_referans_ses = <wav path>` (settings-file key
`ses.xtts_referans_ses` once it is added to the settings layer). If the target language is not in the XTTS list, it
fails with an explicit error.

**Common errors**
- `XTTS v2 kurulu değil` → `pip install .[tts-xtts]`; if dependencies conflict, a separate virtual environment + `DUBLAJ_XTTS_PYTHON`.
- `CPML` acceptance error → the acceptance command.
- `referans ses gerekli` → give a wav path in the settings.

## How it works in this pipeline / Neden böyle

- **Principle:** XTTS v2 extracts speaker conditioning from the reference recording and generates the text
  autoregressively in that timbre. The text is prepared first: abbreviations, ordinal numbers and quoted text are
  kept, in-sentence punctuation is turned into commas (sentence-final punctuation was breaking the model's
  intonation), and the text is split into pieces of at most 150 characters. The pieces are joined with 50 ms of
  silence. The seed is fixed, so the same input is repeatable on the same runner.
- **Why a separate environment and a separate process:** in an earlier version of the pipeline, the Coqui TTS package
  pinned the main environment to an old torch / CUDA 11.8 / numpy 1.22 combination; so coqui-tts is installed either as
  an extra or in a separate environment with `DUBLAJ_XTTS_PYTHON`. In the earlier version the model ran inside the
  long-lived process and released memory only with `del` + `empty_cache()`; now the runner (`xtts_tts/kosucu.py`) is a
  separate subprocess that imports nothing from the package, and all memory is released when it exits
  ([ADR 0001](../adr/0001-one-gpu-job-and-process-per-model.md)).
- **Why it is not the default:** the weights are CPML (non-commercial) licensed and need explicit acceptance; a
  reference voice is mandatory (your own voice or the owner's permission); a GPU is needed for usable speed. The
  default is Supertonic ([ADR 0015](../adr/0015-tts-engine-set-and-default.md), [ADR 0017](../adr/0017-defaults-and-licence-gate.md)).
- **Duration fit and atempo:** XTTS has no candidate selection, repair round or `atempo`. The syllable-based speed
  normalisation of the earlier version was not carried over. The real duration of each segment is measured in the
  shared execution layer, the segment is placed at its start time, and video retiming absorbs the remaining difference
  ([ADR 0010](../adr/0010-real-tts-duration-is-canonical.md)).
  If subtitles are requested, the final dub track is aligned with CTC.
- **How it fits:** the result contract is the same as Supertonic (segment WAV → trim, sample rate, measurement, mix).
  If a segment cannot be generated, the job stops; it is not silently skipped ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)).
  This repository has no speed or VRAM measurement for XTTS.
- Details: [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) §8
- Place in the end-to-end flow: [pipeline-flow.md, branch table](../engineering/pipeline-flow.md#5-branches-what-a-choice-changes)

## Türkçe

**XTTS v2 (`xtts`)**

**Ne yapar:** TTS motoru seçeneği: verdiğiniz kısa **referans sesin** tınısıyla 17 dilde (tr dahil) seslendirir.
Her cümle 150 karakterlik parçalarla, ayrı bir süreçte (coqui-tts) üretilir; iş bitince model belleği boşalır.

| | |
|---|---|
| Lisans | kod: coqui-tts MPL-2.0; **ağırlık: Coqui Public Model License (CPML) — yalnız ticari olmayan kullanım**; çıktı CPML'e tabi |
| Kaynak | https://huggingface.co/coqui/XTTS-v2 , lisans https://coqui.ai/cpml |
| Kurulum | önerilen: `scripts/kur.ps1 -Adim tts-xtts -TicariOlmayanKabul` (ayrı sanal ortam, torch dahil hash'li kilit `requirements/xtts_venv_gpu.txt` / `xtts_venv_cpu.txt`, `.env`'e `DUBLAJ_XTTS_PYTHON` yazar); ya da aynı ortama `pip install .[tts-xtts]` + lisans onayı |
| Donanım | NVIDIA GPU önerilir (~4 GB VRAM, tahmini); işlemcide çalışır ama çok yavaş |
| Varsayılan | kapalı |

**Lisans onayı:** Ağırlık repoda yoktur, otomatik indirilmez. Onay:
`python -m dublaj_hatti.bolum_50_seslendirme.xtts_tts onay` (metni okuyup `kabul ediyorum` yazın). Onay yerel
`runtime_assets/tts_motorlari/xtts/CPML_ONAYI.json` dosyasına yalnız tarih ve lisans adresiyle yazılır; ağırlık
ilk kullanımda Coqui'nin kendi indiricisiyle aynı klasöre iner. Durum: `... xtts_tts durum`.

**Referans ses:** Yalnız kendi sesiniz ya da sahibinin açık izniyle bir ses (6-15 sn, temiz kayıt). Repoda hiçbir
gerçek kişi sesi yoktur; ünlü ya da gerçek kişiyi izinsiz taklit yasaktır (ETHICS.md).

**Ayar:** `ses.motor = "xtts"`, `DubConfig.xtts_referans_ses = <wav yolu>` (ayar dosyası anahtarı
`ses.xtts_referans_ses` ayar katmanına eklenince). Hedef dil XTTS listesinde değilse açık hata verir.

**Sık hata**
- `XTTS v2 kurulu değil` → `pip install .[tts-xtts]`; bağımlılık çakışırsa ayrı sanal ortam + `DUBLAJ_XTTS_PYTHON`.
- `CPML` onay hatası → onay komutu.
- `referans ses gerekli` → ayara wav yolu verin.

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** XTTS v2, referans kayıttan konuşmacı koşullamasını çıkarır ve metni bu tınıyla otoregresif olarak üretir.
  Metin önce hazırlanır: kısaltma, sıra sayısı ve tırnak içi korunur, cümle içi noktalama virgüle çevrilir (cümle sonu
  noktalama modelin tonlamasını bozuyordu), metin en çok 150 karakterlik parçalara bölünür. Parçalar 50 ms sessizlikle
  birleştirilir. Tohum sabittir, böylece aynı girdi aynı koşucuda tekrarlanabilir.
- **Neden ayrı ortam ve ayrı süreç:** Coqui TTS paketi, hattın önceki sürümünde ana ortamı eski bir torch / CUDA 11.8 /
  numpy 1.22 birleşimine sabitliyordu; bu nedenle coqui-tts ya bir ek olarak ya da `DUBLAJ_XTTS_PYTHON` ile ayrı bir
  ortamda kurulur. Önceki sürümde model uzun yaşayan sürecin içinde çalışıp belleği yalnız `del` + `empty_cache()` ile
  bırakıyordu; şimdi koşucu (`xtts_tts/kosucu.py`) paketten hiçbir şey içe aktarmayan ayrı bir alt süreçtir ve çıkınca
  belleğin tamamı boşalır ([ADR 0001](../adr/0001-one-gpu-job-and-process-per-model.md)).
- **Neden varsayılan değil:** ağırlıklar CPML (ticari olmayan) lisanslıdır ve açık onay ister; referans ses zorunludur
  (kendi sesiniz ya da sahibinin izni); kullanılabilir hız için GPU gerekir. Varsayılan Supertonic'tir
  ([ADR 0015](../adr/0015-tts-engine-set-and-default.md), [ADR 0017](../adr/0017-defaults-and-licence-gate.md)).
- **Süre uydurma ve atempo:** XTTS'te aday seçimi, onarım turu ve `atempo` yoktur. Önceki sürümdeki hece tabanlı hız
  normalizasyonu taşınmadı. Her segmentin gerçek süresi ortak yürütme katmanında ölçülür, segment başlangıç zamanına
  yerleştirilir, kalan farkı video yeniden zamanlaması karşılar ([ADR 0010](../adr/0010-real-tts-duration-is-canonical.md)).
  Altyazı istenirse son dublaj izi CTC ile hizalanır.
- **Diğer parçalarla ahengi:** sonuç sözleşmesi Supertonic ile aynıdır (segment WAV'ı → kırpma, örnekleme hızı, ölçüm,
  karışım). Bir segment üretilemezse iş durur; sessizce atlanmaz ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)).
  Bu repoda XTTS için hız ve VRAM ölçümü yoktur.
- Ayrıntı: [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) §8
- Uçtan uca akıştaki yeri: [hat_akisi.md, dallanma tablosu](../muhendislik/hat_akisi.md#5-dallanmalar-bir-seçim-neyi-değiştirir)
