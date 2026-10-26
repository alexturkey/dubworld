"""Ayar dosyası yükleyici ve doğrulayıcı.

Katmanlar (üstteki alttakini ezer): komut satırı `--ayar a.b=c` > `--ayarlar dosya.toml` >
`ayarlar/kullanici.toml` > paketteki `varsayilan.toml` ("Önerilen akış").
`dubconfig_olustur()` doğrulanmış ayarı hattın `DubConfig` nesnesine çevirir; "auto" seçimleri
(cihaz, hesap tipi, transkripsiyon motoru, çeviri arka ucu) burada çözülür.

Doğrulama iki katmanlıdır: (1) her anahtar tek başına (tür, seçenek, aralık), (2) `uyumluluk_denetle()`
anahtarların birlikteliği (hangi TTS hangi dil, hangi motor hangi cihaz, hangi kip hangi çeviri arka ucu).
"hata" seviyesi yüklemeyi durdurur (AyarHatasi), "uyari" seviyesi günlüğe yazılır ve iş sürer.
Kombinasyon tablosu: docs/tarifler/kombinasyonlar.md.
"""

from __future__ import annotations

import copy
import importlib.util
import logging
import os
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dublaj_hatti import arayuz_dili, kayit

PAKET_KOKU = Path(__file__).resolve().parent
PROJE_KOKU = PAKET_KOKU.parents[1]
VARSAYILAN_DOSYA = PAKET_KOKU / "varsayilan.toml"
KULLANICI_DOSYA_ENV = "DUBLAJ_AYARLAR"
logger = logging.getLogger("dublaj_hatti")


class AyarHatasi(ValueError):
    """Ayar dosyasında bilinmeyen anahtar ya da geçersiz değer."""


SUPERTONIC_KADIN_SESLERI = [f"F{i}" for i in range(1, 6)]
SUPERTONIC_ERKEK_SESLERI = [f"M{i}" for i in range(1, 6)]
SUPERTONIC_SESLERI = SUPERTONIC_KADIN_SESLERI + SUPERTONIC_ERKEK_SESLERI
STT_MOTORLARI = kayit.adlar("stt")
CEVIRI_ARKA_UCLARI = kayit.adlar("ceviri")
TTS_MOTORLARI = kayit.adlar("tts")  # "auto" ilk (varsayılan): VoxCPM2 kuruluysa ve NVIDIA GPU varsa o, değilse Supertonic
SUPERTONIC_AKISLARI = [
    "natural_blocks_1", "single_pass_1", "single_pass_2", "single_pass_10", "repair_3_light",
    "repair_2_initial_1_repair_2", "repair_1", "repair_2", "repair_3", "repair_4", "repair_5", "repair_6", "repair_7",
]
# Dil listeleri motor kaydında (kayit.py; kaynakları docs/diller.md). Eşitlikleri tests/test_kombinasyon.py denetler.
SUPERTONIC_DILLERI = kayit.SUPERTONIC_DILLERI  # listede olmayan dil Supertonic'te okunamaz (hata)
VOXCPM2_DENENEN_DILLER = kayit.VOXCPM2_DENENEN_DILLER  # dışındakiler model kartına göre okunur, denenmedi (uyarı)
XTTS_DILLERI = kayit.XTTS_DILLERI  # listede olmayan dil XTTS v2'de okunamaz (hata)
EMA_DILLERI = kayit.EMA_DILLERI  # EMA Lightning yalnız Türkçe okur (hata)
VOXCPM2_VARSAYILAN_SES = "hazir/haber_spikeri"  # varsayilan.toml ses.voxcpm2_ses; başka hedef dilde o dilin anlatıcısına döner
TAM_METIN_TTS = {"supertonic", "ema_lightning"}  # genel.dublaj_kipi=full_text bu motorlarla çalışır
XTTS_KALKIYOR_TR = ("XTTS kullanımdan kalkıyor (ticari olmayan CPML lisansı); VoxCPM2 metinsiz ses klonlamayı "
                    "destekliyor.")
XTTS_KALKIYOR_EN = ("XTTS is being deprecated (non-commercial CPML licence); VoxCPM2 supports voice cloning "
                    "without a reference transcript.")
HEDEF_DILLERI = kayit.tts_hedef_dilleri()
TRANSKRIPT_BICIMLERI = ["srt", "plain", "timestamped", "paragraph"]
WHISPERX_PROFILLERI = ["auto", "whisperx_float32_quality_v1", "whisperx_engine_default_v1"]

# Sabit sözleşmeli transkripsiyon motorları: model ve hesap tipi motorun kendisine bağlıdır (kaynak uygulamanın
# menü ön ayarlarıyla aynı). `transkripsiyon.model` / `hesap_tipi` yalnız faster-whisper (+ CTC) ve whisperx'te geçerlidir.
STT_SABIT_PROFIL: dict[str, tuple[str, str]] = {
    "crisperwhisper_turbo_ct2": ("CrisperWhisper2.0_turbo", "int8"),
    "parakeet_cpu_align": ("parakeet-unified-en-0.6b-int8", "int8"),
    "elevenlabs_scribe_v2": ("scribe_v2", "api"),
    # metin YouTube'un json3 otomatik altyazısından gelir, kelime zamanı CTC hizalamadan; ses tanıma modeli yok
    "youtube_translate": ("json3+ctc", "n/a"),
}
STT_YALNIZ_INGILIZCE = {"parakeet_cpu_align"}
STT_YALNIZ_GPU = {"crisperwhisper_turbo_ct2"}
TTS_YALNIZ_GPU = {"voxcpm2"}
YOUTUBE_ALANLARI = ("youtube.com", "youtu.be")  # youtube_translate yalnız bu alan adlarındaki bağlantıyla
STT_CRISPER = {"crisperwhisper_turbo_ct2"}
# CrisperWhisper dil tespiti kipleri motor başına (Turbo CT2 per_window desteklemez: runtime + contract.py).
# "auto" Turbo'ya çözülebildiği için Turbo'nun listesini alır. Tarif: docs/tarifler/dil_tespiti.md
CRISPER_DIL_KIPLERI = {
    "crisperwhisper_turbo_ct2": ["global_first_window", "continuous_stream"],
    "auto": ["global_first_window", "continuous_stream"],
}
# Konuşmacı ayrımını (ileri.pyannote_konusmaci_ayrimi) kendi içinde destekleyen motorlar
STT_KONUSMACI_AYRIMI = {"whisperx", "elevenlabs_scribe_v2"}
DISTIL_YALNIZ_INGILIZCE = {"distil-large-v3", "distil-large-v3.5"}
LLM_CEVIRI = [ad for ad in CEVIRI_ARKA_UCLARI if ad not in ("auto", "yerel")]
DIL_KODU = re.compile(r"^[a-z]{2,3}$")
MB = 1_000_000  # video.max_mb: ondalık MB (paylaşım uygulamalarının sınırlarıyla aynı birim)

