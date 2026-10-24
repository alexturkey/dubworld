"""Bir iş kaydını bu süreçte çalıştırır (komut satırı ve arayüzlerin alt süreci aynı yolu kullanır).

Sıra: (devam işiyse) checkpoint kopyası hazırlanır → iş sahiplenilir → makine geneli kaynak kilidi beklenir
(GPU ya da ağır CPU; başka bir program/araç kullanıyorsa sıra beklenir) → hat çalışır → sonuç iş kaydına yazılır.
Her checkpoint olayı hem iş kaydına işlenir hem `olay_yaz` ile dışarı verilir (`--olaylar-json`).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dublaj_hatti.is_yonetimi.depo import IsDeposu, IsHatasi, _json, varsayilan_depo_yolu

logger = logging.getLogger("dublaj_hatti")
KILIT_BEKLEME_SN = float(os.environ.get("DUBLAJ_KILIT_BEKLEME_SN", "21600"))  # 6 saat
CIKIS_KAYNAK_MESGUL = 75


def cikti_koku(ayar: dict[str, Any] | None = None) -> Path:
    from dublaj_hatti.bolum_00_omurga.runtime.output_paths import configured_output_root

    if ayar and ayar.get("genel.cikti_klasoru"):
        return Path(str(ayar["genel.cikti_klasoru"])).expanduser().resolve()
    return configured_output_root().expanduser().resolve()


def depo_ac(ayar: dict[str, Any] | None = None) -> IsDeposu:
    kok = cikti_koku(ayar)
    return IsDeposu(varsayilan_depo_yolu(kok), kok)


def is_ayari(is_kaydi: dict[str, Any]) -> dict[str, Any]:
    """İş kaydındaki etkin ayarı bugünkü şemaya göre doğrular (eksik yeni anahtarlar varsayılandan gelir)."""
    from dublaj_hatti import yapilandirma as y

    ayar = {**y.ayarlari_yukle(), **_json(is_kaydi.get("settings_json"))}
    dogru = {k: y._deger_dogrula(k, v) for k, v in ayar.items() if k in y.SEMA}
    y._uyumluluk_uygula(dogru)
    return dogru


def isi_calistir(depo: IsDeposu, job_id: int, olay_yaz: Callable[[dict[str, Any]], None],
                 kilit_bekle_sn: float | None = None) -> int:
    """Çıkış kodu: 0 bitti, 1 iş hatası, 2 kullanım hatası, 75 kaynak meşgul (iş ertelendi), 130 durduruldu."""
    is_kaydi = depo.getir(job_id)
    if not is_kaydi:
        olay_yaz({"event": "hata", "mesaj": f"iş bulunamadı: #{job_id}"})
        return 2
    if is_kaydi["source_job_id"] and not is_kaydi["run_dir"]:
        if not depo.hazirlik_sahiplen(job_id):
            olay_yaz({"event": "hata", "mesaj": f"iş #{job_id} hazırlık için alınamadı (durum: {is_kaydi['status']})"})
            return 2
        olay_yaz({"event": "devam_hazirlaniyor", "is": job_id, "kaynak_is": is_kaydi["source_job_id"],
                  "asama": is_kaydi["resume_after_stage"]})
        try:
            kopya = depo.devam_hazirla(job_id)
        except (IsHatasi, OSError) as hata:
            depo.hazirlik_basarisiz(job_id, str(hata))
            olay_yaz({"event": "hata", "mesaj": f"devam hazırlanamadı: {hata}"})
            return 1
        olay_yaz({"event": "devam_hazir", "is": job_id, "run_dir": str(kopya)})
        beklenen: tuple[str, ...] = ("preparing",)
    else:
        beklenen = ("queued", "deferred")
    if not depo.sahiplen(job_id, beklenen=beklenen):
        guncel = depo.getir(job_id) or {}
        olay_yaz({"event": "hata", "mesaj": f"iş #{job_id} çalıştırılamadı (durum: {guncel.get('status')})"})
        return 2
    is_kaydi = depo.getir(job_id) or is_kaydi
    try:
        return _hatti_kos(depo, is_kaydi, olay_yaz, KILIT_BEKLEME_SN if kilit_bekle_sn is None else kilit_bekle_sn)
    except KeyboardInterrupt:
        depo.bitir(job_id, "cancelled", "Kullanıcı durdurdu")
        olay_yaz({"event": "durduruldu", "is": job_id})
        return 130
    except Exception as hata:  # beklenmeyen hata: iş "işleniyor"da asılı kalmasın, hemen devam ettirilebilsin
        depo.bitir(job_id, "failed", f"beklenmeyen hata: {type(hata).__name__}: {hata}")
        olay_yaz({"event": "hata", "is": job_id, "mesaj": f"beklenmeyen hata: {hata}"})
        raise


def _hatti_kos(depo: IsDeposu, is_kaydi: dict[str, Any], olay_yaz: Callable[[dict[str, Any]], None],
               kilit_bekle_sn: float) -> int:
    from dublaj_hatti.bolum_00_omurga.runtime.kaynak_kilidi import KaynakMesgulError, kaynak_kullan
    from dublaj_hatti.yapilandirma import AyarHatasi, dubconfig_olustur

    job_id = int(is_kaydi["job_id"])
    try:
        ayar = is_ayari(is_kaydi)
        cfg, cozum = dubconfig_olustur(ayar, kaynak=str(is_kaydi["source"] or ""))
    except (AyarHatasi, ValueError) as hata:
        depo.bitir(job_id, "failed", f"ayar hatası: {hata}")
        olay_yaz({"event": "hata", "mesaj": f"ayar hatası: {hata}"})
        return 2
    # Son savunma (tek kapı, lisans_onayi.kapi_adlar): CLI / GUI / web işi eklerken sorar; kuyruk, devam ve arayüz alt
    # süreci buradan geçer. Onay yoksa iş çalışmaz; soru sorulmaz (alt süreçte girdi yok), açık hatayla durur.
    from dublaj_hatti.lisans_onayi import LisansOnayiGerekli, kapi

    try:
        # transkript işi ses motoru çalıştırmaz: yalnız gerçekten kullanılan motorlar sorulur
        kapi({**ayar, "genel.is_turu": "transkript"} if is_kaydi["command"] == "transkript" else ayar, cozum.stt_motoru)
    except LisansOnayiGerekli as gerek:
        mesaj = (f"{gerek}. Kabul ediyorsanız: dubla devam {job_id} --lisans-onay (ya da arayüzde yeniden başlatın) "
                 f"/ to accept: dubla devam {job_id} --lisans-onay")
        depo.bitir(job_id, "failed", mesaj)
        olay_yaz({"event": "hata", "mesaj": mesaj, "lisans_onayi": [ad for ad, _ in gerek.bekleyen]})
        return 2
    olay_yaz({"event": "basladi", "is": job_id, "komut": is_kaydi["command"], "kaynak": is_kaydi["source"],
              "secimler": vars(cozum)})

    def olay(e: dict[str, Any]) -> None:
        if "run_dir" in e and "status" in e:
            depo.boru_olayi(job_id, e)
        olay_yaz({**e, "is": job_id})

    def bekleme_bildir(kaynak: str, kullananlar: list[dict[str, Any]]) -> None:
        olay_yaz({"event": "kaynak_bekleniyor", "is": job_id, "kaynak": kaynak,
                  "kullananlar": [str(k.get("aciklama", "")) for k in kullananlar]})

    from dublaj_hatti.bolum_00_omurga.core import dubber

    kaynak_turu = "gpu" if cozum.cihaz == "cuda" else "cpu_agir"
    istek: dict[str, Any] = {"source": is_kaydi["request_origin"], "launch_method": "dubla",
                             "pipeline_event_callback": olay, "job_id": job_id}
    run_dir = str(is_kaydi["run_dir"] or "")
    if run_dir and (Path(run_dir) / "pipeline_state.json").is_file():
        istek["resume_run_dir"] = run_dir
    try:
        with kaynak_kullan([kaynak_turu], f"uygulama:is-{job_id}", f"{is_kaydi['command']} #{job_id}",
                           bekle_saniye=kilit_bekle_sn, bekleme_bildir=bekleme_bildir):
            if is_kaydi["command"] == "transkript":
                sonuc = dubber.transcript_only_pipeline(is_kaydi["source"], str(depo.cikti_koku),
                                                        is_kaydi["transcript_format"] or "srt", cfg, istek)
            else:
                sonuc = dubber.full_dub_pipeline(is_kaydi["source"], str(depo.cikti_koku), cfg, istek)
    except KaynakMesgulError as hata:
        depo.ertele(job_id, 60, str(hata), "kaynak_mesgul")
        olay_yaz({"event": "hata", "mesaj": f"{hata}; iş ertelendi"})
        return CIKIS_KAYNAK_MESGUL
    except KeyboardInterrupt:
        raise
    except Exception as hata:  # hattın kendi hata türleri günlükte ayrıntılı
        logger.exception("iş #%s başarısız", job_id)
        depo.bitir(job_id, "failed", str(hata)[:2000])
        olay_yaz({"event": "hata", "is": job_id, "mesaj": str(hata)[:2000]})
        return 1
    ozet = {k: sonuc.get(k) for k in ("run_dir", "dubbed_video", "output_video", "transcript_path", "srt_path")
            if isinstance(sonuc, dict) and sonuc.get(k)}
    depo.bitir(job_id, "completed", None, ozet)
    olay_yaz({"event": "bitti", "is": job_id, **ozet})
    return 0
