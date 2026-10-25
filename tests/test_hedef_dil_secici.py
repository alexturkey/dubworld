"""Önerilen sekmesinde hedef dil seçicisi: dil adı arayüz dilinde (yanında dilin kendi adı), düğme tam cümle
("Almanca dublajla", "Dub into German"), Gelişmiş ile tek ayar.

GUI testi görünür pencere açmaz (Tk kökü hemen gizlenir, mainloop yok); ekran yoksa atlanır.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dublaj_hatti import kayit

STATIK = Path(__file__).resolve().parents[1] / "src" / "dublaj_hatti" / "web_statik"


def test_her_hedef_dilin_kendi_adi_var():
    eksik = [kod for kod in kayit.tts_hedef_dilleri() if kod not in kayit.DIL_KENDI_ADLARI]
    assert eksik == []
    assert kayit.dil_kendi_adi("de") == "Deutsch" and kayit.dil_kendi_adi("ja") == "日本語"
    assert kayit.dublajla_etiketi("tr") == "Türkçe dublajla"
    assert kayit.dublajla_etiketi("fr") == "Fransızca dublajla"
    assert kayit.dil_kendi_adi("xx") == "xx"


def test_form_dil_adlarini_tasir(monkeypatch):
    from dublaj_hatti.bolum_00_omurga.runtime import donanim
    from dublaj_hatti.yapilandirma import form_ek_bilgisi

    monkeypatch.setattr(donanim, "gpu_bilgisi_hafif", lambda: (False, 0))
    ek = form_ek_bilgisi()["genel.hedef_dil"]
    assert ek["dil_adlari"]["tr"] == "Türkçe" and set(ek["dil_adlari"]) == set(kayit.tts_hedef_dilleri())
    assert ek["suzgec"]["anahtar"] == "ses.motor"


def test_web_onerilen_sekmesinde_dil_secici():
    html = (STATIK / "index.html").read_text(encoding="utf-8")
    js = (STATIK / "app.js").read_text(encoding="utf-8")
    onerilen = html.split('id="onerilen"', 1)[1].split("</section>", 1)[0]
    assert 'id="hedef-dil"' in onerilen and onerilen.index('id="hedef-dil"') < onerilen.index('id="dublajla"')
    # tek kaynak: Önerilen seçici Gelişmiş alanını (a_genel.hedef_dil) değiştirip onun change olayını tetikler
    assert 'const DIL_ANAHTARI = "genel.hedef_dil"' in js
    assert 'kaynak.dispatchEvent(new Event("change"))' in js
    assert '"dugme.dublajla"' in js and "dil_adlari" in js


class _SahteYurutucu:
    def __init__(self, *a, **k):
        from types import SimpleNamespace

        self.durum = SimpleNamespace(durum="bos", sonuc={}, ozet=lambda: {"durum": "bos"})
        self.baslatilan = []

    def calisiyor(self):
        return False

    def baslat(self, kaynak, ayarlar, komut="dubla", bicim=None):
        self.baslatilan.append((kaynak, dict(ayarlar), komut))
        return 1

    def durdur(self):
        pass

    def kapat(self):
        pass


@pytest.fixture
def uygulama(monkeypatch):
    from dublaj_hatti import arayuz_dili

    monkeypatch.setattr(arayuz_dili, "_secili", "tr")
    tk = pytest.importorskip("tkinter")
    try:
        kok = tk.Tk()
    except tk.TclError:
        pytest.skip("ekran yok (Tk açılamadı)")
    kok.withdraw()  # görünür pencere yok
    from tkinter import ttk

    from dublaj_hatti import gui, gui_isler
    from dublaj_hatti.bolum_00_omurga.runtime import donanim

    class SahteIsler:
        def __init__(self, ust, *a, **k):
            self.cerceve = ttk.Frame(ust)

        def yenile(self):
            pass

    monkeypatch.setattr(donanim, "gpu_bilgisi_hafif", lambda: (False, 0))
    monkeypatch.setattr(gui, "IsYurutucu", _SahteYurutucu)
    monkeypatch.setattr(gui_isler, "IslerSekmesi", SahteIsler)
    monkeypatch.setattr(gui, "kurulum_eksikleri", lambda: [])
    u = gui.Uygulama(kok)
    yield u
    kok.destroy()


def _alan(u, anahtar):
    return next(a for a in u.alanlar if a.alan["anahtar"] == anahtar)


def test_gui_onerilen_dil_secici_gelismis_ile_tek_ayar(uygulama):
    u = uygulama
    dil = _alan(u, "genel.hedef_dil")
    assert u.dil_degisken.get() == "Türkçe" and u.dublajla_dugme.cget("text") == "Türkçe dublajla"
    assert "Almanca (Deutsch)" in u.dil_kutu.cget("values")
    # Önerilen'de seç → Gelişmiş alanı değişir, düğme yeniden adlanır, iş bu ayarla başlar
    u.dil_degisken.set("Almanca (Deutsch)")
    u._onerilen_dil_secildi()
    assert dil.deger() == "de" and u.dublajla_dugme.cget("text") == "Almanca dublajla"
    assert u.degisiklikler()["genel.hedef_dil"] == "de"
    # Gelişmiş'te değiştir → Önerilen eşitlenir
    dil.degisken.set(dil._gorunen("fr"))
    assert u.dil_degisken.get() == "Fransızca (Français)" and u.dublajla_dugme.cget("text") == "Fransızca dublajla"
    # Varsayılana dön → Türkçe
    u.sifirla()
    assert u.dil_degisken.get() == "Türkçe" and "genel.hedef_dil" not in u.degisiklikler()


def test_gui_dil_listesi_ses_motoruna_gore_suzulur(uygulama):
    u = uygulama
    motor = _alan(u, "ses.motor")
    motor.degisken.set(motor._gorunen("xtts"))
    degerler = list(u.dil_kutu.cget("values"))
    assert "Fince (Suomi)" not in degerler and "İtalyanca (Italiano)" in degerler  # fi Supertonic'te var, XTTS'te yok
    motor.degisken.set(motor._gorunen("voxcpm2"))
    degerler = list(u.dil_kutu.cget("values"))
    assert "Türkçe" in degerler and any("denenmedi" in d for d in degerler)


def test_gui_baslat_secilen_dille_gider(uygulama, tmp_path, monkeypatch):
    from dublaj_hatti import gui

    u = uygulama
    monkeypatch.setattr(u, "_lisans_onayi", lambda ayarlar: True)
    u.video = tmp_path / "v.mp4"
    u.dil_degisken.set("İspanyolca (Español)")
    u._onerilen_dil_secildi()
    u.baslat("dublaj")
    assert isinstance(u.yurutucu, gui.IsYurutucu)
    assert u.yurutucu.baslatilan[-1][1]["genel.hedef_dil"] == "es"
