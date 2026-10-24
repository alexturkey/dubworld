"""`python -m dublaj_hatti.bolum_50_seslendirme.xtts_tts durum | onay [--kabul]`"""

from __future__ import annotations

import argparse
import json

from dublaj_hatti.bolum_50_seslendirme.xtts_tts.api import xtts_durumu
from dublaj_hatti.bolum_50_seslendirme.xtts_tts.lisans import LISANS_METNI, ONAY_SOZU, lisans_onayini_kaydet


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="xtts_tts", description="XTTS v2 durum ve CPML lisans onayı")
    alt = ap.add_subparsers(dest="komut", required=True)
    alt.add_parser("durum")
    onay = alt.add_parser("onay")
    onay.add_argument("--kabul", action="store_true", help="metni okudum, ticari olmayan kullanımı kabul ediyorum")
    args = ap.parse_args(argv)
    if args.komut == "durum":
        print(json.dumps(xtts_durumu(), ensure_ascii=False, indent=2))
        return 0
    print(LISANS_METNI)
    if not args.kabul:
        try:
            yanit = input(f'Kabul ediyorsanız "{ONAY_SOZU}" yazın: ')
        except EOFError:
            yanit = ""
        if yanit.strip().lower() != ONAY_SOZU:
            print("Onay verilmedi; XTTS kapalı kalır.")
            return 1
    print(f"Onay kaydedildi: {lisans_onayini_kaydet()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
