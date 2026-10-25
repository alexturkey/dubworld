"""Seslendirmeden önce gözden geçirme (`genel.gozden_gecir`): çeviri satırlarını okuma, düzeltme ve tek satır çevirme.

İş çeviriden sonra `inceleme_bekliyor` durumunda durur (hata değil). Satırlar işin çeviri aşaması çıktısındadır
(`pipeline_translation_result.json`; aşama `ceviri`, yükü `result_path`): her segmentte `text` = çeviri,
`original_source_text` = kaynak metin, `start`/`end` = zaman. Düzeltme bu dosyaya yazılır; kayıtlı özeti
`pipeline_checkpoint.ciktiyi_guncelle` yeniler, böylece `can_restore("ceviri")` doğrulamayı gevşetmeden geçer ve
devamda seslendirme düzeltilmiş metni okur (çeviri ve öncesi yeniden çalışmaz).

Kaynak metin düzeltmesi çeviriyi yeniden tetiklemez: çeviri aşamasının girdi özeti (`source_segments_hash`) çeviriden
ÖNCEKİ aşamanın çıktısından hesaplanır, bu dosyadan değil; `original_source_text` yalnız iki dilli döküm
(`translated_segments_<dil>.txt`) ve kayıt içindir.

Güvenlik: iş klasörü iş deposundaki kayıttan gelir, çıktı kökünün içinde olmalıdır; sonuç dosyası bu klasörün içinde
çözülmelidir (yol kaçışı yok). İstek verisinde dosya yolu yoktur.
"""

from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path
from typing import Any

from dublaj_hatti.bolum_00_omurga.core.pipeline_checkpoint import PipelineCheckpointError, ciktiyi_guncelle
from dublaj_hatti.is_yonetimi.depo import INCELEME, IsDeposu, _json

METIN_SINIRI = 2000
ASAMA = "ceviri"
_KILIT = threading.Lock()  # aynı anda tek kaydetme (web sunucusu çok iş parçacıklı)


class InceleHatasi(Exception):
    """Kullanıcıya gösterilecek hata: `anahtar` arayüzün çevirebileceği kısa kod, `kod` HTTP durumu."""

    def __init__(self, anahtar: str, mesaj: str, kod: int = 400) -> None:
        super().__init__(mesaj)
        self.anahtar = anahtar
        self.kod = kod


def _is_ve_klasor(depo: IsDeposu, job_id: int) -> tuple[dict[str, Any], Path]:
    try:
        no = int(job_id)
    except (TypeError, ValueError):
        raise InceleHatasi("is_gecersiz", "iş numarası sayı olmalı") from None
    kayit = depo.getir(no)
    if not kayit or kayit["command"] != "dubla":
        raise InceleHatasi("is_yok", f"dublaj işi bulunamadı: #{no}", 404)
    klasor = depo._klasor_kok_icinde(str(kayit["run_dir"] or ""))
    if klasor is None or not (klasor / "pipeline_state.json").is_file():
        raise InceleHatasi("klasor_yok", f"iş #{no} için çıktı klasörü yok ya da çıktı kökü dışında", 404)
    return kayit, klasor


def _sonuc_dosyasi(klasor: Path, asama: str = ASAMA) -> Path:
    """Aşamanın kayıtlı sonuç dosyası; iş klasörünün dışına çıkamaz."""
    try:
        durum = json.loads((klasor / "pipeline_state.json").read_text(encoding="utf-8"))
        kayit = durum["stages"][asama]
        if kayit.get("status") != "completed":
            raise KeyError(asama)
        yol = (klasor / str(kayit["payload"]["result_path"])).resolve()
        yol.relative_to(klasor.resolve())
    except (OSError, ValueError, KeyError, TypeError):
        raise InceleHatasi("ceviri_yok", "çeviri henüz tamamlanmadı ya da kaydı bozuk", 409) from None
    if not yol.is_file():
        raise InceleHatasi("ceviri_yok", "çeviri sonuç dosyası bulunamadı", 409)
    return yol


def _yukle(yol: Path) -> dict[str, Any]:
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
        if not isinstance(veri.get("segments"), list):
            raise ValueError("segments")
        return veri
    except (OSError, ValueError, AttributeError):
        raise InceleHatasi("ceviri_bozuk", "çeviri sonuç dosyası okunamadı", 409) from None


