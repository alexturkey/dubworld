"""`dubla-web`: yerel web arayüzü (yalnız bu bilgisayar, 127.0.0.1).

    dubla-web                    # boş bir port seçer, tarayıcıyı açar
    dubla-web --port 7861 --tarayici-acma

Güvenlik (yerel sunucu da saldırı yüzeyidir):
  * yalnız 127.0.0.1'e bağlanır; Host başlığı 127.0.0.1/localhost:<port> değilse 421 (DNS yeniden bağlama)
  * her açılışta rastgele oturum belirteci: adres çubuğundaki ?t=... bir kez çereze (HttpOnly, SameSite=Strict)
    çevrilir; her API isteği çerez + X-Dublaj-Belirtec başlığı ister (CSRF), Origin varsa aynı köken olmalı
  * JSON gövdesi en çok 64 KB ve Content-Type application/json; yükleme yalnız video uzantısı ve boyut sınırı
  * dosya sunumu yalnız çıktı klasörü ve yükleme klasörü içinden (yol kaçışı engelli)
  * aynı anda tek iş; iş ayrı süreçte, pencere açmadan çalışır
  * dış kaynak (CDN, yazı tipi, analiz) yok; Content-Security-Policy default-src 'self'
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
import uuid
import webbrowser
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from dublaj_hatti import __version__
from dublaj_hatti.is_yonetimi.depo import IsDeposu, varsayilan_depo_yolu
from dublaj_hatti.is_yurutucu import IsYurutucu, ayar_formu, cikti_klasoru_ac
from dublaj_hatti.yapilandirma import SEMA, AyarHatasi, ayarlari_yukle

JSON_SINIRI = 64 * 1024
VIDEO_UZANTILARI = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}
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


class Uygulama:
    def __init__(self, port: int, yukleme_siniri_mb: int) -> None:
        self.port = port
        self.belirtec = secrets.token_urlsafe(32)
        kok = cikti_koku()
        self.yurutucu = IsYurutucu(arayuz="web", depo=IsDeposu(varsayilan_depo_yolu(kok), kok))
        self.yukleme_siniri = yukleme_siniri_mb * 1024 * 1024
        self.yukleme_klasoru = cikti_koku() / "_yuklemeler"
        self.yuklenenler: dict[str, Path] = {}

    def izinli_kokler(self) -> list[Path]:
        return [cikti_koku(), self.yukleme_klasoru]


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
                         "default-src 'self'; media-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
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

    def _json_govde(self) -> dict[str, Any]:
        if not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
            raise ValueError("Content-Type application/json olmalı")
        uzunluk = int(self.headers.get("Content-Length") or 0)
        if uzunluk > JSON_SINIRI:
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
                self._gonder(HTTPStatus.FORBIDDEN, "Oturum yok: dubla-web komutunun yazdığı adresi açın.".encode())
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
        if adres.path == "/api/ayarlar":
            self._json(HTTPStatus.OK, {"form": ayar_formu(), "surum": __version__})
        elif adres.path == "/api/durum":
            self._json(HTTPStatus.OK, self.uygulama.yurutucu.durum.ozet())
        elif adres.path == "/api/isler":
            hepsi = parse_qs(adres.query).get("hepsi", ["0"])[0] == "1"
            self._json(HTTPStatus.OK, {"isler": self.uygulama.yurutucu.isler(100, arsiv_dahil=hepsi)})
        elif adres.path == "/api/sorunlu":
            self._json(HTTPStatus.OK, {"isler": self.uygulama.yurutucu.sorunlu(10)})
        elif adres.path == "/api/is":
            try:
                no = int(parse_qs(adres.query).get("no", ["0"])[0])
                self._json(HTTPStatus.OK, self.uygulama.yurutucu.secenekler(no))
            except (ValueError, RuntimeError) as hata:
                self._json(HTTPStatus.NOT_FOUND, {"hata": str(hata)})
        elif adres.path == "/dosya":
            self._dosya_sun(unquote(parse_qs(adres.query).get("yol", [""])[0]))
        else:
            self._gonder(HTTPStatus.NOT_FOUND, b"yok")

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
            elif yol == "/api/klasor_ac":
                veri = self._json_govde()
                hedef = Path(str(veri.get("yol") or cikti_koku()))
                if not any(_icinde_mi(hedef, k) for k in self.uygulama.izinli_kokler()):
                    raise ValueError("yalnız çıktı klasörü açılabilir")
                cikti_klasoru_ac(str(hedef))
                self._json(HTTPStatus.OK, {"tamam": True})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"hata": "yok"})
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
            ifadeler.append(f"{anahtar}={metin}")
        hedef = self.uygulama.yurutucu.devam(no, asama=asama, yeni_is=bool(veri.get("yeni_is")),
                                             ayar_ifadeleri=ifadeler)
        self._json(HTTPStatus.OK, {"tamam": True, "is": hedef})


class Sunucu(http.server.ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16


def main(argv: list[str] | None = None) -> int:
    ayr = argparse.ArgumentParser(prog="dubla-web", description="Dublaj hattı yerel web arayüzü (127.0.0.1)")
    ayr.add_argument("--port", type=int, default=0, help="0 = boş port seç")
    ayr.add_argument("--tarayici-acma", action="store_true", help="tarayıcıyı otomatik açma")
    ayr.add_argument("--yukleme-siniri-mb", type=int, default=8192)
    args = ayr.parse_args(argv)

    sunucu = Sunucu(("127.0.0.1", args.port), Isleyici)
    port = sunucu.server_address[1]
    uygulama = Uygulama(port, args.yukleme_siniri_mb)
    Isleyici.uygulama = uygulama
    adres = f"http://127.0.0.1:{port}/?t={uygulama.belirtec}"
    print(f"Dublaj hattı web arayüzü: {adres}", flush=True)
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
