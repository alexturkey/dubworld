"""Seslendirmeden önce gözden geçirme (arka yüz): `genel.gozden_gecir`, `inceleme_bekliyor` durumu, /api/duzenle,
/api/cevir_satir ve devam. GPU ve gerçek model yok: ağır adımlar sahte işlevlerle değiştirilir (test_tam_hat_devam deseni)."""

from __future__ import annotations

import http.client
import json
import threading
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

np = pytest.importorskip("numpy")
dubber_modulu = pytest.importorskip("dublaj_hatti.bolum_00_omurga.core.dubber")

from dublaj_hatti import web, yapilandirma  # noqa: E402
from dublaj_hatti.bolum_00_omurga.core.dubber import DubConfig  # noqa: E402
from dublaj_hatti.bolum_00_omurga.core.pipeline_checkpoint import (  # noqa: E402
    SEGMENT_SYNC_CHECKPOINT_STAGES,
    GozdenGecirmeBekleniyor,
    PipelineCheckpointError,
    PipelineCheckpointStore,
    ciktiyi_guncelle,
)
from dublaj_hatti.bolum_30_hizalama_ve_segment.nihai_dublaj_segmentleri import NihaiDublajSegmenti  # noqa: E402
from dublaj_hatti.bolum_50_seslendirme.tts_orkestratoru.service import TTSBuildResult  # noqa: E402
from dublaj_hatti.is_yonetimi import calistirici, inceleme  # noqa: E402
from dublaj_hatti.is_yonetimi.depo import IsDeposu, IsHatasi  # noqa: E402
from dublaj_hatti.is_yurutucu import IsYurutucu  # noqa: E402

KAYNAK = "https://example.test/v"
SATIRLAR = [
    {"index": 1, "start": 0.0, "end": 1.5, "text": "merhaba dünya", "original_source_text": "hello world",
     "speaker": "S0"},
    {"index": 2, "start": 2.0, "end": 4.25, "text": "nasılsın", "original_source_text": "how are you", "speaker": "S0"},
]


def _ayar(**ek):
    return {**yapilandirma.ayarlari_yukle(), **ek}


@pytest.fixture()
def depo(tmp_path, monkeypatch):
    monkeypatch.delenv("DUBLAJ_IS_DEPOSU", raising=False)
    kok = tmp_path / "cikti"
    kok.mkdir()
    return IsDeposu(kok / "_is_deposu" / "isler.sqlite3", kok)


def _inceleme_isi(depo: IsDeposu, kaynak: str = KAYNAK, durum: str = "inceleme_bekliyor") -> int:
    """Sentetik iş: çeviriye kadar tamamlanmış aşamalar (gerçek çeviri sonuç dosyasıyla), sonra inceleme bekliyor."""
    job_id = depo.is_ekle(kaynak, _ayar(**{"genel.gozden_gecir": True}), "dubla", "test")
    assert depo.sahiplen(job_id)
    run_dir = depo.cikti_koku / f"is_{job_id}"
    olaylar: list[dict] = []
    store = PipelineCheckpointStore(run_dir, "segment_sync", kaynak, job_id, event_callback=olaylar.append)
    for asama, sira, surum in SEGMENT_SYNC_CHECKPOINT_STAGES:
        if sira > 9:
            break
        dosya = run_dir / f"{sira:02d}_{asama}.json"
        dosya.parent.mkdir(parents=True, exist_ok=True)
        if asama == "konusmaci_yonlendirme":
            kaynak_seg = [{**s, "text": s["original_source_text"]} for s in SATIRLAR]
            for s in kaynak_seg:
                s.pop("original_source_text")
            veri = {"segments": kaynak_seg, "source_lang": "en", "alignment": {}}
        elif asama == "ceviri":
            veri = {"segments": SATIRLAR, "source_lang": "en", "alignment": {}}
        else:
            veri = {"asama": asama}
        dosya.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
        store.begin_stage(asama, sira, surum, {"asama": asama})
        yuk = {"result_path": dosya.name} if asama in ("konusmaci_yonlendirme", "ceviri") else {"dosya": dosya.name}
        store.complete_stage(asama, yuk, [dosya])
    for olay in olaylar:
        depo.boru_olayi(job_id, olay)
    if durum == "inceleme_bekliyor":
        assert depo.inceleme_bekle(job_id)
    else:
        depo.bitir(job_id, durum)
    return job_id


def _ceviri_dosyasi(depo: IsDeposu, job_id: int) -> Path:
    return depo.cikti_koku / f"is_{job_id}" / "09_ceviri.json"


def _geri_yuklenir(depo: IsDeposu, job_id: int, kaynak: str = KAYNAK) -> bool:
    store = PipelineCheckpointStore(depo.cikti_koku / f"is_{job_id}", "segment_sync", kaynak, job_id)
    return store.can_restore("ceviri", 9, 2, {"asama": "ceviri"})