# anahtar -> izinli değerler (liste) ya da tür
SEMA: dict[str, Any] = {
    "genel.is_turu": ["dublaj", "transkript"],
    "genel.dublaj_kipi": ["segment_sync", "full_text"],
    "genel.hedef_dil": HEDEF_DILLERI,
    "genel.transkript_bicimi": TRANSKRIPT_BICIMLERI,
    "genel.cihaz": ["auto", "cuda", "cpu"],
    "genel.cikti_klasoru": str,
    "genel.onbellek_klasoru": str,
    "genel.gunluk_seviyesi": ["DEBUG", "INFO", "WARNING", "ERROR"],
    "genel.arayuz_dili": ["auto", *arayuz_dili.mevcut_diller()],  # yeni dil = arayuz_dilleri/<dil>.json
    "genel.gozden_gecir": bool,
    "transkripsiyon.motor": STT_MOTORLARI,
    "transkripsiyon.model": str,
    "transkripsiyon.hesap_tipi": ["auto", "float16", "int8", "int8_float16", "int8_float32", "float32"],
    "transkripsiyon.kaynak_dil": str,
    "transkripsiyon.vad": bool,
    "transkripsiyon.crisper_dil_tespiti": ["global_first_window", "continuous_stream"],
    "transkripsiyon.whisperx_profili": WHISPERX_PROFILLERI,
    "ses_temizligi.kip": ["original", "clean", "preserve_background", "auto_background"],
    "ceviri.arka_uc": CEVIRI_ARKA_UCLARI,
    "ceviri.codex.model": str,
    "ceviri.codex.akil_yurutme": ["low", "medium", "high"],
    "ceviri.codex.cli_yolu": str,
    "ceviri.claude.model": str,
    "ceviri.claude.caba": ["low", "medium", "high"],
    "ceviri.claude.cli_yolu": str,
    "ses.motor": TTS_MOTORLARI,
    "ses.supertonic_ses": SUPERTONIC_SESLERI,
    "ses.akis": SUPERTONIC_AKISLARI,
    "ses.hiz": float,
    "ses.atempo": bool,
    "ses.voxcpm2_ses": str,
    "ses.voxcpm2_kadin_sesleri": str,
    "ses.voxcpm2_erkek_sesleri": str,
    "ses.ema_cihaz": ["auto", "cuda", "cpu"],
    "ses.ema_hiz": float,
    "ses.ema_tohum": int,
    "ses.konusmaci_cinsiyetine_gore_ses": bool,
    "ses.konusmaci_sesleri": dict,
    "ses.cinsiyet_kipi": ["konusmaci", "segment"],
    "ses.kadin_ses": SUPERTONIC_KADIN_SESLERI,
    "ses.erkek_ses": SUPERTONIC_ERKEK_SESLERI,
    "ses.xtts_referans_ses": str,
    "ses.xtts_lisans_onayi": bool,
    "ses.rvc_model": str,
    "ses.rvc_index": str,
    "ses.rvc_perde": int,
    "ses.rvc_riza_onayi": bool,
    "altyazi.mod": ["segment", "word", "rollup", "none"],
    "video.akilli_kare": bool,
    "video.politika": ["cq", "max_mb"],
    "video.cq": int,
    "video.max_mb": int,
    "video.yapay_zeka_etiketi": bool,
    "video.tam_metin_sure_uyumu": ["audio_to_video", "video_to_audio"],
    "ileri.tts_deneme": int,
    "ileri.tts_deneme_bekleme_sn": float,
    "ileri.ornekleme_hizi": int,
    "ileri.pyannote_konusmaci_ayrimi": bool,
}
SINIRLAR = {"video.cq": (0, 51), "ses.hiz": (0.5, 2.0), "ileri.tts_deneme": (1, 10),
            "video.max_mb": (0, 100000), "ileri.ornekleme_hizi": (8000, 96000), "ses.rvc_perde": (-24, 24),
            "ses.ema_hiz": (0.5, 2.0), "ses.ema_tohum": (0, 2**31 - 1)}


# Kaldırılan ayarlar: eski ayar dosyasında ya da --ayar'da görülürse uyarıyla yok sayılır (hata değil).
# ileri.tts_isci: hiçbir aşama okumuyordu (TTS segmentleri sırayla üretilir; Düzeltme A, madde 14).
KALDIRILAN_AYARLAR = frozenset({"ileri.tts_isci"})


# Emekli motor değerleri: anahtar -> {eski değer: yeni değer}. Enum denetiminden ÖNCE bakılır; eski ayar dosyası
# ya da --ayar bir sürüm boyunca uyarıyla yeni değere eşlenir (kullanici.toml'a dokunulmaz), sonraki sürümde
# bu tablo silinir ve eski değer normal "geçersiz seçenek" hatası olur. Motor kaldıran her değişiklik buraya satır ekler.
EMEKLI_DEGERLER: dict[str, dict[str, str]] = {
    "transkripsiyon.motor": {"crisperwhisper2_medium": "auto", "moonshine_medium_streaming_en": "auto",
                           "whisper_cpp_cpu_align": "auto", "speechmatics": "auto"},
    "transkripsiyon.crisper_dil_tespiti": {"per_window": "global_first_window"},  # yalnız CrisperWhisper Medium destekliyordu
}
_EMEKLI_UYARI = {
    "transkripsiyon.motor": (
        "'{eski}' bu sürümde kaldırıldı; '{yeni}' kullanılıyor (CrisperWhisper Turbo kuruluysa o, değilse faster-whisper).",
        "'{eski}' was removed in this version; using '{yeni}' (CrisperWhisper Turbo if installed, otherwise faster-whisper).",
    ),
    "transkripsiyon.crisper_dil_tespiti": (
        "'{eski}' bu sürümde kaldırıldı (yalnız kaldırılan CrisperWhisper Medium destekliyordu); '{yeni}' kullanılıyor.",
        "'{eski}' was removed in this version (only the removed CrisperWhisper Medium supported it); using '{yeni}'.",
    ),
}


def emekli_deger_esle(anahtar: str, deger: Any) -> Any:
    """Emekli bir seçenek değerini yeni değerine eşler ve iki dilli uyarı yazar; değilse değeri olduğu gibi döndürür."""
    yeni = EMEKLI_DEGERLER.get(anahtar, {}).get(deger) if isinstance(deger, str) else None
    if yeni is None:
        return deger
    tr, en = _EMEKLI_UYARI[anahtar]
    logger.warning("%s: %s | %s", anahtar, tr.format(eski=deger, yeni=yeni), en.format(eski=deger, yeni=yeni))
    return yeni


def _kaldirilanlari_ayikla(ayar: dict[str, Any], kaynak: str) -> dict[str, Any]:
    for anahtar in sorted(KALDIRILAN_AYARLAR & set(ayar)):
        logger.warning("%s: '%s' ayarı kaldırıldı (etkisi yoktu), yok sayılıyor", kaynak, anahtar)
        del ayar[anahtar]
    return ayar


def _duzlestir(veri: dict, onek: str = "") -> dict[str, Any]:
    cikti: dict[str, Any] = {}
    for anahtar, deger in veri.items():
        tam = f"{onek}{anahtar}"
        if isinstance(deger, dict) and tam not in SEMA:
            cikti.update(_duzlestir(deger, tam + "."))
        else:
            cikti[tam] = deger
    return cikti


def _deger_dogrula(anahtar: str, deger: Any) -> Any:
    if anahtar not in SEMA:
        raise AyarHatasi(f"bilinmeyen ayar: {anahtar}")
    kural = SEMA[anahtar]
    if isinstance(kural, list):
        deger = emekli_deger_esle(anahtar, deger)
        if deger not in kural:
            raise AyarHatasi(f"{anahtar} = {deger!r} geçersiz; seçenekler: {', '.join(map(str, kural))}")
        return deger
    if kural is float and isinstance(deger, int) and not isinstance(deger, bool):
        deger = float(deger)
    if kural is dict:
        if not isinstance(deger, dict) or not all(isinstance(v, str) for v in deger.values()):
            raise AyarHatasi(f"{anahtar} bir eşleme olmalı (konusmaci = \"ses\")")
        return {str(k): v for k, v in deger.items()}
    if not isinstance(deger, kural) or (kural is int and isinstance(deger, bool)):
        raise AyarHatasi(f"{anahtar} türü {kural.__name__} olmalı, gelen: {deger!r}")
    if anahtar in SINIRLAR:
        alt, ust = SINIRLAR[anahtar]
        if not alt <= deger <= ust:
            raise AyarHatasi(f"{anahtar} = {deger} aralık dışı ({alt}..{ust})")
    if anahtar == "transkripsiyon.kaynak_dil" and deger != "auto" and not DIL_KODU.match(deger):
        raise AyarHatasi(f"{anahtar} = {deger!r} geçersiz; \"auto\" ya da küçük harf ISO kodu (en, de, ...)")
    return deger


@dataclass(frozen=True)
class Bulgu:
    """Kombinasyon denetiminin tek bulgusu."""

    seviye: str  # "hata" | "uyari"
    anahtarlar: tuple[str, ...]
    mesaj: str

    def __str__(self) -> str:
        return f"{' + '.join(self.anahtarlar)}: {self.mesaj}"


