"""Legal and privacy gate: nothing illegal, unclear or personal enters the repository.

Usage:
    python scripts/yasal_denetim.py                    # scan the repository this script lives in
    python scripts/yasal_denetim.py --kok <dir>        # scan another tree
    python scripts/yasal_denetim.py --json             # machine-readable findings
    python scripts/yasal_denetim.py --kisisel <file>   # extra private terms (names, handles), one per line;
                                                       # the file must live OUTSIDE the repository
Exit code: 0 = clean, 1 = findings, 2 = usage error.

Rules (each finding names its rule):
  edge_tts          edge-tts / unofficial Microsoft speech endpoint
  google_resmi_degil  unofficial Google Translate clients and endpoints
  xtts_referans     XTTS / Coqui reference-voice folders (real people's voices)
  medya_dosyasi     audio/video files in the tree (real voices, copyrighted media) unless allow-listed
  medya_meta        EXIF / ID3 / RIFF INFO / PNG text / MP4 tag metadata inside allow-listed media
  sir               keys, tokens, private keys (value masked in the report)
  kisisel_yol       user-profile and drive paths (C:\\Users\\..., /home/<name>, E:\\..., /c/Users/...)
  e_posta           e-mail addresses other than noreply / example placeholders
  telegram          Telegram chat ids, bot tokens, bot names, t.me links
  kullanim_izi      personal usage statistics ("last 2 months", "42 jobs", "author's settings", ...)
  zaman_izi         time-zone hints and date-stamped work-folder names
  kisisel_terim     terms from the private --kisisel list (or env YASAL_DENETIM_KISISEL)
  git_yazar         git author/committer e-mail that is not a noreply address

False positives go to `scripts/yasal_denetim_izin.txt` (narrow: rule + path glob + optional text regex + reason).
This file, its test and the allow-list are excluded from content rules because they contain the patterns.
Standard library only; never prints a secret in full.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import struct
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

KOK_VARSAYILAN = Path(__file__).resolve().parents[1]
IZIN_DOSYASI = "scripts/yasal_denetim_izin.txt"
KENDI = {"scripts/yasal_denetim.py", "tests/test_yasal_denetim.py", IZIN_DOSYASI}

ATLA_KLASOR = {
    ".git", "__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache", ".venv", "venv", "node_modules",
    "runtime_assets", "cikti", "build", "dist",
}
ATLA_UZANTI = {".pyc", ".pyo", ".safetensors", ".bin", ".pth", ".gguf", ".onnx", ".pt", ".ckpt", ".zip", ".7z"}
MEDYA_UZANTI = {
    ".wav", ".mp3", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".wma",
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v",
}
GORSEL_UZANTI = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic"}
METIN_SINIR = 2_000_000  # bytes; larger text files are reported, not read

# --- content rules ----------------------------------------------------------------------------------------
_K = re.IGNORECASE
KURALLAR: list[tuple[str, re.Pattern[str]]] = [
    ("edge_tts", re.compile(r"\bedge[-_]tts\b|speech\.platform\.bing\.com|readaloud/edge", _K)),
    ("google_resmi_degil", re.compile(
        r"\bgoogletrans\b|\bdeep[-_]translator\b|GoogleTranslator\b|translate\.googleapis\.com"
        r"|translate\.google\.[a-z.]+/translate_a|clients\d*\.google\.com/translate_a|translate_tts\?", _K)),
    ("xtts_referans", re.compile(r"\bxtts[-_ ]?v?2?[/\\]references\b|coqui[/\\]XTTS-v2[/\\]samples", _K)),
    ("sir", re.compile(
        r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"          # OpenAI / Anthropic
        r"|\bAIza[0-9A-Za-z_-]{35}\b"                      # Google API key
        r"|\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b"
        r"|\bhf_[A-Za-z0-9]{30,}\b"                        # Hugging Face
        r"|\bgsk_[A-Za-z0-9]{40,}\b"                       # Groq
        r"|\bcsk-[a-z0-9]{40,}\b"                          # Cerebras
        r"|\bxox[abpr]-[A-Za-z0-9-]{10,}"                  # Slack
        r"|\bAKIA[0-9A-Z]{16}\b"                           # AWS
        r"|-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
        r"|\b(?:api[_-]?key|secret|token|password|passwd)\s*[=:]\s*['\"][A-Za-z0-9_\-./+]{16,}['\"]", _K)),
    ("telegram", re.compile(
        r"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}\b"               # bot token
        r"|\bchat[_-]?id\s*[=:]\s*['\"]?-?\d{6,}"          # chat id value
        r"|(?<![\w.])-100\d{9,}\b"                          # supergroup/channel id
        r"|\bt\.me/[A-Za-z0-9_]{4,}"
        r"|@[A-Za-z0-9_]{3,}_?bot\b", _K)),
    ("kisisel_yol", re.compile(
        r"\b[A-Za-z]:[\\/]+(?:Users|Documents and Settings)[\\/]+(?!<|\{|%|\$|USER|YOU|user\b|example)[^\\/\s\"'`]+"
        r"|/(?:c|mnt/c)/Users/(?!<|\{|\$)[^/\s\"'`]+"
        r"|/home/(?!<|\{|\$|runner\b|user\b|ubuntu\b)[a-z0-9_.-]+/"
        r"|/Users/(?!<|\{|\$|Shared\b|runner\b|user\b)[A-Za-z0-9_.-]+/"
        r"|(?<![\w`])[D-Z]:[\\/]+[A-Za-z0-9_]", 0)),
    ("e_posta", re.compile(
        r"\b[A-Za-z0-9._%+-]+@(?!(?:users\.)?noreply\.|example\.(?:com|org|net)\b|localhost\b)"
        r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")),
    ("kullanim_izi", re.compile(
        # Number words count too, and Turkish suffixes ("aydaki", "işinde"): a sentence like "the author's last two
        # months, 42 jobs" once slipped through because the rule knew only digits and exact endings.
        r"\bson\s+(?:\d+|bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz|on)\s+(?:ay|hafta|gün)\w*"
        r"|\blast\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:months?|weeks?|days?)\b"
        r"|\b\d+\s*/\s*\d+\s+(?:iş|job)"
        r"|\b\d{2,}\s+(?:iş(?!\s+parçac)\w*|jobs?\b|runs?\b)"
        r"|yazar[ıi]n\s+(?:ayarlar|son\b|kulland|tercih|\d+)|author'?s\s+(?:settings|defaults|last|own\s+runs)"
        r"|kullan[ıi]m[ıi]n\s+%\s*\d+|%\s*\d+'?[iı]?\s+(?:bu|this)\s+motor|en\s+çok\s+seçilen|most\s+(?:used|chosen)\s+by\s+(?:me|the author)", _K)),
    ("zaman_izi", re.compile(
        r"Europe/Istanbul|\bUTC\s*\+\s*0?3\b|\bGMT\s*\+\s*0?3\b|T\d{2}:\d{2}(?::\d{2})?\+03:00|Türkiye\s+saati|Turkey\s+time", _K)),
]
YOL_ZAMAN = re.compile(r"(?:^|[/_-])(?:20\d{6}[_-]\d{4,6}|20\d{2}-\d{2}-\d{2}[_-][A-Za-z0-9])")


@dataclass
class Bulgu:
    kural: str
    yol: str
    satir: int
    metin: str


@dataclass
class Izin:
    kural: str
    glob: str
    desen: re.Pattern[str] | None
    neden: str


def _maskele(kural: str, metin: str) -> str:
    metin = metin.strip()
    if kural in ("sir", "telegram") and len(metin) > 8:
        return metin[:4] + "…" + f"({len(metin)} chars)"
    return metin[:120]


def izinleri_oku(kok: Path) -> list[Izin]:
    dosya = kok / IZIN_DOSYASI
    if not dosya.exists():
        return []
    izinler = []
    for no, satir in enumerate(dosya.read_text(encoding="utf-8").splitlines(), 1):
        satir = satir.strip()
        if not satir or satir.startswith("#"):
            continue
        parca = [p.strip() for p in satir.split(" | ", 3)]  # " | " separator: a regex may contain a bare "|"
        if len(parca) != 4 or not parca[3]:
            raise SystemExit(f"{IZIN_DOSYASI}:{no}: format is 'rule | path glob | text regex or - | reason' (spaces around |)")
        if parca[1] in ("*", "**", "**/*"):
            raise SystemExit(f"{IZIN_DOSYASI}:{no}: allow-list must be narrow (no repository-wide glob)")
        izinler.append(Izin(parca[0], parca[1], None if parca[2] in ("", "-") else re.compile(parca[2]), parca[3]))
    return izinler


def _izinli(b: Bulgu, izinler: list[Izin]) -> bool:
    for i in izinler:
        if i.kural == b.kural and fnmatch.fnmatch(b.yol, i.glob) and (i.desen is None or i.desen.search(b.metin)):
            return True
    return False


def dosyalari_listele(kok: Path) -> list[Path]:
    """Files that would be committed: `git ls-files` when available, otherwise a walk that honours .gitignore."""
    if (kok / ".git").exists():
        try:
            cikti = subprocess.run(
                ["git", "-C", str(kok), "ls-files", "-co", "--exclude-standard", "-z"],
                capture_output=True, check=True, timeout=60,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout.decode("utf-8", "replace")
            return [kok / p for p in cikti.split("\0") if p and (kok / p).is_file()]
        except (OSError, subprocess.SubprocessError):
            pass
    desenler = gitignore_desenleri(kok)
    sonuc = []
    for dizin, klasorler, dosyalar in os.walk(kok):
        ust = Path(dizin).relative_to(kok).as_posix()
        ust = "" if ust == "." else ust + "/"
        klasorler[:] = [
            k for k in klasorler
            if k not in ATLA_KLASOR and not k.endswith(".egg-info") and not gitignore_eslesir(ust + k, True, desenler)
        ]
        sonuc.extend(Path(dizin) / d for d in dosyalar if not gitignore_eslesir(ust + d, False, desenler))
    return sonuc


def gitignore_desenleri(kok: Path) -> list[tuple[str, bool, bool]]:
    """Root .gitignore as (pattern, directory only, anchored); used when the tree is not (yet) a git repository.

    Supported subset: comments, blank lines, trailing "/" (directories), leading or inner "/" (anchored to the
    root) and shell globs. Negations ("!") are skipped on purpose: the scan then covers MORE files, never fewer.
    """
    dosya = kok / ".gitignore"
    if not dosya.is_file():
        return []
    desenler = []
    for satir in dosya.read_text(encoding="utf-8", errors="replace").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith(("#", "!")):
            continue
        yalniz_dizin = satir.endswith("/")
        satir = satir.rstrip("/")
        desenler.append((satir.lstrip("/"), yalniz_dizin, "/" in satir))
    return desenler


def gitignore_eslesir(goreli: str, dizin_mi: bool, desenler: list[tuple[str, bool, bool]]) -> bool:
    ad = goreli.rsplit("/", 1)[-1]
    for desen, yalniz_dizin, sabit in desenler:
        if yalniz_dizin and not dizin_mi:
            continue
        if fnmatch.fnmatchcase(goreli if sabit else ad, desen):
            return True
    return False


# --- media metadata (stdlib only) -------------------------------------------------------------------------
def medya_meta(yol: Path) -> list[str]:
    """Return metadata markers that can carry personal data (EXIF, ID3, RIFF INFO, PNG text, MP4 user data)."""
    try:
        veri = yol.read_bytes()[:4_000_000]
    except OSError:
        return []
    uz = yol.suffix.lower()
    isaret = []
    if uz in (".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic") and (b"Exif\x00\x00" in veri or b"<x:xmpmeta" in veri):
        isaret.append("EXIF/XMP")
    if uz == ".png":
        konum = 8
        while konum + 8 <= len(veri):
            uzunluk, tur = struct.unpack(">I4s", veri[konum:konum + 8])
            if tur in (b"tEXt", b"iTXt", b"zTXt", b"eXIf"):
                isaret.append(f"PNG {tur.decode()}")
            if tur == b"IEND":
                break
            konum += 12 + uzunluk
    if uz == ".mp3" and (veri[:3] == b"ID3" or veri[-128:-125] == b"TAG"):
        isaret.append("ID3")
    if uz in (".wav",) and b"LIST" in veri[:4096] and b"INFO" in veri[:4096]:
        isaret.append("RIFF INFO")
    if uz in (".flac", ".ogg", ".opus") and re.search(rb"(?i)(ARTIST|AUTHOR|COMMENT|ENCODED_BY|TITLE)=", veri[:65536]):
        isaret.append("Vorbis comment")
    if uz in (".mp4", ".m4a", ".mov", ".m4v") and re.search(rb"\xa9(ART|nam|cmt|day|too|xyz)|udta.{0,64}meta", veri, re.S):
        isaret.append("MP4 user data")
    if uz in (".mkv", ".webm") and re.search(rb"(?i)\x7b\xa9|(ENCODER|TITLE|ARTIST|COMMENT)", veri[:65536]):
        isaret.append("Matroska tags")
    return isaret


# --- scan -------------------------------------------------------------------------------------------------
def tara(kok: Path, kisisel: list[str] | None = None) -> list[Bulgu]:
    kok = kok.resolve()
    izinler = izinleri_oku(kok)
    bulgular: list[Bulgu] = []
    terimler = [t.strip().lower() for t in (kisisel or []) if len(t.strip()) >= 3]
    for dosya in dosyalari_listele(kok):
        goreli = dosya.relative_to(kok).as_posix()
        uz = dosya.suffix.lower()
        if YOL_ZAMAN.search(goreli):
            bulgular.append(Bulgu("zaman_izi", goreli, 0, "date-stamped path name"))
        if uz in MEDYA_UZANTI | GORSEL_UZANTI:
            if uz in MEDYA_UZANTI:
                bulgular.append(Bulgu("medya_dosyasi", goreli, 0, "media file in repository"))
            for isaret in medya_meta(dosya):
                bulgular.append(Bulgu("medya_meta", goreli, 0, isaret))
            continue
        if uz in ATLA_UZANTI or goreli in KENDI:
            continue
        try:
            if dosya.stat().st_size > METIN_SINIR:
                bulgular.append(Bulgu("medya_dosyasi", goreli, 0, "large file (>2 MB) not scanned"))
                continue
            ham = dosya.read_bytes()
        except OSError:
            continue
        if b"\x00" in ham[:8192]:
            continue  # binary
        metin = ham.decode("utf-8", "replace")
        for no, satir in enumerate(metin.splitlines(), 1):
            for kural, desen in KURALLAR:
                for e in desen.finditer(satir):
                    bulgular.append(Bulgu(kural, goreli, no, e.group(0)))
            if terimler:
                kucuk = satir.lower()
                for t in terimler:
                    if t in kucuk:
                        bulgular.append(Bulgu("kisisel_terim", goreli, no, "private term #" + str(terimler.index(t) + 1)))
    bulgular.extend(git_yazar(kok))
    return [b for b in bulgular if not _izinli(b, izinler)]


def git_yazar(kok: Path) -> list[Bulgu]:
    if not (kok / ".git").exists():
        return []
    try:
        cikti = subprocess.run(
            ["git", "-C", str(kok), "log", "--all", "--format=%ae%n%ce"], capture_output=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return []
    return [Bulgu("git_yazar", ".git", 0, e) for e in sorted(set(cikti.split())) if "noreply" not in e.lower()]


def _kisisel_liste(yol: str | None, kok: Path) -> list[str]:
    yol = yol or os.environ.get("YASAL_DENETIM_KISISEL")
    if not yol:
        return []
    p = Path(yol).resolve()
    if p.is_relative_to(kok.resolve()):
        raise SystemExit("--kisisel list must live outside the repository (it contains personal terms)")
    return p.read_text(encoding="utf-8").splitlines()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Legal and privacy gate (exit 1 on findings).")
    ap.add_argument("--kok", type=Path, default=KOK_VARSAYILAN)
    ap.add_argument("--kisisel", help="file with private terms, one per line (outside the repository)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not args.kok.is_dir():
        print(f"not a directory: {args.kok}", file=sys.stderr)
        return 2
    bulgular = tara(args.kok, _kisisel_liste(args.kisisel, args.kok))
    if args.json:
        print(json.dumps([asdict(b) | {"metin": _maskele(b.kural, b.metin)} for b in bulgular], ensure_ascii=False, indent=1))
    else:
        for b in bulgular:
            print(f"{b.kural:18} {b.yol}:{b.satir}  {_maskele(b.kural, b.metin)}")
        print(f"yasal_denetim: {len(bulgular)} finding(s)" + ("" if bulgular else " - clean"))
    return 1 if bulgular else 0


if __name__ == "__main__":
    sys.exit(main())