# ---- ayar --------------------------------------------------------------------------------------------------------
def test_ayar_varsayilan_kapali_ve_dogrulanir():
    assert yapilandirma.SEMA["genel.gozden_gecir"] is bool
    assert yapilandirma.ayarlari_yukle()["genel.gozden_gecir"] is False
    assert yapilandirma.ayarlari_yukle(ustune=["genel.gozden_gecir=true"])["genel.gozden_gecir"] is True
    with pytest.raises(yapilandirma.AyarHatasi):
        yapilandirma.ayarlari_yukle(ustune=["genel.gozden_gecir=belki"])


def test_ayar_full_text_ile_celisir_transkriptte_uyari():
    bulgular = yapilandirma.uyumluluk_denetle(_ayar(**{"genel.gozden_gecir": True, "genel.dublaj_kipi": "full_text",
                                                      "ses.motor": "supertonic"}))
    assert any(b.seviye == "hata" and "genel.gozden_gecir" in b.anahtarlar for b in bulgular)
    bulgular = yapilandirma.uyumluluk_denetle(_ayar(**{"genel.gozden_gecir": True, "genel.is_turu": "transkript"}))
    assert any(b.seviye == "uyari" and "genel.gozden_gecir" in b.anahtarlar for b in bulgular)
    assert not [b for b in yapilandirma.uyumluluk_denetle(_ayar()) if "genel.gozden_gecir" in b.anahtarlar]


def test_ayar_tum_arayuz_dillerinde_aciklamali():
    from dublaj_hatti import arayuz_dili
    from dublaj_hatti.is_yurutucu import ayar_formu

    for dil in ("tr", "en"):
        alan = next(a for a in ayar_formu(dil) if a["anahtar"] == "genel.gozden_gecir")
        assert alan["tur"] == "evet_hayir" and alan["deger"] is False and alan["aciklama"]
    for anahtar in ("durum.inceleme_bekliyor", "ilerleme.inceleme_bekliyor", "anlati.inceleme_bekliyor"):
        assert all(arayuz_dili.sozluk(d).get(anahtar) for d in ("tr", "en"))


def test_ayar_degisimi_hicbir_asamayi_yeniden_calistirmaz():
    from dublaj_hatti.is_yonetimi.bagimlilik import ETKISIZ

    assert "genel.gozden_gecir" in ETKISIZ


# ---- hat: çeviriden sonra temiz durma + devam ----------------------------------------------------------------------
def _hat_yamalari(tmp_path, ilk_run_dir, sayac, tts_metinleri):
    def prepare_source(source, run_dir, logger=None):
        sayac["source"] += 1
        yol = Path(run_dir) / "video.mp4"
        yol.write_bytes(b"video")
        return str(yol), "Panel Video", "en"

    def extract_source(video_path, cfg, run_dir):
        yol = Path(run_dir) / "source_audio.wav"
        yol.write_bytes(b"audio")
        return str(yol)

    def transcribe(*args, **kwargs):
        sayac["transcription"] += 1
        kelimeler = [{"word": "hello", "start": 0.0, "end": 0.4}, {"word": "world", "start": 0.5, "end": 0.9}]
        ham = NihaiDublajSegmenti(index=0, start=0.0, end=0.9, text="hello world", words=kelimeler)
        return [ham], "en", {"segments": [{"start": 0.0, "end": 0.9, "text": "hello world", "words": kelimeler}]}

    class Translator:
        last_video_usage_report = ""

        def translate_segments(self, segments, run_dir):
            sayac["translation"] += 1
            return ["merhaba dünya" for _ in segments]

    def build_tts(segments, cfg, run_dir):
        sayac["tts"] += 1
        tts_metinleri.extend(s.text for s in segments)
        ses = np.zeros(2400, dtype=np.float32)
        return TTSBuildResult(audio=ses, timing_infos=[{"segment_index": 1, "tts_processed_duration": 0.1}],
                              segment_audios={1: ses})

    d = "dublaj_hatti.bolum_00_omurga.core.dubber."
    return (
        patch(d + "ensure_run_dir", return_value=str(ilk_run_dir)),
        patch(d + "prepare_source_video", side_effect=prepare_source),
        patch(d + "_extract_source_audio", side_effect=extract_source),
        patch(d + "_prepare_audio_for_asr_transcription", side_effect=lambda a, c, r: (a, 0.0)),
        patch(d + "transcribe_and_align", side_effect=transcribe),
        patch(d + "log_video_metadata"),
        patch(d + "write_transcripts"),
        patch(d + "write_full_paragraph"),
        patch(d + "write_word_level_transcript"),
        patch(d + "write_source_subtitle_preview", return_value={}),
        patch(d + "check_global_word_overlaps"),
        patch(d + "_create_segment_translator", side_effect=lambda *a, **k: Translator()),
        patch(d + "_apply_konusmaci_basina_ses_if_needed"),
        patch(d + "build_dubbed_audio", side_effect=build_tts),
        patch(d + "prepare_one_pass_subtitle_assets", side_effect=RuntimeError("tts sonrasi dur")),
    )


