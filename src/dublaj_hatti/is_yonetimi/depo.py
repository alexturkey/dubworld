"""İş deposu (SQLite): iş geçmişi, sorunlu işler, devam / yeniden çalıştırma, kuyruk, açılış kurtarma.

Kaynak projede bu mantık Telegram botunun içindeydi; burada arayüzden bağımsızdır ve komut satırı, masaüstü
arayüz ve web arayüzü aynı depoyu kullanır (aynı anda birden çok süreç: WAL kipi + `BEGIN IMMEDIATE`).

Durumlar: queued (kuyrukta), deferred (ertelendi), preparing (devam kopyası hazırlanıyor), processing
(işleniyor), completed (bitti), failed (hata), cancelled (iptal / yarıda kesildi). `archived=1` iş listeden
gizlenir; iş klasörü ve çıktılar silinmez.

Devam iki biçimdedir:
  * yerinde devam: hata almış/kesilmiş iş aynı klasörde, aynı iş numarasıyla kaldığı aşamadan sürer;
  * yeni işe kopyalayarak: seçilen checkpoint'e kadar olan aşamalar yeni bir iş klasörüne kopyalanır
    (`clone_checkpoint_for_resume`), kaynak iş hiç değişmez; ayar değişikliği varsa aşama bağımlılığına göre
    kopyalama noktası geri çekilir. Biten işte "aşamayı yeniden çalıştır" da budur.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dublaj_hatti.bolum_00_omurga.core.pipeline_checkpoint import (
    PIPELINE_STATE_SCHEMA_VERSION,
    PipelineCheckpointError,
    checkpoint_resume_options,
    checkpoint_stage_registry,
    clone_checkpoint_for_resume,
)
from dublaj_hatti.bolum_00_omurga.runtime.surec_durumu import process_matches, process_start_time
from dublaj_hatti.is_yonetimi.asamalar import asama_adi, asama_coz
from dublaj_hatti.is_yonetimi.bagimlilik import devam_bagimliligi
from dublaj_hatti.is_yonetimi.secim_denetimi import denetim_yaz
from dublaj_hatti.is_yonetimi.soyagaci import JobLineageError, read_job_lineage, write_job_lineage

DEPO_ENV = "DUBLAJ_IS_DEPOSU"
DEPO_DOSYA_ADI = "isler.sqlite3"
AKTIF = ("queued", "deferred", "preparing", "processing")
SORUNLU = ("failed", "cancelled")
DEVAM_EDILEBILIR = ("failed", "cancelled", "completed")
DURUM_ADLARI = {
    "queued": "kuyrukta", "deferred": "ertelendi", "preparing": "hazırlanıyor", "processing": "işleniyor",
    "completed": "bitti", "failed": "hata", "cancelled": "iptal / kesildi",
}

_SEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL DEFAULT 'queued',
    command TEXT NOT NULL DEFAULT 'dubla',
    source TEXT NOT NULL DEFAULT '',
    transcript_format TEXT NOT NULL DEFAULT '',
    settings_json TEXT NOT NULL DEFAULT '{}',
    overrides_json TEXT NOT NULL DEFAULT '[]',
    dubbing_mode TEXT NOT NULL DEFAULT 'segment_sync',
    request_origin TEXT NOT NULL DEFAULT 'cli',
    queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    retry_after_at TIMESTAMP,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error_type TEXT NOT NULL DEFAULT '',
    run_dir TEXT NOT NULL DEFAULT '',
    pipeline_status TEXT NOT NULL DEFAULT '',
    failed_stage TEXT NOT NULL DEFAULT '',
    last_completed_stage TEXT NOT NULL DEFAULT '',
    resume_attempt_count INTEGER NOT NULL DEFAULT 0,
    source_job_id INTEGER,
    resume_after_stage TEXT NOT NULL DEFAULT '',
    resume_source_run_dir TEXT NOT NULL DEFAULT '',
    resume_source_status TEXT NOT NULL DEFAULT '',
    resume_source_manifest_digest TEXT NOT NULL DEFAULT '',
    resume_source_pipeline_status TEXT NOT NULL DEFAULT '',
    checkpoint_plan_json TEXT NOT NULL DEFAULT '',
    result_json TEXT NOT NULL DEFAULT '',
    pid INTEGER NOT NULL DEFAULT 0,
    pid_start TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS jobs_source_job ON jobs(source_job_id);
"""


class IsHatasi(RuntimeError):
    """Kullanıcıya gösterilecek iş yönetimi hatası (neden + ne yapılmalı)."""