def uyumluluk_denetle(ayar: dict[str, Any]) -> list[Bulgu]:
    """Tek tek geçerli ama birlikte çalışmayan seçimleri bulur (donanım ve kurulumdan bağımsız, saf denetim).

    Donanıma/kuruluma bağlı "auto" çözümlerinin denetimi `dubconfig_olustur()` içindedir.
    """
    b: list[Bulgu] = []

    def hata(mesaj: str, *anahtarlar: str) -> None:
        b.append(Bulgu("hata", anahtarlar, mesaj))

    def uyari(mesaj: str, *anahtarlar: str) -> None:
        b.append(Bulgu("uyari", anahtarlar, mesaj))

    kip, tts, dil = ayar["genel.dublaj_kipi"], ayar["ses.motor"], ayar["genel.hedef_dil"]
    stt, kaynak = ayar["transkripsiyon.motor"], ayar["transkripsiyon.kaynak_dil"]
    ceviri, cihaz = ayar["ceviri.arka_uc"], ayar["genel.cihaz"]
    dublaj = ayar["genel.is_turu"] == "dublaj"

    # --- dublaj kipi ---------------------------------------------------------------------------------------
    if ayar.get("genel.gozden_gecir"):
        if not dublaj:
            uyari("genel.gozden_gecir yalnız dublaj işinde durur; transkript işinde yok sayılır", "genel.gozden_gecir",
                  "genel.is_turu")
        elif kip == "full_text":
            hata("genel.gozden_gecir satır satır çalışır ve yalnız segment_sync kipinde vardır; full_text çevirisi tek "
                 "metindir", "genel.gozden_gecir", "genel.dublaj_kipi")
    if kip == "full_text" and dublaj:
        if tts not in TAM_METIN_TTS | {"auto"}:  # auto, full_text'te Supertonic'e çözülür
            hata("full_text kipi yalnız Supertonic ya da EMA Lightning ile seslendirir; ses.motor=supertonic ya da "
                 "ses.motor=ema_lightning seçin", "genel.dublaj_kipi", "ses.motor")
        if ceviri not in ("auto", "codex", "claude_code"):
            hata("full_text kipi yalnız Codex ya da Claude Code çeviri arka ucuyla çalışır", "genel.dublaj_kipi",
                 "ceviri.arka_uc")
    # --- seslendirme dili ----------------------------------------------------------------------------------
    if dublaj and tts == "supertonic" and dil not in SUPERTONIC_DILLERI:
        hata(f"Supertonic '{dil}' dilini okuyamaz; ses.motor=voxcpm2 seçin ya da desteklenen bir dil "
             f"({', '.join(sorted(SUPERTONIC_DILLERI))})", "genel.hedef_dil", "ses.motor")
    if dublaj and tts == "voxcpm2" and dil not in VOXCPM2_DENENEN_DILLER:
        uyari(f"VoxCPM2 '{dil}' dilinde denenmedi (denenen: {', '.join(sorted(VOXCPM2_DENENEN_DILLER))}); "
              "sonucu dinleyerek kontrol edin", "genel.hedef_dil", "ses.motor")
    if dublaj and tts == "xtts" and dil not in XTTS_DILLERI:
        hata(f"XTTS v2 '{dil}' dilini okuyamaz; desteklenen: {', '.join(sorted(XTTS_DILLERI))}",
             "genel.hedef_dil", "ses.motor")
    if dublaj and tts == "ema_lightning" and dil not in EMA_DILLERI:
        hata(f"EMA Lightning '{dil}' dilini okuyamaz (yalnız {', '.join(sorted(EMA_DILLERI))}); ses.motor=supertonic "
             "ya da voxcpm2 seçin", "genel.hedef_dil", "ses.motor")
    if tts == "ema_lightning" and ayar.get("ses.ema_cihaz") == "cuda" and cihaz == "cpu":
        hata("ses.ema_cihaz=cuda ile genel.cihaz=cpu çelişir; ses.ema_cihaz=auto ya da cpu seçin", "ses.ema_cihaz",
             "genel.cihaz")
    if dublaj and tts in TTS_YALNIZ_GPU and cihaz == "cpu":
        hata("VoxCPM2 NVIDIA GPU gerektirir; işlemcide ses.motor=supertonic kullanın", "ses.motor", "genel.cihaz")
    sesler = ayar.get("ses.konusmaci_sesleri") or {}
    if tts == "supertonic":
        yanlis = sorted(k for k, v in sesler.items() if v not in SUPERTONIC_SESLERI)
        if yanlis:
            hata(f"Supertonic konuşmacı sesleri F1..F5 / M1..M5 olmalı; hatalı: {', '.join(yanlis)}",
                 "ses.konusmaci_sesleri", "ses.motor")
    elif tts == "voxcpm2":
        _voxcpm2_sesleri_denetle(ayar, sesler, dil if dublaj else "", hata, uyari)
    elif tts == "ema_lightning" and sesler:
        uyari("EMA Lightning tek sesli; ses.konusmaci_sesleri yok sayılır", "ses.konusmaci_sesleri", "ses.motor")
    elif tts == "xtts" and sesler:
        uyari("XTTS tek referans sesle okur; ses.konusmaci_sesleri yok sayılır", "ses.konusmaci_sesleri", "ses.motor")
    # --- cinsiyete göre ses kipi ---------------------------------------------------------------------------
    if ayar.get("ses.cinsiyet_kipi") == "segment":
        if tts not in ("auto", "supertonic", "voxcpm2") or not ayar["ses.konusmaci_cinsiyetine_gore_ses"]:
            uyari("ses.cinsiyet_kipi=segment yalnız ses.motor=supertonic / voxcpm2 ve "
                  "ses.konusmaci_cinsiyetine_gore_ses=true iken etkilidir", "ses.cinsiyet_kipi", "ses.motor",
                  "ses.konusmaci_cinsiyetine_gore_ses")
        elif sesler:
            cift = ("ses.voxcpm2_kadin_sesleri / ses.voxcpm2_erkek_sesleri listesinin ilk sesiyle" if tts == "voxcpm2"
                    else "ses.kadin_ses / ses.erkek_ses ile")
            uyari(f"segment kipinde konuşmacı ayrımı yapılmaz; ses.konusmaci_sesleri yok sayılır, her cümle {cift} "
                  "okunur", "ses.cinsiyet_kipi", "ses.konusmaci_sesleri")
    if tts not in ("voxcpm2", "auto") and (ayar.get("ses.voxcpm2_kadin_sesleri") or ayar.get("ses.voxcpm2_erkek_sesleri")):
        uyari("ses.voxcpm2_kadin_sesleri / ses.voxcpm2_erkek_sesleri yalnız ses.motor=voxcpm2 iken kullanılır",
              "ses.voxcpm2_kadin_sesleri", "ses.voxcpm2_erkek_sesleri", "ses.motor")
    # --- XTTS v2 (isteğe bağlı, CPML ticari olmayan) ------------------------------------------------------
    if tts == "xtts":
        uyari(XTTS_KALKIYOR_TR + " | " + XTTS_KALKIYOR_EN, "ses.motor")
    referans = str(ayar.get("ses.xtts_referans_ses") or "").strip()
    if dublaj and tts == "xtts" and not referans:
        hata("XTTS referans ses ister: ses.xtts_referans_ses = kendi sesiniz ya da sahibinin izin verdiği bir ses "
             "dosyası (ETHICS.md)", "ses.xtts_referans_ses", "ses.motor")
    if referans and tts != "xtts":
        uyari("ses.xtts_referans_ses yalnız ses.motor=xtts iken kullanılır", "ses.xtts_referans_ses", "ses.motor")
    # --- RVC (isteğe bağlı, kendi modeliniz, rıza zorunlu) ------------------------------------------------
    rvc_model = str(ayar.get("ses.rvc_model") or "").strip()
    if rvc_model and not ayar.get("ses.rvc_riza_onayi"):
        hata("RVC modeli seçili ama rıza onayı yok: modelin sesi size ait değilse sesin sahibinin açık izni "
             "gerekir; onaylıyorsanız ses.rvc_riza_onayi=true (ETHICS.md)", "ses.rvc_model", "ses.rvc_riza_onayi")
    if not rvc_model and (str(ayar.get("ses.rvc_index") or "").strip() or ayar.get("ses.rvc_perde")):
        uyari("ses.rvc_index / ses.rvc_perde yalnız ses.rvc_model doluyken kullanılır", "ses.rvc_index",
              "ses.rvc_perde", "ses.rvc_model")
    if rvc_model and not dublaj:
        uyari("RVC yalnız dublaj sesine uygulanır; transkript işinde yok sayılır", "ses.rvc_model", "genel.is_turu")
    # --- video ---------------------------------------------------------------------------------------------
    if ayar.get("video.akilli_kare") and not dublaj:
        uyari("video.akilli_kare yalnız dublaj videosunu kırpar; transkript işinde yok sayılır", "video.akilli_kare",
              "genel.is_turu")
    # --- çeviri --------------------------------------------------------------------------------------------
    if dublaj and ceviri == "yerel":
        if dil != "tr":
            hata("yerel çeviri (Opus-MT) yalnız İngilizce → Türkçe çevirir; başka hedef dil için LLM arka ucu "
                 f"seçin ({', '.join(LLM_CEVIRI)})", "ceviri.arka_uc", "genel.hedef_dil")
        if kaynak not in ("auto", "en"):
            hata("yerel çeviri (Opus-MT) yalnız İngilizce kaynak çevirir; LLM arka ucu seçin",
                 "ceviri.arka_uc", "transkripsiyon.kaynak_dil")
    if dublaj and ayar["ses.akis"] != "natural_blocks_1" and (ceviri == "yerel" or tts != "supertonic"):
        uyari("ses.akis (aday/onarım akışı) yalnız LLM çeviri arka ucu + Supertonic ile etkilidir; bu seçimde "
              "yok sayılır", "ses.akis", "ceviri.arka_uc", "ses.motor")
    # --- transkripsiyon ------------------------------------------------------------------------------------
    deneysel = {m.ad: m.deneysel for m in kayit.motorlar("stt") if m.deneysel}
    if stt in deneysel:
        uyari(f"{stt} DENEYSEL: {deneysel[stt]}", "transkripsiyon.motor")
    if stt in STT_YALNIZ_INGILIZCE and kaynak not in ("auto", "en"):
        hata(f"{stt} yalnız İngilizce kaynak çözer; kaynak_dil=en/auto ya da çok dilli motor seçin "
             "(faster-whisper, whisperx)", "transkripsiyon.motor", "transkripsiyon.kaynak_dil")
    if stt in STT_YALNIZ_GPU and cihaz == "cpu":
        hata(f"{stt} yalnız NVIDIA GPU'da çalışır; işlemci için faster-whisper ya da "
             "parakeet_cpu_align seçin", "transkripsiyon.motor", "genel.cihaz")
    if ayar["ileri.pyannote_konusmaci_ayrimi"]:
        if stt in STT_SABIT_PROFIL and stt not in STT_KONUSMACI_AYRIMI:
            hata(f"{stt} konuşmacı ayrımı yapmaz; ileri.pyannote_konusmaci_ayrimi=false yapın ya da "
                 f"{', '.join(sorted(STT_KONUSMACI_AYRIMI))} seçin", "ileri.pyannote_konusmaci_ayrimi",
                 "transkripsiyon.motor")
        elif stt not in STT_KONUSMACI_AYRIMI:
            uyari("ileri.pyannote_konusmaci_ayrimi yalnız whisperx / elevenlabs_scribe_v2 ile "
                  "etkilidir (dublajda konuşmacı ayrımını ses.konusmaci_cinsiyetine_gore_ses yapar)",
                  "ileri.pyannote_konusmaci_ayrimi", "transkripsiyon.motor")
    dil_kipi = ayar["transkripsiyon.crisper_dil_tespiti"]
    if dil_kipi != "global_first_window" and stt not in STT_CRISPER | {"auto"}:
        uyari("crisper_dil_tespiti yalnız CrisperWhisper motorlarında etkilidir", "transkripsiyon.crisper_dil_tespiti",
              "transkripsiyon.motor")
    if dil_kipi not in CRISPER_DIL_KIPLERI.get(stt, CRISPER_DIL_KIPLERI["auto"]):
        hata(f"{stt} '{dil_kipi}' dil tespiti kipini desteklemez; seçenekler: "
             f"{', '.join(CRISPER_DIL_KIPLERI[stt])} (docs/tarifler/dil_tespiti.md)",
             "transkripsiyon.crisper_dil_tespiti", "transkripsiyon.motor")
    if stt in STT_CRISPER | {"auto"} and dil_kipi != "global_first_window" and kaynak != "auto":
        uyari(f"sabit kaynak dil yalnız global_first_window kipinde tespiti atlar; {dil_kipi} kipinde dil yine "
              "akış boyunca tespit edilir", "transkripsiyon.kaynak_dil", "transkripsiyon.crisper_dil_tespiti")
    if stt == "youtube_translate" and kaynak != "auto":
        uyari("youtube_translate'te dil videonun altyazı izinden gelir; transkripsiyon.kaynak_dil yok sayılır",
              "transkripsiyon.kaynak_dil", "transkripsiyon.motor")
    if stt == "whisperx" and ayar["transkripsiyon.model"] in DISTIL_YALNIZ_INGILIZCE and kaynak not in ("auto", "en"):
        hata("whisperx'te distil modellerinin çok dilli yedeği yoktur (yedek yalnız faster-whisper'da); "
             "transkripsiyon.model=large-v3-turbo seçin", "transkripsiyon.model", "transkripsiyon.motor",
             "transkripsiyon.kaynak_dil")
    profil = ayar["transkripsiyon.whisperx_profili"]
    if profil != "auto":
        gereken = "float32" if profil == "whisperx_float32_quality_v1" else "int8"
        if stt != "whisperx":
            hata("whisperx_profili yalnız transkripsiyon.motor=whisperx ile seçilir", "transkripsiyon.whisperx_profili",
                 "transkripsiyon.motor")
        elif ayar["transkripsiyon.hesap_tipi"] != gereken:
            hata(f"{profil} profili hesap_tipi={gereken} ister", "transkripsiyon.whisperx_profili",
                 "transkripsiyon.hesap_tipi")
    if (stt in ("faster-whisper", "faster_whisper_ctc", "auto") and ayar["transkripsiyon.model"] in DISTIL_YALNIZ_INGILIZCE
            and kaynak not in ("auto", "en")):
        uyari("distil modelleri yalnız İngilizce çözer; İngilizce olmayan kaynakta hat çok dilli modele geçer "
              "(WhisperX large-v3-turbo float32)",
              "transkripsiyon.model", "transkripsiyon.kaynak_dil")
    # --- video ---------------------------------------------------------------------------------------------
    if ayar["video.politika"] == "max_mb" and ayar["video.max_mb"] <= 0:
        hata("video.politika=max_mb için video.max_mb 1 ya da daha büyük olmalı", "video.politika", "video.max_mb")
    if ayar["video.politika"] == "cq" and ayar["video.max_mb"] > 0:
        uyari("video.max_mb yalnız video.politika=max_mb iken kullanılır", "video.max_mb", "video.politika")
    return b