def _no(segment: dict[str, Any], sira: int) -> int:
    try:
        return int(segment.get("index"))
    except (TypeError, ValueError):
        return sira + 1


def _kaynak_metinleri(klasor: Path) -> dict[int, str]:
    """Çeviri dosyasında kaynak metin yoksa (eski kayıt) çeviriden önceki aşamanın çıktısından."""
    try:
        yol = _sonuc_dosyasi(klasor, "konusmaci_yonlendirme")
        return {_no(s, i): str(s.get("text") or "") for i, s in enumerate(_yukle(yol)["segments"])}
    except InceleHatasi:
        return {}


def satirlari_oku(depo: IsDeposu, job_id: int) -> dict[str, Any]:
    kayit, klasor = _is_ve_klasor(depo, job_id)
    veri = _yukle(_sonuc_dosyasi(klasor))
    yedek = None
    satirlar = []
    for i, s in enumerate(veri["segments"]):
        no = _no(s, i)
        orijinal = str(s.get("original_source_text") or "")
        if not orijinal:
            yedek = _kaynak_metinleri(klasor) if yedek is None else yedek
            orijinal = yedek.get(no, "")
        bas, son = float(s.get("start") or 0.0), float(s.get("end") or 0.0)
        satirlar.append({"no": no, "bas": round(bas, 3), "son": round(son, 3), "orijinal": orijinal,
                         "ceviri": str(s.get("text") or ""), "sure_sn": round(max(0.0, son - bas), 3)})
    hedef = str(_json(kayit["settings_json"]).get("genel.hedef_dil") or "")
    return {"is": int(kayit["job_id"]), "durum": kayit["status"], "satirlar": satirlar,
            "dil": {"kaynak": str(veri.get("source_lang") or ""), "hedef": hedef}}


def _metin(deger: Any, alan: str, no: int) -> str:
    if not isinstance(deger, str):
        raise InceleHatasi("metin_gecersiz", f"satır {no}: {alan} metin olmalı")
    temiz = " ".join(deger.replace("\x00", "").split())  # satır sonları ve art arda boşluklar tek boşluk
    if not temiz:
        raise InceleHatasi("metin_bos", f"satır {no}: {alan} boş olamaz")
    if len(temiz) > METIN_SINIRI:
        raise InceleHatasi("metin_uzun", f"satır {no}: {alan} en çok {METIN_SINIRI} karakter olabilir")
    return temiz


def satirlari_kaydet(depo: IsDeposu, job_id: int, satirlar: Any) -> dict[str, Any]:
    """`[{no, orijinal?, ceviri?}]`: hepsi geçerliyse yazılır (ya hepsi ya hiçbiri). Dönen: {"tamam", "degisen"}."""
    if not isinstance(satirlar, list) or not satirlar:
        raise InceleHatasi("satirlar_bos", "satirlar dolu bir liste olmalı")
    with _KILIT:
        kayit, klasor = _is_ve_klasor(depo, job_id)
        if kayit["status"] != INCELEME:
            raise InceleHatasi("is_inceleme_degil", f"iş #{kayit['job_id']} gözden geçirme beklemiyor "
                               f"(durum: {kayit['status']}); yalnız beklerken düzenlenir", 409)
        if depo.aktif_devam_var(int(kayit["job_id"])):
            raise InceleHatasi("devam_kuyrukta", "bu işten başlatılmış bir devam var; düzenlenemez", 409)
        yol = _sonuc_dosyasi(klasor)
        veri = _yukle(yol)
        dizin = {_no(s, i): s for i, s in enumerate(veri["segments"])}
        gorulen: set[int] = set()
        degisecek: list[tuple[dict[str, Any], str, str]] = []
        for oge in satirlar:
            if not isinstance(oge, dict):
                raise InceleHatasi("satir_gecersiz", "her satır bir nesne olmalı")
            try:
                no = int(oge["no"])
            except (KeyError, TypeError, ValueError):
                raise InceleHatasi("satir_gecersiz", "her satırda sayı olan bir no olmalı") from None
            if no not in dizin:
                raise InceleHatasi("satir_yok", f"satır {no} bu işte yok", 404)
            if no in gorulen:
                raise InceleHatasi("satir_tekrar", f"satır {no} birden çok kez verildi")
            gorulen.add(no)
            if "ceviri" not in oge and "orijinal" not in oge:
                raise InceleHatasi("satir_gecersiz", f"satır {no}: ceviri ya da orijinal verilmeli")
            if "ceviri" in oge:
                degisecek.append((dizin[no], "text", _metin(oge["ceviri"], "ceviri", no)))
            if "orijinal" in oge:
                degisecek.append((dizin[no], "original_source_text", _metin(oge["orijinal"], "orijinal", no)))
        degisen = 0
        for segment, alan, metin in degisecek:
            if segment.get(alan) != metin:
                segment[alan] = metin
                degisen += 1
        if degisen:
            icerik = json.dumps(veri, ensure_ascii=False, indent=2).encode("utf-8")  # hattın yazdığı biçim
            try:
                ciktiyi_guncelle(klasor, ASAMA, yol, icerik)
            except PipelineCheckpointError as hata:
                raise InceleHatasi("kayit_basarisiz", f"düzeltme kaydedilemedi: {hata}", 409) from hata
        return {"tamam": True, "degisen": degisen}


