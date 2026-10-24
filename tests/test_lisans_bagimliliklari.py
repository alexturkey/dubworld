"""Lisans kapısı: yeniden dağıtımı yasak ya da GPL bağımlılıklar kurulumdan ve koddan uzak durur."""

from __future__ import annotations

import importlib
import re
import sys
import tomllib
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
YASAK = ("kaldiio", "funasr", "unidecode")


def _paket_adlari(metin: str) -> set[str]:
    return {m.group(1).lower() for m in re.finditer(r"^\s*([A-Za-z0-9_.\-]+)\s*(?:==|>=|\[|$)", metin, re.M)}


def test_pyproject_yasak_bagimlilik_yok():
    veri = tomllib.loads((KOK / "pyproject.toml").read_text(encoding="utf-8"))
    adlar = {re.split(r"[<>=\[; ]", d, maxsplit=1)[0].lower() for d in veri["project"]["dependencies"]}
    for grup in veri["project"].get("optional-dependencies", {}).values():
        adlar |= {re.split(r"[<>=\[; ]", d, maxsplit=1)[0].lower() for d in grup}
    assert not adlar & set(YASAK)


def test_kilitlerde_yasak_paket_yok():
    for kilit in sorted((KOK / "requirements").glob("*.txt")) + sorted((KOK / "requirements").glob("*.in")):
        bulunan = _paket_adlari(kilit.read_text(encoding="utf-8")) & set(YASAK)
        assert not bulunan, f"{kilit.name}: {sorted(bulunan)}"


def test_kod_yasak_paketi_import_etmiyor():
    desen = re.compile(r"^\s*(?:import|from)\s+(kaldiio|funasr|unidecode)\b", re.M)
    bulunan = [
        str(p.relative_to(KOK))
        for p in (KOK / "src").rglob("*.py")
        if desen.search(p.read_text(encoding="utf-8", errors="replace"))
    ]
    assert not bulunan


def test_dosya_adi_temizleyici_unidecode_olmadan_belirlenimli(monkeypatch):
    monkeypatch.setitem(sys.modules, "unidecode", None)  # kurulu olsa bile kullanılmamalı
    modul = importlib.import_module(
        "dublaj_hatti.bolum_10_kaynak_edinme.adim_10_dosya_adi_guvenligi.filename_sanitizer"
    )
    modul = importlib.reload(modul)
    assert modul.sanitize_filename("РОССИЯ - ЖИЗНЬ.mp4") == "rossiya_-_zhizn.mp4"
    assert modul.sanitize_filename("Çığ İstanbul şöyle.mp4", source_lang="tr") == "cig_istanbul_soyle.mp4"
    assert modul.sanitize_filename("Größe café.mp4", source_lang="de") == "groesse_cafe.mp4"
    assert modul.sanitize_filename("CON.mp4") == "video_con.mp4"