def varsayilan_depo_yolu(cikti_koku: str | Path) -> Path:
    ham = os.environ.get(DEPO_ENV, "").strip()
    return Path(ham).expanduser() if ham else Path(cikti_koku) / "_is_deposu" / DEPO_DOSYA_ADI


def _json(ham: Any, tur: type = dict) -> Any:
    try:
        deger = json.loads(str(ham or "")) if ham else tur()
    except (TypeError, ValueError):
        return tur()
    return deger if isinstance(deger, tur) else tur()


def degisiklikleri_coz(eski: dict[str, Any], ifadeler: Sequence[str]) -> dict[str, Any]:
    """`a.b=c` ifadelerini eski etkin ayarın üstüne uygular, doğrular; yalnız gerçekten değişen anahtarları döndürür."""
    from dublaj_hatti import yapilandirma as y

    yeni = dict(eski)
    for ifade in ifadeler or ():
        if "=" not in ifade:
            raise IsHatasi(f"--ayar biçimi bolum.ad=deger olmalı: {ifade!r}")
        anahtar, ham = (p.strip() for p in ifade.split("=", 1))
        try:
            yeni[anahtar] = y._deger_dogrula(anahtar, y._metin_degeri_coz(anahtar, ham))
        except ValueError as hata:
            raise IsHatasi(str(hata)) from hata
    try:
        y._uyumluluk_uygula({**{k: v for k, v in y.ayarlari_yukle().items()}, **yeni})
    except ValueError as hata:
        raise IsHatasi(str(hata)) from hata
    return {k: v for k, v in yeni.items() if eski.get(k) != v}


def _pid_ve_damga(pid: int | None) -> tuple[int, str]:
    gercek = int(pid or os.getpid())
    return gercek, process_start_time(gercek)


def _sureci_canli(kayit: Any) -> bool:
    """Kaydı sahiplenen süreç hâlâ o süreç mi (PID yeniden kullanımı: D3)."""
    pid = int(kayit["pid"] or 0)
    return pid > 0 and process_matches(pid, str(kayit["pid_start"] or ""))


