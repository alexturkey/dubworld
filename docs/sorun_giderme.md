# Sorun giderme: hata kodları

Kurulumdaki ya da ilk çalıştırmadaki her sorunun kararlı bir `DW-E-...` kodu vardır. Kodu ya da gördüğünüz metni bulun, ilk adımı yapın; olmazsa kodla ve çıktının son 30 satırıyla (kişisel yolları silerek) **Hata raporu** ya da **Kurulum sorunu** açın. Aynı liste makine biçiminde [hata_imzalari.json](hata_imzalari.json) dosyasındadır; `scripts/tani.ps1` onu okuyup kodu sizin için söyler. Satır ayrıntıları: [kurulum.md](kurulum.md) bölüm 12. İngilizce: [troubleshooting.md](troubleshooting.md).

## Önce ne yapılır

1. Aynı komutu bir kez yeniden çalıştırın: indirmeler kaldığı yerden sürer, doğru dosyalar atlanır.
2. `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/tani.ps1 -Log kur.log` çalıştırın (yalnız ekrana yazar; hiçbir yere bir şey göndermez).
3. Aynı hata iki kez: durun ve bildirin; üçüncü kez denemeyin.

## Kodlar

| Kod | Ne görürsünüz | İlk adım |
|---|---|---|
| `DW-E-DISK` | `GB boş yer var` | Klasörün bulunduğu sürücüde yer açın (GPU profili ≈ 22 GB, yalnız işlemci ≈ 14 GB) ya da klasörü daha büyük bir sürücüye taşıyın, sonra aynı komutu yeniden çalıştırın. |
| `DW-E-SHA` | `sha256 tutmadı` | Aynı adımı yeniden çalıştırın (yarım dosya silinir, yeniden iner). İki kez başarısızsa sabitlenmiş kaynak değişmiştir: bildirin; hash'i asla elle değiştirmeyin. |
| `DW-E-PAKET` | `paket kurulumu başarısız` | Çoğunlukla internet kesintisi: aynı komutu yeniden çalıştırın. .venv içine tek tek paket kurmayın. |
| `DW-E-MODEL` | `model indirme başarısız` | Aynı komutu yeniden çalıştırın: inen dosyalar korunur, doğru olanlar atlanır. |
| `DW-E-PYTHON` | `Python kurulamadı` | İnternet bağlantısını denetleyip aynı komutu yeniden çalıştırın. |
| `DW-E-TORCH` | `torch denetimi başarısız` | scripts/kur.ps1 -Adim paketler,kontrol komutunu çalıştırın. PyTorch'u CUDA dizini olmadan kurmayın. |
| `DW-E-TORCH-CPU` | `torch CUDA'sız` | GPU profiline CPU PyTorch paketi kurulmuş: scripts/kur.ps1 -Adim paketler,kontrol komutunu çalıştırın. |
| `DW-E-GPU-CEKIRDEK` | `no kernel image is available` | PyTorch derlemesinde bu GPU mimarisi için çekirdek yok. Windows'ta kilitli cu128 derlemesini kullanın; NVIDIA sürücüsünü güncelleyin (R570 ya da yenisi). Program işlemciyle yine çalışır. |
| `DW-E-POLITIKA` | `running scripts is disabled` | kur.cmd'yi kullanın ya da tam olarak powershell -NoProfile -ExecutionPolicy Bypass -File scripts/kur.ps1 biçimini (yalnız o süreci etkiler). |
| `DW-E-LISANS` | `-TicariOlmayanKabul ile yeniden çalıştırın` | Bu adım lisansı insanın okuyup kabul etmesini ister. Yapay zekâ ajanı kullanıcı yerine kabul yazmaz: kullanıcıya sorun, sonra -TicariOlmayanKabul ekleyin. |
| `DW-E-LISANS-DUBLA` | `lisans onayı yok` | Lisans cevabı henüz kayıtlı değil. Kullanıcıya sorun; yalnız evet'iyle komutu --lisans-onay ile yeniden çalıştırın. Kendi başınıza vermeyin. |
| `DW-E-ADIM` | `bilinmeyen adım` | -Adim listesinde kurulum betiğinin tanımadığı bir adım adı var (yazım hatası?). İleti geçerli adları sayar; listeyi düzeltip -Kuru'yu yeniden çalıştırın. |
| `DW-E-ONCE-TABAN` | `Önce taban kurulum` | İsteğe bağlı bir adım ana ortam yokken çalıştırıldı: önce varsayılan kurulumu çalıştırın (scripts/kur.ps1). |
| `DW-E-KARDES-ADRES` | `Kardeş repo adresi ayarlı değil` | DUBLAJ_TTS_REPO_URL / DUBLAJ_STT_REPO_URL değişkenini düzeltin ya da silin (https:// adresi olmalı). |
| `DW-E-GIT` | `VoxCPM2 adımı git ister` | Git'i kurun (winget install Git.Git), yeni bir PowerShell açıp adımı yeniden çalıştırın. |
| `DW-E-WSL` | `wsl.exe yok` | crisper adımı WSL2 ister: wsl --install -d Ubuntu (Ubuntu 24.04), sonra adımı yeniden çalıştırın. |
| `DW-E-NVENC` | `Driver does not support the required nvenc API version` | Yapacak bir şey yok: video adımı kendiliğinden libx264'e düşer. NVIDIA sürücüsünü güncellemek NVENC'i yeniden açar. |
| `DW-E-FP16` | `Requested float16 compute type` | transkripsiyon.hesap_tipi = auto bırakın; Pascal kartlarda hızlı fp16 yoktur, program int8 ya da fp32 seçer. |
| `DW-E-PKGRES` | `No module named pkg_resources` | .venv içinde setuptools'u yükseltmeyin (kilit 80.9.0 sabitler); -Adim paketler adımını yeniden çalıştırın. |

`UYARI` / `WARNING` satırı bilgidir, hata değildir.
