"""Düzeltme A küçük maddeler: D5 (yalnız DUBLAJ_OUTPUT_DIR), D6 (altyazı yazı tipi yedek zinciri),
D7 (yardımda "==SUPPRESS==" yok). Ağsız, GPU'suz."""

from __future__ import annotations

import pytest

from dublaj_hatti.bolum_00_omurga.runtime import output_paths


# ---- D5 ------------------------------------------------------------------------------------------------
def test_yalniz_uygulama_ortam_degiskeni(tmp_path, monkeypatch):
    assert output_paths.OUTPUT_ENV_NAMES == ("DUBLAJ_OUTPUT_DIR",)
    monkeypatch.delenv("DUBLAJ_OUTPUT_DIR", raising=False)
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "baska_arac"))  # genel ad artık okunmaz
    assert output_paths.configured_output_root() == output_paths.DEFAULT_OUTPUT_ROOT
    monkeypatch.setenv("DUBLAJ_OUTPUT_DIR", str(tmp_path / "dublaj"))
    assert output_paths.configured_output_root() == tmp_path / "dublaj"


# ---- D6 ------------------------------------------------------------------------------------------------
@pytest.fixture()
def yazi_tipi():
    pytest.importorskip("PIL")
    from dublaj_hatti.bolum_50_seslendirme.altyazili_dublaj import yazi_tipi as mod

    mod.yazi_tipi_yolu.cache_clear()
    mod.yazi_tipi.cache_clear()
    yield mod
    mod.yazi_tipi_yolu.cache_clear()
    mod.yazi_tipi.cache_clear()


def test_zincir_sirasi(yazi_tipi):
    adlar = [a.rsplit("/", 1)[-1].lower() for a in yazi_tipi.ADAYLAR]
    assert adlar.index("arial.ttf") < adlar.index("dejavusans.ttf") < adlar.index("liberationsans-regular.ttf")


def test_ilk_acilan_aday_secilir(yazi_tipi, monkeypatch):
    from PIL import ImageFont

    gercek = ImageFont.truetype
    acilan = []

    def sahte(ad, boyut, **ek):
        if not isinstance(ad, str):  # load_default'un gömülü yazı tipi: gerçek yükleyici
            return gercek(ad, boyut, **ek)
        acilan.append(ad)
        if "DejaVu" not in ad:
            raise OSError(ad)
        return ImageFont.load_default(size=boyut)

    monkeypatch.setattr(yazi_tipi.ImageFont, "truetype", sahte)
    assert yazi_tipi.yazi_tipi_yolu() == "DejaVuSans.ttf"
    assert acilan[:3] == list(yazi_tipi.ADAYLAR[:3])  # Arial adayları önce denendi


def test_hicbiri_yoksa_gomulu(yazi_tipi, monkeypatch):
    gercek = yazi_tipi.ImageFont.truetype

    def yok(ad, boyut, **ek):
        if not isinstance(ad, str):
            return gercek(ad, boyut, **ek)
        raise OSError(ad)

    monkeypatch.setattr(yazi_tipi.ImageFont, "truetype", yok)
    assert yazi_tipi.yazi_tipi_yolu() is None
    font = yazi_tipi.yazi_tipi(40)
    assert font.getbbox("Ağ")[3] > 0  # gömülü yazı tipi de ölçeklenir ve çizer
    assert yazi_tipi.yazi_tipi_ozeti() == "pillow_load_default"


# ---- D7 ------------------------------------------------------------------------------------------------
def test_yardimda_suppress_yok(capsys):
    from dublaj_hatti import cli

    with pytest.raises(SystemExit):
        cli._parser().parse_args(["--help"])
    cikti = capsys.readouterr().out
    assert "==SUPPRESS==" not in cikti
    satirlar = [s.strip() for s in cikti.splitlines()]
    assert not any(s.startswith("is-calistir") for s in satirlar)  # iç komut açıklamalı listede yok
    assert any(s.startswith("devam") for s in satirlar)
    assert cli._parser().parse_args(["is-calistir", "3"]).is_ == 3  # iç komut çalışmaya devam eder