class IsDeposu:
    def __init__(self, db_yolu: str | Path, cikti_koku: str | Path) -> None:
        self.db_yolu = Path(db_yolu)
        self.cikti_koku = Path(cikti_koku).resolve()
        self.db_yolu.parent.mkdir(parents=True, exist_ok=True)
        with self._baglan() as db:
            db.executescript(_SEMA)
            sutunlar = {s["name"] for s in db.execute("PRAGMA table_info(jobs)")}
            if "pid_start" not in sutunlar:  # eski veritabanı (D3 öncesi): damgasız kayıtlar canlılıkla denetlenir
                db.execute("ALTER TABLE jobs ADD COLUMN pid_start TEXT NOT NULL DEFAULT ''")

    # ---- temel -------------------------------------------------------------------------------------------
    @contextmanager
    def _baglan(self, yazma: bool = False) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(str(self.db_yolu), timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA busy_timeout=30000")
            if yazma:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if yazma:
                db.execute("COMMIT")
        except BaseException:
            if yazma and db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def getir(self, job_id: int) -> dict[str, Any] | None:
        with self._baglan() as db:
            satir = db.execute("SELECT * FROM jobs WHERE job_id = ?", (int(job_id),)).fetchone()
        return dict(satir) if satir else None

    def run_dir_ile_bul(self, run_dir: str | Path) -> dict[str, Any] | None:
        hedef = Path(run_dir).resolve()
        with self._baglan() as db:
            for satir in db.execute("SELECT * FROM jobs WHERE run_dir != '' ORDER BY job_id DESC"):
                if Path(satir["run_dir"]).resolve() == hedef:
                    return dict(satir)
        return None

    def is_ekle(self, kaynak: str, ayar: dict[str, Any], komut: str = "dubla", arayuz: str = "cli",
                ifadeler: Sequence[str] = (), transkript_bicimi: str = "") -> int:
        if komut not in ("dubla", "transkript"):
            raise IsHatasi(f"bilinmeyen komut: {komut}")
        with self._baglan(yazma=True) as db:
            imlec = db.execute(
                """INSERT INTO jobs (status, command, source, transcript_format, settings_json, overrides_json,
                                     dubbing_mode, request_origin)
                   VALUES ('queued', ?, ?, ?, ?, ?, ?, ?)""",
                (komut, str(kaynak), transkript_bicimi, json.dumps(ayar, ensure_ascii=False, sort_keys=True),
                 json.dumps(list(ifadeler), ensure_ascii=False),
                 str(ayar.get("genel.dublaj_kipi") or "segment_sync"), str(arayuz)),
            )
            return int(imlec.lastrowid or 0)

    def listele(self, limit: int = 50, durumlar: Sequence[str] | None = None,
                arsiv_dahil: bool = False) -> list[dict[str, Any]]:
        kosul, deger = [], []
        if durumlar:
            kosul.append(f"status IN ({','.join('?' for _ in durumlar)})")
            deger += list(durumlar)
        if not arsiv_dahil:
            kosul.append("archived = 0")
        nerede = ("WHERE " + " AND ".join(kosul)) if kosul else ""
        with self._baglan() as db:
            satirlar = db.execute(
                f"SELECT * FROM jobs {nerede} ORDER BY datetime(COALESCE(completed_at, started_at, queued_at)) DESC, "  # noqa: S608 - yalnız '?' yer tutucuları birleştirilir
                "job_id DESC LIMIT ?", (*deger, max(1, min(int(limit), 1000))),
            ).fetchall()
        return [dict(s) for s in satirlar]

    def son_sorunlu(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.listele(limit, SORUNLU)

    def son_biten(self, limit: int = 15) -> list[dict[str, Any]]:
        return [i for i in self.listele(limit, ("completed",)) if i["command"] == "dubla"]

    # ---- çalıştırma durumu -------------------------------------------------------------------------------
    def sahiplen(self, job_id: int, pid: int | None = None, beklenen: Sequence[str] = ("queued", "deferred"),
                 tek_yuva: bool = False) -> bool:
        """İşi atomik olarak 'processing' yapar. `tek_yuva`: başka işlenen/hazırlanan iş varsa almaz (kuyruk)."""
        yer = ",".join("?" for _ in beklenen)
        ek = ("AND NOT EXISTS (SELECT 1 FROM jobs AS a WHERE a.job_id != ? AND a.status IN ('preparing','processing'))"
              if tek_yuva else "")
        with self._baglan(yazma=True) as db:
            imlec = db.execute(
                f"""UPDATE jobs SET status='processing', started_at=CURRENT_TIMESTAMP, error_message=NULL,
                           completed_at=NULL, pid=?, pid_start=?
                    WHERE job_id=? AND status IN ({yer}) AND (retry_after_at IS NULL OR
                          datetime(retry_after_at) <= datetime('now')) {ek}""",  # noqa: S608 - yalnız '?' yer tutucuları birleştirilir
                (*_pid_ve_damga(pid), int(job_id), *beklenen, *((int(job_id),) if tek_yuva else ())),
            )
            return imlec.rowcount == 1

    def boru_olayi(self, job_id: int, olay: dict[str, Any]) -> bool:
        """Checkpoint deposunun olayını (run_dir, durum, son aşama) iş kaydına işler."""
        run_dir = str(olay.get("run_dir") or "").strip()
        if run_dir:
            run_dir = str(Path(run_dir).resolve())
        with self._baglan(yazma=True) as db:
            if run_dir:
                for sahip, sahip_dir in db.execute("SELECT job_id, run_dir FROM jobs WHERE run_dir != ''"):
                    if int(sahip) != int(job_id) and Path(sahip_dir).resolve() == Path(run_dir):
                        return False
            imlec = db.execute(
                """UPDATE jobs SET run_dir = CASE WHEN ? != '' THEN ? ELSE run_dir END,
                           pipeline_status=?, failed_stage=?, last_completed_stage=?,
                           resume_attempt_count = resume_attempt_count + CASE WHEN ?='pipeline_acquired' THEN 1 ELSE 0 END
                   WHERE job_id=?""",
                (run_dir, run_dir, str(olay.get("status") or ""), str(olay.get("failed_stage") or ""),
                 str(olay.get("last_completed_stage") or ""), str(olay.get("event") or ""), int(job_id)),
            )
            degisti = imlec.rowcount == 1
        if degisti:
            self._soyagaci_esitle(job_id)
        return degisti

    def bitir(self, job_id: int, durum: str = "completed", hata: str | None = None,
              sonuc: dict[str, Any] | None = None) -> bool:
        if durum not in ("completed", "failed", "cancelled"):
            raise IsHatasi(f"geçersiz bitiş durumu: {durum}")
        with self._baglan(yazma=True) as db:
            imlec = db.execute(
                """UPDATE jobs SET status=?, completed_at=CURRENT_TIMESTAMP, error_message=?, retry_after_at=NULL,
                           result_json = CASE WHEN ? != '' THEN ? ELSE result_json END, pid=0
                   WHERE job_id=?""",
                (durum, hata, json.dumps(sonuc or {}, ensure_ascii=False) if sonuc else "",
                 json.dumps(sonuc or {}, ensure_ascii=False) if sonuc else "", int(job_id)),
            )
            degisti = imlec.rowcount == 1
        self._soyagaci_esitle(job_id)
        return degisti

    def ertele(self, job_id: int, saniye: int, hata: str, tur: str = "temporary") -> bool:
        with self._baglan(yazma=True) as db:
            imlec = db.execute(
                """UPDATE jobs SET status='deferred', retry_after_at=datetime('now', ?), error_message=?,
                           last_error_type=?, retry_count=retry_count+1, pid=0
                   WHERE job_id=? AND status IN ('queued','processing','deferred')""",
                (f"+{int(saniye)} seconds", hata, tur, int(job_id)),
            )
            return imlec.rowcount == 1

    def iptal(self, job_id: int, neden: str = "Kullanıcı iptal etti") -> bool:
        with self._baglan(yazma=True) as db:
            imlec = db.execute(
                """UPDATE jobs SET status='cancelled', completed_at=CURRENT_TIMESTAMP, error_message=?,
                           retry_after_at=NULL, pid=0 WHERE job_id=? AND status IN ('queued','deferred','preparing')""",
                (neden, int(job_id)),
            )
            degisti = imlec.rowcount == 1
        self._soyagaci_esitle(job_id)
        return degisti

    def arsivle(self, job_id: int, geri_al: bool = False) -> bool:
        """İş kaydını listeden gizler (iş klasörü ve çıktılar silinmez). Etkin iş arşivlenmez."""
        with self._baglan(yazma=True) as db:
            imlec = db.execute(
                f"UPDATE jobs SET archived=? WHERE job_id=? AND status NOT IN ({','.join('?' for _ in AKTIF)})",  # noqa: S608 - yalnız '?' yer tutucuları birleştirilir
                (0 if geri_al else 1, int(job_id), *AKTIF),
            )
            return imlec.rowcount == 1

    # ---- kuyruk ------------------------------------------------------------------------------------------
    def kuyruk(self, arayuz: str | None = None) -> list[dict[str, Any]]:
        with self._baglan() as db:
            satirlar = db.execute(
                """SELECT * FROM jobs WHERE status IN ('queued','deferred') AND (? IS NULL OR request_origin=?)
                   ORDER BY datetime(COALESCE(retry_after_at, queued_at)), job_id""",
                (arayuz, arayuz),
            ).fetchall()
        return [dict(s) for s in satirlar]

    def kuyruk_sirasi(self, job_id: int) -> int:
        for sira, is_kaydi in enumerate(self.kuyruk(), start=1):
            if int(is_kaydi["job_id"]) == int(job_id):
                return sira
        return 0

    def siradaki(self, arayuz: str | None = None) -> dict[str, Any] | None:
        with self._baglan() as db:
            satir = db.execute(
                """SELECT * FROM jobs WHERE status IN ('queued','deferred') AND (? IS NULL OR request_origin=?)
                     AND (retry_after_at IS NULL OR datetime(retry_after_at) <= datetime('now'))
                   ORDER BY datetime(COALESCE(retry_after_at, queued_at)), job_id LIMIT 1""",
                (arayuz, arayuz),
            ).fetchone()
        return dict(satir) if satir else None

    # ---- açılış kurtarma ve bayat işler -----------------------------------------------------------------
    def acilista_kurtar(self, arayuz: str | None = None) -> list[dict[str, Any]]:
        """Kapanmış (süreci ölmüş) işleri toparlar: yarım devam hazırlığı kuyruğa döner, yarıda kalan işlem
        'failed / process_interrupted' olur ve checkpoint'iyle devam ettirilebilir. Canlı sürecin işine dokunmaz."""
        kurtarilan = []
        with self._baglan(yazma=True) as db:
            for satir in db.execute(
                "SELECT * FROM jobs WHERE status IN ('preparing','processing') AND (? IS NULL OR request_origin=?)",
                (arayuz, arayuz),
            ).fetchall():
                is_kaydi = dict(satir)
                if _sureci_canli(is_kaydi):
                    continue
                if is_kaydi["status"] == "preparing":
                    db.execute("""UPDATE jobs SET status='queued', pipeline_status='resume_queued', started_at=NULL,
                                         error_message=NULL, pid=0 WHERE job_id=?""", (is_kaydi["job_id"],))
                    is_kaydi["yeni_durum"] = "queued"
                else:
                    db.execute(
                        """UPDATE jobs SET status='failed', completed_at=CURRENT_TIMESTAMP, retry_after_at=NULL,
                                  error_message='Program ya da bilgisayar kapandı; iş checkpoint ile kesildi',
                                  pipeline_status='failed', pid=0,
                                  failed_stage=CASE WHEN failed_stage='' THEN 'process_interrupted' ELSE failed_stage END
                           WHERE job_id=?""", (is_kaydi["job_id"],))
                    is_kaydi["yeni_durum"] = "failed"
                kurtarilan.append(is_kaydi)
        for is_kaydi in kurtarilan:
            self._soyagaci_esitle(is_kaydi["job_id"])
        return kurtarilan

    def bayat_iptal(self, azami_dakika: int = 360) -> int:
        """`azami_dakika`dan uzun süredir 'processing' görünen ve süreci yaşamayan işleri iptal eder."""
        iptal = []
        with self._baglan(yazma=True) as db:
            for satir in db.execute(
                "SELECT job_id, pid, pid_start FROM jobs WHERE status='processing' AND started_at < datetime('now', ?)",
                (f"-{int(azami_dakika)} minutes",),
            ).fetchall():
                if _sureci_canli(satir):
                    continue
                db.execute("""UPDATE jobs SET status='cancelled', completed_at=CURRENT_TIMESTAMP, pid=0,
                                     error_message='Bayat iş iptal edildi (süreç yok)' WHERE job_id=?""",
                           (satir["job_id"],))
                iptal.append(int(satir["job_id"]))
        for job_id in iptal:
            self._soyagaci_esitle(job_id)
        return len(iptal)

    # ---- devam seçenekleri -------------------------------------------------------------------------------
    def _klasor_kok_icinde(self, run_dir: str) -> Path | None:
        if not str(run_dir or "").strip():
            return None
        yol = Path(run_dir).resolve()
        try:
            yol.relative_to(self.cikti_koku)
        except ValueError:
            return None
        return yol

    def manifest_gecerli(self, is_kaydi: dict[str, Any]) -> bool:
        yol = self._klasor_kok_icinde(str(is_kaydi.get("run_dir") or ""))
        if yol is None:
            return False
        try:
            ham = (yol / "pipeline_state.json").read_bytes()
            if ham.startswith(b"\xef\xbb\xbf"):
                return False
            manifest = json.loads(ham.decode("utf-8"))
        except (OSError, ValueError):
            return False
        return (
            isinstance(manifest, dict)
            and int(manifest.get("schema_version") or 0) == PIPELINE_STATE_SCHEMA_VERSION
            and str(manifest.get("job_id") or "") == str(is_kaydi["job_id"])
            and str(manifest.get("pipeline_kind") or "") == str(is_kaydi.get("dubbing_mode") or "segment_sync")
            and str(manifest.get("source_identity") or "") == str(is_kaydi.get("source") or "")
            and str(manifest.get("status") or "") in {"created", "running", "failed", "completed"}
            and isinstance(manifest.get("stages"), dict)
        )

    def devam_secenekleri(self, is_kaydi: dict[str, Any]) -> list[dict[str, Any]]:
        """Korunabilecek checkpoint'ler (baştan itibaren kesintisiz geçerli aşamalar)."""
        if is_kaydi.get("command") != "dubla" or not self.manifest_gecerli(is_kaydi):
            return []
        try:
            secenekler = checkpoint_resume_options(str(is_kaydi["run_dir"]))
        except (PipelineCheckpointError, OSError, ValueError):
            return []
        return [{**s, "ad": asama_adi(s["stage_id"])} for s in secenekler]

    def yeniden_calistirma_secenekleri(self, is_kaydi: dict[str, Any]) -> list[dict[str, Any]]:
        """Her checkpoint için 'şu aşamadan yeniden çalıştır' seçeneği (checkpoint'ten sonraki ilk aşama)."""
        secenekler = self.devam_secenekleri(is_kaydi)
        if not secenekler:
            return []
        liste = checkpoint_stage_registry(str(is_kaydi.get("dubbing_mode") or "segment_sync"))
        sonuc = []
        for cp in secenekler:
            sonraki = next(((a, o) for a, o, _ in liste if o > int(cp["stage_order"])), None)
            if sonraki:
                sonuc.append({"checkpoint_stage_id": cp["stage_id"], "checkpoint_stage_order": cp["stage_order"],
                              "restart_stage_id": sonraki[0], "restart_stage_order": sonraki[1],
                              "ad": asama_adi(sonraki[0])})
        return sonuc

    # ---- devam -------------------------------------------------------------------------------------------
    def yerinde_devam(self, job_id: int) -> int:
        """Hata almış / kesilmiş işi aynı klasörde, aynı numarayla kuyruğa geri koyar."""
        is_kaydi = self._devam_kaynagi(job_id)
        if is_kaydi["status"] == "completed":
            raise IsHatasi("iş zaten tamamlandı; bir aşamayı yeniden çalıştırmak için --asama verin")
        with self._baglan(yazma=True) as db:
            imlec = db.execute(
                """UPDATE jobs SET status='queued', pipeline_status='resume_queued', error_message=NULL,
                          completed_at=NULL, retry_after_at=NULL, queued_at=CURRENT_TIMESTAMP, pid=0
                   WHERE job_id=? AND status IN ('failed','cancelled')""", (int(job_id),))
            if imlec.rowcount != 1:
                raise IsHatasi("iş durumu değişti; yeniden deneyin")
        return int(job_id)

    def _devam_kaynagi(self, job_id: int) -> dict[str, Any]:
        is_kaydi = self.getir(job_id)
        if not is_kaydi:
            raise IsHatasi(f"iş bulunamadı: #{job_id}")
        if is_kaydi["command"] != "dubla":
            raise IsHatasi("yalnız dublaj işleri devam ettirilebilir (transkript işi yeniden başlatılır)")
        if is_kaydi["status"] not in DEVAM_EDILEBILIR:
            raise IsHatasi(f"iş #{job_id} şu an {DURUM_ADLARI.get(is_kaydi['status'], is_kaydi['status'])}; "
                           "devam yalnız biten, hata alan ya da kesilen işte")
        if not self.manifest_gecerli(is_kaydi):
            raise IsHatasi(f"iş #{job_id} için geçerli checkpoint manifesti yok (klasör silinmiş, çıktı kökü dışında "
                           "ya da başka işe ait); baştan çalıştırın")
        return is_kaydi

    def devam_iste(self, job_id: int, ifadeler: Sequence[str] = (), asama: str | int | None = None,
                   arayuz: str = "cli") -> int:
        """Yeni işe kopyalayarak devam. `asama`: yeniden çalışacak ilk aşama (verilmezse son geçerli checkpoint'ten
        sonrası). `ifadeler`: `a.b=c` ayar değişiklikleri. Yeni iş numarasını döndürür (kuyrukta)."""
        kaynak = self._devam_kaynagi(job_id)
        secenekler = checkpoint_resume_options(str(kaynak["run_dir"]))
        if not secenekler:
            raise IsHatasi("korunabilecek tamamlanmış aşama yok; baştan çalıştırın")
        eski = _json(kaynak["settings_json"])
        degisiklik = degisiklikleri_coz(eski, ifadeler)
        hedef_kip = str({**eski, **degisiklik}.get("genel.dublaj_kipi") or kaynak["dubbing_mode"])
        if asama is not None:
            _, sira = asama_coz(hedef_kip, asama)
            uygun = [int(s["stage_order"]) for s in secenekler if int(s["stage_order"]) < sira]
            if not uygun:
                raise IsHatasi(f"'{asama}' aşamasından önce korunabilecek checkpoint yok; baştan çalıştırın")
            istenen = max(uygun)
        else:
            istenen = int(secenekler[-1]["stage_order"])
            if kaynak["status"] == "completed" and not degisiklik:
                raise IsHatasi("iş tamamlanmış ve ayar değişmedi; --asama ile yeniden çalışacak aşamayı seçin")
        try:
            plan = devam_bagimliligi(eski, degisiklik, istenen)
        except ValueError as hata:
            raise IsHatasi(str(hata)) from hata
        etkin = int(plan["effective_stage_order"])
        secilen = [s for s in secenekler if int(s["stage_order"]) <= etkin]
        if not secilen:
            raise IsHatasi("değişiklik ilk aşamayı etkiliyor; korunacak checkpoint kalmadı, baştan çalıştırın")
        secilen_asama = str(secilen[-1]["stage_id"])
        plan["selected_stage_id"] = secilen_asama
        manifest = (Path(kaynak["run_dir"]) / "pipeline_state.json").read_bytes()
        ozet = hashlib.sha256(manifest).hexdigest()
        boru_durumu = str(json.loads(manifest.decode("utf-8")).get("status") or "")
        yeni_ayar = {**eski, **degisiklik}
        with self._baglan(yazma=True) as db:
            guncel = db.execute("SELECT status, run_dir FROM jobs WHERE job_id=?", (int(job_id),)).fetchone()
            if not guncel or guncel["status"] != kaynak["status"] or guncel["run_dir"] != kaynak["run_dir"]:
                raise IsHatasi("kaynak iş bu sırada değişti; yeniden deneyin")
            aktif = db.execute(
                f"SELECT COUNT(*) FROM jobs WHERE source_job_id=? AND status IN ({','.join('?' for _ in AKTIF)})",  # noqa: S608 - yalnız '?' yer tutucuları birleştirilir
                (int(job_id), *AKTIF)).fetchone()[0]
            if int(aktif):
                raise IsHatasi(f"iş #{job_id} için zaten bekleyen ya da süren bir devam işi var")
            imlec = db.execute(
                """INSERT INTO jobs (status, command, source, transcript_format, settings_json, overrides_json,
                       dubbing_mode, request_origin, pipeline_status, last_completed_stage, source_job_id,
                       resume_after_stage, resume_source_run_dir, resume_source_status,
                       resume_source_manifest_digest, resume_source_pipeline_status, checkpoint_plan_json)
                   VALUES ('queued', ?, ?, ?, ?, ?, ?, ?, 'resume_queued', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kaynak["command"], kaynak["source"], kaynak["transcript_format"],
                 json.dumps(yeni_ayar, ensure_ascii=False, sort_keys=True),
                 json.dumps(_json(kaynak["overrides_json"], list) + list(ifadeler), ensure_ascii=False),
                 hedef_kip, arayuz, secilen_asama, int(job_id), secilen_asama, kaynak["run_dir"], kaynak["status"],
                 ozet, boru_durumu, json.dumps(plan, ensure_ascii=False, sort_keys=True)),
            )
            return int(imlec.lastrowid or 0)

    def hazirlik_sahiplen(self, job_id: int, tek_yuva: bool = False, pid: int | None = None) -> bool:
        ek = ("AND NOT EXISTS (SELECT 1 FROM jobs AS a WHERE a.job_id != ? AND a.status IN ('preparing','processing'))"
              if tek_yuva else "")
        with self._baglan(yazma=True) as db:
            imlec = db.execute(
                f"""UPDATE jobs SET status='preparing', pipeline_status='resume_preparing', pid=?, pid_start=?,
                           started_at=CURRENT_TIMESTAMP, error_message=NULL
                    WHERE job_id=? AND status IN ('queued','deferred') AND source_job_id IS NOT NULL
                          AND run_dir = '' {ek}""",  # noqa: S608 - yalnız '?' yer tutucuları birleştirilir
                (*_pid_ve_damga(pid), int(job_id), *((int(job_id),) if tek_yuva else ())),
            )
            return imlec.rowcount == 1

    def devam_hazirla(self, job_id: int) -> Path:
        """Sahiplenilmiş devam işinin klasörünü kaynak checkpoint'ten kopyalar (SQLite kilidi tutulmadan)."""
        cocuk = self.getir(job_id)
        if not cocuk or cocuk["status"] != "preparing" or not cocuk["source_job_id"]:
            raise IsHatasi("devam işi hazırlık için sahiplenilmedi")
        kaynak = self.getir(int(cocuk["source_job_id"]))
        if not kaynak:
            raise IsHatasi("kaynak checkpoint işi bulunamadı")
        beklenen_dir = cocuk["resume_source_run_dir"]
        if kaynak["run_dir"] != beklenen_dir:
            raise IsHatasi("kaynak iş klasörü kuyruk kaydından sonra değişti")
        if kaynak["status"] != cocuk["resume_source_status"]:
            raise IsHatasi("kaynak iş durumu kuyruk kaydından sonra değişti")
        if not self.manifest_gecerli(kaynak):
            raise IsHatasi("kaynak checkpoint manifesti geçersiz")
        manifest_yolu = Path(beklenen_dir) / "pipeline_state.json"
        if hashlib.sha256(manifest_yolu.read_bytes()).hexdigest() != cocuk["resume_source_manifest_digest"]:
            raise IsHatasi("kaynak checkpoint manifesti kuyruk kaydından sonra değişti")
        if cocuk["resume_after_stage"] not in {s["stage_id"] for s in checkpoint_resume_options(beklenen_dir)}:
            raise IsHatasi("seçilen checkpoint artık kullanılamıyor")
        try:
            kopya = clone_checkpoint_for_resume(beklenen_dir, int(job_id), cocuk["resume_after_stage"],
                                                cocuk["dubbing_mode"] or "segment_sync")
        except PipelineCheckpointError as hata:
            raise IsHatasi(f"checkpoint kopyalanamadı: {hata}") from hata
        if hashlib.sha256(manifest_yolu.read_bytes()).hexdigest() != cocuk["resume_source_manifest_digest"]:
            raise IsHatasi("kaynak checkpoint manifesti kopyalama sırasında değişti")
        with self._baglan(yazma=True) as db:
            imlec = db.execute(
                """UPDATE jobs SET run_dir=?, pipeline_status='created', failed_stage='', last_completed_stage=?,
                          resume_attempt_count=0
                   WHERE job_id=? AND status='preparing'
                     AND EXISTS (SELECT 1 FROM jobs AS k WHERE k.job_id=? AND k.status=? AND k.run_dir=?)""",
                (str(kopya), cocuk["resume_after_stage"], int(job_id), int(kaynak["job_id"]),
                 cocuk["resume_source_status"], beklenen_dir),
            )
            if imlec.rowcount != 1:
                raise IsHatasi("devam işi hazırlık sırasında durum değiştirdi")
        cocuk = self.getir(job_id) or cocuk
        if not self._soyagaci_esitle(job_id, kopya):
            raise IsHatasi("devam işinin soyağacı yazılamadı")
        denetim_yaz(kopya, cocuk, kaynak)
        return kopya

    def hazirlik_basarisiz(self, job_id: int, mesaj: str) -> bool:
        with self._baglan(yazma=True) as db:
            imlec = db.execute(
                """UPDATE jobs SET status='failed', completed_at=CURRENT_TIMESTAMP, error_message=?,
                          pipeline_status='failed', failed_stage='resume_preparation', retry_after_at=NULL, pid=0
                   WHERE job_id=? AND status='preparing'""", (str(mesaj), int(job_id)))
            return imlec.rowcount == 1

    # ---- soyağacı ----------------------------------------------------------------------------------------
    def _soyagaci_esitle(self, job_id: int, run_dir: str | Path | None = None) -> bool:
        try:
            yol = Path(run_dir).resolve() if run_dir else None
            if yol is None:
                is_kaydi = self.getir(job_id)
                yol = self._klasor_kok_icinde(str(is_kaydi["run_dir"])) if is_kaydi else None
                if yol is None:
                    return True
            yol.relative_to(self.cikti_koku)
            if not (yol / "pipeline_state.json").is_file():
                return True
            write_job_lineage(self.db_yolu, int(job_id), yol)
            return True
        except (JobLineageError, OSError, ValueError, sqlite3.Error):
            return False

    def soyagaci(self, job_id: int) -> dict[str, Any]:
        is_kaydi = self.getir(job_id)
        if not is_kaydi or not is_kaydi["run_dir"]:
            raise IsHatasi(f"iş #{job_id} için klasör yok")
        try:
            return read_job_lineage(is_kaydi["run_dir"])
        except JobLineageError:
            if not self._soyagaci_esitle(job_id):
                raise IsHatasi(f"iş #{job_id} soyağacı kurulamadı") from None
            return read_job_lineage(is_kaydi["run_dir"])


def _yerel_saat(utc: Any) -> str | None:
    """SQLite CURRENT_TIMESTAMP (UTC) → bilgisayarın yerel saati, aynı biçimde."""
    if not utc:
        return None
    try:
        an = datetime.strptime(str(utc), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return str(utc)
    return an.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def is_ozeti(is_kaydi: dict[str, Any]) -> dict[str, Any]:
    """Arayüzlerin göstereceği kısa, JSON'a uygun özet (kişisel veri yok; kaynak yalnız dosya adı)."""
    sonuc = _json(is_kaydi.get("result_json"))
    return {
        "is": int(is_kaydi["job_id"]),
        "durum": is_kaydi["status"],
        "durum_adi": DURUM_ADLARI.get(is_kaydi["status"], is_kaydi["status"]),
        "komut": is_kaydi["command"],
        "kaynak_adi": Path(str(is_kaydi["source"] or "")).name,
        "kip": is_kaydi["dubbing_mode"],
        "arayuz": is_kaydi["request_origin"],
        "eklendi": _yerel_saat(is_kaydi["queued_at"]), "basladi": _yerel_saat(is_kaydi["started_at"]),
        "bitti": _yerel_saat(is_kaydi["completed_at"]),
        "hata": (is_kaydi["error_message"] or "")[:500],
        "basarisiz_asama": is_kaydi["failed_stage"], "basarisiz_asama_adi": asama_adi(is_kaydi["failed_stage"]),
        "son_asama": is_kaydi["last_completed_stage"], "son_asama_adi": asama_adi(is_kaydi["last_completed_stage"]),
        "klasor": is_kaydi["run_dir"],
        "ebeveyn": is_kaydi["source_job_id"],
        "devam_asamasi": is_kaydi["resume_after_stage"],
        "deneme": is_kaydi["resume_attempt_count"],
        "arsiv": bool(is_kaydi["archived"]),
        "video": sonuc.get("dubbed_video") or sonuc.get("output_video") or "",
        "srt": sonuc.get("srt_path") or "",
        "kaynak_yolu": str(is_kaydi["source"] or ""),
    }
