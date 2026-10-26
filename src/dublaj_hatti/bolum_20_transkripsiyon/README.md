# Bolum 20: Transkripsiyon

Bu bolum `asr_ready.wav` girdisini metne, kelime zamanlarina ve gerekiyorsa
konusmaci bilgisine ceviren motor kutularini tasir. Bolum ve kutu listesinin
sahibi `docs/arac_katalogu.md` belgesidir.

Her motor kendi alt klasorunde izole durur:

```text
bolum_20_transkripsiyon/
  ayarlar/                            Telegram transkripsiyon preset sahipligi
  whisperx_motoru/                    WhisperX (kendi hizalamasiyla)
  faster_whisper_motoru/
  parakeet_cpu_align_motoru/
  crisperwhisper_turbo_ct2_motoru/    kendi WSL venv'i ve modeliyle Turbo CT2 motor kutusu
  youtube_json3_kaynagi/              YouTube JSON3 metni + WhisperX alignment
```

Kural: Bu bolum kokune dogrudan motor dosyasi eklenmez. Yeni transkripsiyon
motoru kendi klasoru, kendi giris dosyasi ve kendi ayarlariyla eklenir. Kendi
venv'i ve modeli olan motorlar da bu bolumun altindadir; proje kokune motor
kutusu acilmaz.

Ana akis motor kutularindan implementation import etmez. Harici motor kutulari
`src/bolum_00_omurga/runtime/` altindaki sinir adapterleriyle JSON istek ve
subprocess uzerinden cagrilir.