def _uyumluluk_uygula(ayar: dict[str, Any]) -> None:
    hatalar = [str(x) for x in uyumluluk_denetle(ayar) if x.seviye == "hata"]
    if hatalar:
        raise AyarHatasi("uyumsuz seçim: " + " | ".join(hatalar))


def tts_auto_coz(ayar: dict[str, Any]) -> tuple[str, str]:
    """ses.motor="auto" -> (motor, gerekçe). VoxCPM2 kuruluysa ve çalışan NVIDIA GPU varsa o, değilse Supertonic.

    Kurulu denetimi `kayit` kaydındaki VoxCPM2 denetimiyle, GPU denetimi `genel.cihaz` çözümüyle aynıdır.
    full_text kipi yalnız Supertonic/EMA ile seslendirdiği için Supertonic'e çözülür. Açık seçim ("voxcpm2" vb.) buraya girmez.
    """
    if ayar["genel.dublaj_kipi"] == "full_text":
        return "supertonic", "ses.motor=auto → supertonic: full_text kipi yalnız Supertonic ya da EMA ile seslendirir"
    from dublaj_hatti.bolum_00_omurga.runtime.donanim import DonanimHatasi, cihaz_coz

    try:
        gpu = cihaz_coz(ayar["genel.cihaz"]) == "cuda"
    except DonanimHatasi:
        gpu = False
    if not gpu:
        return "supertonic", "ses.motor=auto → supertonic: çalışan NVIDIA GPU yok (VoxCPM2 GPU ister)"
    if not kayit.motor("voxcpm2").kurulu():
        return "supertonic", ("ses.motor=auto → supertonic: VoxCPM2 kurulu değil (kurulum: scripts/kur.ps1 -Adim "
                              "voxcpm2); kurulunca otomatik VoxCPM2 kullanılır")
    return "voxcpm2", "ses.motor=auto → voxcpm2: kurulu ve NVIDIA GPU çalışıyor"


def tts_motoru_coz(ayar: dict[str, Any], gunluk: bool = False) -> str:
    """Ayardaki ses motorunun somut adı ("auto" çözülür); transkript işinde ses kullanılmaz (Supertonic döner)."""
    tts = ayar["ses.motor"]
    if tts != "auto":
        return tts
    if ayar["genel.is_turu"] != "dublaj":
        return "supertonic"
    motor, neden = tts_auto_coz(ayar)
    if gunluk:
        logger.info("Seçim gerekçesi: %s", neden)
    return motor