def test_ceviriden_sonra_durur_tts_calismaz_duzeltilmis_metinle_surer(tmp_path, monkeypatch, depo):
    kok = depo.cikti_koku
    monkeypatch.setenv("DUBLAJ_OUTPUT_DIR", str(kok))
    ilk = kok / "run_ornek"
    ilk.mkdir()
    sayac = {"source": 0, "transcription": 0, "translation": 0, "tts": 0}
    tts_metinleri: list[str] = []
    cfg = DubConfig(dubbing_mode="segment_sync", target_lang="tr", use_demucs=False, llm_backend="codex",
                    gozden_gecir=True)
    monkeypatch.setattr(calistirici, "is_ayari", lambda kayit: _ayar())
    monkeypatch.setattr(yapilandirma, "dubconfig_olustur",
                        lambda ayar, kaynak=None: (cfg, SimpleNamespace(cihaz="cpu", stt_motoru="faster-whisper")))
    monkeypatch.setattr("dublaj_hatti.lisans_onayi.kapi", lambda *a, **k: None)
    monkeypatch.setattr("dublaj_hatti.bolum_00_omurga.runtime.kaynak_kilidi.kaynak_kullan",
                        lambda *a, **k: nullcontext())
    job_id = depo.is_ekle(KAYNAK, _ayar(**{"genel.gozden_gecir": True}), "dubla", "test")
    olaylar: list[dict] = []
    with _tum(_hat_yamalari(tmp_path, ilk, sayac, tts_metinleri)):
        kod = calistirici.isi_calistir(depo, job_id, olaylar.append)
        # 1) çeviriden sonra temiz durdu: hata değil, TTS hiç çağrılmadı
        assert kod == calistirici.CIKIS_INCELEME
        kayit = depo.getir(job_id)
        assert kayit["status"] == "inceleme_bekliyor" and not kayit["error_message"]
        assert sayac == {"source": 1, "transcription": 1, "translation": 1, "tts": 0}
        assert any(o["event"] == "inceleme_bekliyor" for o in olaylar)
        assert not [o for o in olaylar if o["event"] == "hata"]
        store = PipelineCheckpointStore(Path(kayit["run_dir"]), "segment_sync", KAYNAK, job_id)
        assert store.state["stages"]["ceviri"]["status"] == "completed"
        assert "ses_yonlendirme" not in store.state["stages"]
        # 2) satır düzeltilir
        satirlar = inceleme.satirlari_oku(depo, job_id)["satirlar"]
        assert [s["ceviri"] for s in satirlar] == ["merhaba dünya"]
        assert inceleme.satirlari_kaydet(depo, job_id, [{"no": satirlar[0]["no"], "ceviri": "selam evren",
                                                         "orijinal": "hi universe"}])["degisen"] == 2
        # 3) devam: aynı iş, çeviri/transkripsiyon tekrarlanmaz, TTS düzeltilmiş metni okur
        olaylar.clear()
        yurutucu = IsYurutucu(depo=depo, kuyruk_isle=False)
        assert yurutucu.devam(job_id, asama="tts_ve_segment_sesleri") == job_id
        assert depo.getir(job_id)["status"] == "queued"
        assert calistirici.isi_calistir(depo, job_id, olaylar.append) == 1  # "tts sonrasi dur" sahte hatası
    assert sayac == {"source": 1, "transcription": 1, "translation": 1, "tts": 1}
    assert tts_metinleri == ["selam evren"]
    assert any(o["event"] == "stage_restored" and o["stage_id"] == "ceviri" for o in olaylar)
    assert not any(o["event"] == "inceleme_bekliyor" for o in olaylar)  # devamda tekrar durmaz
    bilingual = list(Path(depo.getir(job_id)["run_dir"]).glob("translated_segments_tr.txt"))
    assert bilingual and "hi universe" in bilingual[0].read_text(encoding="utf-8")


class _tum:
    def __init__(self, yamalar):
        self.yamalar = yamalar

    def __enter__(self):
        for y in self.yamalar:
            y.start()

    def __exit__(self, *a):
        for y in reversed(self.yamalar):
            y.stop()


def test_gozden_gecir_kapaliyken_durmaz(tmp_path, monkeypatch, depo):
    monkeypatch.setenv("DUBLAJ_OUTPUT_DIR", str(depo.cikti_koku))
    ilk = depo.cikti_koku / "run_ornek"
    ilk.mkdir()
    sayac = {"source": 0, "transcription": 0, "translation": 0, "tts": 0}
    cfg = DubConfig(dubbing_mode="segment_sync", target_lang="tr", use_demucs=False, llm_backend="codex")
    assert cfg.gozden_gecir is False
    with _tum(_hat_yamalari(tmp_path, ilk, sayac, [])):
        with pytest.raises(RuntimeError, match="tts sonrasi dur"):
            dubber_modulu.full_dub_pipeline(KAYNAK, str(depo.cikti_koku), cfg, {"codex_bridge_backend": "codex"})
    assert sayac["tts"] == 1


