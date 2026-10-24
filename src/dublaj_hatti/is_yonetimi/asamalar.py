"""Aşama adları ve aşama seçimi (komut satırı / arayüz için insan okunur adlar)."""

from __future__ import annotations

from dublaj_hatti.bolum_00_omurga.core.asama_sozlesmesi import PIPELINE_STAGES

ASAMA_ADLARI = {
    "video_indirme_veya_kopyalama": "Kaynak video",
    "kaynak_ses_cikarma": "Ses çıkarma",
    "demucs_vokal_ayirma": "Ses ayrıştırma",
    "asr_sesi_hazirlama": "Ses hazırlama",
    "transkripsiyon": "Transkripsiyon",
    "forced_alignment_ve_nihai_segmentler": "Kelime zamanı ve cümleler",
    "konusmaci_yonlendirme": "Konuşmacı ayrımı",
    "ceviri": "Çeviri",
    "ses_yonlendirme": "Ses seçimi",
    "tts_ve_segment_sesleri": "Seslendirme",
    "altyazi_hazirlama": "Altyazı",
    "video_timeline_ve_final_mux": "Video birleştirme",
    "arka_plan_miksi": "Arka plan miksi",
    "final_altyazi_yakma": "Altyazı yakma",
    "final_dogrulama_ve_meta": "Son denetim",
    "full_text_konusma_penceresi": "Konuşma penceresi",
    "full_text_ceviri": "Tam metin çevirisi",
    "full_text_tek_ses_tts": "Tam metin seslendirme",
    "full_text_final_altyazi_alignment": "Altyazı zamanı",
    "full_text_video_sure_uyumu_ve_final_mux": "Süre uyumu ve birleştirme",
}


def asama_adi(asama_id: str) -> str:
    return ASAMA_ADLARI.get(asama_id, asama_id)


def asamalar(kip: str) -> tuple[tuple[str, int, int], ...]:
    return PIPELINE_STAGES.get(kip or "segment_sync", PIPELINE_STAGES["segment_sync"])


def asama_coz(kip: str, deger: str | int) -> tuple[str, int]:
    """Aşama kimliği, insan okunur adı ya da sıra numarası → (kimlik, sıra). Bulunamazsa ValueError."""
    liste = asamalar(kip)
    metin = str(deger).strip()
    for asama_id, sira, _ in liste:
        if metin in (asama_id, str(sira)) or metin.casefold() == asama_adi(asama_id).casefold():
            return asama_id, sira
    secenekler = ", ".join(f"{a} ({asama_adi(a)})" for a, _, _ in liste)
    raise ValueError(f"bilinmeyen aşama: {deger!r}; seçenekler: {secenekler}")
