"""XTTS v2 ağırlık lisansı (Coqui Public Model License, CPML) onayı.

Kod (coqui-tts, MPL-2.0) serbesttir; ağırlıklar (coqui/XTTS-v2) CPML altındadır: yalnız TİCARİ OLMAYAN kullanım.
Ağırlık bu repoda yoktur ve otomatik indirilmez: kullanıcı onayı yerel dosyaya yazılmadan motor çalışmaz.
Onay kaydı yalnız tarih ve lisans adresini tutar (kişisel bilgi yok); `runtime_assets/` git dışıdır.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import runtime_asset_root

CPML_ADRESI = "https://coqui.ai/cpml"
MODEL_KARTI = "https://huggingface.co/coqui/XTTS-v2"
LISANS_METNI = (
    "XTTS v2 ağırlıkları Coqui Public Model License (CPML) altındadır: yalnız ticari olmayan kullanım "
    f"({CPML_ADRESI}). Ağırlık ilk kullanımda Coqui'nin kendi indiricisiyle sizin makinenize iner. "
    "Referans ses olarak yalnız kendi sesinizi ya da sahibinin açık izniyle bir sesi kullanın; ünlü ya da "
    "gerçek bir kişiyi izinsiz taklit etmek yasaktır (ETHICS.md)."
)
ONAY_SOZU = "kabul ediyorum"


def xtts_kok() -> Path:
    return runtime_asset_root() / "tts_motorlari" / "xtts"


def onay_dosyasi() -> Path:
    return xtts_kok() / "CPML_ONAYI.json"


def lisans_onayli() -> bool:
    try:
        veri = json.loads(onay_dosyasi().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return veri.get("lisans") == CPML_ADRESI and veri.get("ticari_olmayan_kullanim") is True


def lisans_onayini_kaydet() -> Path:
    yol = onay_dosyasi()
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(".tmp")
    gecici.write_text(json.dumps({
        "lisans": CPML_ADRESI,
        "model_karti": MODEL_KARTI,
        "ticari_olmayan_kullanim": True,
        "tarih_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    gecici.replace(yol)
    return yol
