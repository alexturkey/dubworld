"""`dubla-gui`: DubWorld'ü masaüstü programı gibi açar. Tek arayüz web arayüzüdür; bu komut yerel sunucuyu başlatır ve
sayfayı tarayıcının "uygulama penceresi" kipinde (adres çubuğu yok, kendi simgesi ve penceresi) açar.

Sıra: Microsoft Edge (Windows 10/11'de kurulu gelir) > Google Chrome > Chromium > varsayılan tarayıcı (normal sekme).
Pencere ayrı bir profille açılır (kullanıcının tarayıcısına, sekmelerine, eklentilerine dokunulmaz).
Kapanış: pencere süreci bitince ve sayfa 25 saniyedir yoklamıyorsa sunucu kapanır, süren iş durdurulur (iş kaydı ve
checkpoint kalır; İşler'den sürdürülür). Bazı tarayıcılar açılınca hemen çıkıp pencereyi var olan sürece devreder;
bu yüzden kapanış kararı yalnız sürece değil sayfanın yoklamasına da bakar.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from dublaj_hatti import web

NABIZ_ZAMAN_ASIMI_SN = 25.0
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def pencere_tarayicisi() -> str | None:
    """Uygulama penceresi açabilen tarayıcının yolu (Chromium tabanlı: Edge, Chrome, Chromium) ya da None."""
    adaylar: list[str] = []
    if sys.platform == "win32":
        for degisken in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
            kok = os.environ.get(degisken)
            if kok:
                adaylar += [str(Path(kok) / "Microsoft/Edge/Application/msedge.exe"),
                            str(Path(kok) / "Google/Chrome/Application/chrome.exe")]
    elif sys.platform == "darwin":
        adaylar += ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    for ad in ("msedge", "microsoft-edge", "google-chrome", "chromium", "chromium-browser"):
        bulunan = shutil.which(ad)
        if bulunan:
            adaylar.append(bulunan)
    return next((a for a in adaylar if Path(a).is_file()), None)


def pencere_komutu(tarayici: str, adres: str, profil: Path, genislik: int = 1280, yukseklik: int = 860,
                   konum: str = "") -> list[str]:
    komut = [tarayici, f"--app={adres}", f"--user-data-dir={profil}", f"--window-size={genislik},{yukseklik}",
             "--no-first-run", "--no-default-browser-check", "--disable-features=Translate"]
    if konum:
        komut.append(f"--window-position={konum}")
    return komut


def kapanmali(surec_bitti: bool, son_nabiz: float, simdi: float) -> bool:
    """Sunucu kapanır mı: pencere süreci bitti ve sayfa bir süredir yoklamıyor."""
    return surec_bitti and simdi - son_nabiz > NABIZ_ZAMAN_ASIMI_SN


def main(argv: list[str] | None = None) -> int:
    ayr = argparse.ArgumentParser(prog="dubla-gui", description="DubWorld'ü kendi penceresinde açar (web arayüzü)")
    ayr.add_argument("--yukleme-siniri-mb", type=int, default=8192)
    ayr.add_argument("--pencere-konumu", default="", help=argparse.SUPPRESS)  # deneme: "x,y" (ekran dışı)
    args = ayr.parse_args(argv)

    sunucu = web.Sunucu(("127.0.0.1", 0), web.Isleyici)
    uygulama = web.Uygulama(sunucu.server_address[1], args.yukleme_siniri_mb)
    web.Isleyici.uygulama = uygulama
    adres = f"http://127.0.0.1:{uygulama.port}/?t={uygulama.belirtec}"
    threading.Thread(target=sunucu.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True).start()

    tarayici = pencere_tarayicisi()
    surec: subprocess.Popen | None = None
    if tarayici:
        profil = web.cikti_koku() / "_uygulama_penceresi"
        profil.mkdir(parents=True, exist_ok=True)
        surec = subprocess.Popen(pencere_komutu(tarayici, adres, profil, konum=args.pencere_konumu),
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=NO_WINDOW)
    else:
        webbrowser.open(adres)
    uygulama.son_nabiz = time.time()
    try:
        while not kapanmali(surec is None or surec.poll() is not None, uygulama.son_nabiz, time.time()):
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        uygulama.yurutucu.kapat()
        sunucu.shutdown()
        sunucu.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
