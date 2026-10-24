"""Telegram'a dosya teslimi (bot ve `dubla-telegram gonder` aynı yolu kullanır).

Kurallar (yerel sunucuyla büyük dosya gönderiminde oturmuş akış; gerekçe: ADR 0018):
- Boyut göndermeden önce denetlenir: 2000 MB üstü hiç denenmez; yerel sunucu yokken 50 MB üstü açık uyarıyla durur.
- Video varsayılan olarak `sendVideo` ile gider (sınıra kadar her boyutta): sohbette önizlemeli, akışla oynatılabilir
  video olur. Önizleme koşulları: `supports_streaming`, ffprobe'dan genişlik/yükseklik/süre, ffmpeg ile küçük resim
  (en çok 320 px JPEG), MP4 kapsayıcı ve `moov` atomu başta (faststart; değilse kodlama değişmeden geçici kopya).
  `sendDocument` yalnız açıkça istenirse (`--belge`, `TELEGRAM_TESLIM_BICIMI=belge`) ve video olmayan dosyada.
- Zaman aşımı dosya boyutundan hesaplanır (varsayılan hız 5 MB/sn, %70 verim, 4 kat pay + 120 sn; 120-3600 sn).
- En çok 3 deneme, aralar 15 / 30 / 60 sn; her yeni denemede yazma süresi ×1,5, okuma süresi ×1,2.
- Zaman aşımı (`TimedOut`) yeniden DENENMEZ: dosya Telegram'a ulaşmış ama cevap gelmemiş olabilir; yeniden yükleme
  aynı dosyayı iki kez teslim eder. Sonuç "unknown" (belirsiz) olarak raporlanır.
- Dosyanın tamamı okunduktan sonra cevap beklerken kopan büyük dosya (≥ 50 MB) da yeniden gönderilmez:
  "manual_review" (sohbete bakılır). Okuma bitmeden kopan bağlantı yeniden denenir.
- Teslim yalnız Telegram'ın döndürdüğü mesajla "confirmed" sayılır. Her denemenin kaydı iş klasöründe
  `telegram_teslim_raporu.json` dosyasına atomik yazılır (sohbet/kullanıcı kimliği yazılmaz).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import yerel_sunucu as ys
from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu.guvenlik import (
    TelegramAyarHatasi,
    belirteci_al,
    gizle,
    izinli_kullanicilar,
)

VIDEO_UZANTILARI = {".mp4", ".mkv", ".mov", ".webm", ".avi"}
AZAMI_DENEME = 3
BEKLEMELER = (15, 30, 60)
RAPOR_ADI = "telegram_teslim_raporu.json"
VARSAYILAN_HIZ_MB_SN = 5.0
_GIZLI = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


class _YerTutucuHata(Exception):
    pass


def hata_siniflari() -> tuple[type, type, type]:
    """(TimedOut, NetworkError, TelegramError). python-telegram-bot yoksa eşleşmeyen yer tutucular (testler)."""
    try:
        from telegram.error import NetworkError, TelegramError, TimedOut
    except ImportError:
        return _YerTutucuHata, _YerTutucuHata, _YerTutucuHata
    return TimedOut, NetworkError, TelegramError


@dataclass
class TeslimSonucu:
    gonderildi: bool
    durum: str  # confirmed · unknown · manual_review · failed · too_large · needs_local_server
    neden: str
    mesaj_no: int | None = None
    deneme: int = 0
    sure_sn: float = 0.0
    bayt: int = 0
    rapor: str = ""
    telegram_turu: str = ""  # Telegram'ın kaydettiği tür: video (önizlemeli) · document

    def __bool__(self) -> bool:
        return self.gonderildi


def zaman_asimlari(boyut: int, hiz_mb_sn: float = VARSAYILAN_HIZ_MB_SN) -> tuple[int, int]:
    """(yazma, okuma) saniye. Hız bilinmez varsayılır; pay geniş tutulur ki yavaş hatta büyük dosya kesilmesin."""
    mb = boyut / ys.MB
    tahmini = mb / (hiz_mb_sn * 0.7)
    yazma = min(max(int(tahmini * 4.0 + 120), 120), 3600)
    okuma = 120 if mb < 50 else 300 if mb < 200 else 600
    return yazma, okuma


BICIM_DEGISKENI = "TELEGRAM_TESLIM_BICIMI"  # video (varsayılan) · belge


def belge_istendi_mi(deger: str | None = None) -> bool:
    ham = (os.environ.get(BICIM_DEGISKENI, "") if deger is None else deger).strip().lower()
    if ham not in ("", "video", "belge", "document"):
        raise TelegramAyarHatasi(f"{BICIM_DEGISKENI} yalnız video ya da belge olur")
    return ham in ("belge", "document")


def gonderim_yontemi(yol: Path, boyut: int, belge: bool = False) -> str:
    """Video her boyutta sendVideo (sınır boyut denetiminde); belge yalnız açık istekle ya da video olmayan dosyada."""
    return "send_video" if yol.suffix.lower() in VIDEO_UZANTILARI and not belge else "send_document"


def moov_basta_mi(yol: Path) -> bool | None:
    """MP4/MOV üst düzey kutuları: `moov` `mdat`'tan önceyse True (faststart). Okunamazsa None."""
    try:
        with yol.open("rb") as f:
            konum, son = 0, yol.stat().st_size
            while konum + 8 <= son:
                f.seek(konum)
                baslik = f.read(16)
                boy, tur = int.from_bytes(baslik[:4], "big"), baslik[4:8]
                if boy == 1:
                    boy = int.from_bytes(baslik[8:16], "big")
                elif boy == 0:
                    boy = son - konum
                if tur == b"moov":
                    return True
                if tur == b"mdat":
                    return False
                if boy < 8:
                    return None
                konum += boy
    except OSError:
        return None
    return None


