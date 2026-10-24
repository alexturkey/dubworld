"""Word-by-word karaoke subtitles: video -> word times -> ASS karaoke -> video with burned-in subtitles.

    python examples/05_karaoke_altyazi/karaoke.py clip.mp4 --cikti out/ [--dil en] [--yalniz-ass]
    python examples/05_karaoke_altyazi/karaoke.py clip.mp4 --transkript clip.transcript.json   # reuse word times
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dublaj_hatti import api


def main(argv: list[str] | None = None) -> int:
    ayr = argparse.ArgumentParser(description="Word-by-word karaoke subtitles burned into a video.")
    ayr.add_argument("video")
    ayr.add_argument("--cikti", default="karaoke")
    ayr.add_argument("--dil")
    ayr.add_argument("--transkript", help="existing transcript.json with word times (skips speech-to-text)")
    ayr.add_argument("--yalniz-ass", action="store_true", help="write the .ass file only, do not render the video")
    args = ayr.parse_args(argv)

    cikti = Path(args.cikti)
    ad = Path(args.video).stem
    if args.transkript:
        transkript = Path(args.transkript)
    else:
        transkript = api.yaziya_dok(args.video, cikti / f"{ad}.transcript.json", dil=args.dil, srt=False)
    ass = api.altyazi(transkript, cikti / f"{ad}.karaoke.ass", kip="karaoke")
    print(ass)
    if not args.yalniz_ass:
        print(api.birlestir(args.video, cikti / f"{ad}.karaoke.mp4", altyazi=ass, yak=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
