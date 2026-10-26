"""`dubla-web`: yerel web arayüzü (yalnız bu bilgisayar, 127.0.0.1).

    dubla-web                    # boş bir port seçer, tarayıcıyı açar
    dubla-web --port 7861 --tarayici-acma

Güvenlik (yerel sunucu da saldırı yüzeyidir):
  * yalnız 127.0.0.1'e bağlanır; Host başlığı 127.0.0.1/localhost:<port> değilse 421 (DNS yeniden bağlama)
  * her açılışta rastgele oturum belirteci: adres çubuğundaki ?t=... bir kez çereze (HttpOnly, SameSite=Strict)
    çevrilir; her API isteği çerez + X-Dublaj-Belirtec başlığı ister (CSRF), Origin varsa aynı köken olmalı
  * JSON gövdesi en çok 64 KB ve Content-Type application/json; yükleme yalnız video uzantısı ve boyut sınırı
  * dosya sunumu yalnız çıktı klasörü, yükleme klasörü ve ses kitaplığı içinden (yol kaçışı engelli)
  * ses kitaplığına (ses_kitapligi) yalnız rıza kaydıyla ses eklenir; ses yalnız bu bilgisayarda kalır
  * aynı anda tek iş; iş ayrı süreçte, pencere açmadan çalışır
  * dış kaynak (CDN, yazı tipi, analiz) yok; Content-Security-Policy default-src 'self'

Arayüz dili: sayfa sözlüğü `/api/arayuz_dili` ile alır (seçim sırası: sayfada seçilen > genel.arayuz_dili >
tarayıcının dili > bilgisayarın dili > İngilizce); ayar formu `/api/ayarlar?dil=..` ile o dilde gelir.
"""

from __future__ import annotations

import argparse
import hmac
import http.server
import json
import mimetypes
import secrets
import sys
import threading
import time
import uuid
import webbrowser
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from dublaj_hatti import __version__, arayuz_dili, ses_kitapligi
from dublaj_hatti.is_yonetimi import inceleme
from dublaj_hatti.is_yonetimi.depo import IsDeposu, varsayilan_depo_yolu
from dublaj_hatti.is_yurutucu import IsYurutucu, arayuz_ayari_denetle, ayar_formu, cikti_klasoru_ac
from dublaj_hatti.yapilandirma import SEMA, AyarHatasi, ayarlari_yukle

JSON_SINIRI = 64 * 1024
DUZENLE_JSON_SINIRI = 1024 * 1024  # satır düzeltmeleri (en çok 2000 karakterlik çok satır) için
VIDEO_UZANTILARI = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}
SES_YUKLEME_SINIRI = 50 * 1024 * 1024
STATIK = Path(__file__).with_name("web_statik")
CEREZ = "dublaj_oturum"


def cikti_koku() -> Path:
    """Hattın yazdığı kök: ayar > DUBLAJ_OUTPUT_DIR (.env dahil) > repo kökünde cikti/ (iş süreciyle aynı kural)."""
    from dublaj_hatti.bolum_00_omurga.runtime.output_paths import configured_output_root

    deger = str(ayarlari_yukle().get("genel.cikti_klasoru") or "").strip()
    return (Path(deger).expanduser() if deger else configured_output_root()).resolve()


def _icinde_mi(yol: Path, kok: Path) -> bool:
    try:
        yol.resolve().relative_to(kok.resolve())
        return True
    except ValueError:
        return False


def _tam_sayi(deger: Any) -> int:
    if isinstance(deger, bool) or not isinstance(deger, (int, str)):
        raise ValueError("is sayı olmalı")
    return int(deger)


def arayuz_dili_sec(secim: str, tarayici: str, ayar: str | None) -> str:
    """Sayfanın dili: sayfada seçilen > genel.arayuz_dili > tarayıcı dilleri (sırayla) > bilgisayarın dili > en."""
    mevcut = arayuz_dili.mevcut_diller()
    secim, ayar = secim.strip().lower(), str(ayar or "auto").strip().lower()
    if secim in mevcut:
        return secim
    if ayar in mevcut:
        return ayar
    for parca in tarayici.split(","):
        kod = parca.strip().split(";")[0].split("-")[0].lower()
        if kod in mevcut:
            return kod
    return arayuz_dili.cozumle("auto")


