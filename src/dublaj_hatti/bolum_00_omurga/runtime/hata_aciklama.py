from __future__ import annotations

import re
from dataclasses import dataclass

from dublaj_hatti.bolum_00_omurga.runtime.internet_gateway import is_network_path_failure

MAKSIMUM_HATA_UZUNLUGU = 300
VARSAYILAN_YORUM = "Beklenmeyen hata; teknik ayrıntı iş logunda."


@dataclass(frozen=True)
class HataKurali:
    kategori: str
    yorum: str
    sinif_adlari: tuple[str, ...] = ()
    metin_isaretleri: tuple[str, ...] = ()


@dataclass(frozen=True)
class HataAciklamasi:
    kategori: str
    yorum: str
    ozgun_hata: str
    ust_hata: str

    @property
    def kayit_metni(self) -> str:
        if self.ust_hata and self.ust_hata != self.ozgun_hata:
            return f"{self.ust_hata} | kok: {self.ozgun_hata}"
        return self.ozgun_hata


AG_KURALI = HataKurali("ag", "İnternet bağlantısı veya DNS çözümlemesi başarısız; ağ düzelince tekrar dene.")

KURALLAR = (
    HataKurali(
        "google_ceviri",
        "Google Translate yanıt vermedi (hız sınırı veya bağlantı); çevrilmemiş video gönderilmedi. "
        "Biraz sonra tekrar dene veya başka çeviri motoru seç.",
        ("GoogleTranslateServiceError",),
    ),
    HataKurali(
        "ceviri_eksik",
        "Çeviri motoru bazı segmentleri çevirmedi; kaynak dilde kalan video gönderilmedi. "
        "Tekrar dene veya başka çeviri motoru seç.",
        ("CeviriEksikSegmentError",),
    ),
    HataKurali(
        "demucs",
        "Demucs ses ayrıştırması başarısız oldu; iş ham sesle devam ettirilmeden durduruldu.",
        ("DemucsPreparationError",),
    ),
    HataKurali(
        "kapak",
        "Kapak resmi üretilemedi veya gönderilemedi; video kapaktan önce gitmesin diye gönderilmedi.",
        ("CoverDeliveryError",),
    ),
    HataKurali(
        "gpu_bellek",
        "GPU belleği yetmedi; başka GPU işi bitince tekrar dene.",
        ("OutOfMemoryError",),
        ("cuda out of memory", "cuda error: out of memory"),
    ),
    HataKurali(
        "hiz_siniri",
        "Servis hız sınırına veya kotaya takıldı; bir süre sonra tekrar dene ya da başka motor seç.",
        ("TooManyRequests", "RateLimitError"),
        ("too many requests", "rate limit", "resource_exhausted", "quota exceeded", "usage limit"),
    ),
    HataKurali(
        "kimlik",
        "Servis kimlik doğrulaması başarısız; API anahtarı veya oturum geçersiz olabilir.",
        ("AuthenticationError", "PermissionDeniedError"),
        ("unauthorized", "invalid api key", "invalid_api_key", "not authenticated", "not logged in"),
    ),
    HataKurali(
        "zaman_asimi",
        "İşlem zaman aşımına uğradı; servis veya donanım beklenenden yavaş kaldı.",
        ("TimeoutError", "TimeoutExpired", "ReadTimeout", "ConnectTimeout"),
        ("timed out",),
    ),
    HataKurali(
        "indirme",
        "Video indirilemedi; bağlantı özel, silinmiş veya bölge kısıtlı olabilir.",
        ("DownloadError",),
        ("video unavailable", "private video"),
    ),
    HataKurali(
        "seslendirme_eksik",
        "Seslendirme motoru bazı segmentleri üretemedi; sessiz boşluklu video gönderilmedi. "
        "Tekrar dene veya başka ses seç.",
        (),
        ("seslendirme basarisiz",),
    ),
    HataKurali("dosya_yok", "Gerekli bir dosya bulunamadı.", ("FileNotFoundError",)),
)

