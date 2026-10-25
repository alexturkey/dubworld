"""Arayüz dili (arayuz_dilleri/<dil>.json): sözlükler eşit, yer tutucular aynı, sayfada çevrilmemiş yazı yok,
seçim sırası doğru, masaüstü pencere dil değişince değişiklikleri koruyarak yeniden kurulur (docs/arayuz_dili.md).

Yeni dil dosyası eklenince bu testler o dili de kendiliğinden denetler. GUI testi görünür pencere açmaz.
"""

from __future__ import annotations

import json
import re
import string
from html.parser import HTMLParser
from pathlib import Path

import pytest

from dublaj_hatti import arayuz_dili, kayit
from dublaj_hatti.is_yonetimi.asamalar import ASAMA_ADLARI
from dublaj_hatti.is_yonetimi.depo import DURUM_ADLARI
from dublaj_hatti.yapilandirma import SEMA

PAKET = Path(__file__).resolve().parents[1] / "src" / "dublaj_hatti"
STATIK = PAKET / "web_statik"
DILLER = arayuz_dili.mevcut_diller()
ORTAK_DISI = "ayar."  # ayar açıklamalarının Türkçesi varsayilan.toml'da; sözlükte yalnız toml'da olmayanlar


def _yer_tutucular(metin: str) -> set[str]:
    return {ad for _, ad, _, _ in string.Formatter().parse(metin) if ad}


@pytest.fixture(autouse=True)
def _turkce(monkeypatch):
    monkeypatch.setattr(arayuz_dili, "_secili", "tr")


def test_diller_ve_ayar_secenekleri():
    assert DILLER[:2] == ("tr", "en")
    assert SEMA["genel.arayuz_dili"] == ["auto", *DILLER]
    for kod in DILLER:
        ham = json.loads((arayuz_dili.KLASOR / f"{kod}.json").read_text(encoding="utf-8"))
        assert ham.get("_ad") and ham.get("_yon") in ("ltr", "rtl"), kod
        assert all(isinstance(v, str) and v.strip() for v in ham.values()), kod


@pytest.mark.parametrize("kod", [d for d in DILLER if d != "tr"])
def test_her_dil_turkce_ile_ayni_anahtarlar_ve_yer_tutucular(kod):
    tr, diger = arayuz_dili.sozluk("tr"), arayuz_dili.sozluk(kod)
    ortak_tr = {k for k in tr if not k.startswith(ORTAK_DISI)}
    ortak = {k for k in diger if not k.startswith(ORTAK_DISI)}
    assert sorted(ortak_tr - ortak) == [], f"{kod}: eksik"
    assert sorted(ortak - ortak_tr) == [], f"{kod}: Türkçede olmayan"
    for anahtar, metin in diger.items():
        if anahtar in tr:
            assert _yer_tutucular(metin) == _yer_tutucular(tr[anahtar]), (kod, anahtar)


def test_ingilizce_her_ayari_aciklar_turkce_de():
    from dublaj_hatti.is_yurutucu import ayar_formu

    for kod in ("tr", "en"):
        bos = [a["anahtar"] for a in ayar_formu(kod) if not a["aciklama"]]
        assert bos == [], kod
    en = arayuz_dili.sozluk("en")
    assert sorted(k for k in SEMA if f"ayar.{k}" not in en) == []


def test_asama_durum_ve_dil_adlari_tam():
    tr = arayuz_dili.sozluk("tr")
    for kod in DILLER:
        s = arayuz_dili.sozluk(kod)
        assert sorted(a for a in ASAMA_ADLARI if f"asama.{a}" not in s) == [], kod
        assert sorted(d for d in DURUM_ADLARI if f"durum.{d}" not in s) == [], kod
        assert sorted(d for d in kayit.tts_hedef_dilleri() if f"dil.{d}" not in s) == [], kod
    # Türkçe adlar hattın (CLI, Telegram) adlarıyla aynı kalır: iki kaynak ayrışmasın
    assert {a: tr[f"asama.{a}"] for a in ASAMA_ADLARI} == ASAMA_ADLARI
    assert {d: tr[f"durum.{d}"] for d in DURUM_ADLARI} == DURUM_ADLARI


def _kodda_gecen_anahtarlar() -> set[str]:
    metin = "\n".join((PAKET / ad).read_text(encoding="utf-8") for ad in ("gui.py", "gui_isler.py"))
    metin += (STATIK / "app.js").read_text(encoding="utf-8")
    anahtarlar = set(re.findall(r"""\bt\(\s*["']([a-z_]+\.[a-z0-9_.]+)["']""", metin))
    anahtarlar |= set(re.findall(r"""\byaz\([^,]+,\s*["']([a-z_]+\.[a-z0-9_.]+)["']""", metin))
    anahtarlar |= set(re.findall(r"""(isler\.sutun_[a-z]+)""", metin))
    return anahtarlar


def test_koddaki_her_anahtar_sozlukte():
    anahtarlar = _kodda_gecen_anahtarlar()
    assert len(anahtarlar) > 60
    for kod in DILLER:
        s = arayuz_dili.tam_sozluk(kod)
        assert sorted(anahtarlar - set(s)) == [], kod
    for durum in ("hazir", "calisiyor", "bitti", "hata", "durduruldu"):  # t(f"ilerleme.{durum}")
        assert f"ilerleme.{durum}" in arayuz_dili.sozluk("en")


