"""Köprü işçisi zaman aşımında bütün süreç ağacını kapatır ve iş bütçesini aşmaz.

Gerçek kaynak denemesinde codex CLI'nin yeniden deneme çağrısı cevap vermeden asılı kaldı; işçi
zaman aşımına düştükten sonra codex.exe ve araç süreci (node_repl) açık kalmıştı.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
ISCILER = [
    KOK / "src/dublaj_hatti/bolum_40_ceviri/llm_kopru/scripts/bridge_worker.py",
    KOK / "src/dublaj_hatti/bolum_40_ceviri/claude_code_cli/scripts/bridge_worker.py",
]


def _yukle(yol: Path):
    sys.path.insert(0, str(yol.parent))
    try:
        spec = importlib.util.spec_from_file_location(f"kopru_{yol.parent.parent.name}", yol)
        modul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)
        return modul
    finally:
        sys.path.remove(str(yol.parent))


def _canli(pid: int) -> bool:
    if os.name == "nt":
        cikti = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return str(pid) in cikti
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@pytest.mark.parametrize("yol", ISCILER, ids=["llm_kopru", "claude_code_cli"])
def test_zaman_asiminda_torun_surec_de_kapanir(yol, tmp_path):
    modul = _yukle(yol)
    pid_dosyasi = tmp_path / "torun.pid"
    torun = "import time; time.sleep(120)"
    cocuk = (
        "import subprocess, sys, time;"
        f"p = subprocess.Popen([sys.executable, '-c', {torun!r}]);"
        f"open({str(pid_dosyasi)!r}, 'w').write(str(p.pid));"
        "time.sleep(120)"
    )
    with pytest.raises(subprocess.TimeoutExpired):
        modul.agacli_calistir([sys.executable, "-c", cocuk], input_text="", timeout=3,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    torun_pid = int(pid_dosyasi.read_text())
    for _ in range(20):
        if not _canli(torun_pid):
            break
        time.sleep(0.25)
    assert not _canli(torun_pid), "torun süreç zaman aşımından sonra açık kaldı"


@pytest.mark.parametrize("yol", ISCILER, ids=["llm_kopru", "claude_code_cli"])
def test_is_butcesi_yeniden_denemeyi_sinirlar(yol, monkeypatch):
    modul = _yukle(yol)
    modul.is_butcesi_baslat(900)
    assert modul.kalan_sure(900) <= 900
    monkeypatch.setattr(modul, "_IS_BITIS", time.time() + 100)
    assert 90 <= modul.kalan_sure(900) <= 100
    monkeypatch.setattr(modul, "_IS_BITIS", time.time() - 5)
    assert modul.kalan_sure(900) == modul.EN_AZ_CAGRI_SURESI


@pytest.mark.parametrize("yol", ISCILER, ids=["llm_kopru", "claude_code_cli"])
def test_normal_cagri_cikti_doner(yol):
    modul = _yukle(yol)
    sonuc = modul.agacli_calistir([sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"],
                                  input_text="çğı", timeout=30,
                                  env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert sonuc.returncode == 0
    assert sonuc.stdout.strip() == "ÇĞI"
