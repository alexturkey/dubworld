"""Ses kitaplığı web uçları: oturum/belirteç, yükleme sınırı, hata anahtarları, metin başlığı (GPU'suz, ağsız).

Sunucu 127.0.0.1'de boş bir portta; ffmpeg çağrısı sahte (kaynak zaten wav). Kitaplık mantığı: tests/test_ses_kitapligi.py.
"""

from __future__ import annotations

import http.client
import json
import math
import shutil
import struct
import threading
import types
import wave
from pathlib import Path
from urllib.parse import quote

import pytest

from dublaj_hatti import ses_kitapligi, web


def wav_yaz(yol: Path, sn: float, hiz: int = 24000) -> Path:
    with wave.open(str(yol), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(hiz)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * i / hiz)))
                               for i in range(int(sn * hiz))))
    return yol


@pytest.fixture()
def sunucu(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "cikti_koku", lambda: tmp_path)
    monkeypatch.setenv(ses_kitapligi.KITAPLIK_ORTAM, str(tmp_path / "kitaplik"))
    from dublaj_hatti.bolum_00_omurga.runtime import arac_yolu

    monkeypatch.setattr(arac_yolu, "arac_bul", lambda ad: "ffmpeg-sahte")

    def sahte_ffmpeg(komut, **_):
        try:
            shutil.copyfile(komut[komut.index("-i") + 1], komut[-1])
            kod = 0
        except OSError:
            kod = 1
        return types.SimpleNamespace(returncode=kod, stdout="", stderr="")

    monkeypatch.setattr(ses_kitapligi.subprocess, "run", sahte_ffmpeg)
    s = web.Sunucu(("127.0.0.1", 0), web.Isleyici)
    port = s.server_address[1]
    uygulama = web.Uygulama(port, 1)
    web.Isleyici.uygulama = uygulama
    threading.Thread(target=s.serve_forever, daemon=True).start()

    def iste(yontem, yol, govde=None, basliklar=None):
        baglanti = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        baglanti.request(yontem, yol, govde, {"Host": f"127.0.0.1:{port}", **(basliklar or {})})
        yanit = baglanti.getresponse()
        return yanit.status, yanit.read()

    cerez = {"Cookie": f"{web.CEREZ}={uygulama.belirtec}"}
    api = {**cerez, "X-Dublaj-Belirtec": uygulama.belirtec, "Content-Type": "application/json"}
    yield iste, cerez, api, tmp_path
    s.shutdown()
    s.server_close()


def ses_basliklari(api, **ek):
    taban = {"Content-Type": "application/octet-stream", "X-Dosya-Adi": "kayit.wav", "X-Ses-Adi": quote("Ayşe — kendi sesim"),
             "X-Ses-Kategori": "kadin", "X-Ses-Riza": "kendi", "X-Ses-Taklit-Yok": "1"}
    taban.update(ek)
    return {**api, **taban}


def ses_ekle(sunucu, sn=8.0, **ek):
    iste, _, api, tmp = sunucu
    govde = wav_yaz(tmp / "g.wav", sn).read_bytes()
    durum, ham = iste("POST", "/api/ses_ekle", govde, ses_basliklari(api, **ek))
    return durum, json.loads(ham)


def test_oturumsuz_ses_uclari_kapali(sunucu):
    iste, cerez, api, _ = sunucu
    assert iste("GET", "/api/sesler")[0] == 403
    assert iste("POST", "/api/ses_ekle", b"x", {"Content-Type": "application/octet-stream"})[0] == 403
    assert iste("POST", "/api/ses_sil", "{}", {**cerez, "Content-Type": "application/json"})[0] == 403  # belirteç yok
    assert iste("POST", "/api/ses_guncelle", "{}", {**api, "Origin": "http://saldirgan.example"})[0] == 403
    assert iste("GET", "/api/sesler", basliklar=cerez)[0] == 200


def test_sesler_bos_liste_sinirlar_ve_kurulum_bilgisi(sunucu):
    iste, cerez, _, _ = sunucu
    durum, ham = iste("GET", "/api/sesler", basliklar=cerez)
    veri = json.loads(ham)
    assert durum == 200 and veri["sesler"] == []
    assert veri["kategoriler"] == ["kadin", "erkek", "cocuk", "genc", "yasli", "diger"]
    assert veri["sinirlar"]["en_kisa_sn"] == 3 and veri["sinirlar"]["en_uzun_sn"] == 30
    assert veri["sinirlar"]["ad"] == 60 and veri["sinirlar"]["metin"] == 600 and ".wav" in veri["sinirlar"]["uzantilar"]
    assert set(veri["voxcpm2"]) == {"kurulu"} and set(veri["xtts"]) == {"kurulu", "lisans_onayli"}


