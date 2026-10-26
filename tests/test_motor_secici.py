"""Arayüzün "Motorlar" seçicisi (GPU'suz, ağsız): `GET /api/motorlar` verisi, "auto"nun bu bilgisayardaki kararı, Gelişmiş
motor ayarları listesi, iki dilli metinler ve sayfadaki parçalar. "auto" kuralı iş başlarken kullanılanla aynı işlevdir."""

from __future__ import annotations

import http.client
import json
import re
import threading
from pathlib import Path

import pytest

from dublaj_hatti import kayit, motor_secici, web, yapilandirma
from dublaj_hatti.arayuz_dili import sozluk

STATIK = Path(__file__).resolve().parents[1] / "src" / "dublaj_hatti" / "web_statik"
JS = (STATIK / "app.js").read_text(encoding="utf-8")
CSS = (STATIK / "app.css").read_text(encoding="utf-8")
KALDIRILANLAR = ("crisperwhisper2_medium", "moonshine_medium_streaming_en", "whisper_cpp_cpu_align", "speechmatics",
                 "elevenlabs_scribe_v2")


def _kurulu(stt: set[str], tts: set[str]):
    return lambda tur: {m.ad: m.ad in (stt if tur == "stt" else tts) for m in kayit.motorlar(tur)}


def _veri(gpu=True, stt=(), tts=(), **ayar):
    taban = yapilandirma.ayarlari_yukle()
    return motor_secici.motor_secici_verisi({**taban, **ayar}, gpu=gpu, vram_mb=4096 if gpu else 0,
                                            kurulu=_kurulu(set(stt), set(tts)))


def _satir(veri, tur, ad):
    return next(e for e in veri[tur]["engines"] if e["id"] == ad)


def test_her_stt_ve_tts_motoru_listede_kaldirilanlar_yok():
    v = _veri()
    assert [e["id"] for e in v["stt"]["engines"]] == [m.ad for m in kayit.motorlar("stt")]
    assert [e["id"] for e in v["tts"]["engines"]] == [m.ad for m in kayit.motorlar("tts")]
    gorunen = {e["id"] for e in v["stt"]["engines"] + v["tts"]["engines"]}
    assert not gorunen & set(KALDIRILANLAR)
    assert v["stt"]["key"] == "transkripsiyon.motor" and v["tts"]["key"] == "ses.motor"
    # seçilebilir her değer ayar şemasında geçerli (seçici hiçbir zaman geçersiz değer yazmaz)
    assert {e["id"] for e in v["stt"]["engines"]} <= set(yapilandirma.SEMA["transkripsiyon.motor"])
    assert {e["id"] for e in v["tts"]["engines"]} <= set(yapilandirma.SEMA["ses.motor"])


def test_satir_bilgi_alanlari_ve_kurulum_komutu():
    for e in _veri()["stt"]["engines"] + _veri()["tts"]["engines"]:
        for alan in ("name", "licence_commercial", "hardware", "languages", "strength", "install", "installed", "selectable"):
            assert alan in e, (e["id"], alan)
        assert e["strength"]["tr"] and e["strength"]["en"] and e["install"].startswith("scripts/kur.ps1")


def test_kurulu_olmayan_secilemez_komutu_gosterir_kurulu_secilebilir():
    v = _veri(gpu=True, stt={"faster-whisper"}, tts={"supertonic"})
    assert _satir(v, "stt", "faster-whisper")["selectable"] is True
    turbo = _satir(v, "stt", "crisperwhisper_turbo_ct2")
    assert turbo["selectable"] is False and turbo["blocked_by"] == "kurulu_degil"
    assert "-Adim crisper" in turbo["install"]
    assert _satir(v, "tts", "voxcpm2")["blocked_by"] == "kurulu_degil"


