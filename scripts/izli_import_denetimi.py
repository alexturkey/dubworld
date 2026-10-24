"""İzlenen (git'e eklenmiş) Python dosyaları yalnız izlenen modülleri içe aktarıyor mu?

Yerelde testler, çalışma ağacında duran ama commit'e girmeyen bir modülü bulup geçer; CI temiz kopyada aynı
içe aktarmayı bulamaz ve kırılır. Bu denetim commit'ten önce, `git add` sonrası çalışır: `git ls-files` ile
izlenen `src/`, `tests/`, `scripts/` dosyalarındaki `dublaj_hatti...` ve göreli içe aktarmaları dosya yoluna
çevirir; hedef yoksa ya da izlenmiyorsa satırı yazar ve 1 ile çıkar. Yalnız standart kitaplık; kod çalıştırmaz.

    python scripts/izli_import_denetimi.py
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
SRC = KOK / "src"
PAKET = "dublaj_hatti"


def izlenenler() -> set[str]:
    cikti = subprocess.run(["git", "ls-files", "-z", "src", "tests", "scripts"], cwd=KOK, check=True,
                           capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    return {p for p in cikti.decode("utf-8").split("\0") if p}


def _modul_dosyasi(parcalar: list[str]) -> Path | None:
    """`dublaj_hatti.a.b` → src/dublaj_hatti/a/b.py ya da .../b/__init__.py; `__init__`siz klasör (ad alanı
    paketi) klasörün kendisi; diskte yoksa None."""
    taban = SRC.joinpath(*parcalar)
    for aday in (taban.with_suffix(".py"), taban / "__init__.py"):
        if aday.is_file():
            return aday
    return taban if taban.is_dir() else None


def _paket_parcalari(yol: Path) -> list[str] | None:
    try:
        goreli = yol.relative_to(SRC)
    except ValueError:
        return None
    parcalar = list(goreli.with_suffix("").parts)
    return parcalar[:-1] if parcalar[-1] != "__init__" else parcalar[:-1]


def hedefler(yol: Path, agac: ast.AST) -> list[tuple[int, list[str], bool]]:
    """(satır, modül parçaları, zorunlu mu). `from X import Y`: X zorunlu, X.Y alt modülse o da denetlenir."""
    sonuc: list[tuple[int, list[str], bool]] = []
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            for ad in dugum.names:
                if ad.name.split(".")[0] == PAKET:
                    sonuc.append((dugum.lineno, ad.name.split("."), True))
        elif isinstance(dugum, ast.ImportFrom):
            if dugum.level:
                paket = _paket_parcalari(yol)
                if paket is None or dugum.level - 1 > len(paket):
                    continue
                taban = paket[:len(paket) - (dugum.level - 1)]
                modul = taban + (dugum.module.split(".") if dugum.module else [])
            elif dugum.module and dugum.module.split(".")[0] == PAKET:
                modul = dugum.module.split(".")
            else:
                continue
            sonuc.append((dugum.lineno, modul, True))
            sonuc.extend((dugum.lineno, [*modul, ad.name], False) for ad in dugum.names if ad.name != "*")
    return sonuc


def denetle() -> list[str]:
    izli = izlenenler()
    hatalar = []
    for goreli in sorted(izli):
        if not goreli.endswith(".py"):
            continue
        yol = KOK / goreli
        try:
            agac = ast.parse(yol.read_bytes(), filename=goreli)
        except (OSError, SyntaxError) as hata:
            hatalar.append(f"{goreli}: okunamadı ({hata})")
            continue
        for satir, parcalar, zorunlu in hedefler(yol, agac):
            dosya = _modul_dosyasi(parcalar)
            if dosya is None:
                if zorunlu:
                    hatalar.append(f"{goreli}:{satir}: modül yok: {'.'.join(parcalar)}")
                continue
            if dosya.is_file() and dosya.relative_to(KOK).as_posix() not in izli:
                hatalar.append(f"{goreli}:{satir}: izlenmeyen modül: {dosya.relative_to(KOK).as_posix()}"
                               " (git add unutulmuş olabilir)")
    return hatalar


def main() -> int:
    hatalar = denetle()
    for satir in hatalar:
        print(satir)
    print(f"izli içe aktarma denetimi: {'TAMAM' if not hatalar else f'{len(hatalar)} sorun'}")
    return 1 if hatalar else 0


if __name__ == "__main__":
    sys.exit(main())
