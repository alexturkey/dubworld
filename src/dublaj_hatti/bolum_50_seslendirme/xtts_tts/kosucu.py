"""XTTS koşucusu: coqui-tts kurulu Python'da AYRI SÜREÇ olarak çalışır (model belleği iş bitince tamamen boşalır).

Girdi `--is` JSON: {"referans": wav, "dil": "tr", "calisma": klasör, "parcalar": [{"index": n, "metin": [..]}]}
Çıktı `--sonuc` JSON: {"wavlar": {index: yol}, "hatali": [index], "ornekleme": hz}
Bu dosya paketin geri kalanını içe aktarmaz; yalnız standart kütüphane + coqui-tts + soundfile/numpy kullanır.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

MODEL_ADI = "tts_models/multilingual/multi-dataset/xtts_v2"
ARA_SESSIZLIK_SN = 0.05


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--is", dest="is_dosyasi", required=True)
    ap.add_argument("--sonuc", required=True)
    args = ap.parse_args()
    if os.environ.get("COQUI_TOS_AGREED") != "1":
        print("CPML onayı yok (dublaj_hatti xtts onay)", file=sys.stderr)
        return 3
    is_ = json.loads(Path(args.is_dosyasi).read_text(encoding="utf-8"))

    import numpy as np
    import soundfile as sf
    import torch
    from TTS.api import TTS  # coqui-tts

    cihaz = "cuda" if torch.cuda.is_available() else "cpu"
    tts = TTS(MODEL_ADI, progress_bar=False).to(cihaz)
    sr = int(getattr(getattr(tts, "synthesizer", None), "output_sample_rate", 24000) or 24000)
    calisma = Path(is_["calisma"])
    calisma.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(int(is_.get("tohum", 1234)))
    wavlar: dict[str, str] = {}
    hatali: list[int] = []
    for parca in is_["parcalar"]:
        indeks = int(parca["index"])
        try:
            parcalar = []
            for metin in parca["metin"]:
                ses = np.asarray(tts.tts(text=metin, speaker_wav=is_["referans"], language=is_["dil"]), dtype=np.float32)
                parcalar.append(ses)
                parcalar.append(np.zeros(int(sr * ARA_SESSIZLIK_SN), dtype=np.float32))
            ses = np.concatenate(parcalar[:-1]) if parcalar else np.zeros(0, dtype=np.float32)
            yol = calisma / f"xtts_{indeks:04d}.wav"
            sf.write(str(yol), ses, sr)
            wavlar[str(indeks)] = str(yol)
        except Exception as hata:  # tek segment hatası işi düşürmez; çağıran eksikleri raporlar
            print(f"segment {indeks}: {type(hata).__name__}: {hata}", file=sys.stderr)
            hatali.append(indeks)
    Path(args.sonuc).write_text(json.dumps({"wavlar": wavlar, "hatali": hatali, "ornekleme": sr, "cihaz": cihaz}),
                                encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
