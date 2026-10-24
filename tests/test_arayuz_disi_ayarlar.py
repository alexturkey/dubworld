"""Yerel program yolu ayarları (ceviri.codex.cli_yolu, ceviri.claude.cli_yolu) arayüzden değiştirilemez
(Düzeltme A, D2): web belirteci ya da Telegram erişimi yerel program seçtiremez. Ağsız."""

from __future__ import annotations

import pytest

from dublaj_hatti import is_yurutucu
from dublaj_hatti.is_yurutucu import ARAYUZ_DISI_AYARLAR, ayar_degisiklikleri, ayar_formu
from dublaj_hatti.yapilandirma import SEMA


def test_anahtarlar_semada_var():
    assert ARAYUZ_DISI_AYARLAR == {"ceviri.codex.cli_yolu", "ceviri.claude.cli_yolu"}
    assert ARAYUZ_DISI_AYARLAR <= set(SEMA)


@pytest.mark.parametrize("anahtar", sorted(ARAYUZ_DISI_AYARLAR))
def test_yeni_is_ayari_reddedilir(anahtar):
    with pytest.raises(ValueError, match="arayüzden değiştirilemez"):
        ayar_degisiklikleri({anahtar: "C:/Windows/System32/calc.exe"})


def test_formda_gorunmez():
    assert not {o["anahtar"] for o in ayar_formu()} & ARAYUZ_DISI_AYARLAR


@pytest.mark.parametrize("anahtar", sorted(ARAYUZ_DISI_AYARLAR))
def test_devam_ayari_reddedilir(anahtar):
    yurutucu = object.__new__(is_yurutucu.IsYurutucu)  # denetim depoya dokunmadan önce
    with pytest.raises(ValueError, match="arayüzden değiştirilemez"):
        yurutucu.devam(1, ayar_ifadeleri=[f"{anahtar}=/tmp/sahte"])


def test_web_devam_reddeder():
    from dublaj_hatti import web

    istek = object.__new__(web.Isleyici)  # ayar denetimi yürütücüye ulaşmadan önce
    with pytest.raises(ValueError, match="arayüzden değiştirilemez"):
        istek._devam({"is": 1, "ayarlar": {"ceviri.claude.cli_yolu": "x"}})
