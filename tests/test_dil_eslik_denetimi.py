"""scripts/dil_eslik_denetimi.py: negatif kontrol (eksik karşılık, yapı farkı, bayat çeviri, sınıflandırılmamış belge,
Türkçe ADR adı), pozitif kontrol ve repo belgelerinin tamamı temiz."""

from __future__ import annotations

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "scripts"))
import dil_eslik_denetimi as d  # noqa: E402

TEK_DOSYA = "# Başlık\n\nmetin\n\n## How it works\n\n| a | b |\n|---|---|\n\n## Türkçe\n\n### Nasıl çalışır\n\n| a | b |\n|---|---|\n"


def _kucuk_repo(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(d, "CIFTLER", [("README.md", "README.tr.md")])
    monkeypatch.setattr(d, "TEK_DOSYA_KALIPLARI", ("docs/motorlar/*.md",))
    monkeypatch.setattr(d, "SATIR_ICI", ())
    monkeypatch.setattr(d, "MUAF", {})
    monkeypatch.setattr(d, "README_DILLERI", ("de",))
    readme = "# R\n\n[Türkçe](README.tr.md) · [Deutsch](README.de.md)\n\n## Install\n\n```text\nx\n```\n"
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")
    (tmp_path / "README.tr.md").write_text(readme.replace("Install", "Kurulum"), encoding="utf-8")
    ozet = d.readme_ozeti(tmp_path / "README.md")
    (tmp_path / "README.de.md").write_text(
        f"# R\n\n[English](README.md) · [Türkçe](README.tr.md)\n\n## Installieren\n\n```text\nx\n```\n"
        f"<!-- i18n-source: README.md sha256:{ozet} -->\n", encoding="utf-8")
    (tmp_path / "docs" / "motorlar").mkdir(parents=True)
    (tmp_path / "docs" / "motorlar" / "m.md").write_text(TEK_DOSYA, encoding="utf-8")
    (tmp_path / "docs" / "adr").mkdir()
    (tmp_path / "docs" / "muhendislik").mkdir()
    (tmp_path / "docs" / "adr" / "0001-one-thing.md").write_text("# ADR\n\n## Context\nx\n## Decision\ny\n",
                                                                    encoding="utf-8")
    (tmp_path / "docs" / "muhendislik" / "kararlar.md").write_text(
        "# Kararlar\n\n## 0001 — Bir şey\n\n### Bağlam\nx\n### Karar\ny\n", encoding="utf-8")
    return tmp_path


def test_pozitif(tmp_path, monkeypatch):
    kok = _kucuk_repo(tmp_path, monkeypatch)
    denetci = d.Denetci(kok)
    assert denetci.calistir() == 0, denetci.hatalar
    assert denetci.uyarilar == []


def test_negatif(tmp_path, monkeypatch):
    kok = _kucuk_repo(tmp_path, monkeypatch)
    (kok / "README.tr.md").write_text("# R\n\n## Kurulum\n", encoding="utf-8")  # kod bloğu eksik
    (kok / "docs" / "motorlar" / "m.md").write_text(TEK_DOSYA.split("## Türkçe")[0], encoding="utf-8")
    (kok / "README.md").write_text((kok / "README.md").read_text(encoding="utf-8") + "\nyeni\n", encoding="utf-8")
    (kok / "docs" / "yeni.md").write_text("# Yeni\n", encoding="utf-8")
    (kok / "docs" / "adr" / "0002-dil-karar.md").write_text("# ADR\n", encoding="utf-8")
    denetci = d.Denetci(kok)
    assert denetci.calistir() == 1
    metin = "\n".join(denetci.hatalar)
    assert "README.md ↔ README.tr.md" in metin
    assert "m.md: Türkçe bölüm yok" in metin
    assert "docs/yeni.md: sınıflandırılmamış" in metin
    assert "0002-dil-karar.md: ADR dosya adı" in metin
    assert "kararlar.md içinde '## 0002'" in metin
    assert any("README.de.md: README.md değişti" in u for u in denetci.uyarilar)
    kati = d.Denetci(kok, kati=True)
    kati.calistir()
    assert any("README.de.md: README.md değişti" in h for h in kati.hatalar)


def test_repo_temiz():
    denetci = d.Denetci(KOK)
    assert denetci.calistir() == 0, "\n".join(denetci.hatalar)
