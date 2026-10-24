"""İsteğe bağlı geri gelen özellikler: GPU'suz, ağsız birim testleri ve "kurulu değil" mesajları.

Ağır kütüphane gerekenler importorskip ile atlanır (CI yalnız stdlib + paket); RVC, XTTS ve gallery-dl için gerçek
araç yerine sahte komut satırı kullanılır (sözleşme sınaması).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from dublaj_hatti import kayit

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
YENI_MOTORLAR = ("youtube_translate", "xtts", "segment_cinsiyet_kipi", "akilli_kare", "rvc", "gallery_dl",
                 "kapak_gorseli", "telegram_botu")


# --- motor kaydı ------------------------------------------------------------------------------------------
def test_kayit_yeni_satirlar_lisans_ve_bellek_dolu():
    for ad in YENI_MOTORLAR:
        m = kayit.motor(ad)
        assert m.lisans and m.kaynak.startswith("https://") and m.kurulum and m.cihaz and m.bellek
        assert (Path(__file__).resolve().parents[1] / m.belge).is_file(), m.belge


@pytest.mark.parametrize("motor", kayit.MOTORLAR, ids=lambda m: m.ad)
def test_kayittaki_her_motorun_sayfasi_ve_alanlari_var(motor):
    """kayit.MOTORLAR'ın tamamı (K9: 32/32): sayfa var, başlığı motor adını taşır, kayıt alanları dolu."""
    sayfa = Path(__file__).resolve().parents[1] / motor.belge
    assert sayfa.is_file(), motor.belge
    baslik = sayfa.read_text(encoding="utf-8").splitlines()[0]
    assert baslik.startswith("# ") and (f"`{motor.ad}`" in baslik or f"({motor.ad})" in baslik), baslik
    assert motor.lisans and motor.ticari and motor.kaynak.startswith("https://") and motor.kurulum and motor.cihaz


def test_motor_sayfalarinda_kayitsiz_sayfa_yok():
    klasor = Path(__file__).resolve().parents[1] / "docs" / "motorlar"
    sayfalar = {p.stem for p in klasor.glob("*.md") if p.stem.lower() != "readme"}
    assert sayfalar == {m.ad for m in kayit.MOTORLAR}


def test_ticari_olmayan_ve_sartli_uyarilar():
    assert "TİCARİ OLMAYAN" in kayit.lisans_uyarisi("xtts")
    assert "izni" in kayit.lisans_uyarisi("rvc")
    assert kayit.motor("xtts").tur == "tts" and "xtts" in kayit.adlar("tts", auto=False)


def test_kontrol_dusmez():
    for tur in ("stt", "tts", "ek"):
        assert set(kayit.durum(tur)) >= {m.ad for m in kayit.motorlar(tur)}


# --- akıllı kare -------------------------------------------------------------------------------------------
def test_akilli_kare_kurulu_degil_mesaji(monkeypatch):
    from dublaj_hatti.bolum_10_kaynak_edinme import akilli_kare_yakalama as ak

    monkeypatch.setattr(ak, "akilli_kare_kurulu", lambda: False)
    with pytest.raises(ak.AkilliKareKuruluDegil, match="akilli-kare"):
        ak.apply_smart_frame_capture("yok.mp4", ".")


def test_akilli_kare_bantli_videoyu_kirpar(tmp_path):
    pytest.importorskip("cv2")
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg yok")
    from dublaj_hatti.bolum_10_kaynak_edinme.akilli_kare_yakalama import apply_smart_frame_capture

    kaynak = tmp_path / "bantli.mp4"  # 640x360 içerik, üst-alt 60 px siyah bant
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=10",
                    "-t", "3", "-vf", "pad=640:480:0:60:black", "-pix_fmt", "yuv420p", str(kaynak)], check=True,
                   creationflags=NO_WINDOW)
    sonuc = apply_smart_frame_capture(kaynak, tmp_path / "is", enabled=True)
    assert sonuc["status"] == "cropped", sonuc.get("reason")
    assert Path(sonuc["video_path"]).is_file()
    kirp = sonuc["crop_info"]
    assert kirp["source_crop_top"] >= 58 and kirp["source_crop_top"] + kirp["source_crop_height"] <= 422


