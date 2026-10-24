# CrisperWhisper 2.0 Medium, engine 12 (`crisperwhisper2_medium`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Verbatim transcription with the Transformers fp16 model and its own attention word times, in its own Python environment; supports per-window language detection for long multi-language videos.

| | |
|---|---|
| License | weights: **nyra health Non-Commercial Research License**; code MIT |
| Commercial use | **no** |
| Source | https://huggingface.co/nyralabs (model `CrisperWhisper2.0_medium`) |
| Install | manual: a separate Python environment for the engine folder `src/dublaj_hatti/bolum_20_transkripsiyon/crisperwhisper2_medium_motoru/` with its model snapshot; point the app to it with `DUBLAJ_CRISPERWHISPER_ROOT` and `DUBLAJ_CRISPERWHISPER_PYTHON` in `.env` |
| Hardware | NVIDIA GPU, fp16 3.5–3.6 GB VRAM (measured; fp32 does not fit 4 GB); CPU refused |
| Languages | Whisper languages; accepted in production: en, es, zh, ja |
| Default | off |

**Settings**

- `transkripsiyon.motor = "crisperwhisper2_medium"`
- `transkripsiyon.crisper_dil_tespiti`: `global_first_window`, `per_window` (Medium only), `continuous_stream`

**Common errors**

- Tightest VRAM margin of all engines: close every other GPU program first.
- Environment not found → the default engine folder is inside the package (`src/dublaj_hatti/bolum_20_transkripsiyon/crisperwhisper2_medium_motoru/`, its `.venv` and `model_cache/` go there); the installer does not create them. Create them there, or point to another folder with the two variables above.

**Related:** [crisperwhisper_turbo_ct2.md](../engineering/crisperwhisper_turbo_ct2.md) · [gpu_memory_and_isolation.md](../engineering/gpu_memory_and_isolation.md) · [dil_tespiti.md](../tarifler/dil_tespiti.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** the verbatim CrisperWhisper 2 Medium model on Transformers in fp16, run from its own Python
  environment; word times come from the model's own attention heads (one of the documented exceptions to the CTC rule,
  [ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)).
- **Why this choice:** it is the only engine with per-window language detection (`per_window`) for long videos that
  change language. fp16 is used only to fit (fp32 does not fit 4 GB), not for speed. Converting Medium to CTranslate2
  failed a strict word-and-time equality gate, so it stays on Transformers
  ([ADR 0004](../adr/0004-crisperwhisper-turbo-ct2-int8.md)).
- **How it fits:** tightest VRAM margin of all engines (3.5–3.6 GB); no leading pad; separate environment because its
  pins differ from the main environment; same transcript contract.
- Details: [crisperwhisper_turbo_ct2.md](../engineering/crisperwhisper_turbo_ct2.md) §1, §7 · [gpu_memory_and_isolation.md](../engineering/gpu_memory_and_isolation.md) §5

## Türkçe

Kayıt satırı: `src/dublaj_hatti/kayit.py` (kurulu olup olmadığını `dubla kontrol` gösterir)

**Ne yapar:** Transformers fp16 modeli ve modelin kendi dikkat (attention) kelime zamanlarıyla, kendi Python ortamında kelimesi kelimesine (verbatim) transkript; uzun ve çok dilli videolar için pencere başına dil tespitini destekler.

| | |
|---|---|
| Lisans | ağırlıklar: **nyra health Non-Commercial Research License** (ticari olmayan araştırma lisansı); kod MIT |
| Ticari kullanım | **hayır** |
| Kaynak | https://huggingface.co/nyralabs (model `CrisperWhisper2.0_medium`) |
| Kurulum | elle: motor klasörü `src/dublaj_hatti/bolum_20_transkripsiyon/crisperwhisper2_medium_motoru/` için model anlık görüntüsüyle (snapshot) birlikte ayrı bir Python ortamı; uygulamayı ona `.env` içindeki `DUBLAJ_CRISPERWHISPER_ROOT` ve `DUBLAJ_CRISPERWHISPER_PYTHON` ile yönlendirin |
| Donanım | NVIDIA GPU, fp16 3.5–3.6 GB VRAM (ölçüldü; fp32 4 GB'a sığmaz); CPU reddedilir |
| Diller | Whisper dilleri; üretimde kabul edilenler: en, es, zh, ja |
| Varsayılan | kapalı |

**Ayarlar**

- `transkripsiyon.motor = "crisperwhisper2_medium"`
- `transkripsiyon.crisper_dil_tespiti`: `global_first_window`, `per_window` (yalnız Medium), `continuous_stream`

**Sık hatalar**

- Bütün motorlar içinde en dar VRAM payı: önce diğer bütün GPU programlarını kapatın.
- Ortam bulunamadı → varsayılan motor klasörü paketin içindedir (`src/dublaj_hatti/bolum_20_transkripsiyon/crisperwhisper2_medium_motoru/`; `.venv` ve `model_cache/` oraya gider); kurulum betiği bunları oluşturmaz. Onları orada oluşturun ya da yukarıdaki iki değişkenle başka bir klasörü gösterin.

**İlgili:** [crisperwhisper_turbo_ct2.md](../engineering/crisperwhisper_turbo_ct2.md) · [gpu_memory_and_isolation.md](../engineering/gpu_memory_and_isolation.md) · [dil_tespiti.md](../tarifler/dil_tespiti.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** kelimesi kelimesine çalışan CrisperWhisper 2 Medium modeli, Transformers üzerinde fp16 olarak, kendi Python
  ortamından çalışır; kelime zamanları modelin kendi dikkat başlıklarından gelir (CTC kuralının belgelenmiş
  istisnalarından biri, [ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)).
- **Neden bu seçim:** dil değiştiren uzun videolar için pencere başına dil tespiti (`per_window`) yapan tek motordur.
  fp16 hız için değil, yalnız sığmak için kullanılır (fp32 4 GB'a sığmaz). Medium'u CTranslate2'ye dönüştürmek katı bir
  kelime-ve-zaman eşitliği kapısından geçemedi, bu yüzden Transformers üzerinde kalır
  ([ADR 0004](../adr/0004-crisperwhisper-turbo-ct2-int8.md)).
- **Nasıl oturur:** bütün motorlar içinde en dar VRAM payı (3.5–3.6 GB); başa dolgu (leading pad) yok; sabitlenmiş
  paket sürümleri ana ortamdan farklı olduğu için ayrı ortam; aynı transkript sözleşmesi.
- Ayrıntılar: [crisperwhisper_turbo_ct2.md](../engineering/crisperwhisper_turbo_ct2.md) §1, §7 · [gpu_memory_and_isolation.md](../engineering/gpu_memory_and_isolation.md) §5
