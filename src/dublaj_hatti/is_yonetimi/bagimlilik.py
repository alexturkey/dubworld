"""Devamda seçim değiştirme → aşama bağımlılığı.

Bir iş devam ettirilirken ayar değiştirilirse, değişen ayarın girdi olarak ilk kullanıldığı aşama ve sonrası
yeniden çalışmalıdır; ondan önceki aşamalar korunur. Bu modül her ayar anahtarının hangi aşamayı etkilediğini
(dublaj kipine göre) tutar ve en erken etkiden önceki son aşamayı "koruma sınırı" olarak verir.

Son güvence checkpoint deposudur: bir aşamanın kayıtlı girdisi değişmişse `can_restore` o aşamayı ve sonrasını
zaten geçersiz kılar. Bu tablo yalnız kopyalama noktasını seçer (gereksiz iş kopyalamamak ve kullanıcıya
"şu aşamadan yeniden çalışacak" demek için). Tabloda olmayan yeni bir ayar en temkinli yolla, kaynak videodan
sonrası yeniden çalışacak şekilde ele alınır.
"""

from __future__ import annotations

from typing import Any

from dublaj_hatti.bolum_00_omurga.core.asama_sozlesmesi import get_graph_identity
from dublaj_hatti.is_yonetimi.asamalar import asamalar

# Sonucu değiştirmeyen (yalnız çalıştırma biçimi) ayarlar: değişince hiçbir aşama yeniden çalışmaz.
ETKISIZ = frozenset({
    "genel.cihaz", "genel.cikti_klasoru", "genel.onbellek_klasoru", "genel.gunluk_seviyesi",
    "ileri.tts_isci", "ileri.tts_deneme", "ileri.tts_deneme_bekleme_sn",
    "genel.transkript_bicimi",  # yalnız transkript işinin dosya biçimi; dublaj aşamalarına girmez
    "ses.xtts_lisans_onayi", "ses.rvc_riza_onayi",  # yalnız izin kapısı; çıktıyı değiştirmez
})
# Devamda değiştirilemeyen: işin türünü değiştirir (yeni iş açılmalı).
DEGISTIRILEMEZ = frozenset({"genel.is_turu"})

_TRANSKRIPSIYON = ("transkripsiyon.model", "transkripsiyon.hesap_tipi", "transkripsiyon.kaynak_dil",
                   "transkripsiyon.vad", "transkripsiyon.crisper_dil_tespiti", "transkripsiyon.whisperx_profili",
                   "ileri.pyannote_konusmaci_ayrimi")
ETKI: dict[str, dict[str, str]] = {
    "segment_sync": {
        **dict.fromkeys(_TRANSKRIPSIYON, "transkripsiyon"),
        "transkripsiyon.motor": "asr_sesi_hazirlama",
        "genel.hedef_dil": "ceviri",
        "ceviri.*": "ceviri",
        "ses.motor": "konusmaci_yonlendirme",
        "ses.konusmaci_cinsiyetine_gore_ses": "konusmaci_yonlendirme",
        "ses.cinsiyet_kipi": "konusmaci_yonlendirme",
        "ses.kadin_ses": "konusmaci_yonlendirme",
        "ses.erkek_ses": "konusmaci_yonlendirme",
        "ses.xtts_referans_ses": "ses_yonlendirme",
        "ses.rvc_model": "tts_ve_segment_sesleri",
        "ses.rvc_index": "tts_ve_segment_sesleri",
        "ses.rvc_perde": "tts_ve_segment_sesleri",
        "video.akilli_kare": "video_timeline_ve_final_mux",
        "ses.konusmaci_sesleri": "konusmaci_yonlendirme",
        "ses.supertonic_ses": "ceviri",  # çeviri stratejisi ses kimliğini içerir
        "ses.hiz": "ceviri",
        "ses.akis": "ceviri",
        "ses.voxcpm2_ses": "ses_yonlendirme",
        "ses.atempo": "tts_ve_segment_sesleri",
        "ileri.ornekleme_hizi": "tts_ve_segment_sesleri",
        "altyazi.mod": "altyazi_hazirlama",
        "video.politika": "video_timeline_ve_final_mux",
        "video.cq": "video_timeline_ve_final_mux",
        "video.max_mb": "video_timeline_ve_final_mux",
        "video.tam_metin_sure_uyumu": "",  # bu kipte kullanılmaz
        "video.yapay_zeka_etiketi": "final_dogrulama_ve_meta",
    },
    "full_text": {
        **dict.fromkeys(_TRANSKRIPSIYON, "transkripsiyon"),
        "transkripsiyon.motor": "asr_sesi_hazirlama",
        "genel.hedef_dil": "full_text_ceviri",
        "ceviri.*": "full_text_ceviri",
        "ses.motor": "full_text_tek_ses_tts",
        "ses.konusmaci_cinsiyetine_gore_ses": "full_text_tek_ses_tts",
        "ses.cinsiyet_kipi": "full_text_tek_ses_tts",
        "ses.kadin_ses": "full_text_tek_ses_tts",
        "ses.erkek_ses": "full_text_tek_ses_tts",
        "ses.xtts_referans_ses": "full_text_tek_ses_tts",
        "ses.rvc_model": "full_text_tek_ses_tts",
        "ses.rvc_index": "full_text_tek_ses_tts",
        "ses.rvc_perde": "full_text_tek_ses_tts",
        "video.akilli_kare": "full_text_video_sure_uyumu_ve_final_mux",
        "ses.konusmaci_sesleri": "full_text_tek_ses_tts",
        "ses.supertonic_ses": "full_text_tek_ses_tts",
        "ses.hiz": "full_text_tek_ses_tts",
        "ses.akis": "full_text_tek_ses_tts",
        "ses.voxcpm2_ses": "full_text_tek_ses_tts",
        "ses.atempo": "full_text_tek_ses_tts",
        "ileri.ornekleme_hizi": "full_text_tek_ses_tts",
        "video.tam_metin_sure_uyumu": "full_text_tek_ses_tts",
        "altyazi.mod": "full_text_final_altyazi_alignment",
        "video.politika": "full_text_video_sure_uyumu_ve_final_mux",
        "video.cq": "full_text_video_sure_uyumu_ve_final_mux",
        "video.max_mb": "full_text_video_sure_uyumu_ve_final_mux",
        "video.yapay_zeka_etiketi": "final_dogrulama_ve_meta",
    },
}
BILINMEYEN_ETKI = "kaynak_ses_cikarma"  # tabloda olmayan ayar: kaynak video korunur, gerisi yeniden


