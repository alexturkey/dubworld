"""Yerel web arayüzünün güvenlik sınırları (ağsız; sunucu 127.0.0.1'de boş bir portta, tarayıcı açılmaz)."""

from __future__ import annotations

import http.client
import json
import threading

import pytest

from dublaj_hatti import web


@pytest.fixture()
def sunucu(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "cikti_koku", lambda: tmp_path)
    s = web.Sunucu(("127.0.0.1", 0), web.Isleyici)
    port = s.server_address[1]
    uygulama = web.Uygulama(port, 1)
    web.Isleyici.uygulama = uygulama
    threading.Thread(target=s.serve_forever, daemon=True).start()

    def iste(yontem, yol, govde=None, basliklar=None, host=None):
        baglanti = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        tum = {"Host": host or f"127.0.0.1:{port}"}
        tum.update(basliklar or {})
        baglanti.request(yontem, yol, govde, tum)
        yanit = baglanti.getresponse()
        return yanit.status, dict(yanit.getheaders()), yanit.read()

    cerez = {"Cookie": f"{web.CEREZ}={uygulama.belirtec}"}
    api = {**cerez, "X-Dublaj-Belirtec": uygulama.belirtec, "Content-Type": "application/json"}
    yield iste, uygulama, cerez, api, tmp_path
    s.shutdown()
    s.server_close()


def test_yabanci_host_reddedilir(sunucu):
    iste, *_ = sunucu
    assert iste("GET", "/", host="saldirgan.example")[0] == 421


def test_oturumsuz_sayfa_ve_api_kapali(sunucu):
    iste, uygulama, _, _, _ = sunucu
    assert iste("GET", "/")[0] == 403
    assert iste("GET", "/?t=yanlis")[0] == 403
    assert iste("GET", "/api/durum")[0] == 403
    durum, basliklar, _ = iste("GET", "/?t=" + uygulama.belirtec)
    assert durum == 303 and "HttpOnly" in basliklar["Set-Cookie"] and "SameSite=Strict" in basliklar["Set-Cookie"]


def test_sayfa_guvenlik_basliklari(sunucu):
    iste, _, cerez, _, _ = sunucu
    durum, basliklar, govde = iste("GET", "/", basliklar=cerez)
    assert durum == 200 and b"__BELIRTEC__" not in govde
    assert "default-src 'self'" in basliklar["Content-Security-Policy"]
    assert basliklar["X-Frame-Options"] == "DENY"


def test_post_belirtec_ve_koken_ister(sunucu):
    iste, _, cerez, api, _ = sunucu
    assert iste("POST", "/api/durdur", "{}", {**cerez, "Content-Type": "application/json"})[0] == 403
    assert iste("POST", "/api/durdur", "{}", {**api, "Origin": "http://saldirgan.example"})[0] == 403
    assert iste("POST", "/api/durdur", "{}", api)[0] == 200


def test_json_sinirlari(sunucu):
    iste, _, _, api, _ = sunucu
    assert iste("POST", "/api/baslat", "{}", {**api, "Content-Type": "text/plain"})[0] == 400
    assert iste("POST", "/api/baslat", "x" * 70000, api)[0] == 400
    assert iste("POST", "/api/baslat", json.dumps({"yuklenen": "yok"}), api)[0] == 400


def test_yukleme_uzanti_ve_yer(sunucu):
    iste, uygulama, _, api, kok = sunucu
    ikili = {**api, "Content-Type": "application/octet-stream"}
    assert iste("POST", "/api/yukle", b"abc", {**ikili, "X-Dosya-Adi": "a.exe"})[0] == 400
    durum, _, govde = iste("POST", "/api/yukle", b"x" * 100, {**ikili, "X-Dosya-Adi": "..%2F..%2Fdeneme.mp4"})
    assert durum == 200
    yol = uygulama.yuklenenler[json.loads(govde)["kimlik"]]
    assert yol.parent == kok / "_yuklemeler"


def test_dosya_sunumu_kok_disina_cikmaz(sunucu, tmp_path_factory):
    iste, _, cerez, _, kok = sunucu
    disarida = tmp_path_factory.mktemp("disari") / "gizli.txt"
    disarida.write_text("gizli", encoding="utf-8")
    assert iste("GET", "/dosya?yol=" + str(disarida), basliklar=cerez)[0] == 404
    assert iste("GET", "/dosya?yol=" + str(kok / ".." / disarida.parent.name / "gizli.txt"), basliklar=cerez)[0] == 404
    icerde = kok / "cikti.srt"
    icerde.write_text("1\n00:00:00,000 --> 00:00:01,000\nmerhaba\n", encoding="utf-8")
    durum, basliklar, govde = iste("GET", "/dosya?yol=" + str(icerde), basliklar={**cerez, "Range": "bytes=0-0"})
    assert durum == 206 and govde == b"1"


def test_gecersiz_ayar_isi_baslatmaz(sunucu):
    iste, uygulama, _, api, _ = sunucu
    ikili = {**api, "Content-Type": "application/octet-stream", "X-Dosya-Adi": "a.mp4"}
    kimlik = json.loads(iste("POST", "/api/yukle", b"x" * 10, ikili)[2])["kimlik"]
    for ayarlar in ({"video.cq": 99}, {"bilinmeyen.anahtar": 1}):
        durum, _, _ = iste("POST", "/api/baslat", json.dumps({"yuklenen": kimlik, "ayarlar": ayarlar}), api)
        assert durum == 400
    assert not uygulama.yurutucu.calisiyor()


def test_baglanti_girisi_yalniz_https_ve_yerel_yol_kabul_etmez(sunucu, monkeypatch):
    iste, _, _, api, tmp_path = sunucu
    video = tmp_path / "gizli.mp4"
    video.write_bytes(b"\0")
    for kotu in (str(video), "file:///C:/x.mp4", "http://vimeo.com/1", "https://example.com/v.mp4",
                 "https://vimeo.com/1 --exec x", "https://" + "a" * 2100):
        durum, _, govde = iste("POST", "/api/baslat", json.dumps({"baglanti": kotu}), api)
        assert durum == 400, kotu
    from dublaj_hatti import kaynak_girdisi

    monkeypatch.setattr(kaynak_girdisi.importlib.util, "find_spec", lambda ad: None)  # yt-dlp yok
    durum, _, govde = iste("POST", "/api/baslat", json.dumps({"baglanti": "https://vimeo.com/123"}), api)
    assert durum == 400 and "yt-dlp" in json.loads(govde)["hata"]
