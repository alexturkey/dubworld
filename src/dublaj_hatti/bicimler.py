"""Stage file formats: the stable contract between pipeline stages (standard library only).

Every stage reads and writes plain files, so each stage can be used alone or swapped for your own tool:

    transcript.json   schema "dublaj-hatti/transcript@1"   (yaziya-dok, hizala)
    translation.json  schema "dublaj-hatti/translation@1"  (cevir)
    speech.json       schema "dublaj-hatti/speech@1"       (seslendir, segment mode)

The segment/word layout is WhisperX-compatible (``segments[].start/end/text/words[].word/start/end/score``), so a
WhisperX JSON file can be read directly. JSON Schema (draft 2020-12) files: ``dublaj_hatti/semalar/*.schema.json``;
:func:`dogrula` checks the same rules without third-party packages.

Subtitle writers (:func:`altyazi_yaz`): SRT, WebVTT, ASS; modes ``segment`` (one cue per segment), ``kelime`` (one
cue per word) and ``karaoke`` (word highlighting: ASS ``\\k`` tags, WebVTT inline timestamps).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

__all__ = [
    "SEMA_TRANSKRIPT",
    "SEMA_CEVIRI",
    "SEMA_SESLENDIRME",
    "ALTYAZI_BICIMLERI",
    "ALTYAZI_KIPLERI",
    "BicimHatasi",
    "transkript_olustur",
    "dogrula",
    "json_oku",
    "json_yaz",
    "transkript_oku",
    "altyazi_metni",
    "altyazi_yaz",
    "duz_metin",
]

SEMA_TRANSKRIPT = "dublaj-hatti/transcript@1"
SEMA_CEVIRI = "dublaj-hatti/translation@1"
SEMA_SESLENDIRME = "dublaj-hatti/speech@1"
SEMALAR = (SEMA_TRANSKRIPT, SEMA_CEVIRI, SEMA_SESLENDIRME)
ALTYAZI_BICIMLERI = ("srt", "vtt", "ass")
ALTYAZI_KIPLERI = ("segment", "kelime", "karaoke")
SEMA_KLASORU = Path(__file__).resolve().with_name("semalar")
SATIR_UZUNLUGU = 42  # common subtitle guideline (characters per line)


class BicimHatasi(ValueError):
    """A stage file does not match its schema."""


# --- building and validating -------------------------------------------------------------------------------
def _kelime(k: dict[str, Any]) -> dict[str, Any]:
    cikti = {"word": str(k.get("word", k.get("kelime", ""))).strip(),
             "start": round(float(k.get("start", k.get("bas", 0.0))), 3),
             "end": round(float(k.get("end", k.get("son", 0.0))), 3)}
    if k.get("score") is not None:
        cikti["score"] = round(float(k["score"]), 4)
    return cikti


def _segment(s: dict[str, Any] | Any, no: int) -> dict[str, Any]:
    if not isinstance(s, dict):  # dataclass segment of the pipeline (NihaiDublajSegmenti) or similar
        s = {a: getattr(s, a) for a in ("start", "end", "text", "speaker", "words") if hasattr(s, a)}
    cikti: dict[str, Any] = {"id": int(s.get("id", no)), "start": round(float(s["start"]), 3),
                             "end": round(float(s["end"]), 3), "text": str(s.get("text", "")).strip()}
    if s.get("speaker"):
        cikti["speaker"] = str(s["speaker"])
    if s.get("source_text") is not None:
        cikti["source_text"] = str(s["source_text"])
    kelimeler = [_kelime(k) for k in (s.get("words") or []) if str(k.get("word", k.get("kelime", ""))).strip()]
    if kelimeler:
        cikti["words"] = kelimeler
    return cikti


def transkript_olustur(segmentler: Iterable[Any], dil: str, *, sema: str = SEMA_TRANSKRIPT,
                       kaynak_dil: str | None = None, motor: str | None = None,
                       kaynak: str | None = None) -> dict[str, Any]:
    """Builds a transcript@1 / translation@1 document from dicts (WhisperX layout) or pipeline segments."""
    veri: dict[str, Any] = {"schema": sema, "language": str(dil or "und").lower()}
    if kaynak_dil:
        veri["source_language"] = str(kaynak_dil).lower()
    if motor:
        veri["engine"] = motor
    if kaynak:
        veri["source"] = Path(kaynak).name  # file name only: no local paths in shared files
    veri["segments"] = [_segment(s, no) for no, s in enumerate(segmentler, 1)]
    return veri


def _hata(yer: str, mesaj: str) -> BicimHatasi:
    return BicimHatasi(f"{yer}: {mesaj}")


def _zaman(deger: Any, yer: str) -> float:
    if isinstance(deger, bool) or not isinstance(deger, int | float):
        raise _hata(yer, "number expected")
    if deger < 0:
        raise _hata(yer, "negative time")
    return float(deger)


def dogrula(veri: dict[str, Any]) -> dict[str, Any]:
    """Checks a stage document; returns it unchanged or raises :class:`BicimHatasi`."""
    if not isinstance(veri, dict):
        raise BicimHatasi("top level must be a JSON object")
    sema = veri.get("schema")
    if sema not in SEMALAR:
        raise _hata("schema", f"expected one of {', '.join(SEMALAR)}, got {sema!r}")
    if sema == SEMA_SESLENDIRME:
        for anahtar in ("engine", "sample_rate", "audio", "segments"):
            if anahtar not in veri:
                raise _hata(anahtar, "required")
        if not isinstance(veri["sample_rate"], int) or veri["sample_rate"] <= 0:
            raise _hata("sample_rate", "positive integer expected")
    elif not isinstance(veri.get("language"), str) or not veri["language"]:
        raise _hata("language", "language code required")
    if sema == SEMA_CEVIRI and not veri.get("source_language"):
        raise _hata("source_language", "required for a translation")
    segmentler = veri.get("segments")
    if not isinstance(segmentler, list):
        raise _hata("segments", "list expected")
    for i, s in enumerate(segmentler):
        yer = f"segments[{i}]"
        if not isinstance(s, dict):
            raise _hata(yer, "object expected")
        bas, son = _zaman(s.get("start"), f"{yer}.start"), _zaman(s.get("end"), f"{yer}.end")
        if son < bas:
            raise _hata(yer, f"end {son} < start {bas}")
        if not isinstance(s.get("text"), str):
            raise _hata(f"{yer}.text", "string expected")
        for j, k in enumerate(s.get("words") or []):
            kyer = f"{yer}.words[{j}]"
            if not isinstance(k, dict) or not isinstance(k.get("word"), str):
                raise _hata(kyer, "object with 'word' expected")
            kb, ks = _zaman(k.get("start"), f"{kyer}.start"), _zaman(k.get("end"), f"{kyer}.end")
            if ks < kb:
                raise _hata(kyer, f"end {ks} < start {kb}")
        if sema == SEMA_SESLENDIRME and not isinstance(s.get("audio"), str):
            raise _hata(f"{yer}.audio", "relative path of the segment audio expected")
    return veri


# --- files -------------------------------------------------------------------------------------------------
def json_yaz(yol: str | Path, veri: dict[str, Any]) -> Path:
    """Writes JSON atomically (temporary file + replace): an interrupted run never leaves a half file."""
    yol = Path(yol)
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_name(yol.name + ".part")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(gecici, yol)
    return yol


def json_oku(yol: str | Path) -> dict[str, Any]:
    veri = json.loads(Path(yol).read_text(encoding="utf-8-sig"))
    if not isinstance(veri, dict):
        raise BicimHatasi(f"{yol}: JSON object expected")
    return veri


def transkript_oku(yol: str | Path, dil: str | None = None) -> dict[str, Any]:
    """Reads transcript@1 / translation@1, or a plain WhisperX JSON (``segments`` + optional ``language``)."""
    veri = json_oku(yol)
    if "schema" not in veri:  # WhisperX / faster-whisper style dump
        veri = transkript_olustur(veri.get("segments") or [], dil or veri.get("language") or "und")
    return dogrula(veri)


# --- subtitles ---------------------------------------------------------------------------------------------
def _sure(sn: float, ayrac: str) -> str:
    ms = max(0, int(round(sn * 1000)))
    s, ms = divmod(ms, 1000)
    d, s = divmod(s, 60)
    sa, d = divmod(d, 60)
    return f"{sa:02d}:{d:02d}:{s:02d}{ayrac}{ms:03d}"


def _ass_sure(sn: float) -> str:
    cs = max(0, int(round(sn * 100)))
    s, cs = divmod(cs, 100)
    d, s = divmod(s, 60)
    sa, d = divmod(d, 60)
    return f"{sa}:{d:02d}:{s:02d}.{cs:02d}"


def _satirlara_bol(metin: str, genislik: int = SATIR_UZUNLUGU) -> str:
    """At most two balanced lines (broadcast subtitle habit); longer text stays on two longer lines."""
    metin = " ".join(metin.split())
    if len(metin) <= genislik:
        return metin
    kelimeler = metin.split(" ")
    en_iyi, fark = 1, len(metin)
    for i in range(1, len(kelimeler)):
        sol, sag = " ".join(kelimeler[:i]), " ".join(kelimeler[i:])
        if abs(len(sol) - len(sag)) < fark:
            en_iyi, fark = i, abs(len(sol) - len(sag))
    return " ".join(kelimeler[:en_iyi]) + "\n" + " ".join(kelimeler[en_iyi:])


def _ipuclari(veri: dict[str, Any], kip: str) -> list[tuple[float, float, str, list[dict[str, Any]]]]:
    ipuclari = []
    for s in veri["segments"]:
        metin, kelimeler = s.get("text", "").strip(), s.get("words") or []
        if kip == "kelime" and kelimeler:
            ipuclari += [(k["start"], k["end"], k["word"], [k]) for k in kelimeler]
        elif metin:
            ipuclari.append((s["start"], s["end"], metin, kelimeler))
    return ipuclari


def _ass_metni(ipuclari: list[tuple[float, float, str, list[dict[str, Any]]]], kip: str) -> str:
    bas = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n\n"
           "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
           "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
           "MarginL, MarginR, MarginV, Encoding\n"
           "Style: Default,Arial,56,&H00FFFFFF,&H0000D7FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,3,1,2,60,60,50,1\n"
           # karaoke: spoken words turn gold (Primary), words still to come stay white (Secondary)
           "Style: Karaoke,Arial,56,&H0000D7FF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,3,1,2,60,60,50,1\n\n"
           "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    satirlar = []
    for b, s, metin, kelimeler in ipuclari:
        if kip == "karaoke" and kelimeler:
            parcalar, imlec = [], b
            for k in kelimeler:
                if k["start"] > imlec:  # silence before the word: empty karaoke step keeps the timing exact
                    parcalar.append(f"{{\\k{round((k['start'] - imlec) * 100)}}}")
                parcalar.append(f"{{\\k{max(1, round((k['end'] - k['start']) * 100))}}}{k['word']} ")
                imlec = k["end"]
            govde = "".join(parcalar).rstrip()
        else:
            govde = _satirlara_bol(metin).replace("\n", "\\N")
        stil = "Karaoke" if kip == "karaoke" and kelimeler else "Default"
        satirlar.append(f"Dialogue: 0,{_ass_sure(b)},{_ass_sure(s)},{stil},,0,0,0,,{govde}")
    return bas + "\n".join(satirlar) + "\n"


def altyazi_metni(veri: dict[str, Any], bicim: str = "srt", kip: str = "segment") -> str:
    """Renders a transcript/translation document as subtitle text."""
    if bicim not in ALTYAZI_BICIMLERI:
        raise BicimHatasi(f"subtitle format must be one of {', '.join(ALTYAZI_BICIMLERI)}")
    if kip not in ALTYAZI_KIPLERI:
        raise BicimHatasi(f"subtitle mode must be one of {', '.join(ALTYAZI_KIPLERI)}")
    ipuclari = _ipuclari(dogrula(veri), kip)
    if bicim == "ass":
        return _ass_metni(ipuclari, kip)
    if bicim == "srt":
        bloklar = [f"{n}\n{_sure(b, ',')} --> {_sure(s, ',')}\n{_satirlara_bol(m)}\n"
                   for n, (b, s, m, _k) in enumerate(ipuclari, 1)]
        return "\n".join(bloklar)
    bloklar = []
    for b, s, metin, kelimeler in ipuclari:
        if kip == "karaoke" and kelimeler:  # WebVTT karaoke: inline timestamp before every word after the first
            govde = " ".join((f"<{_sure(k['start'], '.')}>" if i else "") + k["word"] for i, k in enumerate(kelimeler))
        else:
            govde = _satirlara_bol(metin)
        bloklar.append(f"{_sure(b, '.')} --> {_sure(s, '.')}\n{govde}\n")
    return "WEBVTT\n\n" + "\n".join(bloklar)


def altyazi_yaz(veri: dict[str, Any], hedef: str | Path, bicim: str | None = None, kip: str = "segment") -> Path:
    """Writes a subtitle file; the format comes from ``bicim`` or the file extension."""
    hedef = Path(hedef)
    bicim = (bicim or hedef.suffix.lstrip(".") or "srt").lower()
    metin = altyazi_metni(veri, bicim, kip)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_name(hedef.name + ".part")
    gecici.write_text(metin, encoding="utf-8-sig" if bicim == "ass" else "utf-8")
    os.replace(gecici, hedef)
    return hedef


def duz_metin(veri: dict[str, Any]) -> str:
    """Plain text, one segment per line."""
    return "\n".join(s["text"].strip() for s in dogrula(veri)["segments"] if s["text"].strip()) + "\n"
