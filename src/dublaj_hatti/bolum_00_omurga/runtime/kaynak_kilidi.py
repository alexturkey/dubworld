"""Makine geneli kaynak kilidi (GPU sırası).

Aynı bilgisayarda birden çok süreç (masaüstü arayüz, web arayüzü, komut satırı, başka araçlar) tek GPU'yu
paylaşır. Her kaynağın bir kapasitesi vardır (GPU: 1); kilit, kilit klasöründe `O_EXCL` ile açılan küçük bir
JSON dosyasıdır ve sahibinin PID'ine bağlıdır: süreç ölünce kilit kendiliğinden geçersizleşir (bayat kilit
bir sonraki okumada silinir). PID'siz kilit yalnız süreyle (`--sure`) alınabilir.

Kilit klasörü: `DUBLAJ_KILIT_KLASORU` ortam değişkeni, yoksa işletim sisteminin geçici klasöründe
`dublaj_hatti_kaynak_kilitleri` (makine geneli; repoya ya da çıktı klasörüne yazılmaz).

Komut satırı:
    python -m dublaj_hatti.bolum_00_omurga.runtime.kaynak_kilidi durum [--json]
    python -m dublaj_hatti.bolum_00_omurga.runtime.kaynak_kilidi calistir --kaynak gpu --sahip ajan:ad \
        --amac test --bekle 600 -- <komut ...>
    python -m dublaj_hatti.bolum_00_omurga.runtime.kaynak_kilidi al --kaynak gpu --sahip ajan:ad --amac x --sure 30
    python -m dublaj_hatti.bolum_00_omurga.runtime.kaynak_kilidi birak --kilit <yol>
Çıkış kodu 75: kaynak meşgul (bekleme süresi doldu).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from dublaj_hatti.bolum_00_omurga.runtime.surec_durumu import process_matches, process_start_time

KILIT_KLASORU_ENV = "DUBLAJ_KILIT_KLASORU"
KAYNAKLAR: dict[str, dict[str, Any]] = {
    "gpu": {"kapasite": 1, "aciklama": "Tek NVIDIA GPU: transkripsiyon, hizalama, ses ayrıştırma, seslendirme, NVENC"},
    "cpu_agir": {"kapasite": 2, "aciklama": "Uzun işlemci işi: CPU transkripsiyon, CPU seslendirme, x264 kodlama"},
    "ag": {"kapasite": 3, "aciklama": "İndirme"},
    "ucretli_api": {"kapasite": 2, "aciklama": "Ücretli transkripsiyon ya da çeviri API çağrısı"},
}
SAHIP_ONEKLERI = ("ajan:", "uygulama:", "kullanici:")
KAYNAK_MESGUL_CIKIS_KODU = 75


class KaynakMesgulError(RuntimeError):
    def __init__(self, kaynak: str, kullananlar: list[dict[str, Any]]) -> None:
        self.kaynak = kaynak
        self.kullananlar = kullananlar
        ozet = "; ".join(str(k.get("aciklama", "")) for k in kullananlar) or "bilinmiyor"
        super().__init__(f"KAYNAK_MESGUL kaynak={kaynak} kullanan={ozet}")


def kilit_klasoru() -> Path:
    ham = os.environ.get(KILIT_KLASORU_ENV, "").strip()
    return Path(ham).expanduser() if ham else Path(tempfile.gettempdir()) / "dublaj_hatti_kaynak_kilitleri"


def _kaynak_tanimi(kaynak: str) -> dict[str, Any]:
    if kaynak not in KAYNAKLAR:
        raise ValueError(f"Bilinmeyen kaynak: {kaynak}")
    return KAYNAKLAR[kaynak]


def _simdi() -> datetime:
    """UTC (saat dilimi bilgili): yaz/kış saati geçişi ve saat dilimi değişimi süreyi kaydırmaz (D3)."""
    return datetime.now(UTC).replace(microsecond=0)


def _zaman_oku(deger: str) -> datetime:
    """Kayıttaki zaman; saat dilimsiz eski kayıtlar yerel saat kabul edilip UTC'ye çevrilir."""
    zaman = datetime.fromisoformat(deger)
    return zaman.astimezone(UTC) if zaman.tzinfo is None else zaman


