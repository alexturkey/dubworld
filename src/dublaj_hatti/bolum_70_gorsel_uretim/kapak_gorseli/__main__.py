"""`python -m dublaj_hatti.bolum_70_gorsel_uretim.kapak_gorseli <transkript.txt> <çıktı klasörü> [--dil tr] [--adet 5]`"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dublaj_hatti.bolum_70_gorsel_uretim.kapak_gorseli.codex_kapak import KapakHatasi, kapak_uret


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kapak_gorseli", description="Transkriptten 9:16 kapak görseli (Codex CLI)")
    ap.add_argument("transkript", type=Path)
    ap.add_argument("cikti", type=Path)
    ap.add_argument("--dil", default="tr")
    ap.add_argument("--adet", type=int, default=5)
    args = ap.parse_args(argv)
    try:
        ozet = kapak_uret(args.transkript.read_text(encoding="utf-8"), args.cikti, args.dil, args.adet)
    except KapakHatasi as hata:
        print(f"kapak üretilemedi ({hata.kod}): {hata}")
        return 0 if hata.kod == "codex_yok" else 1
    print(json.dumps(ozet, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
