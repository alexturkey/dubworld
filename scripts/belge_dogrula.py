"""Belge doğrulama: belgelerde geçen her bağlantı, yol, komut, bayrak, ayar anahtarı, kur.ps1 adımı, `python -m`
modülü ve ortam değişkeni repoda gerçekten var mı; kayıttaki her motorun sayfası var mı.

Documentation check: every link, path, `dubla` sub-command and flag, setting key, `kur.ps1` step, `python -m` module
and environment variable mentioned in the docs must exist in the code; every registered engine must have a page.

    python scripts/belge_dogrula.py                 # varsayılan belge kümesi (repo kökünden)
    python scripts/belge_dogrula.py docs/x.md ...   # yalnız verilen dosyalar (repo köküne göre ya da tam yol)
    python scripts/belge_dogrula.py --kok <repo>    # başka bir kopya

Doğruluk kaynağı koddur: alt komut ve bayraklar argparse'tan (`dublaj_hatti.cli`), ayar anahtarları şemadan
(`yapilandirma.SEMA`), kurulum adımları `scripts/kur.ps1`'den, ortam değişkenleri kaynak koddan okunur. Ağ, GPU ve
ağır kütüphane gerekmez (paket `pip install --no-deps -e .` ile yeterli). Çıkış: 0 temiz, 1 bulgu var.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from pathlib import Path

VARSAYILAN_KOK = Path(__file__).resolve().parents[1]
YOL_KOKLERI = ("src/", "docs/", "scripts/", "examples/", "tests/", "requirements/", ".claude/", ".github/",
               "runtime_assets/", "ayarlar/")
# Kurulum ya da çalışma sırasında oluşan yerler: belgede geçer ama temiz klonda yoktur.
CALISMADA_OLUSUR = ("runtime_assets/", "ayarlar/", "cikti/", ".venv/", "out/")
AYAR_DESENI = re.compile(r"(?<![\w./])((?:genel|transkripsiyon|ses_temizligi|ceviri|ses|altyazi|video|ileri)"
                         r"\.[a-z_0-9]+(?:\.[a-z_A-Z0-9*]+)?\*?)")
ORTAM_DESENI = re.compile(r"\b((?:DUBLAJ|CODEX_BRIDGE|TELEGRAM|SPEECHMATICS|ELEVENLABS|GROQ|MISTRAL|CEREBRAS|GEMINI|HF)"
                          r"_[A-Z0-9_]+|HF_TOKEN|OPENAI_API_KEY)\b")


def capalar(dosya: Path) -> set[str]:
    """GitHub'ın Markdown başlık çapaları (küçük harf, noktalama silinir, boşluk -> '-'; tekrar -1, -2) + <a id>."""
    sonuc: set[str] = set()
    sayim: dict[str, int] = {}
    kod = False
    for satir in dosya.read_text(encoding="utf-8").splitlines():
        if satir.startswith("```"):
            kod = not kod
        sonuc.update(re.findall(r'<a\s+(?:id|name)="([^"]+)"', satir))
        m = None if kod else re.match(r"#{1,6}\s+(.+?)\s*#*\s*$", satir)
        if not m:
            continue
        metin = re.sub(r"`|\*\*|__|\[([^\]]*)\]\([^)]*\)", lambda x: x.group(1) or "", m.group(1)).lower()
        slug = re.sub(r"[^\w\- ]", "", metin).replace(" ", "-")
        n = sayim.get(slug, 0)
        sayim[slug] = n + 1
        sonuc.add(slug if n == 0 else f"{slug}-{n}")
    return sonuc


def varsayilan_dosyalar(kok: Path) -> list[Path]:
    """Kullanıcıya ve ajana yol gösteren belgeler: kök belgeler, docs/ tamamı, beceriler."""
    dosyalar = sorted(kok.glob("*.md")) + sorted((kok / "docs").rglob("*.md"))
    dosyalar += sorted((kok / ".claude" / "skills").glob("*/SKILL.md"))
    return dosyalar


