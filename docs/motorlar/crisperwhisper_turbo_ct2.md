# CrisperWhisper 2.0 Turbo (CT2), engine 13 (`crisperwhisper_turbo_ct2`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Verbatim transcription (keeps fillers, repetitions, false starts) on a CTranslate2 fork, int8, inside WSL2 as a one-shot subprocess; final word times from the shared CTC alignment. Most accurate word timing in this repo.

| | |
|---|---|
| License | weights: **nyra health Non-Commercial Research License**; code MIT |
| Commercial use | **no** (outputs may not train commercial models) |
| Source | https://huggingface.co/nyralabs/CrisperWhisper2.0_turbo |
| Install | `scripts/kur.ps1 -Adim crisper -TicariOlmayanKabul` (uses the sister STT repository's installer at a fixed commit; set `DUBLAJ_STT_REPO_URL` if the placeholder is empty); conversion needs ~4.5 GB free RAM |
| Hardware | NVIDIA GPU + WSL2 Ubuntu; ~1.4 GB VRAM (measured); **no CPU path** |
| Languages | Whisper languages; tested on real audio: tr, en, ja |
| Default | chosen by `transkripsiyon.motor = auto` when installed |

**Settings**

- `transkripsiyon.motor = "crisperwhisper_turbo_ct2"`
- `transkripsiyon.crisper_dil_tespiti`: `global_first_window` (default) or `continuous_stream` (code-switching); `per_window` is rejected for Turbo
- first use asks for license acceptance (`--lisans-onay`)

**Common errors**

- CPU machine / no CUDA → settings error by design.
- `no kernel image is available` inside WSL → Linux torch must be a build with kernels for your GPU ([low_vram.md](../engineering/low_vram.md)).
- `lisans onayı yok` → read the notice; accept only if your use is non-commercial.

**Related:** [crisperwhisper_turbo_ct2.md](../engineering/crisperwhisper_turbo_ct2.md) · [ADR 0004](../adr/0004-crisperwhisper-turbo-ct2-int8.md) · [dil_tespiti.md](../tarifler/dil_tespiti.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** a Whisper Turbo model fine-tuned for verbatim output (fillers, repetitions, false starts), converted to
  a CTranslate2 fork and run with int8 compute, beam 1, in a one-shot WSL2 subprocess that exchanges atomic JSON files.
  After the worker exits, the shared CTC box aligns its text; native times are kept only for diagnostics.
- **Why this choice:** verbatim text matters for dub timing because hesitations occupy real time. The CT2 fork that
  carries the alignment heads ships only Linux wheels (hence WSL2), and Pascal has no fast fp16 (hence int8).
  Native times produced zero-length words that would have slowed the video ≈ 14×, hence CTC. A resident worker was
  measured 16.9 % slower. Non-commercial weights: installed only with an explicit acceptance flag
  ([ADR 0017](../adr/0017-defaults-and-licence-gate.md)).
- **How it fits:** ≈ 1.4 GB VRAM; preferred by `transkripsiyon.motor = auto` when installed; no CPU path; output is the
  same `transcript.json` contract.
- Details: [ADR 0004](../adr/0004-crisperwhisper-turbo-ct2-int8.md) · [crisperwhisper_turbo_ct2.md](../engineering/crisperwhisper_turbo_ct2.md) §2, §6

## Türkçe

Kayıt satırı: `src/dublaj_hatti/kayit.py` (kurulu olup olmadığını `dubla kontrol` gösterir)

**Ne yapar:** Kelimesi kelimesine transkript (dolgu sözcüklerini, tekrarları, yanlış başlangıçları korur); CTranslate2 çatalı (fork) üzerinde, int8, WSL2 içinde tek seferlik alt süreç olarak; son kelime zamanları ortak CTC hizalamasından. Bu repodaki en hassas kelime zamanlaması.

| | |
|---|---|
| Lisans | ağırlıklar: **nyra health Non-Commercial Research License** (ticari olmayan araştırma lisansı); kod MIT |
| Ticari kullanım | **hayır** (çıktılar ticari modelleri eğitmek için kullanılamaz) |
| Kaynak | https://huggingface.co/nyralabs/CrisperWhisper2.0_turbo |
| Kurulum | `scripts/kur.ps1 -Adim crisper -TicariOlmayanKabul` (kardeş STT reposunun kurulum betiğini sabit bir commit'te kullanır; yer tutucu boşsa `DUBLAJ_STT_REPO_URL` ayarlayın); dönüştürme için ~4.5 GB boş RAM gerekir |
| Donanım | NVIDIA GPU + WSL2 Ubuntu; ~1.4 GB VRAM (ölçüldü); **CPU yolu yok** |
| Diller | Whisper dilleri; gerçek seste denendi: tr, en, ja |
| Varsayılan | kuruluysa `transkripsiyon.motor = auto` bunu seçer |

**Ayarlar**

- `transkripsiyon.motor = "crisperwhisper_turbo_ct2"`
- `transkripsiyon.crisper_dil_tespiti`: `global_first_window` (varsayılan) ya da `continuous_stream` (dil değiştirerek konuşma, code-switching); Turbo için `per_window` reddedilir
- ilk kullanımda lisans onayı istenir (`--lisans-onay`)

**Sık hatalar**

- CPU'lu makine / CUDA yok → tasarım gereği ayar hatası.
- WSL içinde `no kernel image is available` → Linux torch, GPU'nuz için çekirdek (kernel) içeren bir derleme olmalı ([low_vram.md](../engineering/low_vram.md)).
- `lisans onayı yok` → bildirimi okuyun; yalnız kullanımınız ticari değilse kabul edin.

**İlgili:** [crisperwhisper_turbo_ct2.md](../engineering/crisperwhisper_turbo_ct2.md) · [ADR 0004](../adr/0004-crisperwhisper-turbo-ct2-int8.md) · [dil_tespiti.md](../tarifler/dil_tespiti.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** kelimesi kelimesine çıktı (dolgu sözcükleri, tekrarlar, yanlış başlangıçlar) için ince ayarlanmış bir Whisper
  Turbo modeli; bir CTranslate2 çatalına dönüştürülür ve int8 hesapla, beam 1 ile, atomik JSON dosyaları alışverişi
  yapan tek seferlik bir WSL2 alt sürecinde çalışır. İşçi kapandıktan sonra ortak CTC kutusu metnini hizalar; modelin
  kendi zamanları yalnız tanılama için saklanır.
- **Neden bu seçim:** duraksamalar gerçek zaman kapladığı için dublaj zamanlaması açısından kelimesi kelimesine metin
  önemlidir. Hizalama başlıklarını taşıyan CT2 çatalı yalnız Linux wheel paketleriyle gelir (WSL2 bu yüzden), Pascal'da
  hızlı fp16 yoktur (int8 bu yüzden). Modelin kendi zamanları, videoyu ≈ 14× yavaşlatacak sıfır uzunlukta kelimeler
  üretti; CTC bu yüzden. Sürekli açık (resident) bir işçi %16.9 daha yavaş ölçüldü. Ticari olmayan ağırlıklar: yalnız
  açık bir kabul bayrağıyla kurulur ([ADR 0017](../adr/0017-defaults-and-licence-gate.md)).
- **Nasıl oturur:** ≈ 1.4 GB VRAM; kuruluysa `transkripsiyon.motor = auto` bunu tercih eder; CPU yolu yok; çıktı aynı
  `transcript.json` sözleşmesidir.
- Ayrıntılar: [ADR 0004](../adr/0004-crisperwhisper-turbo-ct2-int8.md) · [crisperwhisper_turbo_ct2.md](../engineering/crisperwhisper_turbo_ct2.md) §2, §6
