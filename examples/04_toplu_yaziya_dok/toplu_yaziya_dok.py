"""Transcribe every video / audio file in a folder; finished files are skipped (safe to re-run).

    python examples/04_toplu_yaziya_dok/toplu_yaziya_dok.py videos/ --cikti transcripts/ [--dil en]

Writes <name>.transcript.json + <name>.srt per file and ozet.csv (file, status, language, segments, words, error).
One failing file does not stop the others.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from dublaj_hatti import api
from dublaj_hatti.bicimler import json_oku

UZANTILAR = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".wav", ".mp3", ".m4a", ".flac"}


def _ozet(yol: Path) -> dict:
    veri = json_oku(yol)
    segmentler = veri.get("segments") or []
    return {"language": veri.get("language", ""), "segments": len(segmentler),
            "words": sum(len(s.get("words") or []) for s in segmentler)}


def main(argv: list[str] | None = None) -> int:
    ayr = argparse.ArgumentParser(description="Transcribe every video / audio file in a folder (resumable).")
    ayr.add_argument("klasor")
    ayr.add_argument("--cikti", default="transkriptler")
    ayr.add_argument("--dil")
    ayr.add_argument("--motor")
    args = ayr.parse_args(argv)

    cikti = Path(args.cikti)
    cikti.mkdir(parents=True, exist_ok=True)
    dosyalar = sorted(p for p in Path(args.klasor).iterdir() if p.is_file() and p.suffix.lower() in UZANTILAR)
    satirlar, hata_sayisi = [], 0
    for dosya in dosyalar:
        hedef = cikti / f"{dosya.stem}.transcript.json"
        durum, hata = "atlandi", ""
        if not hedef.is_file():
            try:
                api.yaziya_dok(dosya, hedef, motor=args.motor, dil=args.dil)
                durum = "tamam"
            except Exception as e:  # noqa: BLE001 - one bad file must not stop the batch
                durum, hata, hata_sayisi = "hata", str(e)[:200], hata_sayisi + 1
        ozet = _ozet(hedef) if hedef.is_file() else {}
        satirlar.append([dosya.name, durum, ozet.get("language", ""), ozet.get("segments", ""),
                         ozet.get("words", ""), hata])
        print(f"{durum:8} {dosya.name}")
    with open(cikti / "ozet.csv", "w", newline="", encoding="utf-8") as f:
        yazar = csv.writer(f)
        yazar.writerow(["file", "status", "language", "segments", "words", "error"])
        yazar.writerows(satirlar)
    print(f"{len(dosyalar)} files, {hata_sayisi} failed -> {cikti / 'ozet.csv'}")
    return 1 if hata_sayisi else 0


if __name__ == "__main__":
    raise SystemExit(main())