# --- YouTube json3 ----------------------------------------------------------------------------------------
def test_json3_kelimeleri_ayristirir():
    pytest.importorskip("soundfile")
    from dublaj_hatti.bolum_20_transkripsiyon.youtube_json3_kaynagi.engine import (
        is_youtube_url,
        parse_youtube_json3_words,
    )

    json3 = {"events": [{"tStartMs": 0, "segs": [{"utf8": "Merhaba"}, {"utf8": " dunya", "tOffsetMs": 400}]},
                        {"tStartMs": 1200, "segs": [{"utf8": "[Music]"}]},
                        {"tStartMs": 2000, "segs": [{"utf8": "nasilsin"}]}]}
    kelimeler = parse_youtube_json3_words(json.dumps(json3))
    assert [k["word"] for k in kelimeler] == ["Merhaba", "dunya", "nasilsin"]
    assert kelimeler[1]["start_hint"] == pytest.approx(0.4)
    assert is_youtube_url("https://www.youtube.com/watch?v=ornek") and not is_youtube_url("https://example.com/v")


def test_json3_yt_dlp_yoksa_acik_mesaj(monkeypatch):
    pytest.importorskip("soundfile")
    from dublaj_hatti.bolum_20_transkripsiyon.youtube_json3_kaynagi import engine

    monkeypatch.setitem(sys.modules, "yt_dlp", None)
    with pytest.raises(engine.YouTubeJson3Error, match=r"\.\[youtube\]"):
        engine._extract_info("https://www.youtube.com/watch?v=ornek")


# --- segment bazlı cinsiyet kipi -------------------------------------------------------------------------
def test_segment_cinsiyet_kipi_her_cumleye_ses_atar(monkeypatch, tmp_path):
    pytest.importorskip("torch")
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.cinsiyet_secimi import segment_gender_router as r
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.cinsiyet_secimi.voice_pair import validate_voice_pair

    def sahte_isci(ses, istekler, kip):
        cins = {"1": "female", "2": "male"}
        return {"predictions": [{"request_id": i["request_id"], "gender": cins.get(i["request_id"], "male"),
                                 "confidence": 0.99} for i in istekler]}

    monkeypatch.setattr(r, "run_gender_worker", sahte_isci)
    segler = [SimpleNamespace(index=1, start=0.0, end=2.0), SimpleNamespace(index=2, start=2.5, end=4.0),
              SimpleNamespace(index=3, start=4.1, end=4.2)]  # 3. kısa: en yakın güvenilir komşudan alır
    rapor = r.apply_supertonic_segment_gender_routing(segler, "ses.wav", validate_voice_pair("F2", "M3"), str(tmp_path))
    assert [s.supertonic_voice_id for s in segler] == ["F2", "M3", "M3"]
    assert Path(rapor).is_file()


def test_dubber_segment_kipini_secer(monkeypatch, tmp_path):
    pytest.importorskip("torch")
    from dublaj_hatti.bolum_00_omurga.core import dubber
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts import cinsiyet_secimi

    cagri = {}
    monkeypatch.setattr(cinsiyet_secimi, "apply_supertonic_segment_gender_routing",
                        lambda s, a, p, d: cagri.update(ses=a, cift=(p.female_voice_id, p.male_voice_id)))
    cfg = dubber.DubConfig(tts_engine="supertonic", konusmaci_basina_ses=True, konusmaci_ses_yolu="kaynak.wav",
                           cinsiyet_kipi="segment", supertonic_kadin_ses="F4", supertonic_erkek_ses="M2")
    dubber._apply_konusmaci_basina_ses_if_needed([], cfg, str(tmp_path))
    assert cagri == {"ses": "kaynak.wav", "cift": ("F4", "M2")}


