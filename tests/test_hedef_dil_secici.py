"""Önerilen sekmesinde hedef dil seçicisi: dil adı arayüz dilinde (yanında dilin kendi adı), düğme tam cümle
("Almanca dublajla", "Dub into German"), Gelişmiş ile tek ayar.

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
