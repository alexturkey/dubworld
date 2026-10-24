"""İş deposu: sorunlu / biten işler, devam, yeniden çalıştırma, kuyruk, açılış kurtarma, soyağacı, seçim denetimi.

Kaynak projedeki test_telegram_failed_job_resume'un arayüzden bağımsız karşılığı. GPU'suz, ağsız; bütün işler
sentetiktir (örnek kaynak adı, yapay checkpoint dosyaları), kişisel veri yok.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from dublaj_hatti.bolum_00_omurga.core.pipeline_checkpoint import (
    SEGMENT_SYNC_CHECKPOINT_STAGES,
    PipelineCheckpointStore,
)
from dublaj_hatti.is_yonetimi.depo import IsDeposu, IsHatasi, is_ozeti
from dublaj_hatti.is_yonetimi.secim_denetimi import SECIM_DENETIMI_JSON, SECIM_DENETIMI_TXT
from dublaj_hatti.is_yonetimi.soyagaci import read_job_lineage

KAYNAK = "ornek://video-1"


def _ayar(**ek):
    from dublaj_hatti.yapilandirma import ayarlari_yukle

    return {**ayarlari_yukle(), **ek}


@pytest.fixture()
def depo(tmp_path, monkeypatch):
    monkeypatch.delenv("DUBLAJ_IS_DEPOSU", raising=False)
    kok = tmp_path / "cikti"
    kok.mkdir()
    return IsDeposu(kok / "_is_deposu" / "isler.sqlite3", kok)


def _is_olustur(depo: IsDeposu, durum: str, son_sira: int = 9, kaynak: str = KAYNAK, ayar=None,
                basarisiz: str = "ses_yonlendirme") -> int:
    """Sentetik iş: `son_sira`ya kadar tamamlanmış checkpoint'ler, sonra hata (ya da tamamen bitmiş)."""
    ayar = ayar or _ayar()
    job_id = depo.is_ekle(kaynak, ayar, "dubla", "test")
    assert depo.sahiplen(job_id)
    run_dir = depo.cikti_koku / f"is_{job_id}"
    olaylar = []
    store = PipelineCheckpointStore(run_dir, "segment_sync", kaynak, job_id, event_callback=olaylar.append)
    for asama, sira, surum in SEGMENT_SYNC_CHECKPOINT_STAGES:
        if sira > son_sira:
            break
        dosya = run_dir / f"{sira:02d}_{asama}.json"
        dosya.parent.mkdir(parents=True, exist_ok=True)
        dosya.write_text(json.dumps({"asama": asama}), encoding="utf-8")
        store.begin_stage(asama, sira, surum, {"asama": asama})
        store.complete_stage(asama, {"dosya": dosya.name}, [dosya])
    if durum == "failed":
        sira = next(o for a, o, _ in SEGMENT_SYNC_CHECKPOINT_STAGES if a == basarisiz)
        store.begin_stage(basarisiz, sira, 2, {"asama": basarisiz})
        store.fail_stage(basarisiz, "sentetik hata")
    elif durum == "completed":
        store.mark_pipeline_completed()
    for olay in olaylar:
        depo.boru_olayi(job_id, olay)
    depo.bitir(job_id, durum, "sentetik hata" if durum == "failed" else None)
    return job_id


def test_sorunlu_ve_biten_listeleri_sinirli_ve_en_yeni_once(depo):
    for _ in range(12):
        depo.bitir(depo.is_ekle(KAYNAK, _ayar(), "dubla", "test"), "failed", "x")
    for _ in range(17):
        depo.bitir(depo.is_ekle(KAYNAK, _ayar(), "dubla", "test"), "completed")
    sorunlu = depo.son_sorunlu()
    assert len(sorunlu) == 10
    assert [i["job_id"] for i in sorunlu] == sorted((i["job_id"] for i in sorunlu), reverse=True)
    assert len(depo.son_biten()) == 15