def _demucs_acik(ayar: dict[str, Any]) -> bool:
    return str(ayar.get("ses_temizligi.kip") or "original") != "original"


def etki_asamasi(anahtar: str, eski: dict[str, Any], yeni: dict[str, Any], kip: str) -> str:
    """Ayar değişikliğinin ilk etkilediği aşama; "" = hiçbir aşama."""
    if anahtar in ETKISIZ:
        return ""
    if anahtar == "ses_temizligi.kip":
        if _demucs_acik(eski) != _demucs_acik(yeni):
            return "kaynak_ses_cikarma"  # örnekleme hızı ve kanal sayısı değişir
        return "arka_plan_miksi" if _demucs_acik(yeni) else ""
    if anahtar == "transkripsiyon.motor" and _demucs_acik(yeni):
        if (eski.get(anahtar) == "whisperx") != (yeni.get(anahtar) == "whisperx"):
            return "demucs_vokal_ayirma"  # ASR'ye hazır vokal hazırlığı motor sınıfına bağlı
    tablo = ETKI.get(kip, ETKI["segment_sync"])
    if anahtar in tablo:
        return tablo[anahtar]
    if anahtar.startswith("ceviri."):
        return tablo["ceviri.*"]
    return BILINMEYEN_ETKI


def _onceki_sira(kip: str, asama_id: str) -> int:
    liste = asamalar(kip)
    sira = next(int(o) for a, o, _ in liste if a == asama_id)
    onceki = [int(o) for _, o, _ in liste if int(o) < sira]
    return max(onceki) if onceki else 0


def _ortak_sinir(kaynak_kip: str, hedef_kip: str) -> int:
    """İki kipin baştan itibaren ortak aşamalarının son sırası."""
    sinir = 0
    for (a1, o1, c1), (a2, o2, c2) in zip(asamalar(kaynak_kip), asamalar(hedef_kip), strict=False):
        if (a1, o1, c1) != (a2, o2, c2):
            break
        sinir = int(o1)
    return sinir


def devam_bagimliligi(eski: dict[str, Any], degisiklikler: dict[str, Any], istenen_sira: int) -> dict[str, Any]:
    """Değişen ayarlara göre etkin koruma sınırı.

    `eski`: kaynak işin etkin ayarları (düz sözlük). `degisiklikler`: yalnız değişen anahtarlar (doğrulanmış).
    `istenen_sira`: kullanıcının istediği (ya da son geçerli) checkpoint sırası.
    Dönen `effective_stage_order` ≤ istenen; bu sıraya kadar olan aşamalar korunur.
    """
    yeni = {**eski, **degisiklikler}
    kaynak_kip = str(eski.get("genel.dublaj_kipi") or "segment_sync")
    hedef_kip = str(yeni.get("genel.dublaj_kipi") or kaynak_kip)
    degisenler = []
    sinirlar = [int(istenen_sira)]
    if hedef_kip != kaynak_kip:
        sinir = _ortak_sinir(kaynak_kip, hedef_kip)
        sinirlar.append(sinir)
        degisenler.append({"field": "genel.dublaj_kipi", "old": kaynak_kip, "new": hedef_kip,
                           "direct_stage": None, "preserve_order": sinir})
    for anahtar in sorted(degisiklikler):
        if anahtar == "genel.dublaj_kipi" or eski.get(anahtar) == yeni.get(anahtar):
            continue
        if anahtar in DEGISTIRILEMEZ:
            raise ValueError(f"{anahtar} devamda değiştirilemez; yeni iş açın")
        asama = etki_asamasi(anahtar, eski, yeni, hedef_kip)
        if asama and not any(a == asama for a, _, _ in asamalar(hedef_kip)):
            asama = ""  # bu kipte o aşama yok (ör. segment kipinde tam metin süre uyumu)
        koruma = _onceki_sira(hedef_kip, asama) if asama else None
        if koruma is not None:
            sinirlar.append(koruma)
        degisenler.append({
            "field": anahtar, "old": eski.get(anahtar), "new": yeni.get(anahtar),
            "direct_stage": ({"stage_id": asama, "stage_order": next(int(o) for a, o, _ in asamalar(hedef_kip)
                                                                     if a == asama)} if asama else None),
            "preserve_order": koruma,
        })
    kimlik = get_graph_identity()
    return {
        "requested_stage_order": int(istenen_sira),
        "effective_stage_order": min(sinirlar),
        "source_pipeline_kind": kaynak_kip,
        "target_pipeline_kind": hedef_kip,
        "changed_fields": degisenler,
        "graph_version": kimlik["graph_version"],
        "graph_hash": kimlik["graph_hash"],
    }
