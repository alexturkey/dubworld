# 3D-Speaker vendor kopyası

Bu dizin, isteğe bağlı konuşmacı ayrımının (konuşmacı başına ses) kullandığı 3D-Speaker çıkarım kodunun
sadeleştirilmiş kopyasıdır (yalnız `speakerlab` ses yolu; eğitim örnekleri `egs/` çıkarıldı).

- Upstream: `https://github.com/modelscope/3D-Speaker`
- Başlangıç revizyonu: `065629c313eaf1a01c65c640c46d77e61e9607b4`
- Lisans: Apache-2.0 (`LICENSE`, değiştirilmeden korunur)

Model ağırlıkları (ModelScope CAM++) bu dizine konmaz; isteğe bağlı kurulum adımı indirir.
Bu kopyadaki uyarlamalar `speakerlab/bin/infer_diarization.py` başındaki notta yazılıdır.

## Değişiklikler (Apache-2.0 madde 4b)
- 2026-10-24: güvenlik için tüm `torch.load(...)` çağrılarına `weights_only=True` eklendi; `yaml.load(..., Loader=yaml.Loader|FullLoader)` çağrıları `yaml.safe_load(...)` yapıldı. Başka değişiklik yok.
- 2026-10-24 (lisans): `kaldiio` (NTT değerlendirme lisansı, yeniden dağıtım yasak) ve `funasr` (kaldiio'yu zorunlu ister) kurulumdan çıktı.
  Bu yüzden `speakerlab/bin/infer_diarization.py` içindeki FSMN VAD (modelscope → funasr) yerine faster-whisper paketinin
  içindeki Silero VAD v6 (MIT) kullanılır (`SileroVad`, eşik 0,5, en kısa konuşma 250 ms, en kısa sessizlik 100 ms, pay 30 ms).
  kaldiio/funasr çağıran ve hattın hiç çağırmadığı eğitim/değerlendirme betikleri silindi: `speakerlab/bin/compute_score_metrics.py`,
  `extract.py`, `extract_ssl.py`, `infer_sv_batch.py`, `train_para.py` (kanıt: repo ve kaynak projede bu adlarla tek çağrı yok,
  yalnız kendi içleri ve upstream README). `requirements.txt` içinden `kaldiio` satırı çıkarıldı.