def test_hata_alan_is_yerinde_kaldigi_yerden_surer(depo):
    job_id = _is_olustur(depo, "failed")
    kayit = depo.getir(job_id)
    assert kayit["failed_stage"] == "ses_yonlendirme" and kayit["last_completed_stage"] == "ceviri"
    secenekler = depo.devam_secenekleri(kayit)
    assert secenekler[-1]["stage_id"] == "ceviri" and secenekler[-1]["ad"] == "Çeviri"
    assert depo.yerinde_devam(job_id) == job_id
    kayit = depo.getir(job_id)
    assert kayit["status"] == "queued" and kayit["run_dir"]
    assert depo.sahiplen(job_id)


def test_degisiklik_yoksa_tamamlanmis_iste_bos_cocuk_acilmaz(depo):
    job_id = _is_olustur(depo, "completed", son_sira=17)
    with pytest.raises(IsHatasi, match="ayar değişmedi"):
        depo.devam_iste(job_id)
    with pytest.raises(IsHatasi, match="tamamlandı"):
        depo.yerinde_devam(job_id)


def test_hata_alan_is_degisikliksiz_son_gecerli_checkpointten_yeni_ise_kopyalanir(depo):
    job_id = _is_olustur(depo, "failed")
    cocuk = depo.devam_iste(job_id)
    kayit = depo.getir(cocuk)
    assert kayit["status"] == "queued" and kayit["source_job_id"] == job_id
    assert kayit["resume_after_stage"] == "ceviri" and kayit["run_dir"] == ""
    assert kayit["resume_source_status"] == "failed" and len(kayit["resume_source_manifest_digest"]) == 64


def test_biten_isin_secilen_asamasi_kaynak_degismeden_yeniden_calisir(depo):
    job_id = _is_olustur(depo, "completed", son_sira=17)
    kaynak_dir = Path(depo.getir(job_id)["run_dir"])
    once = (kaynak_dir / "pipeline_state.json").read_bytes()
    cocuk = depo.devam_iste(job_id, asama="ceviri")
    assert depo.getir(cocuk)["resume_after_stage"] == "konusmaci_yonlendirme"
    assert depo.hazirlik_sahiplen(cocuk)
    kopya = depo.devam_hazirla(cocuk)
    assert (kaynak_dir / "pipeline_state.json").read_bytes() == once
    durum = json.loads((kopya / "pipeline_state.json").read_text(encoding="utf-8"))
    assert set(durum["stages"]) == {a for a, o, _ in SEGMENT_SYNC_CHECKPOINT_STAGES if o <= 8}
    assert durum["job_id"] == str(cocuk) and durum["resume_source_job_id"] == str(job_id)
    soy = read_job_lineage(kopya)
    assert soy["root_job_id"] == job_id and soy["parent_job_id"] == job_id and soy["generation"] == 1
    assert soy["relationship"] == "rerun_from_completed"
    assert (kopya / SECIM_DENETIMI_JSON).is_file() and (kopya / SECIM_DENETIMI_TXT).is_file()
    assert depo.sahiplen(cocuk, beklenen=("preparing",))


def test_ayar_degisikligi_bagimliliga_gore_geri_ceker_ve_kaydedilir(depo):
    job_id = _is_olustur(depo, "failed")
    cocuk = depo.devam_iste(job_id, ["transkripsiyon.model=large-v3"])
    kayit = depo.getir(cocuk)
    assert kayit["resume_after_stage"] == "asr_sesi_hazirlama"
    plan = json.loads(kayit["checkpoint_plan_json"])
    assert plan["effective_stage_order"] == 5 and plan["requested_stage_order"] == 9
    assert plan["changed_fields"][0]["field"] == "transkripsiyon.model"
    assert json.loads(kayit["settings_json"])["transkripsiyon.model"] == "large-v3"
    assert json.loads(kayit["overrides_json"]) == ["transkripsiyon.model=large-v3"]
    assert depo.hazirlik_sahiplen(cocuk)
    kopya = depo.devam_hazirla(cocuk)
    denetim = json.loads((kopya / SECIM_DENETIMI_JSON).read_text(encoding="utf-8"))
    assert denetim["karsilastirma"]["degisen"][0]["anahtar"] == "transkripsiyon.model"
    assert "transkripsiyon.model" in (kopya / SECIM_DENETIMI_TXT).read_text(encoding="utf-8")


