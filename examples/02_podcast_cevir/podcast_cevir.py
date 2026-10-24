"""Podcast / audio translator: audio -> transcript -> translation -> speech in the target language.

    python examples/02_podcast_cevir/podcast_cevir.py episode.mp3 --cikti out/ [--hedef-dil tr] [--arka-uc yerel]

Every intermediate file stays in the output folder: fix translation.json by hand and re-run with --ses-only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dublaj_hatti import api


def main(argv: list[str] | None = None) -> int:
    ayr = argparse.ArgumentParser(description="Podcast / audio translator: audio -> translated speech.")
    ayr.add_argument("ses", help="audio (or video) file")
    ayr.add_argument("--cikti", default="podcast_ceviri")
    ayr.add_argument("--hedef-dil", default="tr")
    ayr.add_argument("--arka-uc", default="yerel",
                     help="translation backend: yerel (offline, English -> Turkish), codex, claude_code, ...")
    ayr.add_argument("--motor", default="supertonic", choices=("supertonic", "voxcpm2"))
    ayr.add_argument("--ses-adi", help="voice: Supertonic F1-F5 / M1-M5, VoxCPM2 voice folder")
    ayr.add_argument("--ses-only", action="store_true", help="reuse the existing translation.json, only speak it")
    args = ayr.parse_args(argv)

    cikti = Path(args.cikti)
    ceviri = cikti / "translation.json"
    if not (args.ses_only and ceviri.is_file()):
        transkript = api.yaziya_dok(args.ses, cikti / "transcript.json")
        api.cevir(transkript, ceviri, hedef_dil=args.hedef_dil, arka_uc=args.arka_uc)
        api.altyazi(ceviri, cikti / f"subtitles.{args.hedef_dil}.srt")
    print(api.seslendir(ceviri, cikti / "speech", motor=args.motor, ses=args.ses_adi, dil=args.hedef_dil))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
