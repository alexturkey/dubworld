"""CLI günlüğü: her satır bir kez, DEBUG yalnız --ayrintili ile (kök neden: cli._gunlugu_kur belge dizesi)."""

from __future__ import annotations

import logging

import pytest

from dublaj_hatti import cli


@pytest.fixture
def temiz_gunluk():
    paket, kok = logging.getLogger("dublaj_hatti"), logging.getLogger()
    eski = (list(paket.handlers), paket.propagate, paket.level, list(kok.handlers), kok.level)
    for h in list(kok.handlers):
        kok.removeHandler(h)
    for h in list(paket.handlers):
        paket.removeHandler(h)
    yield paket
    for h in list(paket.handlers):
        paket.removeHandler(h)
    for h in list(kok.handlers):
        kok.removeHandler(h)
    for h in eski[0]:
        paket.addHandler(h)
    paket.propagate, paket.level = eski[1], eski[2]
    for h in eski[3]:
        kok.addHandler(h)
    kok.setLevel(eski[4])


def _dubber_gibi(paket):
    """dubber.py modül düzeyindeki davranış: işleyici yoksa yalın StreamHandler, günlükçü DEBUG."""
    if not paket.handlers:
        paket.addHandler(logging.StreamHandler())
        paket.setLevel(logging.DEBUG)


@pytest.mark.parametrize("dubber_once", [True, False])
def test_her_satir_bir_kez(temiz_gunluk, capsys, dubber_once):
    paket = temiz_gunluk
    if dubber_once:
        _dubber_gibi(paket)
    cli._gunlugu_kur(False, "INFO")
    _dubber_gibi(paket)
    cli._gunlugu_kur(False, "INFO")  # ikinci kez kurmak da çoğaltmaz
    logging.getLogger("dublaj_hatti").info("TEK_SATIR")
    logging.getLogger("dublaj_hatti.api").info("ALT_SATIR")
    logging.getLogger("dublaj_hatti").debug("AYRINTI_SATIRI")
    hata = capsys.readouterr().err
    assert hata.count("TEK_SATIR") == 1 and hata.count("ALT_SATIR") == 1
    assert "AYRINTI_SATIRI" not in hata


def test_ayrintili_debug_gosterir_ve_dosya_isleyicisine_dokunmaz(temiz_gunluk, capsys, tmp_path):
    paket = temiz_gunluk
    dosya = logging.FileHandler(tmp_path / "console_log.txt", encoding="utf-8")
    paket.addHandler(dosya)
    cli._gunlugu_kur(True, "INFO")
    paket.debug("AYRINTI_SATIRI")
    dosya.flush()
    assert capsys.readouterr().err.count("AYRINTI_SATIRI") == 1
    assert dosya in paket.handlers
    dosya.close()
    assert "AYRINTI_SATIRI" in (tmp_path / "console_log.txt").read_text(encoding="utf-8")


def test_python_api_basicconfig_ile_tek_satir():
    """Python API kullanıcısı logging.basicConfig() çağırıp dubber'ı içe aktarınca her satır bir kez basılır (propagate=False)."""
    import subprocess
    import sys

    kod = (
        "import logging, sys\n"
        "logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(message)s')\n"
        "try:\n"
        "    from dublaj_hatti.bolum_00_omurga.core import dubber\n"
        "except ImportError as hata:\n"
        "    print('ATLA', hata); sys.exit(0)\n"
        "logging.getLogger('dublaj_hatti.api').info('API_SATIRI')\n"
    )
    bayrak = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    sonuc = subprocess.run([sys.executable, "-c", kod], capture_output=True, text=True, timeout=300, creationflags=bayrak)
    if sonuc.stdout.startswith("ATLA"):
        pytest.skip("dubber ağır bağımlılıkları kurulu değil: " + sonuc.stdout.strip())
    assert sonuc.returncode == 0, sonuc.stderr[-2000:]
    assert sonuc.stderr.count("API_SATIRI") == 1, sonuc.stderr[-2000:]