def test_bekleme_istisnasi_hata_sayilmaz_aktif_asama_bozulmaz(tmp_path, monkeypatch, depo):
    monkeypatch.setenv("DUBLAJ_OUTPUT_DIR", str(depo.cikti_koku))
    ilk = depo.cikti_koku / "run_ornek"
    ilk.mkdir()
    sayac = {"source": 0, "transcription": 0, "translation": 0, "tts": 0}
    cfg = DubConfig(dubbing_mode="segment_sync", target_lang="tr", use_demucs=False, llm_backend="codex",
                    gozden_gecir=True)
    with _tum(_hat_yamalari(tmp_path, ilk, sayac, [])):
        with pytest.raises(GozdenGecirmeBekleniyor) as bilgi:
            dubber_modulu.full_dub_pipeline(KAYNAK, str(depo.cikti_koku), cfg, {"codex_bridge_backend": "codex"})
    assert bilgi.value.stage_id == "ceviri"
    durum = json.loads((next(depo.cikti_koku.glob("panel_video_*")) / "pipeline_state.json").read_text("utf-8"))
    assert durum["failed_stage"] == "" and durum["stages"]["ceviri"]["status"] == "completed"
    assert not list(depo.cikti_koku.glob("panel_video_*/.pipeline_execution.lock"))  # kilit bırakıldı


# ---- depo / durumlar ----------------------------------------------------------------------------------------------
def test_durum_listede_ve_devam_secenekleri(depo):
    job_id = _inceleme_isi(depo)
    ozet = IsYurutucu(depo=depo, kuyruk_isle=False).isler()[0]
    assert ozet["is"] == job_id and ozet["durum"] == "inceleme_bekliyor" and ozet["durum_adi"]
    assert not ozet["hata"] and depo.siradaki() is None  # kuyruğu bloklamaz
    secenek = IsYurutucu(depo=depo, kuyruk_isle=False).secenekler(job_id)
    assert secenek["devam_secenekleri"][-1]["stage_id"] == "ceviri"


def test_devam_ceviriyi_yeniden_calistiran_asamada_yeni_ise_kopyalar(depo):
    job_id = _inceleme_isi(depo)
    yurutucu = IsYurutucu(depo=depo, kuyruk_isle=False)
    yeni = yurutucu.devam(job_id, asama="ceviri")
    assert yeni != job_id and depo.getir(yeni)["source_job_id"] == job_id
    assert depo.getir(job_id)["status"] == "inceleme_bekliyor"


def test_devam_kopyasi_duzeltilmis_dosyayi_ve_yenilenmis_ozeti_tasir(depo):
    job_id = _inceleme_isi(depo)
    inceleme.satirlari_kaydet(depo, job_id, [{"no": 1, "ceviri": "kopyalanan düzeltme"}])
    yeni = depo.devam_iste(job_id, asama="tts_ve_segment_sesleri", arayuz="test")
    assert depo.hazirlik_sahiplen(yeni)
    kopya = depo.devam_hazirla(yeni)
    veri = json.loads((kopya / "09_ceviri.json").read_text(encoding="utf-8"))
    assert veri["segments"][0]["text"] == "kopyalanan düzeltme"
    assert PipelineCheckpointStore(kopya, "segment_sync", KAYNAK, yeni).can_restore("ceviri", 9, 2, {"asama": "ceviri"})


def test_devam_yalniz_ayarsiz_ve_asamasiz_yerinde(depo):
    job_id = _inceleme_isi(depo)
    assert IsYurutucu(depo=depo, kuyruk_isle=False).devam(job_id) == job_id
    assert depo.getir(job_id)["status"] == "queued"
    with pytest.raises(IsHatasi):
        depo.yerinde_devam(job_id)  # artık beklemiyor


# ---- düzenleme: okuma / kaydetme ------------------------------------------------------------------------------------
def test_satirlari_oku(depo):
    job_id = _inceleme_isi(depo)
    veri = inceleme.satirlari_oku(depo, job_id)
    assert veri["durum"] == "inceleme_bekliyor" and veri["is"] == job_id
    assert veri["dil"] == {"kaynak": "en", "hedef": "tr"}
    assert veri["satirlar"][1] == {"no": 2, "bas": 2.0, "son": 4.25, "orijinal": "how are you",
                                   "ceviri": "nasılsın", "sure_sn": 2.25}


def test_kaydet_dosyayi_gunceller_ve_checkpoint_hala_gecerli(depo):
    job_id = _inceleme_isi(depo)
    assert _geri_yuklenir(depo, job_id)
    onceki = _ceviri_dosyasi(depo, job_id).stat().st_mtime_ns
    sonuc = inceleme.satirlari_kaydet(depo, job_id, [{"no": 2, "ceviri": "  nasıl   gidiyor \n"}])
    assert sonuc == {"tamam": True, "degisen": 1}
    veri = json.loads(_ceviri_dosyasi(depo, job_id).read_text(encoding="utf-8"))
    assert veri["segments"][1]["text"] == "nasıl gidiyor"  # boşluklar sadeleşir
    assert veri["segments"][0]["text"] == "merhaba dünya" and veri["segments"][1]["end"] == 4.25
    assert veri["segments"][1]["original_source_text"] == "how are you"
    assert _ceviri_dosyasi(depo, job_id).stat().st_mtime_ns >= onceki
    assert _geri_yuklenir(depo, job_id)  # doğrulama gevşemedi: özet yenilendi
    assert not list(_ceviri_dosyasi(depo, job_id).parent.glob(".09_ceviri.json.*.tmp"))
    assert inceleme.satirlari_oku(depo, job_id)["satirlar"][1]["ceviri"] == "nasıl gidiyor"


