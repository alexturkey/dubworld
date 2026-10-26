"""Arayüzün "Motorlar" seçicisinin verisi (`GET /api/motorlar`): yazıya dökme ve seslendirme motorlarının bilgi satırı
(lisans, donanım, diller, güçlü yan: `kayit.motor_bilgisi`), bu bilgisayardaki durumu (kurulu mu, NVIDIA görünüyor mu) ve
"auto"nun burada neyi seçeceği. "auto" kuralları `yapilandirma.tts_auto_karar` / `stt_auto_karar` ile iş başlarken
kullanılanlarla aynıdır; fark: burada GPU denetimi torch yüklemeden `nvidia-smi` ile yapılır (web sürecinde CUDA açılmaz).

Gelişmiş motor ayarları: motor seçimine bağlı, çoğu kişinin dokunmayacağı anahtarlar; arayüz bunları katlı bir bölümde tutar.
"""

from __future__ import annotations

from typing import Any, Callable

from dublaj_hatti import kayit, yapilandirma

STT_ANAHTAR = "transkripsiyon.motor"
TTS_ANAHTAR = "ses.motor"
# Gelişmiş bölüme giden ayarlar: tam anahtar ya da önek ("ses.ema_" ...). Gerçek adlar varsayilan.toml'dadır; test denetler.
GELISMIS_TAM = ("transkripsiyon.model", "transkripsiyon.hesap_tipi", "transkripsiyon.crisper_dil_tespiti",
                "transkripsiyon.whisperx_profili")
GELISMIS_ONEKLER = ("ses.ema_", "ses.xtts_", "ses.rvc_", "ileri.")


def gelismis_motor_anahtarlari() -> list[str]:
    """Şemadaki gelişmiş motor ayarları (SEMA sırası)."""
    return [a for a in yapilandirma.SEMA if a in GELISMIS_TAM or a.startswith(GELISMIS_ONEKLER)]


def _satir(ad: str, gpu: bool, kurulu: bool) -> dict[str, Any]:
    bilgi = kayit.motor_bilgisi(ad)
    engel = "kurulu_degil" if not kurulu else ("gpu_yok" if bilgi["gpu_only"] and not gpu else "")
    return {**bilgi, "installed": kurulu, "selectable": not engel, "blocked_by": engel}


def motor_secici_verisi(ayar: dict[str, Any] | None = None, gpu: bool | None = None, vram_mb: int | None = None,
                        kurulu: Callable[[str], dict[str, bool]] | None = None) -> dict[str, Any]:
    """Seçici verisi. `gpu`/`vram_mb`/`kurulu` testte verilir; yoksa hafif denetimle bulunur."""
    ayar = ayar if ayar is not None else yapilandirma.ayarlari_yukle()
    if gpu is None:
        from dublaj_hatti.bolum_00_omurga.runtime.donanim import gpu_bilgisi_hafif

        gpu, vram_mb = gpu_bilgisi_hafif()
    kurulu = kurulu or kayit.durum
    stt_durum, tts_durum = kurulu("stt"), kurulu("tts")
    stt = [_satir(m.ad, gpu, bool(stt_durum.get(m.ad))) for m in kayit.motorlar("stt")]
    tts = [_satir(m.ad, gpu, bool(tts_durum.get(m.ad))) for m in kayit.motorlar("tts")]
    stt_secilen, stt_kod = yapilandirma.stt_auto_karar(gpu, gpu and bool(stt_durum.get("crisperwhisper_turbo_ct2")))
    tts_secilen, tts_kod = yapilandirma.tts_auto_karar(
        ayar.get("genel.dublaj_kipi") == "full_text", gpu, gpu and bool(tts_durum.get("voxcpm2")))
    return {
        "gpu": bool(gpu), "vram_mb": int(vram_mb or 0),
        "stt": {"key": STT_ANAHTAR, "engines": stt, "auto": {"engine": stt_secilen, "reason": stt_kod,
                                                                      "installed": bool(stt_durum.get(stt_secilen))}},
        "tts": {"key": TTS_ANAHTAR, "engines": tts, "auto": {"engine": tts_secilen, "reason": tts_kod,
                                                                      "installed": bool(tts_durum.get(tts_secilen))}},
        "advanced_keys": gelismis_motor_anahtarlari(),
    }