def stt_secimi_coz(ayar: dict[str, Any], cihaz: str, hesap_tipi: str) -> tuple[str, str, str, str]:
    """(motor, model, hesap tipi, whisperx profili). "auto" motoru ve sabit sözleşmeli motorların modelini çözer."""
    stt = ayar["transkripsiyon.motor"]
    if stt == "auto":
        # Yedek faster-whisper metni + CTC kelime zamanı (ADR 0017); elle "faster-whisper" Whisper zamanını korur
        stt = "crisperwhisper_turbo_ct2" if cihaz == "cuda" and crisper_turbo_kurulu() else "faster_whisper_ctc"
    if stt in STT_SABIT_PROFIL:
        model, hesap = STT_SABIT_PROFIL[stt]
        return stt, model, hesap, ""
    profil = ayar["transkripsiyon.whisperx_profili"]
    return stt, ayar["transkripsiyon.model"], hesap_tipi, "" if profil == "auto" else profil


def stt_auto_gerekcesi(stt: str, cihaz: str) -> str:
    if stt == "crisperwhisper_turbo_ct2":
        return ("transkripsiyon.motor=auto → crisperwhisper_turbo_ct2: GPU var ve kurulu (int8 ~1,4 GB VRAM, en hassas "
                "kelime zamanı; ticari olmayan lisans)")
    if cihaz == "cuda":
        return ("transkripsiyon.motor=auto → faster_whisper_ctc (GPU): CrisperWhisper Turbo kurulu değil; metin "
                "faster-whisper, kelime zamanı CTC hizalama")
    return ("transkripsiyon.motor=auto → faster_whisper_ctc (işlemci, int8): GPU yok, CrisperWhisper yalnız GPU'da "
            "çalışır; metin faster-whisper, kelime zamanı CTC hizalama")


def _voxcpm2_sesleri_denetle(ayar: dict[str, Any], sesler: dict, dil: str, hata: Callable, uyari: Callable) -> None:
    """Favori listeler ve konuşmacı haritasındaki VoxCPM2 sesleri: hazır ses adı var mı, cinsiyet tutuyor mu."""
    adlar = {"ses.voxcpm2_ses": [str(ayar.get("ses.voxcpm2_ses") or "")],
             "ses.voxcpm2_kadin_sesleri": ses_listesi(ayar.get("ses.voxcpm2_kadin_sesleri")),
             "ses.voxcpm2_erkek_sesleri": ses_listesi(ayar.get("ses.voxcpm2_erkek_sesleri")),
             "ses.konusmaci_sesleri": [str(v) for v in sesler.values()]}
    for anahtar, liste in adlar.items():
        yanlis = [s for s in liste if s.startswith("hazir/") and s[6:] not in kayit.VOXCPM2_HAZIR_SESLER]
        if yanlis:
            hata(f"{anahtar}: bilinmeyen hazır ses {', '.join(yanlis)}; hazır sesler: "
                 f"{', '.join('hazir/' + a for a in kayit.VOXCPM2_HAZIR_SESLER)} (kendi sesiniz: <ad>/<çeşit> ya da kitaplik/<kimlik>)",
                 anahtar, "ses.motor")
    from dublaj_hatti import ses_kitapligi  # yerel içe aktarma: ses_kitapligi bu modülden PROJE_KOKU alır

    for anahtar, liste in adlar.items():  # kitaplik/<kimlik>: kullanıcının kendi sesi, kitaplıkta var mı
        for ses in liste:
            if ses_kitapligi.kitaplik_mi(ses):
                try:
                    ses_kitapligi.coz(ses)
                except ses_kitapligi.SesKitapligiHatasi as sorun:
                    hata(f"{anahtar}: {sorun}", anahtar, "ses.motor")
    for anahtar, cinsiyet in (("ses.voxcpm2_kadin_sesleri", "female"), ("ses.voxcpm2_erkek_sesleri", "male")):
        ters = [s for s in adlar[anahtar]
                if s.startswith("hazir/") and kayit.VOXCPM2_HAZIR_CINSIYET.get(s[6:], cinsiyet) != cinsiyet]
        if ters:
            uyari(f"{anahtar} listesinde öbür cinsiyetin hazır sesi var: {', '.join(ters)}", anahtar)
    if not ayar.get("ses.konusmaci_cinsiyetine_gore_ses") or not dil:
        return
    kadin, erkek, kaynak = voxcpm2_havuzlari({**ayar, "ses.voxcpm2_ses": voxcpm2_tek_ses(ayar)})
    if kaynak == "tek_ses":
        uyari(f"VoxCPM2: '{dil}' için hazır ses yok ve favori liste boş; bütün konuşmacılar tek sesle "
              f"({kadin[0]}) okunur. Kadın ve erkek sesinizi tasarlayıp ses.voxcpm2_kadin_sesleri / "
              "ses.voxcpm2_erkek_sesleri listesine yazın", "ses.voxcpm2_kadin_sesleri", "ses.voxcpm2_erkek_sesleri")
    elif kaynak == "varsayilan" and kadin == erkek:
        uyari(f"VoxCPM2: '{dil}' için hazır kadın sesi yok; kadın konuşmacılar da {erkek[0]} ile okunur. "
              f"Bir kadın sesi tasarlayın (VoxCPM2 reposu örnek: {dil}_belgesel_kadin) ve "
              "ses.voxcpm2_kadin_sesleri listesine yazın", "ses.voxcpm2_kadin_sesleri")


def form_ek_bilgisi(dil: str | None = None) -> dict[str, dict[str, Any]]:
    """Ayarlar çekmecesine şemanın yanında giden ek bilgi (arayüzler otomatik üretir; motor gizlenmez).

    - "etiketler": seçenek → donanım etiketi ("CPU'da yavaş", "CPU'da çalışmaz", "VRAM yetmez ...", "bulut ...");
      GPU bilgisi torch yüklenmeden `nvidia-smi` ile alınır (kesin karar iş başlarken).
    - "suzgec": genel.hedef_dil listesinin ses.motor'a göre süzülmesi (kayit.tts_dil_suzgeci).
    - "ses_secenekleri": ses.konusmaci_sesleri için seçili TTS'in sesleri (konuşmacı başına ses).
    """
    from dublaj_hatti.arayuz_dili import t
    from dublaj_hatti.bolum_00_omurga.runtime.donanim import gpu_bilgisi_hafif, motor_etiketi

    gpu_var, vram = gpu_bilgisi_hafif()
    cihaz = "cuda" if gpu_var else "cpu"
    ek: dict[str, dict[str, Any]] = {}
    for anahtar, tur in (("transkripsiyon.motor", "stt"), ("ceviri.arka_uc", "ceviri"), ("ses.motor", "tts")):
        etiketler = {m.ad: motor_etiketi(m, cihaz, vram, dil) for m in kayit.motorlar(tur)}
        for m in kayit.motorlar(tur):  # deneysel motor gizlenmez, etiketlenir
            if m.deneysel:
                etiketler[m.ad] = "; ".join(e for e in (t("etiket.deneysel", dil), etiketler[m.ad]) if e)
        ek[anahtar] = {"etiketler": {k: v for k, v in etiketler.items() if v}}
    # dil_adlari: Önerilen sekmesindeki hedef dil seçicisi aynı ayarı gösterir, adı dilin kendi dilinde (kayit)
    ek["genel.hedef_dil"] = {"suzgec": {"anahtar": "ses.motor", "degerler": kayit.tts_dil_suzgeci()},
                             "dil_adlari": {kod: kayit.dil_kendi_adi(kod) for kod in kayit.tts_hedef_dilleri()}}
    ek["ses.konusmaci_sesleri"] = {"ses_secenekleri": {
        "supertonic": list(kayit.SUPERTONIC_SESLER),
        "voxcpm2": [f"hazir/{ad}" for ad in kayit.VOXCPM2_HAZIR_SESLER],
        "ema_lightning": [],
        "xtts": [],
    }, "bicim": "SPEAKER_00:M2, SPEAKER_01:F1"}
    for anahtar, cinsiyet in (("ses.voxcpm2_kadin_sesleri", "female"), ("ses.voxcpm2_erkek_sesleri", "male")):
        ek[anahtar] = {"ses_secenekleri": {"voxcpm2": [
            f"hazir/{ad}" for ad in kayit.VOXCPM2_HAZIR_SESLER if kayit.VOXCPM2_HAZIR_CINSIYET[ad] == cinsiyet]},
        }
    ek["genel.cihaz"] = {"donanim": {"gpu": gpu_var, "vram_mb": vram}}
    return ek


