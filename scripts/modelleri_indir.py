"""Model ve araç indirici: yalnız `scripts/modeller.json` içindeki sabit adres + sha256 ile.

    python scripts/modelleri_indir.py --adim supertonic,ceviri,stt,hizalama,konusmaci,ffmpeg [--kok <repo>]
    python scripts/modelleri_indir.py --liste

Kurallar: yalnız https; dosya önce `.part` olarak iner, sha256 ve boyut tutarsa yerine konur; doğru dosya
varsa atlanır (yeniden çalıştırılabilir). Hiçbir ağırlık repoda değildir; hepsi asıl kaynağından iner.
Yalnız standart kütüphane kullanır.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("modeller.json")
VARSAYILAN_ADIMLAR = ("supertonic", "ceviri", "stt", "hizalama", "konusmaci", "ffmpeg")
IZINLI_ALAN_ADLARI = ("huggingface.co", "download.pytorch.org", "raw.githubusercontent.com", "github.com",
                      "www.modelscope.cn", "objects.githubusercontent.com")


def sha256_dosya(yol: Path) -> str:
    ozet = hashlib.sha256()
    with open(yol, "rb") as dosya:
        for parca in iter(lambda: dosya.read(1 << 20), b""):
            ozet.update(parca)
    return ozet.hexdigest()


def _guvenli_hedef(kok: Path, goreli: str) -> Path:
    hedef = (kok / goreli).resolve()
    if not str(hedef).startswith(str((kok / "runtime_assets").resolve())):
        raise SystemExit(f"manifest hedefi runtime_assets dışında: {goreli}")
    return hedef


def https_dogrula(url: str) -> str:
    """Yalnız https şeması ve izinli alan adı; kullanıcı:parola@ ve başka şema (file:, ftp:, data:) reddedilir."""
    parca = urllib.parse.urlsplit(url)
    if parca.scheme != "https" or parca.username or parca.password or parca.hostname not in IZINLI_ALAN_ADLARI:
        raise SystemExit(f"izinli olmayan adres: {url}")
    return url


class _YalnizHttpsYonlendirme(urllib.request.HTTPRedirectHandler):
    """CDN yönlendirmesi (ör. HF -> depolama) izinli, ama yalnız https'e; http/file'a düşüş reddedilir."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise urllib.error.HTTPError(newurl, code, "https olmayan yönlendirme reddedildi", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_ACICI = urllib.request.build_opener(_YalnizHttpsYonlendirme)


def indir(kayit: dict, kok: Path) -> str:
    url = https_dogrula(kayit["url"])
    hedef = _guvenli_hedef(kok, kayit["hedef"])
    if hedef.is_file() and hedef.stat().st_size == kayit["boyut"] and sha256_dosya(hedef) == kayit["sha256"]:
        return "var"
    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_name(hedef.name + ".part")
    # S310: şema yukarıda https_dogrula ile yalnız https'e sınırlı; yönlendirme de yalnız https (_ACICI).
    istek = urllib.request.Request(url, headers={"User-Agent": "dublaj-hatti-kurulum"})  # noqa: S310
    for deneme in range(1, 4):
        try:
            with _ACICI.open(istek, timeout=60) as yanit, open(gecici, "wb") as cikti:
                inen, son = 0, time.time()
                for parca in iter(lambda: yanit.read(1 << 20), b""):
                    cikti.write(parca)
                    inen += len(parca)
                    if time.time() - son > 5:
                        print(f"    {inen / 1e6:.0f}/{kayit['boyut'] / 1e6:.0f} MB", flush=True)
                        son = time.time()
            break
        except OSError as hata:
            if deneme == 3:
                raise SystemExit(f"indirilemedi ({hata}): {url}") from hata
            time.sleep(5 * deneme)
    gelen = sha256_dosya(gecici)
    if gelen != kayit["sha256"] or gecici.stat().st_size != kayit["boyut"]:
        gecici.unlink(missing_ok=True)
        raise SystemExit(f"sha256 tutmadı: {kayit['hedef']}\n  beklenen {kayit['sha256']}\n  gelen    {gelen}")
    os.replace(gecici, hedef)
    return "indi"


def hf_refs_yaz(kok: Path, kayitlar: list[dict]) -> None:
    """HF önbellek düzeni: models--org--ad/refs/main = commit (çevrimdışı çözüm için)."""
    for kayit in kayitlar:
        parcalar = Path(kayit["hedef"]).parts
        if "snapshots" not in parcalar:
            continue
        i = parcalar.index("snapshots")
        model_kok = kok.joinpath(*parcalar[:i])
        refs = model_kok / "refs" / "main"
        refs.parent.mkdir(parents=True, exist_ok=True)
        refs.write_text(parcalar[i + 1], encoding="utf-8")


def ffmpeg_ac(kok: Path, kayit: dict) -> None:
    arsiv = _guvenli_hedef(kok, kayit["hedef"])
    hedef_bin = kok / "runtime_assets" / "ffmpeg" / "bin"
    if (hedef_bin / "ffmpeg.exe").is_file() and (hedef_bin / ".sha256").is_file() \
            and (hedef_bin / ".sha256").read_text().strip() == kayit["sha256"]:
        return
    hedef_bin.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(arsiv) as zf:
        for ad in zf.namelist():
            if ad.endswith(("/bin/ffmpeg.exe", "/bin/ffprobe.exe")) and ".." not in ad:
                (hedef_bin / Path(ad).name).write_bytes(zf.read(ad))
            if ad.endswith(("/LICENSE", "/README.txt")) and ".." not in ad:
                (hedef_bin.parent / Path(ad).name).write_bytes(zf.read(ad))
    (hedef_bin / ".sha256").write_text(kayit["sha256"], encoding="utf-8")


def main(argv=None) -> int:
    ayr = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ayr.add_argument("--adim", default=",".join(VARSAYILAN_ADIMLAR))
    ayr.add_argument("--kok", type=Path, default=KOK)
    ayr.add_argument("--liste", action="store_true")
    args = ayr.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["dosyalar"]
    if args.liste:
        for kayit in manifest:
            print(f"{kayit['adim']:10} {kayit['boyut'] / 1e6:9.1f} MB  {kayit['lisans']:24}  {kayit['hedef']}")
        return 0
    adimlar = [a.strip() for a in args.adim.split(",") if a.strip()]
    bilinmeyen = set(adimlar) - {k["adim"] for k in manifest}
    if bilinmeyen:
        raise SystemExit(f"bilinmeyen adım: {', '.join(sorted(bilinmeyen))}")
    kok = args.kok.resolve()
    for adim in adimlar:
        kayitlar = [k for k in manifest if k["adim"] == adim]
        toplam = sum(k["boyut"] for k in kayitlar) / 1e6
        print(f"== {adim}: {len(kayitlar)} dosya, {toplam:.0f} MB", flush=True)
        for kayit in kayitlar:
            print(f"  {indir(kayit, kok)}: {kayit['hedef']}", flush=True)
        hf_refs_yaz(kok, kayitlar)
        if adim == "ffmpeg":
            ffmpeg_ac(kok, kayitlar[0])
        print(f"{adim.upper()}_OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
