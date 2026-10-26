# Bolum 30: Hizalama ve Segment

Bu bolum transkripsiyondan gelen hizalanmis kelimelerden TTS'e hazir zamanli
dublaj segmentleri uretilene kadar olan ara katmani tasir. Bolum ve kutu
listesinin sahibi `docs/arac_katalogu.md` belgesidir.

```text
bolum_30_hizalama_ve_segment/
  ctc_kelime_hizalama/
    client.py  worker.py  ctc_konusma_siniri.py
  nihai_dublaj_segmentleri.py
  konusmaci_ve_cinsiyet/
    gender_classifier.py
```

Anlam:

- Nihai segment hazirligi tek zorunlu API olarak
  `nihai_dublaj_segmentleri.py` dosyasinda bulunur. Butun transkripsiyon
  kaynaklarinin kelimeleri bu API'ye girer; motorlar bagimsiz final segment
  kurali icat etmez.
- `konusmaci_ve_cinsiyet/` speaker/gender kararlarinda kullanilan yardimci
  modeli tasir.
- `ctc_kelime_hizalama/` bilinen metni sese hizalayan ortak kutudur; 13. motor,
  faster-whisper (CTC), Parakeet ve YouTube JSON3 onu kullanir. Kelime siniri
  politikasi ve kanitlari kutunun `README.md` dosyasindadir.

Bu bolum ses uretmez. Ses uretimi `src/bolum_50_seslendirme/tts_orkestratoru/`
kutusunun isidir.