def _metin_degeri_coz(anahtar: str, ham: str) -> Any:
    kural = SEMA.get(anahtar)
    if kural is bool:
        if ham.lower() in ("true", "1", "evet", "acik", "on"):
            return True
        if ham.lower() in ("false", "0", "hayir", "kapali", "off"):
            return False
        raise AyarHatasi(f"{anahtar} için true/false bekleniyor: {ham!r}")
    if kural is int:
        return int(ham)
    if kural is float:
        return float(ham)
    if kural is dict:  # "SPEAKER_00:M2, SPEAKER_01:F1" (arayüz ve --ayar); boş metin = eşleme yok
        esleme: dict[str, str] = {}
        for parca in filter(None, (p.strip() for p in ham.split(","))):
            if ":" not in parca:
                raise AyarHatasi(f"{anahtar} biçimi KONUSMACI:SES[,KONUSMACI:SES] olmalı: {parca!r}")
            konusmaci, ses = (x.strip() for x in parca.split(":", 1))
            if not konusmaci or not ses:
                raise AyarHatasi(f"{anahtar}: boş konuşmacı ya da ses: {parca!r}")
            esleme[konusmaci] = ses
        return esleme
    return ham


def esleme_metni(esleme: dict[str, str]) -> str:
    """`ses.konusmaci_sesleri` eşlemesinin `--ayar` / arayüz metni (ters işlem: `_metin_degeri_coz`)."""
    return ", ".join(f"{k}:{v}" for k, v in sorted(esleme.items()))


def toml_oku(yol: Path) -> dict[str, Any]:
    with open(yol, "rb") as dosya:
        return _kaldirilanlari_ayikla(_duzlestir(tomllib.load(dosya)), str(yol))


def ayarlari_yukle(dosya: str | Path | None = None, ustune: list[str] | None = None) -> dict[str, Any]:
    """Katmanları birleştirip doğrulanmış düz sözlük döndürür (anahtar: "bolum.ad")."""
    ayar = toml_oku(VARSAYILAN_DOSYA)
    katmanlar = [PROJE_KOKU / "ayarlar" / "kullanici.toml"]
    if os.environ.get(KULLANICI_DOSYA_ENV, "").strip():
        katmanlar.append(Path(os.environ[KULLANICI_DOSYA_ENV]).expanduser())
    if dosya:
        katmanlar.append(Path(dosya).expanduser())
    for katman in katmanlar:
        if katman.is_file():
            ayar.update(toml_oku(katman))
        elif katman != katmanlar[0]:
            raise AyarHatasi(f"ayar dosyası bulunamadı: {katman}")
    for ifade in ustune or []:
        if "=" not in ifade:
            raise AyarHatasi(f"--ayar biçimi bolum.ad=deger olmalı: {ifade!r}")
        anahtar, ham = (parca.strip() for parca in ifade.split("=", 1))
        if anahtar in KALDIRILAN_AYARLAR:
            _kaldirilanlari_ayikla({anahtar: ham}, "--ayar")
            continue
        ust, _, alt = anahtar.rpartition(".")
        if anahtar not in SEMA and SEMA.get(ust) is dict:  # --ayar ses.konusmaci_sesleri.SPEAKER_00=M2
            ayar[ust] = {**(ayar.get(ust) or {}), alt: ham}
            continue
        ayar[anahtar] = _metin_degeri_coz(anahtar, ham)
    dogru = {anahtar: _deger_dogrula(anahtar, deger) for anahtar, deger in ayar.items()}
    _uyumluluk_uygula(dogru)
    return dogru


def ayarlari_ic_ice(ayar: dict[str, Any]) -> dict[str, Any]:
    """Düz sözlüğü arayüzlerin göstereceği iç içe biçime çevirir."""
    cikti: dict[str, Any] = {}
    for anahtar, deger in ayar.items():
        hedef = cikti
        parcalar = anahtar.split(".")
        for parca in parcalar[:-1]:
            hedef = hedef.setdefault(parca, {})
        hedef[parcalar[-1]] = copy.deepcopy(deger)
    return cikti


def crisper_turbo_kurulu() -> bool:
    try:
        from dublaj_hatti.bolum_00_omurga.runtime.crisperwhisper_turbo_ct2_runtime import (
            resolve_worker_path,
            resolve_wsl_python_path,
        )

        resolve_worker_path()
        resolve_wsl_python_path()
        return True
    except (FileNotFoundError, OSError, ImportError):
        return False


def konusmaci_modelleri_kurulu() -> bool:
    """3D-Speaker CAM++ (VAD: faster-whisper içindeki Silero) ve cinsiyet sınıflandırıcı ağırlıkları yerinde mi (kur.ps1 -Adim modeller)."""
    kok = PROJE_KOKU / "runtime_assets" / "model_cache"
    gerekli = [
        kok / "modelscope/hub/models/iic/speech_campplus_sv_zh_en_16k-common_advanced/campplus_cn_en_common.pt",
    ]
    return all(p.is_file() for p in gerekli) and cinsiyet_modeli_kurulu()


def cinsiyet_modeli_kurulu() -> bool:
    """Segment bazlı cinsiyet kipi yalnız cinsiyet sınıflandırıcıyı ister (konuşmacı ayrımı yapılmaz)."""
    kok = PROJE_KOKU / "runtime_assets" / "model_cache"
    cinsiyet = kok / "huggingface/hub/models--alefiury--wav2vec2-large-xlsr-53-gender-recognition-librispeech/snapshots"
    return any(cinsiyet.glob("*/model.safetensors"))


def youtube_baglantisi_mi(kaynak: str) -> bool:
    from urllib.parse import urlparse

    metin = (kaynak or "").strip()
    if not metin.lower().startswith(("https://", "http://")):
        return False
    host = (urlparse(metin).hostname or "").lower()
    return any(host == alan or host.endswith("." + alan) for alan in YOUTUBE_ALANLARI)


@dataclass
class Cozum:
    """"auto" seçimlerinin neye çözüldüğü (günlüğe ve arayüze yazılır)."""

    cihaz: str
    hesap_tipi: str
    stt_motoru: str
    translator_engine: str
    llm_backend: str
    ceviri_kaynagi: str
    gerekceler: list[str] = field(default_factory=list)  # "auto" ve donanım kararlarının nedeni (günlük + ekran)


def _ortami_ayarla(ayar: dict[str, Any]) -> None:
    eslesme = {
        "ceviri.codex.model": "CODEX_BRIDGE_CODEX_MODEL",
        "ceviri.codex.akil_yurutme": "CODEX_BRIDGE_CODEX_REASONING_EFFORT",
        "ceviri.codex.cli_yolu": "CODEX_BRIDGE_CODEX_BIN",
        "ceviri.claude.model": "CODEX_BRIDGE_CLAUDE_MODEL",
        "ceviri.claude.caba": "CODEX_BRIDGE_CLAUDE_EFFORT",
        "ceviri.claude.cli_yolu": "CODEX_BRIDGE_CLAUDE_CLI",
    }
    for anahtar, degisken in eslesme.items():
        deger = str(ayar.get(anahtar) or "").strip()
        if deger and not os.environ.get(degisken, "").strip():
            os.environ[degisken] = deger
    if ayar.get("genel.cikti_klasoru"):  # açıkça verilen ayar .env'deki değeri ezer
        os.environ["DUBLAJ_OUTPUT_DIR"] = str(ayar["genel.cikti_klasoru"])


def _ctc_modeli_denetle(ayar: dict[str, Any], gerekce: Callable[[str], None]) -> None:
    """faster_whisper_ctc: CTC hizalama modeli kurulu mu (Whisper zamanına sessiz düşüş yok; ADR 0005/0009).

    Kaynak dil sabitse ve modeli yoksa iş başlamadan AyarHatasi; dil otomatikse eksik sabit modeller uyarı olarak
    yazılır, asıl denetim dil tespitinden sonra dubber'da yapılır. full_text kipinde kelime zamanı kullanılmaz.
    """
    from dublaj_hatti.bolum_00_omurga.runtime.ctc_model_durumu import (
        KURULUM_ADIMI,
        CtcModeliEksikHatasi,
        ctc_modeli_gerekli,
        kontrol_ozeti,
    )

    if ayar["genel.is_turu"] == "dublaj" and ayar["genel.dublaj_kipi"] == "full_text":
        return
    onbellek = ayar.get("genel.onbellek_klasoru") or None
    kaynak_dil = ayar["transkripsiyon.kaynak_dil"]
    if kaynak_dil != "auto":
        try:
            ctc_modeli_gerekli(kaynak_dil, onbellek)
        except CtcModeliEksikHatasi as hata:
            raise AyarHatasi(str(hata)) from hata
        return
    eksik = [dil for dil, var in kontrol_ozeti(onbellek).items() if not var]
    if eksik:
        metin = (f"faster_whisper_ctc: CTC hizalama modeli eksik ({', '.join(eksik)}); bu dillerde iş dil tespitinden "
                 f"sonra açık hatayla durur. Kurulum: {KURULUM_ADIMI}")
        logger.warning(metin)
        gerekce(metin)


