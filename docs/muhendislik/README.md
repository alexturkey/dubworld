# Mühendislik notları

English: [../engineering/README.md](../engineering/README.md)

Hattın (pipeline, işlem zinciri) her parçasının bugünkü hâline nasıl geldiği: karşılaşılan sorunlar, kök nedenleri,
denenip reddedilenler, çözüm, öncesi ve sonrası ölçümler ve hâlâ açık kalanlar. Katkı verenler ve yapay zekâ kod
ajanları için yazıldı (bkz. `AGENTS.md`).

Her sayfada kullanılan kanıt etiketleri: **ölçüldü** (proje bunu çalıştırdı ve sayıları sakladı; aksi belirtilmedikçe
referans makine: 4 GB VRAM (ekran kartı belleği), Pascal sınıfı GPU (ekran kartı işlemcisi), compute capability
(hesaplama yeteneği sürümü) 6.1, Windows, 16 GB RAM), **belgelendi** (saklanmış bir çalıştırma olmadan kayda geçmiş
kural ya da bulgu), **kayıt yok** (bilinmiyor; varsayma).

| Sayfa | Kapsadığı |
|---|---|
| [hat_akisi.md](hat_akisi.md) | **Bağlantıdan ya da dosyadan teslim edilen videoya bütün iş**: aşamalar, aralarındaki dosyalar, ayara göre dallanmalar, transkriptin neden kelime zamanlarından yeniden gruplandığı |
| [dusuk_vram.md](dusuk_vram.md) | **4 GB kartta ya da yalnız CPU olan makinede buradan başla**: ayarlar, belirtiler, çözümler |
| [gpu_bellek_ve_yalitim.md](gpu_bellek_ve_yalitim.md) | Model başına VRAM bütçesi, OOM (bellek yetmedi hatası) teşhisi, model başına tek süreç, ortamlar, model önbelleği, kaynak kilidi, ölçüm yöntemi |
| [kaynak_ses_ve_ayristirma.md](kaynak_ses_ve_ayristirma.md) | Ses çıkarma, ters faz düzeltmesi, Demucs (toplu işleme, iki parçalı (stem) RAM çalışması, OOM yedeği), otomatik arka plan algılama |
| [transkripsiyon.md](transkripsiyon.md) | faster-whisper, WhisperX, Parakeet, whisper.cpp, bulut motorları, VAD, dil algılama, motor karşılaştırması |
| [crisperwhisper_turbo_ct2.md](crisperwhisper_turbo_ct2.md) | İsteğe bağlı kelimesi kelimesine motorlar (12 ve 13): CT2/int8/WSL2, uzun kayıt düzeltmeleri, çok dilli çalışma, hız |
| [kelime_hizalama.md](kelime_hizalama.md) | CTC zorlamalı hizalama: neden, pencere hazırlama, kelime sonlarındaki sessizlik, boşluksuz yazı sistemleri, sayılar |
| [zaman_kaynaklari.md](zaman_kaynaklari.md) | Her kelime zamanı nereden gelir: motor başına kaynak, YouTube json3 altyazısı, CTC'nin atlandığı yerler, karar akışı |
| [konusmaci_ve_segmentler.md](konusmaci_ve_segmentler.md) | Dublaj bölütleme, konuşmacı ayrımı (diarization; 3D-Speaker), cinsiyet, konuşmacı başına ses, tam metin kipi |
| [ceviri.md](ceviri.md) | Codex / Claude CLI köprüleri, doğal bloklar sözleşmesi, konuşma biçimleri, API sağlayıcıları, Opus-MT, hata sözleşmesi |
| [tts_zamanlama_ve_karisim.md](tts_zamanlama_ve_karisim.md) | Supertonic (sabit hız, CPU hızı, tarif, sessizlik temizliği, yaşam döngüsü), aday hizalama, atempo, ses yüksekliği, arka plan karışımı, VoxCPM2 |
| [video_altyazi_ve_devam.md](video_altyazi_ve_devam.md) | Kodlayıcı seçimi, tek geçişli kodlama, boyut politikası, altyazı sözleşmesi, kontrol noktaları/devam, kullanıcı hataları, duman testi bulguları |
| [sabit_degerler.md](sabit_degerler.md) | Bütün sabit değerler (ses kimlikleri ve hızları, eşikler, pencereler, toplu boylar, zaman aşımları, örnekleme hızları): nerede, neden, değişirse ne bozulur |

Kararlar ADR (mimari karar kaydı) olarak [../adr/](../adr/README.md) altında tutulur.

## Bir şeyi değiştirmeden önce bilinmeye değer on şey

1. Her ağır model kendi sürecinde çalışır; aynı anda tek GPU işi ([ADR 0001](../adr/0001-one-gpu-job-and-process-per-model.md)).
2. Pascal'da fp16 daha hızlı değildir; int8 hızlıdır. `cudnn.benchmark` ya da `CUDA_LAUNCH_BLOCKING` asla açılmaz.
3. Toplu iş (batch) boyutları tahmin edilmedi, ölçüldü (WhisperX: batch 1, 2'den ≈ %41 daha hızlı; Demucs: batch 4, 1'den ≈ %20 daha hızlı).
4. Demucs'un en büyük maliyeti GPU değil, RAM ve verinin bellekte kalma süresiydi (iki parçalı (stem) işçi: 2× hızlı, −2,4 GB RAM).
5. Bir "OOM", GPU'yu paylaşan başka bir bileşen ya da bir girdi uzunluğu sınırı olabilir; hassasiyeti (precision) değiştirmeden önce teşhis koy.
6. Önerilen akışın (`auto`: CrisperWhisper Turbo ya da `faster_whisper_ctc`) kelime zamanları CTC zorlamalı hizalamadan gelir; sessizlik ölçülen konuşma aralığıyla sınırlanır. Kendi zamanını koruyan motorlar: [zaman_kaynaklari.md](zaman_kaynaklari.md) §4.
7. Çeviri yalıtılmış CLI zarflarında çalışır; tek bir eksik bayrak bir keresinde çeviri süresini 23 katına çıkardı.
8. Zamanlamayı gerçek sentezlenmiş süre belirler; TTS (metinden sese) modelinin içindeki hız ses başına sabittir.
9. Hiçbir şey sessizce yedeğe düşmez; yeniden denemeler aynı motorun içinde kalır ve kayda geçer.
10. Her aşama bir girdi parmak izi ve bir sözleşme sürümüyle kontrol noktasına yazılır; davranış değişince sürüm artırılır.

## Değişiklikler nasıl kabul edildi

Yalıtılmış deney → aynı girdi özeti (hash), tek değişken değişir → çıktılar örnek örnek ya da zamanlarıyla kelime kelime
karşılaştırılır → işçi süresi ve uygulama süresi ayrı ölçülür → birleştirmeden önce gerçek giriş noktasından ikinci bir
kanıt. Kısa testler yetmez: birkaç hata (çözücü döngüleri, zamanlama ters dönmeleri, 400 s girdi sınırı) yalnız uzun
dosyalarda ortaya çıktı.