class Dogrulayici:
    def __init__(self, kok: Path) -> None:
        self.kok = kok.resolve()
        sys.path.insert(0, str(self.kok / "src"))
        from dublaj_hatti import cli, kayit, yapilandirma

        ana = cli._parser()
        alt = next(a for a in ana._actions if isinstance(a, argparse._SubParsersAction))
        self.alt = {ad: {s for act in p._actions for s in act.option_strings} for ad, p in alt.choices.items()}
        # "dubla <video> --ayar ..." = "dubla" alt komutu; üst düzey bayraklar (--surum vb.) her yerde geçerli
        ust = {s for act in ana._actions for s in act.option_strings}
        self.alt["dubla"] = self.alt.get("dubla", set()) | ust
        self.sema = set(yapilandirma.SEMA)
        self.kayit = kayit
        kur = (self.kok / "scripts" / "kur.ps1").read_text(encoding="utf-8-sig")
        adimlar = set(re.findall(r'Adim "([a-z0-9-]+)"', kur))
        for liste in re.findall(r"foreach \(\$ek in @\(([^)]*)\)\)", kur):
            adimlar |= set(re.findall(r'"([a-z0-9-]+)"', liste))
        varsayilan = re.search(r'\$Adim = "([^"]+)"', kur)
        if varsayilan:
            adimlar |= set(varsayilan.group(1).split(","))
        self.adimlar = adimlar
        self.kok_dosya = {p.name for p in self.kok.iterdir()}
        kaynaklar = list((self.kok / "src").rglob("*.py")) + [
            self.kok / ".env.example", self.kok / "scripts" / "kur.ps1", self.kok / "scripts" / "crisper_kur.py",
            self.kok / "src" / "dublaj_hatti" / "varsayilan.toml"]
        self.kaynak_metni = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in kaynaklar if p.is_file())
        self.bulgular: list[str] = []
        self.sayac = dict(dosya=0, baglanti=0, yol=0, komut=0, bayrak=0, ayar=0, adim=0, modul=0, ortam=0)

    # --- yardımcılar ------------------------------------------------------------------------------------------
    def _bul(self, dosya: Path, no: int, metin: str) -> None:
        try:
            ad = dosya.resolve().relative_to(self.kok).as_posix()
        except ValueError:
            ad = dosya.name
        self.bulgular.append(f"{ad}:{no}: {metin}")

    def _yol_var(self, goreli: str) -> bool:
        return (self.kok / goreli.replace("\\", "/").rstrip("/")).exists()

    # --- denetimler -------------------------------------------------------------------------------------------
    def dosya_denetle(self, dosya: Path) -> None:
        self.sayac["dosya"] += 1
        metin = dosya.read_text(encoding="utf-8")
        if dosya.name == "SKILL.md":
            m = re.match(r"---\r?\nname: ([^\n]+)\r?\ndescription: \"([^\n]+)\"\r?\n---\r?\n", metin)
            if not m or m.group(1).strip() != dosya.parent.name or len(m.group(2)) < 80:
                self._bul(dosya, 1, "frontmatter (name = klasör adı, description) eksik/yanlış")
            if "## Türkçe özet" not in metin:
                self._bul(dosya, 1, "Türkçe özet yok")
        kod_blogu = False
        for no, satir in enumerate(metin.splitlines(), 1):
            if satir.startswith("```"):
                kod_blogu = not kod_blogu
            self._baglantilar(dosya, no, satir)
            parcalar = re.findall(r"`([^`]+)`", satir)
            if kod_blogu:
                parcalar.append(satir)
            for parca in parcalar:
                self._yollar(dosya, no, parca)
                self._komutlar(dosya, no, parca)
                self._ayarlar(dosya, no, parca)
                self._kur_adimlari(dosya, no, parca)
                self._moduller(dosya, no, parca)
                self._ortam(dosya, no, parca)

    def _baglantilar(self, dosya: Path, no: int, satir: str) -> None:
        for hedef in re.findall(r"\]\(([^)\s]+)\)", satir):
            if hedef.startswith(("http://", "https://", "mailto:")) or re.fullmatch(r"__[A-Z_]+__", hedef):
                # dış adres ya da yayında doldurulan yer tutucu (__REPO_URL__ vb.)
                continue
            self.sayac["baglanti"] += 1
            yol, _, capa = hedef.partition("#")
            hedef_dosya = (dosya.parent / yol).resolve() if yol else dosya.resolve()
            if not hedef_dosya.exists():
                self._bul(dosya, no, f"kırık bağlantı: {hedef}")
            elif capa and hedef_dosya.suffix == ".md" and capa not in capalar(hedef_dosya):
                self._bul(dosya, no, f"kırık çapa: {hedef}")

    def _yollar(self, dosya: Path, no: int, parca: str) -> None:
        for tok in re.split(r"[\s(),;=\"']+", parca):
            tok = tok.strip(".:")
            if not tok or any(ch in tok for ch in "<>*{}|") or "..." in tok or tok == "SKILL.md":
                continue
            norm = tok.replace("\\", "/")
            if norm.startswith(YOL_KOKLERI) or norm in self.kok_dosya or re.fullmatch(r"[A-Z_]+\.md", norm):
                if norm.startswith(CALISMADA_OLUSUR) or "/.venv" in norm:
                    continue
                self.sayac["yol"] += 1
                if "/" not in norm and norm not in self.kok_dosya:
                    # kökte olmayan BÜYÜK_HARF.md (ör. VENDOR_NOTU.md): repoda bir yerde var olmalı
                    if not any(self.kok.rglob(norm)):
                        self._bul(dosya, no, f"yol yok: {tok}")
                    continue
                if not self._yol_var(norm):
                    self._bul(dosya, no, f"yol yok: {tok}")

    def _komutlar(self, dosya: Path, no: int, parca: str) -> None:
        for m in re.finditer(r"(?:^|[\s`])dubla(?:\.exe)?\s+([^\s`]+)((?:\s+[^`#|]*)?)", parca):
            ilk, kalan = m.group(1), m.group(2) or ""
            if ilk.startswith("-"):
                self.sayac["komut"] += 1
                if ilk not in self.alt["dubla"]:
                    self._bul(dosya, no, f"bilinmeyen dubla bayrağı: {ilk}")
                alt_ad = "dubla"
            elif ilk in self.alt:
                alt_ad = ilk
                self.sayac["komut"] += 1
            elif re.search(r"\.(mp4|mkv|mov|wav|mp3)$|^https://|^<|^video|^\.\.\.", ilk):
                alt_ad = "dubla"
                self.sayac["komut"] += 1
            else:
                if re.fullmatch(r"[a-z][a-z-]+", ilk):
                    self._bul(dosya, no, f"bilinmeyen dubla alt komutu: {ilk}")
                continue
            for bayrak in re.findall(r"(?<![\w-])(--?[a-z][a-z-]*)", kalan):
                self.sayac["bayrak"] += 1
                if bayrak not in self.alt[alt_ad] and bayrak != "-h":
                    self._bul(dosya, no, f"'{alt_ad}' alt komutunda bayrak yok: {bayrak}")

    def _ayarlar(self, dosya: Path, no: int, parca: str) -> None:
        for anahtar in AYAR_DESENI.findall(parca):
            if re.search(r"\.(md|py|json|toml|mp4|wav|srt|txt)$", anahtar):
                continue
            self.sayac["ayar"] += 1
            if anahtar.endswith("*"):
                if not any(k.startswith(anahtar.rstrip("*")) for k in self.sema):
                    self._bul(dosya, no, f"ayar ailesi yok: {anahtar}")
            elif anahtar not in self.sema and not anahtar.startswith("ses.konusmaci_sesleri"):
                self._bul(dosya, no, f"ayar anahtarı yok: {anahtar}")

    def _kur_adimlari(self, dosya: Path, no: int, parca: str) -> None:
        for liste in re.findall(r"-Adim\s+([a-z0-9,-]+)", parca):
            for adim in liste.split(","):
                self.sayac["adim"] += 1
                if adim and adim not in self.adimlar:
                    self._bul(dosya, no, f"kur.ps1 adımı yok: {adim}")

    def _moduller(self, dosya: Path, no: int, parca: str) -> None:
        for mod in re.findall(r"python\s+-m\s+(dublaj_hatti[\w.]*)", parca):
            self.sayac["modul"] += 1
            yol = self.kok / "src" / Path(*mod.split("."))
            if not (yol.with_suffix(".py").exists() or (yol / "__main__.py").exists() or (yol / "__init__.py").exists()):
                self._bul(dosya, no, f"modül yok: {mod}")

    def _ortam(self, dosya: Path, no: int, parca: str) -> None:
        for degisken in ORTAM_DESENI.findall(parca):
            self.sayac["ortam"] += 1
            if degisken not in self.kaynak_metni and not re.fullmatch(r"[A-Z_]+_OK", degisken):
                self._bul(dosya, no, f"ortam değişkeni kaynakta yok: {degisken}")

    def motor_sayfalari(self) -> list[str]:
        return [m.belge for m in self.kayit.MOTORLAR if not (self.kok / m.belge).is_file()]

    def calistir(self, dosyalar: Iterable[Path]) -> int:
        for dosya in dosyalar:
            self.dosya_denetle(dosya)
        eksik = self.motor_sayfalari()
        for belge in eksik:
            self.bulgular.append(f"{belge}: kayıttaki motorun sayfası yok")
        return 1 if self.bulgular else 0


def main(argv: list[str] | None = None) -> int:
    for akis in (sys.stdout, sys.stderr):
        if hasattr(akis, "reconfigure"):
            akis.reconfigure(encoding="utf-8", errors="replace")
    ayr = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ayr.add_argument("dosyalar", nargs="*", type=Path)
    ayr.add_argument("--kok", type=Path, default=VARSAYILAN_KOK)
    args = ayr.parse_args(argv)
    kok = args.kok.resolve()
    dosyalar = [d if d.is_absolute() else kok / d for d in args.dosyalar] or varsayilan_dosyalar(kok)
    dogrulayici = Dogrulayici(kok)
    sonuc = dogrulayici.calistir(dosyalar)
    print("sayaç / counts:", dogrulayici.sayac)
    print("motor sayısı / engines:", len(dogrulayici.kayit.MOTORLAR))
    print("bulgu / findings:", len(dogrulayici.bulgular))
    for bulgu in dogrulayici.bulgular:
        print("  ", bulgu)
    return sonuc


if __name__ == "__main__":
    sys.exit(main())