_GIZLI_DESENLER = (
    (re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"), "<token>"),
    (re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}\b"), "<anahtar>"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"), "<anahtar>"),
    (re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"), "<anahtar>"),
    (re.compile(r"(?i)\b(bearer)(\s+)[A-Za-z0-9._~+/-]{12,}=*"), r"\1\2<gizli>"),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password|sessionid|cookie)"
            r"(\s*[:=]\s*)([\"']?)[^\s\"'&,;<]{6,}"
        ),
        r"\1\2\3<gizli>",
    ),
    (re.compile(r"(?i)([?&](?:key|token|sig|signature)=)[^&\s]+"), r"\1<gizli>"),
)
_WINDOWS_YOLU = re.compile(r"(?i)\b[a-z]:[\\/][^\s\"'<>|]*")
_POSIX_YOLU = re.compile(r"(?<![\w.:/])/(?:home|mnt|root|tmp|usr|opt|var)/[^\s\"'<>|]*")


def _yolu_kisalt(eslesme: re.Match) -> str:
    parcalar = [parca for parca in re.split(r"[\\/]", eslesme.group(0)) if parca]
    return f"<yol>/{parcalar[-1]}" if len(parcalar) > 1 else "<yol>"


def guvenli_metin(metin: object, sinir: int = MAKSIMUM_HATA_UZUNLUGU) -> str:
    sonuc = str(metin or "")
    for desen, yerine in _GIZLI_DESENLER:
        sonuc = desen.sub(yerine, sonuc)
    sonuc = _WINDOWS_YOLU.sub(_yolu_kisalt, sonuc)
    sonuc = _POSIX_YOLU.sub(_yolu_kisalt, sonuc)
    sonuc = " ".join(sonuc.split())
    if len(sonuc) > sinir:
        sonuc = sonuc[: sinir - 3].rstrip() + "..."
    return sonuc


def hata_zinciri(hata: BaseException) -> list[BaseException]:
    zincir: list[BaseException] = []
    gorulen: set[int] = set()
    guncel: BaseException | None = hata
    while guncel is not None and id(guncel) not in gorulen:
        gorulen.add(id(guncel))
        zincir.append(guncel)
        sonraki = guncel.__cause__
        if sonraki is None and not guncel.__suppress_context__:
            sonraki = guncel.__context__
        guncel = sonraki
    return zincir


def hata_ozeti(hata: BaseException) -> str:
    mesaj = guvenli_metin(hata)
    sinif = hata.__class__.__name__
    return f"{sinif}: {mesaj}" if mesaj else sinif


def _kural_eslesir(kural: HataKurali, sinif_adlari: set[str], metin: str) -> bool:
    if sinif_adlari.intersection(kural.sinif_adlari):
        return True
    return any(isaret in metin for isaret in kural.metin_isaretleri)


def _kural_sec(sinif_adlari: set[str], metin: str, ag_hatasi: bool) -> HataKurali | None:
    for kural in KURALLAR[:4]:
        if _kural_eslesir(kural, sinif_adlari, metin):
            return kural
    if ag_hatasi:
        return AG_KURALI
    for kural in KURALLAR[4:]:
        if _kural_eslesir(kural, sinif_adlari, metin):
            return kural
    return None


def hata_aciklamasi(hata: BaseException) -> HataAciklamasi:
    zincir = hata_zinciri(hata)
    sinif_adlari = {sinif.__name__ for halka in zincir for sinif in type(halka).__mro__}
    metin = " ".join(str(halka) for halka in zincir).lower()
    kural = _kural_sec(sinif_adlari, metin, is_network_path_failure(hata))
    return HataAciklamasi(
        kategori=kural.kategori if kural else "bilinmeyen",
        yorum=kural.yorum if kural else VARSAYILAN_YORUM,
        ozgun_hata=hata_ozeti(zincir[-1]),
        ust_hata=hata_ozeti(zincir[0]),
    )


def kayitli_hata_yorumu(kayit_metni: str) -> str:
    metin = str(kayit_metni or "")
    sinif_adlari = set(re.findall(r"\b([A-Z][A-Za-z0-9_]*(?:Error|Exception|Requests|Expired|Timeout))\b", metin))
    kural = _kural_sec(sinif_adlari, metin.lower(), is_network_path_failure(RuntimeError(metin)))
    return kural.yorum if kural else ""


def kullanici_mesaji(aciklama: HataAciklamasi, baslik: str, ayrinti_goster: bool, asama: str = "") -> str:
    satirlar = [f"❌ {baslik}", ""]
    if asama:
        satirlar.append(f"Aşama: {asama}")
    if ayrinti_goster:
        satirlar.append(f"Hata: {aciklama.ozgun_hata}")
    satirlar.append(f"Yorum: {aciklama.yorum}")
    return "\n".join(satirlar)
