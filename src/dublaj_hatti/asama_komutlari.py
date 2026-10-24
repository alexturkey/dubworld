"""Single-stage CLI subcommands (each stage on its own; same calls as ``dublaj_hatti.api``).

    dubla indir URL [-o klasor]                         # video from a link (extras youtube / galeri)
    dubla ses-cikar video.mp4 [-o ses.wav]              # audio track as 16 kHz mono WAV
    dubla ayir video.mp4 [-o klasor]                    # speech / background separation (extras separation)
    dubla yaziya-dok video.mp4 [-o transcript.json] [--motor M] [--dil en]
    dubla hizala ses.wav metin.txt|transcript.json [-o aligned.json] --dil en
    dubla cevir transcript.json [-o translation.json] [--hedef-dil tr] [--arka-uc yerel]
    dubla seslendir "metin" | metin.txt | translation.json [-o klasor] [--motor supertonic] [--ses F1]
                    [--motor ema_lightning --cihaz auto|cuda|cpu --hiz 1.0]   # EMA: Turkish only
    dubla altyazi transcript.json [-o sub.srt] [--bicim srt|vtt|ass] [--kip segment|kelime|karaoke]
    dubla birlestir video.mp4 -o out.mp4 [--ses speech.wav] [--altyazi sub.srt] [--yak] [--arka-plan bg.wav]

Every command prints the written path(s) on stdout (``--json``: one JSON object), errors on stderr.
Exit codes: 0 success, 1 stage failed, 2 usage / setting / input error / license not accepted.
License gate: a stage that runs a non-commercial or conditional engine (Supertonic in ``seslendir``, CrisperWhisper /
Parakeet in ``yaziya-dok``) asks once, exactly like ``dubla <video>`` (same gate: lisans_onayi.kapi_adlar);
``--lisans-onay`` or DUBLAJ_LISANS_ONAY=1 accepts without a question.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ASAMA_KOMUTLARI = ("indir", "ses-cikar", "ayir", "yaziya-dok", "hizala", "cevir", "seslendir", "altyazi", "birlestir")


def alt_komutlari_ekle(alt: Any, ortak: Callable[[argparse.ArgumentParser], None]) -> None:
    """Adds the stage subcommands to the ``dubla`` parser (``ortak``: the CLI's shared options)."""

    def yeni(ad: str, yardim: str) -> argparse.ArgumentParser:
        p = alt.add_parser(ad, help=yardim, description=yardim)
        p.add_argument("-o", "--cikti-yolu", dest="cikti_yolu", help="output file or folder")
        p.add_argument("--json", action="store_true", help="print the result as one JSON object")
        p.add_argument("--lisans-onay", action="store_true",
                       help="I read and accept the license notice of the selected non-commercial / conditional engine "
                            "(once; stored in ayarlar/lisans_onaylari.json)")
        ortak(p)
        return p

    p = yeni("indir", "video from an https link (optional extras youtube / galeri; only content you may use)")
    p.add_argument("url")
    p = yeni("ses-cikar", "audio track as WAV (16 kHz mono by default)")
    p.add_argument("medya")
    p.add_argument("--ornekleme", type=int, default=16000)
    p.add_argument("--kanal", type=int, default=1, choices=(1, 2))
    p = yeni("ayir", "separate speech and background (Demucs; extras separation)")
    p.add_argument("medya")
    p = yeni("yaziya-dok", "speech-to-text with word timestamps -> transcript.json + .srt")
    p.add_argument("medya")
    p.add_argument("--motor", help="speech-to-text engine (dubla kontrol lists them); default: recommended")
    p.add_argument("--dil", help="source language code or auto (default: transkripsiyon.kaynak_dil)")
    p.add_argument("--srt-yok", action="store_true", help="do not write the .srt next to the JSON")
    p = yeni("hizala", "word timing for a known text (CTC forced alignment)")
    p.add_argument("ses")
    p.add_argument("metin", help="transcript.json / WhisperX JSON / .txt")
    p.add_argument("--dil", help="language code (required for .txt)")
    p = yeni("cevir", "translate a transcript, timing kept -> translation.json")
    p.add_argument("transkript")
    p.add_argument("--hedef-dil", default="tr")
    p.add_argument("--arka-uc", default="yerel", help="yerel, codex, claude_code, gemini_2_5_flash, ... or auto")
    p.add_argument("--kaynak-dil")
    p = yeni("seslendir", "text to speech: text / .txt -> WAV; transcript or translation JSON -> timed track")
    p.add_argument("girdi", help="text in quotes, a .txt file or a transcript/translation JSON")
    p.add_argument("--motor", default="supertonic", choices=("supertonic", "voxcpm2", "ema_lightning"))
    p.add_argument("--ses", help="voice: Supertonic F1-F5/M1-M5, VoxCPM2 voice folder, EMA ema")
    p.add_argument("--cihaz", choices=("auto", "cuda", "cpu"),
                   help="EMA Lightning device (ses.ema_cihaz): auto falls back to CPU when the GPU is missing or busy")
    p.add_argument("--hiz", type=float, help="EMA Lightning speaking speed (ses.ema_hiz, 0.5-2.0)")
    p.add_argument("--dil", default="tr")
    p = yeni("altyazi", "subtitle file from a transcript (no model, no GPU)")
    p.add_argument("transkript")
    p.add_argument("--bicim", choices=("srt", "vtt", "ass"))
    p.add_argument("--kip", default="segment", choices=("segment", "kelime", "karaoke"))
    p = yeni("birlestir", "video + new audio and/or subtitles -> MP4")
    p.add_argument("video")
    p.add_argument("--ses")
    p.add_argument("--altyazi")
    p.add_argument("--yak", action="store_true", help="burn subtitles into the picture (re-encode)")
    p.add_argument("--arka-plan", help="background audio mixed under --ses")
    p.add_argument("--arka-plan-db", type=float, default=-8.0)
    p.add_argument("--ai-etiketi-yok", action="store_true", help="do not write the AI-dubbed metadata tag")


def _varsayilan_cikti(args: argparse.Namespace) -> Path:
    if args.cikti_yolu:
        return Path(args.cikti_yolu)
    komut = args.komut
    kaynak = Path(getattr(args, "medya", None) or getattr(args, "transkript", None) or getattr(args, "ses", None)
                  or getattr(args, "video", None) or ".")
    kok = kaynak.with_suffix("")
    return {
        "indir": Path("."),
        "ses-cikar": kok.with_name(kok.name + ".wav"),
        "ayir": kok.with_name(kok.name + "_ayrim"),
        "yaziya-dok": kok.with_name(kok.name + ".transcript.json"),
        "hizala": kok.with_name(kok.name + ".aligned.json"),
        "cevir": kok.with_name(kok.name.removesuffix(".transcript") + f".{getattr(args, 'hedef_dil', 'tr')}.json"),
        "seslendir": Path("seslendirme"),
        "altyazi": kok.with_name(kok.name + "." + (getattr(args, "bicim", None) or "srt")),
        "birlestir": kok.with_name(kok.name + "_birlesik.mp4"),
    }[komut]


def _calistir(args: argparse.Namespace) -> Any:
    from dublaj_hatti import api

    cikti = _varsayilan_cikti(args)
    k = args.komut
    onay = bool(getattr(args, "lisans_onay", False))
    if k == "indir":
        return api.indir(args.url, cikti, lisans_onay=onay)
    if k == "ses-cikar":
        return api.ses_cikar(args.medya, cikti, args.ornekleme, args.kanal)
    if k == "ayir":
        return api.ayir(args.medya, cikti, lisans_onay=onay)
    if k == "yaziya-dok":
        return api.yaziya_dok(args.medya, cikti, motor=args.motor, dil=args.dil, srt=not args.srt_yok,
                              lisans_onay=onay)
    if k == "hizala":
        return api.hizala(args.ses, args.metin, cikti, dil=args.dil)
    if k == "cevir":
        return api.cevir(args.transkript, cikti, hedef_dil=args.hedef_dil, arka_uc=args.arka_uc,
                         kaynak_dil=args.kaynak_dil, lisans_onay=onay)
    if k == "seslendir":
        ek = {k: v for k, v in (("ses.ema_cihaz", args.cihaz), ("ses.ema_hiz", args.hiz)) if v is not None}
        return api.seslendir(args.girdi, cikti, motor=args.motor, ses=args.ses, dil=args.dil, ayarlar=ek or None,
                             lisans_onay=onay)
    if k == "altyazi":
        return api.altyazi(args.transkript, cikti, bicim=args.bicim, kip=args.kip)
    if k == "birlestir":
        return api.birlestir(args.video, cikti, ses=args.ses, altyazi=args.altyazi, yak=args.yak,
                             arka_plan=args.arka_plan, arka_plan_db=args.arka_plan_db,
                             ai_etiketi=not args.ai_etiketi_yok)
    raise ValueError(k)


def calistir(args: argparse.Namespace) -> int:
    """Runs one stage command; returns the exit code."""
    from dublaj_hatti.api import AsamaHatasi, AyarHatasi, BicimHatasi, KaynakHatasi, LisansOnayiGerekli, ayarlarla
    from dublaj_hatti.lisans_onayi import komut_satiri_onayi

    katman = list(args.ayar) + ([f"genel.cikti_klasoru={args.cikti}"] if args.cikti else [])
    try:
        with ayarlarla(args.ayarlar, katman):
            try:
                sonuc = _calistir(args)
            except LisansOnayiGerekli as gerek:  # the gate fires before any work: ask once, then run again
                if not komut_satiri_onayi(gerek, sys.stdin.isatty()):
                    return 2
                sonuc = _calistir(args)
    except (AyarHatasi, KaynakHatasi, BicimHatasi, FileNotFoundError) as hata:
        print(f"hata: {hata}", file=sys.stderr)
        return 2
    except (AsamaHatasi, RuntimeError, OSError) as hata:
        print(f"aşama başarısız: {hata}", file=sys.stderr)
        return 1
    if isinstance(sonuc, dict):
        cikti = {ad: str(yol) for ad, yol in sonuc.items()}
    else:
        cikti = {"cikti": str(sonuc)}
    if args.json:
        print(json.dumps({"komut": args.komut, **cikti}, ensure_ascii=False))
    else:
        for ad, yol in cikti.items():
            print(f"{ad}: {yol}")
    return 0
