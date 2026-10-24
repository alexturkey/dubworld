"""scripts/yasal_denetim.py: every rule fires on a planted example, stays silent on a clean tree, allow-list is narrow.

Planted values are assembled at run time so this file itself carries no real-looking secret or path.
"""

from __future__ import annotations

import importlib.util
import struct
import sys
import zlib
from pathlib import Path

import pytest

_YOL = Path(__file__).resolve().parents[1] / "scripts" / "yasal_denetim.py"
_spec = importlib.util.spec_from_file_location("yasal_denetim", _YOL)
assert _spec and _spec.loader
yd = importlib.util.module_from_spec(_spec)
sys.modules["yasal_denetim"] = yd  # dataclasses need the module registered
_spec.loader.exec_module(yd)


def _agac(tmp_path: Path, dosyalar: dict[str, str | bytes]) -> Path:
    for ad, icerik in dosyalar.items():
        p = tmp_path / ad
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(icerik, bytes):
            p.write_bytes(icerik)
        else:
            p.write_text(icerik, encoding="utf-8")
    return tmp_path


def _kurallar(kok: Path, **kw: object) -> set[str]:
    return {b.kural for b in yd.tara(kok, **kw)}


def test_temiz_agac(tmp_path: Path) -> None:
    kok = _agac(tmp_path, {
        "README.md": "Install with `pip install .` then run `dubla video.mp4`. Contact: dev@users.noreply.github.com\n",
        "src/a.py": "import os\nAPI_KEY = os.environ.get('GEMINI_API_KEY', '')\nprint('C:/Users/<you>/video.mp4')\n",
    })
    assert yd.tara(kok) == []
    assert yd.main(["--kok", str(kok)]) == 0


@pytest.mark.parametrize(("kural", "metin"), [
    ("edge_tts", "import " + "edge" + "_tts\n"),
    ("google_resmi_degil", "from " + "google" + "trans import Translator\n"),
    ("google_resmi_degil", "url = 'https://translate." + "googleapis.com/translate_a/single'\n"),
    ("sir", "key = '" + "sk-" + "ant-" + "a1B2" * 8 + "'\n"),
    ("sir", "HF = '" + "hf_" + "Ab3" * 12 + "'\n"),
    ("sir", "-----BEGIN " + "PRIVATE KEY-----\n"),
    ("kisisel_yol", "out = r'C:" + "\\Users\\" + "someone\\Desktop'\n"),
    ("kisisel_yol", "out = r'E:" + "\\cikti'\n"),
    ("kisisel_yol", "cd /c/" + "Users/someone/repo\n"),
    ("e_posta", "author: " + "person" + "@" + "mail.com\n"),
    ("telegram", "chat_id = " + "-100" + "1234567890\n"),
    ("telegram", "token = '" + "123456789:AA" + "x" * 33 + "'\n"),
    ("telegram", "see t." + "me/somechannel\n"),
    ("kullanim_izi", "Varsayılanlar son " + "2 ay en çok seçilen ayarlar\n"),
    ("kullanim_izi", "chosen in 42" + " jobs\n"),
    ("kullanim_izi", "Önerilen akış (yazar" + "ın ayarları)\n"),
    ("zaman_izi", "tz = 'Europe/" + "Istanbul'\n"),
])
def test_kural_yakalar(tmp_path: Path, kural: str, metin: str) -> None:
    kok = _agac(tmp_path, {"src/x.py": metin})
    assert kural in _kurallar(kok)
    assert yd.main(["--kok", str(kok)]) == 1


def test_sir_raporda_maskeli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    deger = "gh" + "p_" + "Z" * 36
    kok = _agac(tmp_path, {"a.txt": f"t = '{deger}'\n"})
    assert yd.main(["--kok", str(kok)]) == 1
    assert deger not in capsys.readouterr().out


