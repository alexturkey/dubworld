# WhisperX Motoru

Lokal WhisperX transkripsiyon ve forced alignment motorudur. Subprocess olarak calisir, kelime zamanlari ve opsiyonel diarization uretir.

Doğrudan `large-v3-turbo + float32` transkripsiyonu
`whisperx_float32_quality_v1` profilini kullanır:

```text
condition_on_previous_text=False
suppress_tokens=[]
```

Int8 `whisperx_engine_default_v1` profilinde `suppress_tokens=[-1]` ile kalır.
Burada `[]` varsayılan non-speech token bastırma kümesini devre dışı bırakır;
`[-1]` tokenizer varsayılan kümesini etkin tutar. Alan boolean değildir.
`worker.py`, `--decoder_profile` değerini `load_model(..., asr_options=...)`
çağrısına uygular ve modelin etkili seçeneklerini doğrular. Alignment-only
çağrılarında decoder profili kullanılmaz.

Alignment kelimelerinde opsiyonel `score` varsa hem normal hem alignment-only
paketleme yolunda korunur; skor yoksa eski alan yapısı değişmez. Skor yalnız
gözlemseldir, zamanları değiştirmez ve job kabul/red kararı üretmez.

Kanonik giris:

```text
worker.py
```
