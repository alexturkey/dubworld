"""EMA Lightning: sabit sürüm, ağırlık özetleri, yollar ve cihaz eşikleri (gerekçeleri docs/engineering/pinned-values.md)."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]

EMA_ENGINE_ID = "ema_lightning"
EMA_PAKET_SURUMU = "1.1.0"  # PyPI ema-lightning; kod Apache-2.0 (requirements/ek_tts_ema.in)
EMA_HF_REPO = "canberkkkkkk/ema-lightning"
EMA_HF_COMMIT = "e7c96f2fc0ba843cd0f86e02786655bb56f50df8"  # model kartı: ses sentetik, ağırlık Apache-2.0
# Yayıncının LFS oid'i = dosyanın sha256'sı (scripts/modeller.json adım tts-ema ile aynı; test eşitliği denetler).
EMA_AGIRLIK_SHA256 = {
    "ema.pt": "95aec03dafbe0e1d69bca774ab597c779464729a14bc99bfcb52480090c7dfe6",
    "decoder.pt": "9595819b173f411340f63d11332695121a97f8bf1f6d8b6fef0b21cf99c7ad67",
}
EMA_SESLER = ("ema",)  # model tek sesli (model kartı: "One voice"); ses tasarımla üretilmiş, gerçek kişi değil
EMA_VARSAYILAN_SES = "ema"
EMA_DILLERI = frozenset({"tr"})  # yalnız Türkçe (model kartı "Limitations")
EMA_ORNEKLEME = 48000
EMA_HIZ_ARALIGI = (0.5, 2.0)  # paket 0.25-4 kabul eder; dublajda anlaşılır kalan aralık (pinned-values)
EMA_CIHAZLAR = ("auto", "cuda", "cpu")
# auto: GPU'da en az bu kadar boş bellek yoksa (başka iş kullanıyor) işlemci yoluna düşülür. Tepe kullanım
# ölçüldü (docs/motorlar/ema_lightning.md); 1 GB, 4 GB'lık kartta da yanlış düşüşe yol açmayan güvenli pay.
EMA_GPU_BOS_MB = 1024
EMA_ONNX_DOSYALARI = ("text.onnx", "sound.onnx", "decoder.onnx")
EMA_ONNX_OPSET = 17
EMA_ONNX_TOLERANS = 1e-3  # dışa aktarım sonrası torch ile en büyük mutlak fark sınırı (ölçülen 3.2e-5)
EMA_KOK_ENV = "DUBLAJ_EMA_KOK"


def ema_kok() -> Path:
    configured = os.environ.get(EMA_KOK_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return PROJECT_ROOT / "runtime_assets" / "tts_motorlari" / "ema_lightning"


def agirlik_dizini() -> Path:
    return ema_kok() / "agirlik"


def onnx_dizini() -> Path:
    return ema_kok() / "onnx"
