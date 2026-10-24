# Bolum 00: Omurga

Bu bolum gorev araci degildir; diger butun bolumlerin uzerinde calistigi
orkestrasyon, secim grafigi, motor sinir adapterleri ve ag katmanini tasir.
Bolum ve kutu listesinin sahibi `docs/arac_katalogu.md` belgesidir.

```text
bolum_00_omurga/
  core/                    Segment Senkron ve Full Metin ana akisi, checkpoint cekirdegi
    dubber.py
    pipeline_checkpoint.py
    pipeline_selection_contract.py
  selection_graph/         Telegram/GUI menu ve is sozlesmesi grafigi
    selection_graph.json
    implementation_registry.json
  runtime/                 output yolu, model/asset yollari ve harici motor adapterleri
    output_paths.py
    asset_paths.py
    crisperwhisper_runtime.py
    crisperwhisper_turbo_ct2_runtime.py
    moonshine_medium_streaming_runtime.py
    whisperx_runtime.py
    internet_gateway/      dis internet route ve DNS/IPv4 egress kurtarmasinin tek sahibi
  full_metin_dublaji.py    Full Metin akisi
```

Kural:

- Ana pipeline orkestrasyonu `core/dubber.py` icindedir.
- Menu, secenek, is alani ve asama etkilerinin makine kaynagi
  `selection_graph/selection_graph.json`, backend sahipligi
  `selection_graph/implementation_registry.json` dosyasidir.
- Kendi venv'i ve modeli olan motor kutulari `src/bolum_20_transkripsiyon/`
  altindadir ve yalniz `runtime/` sinir adapterleriyle cagrilir.