def _kurulum_denetle(ayar: dict[str, Any], kaynak: str | None, gerekce: Callable[[str], None]) -> None:
    """İsteğe bağlı eklerin (K2) kuruluma ve kaynağa bağlı denetimi; saf kurallar `uyumluluk_denetle()` içinde."""
    dublaj = ayar["genel.is_turu"] == "dublaj"
    if ayar["transkripsiyon.motor"] == "youtube_translate":
        if kaynak is not None and not youtube_baglantisi_mi(kaynak):
            raise AyarHatasi("transkripsiyon.motor=youtube_translate yalnız YouTube bağlantısıyla çalışır (metin "
                             "videonun altyazısından gelir); yerel dosya için başka motor seçin (ör. faster-whisper)")
        if importlib.util.find_spec("yt_dlp") is None:
            raise AyarHatasi("youtube_translate yt-dlp ister ve kurulu değil: pip install .[youtube] "
                             "(ya da scripts/kur.ps1 -Adim youtube)")
    if dublaj and ayar.get("video.akilli_kare") and importlib.util.find_spec("cv2") is None:
        gerekce("video.akilli_kare açık ama OpenCV kurulu değil (pip install .[akilli-kare]); video kırpılmadan "
                "kaynak görüntüyle sürer")
    if dublaj and ayar["ses.motor"] == "ema_lightning":
        from dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts import ema_durumu

        durum = ema_durumu()
        if not durum["kurulu"]:
            raise AyarHatasi("ses.motor=ema_lightning kurulu değil: scripts/kur.ps1 -Adim tts-ema "
                             f"(paket {durum['paket']}, ağırlık {durum['agirlik']})")
        if not durum["onnx_cpu"]:
            gerekce("EMA işlemci yolu ONNX'siz (dışa aktarım yok ya da eşitlik denetimi geçmedi): işlemcide torch")
    if dublaj and ayar["ses.motor"] == "xtts":
        from dublaj_hatti.bolum_50_seslendirme.xtts_tts.api import KURULUM_IPUCU, xtts_python
        from dublaj_hatti.bolum_50_seslendirme.xtts_tts.lisans import (
            LISANS_METNI,
            lisans_onayini_kaydet,
            lisans_onayli,
        )

        if xtts_python() is None:
            raise AyarHatasi(KURULUM_IPUCU)
        if not lisans_onayli():
            if not ayar.get("ses.xtts_lisans_onayi"):
                raise AyarHatasi(LISANS_METNI + " Kabul ediyorsanız: ses.xtts_lisans_onayi=true ya da "
                                 "python -m dublaj_hatti.bolum_50_seslendirme.xtts_tts onay --kabul")
            lisans_onayini_kaydet()  # kullanıcı ayarla açıkça kabul etti; onay yerel dosyaya yazılır
            gerekce("XTTS v2 CPML (ticari olmayan) lisans onayı ayardan alındı ve kaydedildi")
        referans = Path(str(ayar["ses.xtts_referans_ses"])).expanduser()
        if not referans.is_file():
            raise AyarHatasi(f"XTTS referans sesi bulunamadı: {referans.name}")
    rvc_model = str(ayar.get("ses.rvc_model") or "").strip()
    if dublaj and rvc_model:
        from dublaj_hatti.bolum_50_seslendirme.rvc_ses_donusturme.donusturucu import KURULUM_IPUCU as RVC_IPUCU
        from dublaj_hatti.bolum_50_seslendirme.rvc_ses_donusturme.donusturucu import rvc_durumu

        if not rvc_durumu()["kurulu"]:
            raise AyarHatasi(RVC_IPUCU)
        for anahtar in ("ses.rvc_model", "ses.rvc_index"):
            deger = str(ayar.get(anahtar) or "").strip()
            if deger and not Path(deger).expanduser().is_file():
                raise AyarHatasi(f"{anahtar} dosyası bulunamadı: {Path(deger).name}")


def ses_listesi(metin: Any) -> list[str]:
    """`ses.voxcpm2_kadin_sesleri` gibi virgüllü ses listesini ayırır: "hazir/a, ad/2" -> ["hazir/a", "ad/2"]."""
    return [p.strip() for p in str(metin or "").split(",") if p.strip()]


def voxcpm2_havuzlari(ayar: dict[str, Any]) -> tuple[list[str], list[str], str]:
    """VoxCPM2 cinsiyete göre (kadın, erkek) favori listesi ve kaynağı
    ("kullanici" | "varsayilan" | "tek_ses" | "secili_ses").

    Kullanıcının listesi önce gelir; boş liste hedef dilin hazır seslerinden dolar; o dilde de yoksa tek ses
    (ses.voxcpm2_ses). Bir cinsiyetin listesi boşsa o cinsiyet öbür listeyi kullanır. Listeler boşken tek ses
    kitaplıktan seçilmişse (kitaplik/<kimlik>) herkes o sesle okunur ("secili_ses").
    """
    kadin = ses_listesi(ayar.get("ses.voxcpm2_kadin_sesleri"))
    erkek = ses_listesi(ayar.get("ses.voxcpm2_erkek_sesleri"))
    kaynak = "kullanici"
    secili = str(ayar.get("ses.voxcpm2_ses") or "")
    if not kadin and not erkek and secili.startswith("kitaplik/"):
        return [secili], [secili], "secili_ses"  # kullanıcı kitaplıktan kendi sesini seçti: herkes o sesle okunur
    if not kadin and not erkek:
        kadin, erkek = kayit.voxcpm2_varsayilan_havuz(str(ayar.get("genel.hedef_dil") or ""))
        kaynak = "varsayilan"
    if not kadin and not erkek:
        tek = str(ayar.get("ses.voxcpm2_ses") or "")
        return [tek], [tek], "tek_ses"
    return kadin or erkek, erkek or kadin, kaynak


def voxcpm2_tek_ses(ayar: dict[str, Any]) -> str:
    """Tek ses: kullanıcının sesi; varsayılan Türkçe ses başka hedef dilde o dilin hazır anlatıcısına döner."""
    ses = str(ayar.get("ses.voxcpm2_ses") or "")
    dil = str(ayar.get("genel.hedef_dil") or "")
    if ses == VOXCPM2_VARSAYILAN_SES and dil != "tr" and f"anlatici_{dil}" in kayit.VOXCPM2_HAZIR_SESLER:
        return f"hazir/anlatici_{dil}"
    return ses


