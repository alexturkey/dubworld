# Runtime Ayarlari

Bu kutu uygulamanin calisma zamani yol kararlarini tasir.

```text
runtime/
  output_paths.py
  hata_aciklama.py
  internet_gateway/
                  merkezi direct/WARP internet yolu ve anlik hata kurtarma
```

Anlam:

- `output_paths.py` merkezi output kokunu `.env` ve proje ayarlarindan cozer.
- `hata_aciklama.py` hata zincirinden ozgun hatayi, maskeli ozeti ve kisa yorumu
  uretir; Telegram, GUI ve Sorunlu Isler ayni metni kullanir
  (`docs/hata_yakalama_ve_kullanici_hata_mesaji_sozlesmesi.md`).
- `internet_gateway/` dis internet yolunu secip DNS/IPv4 egress hatasinda ayni
  checkpoint islemini alternatif yolda yeniden yurutur.
- Output icerigi bu klasore yazilmaz; bu kutu sadece yol kararini verir.
