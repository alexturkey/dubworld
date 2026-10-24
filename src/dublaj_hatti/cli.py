"""`dubla` komut satırı.

    dubla video.mp4                         # Önerilen akış (önerilen varsayılanlar) ile Türkçe dublaj
    dubla video.mp4 --ayar ses.motor=voxcpm2 --ayar altyazi.mod=word
    dubla transkript video.mp4 --bicim srt  # yalnız transkript / altyazı dosyası
    dubla kontrol                           # donanım, motorlar, çeviri arka uçları, ffmpeg
    dubla ayarlar                           # geçerli ayarlar (katmanlar birleşmiş hâli) + uyumluluk uyarıları
    dubla isler                             # iş geçmişi (iş deposu); --kuyruk, --soyagaci N, --arsivle N
    dubla sorunlu                           # hata alan / kesilen işler ve devam seçenekleri
    dubla devam 12 [--asama ceviri] [--yeni-is] [--ayar ses.motor=voxcpm2]   # kaldığı yerden sürdür

Her aşama tek başına (asama_komutlari.py; Python'dan aynısı: dublaj_hatti.api; dosya biçimleri: docs/mimari.md):
    dubla indir URL · ses-cikar · ayir · yaziya-dok · hizala · cevir · seslendir · altyazi · birlestir

Çıkış kodları: 0 başarı, 1 iş hatası, 2 kullanım/ayar hatası, 75 kaynak (GPU) meşgul, 130 durduruldu.
`--olaylar-json`: her aşama olayı stdout'a tek satır JSON yazılır (arayüzler bunu okur); günlük stderr'e gider.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from collections.abc import Callable
from typing import Any

from dublaj_hatti import __version__
from dublaj_hatti.asama_komutlari import ASAMA_KOMUTLARI
from dublaj_hatti.asama_komutlari import alt_komutlari_ekle as asama_komutlarini_ekle
from dublaj_hatti.is_yonetimi.komutlar import IS_KOMUTLARI, alt_komutlari_ekle
from dublaj_hatti.kaynak_girdisi import VIDEO_UZANTILARI  # noqa: F401  (eski içe aktaranlar için)
from dublaj_hatti.yapilandirma import PROJE_KOKU, AyarHatasi, ayarlari_ic_ice, ayarlari_yukle

ALT_KOMUTLAR = ("dubla", "transkript", "kontrol", "ayarlar", *IS_KOMUTLARI, *ASAMA_KOMUTLARI)
TRANSKRIPT_BICIMLERI = ("srt", "plain", "timestamped", "paragraph")
logger = logging.getLogger("dublaj_hatti")


def ortami_hazirla(cihaz: str) -> None:
    """torch içe aktarılmadan önce çağrılır: yerel ffmpeg PATH'e, CPU seçiminde CUDA gizlenir."""
    ffmpeg_bin = PROJE_KOKU / "runtime_assets" / "ffmpeg" / "bin"
    if ffmpeg_bin.is_dir():
        os.environ["PATH"] = str(ffmpeg_bin) + os.pathsep + os.environ.get("PATH", "")
    if cihaz == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    # Model önbelleği repo içinde (kurulum betiği oraya indirir); çalışma anında ağdan model indirilmez.
    # Bilerek çevrimiçi çalışmak için: DUBLAJ_CEVRIMICI=1
    from dublaj_hatti.bolum_00_omurga.runtime import output_paths  # noqa: F401  (.env yüklenir; anahtarlar alt süreçlere geçer)
    from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import apply_huggingface_env, apply_torch_env

    apply_huggingface_env()
    apply_torch_env()
    if os.environ.get("DUBLAJ_CEVRIMICI") != "1":
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"


