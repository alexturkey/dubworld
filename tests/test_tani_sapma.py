"""scripts/tani.ps1 DEVIATIONS section (kit KL-23): names of DUBLAJ_* variables only, never values; no network, no GPU."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
PS = shutil.which("powershell")


@pytest.mark.skipif(PS is None, reason="Windows PowerShell not found")
def test_sapma_ad_gorunur_deger_gizli():
    deger = "gizli" + "Deger" + "12345"
    env = dict(os.environ, DUBLAJ_TEST_EZME=deger)
    p = subprocess.run([PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(KOK / "scripts" / "tani.ps1")],
                       capture_output=True, env=env, timeout=180)
    out = p.stdout.decode("utf-8", "replace")
    assert p.returncode == 0, out[-300:]
    assert "DEVIATIONS" in out
    assert "DUBLAJ_TEST_EZME" in out
    assert deger not in out
