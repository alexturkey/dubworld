# Akıllı İnternet Geçidi

Bu kutu uygulamanın dış internete çıkış yolunun tek runtime sahibidir.

```text
internet_gateway/
  gateway.py   DNS/IPv4 egress hata sınıflandırması, direct/WARP seçimi,
               process proxy sözleşmesi ve aynı işlemin anlık yeniden yürütülmesi
```

Davranış:

- Normal durumda doğrudan bağlantı kullanılır.
- İlk yol `DUBLAJ_EGRESS_MODE` ile seçilir (varsayılan `direct`).
- Bir checkpoint işlemi DNS veya IPv4 route hatası verirse ve `DUBLAJ_EGRESS_PROXY`
  ayarlıysa geçit `warp` yedek yoluna geçer ve yalnız aynı işlemi bir kez yeniden yürütür.
- Daha önce tamamlanmış checkpointler yeniden çalıştırılmaz.
- HTTP, HTTPS ve alt süreçler aynı process proxy sözleşmesini devralır.
- Localhost servisleri `NO_PROXY` ile yerel kalır.
- HTTP, kimlik doğrulama, kota, içerik veya uygulama hataları ağ değişimi
  tetiklemez.
- Her otomatik geçiş `<run_dir>/internet_gateway_events.jsonl` içine secretsız
  kanıt olarak yazılır.

## Yedek yol `warp` (isteğe bağlı vekil sunucu)

`warp`, koddaki ikinci yolun adıdır: doğrudan bağlantı DNS ya da IPv4 yönlendirme hatası verdiğinde aynı işlemin
kullanıcının verdiği bir HTTP(S) vekil sunucusu (proxy) üzerinden bir kez yeniden denenmesi. Ad, bu tür yerel vekil
sunucu sunan VPN istemcilerinden (ör. Cloudflare WARP'ın yerel proxy kipi) gelir; herhangi bir HTTP(S) vekil
sunucusu çalışır, belirli bir hizmet gerekmez ve repo hiçbir vekil sunucu adresi içermez.

| Ortam değişkeni | Varsayılan | Anlamı |
|---|---|---|
| `DUBLAJ_EGRESS_PROXY` | boş | yedek yolun vekil sunucusu, `http://` ya da `https://` adresi; boşsa yedek yol yoktur ve ağ hatası olduğu gibi yükselir |
| `DUBLAJ_EGRESS_MODE` | `direct` | `direct` ya da `warp`; `warp` baştan vekil sunucuyla başlar ve `DUBLAJ_EGRESS_PROXY` ister |
| `DUBLAJ_DIRECT_RECHECK_SECONDS` | `60` (en az 5) | `warp` yolundayken doğrudan yolun ne sıklıkla yeniden sınanacağı |
| `DUBLAJ_DIRECT_PROBE_HOST` / `DUBLAJ_DIRECT_PROBE_PORT` | `1.1.1.1` / `443` | doğrudan yol sınaması: yalnız bir TCP bağlantısı açılıp kapanır, veri gönderilmez |

Yedek yol etkinken süreç ortamına `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` (küçük harfli eşleriyle) yazılır; alt
süreçler de bunu devralır. `NO_PROXY` listesine `127.0.0.1`, `localhost`, `::1`, `host.docker.internal` eklenir, yerel
servisler (web arayüzü, yerel Telegram Bot API sunucusu) vekil sunucuya gitmez. Doğrudan yol yeniden çalışınca vekil
sunucu değişkenleri kaldırılır. `DUBLAJ_EGRESS_PROXY` boşken (varsayılan) bu kutu hiçbir ağ isteği yapmaz.
