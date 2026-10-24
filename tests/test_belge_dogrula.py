"""scripts/belge_dogrula.py: negatif kontrol (her bulgu türünü yakalar), pozitif kontrol ve repo belgelerinin tamamı temiz."""

from __future__ import annotations

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "scripts"))
import belge_dogrula  # noqa: E402

YANLIS = """# deneme
[kırık](yok/olmayan.md)
[çapa](#olmayan-baslik)
`docs/olmayan_sayfa.md`
`dubla uydurmakomut`
`dubla video.mp4 --uydurma-bayrak`
`ses.uydurma_ayar`
`scripts/kur.ps1 -Adim uydurma-adim`
`python -m dublaj_hatti.uydurma_modul`
`DUBLAJ_UYDURMA_DEGISKEN`
"""

DOGRU = """# deneme
[fihrist](README.md) [başa](#deneme) [ikinci](#ikinci-başlık-2)
## İkinci başlık 2
`docs/README.md` `scripts/kur.ps1 -Adim parakeet`
`dubla video.mp4 --ayar ses.motor=supertonic`
`dubla kontrol`
`python -m dublaj_hatti.cli`
`DUBLAJ_OUTPUT_DIR` `CODEX_BRIDGE_GEMINI_API_KEY`
[repo](__REPO_URL__)
"""


def _calistir(tmp_path: Path, metin: str) -> belge_dogrula.Dogrulayici:
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    dosya = tmp_path / "deneme.md"
    dosya.write_text(metin, encoding="utf-8")
    dogrulayici = belge_dogrula.Dogrulayici(KOK)
    for d in [dosya]:
        dogrulayici.dosya_denetle(d)
    return dogrulayici


def test_negatif_kontrol_her_turu_yakalar(tmp_path):
    bulgular = _calistir(tmp_path, YANLIS).bulgular
    beklenen = ("kırık bağlantı", "kırık çapa", "yol yok", "bilinmeyen dubla alt komutu", "bayrak yok", "ayar anahtarı yok",
                "kur.ps1 adımı yok", "modül yok", "ortam değişkeni kaynakta yok")
    for tur in beklenen:
        assert any(tur in b for b in bulgular), (tur, bulgular)
    assert len(bulgular) == len(beklenen), bulgular


def test_pozitif_kontrol_temiz(tmp_path):
    assert _calistir(tmp_path, DOGRU).bulgular == []


def test_repo_belgeleri_temiz(capsys):
    assert belge_dogrula.main([]) == 0, capsys.readouterr().out
