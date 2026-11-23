"""scripts/modelleri_indir.py: yarim .part Range ile kaldigi yerden surer; Range reddi, 416, yanlis sha, atlama, ag kopmasinda .part korunur.
Yerel http sunucusu (ag yok, GPU yok)."""

from __future__ import annotations

import hashlib
import http.server
import re
import sys
import threading
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "scripts"))
import modelleri_indir as m  # noqa: E402

VERI = bytes((i * 7 + 3) % 251 for i in range(300_000))
SHA = hashlib.sha256(VERI).hexdigest()


class Sunucu(http.server.BaseHTTPRequestHandler):
    istekler: list = []
    range_kabul = True
    yalniz_ilk_n = None  # baglantiyi bu kadar bayttan sonra kes
    hep_416 = False  # her Range istegine 416

    def log_message(self, *a):
        pass

    def do_GET(self):
        r = self.headers.get("Range")
        Sunucu.istekler.append(r)
        parca, durum = VERI, 200
        if r and Sunucu.range_kabul:
            bas = int(re.match(r"bytes=(\d+)-", r).group(1))
            if bas >= len(VERI) or Sunucu.hep_416:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % len(VERI))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            parca, durum = VERI[bas:], 206
        self.send_response(durum)
        if durum == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (len(VERI) - len(parca), len(VERI) - 1, len(VERI)))
        self.send_header("Content-Length", str(len(parca)))
        self.end_headers()
        if Sunucu.yalniz_ilk_n is not None:
            self.wfile.write(parca[: Sunucu.yalniz_ilk_n])
            self.wfile.flush()
            self.connection.close()
            return
        self.wfile.write(parca)


@pytest.fixture()
def sunucu():
    Sunucu.istekler, Sunucu.range_kabul, Sunucu.yalniz_ilk_n, Sunucu.hep_416 = [], True, None, False
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Sunucu)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d/d.bin" % srv.server_address[1]
    srv.shutdown()
    srv.server_close()


@pytest.fixture()
def kayit_ve_kok(tmp_path, monkeypatch, sunucu):
    monkeypatch.setattr(m, "https_dogrula", lambda u: u)  # yerel sunucu http konusur; yalniz test
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    kayit = {"url": sunucu, "hedef": "runtime_assets/x/d.bin", "boyut": len(VERI), "sha256": SHA}
    return kayit, tmp_path


def _part(kok: Path) -> Path:
    return kok / "runtime_assets" / "x" / "d.bin.part"


def test_yarim_part_range_ile_surer(kayit_ve_kok):
    kayit, kok = kayit_ve_kok
    _part(kok).parent.mkdir(parents=True)
    _part(kok).write_bytes(VERI[:100_000])
    assert m.indir(kayit, kok) == "indi"
    assert (kok / kayit["hedef"]).read_bytes() == VERI
    assert Sunucu.istekler == ["bytes=100000-"]
    assert not _part(kok).exists()


def test_dogru_hedef_atlanir_ag_yok(kayit_ve_kok):
    kayit, kok = kayit_ve_kok
    hedef = kok / kayit["hedef"]
    hedef.parent.mkdir(parents=True)
    hedef.write_bytes(VERI)
    assert m.indir(kayit, kok) == "var"
    assert Sunucu.istekler == []


def test_tam_part_agsiz_dogrulanir(kayit_ve_kok):
    kayit, kok = kayit_ve_kok
    _part(kok).parent.mkdir(parents=True)
    _part(kok).write_bytes(VERI)
    assert m.indir(kayit, kok) == "indi"
    assert Sunucu.istekler == []


def test_range_reddeden_sunucuda_bastan(kayit_ve_kok):
    kayit, kok = kayit_ve_kok
    Sunucu.range_kabul = False
    _part(kok).parent.mkdir(parents=True)
    _part(kok).write_bytes(VERI[:50_000])
    assert m.indir(kayit, kok) == "indi"
    assert (kok / kayit["hedef"]).read_bytes() == VERI  # kopya degil, bozulmamis


def test_416_gelirse_part_silinip_rangesiz_bastan(kayit_ve_kok):
    kayit, kok = kayit_ve_kok
    Sunucu.hep_416 = True
    _part(kok).parent.mkdir(parents=True)
    _part(kok).write_bytes(VERI[:70_000])
    assert m.indir(kayit, kok) == "indi"
    assert (kok / kayit["hedef"]).read_bytes() == VERI
    assert Sunucu.istekler == ["bytes=70000-", None]


def test_bozuk_onekli_part_sha_ile_yakalanir(kayit_ve_kok):
    kayit, kok = kayit_ve_kok
    _part(kok).parent.mkdir(parents=True)
    _part(kok).write_bytes(b"\x01" * 10)  # sunucu 206 verir ama onek bozuk: sha256 tutmaz, hedefe konmaz
    with pytest.raises(SystemExit, match="sha256 tutmad"):
        m.indir(kayit, kok)
    assert not (kok / kayit["hedef"]).exists()
    assert not _part(kok).exists()


def test_yanlis_sha_hedefe_konmaz(kayit_ve_kok):
    kayit, kok = kayit_ve_kok
    kayit = dict(kayit, sha256="0" * 64)
    with pytest.raises(SystemExit, match="sha256 tutmad"):
        m.indir(kayit, kok)
    assert not (kok / kayit["hedef"]).exists()
    assert not _part(kok).exists()


def test_ag_kopmasinda_part_korunur_ve_sonra_surer(kayit_ve_kok):
    kayit, kok = kayit_ve_kok
    Sunucu.yalniz_ilk_n = 80_000  # sunucu eksik gonderip keser
    with pytest.raises(SystemExit, match="kaldığı yerden"):
        m.indir(kayit, kok)
    kalan = _part(kok).stat().st_size
    assert 0 < kalan < len(VERI)  # .part korundu
    Sunucu.yalniz_ilk_n = None
    Sunucu.istekler.clear()
    assert m.indir(kayit, kok) == "indi"
    assert (kok / kayit["hedef"]).read_bytes() == VERI
    assert Sunucu.istekler[0] == "bytes=%d-" % kalan


def test_boyut_asimi_part_silinir(kayit_ve_kok):
    kayit, kok = kayit_ve_kok
    kayit = dict(kayit, boyut=1000)
    with pytest.raises(SystemExit, match="boyutu aşıldı"):
        m.indir(kayit, kok)
    assert not _part(kok).exists()


def test_bozuk_buyuk_part_silinip_bastan(kayit_ve_kok):
    kayit, kok = kayit_ve_kok
    _part(kok).parent.mkdir(parents=True)
    _part(kok).write_bytes(b"z" * (len(VERI) + 10))
    assert m.indir(kayit, kok) == "indi"
    assert (kok / kayit["hedef"]).read_bytes() == VERI
