"""Kurulum zinciri: Parakeet modeli manifestte (sabit commit + sha256), XTTS ayrı ortamı hash'li kilitle, indirici
yalnız https. Ağsız; gerçek indirme ve kurulum ayrı doğrulandı (DEVIR K17)."""

from __future__ import annotations

import json
import re
import sys
import urllib.error
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "scripts"))
import modelleri_indir  # noqa: E402

MANIFEST = json.loads((KOK / "scripts" / "modeller.json").read_text(encoding="utf-8"))["dosyalar"]
KUR = (KOK / "scripts" / "kur.ps1").read_text(encoding="utf-8-sig")
REQ = KOK / "requirements"


# --- Parakeet ----------------------------------------------------------------------------------------------
def test_parakeet_modeli_manifestte_ve_motorun_bekledigi_yerde():
    from dublaj_hatti import kayit
    from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import parakeet_unified_en_int8_model_dir

    kayitlar = [k for k in MANIFEST if k["adim"] == "parakeet"]
    hedef_klasor = parakeet_unified_en_int8_model_dir().relative_to(KOK).as_posix()
    adlar = {Path(k["hedef"]).name for k in kayitlar}
    assert set(kayit.PARAKEET_MODEL_DOSYALARI) <= adlar
    assert "NVIDIA_MODEL_CARD.md" in adlar  # lisans bildirimi modelle birlikte iner
    for k in kayitlar:
        assert Path(k["hedef"]).parent.as_posix() == hedef_klasor
        assert re.fullmatch(r"https://huggingface\.co/[^/]+/[^/]+/resolve/[0-9a-f]{40}/.+", k["url"]), k["url"]
        assert re.fullmatch(r"[0-9a-f]{64}", k["sha256"]) and k["boyut"] > 0
        assert "NVIDIA Open Model License" in k["lisans"]


def test_parakeet_motor_dosya_listesi_kayitla_ayni():
    kaynak = (KOK / "src/dublaj_hatti/bolum_20_transkripsiyon/parakeet_cpu_align_motoru/worker.py").read_text(
        encoding="utf-8")
    from dublaj_hatti import kayit

    for ad in kayit.PARAKEET_MODEL_DOSYALARI:
        assert f'"{ad}"' in kaynak


def test_kur_parakeet_adimi_modeli_indirir():
    blok = KUR[KUR.index('foreach ($ek in @("demucs", "youtube", "parakeet", "speechmatics"))'):]
    blok = blok[: blok.index("function Ek-Kur")]
    assert '-eq "parakeet"' in blok and "modelleri_indir.py" in blok and "--adim parakeet" in blok


def test_parakeet_kurulu_denetimi_model_ister(monkeypatch, tmp_path):
    from dublaj_hatti import kayit
    from dublaj_hatti.bolum_00_omurga.runtime import asset_paths

    monkeypatch.setattr(kayit.importlib.util, "find_spec", lambda ad: object())
    monkeypatch.setattr(asset_paths, "parakeet_unified_en_int8_model_dir", lambda: tmp_path)
    assert not kayit._parakeet()
    for ad in kayit.PARAKEET_MODEL_DOSYALARI:
        (tmp_path / ad).write_bytes(b"x")
    assert kayit._parakeet()


# --- XTTS ayrı ortam kilidi --------------------------------------------------------------------------------
def _sabitler(yol: Path) -> dict[str, str]:
    return dict(re.findall(r"^([A-Za-z0-9_.\-]+)==(\S+)", yol.read_text(encoding="utf-8"), re.M))


@pytest.mark.parametrize("profil", ["gpu", "cpu"])
def test_xtts_ortam_kilidi_tam_ve_hashli(profil):
    yol = REQ / f"xtts_venv_{profil}.txt"
    metin = yol.read_text(encoding="utf-8")
    sabit = _sabitler(yol)
    assert sabit["coqui-tts"] == _sabitler(REQ / "ek_tts_xtts.txt")["coqui-tts"]
    assert sabit["torch"] == _sabitler(REQ / f"{profil}.txt")["torch"]
    assert sabit["torchaudio"] == _sabitler(REQ / f"{profil}.txt")["torchaudio"]
    # ek_tts_xtts.txt'deki her sürüm aynen (K16 kilidi kullanılır)
    for ad, surum in _sabitler(REQ / "ek_tts_xtts.txt").items():
        assert sabit.get(ad) == surum, ad
    # her paket satırının arkasında en az bir hash
    paketler = re.split(r"\n(?=[A-Za-z0-9_.\-]+==)", metin)
    for blok in paketler[1:]:
        assert "--hash=sha256:" in blok, blok.splitlines()[0]
    assert "_kisit" not in metin


def test_kur_xtts_kilitli_kurar():
    blok = KUR[KUR.index('if (Adim "tts-xtts")'):]
    blok = blok[: blok.index('if (Adim "crisper")')]
    assert "--require-hashes" in blok and "xtts_venv_gpu.txt" in blok and "xtts_venv_cpu.txt" in blok
    assert "coqui-tts==" not in blok and "torch==" not in blok  # kilitsiz paket adı kalmadı


# --- indirici yalnız https ---------------------------------------------------------------------------------
@pytest.mark.parametrize("url", [
    "http://huggingface.co/a/b/resolve/x/y",
    "file:///C:/Windows/win.ini",
    "ftp://huggingface.co/x",
    "https://evil.example/x",
    "https://huggingface.co" + "@" + "evil.example/x",  # @ birleştirilir: yasal denetimin e-posta deseni
    "https://user:pw" + "@" + "huggingface.co/x",
])
def test_indirici_https_disini_reddeder(url):
    with pytest.raises(SystemExit):
        modelleri_indir.https_dogrula(url)


def test_indirici_manifest_adreslerini_kabul_eder():
    for k in MANIFEST:
        assert modelleri_indir.https_dogrula(k["url"]) == k["url"]


def test_yonlendirme_yalniz_https():
    isleyici = modelleri_indir._YalnizHttpsYonlendirme()
    istek = modelleri_indir.urllib.request.Request("https://huggingface.co/x")
    with pytest.raises(urllib.error.HTTPError):
        isleyici.redirect_request(istek, None, 302, "Found", {}, "http://huggingface.co/x")
    yeni = isleyici.redirect_request(istek, None, 302, "Found", {}, "https://cdn-lfs.huggingface.co/x")
    assert yeni.full_url.startswith("https://")


def test_telegram_dockerfile_taban_imaji_ozetle_sabit():
    # Etiket başka imaja taşınabilir; her FROM satırı @sha256 özetiyle sabit olmalı (docs/engineering/pinned-values.md).
    satirlar = [s for s in (KOK / "scripts" / "telegram_bot_api.Dockerfile").read_text(encoding="utf-8").splitlines()
                if s.startswith("FROM ")]
    assert len(satirlar) == 2
    assert all(re.match(r"FROM \S+@sha256:[0-9a-f]{64}(\s|$)", s) for s in satirlar), satirlar
