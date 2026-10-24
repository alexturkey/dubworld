"""Lisans kapısı her giriş yolunda aynı yerden (lisans_onayi.kapi_adlar) ve işten ÖNCE çalışır (ağsız, GPU'suz).

Giriş yolları: api işlevleri, aşama komutları (`dubla seslendir` ...), `dubla <video>` / `dubla transkript`,
`dubla devam`, iş çalıştırıcı (kuyruk / arayüz alt süreci), GUI ve web (arayuz_kapisi; web testi test_lisans_onayi).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from dublaj_hatti import api, lisans_onayi


@pytest.fixture(autouse=True)
def onay_dosyasi(tmp_path, monkeypatch):
    yol = tmp_path / "ayarlar" / "lisans_onaylari.json"
    monkeypatch.setenv(lisans_onayi.ONAY_DOSYASI_ORTAM, str(yol))
    monkeypatch.delenv(lisans_onayi.ONAY_ORTAM, raising=False)
    return yol


class KapiCagrildi(Exception):
    pass


class HazirlikKapidanOnce(AssertionError):
    pass


def _transkript(tmp_path):
    from dublaj_hatti.bicimler import json_yaz, transkript_olustur

    yol = tmp_path / "t.json"
    json_yaz(yol, transkript_olustur([{"start": 0.0, "end": 1.0, "text": "Hello."}], "en"))
    return yol


def _cagrilar(tmp_path):
    """Motor çalıştıran her api aşaması, en az girdiyle."""
    return {
        "indir": lambda: api.indir("https://example.com/v.mp4", tmp_path),
        "ayir": lambda: api.ayir(tmp_path / "v.mp4", tmp_path),
        "yaziya_dok": lambda: api.yaziya_dok(tmp_path / "v.mp4", tmp_path / "o.json"),
        "cevir": lambda: api.cevir(_transkript(tmp_path), tmp_path / "c.json"),
        "seslendir": lambda: api.seslendir("Merhaba.", tmp_path / "s"),
        "dubla": lambda: api.dubla(str(tmp_path / "v.mp4")),
    }


def test_her_api_asamasi_ya_kapidan_gecer_ya_motorsuzdur(tmp_path):
    assert set(_cagrilar(tmp_path)) | api.MOTORSUZ_ASAMALAR == set(api.ASAMALAR)
    assert not set(_cagrilar(tmp_path)) & api.MOTORSUZ_ASAMALAR


@pytest.mark.parametrize("asama", ["indir", "ayir", "yaziya_dok", "cevir", "seslendir", "dubla"])
def test_api_kapisi_isten_once(asama, tmp_path, monkeypatch):
    def kapi(adlar, onay=False):
        raise KapiCagrildi(adlar)

    monkeypatch.setattr(api, "kapi_adlar", kapi)
    monkeypatch.setattr(api, "_hazirla", lambda ayar: (_ for _ in ()).throw(HazirlikKapidanOnce()))
    monkeypatch.setattr(api, "kaynak_dogrula", lambda k: k)
    with pytest.raises(KapiCagrildi):
        _cagrilar(tmp_path)[asama]()


def test_api_seslendir_supertonic_onaysiz_durur_onayla_gecer(tmp_path, monkeypatch, onay_dosyasi):
    monkeypatch.setattr(api, "_hazirla", lambda ayar: (_ for _ in ()).throw(HazirlikKapidanOnce()))
    with pytest.raises(api.LisansOnayiGerekli) as hata:
        api.seslendir("Merhaba.", tmp_path / "s", motor="supertonic")
    assert [ad for ad, _ in hata.value.bekleyen] == ["supertonic"]
    assert not onay_dosyasi.exists()
    with pytest.raises(HazirlikKapidanOnce):  # onayla kapı geçilir, iş başlar
        api.seslendir("Merhaba.", tmp_path / "s", motor="supertonic", lisans_onay=True)
    assert "supertonic" in json.loads(onay_dosyasi.read_text(encoding="utf-8"))
    with pytest.raises(HazirlikKapidanOnce):  # hatırlandı
        api.seslendir("Merhaba.", tmp_path / "s", motor="supertonic")


def test_api_lisansi_temiz_motor_sorulmaz(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "_hazirla", lambda ayar: (_ for _ in ()).throw(HazirlikKapidanOnce()))
    with pytest.raises(HazirlikKapidanOnce):
        api.seslendir("Merhaba.", tmp_path / "s", motor="voxcpm2")


def test_cli_seslendir_onaysiz_2_onayla_calisir(tmp_path, monkeypatch, capsys, onay_dosyasi):
    from dublaj_hatti import cli

    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(api, "_hazirla", lambda ayar: (_ for _ in ()).throw(api.AsamaHatasi("kapıdan geçti")))
    assert cli.main(["seslendir", "Merhaba.", "-o", str(tmp_path / "s")]) == 2
    hata = capsys.readouterr().err
    assert "lisans onayı yok" in hata and "Supertonic" in hata and not onay_dosyasi.exists()
    assert cli.main(["seslendir", "Merhaba.", "-o", str(tmp_path / "s"), "--lisans-onay"]) == 1
    assert "kapıdan geçti" in capsys.readouterr().err
    assert "supertonic" in json.loads(onay_dosyasi.read_text(encoding="utf-8"))


def test_cli_asama_komutu_etkilesimli_sorar(tmp_path, monkeypatch, onay_dosyasi):
    from dublaj_hatti import cli

    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda _: "evet")
    monkeypatch.setattr(api, "_hazirla", lambda ayar: (_ for _ in ()).throw(api.AsamaHatasi("kapıdan geçti")))
    assert cli.main(["seslendir", "Merhaba.", "-o", str(tmp_path / "s")]) == 1
    assert onay_dosyasi.exists()


def test_her_asama_komutunda_lisans_onay_secenegi_var():
    from dublaj_hatti import cli
    from dublaj_hatti.asama_komutlari import ASAMA_KOMUTLARI

    ornek = {"indir": ["https://example.com/v"], "hizala": ["a.wav", "b.txt"], "birlestir": ["v.mp4"],
             "seslendir": ["x"]}
    for komut in ASAMA_KOMUTLARI:
        args = cli._argumanlari_coz([komut, *ornek.get(komut, ["x.json"]), "--lisans-onay"])
        assert args.lisans_onay is True, komut


def test_transkript_ses_motorunu_sormaz():
    """`dubla transkript` ses motoru çalıştırmaz: Supertonic sorulmaz, yalnız STT sorulur (K24 notu)."""
    ayar = {"genel.is_turu": "transkript", "transkripsiyon.motor": "faster-whisper", "ses.motor": "supertonic"}
    assert lisans_onayi.kapi(ayar) == []
    ayar["transkripsiyon.motor"] = "crisperwhisper_turbo_ct2"
    with pytest.raises(lisans_onayi.LisansOnayiGerekli) as hata:
        lisans_onayi.kapi(ayar)
    assert [ad for ad, _ in hata.value.bekleyen] == ["crisperwhisper_turbo_ct2"]


def test_cli_transkript_komutu_kapiya_transkript_ayariyla_gider(monkeypatch, tmp_path):
    from dublaj_hatti import cli

    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    gorulen = {}

    def kapi(ayar, stt, onay, etkilesimli):
        gorulen.update(ayar=ayar)
        return 2

    monkeypatch.setattr(cli, "_lisans_kapisi", kapi)
    monkeypatch.setattr(cli, "ortami_hazirla", lambda cihaz: None)
    monkeypatch.setattr("dublaj_hatti.yapilandirma.dubconfig_olustur",
                        lambda ayar, kaynak=None: (None, SimpleNamespace(stt_motoru="faster-whisper")))
    assert cli.main(["transkript", str(video)]) == 2
    assert gorulen["ayar"]["genel.is_turu"] == "transkript"
    assert lisans_onayi.secili_motorlar(gorulen["ayar"], "faster-whisper") == ["faster-whisper"]


def test_devam_ayni_kapidan_gecer(onay_dosyasi):
    from dublaj_hatti.is_yonetimi import komutlar

    ayar = {"genel.is_turu": "dublaj", "transkripsiyon.motor": "faster-whisper", "ses.motor": "supertonic"}
    assert komutlar._lisans_sor(ayar, onay=False, etkilesimli=False) is False
    assert not onay_dosyasi.exists()
    assert komutlar._lisans_sor(ayar, onay=True, etkilesimli=False) is True
    assert komutlar._lisans_sor(ayar, onay=False, etkilesimli=False) is True  # hatırlandı


class _SahteDepo:
    def __init__(self):
        self.bitenler = []

    def bitir(self, job_id, durum, mesaj):
        self.bitenler.append((job_id, durum, mesaj))


@pytest.mark.parametrize("komut,ses_motoru,beklenen", [
    ("dubla", "supertonic", 2), ("transkript", "supertonic", None), ("dubla", "voxcpm2", None)])
def test_is_calistirici_onaysiz_isi_calistirmaz(komut, ses_motoru, beklenen, monkeypatch):
    """Kuyruk / devam / arayüz alt süreci: onaysız iş çalışmaz, soru sorulmaz, iş açık hatayla biter."""
    from dublaj_hatti.is_yonetimi import calistirici

    ayar = {"genel.is_turu": "dublaj", "transkripsiyon.motor": "faster-whisper", "ses.motor": ses_motoru}
    monkeypatch.setattr(calistirici, "is_ayari", lambda kayit: dict(ayar))
    monkeypatch.setattr("dublaj_hatti.yapilandirma.dubconfig_olustur",
                        lambda a, kaynak=None: (None, SimpleNamespace(stt_motoru="faster-whisper", cihaz="cpu")))

    class Gecti(Exception):
        pass

    olaylar = []

    def olay_yaz(e):
        olaylar.append(e)
        if e.get("event") == "basladi":
            raise Gecti

    depo = _SahteDepo()
    kayit = {"job_id": 7, "source": "v.mp4", "command": komut}
    if beklenen is None:
        with pytest.raises(Gecti):
            calistirici._hatti_kos(depo, kayit, olay_yaz, 0)
        assert depo.bitenler == []
    else:
        assert calistirici._hatti_kos(depo, kayit, olay_yaz, 0) == beklenen
        assert depo.bitenler[0][1] == "failed" and "--lisans-onay" in depo.bitenler[0][2]
        assert olaylar[-1]["lisans_onayi"] == ["supertonic"]


def test_arayuz_kapisi_ayni_kapi(monkeypatch):
    """GUI ve web arayuz_kapisi → kapi → kapi_adlar (tek kapı)."""
    cagrilar = []
    gercek = lisans_onayi.kapi_adlar
    monkeypatch.setattr(lisans_onayi, "kapi_adlar", lambda adlar, onay=False: cagrilar.append(adlar) or gercek(adlar, onay))
    with pytest.raises(lisans_onayi.LisansOnayiGerekli):
        lisans_onayi.arayuz_kapisi({"ses.motor": "supertonic", "transkripsiyon.motor": "faster-whisper"})
    assert cagrilar and "supertonic" in cagrilar[0]
