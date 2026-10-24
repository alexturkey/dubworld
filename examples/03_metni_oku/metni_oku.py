"""Read a text aloud with the TTS engine and voice you choose.

    python examples/03_metni_oku/metni_oku.py "Merhaba, bu bir deneme." --cikti out/
    python examples/03_metni_oku/metni_oku.py chapter.txt --motor voxcpm2 --ses hazir/haber_spikeri
"""

from __future__ import annotations

import argparse

from dublaj_hatti import api


def main(argv: list[str] | None = None) -> int:
    ayr = argparse.ArgumentParser(description="Read a text aloud with the chosen TTS engine and voice.")
    ayr.add_argument("metin", help="text in quotes or a .txt file (UTF-8)")
    ayr.add_argument("--cikti", default="okuma")
    ayr.add_argument("--motor", default="supertonic", choices=("supertonic", "voxcpm2"))
    ayr.add_argument("--ses", help="Supertonic F1-F5 / M1-M5 (default F1); VoxCPM2 voice folder (NVIDIA GPU)")
    ayr.add_argument("--dil", default="tr")
    args = ayr.parse_args(argv)

    print(api.seslendir(args.metin, args.cikti, motor=args.motor, ses=args.ses, dil=args.dil))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
