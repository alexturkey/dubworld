"""Ticari olmayan ya da şartlı lisanslı motorların ilk kullanım onayı (CLI, GUI ve web ortak kapısı).

Uyarı metni tek yerde: `kayit.lisans_uyarisi(ad)`. Burada yalnız "hangi motor seçili, onaylandı mı, onayı kaydet" var.
Onay kullanıcının ayar klasörüne yazılır (`ayarlar/lisans_onaylari.json`, git dışı; yol `DUBLAJ_LISANS_ONAY_DOSYASI`
ile değişir). Kayıt yalnız motor adı, onaylanan lisans metni ve UTC tarihini tutar (kişisel bilgi yok). Motorun
lisans satırı değişirse eski onay geçmez, uyarı yeniden gösterilir.

TEK KAPI: her giriş yolu aynı `kapi_adlar()`dan geçer (tests/test_lisans_kapisi_girisler.py kanıtlar):
  * `dubla <video>` / `dubla transkript` (cli), `dubla devam` (is_yonetimi.komutlar) → komut_satiri_onayi ile sorar
  * her aşama komutu (`dubla seslendir`, `dubla yaziya-dok`, ...) ve `dublaj_hatti.api` işlevleri → api._lisans
  * GUI ve web → arayuz_kapisi
  * iş çalıştırıcı (is_yonetimi.calistirici; kuyruk, devam, arayüz alt süreci) → kapi, son savunma: onaysız iş
    çalışmaz, "lisans onayı yok" ile durur (soru sormaz)

Motor olmayan lisans kalemleri de aynı kapıdan geçer: WhisperX'in fr/de/es/it varsayılan CTC hizalama modelleri
(torchaudio VoxPopuli, CC BY-NC 4.0) `whisperx_ctc_<dil>` adıyla (`MODEL_LISANSLARI`). Dil ayarda sabitse iş başında
sorulur; dil otomatikse modeli yükleyen işçi (`ctc_model_durumu.ctc_lisans_denetle`) onaysız yüklemez.

Kendi onay akışı olan motorlar burada sorulmaz: XTTS v2 (`ses.xtts_lisans_onayi`, CPML onayı) ve RVC
(`ses.rvc_riza_onayi`, sesin sahibinin rızası).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dublaj_hatti import kayit

ONAY_DOSYASI_ORTAM = "DUBLAJ_LISANS_ONAY_DOSYASI"
ONAY_ORTAM = "DUBLAJ_LISANS_ONAY"  # "1" / "evet" / "yes": etkileşimsiz ortamda açık kabul (CI, betik)
KENDI_ONAYI_OLAN = frozenset({"xtts", "rvc"})
# Motor kaydında olmayan, onay isteyen model lisansları: ad -> (lisans satırı, görünen ad).
CTC_LISANS_ONEKI = "whisperx_ctc_"
CTC_NC_LISANSI = "CC BY-NC 4.0 (torchaudio VoxPopuli wav2vec2; ticari olmayan / non-commercial)"
CTC_NC_DILLERI = ("fr", "de", "es", "it")
MODEL_LISANSLARI: dict[str, tuple[str, str]] = {
    f"{CTC_LISANS_ONEKI}{dil}": (CTC_NC_LISANSI, f"WhisperX varsayılan CTC hizalama modeli ({dil})")
    for dil in CTC_NC_DILLERI
}
# Kelime zamanını CTC kutusundan (ya da WhisperX hizalamasından) alan STT motorları; "auto" yedeği faster_whisper_ctc.
CTC_KULLANAN_STT = frozenset({"auto", "faster_whisper_ctc", "whisperx", "crisperwhisper_turbo_ct2",
                              "whisper_cpp_cpu_align", "youtube_translate"})
_KABUL = {"1", "e", "evet", "y", "yes", "true", "kabul", "kabul ediyorum", "i accept"}


class LisansOnayiGerekli(RuntimeError):
    """Seçili motorlardan en az biri için açık onay yok; `bekleyen` = [(motor adı, iki dilli uyarı), ...]."""

    def __init__(self, bekleyen: list[tuple[str, str]]) -> None:
        self.bekleyen = bekleyen
        super().__init__(
            "lisans onayı gerekli / license acceptance required: " + ", ".join(ad for ad, _ in bekleyen)
        )


def onay_dosyasi() -> Path:
    acik = os.environ.get(ONAY_DOSYASI_ORTAM, "").strip()
    if acik:
        return Path(acik).expanduser()
    from dublaj_hatti.yapilandirma import PROJE_KOKU

    return PROJE_KOKU / "ayarlar" / "lisans_onaylari.json"


def _kayitlar() -> dict[str, Any]:
    try:
        veri = json.loads(onay_dosyasi().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return veri if isinstance(veri, dict) else {}


def _lisans_satiri(ad: str) -> str:
    if ad in MODEL_LISANSLARI:
        return MODEL_LISANSLARI[ad][0]
    return kayit.motor(ad).lisans


def onayli(ad: str) -> bool:
    kayit_ = _kayitlar().get(ad)
    return isinstance(kayit_, dict) and kayit_.get("lisans") == _lisans_satiri(ad)


def _model_uyarisi(ad: str) -> str:
    lisans, gorunen = MODEL_LISANSLARI[ad]
    return (
        f"LİSANS UYARISI: {gorunen} = {lisans}. Bu dilde kelime zamanı (kaynak transkript ya da dublaj altyazısı) "
        "bu modelle hizalanır; ticari işte kullanmayın. Ayrıntı: THIRD_PARTY.md, docs/diller.md.\n"
        f"LICENSE NOTICE: {gorunen} = {lisans}. Word timing in this language (source transcript or dub subtitles) is "
        "aligned with this model; do not use it for commercial work. Details: THIRD_PARTY.md, docs/diller.md."
    )


def ctc_lisans_adi(dil: str) -> str | None:
    """Ticari olmayan varsayılan CTC modeli kullanan dil için lisans kalemi adı (`whisperx_ctc_fr`), yoksa None."""
    kod = str(dil or "").strip().lower().split("-", 1)[0].split("_", 1)[0]
    ad = f"{CTC_LISANS_ONEKI}{kod}"
    return ad if ad in MODEL_LISANSLARI else None


def onay_gereken(ad: str) -> str | None:
    """Motor onay istiyorsa iki dilli uyarı metni, istemiyorsa None (bilinmeyen ad da None)."""
    if ad in KENDI_ONAYI_OLAN:
        return None
    if ad in MODEL_LISANSLARI:
        return _model_uyarisi(ad)
    try:
        return kayit.lisans_uyarisi(ad)
    except KeyError:
        return None


def secili_motorlar(ayar: dict[str, Any], stt_motoru: str | None = None) -> list[str]:
    """Ayarın kullanacağı motorlar. `stt_motoru` çözülmüş STT ("auto" sonrası); verilmezse "auto" için
    kurulu olan ticari olmayan STT de (CrisperWhisper Turbo) temkinle listeye girer."""
    adlar: list[str] = []
    stt = stt_motoru or str(ayar.get("transkripsiyon.motor") or "")
    if stt == "auto":
        turbo = kayit.motor("crisperwhisper_turbo_ct2")
        if turbo.kurulu():
            adlar.append(turbo.ad)
    elif stt:
        adlar.append(stt)
    dublaj = ayar.get("genel.is_turu", "dublaj") == "dublaj"
    if dublaj and ayar.get("ses.motor"):
        adlar.append(str(ayar["ses.motor"]))
    # Ticari olmayan CTC modeli: kaynak dil sabitse ve STT CTC kullanıyorsa; dublajda hedef dilin altyazı hizalaması.
    if (stt_motoru or stt) in CTC_KULLANAN_STT:
        ad = ctc_lisans_adi(str(ayar.get("transkripsiyon.kaynak_dil") or ""))
        if ad:
            adlar.append(ad)
    if dublaj:
        ad = ctc_lisans_adi(str(ayar.get("genel.hedef_dil") or ""))
        if ad:
            adlar.append(ad)
    return adlar


def bekleyen_onaylar(adlar: list[str]) -> list[tuple[str, str]]:
    bekleyen = []
    for ad in dict.fromkeys(adlar):
        metin = onay_gereken(ad)
        if metin and not onayli(ad):
            bekleyen.append((ad, metin))
    return bekleyen


def onayla(adlar: list[str]) -> Path:
    """Onayı kaydeder (geçici dosya + os.replace: yarım dosya kalmaz)."""
    veri = _kayitlar()
    simdi = datetime.now(UTC).isoformat(timespec="seconds")
    for ad in adlar:
        veri[ad] = {"lisans": _lisans_satiri(ad), "tarih_utc": simdi}
    yol = onay_dosyasi()
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(gecici, yol)
    return yol


def ortamdan_kabul() -> bool:
    return os.environ.get(ONAY_ORTAM, "").strip().lower() in _KABUL


def kabul_mu(cevap: str) -> bool:
    return cevap.strip().lower() in _KABUL


def kapi(ayar: dict[str, Any], stt_motoru: str | None = None, onay: bool = False) -> list[str]:
    """Ayarın kullanacağı motorlar için `kapi_adlar()`."""
    return kapi_adlar(secili_motorlar(ayar, stt_motoru), onay)


def kapi_adlar(adlar: list[str], onay: bool = False) -> list[str]:
    """Tek kapı. Bekleyen onay varsa: `onay` (ya da DUBLAJ_LISANS_ONAY) ile kaydeder ve adları döndürür, yoksa
    LisansOnayiGerekli fırlatır. Bekleyen yoksa boş liste. Lisansı temiz ya da bilinmeyen ad sessizce geçer."""
    bekleyen = bekleyen_onaylar([str(a) for a in adlar if a])
    if not bekleyen:
        return []
    if not (onay or ortamdan_kabul()):
        raise LisansOnayiGerekli(bekleyen)
    adlar = [ad for ad, _ in bekleyen]
    onayla(adlar)
    return adlar


def komut_satiri_onayi(gerek: LisansOnayiGerekli, etkilesimli: bool) -> bool:
    """Komut satırı için: uyarıyı stderr'e yazar, etkileşimliyse sorar; kabulde onayı kaydeder ve True döner.
    Girdi kapalıysa (ajan / betik) yığın izi yerine sade mesaj; False = çağıran 2 ile çıkar."""
    import sys

    for _, metin in gerek.bekleyen:
        print("", metin, sep="\n", file=sys.stderr)
    if etkilesimli:
        try:
            cevap = input("\nKabul ediyor musunuz? / Do you accept? [evet/yes, hayır/no]: ")
        except EOFError:
            cevap = ""
        if kabul_mu(cevap):
            onayla([ad for ad, _ in gerek.bekleyen])
            return True
    print("\nlisans onayı yok: kabul ediyorsanız --lisans-onay ile yeniden çalıştırın "
          "(ya da DUBLAJ_LISANS_ONAY=1) / not accepted: rerun with --lisans-onay", file=sys.stderr)
    return False


def arayuz_kapisi(degisiklikler: dict[str, Any], onay: bool = False) -> list[str]:
    """GUI ve web için: arayüzdeki değişikliklerden etkin ayarı kurar ve `kapi()`yı uygular."""
    from dublaj_hatti.is_yurutucu import ayar_degisiklikleri
    from dublaj_hatti.yapilandirma import ayarlari_yukle

    etkin = ayarlari_yukle(ustune=ayar_degisiklikleri(degisiklikler))
    return kapi(etkin, None, onay)
