# Parakeet (sherpa-onnx) + CTC alignment (`parakeet_cpu_align`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** English recognition with NVIDIA Parakeet Unified EN 0.6B int8 through sherpa-onnx on the CPU, then the shared CTC alignment. Fastest measured CPU engine; long audio is cut at silences below the 400 s encoder limit.

| | |
|---|---|
| License | weights: NVIDIA Open Model License (commercially usable, with conditions); sherpa-onnx Apache-2.0 |
| Commercial use | conditional (keep the NVIDIA notice if you redistribute the model) |
| Source | https://github.com/k2-fsa/sherpa-onnx , model `nvidia/parakeet-unified-en-0.6b` |
| Install | `scripts/kur.ps1 -Adim parakeet` installs sherpa-onnx (hash-locked) **and** downloads the int8 model (~663 MB) into `runtime_assets/model_cache/sherpa_onnx/sherpa-onnx-nemo-parakeet-unified-en-0.6b-int8-non-streaming/`: the k2-fsa sherpa-onnx export of `nvidia/parakeet-unified-en-0.6b`, pinned commit + sha256 per file in `scripts/modeller.json` (step `parakeet`), together with NVIDIA's model card (license notice). Model only: `python scripts/modelleri_indir.py --adim parakeet` |
| Hardware | CPU int8 ~1.9 GB RAM; 96.9 s audio in 11.9 s with 8 threads (measured) |
| Languages | English only (non-English → multilingual fallback) |
| Default | off |

**Settings**

- `transkripsiyon.motor = "parakeet_cpu_align"`
- first use shows the conditional-license notice

**Common errors**

- Asking ~10 GB for one MatMul on long audio → input limit, not memory; the engine already cuts at ≤ 399 s.
- `yok` in `dubla kontrol` → `sherpa_onnx` not installed in the app environment.

**Related:** [transcription.md](../engineering/transcription.md) · [donanim.md](../donanim.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** NVIDIA Parakeet (English, 0.6B) exported to ONNX int8 and decoded by sherpa-onnx on the CPU with modified
  beam search (4 paths, blank penalty 2.0); the shared CTC box adds word times.
- **Why this choice:** lowest WER on the 10-file corpus (4.49 %) and the best result on ≈ 70-minute files, with no
  VRAM use (≈ 1.9 GB RAM). The encoder accepts at most 400 s, so longer audio is cut at the middle of the last
  ≥ 600 ms silence before 399 s; a 10 GB "OOM" turned out to be this input limit.
- **How it fits:** English only (a non-English detection switches to the multilingual path); 1.0 s leading pad; CTC
  windows are prepared from the real pieces so natural gaps are not inside one window.
- Details: [transcription.md](../engineering/transcription.md) §1, §4 · [word_alignment.md](../engineering/word_alignment.md) §3
- Place in the end-to-end flow: [pipeline-flow.md, segmentation per engine](../engineering/pipeline-flow.md#7-segmentation-per-transcription-engine)

## Türkçe

**Ne yapar:** NVIDIA Parakeet Unified EN 0.6B int8 ile sherpa-onnx üzerinden işlemcide İngilizce tanıma, ardından ortak CTC hizalama. Ölçülen en hızlı işlemci motoru; uzun ses, 400 sn'lik kodlayıcı sınırının altında sessizliklerden kesilir.

| | |
|---|---|
| Lisans | ağırlık: NVIDIA Open Model License (şartlarla ticari kullanılabilir); sherpa-onnx Apache-2.0 |
| Ticari kullanım | şartlı (modeli yeniden dağıtırsanız NVIDIA bildirimini koruyun) |
| Kaynak | https://github.com/k2-fsa/sherpa-onnx , model `nvidia/parakeet-unified-en-0.6b` |
| Kurulum | `scripts/kur.ps1 -Adim parakeet` sherpa-onnx'u (hash kilitli) kurar **ve** int8 modeli (~663 MB) `runtime_assets/model_cache/sherpa_onnx/sherpa-onnx-nemo-parakeet-unified-en-0.6b-int8-non-streaming/` altına indirir: `nvidia/parakeet-unified-en-0.6b` modelinin k2-fsa sherpa-onnx dışa aktarımı, `scripts/modeller.json` içinde (adım `parakeet`) dosya başına sabit commit + sha256, NVIDIA'nın model kartıyla (lisans bildirimi) birlikte. Yalnız model: `python scripts/modelleri_indir.py --adim parakeet` |
| Donanım | işlemci int8 ~1.9 GB RAM; 96.9 sn ses 8 iş parçacığıyla 11.9 sn'de (ölçüldü) |
| Diller | yalnız İngilizce (İngilizce olmayan → çok dilli yedek) |
| Varsayılan | kapalı |

**Ayarlar**

- `transkripsiyon.motor = "parakeet_cpu_align"`
- ilk kullanımda şartlı lisans bildirimi gösterilir

**Sık hatalar**

- Uzun seste tek bir MatMul için ~10 GB istemesi → bellek değil girdi sınırı; motor zaten ≤ 399 sn'de keser.
- `dubla kontrol` içinde `yok` → `sherpa_onnx` uygulama ortamına kurulu değil.

**İlgili:** [transcription.md](../engineering/transcription.md) · [donanim.md](../donanim.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** NVIDIA Parakeet (İngilizce, 0.6B) ONNX int8'e dışa aktarılmış hâliyle işlemcide sherpa-onnx tarafından
  değiştirilmiş ışın aramasıyla (4 yol, boşluk cezası 2.0) çözülür; ortak CTC kutusu kelime zamanlarını ekler.
- **Neden bu seçim:** 10 dosyalık derlemde en düşük WER (4.49 %) ve ≈ 70 dakikalık dosyalarda en iyi sonuç, VRAM
  kullanmadan (≈ 1.9 GB RAM). Kodlayıcı en çok 400 sn kabul eder, bu yüzden daha uzun ses 399 sn'den önceki son
  ≥ 600 ms sessizliğin ortasından kesilir; 10 GB'lık bir "OOM"un bu girdi sınırı olduğu anlaşıldı.
- **Diğer parçalarla ahengi:** yalnız İngilizce (İngilizce dışı bir tespit çok dilli yola geçirir); baştaki 1.0 sn pay;
  CTC pencereleri gerçek parçalardan hazırlanır, böylece doğal boşluklar tek bir pencerenin içinde kalmaz.
- Ayrıntı: [transcription.md](../engineering/transcription.md) §1, §4 · [word_alignment.md](../engineering/word_alignment.md) §3
- Uçtan uca akıştaki yeri: [hat_akisi.md, motora göre segmentleme](../muhendislik/hat_akisi.md#7-transkripsiyon-motoruna-göre-segmentleme)