def _istenen_dil(sorgu: dict[str, list[str]]) -> str | None:
    dil = sorgu.get("dil", [""])[0]
    return dil if dil in arayuz_dili.mevcut_diller() else None


class Uygulama:
    def __init__(self, port: int, yukleme_siniri_mb: int) -> None:
        self.port = port
        self.belirtec = secrets.token_urlsafe(32)
        kok = cikti_koku()
        self.yurutucu = IsYurutucu(arayuz="web", depo=IsDeposu(varsayilan_depo_yolu(kok), kok))
        self.yukleme_siniri = yukleme_siniri_mb * 1024 * 1024
        self.yukleme_klasoru = cikti_koku() / "_yuklemeler"
        self.yuklenenler: dict[str, Path] = {}
        self.son_nabiz = time.time()  # sayfanın son yoklaması (masaüstü penceresi kapandı mı: masaustu.py)

    def izinli_kokler(self) -> list[Path]:
        return [cikti_koku(), self.yukleme_klasoru, ses_kitapligi.kok()]


class Isleyici(http.server.BaseHTTPRequestHandler):
    server_version = "dublaj-web"
    sys_version = ""
    uygulama: Uygulama

    # --- ortak -----------------------------------------------------------------------------------------
    def log_message(self, bicim: str, *args: Any) -> None:  # istek günlüğü yalnız stderr'e, kısa
        sys.stderr.write("web: " + (bicim % args) + "\n")

    def _basliklar(self, tur: str, uzunluk: int, ek: dict[str, str] | None = None) -> None:
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(uzunluk))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; media-src 'self' blob:; img-src 'self' data:; frame-ancestors 'none'; "
                         "base-uri 'none'; form-action 'self'")
        for anahtar, deger in (ek or {}).items():
            self.send_header(anahtar, deger)
        self.end_headers()

    def _gonder(self, kod: int, govde: bytes, tur: str = "text/plain; charset=utf-8",
                ek: dict[str, str] | None = None) -> None:
        self.send_response(kod)
        self._basliklar(tur, len(govde), ek)
        if self.command != "HEAD":
            self.wfile.write(govde)

    def _json(self, kod: int, veri: Any) -> None:
        self._gonder(kod, json.dumps(veri, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _host_dogru(self) -> bool:
        host = (self.headers.get("Host") or "").lower()
        return host in {f"127.0.0.1:{self.uygulama.port}", f"localhost:{self.uygulama.port}"}

    def _cerez_dogru(self) -> bool:
        cerez = SimpleCookie(self.headers.get("Cookie") or "")
        deger = cerez[CEREZ].value if CEREZ in cerez else ""
        return bool(deger) and hmac.compare_digest(deger, self.uygulama.belirtec)

    def _api_yetkili(self) -> bool:
        if not self._cerez_dogru():
            return False
        if not hmac.compare_digest(self.headers.get("X-Dublaj-Belirtec") or "", self.uygulama.belirtec):
            return False
        koken = self.headers.get("Origin")
        return koken is None or koken.lower() in {f"http://127.0.0.1:{self.uygulama.port}",
                                                   f"http://localhost:{self.uygulama.port}"}

    def _json_govde(self, sinir: int = JSON_SINIRI) -> dict[str, Any]:
        if not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
            raise ValueError("Content-Type application/json olmalı")
        uzunluk = int(self.headers.get("Content-Length") or 0)
        if uzunluk > sinir:
            raise ValueError("istek çok büyük")
        veri = json.loads(self.rfile.read(uzunluk) or b"{}")
        if not isinstance(veri, dict):
            raise ValueError("JSON nesnesi bekleniyor")
        return veri

    # --- GET -------------------------------------------------------------------------------------------
    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        if not self._host_dogru():
            self._gonder(421, b"yalniz 127.0.0.1")
            return
        adres = urlparse(self.path)
        if adres.path == "/":
            t = parse_qs(adres.query).get("t", [""])[0]
            if t and hmac.compare_digest(t, self.uygulama.belirtec):
                self._gonder(HTTPStatus.SEE_OTHER, b"", ek={
                    "Location": "/",
                    "Set-Cookie": f"{CEREZ}={self.uygulama.belirtec}; HttpOnly; SameSite=Strict; Path=/"})
                return
            if not self._cerez_dogru():
                self._gonder(HTTPStatus.FORBIDDEN, ("Oturum yok: dubla-web komutunun yazdığı adresi açın.\n"
                                                    "No session: open the address printed by dubla-web.").encode())
                return
            html = (STATIK / "index.html").read_text(encoding="utf-8")
            html = html.replace("__BELIRTEC__", self.uygulama.belirtec).replace("__SURUM__", __version__)
            self._gonder(HTTPStatus.OK, html.encode("utf-8"), "text/html; charset=utf-8")
            return
        if adres.path in ("/app.js", "/app.css"):
            tur = "text/javascript; charset=utf-8" if adres.path.endswith(".js") else "text/css; charset=utf-8"
            self._gonder(HTTPStatus.OK, (STATIK / adres.path.lstrip("/")).read_bytes(), tur)
            return
        if not self._cerez_dogru():
            self._gonder(HTTPStatus.FORBIDDEN, b"oturum yok")
            return
        self.uygulama.son_nabiz = time.time()
        if adres.path == "/api/nabiz":
            self._json(HTTPStatus.OK, {})
        elif adres.path == "/api/ayarlar":
            dil = _istenen_dil(parse_qs(adres.query))
            self._json(HTTPStatus.OK, {"form": ayar_formu(dil or "tr"), "surum": __version__})
        elif adres.path == "/api/arayuz_dili":
            sorgu = parse_qs(adres.query)
            try:
                ayar = ayarlari_yukle().get("genel.arayuz_dili")
            except (AyarHatasi, OSError, ValueError):
                ayar = "auto"
            dil = arayuz_dili_sec(sorgu.get("secim", [""])[0], sorgu.get("tarayici", [""])[0], ayar)
            self._json(HTTPStatus.OK, {
                "dil": dil, "yon": arayuz_dili.yon(dil), "sozluk": arayuz_dili.tam_sozluk(dil),
                "diller": [{"kod": k, "ad": arayuz_dili.kendi_adi(k)} for k in arayuz_dili.mevcut_diller()]})
        elif adres.path == "/api/durum":
            ozet = self.uygulama.yurutucu.durum.ozet()
            ozet["orijinal"] = self._oynatilir(str(ozet.get("kaynak") or ""))
            self._json(HTTPStatus.OK, ozet)
        elif adres.path == "/api/isler":
            hepsi = parse_qs(adres.query).get("hepsi", ["0"])[0] == "1"
            isler = self.uygulama.yurutucu.isler(100, arsiv_dahil=hepsi)
            for o in isler:  # oynatıcıda "Orijinal": yalnız bu sunucunun sunabildiği kaynak (yüklenen dosya)
                o["orijinal"] = self._oynatilir(str(o.get("kaynak_yolu") or ""))
            self._json(HTTPStatus.OK, {"isler": isler})
        elif adres.path == "/api/kurulum":
            from dublaj_hatti.kurulum_denetimi import kurulum_eksikleri

            try:
                eksik = kurulum_eksikleri()
            except Exception as hata:  # denetim arayüzü hiçbir zaman düşürmez
                eksik = [arayuz_dili.t("kurulum.denetlenemedi", None, hata=hata)]
            self._json(HTTPStatus.OK, {"eksik": eksik})
        elif adres.path == "/api/sesler":
            self._json(HTTPStatus.OK, self._sesler())
        elif adres.path == "/api/sorunlu":
            self._json(HTTPStatus.OK, {"isler": self.uygulama.yurutucu.sorunlu(10)})
        elif adres.path == "/api/is":
            try:
                no = int(parse_qs(adres.query).get("no", ["0"])[0])
                self._json(HTTPStatus.OK, self.uygulama.yurutucu.secenekler(no))
            except (ValueError, RuntimeError) as hata:
                self._json(HTTPStatus.NOT_FOUND, {"hata": str(hata)})
        elif adres.path == "/api/duzenle":
            try:
                no = int(parse_qs(adres.query).get("is", [""])[0])
                self._json(HTTPStatus.OK, inceleme.satirlari_oku(self.uygulama.yurutucu.depo, no))
            except ValueError:
                self._json(HTTPStatus.BAD_REQUEST, {"hata": "is sayı olmalı", "anahtar": "is_gecersiz"})
            except inceleme.InceleHatasi as hata:
                self._json(hata.kod, {"hata": str(hata), "anahtar": hata.anahtar})
        elif adres.path == "/dosya":
            self._dosya_sun(unquote(parse_qs(adres.query).get("yol", [""])[0]))
        else:
            self._gonder(HTTPStatus.NOT_FOUND, b"yok")

    def _sesler(self) -> dict[str, Any]:
        """Ses kitaplığı + XTTS durumu (kurulu mu, CPML onayı var mı): Sesler sekmesi ve ana ekrandaki ses seçici."""
        from dublaj_hatti.bolum_50_seslendirme.xtts_tts.api import xtts_python
        from dublaj_hatti.bolum_50_seslendirme.xtts_tts.lisans import lisans_onayli

        try:  # VoxCPM2 kurulu mu: ses seçici kurulu değilse kurulum ipucunu gösterir (hiçbir zaman hata vermez)
            from dublaj_hatti.bolum_50_seslendirme.voxcpm2_tts.api import voxcpm2_durumu

            voxcpm2_kurulu = bool(voxcpm2_durumu()["kurulu"])
        except Exception:
            voxcpm2_kurulu = False
        return {"sesler": ses_kitapligi.listele(), "kategoriler": list(ses_kitapligi.KATEGORILER),
                "sinirlar": {"en_kisa_sn": ses_kitapligi.EN_KISA_SN, "en_uzun_sn": ses_kitapligi.EN_UZUN_SN,
                             "ad": ses_kitapligi.AD_SINIRI, "metin": ses_kitapligi.METIN_SINIRI,
                             "dosya_mb": SES_YUKLEME_SINIRI // 2**20,
                             "uzantilar": sorted(ses_kitapligi.SES_UZANTILARI)},
                "voxcpm2": {"kurulu": voxcpm2_kurulu},
                "xtts": {"kurulu": xtts_python() is not None, "lisans_onayli": lisans_onayli()}}

    def _oynatilir(self, ham: str) -> str:
        """Yerel ve izinli köklerden birinde olan dosya yolu (oynatıcı onu `/dosya` ile açabilir), yoksa boş."""
        if not ham or "://" in ham:
            return ""
        yol = Path(ham)
        return ham if yol.is_file() and any(_icinde_mi(yol, k) for k in self.uygulama.izinli_kokler()) else ""

    def _dosya_sun(self, ham: str) -> None:
        yol = Path(ham)
        if not ham or not yol.is_file() or not any(_icinde_mi(yol, k) for k in self.uygulama.izinli_kokler()):
            self._gonder(HTTPStatus.NOT_FOUND, b"yok")
            return
        tur = mimetypes.guess_type(yol.name)[0] or "application/octet-stream"
        if yol.suffix.lower() in (".srt", ".txt", ".json", ".vtt"):
            tur = "text/plain; charset=utf-8"
        boyut = yol.stat().st_size
        bas, son = 0, boyut - 1
        aralik = self.headers.get("Range", "")
        kod = HTTPStatus.OK
        ek = {"Accept-Ranges": "bytes"}
        if aralik.startswith("bytes="):
            try:
                a, b = aralik[6:].split(",")[0].split("-")
                bas = int(a) if a else max(0, boyut - int(b))
                son = min(int(b), boyut - 1) if a and b else son
                if bas > son:
                    raise ValueError
            except ValueError:
                self._gonder(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, b"", ek={"Content-Range": f"bytes */{boyut}"})
                return
            kod = HTTPStatus.PARTIAL_CONTENT
            ek["Content-Range"] = f"bytes {bas}-{son}/{boyut}"
        self.send_response(kod)
        self._basliklar(tur, son - bas + 1, ek)
        if self.command == "HEAD":
            return
        with open(yol, "rb") as dosya:
            dosya.seek(bas)
            kalan = son - bas + 1
            while kalan > 0:
                parca = dosya.read(min(1 << 20, kalan))
                if not parca:
                    break
                try:
                    self.wfile.write(parca)
                except (BrokenPipeError, ConnectionResetError):
                    return
                kalan -= len(parca)

    # --- POST ------------------------------------------------------------------------------------------
    def do_POST(self) -> None:
        if not self._host_dogru():
            self._gonder(421, b"yalniz 127.0.0.1")
            return
        if not self._api_yetkili():
            self._json(HTTPStatus.FORBIDDEN, {"hata": "oturum ya da belirteç geçersiz"})
            return
        yol = urlparse(self.path).path
        try:
            if yol == "/api/yukle":
                self._yukle()
            elif yol == "/api/baslat":
                self._baslat(self._json_govde())
            elif yol == "/api/durdur":
                self.uygulama.yurutucu.durdur()
                self._json(HTTPStatus.OK, {"tamam": True})
            elif yol == "/api/devam":
                self._devam(self._json_govde())
            elif yol in ("/api/is_arsivle", "/api/is_iptal"):
                no = int(self._json_govde().get("is") or 0)
                y = self.uygulama.yurutucu
                tamam = y.arsivle(no) if yol.endswith("arsivle") else y.iptal(no)
                if not tamam:
                    raise RuntimeError("yapılamadı: iş yok ya da etkin")
                self._json(HTTPStatus.OK, {"tamam": True})
            elif yol == "/api/duzenle":
                veri = self._json_govde(DUZENLE_JSON_SINIRI)
                self._json(HTTPStatus.OK, inceleme.satirlari_kaydet(
                    self.uygulama.yurutucu.depo, _tam_sayi(veri.get("is")), veri.get("satirlar")))
            elif yol == "/api/cevir_satir":
                veri = self._json_govde()
                self._json(HTTPStatus.OK, inceleme.satiri_cevir(
                    self.uygulama.yurutucu.depo, _tam_sayi(veri.get("is")), veri.get("no"), veri.get("metin")))
            elif yol == "/api/ses_ekle":
                self._ses_ekle()
            elif yol == "/api/ses_guncelle":
                veri = self._json_govde()
                self._json(HTTPStatus.OK, ses_kitapligi.guncelle(str(veri.get("kimlik") or ""), veri.get("ad"),
                                                                 veri.get("kategori"), veri.get("metin")))
            elif yol == "/api/ses_sil":
                ses_kitapligi.sil(str(self._json_govde().get("kimlik") or ""))
                self._json(HTTPStatus.OK, {"tamam": True})
            elif yol == "/api/xtts_lisans":
                if self._json_govde().get("kabul") is not True:
                    raise ValueError("lisans onayı için kabul: true gerekli")
                from dublaj_hatti.bolum_50_seslendirme.xtts_tts.lisans import lisans_onayini_kaydet

                lisans_onayini_kaydet()
                self._json(HTTPStatus.OK, self._sesler())
            elif yol == "/api/klasor_ac":
                veri = self._json_govde()
                hedef = Path(str(veri.get("yol") or cikti_koku()))
                if not any(_icinde_mi(hedef, k) for k in self.uygulama.izinli_kokler()):
                    raise ValueError("yalnız çıktı klasörü açılabilir")
                cikti_klasoru_ac(str(hedef))
                self._json(HTTPStatus.OK, {"tamam": True})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"hata": "yok"})
        except inceleme.InceleHatasi as hata:
            self._json(hata.kod, {"hata": str(hata), "anahtar": hata.anahtar})
        except ses_kitapligi.SesKitapligiHatasi as hata:  # ValueError'ın alt sınıfı: önce bu, "anahtar" arayüz dilinde gösterilir
            self.close_connection = True  # okunmamış gövde kalmış olabilir
            self._json(HTTPStatus.BAD_REQUEST, {"hata": str(hata), "anahtar": hata.anahtar})
        except (ValueError, AyarHatasi, json.JSONDecodeError) as hata:
            self.close_connection = True  # okunmamış gövde kalmış olabilir
            self._json(HTTPStatus.BAD_REQUEST, {"hata": str(hata)})
        except RuntimeError as hata:
            self._json(HTTPStatus.CONFLICT, {"hata": str(hata)})

    def _yukle(self) -> None:
        ad = Path(unquote(self.headers.get("X-Dosya-Adi") or "")).name
        uzanti = Path(ad).suffix.lower()
        if uzanti not in VIDEO_UZANTILARI:
            raise ValueError(f"desteklenen video uzantıları: {', '.join(sorted(VIDEO_UZANTILARI))}")
        uzunluk = int(self.headers.get("Content-Length") or 0)
        if uzunluk <= 0 or uzunluk > self.uygulama.yukleme_siniri:
            raise ValueError(f"dosya boyutu 0 ya da sınırın üstünde ({self.uygulama.yukleme_siniri // 2**20} MB)")
        kimlik = uuid.uuid4().hex
        self.uygulama.yukleme_klasoru.mkdir(parents=True, exist_ok=True)
        hedef = self.uygulama.yukleme_klasoru / f"{kimlik}{uzanti}"
        gecici = hedef.with_suffix(uzanti + ".part")
        kalan = uzunluk
        with open(gecici, "wb") as cikti:
            while kalan > 0:
                parca = self.rfile.read(min(1 << 20, kalan))
                if not parca:
                    break
                cikti.write(parca)
                kalan -= len(parca)
        if kalan:
            gecici.unlink(missing_ok=True)
            raise ValueError("yükleme yarım kaldı")
        gecici.replace(hedef)
        self.uygulama.yuklenenler[kimlik] = hedef
        self._json(HTTPStatus.OK, {"kimlik": kimlik, "ad": ad, "boyut": uzunluk})

    def _ses_ekle(self) -> None:
        """Ham gövde = ses dosyası; ad, kategori, rıza ve isteğe bağlı kayıt metni başlıklarda (X-Ses-*, URI kodlu)."""
        baslik = lambda ad: unquote(self.headers.get(ad) or "")  # noqa: E731
        dosya_adi = Path(baslik("X-Dosya-Adi")).name
        if Path(dosya_adi).suffix.lower() not in ses_kitapligi.SES_UZANTILARI:
            raise ses_kitapligi.SesKitapligiHatasi(
                "desteklenen ses dosyaları: " + ", ".join(sorted(ses_kitapligi.SES_UZANTILARI)), "uzanti_gecersiz")
        uzunluk = int(self.headers.get("Content-Length") or 0)
        if uzunluk <= 0 or uzunluk > SES_YUKLEME_SINIRI:
            raise ses_kitapligi.SesKitapligiHatasi(
                f"ses dosyası 0 ya da {SES_YUKLEME_SINIRI // 2**20} MB üstünde", "dosya_boyutu")
        self.uygulama.yukleme_klasoru.mkdir(parents=True, exist_ok=True)
        gecici = self.uygulama.yukleme_klasoru / f"ses_{uuid.uuid4().hex}{Path(dosya_adi).suffix.lower()}.part"
        try:
            kalan = uzunluk
            with open(gecici, "wb") as cikti:
                while kalan > 0:
                    parca = self.rfile.read(min(1 << 20, kalan))
                    if not parca:
                        break
                    cikti.write(parca)
                    kalan -= len(parca)
            if kalan:
                raise ses_kitapligi.SesKitapligiHatasi("yükleme yarım kaldı", "yukleme_yarim")
            kayit = ses_kitapligi.ekle(gecici, baslik("X-Ses-Adi"), baslik("X-Ses-Kategori"), baslik("X-Ses-Riza"),
                                       baslik("X-Ses-Taklit-Yok") == "1", dosya_adi=dosya_adi,
                                       metin=baslik("X-Ses-Metin"))
        finally:
            gecici.unlink(missing_ok=True)
        self._json(HTTPStatus.OK, kayit)

    def _baslat(self, veri: dict[str, Any]) -> None:
        kimlik = str(veri.get("yuklenen") or "")
        kaynak: Path | str | None = self.uygulama.yuklenenler.get(kimlik)
        baglanti = str(veri.get("baglanti") or "").strip()
        if baglanti:  # yalnız https bağlantısı; yerel yol bu uçtan asla kabul edilmez (yalnız yükleme)
            from dublaj_hatti.kaynak_girdisi import baglanti_mi, kaynak_dogrula

            if len(baglanti) > 2048 or not baglanti_mi(baglanti) or any(c.isspace() or ord(c) < 32 for c in baglanti):
                raise ValueError("geçersiz bağlantı")
            kaynak = kaynak_dogrula(baglanti)  # KaynakHatasi (ValueError): kurulum ipucuyla 400
        if kaynak is None:
            raise ValueError("önce bir video yükleyin ya da bağlantı verin")
        ayarlar = veri.get("ayarlar") or {}
        if not isinstance(ayarlar, dict):
            raise ValueError("ayarlar bir nesne olmalı")
        komut = "transkript" if ayarlar.get("genel.is_turu") == "transkript" else "dubla"
        bicim = str(veri.get("bicim") or "") or None  # yoksa Gelişmiş'teki genel.transkript_bicimi
        if bicim is not None and bicim not in ("srt", "plain", "timestamped", "paragraph"):
            raise ValueError("geçersiz transkript biçimi")
        from dublaj_hatti.lisans_onayi import LisansOnayiGerekli, arayuz_kapisi

        try:  # ticari olmayan / şartlı motor: ilk kullanımda açık onay (sayfa onay penceresi gösterip yeniden gönderir)
            arayuz_kapisi(ayarlar, onay=veri.get("lisans_onay") is True)
        except LisansOnayiGerekli as gerek:
            self._json(HTTPStatus.CONFLICT, {"hata": str(gerek), "lisans_onayi": [
                {"ad": ad, "metin": metin} for ad, metin in gerek.bekleyen]})
            return
        self.uygulama.yurutucu.baslat(str(kaynak), ayarlar, komut=komut, bicim=bicim)
        self._json(HTTPStatus.OK, {"tamam": True})

    def _devam(self, veri: dict[str, Any]) -> None:
        """Sorunlu / biten işi sürdür: {"is": N, "asama": "ceviri"?, "yeni_is": bool?, "ayarlar": {anahtar: değer}?}"""
        no = int(veri.get("is") or 0)
        asama = str(veri.get("asama") or "") or None
        ayarlar = veri.get("ayarlar") or {}
        if not isinstance(ayarlar, dict):
            raise ValueError("ayarlar bir nesne olmalı")
        ifadeler = []
        for anahtar, deger in ayarlar.items():
            metin = ("true" if deger else "false") if isinstance(deger, bool) else str(deger)
            if anahtar not in SEMA or any(c in metin for c in "\r\n\x00"):
                raise ValueError(f"geçersiz ayar: {anahtar}")
            arayuz_ayari_denetle(anahtar)
            ifadeler.append(f"{anahtar}={metin}")
        hedef = self.uygulama.yurutucu.devam(no, asama=asama, yeni_is=bool(veri.get("yeni_is")),
                                             ayar_ifadeleri=ifadeler)
        self._json(HTTPStatus.OK, {"tamam": True, "is": hedef})


class Sunucu(http.server.ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16


def main(argv: list[str] | None = None) -> int:
    ayr = argparse.ArgumentParser(prog="dubla-web", description="DubWorld yerel web arayüzü (127.0.0.1)")
    ayr.add_argument("--port", type=int, default=0, help="0 = boş port seç")
    ayr.add_argument("--tarayici-acma", action="store_true", help="tarayıcıyı otomatik açma")
    ayr.add_argument("--yukleme-siniri-mb", type=int, default=8192)
    args = ayr.parse_args(argv)

    sunucu = Sunucu(("127.0.0.1", args.port), Isleyici)
    port = sunucu.server_address[1]
    uygulama = Uygulama(port, args.yukleme_siniri_mb)
    Isleyici.uygulama = uygulama
    adres = f"http://127.0.0.1:{port}/?t={uygulama.belirtec}"
    print(f"DubWorld web arayüzü: {adres}", flush=True)
    print("Kapatmak için bu pencerede Ctrl+C. Adres yalnız bu bilgisayardan açılır.", flush=True)
    if not args.tarayici_acma:
        threading.Timer(0.5, lambda: webbrowser.open(adres)).start()
    try:
        sunucu.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        uygulama.yurutucu.kapat()
        sunucu.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