def _kilit_gecerli_mi(kayit: dict[str, Any]) -> bool:
    son = str(kayit.get("son_gecerlilik") or "")
    if son:
        try:
            if _zaman_oku(son) < _simdi():
                return False
        except ValueError:
            return False
    pid = int(kayit.get("pid") or 0)
    if pid > 0:
        return process_matches(pid, str(kayit.get("pid_baslangic") or ""))
    return bool(son)


def kilitler(kaynak: str) -> list[dict[str, Any]]:
    """Kaynağın geçerli kilitleri; bayat (sahibi ölmüş ya da süresi geçmiş) kilitler silinir."""
    _kaynak_tanimi(kaynak)
    klasor = kilit_klasoru()
    if not klasor.is_dir():
        return []
    sonuc = []
    for yol in sorted(klasor.glob(f"{kaynak}__*.json")):
        try:
            kayit = json.loads(yol.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(kayit, dict) or not _kilit_gecerli_mi(kayit):
            yol.unlink(missing_ok=True)
            continue
        kayit["kilit_dosyasi"] = str(yol)
        kayit["aciklama"] = (f"{kayit.get('sahip')}: {kayit.get('amac')} "
                             f"(pid {kayit.get('pid')}, {kayit.get('baslangic')} itibarıyla)")
        sonuc.append(kayit)
    return sonuc


kullananlar = kilitler


def durum() -> list[dict[str, Any]]:
    sonuc = []
    for kaynak, tanim in KAYNAKLAR.items():
        liste = kilitler(kaynak)
        dolu = len(liste)
        sinyal = "yesil" if dolu == 0 else ("kirmizi" if dolu >= tanim["kapasite"] else "sari")
        sonuc.append({"kaynak": kaynak, "sinyal": sinyal, "kullanilan": dolu, "kapasite": tanim["kapasite"],
                      "aciklama": tanim["aciklama"], "kullananlar": [k["aciklama"] for k in liste]})
    return sonuc


def kilit_al(kaynak: str, sahip: str, amac: str, pid: int | None = None, sure_dakika: float | None = None) -> Path:
    tanim = _kaynak_tanimi(kaynak)
    if not sahip.startswith(SAHIP_ONEKLERI):
        raise ValueError(f"Sahip {'/'.join(SAHIP_ONEKLERI)}<ad> biçiminde olmalı")
    if pid == 0 and not sure_dakika:
        raise ValueError("PID'e bağlı olmayan kilit için süre gerekli")
    liste = kilitler(kaynak)
    if len(liste) >= tanim["kapasite"]:
        raise KaynakMesgulError(kaynak, liste)
    klasor = kilit_klasoru()
    klasor.mkdir(parents=True, exist_ok=True)
    baslangic = _simdi()
    kayit = {
        "kaynak": kaynak, "sahip": sahip, "amac": amac,
        "pid": int(os.getpid() if pid is None else pid),
        "pid_baslangic": process_start_time(int(os.getpid() if pid is None else pid)),
        "baslangic": baslangic.isoformat(),
        "son_gecerlilik": (baslangic + timedelta(minutes=sure_dakika)).isoformat() if sure_dakika else "",
        "kimlik": uuid.uuid4().hex,
    }
    for slot in range(tanim["kapasite"]):
        yol = klasor / f"{kaynak}__{slot}.json"
        try:
            tanitici = os.open(str(yol), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue
        with os.fdopen(tanitici, "w", encoding="utf-8") as akis:
            json.dump(kayit, akis, ensure_ascii=False, indent=2)
        guncel = kilitler(kaynak)
        if len(guncel) > tanim["kapasite"]:
            yol.unlink(missing_ok=True)
            raise KaynakMesgulError(kaynak, [k for k in guncel if k.get("kimlik") != kayit["kimlik"]])
        return yol
    raise KaynakMesgulError(kaynak, kilitler(kaynak))


def kilit_birak(yol: str | Path) -> None:
    Path(yol).unlink(missing_ok=True)


@contextmanager
def kaynak_kullan(kaynaklar: list[str], sahip: str, amac: str, bekle_saniye: float = 0.0, pid: int | None = None,
                  bekleme_bildir: Any = None, aralik_sn: float = 5.0) -> Iterator[list[Path]]:
    """Kaynakları sırayla alır; meşgulse `bekle_saniye` boyunca bekler. `bekleme_bildir(kaynak, kullananlar)` bir
    kez çağrılır (arayüz "GPU sırası bekleniyor" gösterir)."""
    bitis = time.monotonic() + max(0.0, bekle_saniye)
    alinan: list[Path] = []
    try:
        for kaynak in kaynaklar:
            bildirildi = False
            while True:
                try:
                    alinan.append(kilit_al(kaynak, sahip, amac, pid=pid))
                    break
                except KaynakMesgulError as hata:
                    if time.monotonic() >= bitis:
                        raise
                    if callable(bekleme_bildir) and not bildirildi:
                        bekleme_bildir(kaynak, hata.kullananlar)
                        bildirildi = True
                    time.sleep(aralik_sn)
        yield alinan
    finally:
        for yol in alinan:
            kilit_birak(yol)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kaynak_kilidi", description="Makine geneli kaynak kilidi (GPU sırası).")
    komutlar = parser.add_subparsers(dest="komut", required=True)
    durum_k = komutlar.add_parser("durum")
    durum_k.add_argument("--json", action="store_true")
    calistir = komutlar.add_parser("calistir")
    calistir.add_argument("--kaynak", action="append", required=True, choices=sorted(KAYNAKLAR))
    calistir.add_argument("--sahip", required=True)
    calistir.add_argument("--amac", required=True)
    calistir.add_argument("--bekle", type=float, default=0.0, help="saniye")
    calistir.add_argument("komut_satiri", nargs=argparse.REMAINDER)
    al = komutlar.add_parser("al")
    al.add_argument("--kaynak", required=True, choices=sorted(KAYNAKLAR))
    al.add_argument("--sahip", required=True)
    al.add_argument("--amac", required=True)
    al.add_argument("--sure", type=float, required=True, help="dakika")
    birak = komutlar.add_parser("birak")
    birak.add_argument("--kilit", required=True)
    args = parser.parse_args(argv)

    if args.komut == "durum":
        liste = durum()
        if args.json:
            print(json.dumps(liste, ensure_ascii=False, indent=2))
        else:
            for kayit in liste:
                print(f"{kayit['sinyal'].upper():8} {kayit['kaynak']:12} {kayit['kullanilan']}/{kayit['kapasite']}")
                for satir in kayit["kullananlar"]:
                    print(f"         - {satir}")
        return 0
    if args.komut == "birak":
        kilit_birak(args.kilit)
        print("KILIT_BIRAKILDI")
        return 0
    if args.komut == "al":
        try:
            yol = kilit_al(args.kaynak, args.sahip, args.amac, pid=0, sure_dakika=args.sure)
        except KaynakMesgulError as hata:
            print(str(hata))
            return KAYNAK_MESGUL_CIKIS_KODU
        print(f"KILIT={yol}")
        return 0
    komut_satiri = [parca for parca in args.komut_satiri if parca != "--"]
    if not komut_satiri:
        parser.error("calistir için '--' sonrasında komut gerekli")
    t0 = time.perf_counter()
    try:
        with kaynak_kullan(args.kaynak, args.sahip, args.amac, bekle_saniye=args.bekle):
            t1 = time.perf_counter()
            kod = subprocess.run(komut_satiri, check=False).returncode  # noqa: S603 - kullanıcının verdiği argüman listesi, kabuk yok
            print(f"KILIT: kaynak={'+'.join(args.kaynak)} bekleme={t1 - t0:.2f} sn "
                  f"calisma={time.perf_counter() - t1:.2f} sn sahip={args.sahip}", file=sys.stderr, flush=True)
            return kod
    except KaynakMesgulError as hata:
        print(str(hata))
        return KAYNAK_MESGUL_CIKIS_KODU


if __name__ == "__main__":
    raise SystemExit(main())
