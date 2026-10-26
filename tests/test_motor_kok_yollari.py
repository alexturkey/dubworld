"""Motor kök yolları paket içinden çözülür (src/dublaj_hatti/...), ortam değişkeni geçersiz kılar.

Kök hata (K9 bulgusu): paket `src/dublaj_hatti/` altına taşınınca CrisperWhisper
Turbo sözleşme girdileri hâlâ `<repo>/src/bolum_*` gösteriyordu; ortam değişkeni verilmezse motor açılmıyordu.
"""

from __future__ import annotations

import re
from pathlib import Path

import dublaj_hatti
from dublaj_hatti.bolum_00_omurga.runtime import crisperwhisper_turbo_ct2_runtime as turbo

PAKET = Path(dublaj_hatti.__file__).resolve().parent
KOK = Path(__file__).resolve().parents[1]


def test_paket_koku_dogru():
    for modul in (turbo,):
        assert modul.PACKAGE_ROOT == PAKET
        assert modul.PROJECT_ROOT == KOK


def test_turbo_sozlesme_kaynaklari_var():
    ctc = PAKET / "bolum_30_hizalama_ve_segment" / "ctc_kelime_hizalama"
    for ad in ("worker.py", "ctc_konusma_siniri.py", "client.py"):
        assert (ctc / ad).is_file()
    assert (PAKET / "bolum_20_transkripsiyon" / "youtube_json3_kaynagi" / "engine.py").is_file()


def test_kodda_tasima_oncesi_yol_kalmadi():
    desen = re.compile(r"""["']src["']\s*/\s*["']bolum_|["']src/bolum_\d""")
    bulgular = []
    for dosya in (KOK / "src").rglob("*.py"):
        for no, satir in enumerate(dosya.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if desen.search(satir):
                bulgular.append(f"{dosya.relative_to(KOK)}:{no}")
    assert not bulgular, bulgular
