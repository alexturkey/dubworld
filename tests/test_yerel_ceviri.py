"""Yerel Opus-MT (model ve torch sahte, ağsız):

* boş model çıktısı kaynak metne sessizce dönmez, açık hata verir (ADR 0009);
* girdiler uzunluğa göre sıralanır, toplu iş token bütçesine göre kurulur, OOM'da grup yarıya iner, en sonda
  işlemciye geçilir; uzun girdi cümleden bölünür, tek cümle sınırı aşarsa açık hata (Düzeltme A, O2).

Gerçek modelle "kısa girdide çeviri değişmedi" kanıtı: tests/test_yerel_ceviri_altin.py (slow).
"""

from __future__ import annotations

import contextlib
import sys
import types

import pytest

from dublaj_hatti.bolum_40_ceviri.yerel_ceviri import engine


class _OOM(RuntimeError):
    pass


class _SahteTokenizer:
    """Token = boşlukla ayrılmış kelime. Çeviri = sözlükten (yoksa 'TR:' + metin)."""

    def __init__(self, sozluk=None):
        self.sozluk = dict(sozluk or {})
        self.gruplar: list[list[str]] = []

    def __call__(self, metinler, **_):
        if isinstance(metinler, str):
            return {"input_ids": metinler.split()}
        self.son = list(metinler)
        self.gruplar.append(self.son)
        return {}

    def batch_decode(self, _uretilen, **_):
        return [self.sozluk.get(m, "TR:" + m) for m in self.son]


class _SahteModel:
    def __init__(self, oom_esigi=None, cpu_oom=False):
        self.oom_esigi = oom_esigi  # bu kadar ya da fazla girdili grup "bellek yetmedi" verir
        self.cpu_oom = cpu_oom
        self.cihaz = "cuda"

    def to(self, cihaz):
        self.cihaz = cihaz
        return self

    def generate(self, **_):
        return None


@pytest.fixture()
def cevirmen(monkeypatch):
    sahte_torch = types.SimpleNamespace(
        inference_mode=contextlib.nullcontext,
        cuda=types.SimpleNamespace(OutOfMemoryError=_OOM, is_available=lambda: True, empty_cache=lambda: None),
    )
    monkeypatch.setitem(sys.modules, "torch", sahte_torch)

    def kur(sozluk=None, model=None, cihaz="cpu"):
        c = engine.yerel_ceviri_translator("en", "tr", device=cihaz)
        c._model, c._tokenizer, c._device = model or _SahteModel(), _SahteTokenizer(sozluk), cihaz
        uret = c._uret

        def sinirli_uret(metinler):
            m = c._model
            if m.oom_esigi is not None and len(metinler) >= m.oom_esigi and (c._device != "cpu" or m.cpu_oom):
                raise _OOM("CUDA out of memory")
            return uret(metinler)

        c._uret = sinirli_uret
        return c

    return kur


def test_ceviri_ciktisi_doner(cevirmen):
    c = cevirmen({"Hello": "Merhaba", "How are you": "Nasılsın"})
    assert c.translate_texts(["Hello", "", "How are you"]) == ["Merhaba", "", "Nasılsın"]


def test_bos_cikti_kaynaga_donmez_acik_hata(cevirmen):
    with pytest.raises(engine.YerelCeviriHatasi, match="segment no: 2"):
        cevirmen({"Hello": "Merhaba", "Untranslated sentence": "   "}).translate_texts(["Hello", "Untranslated sentence"])


def test_uzunluga_gore_siralanir_ve_sonuc_sirasi_korunur(cevirmen):
    metinler = ["a", "b c d e", "f g", "h i j"]
    c = cevirmen()
    assert c.translate_texts(metinler) == ["TR:" + m for m in metinler]
    assert c._tokenizer.gruplar == [["b c d e", "h i j", "f g", "a"]]


