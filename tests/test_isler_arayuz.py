"""İşler sekmesi: web API (/api/isler, /api/sorunlu, /api/is, /api/devam, arşiv) ve masaüstü sekmesi.

Kaynak projedeki gui_management_dialogs_test karşılığı. Web sunucusu 127.0.0.1'de boş portta çalışır, tarayıcı
açılmaz; masaüstü sekmesi görünmez Tk kökünde (withdraw + ekran dışı) kurulur, pencere ekrana gelmez.
Kuyruk işleyici kapalıdır: hiçbir iş alt süreci başlatılmaz.
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


def test_masaustu_isler_sekmesi(tmp_path, monkeypatch):
    tk = pytest.importorskip("tkinter")
    from tkinter import ttk

    from dublaj_hatti import gui_isler

    try:
        kok = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk kurulamadı (ekransız ortam)")
    kok.withdraw()
    kok.geometry("10x10+-20000+-20000")
    try:
        depo = IsDeposu(varsayilan_depo_yolu(tmp_path / "cikti"), tmp_path / "cikti")
        hata = _is_olustur(depo, "failed")
        bitti = _is_olustur(depo, "completed", son_sira=17)
        yurutucu = IsYurutucu(arayuz="gui", depo=depo, kuyruk_isle=False)
        sekme = gui_isler.IslerSekmesi(ttk.Notebook(kok), yurutucu, lambda: {"altyazi.mod": "word"})
        sekme.yenile()
        assert set(sekme.agac.get_children()) == {str(hata), str(bitti)}
        sekme.agac.selection_set(str(hata))
        sekme._secim_degisti()
        assert str(sekme.devam_dugme["state"]) == "normal"
        assert "Çeviri" in sekme.ayrinti["text"]
        sekme.devam_et()
        assert depo.getir(hata)["status"] == "queued"
        sekme.agac.selection_set(str(bitti))
        sekme._secim_degisti()
        assert str(sekme.devam_dugme["state"]) == "disabled" and str(sekme.yeniden_dugme["state"]) == "normal"
        sekme.asama.set("Çeviri")
        sekme.gelismis.set(True)
        sekme.yeniden_calistir()
        cocuk = max(int(i) for i in sekme.agac.get_children())
        assert depo.getir(cocuk)["source_job_id"] == bitti
        assert json.loads(depo.getir(cocuk)["settings_json"])["altyazi.mod"] == "word"
        sekme.agac.selection_set(str(bitti))
        monkeypatch.setattr(gui_isler.messagebox, "askyesno", lambda *a, **k: True)
        sekme.arsivle()
        assert str(bitti) not in sekme.agac.get_children()
        sekme.arsiv.set(True)
        sekme.yenile()
        assert str(bitti) in sekme.agac.get_children()
    finally:
        kok.destroy()