class _Sayfa(HTMLParser):
    """index.html: her görünen yazı data-t taşıyan bir öğede ve tr.json ile aynı mı."""

    BOS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self.yigin: list[tuple[str, str | None]] = []
        self.eslesme: dict[str, list[str]] = {}
        self.cevrilmemis: list[str] = []
        self.ipuclari: list[tuple[str, str]] = []

    def handle_starttag(self, etiket, nitelikler):
        n = dict(nitelikler)
        if n.get("data-t-ipucu"):
            self.ipuclari.append((n["data-t-ipucu"], n.get("placeholder", "")))
        if etiket not in self.BOS:
            self.yigin.append((etiket, n.get("data-t")))

    def handle_endtag(self, etiket):
        while self.yigin and self.yigin.pop()[0] != etiket:
            pass

    def handle_data(self, veri):
        yazi = " ".join(veri.split())
        if not yazi or any(e in ("script", "style", "title") for e, _ in self.yigin):
            return
        anahtar = next((a for _, a in reversed(self.yigin) if a), None)
        if anahtar:
            self.eslesme.setdefault(anahtar, []).append(yazi)
        elif yazi not in ("DubWorld", "__SURUM__", "Türkçe dublajla"):  # ad, sürüm; düğmeyi app.js yazar
            self.cevrilmemis.append(yazi)


def test_web_sayfasinda_cevrilmemis_yazi_yok():
    sayfa = _Sayfa()
    sayfa.feed((STATIK / "index.html").read_text(encoding="utf-8"))
    assert sayfa.cevrilmemis == []
    tr = arayuz_dili.sozluk("tr")
    for anahtar, yazilar in sayfa.eslesme.items():
        assert anahtar in tr, anahtar
        for yazi in yazilar:  # sayfadaki yedek = tr.json
            assert yazi == " ".join(tr[anahtar].split()), anahtar
    for anahtar, ipucu in sayfa.ipuclari:
        assert ipucu == tr[anahtar]
    assert len(sayfa.eslesme) > 25


def test_secim_sirasi(monkeypatch):
    from dublaj_hatti import web

    monkeypatch.setattr(arayuz_dili, "sistem_dili", lambda: "de")
    assert arayuz_dili.cozumle("auto") == "en"  # Almanca sözlük yok → İngilizce
    assert arayuz_dili.cozumle("tr") == "tr" and arayuz_dili.cozumle("xx") == "en"
    monkeypatch.setattr(arayuz_dili, "sistem_dili", lambda: "tr")
    assert arayuz_dili.cozumle("auto") == "tr"
    # web: sayfada seçilen > ayar > tarayıcı > bilgisayar
    assert web.arayuz_dili_sec("en", "tr-TR", "tr") == "en"
    assert web.arayuz_dili_sec("", "tr-TR", "en") == "en"
    assert web.arayuz_dili_sec("", "de-DE,en-US;q=0.8", "auto") == "en"
    assert web.arayuz_dili_sec("xx", "fr", "auto") == "tr"  # tarayıcı dili yok → bilgisayarın dili


def test_metin_yedegi_ve_tam_cumle():
    assert arayuz_dili.t("yok.boyle_anahtar") == "yok.boyle_anahtar"
    assert arayuz_dili.t("dugme.dublajla", "en", hedef="German") == "Dub into German"
    assert kayit.dublajla_etiketi("de") == "Almanca dublajla"
    assert kayit.dublajla_etiketi("de", "en") == "Dub into German"
    assert arayuz_dili.dil_secenegi("ja", "en") == "Japanese (日本語)"
    assert arayuz_dili.dil_secenegi("en", "en") == "English"


def test_donanim_etiketi_arayuz_dilinde():
    from dublaj_hatti.bolum_00_omurga.runtime import donanim

    turbo = kayit.motor("crisperwhisper_turbo_ct2")
    assert donanim.motor_etiketi(turbo, "cpu", 0) == "CPU'da çalışmaz (NVIDIA GPU gerekir)"
    assert donanim.motor_etiketi(turbo, "cpu", 0, "en") == "doesn't run on CPU (needs an NVIDIA GPU)"


@pytest.fixture
def uygulama(monkeypatch):
    tk = pytest.importorskip("tkinter")
    try:
        kok = tk.Tk()
    except tk.TclError:
        pytest.skip("ekran yok (Tk açılamadı)")
    kok.withdraw()  # görünür pencere yok
    from tkinter import ttk

    from dublaj_hatti import gui, gui_isler
    from dublaj_hatti.bolum_00_omurga.runtime import donanim

    class _SahteYurutucu:
        def __init__(self, *a, **k):
            from types import SimpleNamespace

            self.durum = SimpleNamespace(durum="bos", sonuc={}, ozet=lambda: {"durum": "bos"})

        def calisiyor(self):
            return False

        def durdur(self):
            pass

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


def test_gui_dil_degisince_degisiklikler_korunur(uygulama, tmp_path):
    u = uygulama
    assert u.dublajla_dugme.cget("text") == "Türkçe dublajla"
    alan = next(a for a in u.alanlar if a.alan["anahtar"] == "genel.hedef_dil")
    alan.degisken.set(alan._gorunen("de"))
    u.video = tmp_path / "v.mp4"
    yeni = u.dili_degistir("en")
    assert arayuz_dili.secili() == "en" and yeni.yurutucu is u.yurutucu
    assert yeni.dublajla_dugme.cget("text") == "Dub into German"
    assert yeni.dil_degisken.get() == "German (Deutsch)"
    assert yeni.degisiklikler()["genel.hedef_dil"] == "de" and yeni.video == u.video
    assert str(yeni.dublajla_dugme.cget("state")) == "normal"
    aciklama = next(a for a in yeni.alanlar if a.alan["anahtar"] == "ses.motor").alan["aciklama"]
    assert aciklama.startswith("Voice engine")