def test_cocuk_tum_secimleri_korur(depo):
    ayar = _ayar(**{"altyazi.mod": "word", "video.cq": 30})
    job_id = _is_olustur(depo, "failed", ayar=ayar)
    cocuk = depo.devam_iste(job_id, ["ses.hiz=1.1"])
    yeni = json.loads(depo.getir(cocuk)["settings_json"])
    assert {k: v for k, v in yeni.items() if k != "ses.hiz"} == {k: v for k, v in ayar.items() if k != "ses.hiz"}
    assert yeni["ses.hiz"] == 1.1


def test_ikinci_devam_istegi_ilki_bitmeden_reddedilir(depo):
    job_id = _is_olustur(depo, "failed")
    depo.devam_iste(job_id)
    with pytest.raises(IsHatasi, match="zaten bekleyen"):
        depo.devam_iste(job_id)


@pytest.mark.parametrize("bozma", ["sil", "bom", "baska_is", "baska_kaynak", "baska_kip", "gecersiz_json"])
def test_bozuk_ya_da_uyusmayan_manifest_reddedilir(depo, bozma):
    job_id = _is_olustur(depo, "failed")
    yol = Path(depo.getir(job_id)["run_dir"]) / "pipeline_state.json"
    veri = json.loads(yol.read_text(encoding="utf-8"))
    if bozma == "sil":
        yol.unlink()
    elif bozma == "bom":
        yol.write_bytes(b"\xef\xbb\xbf" + json.dumps(veri).encode())
    elif bozma == "gecersiz_json":
        yol.write_text("{", encoding="utf-8")
    else:
        anahtar = {"baska_is": "job_id", "baska_kaynak": "source_identity", "baska_kip": "pipeline_kind"}[bozma]
        veri[anahtar] = "baska"
        yol.write_text(json.dumps(veri), encoding="utf-8")
    assert depo.devam_secenekleri(depo.getir(job_id)) == []
    with pytest.raises(IsHatasi, match="manifest"):
        depo.devam_iste(job_id)


def test_cikti_koku_disindaki_ya_da_bos_klasor_kullanilmaz(depo, tmp_path):
    job_id = _is_olustur(depo, "failed")
    with sqlite3.connect(depo.db_yolu) as db:
        db.execute("UPDATE jobs SET run_dir=? WHERE job_id=?", (str(tmp_path / "dis_klasor"), job_id))
    assert not depo.manifest_gecerli(depo.getir(job_id))
    with sqlite3.connect(depo.db_yolu) as db:
        db.execute("UPDATE jobs SET run_dir='' WHERE job_id=?", (job_id,))
    assert not depo.manifest_gecerli(depo.getir(job_id))
    with pytest.raises(IsHatasi):
        depo.devam_iste(job_id)


def test_hazirlik_kuyruktan_sonra_degisen_manifesti_reddeder(depo):
    job_id = _is_olustur(depo, "failed")
    cocuk = depo.devam_iste(job_id)
    yol = Path(depo.getir(job_id)["run_dir"]) / "pipeline_state.json"
    veri = json.loads(yol.read_text(encoding="utf-8"))
    veri["updated_at"] = "2000-01-01T00:00:00Z"
    yol.write_text(json.dumps(veri), encoding="utf-8")
    assert depo.hazirlik_sahiplen(cocuk)
    with pytest.raises(IsHatasi, match="değişti"):
        depo.devam_hazirla(cocuk)
    assert depo.hazirlik_basarisiz(cocuk, "manifest değişti")
    assert depo.getir(cocuk)["failed_stage"] == "resume_preparation"