def test_gpu_yoksa_yalniz_gpu_motoru_engelli_nedeni_gpu():
    v = _veri(gpu=False, stt={"crisperwhisper_turbo_ct2"}, tts={"voxcpm2", "supertonic"})
    assert _satir(v, "stt", "crisperwhisper_turbo_ct2")["blocked_by"] == "gpu_yok"
    assert _satir(v, "tts", "voxcpm2")["blocked_by"] == "gpu_yok"
    assert _satir(v, "tts", "supertonic")["selectable"] is True


def test_xtts_kullanimdan_kalkiyor_isareti():
    v = _veri()
    assert _satir(v, "tts", "xtts")["deprecated"] is True
    assert not any(e["deprecated"] for e in v["stt"]["engines"]) and not _satir(v, "tts", "voxcpm2")["deprecated"]


@pytest.mark.parametrize("gpu, stt, tts, beklenen_stt, beklenen_tts", [
    (True, {"crisperwhisper_turbo_ct2"}, {"voxcpm2"}, ("crisperwhisper_turbo_ct2", "turbo"), ("voxcpm2", "tamam")),
    (True, set(), set(), ("faster_whisper_ctc", "turbo_yok"), ("supertonic", "kurulu_degil")),
    (False, {"crisperwhisper_turbo_ct2"}, {"voxcpm2"}, ("faster_whisper_ctc", "gpu_yok"), ("supertonic", "gpu_yok")),
])
def test_auto_bu_bilgisayarda_ne_secer(gpu, stt, tts, beklenen_stt, beklenen_tts):
    v = _veri(gpu=gpu, stt=stt, tts=tts)
    assert (v["stt"]["auto"]["engine"], v["stt"]["auto"]["reason"]) == beklenen_stt
    assert (v["tts"]["auto"]["engine"], v["tts"]["auto"]["reason"]) == beklenen_tts


def test_auto_full_text_kipinda_supertonic():
    v = _veri(gpu=True, tts={"voxcpm2"}, **{"genel.dublaj_kipi": "full_text"})
    assert v["tts"]["auto"] == {"engine": "supertonic", "reason": "full_text", "installed": False}


def test_auto_kurali_is_baslarkenkiyle_ayni_islev(monkeypatch):
    """Seçici ile iş başlarken kullanılan karar aynı saf işlevden gelir: gerekçe kodu ↔ ileti eşleşir."""
    for kod, parca in (("tamam", "→ voxcpm2"), ("gpu_yok", "GPU yok"), ("kurulu_degil", "kurulu değil"), ("full_text", "full_text")):
        assert parca in yapilandirma._TTS_AUTO_NEDEN[kod]
    assert yapilandirma.tts_auto_karar(False, True, True) == ("voxcpm2", "tamam")
    assert yapilandirma.stt_auto_karar(True, True) == ("crisperwhisper_turbo_ct2", "turbo")


def test_gelismis_motor_anahtarlari_gercek_ve_tam():
    anahtarlar = motor_secici.gelismis_motor_anahtarlari()
    assert set(anahtarlar) <= set(yapilandirma.SEMA)
    for beklenen in ("transkripsiyon.model", "transkripsiyon.hesap_tipi", "ses.ema_cihaz", "ses.xtts_referans_ses",
                     "ses.rvc_model", "ileri.pyannote_konusmaci_ayrimi"):
        assert beklenen in anahtarlar, beklenen
    assert {a for a in yapilandirma.SEMA if a.startswith(("ses.ema_", "ses.xtts_", "ses.rvc_", "ileri."))} <= set(anahtarlar)
    assert "transkripsiyon.motor" not in anahtarlar and "ses.motor" not in anahtarlar  # seçici onları yönetir


