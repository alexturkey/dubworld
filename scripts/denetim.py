"""PR oncesi tek komut: bu reponun butun yerel kapilarini sirayla kosar ve tek SONUC satiri basar.

One command before you open a pull request: runs every local gate of this repository and prints one SONUC line.

    python -I -X utf8 scripts/denetim.py --hizli     # hizli kapilar (yaklasik bir dakika, indirme yok, GPU yok)
    python -I -X utf8 scripts/denetim.py --tam       # hizli kapilar + CPU testleri (CI'deki test-cpu ile ayni)
    python -I -X utf8 scripts/denetim.py --kapi unicode   # tek kapi (unicode, yasal, izli_import, belge, dil, pr_kapi, ruff, test)
    python -I -X utf8 scripts/denetim.py --json      # makine ciktisi

Kapilar (hepsi yalniz okur, ag kullanmaz, dosya yazmaz):
  unicode      git'in izledigi metin dosyalarinda gorunmez/bidi/sifir genislik/kontrol karakteri (Trojan Source tipi).
               Dile ozgu istisna: Farsca/Bengalce/Hintce/Tayca README'de ZWNJ/ZWJ; Arapca/Farsca/Ibranice/Urduca README'de LRM/RLM.
               Baska hicbir yerde yok. PowerShell dosyasinin basindaki BOM serbest.
  yasal        scripts/yasal_denetim.py (hukuk ve gizlilik: kisisel yol, e-posta, anahtar, medya, yasakli servis).
  izli_import  scripts/izli_import_denetimi.py (izlenen dosya yalniz izlenen modulu iceri alir).
  belge        scripts/belge_dogrula.py (belgedeki baglanti, yol, komut, ayar, ortam degiskeni koda uyuyor mu).
  dil          scripts/dil_eslik_denetimi.py (EN/TR yapisi; README ceviri gecikmesi yalniz uyari).
  pr_kapi      scripts/pr_kapi.py --ozdenetim (kotu niyetli PR kapisi kendi orneklerini yakaliyor mu).
  ruff         CI'yi durduran ruff kurallari (ruff kurulu degilse CALISMADI: yesil sayilmaz).
  test         (--tam) python -m pytest -m "not gpu and not slow".

Cikis kodu: 0 hepsi GECTI | 1 en az bir kapi KIRMIZI | 3 girdi/ortam hatasi (kok bulunamadi, bilinmeyen kapi) |
            6 en az bir kapi CALISMADI (kapi yoksa/coktuyse yesil verilmez).
Son satir tek `SONUC:` satiridir. Yalniz standart kutuphane.
NEDEN: PR'da CI'dan once yerelde ayni kapilari tek komutla gormek. BEDEL: kapilar yavas degil ama sirayla kosar.
GEVSETME: kapi kapatilmaz; yanlis pozitif dar, gerekceli istisnayla (yasal_denetim_izin.txt, UNICODE_IZIN) giderilir.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
SCRIPTS = KOK / "scripts"
PENCERESIZ = getattr(subprocess, "CREATE_NO_WINDOW", 0)

METIN_UZANTI = frozenset({
    ".py", ".ps1", ".psm1", ".cmd", ".bat", ".sh", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini",
    ".in", ".html", ".js", ".css", ".xml", ".conf", ".env", ".example", ".gitattributes", ".gitignore",
})
METIN_ADLAR = frozenset({"LICENSE", "NOTICE", "Dockerfile", ".gitattributes", ".gitignore", ".editorconfig"})
ATLA_KLASOR = frozenset({".git", ".venv", "venv", "__pycache__", "runtime_assets", "cikti", "node_modules", ".mypy_cache", ".pytest_cache", ".ruff_cache"})

# (ad, ilk, son): gorunmez ya da yon degistiren karakter araliklari
SINIFLAR = (
    ("bidi", 0x202A, 0x202E), ("bidi", 0x2066, 0x2069), ("bidi", 0x061C, 0x061C),
    ("lrm_rlm", 0x200E, 0x200F),
    ("zwnj_zwj", 0x200C, 0x200D),
    ("sifir_genislik", 0x200B, 0x200B), ("sifir_genislik", 0x2060, 0x2064), ("sifir_genislik", 0x180E, 0x180E),
    ("sifir_genislik", 0x00AD, 0x00AD), ("sifir_genislik", 0x034F, 0x034F), ("sifir_genislik", 0xFEFF, 0xFEFF),
    ("sifir_genislik", 0xFFF9, 0xFFFB),
    ("etiket", 0xE0000, 0xE007F),
)
# Dil -> izinli sinif. Yalniz README.<dil>.md ceviri dosyalarinda gecerli.
ZWJ_DILLER = frozenset({"fa", "bn", "hi", "th"})
LRM_DILLER = frozenset({"ar", "fa", "he", "ur"})
# Dar, tarihli, gerekceli istisna: (yol deseni, sinif, neden). Bos: istisna yok.
UNICODE_IZIN: tuple[tuple[str, str, str], ...] = ()


def unicode_sinifi(kod: int) -> str | None:
    for ad, ilk, son in SINIFLAR:
        if ilk <= kod <= son:
            return ad
    return None


def unicode_izinli(yol: str, sinif: str) -> bool:
    m = re.fullmatch(r"README\.([A-Za-z-]+)\.md", yol)
    if m:
        dil = m.group(1).split("-")[0].lower()
        if sinif == "zwnj_zwj" and dil in ZWJ_DILLER:
            return True
        if sinif == "lrm_rlm" and dil in LRM_DILLER:
            return True
    import fnmatch
    return any(s == sinif and fnmatch.fnmatchcase(yol, g) for g, s, _ in UNICODE_IZIN)


def izlenen_dosyalar(kok: Path) -> list[str]:
    try:
        p = subprocess.run(["git", "-C", str(kok), "ls-files", "-z"], capture_output=True, timeout=60,
                           creationflags=PENCERESIZ)
        if p.returncode == 0 and p.stdout:
            return [x for x in p.stdout.decode("utf-8", "replace").split("\0") if x]
    except (OSError, subprocess.SubprocessError):
        pass
    sonuc = []
    for yol, klasorler, dosyalar in os.walk(kok):
        klasorler[:] = [k for k in klasorler if k not in ATLA_KLASOR]
        for d in dosyalar:
            sonuc.append(os.path.relpath(os.path.join(yol, d), kok).replace(os.sep, "/"))
    return sonuc


def metin_mi(yol: str) -> bool:
    ad = yol.rsplit("/", 1)[-1]
    return ad in METIN_ADLAR or os.path.splitext(ad)[1].lower() in METIN_UZANTI


def unicode_tara_metin(yol: str, ham: bytes) -> list[str]:
    """Bir dosyanin baytlarini tarar -> bulgu listesi ('yol:satir sinif U+XXXX'); karakterin kendisi basilmaz."""
    bulgu: list[str] = []
    if ham[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return [f"{yol}: UTF-16 metin (okunamaz; UTF-8 yapin)"]
    if ham[:3] == b"\xef\xbb\xbf":
        ham = ham[3:]  # dosya basindaki BOM serbest (PowerShell 5.1 icin gerekli)
    metin = ham.decode("utf-8", "replace")
    for no, satir in enumerate(metin.split("\n"), 1):
        for ch in satir:
            k = ord(ch)
            if k < 32 and ch not in "\t\r\x0c" or k == 0x7F or 0x80 <= k <= 0x9F:
                bulgu.append(f"{yol}:{no} kontrol karakteri U+{k:04X}")
                break
            sinif = unicode_sinifi(k)
            if sinif and not unicode_izinli(yol, sinif):
                bulgu.append(f"{yol}:{no} {sinif} U+{k:04X}")
                break
    return bulgu


def kapi_unicode(kok: Path) -> tuple[str, list[str]]:
    bulgu: list[str] = []
    sayi = 0
    for yol in izlenen_dosyalar(kok):
        if not metin_mi(yol):
            continue
        dosya = kok / yol
        if not dosya.is_file():
            continue
        sayi += 1
        bulgu += unicode_tara_metin(yol, dosya.read_bytes())
    if sayi == 0:
        return "CALISMADI", ["taranacak metin dosyasi bulunamadi"]
    return ("KIRMIZI" if bulgu else "GECTI"), bulgu


def alt_surec(argv: list[str], kok: Path, zaman: int = 900) -> tuple[str, list[str]]:
    try:
        p = subprocess.run(argv, cwd=kok, capture_output=True, timeout=zaman, creationflags=PENCERESIZ)
    except (OSError, subprocess.SubprocessError) as e:
        return "CALISMADI", [f"{type(e).__name__}"]
    cikti = (p.stdout + p.stderr).decode("utf-8", "replace").strip().splitlines()
    son = cikti[-6:]
    if p.returncode != 0 and "No module named" in " ".join(son):
        modul = re.search(r"No module named '?([A-Za-z0-9_.]+)", " ".join(son))
        return "CALISMADI", ["gereken arac kurulu degil: " + (modul.group(1) if modul else "?"),
                             "kurmak icin: python -m pip install ruff pytest"]
    if p.returncode == 0:
        return "GECTI", []
    if p.returncode == 1:
        return "KIRMIZI", son
    return "CALISMADI", [f"cikis kodu {p.returncode}"] + son


def python_arg(*a: str) -> list[str]:
    return [sys.executable, "-I", "-X", "utf8", *a]


def kapilar(tam: bool) -> list[tuple[str, object]]:
    ruff = [sys.executable, "-m", "ruff", "check", "--select", "E9,F63,F7,F82", "src", "tests"]
    if shutil.which("ruff") and subprocess.run([sys.executable, "-m", "ruff", "--version"], capture_output=True,
                                                creationflags=PENCERESIZ).returncode != 0:
        ruff = ["ruff", "check", "--select", "E9,F63,F7,F82", "src", "tests"]
    liste: list[tuple[str, object]] = [
        ("unicode", lambda: kapi_unicode(KOK)),
        ("yasal", lambda: alt_surec(python_arg("scripts/yasal_denetim.py"), KOK)),
        ("izli_import", lambda: alt_surec(python_arg("scripts/izli_import_denetimi.py"), KOK)),
        ("belge", lambda: alt_surec(python_arg("scripts/belge_dogrula.py"), KOK)),
        ("dil", lambda: alt_surec(python_arg("scripts/dil_eslik_denetimi.py"), KOK)),
        ("pr_kapi", lambda: alt_surec(python_arg("scripts/pr_kapi.py", "--ozdenetim"), KOK)),
        ("ruff", lambda: alt_surec(ruff, KOK)),
    ]
    if tam:
        liste.append(("test", lambda: alt_surec([sys.executable, "-m", "pytest", "-m", "not gpu and not slow", "-q",
                                                  "-p", "no:cacheprovider"], KOK, 1800)))
    return liste


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="denetim.py", description="Yerel kapilar, tek SONUC satiri")
    kip = ap.add_mutually_exclusive_group()
    kip.add_argument("--hizli", action="store_true", help="hizli kapilar (varsayilan)")
    kip.add_argument("--tam", action="store_true", help="hizli kapilar + CPU testleri")
    ap.add_argument("--kapi", help="yalniz bu kapi")
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 3 if e.code else 0
    if not (KOK / "pyproject.toml").is_file():
        print("GIRDI HATALI: repo koku bulunamadi")
        print("SONUC: GIRDI HATALI (3)")
        return 3
    secili = kapilar(a.tam)
    if a.kapi:
        secili = [k for k in kapilar(True) if k[0] == a.kapi]
        if not secili:
            print(f"GIRDI HATALI: bilinmeyen kapi: {re.sub(r'[^A-Za-z0-9_]', '?', a.kapi)[:30]}")
            print("SONUC: GIRDI HATALI (3)")
            return 3
    sonuclar = []
    for ad, fonk in secili:
        t0 = time.time()
        try:
            durum, ayrinti = fonk()  # type: ignore[operator]
        except Exception as e:  # kapali hata: coken kapi yesil degildir
            durum, ayrinti = "CALISMADI", [type(e).__name__]
        sonuclar.append((ad, durum, ayrinti, round(time.time() - t0, 1)))
        if not a.json:
            print(f"{durum:<10} {ad:<12} ({sonuclar[-1][3]} s)")
            for satir in ayrinti[:20]:
                print(f"    {satir}")
    kirmizi = [s for s in sonuclar if s[1] == "KIRMIZI"]
    calismadi = [s for s in sonuclar if s[1] == "CALISMADI"]
    if a.json:
        print(json.dumps([{"kapi": s[0], "durum": s[1], "ayrinti": s[2], "sure_s": s[3]} for s in sonuclar],
                         ensure_ascii=True, indent=1))
    if kirmizi:
        print(f"SONUC: KIRMIZI ({len(kirmizi)} kapi: {', '.join(s[0] for s in kirmizi)})")
        return 1
    if calismadi:
        print(f"SONUC: CALISMADI ({len(calismadi)} kapi: {', '.join(s[0] for s in calismadi)}); yesil sayilmaz")
        return 6
    print(f"SONUC: GECTI ({len(sonuclar)} kapi)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
