"""İşler: web API (/api/isler, /api/sorunlu, /api/is, /api/devam, arşiv), nabız ve kurulum uçları.

Kaynak projedeki gui_management_dialogs_test karşılığı. Web sunucusu 127.0.0.1'de boş portta çalışır, tarayıcı
açılmaz. Kuyruk işleyici kapalıdır: hiçbir iş alt süreci başlatılmaz.
"""

from __future__ import annotations

import json
import threading

import pytest

from dublaj_hatti import web
from dublaj_hatti.is_yonetimi.depo import IsDeposu, varsayilan_depo_yolu
from dublaj_hatti.is_yurutucu import IsYurutucu
from test_is_yonetimi import _is_olustur


@pytest.fixture()
def sunucu(tmp_path, monkeypatch):
    monkeypatch.delenv("DUBLAJ_IS_DEPOSU", raising=False)
    monkeypatch.setattr(web, "cikti_koku", lambda: tmp_path)
    monkeypatch.setattr("dublaj_hatti.is_yurutucu.IsYurutucu.__init__.__defaults__", ("gui", None, False))
    s = web.Sunucu(("127.0.0.1", 0), web.Isleyici)
    port = s.server_address[1]
    uygulama = web.Uygulama(port, 1)
    web.Isleyici.uygulama = uygulama
    threading.Thread(target=s.serve_forever, daemon=True).start()
    import http.client

    def iste(yontem, yol, govde=None, basliklar=None):
        baglanti = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        tum = {"Host": f"127.0.0.1:{port}", **(basliklar or {})}
        baglanti.request(yontem, yol, json.dumps(govde) if govde is not None else None, tum)
        yanit = baglanti.getresponse()
        govde_bayt = yanit.read()
        try:
            return yanit.status, json.loads(govde_bayt or b"{}")
        except ValueError:
            return yanit.status, {"ham": govde_bayt.decode("utf-8", "replace")}

    api = {"Cookie": f"{web.CEREZ}={uygulama.belirtec}", "X-Dublaj-Belirtec": uygulama.belirtec,
           "Content-Type": "application/json"}
    yield iste, api, uygulama.yurutucu.depo
    s.shutdown()
    s.server_close()


def test_web_isler_api_oturum_ister(sunucu):
    iste, _, _ = sunucu
    assert iste("GET", "/api/isler")[0] == 403
    assert iste("GET", "/api/sorunlu")[0] == 403
    assert iste("POST", "/api/devam", {"is": 1}, {"Content-Type": "application/json"})[0] == 403


def test_web_sorunlu_liste_devam_ve_arsiv(sunucu):
    iste, api, depo = sunucu
    hata = _is_olustur(depo, "failed")
    bitti = _is_olustur(depo, "completed", son_sira=17)
    kod, veri = iste("GET", "/api/sorunlu", basliklar=api)
    assert kod == 200 and [o["is"] for o in veri["isler"]] == [hata]
    assert veri["isler"][0]["devam_secenekleri"][-1]["stage_id"] == "ceviri"
    kod, veri = iste("GET", f"/api/is?no={bitti}", basliklar=api)
    assert kod == 200 and veri["yeniden_calistir"][-1]["restart_stage_id"] == "final_dogrulama_ve_meta"
    kod, veri = iste("POST", "/api/devam", {"is": hata}, api)
    assert kod == 200 and veri["is"] == hata and depo.getir(hata)["status"] == "queued"
    kod, veri = iste("POST", "/api/devam", {"is": bitti, "asama": "ceviri", "yeni_is": True,
                                            "ayarlar": {"altyazi.mod": "word"}}, api)
    assert kod == 200 and depo.getir(veri["is"])["source_job_id"] == bitti
    kod, veri = iste("POST", "/api/devam", {"is": bitti, "ayarlar": {"bilinmeyen.ayar": 1}}, api)
    assert kod == 400
    kod, veri = iste("POST", "/api/devam", {"is": 999}, api)
    assert kod == 409 and "bulunamadı" in veri["hata"]
    assert iste("POST", "/api/is_arsivle", {"is": bitti}, api)[0] == 200
    kod, veri = iste("GET", "/api/isler", basliklar=api)
    assert bitti not in [o["is"] for o in veri["isler"]]
    kod, veri = iste("GET", "/api/isler?hepsi=1", basliklar=api)
    assert bitti in [o["is"] for o in veri["isler"]]


def test_web_nabiz_kurulum_ve_oynatilabilir_kaynak(sunucu, tmp_path, monkeypatch):
    iste, api, depo = sunucu
    uygulama = web.Isleyici.uygulama
    uygulama.son_nabiz = 0.0
    assert iste("GET", "/api/nabiz")[0] == 403  # oturumsuz nabız sayılmaz
    assert uygulama.son_nabiz == 0.0
    assert iste("GET", "/api/nabiz", basliklar=api)[0] == 200 and uygulama.son_nabiz > 0
    from dublaj_hatti import kayit

    monkeypatch.setattr(kayit, "durum", lambda grup: {})
    kod, veri = iste("GET", "/api/kurulum", basliklar=api)
    assert kod == 200 and "supertonic" in veri["eksik"]
    bitti = _is_olustur(depo, "completed", son_sira=17)
    kod, veri = iste("GET", "/api/isler", basliklar=api)
    satir = next(o for o in veri["isler"] if o["is"] == bitti)
    assert "srt" in satir and satir["orijinal"] == ""  # izinli kök dışındaki kaynak oynatıcıya verilmez
    yuklenen = uygulama.yukleme_klasoru / "v.mp4"
    yuklenen.parent.mkdir(parents=True, exist_ok=True)
    yuklenen.write_bytes(b"0")
    baglanti = "https://example.invalid/v.mp4"
    handler = web.Isleyici.__new__(web.Isleyici)
    assert handler._oynatilir(str(yuklenen)) == str(yuklenen)
    assert handler._oynatilir(baglanti) == "" and handler._oynatilir(str(tmp_path.parent / "x.mp4")) == ""