def satiri_cevir(depo: IsDeposu, job_id: int, no: Any, metin: Any) -> dict[str, Any]:
    """Tek satırı işin çeviri arka ucuyla çevirir (KAYDETMEZ; istemci /api/duzenle ile kaydeder)."""
    kayit, klasor = _is_ve_klasor(depo, job_id)
    veri = _yukle(_sonuc_dosyasi(klasor))
    try:
        no = int(no)
    except (TypeError, ValueError):
        raise InceleHatasi("satir_gecersiz", "no sayı olmalı") from None
    segment = next((s for i, s in enumerate(veri["segments"]) if _no(s, i) == no), None)
    if segment is None:
        raise InceleHatasi("satir_yok", f"satır {no} bu işte yok", 404)
    metin = _metin(metin, "metin", no)
    kaynak_dil = str(veri.get("source_lang") or "")
    ceviri = _cevirmen_calistir(kayit, segment, metin, kaynak_dil, klasor)
    return {"ceviri": ceviri}


def _cevirmen_calistir(kayit: dict[str, Any], segment: dict[str, Any], metin: str, kaynak_dil: str,
                       klasor: Path) -> str:
    from dublaj_hatti.is_yonetimi.calistirici import is_ayari
    from dublaj_hatti.yapilandirma import AyarHatasi, dubconfig_olustur

    try:
        cfg, _cozum = dubconfig_olustur(is_ayari(kayit), kaynak=str(kayit["source"] or ""))
    except (AyarHatasi, ValueError) as hata:
        raise InceleHatasi("ayar_hatasi", f"işin ayarı çalıştırılamadı: {hata}", 409) from hata
    if cfg.translator_engine not in ("yerel", "codex_bridge"):
        raise InceleHatasi("tek_satir_desteklenmiyor",
                           f"{cfg.translator_engine} çeviri arka ucu tek satır çevirmeyi desteklemiyor", 409)
    if cfg.translator_engine == "yerel":
        cfg.device = "cpu"  # web süreci GPU kilidi almaz; tek cümle için işlemci yeter
    from dublaj_hatti.bolum_00_omurga.core.dubber import _create_segment_translator
    from dublaj_hatti.bolum_30_hizalama_ve_segment.nihai_dublaj_segmentleri import NihaiDublajSegmenti

    parca = NihaiDublajSegmenti(index=int(segment.get("index") or 1), start=float(segment.get("start") or 0.0),
                                end=float(segment.get("end") or 0.0), text=metin, speaker=str(segment.get("speaker") or ""))
    try:
        with tempfile.TemporaryDirectory(prefix=".cevir_satir_", dir=str(klasor)) as gecici:
            cevirmen = _create_segment_translator(cfg, {}, kaynak_dil)
            sonuc = cevirmen.translate_segments([parca], gecici)
        if len(sonuc) != 1 or not str(sonuc[0]).strip():
            raise ValueError("çeviri motoru boş sonuç döndürdü")
        return " ".join(str(sonuc[0]).split())
    except Exception as hata:  # arka uç hataları çeşitli: tek satırda anlaşılır kodla
        raise InceleHatasi("ceviri_basarisiz", f"satır çevrilemedi: {str(hata)[:300]}", 502) from hata
