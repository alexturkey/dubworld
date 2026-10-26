"""API anahtar adları tek kaynaktan: köprünün okuduğu adlar = `dubla kontrol` = .env.example = belgeler.

Kök hata (K9 bulgusu): kayit.py `GEMINI_API_KEY` / `GROQ_API_KEY` arıyordu, köprü başka adları okuyordu; anahtar
doğruyken `dubla kontrol` "yok" diyordu.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dublaj_hatti import kayit
from dublaj_hatti.bolum_40_ceviri import arka_uc_secimi

KOK = Path(__file__).resolve().parents[1]
KOPRU = KOK / "src/dublaj_hatti/bolum_40_ceviri/llm_kopru/scripts/bridge_worker.py"
ANAHTAR_DESENI = re.compile(r"\b[A-Z][A-Z0-9_]*_API_KEY(?:_[0-9]+)?\b")
# Codex CLI'nin kendi oturum değişkenleri: köprü bunları alt süreçten SİLER (anahtar olarak okumaz).
CODEX_OTURUM = {"OPENAI_API_KEY", "CODEX_API_KEY"}


def _ceviri_adlari() -> set[str]:
    return {ad for adlar in arka_uc_secimi.API_ANAHTARI_DEGISKENLERI.values() for ad in adlar}


def _temizle(monkeypatch: pytest.MonkeyPatch) -> None:
    for ad in _ceviri_adlari() | {"GEMINI_API_KEY", "GROQ_API_KEY"}:
        monkeypatch.delenv(ad, raising=False)


def test_kopru_adlari_tablo_ile_ayni():
    kopru = set(ANAHTAR_DESENI.findall(KOPRU.read_text(encoding="utf-8"))) - CODEX_OTURUM
    assert kopru == _ceviri_adlari()


@pytest.mark.parametrize("ad", sorted(arka_uc_secimi.API_ANAHTARI_DEGISKENLERI))
def test_kontrol_her_kopru_adini_tanir(monkeypatch, ad):
    _temizle(monkeypatch)
    motor = kayit.motor(ad)
    assert motor is not None and not motor.kurulu()
    for degisken in arka_uc_secimi.API_ANAHTARI_DEGISKENLERI[ad]:
        _temizle(monkeypatch)
        monkeypatch.setenv(degisken, "x")
        assert motor.kurulu(), f"{ad}: {degisken} köprüde okunuyor ama `dubla kontrol` görmüyor"


def test_eski_yanlis_adlar_sayilmaz(monkeypatch):
    _temizle(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert not kayit.motor("gemini_2_5_flash").kurulu()


def test_env_ornegi_her_motora_bir_ad_verir_ve_bilinmeyen_ad_yok():
    satirlar = (KOK / ".env.example").read_text(encoding="utf-8").splitlines()
    tanimli = {s.split("=", 1)[0] for s in satirlar if "=" in s and not s.startswith("#")}
    bilinen = _ceviri_adlari()
    for adlar in list(arka_uc_secimi.API_ANAHTARI_DEGISKENLERI.values()):
        assert tanimli & set(adlar), adlar
    assert {a for a in tanimli if ANAHTAR_DESENI.fullmatch(a)} <= bilinen


def test_belgeler_yalniz_gercek_adlari_ogretir():
    bilinen = _ceviri_adlari() | CODEX_OTURUM
    dosyalar = [*KOK.glob("*.md"), *(KOK / "docs").rglob("*.md"), *(KOK / ".claude").rglob("*.md")]
    yanlis = []
    for dosya in dosyalar:
        for no, satir in enumerate(dosya.read_text(encoding="utf-8").splitlines(), 1):
            for ad in ANAHTAR_DESENI.findall(satir):
                if ad not in bilinen:
                    yanlis.append(f"{dosya.relative_to(KOK)}:{no}: {ad}")
    assert not yanlis, yanlis
