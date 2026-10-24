"""python -m dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts durum | aktar

durum: paket, ağırlık ve ONNX işlemci yolunun durumu (JSON).
aktar: ONNX dosyalarını resmî ağırlıktan üretir ve torch ile eşitliğini denetler (kur.ps1 -Adim tts-ema çağırır).
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv=None) -> int:
    ayr = argparse.ArgumentParser(prog="python -m dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts")
    ayr.add_argument("komut", choices=("durum", "aktar"))
    args = ayr.parse_args(argv)
    if args.komut == "durum":
        from dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts.api import ema_durumu

        print(json.dumps(ema_durumu(), ensure_ascii=False, indent=1))
        return 0
    os.environ["CUDA_VISIBLE_DEVICES"] = ""  # dışa aktarım işlemcide yapılır
    from dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts.onnx_aktar import aktar

    sonuc = aktar()
    print(json.dumps(sonuc, ensure_ascii=False, indent=1))
    if not sonuc["gecti"]:
        print("EMA ONNX eşitlik denetimi GEÇMEDİ: işlemci yolu torch ile çalışır", file=sys.stderr)
        return 2
    print("EMA_ONNX_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