def test_dogrulama_gevsetilmedi_dis_mudahale_hala_yakalanir(depo):
    job_id = _inceleme_isi(depo)
    inceleme.satirlari_kaydet(depo, job_id, [{"no": 1, "ceviri": "bir"}])
    dosya = _ceviri_dosyasi(depo, job_id)
    dosya.write_text(dosya.read_text(encoding="utf-8").replace("bir", "iki"), encoding="utf-8")  # aynı boyut
    assert not _geri_yuklenir(depo, job_id)


def test_orijinal_duzeltmesi_ceviriyi_yeniden_tetiklemez(depo):
    job_id = _inceleme_isi(depo)
    run_dir = depo.cikti_koku / f"is_{job_id}"
    onceki = json.loads((run_dir / "pipeline_state.json").read_text(encoding="utf-8"))["stages"]["ceviri"]
    inceleme.satirlari_kaydet(depo, job_id, [{"no": 1, "orijinal": "hello there world"}])
    sonraki = json.loads((run_dir / "pipeline_state.json").read_text(encoding="utf-8"))["stages"]["ceviri"]
    assert sonraki["input_hash"] == onceki["input_hash"] and sonraki["inputs"] == onceki["inputs"]
    assert sonraki["artifacts"][0]["digest"] != onceki["artifacts"][0]["digest"]
    assert _geri_yuklenir(depo, job_id)
    assert inceleme.satirlari_oku(depo, job_id)["satirlar"][0]["orijinal"] == "hello there world"
    assert inceleme.satirlari_oku(depo, job_id)["satirlar"][0]["ceviri"] == "merhaba dünya"


@pytest.mark.parametrize("satirlar,anahtar", [
    ([], "satirlar_bos"),
    ("x", "satirlar_bos"),
    ([{"no": 99, "ceviri": "x"}], "satir_yok"),
    ([{"no": 1, "ceviri": "   "}], "metin_bos"),
    ([{"no": 1, "ceviri": "a" * 2001}], "metin_uzun"),
    ([{"no": 1, "orijinal": ""}], "metin_bos"),
    ([{"no": 1, "ceviri": 5}], "metin_gecersiz"),
    ([{"no": 1}], "satir_gecersiz"),
    ([{"no": "x", "ceviri": "a"}], "satir_gecersiz"),
    (["a"], "satir_gecersiz"),
    ([{"no": 1, "ceviri": "a"}, {"no": 1, "ceviri": "b"}], "satir_tekrar"),
    ([{"no": 1, "ceviri": "gecerli"}, {"no": 2, "ceviri": ""}], "metin_bos"),  # ya hepsi ya hiçbiri
])
def test_gecersiz_girdi_reddedilir_dosya_degismez(depo, satirlar, anahtar):
    job_id = _inceleme_isi(depo)
    once = _ceviri_dosyasi(depo, job_id).read_bytes()
    with pytest.raises(inceleme.InceleHatasi) as hata:
        inceleme.satirlari_kaydet(depo, job_id, satirlar)
    assert hata.value.anahtar == anahtar
    assert _ceviri_dosyasi(depo, job_id).read_bytes() == once and _geri_yuklenir(depo, job_id)


def test_2000_karakter_kabul_edilir(depo):
    job_id = _inceleme_isi(depo)
    assert inceleme.satirlari_kaydet(depo, job_id, [{"no": 1, "ceviri": "a" * 2000}])["degisen"] == 1


def test_yalniz_beklerken_duzenlenir(depo):
    bitti = _inceleme_isi(depo, durum="completed")
    with pytest.raises(inceleme.InceleHatasi) as hata:
        inceleme.satirlari_kaydet(depo, bitti, [{"no": 1, "ceviri": "x"}])
    assert hata.value.anahtar == "is_inceleme_degil" and hata.value.kod == 409
    assert inceleme.satirlari_oku(depo, bitti)["durum"] == "completed"  # okumak serbest


def test_devam_kuyrukta_iken_duzenlenemez(depo):
    job_id = _inceleme_isi(depo)
    depo.devam_iste(job_id, asama="tts_ve_segment_sesleri", arayuz="test")
    with pytest.raises(inceleme.InceleHatasi) as hata:
        inceleme.satirlari_kaydet(depo, job_id, [{"no": 1, "ceviri": "x"}])
    assert hata.value.anahtar == "devam_kuyrukta"


# ---- yol kaçışı --------------------------------------------------------------------------------------------------
def test_klasor_cikti_kokunun_disindaysa_reddedilir(depo, tmp_path):
    job_id = _inceleme_isi(depo)
    disari = tmp_path / "disari"
    disari.mkdir()
    (disari / "pipeline_state.json").write_text("{}", encoding="utf-8")
    with depo._baglan(yazma=True) as db:
        db.execute("UPDATE jobs SET run_dir=? WHERE job_id=?", (str(disari), job_id))
    for islem in (lambda: inceleme.satirlari_oku(depo, job_id),
                  lambda: inceleme.satirlari_kaydet(depo, job_id, [{"no": 1, "ceviri": "x"}]),
                  lambda: inceleme.satiri_cevir(depo, job_id, 1, "x")):
        with pytest.raises(inceleme.InceleHatasi) as hata:
            islem()
        assert hata.value.anahtar == "klasor_yok" and hata.value.kod == 404