def _olu_pid() -> int:
    surec = subprocess.Popen([sys.executable, "-c", "pass"], creationflags=0x08000000 if os.name == "nt" else 0)
    surec.wait()
    return surec.pid


def test_acilista_yarim_isler_toparlanir_canli_surece_dokunulmaz(depo):
    yarim = _is_olustur(depo, "failed")
    cocuk = depo.devam_iste(yarim)
    assert depo.hazirlik_sahiplen(cocuk, pid=_olu_pid())
    isleniyor = depo.is_ekle(KAYNAK, _ayar(), "dubla", "test")
    assert depo.sahiplen(isleniyor, pid=_olu_pid())
    canli = depo.is_ekle(KAYNAK, _ayar(), "dubla", "test")
    assert depo.sahiplen(canli, pid=os.getpid())
    kurtarilan = {i["job_id"]: i["yeni_durum"] for i in depo.acilista_kurtar()}
    assert kurtarilan == {cocuk: "queued", isleniyor: "failed"}
    assert depo.getir(isleniyor)["failed_stage"] == "process_interrupted"
    assert depo.getir(canli)["status"] == "processing"


def test_bayat_is_iptali_yalniz_sureci_olmayan_eski_isi_kapatir(depo):
    eski = depo.is_ekle(KAYNAK, _ayar(), "dubla", "test")
    assert depo.sahiplen(eski, pid=_olu_pid())
    canli = depo.is_ekle(KAYNAK, _ayar(), "dubla", "test")
    assert depo.sahiplen(canli, pid=os.getpid())
    with sqlite3.connect(depo.db_yolu) as db:
        db.execute("UPDATE jobs SET started_at=datetime('now','-2 days')")
    assert depo.bayat_iptal(60) == 1
    assert depo.getir(eski)["status"] == "cancelled" and depo.getir(canli)["status"] == "processing"


def test_kuyruk_sirasi_esit_zamanda_is_numarasina_gore(depo):
    isler = [depo.is_ekle(KAYNAK, _ayar(), "dubla", "test") for _ in range(3)]
    with sqlite3.connect(depo.db_yolu) as db:
        db.execute("UPDATE jobs SET queued_at='2030-01-01 00:00:00'")
    assert [i["job_id"] for i in depo.kuyruk()] == isler
    assert depo.kuyruk_sirasi(isler[2]) == 3
    assert depo.siradaki()["job_id"] == isler[0]


def test_tek_yuva_sahiplenme_atomik(depo):
    a = depo.is_ekle(KAYNAK, _ayar(), "dubla", "test")
    b = depo.is_ekle(KAYNAK, _ayar(), "dubla", "test")
    assert depo.sahiplen(a, tek_yuva=True)
    assert not depo.sahiplen(b, tek_yuva=True)
    assert not depo.sahiplen(a, tek_yuva=True)  # zaten işleniyor
    depo.bitir(a, "completed")
    assert depo.sahiplen(b, tek_yuva=True)


def test_ertelenen_is_zamani_gelince_alinir(depo):
    job_id = depo.is_ekle(KAYNAK, _ayar(), "dubla", "test")
    assert depo.ertele(job_id, 3600, "gpu meşgul", "kaynak_mesgul")
    assert not depo.sahiplen(job_id)
    assert depo.siradaki() is None
    with sqlite3.connect(depo.db_yolu) as db:
        db.execute("UPDATE jobs SET retry_after_at=datetime('now','-1 minute')")
    assert depo.siradaki()["job_id"] == job_id
    assert depo.sahiplen(job_id)


def test_arsivleme_yalniz_kaydi_gizler_dosyaya_dokunmaz(depo):
    job_id = _is_olustur(depo, "completed", son_sira=17)
    klasor = Path(depo.getir(job_id)["run_dir"])
    assert depo.arsivle(job_id)
    assert job_id not in [i["job_id"] for i in depo.listele()]
    assert job_id in [i["job_id"] for i in depo.listele(arsiv_dahil=True)]
    assert klasor.is_dir() and (klasor / "pipeline_state.json").is_file()
    etkin = depo.is_ekle(KAYNAK, _ayar(), "dubla", "test")
    assert not depo.arsivle(etkin)


