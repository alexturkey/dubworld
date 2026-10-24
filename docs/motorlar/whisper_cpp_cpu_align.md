# whisper.cpp (CPU) + CTC alignment (`whisper_cpp_cpu_align`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** English recognition with whisper.cpp `ggml-base.en` on the CPU, then the shared CTC word alignment.

| | |
|---|---|
| License | MIT (whisper.cpp and the ggml model) |
| Commercial use | yes |
| Source | https://github.com/ggml-org/whisper.cpp , model https://huggingface.co/ggerganov/whisper.cpp |
| Install | manual: official prebuilt `whisper-cli.exe` into `runtime_assets/transkripsiyon_motorlari/whisper_cpp_cpu_align/engines/whisper_cpp/bin/` and `ggml-base.en.bin` into `.../whisper_cpp_cpu_align/models/whisper/` (or set `DUBLAJ_WHISPER_CPP_CPU_ROOT`) |
| Hardware | CPU; 96.9 s audio in 32.4 s (12.7 recognition + 19.4 alignment, measured); the CTC step may use the GPU |
| Languages | English only |
| Default | off |

**Settings**

- `transkripsiyon.motor = "whisper_cpp_cpu_align"`
- `transkripsiyon.kaynak_dil = auto` or `en`

**Common errors**

- Non-English input → error by design.
- `whisper-cli` not found → check the folder layout above.

**Related:** [transcription.md](../engineering/transcription.md) · [word_alignment.md](../engineering/word_alignment.md) · [donanim.md](../donanim.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** whisper.cpp runs `ggml-base.en` as a separate executable on the CPU for the text; the shared CTC box then
  aligns that text for word times.
- **Why this choice:** an English CPU path with MIT code and model and no PyTorch in the recognition step. It is not
  the recommended CPU engine: WER 6.89 % against 4.49 % for Parakeet on the same corpus. A larger whisper.cpp model was
  tested on CUDA; its native timestamps placed the first word up to 4.3 s early, which confirmed the text + CTC design.
- **How it fits:** 1.0 s leading pad; the CTC step may use the GPU under the lock; same transcript contract.
- Details: [transcription.md](../engineering/transcription.md) §1, §5 · [ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)
- Place in the end-to-end flow: [pipeline-flow.md, segmentation per engine](../engineering/pipeline-flow.md#7-segmentation-per-transcription-engine)

## Türkçe

**Ne yapar:** İşlemcide whisper.cpp `ggml-base.en` ile İngilizce tanıma, ardından ortak CTC kelime hizalaması.

| | |
|---|---|
| Lisans | MIT (whisper.cpp ve ggml modeli) |
| Ticari kullanım | evet |
| Kaynak | https://github.com/ggml-org/whisper.cpp , model https://huggingface.co/ggerganov/whisper.cpp |
| Kurulum | elle: resmî hazır derleme `whisper-cli.exe` dosyasını `runtime_assets/transkripsiyon_motorlari/whisper_cpp_cpu_align/engines/whisper_cpp/bin/` altına ve `ggml-base.en.bin` dosyasını `.../whisper_cpp_cpu_align/models/whisper/` altına koyun (ya da `DUBLAJ_WHISPER_CPP_CPU_ROOT` ayarlayın) |
| Donanım | işlemci; 96.9 sn ses 32.4 sn'de (12.7 tanıma + 19.4 hizalama, ölçüldü); CTC adımı GPU kullanabilir |
| Diller | yalnız İngilizce |
| Varsayılan | kapalı |

**Ayarlar**

- `transkripsiyon.motor = "whisper_cpp_cpu_align"`
- `transkripsiyon.kaynak_dil = auto` ya da `en`

**Sık hatalar**

- İngilizce olmayan girdi → tasarım gereği hata.
- `whisper-cli` bulunamadı → yukarıdaki klasör düzenini denetleyin.

**İlgili:** [transcription.md](../engineering/transcription.md) · [word_alignment.md](../engineering/word_alignment.md) · [donanim.md](../donanim.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** whisper.cpp, metin için `ggml-base.en` modelini işlemcide ayrı bir çalıştırılabilir dosya olarak çalıştırır;
  ardından ortak CTC kutusu kelime zamanları için bu metni hizalar.
- **Neden bu seçim:** MIT kodlu ve modelli, tanıma adımında PyTorch olmayan bir İngilizce işlemci yolu. Önerilen
  işlemci motoru değildir: aynı derlemde WER 6.89 %, Parakeet'te 4.49 %. Daha büyük bir whisper.cpp modeli CUDA'da
  denendi; yerel zaman damgaları ilk kelimeyi 4.3 sn'ye kadar erken koydu, bu da metin + CTC tasarımını doğruladı.
- **Diğer parçalarla ahengi:** baştaki 1.0 sn pay; CTC adımı kilit altında GPU kullanabilir; aynı transkript sözleşmesi.
- Ayrıntı: [transcription.md](../engineering/transcription.md) §1, §5 · [ADR 0005](../adr/0005-ctc-forced-alignment-only-time-source.md)
- Uçtan uca akıştaki yeri: [hat_akisi.md, motora göre segmentleme](../muhendislik/hat_akisi.md#7-transkripsiyon-motoruna-göre-segmentleme)