def onizleme_hazirla(yol: Path, gecici: Path) -> tuple[Path, Path | None, dict[str, Any]]:
    """(gönderilecek dosya, küçük resim ya da None, sendVideo ek alanları). ffmpeg/ffprobe yoksa dosya olduğu gibi
    gider (Telegram yine video olarak alır, önizleme alanları eksik kalır). Yeniden kodlama YOK: kalite değişmez."""
    bilgi = video_bilgisi(yol)
    ffmpeg = shutil.which("ffmpeg")
    gonderilecek = yol
    if ffmpeg and (yol.suffix.lower() not in (".mp4", ".mov") or moov_basta_mi(yol) is False):
        kopya = gecici / f"{yol.stem}.mp4"
        sonuc = subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-y", "-i", str(yol), "-map", "0", "-c", "copy",
                                "-movflags", "+faststart", str(kopya)], capture_output=True, timeout=1800, **_GIZLI)
        if sonuc.returncode == 0 and kopya.exists():
            gonderilecek = kopya
    kucuk = None
    if ffmpeg:
        resim = gecici / "kucuk_resim.jpg"
        an = max(0.0, min(1.0, float(bilgi.get("duration") or 0) / 2))
        sonuc = subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-y", "-ss", f"{an:.2f}", "-i", str(yol),
                                "-frames:v", "1", "-vf", "scale='min(320,iw)':-2", "-q:v", "5", str(resim)],
                               capture_output=True, timeout=120, **_GIZLI)
        if sonuc.returncode == 0 and resim.exists() and resim.stat().st_size <= 200 * 1024:  # Bot API sınırı
            kucuk = resim
    return gonderilecek, kucuk, {k: v for k, v in bilgi.items() if v}


