"""PID yeniden kullanımı (Düzeltme A, D3): kaynak kilidi ve iş deposu PID ile birlikte süreç başlangıç damgasını
yazar; aynı PID'yi alan başka bir süreç kilidi ya da işi canlı tutamaz. Kilit zamanları UTC. Ağsız, GPU'suz."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta

from dublaj_hatti.bolum_00_omurga.runtime import kaynak_kilidi
from dublaj_hatti.bolum_00_omurga.runtime.surec_durumu import process_matches, process_start_time
from dublaj_hatti.is_yonetimi import depo as depo_mod
from dublaj_hatti.is_yonetimi.depo import IsDeposu

BU_SUREC = os.getpid()


def test_baslangic_damgasi_kendi_surecim():
    damga = process_start_time(BU_SUREC)
    assert damga and damga == process_start_time(BU_SUREC)
    assert process_matches(BU_SUREC, damga)
    assert process_matches(BU_SUREC, "")  # damgasız eski kayıt: yalnız canlılık
    assert not process_matches(BU_SUREC, "win:1" if os.name == "nt" else "linux:1")  # aynı PID, başka süreç
    assert process_start_time(0) == "" and not process_matches(0, "")


def test_kilit_damga_ve_utc_yazar(tmp_path, monkeypatch):
    monkeypatch.setenv(kaynak_kilidi.KILIT_KLASORU_ENV, str(tmp_path))
    yol = kaynak_kilidi.kilit_al("gpu", "ajan:test", "d3")
    kayit = json.loads(yol.read_text(encoding="utf-8"))
    assert kayit["pid"] == BU_SUREC and kayit["pid_baslangic"] == process_start_time(BU_SUREC)
    assert datetime.fromisoformat(kayit["baslangic"]).utcoffset() == timedelta(0)
    assert len(kaynak_kilidi.kilitler("gpu")) == 1


def test_yeniden_kullanilan_pid_kilidi_bayat_sayilir(tmp_path, monkeypatch):
    monkeypatch.setenv(kaynak_kilidi.KILIT_KLASORU_ENV, str(tmp_path))
    yol = kaynak_kilidi.kilit_al("gpu", "ajan:test", "d3")
    kayit = json.loads(yol.read_text(encoding="utf-8"))
    kayit["pid_baslangic"] = "win:1" if os.name == "nt" else "linux:1"  # PID canlı ama başka süreç
    yol.write_text(json.dumps(kayit), encoding="utf-8")
    assert kaynak_kilidi.kilitler("gpu") == []
    assert not yol.exists()


def test_saat_dilimsiz_eski_kilit_okunur(tmp_path, monkeypatch):
    monkeypatch.setenv(kaynak_kilidi.KILIT_KLASORU_ENV, str(tmp_path))
    gecmis = (datetime.now() - timedelta(minutes=5)).replace(microsecond=0).isoformat()  # eski biçim: yerel, dilimsiz
    gelecek = (datetime.now() + timedelta(minutes=30)).replace(microsecond=0).isoformat()
    for ad, son in (("gecmis", gecmis), ("gelecek", gelecek)):
        (tmp_path / f"gpu__{ad}.json").write_text(json.dumps(
            {"kaynak": "gpu", "sahip": ad, "amac": "eski", "pid": 0, "baslangic": gecmis, "son_gecerlilik": son}),
            encoding="utf-8")
    assert [k["sahip"] for k in kaynak_kilidi.kilitler("gpu")] == ["gelecek"]
    assert kaynak_kilidi._zaman_oku(gelecek).tzinfo is not None
    assert kaynak_kilidi._simdi().tzinfo == UTC


def _depo(tmp_path):
    return IsDeposu(tmp_path / "_is_deposu" / "isler.sqlite3", tmp_path)


def test_depo_sahiplenince_damga_yazar(tmp_path):
    depo = _depo(tmp_path)
    job_id = depo.is_ekle("C:/yok/video.mp4", {}, "dubla", "test")
    assert depo.sahiplen(job_id)
    kayit = depo.getir(job_id)
    assert kayit["pid"] == BU_SUREC and kayit["pid_start"] == process_start_time(BU_SUREC)
    assert depo.acilista_kurtar() == []  # gerçekten bu süreç: dokunulmaz


def test_depo_yeniden_kullanilan_pid_kurtarilir(tmp_path):
    depo = _depo(tmp_path)
    job_id = depo.is_ekle("C:/yok/video.mp4", {}, "dubla", "test")
    assert depo.sahiplen(job_id)
    with sqlite3.connect(depo.db_yolu) as db:
        db.execute("UPDATE jobs SET pid_start=? WHERE job_id=?", ("win:1" if os.name == "nt" else "linux:1", job_id))
    kurtarilan = depo.acilista_kurtar()
    assert [k["job_id"] for k in kurtarilan] == [job_id]
    assert depo.getir(job_id)["status"] == "failed"


def test_depo_bayat_iptal_damgaya_bakar(tmp_path):
    depo = _depo(tmp_path)
    job_id = depo.is_ekle("C:/yok/video.mp4", {}, "dubla", "test")
    assert depo.sahiplen(job_id)
    with sqlite3.connect(depo.db_yolu) as db:
        db.execute("UPDATE jobs SET started_at=datetime('now','-2 hours') WHERE job_id=?", (job_id,))
    assert depo.bayat_iptal(60) == 0  # süreç gerçekten canlı
    with sqlite3.connect(depo.db_yolu) as db:
        db.execute("UPDATE jobs SET pid_start='win:1' WHERE job_id=?", (job_id,))
    assert depo.bayat_iptal(60) == 1


def test_eski_veritabani_goc(tmp_path):
    eski = depo_mod._SEMA.replace("    pid_start TEXT NOT NULL DEFAULT '',\n", "")
    assert "pid_start" not in eski
    yol = tmp_path / "_is_deposu" / "isler.sqlite3"
    yol.parent.mkdir(parents=True)
    with sqlite3.connect(yol) as db:
        db.executescript(eski)
    depo = IsDeposu(yol, tmp_path)
    job_id = depo.is_ekle("C:/yok/video.mp4", {}, "dubla", "test")
    assert depo.sahiplen(job_id) and depo.getir(job_id)["pid_start"]
    IsDeposu(yol, tmp_path)  # ikinci açılış: sütun zaten var, hata yok
