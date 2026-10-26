# CrisperWhisper Turbo CT2 motor kutusu

Bu kutu, Nyralabs CrisperWhisper2.0 Turbo kombinasyonunun güncel DubWorld
üretim sahibidir. Tek-dil modunda geçerli platform dilini CTranslate2 dil
tablosunda doğrulayıp doğrudan kullanabilir; bilgi yoksa kaynak dili kendi dil
kimliği olasılıklarıyla bulur. Sürekli çok dilli modda platform bilgisi karar
olmaz ve motor ses akışını kendi ölçer.

Bu iletişim internet API'si, HTTP portu veya sürekli sunucu değildir. Auto
Dubber tam 16 kHz mono sesi atomik yerel JSON istekle verir; Ubuntu/WSL2 alt
süreci metni, doğal kelime zamanlarını, tespit edilen dili ve denetim
artefaktlarını geri döndürür. DubWorld'ün ortak job alanı
`use_diarization=false` worker isteğine gönderilmez; motorun yerel API'sinde
diarization girdisi ve konuşmacı çıktısı yoktur.

```text
engine                 = crisperwhisper_turbo_ct2
model                  = CrisperWhisper2.0_turbo
model commit           = de0369c8a68025b7f6e86387b6eb5a3b369787c8
backend                = ctranslate2-crisperwhisper 4.7.1.post3
model storage          = CTranslate2 FLOAT16
runtime                = Ubuntu/WSL2, Python 3.12.3
runtime compute        = CUDA INT8
CPU fallback           = false
language               = platform_or_detected_by_ct2_language_id
language modes         = global_first_window | continuous_stream
word timestamps        = CTC character alignment (application delivery)
forced alignment       = required, separate CUDA subprocess
diarization input      = none
speaker output         = none
```

Üretim giriş noktası `src/worker_entry.py`, Windows köprüsü ise ana projedeki
`src/bolum_00_omurga/runtime/crisperwhisper_turbo_ct2_runtime.py` dosyasıdır. `engine.py`
yalnız kanıtlanmış window/Stitch/coverage yürütme fonksiyonlarını taşır;
üretim yürütmesi benchmark, referans transkript veya deney sesi kullanmaz.
`tests/run_native_acceptance.py`, yalnız açıkça verilen harici ses ve referans
yollarıyla gerçek adaptör kabulünü çalıştıran test aracıdır.

`src/native_softmax.py`, doğrulanan `src/native/` çekirdeğini aynı iş sürecine
bağlar; ardından `src/worker.py` mevcut model/dil/kelime akışını yürütür.
Native dosya kimlikleri `config/native_softmax.json` sahibindedir. Kurulu
CTranslate2 dosyaları değiştirilmez ve deney klasörü çalışma bağımlılığı olmaz.
Güncel çekirdek `softmax_packed_256_v1`; en çok 256 fiziksel thread ile
özgün toplama sırasını korur. Kesin kapsam ve seçim kapısı motor sözleşmesindedir.

Kurulum için `docs/kurulum_ve_yeniden_uretim.md`; ortak job ile yerel motor API
ayrımı, kesin istek/yanıt alanları ve artefakt sözleşmesi için kanonik
`docs/motor_sozlesmesi.md` okunur.

Ortak hazırlık ve pencere içi encoder yeniden kullanımı
`src/runtime_efficiency.py`; tam dosya doğrulama yolu `src/file_integrity.py`
tarafından yönetilir. Süreçler arasında model veya transkript tutulmaz.
Ölçüm alanları ve hata yolları kanonik motor sözleşmesinde açıklanır.

Unicode token grupları ve doğal zaman kapsamının sahibi
`src/multilingual_timing.py` dosyasıdır. Güncel API şeması `3`, runtime
`crisperwhisper_turbo_ct2_v6`; üretim deney kabulü ve tarihsel adayların
ayrımı ana projedeki `docs/crisperwhisper_turbo_ct2_verbatim_kalite_iz_defteri.md`
belgesindedir.

`src/dubbing_ready.py` yerel ayrıştırma kodudur (kaldırılan Medium motorundaki ayrıştırmadan türemiştir).
Worker ana uygulamaya teslimden önce bu dönüşümü uygular; raw ve hazırlanmış
çıktı aynı dublaj klasöründe tutulur. Olay/filler ve checkpoint sözleşmesinin
ayrıntısı `docs/motor_sozlesmesi.md` içindedir.

Native worker kapandıktan sonra adaptör, ana projedeki ortak CTC kelime
hizalama kutusunu (`src/bolum_30_hizalama_ve_segment/ctc_kelime_hizalama`) çağırır. Turbo kutusunda
ayrı bir CTC/WhisperX worker kopyası çalıştırılmaz; kaynak metin ve kelime
dizgeleri alignment sonucunda birebir korunur, yalnız zaman alanları teslim edilir.
`runtime_contract_version` v6 bu zorunlu teslimi ve ortak WhisperX runtime kimliğini
checkpoint/fingerprint sözleşmesine bağlar.
