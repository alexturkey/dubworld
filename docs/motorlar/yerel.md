# Local Opus-MT (English → Turkish) (`yerel`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Offline machine translation with Helsinki-NLP `opus-mt-tc-big-en-tr` (MarianMT). The keyless floor of `ceviri.arka_uc = auto` when no Codex / Claude Code CLI is found.

| | |
|---|---|
| License | CC-BY-4.0 (model) |
| Commercial use | yes (attribution in NOTICE) |
| Source | https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-tr (pinned commit + sha256) |
| Install | base install (step `modeller`) |
| Hardware | GPU or CPU; ~1 GB (estimate, not measured); passed the end-to-end CPU smoke test |
| Languages | **English → Turkish only** |
| Default | last step of `auto` |

**Settings**

- `ceviri.arka_uc = "yerel"`
- no candidates, no timing-aware repair: `ses.akis` other than `natural_blocks_1` is ignored

**Common errors**

- Target ≠ `tr` or non-English source → settings error by design; use an LLM backend.
- Quality versus LLM backends: no measurement yet.

**Related:** [translation.md](../engineering/translation.md) · [kombinasyonlar.md](../tarifler/kombinasyonlar.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** MarianMT sequence-to-sequence translation (Opus-MT, English → Turkish), offline, batch 16, beam 4,
  `max_new_tokens` 256, on GPU or CPU.
- **Why this choice:** the keyless, offline floor of `ceviri.arka_uc = auto` when no Codex or Claude Code CLI is found
  ([ADR 0008](../adr/0008-translation-backend-order.md)). Local LLMs on a 4 GB card were tried before: meaning errors and
  ≈ 13 minutes for a 66 s video, so a dedicated MT model replaced them.
- **How it fits:** it cannot provide the natural-blocks contract (no candidates, no ownership check, no spoken-form
  rules), so `ses.akis` values other than `natural_blocks_1` have no effect and full-text mode is blocked. Output is
  the same `translation.json`. Quality against the LLM backends: no record.
- Details: [translation.md](../engineering/translation.md) §4, §5

## Türkçe

**Ne yapar:** Helsinki-NLP `opus-mt-tc-big-en-tr` (MarianMT) ile ağsız makine çevirisi. Hiçbir Codex / Claude Code CLI bulunamadığında `ceviri.arka_uc = auto` için anahtarsız taban.

| | |
|---|---|
| Lisans | CC-BY-4.0 (model) |
| Ticari kullanım | evet (NOTICE içinde atıf) |
| Kaynak | https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-tr (sabit commit + sha256) |
| Kurulum | temel kurulum (adım `modeller`) |
| Donanım | GPU ya da işlemci; ~1 GB (tahmin, ölçülmedi); uçtan uca işlemci duman testini geçti |
| Diller | **yalnız İngilizce → Türkçe** |
| Varsayılan | `auto` sırasının son adımı |

**Ayarlar**

- `ceviri.arka_uc = "yerel"`
- aday yok, zamanlamaya duyarlı onarım yok: `natural_blocks_1` dışındaki `ses.akis` değerleri yok sayılır

**Sık hatalar**

- Hedef ≠ `tr` ya da İngilizce olmayan kaynak → tasarım gereği ayar hatası; bir LLM arka ucu kullanın.
- LLM arka uçlarına göre kalite: henüz ölçüm yok.

**İlgili:** [translation.md](../engineering/translation.md) · [kombinasyonlar.md](../tarifler/kombinasyonlar.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** MarianMT diziden diziye çeviri (Opus-MT, İngilizce → Türkçe), ağsız, toplu iş 16, ışın 4,
  `max_new_tokens` 256, GPU ya da işlemcide.
- **Neden bu seçim:** hiçbir Codex ya da Claude Code CLI bulunamadığında `ceviri.arka_uc = auto` için anahtarsız, ağsız
  taban ([ADR 0008](../adr/0008-translation-backend-order.md)). Daha önce 4 GB'lık kartta yerel LLM'ler denendi: anlam
  hataları ve 66 sn'lik bir video için ≈ 13 dakika; bu yüzden yerlerini özel bir MT modeli aldı.
- **Diğer parçalarla ahengi:** doğal bloklar sözleşmesini sağlayamaz (aday yok, sahiplik denetimi yok, konuşma biçimi
  kuralları yok), bu yüzden `natural_blocks_1` dışındaki `ses.akis` değerlerinin etkisi yoktur ve tam metin kipi
  engellenir. Çıktı aynı `translation.json` dosyasıdır. LLM arka uçlarına göre kalite: kayıt yok.
- Ayrıntı: [translation.md](../engineering/translation.md) §4, §5
