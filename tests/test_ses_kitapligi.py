"""Ses kitaplığı (GPU'suz, ağsız): ekle / güncelle / sil / listele / bul / metin / tohum, `kitaplik/<kimlik>` çözümü,
VoxCPM2 koşucusuna giden referans (yalnız ses ya da ses + metin) ve ayar doğrulaması.

ffmpeg çağrısı sahte (kaynak zaten wav olduğu için kopyalanır); gerçek ffmpeg ile bir dönüştürme testi ayrıca,
ffmpeg yoksa atlanır. Web uçları: tests/test_ses_kitapligi_web.py.
"""

from __future__ import annotations

import json
import math
import shutil
import struct
import sys
import types
import wave
from pathlib import Path

import pytest

from dublaj_hatti import ses_kitapligi
from dublaj_hatti.ses_kitapligi import SesKitapligiHatasi


def wav_yaz(yol: Path, sn: float, hiz: int = 24000, kanal: int = 1) -> Path:
    """Sinüs dalgalı gerçek bir wav dosyası (wave modülü)."""
    kare = int(sn * hiz)
    with wave.open(str(yol), "wb") as w:
        w.setnchannels(kanal)
        w.setsampwidth(2)
        w.setframerate(hiz)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * i / hiz))) * kanal
                               for i in range(kare)))
    return yol


@pytest.fixture()
def kitaplik(tmp_path, monkeypatch):
    kok = tmp_path / "kitaplik"
    monkeypatch.setenv(ses_kitapligi.KITAPLIK_ORTAM, str(kok))
    from dublaj_hatti.bolum_00_omurga.runtime import arac_yolu

    monkeypatch.setattr(arac_yolu, "arac_bul", lambda ad: "ffmpeg-sahte")

    def sahte_ffmpeg(komut, **_):  # ffmpeg ... -i <girdi> ... <cikti>: girdi zaten wav, kopyalanır
        girdi = Path(komut[komut.index("-i") + 1])
        try:
            shutil.copyfile(girdi, komut[-1])
            kod = 0
        except OSError:
            kod = 1
        return types.SimpleNamespace(returncode=kod, stdout="", stderr="")

    monkeypatch.setattr(ses_kitapligi.subprocess, "run", sahte_ffmpeg)
    return kok


def ekle(tmp_path, sn=8.0, **kw):
    kaynak = wav_yaz(tmp_path / f"kayit_{sn}.wav", sn)
    argumanlar = dict(ad="Ayşe — kendi sesim", kategori="kadin", riza="kendi", taklit_yok=True)
    argumanlar.update(kw)
    return ses_kitapligi.ekle(kaynak, **argumanlar)


def test_ekle_kaydi_yazar(kitaplik, tmp_path):
    kayit = ekle(tmp_path)
    assert (kitaplik / kayit["kimlik"] / "ses.wav").is_file()
    assert kayit["ad"] == "Ayşe — kendi sesim" and kayit["kategori"] == "kadin" and kayit["sure_sn"] == 8.0
    assert kayit["riza"] == {"tur": "kendi", "taklit_yok": True, "surum": ses_kitapligi.RIZA_SURUMU}
    assert kayit["metin"] == "" and isinstance(kayit["tohum"], int) and kayit["tohum"] > 0
    ham = json.loads((kitaplik / kayit["kimlik"] / "kimlik.json").read_text(encoding="utf-8"))
    assert "yol" not in ham  # yol çalışma anında eklenir, diske yazılmaz
    assert not [p for p in kitaplik.iterdir() if p.name.startswith(".ekle_")]  # geçici klasör kalmaz


@pytest.mark.parametrize("riza", ["", "baskasi", None])
def test_riza_olmadan_eklenmez(kitaplik, tmp_path, riza):
    with pytest.raises(SesKitapligiHatasi) as hata:
        ekle(tmp_path, riza=riza)
    assert hata.value.anahtar == "riza_yok"
    assert not kitaplik.exists() or not list(kitaplik.iterdir())


@pytest.mark.parametrize("onay", [False, None, "evet", 1])
def test_taklit_yok_onayi_zorunlu(kitaplik, tmp_path, onay):
    with pytest.raises(SesKitapligiHatasi) as hata:
        ekle(tmp_path, taklit_yok=onay)
    assert hata.value.anahtar == "taklit_yok" and "ETHICS.md" in str(hata.value)


