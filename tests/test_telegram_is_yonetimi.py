"""Telegram botu ↔ iş yönetimi çekirdeği (kaynak projedeki test_telegram_failed_job_resume karşılığı).

Gerçek Telegram'a bağlanılmaz, python-telegram-bot gerekmez: bot işleyicileri sahte güncelleme/sorgu nesneleriyle
çağrılır, klavye düz listeye çevrilir. Kuyruk işleyici kapalıdır (hiçbir dublaj alt süreci başlamaz).
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import is_menuleri
from dublaj_hatti.is_yonetimi.depo import IsDeposu, varsayilan_depo_yolu
from dublaj_hatti.is_yonetimi.telegram_uyarlayici import TelegramArkaUcu, ayar_ifadeleri
from dublaj_hatti.is_yurutucu import IsYurutucu
from test_is_yonetimi import _is_olustur

SAHIP = 1001  # sentetik izinli Telegram kimliği


@pytest.fixture()
def arka(tmp_path, monkeypatch):
    monkeypatch.delenv("DUBLAJ_IS_DEPOSU", raising=False)
    kok = tmp_path / "cikti"
    depo = IsDeposu(varsayilan_depo_yolu(kok), kok)
    return TelegramArkaUcu(IsYurutucu(arayuz="telegram", depo=depo, kuyruk_isle=False))


# ---- arka uç sözleşmesi --------------------------------------------------------------------------------
def test_fabrika_cekirdegi_verir_ve_bot_onu_secer(tmp_path, monkeypatch):
    from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import arka_uc
    from dublaj_hatti.is_yonetimi import telegram_arka_ucu

    monkeypatch.setenv("DUBLAJ_IS_DEPOSU", str(tmp_path / "d" / "isler.sqlite3"))
    monkeypatch.setenv("DUBLAJ_OUTPUT_DIR", str(tmp_path / "cikti"))
    secilen = arka_uc.arka_uc_sec()
    try:
        assert isinstance(secilen, TelegramArkaUcu) and callable(telegram_arka_ucu)
        assert secilen._y.arayuz == "telegram" and secilen.liste() == []
    finally:
        secilen._y.kapat()


def test_baslat_durum_liste_iptal(arka):
    is_id = arka.baslat("ornek://video-2", {"altyazi.mod": "word"})
    ozet = arka.durum(is_id)
    assert ozet["durum"] == "kuyrukta" and ozet["is_id"] == is_id and ozet["arayuz"] == "telegram"
    assert {"yuzde", "asama_adi", "hata", "ciktilar", "gecen_sn"} <= set(ozet)
    assert arka.liste(5)[0]["is_id"] == is_id
    assert arka.iptal(is_id) and arka.durum(is_id)["durum"] == "iptal"
    assert not arka.iptal(is_id)  # ikinci kez iptal edilemez
    assert arka.durum("999")["durum"] == "yok" and arka.durum("abc")["durum"] == "yok"


def test_sorunlu_is_yuzdesi_asamasi_ve_secenekleri(arka):
    hata = _is_olustur(arka.depo, "failed")
    o = arka.sorunlu()[0]
    assert o["is_id"] == str(hata) and o["durum"] == "hata"
    assert o["asama_adi"] and 0 < o["yuzde"] < 100
    s = arka.secenekler(str(hata))
    assert s["yerinde_devam"] and s["arsivlenebilir"] and not s["iptal_edilebilir"]
    assert s["yeniden"][-1]["ad"] and all(isinstance(y["sira"], int) for y in s["yeniden"])


def test_devam_yerinde_asamadan_ve_secimlerle(arka):
    hata = _is_olustur(arka.depo, "failed")
    assert arka.devam(str(hata)) == str(hata)  # kaldığı yerden, aynı iş
    assert arka.depo.getir(hata)["status"] == "queued"
    bitti = _is_olustur(arka.depo, "completed", son_sira=17)
    biten = arka.biten()
    assert biten[0]["is_id"] == str(bitti) and biten[0]["yuzde"] == 100
    ceviri = next(y["sira"] for y in arka.secenekler(str(bitti))["yeniden"] if y["ad"] == "Çeviri")
    cocuk = arka.devam(str(bitti), asama=ceviri, yeni_is=True, ayarlar={"altyazi.mod": "word"})
    kayit = arka.depo.getir(int(cocuk))
    assert kayit["source_job_id"] == bitti and json.loads(kayit["settings_json"])["altyazi.mod"] == "word"
    assert kayit["resume_after_stage"] != "final_dogrulama_ve_meta"  # çeviri öncesi korunur, sonrası yeniden


def test_arsiv_yalniz_kaydi_gizler(arka):
    bitti = _is_olustur(arka.depo, "completed", son_sira=17)
    klasor = arka.depo.getir(bitti)["run_dir"]
    assert arka.arsivle(str(bitti))
    assert str(bitti) not in [o["is_id"] for o in arka.liste()]
    from pathlib import Path

    assert Path(klasor).is_dir()


def test_ayar_ifadeleri_bicimi():
    assert ayar_ifadeleri({"ses.atempo": False, "altyazi.mod": "word"}) == ["ses.atempo=false", "altyazi.mod=word"]
    with pytest.raises(ValueError):
        ayar_ifadeleri({"altyazi.mod": "a\nb"})


# ---- saf menü ------------------------------------------------------------------------------------------
def test_menu_geri_cagirma_cozumu_ve_64_bayt():
    assert is_menuleri.coz("j:s") == ("s", None, None)
    assert is_menuleri.coz("j:v:12") == ("v", 12, None)
    assert is_menuleri.coz("j:r:12:8") == ("r", 12, 8)
    for bozuk in ("j:", "j:v", "j:v:x", "j:r:12", "j:q:1", "j:d:1:2", "b:ses", None):
        assert is_menuleri.coz(bozuk) is None
    s = {"is_id": "123456789", "durum": "hata", "yerinde_devam": True, "iptal_edilebilir": True,
         "arsivlenebilir": True, "yeniden": [{"sira": 17, "ad": "Final doğrulama ve meta"}]}
    tum = (is_menuleri.ayrinti_dugmeleri(s, True) + is_menuleri.asama_dugmeleri(s, True)
           + is_menuleri.arsiv_onay_dugmeleri("123456789"))
    assert all(len(v.encode()) <= 64 for _, v in tum)
    assert all(is_menuleri.coz(v) for _, v in tum if v.startswith("j:"))


def test_ayrinti_dugmeleri_duruma_gore():
    biten = {"is_id": "3", "durum": "bitti", "yerinde_devam": False, "yeniden": [{"sira": 9, "ad": "Çeviri"}],
             "iptal_edilebilir": False, "arsivlenebilir": True}
    veriler = [v for _, v in is_menuleri.ayrinti_dugmeleri(biten, secim_var=False)]
    assert "j:d:3" not in veriler and "j:a:3" in veriler and "j:z:3" in veriler and "j:x:3" not in veriler
    assert not any(v.startswith("j:R") for _, v in is_menuleri.asama_dugmeleri(biten, secim_var=False))
    assert any(v == "j:R:3:9" for _, v in is_menuleri.asama_dugmeleri(biten, secim_var=True))


# ---- bot, sahte Telegram istemcisiyle ------------------------------------------------------------------
class _Mesaj:
    def __init__(self, gunluk):
        self.gunluk = gunluk

    async def reply_text(self, metin, reply_markup=None):
        self.gunluk.append(("yanit", metin, reply_markup))
        return _Mesaj(self.gunluk)

    async def edit_text(self, metin, reply_markup=None):
        self.gunluk.append(("duzenle", metin, reply_markup))


class _Sorgu:
    def __init__(self, veri, gunluk):
        self.data, self.gunluk, self.message = veri, gunluk, _Mesaj(gunluk)

    async def answer(self):
        pass

    async def edit_message_text(self, metin, reply_markup=None):
        self.gunluk.append(("duzenle", metin, reply_markup))


class _Uygulama:
    def __init__(self):
        self.gorevler = []

    def create_task(self, coro):
        self.gorevler.append(coro)
        coro.close()  # izleme döngüsü testte çalıştırılmaz


@pytest.fixture()
def bot(arka, tmp_path, monkeypatch):
    from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import bot as bot_mod

    b = bot_mod.DublajBotu(frozenset({SAHIP}), arka_uc=arka, girdi_klasoru=tmp_path / "girdi")
    monkeypatch.setattr(b, "_klavye", lambda dugmeler: list(dugmeler))  # telegram kütüphanesi gerekmez
    gunluk: list = []
    ctx = SimpleNamespace(args=[], application=_Uygulama(), bot=None)

    def komut(ad, kisi=SAHIP):
        guncelleme = SimpleNamespace(effective_user=SimpleNamespace(id=kisi), effective_chat=SimpleNamespace(id=kisi),
                                     message=_Mesaj(gunluk))
        asyncio.run(getattr(b, ad)(guncelleme, ctx))

    def bas(veri, kisi=SAHIP):
        guncelleme = SimpleNamespace(effective_user=SimpleNamespace(id=kisi), effective_chat=SimpleNamespace(id=kisi),
                                     callback_query=_Sorgu(veri, gunluk))
        asyncio.run(b.dugme(guncelleme, ctx))

    return SimpleNamespace(b=b, gunluk=gunluk, ctx=ctx, komut=komut, bas=bas, depo=arka.depo)


def _dugmeler(kayit):
    return [v for _, v in (kayit[2] or [])]


def test_bot_sorunlu_menusu_kaldigi_yerden_devam(bot):
    hata = _is_olustur(bot.depo, "failed")
    bot.komut("sorunlu")
    _, metin, klavye = bot.gunluk[-1]
    assert f"#{hata}" in metin and f"j:v:{hata}" in _dugmeler(bot.gunluk[-1])
    bot.bas(f"j:v:{hata}")
    assert "Kesildiği aşama" in bot.gunluk[-1][1] and f"j:d:{hata}" in _dugmeler(bot.gunluk[-1])
    bot.bas(f"j:d:{hata}")
    assert any("sıraya alındı" in g[1] for g in bot.gunluk[-2:])
    assert bot.depo.getir(hata)["status"] == "queued" and len(bot.ctx.application.gorevler) == 1


def test_bot_biten_isi_asamadan_secimlerle_yeniden_calistirir_ve_arsivler(bot):
    bitti = _is_olustur(bot.depo, "completed", son_sira=17)
    bot.b.secimler[SAHIP] = {"altyazi.mod": "word"}
    bot.komut("biten")
    bot.bas(f"j:a:{bitti}")
    secim_dugmeleri = [v for v in _dugmeler(bot.gunluk[-1]) if v.startswith(f"j:R:{bitti}:")]
    assert secim_dugmeleri
    bot.bas(secim_dugmeleri[-1])
    cocuk = max(i["job_id"] for i in bot.depo.listele())
    kayit = bot.depo.getir(cocuk)
    assert kayit["source_job_id"] == bitti and json.loads(kayit["settings_json"])["altyazi.mod"] == "word"
    bot.bas(f"j:z:{bitti}")
    assert f"j:Z:{bitti}" in _dugmeler(bot.gunluk[-1])
    bot.bas(f"j:Z:{bitti}")
    assert "arşivlendi" in bot.gunluk[-1][1] and bot.depo.getir(bitti)["archived"]


def test_bot_iptal_ve_hatali_istek(bot):
    is_id = bot.b.arka_uc.baslat("ornek://video-3", {})
    bot.bas(f"j:x:{is_id}")
    assert "iptal edildi" in bot.gunluk[-1][1]
    bot.bas("j:d:999")
    assert bot.gunluk[-1][1].startswith("Olmadı")
    bot.bas("j:bozuk")
    assert bot.gunluk[-1][1] == "Menü kapandı."


def test_bot_izinsiz_kisiye_hicbir_sey_gostermez(bot):
    _is_olustur(bot.depo, "failed")
    bot.komut("sorunlu", kisi=42)
    bot.bas("j:s", kisi=42)
    assert bot.gunluk == [] and bot.b.izinsiz_istek == 2
