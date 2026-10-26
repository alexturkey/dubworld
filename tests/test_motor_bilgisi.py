"""Motor bilgi satırı: her stt ve tts motorunun lisans, donanım, dil ve güçlü yan alanları var (arayüz API'si okur)."""

from __future__ import annotations

import json

from dublaj_hatti import kayit


def test_her_stt_ve_tts_motorunun_bilgi_alanlari_dolu():
    for tur in ("stt", "tts"):
        for m in kayit.motorlar(tur):
            b = kayit.motor_bilgisi(m.ad)
            assert isinstance(b["licence_commercial"], bool), m.ad
            assert b["hardware"], m.ad
            assert b["languages"], m.ad
            assert b["strength"]["tr"] and b["strength"]["en"], m.ad


def test_bilgi_json_cevrilebilir_ve_tur_suzgeci():
    tum = kayit.motor_bilgileri()
    assert json.loads(json.dumps(tum)) == tum
    assert {b["kind"] for b in tum} == {"stt", "tts"}
    assert {b["id"] for b in kayit.motor_bilgileri("tts")} == {m.ad for m in kayit.motorlar("tts")}


def test_ticari_olmayan_motorlar_isaretli():
    assert kayit.motor_bilgisi("crisperwhisper_turbo_ct2")["licence_commercial"] is False
    assert kayit.motor_bilgisi("xtts")["licence_commercial"] is False
    assert kayit.motor_bilgisi("voxcpm2")["licence_commercial"] is True