def test_gecersiz_uzanti(kitaplik, tmp_path):
    kaynak = tmp_path / "belge.pdf"
    kaynak.write_bytes(b"x")
    with pytest.raises(SesKitapligiHatasi) as hata:
        ses_kitapligi.ekle(kaynak, "Ses", "kadin", "kendi", True)
    assert hata.value.anahtar == "uzanti_gecersiz" and ".wav" in str(hata.value)


@pytest.mark.parametrize("sn", [1.0, 2.9, 31.0])
def test_cok_kisa_ya_da_cok_uzun_kayit(kitaplik, tmp_path, sn):
    with pytest.raises(SesKitapligiHatasi) as hata:
        ekle(tmp_path, sn=sn)
    assert hata.value.anahtar == "sure_disi" and "6-15 sn" in str(hata.value)
    assert not [p for p in kitaplik.iterdir() if p.is_dir()]  # yarım klasör bırakmaz


@pytest.mark.parametrize("sn", [3.0, 6.0, 30.0])
def test_sinir_degerleri_kabul(kitaplik, tmp_path, sn):
    assert ekle(tmp_path, sn=sn)["sure_sn"] == sn


def test_okunamayan_dosya(kitaplik, tmp_path):
    kaynak = tmp_path / "bozuk.wav"
    kaynak.write_bytes(b"")
    with pytest.raises(SesKitapligiHatasi):
        ses_kitapligi.ekle(kaynak, "Ses", "kadin", "kendi", True)


@pytest.mark.parametrize("ad", ["", "   ", "a" * 61, "x\x00y"])
def test_gecersiz_ad(kitaplik, tmp_path, ad):
    with pytest.raises(SesKitapligiHatasi) as hata:
        ekle(tmp_path, ad=ad)
    assert hata.value.anahtar == "ad_gecersiz"


def test_ad_sessizce_duzelir(kitaplik, tmp_path):
    assert ekle(tmp_path, ad="  Ayşe   Hanım ")["ad"] == "Ayşe Hanım"


def test_gecersiz_kategori(kitaplik, tmp_path):
    with pytest.raises(SesKitapligiHatasi) as hata:
        ekle(tmp_path, kategori="robot")
    assert hata.value.anahtar == "kategori_gecersiz"


def test_izinli_riza_turu(kitaplik, tmp_path):
    assert ekle(tmp_path, riza="izinli")["riza"]["tur"] == "izinli"


# --- kaydın metni (isteğe bağlı) ---------------------------------------------------------------------------------

def test_metin_kirpilir_ve_saklanir(kitaplik, tmp_path):
    kayit = ekle(tmp_path, metin="  Merhaba   dünya.\n\tBugün hava güzel.  ")
    assert kayit["metin"] == "Merhaba dünya. Bugün hava güzel."


def test_metin_en_cok_600_karakter(kitaplik, tmp_path):
    assert len(ekle(tmp_path, metin="a" * 600)["metin"]) == 600
    with pytest.raises(SesKitapligiHatasi) as hata:
        ekle(tmp_path, metin="a" * 601)
    assert hata.value.anahtar == "metin_uzun" and "601" in str(hata.value)


def test_guncelle_ad_kategori_metin(kitaplik, tmp_path):
    kimlik = ekle(tmp_path)["kimlik"]
    tohum = ses_kitapligi.coz("kitaplik/" + kimlik)["tohum"]
    g = ses_kitapligi.guncelle(kimlik, ad="Yeni ad", kategori="genc", metin=" Selam  dünya ")
    assert (g["ad"], g["kategori"], g["metin"]) == ("Yeni ad", "genc", "Selam dünya")
    g = ses_kitapligi.guncelle(kimlik, ad="Başka")  # None = dokunma
    assert (g["kategori"], g["metin"]) == ("genc", "Selam dünya")
    assert ses_kitapligi.guncelle(kimlik, metin="")["metin"] == ""  # boş metin = sil
    assert ses_kitapligi.coz("kitaplik/" + kimlik)["tohum"] == tohum  # güncelleme tohumu değiştirmez


