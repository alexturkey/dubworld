"""Makine geneli kaynak kilidi (GPU sırası): kapasite, bayat kilit, süreli kilit, bekleme bildirimi."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from dublaj_hatti.bolum_00_omurga.runtime import kaynak_kilidi as kk


@pytest.fixture(autouse=True)
def gecici_kilit_klasoru(tmp_path, monkeypatch):
    monkeypatch.setenv(kk.KILIT_KLASORU_ENV, str(tmp_path / "kilitler"))
    return tmp_path / "kilitler"


def _olu_pid() -> int:
    surec = subprocess.Popen([sys.executable, "-c", "pass"], creationflags=0x08000000 if os.name == "nt" else 0)
    surec.wait()
    return surec.pid


def test_gpu_kapasitesi_bir_ikinci_istek_mesgul():
    yol = kk.kilit_al("gpu", "uygulama:test", "birinci")
    with pytest.raises(kk.KaynakMesgulError) as hata:
        kk.kilit_al("gpu", "ajan:test", "ikinci")
    assert "birinci" in str(hata.value)
    kk.kilit_birak(yol)
    kk.kilit_birak(kk.kilit_al("gpu", "ajan:test", "ikinci"))


def test_olu_surecin_kilidi_bayat_sayilir_ve_silinir(gecici_kilit_klasoru):
    kk.kilit_al("gpu", "uygulama:test", "ölü", pid=_olu_pid())
    assert kk.kilitler("gpu") == []
    assert not list(gecici_kilit_klasoru.glob("gpu__*.json"))
    kk.kilit_birak(kk.kilit_al("gpu", "uygulama:test", "yeni"))


def test_pidsiz_kilit_sure_ister_ve_suresi_icinde_gecerli():
    with pytest.raises(ValueError):
        kk.kilit_al("gpu", "ajan:test", "x", pid=0)
    yol = kk.kilit_al("gpu", "ajan:test", "süreli", pid=0, sure_dakika=5)
    assert len(kk.kilitler("gpu")) == 1
    kk.kilit_birak(yol)


def test_sahip_bicimi_ve_bilinmeyen_kaynak_reddedilir():
    with pytest.raises(ValueError):
        kk.kilit_al("gpu", "kimsesiz", "x")
    with pytest.raises(ValueError):
        kk.kilit_al("uzay", "ajan:test", "x")


def test_kaynak_kullan_bekler_bildirir_ve_birakir():
    tutan = kk.kilit_al("gpu", "ajan:test", "tutan")
    bildirimler = []
    with pytest.raises(kk.KaynakMesgulError):
        with kk.kaynak_kullan(["gpu"], "uygulama:test", "bekleyen", bekle_saniye=0.2, aralik_sn=0.05,
                              bekleme_bildir=lambda k, liste: bildirimler.append((k, len(liste)))):
            pass
    assert bildirimler == [("gpu", 1)]
    kk.kilit_birak(tutan)
    with kk.kaynak_kullan(["gpu", "cpu_agir"], "uygulama:test", "alan") as alinan:
        assert len(alinan) == 2
    assert kk.kilitler("gpu") == [] and kk.kilitler("cpu_agir") == []


def test_durum_ve_komut_satiri(capsys):
    assert {k["kaynak"]: k["sinyal"] for k in kk.durum()}["gpu"] == "yesil"
    assert kk.main(["durum"]) == 0
    assert "gpu" in capsys.readouterr().out
    assert kk.main(["calistir", "--kaynak", "gpu", "--sahip", "ajan:test", "--amac", "deneme", "--",
                    sys.executable, "-c", "pass"]) == 0
    assert kk.kilitler("gpu") == []