def test_metinler_iki_dilde_ve_dinamik_anahtarlar_var():
    tr, en = sozluk("tr"), sozluk("en")
    gerekli = {"motor.grup", "motor.grup_yardim", "motor.stt.baslik", "motor.tts.baslik", "motor.auto.ad", "motor.auto.burada",
               "motor.auto.kurulu_degil_ek", "motor.auto.sonra", "motor.cip.kurulu", "motor.cip.kurulu_degil",
               "motor.cip.ticari_evet", "motor.cip.ticari_hayir", "motor.cip.kalkiyor", "motor.cip.deneysel", "motor.cip.secili",
               "motor.engel.kurulu_degil", "motor.engel.gpu_yok", "motor.secili_kurulu_degil", "motor.kalkiyor_not",
               "motor.degisti", "motor.yukleniyor", "motor.yuklenemedi", "motor.kitaplik_birakildi",
               "motor.gelismis.baslik", "motor.gelismis.yardim"}
    for kod in ("turbo", "turbo_yok", "gpu_yok"):
        gerekli.add("motor.auto.stt." + kod)
    for kod in ("tamam", "kurulu_degil", "gpu_yok", "full_text"):
        gerekli.add("motor.auto.tts." + kod)
    for m in kayit.motorlar("stt") + kayit.motorlar("tts"):
        gerekli |= {f"motor.ad.{m.ad}", f"motor.donanim.{m.ad}", f"motor.diller.{m.ad}"}
    for ad, s in (("tr", tr), ("en", en)):
        assert sorted(k for k in gerekli if not s.get(k, "").strip()) == [], ad
    for k in gerekli:  # yer tutucular iki dilde aynı
        assert set(re.findall(r"\{(\w+)\}", tr[k])) == set(re.findall(r"\{(\w+)\}", en[k])), k
    assert "{komut}" in tr["motor.engel.kurulu_degil"] and "{ad}" in tr["motor.auto.burada"]


def test_sayfada_secici_gelismis_bolum_ve_bildirim_duzeltmesi():
    assert '"/api/motorlar"' in JS and "function motorGrubuCiz(" in JS and "function motorlariEsitle(" in JS
    assert 'ayarYaz(grup.veri.key, deger)' in JS  # seçim yalnız a_ alanına + change olayıyla yazılır
    assert 'createElement("details")' in JS and 'gelismisKap.className = "gelismis-motor"' in JS
    assert re.search(r'role", "radiogroup"', JS) and "motor-secili-isareti" in JS
    # arama: seçici ve katlı gelişmiş bölümde çalışır, arama bitince katlama geri gelir
    assert "motor-bolum" in JS and "details.gelismis-motor" in JS and "dataset.once" in JS
    # bildirim: dar ekranda üstte, "Geri al" tek satır ve 44 px
    assert "function bildirimYeri(" in JS and 'matchMedia("(max-width: 640px)")' in JS
    assert re.search(r"\.bildirim \.metin-dugme \{[^}]*white-space: nowrap", CSS)
    assert re.search(r"\.bildirim \{[^}]*width: max-content", CSS)
    assert re.search(r"\.bildirim\.ustte \{[^}]*bottom: auto", CSS) and re.search(r"\.metin-dugme \{[^}]*min-height: 44px", CSS)
    assert re.search(r"fieldset \{[^}]*min-width: 0", CSS)  # geniş bir seçenek çekmeceyi yana taşırmaz
    assert re.search(r"\.motor-secenek \{[^}]*min-height: 44px", CSS)
    assert re.search(r"\.motor-secili-isareti \{[^}]*visibility: hidden", CSS)  # seçimde yer değişmez


def test_secici_yeni_renk_ciftleri_okunur():
    from tests.test_web_arayuz import _temalar, kontrast  # noqa: PLC0415

    for ad, r in _temalar().items():
        for yazi, zemin in (("yazi", "kart2"), ("tamam", "kart2"), ("uyari", "kart2"), ("soluk", "ana-acik"),
                            ("yazi", "ana-acik"), ("ana-yazi", "ana"), ("uyari", "ana-acik")):
            assert kontrast(r[yazi], r[zemin]) >= 4.5, (ad, yazi, zemin)


