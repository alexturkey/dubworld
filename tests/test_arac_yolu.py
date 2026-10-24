"""ffmpeg / ffprobe tam yolla çağrılır; çalışma klasörüne konmuş sahte ffmpeg seçilmez (Düzeltme A, D1). Ağsız."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

from dublaj_hatti.bolum_00_omurga.runtime import arac_yolu

SRC = Path(__file__).resolve().parents[1] / "src" / "dublaj_hatti"
# Ayrı yorumlayıcıda (CrisperWhisper 2.0 Medium deney ortamı) çalışan, paket içe aktaramayan betik: bilinen istisna.
ISTISNALAR = {
    "bolum_20_transkripsiyon/crisperwhisper2_medium_motoru/src/crisperwhisper2_medium_transkript.py",  # ayrı yorumlayıcı
    "bolum_00_omurga/runtime/arac_yolu.py",  # yardımcının kendisi (belgesinde örnek olarak geçer)
}


def _sahte(klasor: Path, ad: str) -> Path:
    klasor.mkdir(parents=True, exist_ok=True)
    yol = klasor / (f"{ad}.exe" if sys.platform == "win32" else ad)
    yol.write_text("sahte", encoding="utf-8")
    yol.chmod(0o755)
    return yol


@pytest.fixture()
def ortam(tmp_path, monkeypatch):
    monkeypatch.setattr(arac_yolu, "runtime_asset_root", lambda: tmp_path / "runtime_assets")
    monkeypatch.delenv(arac_yolu.KLASOR_ORTAMI, raising=False)
    calisma = tmp_path / "calisma"
    calisma.mkdir()
    monkeypatch.chdir(calisma)
    return tmp_path


def test_calisma_klasorundeki_sahte_secilmez(ortam, monkeypatch):
    _sahte(ortam / "calisma", "ffmpeg")
    _sahte(ortam / "calisma" / "goreli", "ffmpeg")
    gercek = _sahte(ortam / "path_klasoru", "ffmpeg")
    monkeypatch.setenv("PATH", os.pathsep.join([".", "", "goreli", str(ortam / "path_klasoru")]))
    assert arac_yolu.arac_bul("ffmpeg") == str(gercek.resolve())


def test_yalniz_calisma_klasorunde_varsa_bulunamadi(ortam, monkeypatch):
    _sahte(ortam / "calisma", "ffprobe")
    monkeypatch.setenv("PATH", os.pathsep.join([".", "goreli"]))
    assert arac_yolu.arac_bul("ffprobe") is None
    with pytest.raises(arac_yolu.AracBulunamadi, match="kur.ps1"):
        arac_yolu.ffprobe_yolu()
    with pytest.raises(FileNotFoundError):  # eski "dosya yok" davranışıyla uyumlu
        arac_yolu.ffprobe_yolu()


def test_sira_ortam_sonra_kurulu_sonra_path(ortam, monkeypatch):
    path_kopyasi = _sahte(ortam / "path_klasoru", "ffmpeg")
    monkeypatch.setenv("PATH", str(ortam / "path_klasoru"))
    assert arac_yolu.ffmpeg_yolu() == str(path_kopyasi.resolve())
    kurulu = _sahte(ortam / "runtime_assets" / "ffmpeg" / "bin", "ffmpeg")
    assert arac_yolu.ffmpeg_yolu() == str(kurulu.resolve())
    acik = _sahte(ortam / "acik", "ffmpeg")
    monkeypatch.setenv(arac_yolu.KLASOR_ORTAMI, str(ortam / "acik"))
    assert arac_yolu.ffmpeg_yolu() == str(acik.resolve())
    monkeypatch.setenv(arac_yolu.KLASOR_ORTAMI, "acik")  # göreli: yok sayılır
    assert arac_yolu.ffmpeg_yolu() == str(kurulu.resolve())


def test_bilinmeyen_arac_reddedilir():
    with pytest.raises(ValueError):
        arac_yolu.arac_bul("cmd")


def test_kaynakta_ciplak_ffmpeg_cagrisi_yok():
    """Statik: liste başında "ffmpeg"/"ffprobe" dizgesi ya da shutil.which("ffmpeg") kalmadı."""
    desen = re.compile(r'\[\s*"(?:ffmpeg|ffprobe)"\s*,|shutil\.which\(\s*"(?:ffmpeg|ffprobe)"\s*\)')
    bulunan = []
    for yol in SRC.rglob("*.py"):
        goreli = yol.relative_to(SRC).as_posix()
        if goreli in ISTISNALAR:
            continue
        for eslesme in desen.finditer(yol.read_text(encoding="utf-8")):
            bulunan.append(f"{goreli}: {eslesme.group(0)}")
    assert bulunan == []
