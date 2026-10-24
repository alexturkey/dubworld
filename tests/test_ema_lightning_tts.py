"""EMA Lightning TTS: pins, device choice and fallback, settings rules, full-text contract (GPU-free, offline).

The real engine runs only in the `slow` test (CPU ONNX path, needs `kur.ps1 -Adim tts-ema`); everything else uses
fakes and the standard library.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from dublaj_hatti import kayit
from dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts import api, ayarlar, kosucu
from dublaj_hatti.yapilandirma import SEMA, AyarHatasi, ayarlari_yukle, uyumluluk_denetle

KOK = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((KOK / "scripts" / "modeller.json").read_text(encoding="utf-8"))["dosyalar"]


def _bulgular(*ifadeler: str, seviye: str) -> list[str]:
    ayar = ayarlari_yukle(None, ["ceviri.arka_uc=codex"])
    for ifade in ifadeler:
        anahtar, deger = ifade.split("=", 1)
        ayar[anahtar] = deger
    return [str(b) for b in uyumluluk_denetle(ayar) if b.seviye == seviye]


# --- sabitler: tek doğruluk kaynağı ------------------------------------------------------------------------------
def test_agirlik_ozetleri_her_yerde_ayni():
    assert kosucu.AGIRLIK_SHA256 == ayarlar.EMA_AGIRLIK_SHA256
    satirlar = {Path(k["hedef"]).name: k for k in MANIFEST if k["adim"] == "tts-ema"}
    assert set(satirlar) == {"README.md", "config.json", "ema.pt", "decoder.pt"}
    for ad, ozet in ayarlar.EMA_AGIRLIK_SHA256.items():
        assert satirlar[ad]["sha256"] == ozet
    for satir in satirlar.values():
        assert ayarlar.EMA_HF_COMMIT in satir["url"] and satir["url"].startswith("https://huggingface.co/")
        assert satir["lisans"] == "Apache-2.0"


def test_kayit_ve_kilit_uyumlu():
    motor = kayit.motor("ema_lightning")
    assert motor.tur == "tts" and motor.cihaz == "gpu+cpu" and motor.ticari == "evet"
    assert kayit.EMA_DILLERI == ayarlar.EMA_DILLERI == frozenset({"tr"})
    assert kosucu.ORNEKLEME == ayarlar.EMA_ORNEKLEME
    for kilit in ("ek_tts_ema.txt", "ek_tts_ema_cpu.txt"):
        metin = (KOK / "requirements" / kilit).read_text(encoding="utf-8")
        assert f"ema-lightning=={ayarlar.EMA_PAKET_SURUMU}" in metin and "--hash=sha256:" in metin


def test_kur_betigi_adimi_ve_kontrol():
    kur = (KOK / "scripts" / "kur.ps1").read_text(encoding="utf-8-sig")
    assert 'Adim "tts-ema"' in kur and "ek_tts_ema_cpu.txt" in kur and "--adim tts-ema" in kur
    assert "ema_lightning_tts aktar" in kur


# --- ayarlar ve uyumluluk -------------------------------------------------------------------------------------
def test_sema_ve_varsayilanlar():
    ayar = ayarlari_yukle()
    assert SEMA["ses.ema_cihaz"] == ["auto", "cuda", "cpu"]
    assert ayar["ses.ema_cihaz"] == "auto" and ayar["ses.ema_hiz"] == 1.0 and ayar["ses.ema_tohum"] == 0
    with pytest.raises(AyarHatasi):
        ayarlari_yukle(None, ["ses.ema_hiz=3.0"])
    with pytest.raises(AyarHatasi):
        ayarlari_yukle(None, ["ses.ema_cihaz=tpu"])


def test_yalniz_turkce_okur():
    assert not [h for h in _bulgular("ses.motor=ema_lightning", "genel.hedef_dil=tr", seviye="hata")
                if "okuyamaz" in h]
    hatalar = _bulgular("ses.motor=ema_lightning", "genel.hedef_dil=de", seviye="hata")
    assert any("dilini okuyamaz" in h for h in hatalar)
    assert kayit.tts_dil_suzgeci()["ema_lightning"]["izinli"] == ["tr"]


def test_tam_metin_kipi_ema_ile_acik_baska_motorla_kapali():
    assert not [h for h in _bulgular("ses.motor=ema_lightning", "genel.dublaj_kipi=full_text", seviye="hata")
                if "full_text" in h]
    assert any("full_text" in h for h in _bulgular("ses.motor=voxcpm2", "genel.dublaj_kipi=full_text",
                                                   seviye="hata"))


def test_cuda_ve_genel_cpu_celiskisi():
    hatalar = _bulgular("ses.motor=ema_lightning", "ses.ema_cihaz=cuda", "genel.cihaz=cpu", seviye="hata")
    assert any("ses.ema_cihaz" in h for h in hatalar)


# --- cihaz seçimi ve düşüş -------------------------------------------------------------------------------------
@pytest.fixture
def onnx_hazir(monkeypatch):
    durum = {"hazir": True}
    monkeypatch.setattr(api, "_onnx_durumu", lambda: {"hazir": durum["hazir"], "kok": "x", "aktarim": {}})
    return durum


@pytest.mark.parametrize(("bos", "beklenen"), [(-1, "onnx-cpu"), (300, "onnx-cpu"), (3900, "torch-cuda")])
def test_auto_gpu_yok_ya_da_mesgulse_islemci(monkeypatch, onnx_hazir, bos, beklenen):
    monkeypatch.setattr(api, "gpu_bos_mb", lambda: bos)
    assert api.cihaz_sec("auto")[0] == beklenen


def test_onnx_yoksa_islemcide_torch(monkeypatch, onnx_hazir):
    onnx_hazir["hazir"] = False
    monkeypatch.setattr(api, "gpu_bos_mb", lambda: -1)
    assert api.cihaz_sec("auto")[0] == "torch-cpu"
    assert api.cihaz_sec("cpu")[0] == "torch-cpu"


def test_cpu_secimi_ve_genel_cpu_gpuya_bakmaz(monkeypatch, onnx_hazir):
    monkeypatch.setattr(api, "gpu_bos_mb", lambda: pytest.fail("GPU sorgulanmamalı"))
    assert api.cihaz_sec("cpu")[0] == "onnx-cpu"
    assert api.cihaz_sec("auto", "cpu")[0] == "onnx-cpu"


def test_cuda_istendi_gpu_yok_acik_hata(monkeypatch, onnx_hazir):
    monkeypatch.setattr(api, "gpu_bos_mb", lambda: -1)
    with pytest.raises(api.EMAHatasi, match="cuda"):
        api.cihaz_sec("cuda")


@pytest.fixture
def kurulu(monkeypatch, onnx_hazir):
    monkeypatch.setattr(api, "ema_durumu", lambda: {"kurulu": True, "paket": True, "agirlik": True,
                                                    "agirlik_kok": "x"})


def test_gpu_kosusu_duserse_islemcide_bir_kez_tekrar(monkeypatch, kurulu, tmp_path):
    monkeypatch.setattr(api, "gpu_bos_mb", lambda: 3900)
    yollar = []

    def kosucu_sahte(yol, parcalar, hiz, tohum, calisma):
        yollar.append(yol)
        if yol == "torch-cuda":
            raise api.EMAHatasi("CUDA out of memory")
        return {"wavlar": {}, "yol": yol}

    monkeypatch.setattr(api, "_kosucu_calistir", kosucu_sahte)
    ozet = api.ema_oku([{"index": 1, "text": "Merhaba."}], {"ses.ema_cihaz": "auto"}, tmp_path)
    assert yollar == ["torch-cuda", "onnx-cpu"] and "düştü" in ozet["gerekce"]


def test_cuda_acikca_istendiyse_dusus_yok(monkeypatch, kurulu, tmp_path):
    monkeypatch.setattr(api, "gpu_bos_mb", lambda: 3900)

    def kosucu_sahte(yol, *_):
        raise api.EMAHatasi("CUDA out of memory")

    monkeypatch.setattr(api, "_kosucu_calistir", kosucu_sahte)
    with pytest.raises(api.EMAHatasi):
        api.ema_oku([{"index": 1, "text": "Merhaba."}], {"ses.ema_cihaz": "cuda"}, tmp_path)


def test_kurulu_degilse_kurulum_adimini_soyler(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "ema_durumu", lambda: {"kurulu": False, "paket": False, "agirlik": False,
                                                    "agirlik_kok": "x"})
    with pytest.raises(api.EMAHatasi, match="tts-ema"):
        api.ema_oku([{"index": 1, "text": "Merhaba."}], {}, tmp_path)


def test_ayarlar_cfgden_ve_sozlukten_okunur():
    class Cfg:
        ema_cihaz, ema_hiz, ema_tohum, device = "cpu", 1.2, 5, "cuda"

    assert api._al(Cfg(), "ema_hiz", "ses.ema_hiz", 1.0) == 1.2
    assert api._al({"ses.ema_tohum": 9}, "ema_tohum", "ses.ema_tohum", 0) == 9
    assert api._al({}, "ema_tohum", "ses.ema_tohum", 0) == 0


# --- ağırlık kapısı ve tam metin sözleşmesi ---------------------------------------------------------------------
def test_agirlik_kapisi_yanlis_dosyayi_yuklemez(tmp_path):
    (tmp_path / "ema.pt").write_bytes(b"degistirilmis")
    with pytest.raises(kosucu.AgirlikHatasi, match="sha256"):
        kosucu.dogrulanmis_bayt(tmp_path, "ema.pt")
    with pytest.raises(kosucu.AgirlikHatasi, match="tts-ema"):
        kosucu.dogrulanmis_bayt(tmp_path, "decoder.pt")


def test_tam_metin_parcalari_hizalama_penceresiyle_uyumlu(monkeypatch, tmp_path):
    from dublaj_hatti.bolum_00_omurga.full_metin_dublaji import build_full_text_alignment_windows

    def oku_sahte(metin, cfg, calisma):
        cumleler = api.cumlelere_bol(metin)
        return [(c, np.full(4800 * (i + 1), 0.1, np.float32)) for i, c in enumerate(cumleler)], 12000

    monkeypatch.setattr(api, "metni_oku", oku_sahte)
    sentez = api.synthesize_full_text_ema("Birinci cümle. İkinci cümle! Üçüncü?", object(), str(tmp_path))
    assert sentez.sample_rate == 48000 and sentez.chunk_count == 3
    assert len(sentez.audio) == 4800 * 6 + 12000 * 2
    pencereler = build_full_text_alignment_windows(sentez, sentez.audio)
    assert [p["text"] for p in pencereler] == ["Birinci cümle.", "İkinci cümle!", "Üçüncü?"]


@pytest.mark.slow
@pytest.mark.skipif(importlib.util.find_spec("ema_lightning") is None, reason="kur.ps1 -Adim tts-ema")
def test_gercek_islemci_onnx_okumasi(tmp_path):
    durum = api.ema_durumu()
    if not (durum["kurulu"] and durum["onnx_cpu"]):
        pytest.skip("EMA ağırlığı ya da ONNX dışa aktarımı yok (kur.ps1 -Adim tts-ema)")
    ozet = api._kosucu_calistir("onnx-cpu", [{"index": 1, "text": "Merhaba, bu bir denemedir."}], 1.0, 0, tmp_path)
    import soundfile as sf

    dalga, oran = sf.read(ozet["wavlar"]["1"], dtype="float32")
    assert oran == 48000 and 0.8 < len(dalga) / oran < 6 and float(np.abs(dalga).max()) > 0.05