def test_sonuc_dosyasi_yolu_klasorden_cikamaz(depo, tmp_path):
    job_id = _inceleme_isi(depo)
    run_dir = depo.cikti_koku / f"is_{job_id}"
    disari = tmp_path / "gizli.json"
    disari.write_text(json.dumps({"segments": [{"index": 1, "text": "sızıntı"}], "source_lang": "en"}), encoding="utf-8")
    durum_yolu = run_dir / "pipeline_state.json"
    durum = json.loads(durum_yolu.read_text(encoding="utf-8"))
    durum["stages"]["ceviri"]["payload"]["result_path"] = "../../../gizli.json"
    durum_yolu.write_text(json.dumps(durum), encoding="utf-8")
    with pytest.raises(inceleme.InceleHatasi) as hata:
        inceleme.satirlari_oku(depo, job_id)
    assert hata.value.anahtar == "ceviri_yok"


def test_ciktiyi_guncelle_yalniz_kayitli_cikti_ve_klasor_icinde(depo, tmp_path):
    job_id = _inceleme_isi(depo)
    run_dir = depo.cikti_koku / f"is_{job_id}"
    with pytest.raises(PipelineCheckpointError, match="disinda"):
        ciktiyi_guncelle(run_dir, "ceviri", tmp_path / "baska.json", b"{}")
    with pytest.raises(PipelineCheckpointError, match="kayitli ciktisi degil"):
        ciktiyi_guncelle(run_dir, "ceviri", run_dir / "08_konusmaci_yonlendirme.json", b"{}")
    with pytest.raises(PipelineCheckpointError, match="Tamamlanmis asama"):
        ciktiyi_guncelle(run_dir, "tts_ve_segment_sesleri", run_dir / "09_ceviri.json", b"{}")
    assert _geri_yuklenir(depo, job_id)


def test_ciktiyi_guncelle_calisan_hatta_kilit_varken_reddedilir(depo):
    import os

    job_id = _inceleme_isi(depo)
    run_dir = depo.cikti_koku / f"is_{job_id}"
    (run_dir / ".pipeline_execution.lock").write_text(json.dumps({"pid": os.getpid(), "token": "t"}), encoding="utf-8")
    with pytest.raises(PipelineCheckpointError, match="calisiyor"):
        ciktiyi_guncelle(run_dir, "ceviri", run_dir / "09_ceviri.json", b"{}")


# ---- tek satır çevirme -------------------------------------------------------------------------------------------
class _SahteCevirmen:
    gelenler: list = []

    def translate_segments(self, segments, run_dir):
        _SahteCevirmen.gelenler.append(([s.text for s in segments], Path(run_dir).is_dir()))
        return ["  yeni   çeviri "]


def _sahte_cevirmen(monkeypatch, motor="codex_bridge", kayit=None):
    _SahteCevirmen.gelenler = []
    cfg = DubConfig(translator_engine=motor, target_lang="tr", device="cuda")
    monkeypatch.setattr(calistirici, "is_ayari", lambda k: _ayar())
    monkeypatch.setattr(yapilandirma, "dubconfig_olustur", lambda a, kaynak=None: (cfg, SimpleNamespace()))
    monkeypatch.setattr("dublaj_hatti.bolum_00_omurga.core.dubber._create_segment_translator",
                        lambda c, m, kaynak_dil: _SahteCevirmen())
    return cfg


def test_cevir_satir_kaydetmeden_ceviri_dondurur(depo, monkeypatch):
    job_id = _inceleme_isi(depo)
    _sahte_cevirmen(monkeypatch)
    once = _ceviri_dosyasi(depo, job_id).read_bytes()
    assert inceleme.satiri_cevir(depo, job_id, 1, "hello again") == {"ceviri": "yeni çeviri"}
    assert _SahteCevirmen.gelenler == [(["hello again"], True)]
    assert _ceviri_dosyasi(depo, job_id).read_bytes() == once  # kaydetmez
    assert not list((depo.cikti_koku / f"is_{job_id}").glob(".cevir_satir_*"))  # geçici klasör temizlendi


def test_cevir_satir_yerel_motor_islemcide_calisir(depo, monkeypatch):
    job_id = _inceleme_isi(depo)
    cfg = _sahte_cevirmen(monkeypatch, motor="yerel")
    inceleme.satiri_cevir(depo, job_id, 2, "x")
    assert cfg.device == "cpu"


