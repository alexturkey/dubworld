"""Ticari olmayan / şartlı motorların ilk kullanım onayı: modül, CLI ve web kapısı (ağsız, GPU'suz)."""

from __future__ import annotations

import json

import pytest

from dublaj_hatti import kayit, lisans_onayi


@pytest.fixture(autouse=True)
def onay_dosyasi(tmp_path, monkeypatch):
    yol = tmp_path / "ayarlar" / "lisans_onaylari.json"
    monkeypatch.setenv(lisans_onayi.ONAY_DOSYASI_ORTAM, str(yol))
    monkeypatch.delenv(lisans_onayi.ONAY_ORTAM, raising=False)
    return yol


def _ayar(**ust):
    ayar = {"genel.is_turu": "dublaj", "transkripsiyon.motor": "faster-whisper", "ses.motor": "voxcpm2"}
    ayar.update(ust)
    return ayar


def test_izinli_motorlar_onay_istemez():
    assert lisans_onayi.kapi(_ayar()) == []


def test_sartli_ve_ticari_olmayan_motor_onay_ister(onay_dosyasi):
    ayar = _ayar(**{"ses.motor": "supertonic", "transkripsiyon.motor": "crisperwhisper_turbo_ct2"})
    with pytest.raises(lisans_onayi.LisansOnayiGerekli) as hata:
        lisans_onayi.kapi(ayar)
    adlar = [ad for ad, _ in hata.value.bekleyen]
    assert adlar == ["crisperwhisper_turbo_ct2", "supertonic"]
    for _, metin in hata.value.bekleyen:  # iki dilli
        assert "THIRD_PARTY.md" in metin and "\n" in metin
    assert not onay_dosyasi.exists()


def test_onay_hatirlanir_ve_kisisel_bilgi_tutmaz(onay_dosyasi):
    ayar = _ayar(**{"ses.motor": "supertonic"})
    assert lisans_onayi.kapi(ayar, onay=True) == ["supertonic"]
    assert lisans_onayi.kapi(ayar) == []  # ikinci kez sorulmaz
    veri = json.loads(onay_dosyasi.read_text(encoding="utf-8"))
    assert set(veri) == {"supertonic"} and set(veri["supertonic"]) == {"lisans", "tarih_utc"}


def test_lisans_degisirse_yeniden_sorulur(onay_dosyasi):
    lisans_onayi.onayla(["supertonic"])
    veri = json.loads(onay_dosyasi.read_text(encoding="utf-8"))
    veri["supertonic"]["lisans"] = "eski lisans"
    onay_dosyasi.write_text(json.dumps(veri), encoding="utf-8")
    assert not lisans_onayi.onayli("supertonic")


def test_ortam_degiskeni_acik_kabuldur(monkeypatch):
    monkeypatch.setenv(lisans_onayi.ONAY_ORTAM, "1")
    assert lisans_onayi.kapi(_ayar(**{"ses.motor": "supertonic"})) == ["supertonic"]


def test_kendi_onayi_olan_ve_transkript_isi():
    assert lisans_onayi.secili_motorlar(_ayar(**{"genel.is_turu": "transkript", "ses.motor": "supertonic"})) == [
        "faster-whisper"]
    assert lisans_onayi.onay_gereken("xtts") is None and lisans_onayi.onay_gereken("rvc") is None
    assert kayit.lisans_uyarisi("xtts")  # metin kayıtta var, onayı kendi akışında


def test_auto_kurulu_crisper_turbo_temkinle_sayilir(monkeypatch):
    turbo = kayit.motor("crisperwhisper_turbo_ct2")
    monkeypatch.setattr(kayit, "motor", lambda ad: type("M", (), {"ad": ad, "kurulu": lambda self=None: True})()
                        if ad == turbo.ad else turbo)
    assert lisans_onayi.secili_motorlar(_ayar(**{"transkripsiyon.motor": "auto"}))[0] == turbo.ad


def test_cli_onaysiz_durur_onayla_gecer(monkeypatch, capsys, onay_dosyasi):
    from dublaj_hatti import cli

    ayar = _ayar(**{"ses.motor": "supertonic"})
    assert cli._lisans_kapisi(ayar, "faster-whisper", onay=False, etkilesimli=False) == 2
    hata = capsys.readouterr().err
    assert "NON-COMMERCIAL" in hata or "use conditions" in hata
    assert "--lisans-onay" in hata
    monkeypatch.setattr("builtins.input", lambda _: "hayır")
    assert cli._lisans_kapisi(ayar, "faster-whisper", onay=False, etkilesimli=True) == 2
    monkeypatch.setattr("builtins.input", lambda _: "evet")
    assert cli._lisans_kapisi(ayar, "faster-whisper", onay=False, etkilesimli=True) == 0
    assert cli._lisans_kapisi(ayar, "faster-whisper", onay=False, etkilesimli=False) == 0  # hatırlandı


def test_cli_secenegi_dubla_ve_transkriptte():
    from dublaj_hatti import cli

    assert cli._argumanlari_coz(["video.mp4", "--lisans-onay"]).lisans_onay is True
    assert cli._argumanlari_coz(["transkript", "video.mp4"]).lisans_onay is False


def test_web_onaysiz_409_onayla_baslar(tmp_path, monkeypatch):
    import http.client
    import threading

    from dublaj_hatti import web

    monkeypatch.setattr(web, "cikti_koku", lambda: tmp_path)
    s = web.Sunucu(("127.0.0.1", 0), web.Isleyici)
    port = s.server_address[1]
    uygulama = web.Uygulama(port, 1)
    web.Isleyici.uygulama = uygulama
    baslatilan = []
    monkeypatch.setattr(uygulama.yurutucu, "baslat", lambda *a, **k: baslatilan.append(a) or 1)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    api = {"Cookie": f"{web.CEREZ}={uygulama.belirtec}", "X-Dublaj-Belirtec": uygulama.belirtec,
           "Content-Type": "application/json", "Host": f"127.0.0.1:{port}"}

    def iste(yontem, yol, govde, basliklar):
        b = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        b.request(yontem, yol, govde, basliklar)
        y = b.getresponse()
        return y.status, y.read()

    try:
        ikili = {**api, "Content-Type": "application/octet-stream", "X-Dosya-Adi": "a.mp4"}
        kimlik = json.loads(iste("POST", "/api/yukle", b"x" * 10, ikili)[1])["kimlik"]
        govde = {"yuklenen": kimlik, "ayarlar": {"ses.motor": "supertonic", "transkripsiyon.motor": "faster-whisper"}}
        durum, yanit = iste("POST", "/api/baslat", json.dumps(govde), api)
        assert durum == 409 and json.loads(yanit)["lisans_onayi"][0]["ad"] == "supertonic"
        assert baslatilan == []
        durum, _ = iste("POST", "/api/baslat", json.dumps({**govde, "lisans_onay": True}), api)
        assert durum == 200 and len(baslatilan) == 1
        durum, _ = iste("POST", "/api/baslat", json.dumps(govde), api)  # onay hatırlandı
        assert durum == 200 and len(baslatilan) == 2
    finally:
        s.shutdown()
        s.server_close()
