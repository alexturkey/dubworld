"""Yerel Telegram Bot API sunucusu ve büyük dosya teslimi (ağsız; gerçek Telegram'a bağlanılmaz).

Kapsam: ayar okuma (`TELEGRAM_YEREL_SUNUCU`), 50 MB / 2000 MB eşikleri, sunucu kapalıyken açık uyarı, yeniden deneme
kuralları (zaman aşımında yeniden yükleme yok), kapsayıcı yolu güvenliği, temizlik kapsamı, `.env` yazımı.
python-telegram-bot gerekmez: hata sınıfları ve bot sahte nesnelerle verilir.
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import teslim
from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import yerel_sunucu as ys
from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu.guvenlik import TelegramAyarHatasi

MB = ys.MB
SAHTE_BELIRTEC = "123456:" + "A" * 35  # biçime uyan sentetik değer


# --- ayar okuma ------------------------------------------------------------------------------------------
def test_adres_bos_ise_bulut(monkeypatch):
    monkeypatch.delenv(ys.ADRES_DEGISKENI, raising=False)
    assert ys.yerel_adres() == ""
    assert ys.gonderme_siniri("") == 50 * MB and ys.indirme_siniri("") == 20 * MB


@pytest.mark.parametrize("deger,beklenen", [
    ("http://127.0.0.1:8081", "http://127.0.0.1:8081"),
    ("http://localhost:8082/", "http://localhost:8082"),
    ("https://bot-api.example.org", "https://bot-api.example.org"),
])
def test_adres_gecerli(monkeypatch, deger, beklenen):
    monkeypatch.setenv(ys.ADRES_DEGISKENI, deger)
    assert ys.yerel_adres() == beklenen
    assert ys.gonderme_siniri(beklenen) == 2000 * MB


@pytest.mark.parametrize("deger", ["http://192.168.1.5:8081", "ftp://127.0.0.1:8081", "127.0.0.1:8081",
                                   "http://127.0.0.1:8081/bot"])
def test_adres_gecersiz(deger):
    with pytest.raises(TelegramAyarHatasi):
        ys.yerel_adres(deger)


def test_env_yaz_tek_anahtari_degistirir(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# yorum\nA=1\nTELEGRAM_YEREL_SUNUCU=\nB=2\n", encoding="utf-8")
    ys.env_yaz(ys.ADRES_DEGISKENI, "http://127.0.0.1:8081", env)
    assert env.read_text(encoding="utf-8").splitlines() == ["# yorum", "A=1", "TELEGRAM_YEREL_SUNUCU=http://127.0.0.1:8081",
                                                             "B=2"]
    ys.env_yaz("YENI", "x", env)
    assert env.read_text(encoding="utf-8").splitlines()[-1] == "YENI=x"


def test_kimlik_eksikse_rehbere_yonlendirir(monkeypatch):
    monkeypatch.delenv(ys.API_ID_DEGISKENI, raising=False)
    monkeypatch.delenv(ys.API_HASH_DEGISKENI, raising=False)
    with pytest.raises(TelegramAyarHatasi, match="my.telegram.org"):
        ys.kimlik_denetimi()
    monkeypatch.setenv(ys.API_ID_DEGISKENI, "12345")
    monkeypatch.setenv(ys.API_HASH_DEGISKENI, "kisa")
    with pytest.raises(TelegramAyarHatasi, match="32"):
        ys.kimlik_denetimi()
    monkeypatch.setenv(ys.API_HASH_DEGISKENI, "0123456789abcdef" * 2)
    ys.kimlik_denetimi()


# --- 50 MB / 2000 MB eşikleri ------------------------------------------------------------------------------
@pytest.mark.parametrize("boyut,adres,uygun,ipucu", [
    (50 * MB, "", True, ""),
    (50 * MB + 1, "", False, "dubla-telegram sunucu kur"),
    (50 * MB + 1, "http://127.0.0.1:8081", True, ""),
    (2000 * MB, "http://127.0.0.1:8081", True, ""),
    (2000 * MB + 1, "http://127.0.0.1:8081", False, "2000 MB"),
    (2000 * MB + 1, "", False, "2000 MB"),
    (0, "", False, "boş"),
])
def test_boyut_denetimi(boyut, adres, uygun, ipucu):
    sonuc, neden = ys.boyut_denetimi(boyut, adres)
    assert sonuc is uygun and ipucu in neden


def test_gonderim_yontemi_video_varsayilan():
    """Video her boyutta önizlemeli video olarak gider; belge yalnız açık istekle."""
    assert teslim.gonderim_yontemi(Path("a.mp4"), 50 * MB) == "send_video"
    assert teslim.gonderim_yontemi(Path("a.mp4"), 1900 * MB) == "send_video"
    assert teslim.gonderim_yontemi(Path("a.mp4"), 10 * MB, belge=True) == "send_document"
    assert teslim.gonderim_yontemi(Path("a.zip"), 1 * MB) == "send_document"


def test_belge_ayari(monkeypatch):
    monkeypatch.delenv(teslim.BICIM_DEGISKENI, raising=False)
    assert teslim.belge_istendi_mi() is False
    assert teslim.belge_istendi_mi("belge") is True and teslim.belge_istendi_mi("video") is False
    with pytest.raises(TelegramAyarHatasi):
        teslim.belge_istendi_mi("zip")


def _kutu(tur: bytes, govde: bytes = b"") -> bytes:
    return (8 + len(govde)).to_bytes(4, "big") + tur + govde


def test_moov_basta_mi(tmp_path):
    basta = tmp_path / "a.mp4"
    basta.write_bytes(_kutu(b"ftyp", b"isom") + _kutu(b"moov", b"x" * 20) + _kutu(b"mdat", b"y" * 50))
    sonda = tmp_path / "b.mp4"
    sonda.write_bytes(_kutu(b"ftyp", b"isom") + _kutu(b"mdat", b"y" * 50) + _kutu(b"moov", b"x" * 20))
    assert teslim.moov_basta_mi(basta) is True and teslim.moov_basta_mi(sonda) is False
    assert teslim.moov_basta_mi(tmp_path / "yok.mp4") is None


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="ffmpeg yok")
def test_onizleme_hazirla_faststart_ve_kucuk_resim(tmp_path):
    import subprocess

    kaynak = tmp_path / "v.mp4"  # faststart'sız (moov sonda) küçük sentetik video
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(kaynak)], check=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert teslim.moov_basta_mi(kaynak) is False
    gecici = tmp_path / "g"
    gecici.mkdir()
    gonderilecek, kucuk, bilgi = teslim.onizleme_hazirla(kaynak, gecici)
    assert gonderilecek != kaynak and teslim.moov_basta_mi(gonderilecek) is True
    assert kucuk is not None and kucuk.stat().st_size <= 200 * 1024
    assert bilgi == {"width": 640, "height": 360, "duration": 2}


def test_zaman_asimlari_sinirli():
    assert teslim.zaman_asimlari(1 * MB) == (121, 120)  # 1 MB / (5 MB/sn × 0,7) × 4 + 120
    yazma, okuma = teslim.zaman_asimlari(100 * MB)
    assert 120 < yazma <= 3600 and okuma == 300
    assert teslim.zaman_asimlari(2000 * MB) == (2405, 600)
    assert teslim.zaman_asimlari(2000 * MB, hiz_mb_sn=1.0) == (3600, 600)  # üst sınır


# --- teslim (sahte bot) -----------------------------------------------------------------------------------
class TgHata(Exception):
    pass


class AgHata(TgHata):
    pass


class ZamanAsimi(AgHata):
    pass


@pytest.fixture()
def siniflar(monkeypatch):
    monkeypatch.setattr(teslim, "hata_siniflari", lambda: (ZamanAsimi, AgHata, TgHata))
    monkeypatch.setattr(teslim, "video_bilgisi", lambda yol: {})
    monkeypatch.setattr(teslim, "onizleme_hazirla", lambda yol, gecici: (yol, None, {"width": 1, "height": 1}))
    monkeypatch.delenv(teslim.BICIM_DEGISKENI, raising=False)
    monkeypatch.setattr(ys, "sunucu_bos_alan", lambda ad=None: None)


class SahteBot:
    def __init__(self, hatalar=()):
        self.hatalar = list(hatalar)
        self.cagrilar = []

    async def _gonder(self, yontem, **kw):
        akim = kw.get("video") or kw.get("document")
        while akim.read(8 * MB):  # dosyanın tamamını okur (gerçek istemci gibi)
            pass
        self.cagrilar.append((yontem, kw))
        if self.hatalar:
            raise self.hatalar.pop(0)
        tur = "video" if yontem == "send_video" else "document"
        return SimpleNamespace(message_id=42, **{tur: SimpleNamespace(file_id="f")})

    async def send_video(self, **kw):
        return await self._gonder("send_video", **kw)

    async def send_document(self, **kw):
        return await self._gonder("send_document", **kw)


def _dosya(tmp_path: Path, ad: str, boyut: int) -> Path:
    yol = tmp_path / ad
    with yol.open("wb") as f:  # seyrek dosya: disk harcamaz
        f.truncate(boyut)
    return yol


def _kos(bot, yol, adres, beklemeler=None):
    async def bekle(sn):
        if beklemeler is not None:
            beklemeler.append(sn)
    return asyncio.run(teslim.dosya_gonder(bot, 1001, yol, baslik="deneme", adres=adres, bekle=bekle))


def test_sunucu_yokken_50mb_ustu_denenmez_ve_uyarir(tmp_path, siniflar):
    bot = SahteBot()
    sonuc = _kos(bot, _dosya(tmp_path, "b.mp4", 60 * MB), "")
    assert not sonuc and sonuc.durum == "needs_local_server" and "sunucu kur" in sonuc.neden
    assert bot.cagrilar == []


def test_2gb_ustu_hic_denenmez(tmp_path, siniflar):
    bot = SahteBot()
    sonuc = _kos(bot, _dosya(tmp_path, "b.mp4", 2000 * MB + 1), "http://127.0.0.1:8081")
    assert sonuc.durum == "too_large" and bot.cagrilar == []


def test_yerel_sunucuyla_buyuk_video_onizlemeli_gider(tmp_path, siniflar):
    bot = SahteBot()
    yol = _dosya(tmp_path, "b.mp4", 60 * MB)
    sonuc = _kos(bot, yol, "http://127.0.0.1:8081")
    assert sonuc and sonuc.mesaj_no == 42 and sonuc.deneme == 1 and sonuc.telegram_turu == "video"
    yontem, kw = bot.cagrilar[0]
    assert yontem == "send_video" and kw["supports_streaming"] is True and kw["width"] == 1
    assert kw["filename"] == "b.mp4" and "thumbnail" in kw
    rapor = json.loads((tmp_path / teslim.RAPOR_ADI).read_text(encoding="utf-8"))
    assert rapor["sonuc"] == "confirmed" and rapor["sunucu"] == "yerel" and rapor["telegram_turu"] == "video"
    assert "1001" not in json.dumps(rapor)  # sohbet kimliği diske yazılmaz
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(["b.mp4", teslim.RAPOR_ADI])  # geçici klasör silindi


def test_belge_istenirse_document(tmp_path, siniflar):
    bot = SahteBot()
    sonuc = asyncio.run(teslim.dosya_gonder(bot, 1, _dosya(tmp_path, "b.mp4", 2 * MB), adres="", belge=True))
    assert sonuc.telegram_turu == "document" and bot.cagrilar[0][0] == "send_document"


def test_kucuk_video_video_olarak_gider(tmp_path, siniflar):
    bot = SahteBot()
    assert _kos(bot, _dosya(tmp_path, "k.mp4", 1 * MB), "")
    assert bot.cagrilar[0][0] == "send_video" and bot.cagrilar[0][1]["supports_streaming"] is True


def test_ag_kopmasi_yeniden_denenir(tmp_path, siniflar):
    """Okuma bitmeden kopan bağlantı (sunucu reddi / ağ) 15 sn sonra yeniden denenir; süreler büyür."""

    class OkumadanKopan(SahteBot):
        async def _gonder(self, yontem, **kw):
            self.cagrilar.append((yontem, kw))
            if len(self.cagrilar) == 1:
                raise AgHata("bağlantı koptu")
            return SimpleNamespace(message_id=7)

    bot, beklemeler = OkumadanKopan(), []
    sonuc = _kos(bot, _dosya(tmp_path, "k.mp4", 1 * MB), "", beklemeler)
    assert sonuc and sonuc.deneme == 2 and beklemeler == [15]
    assert bot.cagrilar[1][1]["write_timeout"] > bot.cagrilar[0][1]["write_timeout"]


def test_uc_denemeden_sonra_durur(tmp_path, siniflar):
    class HepReddeden(SahteBot):
        async def _gonder(self, yontem, **kw):
            self.cagrilar.append(yontem)
            raise TgHata("Bad Request")

    bot, beklemeler = HepReddeden(), []
    sonuc = _kos(bot, _dosya(tmp_path, "k.mp4", 1 * MB), "", beklemeler)
    assert not sonuc and sonuc.durum == "failed" and len(bot.cagrilar) == 3 and beklemeler == [15, 30]


def test_zaman_asiminda_yeniden_yukleme_yok(tmp_path, siniflar):
    """Dosya tamamen okunduktan sonra cevap beklerken zaman aşımı: Telegram almış olabilir → çift teslim olmasın."""
    bot, beklemeler = SahteBot([ZamanAsimi("Timed out")]), []
    sonuc = _kos(bot, _dosya(tmp_path, "b.mp4", 60 * MB), "http://127.0.0.1:8081", beklemeler)
    assert not sonuc and sonuc.durum == "unknown" and len(bot.cagrilar) == 1 and beklemeler == []
    assert "sohbete bakın" in sonuc.neden


def test_buyuk_dosya_cevap_beklerken_koparsa_elle_bakilir(tmp_path, siniflar):
    bot = SahteBot([AgHata("Server disconnected")])
    sonuc = _kos(bot, _dosya(tmp_path, "b.mp4", 60 * MB), "http://127.0.0.1:8081", [])
    assert sonuc.durum == "manual_review" and len(bot.cagrilar) == 1


def test_sunucu_diski_doluysa_denenmez(tmp_path, siniflar, monkeypatch):
    monkeypatch.setattr(ys, "sunucu_bos_alan", lambda ad=None: 10 * MB)
    bot = SahteBot()
    sonuc = _kos(bot, _dosya(tmp_path, "b.mp4", 60 * MB), "http://127.0.0.1:8081")
    assert not sonuc and "temizle" in sonuc.neden and bot.cagrilar == []


# --- sunucu durumu (dubla kontrol) -------------------------------------------------------------------------
class _SahteBotApi(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == f"/bot{SAHTE_BELIRTEC}/getMe":
            govde, kod = {"ok": True, "result": {"id": 1, "is_bot": True}}, 200
        else:
            govde, kod = {"ok": False, "error_code": 401, "description": "Unauthorized"}, 401
        veri = json.dumps(govde).encode()
        self.send_response(kod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(veri)))
        self.end_headers()
        self.wfile.write(veri)

    def log_message(self, *a):
        pass


@pytest.fixture()
def sahte_sunucu():
    sunucu = HTTPServer(("127.0.0.1", 0), _SahteBotApi)
    is_parcacigi = threading.Thread(target=sunucu.serve_forever, daemon=True)
    is_parcacigi.start()
    yield f"http://127.0.0.1:{sunucu.server_address[1]}"
    sunucu.shutdown()
    sunucu.server_close()


def test_kontrol_kapali(monkeypatch):
    monkeypatch.delenv(ys.ADRES_DEGISKENI, raising=False)
    ozet = ys.kontrol_ozeti(belirtec="")
    assert ozet["durum"] == "kapali" and ozet["sinir_mb"] == 50
    assert "50 MB" in ys.kontrol_metni(ozet) and "sunucu kur" in ys.kontrol_metni(ozet)


def test_kontrol_sunucu_kapaliysa_uyarir(monkeypatch):
    port = ys.bos_port(range(18081, 18181))
    monkeypatch.setenv(ys.ADRES_DEGISKENI, f"http://127.0.0.1:{port}")
    ozet = ys.kontrol_ozeti(belirtec=SAHTE_BELIRTEC)
    assert ozet["durum"] == "calismiyor" and ozet["sinir_mb"] == 50
    assert "ÇALIŞMIYOR" in ys.kontrol_metni(ozet) and "sunucu baslat" in ys.kontrol_metni(ozet)


def test_kontrol_hazir_ve_yanlis_belirtec(monkeypatch, sahte_sunucu):
    monkeypatch.setenv(ys.ADRES_DEGISKENI, sahte_sunucu)
    assert ys.kontrol_ozeti(belirtec=SAHTE_BELIRTEC)["durum"] == "hazir"
    assert ys.kontrol_ozeti(belirtec="9:" + "B" * 35)["durum"] == "telegrama_ulasamiyor"
    assert ys.bot_api_mi(sahte_sunucu) is True
    assert ys.hazir_bekle(sahte_sunucu, SAHTE_BELIRTEC, sure=3) is True


def test_kontrol_ayar_hatasi(monkeypatch):
    monkeypatch.setenv(ys.ADRES_DEGISKENI, "http://10.0.0.2:8081")
    ozet = ys.kontrol_ozeti(belirtec="")
    assert ozet["durum"] == "ayar_hatasi" and "AYAR HATASI" in ys.kontrol_metni(ozet)


def test_dubla_kontrol_satiri(capsys):
    from dublaj_hatti import cli

    cli._kontrol_yaz({"surum": "0", "python": "3", "donanim": {}, "ffmpeg": "f", "stt": {}, "ceviri": {}, "tts": {},
                      "ek": {}, "ctc_modelleri": {}, "telegram_sunucu": {"durum": "kapali", "sinir_mb": 50}})
    assert "telegram yerel sunucu: kapalı" in capsys.readouterr().out


def test_dubla_kontrol_telegram_eki_yoksa_cokmez(monkeypatch, capsys):
    """Telegram modülü içe aktarılamazsa `dubla kontrol` çökmez, 'kurulu değil' der."""
    import sys

    from dublaj_hatti import cli

    monkeypatch.setitem(sys.modules, "dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu.yerel_sunucu", None)
    monkeypatch.delattr("dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu.yerel_sunucu", raising=False)
    ozet = cli._telegram_sunucu_ozeti()
    assert ozet == {"durum": "kurulu_degil"}
    cli._kontrol_yaz({"surum": "0", "python": "3", "donanim": {}, "ffmpeg": "f", "stt": {}, "ceviri": {}, "tts": {},
                      "ek": {}, "ctc_modelleri": {}, "telegram_sunucu": ozet})
    assert "telegram eki kurulu değil" in capsys.readouterr().out


# --- port, kip, kurulum planı --------------------------------------------------------------------------------
def test_port_dolu_ise_bos_port_secer(monkeypatch, tmp_path, sahte_sunucu):
    """İstenen port Bot API olmayan bir programdaysa sıradaki boş port seçilir; Bot API ise yeniden kullanılır."""
    monkeypatch.setenv(ys.API_ID_DEGISKENI, "12345")
    monkeypatch.setenv(ys.API_HASH_DEGISKENI, "0123456789abcdef" * 2)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", SAHTE_BELIRTEC)
    monkeypatch.setenv("DUBLAJ_ENV_DOSYASI", str(tmp_path / ".env"))
    monkeypatch.setattr(ys, "docker_yolu", lambda: "docker")
    port = int(sahte_sunucu.rsplit(":", 1)[1])
    plan = ys.kur(port=port, kuru=True)
    assert plan["kip"] == "mevcut" and plan["port"] == port  # çalışan Bot API sunucusu yeniden kurulmaz
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "9:" + "B" * 35)  # aynı port, getMe olmuyor → başka program sayılır
    monkeypatch.setattr(ys, "_bizim_kapsayici_portu", lambda p: False)
    plan = ys.kur(port=port, kuru=True)
    assert plan["kip"] == "docker" and plan["port"] != port
    assert not (tmp_path / ".env").exists()  # kuru çalışma diske yazmaz


def test_kip_secimi(monkeypatch):
    monkeypatch.setattr(ys, "docker_yolu", lambda: "docker")
    assert ys.kip_sec() == "docker"
    monkeypatch.setattr(ys, "docker_yolu", lambda: None)
    monkeypatch.setattr(ys.os, "name", "nt")
    monkeypatch.setattr(ys, "wsl_var", lambda: False)
    with pytest.raises(TelegramAyarHatasi, match="Docker"):
        ys.kip_sec()
    monkeypatch.setattr(ys, "wsl_var", lambda: True)
    assert ys.kip_sec() == "derleme"


def test_sozlesme_denetimi():
    dogru = {"ag": ys.AG, "yerel_kip": True, "host_ip": "127.0.0.1", "host_port": 8081}
    assert ys.sozlesme_uygun(dogru, 8081)
    assert not ys.sozlesme_uygun({**dogru, "host_ip": "0.0.0.0"}, 8081)  # ağa açık port kabul edilmez
    assert not ys.sozlesme_uygun({**dogru, "ag": "bridge"}, 8081)  # IPv6'sız varsayılan köprü
    assert not ys.sozlesme_uygun({**dogru, "yerel_kip": False}, 8081)


def test_kimlik_komut_satirina_yazilmaz(monkeypatch):
    cagrilar = []
    monkeypatch.setenv(ys.API_ID_DEGISKENI, "12345")
    monkeypatch.setenv(ys.API_HASH_DEGISKENI, "0123456789abcdef" * 2)
    monkeypatch.setattr(ys, "ag_kur", lambda ag=ys.AG: None)
    monkeypatch.setattr(ys, "kapsayici_bilgisi", lambda ad=ys.KAPSAYICI: None)
    monkeypatch.setattr(ys, "imaj_hazirla", lambda kaynaktan: "imaj")
    monkeypatch.setattr(ys, "_docker", lambda *a, **kw: cagrilar.append((a, kw)) or SimpleNamespace(returncode=0,
                                                                                                    stdout="", stderr=""))
    ys.kapsayici_kur(8081)
    argumanlar, kw = cagrilar[0]
    assert "0123456789abcdef" * 2 not in " ".join(argumanlar) and "12345" not in " ".join(argumanlar)
    assert ys.API_HASH_DEGISKENI in argumanlar and kw["ortam"][ys.API_HASH_DEGISKENI] == "0123456789abcdef" * 2
    assert "127.0.0.1:8081:8081" in argumanlar and "unless-stopped" in argumanlar


# --- kapsayıcı yolu ve temizlik -------------------------------------------------------------------------------
def test_kapsayici_yolu_guvenligi():
    from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import bot

    kok = ys.KAPSAYICI_IS_KLASORU
    yol = f"{kok}/{SAHTE_BELIRTEC}/videos/file_1.mp4"
    assert bot.kapsayici_dosya_yolu(yol, SAHTE_BELIRTEC) == yol
    assert bot.kapsayici_dosya_yolu(f"http://127.0.0.1:8081/file/bot{SAHTE_BELIRTEC}{yol}", SAHTE_BELIRTEC) == yol
    assert bot.kapsayici_dosya_yolu(f"{kok}/9:baskabot/videos/a.mp4", SAHTE_BELIRTEC) is None
    assert bot.kapsayici_dosya_yolu(f"{kok}/{SAHTE_BELIRTEC}/../../etc/passwd", SAHTE_BELIRTEC) is None
    assert bot.kapsayici_dosya_yolu("videos/file_1.mp4", SAHTE_BELIRTEC) is None
    assert bot.kapsayici_dosya_yolu(None, SAHTE_BELIRTEC) is None


def test_temizlik_bot_veritabanina_dokunmaz():
    komut = ys.temizle_komutu(24)
    assert "-mmin +1440" in komut and "/videos" in komut and "/documents" in komut
    assert "binlog" not in komut and f"{ys.KAPSAYICI_IS_KLASORU}/* " not in komut


def test_uygulama_kurucu_yerel_adres():
    class Kurucu:
        def __init__(self):
            self.ayar = {}

        def __getattr__(self, ad):
            def yaz(deger):
                self.ayar[ad] = deger
                return self
            return yaz

    from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import bot

    bulut = bot.uygulama_kurucu(Kurucu(), "").ayar
    assert "base_url" not in bulut and bulut["write_timeout"] == 600
    yerel = bot.uygulama_kurucu(Kurucu(), "http://127.0.0.1:8081").ayar
    assert yerel["base_url"] == "http://127.0.0.1:8081/bot" and yerel["local_mode"] is True
    assert yerel["base_file_url"] == "http://127.0.0.1:8081/file/bot"


def test_alt_komutlar_bot_olmadan_calisir(monkeypatch, capsys, tmp_path):
    from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import bot

    monkeypatch.setenv("DUBLAJ_ENV_DOSYASI", str(tmp_path / ".env"))
    monkeypatch.delenv(ys.API_ID_DEGISKENI, raising=False)
    monkeypatch.delenv(ys.API_HASH_DEGISKENI, raising=False)
    assert bot.main(["sunucu", "kur", "--kuru"]) == 2
    assert "my.telegram.org" in capsys.readouterr().out
    assert bot.main(["gonder", str(tmp_path / "yok.mp4"), "--sohbet", "1"]) == 2