def test_ekle_listele_guncelle_sil_dongusu(sunucu):
    iste, cerez, api, _ = sunucu
    durum, kayit = ses_ekle(sunucu, **{"X-Ses-Metin": quote("Kayıtta  söylenen\nmetin.")})
    assert durum == 200 and kayit["ad"] == "Ayşe — kendi sesim" and kayit["metin"] == "Kayıtta söylenen metin."
    liste = json.loads(iste("GET", "/api/sesler", basliklar=cerez)[1])["sesler"]
    assert [s["kimlik"] for s in liste] == [kayit["kimlik"]]
    durum, ham = iste("POST", "/api/ses_guncelle", json.dumps({"kimlik": kayit["kimlik"], "ad": "Yeni", "kategori": "genc",
                                                                "metin": ""}), api)
    g = json.loads(ham)
    assert durum == 200 and (g["ad"], g["kategori"], g["metin"]) == ("Yeni", "genc", "")
    assert iste("POST", "/api/ses_sil", json.dumps({"kimlik": kayit["kimlik"]}), api)[0] == 200
    assert json.loads(iste("GET", "/api/sesler", basliklar=cerez)[1])["sesler"] == []


def test_ses_dosyasi_oynatma_icin_sunulur(sunucu):
    iste, cerez, _, _ = sunucu
    _, kayit = ses_ekle(sunucu)
    durum, govde = iste("GET", "/dosya?yol=" + quote(kayit["yol"]), basliklar=cerez)
    assert durum == 200 and govde[:4] == b"RIFF"


@pytest.mark.parametrize("ek,anahtar", [
    ({"X-Ses-Riza": ""}, "riza_yok"),
    ({"X-Ses-Riza": "baskasi"}, "riza_yok"),
    ({"X-Ses-Taklit-Yok": "0"}, "taklit_yok"),
    ({"X-Ses-Adi": ""}, "ad_gecersiz"),
    ({"X-Ses-Adi": quote("a" * 61)}, "ad_gecersiz"),
    ({"X-Ses-Kategori": "robot"}, "kategori_gecersiz"),
    ({"X-Dosya-Adi": "kayit.exe"}, "uzanti_gecersiz"),
    ({"X-Ses-Metin": quote("a" * 601)}, "metin_uzun"),
])
def test_ekle_hata_anahtarlari(sunucu, ek, anahtar):
    durum, veri = ses_ekle(sunucu, **ek)
    assert durum == 400 and veri["anahtar"] == anahtar and veri["hata"]
    assert json.loads(sunucu[0]("GET", "/api/sesler", basliklar=sunucu[1])[1])["sesler"] == []


def test_ekle_sure_disi_hata_anahtari(sunucu):
    for sn in (1.0, 31.0):
        durum, veri = ses_ekle(sunucu, sn=sn)
        assert durum == 400 and veri["anahtar"] == "sure_disi" and "6-15 sn" in veri["hata"]


def test_yukleme_siniri(sunucu, monkeypatch):
    monkeypatch.setattr(web, "SES_YUKLEME_SINIRI", 1000)
    iste, _, api, _ = sunucu
    durum, ham = iste("POST", "/api/ses_ekle", b"x" * 2000, ses_basliklari(api))
    veri = json.loads(ham)
    assert durum == 400 and veri["anahtar"] == "dosya_boyutu" and "MB" in veri["hata"]
    durum, ham = iste("POST", "/api/ses_ekle", b"", ses_basliklari(api))
    assert durum == 400 and json.loads(ham)["anahtar"] == "dosya_boyutu"
    assert not list((sunucu[3] / "_yuklemeler").glob("ses_*")) if (sunucu[3] / "_yuklemeler").exists() else True


def test_olmayan_ses_guncelle_ve_sil(sunucu):
    iste, _, api, _ = sunucu
    for yol in ("/api/ses_guncelle", "/api/ses_sil"):
        durum, ham = iste("POST", yol, json.dumps({"kimlik": "0" * 32, "ad": "x"}), api)
        assert durum == 400 and json.loads(ham)["anahtar"] == "ses_yok"
    durum, ham = iste("POST", "/api/ses_sil", json.dumps({"kimlik": "../x"}), api)
    assert durum == 400 and json.loads(ham)["anahtar"] == "kimlik_gecersiz"


def test_xtts_lisans_acik_onay_ister(sunucu):
    iste, _, api, _ = sunucu
    durum, ham = iste("POST", "/api/xtts_lisans", json.dumps({"kabul": "evet"}), api)
    assert durum == 400 and "kabul" in json.loads(ham)["hata"]
    assert Path(sunucu[3]).exists()