def test_token_butcesi_grubu_kucultur(cevirmen, monkeypatch):
    monkeypatch.setattr(engine, "TOKEN_BUTCESI", 40)  # 10 token x 4 ışın = 40 -> tek girdi
    uzun = " ".join(["w"] * 10)
    c = cevirmen()
    c.translate_texts([uzun, "x", "y z"])
    assert c._tokenizer.gruplar[0] == [uzun]
    assert all(len(g) <= engine.BATCH_SIZE for g in c._tokenizer.gruplar)
    assert sum(len(g) for g in c._tokenizer.gruplar) == 3


def test_bellek_tasinca_grup_yarilanir(cevirmen):
    c = cevirmen(model=_SahteModel(oom_esigi=3), cihaz="cuda")
    metinler = [f"m{i}" for i in range(8)]
    assert c.translate_texts(metinler) == ["TR:" + m for m in metinler]
    assert max(len(g) for g in c._tokenizer.gruplar) == 2
    assert c._device == "cuda"


def test_tek_girdide_de_tasarsa_islemciye_gecer(cevirmen):
    model = _SahteModel(oom_esigi=1)
    c = cevirmen(model=model, cihaz="cuda")
    assert c.translate_texts(["a b", "c"]) == ["TR:a b", "TR:c"]
    assert c._device == "cpu" and model.cihaz == "cpu"


def test_islemcide_de_tasarsa_hata_yukselir(cevirmen):
    c = cevirmen(model=_SahteModel(oom_esigi=1, cpu_oom=True), cihaz="cpu")
    with pytest.raises(_OOM):
        c.translate_texts(["a"])


def test_baska_hata_yutulmaz(cevirmen):
    c = cevirmen()

    def bozuk(_):
        raise ValueError("model bozuk")

    c._uret = bozuk
    with pytest.raises(ValueError):
        c.translate_texts(["a"])


def test_uzun_girdi_cumleden_bolunur(cevirmen, monkeypatch):
    monkeypatch.setattr(engine, "BOLME_ESIGI", 6)
    metin = "one two three. four five six. seven eight nine ten."
    c = cevirmen()
    # cümleler eşiğe sığdıkça aynı parçada toplanır (6 + 4 > 6: üçüncü cümle ayrı parça)
    assert c.translate_texts([metin]) == ["TR:one two three. four five six. TR:seven eight nine ten."]


def test_kisa_girdi_bolunmez(cevirmen):
    metin = "one two three. four five six."
    c = cevirmen()
    c.translate_texts([metin])
    assert c._tokenizer.gruplar == [[metin]]


def test_sinir_asan_tek_cumle_kesilmez_acik_hata(cevirmen, monkeypatch):
    monkeypatch.setattr(engine, "BOLME_ESIGI", 4)
    monkeypatch.setattr(engine, "GIRDI_TOKEN_SINIRI", 5)
    c = cevirmen()
    with pytest.raises(engine.YerelCeviriHatasi, match="sessizce kesilmez"):
        c.translate_texts(["kisa.", "bir iki uc dort bes alti yedi"])
    assert c._tokenizer.gruplar == []  # model hiç çalışmadı


class _Satir(list):
    def __eq__(self, diger):
        return _Satir(x == diger for x in self)

    def any(self):
        return any(self)


def test_kesik_cikti_acik_hata(cevirmen):
    c = cevirmen()
    c._model.config = types.SimpleNamespace(eos_token_id=0)
    satirlar = [_Satir([5] * (engine.MAX_NEW_TOKENS + 1))]

    class Uretilen(list):
        shape = (1, engine.MAX_NEW_TOKENS + 1)

    with pytest.raises(engine.YerelCeviriHatasi, match="kesildi"):
        c._kesik_cikti_denetle(Uretilen(satirlar), ["uzun girdi"])
    tamam = [_Satir([5] * engine.MAX_NEW_TOKENS + [0])]
    c._kesik_cikti_denetle(Uretilen(tamam), ["uzun girdi"])  # bitiş tokeni var: geçer
