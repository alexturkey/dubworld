"""`scripts/varsayilan_motor.py`: seçilen VoxCPM2 sesi kullanıcı katmanına varsayılan olarak yazılır (AGENTS.md)."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

_YOL = Path(__file__).resolve().parents[1] / "scripts" / "varsayilan_motor.py"
_spec = importlib.util.spec_from_file_location("varsayilan_motor", _YOL)
vm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vm)


def _oku(dosya: Path) -> dict:
    return tomllib.loads(dosya.read_text(encoding="utf-8"))


def test_dosya_yoksa_olusturur(tmp_path):
    dosya = tmp_path / "ayarlar" / "kullanici.toml"
    assert vm.varsayilan_yap(dosya, "voxcpm2", "ayse/2").startswith("yazildi")
    assert _oku(dosya)["ses"] == {"motor": "voxcpm2", "voxcpm2_ses": "ayse/2"}


def test_var_olan_ses_bolumune_ekler_ve_sesi_degistirir(tmp_path):
    dosya = tmp_path / "kullanici.toml"
    dosya.write_text('[genel]\nhedef_dil = "de"\n\n[ses]\nvoxcpm2_ses = "eski/1"\n\n[video]\ncq = 20\n', encoding="utf-8")
    assert vm.varsayilan_yap(dosya, "voxcpm2", "yeni/3") == "yazildi: motor=voxcpm2, voxcpm2_ses=yeni/3"
    ayar = _oku(dosya)
    assert ayar["ses"] == {"motor": "voxcpm2", "voxcpm2_ses": "yeni/3"}
    assert ayar["genel"]["hedef_dil"] == "de" and ayar["video"]["cq"] == 20


def test_kullanicinin_motor_secimine_dokunmaz(tmp_path):
    dosya = tmp_path / "kullanici.toml"
    dosya.write_text('[ses]\nmotor = "supertonic"\n', encoding="utf-8")
    assert vm.varsayilan_yap(dosya, "voxcpm2").startswith("dokunulmadi")
    assert vm.varsayilan_yap(dosya, "voxcpm2", "ayse/2") == "yazildi: voxcpm2_ses=ayse/2"
    assert _oku(dosya)["ses"] == {"motor": "supertonic", "voxcpm2_ses": "ayse/2"}


def test_islemci_secilmisse_dokunmaz(tmp_path):
    dosya = tmp_path / "kullanici.toml"
    dosya.write_text('[genel]\ncihaz = "cpu"\n', encoding="utf-8")
    assert vm.varsayilan_yap(dosya, "voxcpm2", "ayse/2").startswith("dokunulmadi")
    assert "ses" not in _oku(dosya)


def test_klasor_yolu_kacislanir(tmp_path):
    dosya = tmp_path / "kullanici.toml"
    yol = 'sesler\\benim "en iyi" sesim'
    vm.varsayilan_yap(dosya, "voxcpm2", yol)
    assert _oku(dosya)["ses"]["voxcpm2_ses"] == yol
