# Akıllı İnternet Geçidi

Bu kutu uygulamanın dış internete çıkış yolunun tek runtime sahibidir.

```text
internet_gateway/
  gateway.py   DNS/IPv4 egress hata sınıflandırması, direct/WARP seçimi,
               process proxy sözleşmesi ve aynı işlemin anlık yeniden yürütülmesi
```

Davranış:

- Normal durumda doğrudan bağlantı kullanılır.
- Launcher başlangıçta IPv4 yolunu sınar ve ilk route kararını ortama yazar.
- Bir checkpoint işlemi DNS veya IPv4 route hatası verirse geçit WARP yoluna
  geçer ve yalnız aynı işlemi bir kez yeniden yürütür.
- Daha önce tamamlanmış checkpointler yeniden çalıştırılmaz.
- HTTP, HTTPS ve alt süreçler aynı process proxy sözleşmesini devralır.
- Localhost servisleri `NO_PROXY` ile yerel kalır.
- HTTP, kimlik doğrulama, kota, içerik veya uygulama hataları ağ değişimi
  tetiklemez.
- Her otomatik geçiş `<run_dir>/internet_gateway_events.jsonl` içine secretsız
  kanıt olarak yazılır.
