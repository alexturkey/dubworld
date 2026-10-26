"""Telegram ayar menüsü: video.cq / video.max_mb hazır düğmeler + özel değer, transkripsiyon.model motora göre
(Düzeltme A, madde 15; kaynak uygulamanın final video menüsüyle aynı hazır değerler). Telegram kütüphanesi gerekmez."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import menuler
from dublaj_hatti.is_yurutucu import ARAYUZ_DISI_AYARLAR, ayar_formu

SAHIP = 1001


@pytest.fixture(scope="module")
def ogeler():
    return menuler.menu_ogeleri(ayar_formu())


def _oge(ogeler, anahtar):
    return next(o for o in ogeler if o["anahtar"] == anahtar)


def test_menude_yeni_ayarlar_var_program_yolu_yok(ogeler):
    adlar = {o["anahtar"] for o in ogeler}
    assert {"video.cq", "video.max_mb", "transkripsiyon.model"} <= adlar
    assert not adlar & ARAYUZ_DISI_AYARLAR
    assert all(len(v.encode()) <= 64 for o in ogeler for _, v in menuler.deger_dugmeleri(ogeler, o))


def test_cq_ve_boyut_hazir_dugmeleri(ogeler):
    cq = _oge(ogeler, "video.cq")
    assert menuler.secenekler(cq) == [23, 26, 30, 40]
    dugmeler = menuler.deger_dugmeleri(ogeler, cq)
    assert dugmeler[-1][1] == f"o:{ogeler.index(cq)}" and "1-51" in dugmeler[-1][0]
    mb = _oge(ogeler, "video.max_mb")
    assert menuler.secenekler(mb) == [100, 179, 500, 1000]
    assert any("179 MB (WhatsApp)" == m for m, _ in menuler.deger_dugmeleri(ogeler, mb))
    assert "1-2000" in menuler.deger_dugmeleri(ogeler, mb)[-1][0]


@pytest.mark.parametrize("anahtar,metin,beklenen", [
    ("video.cq", "26", 26), ("video.cq", " 1 ", 1), ("video.cq", "51", 51),
    ("video.max_mb", "347", 347), ("video.max_mb", "2000 MB", 2000),
])
def test_ozel_deger_gecerli(ogeler, anahtar, metin, beklenen):
    assert menuler.ozel_deger_coz(_oge(ogeler, anahtar), metin) == beklenen


@pytest.mark.parametrize("anahtar,metin", [
    ("video.cq", "0"), ("video.cq", "52"), ("video.cq", "26.5"), ("video.cq", "-3"), ("video.cq", "yirmi"),
    ("video.max_mb", "0"), ("video.max_mb", "2001"), ("video.max_mb", ""),
])
def test_ozel_deger_aralik_disi(ogeler, anahtar, metin):
    with pytest.raises(ValueError):
        menuler.ozel_deger_coz(_oge(ogeler, anahtar), metin)


def test_model_secimi_motora_gore(ogeler):
    model = _oge(ogeler, "transkripsiyon.model")
    assert menuler.secenekler(model) == ["large-v3-turbo", "distil-large-v3", "distil-large-v3.5"]
    bolum = model["bolum"]

    def gorunen(secim):
        return any(v == f"a:{ogeler.index(model)}" for _, v in menuler.anahtar_dugmeleri(ogeler, bolum, secim))

    for motor in ("auto", "faster-whisper", "faster_whisper_ctc", "whisperx"):
        assert gorunen({"transkripsiyon.motor": motor}), motor
    for motor in ("crisperwhisper_turbo_ct2", "parakeet_cpu_align"):
        assert not gorunen({"transkripsiyon.motor": motor}), motor


def test_geri_cagirma_ozel(ogeler):
    cq = _oge(ogeler, "video.cq")
    assert menuler.geri_cagirma_coz(f"o:{ogeler.index(cq)}", ogeler) == ("ozel", cq)
    ses = _oge(ogeler, "ses.motor")
    assert menuler.geri_cagirma_coz(f"o:{ogeler.index(ses)}", ogeler)[0] == "kapat"  # özel değeri olmayan öğe


# ---- bot akışı (sahte güncelleme) ----------------------------------------------------------------------
class _Mesaj:
    def __init__(self, gunluk, metin=""):
        self.gunluk, self.text = gunluk, metin

    async def reply_text(self, metin, reply_markup=None):
        self.gunluk.append(("yanit", metin, reply_markup))


class _Sorgu:
    def __init__(self, veri, gunluk):
        self.data, self.gunluk = veri, gunluk

    async def answer(self):
        pass

    async def edit_message_text(self, metin, reply_markup=None):
        self.gunluk.append(("duzenle", metin, reply_markup))


@pytest.fixture()
def bot(tmp_path, monkeypatch):
    from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import bot as bot_mod

    baslatilan: list = []
    arka = SimpleNamespace(baslat=lambda kaynak, secim: baslatilan.append((kaynak, secim)) or "1")
    b = bot_mod.DublajBotu(frozenset({SAHIP}), arka_uc=arka, girdi_klasoru=tmp_path / "girdi", yerel_adres="")
    monkeypatch.setattr(b, "_klavye", lambda dugmeler: list(dugmeler))
    gunluk: list = []
    ctx = SimpleNamespace(args=[], application=SimpleNamespace(create_task=lambda coro: coro.close()), bot=None)

    def guncelleme(**ek):
        return SimpleNamespace(effective_user=SimpleNamespace(id=SAHIP), effective_chat=SimpleNamespace(id=SAHIP), **ek)

    def bas(veri):
        asyncio.run(b.dugme(guncelleme(callback_query=_Sorgu(veri, gunluk)), ctx))

    def yaz(metin):
        asyncio.run(b.baglanti(guncelleme(message=_Mesaj(gunluk, metin)), ctx))

    return SimpleNamespace(b=b, gunluk=gunluk, bas=bas, yaz=yaz, baslatilan=baslatilan)


def test_bot_hazir_boyut_politikayi_da_secer(bot):
    i = next(n for n, o in enumerate(bot.b.ogeler) if o["anahtar"] == "video.max_mb")
    bot.bas(f"d:{i}:1")  # 179 MB
    assert bot.b.secimler[SAHIP] == {"video.max_mb": 179, "video.politika": "max_mb"}
    assert "video.politika = max_mb" in bot.gunluk[-1][1]


def test_bot_ozel_cq_akisi(bot):
    i = next(n for n, o in enumerate(bot.b.ogeler) if o["anahtar"] == "video.cq")
    bot.bas(f"o:{i}")
    assert "1-51" in bot.gunluk[-1][1]
    bot.yaz("99")  # aralık dışı: kabul edilmez, hâlâ bekler
    assert "Olmadı" in bot.gunluk[-1][1] and SAHIP in bot.b.ozel_bekleyen
    bot.yaz("28")
    assert bot.b.secimler[SAHIP] == {"video.cq": 28, "video.politika": "cq"}
    assert SAHIP not in bot.b.ozel_bekleyen
    bot.yaz("https://example.invalid/v.mp4")  # bekleyen yokken metin = bağlantı: iş başlar, seçimler gider
    assert bot.baslatilan == [("https://example.invalid/v.mp4", {"video.cq": 28, "video.politika": "cq"})]


def test_bot_ozel_max_mb_ve_ayarlar_vazgecer(bot):
    i = next(n for n, o in enumerate(bot.b.ogeler) if o["anahtar"] == "video.max_mb")
    bot.bas(f"o:{i}")
    asyncio.run(bot.b.ayarlar(SimpleNamespace(effective_user=SimpleNamespace(id=SAHIP),
                                              message=_Mesaj(bot.gunluk)), None))
    assert SAHIP not in bot.b.ozel_bekleyen
    bot.bas(f"o:{i}")
    bot.yaz("347")
    assert bot.b.secimler[SAHIP] == {"video.max_mb": 347, "video.politika": "max_mb"}


def test_bot_model_secimi_dogrulanir(bot):
    ogeler = bot.b.ogeler
    i = next(n for n, o in enumerate(ogeler) if o["anahtar"] == "transkripsiyon.model")
    bot.bas(f"d:{i}:2")
    assert bot.b.secimler[SAHIP]["transkripsiyon.model"] == "distil-large-v3.5"
