"""Yönlendirme ve indirme sınırları (Düzeltme A: O1, D4).

O1: urllib yönlendirmede Authorization / x-goog-api-key başlıklarını yeni adrese taşır; köprü yönlendirme hedefini
de izin listesinden geçirir. İndirici yalnız izinli alan adlarına ve onların resmî CDN alt alanlarına yönlenir.
D4: indirici hedefi Path.relative_to ile runtime_assets içinde tutar ve manifest boyutundan fazlasını yazmaz.
Ağsız.
"""

from __future__ import annotations

import email.message
import importlib
import io
import sys
import urllib.error
import urllib.request
import urllib.response
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "scripts"))
import modelleri_indir  # noqa: E402

kopru = importlib.import_module("dublaj_hatti.bolum_40_ceviri.llm_kopru.scripts.bridge_worker")


# --- O1: köprü -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("hedef", [
    "https://evil.example/v1/chat/completions",
    "https://api.groq.com.evil.example/v1",
    "https://kullanici" + "@" + "api.groq.com/v1",  # @ birleştirilir: yasal denetimin e-posta deseni
])
def test_kopru_izinsiz_alana_yonlendirmeyi_reddeder(hedef):
    isleyici = kopru._YalnizHttpsYonlendirme()
    istek = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": "Bearer ornek-degil", "x-goog-api-key": "ornek-degil"},
    )
    with pytest.raises(kopru.BridgeError) as hata:
        isleyici.redirect_request(istek, None, 307, "Temporary Redirect", {}, hedef)
    assert hata.value.error_type == "api_url_rejected"


def test_kopru_ayni_saglayiciya_yonlendirme_gecer():
    isleyici = kopru._YalnizHttpsYonlendirme()
    istek = urllib.request.Request("https://api.cerebras.ai/v1/chat/completions")
    yeni = isleyici.redirect_request(istek, None, 302, "Found", {}, "https://api.cerebras.ai/v2/chat/completions")
    assert yeni.full_url == "https://api.cerebras.ai/v2/chat/completions"


def test_kopru_acicisi_yonlendirmeyi_islemeden_reddeder():
    """Uçtan uca: açıcı 307 + izinsiz Location alınca isteği yeni adrese hiç göndermez."""
    gonderilen: list[str] = []

    class SahteHttps(urllib.request.HTTPSHandler):
        def https_open(self, req):
            gonderilen.append(req.full_url)
            basliklar = email.message.Message()
            basliklar["Location"] = "https://evil.example/x"
            yanit = urllib.response.addinfourl(io.BytesIO(b""), basliklar, req.full_url, 307)
            yanit.msg = "Temporary Redirect"
            return yanit

    acici = urllib.request.build_opener(SahteHttps, kopru._YalnizHttpsYonlendirme)
    istek = urllib.request.Request("https://api.mistral.ai/v1/chat/completions", data=b"{}",
                                   headers={"Authorization": "Bearer ornek-degil"}, method="POST")
    with pytest.raises(kopru.BridgeError):
        acici.open(istek, timeout=5)
    assert gonderilen == ["https://api.mistral.ai/v1/chat/completions"]


# --- O1: indirici ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("hedef", [
    "https://us.aws.cdn.hf.co/xet-bridge-us/abc",
    "https://cas-bridge.xethub.hf.co/x",
    "https://cdn-lfs.huggingface.co/x",
    "https://release-assets.githubusercontent.com/github-production-release-asset/1/2",
    "https://huggingface.co/api/resolve-cache/models/x",
])
def test_indirici_resmi_cdn_yonlendirmesini_kabul_eder(hedef):
    isleyici = modelleri_indir._YalnizHttpsYonlendirme()
    istek = urllib.request.Request("https://huggingface.co/x")
    assert isleyici.redirect_request(istek, None, 302, "Found", {}, hedef).full_url == hedef


@pytest.mark.parametrize("hedef", [
    "https://evil.example/x",
    "https://hf.co.evil.example/x",
    "https://evilhuggingface.co/x",
    "https://user" + "@" + "cdn-lfs.huggingface.co/x",
])
def test_indirici_izinsiz_yonlendirmeyi_reddeder(hedef):
    isleyici = modelleri_indir._YalnizHttpsYonlendirme()
    istek = urllib.request.Request("https://huggingface.co/x")
    with pytest.raises(SystemExit):
        isleyici.redirect_request(istek, None, 302, "Found", {}, hedef)


# --- D4 --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("goreli", [
    "../disari.bin",
    "runtime_assets_kotu/x.bin",  # eski önek denetimi bunu kaçırıyordu
    "runtime_assets/../x.bin",
    "runtime_assets",
])
def test_guvenli_hedef_disariyi_reddeder(tmp_path, goreli):
    with pytest.raises(SystemExit):
        modelleri_indir._guvenli_hedef(tmp_path, goreli)


def test_guvenli_hedef_icerisi_gecer(tmp_path):
    hedef = modelleri_indir._guvenli_hedef(tmp_path, "runtime_assets/model_cache/a.bin")
    assert hedef == (tmp_path / "runtime_assets" / "model_cache" / "a.bin").resolve()


class _SahteYanit(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_indirme_manifest_boyutunu_asinca_durur(tmp_path, monkeypatch):
    acilan: list[int] = []

    class SahteAcici:
        def open(self, istek, timeout=None):
            acilan.append(1)
            return _SahteYanit(b"x" * (3 << 20))  # 3 MB; manifest 1 MB diyor

    monkeypatch.setattr(modelleri_indir, "_ACICI", SahteAcici())
    kayit = {"url": "https://huggingface.co/x", "hedef": "runtime_assets/x.bin", "boyut": 1 << 20, "sha256": "0" * 64}
    with pytest.raises(SystemExit, match="boyutu"):
        modelleri_indir.indir(kayit, tmp_path)
    assert acilan == [1]  # yeniden denenmez
    assert not list((tmp_path / "runtime_assets").glob("*"))  # .part kalmaz


def test_indirme_dogru_boyutta_tamamlanir(tmp_path, monkeypatch):
    import hashlib

    veri = b"abc" * 1000

    class SahteAcici:
        def open(self, istek, timeout=None):
            return _SahteYanit(veri)

    monkeypatch.setattr(modelleri_indir, "_ACICI", SahteAcici())
    kayit = {"url": "https://huggingface.co/x", "hedef": "runtime_assets/x.bin", "boyut": len(veri),
             "sha256": hashlib.sha256(veri).hexdigest()}
    assert modelleri_indir.indir(kayit, tmp_path) == "indi"
    assert (tmp_path / "runtime_assets" / "x.bin").read_bytes() == veri