def test_guncelle_gecersiz_ve_olmayan(kitaplik, tmp_path):
    kimlik = ekle(tmp_path)["kimlik"]
    with pytest.raises(SesKitapligiHatasi):
        ses_kitapligi.guncelle(kimlik, ad="")
    with pytest.raises(SesKitapligiHatasi):
        ses_kitapligi.guncelle(kimlik, kategori="x")
    with pytest.raises(SesKitapligiHatasi):
        ses_kitapligi.guncelle(kimlik, metin="a" * 700)
    assert ses_kitapligi.listele()[0]["ad"] == "Ayşe — kendi sesim"  # hatalı istek kaydı bozmadı
    with pytest.raises(SesKitapligiHatasi) as hata:
        ses_kitapligi.guncelle("0" * 32, ad="x")
    assert hata.value.anahtar == "ses_yok"
    with pytest.raises(SesKitapligiHatasi) as hata:
        ses_kitapligi.guncelle("../..", ad="x")
    assert hata.value.anahtar == "kimlik_gecersiz"


def test_sil_klasoru_kaldirir_ve_baskasina_dokunmaz(kitaplik, tmp_path):
    a, b = ekle(tmp_path)["kimlik"], ekle(tmp_path, ad="İkinci")["kimlik"]
    ses_kitapligi.sil(a)
    assert not (kitaplik / a).exists() and (kitaplik / b / "ses.wav").is_file()
    with pytest.raises(SesKitapligiHatasi):
        ses_kitapligi.sil(a)
    with pytest.raises(SesKitapligiHatasi):
        ses_kitapligi.sil("..")


def test_listele_son_eklenen_once_ve_bozuk_kayit_atlanir(kitaplik, tmp_path, monkeypatch):
    sirayla = iter(["2026-10-26T01:00:00.000001Z", "2026-10-26T02:00:00.000001Z", "2026-10-26T03:00:00.000001Z"])

    class SahteZaman:
        @staticmethod
        def now(_tz=None):
            return types.SimpleNamespace(strftime=lambda _f: next(sirayla))

    monkeypatch.setattr(ses_kitapligi, "datetime", SahteZaman)
    adlar = [ekle(tmp_path, ad=ad)["ad"] for ad in ("bir", "iki", "üç")]
    assert adlar == ["bir", "iki", "üç"]
    assert [s["ad"] for s in ses_kitapligi.listele()] == ["üç", "iki", "bir"]
    bozuk = kitaplik / ("a" * 32)
    bozuk.mkdir()
    (bozuk / "kimlik.json").write_text("{bozuk", encoding="utf-8")
    (bozuk / "ses.wav").write_bytes(b"")
    assert [s["ad"] for s in ses_kitapligi.listele()] == ["üç", "iki", "bir"]


def test_liste_bos_kitaplikta_bos(kitaplik):
    assert ses_kitapligi.listele() == []


def test_bul_referans_yolundan_kaydi_bulur(kitaplik, tmp_path):
    kayit = ekle(tmp_path)
    assert ses_kitapligi.bul(kayit["yol"])["kimlik"] == kayit["kimlik"]
    assert ses_kitapligi.bul(tmp_path / "baska.wav") is None


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg yok")
def test_gercek_ffmpeg_stereo_44k_wav_24k_monoya_cevirir(kitaplik, tmp_path, monkeypatch):
    monkeypatch.undo()  # sahte ffmpeg'i kaldır; kitaplık yolunu yeniden ver
    monkeypatch.setenv(ses_kitapligi.KITAPLIK_ORTAM, str(kitaplik))
    from dublaj_hatti.bolum_00_omurga.runtime import arac_yolu

    monkeypatch.setattr(arac_yolu, "arac_bul", lambda ad: shutil.which("ffmpeg"))
    kaynak = wav_yaz(tmp_path / "stereo.wav", 5.0, hiz=44100, kanal=2)
    kayit = ses_kitapligi.ekle(kaynak, "Gerçek", "erkek", "kendi", True)
    with wave.open(kayit["yol"], "rb") as w:
        assert (w.getframerate(), w.getnchannels()) == (24000, 1)
    assert 4.9 <= kayit["sure_sn"] <= 5.1


# --- kitaplik/<kimlik> çözümü ------------------------------------------------------------------------------------

def test_coz_yalniz_ses_ve_metinli(kitaplik, tmp_path):
    yalniz = ekle(tmp_path)
    metinli = ekle(tmp_path, ad="Metinli", metin="Kayıtta söylenen metin.")
    a = ses_kitapligi.coz("kitaplik/" + yalniz["kimlik"])
    b = ses_kitapligi.coz("kitaplik/" + metinli["kimlik"])
    assert a["metin"] == "" and b["metin"] == "Kayıtta söylenen metin."
    assert Path(a["yol"]) == kitaplik / yalniz["kimlik"] / "ses.wav" and Path(a["yol"]).is_file()
    assert a["ad"] == "Ayşe — kendi sesim"