def test_cevir_satir_desteklenmeyen_arka_uc_ve_hatalar(depo, monkeypatch):
    job_id = _inceleme_isi(depo)
    _sahte_cevirmen(monkeypatch, motor="bilinmeyen")
    with pytest.raises(inceleme.InceleHatasi) as hata:
        inceleme.satiri_cevir(depo, job_id, 1, "x")
    assert hata.value.anahtar == "tek_satir_desteklenmiyor"
    _sahte_cevirmen(monkeypatch)
    for no, metin, anahtar in ((99, "x", "satir_yok"), (1, "", "metin_bos"), (1, "a" * 2001, "metin_uzun"),
                               ("x", "x", "satir_gecersiz")):
        with pytest.raises(inceleme.InceleHatasi) as hata:
            inceleme.satiri_cevir(depo, job_id, no, metin)
        assert hata.value.anahtar == anahtar

    class Patlayan:
        def translate_segments(self, segments, run_dir):
            raise ConnectionError("ağ yok")

    monkeypatch.setattr("dublaj_hatti.bolum_00_omurga.core.dubber._create_segment_translator",
                        lambda c, m, kaynak_dil: Patlayan())
    with pytest.raises(inceleme.InceleHatasi) as hata:
        inceleme.satiri_cevir(depo, job_id, 1, "x")
    assert hata.value.anahtar == "ceviri_basarisiz" and "ağ yok" in str(hata.value)


# ---- web ----------------------------------------------------------------------------------------------------------
@pytest.fixture()
def sunucu(tmp_path, monkeypatch):
    monkeypatch.delenv("DUBLAJ_IS_DEPOSU", raising=False)
    kok = tmp_path / "cikti"
    kok.mkdir()
    monkeypatch.setattr(web, "cikti_koku", lambda: kok)
    monkeypatch.setattr("dublaj_hatti.is_yurutucu.IsYurutucu.__init__.__defaults__", ("gui", None, False))
    s = web.Sunucu(("127.0.0.1", 0), web.Isleyici)
    port = s.server_address[1]
    uygulama = web.Uygulama(port, 1)
    web.Isleyici.uygulama = uygulama
    threading.Thread(target=s.serve_forever, daemon=True).start()

    def iste(yontem, yol, govde=None, basliklar=None):
        baglanti = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        baglanti.request(yontem, yol, json.dumps(govde) if govde is not None else None,
                         {"Host": f"127.0.0.1:{port}", **(basliklar or {})})
        yanit = yanit_ = baglanti.getresponse()
        ham = yanit_.read()
        try:
            return yanit.status, json.loads(ham or b"{}")
        except ValueError:
            return yanit.status, {"ham": ham.decode("utf-8", "replace")}

    api = {"Cookie": f"{web.CEREZ}={uygulama.belirtec}", "X-Dublaj-Belirtec": uygulama.belirtec,
           "Content-Type": "application/json"}
    yield iste, api, uygulama.yurutucu.depo
    s.shutdown()
    s.server_close()


def test_web_uclari_oturum_ve_belirtec_ister(sunucu):
    iste, api, depo = sunucu
    job_id = _inceleme_isi(depo)
    cerezsiz = {"Content-Type": "application/json"}
    once = _ceviri_dosyasi(depo, job_id).read_bytes()
    assert iste("GET", f"/api/duzenle?is={job_id}")[0] == 403
    assert iste("POST", "/api/duzenle", {"is": job_id, "satirlar": [{"no": 1, "ceviri": "x"}]}, cerezsiz)[0] == 403
    assert iste("POST", "/api/cevir_satir", {"is": job_id, "no": 1, "metin": "x"}, cerezsiz)[0] == 403
    yalniz_cerez = {"Cookie": api["Cookie"], "Content-Type": "application/json"}  # X-Dublaj-Belirtec yok
    assert iste("POST", "/api/duzenle", {"is": job_id, "satirlar": [{"no": 1, "ceviri": "x"}]}, yalniz_cerez)[0] == 403
    assert iste("POST", "/api/duzenle", {"is": job_id, "satirlar": [{"no": 1, "ceviri": "x"}]},
                {**api, "Origin": "http://saldirgan.example"})[0] == 403
    assert _ceviri_dosyasi(depo, job_id).read_bytes() == once  # hiçbiri dosyayı değiştirmedi


def test_web_get_ve_post_duzenle(sunucu):
    iste, api, depo = sunucu
    job_id = _inceleme_isi(depo)
    kod, veri = iste("GET", f"/api/duzenle?is={job_id}", basliklar=api)
    assert kod == 200 and veri["durum"] == "inceleme_bekliyor" and len(veri["satirlar"]) == 2
    assert set(veri["satirlar"][0]) == {"no", "bas", "son", "orijinal", "ceviri", "sure_sn"}
    assert veri["dil"] == {"kaynak": "en", "hedef": "tr"}
    kod, veri = iste("POST", "/api/duzenle", {"is": job_id, "satirlar": [{"no": 1, "ceviri": "web düzeltmesi"}]}, api)
    assert kod == 200 and veri == {"tamam": True, "degisen": 1}
    assert iste("GET", f"/api/duzenle?is={job_id}", basliklar=api)[1]["satirlar"][0]["ceviri"] == "web düzeltmesi"
    assert _geri_yuklenir(depo, job_id)
    kod, veri = iste("GET", "/api/isler", basliklar=api)
    assert [o["durum"] for o in veri["isler"] if o["is"] == job_id] == ["inceleme_bekliyor"]