def _olay_yazici(etkin: bool) -> Callable[[dict[str, Any]], None]:
    def yaz(olay: dict[str, Any]) -> None:
        if etkin:
            sys.stdout.write(json.dumps(olay, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    return yaz


def _kaynak_dogrula(kaynak: str) -> str:
    """Yerel dosya ya da bağlantı; bağlantı türüne göre yalnız gereken isteğe bağlı araç aranır (kaynak_girdisi)."""
    from dublaj_hatti.kaynak_girdisi import KaynakHatasi, kaynak_dogrula

    try:
        return kaynak_dogrula(kaynak)
    except KaynakHatasi as hata:
        raise AyarHatasi(str(hata)) from None


def _ortak_secenekler(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ayarlar", help="ek ayar dosyası (.toml); varsayılanın üstüne yazar")
    parser.add_argument("--ayar", action="append", default=[], metavar="BOLUM.AD=DEGER",
                        help="tek ayarı değiştir (birden çok kez verilebilir), ör. ses.motor=voxcpm2")
    parser.add_argument("--cikti", help="çıktı klasörü (genel.cikti_klasoru)")
    parser.add_argument("--olaylar-json", action="store_true", help="aşama olaylarını stdout'a JSON satırı yaz")
    parser.add_argument("--ayrintili", action="store_true", help="DEBUG günlüğü")


def _lisans_secenegi(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--lisans-onay", action="store_true",
                        help="seçili ticari olmayan / şartlı motorun lisans uyarısını okudum, kabul ediyorum "
                             "(bir kez; ayarlar/lisans_onaylari.json'a yazılır)")


def _lisans_kapisi(ayar: dict[str, Any], stt_motoru: str, onay: bool, etkilesimli: bool) -> int:
    """İlk kullanımda iki dilli lisans uyarısı + açık onay; 0 = devam, 2 = onay yok."""
    from dublaj_hatti.lisans_onayi import LisansOnayiGerekli, kapi, komut_satiri_onayi

    try:
        kapi(ayar, stt_motoru, onay)
        return 0
    except LisansOnayiGerekli as gerek:  # soru ve mesaj tek yerde (aşama komutları ve devam da aynısını kullanır)
        return 0 if komut_satiri_onayi(gerek, etkilesimli) else 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dubla", description="DubWorld: yerel video için otomatik dublaj.")
    parser.add_argument("--surum", action="version", version=f"DubWorld {__version__}")
    alt = parser.add_subparsers(dest="komut")

    dubla = alt.add_parser("dubla", help="videoyu dublajla (varsayılan komut)")
    dubla.add_argument("kaynak", help="yerel video dosyası (bağlantı yalnız [youtube] eki kuruluysa)")
    dubla.add_argument("--devam", metavar="IS_KLASORU", help="yarım kalan işi kaldığı aşamadan sürdür")
    _lisans_secenegi(dubla)
    _ortak_secenekler(dubla)

    transkript = alt.add_parser("transkript", help="yalnız transkript / altyazı dosyası üret")
    transkript.add_argument("kaynak")
    transkript.add_argument("--bicim", choices=TRANSKRIPT_BICIMLERI, default=None,
                            help="çıktı biçimi (varsayılan: genel.transkript_bicimi)")
    _lisans_secenegi(transkript)
    _ortak_secenekler(transkript)

    kontrol = alt.add_parser("kontrol", help="kurulumu ve donanımı denetle")
    kontrol.add_argument("--json", action="store_true")
    _ortak_secenekler(kontrol)

    ayarlar = alt.add_parser("ayarlar", help="geçerli ayarları göster")
    ayarlar.add_argument("--json", action="store_true")
    _ortak_secenekler(ayarlar)
    alt_komutlari_ekle(alt, _ortak_secenekler)  # isler, sorunlu, devam (is_yonetimi)
    asama_komutlarini_ekle(alt, _ortak_secenekler)  # her aşama tek başına (asama_komutlari, api)
    return parser


def _argumanlari_coz(argv: list[str]) -> argparse.Namespace:
    if argv and argv[0] not in ALT_KOMUTLAR and not argv[0].startswith("-"):
        argv = ["dubla", *argv]
    args = _parser().parse_args(argv)
    if not args.komut:
        _parser().print_help()
        raise SystemExit(2)
    return args


KONSOL_ISARETI = "_dublaj_konsol"  # paketin konsol işleyicisi; ikinci kez kurulunca eskisi kaldırılır


def _gunlugu_kur(ayrintili: bool, seviye: str) -> None:
    """Konsol günlüğü: her satır bir kez, seçilen seviyede.

    Kök neden (çift satır): dubber.py "dublaj_hatti" günlükçüsüne kendi konsol işleyicisini ekliyordu ve günlükçü kök
    günlükçüye de yayıyordu (propagate), kökte de basicConfig işleyicisi vardı → her satır iki kez; günlükçü DEBUG
    seviyesinde olduğundan DEBUG satırları --ayrintili olmadan da kökten basılıyordu. Şimdi: paketin tek konsol
    işleyicisi burada (seviyeli), paket kök günlükçüye yaymaz; kök yalnız üçüncü taraf kitaplıkların günlüğü için."""
    duzey = logging.DEBUG if ayrintili else getattr(logging, seviye, logging.INFO)
    bicim = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    logging.basicConfig(level=duzey, format=bicim._fmt, stream=sys.stderr)
    paket = logging.getLogger("dublaj_hatti")
    # dubber.py modül düzeyinde (bu çağrıdan önce içe aktarılmışsa) yalın bir StreamHandler ekler: o da kaldırılır;
    # FileHandler (iş klasörü günlüğü) StreamHandler alt sınıfıdır, type() karşılaştırması ona dokunmaz.
    for eski in [h for h in paket.handlers if getattr(h, KONSOL_ISARETI, False) or type(h) is logging.StreamHandler]:
        paket.removeHandler(eski)
    konsol = logging.StreamHandler(sys.stderr)
    konsol.setFormatter(bicim)
    konsol.setLevel(duzey)
    setattr(konsol, KONSOL_ISARETI, True)
    paket.addHandler(konsol)
    paket.setLevel(logging.DEBUG)  # iş klasörü günlük dosyası (dubber) DEBUG'a kadar alabilsin; konsol süzer
    paket.propagate = False


def kontrol_raporu(ayar: dict[str, Any] | None = None) -> dict[str, Any]:
    """`ayar` verilirse CTC modelleri genel.onbellek_klasoru'nda aranır (hatla aynı yer); yoksa varsayılan önbellek."""
    from dublaj_hatti import kayit
    from dublaj_hatti.bolum_00_omurga.runtime.ctc_model_durumu import kontrol_ozeti
    from dublaj_hatti.bolum_00_omurga.runtime.donanim import donanim_ozeti

    return {
        "surum": __version__,
        "python": sys.version.split()[0],
        "donanim": donanim_ozeti(),
        "ffmpeg": shutil.which("ffmpeg") or "",
        **{grup: kayit.durum(grup) for grup in ("stt", "ceviri", "tts", "ek")},
        "deneysel": {m.ad: m.deneysel for m in kayit.MOTORLAR if m.deneysel},
        "ctc_modelleri": kontrol_ozeti((ayar or {}).get("genel.onbellek_klasoru") or None),
        "telegram_sunucu": _telegram_sunucu_ozeti(),
    }


def _telegram_sunucu_ozeti() -> dict[str, Any]:
    """Yerel Telegram Bot API sunucusu (isteğe bağlı; 2000 MB teslim). Docker'a dokunmaz, en çok ~5 sn."""
    try:
        from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import yerel_sunucu
    except ImportError:
        return {"durum": "kurulu_degil"}

    yerel_sunucu.env_yukle()
    return yerel_sunucu.kontrol_ozeti()


def _kontrol_yaz(rapor: dict[str, Any]) -> None:
    print(f"DubWorld {rapor['surum']} · Python {rapor['python']}")
    for anahtar, deger in rapor["donanim"].items():
        print(f"  donanım.{anahtar}: {deger}")
    print(f"  ffmpeg: {rapor['ffmpeg'] or 'YOK (scripts/kur.ps1 -Adim modeller; FFmpeg bu adımla iner)'}")
    for grup in ("stt", "ceviri", "tts", "ek"):
        satir = ", ".join(f"{ad}={'var' if var else 'yok'}" for ad, var in rapor[grup].items())
        print(f"  {grup}: {satir}")
    for ad, neden in rapor.get("deneysel", {}).items():
        print(f"  deneysel / experimental: {ad} ({neden})")
    telegram = rapor.get("telegram_sunucu")
    if telegram and telegram.get("durum") == "kurulu_degil":
        print("  telegram yerel sunucu: telegram eki kurulu değil / Telegram add-on not installed")
    elif telegram:
        from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu.yerel_sunucu import kontrol_metni

        print(f"  telegram yerel sunucu: {kontrol_metni(telegram)}")
    ctc = rapor.get("ctc_modelleri", {})
    print("  hizalama (CTC): " + ", ".join(f"{dil}={'var' if var else 'yok'}" for dil, var in ctc.items()))
    eksik = [dil for dil, var in ctc.items() if not var]
    if eksik:
        from dublaj_hatti.bolum_00_omurga.runtime.ctc_model_durumu import KURULUM_ADIMI

        print(f"  UYARI: CTC modeli eksik ({', '.join(eksik)}): auto yedeği faster_whisper_ctc ve CTC kullanan "
              f"motorlar bu dillerde açık hatayla durur. Kurulum: {KURULUM_ADIMI}")


# Önerilen akışın (`dubla <video>`, arayüzde "Türkçe dublajla") kurulu olması gereken parçaları (varsayilan.toml).
# STT: transkripsiyon.motor=auto CrisperWhisper yoksa faster_whisper_ctc'yi seçer (yedek, CTC kelime zamanı).
ONERILEN_AKIS_PARCALARI = (("stt", "faster_whisper_ctc"), ("ceviri", "yerel"), ("tts", "supertonic"),
                           ("ek", "konusmaci_ayrimi"))


def onerilen_akis_eksikleri(rapor: dict[str, Any]) -> list[str]:
    """`dubla kontrol` sonuç satırı için: Önerilen akışta eksik parçalar (boş = hazır). Yalnız raporu okur."""
    eksik = [] if rapor.get("ffmpeg") else ["ffmpeg"]
    eksik += [ad for grup, ad in ONERILEN_AKIS_PARCALARI if not rapor.get(grup, {}).get(ad)]
    return eksik + [f"CTC ({dil})" for dil, var in rapor.get("ctc_modelleri", {}).items() if not var]


def _sonuc_yaz(rapor: dict[str, Any], cihaz: str) -> None:
    """Teknik olmayan kullanıcı ve ajan için tek sonuç satırı; çıkış kodu değişmez (docs/getting-started.md)."""
    donanim = rapor.get("donanim", {})
    if cihaz != "cpu" and "+cu" in str(donanim.get("torch", "")) and not donanim.get("cuda"):
        print("  not / note: GPU için kuruldu ama GPU çalışmıyor; işler işlemciyle (daha yavaş) yapılır. "
              "Sürücü: docs/kurulum.md §12 · GPU install but the GPU does not run; jobs use the CPU (slower).")
    eksik = onerilen_akis_eksikleri(rapor)
    if not eksik:
        print("SONUÇ / RESULT: Önerilen akış HAZIR / recommended flow READY · arayüz / app: arayuz.cmd")
    else:
        print(f"SONUÇ / RESULT: EKSİK / MISSING: {', '.join(eksik)} · kurulumu yeniden çalıştırın (kur.cmd); "
              "kurulu olanlar atlanır / re-run the installer (kur.cmd); installed parts are skipped")


def _konsolu_utf8_yap() -> None:
    for akis in (sys.stdout, sys.stderr):
        if hasattr(akis, "reconfigure"):
            try:
                akis.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def main(argv: list[str] | None = None) -> int:
    _konsolu_utf8_yap()
    args = _argumanlari_coz(list(sys.argv[1:] if argv is None else argv))
    ustune = list(args.ayar)
    if getattr(args, "cikti", None):
        ustune.append(f"genel.cikti_klasoru={args.cikti}")
    try:
        ayar = ayarlari_yukle(args.ayarlar, ustune)
    except (AyarHatasi, ValueError, OSError) as hata:
        print(f"ayar hatası: {hata}", file=sys.stderr)
        return 2
    _gunlugu_kur(args.ayrintili, ayar["genel.gunluk_seviyesi"])
    if args.komut in ASAMA_KOMUTLARI:  # tek aşama: api ortamı kendisi hazırlar
        from dublaj_hatti.asama_komutlari import calistir as asama_calistir

        return asama_calistir(args)
    if args.komut in IS_KOMUTLARI:  # iş kaydının kendi cihazıyla ortamı kendisi hazırlar
        from dublaj_hatti.is_yonetimi import komutlar

        return komutlar.calistir(args, ayar, ortami_hazirla, _olay_yazici(args.olaylar_json))
    ortami_hazirla(ayar["genel.cihaz"])

    if args.komut == "ayarlar":
        from dublaj_hatti.yapilandirma import uyumluluk_denetle

        uyarilar = [str(b) for b in uyumluluk_denetle(ayar) if b.seviye == "uyari"]
        if args.json:
            print(json.dumps(ayarlari_ic_ice(ayar), ensure_ascii=False, indent=2))
        else:
            for anahtar in sorted(ayar):
                print(f"{anahtar} = {ayar[anahtar]!r}")
        for uyari in uyarilar:
            print(f"uyarı: {uyari}", file=sys.stderr)
        return 0

    if args.komut == "kontrol":
        rapor = kontrol_raporu(ayar)
        if args.json:
            print(json.dumps(rapor, ensure_ascii=False, indent=2))
        else:
            _kontrol_yaz(rapor)
            _sonuc_yaz(rapor, ayar["genel.cihaz"])
        return 0

    olay = _olay_yazici(args.olaylar_json)
    try:
        from dublaj_hatti.yapilandirma import dubconfig_olustur

        kaynak = _kaynak_dogrula(args.kaynak)
        _, cozum = dubconfig_olustur(ayar, kaynak=kaynak)  # çözümleme hatası iş kaydı açılmadan görünsün
    except AyarHatasi as hata:
        print(f"hata: {hata}", file=sys.stderr)
        return 2
    etkilesimli = sys.stdin.isatty() and not args.olaylar_json
    # Kapı yalnız bu komutta gerçekten çalışan motoru sorar: `dubla transkript` ses motoru kullanmaz.
    kapi_ayari = {**ayar, "genel.is_turu": "transkript"} if args.komut == "transkript" else ayar
    if _lisans_kapisi(kapi_ayari, cozum.stt_motoru, args.lisans_onay, etkilesimli):
        return 2

    from dublaj_hatti.is_yonetimi.calistirici import depo_ac, isi_calistir
    from dublaj_hatti.is_yonetimi.depo import IsHatasi

    def yaz(e: dict[str, Any]) -> None:
        olay(e)
        if args.olaylar_json:
            return
        if e.get("event") == "bitti":
            for anahtar, deger in e.items():
                if anahtar not in ("event", "is"):
                    print(f"{anahtar}: {deger}")
        elif e.get("event") == "kaynak_bekleniyor":
            print(f"{e['kaynak']} meşgul, sıra bekleniyor: {'; '.join(e.get('kullananlar') or [])}", file=sys.stderr)

    depo = depo_ac(ayar)
    if args.komut == "dubla" and args.devam:  # eski biçim: --devam <iş klasörü>
        kayit = depo.run_dir_ile_bul(args.devam)
        if not kayit:
            print(f"hata: bu klasör iş deposunda kayıtlı değil: {args.devam} (dubla sorunlu)", file=sys.stderr)
            return 2
        try:
            job_id = depo.yerinde_devam(int(kayit["job_id"]))
        except IsHatasi as hata:
            print(f"hata: {hata}", file=sys.stderr)
            return 2
    else:
        bicim = (args.bicim or ayar.get("genel.transkript_bicimi") or "srt") if args.komut == "transkript" else ""
        job_id = depo.is_ekle(kaynak, ayar, "transkript" if args.komut == "transkript" else "dubla", "cli",
                              ifadeler=list(args.ayar), transkript_bicimi=bicim)
    logger.info("iş #%s (iş deposu: %s)", job_id, depo.db_yolu)
    kod = isi_calistir(depo, job_id, yaz)
    if kod == 130:
        print(f"durduruldu; sürdürmek için: dubla devam {job_id}", file=sys.stderr)
    elif kod == 1:
        print(f"iş #{job_id} başarısız; ayrıntı: dubla sorunlu · sürdürmek için: dubla devam {job_id}", file=sys.stderr)
    return kod

if __name__ == "__main__":
    raise SystemExit(main())