def test_coz_olmayan_kimlikte_yol_gosterir(kitaplik):
    with pytest.raises(SesKitapligiHatasi) as hata:
        ses_kitapligi.coz("kitaplik/" + "0" * 32)
    mesaj = str(hata.value)
    assert hata.value.anahtar == "ses_yok" and "Sesler sekmesinden" in mesaj and "kitaplik/" in mesaj
    for kotu in ("kitaplik/", "kitaplik/../x", "hazir/haber_spikeri", ""):
        with pytest.raises(SesKitapligiHatasi):
            ses_kitapligi.coz(kotu)


def test_tohum_sabit_kayitli_ve_sesler_arasi_ayri(kitaplik, tmp_path):
    a, b = ekle(tmp_path), ekle(tmp_path, ad="İkinci")
    tohumlar = {ses_kitapligi.coz("kitaplik/" + a["kimlik"])["tohum"] for _ in range(5)}
    assert tohumlar == {a["tohum"]}  # her okumada aynı
    ham = json.loads((kitaplik / a["kimlik"] / "kimlik.json").read_text(encoding="utf-8"))
    assert ham["tohum"] == a["tohum"]  # diskte saklı
    assert ses_kitapligi.coz("kitaplik/" + b["kimlik"])["tohum"] == b["tohum"]  # her sesin tohumu kendine ait


def test_eski_kayitta_tohum_kimlikten_turetilir_ve_sabit(kitaplik, tmp_path):
    kimlik = ekle(tmp_path)["kimlik"]
    yol = kitaplik / kimlik / "kimlik.json"
    ham = json.loads(yol.read_text(encoding="utf-8"))
    del ham["tohum"], ham["metin"]
    yol.write_text(json.dumps(ham), encoding="utf-8")
    ilk = ses_kitapligi.coz("kitaplik/" + kimlik)
    assert ilk["tohum"] > 0 and ilk["metin"] == "" and ilk == ses_kitapligi.coz("kitaplik/" + kimlik)


# --- VoxCPM2 hattı: iş dosyası ve koşucu --------------------------------------------------------------------------

@pytest.fixture()
def motor_sahte(tmp_path, monkeypatch, kitaplik):
    """voxcpm2_durumu kurulu; alt süreç yerine koşucu aynı süreçte, sahte ses_tasarim paketiyle çalışır."""
    pytest.importorskip("soundfile")
    from dublaj_hatti.bolum_50_seslendirme.voxcpm2_tts import api, kosucu

    kok = tmp_path / "kardes"
    (kok / "ses_tasarim").mkdir(parents=True)
    (kok / "ayarlar.json").write_text("{}", encoding="utf-8")
    istekler: list[dict] = []
    paket = types.ModuleType("ses_tasarim")
    ayarlar = types.ModuleType("ses_tasarim.ayarlar")
    ayarlar.load = lambda yol: {}
    motor = types.ModuleType("ses_tasarim.motor")
    motor.FIXED = {"adim": 16, "cfg": 2.0}
    motor.SAMPLE_RATE = 48000
    motor.reference_wav = lambda yol, calisma: Path(yol)
    motor.read_request = lambda i, metin, tohum, ref, ref_metin: {
        "id": i, "text": metin, "seed": tohum, "audio": str(ref), "voice_ref": str(ref), "reference_text": ref_metin.strip()}

    def calistir(ayar, istekler_, calisma):
        istekler.extend(istekler_)
        return {"audios": {r["id"]: [0.0] for r in istekler_}, "bad": [], "seconds": 1.0, "vram_peak_mb": 1}

    motor.run_sequence = calistir
    motor.write_wav = lambda yol, ses: Path(yol).write_bytes(b"RIFF")
    oku = types.ModuleType("ses_tasarim.oku")
    oku.find_voice = lambda ayar, kimlik: (_ for _ in ()).throw(AssertionError("kitaplik sesi hazır ses gibi aranmaz"))
    okunus = types.ModuleType("ses_tasarim.okunus")
    okunus.lines = lambda metin: [(metin, 0)]
    okunus.spoken = lambda metin, dil: metin
    for ad, mod in {"ses_tasarim": paket, "ses_tasarim.ayarlar": ayarlar, "ses_tasarim.motor": motor,
                    "ses_tasarim.oku": oku, "ses_tasarim.okunus": okunus}.items():
        monkeypatch.setitem(sys.modules, ad, mod)
    for alt in ("ayarlar", "motor", "oku", "okunus"):
        setattr(paket, alt, sys.modules["ses_tasarim." + alt])
    monkeypatch.setattr(api, "voxcpm2_durumu", lambda: {"kurulu": True, "kok": str(kok), "python": "py", "commit": "x"})

    ffmpeg_sahte = ses_kitapligi.subprocess.run  # subprocess modülü ortak: ffmpeg çağrıları eskisi gibi sahte kalır

    def sahte_calistir(komut, **ek):  # alt süreç: koşucu aynı süreçte
        if "--is" not in komut:
            return ffmpeg_sahte(komut, **ek)
        kosucu.main(["--kok", str(kok), "--is", komut[komut.index("--is") + 1],
                     "--sonuc", komut[komut.index("--sonuc") + 1]])
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(api.subprocess, "run", sahte_calistir)
    return types.SimpleNamespace(api=api, istekler=istekler)


