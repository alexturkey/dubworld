"""Sabit değer koruması: kritik sabitler kaynaktan okunur (içe aktarma yok, model yok, GPU yok).

Bir değer değişirse test düşer ve docs/engineering/pinned-values.md içindeki gerekçeye yönlendirir. Değeri bilerek
değiştiriyorsan: o satırdaki ölçümü yeniden yap, belgeyi (EN + TR) ve buradaki beklenen değeri aynı değişiklikte güncelle.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
PAKET = KOK / "src" / "dublaj_hatti"
BELGE = "docs/engineering/pinned-values.md"
BELGE_TR = "docs/muhendislik/sabit_degerler.md"

# (dosya, sabit adı, beklenen değer, belge bölümü)
SABITLER = [
    ("bolum_50_seslendirme/supertonic_tts/speed_policy.py", "SUPERTONIC_VOICE_SPEEDS",
     {"F1": 1.30, "F2": 1.15, "F3": 1.30, "F4": 1.00, "F5": 1.15,
      "M1": 1.15, "M2": 1.00, "M3": 1.00, "M4": 1.15, "M5": 1.25}, "supertonic-voices"),
    ("bolum_50_seslendirme/supertonic_tts/speed_policy.py", "DEFAULT_SUPERTONIC_VOICE_ID", "F1", "supertonic-voices"),
    ("bolum_50_seslendirme/supertonic_tts/konusmaci_secimi/voice_assignment.py", "FEMALE_VOICE_POOL",
     ["F1", "F2", "F3", "F4", "F5"], "supertonic-voices"),
    ("bolum_50_seslendirme/supertonic_tts/konusmaci_secimi/voice_assignment.py", "MALE_VOICE_POOL",
     ["M1", "M2", "M3", "M4", "M5"], "supertonic-voices"),
    ("bolum_50_seslendirme/supertonic_tts/synthesis_profile.py", "SUPERTONIC_SYNTHESIS_CONTRACT",
     "supertonic_k15_cfg5_7plus3_silence_v2", "supertonic-synthesis"),
    ("bolum_50_seslendirme/supertonic_tts/synthesis_profile.py", "SUPERTONIC_TOTAL_STEPS", 10, "supertonic-synthesis"),
    ("bolum_50_seslendirme/supertonic_tts/synthesis_profile.py", "SUPERTONIC_TRANSITION_STEP", 7, "supertonic-synthesis"),
    ("bolum_50_seslendirme/supertonic_tts/synthesis_profile.py", "SUPERTONIC_CFG_SCALE", 5.0, "supertonic-synthesis"),
    ("bolum_50_seslendirme/supertonic_tts/silence_cleanup.py", "CANDIDATE_BELOW_PEAK_DB", 20.0, "supertonic-synthesis"),
    ("bolum_50_seslendirme/supertonic_tts/silence_cleanup.py", "NOTE_SILENT_MAX_DB", -95.0, "supertonic-synthesis"),
    ("bolum_50_seslendirme/supertonic_tts/silence_cleanup.py", "NOTE_SPEECH_MIN_DB", -50.0, "supertonic-synthesis"),
    ("bolum_50_seslendirme/supertonic_tts/final_audio_profile.py", "SUPERTONIC_TARGET_LUFS", -18.0, "supertonic-synthesis"),
    ("bolum_50_seslendirme/supertonic_tts/final_audio_profile.py", "SUPERTONIC_TRUE_PEAK_CEILING", -1.3,
     "supertonic-synthesis"),
    ("bolum_50_seslendirme/supertonic_tts/parallel.py", "SUPERTONIC_PARALLEL_LANES", 4, "supertonic-synthesis"),
    ("bolum_50_seslendirme/supertonic_tts/parallel.py", "SUPERTONIC_PARALLEL_INTRA_OP_THREADS", 2,
     "supertonic-synthesis"),
    ("bolum_50_seslendirme/supertonic_tts/parallel.py", "SUPERTONIC_DIRECT_INTRA_OP_THREADS", 3, "supertonic-synthesis"),
    ("bolum_50_seslendirme/supertonic_tts/atempo_sure_uyumu/policy.py", "SUPERTONIC_ATEMPO_MIN_FACTOR", 0.90,
     "duration-matching"),
    ("bolum_50_seslendirme/supertonic_tts/atempo_sure_uyumu/policy.py", "SUPERTONIC_ATEMPO_MAX_FACTOR", 1.25,
     "duration-matching"),
    ("bolum_50_seslendirme/tts_orkestratoru/service.py", "REAL_TTS_MIN_VIDEO_SPEED", 0.90, "duration-matching"),
    ("bolum_50_seslendirme/tts_orkestratoru/service.py", "REAL_TTS_MAX_VIDEO_SPEED", 1.15, "duration-matching"),
    ("bolum_50_seslendirme/candidate_alignment/aligner.py", "ALIGNMENT_START_BOUNDARY_TOLERANCE_SECONDS", 0.005,
     "duration-matching"),
    ("bolum_50_seslendirme/candidate_alignment/aligner.py", "ALIGNMENT_END_BOUNDARY_TOLERANCE_SECONDS", 0.025,
     "duration-matching"),
    ("bolum_50_seslendirme/supertonic_tts/candidate_lanes.py", "LONG_CANDIDATE_LANE_ALIGNMENT_SECONDS", 30.0,
     "duration-matching"),
    ("bolum_00_omurga/core/dubber.py", "SUPERTONIC_NATIVE_SAMPLE_RATE", 44100, "sample-rates-and-other-tts-engines"),
    ("bolum_50_seslendirme/supertonic_tts/cinsiyet_secimi/gender_classifier.py", "MODEL_REVISION",
     "7a28165f33e1dbb37adbce09c0a9afcd6095dd4d", "speakers-and-gender"),
    ("bolum_40_ceviri/llm_kopru/scripts/bridge_worker.py", "FULL_TEXT_HIGH_REASONING_WORD_THRESHOLD", 6000,
     "translation"),
    ("bolum_40_ceviri/claude_code_cli/scripts/bridge_worker.py", "FULL_TEXT_HIGH_EFFORT_WORD_THRESHOLD", 6000,
     "translation"),
    ("bolum_40_ceviri/llm_kopru/scripts/natural_blocks_chain_contract.py", "NATURAL_BLOCKS_COVERAGE_MIN_SOURCE_WORDS", 8,
     "translation"),
    ("bolum_40_ceviri/llm_kopru/scripts/natural_blocks_chain_contract.py", "NATURAL_BLOCKS_COVERAGE_RATIO_DENOMINATOR", 4,
     "translation"),
    ("bolum_40_ceviri/claude_code_cli/scripts/natural_blocks_chain_contract.py",
     "NATURAL_BLOCKS_COVERAGE_MIN_SOURCE_WORDS", 8, "translation"),
    ("bolum_40_ceviri/claude_code_cli/scripts/natural_blocks_chain_contract.py",
     "NATURAL_BLOCKS_COVERAGE_RATIO_DENOMINATOR", 4, "translation"),
    ("bolum_40_ceviri/bridge_motor_orkestratoru/quality.py", "SOURCE_LIKE_SIMILARITY_THRESHOLD", 0.90, "translation"),
    ("bolum_00_omurga/core/dubber.py", "ASR_LEADING_PAD_SECONDS", 1.0, "transcription"),
    ("bolum_20_transkripsiyon/whisperx_motoru/worker.py", "CUDA_TRANSCRIBE_BATCH_SIZE", 1, "transcription"),
    ("bolum_20_transkripsiyon/parakeet_cpu_align_motoru/worker.py", "PARAKEET_TECHNICAL_MAX_SECONDS", 400.0,
     "transcription"),
    ("bolum_20_transkripsiyon/parakeet_cpu_align_motoru/worker.py", "PARAKEET_OPERATIONAL_MAX_SECONDS", 399.0,
     "transcription"),
    ("bolum_20_transkripsiyon/parakeet_cpu_align_motoru/worker.py", "ALIGNMENT_NATURAL_GAP_SECONDS", 1.0,
     "transcription"),
    ("bolum_20_transkripsiyon/parakeet_cpu_align_motoru/worker.py", "PARAKEET_TIMESTAMP_FRAME_SECONDS", 0.08,
     "transcription"),
    ("bolum_20_transkripsiyon/parakeet_cpu_align_motoru/worker.py", "PARAKEET_MAX_ACTIVE_PATHS", 4, "transcription"),
    ("bolum_20_transkripsiyon/parakeet_cpu_align_motoru/worker.py", "PARAKEET_BLANK_PENALTY", 2.0, "transcription"),
    ("bolum_00_omurga/runtime/crisperwhisper_turbo_ct2_runtime.py", "SHARED_ALIGNMENT_SILENCE_LIMIT_SECONDS", 1.5,
     "transcription"),
    ("bolum_00_omurga/runtime/crisperwhisper_turbo_ct2_runtime.py", "SHARED_ALIGNMENT_RAW_SILENCE_LIMIT_SECONDS", 0.5,
     "transcription"),
    ("bolum_30_hizalama_ve_segment/ctc_kelime_hizalama/ctc_konusma_siniri.py", "SPEECH_PAD_SECONDS", 0.15,
     "word-alignment"),
    ("bolum_30_hizalama_ve_segment/ctc_kelime_hizalama/ctc_konusma_siniri.py", "RAW_SILENCE_LEVEL_RATIO", 0.35,
     "word-alignment"),
    ("bolum_30_hizalama_ve_segment/ctc_kelime_hizalama/ctc_konusma_siniri.py", "RAW_SILENCE_MINIMUM_CONTRAST_DB", 6.0,
     "word-alignment"),
    ("bolum_30_hizalama_ve_segment/nihai_dublaj_segmentleri.py", "BOSLUK_ESIGI_SANIYE", 1.0, "dub-segmentation"),
    ("bolum_30_hizalama_ve_segment/nihai_dublaj_segmentleri.py", "MAKSIMUM_KELIME_SAYISI", 150, "dub-segmentation"),
    ("bolum_30_hizalama_ve_segment/nihai_dublaj_segmentleri.py", "NOKTALAMA_ONCELIGI", (".", "?", "!", ","),
     "dub-segmentation"),
    ("bolum_00_omurga/core/dubber.py", "DEMUCS_MODEL_NAME", "htdemucs", "source-audio-and-separation"),
    ("bolum_10_kaynak_edinme/adim_50_asr_sesi_hazirlama/demucs_cleaner.py", "CUDA_BATCH_SIZE", 4,
     "source-audio-and-separation"),
    ("bolum_10_kaynak_edinme/adim_50_asr_sesi_hazirlama/demucs_cleaner.py", "CUDA_BATCH_OVERLAP", 0.25,
     "source-audio-and-separation"),
    ("bolum_10_kaynak_edinme/adim_50_asr_sesi_hazirlama/arka_plan_sesi_olcumu.py", "DYNAMIC_RANGE_THRESHOLD_DB", 32.0,
     "source-audio-and-separation"),
    ("bolum_10_kaynak_edinme/adim_50_asr_sesi_hazirlama/arka_plan_sesi_olcumu.py", "SILENT_AUDIO_PEAK_DB", -60.0,
     "source-audio-and-separation"),
]

# (anahtar yolu, beklenen, belge bölümü) — paketteki varsayılan ayar dosyası
AYARLAR = [
    (("ses", "supertonic_ses"), "F1", "supertonic-voices"),
    (("ses", "akis"), "natural_blocks_1", "translation"),
    (("ses", "hiz"), 1.2, "duration-matching"),
    (("video", "cq"), 26, "video-and-output"),
    (("video", "yapay_zeka_etiketi"), True, "video-and-output"),
]


def _mesaj(yer: str, gercek, beklenen, bolum: str) -> str:
    return (f"{yer} = {gercek!r}, beklenen {beklenen!r}. Bu sabit bilerek seçildi: önce {BELGE}#{bolum} "
            f"(TR: {BELGE_TR}) gerekçesini oku; değiştiriyorsan ölçümü yeniden yap, belgeyi ve bu testi birlikte güncelle.")


def _sabit_oku(dosya: Path, ad: str):
    agac = ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))
    for dugum in agac.body:
        hedefler = []
        if isinstance(dugum, ast.Assign):
            hedefler = [h.id for h in dugum.targets if isinstance(h, ast.Name)]
        elif isinstance(dugum, ast.AnnAssign) and isinstance(dugum.target, ast.Name) and dugum.value is not None:
            hedefler = [dugum.target.id]
        if ad in hedefler:
            deger = dugum.value
            # MappingProxyType({...}) gibi tek argümanlı sarmalayıcı
            if isinstance(deger, ast.Call) and len(deger.args) == 1 and not deger.keywords:
                deger = deger.args[0]
            return ast.literal_eval(deger)
    raise AssertionError(f"{dosya.relative_to(KOK)}: {ad} modül düzeyinde bulunamadı ({BELGE} satırını güncelle)")


def _baslik_capalari(belge: Path) -> set[str]:
    capalar = set()
    for satir in belge.read_text(encoding="utf-8").splitlines():
        if satir.startswith("## "):
            metin = satir[3:].strip().lower()
            capalar.add(re.sub(r"[^\w\- ]", "", metin).replace(" ", "-"))
    return capalar


@pytest.mark.parametrize("dosya,ad,beklenen,bolum", SABITLER, ids=[f"{a}" for _, a, _, _ in SABITLER])
def test_kritik_sabit_degismedi(dosya, ad, beklenen, bolum):
    gercek = _sabit_oku(PAKET / dosya, ad)
    if isinstance(beklenen, float) or (isinstance(beklenen, dict) and beklenen
                                       and isinstance(next(iter(beklenen.values())), float)):
        assert gercek == pytest.approx(beklenen), _mesaj(f"{dosya}:{ad}", gercek, beklenen, bolum)
    else:
        assert gercek == beklenen, _mesaj(f"{dosya}:{ad}", gercek, beklenen, bolum)


@pytest.mark.parametrize("yol,beklenen,bolum", AYARLAR, ids=[".".join(y) for y, _, _ in AYARLAR])
def test_varsayilan_ayar_degismedi(yol, beklenen, bolum):
    tomllib = pytest.importorskip("tomllib")
    ayar = tomllib.loads((PAKET / "varsayilan.toml").read_text(encoding="utf-8"))
    for parca in yol:
        ayar = ayar[parca]
    assert ayar == beklenen, _mesaj("varsayilan.toml:" + ".".join(yol), ayar, beklenen, bolum)


def test_video_kodlayici_varsayilanlari():
    """VideoProcessOptions içindeki CQ ve NVENC ön ayarı (sınıf alanı, modül sabiti değil)."""
    dosya = PAKET / "bolum_60_video_ve_encode/timeline_ve_final_encode/video_processor.py"
    agac = ast.parse(dosya.read_text(encoding="utf-8"))
    alanlar = {}
    for dugum in agac.body:
        if isinstance(dugum, ast.ClassDef) and dugum.name == "VideoProcessOptions":
            for alan in dugum.body:
                if isinstance(alan, ast.AnnAssign) and isinstance(alan.target, ast.Name) and alan.value is not None:
                    alanlar[alan.target.id] = ast.literal_eval(alan.value)
    for ad, beklenen in (("encoder_cq", "26"), ("encoder_preset", "p2")):
        assert alanlar.get(ad) == beklenen, _mesaj(f"video_processor.py:VideoProcessOptions.{ad}", alanlar.get(ad),
                                                   beklenen, "video-and-output")


def test_crisper_turbo_pencere_suresi():
    profil = json.loads((PAKET / "bolum_20_transkripsiyon/crisperwhisper_turbo_ct2_motoru/config/runtime_profile.json")
                        .read_text(encoding="utf-8"))
    bulunan = []

    def gez(d):
        if isinstance(d, dict):
            for k, v in d.items():
                if k == "outer_window_seconds":
                    bulunan.append(v)
                gez(v)
        elif isinstance(d, list):
            for v in d:
                gez(v)

    gez(profil)
    assert bulunan and all(v == 29.5 for v in bulunan), _mesaj("runtime_profile.json:outer_window_seconds", bulunan,
                                                               29.5, "transcription")


def test_belge_bolumleri_var():
    """Hata mesajlarının gösterdiği bölümler belgede gerçekten var; TR karşılığı da var."""
    capalar = _baslik_capalari(KOK / BELGE)
    gereken = {b for *_, b in SABITLER} | {b for *_, b in AYARLAR} | {"video-and-output", "transcription"}
    eksik = sorted(gereken - capalar)
    assert not eksik, f"{BELGE} içinde bölüm yok: {eksik}"
    assert (KOK / BELGE_TR).is_file(), f"{BELGE_TR} yok"