def test_medya_ve_meta(tmp_path: Path) -> None:
    def parca(tur: bytes, veri: bytes) -> bytes:
        return struct.pack(">I", len(veri)) + tur + veri + struct.pack(">I", zlib.crc32(tur + veri))
    png = b"\x89PNG\r\n\x1a\n" + parca(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)) \
        + parca(b"tEXt", b"Author\x00someone") + parca(b"IEND", b"")
    kok = _agac(tmp_path, {"docs/ekran.png": png, "ornek/ses.mp3": b"ID3\x03\x00" + b"\x00" * 64})
    k = _kurallar(kok)
    assert {"medya_dosyasi", "medya_meta"} <= k


def test_tarih_damgali_klasor(tmp_path: Path) -> None:
    kok = _agac(tmp_path, {"uretimler/2026-10-24_deneme/not.txt": "x\n"})
    assert "zaman_izi" in _kurallar(kok)


def test_kisisel_liste_repo_disinda(tmp_path: Path) -> None:
    kok = _agac(tmp_path / "repo", {"a.md": "Made by Jane Q Example\n"})
    liste = tmp_path / "gizli.txt"
    liste.write_text("jane q example\n", encoding="utf-8")
    assert "kisisel_terim" in _kurallar(kok, kisisel=["jane q example"])
    assert yd.main(["--kok", str(kok), "--kisisel", str(liste)]) == 1
    icerde = kok / "liste.txt"
    icerde.write_text("x\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        yd.main(["--kok", str(kok), "--kisisel", str(icerde)])


def test_izin_listesi_dar(tmp_path: Path) -> None:
    kok = _agac(tmp_path, {
        "THIRD_PARTY.md": "Not included: edge" + "-tts\n",
        "src/a.py": "import edge" + "_tts\n",
        "scripts/yasal_denetim_izin.txt": "edge_tts | THIRD_PARTY.md | - | excluded-component list\n",
    })
    bulgular = yd.tara(kok)
    assert [b.yol for b in bulgular] == ["src/a.py"]
    (kok / "scripts/yasal_denetim_izin.txt").write_text("edge_tts | ** | - | too broad\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        yd.tara(kok)


def test_onbellek_klasorleri_atlanir(tmp_path: Path) -> None:
    kok = _agac(tmp_path, {
        ".ruff_cache/x": "C:" + "\\Users\\someone\\a",
        "runtime_assets/m/README.md": "import edge" + "_tts\n",
        "cikti/is/log.txt": "E:" + "\\cikti\n",
    })
    assert yd.tara(kok) == []


def test_gitignore_klasorleri_git_olmadan_da_atlanir(tmp_path: Path) -> None:
    kok = _agac(tmp_path, {
        ".gitignore": "# yerel\nyerel_onbellek/\n*.gecici\n/kokte_yalniz.txt\n!geri_alinmaz.txt\n",
        "yerel_onbellek/a.txt": "C:" + "\\Users\\someone\\a",
        "src/derin/yerel_onbellek/b.txt": "C:" + "\\Users\\someone\\b",
        "src/not.gecici": "C:" + "\\Users\\someone\\c",
        "kokte_yalniz.txt": "C:" + "\\Users\\someone\\d",
        "src/kokte_yalniz.txt": "C:" + "\\Users\\someone\\e",  # sabitli desen yalnız kökte
    })
    assert {b.yol for b in yd.tara(kok)} == {"src/kokte_yalniz.txt"}


@pytest.mark.parametrize("metin", [
    "Varsayılanlar yazar" + "ın son iki aydaki 42 işinde en çok seçilenler\n",
    "son " + "iki aydaki işlerde\n",
    "the author's last " + "two months\n",
    "chosen in 42" + " runs\n",
])
def test_kullanim_izi_sayi_kelimesi_ve_ekler(tmp_path: Path, metin: str) -> None:
    assert "kullanim_izi" in _kurallar(_agac(tmp_path, {"src/x.toml": "# " + metin}))


def test_kullanim_izi_teknik_sayi_yanlis_alarm_vermez(tmp_path: Path) -> None:
    kok = _agac(tmp_path, {"docs/x.md": "Blok başına 256 iş" + " parçacığıyla 7,9 ms; 1000 tekrar.\n"})
    assert yd.tara(kok) == []
