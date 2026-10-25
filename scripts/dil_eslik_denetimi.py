"""Dil eşlik denetimi: her İngilizce belgenin Türkçe karşılığı var mı ve yapısı aynı mı; README çevirileri bayat mı.

Language parity check: every English document has a Turkish counterpart with the same structure (section headings,
table rows, code blocks), and the README translations still match the English README.

    python scripts/dil_eslik_denetimi.py            # repo kökünden
    python scripts/dil_eslik_denetimi.py --kati     # README çevirilerindeki farklar da hata sayılır
    python scripts/dil_eslik_denetimi.py --kok <repo>

Belge türleri (aşağıdaki listeler tek doğruluk kaynağıdır; yeni bir .md eklenince buraya da eklenir):

- ``CIFTLER``: ayrı dosyalı EN ↔ TR çiftleri. Başlık sayısı (seviye başına), tablo satırı ve kod bloğu sayısı eşit
  olmalı. Fark HATA'dır.
- ADR'ler: ``docs/adr/NNNN-*.md`` ↔ ``docs/muhendislik/kararlar.md`` içindeki ``## NNNN`` bölümü. Aynı ölçüt.
- ``TEK_DOSYA``: aynı dosyada iki dil; ``## Türkçe`` / ``## TR`` / ``**TR**`` gibi bir dil başlığıyla bölünür. İki
  yarının başlık, tablo satırı ve kod bloğu sayısı eşit olmalı (başlık seviyesi yarılar arasında kayabilir). HATA.
- ``SATIR_ICI``: başlıkların kendisi iki dilli (``## Start here / Başlangıç``). Her başlıkta `` / `` olmalı. HATA.
- ``README_CEVIRILERI``: ``README.<dil>.md``. Bölüm yapısı (H2 sayısı, kod bloğu, tablo satırı) README.md ile aynı
  olmalı ve ``<!-- i18n-source: README.md sha256:<12 hex> -->`` işareti README.md'nin şimdiki özetini taşımalı.
  Fark varsayılan olarak UYARI'dır (çıkışı bozmaz; karar: çeviri gecikebilir, İngilizce bağlayıcıdır), ``--kati``
  ile HATA.
- ``MUAF``: gerekçesiyle tek dilde kalan belgeler.

Kök ve ``docs/`` altındaki her .md bu türlerden birine girmelidir; girmeyen HATA verir (yeni belge sessizce tek dilde
kalmasın). Git varsa her fark için hangi tarafın daha yeni değiştiği yazılır (güncelleme kaynağı odur).
Yalnız standart kütüphane; ağ yok. Çıkış: 0 temiz (uyarı olabilir), 1 hata var.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

VARSAYILAN_KOK = Path(__file__).resolve().parents[1]

CIFTLER: list[tuple[str, str]] = [
    ("README.md", "README.tr.md"),
    ("AGENTS.md", "AGENTS.tr.md"),
    ("docs/installation.md", "docs/kurulum.md"),
    ("docs/getting-started.md", "docs/baslarken.md"),
    ("docs/engineering/README.md", "docs/muhendislik/README.md"),
    ("docs/engineering/crisperwhisper_turbo_ct2.md", "docs/muhendislik/crisperwhisper_turbo_ct2.md"),
    ("docs/engineering/gpu_memory_and_isolation.md", "docs/muhendislik/gpu_bellek_ve_yalitim.md"),
    ("docs/engineering/low_vram.md", "docs/muhendislik/dusuk_vram.md"),
    ("docs/engineering/pinned-values.md", "docs/muhendislik/sabit_degerler.md"),
    ("docs/engineering/pipeline-flow.md", "docs/muhendislik/hat_akisi.md"),
    ("docs/engineering/source_audio_and_separation.md", "docs/muhendislik/kaynak_ses_ve_ayristirma.md"),
    ("docs/engineering/speakers_and_segments.md", "docs/muhendislik/konusmaci_ve_segmentler.md"),
    ("docs/engineering/timing-sources.md", "docs/muhendislik/zaman_kaynaklari.md"),
    ("docs/engineering/transcription.md", "docs/muhendislik/transkripsiyon.md"),
    ("docs/engineering/translation.md", "docs/muhendislik/ceviri.md"),
    ("docs/engineering/tts_timing_and_mix.md", "docs/muhendislik/tts_zamanlama_ve_karisim.md"),
    ("docs/engineering/video_subtitles_and_resume.md", "docs/muhendislik/video_altyazi_ve_devam.md"),
    ("docs/engineering/word_alignment.md", "docs/muhendislik/kelime_hizalama.md"),
]
ADR_KLASORU = "docs/adr"
ADR_TR = "docs/muhendislik/kararlar.md"
TEK_DOSYA_KALIPLARI = (
    "PRIVACY.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "ETHICS.md",
    "docs/motorlar/*.md",
    "docs/tarifler/*.md",
    "docs/diller.md",
    "docs/donanim.md",
    "docs/sesler.md",
    "docs/mimari.md",
    "docs/olcumler.md",
    "docs/beceriler/README.md",
)
SATIR_ICI = ("docs/README.md",)
README_DILLERI = ("ar", "de", "es", "fr", "hi", "id", "it", "ja", "ko", "pt-BR", "ru", "vi", "zh-CN")
MUAF: dict[str, str] = {
    "CHANGELOG.md": "sürüm notları İngilizce tutulur / release notes are kept in English",
    "CLAUDE.md": "AGENTS.md'ye yönlendiren üç satır / three-line pointer to AGENTS.md",
    "GEMINI.md": "AGENTS.md'ye yönlendiren üç satır (Gemini CLI) / three-line pointer to AGENTS.md (Gemini CLI)",
    "CODE_OF_CONDUCT.md": "Contributor Covenant özgün metni + Türkçe özet / original Covenant text + Turkish summary",
    "THIRD_PARTY.md": "lisans ve sürüm tablosu, iki dilli başlıklar / licence tables with bilingual headings",
    "docs/adr/README.md": "ADR fihristi; Türkçe karşılığı kararlar.md / ADR index; Turkish counterpart is kararlar.md",
}
DIL_BOLUCU = re.compile(r"^(?:#{2}\s+(?:EN|English|TR|Türkçe|Türkçe özet)\s*|\*\*(?:EN|English|TR|Türkçe)\*\*\s*)$")
TR_ISARETI = re.compile(r"(TR|Türkçe)")
KAYNAK_ISARETI = re.compile(r"<!--\s*i18n-source:\s*README\.md\s+sha256:([0-9a-f]{12})\s*-->")


@dataclass
class Yapi:
    """Bir metin parçasının dilden bağımsız yapısı."""

    basliklar: dict[int, int] = field(default_factory=dict)  # seviye -> sayı (H1 hariç)
    tablo_satiri: int = 0
    kod_blogu: int = 0

    @property
    def baslik_toplami(self) -> int:
        return sum(self.basliklar.values())

    def ozet(self, seviyeli: bool = True) -> str:
        if seviyeli:
            b = ",".join(f"H{s}:{n}" for s, n in sorted(self.basliklar.items())) or "0"
        else:
            b = str(self.baslik_toplami)
        return f"başlık/headings {b} · tablo/table rows {self.tablo_satiri} · kod/code blocks {self.kod_blogu}"


def yapi_cikar(satirlar: list[str]) -> Yapi:
    yapi = Yapi()
    kod = False
    for satir in satirlar:
        if satir.lstrip().startswith("```"):
            if not kod:
                yapi.kod_blogu += 1
            kod = not kod
            continue
        if kod:
            continue
        m = re.match(r"(#{2,6})\s+\S", satir)
        if m:
            seviye = len(m.group(1))
            yapi.basliklar[seviye] = yapi.basliklar.get(seviye, 0) + 1
        elif satir.lstrip().startswith("|"):
            yapi.tablo_satiri += 1
    return yapi


def satirlar(dosya: Path) -> list[str]:
    return dosya.read_text(encoding="utf-8").splitlines()


def readme_ozeti(dosya: Path) -> str:
    veri = dosya.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(veri).hexdigest()[:12]


class Denetci:
    def __init__(self, kok: Path, kati: bool = False) -> None:
        self.kok = kok
        self.kati = kati
        self.hatalar: list[str] = []
        self.uyarilar: list[str] = []
        self.sayac = {
            "çift/pairs": 0,
            "adr": 0,
            "tek dosya/in-file": 0,
            "satır içi/inline": 0,
            "readme çeviri": 0,
            "muaf/exempt": 0,
        }
        self._git = (kok / ".git").exists()

    # --- yardımcılar
    def _goreli(self, yol: Path) -> str:
        return yol.relative_to(self.kok).as_posix()

    def _git_zamani(self, goreli: str) -> int | None:
        if not self._git:
            return None
        try:
            cikti = subprocess.run(
                ["git", "log", "-1", "--format=%ct", "--", goreli],
                cwd=self.kok,
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return int(cikti.stdout.strip()) if cikti.stdout.strip() else None
        except (OSError, ValueError, subprocess.SubprocessError):
            return None

    def _yeni_taraf(self, en: str, tr: str) -> str:
        a, b = self._git_zamani(en), self._git_zamani(tr)
        if a is None or b is None or a == b:
            return ""
        return f" (git: daha yeni / newer = {en if a > b else tr})"

    # --- türler
    def cift(self, en: str, tr: str) -> None:
        self.sayac["çift/pairs"] += 1
        p_en, p_tr = self.kok / en, self.kok / tr
        for yol, ad in ((p_en, en), (p_tr, tr)):
            if not yol.is_file():
                self.hatalar.append(f"{ad}: karşılığı eksik / counterpart missing (çift/pair {en} ↔ {tr})")
        if not (p_en.is_file() and p_tr.is_file()):
            return
        y_en, y_tr = yapi_cikar(satirlar(p_en)), yapi_cikar(satirlar(p_tr))
        if y_en != y_tr:
            self.hatalar.append(
                f"{en} ↔ {tr}: yapı farklı / structure differs{self._yeni_taraf(en, tr)}\n"
                f"      EN {y_en.ozet()}\n      TR {y_tr.ozet()}"
            )

    def adrler(self) -> None:
        klasor = self.kok / ADR_KLASORU
        tr_yolu = self.kok / ADR_TR
        if not tr_yolu.is_file():
            self.hatalar.append(f"{ADR_TR}: yok / missing")
            return
        bolumler: dict[str, list[str]] = {}
        anahtar = None
        for satir in satirlar(tr_yolu):
            m = re.match(r"##\s+(\d{4})\b", satir)
            if m:
                anahtar = m.group(1)
                bolumler[anahtar] = []
                continue
            if re.match(r"##\s", satir):
                anahtar = None
            if anahtar:
                bolumler[anahtar].append(satir)
        adr_dosyalari = sorted(klasor.glob("[0-9][0-9][0-9][0-9]-*.md"))
        numaralar = set()
        for dosya in adr_dosyalari:
            self.sayac["adr"] += 1
            no = dosya.name[:4]
            numaralar.add(no)
            if not re.fullmatch(r"\d{4}-[a-z0-9-]+\.md", dosya.name) or TR_ADI & set(dosya.stem.split("-")):
                self.hatalar.append(
                    f"{self._goreli(dosya)}: ADR dosya adı İngilizce ve küçük harf-tire olmalı / "
                    "ADR file name must be English kebab-case"
                )
            if no not in bolumler:
                self.hatalar.append(f"{self._goreli(dosya)}: {ADR_TR} içinde '## {no}' bölümü yok / section missing")
                continue
            # ADR'de H2 = Context/Decision/...; kararlar.md'de H3. Seviyesiz karşılaştırılır.
            y_en = yapi_cikar(satirlar(dosya))
            y_tr = yapi_cikar(bolumler[no])
            if (y_en.baslik_toplami, y_en.tablo_satiri, y_en.kod_blogu) != (
                y_tr.baslik_toplami,
                y_tr.tablo_satiri,
                y_tr.kod_blogu,
            ):
                self.hatalar.append(
                    f"{self._goreli(dosya)} ↔ {ADR_TR}#{no}: yapı farklı / structure differs"
                    f"{self._yeni_taraf(self._goreli(dosya), ADR_TR)}\n"
                    f"      EN {y_en.ozet(False)}\n      TR {y_tr.ozet(False)}"
                )
        for no in sorted(set(bolumler) - numaralar):
            self.hatalar.append(f"{ADR_TR}#{no}: İngilizce ADR dosyası yok / English ADR missing")

    def tek_dosya(self, dosya: Path) -> None:
        self.sayac["tek dosya/in-file"] += 1
        metin = satirlar(dosya)
        bolucu = [i for i, s in enumerate(metin) if DIL_BOLUCU.match(s.strip())]
        ad = self._goreli(dosya)
        if not bolucu:
            self.hatalar.append(f"{ad}: Türkçe bölüm yok (## Türkçe) / no Turkish section")
            return
        if len(bolucu) == 1:
            # Biçim A: İngilizce gövde, sonra "## Türkçe". İlk satırdaki H1 iki dilin ortak başlığıdır.
            en_par, tr_par = metin[1 : bolucu[0]], metin[bolucu[0] + 1 :]
        elif len(bolucu) == 2:
            # Biçim B: "## EN ... ## TR" ya da tersi.
            a, b = metin[bolucu[0] + 1 : bolucu[1]], metin[bolucu[1] + 1 :]
            ilk_tr = bool(TR_ISARETI.search(metin[bolucu[0]]))
            en_par, tr_par = (b, a) if ilk_tr else (a, b)
        else:
            self.hatalar.append(
                f"{ad}: {len(bolucu)} dil başlığı var, 1 ya da 2 beklenir / expected 1 or 2 language headings"
            )
            return
        y_en, y_tr = yapi_cikar(en_par), yapi_cikar(tr_par)
        if (y_en.baslik_toplami, y_en.tablo_satiri, y_en.kod_blogu) != (
            y_tr.baslik_toplami,
            y_tr.tablo_satiri,
            y_tr.kod_blogu,
        ):
            self.hatalar.append(
                f"{ad}: EN ve TR yarıları farklı / halves differ\n"
                f"      EN {y_en.ozet(False)}\n      TR {y_tr.ozet(False)}"
            )

    def satir_ici(self, dosya: Path) -> None:
        self.sayac["satır içi/inline"] += 1
        kod = False
        for no, satir in enumerate(satirlar(dosya), 1):
            if satir.lstrip().startswith("```"):
                kod = not kod
            if not kod and re.match(r"#{1,6}\s", satir) and " / " not in satir:
                self.hatalar.append(
                    f"{self._goreli(dosya)}:{no}: başlık iki dilli değil / heading not bilingual: {satir.strip()}"
                )

    def readme_cevirileri(self) -> None:
        kaynak = self.kok / "README.md"
        if not kaynak.is_file():
            return
        ozet = readme_ozeti(kaynak)
        y_en = yapi_cikar(satirlar(kaynak))
        for dil in README_DILLERI:
            self.sayac["readme çeviri"] += 1
            ad = f"README.{dil}.md"
            yol = self.kok / ad
            if not yol.is_file():
                self.hatalar.append(f"{ad}: yok / missing")
                continue
            metin = yol.read_text(encoding="utf-8")
            hedef = self.hatalar if self.kati else self.uyarilar
            m = KAYNAK_ISARETI.search(metin)
            if not m:
                self.hatalar.append(f"{ad}: i18n-source işareti yok / marker missing")
            elif m.group(1) != ozet:
                hedef.append(
                    f"{ad}: README.md değişti, çeviri eşitlenmedi / README.md changed since this translation"
                    f" (işaret/marker {m.group(1)}, şimdi/now {ozet})"
                )
            y = yapi_cikar(metin.splitlines())
            if (y.basliklar.get(2, 0), y.tablo_satiri, y.kod_blogu) != (
                y_en.basliklar.get(2, 0),
                y_en.tablo_satiri,
                y_en.kod_blogu,
            ):
                hedef.append(
                    f"{ad}: bölüm yapısı README.md'den farklı / section structure differs\n"
                    f"      EN H2 {y_en.basliklar.get(2, 0)} · tablo {y_en.tablo_satiri} · kod {y_en.kod_blogu}"
                    f"\n      {dil} H2 {y.basliklar.get(2, 0)} · tablo {y.tablo_satiri} · kod {y.kod_blogu}"
                )
            for diger in ["README.md", "README.tr.md", *(f"README.{d}.md" for d in README_DILLERI)]:
                if diger != ad and f"({diger})" not in metin:
                    self.hatalar.append(f"{ad}: dil çubuğunda {diger} bağlantısı yok / language bar link missing")
        for diger in ("README.md", "README.tr.md"):
            metin = (self.kok / diger).read_text(encoding="utf-8") if (self.kok / diger).is_file() else ""
            for dil in README_DILLERI:
                if f"(README.{dil}.md)" not in metin:
                    self.hatalar.append(f"{diger}: dil çubuğunda README.{dil}.md yok / language bar link missing")

    # --- sınıflandırma
    def calistir(self) -> int:
        bilinen: set[str] = set(MUAF)
        self.sayac["muaf/exempt"] = len(MUAF)
        for en, tr in CIFTLER:
            self.cift(en, tr)
            bilinen.update((en, tr))
        self.adrler()
        bilinen.add(ADR_TR)
        bilinen.update(self._goreli(p) for p in (self.kok / ADR_KLASORU).glob("[0-9][0-9][0-9][0-9]-*.md"))
        for kalip in TEK_DOSYA_KALIPLARI:
            for dosya in sorted(self.kok.glob(kalip)):
                self.tek_dosya(dosya)
                bilinen.add(self._goreli(dosya))
        for ad in SATIR_ICI:
            if (self.kok / ad).is_file():
                self.satir_ici(self.kok / ad)
            bilinen.add(ad)
        self.readme_cevirileri()
        bilinen.update(f"README.{d}.md" for d in README_DILLERI)
        hepsi = list(self.kok.glob("*.md")) + list((self.kok / "docs").rglob("*.md"))
        for yol in sorted(hepsi):
            ad = self._goreli(yol)
            if ad not in bilinen:
                self.hatalar.append(
                    f"{ad}: sınıflandırılmamış belge (scripts/dil_eslik_denetimi.py listelerine "
                    "ekleyin) / unclassified document"
                )
        return 1 if self.hatalar else 0


# ADR adında Türkçe kelime yakalayıcı (ad İngilizce olmalı); küçük, bilinen kelime listesi.
TR_ADI = {"dil", "dilden", "bagimsiz", "ceviri", "istem", "istemleri", "karar", "ses", "kelime", "motor", "ve"}


def _yaz(baslik: str, kayitlar: list[str], gh_turu: str) -> None:
    print(f"{baslik}: {len(kayitlar)}")
    for kayit in kayitlar:
        print("  ", kayit)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::{gh_turu}::{kayit.splitlines()[0]}")


def main(argv: list[str] | None = None) -> int:
    ayr = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ayr.add_argument("--kok", type=Path, default=VARSAYILAN_KOK, help="repo kökü / repo root")
    ayr.add_argument("--kati", action="store_true", help="README çeviri farkları da hata / translation drift fails")
    secim = ayr.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    denetci = Denetci(secim.kok.resolve(), kati=secim.kati)
    kod = denetci.calistir()
    print("sayaç / counts:", denetci.sayac)
    _yaz("uyarı / warnings", denetci.uyarilar, "warning")
    _yaz("hata / errors", denetci.hatalar, "error")
    return kod


if __name__ == "__main__":
    sys.exit(main())