def test_web_hata_kodlari(sunucu):
    iste, api, depo = sunucu
    job_id = _inceleme_isi(depo)
    bitti = _inceleme_isi(depo, durum="completed")
    kod, veri = iste("POST", "/api/duzenle", {"is": job_id, "satirlar": [{"no": 1, "ceviri": ""}]}, api)
    assert kod == 400 and veri["anahtar"] == "metin_bos"
    kod, veri = iste("POST", "/api/duzenle", {"is": job_id, "satirlar": [{"no": 7, "ceviri": "x"}]}, api)
    assert kod == 404 and veri["anahtar"] == "satir_yok"
    kod, veri = iste("POST", "/api/duzenle", {"is": bitti, "satirlar": [{"no": 1, "ceviri": "x"}]}, api)
    assert kod == 409 and veri["anahtar"] == "is_inceleme_degil"
    assert iste("POST", "/api/duzenle", {"is": 9999, "satirlar": [{"no": 1, "ceviri": "x"}]}, api)[0] == 404
    assert iste("POST", "/api/duzenle", {"is": True, "satirlar": []}, api)[0] == 400
    assert iste("POST", "/api/duzenle", {"is": "abc", "satirlar": []}, api)[0] == 400
    assert iste("POST", "/api/cevir_satir", {"is": job_id, "no": 99, "metin": "x"}, api)[0] == 404


def test_web_yol_kacisi_ve_gecersiz_is_numarasi(sunucu, tmp_path):
    iste, api, depo = sunucu
    _inceleme_isi(depo)
    for kotu in ("..%2F..%2Fetc", "1;DROP", "../1", "%00", "", "1e3", "0x1"):
        assert iste("GET", f"/api/duzenle?is={kotu}", basliklar=api)[0] == 400, kotu
    assert iste("GET", "/api/duzenle", basliklar=api)[0] == 400
    # iş klasörü kök dışına işaret ederse sızmaz
    job_id = _inceleme_isi(depo)
    disari = tmp_path / "disari"
    disari.mkdir()
    (disari / "pipeline_state.json").write_text("{}", encoding="utf-8")
    with depo._baglan(yazma=True) as db:
        db.execute("UPDATE jobs SET run_dir=? WHERE job_id=?", (str(disari), job_id))
    kod, veri = iste("GET", f"/api/duzenle?is={job_id}", basliklar=api)
    assert kod == 404 and veri["anahtar"] == "klasor_yok"
    # istek gövdesindeki ek alanlar (yol vb.) yok sayılır: yalnız no/orijinal/ceviri okunur
    kod, _ = iste("POST", "/api/duzenle", {"is": job_id, "yol": "../x", "satirlar": [{"no": 1, "ceviri": "x"}]}, api)
    assert kod == 404


def test_web_cevir_satir(sunucu, monkeypatch):
    iste, api, depo = sunucu
    job_id = _inceleme_isi(depo)
    _sahte_cevirmen(monkeypatch)
    kod, veri = iste("POST", "/api/cevir_satir", {"is": job_id, "no": 1, "metin": "hello"}, api)
    assert kod == 200 and veri == {"ceviri": "yeni çeviri"}
    assert iste("GET", f"/api/duzenle?is={job_id}", basliklar=api)[1]["satirlar"][0]["ceviri"] == "merhaba dünya"
    _sahte_cevirmen(monkeypatch, motor="bilinmeyen")
    kod, veri = iste("POST", "/api/cevir_satir", {"is": job_id, "no": 1, "metin": "hello"}, api)
    assert kod == 409 and veri["anahtar"] == "tek_satir_desteklenmiyor"


def test_web_devam_inceleme_isini_seslendirmeden_surdurur(sunucu):
    iste, api, depo = sunucu
    job_id = _inceleme_isi(depo)
    kod, veri = iste("POST", "/api/devam", {"is": job_id, "asama": "tts_ve_segment_sesleri"}, api)
    assert kod == 200 and veri["is"] == job_id
    assert depo.getir(job_id)["status"] == "queued"
    kod, veri = iste("POST", "/api/duzenle", {"is": job_id, "satirlar": [{"no": 1, "ceviri": "gec"}]}, api)
    assert kod == 409 and veri["anahtar"] == "is_inceleme_degil"


def test_cok_satirli_buyuk_istek_kabul_edilir(sunucu):
    iste, api, depo = sunucu
    job_id = _inceleme_isi(depo)
    govde = {"is": job_id, "satirlar": [{"no": 1, "ceviri": "a" * 2000}, {"no": 2, "orijinal": "b" * 2000}] * 0
             + [{"no": 1, "ceviri": "a" * 2000, "orijinal": "b" * 2000}]}
    assert len(json.dumps(govde)) < web.DUZENLE_JSON_SINIRI
    assert iste("POST", "/api/duzenle", govde, api)[0] == 200
    cok = {"is": job_id, "satirlar": [{"no": 1, "ceviri": "x" * 2000}] * 700}
    try:
        assert iste("POST", "/api/duzenle", cok, api)[0] == 400  # 1 MB sınırı (sunucu gövdeyi okumadan reddeder)
    except OSError:
        pass  # gövde okunmadan bağlantı kapatıldı: istemci yazarken kopma da ret demektir
    assert _ceviri_dosyasi(depo, job_id).stat().st_size < 20000