def _cfg():
    return types.SimpleNamespace(target_lang="tr")


def test_hat_yalniz_ses_klonu_voice_ref_ile(kitaplik, tmp_path, motor_sahte):
    kayit = ekle(tmp_path)
    ozet = motor_sahte.api._run_engine("kitaplik/" + kayit["kimlik"], [{"index": 1, "text": "Merhaba."}], _cfg(),
                                       tmp_path / "is")
    (istek,) = motor_sahte.istekler
    assert istek["voice_ref"] == kayit["yol"] and "audio" not in istek and "reference_text" not in istek
    assert istek["seed"] == kayit["tohum"] and ozet["tohum"] == kayit["tohum"] and ozet["referans_metin"] is False
    is_json = json.loads((tmp_path / "is" / "is.json").read_text(encoding="utf-8"))
    assert is_json["ses"] == "kitaplik/" + kayit["kimlik"] and is_json["kitaplik"]["metin"] == ""


def test_hat_metin_varsa_referans_metin_verilir(kitaplik, tmp_path, motor_sahte):
    kayit = ekle(tmp_path, metin="Bu kayıtta söylenen cümle.")
    ozet = motor_sahte.api._run_engine("kitaplik/" + kayit["kimlik"], [{"index": 1, "text": "Merhaba."}], _cfg(),
                                       tmp_path / "is")
    (istek,) = motor_sahte.istekler
    assert istek["reference_text"] == "Bu kayıtta söylenen cümle." and istek["audio"] == istek["voice_ref"] == kayit["yol"]
    assert ozet["referans_metin"] is True


def test_hat_ayni_ses_her_okumada_ayni_tohum(kitaplik, tmp_path, motor_sahte):
    kayit = ekle(tmp_path)
    for i in range(3):
        motor_sahte.api._run_engine("kitaplik/" + kayit["kimlik"], [{"index": 1, "text": f"Cümle {i}."}], _cfg(),
                                    tmp_path / f"is{i}")
    assert {i["seed"] for i in motor_sahte.istekler} == {kayit["tohum"]}


def test_hat_olmayan_kimlik_yol_gosteren_hata(kitaplik, tmp_path, motor_sahte):
    with pytest.raises(SesKitapligiHatasi, match="Sesler sekmesinden"):
        motor_sahte.api._run_engine("kitaplik/" + "f" * 32, [{"index": 1, "text": "x"}], _cfg(), tmp_path / "is")
    assert not motor_sahte.istekler  # motor hiç çalışmadı


def test_segment_sesi_kitaplik_kimligini_aynen_gecirir(kitaplik, tmp_path, motor_sahte):
    kayit = ekle(tmp_path)
    kimlik = "kitaplik/" + kayit["kimlik"]
    seg = types.SimpleNamespace(speaker="SPEAKER_00", voxcpm2_voice="")
    cfg = types.SimpleNamespace(voxcpm2_konusmaci_sesleri={"SPEAKER_00": kimlik}, voxcpm2_ses="hazir/haber_spikeri")
    assert motor_sahte.api._segment_voice(seg, cfg) == kimlik  # konuşmacı başına
    seg2 = types.SimpleNamespace(speaker="SPEAKER_01", voxcpm2_voice=kimlik)  # cinsiyet listesinden atanan
    assert motor_sahte.api._segment_voice(seg2, cfg) == kimlik
    cfg2 = types.SimpleNamespace(voxcpm2_konusmaci_sesleri={}, voxcpm2_ses=kimlik)  # tek ses
    assert motor_sahte.api._segment_voice(seg2.__class__(speaker="", voxcpm2_voice=""), cfg2) == kimlik


