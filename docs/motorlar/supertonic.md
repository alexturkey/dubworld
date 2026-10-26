# Supertonic 3 (`supertonic`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Default text-to-speech: ONNX on the CPU, ten built-in voice styles (F1..F5, M1..M5), natural-blocks flow, sentence-by-sentence synthesis with timing fit (atempo).

| | |
|---|---|
| License | BigScience Open RAIL-M (use restrictions, Attachment A) |
| Commercial use | conditional (allowed within the use restrictions) |
| Source | https://huggingface.co/Supertone/supertonic-3 (pinned commit + sha256) |
| Install | base install (step `modeller`) |
| Hardware | CPU, 4 lanes × 2 threads, ~2.3× real time, ~1.8 GB RAM (measured); the CUDA provider was slower and is not used |
| Languages | 31 (no `zh`), [diller.md](../diller.md) |
| Default | `ses.motor = auto`: Supertonic unless VoxCPM2 is installed and an NVIDIA GPU is usable |

**Settings**

- `ses.supertonic_ses` (one voice), `ses.konusmaci_cinsiyetine_gore_ses`, `ses.cinsiyet_kipi`, `ses.kadin_ses`, `ses.erkek_ses`, `ses.konusmaci_sesleri.<SPEAKER>`
- `ses.akis` (`natural_blocks_1` default; `single_pass_*`, `repair_*` with LLM backends), `ses.hiz` (one rate for every voice), `ses.atempo`

**Common errors**

- `Supertonic '<x>' dilini okuyamaz` → choose a supported language or `voxcpm2`.
- Unknown voice name → only F1..F5 and M1..M5 exist.
- First use shows the conditional-license notice (use restrictions).

**Related:** [sesler.md](../sesler.md) · [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) · [diller.md](../diller.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** ONNX text-to-speech on the CPU: a duration predictor runs once, the target length is the predicted length
  divided by the voice's fixed speed, a latent is generated with 10 Euler steps (7 at normal length, linear
  interpolation to the target length, 3 more) with CFG 5, and a vocoder renders it. Frames that are neither speech nor
  silence are replaced by one canonical silence latent before a second vocoder pass. The seed is a hash of language,
  voice, steps and text.
- **Why this choice:** it is the default because it runs on any machine without a GPU, its licence allows the
  repository to point to it, and the timing layer (candidates, repair rounds, `atempo`) was built and measured on it
  ([ADR 0015](../adr/0015-tts-engine-set-and-default.md), [ADR 0017](../adr/0017-defaults-and-licence-gate.md)). In-model
  speed is fixed per voice because changing it changed what the model said
  ([ADR 0010](../adr/0010-real-tts-duration-is-canonical.md)). The CUDA provider was slower than 4 CPU lanes × 2 threads.
- **How it fits:** one worker subprocess per request and voice group (a long-lived pool had grown past physical RAM);
  output 44.1 kHz; the execution layer measures the real duration, CTC aligns candidates, optional `atempo` stays in
  0.90–1.25 and the video absorbs the rest. Voice per speaker comes from speaker separation and gender, or from an
  explicit map.
- Details: [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) §1–§4 · [speakers_and_segments.md](../engineering/speakers_and_segments.md) §3
- Place in the end-to-end flow: [pipeline-flow.md, branch table](../engineering/pipeline-flow.md#5-branches-what-a-choice-changes)

## Türkçe

**Ne yapar:** Varsayılan metinden sese (TTS): işlemcide ONNX, on yerleşik ses stili (F1..F5, M1..M5), doğal bloklar akışı, süre uydurmalı (atempo) cümle cümle sentez.

| | |
|---|---|
| Lisans | BigScience Open RAIL-M (kullanım kısıtları, Ek A) |
| Ticari kullanım | şartlı (kullanım kısıtları içinde izinli) |
| Kaynak | https://huggingface.co/Supertone/supertonic-3 (sabit commit + sha256) |
| Kurulum | temel kurulum (adım `modeller`) |
| Donanım | işlemci, 4 hat × 2 iş parçacığı, ~2.3× gerçek zaman, ~1.8 GB RAM (ölçüldü); CUDA sağlayıcısı daha yavaştı ve kullanılmaz |
| Diller | 31 (`zh` yok), [diller.md](../diller.md) |
| Varsayılan | `ses.motor = auto`: VoxCPM2 kurulu ve NVIDIA GPU çalışır değilse Supertonic |

**Ayarlar**

- `ses.supertonic_ses` (tek ses), `ses.konusmaci_cinsiyetine_gore_ses`, `ses.cinsiyet_kipi`, `ses.kadin_ses`, `ses.erkek_ses`, `ses.konusmaci_sesleri.<SPEAKER>`
- `ses.akis` (varsayılan `natural_blocks_1`; LLM arka uçlarıyla `single_pass_*`, `repair_*`), `ses.hiz` (her ses için tek hız), `ses.atempo`

**Sık hatalar**

- `Supertonic '<x>' dilini okuyamaz` → desteklenen bir dil ya da `voxcpm2` seçin.
- Bilinmeyen ses adı → yalnız F1..F5 ve M1..M5 vardır.
- İlk kullanımda şartlı lisans bildirimi (kullanım kısıtları) gösterilir.

**İlgili:** [sesler.md](../sesler.md) · [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) · [diller.md](../diller.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** işlemcide ONNX metinden sese: süre tahmincisi bir kez çalışır, hedef uzunluk tahmin edilen uzunluğun sesin
  sabit hızına bölümüdür, CFG 5 ile 10 Euler adımında bir gizil temsil üretilir (normal uzunlukta 7 adım, hedef
  uzunluğa doğrusal ara değerleme, 3 adım daha) ve bir vocoder bunu sese çevirir. Ne konuşma ne sessizlik olan kareler,
  ikinci vocoder geçişinden önce tek bir standart sessizlik gizil temsiliyle değiştirilir. Tohum dil, ses, adım sayısı
  ve metnin özetidir (hash).
- **Neden bu seçim:** GPU'suz her makinede çalıştığı, lisansı reponun ona yönlendirmesine izin verdiği ve zamanlama
  katmanı (adaylar, onarım turları, `atempo`) onun üzerinde kurulup ölçüldüğü için varsayılandır
  ([ADR 0015](../adr/0015-tts-engine-set-and-default.md), [ADR 0017](../adr/0017-defaults-and-licence-gate.md)). Model içi
  hız ses başına sabittir, çünkü onu değiştirmek modelin söylediği şeyi değiştirdi
  ([ADR 0010](../adr/0010-real-tts-duration-is-canonical.md)). CUDA sağlayıcısı 4 işlemci hattı × 2 iş parçacığından yavaştı.
- **Diğer parçalarla ahengi:** istek ve ses grubu başına bir işçi alt süreci (uzun yaşayan bir havuz fiziksel RAM'i
  aşmıştı); çıktı 44.1 kHz; yürütme katmanı gerçek süreyi ölçer, CTC adayları hizalar, isteğe bağlı `atempo`
  0.90–1.25 içinde kalır ve kalanı video karşılar. Konuşmacı başına ses, konuşmacı ayrımı ve cinsiyetten ya da açık
  bir haritadan gelir.
- Ayrıntı: [tts_timing_and_mix.md](../engineering/tts_timing_and_mix.md) §1–§4 · [speakers_and_segments.md](../engineering/speakers_and_segments.md) §3
- Uçtan uca akıştaki yeri: [hat_akisi.md, dallanma tablosu](../muhendislik/hat_akisi.md#5-dallanmalar-bir-seçim-neyi-değiştirir)