# --- RVC --------------------------------------------------------------------------------------------------
def test_rvc_riza_olmadan_calismaz():
    from dublaj_hatti.bolum_50_seslendirme.rvc_ses_donusturme import RvcRizaHatasi, rvc_ayari_cfgden

    assert rvc_ayari_cfgden(SimpleNamespace(rvc_model_yolu="")) is None
    with pytest.raises(RvcRizaHatasi):
        rvc_ayari_cfgden(SimpleNamespace(rvc_model_yolu="m.pth", rvc_riza_onayi=False))


def test_rvc_kurulu_degil_mesaji(monkeypatch):
    from dublaj_hatti.bolum_50_seslendirme.rvc_ses_donusturme import RvcAyar, RvcKuruluDegil, rvc_karisima_uygula

    pytest.importorskip("numpy")
    import numpy as np

    monkeypatch.delenv("DUBLAJ_RVC_KOK", raising=False)
    assert kayit.durum("ek")["rvc"] is False
    with pytest.raises(RvcKuruluDegil, match="DUBLAJ_RVC_KOK"):
        rvc_karisima_uygula(np.zeros(100, dtype=np.float32), 16000, RvcAyar("m.pth"), ".")


def test_rvc_sahte_cli_ile_uctan_uca(monkeypatch, tmp_path):
    np = pytest.importorskip("numpy")
    pytest.importorskip("soundfile")
    pytest.importorskip("scipy")
    from dublaj_hatti.bolum_50_seslendirme.rvc_ses_donusturme import RvcAyar, komut_olustur, rvc_karisima_uygula

    kok = tmp_path / "rvc"
    (kok / "infer").mkdir(parents=True)
    # resmî infer/cli.py ile aynı argümanlar; sesi 2 kat yükseltip 40 kHz'e çevirir
    (kok / "infer" / "cli.py").write_text(textwrap.dedent("""
        import argparse, soundfile as sf
        from scipy.signal import resample_poly
        p = argparse.ArgumentParser()
        for a in ("--model", "--input", "--output", "--pitch", "--f0-method", "--index", "--index-rate",
                  "--rms-mix-rate", "--protect", "--format"):
            p.add_argument(a)
        p.add_argument("--overwrite", action="store_true")
        a = p.parse_args()
        x, sr = sf.read(a.input, dtype="float32")
        sf.write(a.output, resample_poly(x * 2, 5, 2), 40000)
    """), encoding="utf-8")
    model = tmp_path / "kendi_modelim.pth"
    model.write_bytes(b"0")
    monkeypatch.setenv("DUBLAJ_RVC_KOK", str(kok))
    monkeypatch.setenv("DUBLAJ_RVC_PYTHON", sys.executable)
    sr = 16000
    ses = np.concatenate([np.zeros(sr, dtype=np.float32), 0.2 * np.ones(sr, dtype=np.float32)])
    cikti = rvc_karisima_uygula(ses, sr, RvcAyar(str(model)), tmp_path / "is")
    assert len(cikti) == len(ses)
    assert float(np.abs(cikti[: sr // 2]).max()) == 0.0  # kaynaktaki sessizlik korunur
    assert float(np.median(cikti[sr + 1000:])) == pytest.approx(0.4, abs=0.02)
    assert json.loads((tmp_path / "is" / "rvc" / "rvc_rapor.json").read_text(encoding="utf-8"))["model_yolu"] == model.name
    komut = komut_olustur("py", "cli.py", "g.wav", "c.wav", RvcAyar("m.pth", index_yolu="i.index", perde=-3))
    assert komut[komut.index("--pitch") + 1] == "-3" and "--index" in komut


# --- XTTS ------------------------------------------------------------------------------------------------
def _xtts_kok(monkeypatch, tmp_path):
    from dublaj_hatti.bolum_50_seslendirme.xtts_tts import lisans

    monkeypatch.setattr(lisans, "xtts_kok", lambda: tmp_path / "xtts")
    return lisans


def test_xtts_lisans_onayi_ve_kurulu_degil(monkeypatch, tmp_path):
    lisans = _xtts_kok(monkeypatch, tmp_path)
    from dublaj_hatti.bolum_50_seslendirme.xtts_tts import api

    monkeypatch.setenv("DUBLAJ_XTTS_PYTHON", str(tmp_path / "yok" / "python.exe"))
    with pytest.raises(api.XttsHatasi, match=r"\.\[tts-xtts\]"):
        api.on_denetim(SimpleNamespace(xtts_referans_ses="", target_lang="tr"))
    monkeypatch.setenv("DUBLAJ_XTTS_PYTHON", sys.executable)
    with pytest.raises(api.XttsHatasi, match="CPML"):
        api.on_denetim(SimpleNamespace(xtts_referans_ses="", target_lang="tr"))
    assert not lisans.lisans_onayli()
    lisans.lisans_onayini_kaydet()
    assert lisans.lisans_onayli()
    with pytest.raises(api.XttsHatasi, match="referans ses gerekli"):
        api.on_denetim(SimpleNamespace(xtts_referans_ses="", target_lang="tr"))
    with pytest.raises(api.XttsHatasi, match="desteklemiyor"):
        api.xtts_dil_kodu("fi")


def test_xtts_onay_komutu_sozsuz_reddeder(monkeypatch, tmp_path):
    lisans = _xtts_kok(monkeypatch, tmp_path)
    from dublaj_hatti.bolum_50_seslendirme.xtts_tts.__main__ import main

    monkeypatch.setattr("builtins.input", lambda _: "evet")
    assert main(["onay"]) == 1 and not lisans.lisans_onayli()
    assert main(["onay", "--kabul"]) == 0 and lisans.lisans_onayli()


def test_xtts_kosucu_onaysiz_calismaz(tmp_path):
    kosucu = Path(__file__).resolve().parents[1] / "src/dublaj_hatti/bolum_50_seslendirme/xtts_tts/kosucu.py"
    env = {k: v for k, v in __import__("os").environ.items() if k != "COQUI_TOS_AGREED"}
    tamam = subprocess.run([sys.executable, str(kosucu), "--is", "x", "--sonuc", "y"], env=env,
                           capture_output=True, text=True, creationflags=NO_WINDOW)
    assert tamam.returncode == 3 and "CPML" in tamam.stderr


def test_xtts_sahte_coqui_ile_uctan_uca(monkeypatch, tmp_path):
    pytest.importorskip("torch")
    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")
    _xtts_kok(monkeypatch, tmp_path).lisans_onayini_kaydet()
    sahte = tmp_path / "sahte_paket" / "TTS"
    sahte.mkdir(parents=True)
    (sahte / "__init__.py").write_text("", encoding="utf-8")
    (sahte / "api.py").write_text(textwrap.dedent("""
        import numpy as np
        class TTS:
            def __init__(self, ad, progress_bar=False):
                assert ad.endswith("xtts_v2")
                self.synthesizer = type("S", (), {"output_sample_rate": 24000})()
            def to(self, cihaz):
                return self
            def tts(self, text, speaker_wav, language):
                assert language == "tr"
                return (0.1 * np.sin(np.linspace(0, 400, 24000))).tolist()
    """), encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(sahte.parent))
    monkeypatch.setenv("DUBLAJ_XTTS_PYTHON", sys.executable)
    referans = tmp_path / "kendi_sesim.wav"
    sf.write(str(referans), np.zeros(24000, dtype=np.float32), 24000)
    from dublaj_hatti.bolum_00_omurga.core.dubber import DubConfig
    from dublaj_hatti.bolum_50_seslendirme.xtts_tts import build_xtts_dubbed_audio

    cfg = DubConfig(tts_engine="xtts", xtts_referans_ses=str(referans), target_lang="tr")
    segler = [SimpleNamespace(index=1, start=0.0, end=1.2, text="Merhaba dünya.", words=[], speaker=""),
              SimpleNamespace(index=2, start=1.5, end=2.8, text="İkinci cümle.", words=[], speaker="")]
    try:
        sonuc = build_xtts_dubbed_audio(segler, cfg, str(tmp_path / "is"))
    except AttributeError as hata:  # Supertonic hazırlayıcı tam Segment ister; sözleşme farkı burada görünür
        pytest.fail(f"Segment sözleşmesi: {hata}")
    assert set(sonuc.segment_audios) == {1, 2}
    assert len(sonuc.audio) > 0


# --- gallery-dl -------------------------------------------------------------------------------------------
def test_galeri_adres_ve_komut(monkeypatch):
    from dublaj_hatti.bolum_10_kaynak_edinme.adim_20_kaynak_alma import galeri_indirici as g

    assert g.galeri_adresi_mi("https://www.instagram.com/reel/ornek/")
    assert not g.galeri_adresi_mi("http://www.instagram.com/reel/ornek/")
    assert not g.galeri_adresi_mi("https://instagram.com.kotu.example/x")
    komut = g.komut_olustur(["gallery-dl"], "https://www.instagram.com/reel/ornek/", Path("hedef"), "ayar.conf")
    assert komut[-2:] == ["--", "https://www.instagram.com/reel/ornek/"] and "--destination" in komut
    monkeypatch.setenv("DUBLAJ_GALLERY_DL", "")
    monkeypatch.setattr(g.shutil, "which", lambda _: None)
    monkeypatch.setattr("importlib.util.find_spec", lambda ad: None)
    assert g.galeri_komutu() is None
    with pytest.raises(g.GaleriIndiriciHatasi, match=r"\.\[galeri\]"):
        g.indir("https://www.instagram.com/reel/ornek/", ".")


def test_galeri_kod_ice_aktarmaz():
    kaynak = (Path(__file__).resolve().parents[1] / "src/dublaj_hatti/bolum_10_kaynak_edinme/adim_20_kaynak_alma/"
              "galeri_indirici.py").read_text(encoding="utf-8")
    assert "import gallery_dl" not in kaynak and "from gallery_dl" not in kaynak


# --- kapak görseli ----------------------------------------------------------------------------------------
def test_kapak_codex_yoksa_atlanir(monkeypatch, tmp_path):
    from dublaj_hatti.bolum_70_gorsel_uretim.kapak_gorseli import codex_kapak as k

    monkeypatch.setenv("CODEX_BRIDGE_CODEX_BIN", "")
    monkeypatch.setattr(k.shutil, "which", lambda _: None)
    with pytest.raises(k.KapakHatasi) as hata:
        k.kapak_uret("bir transkript", tmp_path)
    assert hata.value.kod == "codex_yok"


def test_kapak_komutu_ve_sonuc_dogrulama(tmp_path):
    pil = pytest.importorskip("PIL.Image")
    from dublaj_hatti.bolum_70_gorsel_uretim.kapak_gorseli import codex_kapak as k

    komut = k.komut_olustur(["codex"], tmp_path / "is", tmp_path / "s.json", tmp_path / "m.json")
    assert komut[:2] == ["codex", "exec"] and "shell_tool" in komut and komut[-1] == "-"
    assert komut[komut.index("--sandbox") + 1] == "workspace-write"
    # yazma izni yalnız iş klasörüne (çıktı klasörü Codex'e verilmez)
    assert komut[komut.index("--add-dir") + 1] == komut[komut.index("--cd") + 1] == str(tmp_path / "is")
    calisma = tmp_path / "calisma"
    calisma.mkdir()
    pil.new("RGB", (900, 1600), "navy").save(calisma / "a.png")
    pil.new("RGB", (1600, 1600), "navy").save(calisma / "kare.png")
    iyi = {"status": "success", "images": [{"variant_index": 1, "cover_text": "Örnek", "self_check": {"safe_area": True},
                                            "artifact": {"path": str(calisma / "a.png"), "mime_type": "image/png"}}]}
    sonuc = k.sonucu_dogrula(iyi, calisma, tmp_path, 1)
    assert Path(sonuc[0]["yol"]).name == "kapak_01_9x16.png" and sonuc[0]["yukseklik"] == 1600
    iyi["images"][0]["artifact"]["path"] = str(calisma / "kare.png")
    with pytest.raises(k.KapakHatasi, match="9:16"):
        k.sonucu_dogrula(iyi, calisma, tmp_path, 1)
    disari = {"status": "success", "images": [{"variant_index": 1, "cover_text": "", "self_check": {"safe_area": True},
                                               "artifact": {"path": sys.executable, "mime_type": "image/png"}}]}
    with pytest.raises(k.KapakHatasi, match="dosyasını vermedi"):  # iş klasörü dışındaki dosya kabul edilmez
        k.sonucu_dogrula(disari, calisma, tmp_path, 1)


# --- Telegram botu ----------------------------------------------------------------------------------------
def test_telegram_guvenlik():
    from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import guvenlik as g

    assert g.izinli_kullanicilar("111, 222;333") == frozenset({111, 222, 333})
    with pytest.raises(g.TelegramAyarHatasi):
        g.izinli_kullanicilar("ali")
    with pytest.raises(g.TelegramAyarHatasi, match="boş"):
        g.belirteci_al("")
    sahte = "123456:" + "A" * 35
    assert g.belirteci_al(sahte) == sahte and "<belirtec>" in g.gizle(f"hata {sahte}")
    assert g.yetkili_mi(111, frozenset({111})) and not g.yetkili_mi(None, frozenset({111}))


def test_telegram_izinli_liste_bossa_baslamaz(monkeypatch):
    from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import guvenlik as g

    monkeypatch.setenv(g.BELIRTEC_DEGISKENI, "123456:" + "B" * 35)
    monkeypatch.setenv(g.IZINLI_DEGISKENI, "")
    with pytest.raises(g.TelegramAyarHatasi, match="izinli|IZINLI"):
        g.baslatma_denetimi()


def test_telegram_kurulu_degil_mesaji(monkeypatch, capsys):
    from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import bot

    monkeypatch.setitem(sys.modules, "telegram", None)
    assert bot.main([]) == 2
    assert ".[telegram]" in capsys.readouterr().out


def test_telegram_menu_sema_ile_ayni():
    from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import menuler
    from dublaj_hatti.is_yurutucu import ayar_formu

    ogeler = menuler.menu_ogeleri(ayar_formu())
    i = next(n for n, o in enumerate(ogeler) if o["anahtar"] == "ses.motor")
    tur, (anahtar, deger) = menuler.geri_cagirma_coz(f"d:{i}:0", ogeler)
    assert tur == "deger" and anahtar == "ses.motor" and deger in kayit.adlar("tts", auto=False)
    assert all(len(v.encode()) <= 64 for o in ogeler for _, v in menuler.deger_dugmeleri(ogeler, o))
    assert menuler.geri_cagirma_coz("d:999:0", ogeler)[0] == "kapat"


def test_telegram_arka_uc_tek_is():
    from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu.arka_uc import YurutucuArkaUcu
    from dublaj_hatti.is_yurutucu import IsDurumu

    class Sahte:
        def __init__(self):
            self.durum, self.calisan, self.durduruldu = IsDurumu(), False, False

        def calisiyor(self):
            return self.calisan

        def baslat(self, kaynak, ayarlar):
            self.durum, self.calisan = IsDurumu(durum="calisiyor", kaynak=kaynak), True

        def durdur(self):
            self.durduruldu, self.calisan = True, False

    s = Sahte()
    uc = YurutucuArkaUcu(s)
    is_id = uc.baslat("v.mp4", {})
    assert uc.durum(is_id)["durum"] == "calisiyor"
    with pytest.raises(RuntimeError):
        uc.baslat("v2.mp4", {})
    assert uc.iptal(is_id) and s.durduruldu
    assert uc.durum("99")["durum"] == "yok" and uc.liste()[0]["is_id"] == is_id
