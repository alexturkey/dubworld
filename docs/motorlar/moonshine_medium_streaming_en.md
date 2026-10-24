# Moonshine Medium Streaming (English) (`moonshine_medium_streaming_en`) — EXPERIMENTAL

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** English speech-to-text on the CPU with Moonshine's streaming model, in its own Python environment.

> **Experimental.** At chunk boundaries the streaming model can place a word start before the previous word (known upstream limit, no proven fix for the pinned native build; [transcription.md §6](../engineering/transcription.md)). The pipeline never edits raw times: such output stops with an explicit `MoonshineDeneyselHatasi` naming the first bad word and the alternatives. `dubla kontrol`, the settings check and the GUI/web labels mark the engine `deneysel`. For English on CPU prefer `parakeet_cpu_align`.

| | |
|---|---|
| License | MIT (code and the English streaming model; the non-commercial legacy models are not used) |
| Commercial use | yes |
| Source | https://github.com/moonshine-ai/moonshine |
| Install | manual: own virtual environment with the `stt-moonshine` extra (`moonshine-voice==0.0.73`, pinned: the engine checks that build's DLL sha256); by default the engine folder is `src/dublaj_hatti/bolum_20_transkripsiyon/moonshine_medium_streaming_motoru/` (its `.venv` and `models/` go there); override the folder with `DUBLAJ_MOONSHINE_ROOT` and the python with `DUBLAJ_MOONSHINE_PYTHON` in `.env`; model files as listed in the engine's `config/model_manifest.json` |
| Hardware | CPU only; 96.9 s audio in 75.4 s streaming (measured); RAM not measured |
| Languages | English only |
| Default | off |

**Settings**

- `transkripsiyon.motor = "moonshine_medium_streaming_en"`
- `transkripsiyon.kaynak_dil = auto` or `en`

**Common errors**

- Non-English `kaynak_dil` → settings error by design.
- `Moonshine native DLL kimlikleri beklenen ortamla eslesmiyor` → the environment's native files differ from the pinned build; reinstall the pinned package.
- `Moonshine (experimental / deneysel): N word start(s) go backwards ...` → the known limit above (measured); times are not edited. Switch to `transkripsiyon.motor = parakeet_cpu_align` or `faster-whisper`.

**Related:** [transcription.md](../engineering/transcription.md) · [dil_tespiti.md](../tarifler/dil_tespiti.md) · [donanim.md](../donanim.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

## How it works in this pipeline / Neden böyle

- **Principle:** Moonshine's streaming encoder-decoder for English on the CPU, from its own environment with a pinned
  native build; text and native word times come from that build.
- **Why it is experimental:** at chunk boundaries the build can place a word start before the previous word, and its
  confidence is always 1.0, so it cannot flag the error. The pipeline does not edit raw times; it stops with
  `MoonshineDeneyselHatasi` ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)). The non-streaming API was 3.6×
  faster than streaming in the recorded test.
- **How it fits:** CPU only, English only; same transcript contract; Parakeet is the recommended CPU alternative.
- Details: [transcription.md](../engineering/transcription.md) §6

## Türkçe

**Ne yapar:** Moonshine'ın akış (streaming) modeliyle işlemcide, kendi Python ortamında İngilizce konuşmayı metne çevirir.

> **Deneysel.** Parça sınırlarında akış modeli bir kelimenin başlangıcını önceki kelimeden öne koyabilir (üst akımda bilinen sınır, sabitlenen yerel derleme için kanıtlanmış bir çözüm yok; [transcription.md §6](../engineering/transcription.md)). Hat ham zamanları asla düzeltmez: böyle bir çıktı, ilk hatalı kelimeyi ve seçenekleri adıyla söyleyen açık bir `MoonshineDeneyselHatasi` ile durur. `dubla kontrol`, ayar denetimi ve GUI/web etiketleri motoru `deneysel` olarak işaretler. İşlemcide İngilizce için `parakeet_cpu_align` tercih edin.

| | |
|---|---|
| Lisans | MIT (kod ve İngilizce akış modeli; ticari olmayan eski modeller kullanılmaz) |
| Ticari kullanım | evet |
| Kaynak | https://github.com/moonshine-ai/moonshine |
| Kurulum | elle: `stt-moonshine` ekiyle kendi sanal ortamı (`moonshine-voice==0.0.73`, sabitlenmiş: motor o derlemenin DLL sha256 değerini denetler); varsayılan motor klasörü `src/dublaj_hatti/bolum_20_transkripsiyon/moonshine_medium_streaming_motoru/` (`.venv` ve `models/` oraya gider); klasörü `DUBLAJ_MOONSHINE_ROOT`, python'u `DUBLAJ_MOONSHINE_PYTHON` ile `.env` içinde geçersiz kılın; model dosyaları motorun `config/model_manifest.json` dosyasındaki listeye göre |
| Donanım | yalnız işlemci; 96.9 sn ses 75.4 sn'de akışla işlendi (ölçüldü); RAM ölçülmedi |
| Diller | yalnız İngilizce |
| Varsayılan | kapalı |

**Ayarlar**

- `transkripsiyon.motor = "moonshine_medium_streaming_en"`
- `transkripsiyon.kaynak_dil = auto` ya da `en`

**Sık hatalar**

- İngilizce olmayan `kaynak_dil` → tasarım gereği ayar hatası.
- `Moonshine native DLL kimlikleri beklenen ortamla eslesmiyor` → ortamın yerel dosyaları sabitlenen derlemeden farklı; sabitlenmiş paketi yeniden kurun.
- `Moonshine (experimental / deneysel): N word start(s) go backwards ...` → yukarıdaki bilinen sınır (ölçüldü); zamanlar düzeltilmez. `transkripsiyon.motor = parakeet_cpu_align` ya da `faster-whisper` seçin.

**İlgili:** [transcription.md](../engineering/transcription.md) · [dil_tespiti.md](../tarifler/dil_tespiti.md) · [donanim.md](../donanim.md) · [THIRD_PARTY.md](../../THIRD_PARTY.md)

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** Moonshine'ın İngilizce akış kodlayıcı-kod çözücüsü işlemcide, sabitlenmiş yerel derlemesiyle kendi ortamından
  çalışır; metin ve yerel kelime zamanları bu derlemeden gelir.
- **Neden deneysel:** parça sınırlarında derleme bir kelime başlangıcını önceki kelimeden öne koyabilir ve güven değeri
  her zaman 1.0'dır, bu yüzden hatayı işaretleyemez. Hat ham zamanları düzeltmez; `MoonshineDeneyselHatasi` ile durur
  ([ADR 0009](../adr/0009-fail-closed-no-silent-fallback.md)). Kayıtlı testte akışsız API akıştan 3.6× daha hızlıydı.
- **Diğer parçalarla ahengi:** yalnız işlemci, yalnız İngilizce; aynı transkript sözleşmesi; önerilen işlemci
  seçeneği Parakeet'tir.
- Ayrıntı: [transcription.md](../engineering/transcription.md) §6