# --- uç nokta ---------------------------------------------------------------------------------------------------
@pytest.fixture()
def sunucu(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "cikti_koku", lambda: tmp_path)
    hazir = _veri(gpu=False, stt={"faster-whisper"})
    monkeypatch.setattr(motor_secici, "motor_secici_verisi", lambda *a, **k: hazir)
    s = web.Sunucu(("127.0.0.1", 0), web.Isleyici)
    port = s.server_address[1]
    uygulama = web.Uygulama(port, 1)
    web.Isleyici.uygulama = uygulama
    threading.Thread(target=s.serve_forever, daemon=True).start()

    def iste(yol, cerez=True):
        b = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        b.request("GET", yol, headers={"Host": f"127.0.0.1:{port}", **({"Cookie": f"{web.CEREZ}={uygulama.belirtec}"} if cerez else {})})
        y = b.getresponse()
        return y.status, y.read()

    yield iste, uygulama
    s.shutdown()
    s.server_close()


def test_uc_nokta_oturum_ister_ve_json_doner(sunucu):
    iste, uygulama = sunucu
    assert iste("/api/motorlar", cerez=False)[0] == 403
    durum, govde = iste("/api/motorlar")
    assert durum == 200
    veri = json.loads(govde)
    assert veri["gpu"] is False and veri["stt"]["auto"]["reason"] == "gpu_yok"
    assert "advanced_keys" in veri
    assert uygulama.motorlar() is uygulama.motorlar()  # 15 sn önbellek: ikinci çağrı yeniden denetlemez


# --- "auto" + kitaplık sesi ---------------------------------------------------------------------------------------
def _kitaplik_sesi(monkeypatch, var: bool):
    from dublaj_hatti import ses_kitapligi

    def coz(ses):
        if var and ses == "kitaplik/abc123":
            return {"yol": "x.wav", "metin": "", "ad": "Ayşe", "tohum": 7}
        raise ses_kitapligi.SesKitapligiHatasi("yok", "ses_yok")

    monkeypatch.setattr(ses_kitapligi, "coz", coz)


def test_auto_kitaplik_sesiyle_voxcpm2_secer_ve_ses_dogrulanir(monkeypatch):
    from dublaj_hatti.bolum_00_omurga.runtime import donanim

    monkeypatch.setattr(donanim, "cihaz_coz", lambda secim="auto": "cuda")
    ham = kayit.motor("voxcpm2")
    asil = kayit.motor
    monkeypatch.setattr(kayit, "motor", lambda ad: ham.__class__(**{**ham.__dict__, "kurulu": lambda: True}) if ad == "voxcpm2" else asil(ad))
    _kitaplik_sesi(monkeypatch, True)
    ayar = yapilandirma.ayarlari_yukle(ustune=["ses.voxcpm2_ses=kitaplik/abc123"])
    assert ayar["ses.motor"] == "auto"
    motor, neden = yapilandirma.tts_auto_coz(ayar)
    assert motor == "voxcpm2" and "kitaplık" not in neden
    yapilandirma._uyumluluk_uygula({**ayar, "ses.motor": motor})  # dubconfig_olustur'un yaptığı: hata yok
    _kitaplik_sesi(monkeypatch, False)  # ses silinmişse çözülen motor açık hata verir (sessiz Supertonic'e düşmez)
    with pytest.raises(yapilandirma.AyarHatasi, match="ses.voxcpm2_ses"):
        yapilandirma._uyumluluk_uygula({**ayar, "ses.motor": motor})


def test_auto_voxcpm2_yoksa_kitaplik_sesinin_yok_sayildigini_soyler(monkeypatch):
    from dublaj_hatti.bolum_00_omurga.runtime import donanim

    monkeypatch.setattr(donanim, "cihaz_coz", lambda secim="auto": "cpu")
    ayar = yapilandirma.ayarlari_yukle(ustune=["ses.voxcpm2_ses=kitaplik/abc123"])
    motor, neden = yapilandirma.tts_auto_coz(ayar)
    assert motor == "supertonic" and "kitaplık sesi (kitaplik/abc123) yalnız VoxCPM2" in neden
