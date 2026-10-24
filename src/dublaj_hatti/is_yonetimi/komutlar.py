"""`dubla` komut satırının iş yönetimi alt komutları.

    dubla isler [--hepsi] [--limit N] [--json]        # iş geçmişi (en yeni önce)
    dubla isler --kuyruk | --soyagaci N | --arsivle N | --arsivden-cikar N | --iptal N
    dubla isler --kurtar | --bayat-iptal DAKIKA        # açılış kurtarma / bayat iş iptali (elle)
    dubla sorunlu [--json]                            # hata alan / kesilen işler + devam seçenekleri
    dubla devam <is no | iş klasörü> [--asama X] [--yeni-is] [--ayar a.b=c ...]
    dubla is-calistir <is no>                         # (arayüzlerin iç komutu) kuyruktaki işi çalıştırır
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dublaj_hatti.is_yonetimi.calistirici import depo_ac, is_ayari, isi_calistir
from dublaj_hatti.is_yonetimi.depo import IsDeposu, IsHatasi, degisiklikleri_coz, is_ozeti

IS_KOMUTLARI = ("isler", "sorunlu", "devam", "is-calistir")


def alt_komutlari_ekle(alt: Any, ortak: Callable[[argparse.ArgumentParser], None]) -> None:
    isler = alt.add_parser("isler", help="iş geçmişi, kuyruk, arşiv, soyağacı")
    isler.add_argument("--hepsi", action="store_true", help="arşivlenmiş işleri de göster")
    isler.add_argument("--limit", type=int, default=30)
    isler.add_argument("--json", action="store_true")
    eylem = isler.add_mutually_exclusive_group()
    eylem.add_argument("--kuyruk", action="store_true", help="bekleyen işleri sırasıyla göster")
    eylem.add_argument("--soyagaci", type=int, metavar="IS", help="işin soyağacını göster")
    eylem.add_argument("--arsivle", type=int, metavar="IS", help="iş kaydını listeden gizle (dosyalar silinmez)")
    eylem.add_argument("--arsivden-cikar", type=int, metavar="IS")
    eylem.add_argument("--iptal", type=int, metavar="IS", help="kuyruktaki / ertelenen işi iptal et")
    eylem.add_argument("--kurtar", action="store_true", help="süreci ölmüş yarım işleri toparla")
    eylem.add_argument("--bayat-iptal", type=int, metavar="DAKIKA", help="DAKIKA'dan eski, süreci olmayan işleri iptal et")
    ortak(isler)

    sorunlu = alt.add_parser("sorunlu", help="hata alan ya da yarıda kesilen işler ve devam seçenekleri")
    sorunlu.add_argument("--limit", type=int, default=10)
    sorunlu.add_argument("--json", action="store_true")
    ortak(sorunlu)

    devam = alt.add_parser("devam", help="işi kaldığı yerden ya da seçilen aşamadan sürdür")
    devam.add_argument("is_", metavar="IS", help="iş numarası ya da iş klasörü")
    devam.add_argument("--asama", help="yeniden çalışacak ilk aşama (kimlik, ad ya da sıra no); yeni işe kopyalar")
    devam.add_argument("--yeni-is", action="store_true", help="kaynak işi değiştirmeden yeni işe kopyalayarak sürdür")
    devam.add_argument("--lisans-onay", action="store_true",
                       help="seçili ticari olmayan / şartlı motorun lisans uyarısını okudum, kabul ediyorum")
    ortak(devam)

    calistir = alt.add_parser("is-calistir", help=argparse.SUPPRESS)
    calistir.add_argument("is_", metavar="IS", type=int)
    ortak(calistir)


def _yaz_tablo(isler: list[dict[str, Any]]) -> None:
    if not isler:
        print("kayıt yok")
        return
    for i in isler:
        o = is_ozeti(i)
        satir = f"#{o['is']:<5} {o['durum_adi']:<15} {o['komut']:<10} {o['kip']:<12} {o['kaynak_adi'][:40]:<40}"
        if o["durum"] in ("failed", "cancelled"):
            satir += f"  ✗ {o['basarisiz_asama_adi'] or '-'}: {o['hata'][:80]}"
        elif o["son_asama"]:
            satir += f"  son: {o['son_asama_adi']}"
        if o["ebeveyn"]:
            satir += f"  (← #{o['ebeveyn']})"
        print(satir)


def _is_bul(depo: IsDeposu, deger: str) -> dict[str, Any]:
    if deger.strip().lstrip("#").isdigit():
        kayit = depo.getir(int(deger.strip().lstrip("#")))
    else:
        kayit = depo.run_dir_ile_bul(deger)
    if not kayit:
        raise IsHatasi(f"iş bulunamadı: {deger} (dubla isler ile bakın)")
    return kayit


def sorunlu_raporu(depo: IsDeposu, limit: int = 10) -> list[dict[str, Any]]:
    rapor = []
    for i in depo.son_sorunlu(limit):
        o = is_ozeti(i)
        o["devam_secenekleri"] = depo.devam_secenekleri(i)
        o["yeniden_calistir"] = depo.yeniden_calistirma_secenekleri(i)
        rapor.append(o)
    return rapor


def calistir(args: argparse.Namespace, ayar: dict[str, Any], ortami_hazirla: Callable[[str], None],
             olay_yaz: Callable[[dict[str, Any]], None]) -> int:
    try:
        depo = depo_ac(ayar)
        if args.komut == "isler":
            return _isler(depo, args)
        if args.komut == "sorunlu":
            rapor = sorunlu_raporu(depo, args.limit)
            if args.json:
                print(json.dumps(rapor, ensure_ascii=False, indent=2))
                return 0
            if not rapor:
                print("sorunlu iş yok")
            for o in rapor:
                print(f"#{o['is']} {o['durum_adi']} · {o['kaynak_adi']} · kesildiği aşama: "
                      f"{o['basarisiz_asama_adi'] or '-'} · {o['hata'][:120]}")
                if o["devam_secenekleri"]:
                    son = o["devam_secenekleri"][-1]
                    print(f"    devam: dubla devam {o['is']}   (korunan son aşama: {son['ad']})")
                    adlar = ", ".join(s["restart_stage_id"] for s in o["yeniden_calistir"])
                    print(f"    aşamadan: dubla devam {o['is']} --asama <{adlar}>")
                else:
                    print("    korunabilecek checkpoint yok; baştan çalıştırın")
            return 0
        if args.komut == "devam":
            return _devam(depo, args, ortami_hazirla, olay_yaz)
        if args.komut == "is-calistir":
            kayit = depo.getir(args.is_)
            if not kayit:
                raise IsHatasi(f"iş bulunamadı: #{args.is_}")
            ortami_hazirla(str(is_ayari(kayit).get("genel.cihaz") or "auto"))
            return isi_calistir(depo, args.is_, olay_yaz)
    except IsHatasi as hata:
        olay_yaz({"event": "hata", "mesaj": str(hata)})
        print(f"hata: {hata}", file=__import__("sys").stderr)
        return 2
    return 2


def _isler(depo: IsDeposu, args: argparse.Namespace) -> int:
    def tamam(ok: bool, mesaj: str) -> int:
        print(mesaj if ok else f"yapılamadı: {mesaj} (iş yok ya da etkin)")
        return 0 if ok else 1

    if args.arsivle:
        return tamam(depo.arsivle(args.arsivle), f"iş #{args.arsivle} arşivlendi (klasör silinmedi)")
    if args.arsivden_cikar:
        return tamam(depo.arsivle(args.arsivden_cikar, geri_al=True), f"iş #{args.arsivden_cikar} listeye döndü")
    if args.iptal:
        return tamam(depo.iptal(args.iptal), f"iş #{args.iptal} iptal edildi")
    if args.kurtar:
        kurtarilan = depo.acilista_kurtar()
        print(f"toparlanan iş: {len(kurtarilan)}")
        for i in kurtarilan:
            print(f"  #{i['job_id']} → {i['yeni_durum']}")
        return 0
    if args.bayat_iptal:
        print(f"iptal edilen bayat iş: {depo.bayat_iptal(args.bayat_iptal)}")
        return 0
    if args.soyagaci:
        print(json.dumps(depo.soyagaci(args.soyagaci), ensure_ascii=False, indent=2))
        return 0
    isler = depo.kuyruk() if args.kuyruk else depo.listele(args.limit, arsiv_dahil=args.hepsi)
    if args.json:
        print(json.dumps([is_ozeti(i) for i in isler], ensure_ascii=False, indent=2))
    else:
        _yaz_tablo(isler)
    return 0


def _devam(depo: IsDeposu, args: argparse.Namespace, ortami_hazirla: Callable[[str], None],
           olay_yaz: Callable[[dict[str, Any]], None]) -> int:
    kayit = _is_bul(depo, args.is_)
    # Aynı değeri tekrar veren --ayar değişiklik sayılmaz: iş yerinde sürer (gereksiz kopya açılmaz).
    degisen = degisiklikleri_coz(is_ayari(kayit), list(args.ayar)) if args.ayar else {}
    yeni_is = bool(args.yeni_is or args.asama or degisen or kayit["status"] == "completed")
    hedef_ayar = {**is_ayari(kayit), **degisen}  # sürecek işin ayarı; lisans sorusu iş açılmadan önce
    if kayit.get("command") == "transkript":  # transkript işi ses motoru çalıştırmaz
        hedef_ayar["genel.is_turu"] = "transkript"
    if not _lisans_sor(hedef_ayar, bool(getattr(args, "lisans_onay", False)), not args.olaylar_json):
        return 2
    if yeni_is:
        hedef = depo.devam_iste(int(kayit["job_id"]), list(args.ayar), args.asama, arayuz="cli")
        cocuk = depo.getir(hedef) or {}
        plan = json.loads(cocuk.get("checkpoint_plan_json") or "{}")
        print(f"yeni iş #{hedef}: iş #{kayit['job_id']} kaydından, korunan son aşama "
              f"{cocuk.get('resume_after_stage')}; değişen ayar: {len(plan.get('changed_fields') or [])}")
    else:
        hedef = depo.yerinde_devam(int(kayit["job_id"]))
        print(f"iş #{hedef} kaldığı yerden sürüyor ({Path(str(kayit['run_dir'])).name})")
    hedef_ayar = is_ayari(depo.getir(hedef) or kayit)
    ortami_hazirla(str(hedef_ayar.get("genel.cihaz") or "auto"))
    return isi_calistir(depo, hedef, olay_yaz)


def _lisans_sor(ayar: dict[str, Any], onay: bool, etkilesimli: bool) -> bool:
    """`dubla devam` (--ayar ile motor değişmiş olabilir): `dubla <video>` ile aynı tek kapı ve aynı soru.
    Hayırda iş açılmaz (çıkış 2); iş çalıştırıcı da onaysız işi çalıştırmaz (calistirici._hatti_kos)."""
    import sys

    from dublaj_hatti.lisans_onayi import LisansOnayiGerekli, kapi, komut_satiri_onayi

    try:
        kapi(ayar, None, onay)
        return True
    except LisansOnayiGerekli as gerek:
        return komut_satiri_onayi(gerek, etkilesimli and sys.stdin.isatty())