def test_soyagaci_ve_ozet_kisisel_veri_tasimaz(depo):
    job_id = _is_olustur(depo, "failed")
    soy = depo.soyagaci(job_id)
    assert soy["relationship"] == "fresh" and soy["evidence"]["source"] == "is_deposu/jobs"
    ozet = is_ozeti(depo.getir(job_id))
    assert ozet["kaynak_adi"] == "video-1" and ozet["basarisiz_asama_adi"] == "Ses seçimi"
    json.dumps(ozet)  # arayüzlere JSON olarak gider


def test_transkript_isi_devam_ettirilemez(depo):
    job_id = depo.is_ekle(KAYNAK, _ayar(), "transkript", "test", transkript_bicimi="srt")
    depo.bitir(job_id, "failed", "x")
    with pytest.raises(IsHatasi, match="yalnız dublaj"):
        depo.devam_iste(job_id)


def test_cli_isler_ve_sorunlu_calisir(tmp_path, monkeypatch, capsys):
    from dublaj_hatti import cli

    kok = tmp_path / "cikti"
    monkeypatch.delenv("DUBLAJ_IS_DEPOSU", raising=False)
    depo = IsDeposu(kok / "_is_deposu" / "isler.sqlite3", kok)
    job_id = _is_olustur(depo, "failed")
    assert cli.main(["isler", "--cikti", str(kok)]) == 0
    assert f"#{job_id}" in capsys.readouterr().out
    assert cli.main(["sorunlu", "--json", "--cikti", str(kok)]) == 0
    rapor = json.loads(capsys.readouterr().out)
    assert rapor[0]["is"] == job_id and rapor[0]["devam_secenekleri"][-1]["stage_id"] == "ceviri"
    assert cli.main(["isler", "--arsivle", str(job_id), "--cikti", str(kok)]) == 0


def test_cli_devam_ayni_ayar_degerini_degisiklik_saymaz(tmp_path, monkeypatch):
    from dublaj_hatti import cli
    from dublaj_hatti.is_yonetimi import calistirici, komutlar

    kok = tmp_path / "cikti"
    monkeypatch.delenv("DUBLAJ_IS_DEPOSU", raising=False)
    monkeypatch.setenv("DUBLAJ_LISANS_ONAY_DOSYASI", str(tmp_path / "lisans_onaylari.json"))  # devam lisans kapısı
    monkeypatch.setenv("DUBLAJ_LISANS_ONAY", "1")
    depo = IsDeposu(kok / "_is_deposu" / "isler.sqlite3", kok)
    job_id = _is_olustur(depo, "failed")
    cihaz = calistirici.is_ayari(depo.getir(job_id))["genel.cihaz"]
    calisan = []
    monkeypatch.setattr(komutlar, "isi_calistir", lambda d, j, o: calisan.append(j) or 0)
    assert cli.main(["devam", str(job_id), "--ayar", f"genel.cihaz={cihaz}", "--cikti", str(kok)]) == 0
    assert calisan == [job_id]  # yerinde devam: yeni iş açılmadı
    assert [i["job_id"] for i in depo.listele()] == [job_id]


def test_beklenmeyen_hata_isi_isleniyorda_asili_birakmaz(depo, monkeypatch):
    from dublaj_hatti.is_yonetimi import calistirici

    job_id = depo.is_ekle(KAYNAK, _ayar(), "dubla", "test")

    def patla(*_a, **_k):
        raise NameError("sentetik")

    monkeypatch.setattr(calistirici, "_hatti_kos", patla)
    with pytest.raises(NameError):
        calistirici.isi_calistir(depo, job_id, lambda _o: None)
    kayit = depo.getir(job_id)
    assert kayit["status"] == "failed" and "sentetik" in kayit["error_message"]