def _simdi() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _rapor_yaz(yol: Path | None, rapor: dict[str, Any]) -> None:
    if yol is None:
        return
    gecici = yol.with_name(yol.name + ".tmp")
    gecici.write_text(json.dumps(rapor, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(gecici, yol)


class IlerlemeDosyasi:
    """Dosya okuma ilerlemesini rapora yazar. Ölçülen, istemcinin okuduğu bayttır; Telegram'ın aldığının kanıtı
    değildir. Okuma bitince deneme 'waiting_for_response' olur: bundan sonraki kopma belirsiz teslim sayılır."""

    def __init__(self, ham: Any, deneme: dict[str, Any], toplam: int, yaz: Callable[[], None]) -> None:
        self.ham, self.deneme, self.toplam, self._yaz = ham, deneme, toplam, yaz
        self.okunan = 0
        self._son_bayt, self._son_an, self._basla = 0, time.monotonic(), time.monotonic()
        self.name = getattr(ham, "name", "")

    def read(self, boyut: int = -1) -> bytes:
        veri = self.ham.read(boyut)
        self.okunan += len(veri or b"")
        self._guncelle(not veri)
        return veri

    def seek(self, *a: Any) -> int:
        return self.ham.seek(*a)

    def tell(self) -> int:
        return self.ham.tell()

    def close(self) -> None:
        self.ham.close()

    def readable(self) -> bool:
        return True

    def _guncelle(self, zorla: bool) -> None:
        simdi = time.monotonic()
        if not zorla and self.okunan - self._son_bayt < 5 * ys.MB and simdi - self._son_an < 30:
            return
        self.deneme["okunan_bayt"] = self.okunan
        self.deneme["okunan_yuzde"] = round(self.okunan / self.toplam * 100, 2) if self.toplam else 0
        self.deneme["gecen_sn"] = round(simdi - self._basla, 3)
        if self.toplam and self.okunan >= self.toplam:
            self.deneme["durum"] = "waiting_for_response"
        self._yaz()
        self._son_bayt, self._son_an = self.okunan, simdi


def _belirsiz_mi(deneme: dict[str, Any], hata: BaseException) -> bool:
    timed_out, network, _ = hata_siniflari()
    return deneme.get("durum") == "waiting_for_response" and hata.__class__ in (timed_out, network)


def yeniden_deneme_karari(boyut: int, deneme: dict[str, Any], sira: int) -> tuple[str, int]:
    """('retry', bekleme) · ('manual_review', 0) · ('stop', 0)."""
    if deneme.get("sonuc") == "unknown" and boyut >= ys.BELIRSIZ_TESLIM_ESIGI:
        return "manual_review", 0
    if sira < AZAMI_DENEME:
        return "retry", BEKLEMELER[sira - 1]
    return "stop", 0


def video_bilgisi(yol: Path) -> dict[str, Any]:
    """ffprobe varsa genişlik/yükseklik/süre (oynatıcı önizlemesi için); yoksa boş."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {}
    try:
        sonuc = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height:format=duration", "-of", "json", str(yol)],
                               capture_output=True, text=True, timeout=30, **_GIZLI)
        veri = json.loads(sonuc.stdout or "{}")
        akis = (veri.get("streams") or [{}])[0]
        return {"width": akis.get("width"), "height": akis.get("height"),
                "duration": int(float((veri.get("format") or {}).get("duration") or 0)) or None}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {}


async def dosya_gonder(bot: Any, sohbet: int | str, yol: str | Path, *, baslik: str | None = None,
                       adres: str | None = None, rapor_klasoru: Path | None = None,
                       bekle: Callable[[float], Awaitable[Any]] = asyncio.sleep,
                       belge: bool | None = None) -> TeslimSonucu:
    """Tek dosyayı teslim eder. `adres` = yerel sunucu adresi (boş = bulut); None ise ortamdan okunur.
    `belge` = True ise video da dosya (document) olarak gider; None ise `TELEGRAM_TESLIM_BICIMI` okunur."""
    yol = Path(yol)
    adres = ys.yerel_adres() if adres is None else adres
    boyut = yol.stat().st_size if yol.is_file() else 0
    uygun, neden = ys.boyut_denetimi(boyut, adres)
    if not uygun:
        durum = "too_large" if boyut > ys.YEREL_SINIR else "needs_local_server" if boyut else "failed"
        return TeslimSonucu(False, durum, neden, bayt=boyut)
    if adres and boyut > ys.BULUT_GONDERME_SINIRI:
        bos = await asyncio.to_thread(ys.sunucu_bos_alan)
        if bos is not None and bos < boyut * ys.YUKLEME_PAYI:
            return TeslimSonucu(False, "failed", (
                f"yerel sunucunun diskinde {bos // ys.MB} MB boş; bu dosya için ~{int(boyut * ys.YUKLEME_PAYI) // ys.MB} "
                "MB gerekir (sunucu yüklemeyi önce kendi geçici klasörüne yazar). Yer açın: "
                "dubla-telegram sunucu temizle"), bayt=boyut)
    belge = belge_istendi_mi() if belge is None else belge
    yontem = gonderim_yontemi(yol, boyut, belge)
    try:  # faststart kopyası dosyanın yanında (aynı disk); olmazsa sistemin geçici klasörü
        gecici = Path(tempfile.mkdtemp(prefix=".telegram_onizleme_", dir=yol.parent))
    except OSError:
        gecici = Path(tempfile.mkdtemp(prefix="telegram_onizleme_"))
    try:
        return await _gonder_dongusu(bot, sohbet, yol, boyut, yontem, gecici, baslik, adres, rapor_klasoru, bekle)
    finally:
        shutil.rmtree(gecici, ignore_errors=True)


async def _gonder_dongusu(bot: Any, sohbet: int | str, yol: Path, boyut: int, yontem: str, gecici: Path,
                          baslik: str | None, adres: str, rapor_klasoru: Path | None,
                          bekle: Callable[[float], Awaitable[Any]]) -> TeslimSonucu:
    if yontem == "send_video":
        gonderilecek, kucuk, bilgi = await asyncio.to_thread(onizleme_hazirla, yol, gecici)
    else:
        gonderilecek, kucuk, bilgi = yol, None, {}
    gonderilen_boyut = gonderilecek.stat().st_size
    rapor_yolu = (rapor_klasoru or yol.parent) / RAPOR_ADI
    rapor: dict[str, Any] = {
        "dosya": yol.name, "bayt": boyut, "yontem": yontem, "sunucu": "yerel" if adres else "bulut",
        "onizleme": {"faststart_kopyasi": gonderilecek != yol, "kucuk_resim": kucuk is not None, **bilgi},
        "ilerleme_notu": "okunan_bayt istemcinin okuduğu bayttır, Telegram'ın aldığının kanıtı değildir",
        "baslangic": _simdi(), "denemeler": [], "sonuc": "started",
    }
    try:
        _rapor_yaz(rapor_yolu, rapor)
    except OSError:
        rapor_yolu = None  # salt okunur klasör: rapor yazılamaz, teslim sürer
    yazma, okuma = zaman_asimlari(boyut)
    timed_out, network, telegram_hatasi = hata_siniflari()
    kucuk_bayt = kucuk.read_bytes() if kucuk else None
    basla = time.monotonic()
    son_hata: BaseException | None = None
    for sira in range(1, AZAMI_DENEME + 1):
        deneme: dict[str, Any] = {"sira": sira, "baslangic": _simdi(), "durum": "uploading",
                                  "yazma_sn": yazma, "okuma_sn": okuma}
        rapor["denemeler"].append(deneme)
        _rapor_yaz(rapor_yolu, rapor)
        try:
            with gonderilecek.open("rb") as ham:
                akim = IlerlemeDosyasi(ham, deneme, gonderilen_boyut, lambda: _rapor_yaz(rapor_yolu, rapor))
                if yontem == "send_video":
                    mesaj = await bot.send_video(chat_id=sohbet, video=akim, caption=baslik, supports_streaming=True,
                                                 filename=f"{yol.stem}.mp4", thumbnail=kucuk_bayt,
                                                 read_timeout=okuma, write_timeout=yazma, **bilgi)
                else:
                    mesaj = await bot.send_document(chat_id=sohbet, document=akim, caption=baslik, filename=yol.name,
                                                    read_timeout=okuma, write_timeout=yazma)
        except Exception as hata:  # noqa: BLE001 — sınıfa göre karar aşağıda
            son_hata = hata
            belirsiz = _belirsiz_mi(deneme, hata)  # aşama (okuma bitti mi) hata yazılmadan önce okunur
            deneme.update({"asama": deneme.get("durum"), "durum": "error", "hata_sinifi": hata.__class__.__name__,
                           "hata": gizle(str(hata))[:300], "bitis": _simdi()})
            deneme["sonuc"] = "unknown" if belirsiz else "failed"
            if isinstance(hata, timed_out):
                # Zaman aşımı: yeniden yükleme çift teslim yaratabilir → dur.
                rapor["sonuc"] = deneme["sonuc"]
                _rapor_yaz(rapor_yolu, rapor)
                break
            karar, sn = yeniden_deneme_karari(boyut, deneme, sira)
            deneme.update({"karar": karar, "sonraki_bekleme_sn": sn})
            rapor["sonuc"] = "manual_review" if karar == "manual_review" else deneme["sonuc"]
            _rapor_yaz(rapor_yolu, rapor)
            if karar != "retry":
                break
            await bekle(sn)
            if isinstance(hata, (network, telegram_hatasi)):
                yazma, okuma = int(yazma * 1.5), int(okuma * 1.2)
            continue
        mesaj_no = getattr(mesaj, "message_id", None)
        # Telegram'ın cevabı neyi kaydettiğini söyler: 'video' alanı = önizlemeli video, 'document' = dosya.
        tur = "video" if getattr(mesaj, "video", None) else "document" if getattr(mesaj, "document", None) else ""
        deneme.update({"durum": "confirmed", "mesaj_no": mesaj_no, "bitis": _simdi()})
        rapor.update({"sonuc": "confirmed", "mesaj_no": mesaj_no, "telegram_turu": tur, "bitis": _simdi(),
                      "sure_sn": round(time.monotonic() - basla, 1)})
        _rapor_yaz(rapor_yolu, rapor)
        return TeslimSonucu(True, "confirmed", "Telegram mesajı döndürdü", mesaj_no, sira,
                            round(time.monotonic() - basla, 1), boyut, str(rapor_yolu or ""), tur)
    durum = rapor.get("sonuc") if rapor.get("sonuc") in ("unknown", "manual_review") else "failed"
    neden = gizle(str(son_hata))[:300] if son_hata else "teslim doğrulanmadı"
    if durum in ("unknown", "manual_review"):
        neden = ("dosya gönderildi ama Telegram cevabı gelmedi; çift teslim olmasın diye yeniden denenmedi, "
                 "sohbete bakın · " + neden)
    rapor.update({"sonuc": durum, "bitis": _simdi(), "sure_sn": round(time.monotonic() - basla, 1)})
    _rapor_yaz(rapor_yolu, rapor)
    return TeslimSonucu(False, durum, neden, None, len(rapor["denemeler"]), round(time.monotonic() - basla, 1),
                        boyut, str(rapor_yolu or ""))


def bot_olustur(belirtec: str, adres: str) -> Any:
    """Bağımsız gönderim için Bot (uygulama kurmadan). Yerel adres varsa bütün istekler oraya gider."""
    from telegram import Bot
    from telegram.request import HTTPXRequest

    istek = HTTPXRequest(connection_pool_size=8, read_timeout=300, write_timeout=600, connect_timeout=30,
                         pool_timeout=60)
    if adres:
        return Bot(belirtec, base_url=f"{adres}/bot", base_file_url=f"{adres}/file/bot", local_mode=True,
                   request=istek)
    return Bot(belirtec, request=istek)


async def _gonder_kos(dosya: Path, sohbet: str, metin: str | None, belge: bool | None = None) -> TeslimSonucu:
    adres = ys.yerel_adres()
    belirtec = belirteci_al()
    uygun, neden = ys.boyut_denetimi(dosya.stat().st_size, adres)
    if not uygun:  # ağa hiç çıkmadan
        return TeslimSonucu(False, "too_large" if dosya.stat().st_size > ys.YEREL_SINIR else "needs_local_server",
                            neden, bayt=dosya.stat().st_size)
    if adres and not await asyncio.to_thread(ys.get_me, adres, belirtec):
        # Ölü sunucu önünde uzun yükleme süresi beklenmez: önce gerçek getMe.
        raise TelegramAyarHatasi(f"yerel sunucu {adres} cevap vermiyor (getMe): dubla-telegram sunucu baslat; "
                                 f"durum: dubla-telegram sunucu durum")
    bot = bot_olustur(belirtec, adres)
    async with bot:
        return await dosya_gonder(bot, sohbet, dosya, baslik=metin, adres=adres, belge=belge)


def main(argv: list[str] | None = None) -> int:
    """dubla-telegram gonder <dosya> [--metin ..] [--sohbet ..]: dosyayı izinli listedeki ilk kişiye gönderir."""
    ayr = argparse.ArgumentParser(prog="dubla-telegram gonder", description="Dosyayı Telegram'a gönder (en çok 2000 MB)")
    ayr.add_argument("dosya", type=Path)
    ayr.add_argument("--metin", help="dosyanın altındaki açıklama")
    ayr.add_argument("--sohbet", help="sayısal sohbet kimliği (boşsa TELEGRAM_IZINLI_KULLANICILAR'daki ilk kimlik)")
    ayr.add_argument("--belge", action="store_true",
                     help="videoyu da dosya (document) olarak gönder; varsayılan önizlemeli video")
    args = ayr.parse_args(argv)
    ys.env_yukle()
    try:
        sohbet = args.sohbet or next(iter(sorted(izinli_kullanicilar())), None)
        if not sohbet:
            raise TelegramAyarHatasi("sohbet kimliği yok: --sohbet ya da TELEGRAM_IZINLI_KULLANICILAR")
        if not args.dosya.is_file():
            raise TelegramAyarHatasi(f"dosya yok: {args.dosya.name}")
        sonuc = asyncio.run(_gonder_kos(args.dosya, str(sohbet), args.metin, True if args.belge else None))
    except TelegramAyarHatasi as hata:
        print(f"Gönderilemedi: {gizle(str(hata))}")
        return 2
    except ImportError:
        print("python-telegram-bot kurulu değil: pip install .[telegram]")
        return 2
    satir = (f"{sonuc.durum.upper()}: bayt={sonuc.bayt} sure_sn={sonuc.sure_sn} deneme={sonuc.deneme}"
             + (f" mesaj_no={sonuc.mesaj_no} tur={sonuc.telegram_turu}" if sonuc.mesaj_no else "") + (f" · {sonuc.neden}" if not sonuc else ""))
    print(satir)
    return 0 if sonuc else (3 if sonuc.durum in ("unknown", "manual_review") else 1)


if __name__ == "__main__":
    sys.exit(main())