def dubconfig_olustur(ayar: dict[str, Any], kaynak: str | None = None) -> tuple[Any, Cozum]:
    """Doğrulanmış ayardan (DubConfig, Cozum) üretir.

    `kaynak` verilirse kaynağa bağlı kurallar da denetlenir (youtube_translate yalnız YouTube bağlantısıyla).
    "auto" ve donanım kararlarının gerekçesi `Cozum.gerekceler`e ve günlüğe yazılır.
    """
    from dublaj_hatti.bolum_00_omurga.core.dubber import DubConfig
    from dublaj_hatti.bolum_00_omurga.runtime.donanim import cihaz_coz, cihaz_gerekcesi, hesap_tipi_coz
    from dublaj_hatti.bolum_40_ceviri.arka_uc_secimi import ceviri_secimi_coz

    gerekceler: list[str] = []

    def gerekce(metin: str) -> None:
        gerekceler.append(metin)
        logger.info("Seçim gerekçesi: %s", metin)

    _ortami_ayarla(ayar)
    if ayar["ses.motor"] == "auto":
        if ayar["genel.is_turu"] == "dublaj":
            secilen, neden = tts_auto_coz(ayar)
            gerekce(neden)
        else:
            secilen = "supertonic"
        ayar = {**ayar, "ses.motor": secilen}
        _uyumluluk_uygula(ayar)  # çözülen motorun saf denetimi (ör. Supertonic'in okuyamadığı hedef dil)
    for bulgu in uyumluluk_denetle(ayar):
        if bulgu.seviye == "uyari":
            logger.warning("Ayar uyarısı: %s", bulgu)
    cihaz = cihaz_coz(ayar["genel.cihaz"])
    gerekce(cihaz_gerekcesi(ayar["genel.cihaz"], cihaz))
    hesap_tipi = hesap_tipi_coz(ayar["transkripsiyon.hesap_tipi"], cihaz)
    stt, stt_modeli, hesap_tipi, whisperx_profili = stt_secimi_coz(ayar, cihaz, hesap_tipi)
    if ayar["transkripsiyon.motor"] == "auto":
        gerekce(stt_auto_gerekcesi(stt, cihaz))
    if stt == "faster_whisper_ctc":
        _ctc_modeli_denetle(ayar, gerekce)
    if stt in STT_YALNIZ_GPU and cihaz != "cuda":
        raise AyarHatasi(f"{stt} NVIDIA GPU ister, çalışan CUDA yok; transkripsiyon.motor=faster-whisper seçin")
    if ayar["genel.is_turu"] == "dublaj" and ayar["ses.motor"] in TTS_YALNIZ_GPU and cihaz != "cuda":
        raise AyarHatasi(f"ses.motor={ayar['ses.motor']} NVIDIA GPU ister, çalışan CUDA yok; işlemcide "
                         "ses.motor=supertonic seçin")
    _kurulum_denetle(ayar, kaynak, gerekce)
    konusmaci_ayrimi = bool(ayar["ileri.pyannote_konusmaci_ayrimi"]) and stt in STT_KONUSMACI_AYRIMI
    try:
        ceviri = ceviri_secimi_coz(ayar["ceviri.arka_uc"])
    except ValueError as hata:
        raise AyarHatasi(str(hata)) from hata
    dublaj_kipi = ayar["genel.dublaj_kipi"]
    dublaj = ayar["genel.is_turu"] == "dublaj"
    if dublaj and dublaj_kipi == "full_text" and ceviri["llm_backend"] not in ("codex", "claude_code"):
        raise AyarHatasi("full_text kipi yalnız Codex ya da Claude Code çeviri arka ucuyla çalışır "
                         "(ceviri.arka_uc=auto hiçbir CLI bulamadı ya da başka arka uç seçildi)")
    if dublaj and ceviri["translator_engine"] == "yerel" and ayar["genel.hedef_dil"] != "tr":
        raise AyarHatasi("çeviri yerel Opus-MT'ye düştü (Codex/Claude CLI yok) ama o yalnız Türkçeye çevirir; "
                         f"hedef_dil={ayar['genel.hedef_dil']} için bir LLM arka ucu kurun ya da seçin")
    kip = ayar["ses_temizligi.kip"]
    if kip in ("clean", "preserve_background") and importlib.util.find_spec("demucs") is None:
        raise AyarHatasi(f"ses_temizligi.kip={kip} Demucs ister ve kurulu değil: pip install .[separation] "
                         "(ya da kip=original)")
    voxcpm2 = ayar["ses.motor"] == "voxcpm2"
    voxcpm2_ses = voxcpm2_tek_ses(ayar)
    if voxcpm2 and voxcpm2_ses != ayar["ses.voxcpm2_ses"]:
        gerekce(f"VoxCPM2 tek ses: hedef dil {ayar['genel.hedef_dil']} için {voxcpm2_ses} (Türkçe varsayılan yerine)")
    tek_ses = voxcpm2_ses if voxcpm2 else ayar["ses.supertonic_ses"]
    konusmaci = ayar["ses.konusmaci_cinsiyetine_gore_ses"] and ayar["ses.motor"] in ("supertonic", "voxcpm2")
    segment_kipi = ayar["ses.cinsiyet_kipi"] == "segment"
    modeller_var = cinsiyet_modeli_kurulu() if segment_kipi else konusmaci_modelleri_kurulu()
    if konusmaci and not modeller_var:
        logger.warning("Konuşmacı/cinsiyet modelleri kurulu değil (scripts/kur.ps1 -Adim modeller); tek ses (%s) kullanılacak",
                       tek_ses)
        gerekce(f"cinsiyete göre ses kapalı: modeller kurulu değil; tek ses {tek_ses}")
        konusmaci = False
    kadin_sesleri: list[str] = []
    erkek_sesleri: list[str] = []
    if voxcpm2 and konusmaci:
        kadin_sesleri, erkek_sesleri, havuz_kaynagi = voxcpm2_havuzlari({**ayar, "ses.voxcpm2_ses": voxcpm2_ses})
        gerekce(f"VoxCPM2 cinsiyete göre ses ({havuz_kaynagi}): kadın {', '.join(kadin_sesleri)}; "
                f"erkek {', '.join(erkek_sesleri)}")
    cfg = DubConfig(
        model_name=stt_modeli,
        compute_type=hesap_tipi,
        device=cihaz,
        target_lang=ayar["genel.hedef_dil"],
        tts_retry_attempts=ayar["ileri.tts_deneme"],
        tts_retry_delay=ayar["ileri.tts_deneme_bekleme_sn"],
        use_demucs=kip in ("clean", "preserve_background"),
        preserve_background_audio=kip == "preserve_background",
        auto_background_preservation=kip == "auto_background",
        sample_rate=ayar["ileri.ornekleme_hizi"],
        tts_speed_factor=ayar["ses.hiz"],
        tts_engine=ayar["ses.motor"],
        tts_voice_id=ayar["ses.supertonic_ses"],
        voxcpm2_ses=voxcpm2_ses,
        voxcpm2_kadin_sesleri=kadin_sesleri,
        voxcpm2_erkek_sesleri=erkek_sesleri,
        voxcpm2_konusmaci_sesleri=dict(ayar["ses.konusmaci_sesleri"]) if ayar["ses.motor"] == "voxcpm2" else {},
        ema_cihaz=ayar["ses.ema_cihaz"],
        ema_hiz=ayar["ses.ema_hiz"],
        ema_tohum=ayar["ses.ema_tohum"],
        translator_engine=ceviri["translator_engine"],
        llm_backend=ceviri["llm_backend"],
        transcription_engine=stt,
        transcription_decoder_profile=whisperx_profili,
        crisper_language_detection_mode=ayar["transkripsiyon.crisper_dil_tespiti"],
        whisper_language=ayar["transkripsiyon.kaynak_dil"],
        whisper_vad_filter=ayar["transkripsiyon.vad"],
        cache_dir=ayar["genel.onbellek_klasoru"],
        use_diarization=konusmaci_ayrimi,
        supertonic_flow_mode=ayar["ses.akis"],
        supertonic_atempo_enabled=ayar["ses.atempo"] and dublaj_kipi == "segment_sync",
        konusmaci_basina_ses=konusmaci,
        supertonic_konusmaci_sesleri=dict(ayar["ses.konusmaci_sesleri"]) if ayar["ses.motor"] == "supertonic" else {},
        subtitle_mode=ayar["altyazi.mod"],
        dubbing_mode=dublaj_kipi,
        full_text_duration_fit_mode=ayar["video.tam_metin_sure_uyumu"],
        video_output_policy=ayar["video.politika"],
        video_encoder_cq=ayar["video.cq"],
        max_output_bytes=ayar["video.max_mb"] * MB if ayar["video.politika"] == "max_mb" else 0,
        ai_label=ayar["video.yapay_zeka_etiketi"],
        smart_frame_capture_enabled=bool(ayar["video.akilli_kare"]) and importlib.util.find_spec("cv2") is not None,
        cinsiyet_kipi=ayar["ses.cinsiyet_kipi"],
        supertonic_kadin_ses=ayar["ses.kadin_ses"],
        supertonic_erkek_ses=ayar["ses.erkek_ses"],
        xtts_referans_ses=str(ayar["ses.xtts_referans_ses"] or "") if ayar["ses.motor"] == "xtts" else "",
        rvc_model_yolu=str(ayar["ses.rvc_model"] or "").strip() if dublaj else "",
        rvc_index_yolu=str(ayar["ses.rvc_index"] or "").strip(),
        rvc_perde=int(ayar["ses.rvc_perde"]),
        rvc_riza_onayi=bool(ayar["ses.rvc_riza_onayi"]),
        gozden_gecir=bool(ayar["genel.gozden_gecir"]) and dublaj and dublaj_kipi == "segment_sync",
    )
    cozum = Cozum(cihaz, hesap_tipi, stt, ceviri["translator_engine"], ceviri["llm_backend"], ceviri["kaynak"],
                  gerekceler)
    return cfg, cozum
