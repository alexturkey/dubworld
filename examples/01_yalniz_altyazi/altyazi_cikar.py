"""Subtitle extractor: video (or audio) -> transcript.json + SRT + WebVTT, no dubbing.

    python examples/01_yalniz_altyazi/altyazi_cikar.py talk.mp4 --cikti out/ [--dil en] [--motor faster-whisper]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dublaj_hatti import api


def main(argv: list[str] | None = None) -> int:
    ayr = argparse.ArgumentParser(description="Subtitle extractor: video or audio -> SRT + WebVTT.")
    ayr.add_argument("medya", help="video or audio file")
    ayr.add_argument("--cikti", default="altyazilar", help="output folder")
    ayr.add_argument("--dil", help="source language code (default: detect)")
    ayr.add_argument("--motor", help="speech-to-text engine (default: recommended for this machine)")
    args = ayr.parse_args(argv)

    cikti = Path(args.cikti)
    ad = Path(args.medya).stem
    transkript = api.yaziya_dok(args.medya, cikti / f"{ad}.transcript.json", motor=args.motor, dil=args.dil, srt=False)
    for bicim in ("srt", "vtt"):
        print(api.altyazi(transkript, cikti / f"{ad}.{bicim}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