# --- ayar doğrulaması: tek ses, cinsiyet listeleri, konuşmacı başına ----------------------------------------------

def _ayar(**ek):
    from dublaj_hatti import yapilandirma

    ayar = yapilandirma.ayarlari_yukle()
    ayar.update({"ses.motor": "voxcpm2", "genel.hedef_dil": "tr", "ses.voxcpm2_kadin_sesleri": "",
                 "ses.voxcpm2_erkek_sesleri": "", "ses.voxcpm2_ses": yapilandirma.VOXCPM2_VARSAYILAN_SES,
                 "ses.konusmaci_sesleri": {}, "ses.konusmaci_cinsiyetine_gore_ses": False})
    ayar.update(ek)
    return ayar


def _hatalar(ayar):
    from dublaj_hatti.yapilandirma import uyumluluk_denetle

    return [str(b) for b in uyumluluk_denetle(ayar) if b.seviye == "hata"]


@pytest.mark.parametrize("anahtar,deger", [
    ("ses.voxcpm2_ses", "kitaplik/{k}"),
    ("ses.voxcpm2_kadin_sesleri", "hazir/belgesel_hanim, kitaplik/{k}"),
    ("ses.voxcpm2_erkek_sesleri", "kitaplik/{k}"),
    ("ses.konusmaci_sesleri", {"SPEAKER_00": "kitaplik/{k}"}),
])
def test_ayar_kitaplik_sesi_her_yerde_kabul(kitaplik, tmp_path, anahtar, deger):
    kimlik = ekle(tmp_path)["kimlik"]
    if isinstance(deger, dict):
        deger = {k: v.format(k=kimlik) for k, v in deger.items()}
    else:
        deger = deger.format(k=kimlik)
    assert not [h for h in _hatalar(_ayar(**{anahtar: deger})) if "kitaplik" in h or "ses kitaplığı" in h]


@pytest.mark.parametrize("anahtar,deger", [
    ("ses.voxcpm2_ses", "kitaplik/" + "0" * 32),
    ("ses.voxcpm2_kadin_sesleri", "kitaplik/" + "0" * 32),
    ("ses.voxcpm2_erkek_sesleri", "hazir/haber_spikeri, kitaplik/" + "0" * 32),
    ("ses.konusmaci_sesleri", {"SPEAKER_00": "kitaplik/" + "0" * 32}),
])
def test_ayar_olmayan_kitaplik_sesi_yol_gosteren_hata(kitaplik, anahtar, deger):
    hatalar = _hatalar(_ayar(**{anahtar: deger}))
    assert any("Sesler sekmesinden" in h and anahtar in h for h in hatalar), hatalar


def test_kitaplik_sesi_voxcpm2_disinda_denetlenmez(kitaplik):
    ayar = _ayar(**{"ses.motor": "supertonic", "ses.voxcpm2_ses": "kitaplik/" + "0" * 32})
    assert not [h for h in _hatalar(ayar) if "Sesler sekmesinden" in h]


def test_secili_kitaplik_sesi_cinsiyet_havuzunu_gecer(kitaplik, tmp_path):
    """Sesler sekmesinden seçilen ses tek ses olarak herkesi okur; açık kadın/erkek listeleri yine önce gelir."""
    from dublaj_hatti import yapilandirma

    kimlik = "kitaplik/" + ekle(tmp_path)["kimlik"]
    assert yapilandirma.voxcpm2_havuzlari(_ayar(**{"ses.voxcpm2_ses": kimlik})) == ([kimlik], [kimlik], "secili_ses")
    liste = _ayar(**{"ses.voxcpm2_ses": kimlik, "ses.voxcpm2_kadin_sesleri": "hazir/belgesel_hanim"})
    assert yapilandirma.voxcpm2_havuzlari(liste)[2] == "kullanici"
    assert not [u for u in yapilandirma.uyumluluk_denetle(_ayar(**{"ses.voxcpm2_ses": kimlik, "genel.hedef_dil": "en",
                                                                    "ses.konusmaci_cinsiyetine_gore_ses": True}))
                if "hazır ses yok" in str(u)]
