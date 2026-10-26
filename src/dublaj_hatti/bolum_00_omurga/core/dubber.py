from __future__ import annotations

import gc
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf
import torch
# cuDNN otomatik algoritma seçimi kapalı (kural: docs/engineering/low_vram.md 4; işçilerle aynı). Açıkken her yeni
# girdi boyunda algoritma süre ölçümüyle seçilir: aynı girdiye koşudan koşuya farklı evrişim algoritması (sonuç
# bit düzeyinde değişebilir) ve 4 GB Pascal kartta ölçülmüş 200 kata varan yavaşlama. Evrişimli modeller (STT,
# hizalama, cinsiyet, Demucs, TTS) ayrı süreçte koşar; bu süreçteki GPU modeli Opus-MT evrişimsizdir, yani
# bugünkü çıktı değişmez. Ayar, ileride süreç içine alınacak modeli korur.
torch.backends.cudnn.benchmark = False
torch.set_num_threads(4)
from dublaj_hatti.bolum_50_seslendirme.tts_orkestratoru.service import (
    TTSBuildResult,
    build_dubbed_audio,
    build_dubbed_audio_with_real_candidate_selection,
    get_supertonic_direct_runtime_context,
)
from dublaj_hatti.bolum_60_video_ve_encode.timeline_ve_final_encode.video_processor import (
    VideoProcessOptions,
    apply_timeline_to_audio,
    build_new_audio_mix,
    calculate_new_timeline,
    calculate_segment_speeds,
    corrected_video_bitrate_kbps,
    get_video_duration,
    video_encode_args,
)
from dublaj_hatti.bolum_40_ceviri.bridge_motor_orkestratoru.engine import BridgeMotorOrkestratoruTranslator, FullTextBridgeTranslator
from dublaj_hatti.bolum_60_video_ve_encode.timeline_ve_final_encode.yapay_zeka_etiketi import yapay_zeka_etiketi_ekle
from dublaj_hatti.bolum_40_ceviri.yerel_ceviri import yerel_ceviri_translator
from dublaj_hatti.bolum_40_ceviri.gorunum_adlari import (
    bridge_backend_normalize,
    ceviri_motoru_gorunum_adi,
    ceviri_orkestratoru_gorunum_adi,
)
from dublaj_hatti.bolum_00_omurga.core.source_subtitle_preview import write_source_subtitle_preview
from dublaj_hatti.bolum_00_omurga.core.pipeline_checkpoint import (
    GozdenGecirmeBekleniyor,
    PipelineCheckpointStore,
    canonical_json_hash,
)
from dublaj_hatti.bolum_00_omurga.core.pipeline_selection_contract import segment_translation_checkpoint_inputs
from dublaj_hatti.bolum_10_kaynak_edinme.adim_20_kaynak_alma.source_video import prepare_source_video
from dublaj_hatti.bolum_10_kaynak_edinme.adim_30_video_bilgisi.video_metadata import log_video_metadata
from dublaj_hatti.bolum_10_kaynak_edinme.adim_40_ses_cikarma.audio_extractor import extract_audio
from dublaj_hatti.bolum_10_kaynak_edinme.adim_50_asr_sesi_hazirlama.arka_plan_sesi_olcumu import (
    BACKGROUND_DETECTION_CONTRACT,
    measure_background,
)
from dublaj_hatti.bolum_10_kaynak_edinme.adim_50_asr_sesi_hazirlama.demucs_cleaner import clean_audio_with_demucs
from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import build_model_cache_env, huggingface_home
from dublaj_hatti.bolum_00_omurga.runtime.arac_yolu import ffmpeg_yolu, ffprobe_yolu
from dublaj_hatti.bolum_00_omurga.runtime.internet_gateway import run_with_internet_gateway
from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.flow_modes import (
    get_supertonic_flow_category,
    get_supertonic_flow_settings,
)
from dublaj_hatti.bolum_50_seslendirme.supertonic_tts import (
    SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER,
    SUPERTONIC_SYNTHESIS_CONTRACT,
    render_supertonic_constant_gain,
)
from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.speed_policy import apply_supertonic_voice_speed_plan
from dublaj_hatti.bolum_50_seslendirme.final_dub_alignment import (
    align_final_dub_audio,
    write_final_dub_alignment_debug,
)
from dublaj_hatti.bolum_50_seslendirme.altyazili_dublaj import (
    SUBTITLE_TIMING_CONTRACT_SCHEMA_VERSION,
    normalize_subtitle_mode,
    write_subtitle_timing_contract,
)
from dublaj_hatti.bolum_50_seslendirme.altyazili_dublaj.burnin import prepare_subtitle_burnin_assets
from dublaj_hatti.bolum_50_seslendirme.final_dub_alignment.writer import (
    ENGINE_DEBUG_DIRS as FINAL_DUB_ENGINE_DEBUG_DIRS,
)
from dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama import WORD_BOUNDARY_POLICY as CTC_WORD_BOUNDARY_POLICY
from dublaj_hatti.bolum_30_hizalama_ve_segment.nihai_dublaj_segmentleri import (
    NihaiDublajSegmenti as Segment,
    ZAMAN_KARSILASTIRMA_TOLERANSI,
    nihai_dublaj_segmentlerini_olustur,
)
from dublaj_hatti.bolum_00_omurga.full_metin_dublaji import (
    FullTextAudioChunk,
    FullTextSpeechWindow,
    FullTextSynthesis,
    build_full_text_alignment_windows,
    build_full_text_speech_window,
    fit_audio_to_speech_window,
    synthesize_full_text_supertonic,
)
from dublaj_hatti.bolum_00_omurga.runtime.crisperwhisper_turbo_ct2_runtime import (
    ENGINE_ID as CRISPERWHISPER_TURBO_CT2_ENGINE,
    MODEL_ID as CRISPERWHISPER_TURBO_CT2_MODEL,
    crisperwhisper_turbo_ct2_contract_inputs,
    invoke_crisperwhisper_turbo_ct2,
)
from dublaj_hatti.bolum_00_omurga.runtime.whisperx_runtime import build_whisperx_subprocess_env, resolve_whisperx_python
from dublaj_hatti.bolum_20_transkripsiyon.whisperx_motoru.decoder_profiles import (
    resolve_transcription_decoder_profile,
    transcription_decoder_contract_version,
)


LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"

DEMUCS_MODEL_NAME = "htdemucs"
DEMUCS_SUBDIR = "demucs"
# Neden: motorlar siki kesilmis videoda ilk kelimeyi kirpiyordu; cikarilan kayma bu degere esit olmali. bkz. docs/engineering/pinned-values.md#transcription
ASR_LEADING_PAD_SECONDS = 1.0
ASR_LEADING_PAD_FILENAME = "asr_leading_pad.wav"
SEGMENT_TTS_ENGINES = {"supertonic", "voxcpm2", "xtts", "ema_lightning"}
ALTYAZI_MOTOR_ETIKETI = {"supertonic": "Supertonic", "voxcpm2": "VoxCPM2", "xtts": "XTTS",
                         "ema_lightning": "EMA Lightning"}
# faster-whisper metni + ortak CTC kutusu kelime zamani; transkripsiyon.motor=auto'nun izin verici yedegi (ADR 0017).
# Elle secilen "faster-whisper" Whisper'in kendi zamanlarini korur. docs/engineering/timing-sources.md
FASTER_WHISPER_CTC_ENGINE = "faster_whisper_ctc"
FASTER_WHISPER_ENGINES = {"faster-whisper", FASTER_WHISPER_CTC_ENGINE}
ASR_LEADING_PAD_ENGINES = {
    "faster-whisper",
    FASTER_WHISPER_CTC_ENGINE,
    "whisperx",
    "parakeet_cpu_align",
}
PARAKEET_ALIGNMENT_INPUT_CONTRACT_VERSION = 2
CRISPER_GLOBAL_FIRST_WINDOW_LANGUAGE_MODE = "global_first_window"
asr_timestamp_zero_epsilon_seconds = 1e-6
DISTIL_ENGLISH_ONLY_MODELS = {"distil-large-v3", "distil-large-v3.5"}
DEMUCS_TO_ASR_HANDOFF_DELAY_SECONDS = 3
logger = logging.getLogger("dublaj_hatti")
if not logger.handlers:
    _stream_handler = logging.StreamHandler()
    _stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    _stream_handler.setLevel(logging.INFO)
    setattr(_stream_handler, "_dublaj_konsol", True)  # cli._gunlugu_kur bu işaretli işleyiciyi kendi işleyicisiyle değiştirir
    logger.addHandler(_stream_handler)
    logger.setLevel(logging.DEBUG)   # logger DEBUG alır, handler seviyeleri filtreler
    # Paketin kendi konsol işleyicisi var: kök günlükçüye yaymaz. Yoksa Python API kullanıcısı logging.basicConfig()
    # çağırınca her satır iki kez basılır (paket işleyicisi + kök işleyicisi).
    logger.propagate = False


def _hat_cihazi(cfg: "DubConfig") -> str:
    """Ayardaki cihaz ("auto" | "cuda" | "cpu"); "auto" gercek CUDA cekirdegi denemesiyle cozulur."""
    from dublaj_hatti.bolum_00_omurga.runtime.donanim import cihaz_coz

    return cihaz_coz(str(getattr(cfg, "device", "auto") or "auto"))


def _youtube_json3_on_denetim(source: str, cfg: "DubConfig", resume: bool = False) -> None:
    """`youtube_translate` seçiliyse iş başlamadan json3 yoklaması (önceki sürümün GUI/Telegram probe'u).

    İndirme, ses çıkarma ve ayrıştırma boşa çalışmasın diye kaynak aşamasından önce bakılır: bağlantıda otomatik
    json3 altyazı yoksa iş açık hatayla durur (sessiz motor değişimi yok, ADR 0009). Devam eden işte atlanır.
    """
    if getattr(cfg, "transcription_engine", "") != "youtube_translate" or resume:
        return
    from dublaj_hatti.bolum_20_transkripsiyon.youtube_json3_kaynagi import probe_youtube_json3

    sonuc = probe_youtube_json3(source, logger)
    if not sonuc.get("ok"):
        raise RuntimeError(
            "youtube_translate: bu bağlantıda kullanılabilir json3 otomatik altyazı yok "
            f"({sonuc.get('reason', 'bilinmiyor')}); ses tanıyan bir motor seçin "
            "(transkripsiyon.motor=faster-whisper, whisperx ya da parakeet_cpu_align)"
        )
    logger.info(
        "youtube_translate ön denetim: json3 var (dil=%s, kelime=%s)", sonuc.get("language"), sonuc.get("word_count")
    )


def _transcribe_youtube_json3(
    wav_path: str,
    cfg: "DubConfig",
    run_dir: str,
    source_url: Optional[str],
    asr_time_offset: float,
    full_text_mode: bool,
    prepare_final_segments: bool,
):
    """`youtube_translate`: YouTube json3 otomatik altyazı metni + kendi CTC kelime hizalamamız (extras youtube)."""
    from dublaj_hatti.bolum_20_transkripsiyon.youtube_json3_kaynagi import build_youtube_json3_transcript

    if asr_time_offset:
        raise RuntimeError("youtube_translate kipinde ASR baş dolgusu uygulanamaz")
    if not source_url:
        raise RuntimeError("youtube_translate yalnız YouTube bağlantısıyla çalışır (yerel dosyada başka motor seçin)")
    cache_dir = cfg.cache_dir if cfg.cache_dir else str(huggingface_home())
    result = build_youtube_json3_transcript(
        source_url, run_dir, audio_path=wav_path, device=_hat_cihazi(cfg), cache_dir=cache_dir, logger=logger
    )
    detected_language = result.get("detected_language", "en")
    all_words = list(result.get("words") or [])
    if not all_words:
        for seg in result.get("segments") or []:
            all_words.extend(seg.get("words") or [])
    if not all_words:
        raise RuntimeError("youtube_translate: CTC hizalama kelime zamani uretmedi")
    full_text = " ".join(str(word.get("word", "")).strip() for word in all_words)
    start, end = float(all_words[0]["start"]), float(all_words[-1]["end"])
    if full_text_mode:
        return [Segment(index=1, start=start, end=end, text=full_text, words=[])], detected_language, {"segments": []}
    if not prepare_final_segments:
        raw = Segment(index=0, start=start, end=end, text=full_text, words=list(all_words))
        return [raw], detected_language, {
            "segments": [{"start": start, "end": end, "text": full_text, "words": list(all_words)}]
        }
    segments, aligned = _nihai_kaynak_segmentlerini_olustur(all_words)
    logger.info("youtube_translate tamam: dil=%s segment=%d", detected_language, len(segments))
    check_word_overlaps(aligned)
    return segments, detected_language, aligned


def _transcription_engine_contract_inputs(engine_name: str) -> dict[str, Any]:
    if engine_name == CRISPERWHISPER_TURBO_CT2_ENGINE:
        return crisperwhisper_turbo_ct2_contract_inputs()
    if engine_name == "parakeet_cpu_align":
        return {
            "parakeet_alignment_input_contract_version": PARAKEET_ALIGNMENT_INPUT_CONTRACT_VERSION,
            "ctc_word_boundary_policy": CTC_WORD_BOUNDARY_POLICY,
        }
    if engine_name in {"youtube_translate", FASTER_WHISPER_CTC_ENGINE}:
        return {"ctc_word_boundary_policy": CTC_WORD_BOUNDARY_POLICY}
    return {}


def setup_file_logging(run_dir: str, debug: bool = False) -> str:
    previous_handler = getattr(logger, "_file_handler", None)
    if previous_handler:
        logger.removeHandler(previous_handler)
        try:
            previous_handler.flush()
            previous_handler.close()
        except Exception:
            pass

    existing_logs = []
    if os.path.exists(run_dir):
        for filename in os.listdir(run_dir):
            if filename.startswith("console_log_") and filename.endswith(".txt"):
                existing_logs.append(filename)

    if existing_logs:
        existing_logs.sort()
        log_filename = existing_logs[0]
        log_path = os.path.join(run_dir, log_filename)
        mode = "a"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"console_log_{timestamp}.txt"
        log_path = os.path.join(run_dir, log_filename)
        mode = "w"

    file_handler = logging.FileHandler(log_path, encoding="utf-8", mode=mode)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    file_handler.setLevel(logging.DEBUG if debug else logging.INFO)

    logger.addHandler(file_handler)
    logger._file_handler = file_handler

    if mode == "w":
        logger.info("=" * 60)
        logger.info("LOG DOSYASI: %s", log_path)
        logger.info("=" * 60)
    else:
        logger.info("")
        logger.info("=" * 60)
        logger.info("LOG DEVAM EDIYOR: %s", log_path)
        logger.info("=" * 60)

    return log_path


def get_active_log_path() -> str:
    file_handler = getattr(logger, "_file_handler", None)
    if file_handler and getattr(file_handler, "baseFilename", None):
        return file_handler.baseFilename
    return ""


def flush_file_logging() -> None:
    file_handler = getattr(logger, "_file_handler", None)
    if file_handler:
        try:
            file_handler.flush()
        except Exception:
            pass


def close_file_logging() -> None:
    file_handler = getattr(logger, "_file_handler", None)
    if file_handler:
        try:
            logger.removeHandler(file_handler)
            file_handler.flush()
            file_handler.close()
        except Exception:
            pass
        logger._file_handler = None


def run_video_processor_subprocess(
    input_video: str,
    segments: List,
    timing_infos: List,
    segment_audios: Dict[int, np.ndarray],
    output_video: str,
    work_dir: str,
    sample_rate: int = 24000,
    subtitle_ass_path: str = "",
    final_audio_filter: str = "",
    video_output_policy: str = "cq",
    video_encoder_cq: int = 26,
    max_output_bytes: int = 0,
) -> Dict:
    """
    Video islemesini izole subprocess'te calistirir.
    VRAM temizligi icin process bitince GPU bellek serbest kalir.

    Args:
        input_video: Giris video yolu
        segments: Segment listesi
        timing_infos: TTS timing bilgileri
        segment_audios: Her segment icin TTS ses arrayi {index: audio}
        output_video: Cikis video yolu
        work_dir: Calisma dizini
        sample_rate: Ses ornekleme hizi
        subtitle_ass_path: Tek gecis altyazi ASS yolu
        final_audio_filter: Final mux oncesi audio_new_timeline.wav uzerine uygulanacak FFmpeg audio filter

    Returns:
        Islem sonucu bilgileri
    """
    logger.info("Video isleme subprocess baslatiliyor...")

    segments_file = os.path.join(work_dir, "video_segments.json")
    segments_data = []
    for seg in segments:
        segments_data.append({
            "index": seg.index,
            "start": seg.start,
            "end": seg.end,
            "text": getattr(seg, "text", "")
        })
    with open(segments_file, "w", encoding="utf-8") as f:
        json.dump(segments_data, f, ensure_ascii=False, indent=2)

    timing_infos_file = os.path.join(work_dir, "video_timing_infos.json")
    timing_data = []
    for info in timing_infos:
        if isinstance(info, dict):
            timing_data.append(info)
        else:
            timing_data.append({
                "segment_index": getattr(info, "segment_index", 0),
                "tts_raw_duration": getattr(info, "tts_raw_duration", 0),
                "tts_final_duration": getattr(info, "tts_final_duration", 0),
                "original_duration": getattr(info, "original_duration", 0),
                "speed_factor": getattr(info, "speed_factor", 1.0)
            })
    with open(timing_infos_file, "w", encoding="utf-8") as f:
        json.dump(timing_data, f, ensure_ascii=False, indent=2)

    segment_audios_dir = os.path.join(work_dir, "segment_audios")
    os.makedirs(segment_audios_dir, exist_ok=True)

    from dublaj_hatti.bolum_60_video_ve_encode.timeline_ve_final_encode.audio_files import write_segment_audio_files

    write_segment_audio_files(
        segment_audios, segment_audios_dir, sample_rate, "FLOAT" if final_audio_filter else "PCM_16",
    )

    logger.info("Segment audios kaydedildi: %d dosya", len(segment_audios))

    config = {
        "input_video": input_video,
        "output_video": output_video,
        "work_dir": work_dir,
        "sample_rate": sample_rate,
        "segments_file": segments_file,
        "timing_infos_file": timing_infos_file,
        "segment_audios_dir": segment_audios_dir,
        "subtitle_ass_path": subtitle_ass_path or "",
        "final_audio_filter": final_audio_filter or "",
        "video_output_policy": video_output_policy,
        "video_encoder_cq": video_encoder_cq,
        "max_output_bytes": max_output_bytes,
    }

    config_file = os.path.join(work_dir, "video_processor_config.json")
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    worker_script = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "bolum_60_video_ve_encode",
        "timeline_ve_final_encode",
        "video_processor_worker.py",
    )

    python_exe = sys.executable

    cmd = [python_exe, worker_script, "--config", config_file]

    logger.info("Subprocess komutu: %s", " ".join(cmd))

    utf8_env = os.environ.copy()
    utf8_env['PYTHONIOENCODING'] = 'utf-8'

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,
            encoding='utf-8',
            errors='replace',
            env=utf8_env,
            **GIZLI_SUREC,
        )
        if result.stderr:
            for line in result.stderr.strip().split("\n")[:50]:
                line = line.strip()
                if not line:
                    continue
                if any(kw in line.lower() for kw in ("error", "exception", "traceback", "hata")):
                    logger.error("  [VIDEO-WORKER] %s", line)
                elif any(kw in line.lower() for kw in ("warning", "warn", "uyari")):
                    logger.warning("  [VIDEO-WORKER] %s", line)
                else:
                    logger.info("  [VIDEO-WORKER] %s", line)

        if result.returncode != 0:
            logger.error("Video processor subprocess hatasi (code %d)", result.returncode)
            raise RuntimeError(f"Video processor subprocess hatasi: {result.stderr}")

        stdout_json = json.loads(result.stdout.strip())
        result_file = stdout_json.get("result_file")

        if not result_file or not os.path.exists(result_file):
            raise RuntimeError("Video processor result dosyasi bulunamadi")

        with open(result_file, "r", encoding="utf-8") as f:
            video_result = json.load(f)

        if not video_result.get("success"):
            error_msg = video_result.get("error", "Bilinmeyen hata")
            raise RuntimeError(f"Video isleme hatasi: {error_msg}")

        logger.info("Video isleme subprocess tamamlandi!")
        logger.info("Orijinal sure: %.2fs, Yeni sure: %.2fs",
                    video_result.get("original_duration", 0),
                    video_result.get("new_duration", 0))

        return video_result

    except json.JSONDecodeError as e:
        logger.error("Video processor JSON parse hatasi: %s", e)
        raise RuntimeError(f"Video processor JSON hatasi: {e}") from e


def prepare_one_pass_subtitle_assets(
    video_path: str,
    output_video: str,
    segments: List,
    timing_infos: List,
    segment_audios: Dict[int, np.ndarray],
    cfg: "DubConfig",
    run_dir: str,
    known_alignment_windows: Optional[List[Dict[str, Any]]] = None,
    verified_word_timeline: Optional[List[Dict[str, Any]]] = None,
    require_verified_word_timeline: bool = False,
) -> Dict[str, Any]:
    subtitle_mode = normalize_subtitle_mode(getattr(cfg, "subtitle_mode", "none"))
    artifacts: Dict[str, Any] = {"enabled": False, "mode": subtitle_mode}
    if subtitle_mode == "none":
        return artifacts

    if cfg.tts_engine not in SEGMENT_TTS_ENGINES:
        return artifacts

    video_duration = get_video_duration(video_path)
    speed_infos = calculate_segment_speeds(segments, timing_infos)
    timeline = calculate_new_timeline(speed_infos, video_duration)
    total_new_duration = timeline[-1]["new_end"] if timeline else video_duration
    clean_dub_audio = os.path.join(run_dir, "audio_new_timeline.wav")
    new_audio = build_new_audio_mix(segment_audios, timeline, total_new_duration, cfg.sample_rate)
    sf.write(clean_dub_audio, new_audio, cfg.sample_rate)
    timeline_map = {item["index"]: item for item in timeline if item.get("type") == "segment" and "index" in item}
    aligned_segments = []
    if known_alignment_windows:
        if len(segments) != 1:
            raise ValueError("Bilinen alignment pencereleri yalniz tek Full Metin segmentiyle kullanilir")
        base_timeline = timeline_map.get(segments[0].index)
        if base_timeline is None:
            raise RuntimeError("Full Metin alignment timeline segmenti bulunamadi")
        for item in known_alignment_windows:
            text = str(item.get("text") or "").strip()
            start = max(float(item.get("start", 0.0) or 0.0), 0.0)
            end = max(float(item.get("end", start) or start), start + 0.01)
            if text:
                aligned_segments.append(Segment(
                    index=100000 + int(item.get("index", len(aligned_segments) + 1) or len(aligned_segments) + 1),
                    start=float(base_timeline["new_start"]) + start,
                    end=min(float(base_timeline["new_end"]), float(base_timeline["new_start"]) + end),
                    text=text,
                ))
        if not aligned_segments:
            raise RuntimeError("Full Metin bilinen alignment pencereleri gecersiz")
    else:
        for seg in segments:
            segment_info = timeline_map.get(seg.index)
            if segment_info:
                aligned_segments.append(Segment(
                    index=seg.index,
                    start=float(segment_info["new_start"]),
                    end=float(segment_info["new_end"]),
                    text=getattr(seg, "text", ""),
                    gender=getattr(seg, "gender", ""),
                    speaker=getattr(seg, "speaker", ""),
                    pitch=getattr(seg, "pitch", "+0Hz"),
                    protected_terms=getattr(seg, "protected_terms", None),
                ))
            else:
                aligned_segments.append(seg)

    aligned_words = []
    if verified_word_timeline:
        for word in verified_word_timeline:
            segment_index = int(word.get("segment_index", 0) or 0)
            timeline_item = timeline_map.get(segment_index)
            if timeline_item is None:
                continue
            start = float(word.get("start", 0.0) or 0.0)
            end = max(float(word.get("end", start) or start), start + 0.01)
            text = str(word.get("word") or "").strip()
            if text:
                aligned_words.append({
                    **dict(word),
                    "word": text,
                    "start": round(float(timeline_item["new_start"]) + start, 6),
                    "end": round(float(timeline_item["new_start"]) + end, 6),
                    "segment_index": segment_index,
                    "source": "candidate_audio_forced_alignment",
                })
        alignment_report = {
            "failed": False,
            "worker_success": True,
            "source": "candidate_audio_forced_alignment",
        }
    else:
        if require_verified_word_timeline:
            raise RuntimeError("Secilmis adayli dublajda dogrulanmis kelime zamanlari zorunludur")
        alignment_report = align_final_dub_audio(clean_dub_audio, aligned_segments, cfg.target_lang, run_dir)
        if alignment_report.get("failed") or not alignment_report.get("worker_success"):
            raise RuntimeError(f"Final dublaj altyazi alignment basarisiz: {alignment_report.get('error', 'bilinmeyen')}")
        alignment_result_path = os.path.join(run_dir, "final_dub_alignment", "alignment_result.json")
        with open(alignment_result_path, "r", encoding="utf-8") as f:
            alignment_result = json.load(f)
        aligned_words = list(alignment_result.get("words", []) or [])
    if not aligned_words:
        raise RuntimeError("Final dublaj altyazi alignment kelime timeline uretmedi")
    candidate_timeline_used = bool(verified_word_timeline)
    final_alignment_artifacts = write_final_dub_alignment_debug(
        run_dir=run_dir,
        language=cfg.target_lang,
        segments=aligned_segments,
        words=aligned_words,
        engine=cfg.tts_engine,
        debug_dir_name="candidate_word_timeline" if candidate_timeline_used else "final_dub_alignment",
        timing_source="candidate_audio_forced_alignment" if candidate_timeline_used else "final_dub_audio_forced_alignment",
        timing_method="candidate_audio_local_timeline_mapped_to_video" if candidate_timeline_used else "final_timeline_clean_dub_audio_forced_alignment",
    )
    verification_evidence_paths = (
        [os.path.join(run_dir, "pipeline_tts_result", "manifest.json")]
        if candidate_timeline_used
        else [
            os.path.join(run_dir, "final_dub_alignment", "alignment_result.json"),
            os.path.join(run_dir, "final_dub_alignment", "alignment_report.json"),
        ]
    )
    timing_contract_path = write_subtitle_timing_contract(
        run_dir=run_dir,
        language=cfg.target_lang,
        engine=cfg.tts_engine,
        timing_source="candidate_audio_forced_alignment" if candidate_timeline_used else "final_dub_audio_forced_alignment",
        timing_method="candidate_audio_local_timeline_mapped_to_video" if candidate_timeline_used else "final_timeline_clean_dub_audio_forced_alignment",
        word_timeline_path=final_alignment_artifacts["engine_word_timeline_path"],
        timing_report_path=final_alignment_artifacts["engine_timing_report_path"],
        verification_evidence_paths=verification_evidence_paths,
    )
    logger.info(
        "%s altyazi zamanlari hazir: engine=%s, kelime=%d, klasor=%s",
        "Dogrulanmis aday" if candidate_timeline_used else "Final dublaj forced alignment",
        cfg.tts_engine,
        len(aligned_words),
        final_alignment_artifacts.get("debug_dir", ""),
    )

    if cfg.tts_engine in SEGMENT_TTS_ENGINES:
        # Sözleşme cfg.tts_engine adıyla yazıldı; okuyan taraf da aynı motor adını, kendi hata ayıklama klasörünü ve
        # etiketini kullanır (Supertonic için değerler önceki ince bağdaştırıcıyla birebir aynı).
        return prepare_subtitle_burnin_assets(
            input_video=video_path,
            output_video=output_video,
            run_dir=run_dir,
            language=cfg.target_lang,
            mode=subtitle_mode,
            timeline=[],
            burn_strategy="one_pass_final_mux",
            engine=cfg.tts_engine,
            debug_dir_name=FINAL_DUB_ENGINE_DEBUG_DIRS[cfg.tts_engine],
            engine_label=ALTYAZI_MOTOR_ETIKETI.get(cfg.tts_engine, cfg.tts_engine),
            timing_contract_path=timing_contract_path,
        )

    return artifacts


SUPERTONIC_NATIVE_SAMPLE_RATE = 44100
EMA_NATIVE_SAMPLE_RATE = 48000  # ema_lightning_tts/ayarlar.py EMA_ORNEKLEME

def _nihai_kaynak_segmentlerini_olustur(all_words: List[Dict]) -> Tuple[List["Segment"], Dict]:
    segments, alignment, report = nihai_dublaj_segmentlerini_olustur(all_words)
    logger.info(
        "[SEGMENT] Merkezi zorunlu katman: kelime=%d ana_segment=%d nihai_segment=%d bolunen_ana_segment=%d max_kelime=%d",
        report.girdi_kelime_sayisi,
        report.ana_segment_sayisi,
        report.nihai_segment_sayisi,
        report.bolunen_ana_segment_sayisi,
        report.maksimum_nihai_segment_kelime_sayisi,
    )
    return segments, alignment


@dataclass
class DubConfig:
    model_name: str = "large-v3-turbo"
    compute_type: str = "auto"
    device: str = "auto"
    target_lang: str = "tr"
    tts_retry_attempts: int = 3
    tts_retry_delay: float = 2.0
    use_demucs: bool = False
    preserve_background_audio: bool = False
    auto_background_preservation: bool = False
    sample_rate: int = 24000
    tts_speed_factor: float = 1.2
    tts_engine: str = "supertonic"
    tts_fallback_enabled: bool = False
    tts_voice_id: str = "F1"
    voxcpm2_ses: str = "hazir/haber_spikeri"
    voxcpm2_konusmaci_sesleri: Dict[str, str] = field(default_factory=dict)
    voxcpm2_kadin_sesleri: List[str] = field(default_factory=list)  # favori kadın sesleri (sırayla dağıtılır)
    voxcpm2_erkek_sesleri: List[str] = field(default_factory=list)  # favori erkek sesleri
    ema_ses: str = "ema"  # EMA Lightning tek sesli; ayar ileride ses eklenirse hazır
    ema_cihaz: str = "auto"  # auto | cuda | cpu (auto: GPU meşgulse işlemci ONNX)
    ema_hiz: float = 1.0  # EMA okuma hızı (paketin speed değeri)
    ema_tohum: int = 0  # sabit tohum: aynı metin aynı ses (tekrar üretilebilirlik)
    translator_engine: str = "yerel"
    llm_backend: str = ""
    transcription_engine: str = "faster-whisper"
    transcription_decoder_profile: str = ""
    crisper_language_detection_mode: str = CRISPER_GLOBAL_FIRST_WINDOW_LANGUAGE_MODE
    transcription_runtime_engine: str = ""
    transcription_runtime_model_name: str = ""
    transcription_runtime_compute_type: str = ""
    transcription_runtime_decoder_profile: str = ""
    transcription_fallback_applied: bool = False
    transcription_fallback_reason: str = ""
    transcription_usage_report: str = ""
    whisper_language: str = "auto"
    whisper_vad_filter: bool = True
    cache_dir: str = ""
    tts_pitch: str = "+0Hz"
    use_diarization: bool = False
    supertonic_flow_mode: str = "natural_blocks_1"
    supertonic_atempo_enabled: bool = True
    konusmaci_basina_ses: bool = False
    konusmaci_ses_yolu: str = ""
    supertonic_konusmaci_sesleri: Dict[str, str] = field(default_factory=dict)
    subtitle_mode: str = "segment"
    dubbing_mode: str = "segment_sync"
    full_text_duration_fit_mode: str = "audio_to_video"
    video_output_policy: str = "cq"
    video_encoder_cq: int = 26
    max_output_bytes: int = 0
    ai_label: bool = True
    # --- isteğe bağlı özellikler (hepsi varsayılan kapalı; docs/motorlar/) ---
    smart_frame_capture_enabled: bool = False  # akıllı kare (extras akilli-kare)
    cinsiyet_kipi: str = "konusmaci"  # konusmaci (3D-Speaker + konuşmacı başına) | segment (her cümle ayrı)
    supertonic_kadin_ses: str = "F1"  # segment kipinde kadın sesi
    supertonic_erkek_ses: str = "M1"  # segment kipinde erkek sesi
    rvc_model_yolu: str = ""  # boşsa RVC kapalı; kullanıcının kendi .pth modeli
    rvc_index_yolu: str = ""
    rvc_perde: int = 0
    rvc_riza_onayi: bool = False  # model sesinin sahibinden rıza alındı beyanı (zorunlu)
    xtts_referans_ses: str = ""  # XTTS v2 için kullanıcının kendi (rızalı) referans sesi
    gozden_gecir: bool = False  # true: çeviri bitince seslendirmeden önce dur (GozdenGecirmeBekleniyor; hata değil)


def _last_stderr_line(stderr: str | None) -> str:
    lines = [line.strip() for line in str(stderr or "").splitlines() if line.strip()]
    return lines[-1] if lines else "stderr bos"


def should_use_real_tts_candidate_selection(cfg: DubConfig) -> bool:
    if cfg.translator_engine != "codex_bridge" or cfg.tts_engine != "supertonic":
        return False
    if cfg.target_lang == "tr":
        return True
    return (
        str(getattr(cfg, "dubbing_mode", "segment_sync") or "segment_sync").strip().lower() == "segment_sync"
        and bool(getattr(cfg, "supertonic_atempo_enabled", False))
    )


def _create_segment_translator(cfg: DubConfig, request_metadata: Dict[str, Any], source_lang: str):
    if cfg.translator_engine == "yerel":
        return yerel_ceviri_translator(source_lang=source_lang, target_lang=cfg.target_lang, device=cfg.device)
    if cfg.translator_engine != "codex_bridge":
        raise ValueError(f"Desteklenmeyen ceviri motoru: {cfg.translator_engine}")
    selection_settings = _get_real_tts_selection_settings(cfg)
    candidate_count = int(selection_settings.get("initial_candidate_count", selection_settings.get("candidate_count")) or 5)
    repair_candidate_count = int(selection_settings.get("repair_candidate_count") or 0)
    translation_group_size = int(selection_settings.get("translation_group_size") or 0)
    translation_prompt_mode = str(selection_settings.get("translation_prompt_mode") or "").strip()
    translation_flow_options = {}
    if translation_group_size > 0:
        translation_flow_options["group_size"] = translation_group_size
        translation_flow_options["fixed_group_size"] = True
    if translation_prompt_mode:
        translation_flow_options["prompt_mode"] = translation_prompt_mode
    return BridgeMotorOrkestratoruTranslator(
        source_lang=source_lang,
        target_lang=cfg.target_lang,
        candidate_count=candidate_count,
        repair_candidate_count=repair_candidate_count,
        timing_selection=False,
        tts_voice_id=cfg.tts_voice_id,
        tts_pitch=cfg.tts_pitch,
        tts_speed_factor=cfg.tts_speed_factor,
        tts_engine=cfg.tts_engine,
        bridge_backend=_request_bridge_backend(cfg, request_metadata),
        **translation_flow_options,
    )


def _ema_checkpoint_girdisi(cfg: DubConfig) -> Dict[str, Any]:
    """EMA ayarları değişince seslendirme aşaması yeniden koşar; başka motorda boş (eski checkpoint'ler geçerli kalır)."""
    if cfg.tts_engine != "ema_lightning":
        return {}
    return {"ema_ses": cfg.ema_ses, "ema_hiz": float(cfg.ema_hiz), "ema_tohum": int(cfg.ema_tohum),
            "ema_cihaz": cfg.ema_cihaz}


def _tts_ses_etiketi(cfg: DubConfig) -> str:
    if cfg.tts_engine == "voxcpm2":
        return getattr(cfg, "voxcpm2_ses", "") or "F1"
    if cfg.tts_engine == "ema_lightning":
        return f"{cfg.ema_ses} (hiz {cfg.ema_hiz:g}, tohum {cfg.ema_tohum})"
    return cfg.tts_voice_id or "F1"


def _apply_engine_sample_rate(cfg: DubConfig, logger: Optional[logging.Logger] = None) -> None:
    # Motorun kendi örnekleme hızı: ara yeniden örnekleme olmaz; tam metin kipinde sentez hızı = karışım hızı olmalı.
    native = {"supertonic": SUPERTONIC_NATIVE_SAMPLE_RATE, "ema_lightning": EMA_NATIVE_SAMPLE_RATE}.get(cfg.tts_engine)
    if native is None:
        return
    if cfg.sample_rate == native:
        return
    previous_sample_rate = cfg.sample_rate
    cfg.sample_rate = native
    if logger:
        logger.info("TTS sample rate ayarlandi (%s): onceki=%s yeni=%s", cfg.tts_engine, previous_sample_rate,
                    cfg.sample_rate)


def _request_bridge_backend(cfg: DubConfig, request_metadata: Optional[Dict[str, Any]] = None) -> str:
    value = cfg.llm_backend or (request_metadata or {}).get("codex_bridge_backend") or os.getenv("DUBLAJ_LLM_BACKEND", "")
    return bridge_backend_normalize(value)


def _log_ceviri_kimligi(
    logger: logging.Logger,
    cfg: "DubConfig",
    request_metadata: Dict[str, Any],
    prefix: str = "",
) -> None:
    translator_engine = cfg.translator_engine
    orkestrator = ceviri_orkestratoru_gorunum_adi(translator_engine)
    bridge_backend = _request_bridge_backend(cfg, request_metadata) if translator_engine == "codex_bridge" else ""
    motor = ceviri_motoru_gorunum_adi(translator_engine, bridge_backend)
    if orkestrator:
        logger.info("%sCeviri Orkestratoru: %s", prefix, orkestrator)
    logger.info("%sCeviri Motoru: %s", prefix, motor)


def _acik_kapali(value: bool) -> str:
    return "ACIK" if bool(value) else "KAPALI"


def _var_yok(value: str | None) -> str:
    text = str(value or "").strip()
    return text if text else "YOK"


def _log_secilen_parametreler(
    logger: logging.Logger,
    cfg: DubConfig,
    request_metadata: Optional[Dict] = None,
    transcript_format: str = "",
) -> None:
    request_metadata = request_metadata or {}
    bridge_backend = _request_bridge_backend(cfg, request_metadata) if cfg.translator_engine == "codex_bridge" else ""
    logger.info("SECILEN PARAMETRELER")
    logger.info("=" * 60)
    if transcript_format:
        logger.info("Transcript Formati: %s", transcript_format)
    logger.info("Cihaz: %s", cfg.device)
    logger.info("Hedef Dil: %s", cfg.target_lang)
    logger.info("Transkripsiyon Motoru: %s", cfg.transcription_engine)
    logger.info("Whisper Modeli: %s", cfg.model_name)
    logger.info("Hesaplama Tipi: %s", cfg.compute_type)
    logger.info("Transkripsiyon Decoder Profili: %s", cfg.transcription_decoder_profile)
    logger.info("Vokal Izolasyonu (Demucs): %s", _acik_kapali(cfg.use_demucs))
    logger.info("Arka Plan Koruma: %s", _acik_kapali(cfg.preserve_background_audio))
    logger.info("Otomatik Arka Plan Koruma: %s", _acik_kapali(cfg.auto_background_preservation))
    logger.info("TTS Motoru: %s", cfg.tts_engine)
    logger.info("Dublaj Sample Rate: %s", cfg.sample_rate)
    logger.info("TTS Sesi: %s", _var_yok(cfg.tts_voice_id))
    logger.info("Supertonic Akis Modu: %s", _var_yok(cfg.supertonic_flow_mode))
    logger.info("Supertonic Akis Turu: %s", get_supertonic_flow_category(cfg.supertonic_flow_mode).upper())
    logger.info("Supertonic FFmpeg Atempo: %s", _acik_kapali(cfg.supertonic_atempo_enabled))
    logger.info("Konusmaci basina ses: %s", _acik_kapali(cfg.konusmaci_basina_ses))
    logger.info("Konusmaci ses haritasi: %s", _var_yok(", ".join(f"{k}={v}" for k, v in sorted(cfg.supertonic_konusmaci_sesleri.items()))))
    logger.info("Altyazi Stili: %s", _var_yok(cfg.subtitle_mode))
    logger.info("Ceviri Motoru: %s", ceviri_motoru_gorunum_adi(cfg.translator_engine, bridge_backend))
    logger.info("Ceviri Backend Anahtari: %s", _var_yok(bridge_backend))
    logger.info("Yapay Zeka Etiketi: %s", _acik_kapali(cfg.ai_label))


def _wait_after_demucs_before_asr(logger: logging.Logger) -> None:
    logger.info(
        "Demucs sonrasi ASR handoff beklemesi: %d saniye",
        DEMUCS_TO_ASR_HANDOFF_DELAY_SECONDS,
    )
    time.sleep(DEMUCS_TO_ASR_HANDOFF_DELAY_SECONDS)


def _normalize_transcription_engine_name(engine_name: str) -> str:
    return str(engine_name or "").strip().lower()


def _should_apply_asr_leading_pad(cfg: "DubConfig") -> bool:
    engine_name = _normalize_transcription_engine_name(getattr(cfg, "transcription_engine", ""))
    return engine_name in ASR_LEADING_PAD_ENGINES


def _audio_duration_seconds(audio_path: str) -> float:
    try:
        return float(sf.info(audio_path).duration)
    except Exception as exc:
        raise RuntimeError(f"ASR ses suresi okunamadi: {audio_path} ({exc})") from exc


def _create_asr_leading_pad_audio(audio_path: str, run_dir: str, pad_seconds: float = ASR_LEADING_PAD_SECONDS) -> str:
    if not audio_path or not os.path.exists(audio_path):
        raise RuntimeError(f"ASR padding icin ses dosyasi bulunamadi: {audio_path}")
    if pad_seconds <= 0:
        raise RuntimeError(f"ASR padding suresi gecersiz: {pad_seconds}")

    output_path = os.path.join(run_dir, ASR_LEADING_PAD_FILENAME)
    if os.path.abspath(output_path) == os.path.abspath(audio_path):
        raise RuntimeError("ASR padding cikisi kaynak dosya ile ayni olamaz")

    input_duration = _audio_duration_seconds(audio_path)
    delay_ms = int(round(pad_seconds * 1000.0))
    cmd = [
        ffmpeg_yolu(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        audio_path,
        "-af",
        f"adelay={delay_ms}:all=1",
        "-acodec",
        "pcm_s16le",
        output_path,
    ]
    try:
        subprocess.run(cmd, check=True, **GIZLI_SUREC)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ASR padding sesi olusturulamadi: {exc}") from exc

    output_duration = _audio_duration_seconds(output_path)
    expected_duration = input_duration + pad_seconds
    if abs(output_duration - expected_duration) > 0.05:
        raise RuntimeError(
            "ASR padding sure dogrulamasi basarisiz: "
            f"giris={input_duration:.3f}s cikis={output_duration:.3f}s beklenen={expected_duration:.3f}s"
        )
    return output_path


def _shift_timed_item_for_asr_offset(item: Dict[str, Any], offset_seconds: float) -> bool:
    if "start" not in item and "end" not in item:
        return False
    if "start" not in item or "end" not in item:
        raise RuntimeError(f"ASR zaman offset icin eksik start/end alani: {item}")

    old_start = float(item["start"])
    old_end = float(item["end"])
    new_start = max(0.0, old_start - offset_seconds)
    new_end = max(0.0, old_end - offset_seconds)
    if new_start <= asr_timestamp_zero_epsilon_seconds:
        new_start = 0.0
    if new_end <= asr_timestamp_zero_epsilon_seconds:
        new_end = 0.0
    if new_end < new_start:
        raise RuntimeError(
            "ASR zaman offset gecersiz zaman uretti: "
            f"start={old_start:.3f}->{new_start:.3f}, end={old_end:.3f}->{new_end:.3f}"
        )
    item["start"] = new_start
    item["end"] = new_end
    return True


def _apply_asr_time_offset_to_transcription_data(data: Dict[str, Any], offset_seconds: float) -> Dict[str, int]:
    if offset_seconds <= 0:
        return {"words": 0, "segments": 0, "segment_words": 0}

    counts = {"words": 0, "segments": 0, "segment_words": 0}
    for word in data.get("words") or []:
        if _shift_timed_item_for_asr_offset(word, offset_seconds):
            counts["words"] += 1

    for segment in data.get("segments") or []:
        if _shift_timed_item_for_asr_offset(segment, offset_seconds):
            counts["segments"] += 1
        for word in segment.get("words") or []:
            if _shift_timed_item_for_asr_offset(word, offset_seconds):
                counts["segment_words"] += 1

    logger.info(
        "ASR zaman offset uygulandi: offset=%.3fs, words=%d, segments=%d, segment_words=%d",
        offset_seconds,
        counts["words"],
        counts["segments"],
        counts["segment_words"],
    )
    return counts


def _prepare_audio_for_asr_transcription(audio_path: str, cfg: "DubConfig", run_dir: str) -> Tuple[str, float]:
    engine_name = _normalize_transcription_engine_name(getattr(cfg, "transcription_engine", ""))
    if not _should_apply_asr_leading_pad(cfg):
        logger.info("ASR leading padding: KAPALI, engine=%s, audio=%s, offset=0.000s", engine_name, audio_path)
        return audio_path, 0.0

    padded_path = _create_asr_leading_pad_audio(audio_path, run_dir, ASR_LEADING_PAD_SECONDS)
    logger.info(
        "ASR leading padding: ACIK, engine=%s, kaynak=%s, padded=%s, offset=%.3fs",
        engine_name,
        audio_path,
        padded_path,
        ASR_LEADING_PAD_SECONDS,
    )
    return padded_path, ASR_LEADING_PAD_SECONDS


def _prepare_source_audio_for_transcription(video_path: str, cfg: "DubConfig", run_dir: str) -> Tuple[str, str, Optional[str]]:
    source_audio_path = _extract_source_audio(video_path, cfg, run_dir)
    if not cfg.use_demucs:
        return source_audio_path, source_audio_path, None
    clean_audio_path = _clean_source_audio_with_demucs(source_audio_path, cfg, run_dir)
    return source_audio_path, clean_audio_path, clean_audio_path


def _extract_source_audio(video_path: str, cfg: "DubConfig", run_dir: str) -> str:
    if not cfg.use_demucs:
        source_audio_path = os.path.join(run_dir, "source_audio.wav")
        extract_audio(video_path, source_audio_path, sample_rate=16000, logger=logger)
        return source_audio_path
    return _extract_demucs_source_audio(video_path, run_dir)


def _extract_demucs_source_audio(video_path: str, run_dir: str) -> str:
    source_audio_path = os.path.join(run_dir, "demucs_source.wav")
    extract_audio(video_path, source_audio_path, sample_rate=44100, channels=2, logger=logger)
    return source_audio_path


AUTO_BACKGROUND_POLICY = "auto_detect_raw_asr_v1"
BACKGROUND_DETECTION_FILENAME = "arka_plan_olcumu.json"


def _validate_background_selection(cfg: "DubConfig") -> None:
    if cfg.auto_background_preservation and (cfg.use_demucs or cfg.preserve_background_audio):
        raise ValueError(
            "Otomatik arka plan korumasi Demucs ASR veya sabit arka plan secimiyle birlikte kullanilamaz"
        )


def _detect_and_separate_background(video_path: str, source_audio_path: str, run_dir: str) -> Dict[str, Any]:
    detection = measure_background(source_audio_path)
    detection_path = os.path.join(run_dir, BACKGROUND_DETECTION_FILENAME)
    with open(detection_path, "w", encoding="utf-8", newline="\n") as detection_file:
        json.dump(detection, detection_file, ensure_ascii=False, indent=2)
        detection_file.write("\n")
    logger.info(
        "Arka plan olcumu: dinamik_aralik=%.2fdB esik=%.2fdB arka_plan=%s",
        detection["dynamic_range_db"],
        detection["threshold_db"],
        detection["has_background"],
    )
    if not detection["has_background"]:
        return {"detection": detection, "detection_path": detection_path, "background_path": None}
    demucs_source_path = _extract_demucs_source_audio(video_path, run_dir)
    clean_audio_with_demucs(
        demucs_source_path,
        run_dir,
        demucs_model_name=DEMUCS_MODEL_NAME,
        logger=logger,
        prepare_asr_ready=False,
    )
    _wait_after_demucs_before_asr(logger)
    background_path = _demucs_background_audio_path(run_dir)
    if not os.path.isfile(background_path):
        raise RuntimeError(f"Demucs arka plan stem dosyasi bulunamadi: {background_path}")
    return {"detection": detection, "detection_path": detection_path, "background_path": background_path}


def _clean_source_audio_with_demucs(source_audio_path: str, cfg: "DubConfig", run_dir: str) -> str:
    clean_audio_path = clean_audio_with_demucs(
        source_audio_path,
        run_dir,
        demucs_model_name=DEMUCS_MODEL_NAME,
        logger=logger,
        prepare_asr_ready=cfg.transcription_engine != "whisperx",
    )
    _wait_after_demucs_before_asr(logger)
    return clean_audio_path


def _run_auto_background_stage(
    checkpoint_store: PipelineCheckpointStore,
    demucs_inputs: Dict[str, Any],
    video_path: str,
    source_audio_path: str,
    run_dir: str,
) -> bool:
    if checkpoint_store.can_restore("demucs_vokal_ayirma", 4, 2, demucs_inputs):
        background_preserved = bool(checkpoint_store.stage_payload("demucs_vokal_ayirma")["background_preserved"])
        logger.info("Checkpoint kullanildi: demucs_vokal_ayirma (otomatik arka plan karari)")
    else:
        checkpoint_store.begin_stage("demucs_vokal_ayirma", 4, 2, demucs_inputs)
        try:
            separation = _detect_and_separate_background(video_path, source_audio_path, run_dir)
            background_preserved = separation["background_path"] is not None
            artifact_paths = [separation["detection_path"]]
            payload = {
                "background_preserved": background_preserved,
                "background_detection_path": _checkpoint_relative_path(run_dir, separation["detection_path"]),
                "background_detection": separation["detection"],
            }
            if background_preserved:
                payload["background_audio_path"] = _checkpoint_relative_path(run_dir, separation["background_path"])
                artifact_paths.append(separation["background_path"])
            checkpoint_store.complete_stage("demucs_vokal_ayirma", payload, artifact_paths)
        except Exception as exc:
            checkpoint_store.fail_stage("demucs_vokal_ayirma", exc)
            raise
    logger.info("Otomatik arka plan karari: korunacak=%s, ASR ham sesle", background_preserved)
    return background_preserved


def _demucs_background_audio_path(run_dir: str) -> str:
    return os.path.join(run_dir, "demucs", DEMUCS_MODEL_NAME, "demucs_source", "no_vocals.wav")


def _checkpoint_relative_path(run_dir: str, path: str) -> str:
    return Path(path).resolve().relative_to(Path(run_dir).resolve()).as_posix()


def _checkpoint_input_path(run_dir: str, path: str) -> str:
    resolved_path = Path(path).resolve()
    try:
        return resolved_path.relative_to(Path(run_dir).resolve()).as_posix()
    except ValueError:
        return str(resolved_path)


def _background_audio_checkpoint_map(run_dir: str, artifacts: Dict[str, str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for key in (
        "background_audio_new_timeline", "background_mixed_audio", "dubbed_audio",
        "background_raw_mixed_audio", "background_gain_report",
    ):
        path = str(artifacts.get(key) or "")
        if path and os.path.isfile(path):
            result[key] = _checkpoint_relative_path(run_dir, path)
    return result


def _portable_checkpoint_path_fields(
    run_dir: str,
    payload: Dict[str, Any],
    field_names: Tuple[str, ...],
) -> Dict[str, Any]:
    portable = dict(payload)
    for field_name in field_names:
        path = str(portable.get(field_name) or "")
        if path:
            portable[field_name] = _checkpoint_input_path(run_dir, path)
    return portable


def _restore_checkpoint_path_fields(
    run_dir: str,
    payload: Dict[str, Any],
    field_names: Tuple[str, ...],
) -> Dict[str, Any]:
    restored = dict(payload)
    for field_name in field_names:
        path = str(restored.get(field_name) or "")
        if path and not Path(path).is_absolute():
            restored[field_name] = _checkpoint_absolute_path(run_dir, path)
    return restored


def _restore_background_audio_checkpoint_map(
    run_dir: str,
    artifacts: Dict[str, str],
    payload: Dict[str, Any],
) -> Dict[str, str]:
    restored = _restore_checkpoint_path_fields(
        run_dir,
        artifacts,
        ("background_audio", "background_audio_new_timeline", "background_mixed_audio", "dubbed_audio",
         "background_raw_mixed_audio", "background_gain_report"),
    )
    for key, path in dict(payload.get("audio_artifacts") or {}).items():
        restored[str(key)] = _checkpoint_absolute_path(run_dir, str(path))
    return restored


def _portable_video_result(run_dir: str, video_result: Dict[str, Any]) -> Dict[str, Any]:
    portable = dict(video_result)
    final_audio_profile = portable.get("final_audio_profile")
    if isinstance(final_audio_profile, dict):
        portable["final_audio_profile"] = _portable_checkpoint_path_fields(
            run_dir,
            final_audio_profile,
            ("raw_audio", "profiled_audio", "timeline_audio", "source_audio"),
        )
    return portable


def _restore_video_result(run_dir: str, video_result: Dict[str, Any]) -> Dict[str, Any]:
    restored = dict(video_result)
    final_audio_profile = restored.get("final_audio_profile")
    if isinstance(final_audio_profile, dict):
        restored["final_audio_profile"] = _restore_checkpoint_path_fields(
            run_dir,
            final_audio_profile,
            ("raw_audio", "profiled_audio", "timeline_audio", "source_audio"),
        )
    return restored


def _video_result_audio_artifacts(video_result: Dict[str, Any]) -> List[str]:
    final_audio_profile = video_result.get("final_audio_profile")
    if not isinstance(final_audio_profile, dict):
        return []
    paths = []
    for field_name in ("raw_audio", "profiled_audio", "timeline_audio"):
        path = str(final_audio_profile.get(field_name) or "")
        if path and os.path.isfile(path) and path not in paths:
            paths.append(path)
    return paths


def _checkpoint_absolute_path(run_dir: str, relative_path: str) -> str:
    return str((Path(run_dir).resolve() / relative_path).resolve())


def _json_checkpoint_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_checkpoint_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_checkpoint_value(item) for item in value]
    return str(value)


def _segments_to_checkpoint_payload(segments: List[Segment]) -> List[Dict[str, Any]]:
    return [_json_checkpoint_value(vars(segment)) for segment in segments]


def _segments_from_checkpoint_payload(records: List[Dict[str, Any]]) -> List[Segment]:
    segments = []
    field_names = set(Segment.__dataclass_fields__.keys())
    for record in records:
        base_values = {key: record[key] for key in field_names if key in record}
        segment = Segment(**base_values)
        for key, value in record.items():
            if key not in field_names:
                setattr(segment, key, value)
        segments.append(segment)
    return segments


def _write_transcription_checkpoint(
    run_dir: str,
    segments: List[Segment],
    source_lang: str,
    alignment: Dict[str, Any],
    filename: str = "pipeline_transcription_result.json",
) -> str:
    path = os.path.join(run_dir, filename)
    payload = {
        "segments": _segments_to_checkpoint_payload(segments),
        "source_lang": source_lang,
        "alignment": _json_checkpoint_value(alignment),
    }
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
    return path


def _read_transcription_checkpoint(path: str) -> Tuple[List[Segment], str, Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as stream:
        payload = json.load(stream)
    segments = _segments_from_checkpoint_payload(payload["segments"])
    source_lang = str(payload["source_lang"])
    alignment = dict(payload["alignment"])
    return segments, source_lang, alignment


def _alignment_words_for_final_segments(alignment: Dict[str, Any]) -> List[Dict[str, Any]]:
    words = []
    for segment in alignment.get("segments") or []:
        words.extend(list(segment.get("words") or []))
    if not words:
        words.extend(list(alignment.get("words") or []))
    return words


def _write_tts_checkpoint(run_dir: str, tts_result: TTSBuildResult, sample_rate: int) -> Tuple[str, str]:
    checkpoint_dir = Path(run_dir) / "pipeline_tts_result"
    segment_dir = checkpoint_dir / "segment_audios"
    segment_dir.mkdir(parents=True, exist_ok=True)
    for old_path in segment_dir.glob("segment_*.wav"):
        old_path.unlink()
    mixed_audio_path = checkpoint_dir / "mixed_audio.wav"
    sf.write(str(mixed_audio_path), tts_result.audio, sample_rate, subtype="FLOAT")
    segment_files = {}
    for segment_index, audio in sorted(tts_result.segment_audios.items()):
        segment_path = segment_dir / f"segment_{int(segment_index)}.wav"
        sf.write(str(segment_path), audio, sample_rate, subtype="FLOAT")
        segment_files[str(int(segment_index))] = segment_path.relative_to(checkpoint_dir).as_posix()
    manifest_path = checkpoint_dir / "manifest.json"
    manifest = {
        "sample_rate": int(sample_rate),
        "mixed_audio": mixed_audio_path.relative_to(checkpoint_dir).as_posix(),
        "segment_audios": segment_files,
        "timing_infos": _json_checkpoint_value(tts_result.timing_infos),
        "verified_word_timeline": _json_checkpoint_value(tts_result.verified_word_timeline),
    }
    with open(manifest_path, "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    return str(manifest_path), str(checkpoint_dir)


def _checkpoint_audio_files(manifest_path: str, expected_sample_rate: int, full_text: bool = False):
    from dublaj_hatti.bolum_60_video_ve_encode.timeline_ve_final_encode.audio_files import WavAudioFiles

    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if int(manifest["sample_rate"]) != int(expected_sample_rate):
        raise ValueError("TTS checkpoint sample rate mismatch")
    paths = {1: manifest["final_audio_path"]} if full_text else manifest["segment_audios"]
    return WavAudioFiles.from_relative_paths(manifest_file.parent, paths, expected_sample_rate)


def _release_tts_audio_for_video(tts_result: TTSBuildResult, manifest_path: str, sample_rate: int):
    audio_files = _checkpoint_audio_files(manifest_path, sample_rate)
    if set(audio_files) != set(tts_result.segment_audios):
        raise ValueError("TTS checkpoint segment indexes mismatch")
    tts_result.segment_audios = audio_files
    tts_result.audio = np.empty(0, dtype=np.float32)
    logger.info("[AUDIO-MEMORY] Parent TTS arrays released; %d checkpoint file references retained", len(audio_files))


def _read_tts_checkpoint(manifest_path: str, expected_sample_rate: int) -> TTSBuildResult:
    manifest_file = Path(manifest_path)
    with open(manifest_file, "r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    sample_rate = int(manifest["sample_rate"])
    if sample_rate != int(expected_sample_rate):
        raise RuntimeError(
            f"TTS checkpoint sample rate uyusmuyor: checkpoint={sample_rate} expected={expected_sample_rate}"
        )
    checkpoint_dir = manifest_file.parent
    mixed_audio, mixed_rate = sf.read(str(checkpoint_dir / manifest["mixed_audio"]), dtype="float32")
    if int(mixed_rate) != sample_rate:
        raise RuntimeError("TTS checkpoint karma ses sample rate degeri gecersiz")
    segment_audios = {}
    for segment_index, relative_path in manifest["segment_audios"].items():
        audio, audio_rate = sf.read(str(checkpoint_dir / relative_path), dtype="float32")
        if int(audio_rate) != sample_rate:
            raise RuntimeError(f"TTS checkpoint segment sample rate degeri gecersiz: {segment_index}")
        segment_audios[int(segment_index)] = np.asarray(audio, dtype=np.float32)
    return TTSBuildResult(
        audio=np.asarray(mixed_audio, dtype=np.float32),
        timing_infos=list(manifest.get("timing_infos") or []),
        segment_audios=segment_audios,
        verified_word_timeline=list(manifest.get("verified_word_timeline") or []),
    )


def _write_pipeline_json(run_dir: str, filename: str, payload: Dict[str, Any]) -> str:
    path = os.path.join(run_dir, filename)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(_json_checkpoint_value(payload), stream, ensure_ascii=False, indent=2)
    return path


def _read_pipeline_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Pipeline JSON nesne olmali: {path}")
    return payload


def _write_full_text_tts_checkpoint(
    run_dir: str,
    synthesis: FullTextSynthesis,
    final_audio: np.ndarray,
    alignment_windows: List[Dict[str, Any]],
) -> Tuple[str, str]:
    checkpoint_dir = Path(run_dir) / "pipeline_full_text_tts_result"
    chunks_dir = checkpoint_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    for old_path in chunks_dir.glob("chunk_*.wav"):
        old_path.unlink()
    raw_audio_path = checkpoint_dir / "raw_audio.wav"
    final_audio_path = checkpoint_dir / "final_audio.wav"
    sf.write(str(raw_audio_path), synthesis.audio, synthesis.sample_rate, subtype="FLOAT")
    sf.write(str(final_audio_path), final_audio, synthesis.sample_rate, subtype="FLOAT")
    chunks = []
    for index, chunk in enumerate(synthesis.actual_chunks, start=1):
        chunk_path = chunks_dir / f"chunk_{index}.wav"
        sf.write(str(chunk_path), chunk.audio, synthesis.sample_rate, subtype="FLOAT")
        chunks.append({
            "text": chunk.text,
            "audio_path": chunk_path.relative_to(checkpoint_dir).as_posix(),
        })
    manifest_path = checkpoint_dir / "manifest.json"
    manifest = {
        "sample_rate": synthesis.sample_rate,
        "chunk_count": synthesis.chunk_count,
        "inter_chunk_silence_samples": synthesis.inter_chunk_silence_samples,
        "raw_audio_path": raw_audio_path.relative_to(checkpoint_dir).as_posix(),
        "final_audio_path": final_audio_path.relative_to(checkpoint_dir).as_posix(),
        "chunks": chunks,
        "alignment_windows": alignment_windows,
    }
    with open(manifest_path, "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    return str(manifest_path), str(checkpoint_dir)


def _read_full_text_tts_checkpoint(manifest_path: str) -> Tuple[FullTextSynthesis, np.ndarray, List[Dict[str, Any]]]:
    manifest_file = Path(manifest_path)
    manifest = _read_pipeline_json(str(manifest_file))
    checkpoint_dir = manifest_file.parent
    sample_rate = int(manifest["sample_rate"])
    raw_audio, raw_rate = sf.read(str(checkpoint_dir / manifest["raw_audio_path"]), dtype="float32")
    final_audio, final_rate = sf.read(str(checkpoint_dir / manifest["final_audio_path"]), dtype="float32")
    if int(raw_rate) != sample_rate or int(final_rate) != sample_rate:
        raise RuntimeError("Full Metin TTS checkpoint sample rate degeri gecersiz")
    chunks = []
    for chunk_record in manifest["chunks"]:
        chunk_audio, chunk_rate = sf.read(str(checkpoint_dir / chunk_record["audio_path"]), dtype="float32")
        if int(chunk_rate) != sample_rate:
            raise RuntimeError("Full Metin TTS checkpoint parca sample rate degeri gecersiz")
        chunks.append(FullTextAudioChunk(
            text=str(chunk_record["text"]),
            audio=np.asarray(chunk_audio, dtype=np.float32),
        ))
    synthesis = FullTextSynthesis(
        audio=np.asarray(raw_audio, dtype=np.float32),
        sample_rate=sample_rate,
        chunk_count=int(manifest["chunk_count"]),
        actual_chunks=tuple(chunks),
        inter_chunk_silence_samples=int(manifest["inter_chunk_silence_samples"]),
    )
    return synthesis, np.asarray(final_audio, dtype=np.float32), list(manifest.get("alignment_windows") or [])


def _align_whisperx_checkpoint_segments(
    audio_path: str,
    raw_segments: List[Segment],
    detected_language: str,
    cfg: DubConfig,
    run_dir: str,
    asr_time_offset: float,
) -> Tuple[List[Segment], Dict[str, Any], str]:
    worker_script = Path(__file__).resolve().parents[2] / "bolum_20_transkripsiyon" / "whisperx_motoru" / "worker.py"
    segments_path = Path(run_dir) / "pipeline_whisperx_alignment_input.json"
    provided_segments = [
        {
            "start": float(segment.start),
            "end": float(segment.end),
            "text": str(segment.text),
        }
        for segment in raw_segments
    ]
    with open(segments_path, "w", encoding="utf-8") as stream:
        json.dump(provided_segments, stream, ensure_ascii=False, indent=2)
    cache_dir = cfg.cache_dir if cfg.cache_dir else str(huggingface_home())
    device = _hat_cihazi(cfg)
    compute_type = cfg.compute_type
    if device == "cpu" and compute_type not in ("float32", "int8"):
        compute_type = "float32"
    command = [
        str(resolve_whisperx_python()),
        str(worker_script),
        "--audio_path", audio_path,
        "--model_name", cfg.model_name,
        "--device", device,
        "--compute_type", compute_type,
        "--language", detected_language,
        "--cache_dir", cache_dir,
        "--align_segments_json", str(segments_path),
        "--profile_path", os.path.join(run_dir, "alignment_profile_whisperx.json"),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=1800,
        encoding="utf-8",
        errors="replace",
        env=build_whisperx_subprocess_env(cache_dir),
        **GIZLI_SUREC,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"WhisperX alignment-only ciktisi parse edilemedi: {exc}") from exc
    if result.returncode != 0 or not data.get("success"):
        raise RuntimeError(f"WhisperX alignment-only basarisiz: {data.get('error') or result.stderr[-1000:]}")
    _apply_asr_time_offset_to_transcription_data(data, asr_time_offset)
    aligned_segments = [
        Segment(
            index=int(record.get("index", index)),
            start=float(record["start"]),
            end=float(record["end"]),
            text=str(record["text"]),
            speaker=str(record.get("speaker") or ""),
            words=list(record.get("words") or []),
        )
        for index, record in enumerate(data.get("segments") or [])
    ]
    alignment = {"segments": [
        {
            "start": float(record["start"]),
            "end": float(record["end"]),
            "text": str(record["text"]),
            "words": list(record.get("words") or []),
        }
        for record in data.get("segments") or []
    ]}
    if not _alignment_words_for_final_segments(alignment):
        raise RuntimeError("WhisperX alignment-only hizalanmis kelime zamani uretmedi")
    return aligned_segments, alignment, str(segments_path)


def _apply_supertonic_manual_voice_metadata_if_needed(segments: List[Segment], cfg: DubConfig) -> None:
    if cfg.tts_engine != "supertonic":
        return
    if getattr(cfg, "konusmaci_basina_ses", False):
        return
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts import apply_manual_supertonic_voice_metadata

    apply_manual_supertonic_voice_metadata(segments, cfg.tts_voice_id or "F1")


def _konusmaci_motoru(cfg: DubConfig) -> bool:
    """Konuşmacı/cinsiyet yönlendirmesi olan motorlar: Supertonic (F/M sesleri) ve VoxCPM2 (favori listeler)."""
    return cfg.tts_engine in ("supertonic", "voxcpm2") and bool(getattr(cfg, "konusmaci_basina_ses", False))


def _voxcpm2_ses_havuzlari(cfg: DubConfig) -> Tuple[List[str], List[str]]:
    kadin = [str(v).strip() for v in (getattr(cfg, "voxcpm2_kadin_sesleri", None) or []) if str(v).strip()]
    erkek = [str(v).strip() for v in (getattr(cfg, "voxcpm2_erkek_sesleri", None) or []) if str(v).strip()]
    tek = str(getattr(cfg, "voxcpm2_ses", "") or "").strip()
    kadin = kadin or erkek or [tek]
    erkek = erkek or kadin
    return kadin, erkek


def _apply_konusmaci_basina_ses_if_needed(segments: List[Segment], cfg: DubConfig, run_dir: str) -> None:
    if not _konusmaci_motoru(cfg):
        return
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.konusmaci_secimi import konusmaci_seslerini_ata

    audio_path = str(getattr(cfg, "konusmaci_ses_yolu", "") or "").strip()
    if not audio_path:
        raise RuntimeError("Konusmaci ayrimi icin kaynak ses yolu yok")
    voxcpm2 = cfg.tts_engine == "voxcpm2"
    if str(getattr(cfg, "cinsiyet_kipi", "konusmaci") or "konusmaci") == "segment":
        # segment kipi: konuşmacı ayrımı yok, her cümlenin cinsiyeti ayrı tahmin edilir (alefiury wav2vec2)
        from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.cinsiyet_secimi import apply_supertonic_segment_gender_routing
        from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.cinsiyet_secimi.voice_pair import validate_voice_pair

        if voxcpm2:
            voice_pair = validate_voice_pair("F1", "M1")
        else:
            voice_pair = validate_voice_pair(
                str(getattr(cfg, "supertonic_kadin_ses", "F1")), str(getattr(cfg, "supertonic_erkek_ses", "M1"))
            )
        apply_supertonic_segment_gender_routing(segments, audio_path, voice_pair, run_dir)
        if voxcpm2:
            # cinsiyet cümle başına; ses her cinsiyetin favori listesindeki ilk ses (konuşmacı yok, sıra dağıtılamaz)
            kadin, erkek = _voxcpm2_ses_havuzlari(cfg)
            for seg in segments:
                setattr(seg, "voxcpm2_voice", erkek[0] if getattr(seg, "gender", "") == "male" else kadin[0])
        return
    if voxcpm2:
        kadin, erkek = _voxcpm2_ses_havuzlari(cfg)
        konusmaci_seslerini_ata(
            segments=segments, audio_path=audio_path, run_dir=run_dir,
            manual_voice_map=dict(getattr(cfg, "voxcpm2_konusmaci_sesleri", {}) or {}),
            female_pool=kadin, male_pool=erkek, voice_attr="voxcpm2_voice",
        )
        return
    konusmaci_seslerini_ata(
        segments=segments, audio_path=audio_path, run_dir=run_dir,
        manual_voice_map=dict(getattr(cfg, "supertonic_konusmaci_sesleri", {}) or {}),
    )


def _supertonic_speaker_timeline_source(cfg: DubConfig) -> str:
    if not _konusmaci_motoru(cfg):
        return "disabled"
    return "local_3d_speaker"


def _rebuild_alignment_from_segment_words_if_available(segments: List[Segment], alignment: Dict) -> Dict:
    rebuilt_segments = []
    has_words = False
    for seg in segments:
        words = getattr(seg, "words", None) or []
        if words:
            has_words = True
        rebuilt_segments.append(
            {
                "start": float(getattr(seg, "start", 0.0) or 0.0),
                "end": float(getattr(seg, "end", 0.0) or 0.0),
                "text": str(getattr(seg, "text", "") or ""),
                "words": list(words),
            }
        )
    if not has_words:
        return alignment
    return {"segments": rebuilt_segments}


def _get_real_tts_selection_settings(cfg: DubConfig) -> Dict:
    if cfg.tts_engine == "supertonic":
        return get_supertonic_flow_settings(cfg.supertonic_flow_mode)
    return {}


def _candidate_pool_from_translator(segments: List[Segment], translated_texts: List[str], translator) -> Dict[str, List[str]]:
    candidates_by_id = {
        str(key): [str(item).strip() for item in value if str(item).strip()]
        for key, value in (getattr(translator, "last_candidates_by_id", {}) or {}).items()
    }
    for seg, translated_text in zip(segments, translated_texts):
        seg_id = str(seg.index)
        text = str(translated_text or "").strip()
        current = candidates_by_id.setdefault(seg_id, [])
        if text and text not in current:
            current.insert(0, text)
    return candidates_by_id


def _candidate_history_key(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _candidate_history_entry(candidate: Dict, round_label: str) -> Dict:
    return {
        "round": round_label,
        "candidate_number": candidate.get("candidate_number"),
        "text": str(candidate.get("text") or "").strip(),
        "spoken_text": str(candidate.get("spoken_text") or candidate.get("text") or "").strip(),
        "duration": round(float(candidate.get("processed_duration") or candidate.get("duration") or 0.0), 3),
        "target_duration": round(float(candidate.get("target_duration") or candidate.get("target_duration_seconds") or 0.0), 3),
        "video_speed": round(float(candidate.get("video_speed") or 0.0), 3),
        "status": str(candidate.get("status") or ""),
    }


def _update_real_tts_candidate_history(history_by_id: Dict[str, List[Dict]], selection, round_label: str) -> None:
    for report in getattr(selection, "candidate_report", []) or []:
        seg_id = str(report.get("segment_id") or report.get("segment_index") or "").strip()
        if not seg_id:
            continue
        current = history_by_id.setdefault(seg_id, [])
        seen = {_candidate_history_key(item.get("text", "")) for item in current}
        for candidate in report.get("candidates") or []:
            text = str(candidate.get("text") or "").strip()
            if not text or str(candidate.get("status") or "") == "tts_failed":
                continue
            key = _candidate_history_key(text)
            if key in seen:
                continue
            current.append(_candidate_history_entry(candidate, round_label))
            seen.add(key)


def _best_candidate_history_entry(items: List[Dict]) -> Dict:
    usable = [item for item in items if item.get("duration", 0) > 0]
    if not usable:
        return {}
    return sorted(
        usable,
        key=lambda item: (
            0 if item.get("status") == "accepted" else 1,
            abs(float(item.get("video_speed") or 0.0) - 1.0),
            -float(item.get("duration") or 0.0),
        ),
    )[0]


def _attach_candidate_history_to_problem_segments(problem_segments: List[Dict], history_by_id: Dict[str, List[Dict]]) -> List[Dict]:
    enriched = []
    for problem_segment in problem_segments:
        item = dict(problem_segment)
        seg_id = str(item.get("segment_id") or item.get("segment_index") or "").strip()
        history = list(history_by_id.get(seg_id, []))
        if history:
            item["all_previous_candidate_timings"] = history
            item["all_previous_candidate_count"] = len(history)
            best = _best_candidate_history_entry(history)
            if best:
                item["best_previous_candidate_timing"] = best
        enriched.append(item)
    return enriched


def _write_real_tts_final_summary(
    run_dir: str,
    rounds: List[dict],
    final_problem_count: int,
    selection_settings: Optional[Dict] = None,
) -> None:
    report_dir = os.path.join(run_dir, "real_tts_candidate_selection")
    os.makedirs(report_dir, exist_ok=True)
    selection_settings = selection_settings or {}
    repair_attempt_count = sum(1 for item in rounds if item.get("repair_attempted"))
    max_repair_rounds = max(
        [int(item.get("max_repair_rounds") or 0) for item in rounds],
        default=0,
    )
    atempo_rounds = [dict(item.get("supertonic_atempo") or {}) for item in rounds]
    candidate_reuse_rounds = [dict(item.get("candidate_reuse") or {}) for item in rounds]
    with open(os.path.join(report_dir, "final_summary.json"), "w", encoding="utf-8") as f:
        json.dump({
            "status": "completed" if final_problem_count == 0 else "completed_with_unresolved_timing",
            "round_count": len(rounds),
            "measurement_round_count": len(rounds),
            "repair_attempt_count": repair_attempt_count,
            "max_repair_rounds": max_repair_rounds,
            "selection_mode": selection_settings.get("mode", ""),
            "candidate_count": selection_settings.get("candidate_count", ""),
            "initial_candidate_count": selection_settings.get("initial_candidate_count", selection_settings.get("candidate_count", "")),
            "repair_candidate_count": selection_settings.get("repair_candidate_count", ""),
            "repair_enabled": selection_settings.get("repair_enabled", max_repair_rounds > 0),
            "final_problem_count": final_problem_count,
            "supertonic_atempo": {
                "enabled": any(bool(item.get("enabled")) for item in atempo_rounds),
                "applied_segment_count": sum(int(item.get("applied_segment_count") or 0) for item in atempo_rounds),
                "word_timing_rescaled_count": sum(int(item.get("word_timing_rescaled_count") or 0) for item in atempo_rounds),
                "resolved_segment_count": sum(int(item.get("resolved_segment_count") or 0) for item in atempo_rounds),
                "final_video_timing_problem_count": final_problem_count,
            },
            "candidate_reuse": {
                "new_candidate_tts_count": sum(int(item.get("new_candidate_tts_count") or 0) for item in candidate_reuse_rounds),
                "reused_candidate_tts_count": sum(int(item.get("reused_candidate_tts_count") or 0) for item in candidate_reuse_rounds),
                "prevented_candidate_tts_count": sum(int(item.get("prevented_candidate_tts_count") or 0) for item in candidate_reuse_rounds),
                "invalid_cached_tts_count": sum(int(item.get("invalid_cached_tts_count") or 0) for item in candidate_reuse_rounds),
                "final_cumulative_candidate_count": int(candidate_reuse_rounds[-1].get("cumulative_candidate_count") or 0) if candidate_reuse_rounds else 0,
            },
            "rounds": rounds,
        }, f, ensure_ascii=False, indent=2)


def _srt_timestamp(seconds: float) -> str:
    value = max(0.0, float(seconds or 0.0))
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    whole_seconds = int(value % 60)
    millis = int(round((value - int(value)) * 1000))
    if millis >= 1000:
        whole_seconds += 1
        millis -= 1000
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{millis:03d}"


def _write_srt(entries: List[Dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for index, item in enumerate(entries, start=1):
            f.write(f"{index}\n")
            f.write(f"{_srt_timestamp(item['start'])} --> {_srt_timestamp(item['end'])}\n")
            f.write(f"{item['text']}\n\n")


def _apply_preserved_background_audio(
    input_video: str,
    timeline: List[Dict],
    run_dir: str,
    sample_rate: int,
    expected_duration: float,
    audio_bitrate: str = "192k",
    max_output_bytes: int = 0,
    supertonic_constant_gain: bool = False,
) -> Dict[str, str]:
    background_audio = _demucs_background_audio_path(run_dir)
    new_audio_path = os.path.join(run_dir, "audio_new_timeline.wav")
    background_new_timeline = os.path.join(run_dir, "background_new_timeline.wav")
    mixed_audio = os.path.join(run_dir, "audio_new_timeline_with_background.wav")
    if not os.path.exists(background_audio):
        raise RuntimeError(f"Arka plan sesi bulunamadi: {background_audio}")
    if not os.path.exists(new_audio_path):
        raise RuntimeError(f"Yeni timeline sesi bulunamadi: {new_audio_path}")
    apply_timeline_to_audio(
        background_audio,
        timeline,
        background_new_timeline,
        run_dir,
        sample_rate=sample_rate,
        expected_duration=expected_duration,
    )
    mix_filter = "[0:a][1:a]amix=inputs=2:duration=longest:normalize=0"
    raw_mixed_audio = os.path.join(run_dir, "audio_background_mix_raw.wav") if supertonic_constant_gain else mixed_audio
    if not supertonic_constant_gain:
        mix_filter += ",alimiter=limit=0.95:level=false"
    subprocess.run(
        [
            ffmpeg_yolu(),
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", new_audio_path,
            "-i", background_new_timeline,
            "-filter_complex", mix_filter + "[outa]",
            "-map", "[outa]",
            "-ar", str(sample_rate),
            "-ac", "1",
            "-c:a", "pcm_f32le" if supertonic_constant_gain else "pcm_s16le",
            raw_mixed_audio,
        ],
        check=True,
        **GIZLI_SUREC,
    )
    if supertonic_constant_gain:
        render_supertonic_constant_gain(raw_mixed_audio, mixed_audio)
    remuxed_video = os.path.join(run_dir, "dubbed_with_background_tmp.mp4")
    final_audio_input = mixed_audio
    final_audio_args = ["-c:a", "aac", "-b:a", audio_bitrate]
    max_output_options: Optional[VideoProcessOptions] = None
    if max_output_bytes > 0:
        measured_mixed_audio = os.path.join(run_dir, "audio_new_timeline_with_background_max_mb.m4a")
        subprocess.run(
            [
                ffmpeg_yolu(),
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-i", mixed_audio,
                "-map", "0:a:0",
                "-vn",
                "-c:a", "aac",
                "-b:a", audio_bitrate,
                "-ar", str(sample_rate),
                "-ac", "1",
                measured_mixed_audio,
            ],
            check=True,
            **GIZLI_SUREC,
        )
        max_output_options = VideoProcessOptions(
            output_policy="max_mb",
            max_output_bytes=max_output_bytes,
            measured_audio_bytes=os.path.getsize(measured_mixed_audio),
        )
        final_audio_input = measured_mixed_audio
        final_audio_args = ["-c:a", "copy"]
    remux_command = [
        ffmpeg_yolu(),
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", input_video,
        "-i", final_audio_input,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        *final_audio_args,
        "-shortest",
        remuxed_video,
    ]
    subprocess.run(remux_command, check=True, **GIZLI_SUREC)
    if max_output_options is not None:
        first_output_bytes = os.path.getsize(remuxed_video)
        if first_output_bytes > max_output_bytes:
            corrected_bitrate = corrected_video_bitrate_kbps(
                max_output_options,
                expected_duration,
                first_output_bytes,
            )
            max_output_options.video_bitrate_override_kbps = corrected_bitrate
            retry_command = [
                ffmpeg_yolu(),
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-i", input_video,
                "-i", final_audio_input,
                *video_encode_args(max_output_options, expected_duration),
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:a", "copy",
                "-shortest",
                remuxed_video,
            ]
            logger.warning(
                "Arka plan miks sonrasi maksimum MB siniri asildi, yalniz video bitrate dusuruluyor: gercek=%d sinir=%d yeni_video_bitrate=%dk",
                first_output_bytes,
                max_output_bytes,
                corrected_bitrate,
            )
            subprocess.run(retry_command, check=True, **GIZLI_SUREC)
            retry_output_bytes = os.path.getsize(remuxed_video)
            if retry_output_bytes > max_output_bytes:
                raise RuntimeError(
                    "Arka plan miksli nihai video maksimum boyut sinirini video bitrate duzeltmesinden sonra da asti: "
                    f"gercek={retry_output_bytes} sinir={max_output_bytes}"
                )
        logger.info(
            "Arka plan miksli maksimum MB kontrolu basarili: gercek=%d sinir=%d ses=%d",
            os.path.getsize(remuxed_video),
            max_output_bytes,
            max_output_options.measured_audio_bytes,
        )
    os.replace(remuxed_video, input_video)
    logger.info("Arka plan sesi yeni timeline ile mikslenip videoya yazildi: %s", mixed_audio)
    artifacts = {
        "background_audio": background_audio,
        "background_audio_new_timeline": background_new_timeline,
        "background_mixed_audio": mixed_audio,
        "dubbed_audio": mixed_audio,
    }
    if supertonic_constant_gain:
        artifacts["background_raw_mixed_audio"] = raw_mixed_audio
        artifacts["background_gain_report"] = str(Path(mixed_audio).with_suffix(".gain.json"))
    return artifacts


def build_audio_with_real_tts_selection(
    segments: List[Segment],
    cfg: DubConfig,
    run_dir: str,
    translator,
    translated_texts: List[str],
    max_repair_rounds: int = 7,
) -> TTSBuildResult:
    candidates_by_id = _candidate_pool_from_translator(segments, translated_texts, translator)
    final_selection = None
    measure_segment_ids = None
    round_summaries = []
    candidate_history_by_id: Dict[str, List[Dict]] = {}
    max_repair_rounds = max(0, int(max_repair_rounds or 0))
    max_measurement_rounds = max_repair_rounds + 1
    selection_settings = _get_real_tts_selection_settings(cfg)
    if selection_settings:
        log_prefix = "[SUPERTONIC]"
        logger.info(
            "%s Akis modu: %s | ilk_aday=%s | repair_aday=%s | repair=%s | max_repair=%s",
            log_prefix,
            selection_settings["mode"],
            selection_settings.get("initial_candidate_count", selection_settings["candidate_count"]),
            selection_settings.get("repair_candidate_count", ""),
            selection_settings["repair_enabled"],
            max_repair_rounds,
        )
    supertonic_runtime_context = (
        get_supertonic_direct_runtime_context(cfg.tts_voice_id if cfg.tts_voice_id else "F1", cfg.target_lang)
        if cfg.tts_engine == "supertonic"
        else None
    )
    for round_index in range(1, max_measurement_rounds + 1):
        round_label = f"round_{round_index}"
        selection = build_dubbed_audio_with_real_candidate_selection(
            segments=segments,
            cfg=cfg,
            run_dir=run_dir,
            candidates_by_id=candidates_by_id,
            round_label=round_label,
            segment_ids_to_measure=measure_segment_ids,
            previous_selection=final_selection,
            supertonic_runtime_context=supertonic_runtime_context,
        )
        final_selection = selection
        _update_real_tts_candidate_history(candidate_history_by_id, selection, round_label)
        round_summaries.append({
            "round": round_label,
            "measurement_round": round_index,
            "max_repair_rounds": max_repair_rounds,
            "report_path": selection.report_path,
            "problem_count": len(selection.problem_segments),
            "repair_attempted": False,
            "supertonic_atempo": dict(getattr(selection, "atempo_summary", {}) or {}),
            "candidate_reuse": dict(getattr(selection, "candidate_reuse_summary", {}) or {}),
        })
        if not selection.problem_segments:
            break
        problem_segment_ids = {
            str(item.get("segment_id", "")).strip()
            for item in selection.problem_segments
            if str(item.get("segment_id", "")).strip()
        }
        if round_index > max_repair_rounds or not hasattr(translator, "repair_candidates_with_real_tts"):
            logger.warning(
                "Gercek TTS aday secimi tamamlandi: olcum_turu=%d repair_hakki=%d ideal_sure_uyumu_disinda=%d",
                round_index,
                max_repair_rounds,
                len(selection.problem_segments),
            )
            break
        enriched_problem_segments = _attach_candidate_history_to_problem_segments(
            selection.problem_segments,
            candidate_history_by_id,
        )
        candidates_by_id, repair_summary = translator.repair_candidates_with_real_tts(
            segments=segments,
            by_id=candidates_by_id,
            problem_segments=enriched_problem_segments,
            run_dir=run_dir,
            repair_round=round_index,
            current_target_by_id=dict(selection.selected_texts_by_id),
        )
        if hasattr(translator, "_clean_candidates_by_id"):
            candidates_by_id = translator._clean_candidates_by_id(segments, candidates_by_id, f"real_tts_repair_r{round_index}")
        translator.last_candidates_by_id = {str(key): list(value) for key, value in candidates_by_id.items()}
        round_summaries[-1]["repair_attempted"] = True
        round_summaries[-1]["repair_round"] = round_index
        round_summaries[-1]["repair_status"] = repair_summary.get("status")
        round_summaries[-1]["repaired_count"] = repair_summary.get("repaired_count", 0)
        if int(repair_summary.get("repaired_count", 0) or 0) <= 0:
            logger.warning(
                "Gercek TTS repair yeni aday uretmedi, tekrar olcum durduruldu: round=%d problem=%d",
                round_index,
                len(selection.problem_segments),
            )
            break
        measure_segment_ids = problem_segment_ids

    if final_selection is None:
        raise RuntimeError("Gercek TTS aday secimi sonuc uretmedi")

    for seg in segments:
        selected_text = final_selection.selected_texts_by_id.get(str(seg.index), "").strip()
        if selected_text:
            seg.text = selected_text
    _write_real_tts_final_summary(
        run_dir,
        round_summaries,
        len(final_selection.problem_segments),
        selection_settings,
    )
    if hasattr(translator, "_write_video_usage_report"):
        try:
            translator.last_video_usage_report = translator._write_video_usage_report(
                run_dir,
                f"real_tts_selection_{Path(run_dir).name}",
                "real_tts_candidate_selection",
                len(segments),
            )
        except Exception as exc:
            logger.warning("Gercek TTS repair sonrasi usage report guncellenemedi: %s", exc)
    logger.info(
        "Gercek TTS final secim tamamlandi: round=%d problem=%d",
        len(round_summaries),
        len(final_selection.problem_segments),
    )
    return final_selection.tts_result


def ensure_run_dir(base_dir: str, video_title: str = None) -> str:
    """
    Output klasörü oluşturur.

    Args:
        base_dir: Ana dizin
        video_title: Video başlığı (opsiyonel, klasör adında kullanılır)

    Returns:
        Oluşturulan run klasörü yolu

    Klasör formatı:
        - video_title varsa: output/{sanitized_title}_{timestamp}/
        - video_title yoksa: output/run_{timestamp}/
    """
    from dublaj_hatti.bolum_10_kaynak_edinme.adim_10_dosya_adi_guvenligi.filename_sanitizer import sanitize_filename
    from dublaj_hatti.bolum_00_omurga.runtime.output_paths import get_output_root

    output_root = str(get_output_root(base_dir))
    os.makedirs(output_root, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if video_title:
        # Video adını sanitize et ve klasör adı oluştur
        sanitized_title = sanitize_filename(video_title, keep_case=False)
        # Çok uzun başlıkları kısalt (klasör adı için max 50 karakter)
        if len(sanitized_title) > 50:
            sanitized_title = sanitized_title[:50].rstrip('_')
        run_dir = os.path.join(output_root, f"{sanitized_title}_{ts}")
    else:
        run_dir = os.path.join(output_root, f"run_{ts}")

    os.makedirs(run_dir, exist_ok=True)
    return run_dir


# Windows'ta alt süreç (ffmpeg, işçiler) konsol penceresi açmaz; diğer sistemlerde boş.
GIZLI_SUREC: Dict[str, Any] = {"creationflags": 0x08000000} if sys.platform == "win32" else {}


# Yalnız platform dilini okuyan motorlar (cfg.whisper_language'ı kendileri okumaz). docs/tarifler/dil_tespiti.md
SABIT_DIL_PLATFORM_YOLU_MOTORLARI = frozenset({
    "crisperwhisper_turbo_ct2",
})


def _sabit_dil_platform_yerine(engine_name: str, cfg: Any, platform_lang: Optional[str]) -> Optional[str]:
    """Elle sabit kaynak dil (transkripsiyon.kaynak_dil) bu motorlara platform dili yolundan iletilir.

    Platform (YouTube) dili varsa o önceliklidir (kaynak uygulamayla aynı sıra: platform > kullanıcı > otomatik).
    CrisperWhisper'da sabit dil yalnız global_first_window kipinde tespiti atlar; diğer kiplerde tespit sürer.
    """
    if platform_lang or engine_name not in SABIT_DIL_PLATFORM_YOLU_MOTORLARI:
        return platform_lang
    sabit = str(getattr(cfg, "whisper_language", "") or "").strip().lower()
    return sabit if sabit and sabit != "auto" else platform_lang


def normalize_language_code(lang_code: str) -> str:
    """
    Dil kodunu Faster-Whisper icin normalize eder.

    Locale-specific kodlari (en-US, pt-BR, es-MX) base kodlara (en, pt, es) donusturur.
    Faster-Whisper sadece base ISO 639-1 kodlarini kabul eder.

    Ornekler:
        en-US -> en
        pt-BR -> pt
        es-MX -> es
        zh-CN -> zh
        en -> en (zaten normalize)
    """
    if not lang_code:
        return "auto"

    base_code = lang_code.split('-')[0].split('_')[0].lower()

    return base_code


def normalize_platform_language_for_crisper(lang_code: Optional[str]) -> str:
    normalized = normalize_language_code(str(lang_code or ""))
    if normalized == "auto" or not re.fullmatch(r"[a-z]{2,3}", normalized):
        return ""
    return normalized


_transcription_engine_display_names = {
    "faster-whisper": "faster-whisper",
    FASTER_WHISPER_CTC_ENGINE: "faster-whisper + CTC",
    "whisperx": "WhisperX",
    "crisperwhisper_turbo_ct2": "CrisperWhisper2.0 Turbo CT2 (istege bagli, ticari olmayan)",
    "parakeet_cpu_align": "Parakeet Unified EN INT8 CPU + CTC",
    "youtube_translate": "YouTube json3 altyazi + CTC (istege bagli, yt-dlp)",
}



def _transcription_engine_display_name(engine_name: str) -> str:
    normalized_name = str(engine_name or "").strip().lower()
    return _transcription_engine_display_names.get(normalized_name, normalized_name or "transcription")


def _transcription_ham_file_name(engine_name: str) -> str:
    normalized_name = str(engine_name or "").strip().lower()
    artifact_name = re.sub(r"[^a-z0-9]+", "_", normalized_name).strip("_") or "transcription"
    return f"{artifact_name}_HAM_segmentleri.txt"


def _capture_gpu_diagnostic_snapshot(run_dir: str, stage: str) -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "stage": stage,
        "nvidia_smi_available": bool(shutil.which("nvidia-smi")),
        "torch_cuda_available": bool(torch.cuda.is_available()),
    }
    if snapshot["torch_cuda_available"]:
        try:
            free_bytes, total_bytes = torch.cuda.mem_get_info()
            snapshot["torch_cuda_free_bytes"] = int(free_bytes)
            snapshot["torch_cuda_total_bytes"] = int(total_bytes)
            snapshot["torch_cuda_allocated_bytes"] = int(torch.cuda.memory_allocated())
            snapshot["torch_cuda_reserved_bytes"] = int(torch.cuda.memory_reserved())
        except Exception as exc:
            snapshot["torch_cuda_error"] = str(exc)
    if snapshot["nvidia_smi_available"]:
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace",
                **GIZLI_SUREC,
            )
            snapshot["nvidia_smi_returncode"] = result.returncode
            snapshot["nvidia_smi_stdout"] = result.stdout.strip()
            if result.stderr.strip():
                snapshot["nvidia_smi_stderr"] = result.stderr.strip()
        except Exception as exc:
            snapshot["nvidia_smi_error"] = str(exc)
    diagnostic_path = os.path.join(run_dir, "gpu_diagnostics.jsonl")
    try:
        os.makedirs(run_dir, exist_ok=True)
        with open(diagnostic_path, "a", encoding="utf-8") as file:
            file.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
        logger.info("GPU diagnostic snapshot: stage=%s path=%s", stage, diagnostic_path)
    except Exception as exc:
        logger.warning("GPU diagnostic snapshot write failed: stage=%s error=%s", stage, exc)
    return snapshot


def _write_transcription_profile(
    run_dir: str,
    engine_name: str,
    data: Dict[str, Any],
    subprocess_returncode: Optional[int],
) -> Optional[str]:
    normalized_engine = str(engine_name or "").strip().lower()
    if normalized_engine != "whisperx":
        return None
    profile_path = os.path.join(run_dir, f"transcription_profile_{normalized_engine}.json")
    payload: Dict[str, Any] = {
        "success": bool(data.get("success")),
        "subprocess_returncode": subprocess_returncode,
        "profile_steps": data.get("profile_steps", []),
        "profile_summary": data.get("profile_summary", {}),
    }
    for key in ("error", "traceback"):
        if data.get(key):
            payload[key] = data[key]
    try:
        os.makedirs(run_dir, exist_ok=True)
        with open(profile_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        logger.info("%s transkripsiyon profil kaydedildi: %s", _transcription_engine_display_name(normalized_engine), profile_path)
    except Exception as exc:
        logger.warning("%s transkripsiyon profil yazilamadi: %s", _transcription_engine_display_name(normalized_engine), exc)
    return profile_path


def _transcription_runtime_metadata(cfg: DubConfig) -> Dict[str, Any]:
    selected_engine = cfg.transcription_engine
    runtime_engine = cfg.transcription_runtime_engine or selected_engine
    metadata = {
        "transcription_decoder_profile": cfg.transcription_decoder_profile,
        "transcription_decoder_contract_version": transcription_decoder_contract_version(selected_engine),
        "transcription_runtime_engine": runtime_engine,
        "transcription_runtime_model_name": cfg.transcription_runtime_model_name or cfg.model_name,
        "transcription_runtime_compute_type": cfg.transcription_runtime_compute_type or cfg.compute_type,
        "transcription_runtime_decoder_profile": (
            cfg.transcription_runtime_decoder_profile or cfg.transcription_decoder_profile
        ),
        "transcription_runtime_decoder_contract_version": transcription_decoder_contract_version(runtime_engine),
        "transcription_fallback_applied": bool(cfg.transcription_fallback_applied),
        "transcription_fallback_reason": cfg.transcription_fallback_reason,
    }
    if cfg.transcription_usage_report:
        metadata["transcription_usage_report"] = cfg.transcription_usage_report
    return metadata


def _restore_transcription_usage_report(cfg: DubConfig, alignment: Dict[str, Any], run_dir: str) -> None:
    relative_path = str(alignment.get("transcription_usage_report") or "").strip()
    if relative_path:
        cfg.transcription_usage_report = _checkpoint_absolute_path(run_dir, relative_path)


def _run_distil_language_fallback(
    wav_path: str,
    cfg: DubConfig,
    run_dir: str,
    platform_lang: Optional[str],
    source_url: Optional[str],
    asr_time_offset: float,
    full_text_mode: bool,
    prepare_final_segments: bool,
    trigger: str,
    detected_language: str,
    english_probability: Optional[float] = None,
    best_non_english_language: str = "",
    best_non_english_probability: Optional[float] = None,
    fallback_family: str = "distil",
) -> Tuple[List[Segment], str, Dict]:
    family = str(fallback_family or "distil").strip().lower()
    reason = f"{family}_english_only_source_not_confirmed"
    fallback_decoder_profile = resolve_transcription_decoder_profile(
        "whisperx",
        "large-v3-turbo",
        "float32",
    )
    cfg.transcription_runtime_engine = "whisperx"
    cfg.transcription_runtime_model_name = "large-v3-turbo"
    cfg.transcription_runtime_compute_type = "float32"
    cfg.transcription_runtime_decoder_profile = fallback_decoder_profile
    cfg.transcription_fallback_applied = True
    cfg.transcription_fallback_reason = reason
    fallback_record = {
        "selected_engine": cfg.transcription_engine,
        "selected_model_name": cfg.model_name,
        "selected_compute_type": cfg.compute_type,
        "selected_decoder_profile": cfg.transcription_decoder_profile,
        "trigger": trigger,
        "detected_language": detected_language,
        "english_probability": english_probability,
        "best_non_english_language": best_non_english_language,
        "best_non_english_probability": best_non_english_probability,
        "actual_engine": "whisperx",
        "actual_model_name": "large-v3-turbo",
        "actual_compute_type": "float32",
        "actual_decoder_profile": fallback_decoder_profile,
        "reason": reason,
    }
    fallback_path = os.path.join(run_dir, f"transcription_{family}_language_fallback.json")
    os.makedirs(run_dir, exist_ok=True)
    with open(fallback_path, "w", encoding="utf-8") as file:
        json.dump(fallback_record, file, ensure_ascii=False, indent=2)
    family_label = family.upper()
    logger.warning("%s DIL KAPISI: %s secildi ancak kaynak Ingilizce olarak dogrulanamadi", family_label, cfg.model_name)
    logger.warning("%s DIL KAPISI: trigger=%s detected_language=%s english_probability=%s", family_label, trigger, detected_language or "unknown", english_probability)
    if best_non_english_language:
        logger.warning("%s DIL KAPISI: best_non_english=%s probability=%s", family_label, best_non_english_language, best_non_english_probability)
    logger.warning("OTOMATIK GECIS: WhisperX large-v3-turbo float32 kullanilacak")
    logger.warning("OTOMATIK GECIS KAYDI: %s", fallback_path)
    fallback_cfg = replace(
        cfg,
        transcription_engine="whisperx",
        model_name="large-v3-turbo",
        compute_type="float32",
        transcription_decoder_profile=fallback_decoder_profile,
    )
    try:
        return transcribe_and_align(
            wav_path,
            fallback_cfg,
            run_dir,
            platform_lang=platform_lang,
            source_url=source_url,
            asr_time_offset=asr_time_offset,
            full_text_mode=full_text_mode,
            prepare_final_segments=prepare_final_segments,
        )
    except RuntimeError as exc:
        error_text = str(exc).lower()
        if "cuda" not in error_text or "out of memory" not in error_text:
            raise

    logger.warning("WHISPERX FLOAT32 CUDA OOM: worker kapandi, tek kontrollu int8 retry uygulanacak")
    float32_profile_path = os.path.join(run_dir, "transcription_profile_whisperx.json")
    float32_oom_profile_path = os.path.join(run_dir, "transcription_profile_whisperx_float32_oom.json")
    if os.path.exists(float32_profile_path):
        shutil.copy2(float32_profile_path, float32_oom_profile_path)
    gc.collect()
    if torch.cuda.is_available():
        try:
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            torch.cuda.synchronize()
        except Exception as exc:
            logger.warning("WHISPERX OOM retry oncesi ana process CUDA temizligi tamamlanamadi: %s", exc)
        _capture_gpu_diagnostic_snapshot(run_dir, "before_whisperx_int8_oom_retry")

    cfg.transcription_runtime_compute_type = "int8"
    int8_decoder_profile = resolve_transcription_decoder_profile(
        "whisperx",
        "large-v3-turbo",
        "int8",
    )
    cfg.transcription_runtime_decoder_profile = int8_decoder_profile
    fallback_record.update({
        "actual_compute_type": "int8",
        "actual_decoder_profile": int8_decoder_profile,
        "initial_compute_type": "float32",
        "oom_retry_applied": True,
        "oom_retry_reason": "whisperx_float32_cuda_oom",
        "attempt_count": 2,
    })
    with open(fallback_path, "w", encoding="utf-8") as file:
        json.dump(fallback_record, file, ensure_ascii=False, indent=2)
    logger.warning("OTOMATIK GECIS OOM RETRY: WhisperX large-v3-turbo int8 kullanilacak")
    int8_fallback_cfg = replace(
        fallback_cfg,
        compute_type="int8",
        transcription_decoder_profile=int8_decoder_profile,
    )
    try:
        retry_result = transcribe_and_align(
            wav_path,
            int8_fallback_cfg,
            run_dir,
            platform_lang=platform_lang,
            source_url=source_url,
            asr_time_offset=asr_time_offset,
            full_text_mode=full_text_mode,
            prepare_final_segments=prepare_final_segments,
        )
    except Exception as exc:
        fallback_record["oom_retry_outcome"] = "failed"
        fallback_record["oom_retry_error"] = str(exc)
        with open(fallback_path, "w", encoding="utf-8") as file:
            json.dump(fallback_record, file, ensure_ascii=False, indent=2)
        raise
    fallback_record["oom_retry_outcome"] = "succeeded"
    with open(fallback_path, "w", encoding="utf-8") as file:
        json.dump(fallback_record, file, ensure_ascii=False, indent=2)
    return retry_result


def _transcribe_crisperwhisper_turbo_ct2(
    wav_path: str,
    cfg: DubConfig,
    run_dir: str,
    platform_lang: Optional[str],
    asr_time_offset: float,
    full_text_mode: bool,
    prepare_final_segments: bool,
) -> Tuple[List[Segment], str, Dict]:
    if getattr(cfg, "use_diarization", False):
        raise RuntimeError(
            "CrisperWhisper2.0 Turbo CT2 diarization desteklemez; use_diarization=false olmali"
        )
    if str(cfg.model_name or "").strip() != CRISPERWHISPER_TURBO_CT2_MODEL:
        raise RuntimeError(
            "CrisperWhisper2.0 Turbo CT2 kanonik model adi gerekli: "
            f"{CRISPERWHISPER_TURBO_CT2_MODEL}; alinan={cfg.model_name}"
        )
    if str(cfg.compute_type or "").strip().lower() != "int8":
        raise RuntimeError(
            "CrisperWhisper2.0 Turbo CT2 yalniz compute_type=int8 destekler: "
            f"{cfg.compute_type}"
        )
    language_detection_mode = str(
        getattr(cfg, "crisper_language_detection_mode", "global_first_window")
        or "global_first_window"
    )

    logger.info("CrisperWhisper2.0 Turbo CT2 WSL worker baslatiliyor")
    logger.info(
        "CrisperWhisper2.0 Turbo CT2: CUDA INT8, Silero ONNX VAD, "
        "native transkript + zorunlu CTC kelime hizalama"
    )
    try:
        _capture_gpu_diagnostic_snapshot(run_dir, "before_crisperwhisper_turbo_ct2")
        data, result = invoke_crisperwhisper_turbo_ct2(
            wav_path,
            run_dir,
            language_detection_mode=language_detection_mode,
            platform_language=normalize_platform_language_for_crisper(platform_lang),
        )
        _capture_gpu_diagnostic_snapshot(run_dir, "after_crisperwhisper_turbo_ct2")
    except subprocess.TimeoutExpired as error:
        _capture_gpu_diagnostic_snapshot(run_dir, "crisperwhisper_turbo_ct2_timeout")
        raise RuntimeError("CrisperWhisper2.0 Turbo CT2 WSL worker timeout") from error
    except Exception:
        _capture_gpu_diagnostic_snapshot(run_dir, "crisperwhisper_turbo_ct2_error")
        raise
    if result.stderr:
        for line in result.stderr.strip().split("\n"):
            if line.strip():
                logger.info("  %s", line.strip())

    all_words = [dict(value) for value in list(data.get("words") or [])]
    _apply_asr_time_offset_to_transcription_data(
        {"words": all_words, "segments": []},
        asr_time_offset,
    )
    if not all_words:
        raise RuntimeError("CrisperWhisper2.0 Turbo CT2 kelime zamani uretmedi")
    full_text = str(data.get("text") or "").strip()
    if not full_text:
        full_text = " ".join(str(word.get("word", "")).strip() for word in all_words).strip()
    detected_language = str(data.get("language") or "").strip()
    if not detected_language:
        raise RuntimeError("CrisperWhisper2.0 Turbo CT2 kaynak dili tespit etmedi")
    platform_language = normalize_platform_language_for_crisper(platform_lang)
    expected_language_source = (
        "platform_metadata"
        if language_detection_mode == "global_first_window" and platform_language
        else "crisper_continuous_stream_language_detection"
        if language_detection_mode == "continuous_stream"
        else "crisper_global_first_window_language_detection"
    )
    if data.get("language_source") != expected_language_source:
        raise RuntimeError(
            "CrisperWhisper2.0 Turbo CT2 dil kaynagi sozlesmesi gecersiz"
        )
    if expected_language_source == "platform_metadata" and detected_language != platform_language:
        raise RuntimeError("CrisperWhisper2.0 Turbo CT2 platform dili korunmadi")

    artifact_metadata = {
        "api_request_path": "crisperwhisper_turbo_ct2_request.json",
        "transcription_profile_path": "transcription_profile_crisperwhisper_turbo_ct2.json",
        "raw_result_path": "crisperwhisper_turbo_ct2_raw.json",
        "dubbing_ready_result_path": "crisperwhisper_turbo_ct2_dubbing_ready.json",
        "ctc_alignment_result_path": "crisperwhisper_turbo_ct2_ctc_alignment.json",
        "diagnostics_path": "crisperwhisper_turbo_ct2_diagnostics.json",
        "language_detection_artifact_path": "crisperwhisper_turbo_ct2_language_detection.json",
        "language_detection_profile_path": "language_detection_profile_crisperwhisper_turbo_ct2.json",
        "profile_summary": {
            "engine": CRISPERWHISPER_TURBO_CT2_ENGINE,
            "model": CRISPERWHISPER_TURBO_CT2_MODEL,
            "runtime_identity": dict(data.get("runtime_identity") or {}),
            "timings": dict(data.get("timings") or {}),
            "physical_audio_seconds": float(data.get("physical_audio_seconds") or 0.0),
            "full_duration_processed": bool(data.get("full_duration_processed")),
            "external_forced_alignment": True,
            "ctc_alignment": dict(data.get("ctc_alignment") or {}),
            "language_detection_mode": language_detection_mode,
            "language_source": expected_language_source,
            "platform_language": platform_language,
            "detected_language": detected_language,
            "detected_languages": list(data.get("detected_languages") or []),
        },
    }
    source_segment = {
        "index": 0,
        "start": float(all_words[0]["start"]),
        "end": float(all_words[-1]["end"]),
        "text": full_text,
        "words": all_words,
    }
    aligned = {"segments": [source_segment], **artifact_metadata}
    ham_segments_path = os.path.join(
        run_dir,
        _transcription_ham_file_name(CRISPERWHISPER_TURBO_CT2_ENGINE),
    )
    with open(ham_segments_path, "w", encoding="utf-8") as file:
        file.write("CRISPERWHISPER2.0 TURBO CT2 HAM TRANSKRIPT\n")
        file.write("=" * 70 + "\n\n")
        file.write(full_text + "\n\n")
        file.write(f"Toplam kelime: {len(all_words)}\n")

    if full_text_mode:
        return [
            Segment(
                index=1,
                start=float(all_words[0]["start"]),
                end=float(all_words[-1]["end"]),
                text=full_text,
                words=[],
            )
        ], detected_language, {"segments": [], **artifact_metadata}
    if not prepare_final_segments:
        return [
            Segment(
                index=0,
                start=float(source_segment["start"]),
                end=float(source_segment["end"]),
                text=full_text,
                words=all_words,
            )
        ], detected_language, aligned

    segments, final_aligned = _nihai_kaynak_segmentlerini_olustur(all_words)
    final_aligned.update(artifact_metadata)
    logger.info(
        "CrisperWhisper2.0 Turbo CT2 tamamlandi. Dil: %s, Segment: %d, Kelime: %d",
        detected_language,
        len(segments),
        len(all_words),
    )
    check_word_overlaps(final_aligned)
    return segments, detected_language, final_aligned


def transcribe_and_align(
    wav_path: str,
    cfg: DubConfig,
    run_dir: str,
    platform_lang: Optional[str] = None,
    source_url: Optional[str] = None,
    asr_time_offset: float = 0.0,
    full_text_mode: bool = False,
    prepare_final_segments: bool = True,
) -> Tuple[List[Segment], str, Dict]:
    """
    Transkripsiyon islemi (faster-whisper veya WhisperX).

    VRAM izolasyonu icin subprocess olarak calisir.
    Process bittiginde OS tum VRAM'i otomatik serbest birakir.

    Args:
        platform_lang: Platform metadata'dan gelen dil kodu (YouTube, TikTok vb.)
                       Eger varsa, Whisper auto-detect atlanir ve direkt bu dil kullanilir.
    """
    engine_name = cfg.transcription_engine
    cfg.transcription_decoder_profile = resolve_transcription_decoder_profile(
        engine_name,
        cfg.model_name,
        cfg.compute_type,
        cfg.transcription_decoder_profile,
    )
    if not cfg.transcription_runtime_engine:
        cfg.transcription_runtime_engine = engine_name
        cfg.transcription_runtime_model_name = cfg.model_name
        cfg.transcription_runtime_compute_type = cfg.compute_type
        cfg.transcription_runtime_decoder_profile = cfg.transcription_decoder_profile

    platform_lang = _sabit_dil_platform_yerine(engine_name, cfg, platform_lang)
    if engine_name == CRISPERWHISPER_TURBO_CT2_ENGINE:
        return _transcribe_crisperwhisper_turbo_ct2(
            wav_path,
            cfg,
            run_dir,
            platform_lang,
            asr_time_offset,
            full_text_mode,
            prepare_final_segments,
        )

    if engine_name == "youtube_translate":
        return _transcribe_youtube_json3(
            wav_path, cfg, run_dir, source_url, asr_time_offset, full_text_mode, prepare_final_segments
        )

    if platform_lang:
        normalized_lang = normalize_language_code(platform_lang)
        whisper_lang = normalized_lang
        lang_source = "platform_metadata"
    else:
        if cfg.whisper_language and cfg.whisper_language != "auto":
            whisper_lang = cfg.whisper_language
            lang_source = "user_config"
        else:
            whisper_lang = None
            lang_source = "whisper_auto"

    distil_english_only = (
        engine_name in FASTER_WHISPER_ENGINES and str(cfg.model_name).strip().lower() in DISTIL_ENGLISH_ONLY_MODELS
    )
    if distil_english_only and whisper_lang and whisper_lang != "en":
        return _run_distil_language_fallback(
            wav_path,
            cfg,
            run_dir,
            platform_lang,
            source_url,
            asr_time_offset,
            full_text_mode,
            prepare_final_segments,
            trigger=lang_source,
            detected_language=whisper_lang,
        )

    engine_display = _transcription_engine_display_name(engine_name)

    logger.info("=" * 60)
    logger.info("%s TRANSKRIPSIYON BASLIYOR", engine_display.upper())
    logger.info("  Model: %s", cfg.model_name)
    logger.info("  Compute type: %s", cfg.compute_type)
    logger.info("=" * 60)

    if lang_source == "platform_metadata":
        logger.info("[DIL TESPITI] Platform metadata: %s (BULUNDU)", platform_lang)
        if platform_lang != whisper_lang:
            logger.info("[DIL TESPITI] Normalize edildi: %s -> %s", platform_lang, whisper_lang)
        logger.info("[DIL TESPITI] Whisper modu: DIREKT DIL (%s)", whisper_lang)
    elif lang_source == "user_config":
        logger.info("[DIL TESPITI] Kullanici ayari: %s", whisper_lang)
        logger.info("[DIL TESPITI] Whisper modu: DIREKT DIL (%s)", whisper_lang)
    elif lang_source == "whisper_auto":
        logger.info("[DIL TESPITI] Whisper modu: OTOMATIK TESPIT (%s)", cfg.model_name)
        logger.info("[DIL TESPITI] Dil parametresi: auto")

    if engine_name == "parakeet_cpu_align":
        from bolum_20_transkripsiyon.parakeet_cpu_align_motoru import transcribe_audio as transcribe_with_cpu_align
        transcribe_label = "Parakeet Unified EN 0.6B INT8 CPU"
        profile_slug = "parakeet_cpu_align"
        ham_title = "PARAKEET UNIFIED EN INT8 CPU ALIGN"

        if whisper_lang and whisper_lang != "en":
            return _run_distil_language_fallback(
                wav_path,
                cfg,
                run_dir,
                platform_lang,
                source_url,
                asr_time_offset,
                full_text_mode,
                prepare_final_segments,
                trigger=lang_source,
                detected_language=whisper_lang,
                fallback_family="parakeet",
            )

        cache_dir = cfg.cache_dir if cfg.cache_dir else str(huggingface_home())
        os.makedirs(cache_dir, exist_ok=True)
        device = _hat_cihazi(cfg)

        logger.info("=" * 60)
        logger.info("%s + CTC HIZALAMA BASLIYOR", ham_title)
        logger.info("  Transcribe: %s", transcribe_label)
        logger.info("  Alignment: ctc_kelime_hizalama kutusu (wav2vec2, %s, %s)", device, CTC_WORD_BOUNDARY_POLICY)
        logger.info("  Dil: en")
        logger.info("=" * 60)

        data = transcribe_with_cpu_align(
            wav_path,
            language="en",
            run_dir=run_dir,
            cache_dir=cache_dir,
            alignment_device=device,
            use_diarization=getattr(cfg, "use_diarization", False),
        )
        _apply_asr_time_offset_to_transcription_data(data, asr_time_offset)

        profile_path = os.path.join(run_dir, f"transcription_profile_{profile_slug}.json")
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump({
                "profile_steps": data.get("profile_steps", []),
                "profile_summary": data.get("profile_summary", {}),
            }, f, ensure_ascii=False, indent=2)
        logger.info("%s profil kaydedildi: %s", engine_display, profile_path)

        all_words = data.get("words", [])
        if not all_words:
            for seg in data.get("segments", []):
                all_words.extend(seg.get("words", []))
        if not all_words:
            raise RuntimeError(f"{engine_display} kelime zamani uretmedi")

        ham_segments_path = os.path.join(run_dir, _transcription_ham_file_name(engine_name))
        with open(ham_segments_path, "w", encoding="utf-8") as f:
            f.write(f"{ham_title} HAM SEGMENTLER (CUMLE SEGMENTASYONU ONCESI)\n")
            f.write("=" * 70 + "\n\n")
            for idx, seg_data in enumerate(data.get("segments", []), 1):
                f.write(f"{idx}. [{float(seg_data.get('start', 0.0)):.3f}s - {float(seg_data.get('end', 0.0)):.3f}s] {seg_data.get('text', '')}\n")
            f.write(f"\nToplam segment: {len(data.get('segments', []))}\n")
            f.write(f"Toplam kelime: {len(all_words)}\n")
        logger.info("HAM segmentler kaydedildi: %s", ham_segments_path)

        detected_language = data.get("detected_language", "en")
        full_text = " ".join([w.get("word", "").strip() for w in all_words])
        if full_text_mode:
            return [Segment(
                index=1,
                start=float(all_words[0]["start"]),
                end=float(all_words[-1]["end"]),
                text=full_text,
                words=[],
            )], detected_language, {"segments": []}
        aligned = {
            "segments": [
                {
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                    "text": seg.get("text", ""),
                    "words": seg.get("words", []),
                }
                for seg in data.get("segments", [])
            ]
        }
        if not prepare_final_segments:
            raw_segments = [
                Segment(
                    index=int(seg.get("index", index)),
                    start=float(seg.get("start", 0.0)),
                    end=float(seg.get("end", 0.0)),
                    text=str(seg.get("text", "")),
                    speaker=str(seg.get("speaker", "")),
                    words=list(seg.get("words") or []),
                )
                for index, seg in enumerate(data.get("segments", []))
            ]
            return raw_segments, detected_language, aligned
        segments, aligned = _nihai_kaynak_segmentlerini_olustur(all_words)
        logger.info("%s tamamlandi. Dil: %s, Segment: %d, Kelime: %d", engine_display, detected_language, len(segments), len(all_words))
        check_word_overlaps(aligned)
        return segments, detected_language, aligned

    src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    worker_dir = os.path.join(src_dir, "bolum_20_transkripsiyon")
    if engine_name == "whisperx":
        worker_script = os.path.join(worker_dir, "whisperx_motoru", "worker.py")
    else:
        worker_script = os.path.join(worker_dir, "faster_whisper_motoru", "worker.py")

    if not os.path.exists(worker_script):
        raise FileNotFoundError(f"{engine_display} worker bulunamadi: {worker_script}")

    cache_dir = cfg.cache_dir if cfg.cache_dir else str(huggingface_home())
    os.makedirs(cache_dir, exist_ok=True)

    device = _hat_cihazi(cfg)
    if engine_name == FASTER_WHISPER_CTC_ENGINE and whisper_lang and not full_text_mode:
        # Dil önceden biliniyorsa CTC modeli tanımadan önce denetlenir (eksikse tanıma boşa koşmaz)
        from dublaj_hatti.bolum_00_omurga.runtime.ctc_model_durumu import ctc_modeli_gerekli

        ctc_modeli_gerekli(whisper_lang, cache_dir, FASTER_WHISPER_CTC_ENGINE)

    compute_type = cfg.compute_type
    if device == "cpu" and compute_type not in ("float32", "int8"):
        compute_type = "float32"
        logger.warning("CPU modunda compute_type=%s desteklenmiyor, float32 kullaniliyor", cfg.compute_type)

    worker_python = Path(sys.executable)
    if engine_name == "whisperx":
        worker_python = resolve_whisperx_python()
        logger.info("WhisperX clean CTC Python: %s", worker_python)

    cmd = [
        str(worker_python),
        worker_script,
        "--audio_path", wav_path,
        "--model_name", cfg.model_name,
        "--device", device,
        "--compute_type", compute_type,
        "--language", whisper_lang if whisper_lang else "auto",
        "--cache_dir", cache_dir,
    ]
    if engine_name == "whisperx":
        cmd.extend([
            "--decoder_profile",
            cfg.transcription_decoder_profile,
            "--profile_path",
            os.path.join(run_dir, "transcription_profile_whisperx.json"),
        ])
    if full_text_mode and engine_name == "whisperx":
        cmd.append("--skip_alignment")
    if engine_name == FASTER_WHISPER_CTC_ENGINE and not whisper_lang and not full_text_mode:
        # Dil otomatikse işçi, tespitten hemen sonra ve tanımadan önce CTC modelini denetler
        cmd.append("--ctc_dil_denetimi")

    logger.info("=" * 60)
    logger.info("SUBPROCESS BASLATILIYOR")
    logger.info("  Device: %s", device)
    logger.info("  Language: %s", whisper_lang or "auto")
    logger.info("=" * 60)

    utf8_env = build_whisperx_subprocess_env(cache_dir) if engine_name == "whisperx" else build_model_cache_env(cache_dir)
    utf8_env.setdefault('PYTHONIOENCODING', 'utf-8')

    try:
        if device == "cuda":
            _capture_gpu_diagnostic_snapshot(run_dir, "before_worker")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,
            encoding='utf-8',
            errors='replace',
            env=utf8_env,
            **GIZLI_SUREC,
        )
        if device == "cuda":
            _capture_gpu_diagnostic_snapshot(run_dir, "after_worker")
            if result.returncode != 0:
                _capture_gpu_diagnostic_snapshot(run_dir, "worker_failure")

        if result.stderr:
            for line in result.stderr.strip().split("\n"):
                if line.strip():
                    logger.info("  %s", line.strip())

    except subprocess.TimeoutExpired as error:
        if device == "cuda":
            _capture_gpu_diagnostic_snapshot(run_dir, "worker_timeout")
        logger.error("%s timeout - islem 30 dakikayi asti", engine_display)
        raise RuntimeError(f"{engine_display} transkripsiyon timeout") from error

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        _write_transcription_profile(
            run_dir,
            engine_name,
            {
                "success": False,
                "error": f"Worker JSON parse hatasi: {e}",
                "traceback": result.stderr[-10000:] if result.stderr else "",
            },
            result.returncode,
        )
        if result.returncode != 0:
            logger.error("%s subprocess hatasi (code %d)", engine_display, result.returncode)
            raise RuntimeError(
                f"{engine_display} transkripsiyon basarisiz (code {result.returncode}): {_last_stderr_line(result.stderr)}"
            ) from None
        logger.error("JSON parse hatasi: %s", e)
        logger.error("STDOUT: %s", result.stdout[:500] if result.stdout else "BOS")
        raise RuntimeError(f"{engine_display} ciktisi parse edilemedi: {e}") from e

    _write_transcription_profile(run_dir, engine_name, data, result.returncode)

    if result.returncode != 0 and result.returncode != 3221226505:
        logger.warning("%s subprocess beklenmeyen kod ile cikti: %d (veri alindi, devam ediliyor)", engine_display, result.returncode)
    elif result.returncode == 3221226505:
        logger.info("%s CUDA temizlik hatasi (kod 3221226505) - veri basariyla alindi, devam ediliyor", engine_display)

    if result.returncode != 0:
        logger.info("Subprocess temizlik basarisiz, ana process'te CUDA temizligi yapiliyor...")
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                logger.info("CUDA cache temizlendi (torch.cuda.empty_cache)")
        except Exception as cuda_err:
            logger.warning("CUDA temizlik hatasi: %s", cuda_err)
        gc.collect()
        logger.info("GC calistirildi, bellek temizligi tamamlandi")

    if not data.get("success"):
        error_msg = data.get("error", "Bilinmeyen hata")
        logger.error("Worker hatasi: %s", error_msg)
        if data.get("hata_turu") == "ctc_modeli_eksik":
            from dublaj_hatti.bolum_00_omurga.runtime.ctc_model_durumu import CtcModeliEksikHatasi

            raise CtcModeliEksikHatasi(error_msg)
        raise RuntimeError(f"{engine_display} worker hatasi: {error_msg}")

    if distil_english_only and data.get("fallback_required"):
        return _run_distil_language_fallback(
            wav_path,
            cfg,
            run_dir,
            platform_lang,
            source_url,
            asr_time_offset,
            full_text_mode,
            prepare_final_segments,
            trigger=str(data.get("fallback_trigger") or "distil_language_gate"),
            detected_language=str(data.get("detected_language") or ""),
            english_probability=data.get("english_probability"),
            best_non_english_language=str(data.get("best_non_english_language") or ""),
            best_non_english_probability=data.get("best_non_english_probability"),
        )

    if engine_name == FASTER_WHISPER_CTC_ENGINE and not full_text_mode:
        data = _faster_whisper_ctc_hizala(data, wav_path, run_dir, whisper_lang, device, cache_dir)

    _apply_asr_time_offset_to_transcription_data(data, asr_time_offset)

    segments: List[Segment] = []
    for seg_data in data.get("segments", []):
        segment_words = list(seg_data.get("words") or [])
        segment_speaker = str(seg_data.get("speaker") or "")
        if not segment_speaker:
            segment_speaker = next(
                (str(word.get("speaker") or "") for word in segment_words if word.get("speaker")),
                "",
            )
        segments.append(
            Segment(
                index=seg_data["index"],
                start=float(seg_data["start"]),
                end=float(seg_data["end"]),
                text=seg_data["text"],
                speaker=segment_speaker,
                words=segment_words,
            )
        )

    detected_language = data.get("detected_language", "en")

    if full_text_mode:
        if not segments:
            raise RuntimeError(f"{engine_display} Full Metin icin konusma segmenti uretmedi")
        return segments, detected_language, {"segments": []}

    aligned = {
        "segments": [
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
                "words": seg.get("words", [])
            }
            for seg in data.get("segments", [])
        ]
    }

    logger.info("%s subprocess tamamlandi. Dil: %s, Segment: %d, Kelime: %d",
                engine_display, detected_language, len(segments), data.get("total_words", 0))
    logger.info("VRAM subprocess ile birlikte otomatik temizlendi.")

    check_word_overlaps(aligned)

    refine_segment_times_from_words(segments, aligned)

    if not prepare_final_segments:
        return segments, detected_language, aligned

    ham_segments_for_debug = [(seg.index, seg.start, seg.end, seg.text) for seg in segments]
    ham_segment_count = len(segments)

    ham_segments_path = os.path.join(run_dir, _transcription_ham_file_name(engine_name))
    with open(ham_segments_path, "w", encoding="utf-8") as f:
        f.write(f"{engine_display.upper()} HAM SEGMENTLER (CUMLE SEGMENTASYONU ONCESI)\n")
        f.write("=" * 70 + "\n\n")
        for idx, start, end, text in ham_segments_for_debug:
            f.write(f"{idx+1}. [{start:.3f}s - {end:.3f}s] {text}\n")
        f.write(f"\nToplam: {ham_segment_count} segment\n")
    logger.info("HAM segmentler kaydedildi (cumle seg. oncesi): %s", ham_segments_path)

    logger.info("=" * 60)
    logger.info("KAYNAK SEGMENT HAZIRLIGI BASLIYOR")
    logger.info("=" * 60)

    all_words = data.get("words", [])
    if not all_words:
        for seg in data.get("segments", []):
            all_words.extend(seg.get("words", []))

    full_text_from_segments = " ".join([seg.text for seg in segments])
    full_text_from_words = " ".join([w.get("word", "").strip() for w in all_words])

    segment_word_count = len(full_text_from_segments.split())
    whisper_word_count = len(all_words)

    if segment_word_count != whisper_word_count:
        logger.warning("KELIME SAYISI UYUMSUZLUGU TESPIT EDILDI!")
        logger.warning("  Segment metinlerinden: %d kelime", segment_word_count)
        logger.warning("  Whisper words listesinden: %d kelime", whisper_word_count)
        logger.warning("  Fark: %d kelime - words listesi kullanilacak", whisper_word_count - segment_word_count)
        full_text = full_text_from_words
    else:
        full_text = full_text_from_segments

    logger.info("Tam metin uzunlugu: %d karakter", len(full_text))
    logger.info("Toplam kelime: %d", len(all_words))

    if not all_words:
        raise RuntimeError(f"{engine_display} hizalanmis kelime zamani uretmedi")

    sentence_segments, sentence_aligned = _nihai_kaynak_segmentlerini_olustur(all_words)
    logger.info("Kaynak segment hazirligi tamamlandi:")
    logger.info("  Onceki ham segment sayisi: %d", len(segments))
    logger.info("  Yeni nihai segment sayisi: %d", len(sentence_segments))
    segments = sentence_segments
    aligned = sentence_aligned

    logger.info("=" * 60)

    return segments, detected_language, aligned


def _ctc_kelimelerini_dogrula(words: List[Dict[str, Any]]) -> None:
    """CTC hizalamasının kelime listesi boş değil, her kelime metinli, başlangıç <= bitiş ve başlangıçlar sıralı."""
    if not words:
        raise RuntimeError("CTC kelime hizalama bos kelime listesi dondurdu")
    previous_start = -1.0
    for index, word in enumerate(words):
        text = str(word.get("word") or "").strip()
        start = float(word.get("start"))
        end = float(word.get("end"))
        if not text:
            raise RuntimeError(f"Aligned word text is empty at index {index}")
        if end < start:
            raise RuntimeError(f"Aligned word end before start at index {index}")
        if start < previous_start:
            raise RuntimeError(f"Aligned word order is not monotonic at index {index}")
        previous_start = start


def faster_whisper_ctc_pencereleri(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """faster-whisper segmentleri -> CTC pencereleri [{start, end, text}] (boş metin atlanır, süre > 0 olmalı)."""
    pencereler: List[Dict[str, Any]] = []
    for seg in segments or []:
        metin = str(seg.get("text") or "").strip()
        if not metin:
            continue
        start, end = float(seg["start"]), float(seg["end"])
        if end <= start:
            raise RuntimeError(f"faster-whisper + CTC: süresiz pencere ({start:.3f}-{end:.3f} sn): {metin[:40]!r}")
        pencereler.append({"start": start, "end": end, "text": metin})
    return pencereler


def faster_whisper_ctc_metin_ayni(whisper_kelimeleri: List[Dict[str, Any]], ctc_kelimeleri: List[Dict[str, Any]]) -> bool:
    """Boşluklar yok sayılınca aynı metin mi? Whisper "İstanbul" + "'a" diye böler, CTC "İstanbul'a" der (sayı farkı
    metin kaybı değildir; gerçek koşu K24, tr: 105 → 99 kelime, metin aynı)."""
    def birlestir(kelimeler: List[Dict[str, Any]]) -> str:
        return "".join("".join(str(k.get("word") or "").split()) for k in kelimeler)

    return birlestir(whisper_kelimeleri) == birlestir(ctc_kelimeleri)


def faster_whisper_ctc_zaman_asimi(ses_saniye: float, device: str) -> float:
    """CTC alt süreç zaman aşımı: GPU 1800 sn (Parakeet ile aynı); işlemcide ses süresiyle büyür.

    Ölçüm (işlemci): tr xls-r-300m 60 sn ses 42,9 sn (yükleme ~10 sn), en base-960h 23,8 sn ses 16,5 sn; belgedeki
    en kötü işlemci vakası 3,5 dk ses ~10 dk (≈ 2,9×). 3× + 600 sn bu vakayı da kapsar; taban 1800 sn korunur.
    bkz. docs/engineering/timing-sources.md §2.1
    """
    if device == "cuda":
        return 1800.0
    return max(1800.0, 600.0 + float(ses_saniye) * 3.0)


def _faster_whisper_ctc_hizala(
    data: Dict[str, Any],
    wav_path: str,
    run_dir: str,
    whisper_lang: Optional[str],
    device: str,
    cache_dir: str,
) -> Dict[str, Any]:
    """`faster_whisper_ctc`: faster-whisper metni ortak CTC kutusundan geçer (Parakeet ile aynı bağ).

    Pencere = faster-whisper segmentleri; kelime zamanı = CTC (`ctc_speech_bounded_v2`). Whisper'ın kendi kelime
    zamanları yalnız tanılama için `faster_whisper_ctc/whisper_dogal_kelimeler.json` dosyasında kalır. CTC modeli
    yoksa iş açık hatayla durur; Whisper zamanına sessizce düşülmez (ADR 0005, ADR 0009).
    """
    from dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama import run_ctc_word_alignment
    from dublaj_hatti.bolum_00_omurga.runtime.ctc_model_durumu import ctc_modeli_gerekli

    language = normalize_language_code(str(data.get("detected_language") or whisper_lang or "en")) or "en"
    model = ctc_modeli_gerekli(language, cache_dir, FASTER_WHISPER_CTC_ENGINE)
    debug_dir = Path(run_dir) / FASTER_WHISPER_CTC_ENGINE
    debug_dir.mkdir(parents=True, exist_ok=True)
    pencereler = faster_whisper_ctc_pencereleri(list(data.get("segments") or []))
    if not pencereler:
        raise RuntimeError("faster-whisper + CTC: faster-whisper hizalanacak metin üretmedi")
    girdi = debug_dir / "alignment_input_segments.json"
    girdi.write_text(json.dumps(pencereler, ensure_ascii=False, indent=2), encoding="utf-8")
    dogal = [w for seg in data.get("segments") or [] for w in (seg.get("words") or [])]
    (debug_dir / "whisper_dogal_kelimeler.json").write_text(
        json.dumps(dogal, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    zaman_asimi = faster_whisper_ctc_zaman_asimi(_audio_duration_seconds(wav_path), device)
    logger.info("=" * 60)
    logger.info("FASTER-WHISPER + CTC HIZALAMA BASLIYOR")
    logger.info("  Alignment: ctc_kelime_hizalama kutusu (wav2vec2 %s, %s, %s)", model.get("model"), device,
                CTC_WORD_BOUNDARY_POLICY)
    logger.info("  Dil: %s  Pencere: %d  Zaman asimi: %.0f sn", language, len(pencereler), zaman_asimi)
    logger.info("=" * 60)
    sonuc = run_ctc_word_alignment(wav_path, girdi, language, cache_dir, zaman_asimi, device=device,
                                   debug_dir=debug_dir)
    words = list(sonuc.get("words") or [])
    _ctc_kelimelerini_dogrula(words)
    metin_ayni = faster_whisper_ctc_metin_ayni(dogal, words)
    if not metin_ayni:
        logger.warning("faster-whisper + CTC: hizalanan metin Whisper metninden farkli (whisper %d, CTC %d kelime); "
                       "CTC listesi kullanilir (zamansiz kalan kelimeyi CTC kutusu atar, "
                       "docs/engineering/timing-sources.md §6)", len(dogal), len(words))
    ozet = {
        "engine": FASTER_WHISPER_CTC_ENGINE,
        "word_timing_source": "ctc_kelime_hizalama",
        "alignment_window_source": "faster_whisper_segments",
        "language": language,
        "alignment_model": model.get("model"),
        "alignment_device": device,
        "word_boundary_policy": CTC_WORD_BOUNDARY_POLICY,
        "window_count": len(pencereler),
        "whisper_word_count": len(dogal),
        "ctc_word_count": len(words),
        "text_identical": metin_ayni,
        "alignment_subprocess_seconds": sonuc.get("alignment_subprocess_seconds"),
        "ctc_profile_summary": sonuc.get("profile_summary", {}),
    }
    (debug_dir / "report.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("faster-whisper + CTC tamam: kelime %d (whisper %d), %.1f sn", len(words), len(dogal),
                float(sonuc.get("alignment_subprocess_seconds") or 0.0))
    return {
        **{k: v for k, v in data.items() if k not in ("segments", "words")},
        "success": True,
        "segments": list(sonuc.get("segments") or []),
        "words": words,
        "detected_language": language,
        "total_words": len(words),
        "word_timing_source": "ctc_kelime_hizalama",
    }


def check_word_overlaps(aligned: Dict) -> None:
    """
    Transkripsiyon ciktisindaki kelime zamanlamalarinda overlap kontrolu yapar.

    Overlap = Bir kelimenin bitis zamani, sonraki kelimenin baslangic zamanindan buyuk

    Ornek:
        "hello" : 0.0 - 0.8
        "world" : 0.5 - 1.2  <-- OVERLAP! (0.5 < 0.8)

    NOT: Native word timestamps kullanildigi icin overlap olusma
    ihtimali cok dusuk. Bu fonksiyon sadece kontrol amacli tutuluyor.

    Args:
        aligned: Alignment verisi (segments > words)
    """
    logger.info("=" * 60)
    logger.info("OVERLAP KONTROLU BASLIYOR")
    logger.info("=" * 60)

    word_segments = aligned.get("segments") or []
    if not word_segments:
        logger.info("Kelime verisi bulunamadi, overlap kontrolu atlanıyor.")
        return

    total_words = 0
    overlap_count = 0
    overlap_details = []

    for seg_idx, seg in enumerate(word_segments):
        words = seg.get("words") or []
        total_words += len(words)

        for i in range(len(words) - 1):
            current_word = words[i]
            next_word = words[i + 1]

            current_end = float(current_word.get("end", 0.0))
            next_start = float(next_word.get("start", 0.0))

            if current_end > next_start:
                overlap_count += 1
                overlap_ms = (current_end - next_start) * 1000
                detail = (
                    f"  Segment {seg_idx + 1}, Kelime {i + 1}-{i + 2}: "
                    f"'{current_word.get('word', '')}' (bitis: {current_end:.3f}s) -> "
                    f"'{next_word.get('word', '')}' (baslangic: {next_start:.3f}s) "
                    f"[OVERLAP: {overlap_ms:.0f}ms]"
                )
                overlap_details.append(detail)

    logger.info("Toplam kelime sayisi: %d", total_words)
    logger.info("Toplam segment sayisi: %d", len(word_segments))

    if overlap_count == 0:
        logger.info("OVERLAP KONTROLU SONUCU: BASARILI - Hic overlap yok!")
        logger.info("=" * 60)
    else:
        logger.warning("OVERLAP KONTROLU SONUCU: %d overlap tespit edildi", overlap_count)
        for detail in overlap_details:
            logger.warning(detail)
        logger.info("=" * 60)
        logger.warning(
            "NOT: Native word timestamps kullanilir, "
            "overlap nadiren olusur. Devam ediliyor..."
        )


def refine_segment_times_from_words(segments: List[Segment], aligned: Dict) -> None:
    """
    Segment zamanlarini kelime zamanlarindan alarak duzeltir.

    Her segment icin:
    - Baslangic zamani = Ilk kelimenin baslangic zamani
    - Bitis zamani = Son kelimenin bitis zamani

    Bu sayede segment overlap'leri onlenir cunku kelime zamanlari
    overlap kontrolunden gecmis ve dogrulanmistir.

    Args:
        segments: Segment listesi (zamanlar yerinde guncellenir)
        aligned: Alignment verisi (segments > words)
    """
    logger.info("=" * 60)
    logger.info("SEGMENT ZAMANLARI KELIMELERDEN ALINIYOR")
    logger.info("=" * 60)

    word_segments = aligned.get("segments") or []
    if not word_segments:
        logger.warning("Kelime verisi bulunamadi, segment zamanlari degistirilmedi.")
        return

    if len(segments) != len(word_segments):
        logger.warning(
            "Segment sayisi uyusmuyor (segments=%d, aligned=%d), zaman duzeltme atlanıyor.",
            len(segments), len(word_segments)
        )
        return

    corrected_count = 0

    for i, (seg, aligned_seg) in enumerate(zip(segments, word_segments)):
        words = aligned_seg.get("words") or []
        if not words:
            continue
        setattr(seg, "words", list(words))

        old_start = seg.start
        old_end = seg.end

        first_word = words[0]
        last_word = words[-1]

        new_start = float(first_word.get("start", old_start))
        new_end = float(last_word.get("end", old_end))

        if new_start != old_start or new_end != old_end:
            corrected_count += 1
            logger.info(
                "  Segment %d: [%.3fs - %.3fs] -> [%.3fs - %.3fs]",
                i + 1, old_start, old_end, new_start, new_end
            )

        seg.start = new_start
        seg.end = new_end

    logger.info("Toplam %d segment zamani duzeltildi.", corrected_count)
    logger.info("=" * 60)


def _format_time(value: float) -> str:
    return f"{value:.3f}s"


def write_transcripts(
    segments: List[Segment],
    run_dir: str,
    source_label: str,
    src_lang: str,
    target_lang: str,
) -> None:
    if not segments:
        return

    base = os.path.splitext(os.path.basename(source_label))[0] or "Video"

    lang_map = {
        "en": "English", "tr": "Turkish", "fr": "French", "de": "German", "es": "Spanish",
        "it": "Italian", "pt": "Portuguese", "ru": "Russian", "ja": "Japanese", "ko": "Korean",
        "zh": "Chinese", "ar": "Arabic", "hi": "Hindi", "nl": "Dutch", "pl": "Polish",
        "sv": "Swedish", "da": "Danish", "no": "Norwegian", "fi": "Finnish", "cs": "Czech",
        "el": "Greek", "he": "Hebrew", "hu": "Hungarian", "id": "Indonesian", "ms": "Malay",
        "th": "Thai", "vi": "Vietnamese", "uk": "Ukrainian", "ro": "Romanian", "bg": "Bulgarian",
        "hr": "Croatian", "sk": "Slovak", "sl": "Slovenian", "sr": "Serbian", "lt": "Lithuanian",
        "lv": "Latvian", "et": "Estonian", "fa": "Persian", "bn": "Bengali", "ta": "Tamil",
        "te": "Telugu", "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
        "pa": "Punjabi", "ur": "Urdu", "sw": "Swahili", "af": "Afrikaans", "ca": "Catalan",
        "gl": "Galician", "eu": "Basque", "cy": "Welsh", "ga": "Irish", "mt": "Maltese",
        "is": "Icelandic", "mk": "Macedonian", "sq": "Albanian", "bs": "Bosnian", "az": "Azerbaijani",
        "ka": "Georgian", "hy": "Armenian", "ne": "Nepali", "si": "Sinhala", "km": "Khmer",
        "lo": "Lao", "my": "Burmese", "mn": "Mongolian", "kk": "Kazakh", "uz": "Uzbek",
        "tg": "Tajik", "ky": "Kyrgyz", "tk": "Turkmen", "am": "Amharic", "yo": "Yoruba",
        "zu": "Zulu", "xh": "Xhosa", "so": "Somali", "ha": "Hausa", "ig": "Igbo",
    }

    src_lang_lower = src_lang.lower()
    src_lang_name = lang_map.get(src_lang_lower, src_lang.upper())

    src_title = f"Original Transcript ({src_lang_name}) - {base}"

    lines = [src_title, "=" * len(src_title), ""]
    for idx, seg in enumerate(segments, start=1):
        content = seg.text or ""
        lines.append(
            f"{idx}. [{_format_time(seg.start)} - {_format_time(seg.end)}] {content}".strip()
        )

    src_path = os.path.join(run_dir, f"transcript_{src_lang_lower}.txt")

    with open(src_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    logger.info("Transkript dosyasi olusturuldu: %s", src_path)


def write_full_paragraph(
    segments: List[Segment],
    run_dir: str,
    source_lang: str,
) -> None:
    import textwrap

    if not segments:
        return

    full_text = " ".join([seg.text for seg in segments])

    wrapped_text = textwrap.fill(full_text, width=80)

    output_path = os.path.join(run_dir, f"full_paragraf_{source_lang}.txt")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(wrapped_text)

    logger.info("Full paragraf kaydedildi: %s", output_path)


def write_word_level_transcript(
    aligned_segments: Dict,
    run_dir: str,
    source_label: str,
    source_lang: str,
) -> None:
    word_segments = aligned_segments.get("segments") or []
    if not word_segments:
        return

    base = os.path.splitext(os.path.basename(source_label))[0] or "Video"
    title = f"WORD-LEVEL TIMESTAMPS - {base}"
    path = os.path.join(run_dir, "transcript_word_level.txt")

    lines = [
        "=" * len(title),
        title,
        "=" * len(title),
        "",
        "This file contains word-level timestamps from transcription alignment.",
        "Useful for debugging timing issues and advanced analysis.",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Source Language: {source_lang}",
        "",
        f"Total Segments: {len(word_segments)}",
        f"Total Words   : {sum(len(seg.get('words') or []) for seg in word_segments)}",
        "",
        "=" * 80,
        "",
    ]

    for idx, seg in enumerate(word_segments, start=1):
        seg_text = seg.get("text", "").strip()
        words = seg.get("words") or []
        lines.extend(
            [
                f"SEGMENT {idx}",
                "=" * 80,
                f"Time Range : [{_format_time(seg.get('start', 0.0))} - {_format_time(seg.get('end', 0.0))}]",
                f"Duration   : {seg.get('end', 0.0) - seg.get('start', 0.0):.3f}s",
                f'Text       : "{seg_text}"',
                "",
                "Word-Level Timing:",
                "-" * 80,
                "#    Word                 Start (s)    End (s)      Duration (ms)  ",
                "-" * 80,
            ]
        )
        for word_idx, word in enumerate(words, start=1):
            word_text = word.get("word", "").strip()
            start = float(word.get("start", 0.0))
            end = float(word.get("end", start))
            duration_ms = int(max((end - start) * 1000, 0))
            lines.append(
                f"{word_idx:<4} {word_text:<20} {start:<11.3f} {end:<11.3f} {duration_ms:<14}"
            )
        lines.append("-" * 80)
        lines.append(f"Total Words: {len(words)}")
        lines.append("")
        lines.append("=" * 80)
        lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    logger.info("Kelime seviyesinde transkript yazıldı: %s", path)


def _format_time_srt(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_transcript_plain_text(
    segments: List[Segment],
    run_dir: str,
    src_lang: str,
) -> str:
    if not segments:
        return ""

    src_lang_lower = src_lang.lower()
    output_path = os.path.join(run_dir, f"transcript_plain_{src_lang_lower}.txt")

    lines = []
    for seg in segments:
        content = (seg.text or "").strip()
        if content:
            lines.append(content)

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    logger.info("Duz metin transkript olusturuldu: %s", output_path)
    return output_path


def write_transcript_srt(
    segments: List[Segment],
    run_dir: str,
    src_lang: str,
) -> str:
    if not segments:
        return ""

    src_lang_lower = src_lang.lower()
    output_path = os.path.join(run_dir, f"transcript_{src_lang_lower}.srt")

    lines = []
    for idx, seg in enumerate(segments, start=1):
        content = (seg.text or "").strip()
        if not content:
            continue

        start_time = _format_time_srt(seg.start)
        end_time = _format_time_srt(seg.end)

        lines.append(str(idx))
        lines.append(f"{start_time} --> {end_time}")
        lines.append(content)
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    logger.info("SRT altyazi dosyasi olusturuldu: %s", output_path)
    return output_path


def check_global_word_overlaps(
    aligned_segments: Dict,
    run_dir: str,
    source_label: str,
) -> None:
    """
    Tum kelimeleri global timeline olarak siralar ve overlap kontrolu yapar.

    Segment farketmeksizin tum kelimeler zamana gore siralanir ve
    ardisik kelimeler arasinda overlap olup olmadigi kontrol edilir.

    Args:
        aligned_segments: Alignment verisi (segments > words)
        run_dir: Cikti klasoru
        source_label: Kaynak dosya adi

    Raises:
        RuntimeError: Overlap tespit edilirse hata firlatir
    """
    logger.info("=" * 60)
    logger.info("GLOBAL WORD TIMELINE KONTROLU BASLIYOR")
    logger.info("=" * 60)

    word_segments = aligned_segments.get("segments") or []
    if not word_segments:
        logger.info("Kelime verisi bulunamadi, global kontrol atlaniyor.")
        return

    all_words = []
    for seg_idx, seg in enumerate(word_segments):
        words = seg.get("words") or []
        for word in words:
            all_words.append({
                "word": word.get("word", "").strip(),
                "start": float(word.get("start", 0.0)),
                "end": float(word.get("end", 0.0)),
                "segment": seg_idx + 1,
            })

    if not all_words:
        logger.info("Hic kelime bulunamadi, global kontrol atlaniyor.")
        return

    all_words.sort(key=lambda w: w["start"])

    overlap_count = 0
    tolerance_boundary_count = 0
    overlap_details = []

    for i in range(len(all_words) - 1):
        current = all_words[i]
        next_word = all_words[i + 1]

        overlap_seconds = current["end"] - next_word["start"]
        if overlap_seconds > ZAMAN_KARSILASTIRMA_TOLERANSI:
            overlap_count += 1
            overlap_ms = overlap_seconds * 1000
            if current["segment"] == next_word["segment"]:
                overlap_type = "SEGMENT ICI"
            else:
                overlap_type = f"SEGMENT ARASI ({current['segment']} -> {next_word['segment']})"
            detail = (
                f"  #{i + 1}-{i + 2}: '{current['word']}' [{current['end']:.3f}s] -> "
                f"'{next_word['word']}' [{next_word['start']:.3f}s] "
                f"| {overlap_ms:.0f}ms | {overlap_type}"
            )
            overlap_details.append(detail)
        elif overlap_seconds > 0.0:
            tolerance_boundary_count += 1

    base = os.path.splitext(os.path.basename(source_label))[0] or "Video"
    path = os.path.join(run_dir, "global_word_timeline.txt")

    overlap_status = "YOK" if overlap_count == 0 else f"{overlap_count} adet tespit edildi"

    lines = [
        "=" * 72,
        f"GLOBAL WORD TIMELINE - {base}",
        "=" * 72,
        "",
        f"Kaynak: {os.path.basename(source_label)}",
        f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Toplam Segment: {len(word_segments)}",
        f"Toplam Kelime: {len(all_words)}",
        f"Zaman Karsilastirma Toleransi: {ZAMAN_KARSILASTIRMA_TOLERANSI:.12f}s",
        f"Tolerans Icinde Esit Sayilan Sinir: {tolerance_boundary_count}",
        f"Overlap Durumu: {overlap_status}",
        "",
        "=" * 72,
        "",
        "#     Kelime               Baslangic    Bitis        Sure(ms)   Segment",
        "-" * 72,
    ]

    for idx, w in enumerate(all_words, start=1):
        duration_ms = int(max((w["end"] - w["start"]) * 1000, 0))
        lines.append(
            f"{idx:<5} {w['word']:<20} {w['start']:<12.3f} {w['end']:<12.3f} {duration_ms:<10} {w['segment']}"
        )

    lines.extend([
        "",
        "=" * 72,
        "OVERLAP DETAYLARI",
        "=" * 72,
        "",
    ])

    if overlap_count == 0:
        lines.append("(Overlap tespit edilmedi)")
    else:
        lines.append("Kelime#   Kelime1 [bitis] -> Kelime2 [baslangic] | Miktar | Tur")
        lines.append("-" * 72)
        for detail in overlap_details:
            lines.append(detail)

    lines.append("")
    lines.append("=" * 72)

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    logger.info("Global word timeline yazildi: %s", path)
    logger.info("Toplam kelime: %d, Toplam segment: %d", len(all_words), len(word_segments))

    if overlap_count == 0:
        logger.info("GLOBAL OVERLAP KONTROLU: BASARILI - Hic overlap yok!")
    else:
        logger.error("GLOBAL OVERLAP KONTROLU: BASARISIZ!")
        logger.error("Toplam %d overlap tespit edildi:", overlap_count)
        for detail in overlap_details:
            logger.error("  %s", detail)
        raise RuntimeError(
            f"Global timeline'da {overlap_count} adet overlap tespit edildi. "
            f"Detaylar icin: {path}"
        )

    logger.info("=" * 60)


def save_wave(path: str, audio: np.ndarray, sample_rate: int) -> None:
    logger.info("Dublaj ses dosyasi yaziliyor: %s", path)
    sf.write(path, audio, sample_rate, subtype='FLOAT' if np.max(np.abs(audio), initial=0) >= 1 else 'PCM_24')


def mux_video_and_audio(input_video: str, dubbed_wav: str, output_video: str) -> None:
    logger.info("Video ile ses birleştiriliyor: %s", output_video)
    cmd = [
        ffmpeg_yolu(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        input_video,
        "-i",
        dubbed_wav,
        "-c:v",
        "copy",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        output_video,
    ]
    subprocess.run(cmd, check=True, **GIZLI_SUREC)


def _prepare_visual_video(video_path: str, run_dir: str, enabled: bool) -> tuple[str, Dict[str, Any], List[str]]:
    """Akıllı kare (isteğe bağlı, extras `akilli-kare`): kenar bantlarını kırpar; kapalı/kurulu değilse kaynak aynen."""
    result: Dict[str, Any] = {
        "status": "disabled",
        "enabled": False,
        "crop_applied": False,
        "reason": "user_disabled",
        "video_path": video_path,
    }
    if not enabled:
        return video_path, result, []
    from dublaj_hatti.bolum_10_kaynak_edinme.akilli_kare_yakalama import (
        KURULUM_IPUCU,
        akilli_kare_kurulu,
        apply_smart_frame_capture,
    )

    if not akilli_kare_kurulu():
        logger.warning("[AKILLI_KARE] %s; kaynak video değiştirilmeden kullanılıyor", KURULUM_IPUCU)
        result.update(enabled=True, reason="not_installed")
        return video_path, result, []
    result = apply_smart_frame_capture(video_path, run_dir, enabled=True, logger=logger)
    visual_video_path = str(result["video_path"])
    artifacts: List[str] = []
    for path_value in (visual_video_path, result.get("analysis_path"), result.get("preview_path")):
        artifact_path = str(path_value or "")
        if artifact_path and artifact_path != video_path and artifact_path not in artifacts:
            artifacts.append(artifact_path)
    return visual_video_path, result, artifacts


def _run_full_text_dub_after_transcription(
    video_path: str,
    wav_path: str,
    demucs_clean_path: Optional[str],
    segments: List[Segment],
    source_lang: str,
    cfg: DubConfig,
    run_dir: str,
    request_metadata: Dict[str, Any],
    checkpoint_store: Optional[PipelineCheckpointStore] = None,
    background_preserved: Optional[bool] = None,
) -> Dict:
    if background_preserved is None:
        background_preserved = bool(cfg.preserve_background_audio)
    if cfg.tts_engine != "supertonic":
        raise ValueError("Full Metin Dublaji yalniz Supertonic TTS kullanir")
    if cfg.translator_engine != "codex_bridge":
        raise ValueError("Full Metin Dublaji ilk surumde yalniz Codex Exec ceviri motorunu kullanir")
    if checkpoint_store is None:
        checkpoint_store = PipelineCheckpointStore(
            run_dir,
            pipeline_kind="full_text",
            source_identity=f"direct_full_text:{Path(video_path).resolve()}",
        )
    speech_window_inputs = {
        "segments_hash": canonical_json_hash(_segments_to_checkpoint_payload(segments)),
        "source_lang": source_lang,
    }
    if checkpoint_store.can_restore("full_text_konusma_penceresi", 7, 1, speech_window_inputs):
        speech_payload = checkpoint_store.stage_payload("full_text_konusma_penceresi")
        speech_window = FullTextSpeechWindow(
            source_text=str(speech_payload["source_text"]),
            speech_start=float(speech_payload["speech_start"]),
            speech_end=float(speech_payload["speech_end"]),
        )
    else:
        checkpoint_store.begin_stage("full_text_konusma_penceresi", 7, 1, speech_window_inputs)
        speech_window = build_full_text_speech_window(segments)
        checkpoint_store.complete_stage("full_text_konusma_penceresi", {
            "source_text": speech_window.source_text,
            "speech_start": speech_window.speech_start,
            "speech_end": speech_window.speech_end,
        })

    translation_inputs = {
        "source_text_hash": canonical_json_hash(speech_window.source_text),
        "source_lang": source_lang,
        "target_lang": cfg.target_lang,
        "bridge_backend": _request_bridge_backend(cfg, request_metadata),
    }
    translator = FullTextBridgeTranslator(
        source_lang=source_lang,
        target_lang=cfg.target_lang,
        bridge_backend=translation_inputs["bridge_backend"],
    )
    source_path = os.path.join(run_dir, f"full_text_source_{source_lang}.txt")
    translated_path = os.path.join(run_dir, f"full_text_translated_{cfg.target_lang}.txt")
    transcript_path = os.path.join(run_dir, f"full_text_transcript_{source_lang}_to_{cfg.target_lang}.txt")
    if checkpoint_store.can_restore("full_text_ceviri", 8, 3, translation_inputs):
        translation_payload = checkpoint_store.stage_payload("full_text_ceviri")
        translated_text = str(translation_payload["translated_text"])
        video_usage_report = str(translation_payload.get("video_usage_report") or "")
        if video_usage_report:
            translator.last_video_usage_report = video_usage_report
    else:
        checkpoint_store.begin_stage("full_text_ceviri", 8, 3, translation_inputs)
        def translate_full_text_operation(route):
            current_translator = FullTextBridgeTranslator(
                source_lang=source_lang,
                target_lang=cfg.target_lang,
                bridge_backend=translation_inputs["bridge_backend"],
            )
            return current_translator, current_translator.translate_full_text(speech_window.source_text, run_dir)

        translator, translated_text = run_with_internet_gateway(
            translate_full_text_operation,
            "full_text_ceviri",
            logger,
            run_dir,
        )
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(speech_window.source_text + "\n")
        with open(translated_path, "w", encoding="utf-8") as f:
            f.write(translated_text + "\n")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write("FULL METIN DUBLAJ TRANSKRIPTI\n")
            f.write("=============================\n\n")
            f.write(f"KAYNAK METIN ({source_lang.upper()})\n")
            f.write("------------------------\n")
            f.write(speech_window.source_text + "\n\n")
            f.write(f"CEVIRI ({cfg.target_lang.upper()})\n")
            f.write("------------\n")
            f.write(translated_text + "\n")
        checkpoint_store.complete_stage(
            "full_text_ceviri",
            {
                "translated_text": translated_text,
                "video_usage_report": str(getattr(translator, "last_video_usage_report", "") or ""),
            },
            [source_path, translated_path, transcript_path],
        )
    if not os.path.isfile(transcript_path):
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(speech_window.source_text + "\n")
        with open(translated_path, "w", encoding="utf-8") as f:
            f.write(translated_text + "\n")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(f"KAYNAK METIN ({source_lang.upper()})\n{speech_window.source_text}\n\n")
            f.write(f"CEVIRI ({cfg.target_lang.upper()})\n{translated_text}\n")
    checkpoint_store.emit_artifact_ready("bilingual_dubbing_transcript", transcript_path)
    duration_fit_mode = str(cfg.full_text_duration_fit_mode or "audio_to_video").strip().lower()
    if duration_fit_mode not in {"audio_to_video", "video_to_audio"}:
        raise ValueError("Full Metin sure uyumu secimi gecersiz")
    tts_inputs = {
        "translated_text_hash": canonical_json_hash(translated_text),
        "supertonic_synthesis_contract": SUPERTONIC_SYNTHESIS_CONTRACT,
        "voice_id": cfg.tts_voice_id or "F1",
        "target_lang": cfg.target_lang,
        **_ema_checkpoint_girdisi(cfg),
        "duration_fit_mode": duration_fit_mode,
        "speech_duration": speech_window.duration,
    }
    if checkpoint_store.can_restore("full_text_tek_ses_tts", 9, 1, tts_inputs):
        tts_payload = checkpoint_store.stage_payload("full_text_tek_ses_tts")
        full_text_tts_manifest = _checkpoint_absolute_path(run_dir, tts_payload["manifest_path"])
        synthesis, final_audio, known_alignment_windows = _read_full_text_tts_checkpoint(full_text_tts_manifest)
    else:
        checkpoint_store.begin_stage("full_text_tek_ses_tts", 9, 1, tts_inputs)
        if cfg.tts_engine == "ema_lightning":
            from dublaj_hatti.bolum_50_seslendirme.ema_lightning_tts import synthesize_full_text_ema

            synthesis = synthesize_full_text_ema(translated_text, cfg, run_dir)
        else:
            synthesis = synthesize_full_text_supertonic(
                text=translated_text,
                voice_id=cfg.tts_voice_id or "F1",
                language=cfg.target_lang,
                work_dir=run_dir,
            )
        final_audio = synthesis.audio
        if duration_fit_mode == "audio_to_video":
            final_audio = fit_audio_to_speech_window(
                audio=synthesis.audio,
                sample_rate=synthesis.sample_rate,
                target_duration=speech_window.duration,
                work_dir=run_dir,
            )
        known_alignment_windows = list(build_full_text_alignment_windows(synthesis, final_audio))
        full_text_tts_manifest, full_text_tts_dir = _write_full_text_tts_checkpoint(
            run_dir,
            synthesis,
            final_audio,
            known_alignment_windows,
        )
        checkpoint_store.complete_stage(
            "full_text_tek_ses_tts",
            {"manifest_path": _checkpoint_relative_path(run_dir, full_text_tts_manifest)},
            [full_text_tts_manifest, full_text_tts_dir],
        )
    final_duration = len(final_audio) / synthesis.sample_rate
    full_segment = Segment(
        index=1,
        start=speech_window.speech_start,
        end=speech_window.speech_end,
        text=translated_text,
    )
    timeline_tts_duration = speech_window.duration if duration_fit_mode == "audio_to_video" else final_duration
    timing_infos = [{
        "segment_index": 1,
        "tts_raw_duration": timeline_tts_duration,
        "original_duration": speech_window.duration,
        "start_time": speech_window.speech_start,
    }]
    segment_audios = {1: final_audio}
    dubbed_wav = os.path.join(run_dir, f"dubbed_{cfg.target_lang}.wav")
    save_wave(dubbed_wav, final_audio, synthesis.sample_rate)
    canonical_output_video = os.path.join(run_dir, f"dubbed_{cfg.target_lang}.mp4")
    output_video = os.path.join(run_dir, f"dubbed_{cfg.target_lang}_full_text_working.mp4")
    smart_frame_enabled = bool(getattr(cfg, "smart_frame_capture_enabled", False))
    subtitle_inputs = {
        "tts_manifest_path": _checkpoint_relative_path(run_dir, full_text_tts_manifest),
        "subtitle_mode": normalize_subtitle_mode(getattr(cfg, "subtitle_mode", "none")),
        "source_video_path": _checkpoint_input_path(run_dir, video_path),
        "smart_frame_capture_enabled": smart_frame_enabled,
        "subtitle_timing_contract_version": SUBTITLE_TIMING_CONTRACT_SCHEMA_VERSION,
    }
    if subtitle_inputs["subtitle_mode"] == "rollup":
        from dublaj_hatti.bolum_50_seslendirme.altyazili_dublaj.rollup import rollup_contract_inputs

        subtitle_inputs["rollup_contract"] = rollup_contract_inputs()
    if checkpoint_store.can_restore("full_text_final_altyazi_alignment", 10, 1, subtitle_inputs):
        subtitle_payload = checkpoint_store.stage_payload("full_text_final_altyazi_alignment")
        subtitle_result_path = _checkpoint_absolute_path(run_dir, subtitle_payload["result_path"])
        visual_video_path = _checkpoint_absolute_path(run_dir, subtitle_payload.get("visual_video_path") or _checkpoint_input_path(run_dir, video_path))
        subtitle_artifacts = _read_pipeline_json(subtitle_result_path)
    else:
        checkpoint_store.begin_stage("full_text_final_altyazi_alignment", 10, 1, subtitle_inputs)
        visual_video_path, smart_frame_result, smart_frame_artifacts = _prepare_visual_video(
            video_path,
            run_dir,
            smart_frame_enabled,
        )
        subtitle_artifacts = prepare_one_pass_subtitle_assets(
            video_path=visual_video_path,
            output_video=output_video,
            segments=[full_segment],
            timing_infos=timing_infos,
            segment_audios=segment_audios,
            cfg=cfg,
            run_dir=run_dir,
            known_alignment_windows=list(known_alignment_windows),
        )
        subtitle_result_path = _write_pipeline_json(run_dir, "pipeline_full_text_subtitle_result.json", subtitle_artifacts)
        subtitle_paths = [subtitle_result_path, *smart_frame_artifacts]
        if subtitle_artifacts.get("enabled") and subtitle_artifacts.get("ass_path"):
            subtitle_paths.extend([
                str(subtitle_artifacts["ass_path"]),
                str(subtitle_artifacts["timing_contract_path"]),
                str(subtitle_artifacts["timeline_path"]),
                str(subtitle_artifacts["timing_report_path"]),
            ])
        checkpoint_store.complete_stage(
            "full_text_final_altyazi_alignment",
            {
                "result_path": _checkpoint_relative_path(run_dir, subtitle_result_path),
                "visual_video_path": _checkpoint_input_path(run_dir, visual_video_path),
                "smart_frame_status": str(smart_frame_result.get("status") or ""),
            },
            subtitle_paths,
        )
    subtitle_ass_path = str(subtitle_artifacts.get("ass_path") or "") if subtitle_artifacts.get("enabled") else ""
    sample_rate = synthesis.sample_rate
    chunk_count = synthesis.chunk_count
    segment_audios = _checkpoint_audio_files(full_text_tts_manifest, sample_rate, full_text=True)
    del final_audio, synthesis
    logger.info("[AUDIO-MEMORY] Full text arrays released after subtitle preparation")
    mux_inputs = {
        "tts_manifest_path": _checkpoint_relative_path(run_dir, full_text_tts_manifest),
        "subtitle_result_path": _checkpoint_relative_path(run_dir, subtitle_result_path),
        "duration_fit_mode": duration_fit_mode,
        "final_audio_filter": SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER,
        "video_output_policy": cfg.video_output_policy,
        "video_encoder_cq": cfg.video_encoder_cq,
        "max_output_bytes": cfg.max_output_bytes,
        "source_video_path": _checkpoint_input_path(run_dir, visual_video_path),
    }
    base_output_video = os.path.join(run_dir, f"dubbed_{cfg.target_lang}_full_text_base_mux.mp4")
    timeline_audio_path = os.path.join(run_dir, "audio_new_timeline.wav")
    if checkpoint_store.can_restore("full_text_video_sure_uyumu_ve_final_mux", 11, 2, mux_inputs):
        mux_payload = checkpoint_store.stage_payload("full_text_video_sure_uyumu_ve_final_mux")
        base_output_video = _checkpoint_absolute_path(run_dir, mux_payload["output_video"])
        video_result_path = _checkpoint_absolute_path(run_dir, mux_payload["result_path"])
        timeline_audio_path = _checkpoint_absolute_path(run_dir, mux_payload["timeline_audio_path"])
        video_result = _restore_video_result(run_dir, _read_pipeline_json(video_result_path))
    else:
        checkpoint_store.begin_stage("full_text_video_sure_uyumu_ve_final_mux", 11, 2, mux_inputs)
        Path(timeline_audio_path).unlink(missing_ok=True)
        video_result = run_video_processor_subprocess(
            input_video=visual_video_path,
            segments=[full_segment],
            timing_infos=timing_infos,
            segment_audios=segment_audios,
            output_video=base_output_video,
            work_dir=run_dir,
            sample_rate=sample_rate,
            subtitle_ass_path=subtitle_ass_path,
            final_audio_filter=SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER,
            video_output_policy=cfg.video_output_policy,
            video_encoder_cq=cfg.video_encoder_cq,
            max_output_bytes=cfg.max_output_bytes,
        )
        video_result_path = _write_pipeline_json(
            run_dir,
            "pipeline_full_text_video_result.json",
            _portable_video_result(run_dir, video_result),
        )
        checkpoint_store.complete_stage(
            "full_text_video_sure_uyumu_ve_final_mux",
            {
                "output_video": _checkpoint_relative_path(run_dir, base_output_video),
                "result_path": _checkpoint_relative_path(run_dir, video_result_path),
                "timeline_audio_path": _checkpoint_relative_path(run_dir, timeline_audio_path),
            },
            [base_output_video, video_result_path, timeline_audio_path, *_video_result_audio_artifacts(video_result)],
        )
    shutil.copy2(base_output_video, output_video)
    background_artifacts: Dict[str, str] = {}
    new_timeline_duration = float(video_result.get("new_duration") or 0.0)
    background_inputs = {
        "mux_result_path": _checkpoint_relative_path(run_dir, video_result_path),
        "enabled": background_preserved,
        "sample_rate": sample_rate,
        "new_timeline_duration": new_timeline_duration,
    }
    if background_preserved:
        background_inputs["background_gain_contract"] = SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER
    if not background_preserved:
        if not checkpoint_store.can_restore("arka_plan_miksi", 15, 2, background_inputs):
            checkpoint_store.skip_stage("arka_plan_miksi", 15, 2, background_inputs, "disabled_by_configuration")
    elif checkpoint_store.can_restore("arka_plan_miksi", 15, 2, background_inputs):
        background_payload = checkpoint_store.stage_payload("arka_plan_miksi")
        background_output_video = _checkpoint_absolute_path(run_dir, background_payload["output_video"])
        background_result_path = _checkpoint_absolute_path(run_dir, background_payload["result_path"])
        background_artifacts = _restore_background_audio_checkpoint_map(
            run_dir,
            _read_pipeline_json(background_result_path),
            background_payload,
        )
        shutil.copy2(background_output_video, output_video)
    else:
        checkpoint_store.begin_stage("arka_plan_miksi", 15, 2, background_inputs)
        background_output_video = os.path.join(run_dir, f"dubbed_{cfg.target_lang}_full_text_background.mp4")
        shutil.copy2(output_video, background_output_video)
        background_artifacts = _apply_preserved_background_audio(
            background_output_video,
            video_result.get("timeline", []),
            run_dir,
            sample_rate,
            new_timeline_duration,
            "96k" if cfg.video_output_policy == "max_mb" else "192k",
            cfg.max_output_bytes if cfg.video_output_policy == "max_mb" else 0,
            supertonic_constant_gain=True,
        )
        background_result_path = _write_pipeline_json(
            run_dir,
            "pipeline_full_text_background_result.json",
            _portable_checkpoint_path_fields(
                run_dir,
                background_artifacts,
                ("background_audio", "background_audio_new_timeline", "background_mixed_audio", "dubbed_audio",
                 "background_raw_mixed_audio", "background_gain_report"),
            ),
        )
        background_audio_artifacts = _background_audio_checkpoint_map(run_dir, background_artifacts)
        checkpoint_store.complete_stage(
            "arka_plan_miksi",
            {
                "output_video": _checkpoint_relative_path(run_dir, background_output_video),
                "result_path": _checkpoint_relative_path(run_dir, background_result_path),
                "audio_artifacts": background_audio_artifacts,
            },
            [
                background_output_video,
                background_result_path,
                *[_checkpoint_absolute_path(run_dir, path) for path in background_audio_artifacts.values()],
            ],
        )
        shutil.copy2(background_output_video, output_video)
    final_dubbed_audio = background_artifacts.get("dubbed_audio") or timeline_audio_path
    shutil.copy2(output_video, canonical_output_video)
    output_video = canonical_output_video
    final_inputs = {
        "mux_result_path": _checkpoint_relative_path(run_dir, video_result_path),
        "background_enabled": background_preserved,
        "output_video": _checkpoint_relative_path(run_dir, output_video),
    }
    if checkpoint_store.can_restore("final_dogrulama_ve_meta", 17, 1, final_inputs):
        final_payload = checkpoint_store.stage_payload("final_dogrulama_ve_meta")
        meta = _read_pipeline_json(_checkpoint_absolute_path(run_dir, final_payload["meta_path"]))
        checkpoint_store.mark_pipeline_completed()
        return meta
    checkpoint_store.begin_stage("final_dogrulama_ve_meta", 17, 1, final_inputs)
    meta: Dict[str, Any] = {
        "run_dir": run_dir,
        "source_video": video_path,
        "source_audio": wav_path,
        "clean_audio": demucs_clean_path or "",
        "dubbed_audio": final_dubbed_audio,
        "dubbed_video": output_video,
        "source_language": source_lang,
        "target_language": cfg.target_lang,
        "full_text_transcript_file": transcript_path,
        "dubbing_mode": "full_text",
        "full_text_duration_fit_mode": duration_fit_mode,
        "speech_start": speech_window.speech_start,
        "speech_end": speech_window.speech_end,
        "speech_duration": speech_window.duration,
        "full_text_tts_duration": final_duration,
        "supertonic_chunk_count": chunk_count,
        "supertonic_synthesis_contract": SUPERTONIC_SYNTHESIS_CONTRACT,
        "supertonic_final_audio_profile": video_result.get("final_audio_profile", {}),
        "tts_engine": cfg.tts_engine,
        "tts_voice": _tts_ses_etiketi(cfg),
        "transcription_engine": cfg.transcription_engine,
        "model_name": cfg.model_name,
        "compute_type": cfg.compute_type,
        "transcription_preset": request_metadata.get("transcription_preset", ""),
        "transcription_preset_owner": request_metadata.get("transcription_preset_owner", ""),
        "preserve_background_audio": background_preserved,
        "auto_background_preservation": bool(cfg.auto_background_preservation),
        "subtitle_mode": normalize_subtitle_mode(getattr(cfg, "subtitle_mode", "none")),
        "subtitle_artifacts": subtitle_artifacts,
        "video_duration": float(video_result.get("original_duration") or 0.0),
        "source_video_duration": float(video_result.get("original_duration") or 0.0),
        "new_timeline_duration": new_timeline_duration,
    }
    meta.update(_transcription_runtime_metadata(cfg))
    video_usage_report = getattr(translator, "last_video_usage_report", "")
    if isinstance(video_usage_report, str) and video_usage_report:
        meta["video_usage_report"] = video_usage_report
    if background_artifacts:
        meta.update(background_artifacts)
    if cfg.ai_label:
        meta.update(yapay_zeka_etiketi_ekle(output_video))
    with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    log_video_metadata(output_video, "ISLENMIS VIDEO (Full Metin Dublaji)", logger)
    checkpoint_store.complete_stage(
        "final_dogrulama_ve_meta",
        {"meta_path": _checkpoint_relative_path(run_dir, os.path.join(run_dir, "meta.json"))},
        [os.path.join(run_dir, "meta.json"), output_video],
    )
    checkpoint_store.mark_pipeline_completed()
    return meta


def full_dub_pipeline(source: str, base_dir: str, cfg: Optional[DubConfig] = None, request_metadata: Optional[Dict] = None) -> Dict:
    if cfg is None:
        cfg = DubConfig()
    cfg.transcription_decoder_profile = resolve_transcription_decoder_profile(
        cfg.transcription_engine,
        cfg.model_name,
        cfg.compute_type,
        cfg.transcription_decoder_profile,
    )

    if request_metadata is None:
        request_metadata = {}
    if cfg.translator_engine == "codex_bridge":
        _request_bridge_backend(cfg, request_metadata)

    requested_resume_run_dir = str(request_metadata.get("resume_run_dir") or "").strip()
    _youtube_json3_on_denetim(source, cfg, resume=bool(requested_resume_run_dir))
    if requested_resume_run_dir:
        from dublaj_hatti.bolum_00_omurga.runtime.output_paths import get_output_root

        base_dir_path = get_output_root(base_dir, create=False).resolve()
        resume_run_dir_path = Path(requested_resume_run_dir).resolve()
        try:
            resume_run_dir_path.relative_to(base_dir_path)
        except ValueError as exc:
            raise ValueError(f"Devam klasoru output kokunun disinda olamaz: {resume_run_dir_path}") from exc
        temp_run_dir = str(resume_run_dir_path)
        if not os.path.isdir(temp_run_dir):
            raise FileNotFoundError(f"Devam edilecek pipeline klasoru bulunamadi: {temp_run_dir}")
    else:
        temp_run_dir = ensure_run_dir(base_dir, video_title=None)
    pipeline_event_callback = request_metadata.get("pipeline_event_callback")
    if not callable(pipeline_event_callback):
        pipeline_event_callback = None
    checkpoint_store = PipelineCheckpointStore(
        temp_run_dir,
        pipeline_kind=str(getattr(cfg, "dubbing_mode", "segment_sync") or "segment_sync"),
        source_identity=source,
        job_id=request_metadata.get("job_id"),
        event_callback=pipeline_event_callback,
        selection_graph_version=str(request_metadata.get("selection_graph_version") or ""),
        selection_graph_hash=str(request_metadata.get("selection_graph_hash") or ""),
    )
    setup_file_logging(temp_run_dir)
    _apply_engine_sample_rate(cfg, logger)
    logger.info("Video kaynagi: %s", source)
    logger.info("Gecici run klasoru: %s", temp_run_dir)

    dubbed_audio: Optional[np.ndarray] = None
    checkpoint_store.acquire()

    try:
        source_stage_inputs = {"source": source}
        if checkpoint_store.can_restore("video_indirme_veya_kopyalama", 2, 1, source_stage_inputs):
            source_payload = checkpoint_store.stage_payload("video_indirme_veya_kopyalama")
            run_dir = str(checkpoint_store.run_dir)
            video_path = _checkpoint_absolute_path(run_dir, source_payload["video_path"])
            video_title = str(source_payload["video_title"])
            source_lang = source_payload.get("source_lang")
            logger.info("Checkpoint kullanildi: video_indirme_veya_kopyalama")
        else:
            checkpoint_store.begin_stage("video_indirme_veya_kopyalama", 2, 1, source_stage_inputs)
            try:
                video_path, video_title, source_lang = run_with_internet_gateway(
                    lambda route: prepare_source_video(source, temp_run_dir, logger=logger),
                    "video_indirme_veya_kopyalama",
                    logger,
                    temp_run_dir,
                )

                from dublaj_hatti.bolum_10_kaynak_edinme.adim_10_dosya_adi_guvenligi.filename_sanitizer import sanitize_filename
                ts = os.path.basename(temp_run_dir).replace("run_", "")
                sanitized_title = sanitize_filename(video_title, keep_case=False, source_lang=source_lang)
                if len(sanitized_title) > 50:
                    sanitized_title = sanitized_title[:50].rstrip('_')

                output_root = os.path.dirname(temp_run_dir)
                new_run_dir = os.path.join(output_root, f"{sanitized_title}_{ts}")

                if temp_run_dir != new_run_dir and not os.path.exists(new_run_dir):
                    previous_handler = getattr(logger, "_file_handler", None)
                    if previous_handler:
                        logger.removeHandler(previous_handler)
                        try:
                            previous_handler.close()
                        except Exception:
                            pass
                        logger._file_handler = None

                    os.rename(temp_run_dir, new_run_dir)
                    run_dir = new_run_dir
                    checkpoint_store.relocate(run_dir)
                    temp_run_dir = run_dir
                    video_path = os.path.join(run_dir, os.path.basename(video_path))

                    setup_file_logging(run_dir)
                    logger.info("Klasor yeniden adlandirildi: %s", run_dir)
                else:
                    run_dir = temp_run_dir
                checkpoint_store.complete_stage(
                    "video_indirme_veya_kopyalama",
                    {
                        "video_path": _checkpoint_relative_path(run_dir, video_path),
                        "video_title": video_title,
                        "source_lang": source_lang,
                    },
                    [video_path],
                )
            except Exception as exc:
                checkpoint_store.fail_stage("video_indirme_veya_kopyalama", exc)
                raise

        logger.info("=" * 60)
        logger.info("UYGULAMA BASLATILDI - VIDEO DUBLAJI")
        logger.info("=" * 60)
        logger.info("Kaynak: %s", request_metadata.get("source", "BILINMIYOR"))
        logger.info("Baslatma Yontemi: %s", request_metadata.get("launch_method", "MANUEL"))
        logger.info("Istek Zamani: %s", request_metadata.get("request_time", "BILINMIYOR"))
        logger.info("Video URL: %s", source)
        logger.info("Platform: %s", request_metadata.get("platform", "TESPIT EDILECEK"))
        logger.info("Istek Modu: VIDEO_DUBLAJI")
        logger.info("=" * 60)
        logger.info("")
        logger.info("=" * 60)
        _log_secilen_parametreler(logger, cfg, request_metadata)
        logger.info("=" * 60)
        logger.info("")
        logger.info("Dublaj pipeline basladi. run_dir=%s", run_dir)

        log_video_metadata(video_path, "ORIJINAL VIDEO (Download sonrasi)", logger)

        audio_extract_inputs = {
            "video_path": _checkpoint_relative_path(run_dir, video_path),
            "use_demucs": bool(cfg.use_demucs),
            "sample_rate": 44100 if cfg.use_demucs else 16000,
            "channels": 2 if cfg.use_demucs else 1,
        }
        if checkpoint_store.can_restore("kaynak_ses_cikarma", 3, 1, audio_extract_inputs):
            audio_payload = checkpoint_store.stage_payload("kaynak_ses_cikarma")
            wav_path = _checkpoint_absolute_path(run_dir, audio_payload["source_audio_path"])
            logger.info("Checkpoint kullanildi: kaynak_ses_cikarma")
        else:
            checkpoint_store.begin_stage("kaynak_ses_cikarma", 3, 1, audio_extract_inputs)
            try:
                wav_path = _extract_source_audio(video_path, cfg, run_dir)
                checkpoint_store.complete_stage(
                    "kaynak_ses_cikarma",
                    {"source_audio_path": _checkpoint_relative_path(run_dir, wav_path)},
                    [wav_path],
                )
            except Exception as exc:
                checkpoint_store.fail_stage("kaynak_ses_cikarma", exc)
                raise

        _validate_background_selection(cfg)
        demucs_inputs = {
            "source_audio_path": _checkpoint_relative_path(run_dir, wav_path),
            "enabled": bool(cfg.use_demucs),
            "model": DEMUCS_MODEL_NAME,
            "prepare_asr_ready": bool(cfg.use_demucs and cfg.transcription_engine != "whisperx"),
        }
        if cfg.auto_background_preservation:
            demucs_inputs["background_policy"] = AUTO_BACKGROUND_POLICY
            demucs_inputs["background_detection_contract"] = BACKGROUND_DETECTION_CONTRACT
        background_preserved = bool(cfg.preserve_background_audio)
        if cfg.auto_background_preservation:
            demucs_clean_path = None
            audio_for_asr = wav_path
            background_preserved = _run_auto_background_stage(
                checkpoint_store, demucs_inputs, video_path, wav_path, run_dir
            )
        elif not cfg.use_demucs:
            if not checkpoint_store.can_restore("demucs_vokal_ayirma", 4, 2, demucs_inputs):
                checkpoint_store.skip_stage(
                    "demucs_vokal_ayirma",
                    4,
                    2,
                    demucs_inputs,
                    "disabled_by_configuration",
                )
            demucs_clean_path = None
            audio_for_asr = wav_path
        elif checkpoint_store.can_restore("demucs_vokal_ayirma", 4, 2, demucs_inputs):
            demucs_payload = checkpoint_store.stage_payload("demucs_vokal_ayirma")
            demucs_clean_path = _checkpoint_absolute_path(run_dir, demucs_payload["clean_audio_path"])
            audio_for_asr = demucs_clean_path
            logger.info("Checkpoint kullanildi: demucs_vokal_ayirma")
        else:
            checkpoint_store.begin_stage("demucs_vokal_ayirma", 4, 2, demucs_inputs)
            try:
                demucs_clean_path = _clean_source_audio_with_demucs(wav_path, cfg, run_dir)
                audio_for_asr = demucs_clean_path
                demucs_background_path = _demucs_background_audio_path(run_dir)
                if not os.path.isfile(demucs_background_path):
                    raise RuntimeError(f"Demucs arka plan stem dosyasi bulunamadi: {demucs_background_path}")
                checkpoint_store.complete_stage(
                    "demucs_vokal_ayirma",
                    {
                        "clean_audio_path": _checkpoint_relative_path(run_dir, demucs_clean_path),
                        "background_audio_path": _checkpoint_relative_path(run_dir, demucs_background_path),
                    },
                    [demucs_clean_path, demucs_background_path],
                )
            except Exception as exc:
                checkpoint_store.fail_stage("demucs_vokal_ayirma", exc)
                raise

        if _konusmaci_motoru(cfg):
            cfg.konusmaci_ses_yolu = audio_for_asr

        asr_prepare_inputs = {
            "audio_for_asr": _checkpoint_relative_path(run_dir, audio_for_asr),
            "transcription_engine": cfg.transcription_engine,
            "leading_pad_seconds": ASR_LEADING_PAD_SECONDS if _should_apply_asr_leading_pad(cfg) else 0.0,
        }
        if checkpoint_store.can_restore("asr_sesi_hazirlama", 5, 1, asr_prepare_inputs):
            asr_payload = checkpoint_store.stage_payload("asr_sesi_hazirlama")
            audio_for_transcription = _checkpoint_absolute_path(run_dir, asr_payload["audio_for_transcription"])
            asr_time_offset = float(asr_payload["asr_time_offset"])
            logger.info("Checkpoint kullanildi: asr_sesi_hazirlama")
        else:
            checkpoint_store.begin_stage("asr_sesi_hazirlama", 5, 1, asr_prepare_inputs)
            try:
                audio_for_transcription, asr_time_offset = _prepare_audio_for_asr_transcription(audio_for_asr, cfg, run_dir)
                checkpoint_store.complete_stage(
                    "asr_sesi_hazirlama",
                    {
                        "audio_for_transcription": _checkpoint_relative_path(run_dir, audio_for_transcription),
                        "asr_time_offset": asr_time_offset,
                    },
                    [audio_for_transcription],
                )
            except Exception as exc:
                checkpoint_store.fail_stage("asr_sesi_hazirlama", exc)
                raise

        transcription_inputs = {
            "audio_for_transcription": _checkpoint_relative_path(run_dir, audio_for_transcription),
            "engine": cfg.transcription_engine,
            "model_name": cfg.model_name,
            "compute_type": cfg.compute_type,
            "decoder_profile": cfg.transcription_decoder_profile,
            "decoder_contract_version": transcription_decoder_contract_version(cfg.transcription_engine),
            "whisper_language": cfg.whisper_language,
            "use_diarization": bool(cfg.use_diarization),
            "platform_language": source_lang,
            "asr_time_offset": asr_time_offset,
            "dubbing_mode": cfg.dubbing_mode,
            "crisper_language_detection_mode": cfg.crisper_language_detection_mode,
        }
        transcription_inputs.update(_transcription_engine_contract_inputs(cfg.transcription_engine))
        split_whisperx_alignment = (
            cfg.dubbing_mode == "segment_sync"
            and cfg.transcription_engine == "whisperx"
            and not bool(cfg.use_diarization)
        )
        transcription_inputs["split_whisperx_alignment"] = split_whisperx_alignment
        if checkpoint_store.can_restore("transkripsiyon", 6, 1, transcription_inputs):
            transcription_payload = checkpoint_store.stage_payload("transkripsiyon")
            transcription_result_path = _checkpoint_absolute_path(run_dir, transcription_payload["result_path"])
            segments, src_lang, alignment = _read_transcription_checkpoint(transcription_result_path)
            _restore_transcription_usage_report(cfg, alignment, run_dir)
            logger.info("Checkpoint kullanildi: transkripsiyon")
        else:
            checkpoint_store.begin_stage("transkripsiyon", 6, 1, transcription_inputs)
            try:
                segments, src_lang, alignment = run_with_internet_gateway(
                    lambda route: transcribe_and_align(
                        audio_for_transcription,
                        cfg,
                        run_dir,
                        platform_lang=source_lang,
                        source_url=source,
                        asr_time_offset=0.0 if split_whisperx_alignment else asr_time_offset,
                        full_text_mode=cfg.dubbing_mode == "full_text" or split_whisperx_alignment,
                        prepare_final_segments=cfg.dubbing_mode == "full_text",
                    ),
                    "transkripsiyon",
                    logger,
                    run_dir,
                )
                transcription_result_path = _write_transcription_checkpoint(run_dir, segments, src_lang, alignment)
                _restore_transcription_usage_report(cfg, alignment, run_dir)
                transcription_artifacts = [transcription_result_path]
                transcription_payload = {"result_path": _checkpoint_relative_path(run_dir, transcription_result_path)}
                for alignment_key in (
                    "api_request_path",
                    "transcription_profile_path",
                    "raw_result_path",
                    "transcript_path",
                    "dubbing_ready_result_path",
                    "ctc_alignment_result_path",
                    "diagnostics_path",
                    "language_detection_artifact_path",
                    "language_detection_profile_path",
                ):
                    relative_artifact = str(alignment.get(alignment_key) or "").strip()
                    if not relative_artifact:
                        continue
                    artifact_path = _checkpoint_absolute_path(run_dir, relative_artifact)
                    if not os.path.isfile(artifact_path):
                        raise RuntimeError(
                            f"Transkripsiyon artefakti bulunamadi: {alignment_key}={relative_artifact}"
                        )
                    transcription_payload[alignment_key] = relative_artifact
                    transcription_artifacts.append(artifact_path)
                if cfg.transcription_usage_report:
                    transcription_payload["usage_report_path"] = _checkpoint_relative_path(run_dir, cfg.transcription_usage_report)
                    transcription_artifacts.append(os.path.dirname(cfg.transcription_usage_report))
                checkpoint_store.complete_stage(
                    "transkripsiyon",
                    transcription_payload,
                    transcription_artifacts,
                )
            except Exception as exc:
                checkpoint_store.fail_stage("transkripsiyon", exc)
                raise

        if cfg.dubbing_mode == "segment_sync":
            final_segment_inputs = {
                "transcription_result_path": _checkpoint_relative_path(run_dir, transcription_result_path),
                "gap_threshold_seconds": 1.0,
                "maximum_words": 150,
                "punctuation_priority": [".", "?", "!", ","],
                "word_text_assembly": "detected_language_separator_v1",
                "split_whisperx_alignment": split_whisperx_alignment,
            }
            if checkpoint_store.can_restore("forced_alignment_ve_nihai_segmentler", 7, 1, final_segment_inputs):
                final_segment_payload = checkpoint_store.stage_payload("forced_alignment_ve_nihai_segmentler")
                final_segment_result_path = _checkpoint_absolute_path(run_dir, final_segment_payload["result_path"])
                segments, src_lang, alignment = _read_transcription_checkpoint(final_segment_result_path)
                logger.info("Checkpoint kullanildi: forced_alignment_ve_nihai_segmentler")
            else:
                checkpoint_store.begin_stage("forced_alignment_ve_nihai_segmentler", 7, 1, final_segment_inputs)
                try:
                    if split_whisperx_alignment:
                        segments, alignment, alignment_input_path = _align_whisperx_checkpoint_segments(
                            audio_for_transcription,
                            segments,
                            src_lang,
                            cfg,
                            run_dir,
                            asr_time_offset,
                        )
                    aligned_words = _alignment_words_for_final_segments(alignment)
                    segments, alignment = _nihai_kaynak_segmentlerini_olustur(aligned_words)
                    final_segment_result_path = _write_transcription_checkpoint(
                        run_dir,
                        segments,
                        src_lang,
                        alignment,
                        filename="pipeline_final_segments_result.json",
                    )
                    checkpoint_store.complete_stage(
                        "forced_alignment_ve_nihai_segmentler",
                        {"result_path": _checkpoint_relative_path(run_dir, final_segment_result_path)},
                        [final_segment_result_path],
                    )
                except Exception as exc:
                    checkpoint_store.fail_stage("forced_alignment_ve_nihai_segmentler", exc)
                    raise

        if cfg.dubbing_mode == "full_text":
            return _run_full_text_dub_after_transcription(
                video_path=video_path,
                wav_path=wav_path,
                demucs_clean_path=demucs_clean_path,
                background_preserved=background_preserved,
                segments=segments,
                source_lang=src_lang,
                cfg=cfg,
                run_dir=run_dir,
                request_metadata=request_metadata,
                checkpoint_store=checkpoint_store,
            )

        logger.info("=" * 60)
        logger.info("DIL TESPITI SONUCLARI (TRANSKRIPSIYON TAMAMLANDI)")
        logger.info("=" * 60)
        logger.info("  [1] Platform metadata bilgisi: %s", source_lang if source_lang else "YOK (Lokal dosya veya metadata eksik)")
        logger.info("  [2] Whisper tespiti (FINAL): %s", src_lang)
        if source_lang and source_lang == src_lang:
            logger.info("  [DURUM] Platform ve Whisper UYUMLU - Her sey normal")
        elif source_lang and source_lang != src_lang:
            logger.info("  [UYARI] Platform (%s) ve Whisper (%s) FARKLI!", source_lang, src_lang)
            logger.info("  [UYARI] Whisper tespiti kullanilacak: %s", src_lang)
        else:
            logger.info("  [DURUM] Platform bilgisi yok, Whisper tespiti kullanildi")
        logger.info("=" * 60)
        logger.info("  Segment sayisi: %d", len(segments))
        logger.info("=" * 60)

        speaker_inputs = {
            "final_segments": _checkpoint_relative_path(run_dir, final_segment_result_path),
            "tts_engine": cfg.tts_engine,
            "konusmaci_basina_ses": bool(getattr(cfg, "konusmaci_basina_ses", False)),
            "konusmaci_sesleri": dict(sorted((getattr(cfg, "supertonic_konusmaci_sesleri", {}) or {}).items())),
            "voxcpm2_konusmaci_sesleri": dict(sorted((getattr(cfg, "voxcpm2_konusmaci_sesleri", {}) or {}).items())),
            "voxcpm2_havuz": list(_voxcpm2_ses_havuzlari(cfg)) if cfg.tts_engine == "voxcpm2" else [],
            "cinsiyet_kipi": str(getattr(cfg, "cinsiyet_kipi", "konusmaci")),
            "segment_ses_cifti": [str(getattr(cfg, "supertonic_kadin_ses", "F1")), str(getattr(cfg, "supertonic_erkek_ses", "M1"))],
            "speaker_timeline_source": _supertonic_speaker_timeline_source(cfg),
            "use_diarization": bool(cfg.use_diarization),
        }
        speaker_stage_enabled = _konusmaci_motoru(cfg)
        if not speaker_stage_enabled:
            if not checkpoint_store.can_restore("konusmaci_yonlendirme", 8, 2, speaker_inputs):
                checkpoint_store.skip_stage(
                    "konusmaci_yonlendirme",
                    8,
                    2,
                    speaker_inputs,
                    "disabled_by_configuration",
                )
        elif checkpoint_store.can_restore("konusmaci_yonlendirme", 8, 2, speaker_inputs):
            speaker_payload = checkpoint_store.stage_payload("konusmaci_yonlendirme")
            speaker_result_path = _checkpoint_absolute_path(run_dir, speaker_payload["result_path"])
            segments, src_lang, alignment = _read_transcription_checkpoint(speaker_result_path)
            logger.info("Checkpoint kullanildi: konusmaci_yonlendirme")
        else:
            checkpoint_store.begin_stage("konusmaci_yonlendirme", 8, 2, speaker_inputs)
            try:
                _apply_konusmaci_basina_ses_if_needed(segments, cfg, run_dir)
                alignment = _rebuild_alignment_from_segment_words_if_available(segments, alignment)
                speaker_result_path = _write_transcription_checkpoint(
                    run_dir,
                    segments,
                    src_lang,
                    alignment,
                    filename="pipeline_speaker_routing_result.json",
                )
                checkpoint_store.complete_stage(
                    "konusmaci_yonlendirme",
                    {"result_path": _checkpoint_relative_path(run_dir, speaker_result_path)},
                    [speaker_result_path],
                )
            except Exception as exc:
                checkpoint_store.fail_stage("konusmaci_yonlendirme", exc)
                raise
        alignment = _rebuild_alignment_from_segment_words_if_available(segments, alignment)
        nihai_segmentler_path = os.path.join(run_dir, "nihai_kaynak_dublaj_segmentleri.txt")
        with open(nihai_segmentler_path, "w", encoding="utf-8") as f:
            f.write("NIHAI KAYNAK DUBLAJ SEGMENTLERI\n")
            f.write("=" * 70 + "\n\n")
            for i, seg in enumerate(segments):
                f.write(f"{i+1}. [{seg.start:.3f}s - {seg.end:.3f}s] {seg.text}\n")
            f.write(f"\nToplam: {len(segments)} segment\n")
            ham_file_name = _transcription_ham_file_name(cfg.transcription_engine)
            if os.path.isfile(os.path.join(run_dir, ham_file_name)):
                f.write(f"\nNOT: HAM segmentler icin '{ham_file_name}' dosyasina bakin.\n")
        logger.info("Nihai kaynak dublaj segmentleri kaydedildi: %s", nihai_segmentler_path)

        write_transcripts(segments, run_dir, source, src_lang, cfg.target_lang)
        write_full_paragraph(segments, run_dir, src_lang)
        write_word_level_transcript(alignment, run_dir, source, src_lang)
        try:
            preview_artifacts = write_source_subtitle_preview(segments, alignment, run_dir, src_lang)
            if preview_artifacts:
                logger.info("Kaynak altyazi HTML onizlemesi hazirlandi: %s", preview_artifacts.get("html", ""))
        except Exception:
            logger.exception("Kaynak altyazi HTML onizlemesi olusturulamadi.")
        check_global_word_overlaps(alignment, run_dir, source)

        logger.info("=" * 60)
        logger.info("CEVIRI BASLADI")
        logger.info("=" * 60)
        _log_ceviri_kimligi(logger, cfg, request_metadata, prefix="  ")
        logger.info("  Kaynak dil (Whisper): %s", src_lang)
        logger.info("  Hedef dil (Kullanici): %s", cfg.target_lang)
        if cfg.translator_engine == "groq":
            logger.info("  Format: ISO kod -> Turkce dil ismi (Prompt icin)")
        else:
            logger.info("  Format: ISO kod (Google API)")
        logger.info("=" * 60)

        translation_inputs = segment_translation_checkpoint_inputs(
            source_segments_hash=canonical_json_hash(_segments_to_checkpoint_payload(segments)),
            source_lang=src_lang,
            target_lang=cfg.target_lang,
            translator_engine=cfg.translator_engine,
            bridge_backend=(
                _request_bridge_backend(cfg, request_metadata)
                if cfg.translator_engine == "codex_bridge"
                else ""
            ),
            tts_engine=cfg.tts_engine,
            tts_voice_id=cfg.tts_voice_id,
            tts_speed_factor=cfg.tts_speed_factor,
            supertonic_flow_mode=cfg.supertonic_flow_mode,
        )
        translator = _create_segment_translator(cfg, request_metadata, src_lang)
        translation_ran = False
        if checkpoint_store.can_restore("ceviri", 9, 2, translation_inputs):
            translation_payload = checkpoint_store.stage_payload("ceviri")
            translation_result_path = _checkpoint_absolute_path(run_dir, translation_payload["result_path"])
            segments, checkpoint_source_lang, alignment = _read_transcription_checkpoint(translation_result_path)
            if checkpoint_source_lang != src_lang:
                raise RuntimeError("Ceviri checkpoint kaynak dili mevcut istekle uyusmuyor")
            translated_texts = [segment.text for segment in segments]
            original_texts = {
                segment.index: str(getattr(segment, "original_source_text", ""))
                for segment in segments
            }
            video_usage_report = str(translation_payload.get("video_usage_report") or "")
            if video_usage_report:
                translator.last_video_usage_report = video_usage_report
            logger.info("Checkpoint kullanildi: ceviri")
        else:
            translation_ran = True
            checkpoint_store.begin_stage("ceviri", 9, 2, translation_inputs)
            try:
                def translate_segments_operation(route):
                    current_translator = _create_segment_translator(cfg, request_metadata, src_lang)
                    return current_translator, current_translator.translate_segments(segments, run_dir)

                translator, translated_texts = run_with_internet_gateway(
                    translate_segments_operation,
                    "ceviri",
                    logger,
                    run_dir,
                )
                if len(translated_texts) != len(segments):
                    raise RuntimeError(
                        f"Ceviri motoru {len(segments)} segment yerine {len(translated_texts)} sonuc dondurdu"
                    )
                original_texts = {seg.index: seg.text for seg in segments}
                for seg in segments:
                    setattr(seg, "original_source_text", original_texts.get(seg.index, seg.text))
                for seg, translated_text in zip(segments, translated_texts):
                    seg.text = translated_text
                translation_result_path = _write_transcription_checkpoint(
                    run_dir,
                    segments,
                    src_lang,
                    alignment,
                    filename="pipeline_translation_result.json",
                )
                checkpoint_store.complete_stage(
                    "ceviri",
                    {
                        "result_path": _checkpoint_relative_path(run_dir, translation_result_path),
                        "video_usage_report": str(getattr(translator, "last_video_usage_report", "") or ""),
                    },
                    [translation_result_path],
                )
                logger.info("Ceviri tamamlandi, segmentler guncellendi")
            except Exception as exc:
                checkpoint_store.fail_stage("ceviri", exc)
                raise

        if translation_ran and getattr(cfg, "gozden_gecir", False):
            # Çeviri bu çalıştırmada yapıldı ve checkpoint'i yazıldı: seslendirmeden önce temiz dur (hata değil).
            # Devamda çeviri geri yüklenir (düzeltilmiş metin), bu yüzden tekrar durmaz.
            logger.info("Gozden gecirme icin duruldu: ceviri bitti, seslendirme baslamadi")
            raise GozdenGecirmeBekleniyor("ceviri", translation_result_path)

        voice_routing_inputs = {
            "translation_result_path": _checkpoint_relative_path(run_dir, translation_result_path),
            "tts_engine": cfg.tts_engine,
            "tts_voice_id": cfg.tts_voice_id,
            "voxcpm2_ses": getattr(cfg, "voxcpm2_ses", ""),
            **_ema_checkpoint_girdisi(cfg),
        }
        if checkpoint_store.can_restore("ses_yonlendirme", 10, 2, voice_routing_inputs):
            voice_payload = checkpoint_store.stage_payload("ses_yonlendirme")
            voice_result_path = _checkpoint_absolute_path(run_dir, voice_payload["result_path"])
            segments, checkpoint_source_lang, alignment = _read_transcription_checkpoint(voice_result_path)
            if checkpoint_source_lang != src_lang:
                raise RuntimeError("Ses yonlendirme checkpoint kaynak dili mevcut istekle uyusmuyor")
            translated_texts = [segment.text for segment in segments]
            original_texts = {
                segment.index: str(getattr(segment, "original_source_text", ""))
                for segment in segments
            }
            logger.info("Checkpoint kullanildi: ses_yonlendirme")
        else:
            checkpoint_store.begin_stage("ses_yonlendirme", 10, 2, voice_routing_inputs)
            try:
                _apply_supertonic_manual_voice_metadata_if_needed(segments, cfg)
                if cfg.tts_engine == "supertonic":
                    apply_supertonic_voice_speed_plan(
                        segments,
                        run_dir,
                        default_voice_id=cfg.tts_voice_id or "F1",
                    )
                voice_result_path = _write_transcription_checkpoint(
                    run_dir,
                    segments,
                    src_lang,
                    alignment,
                    filename="pipeline_voice_routing_result.json",
                )
                checkpoint_store.complete_stage(
                    "ses_yonlendirme",
                    {"result_path": _checkpoint_relative_path(run_dir, voice_result_path)},
                    [voice_result_path],
                )
            except Exception as exc:
                checkpoint_store.fail_stage("ses_yonlendirme", exc)
                raise

        write_full_paragraph(segments, run_dir, cfg.target_lang)

        cevirili_segments_path = os.path.join(run_dir, f"translated_segments_{cfg.target_lang}.txt")
        with open(cevirili_segments_path, "w", encoding="utf-8") as f:
            f.write(f"ORIJINAL VE CEVIRILMIS SEGMENTLER ({src_lang.upper()} -> {cfg.target_lang.upper()})\n")
            f.write("=" * 70 + "\n\n")
            for seg in segments:
                orig_text = original_texts.get(seg.index, "")
                f.write(f"{seg.index}. [{seg.start:.3f}s - {seg.end:.3f}s]\n")
                f.write(f"   [{src_lang.upper()}] {orig_text}\n")
                f.write(f"   [{cfg.target_lang.upper()}] {seg.text}\n\n")
            f.write(f"Toplam: {len(segments)} segment\n")
        logger.info("Cevirilmis segmentler kaydedildi: %s", cevirili_segments_path)
        checkpoint_store.emit_artifact_ready("bilingual_dubbing_transcript", cevirili_segments_path)

        tts_inputs = {
            "voice_routing_result_path": _checkpoint_relative_path(run_dir, voice_result_path),
            "segments_hash": canonical_json_hash(_segments_to_checkpoint_payload(segments)),
            "tts_engine": cfg.tts_engine,
            "tts_voice_id": cfg.tts_voice_id,
            "tts_pitch": cfg.tts_pitch,
            "sample_rate": cfg.sample_rate,
            "speed_factor": cfg.tts_speed_factor,
            "real_candidate_selection": should_use_real_tts_candidate_selection(cfg),
            "supertonic_flow_mode": cfg.supertonic_flow_mode,
            "supertonic_atempo_enabled": bool(getattr(cfg, "supertonic_atempo_enabled", False)),
        }
        if cfg.tts_engine == "supertonic":
            tts_inputs["supertonic_synthesis_contract"] = SUPERTONIC_SYNTHESIS_CONTRACT
        if cfg.tts_engine == "xtts":
            tts_inputs["xtts_referans_ses"] = str(getattr(cfg, "xtts_referans_ses", "") or "")
        if str(getattr(cfg, "rvc_model_yolu", "") or "").strip():
            tts_inputs["rvc"] = [str(cfg.rvc_model_yolu), str(getattr(cfg, "rvc_index_yolu", "") or ""),
                                 int(getattr(cfg, "rvc_perde", 0) or 0)]
        if checkpoint_store.can_restore("tts_ve_segment_sesleri", 11, 2, tts_inputs):
            tts_payload = checkpoint_store.stage_payload("tts_ve_segment_sesleri")
            tts_manifest_path = _checkpoint_absolute_path(run_dir, tts_payload["manifest_path"])
            tts_result = _read_tts_checkpoint(tts_manifest_path, cfg.sample_rate)
            logger.info("Checkpoint kullanildi: tts_ve_segment_sesleri")
        else:
            checkpoint_store.begin_stage("tts_ve_segment_sesleri", 11, 2, tts_inputs)
            try:
                def build_tts_operation(route):
                    current_translator = translator
                    if should_use_real_tts_candidate_selection(cfg) and translator is not None:
                        current_translator = _create_segment_translator(cfg, request_metadata, src_lang)
                        selection_settings = _get_real_tts_selection_settings(cfg)
                        max_repair_rounds = int(selection_settings.get("max_repair_rounds") or 0)
                        result = build_audio_with_real_tts_selection(
                            segments,
                            cfg,
                            run_dir,
                            current_translator,
                            translated_texts,
                            max_repair_rounds=max_repair_rounds,
                        )
                    else:
                        result = build_dubbed_audio(segments, cfg, run_dir)
                    return current_translator, result

                translator, tts_result = run_with_internet_gateway(
                    build_tts_operation,
                    "tts_ve_segment_sesleri",
                    logger,
                    run_dir,
                )
                tts_manifest_path, tts_checkpoint_dir = _write_tts_checkpoint(run_dir, tts_result, cfg.sample_rate)
                checkpoint_store.complete_stage(
                    "tts_ve_segment_sesleri",
                    {"manifest_path": _checkpoint_relative_path(run_dir, tts_manifest_path)},
                    [tts_manifest_path, tts_checkpoint_dir],
                )
            except Exception as exc:
                checkpoint_store.fail_stage("tts_ve_segment_sesleri", exc)
                raise

        dubbed_wav = os.path.join(run_dir, f"dubbed_{cfg.target_lang}.wav")
        save_wave(dubbed_wav, tts_result.audio, cfg.sample_rate)
        tts_result.audio = np.empty(0, dtype=np.float32)

        canonical_output_video = os.path.join(run_dir, f"dubbed_{cfg.target_lang}.mp4")
        output_video = os.path.join(run_dir, f"dubbed_{cfg.target_lang}_working.mp4")
        smart_frame_enabled = bool(getattr(cfg, "smart_frame_capture_enabled", False))
        subtitle_inputs = {
            "tts_manifest_path": _checkpoint_relative_path(run_dir, tts_manifest_path),
            "subtitle_mode": normalize_subtitle_mode(getattr(cfg, "subtitle_mode", "none")),
            "tts_engine": cfg.tts_engine,
            "require_verified_word_timeline": should_use_real_tts_candidate_selection(cfg),
            "source_video_path": _checkpoint_input_path(run_dir, video_path),
            "smart_frame_capture_enabled": smart_frame_enabled,
            "subtitle_timing_contract_version": SUBTITLE_TIMING_CONTRACT_SCHEMA_VERSION,
        }
        if subtitle_inputs["subtitle_mode"] == "rollup":
            from dublaj_hatti.bolum_50_seslendirme.altyazili_dublaj.rollup import rollup_contract_inputs

            subtitle_inputs["rollup_contract"] = rollup_contract_inputs()
        if checkpoint_store.can_restore("altyazi_hazirlama", 12, 1, subtitle_inputs):
            subtitle_payload = checkpoint_store.stage_payload("altyazi_hazirlama")
            subtitle_result_path = _checkpoint_absolute_path(run_dir, subtitle_payload["result_path"])
            visual_video_path = _checkpoint_absolute_path(run_dir, subtitle_payload.get("visual_video_path") or _checkpoint_input_path(run_dir, video_path))
            subtitle_artifacts = _read_pipeline_json(subtitle_result_path)
            logger.info("Checkpoint kullanildi: altyazi_hazirlama")
        else:
            checkpoint_store.begin_stage("altyazi_hazirlama", 12, 1, subtitle_inputs)
            try:
                visual_video_path, smart_frame_result, smart_frame_artifacts = _prepare_visual_video(
                    video_path,
                    run_dir,
                    smart_frame_enabled,
                )
                subtitle_artifacts = prepare_one_pass_subtitle_assets(
                    video_path=visual_video_path,
                    output_video=output_video,
                    segments=segments,
                    timing_infos=tts_result.timing_infos,
                    segment_audios=tts_result.segment_audios,
                    cfg=cfg,
                    run_dir=run_dir,
                    verified_word_timeline=tts_result.verified_word_timeline,
                    require_verified_word_timeline=should_use_real_tts_candidate_selection(cfg),
                )
                subtitle_result_path = _write_pipeline_json(
                    run_dir,
                    "pipeline_subtitle_result.json",
                    subtitle_artifacts,
                )
                subtitle_artifact_paths = [subtitle_result_path, *smart_frame_artifacts]
                subtitle_ass_artifact = str(subtitle_artifacts.get("ass_path") or "")
                if subtitle_artifacts.get("enabled") and subtitle_ass_artifact:
                    subtitle_artifact_paths.append(subtitle_ass_artifact)
                    subtitle_artifact_paths.extend([
                        str(subtitle_artifacts["timing_contract_path"]),
                        str(subtitle_artifacts["timeline_path"]),
                        str(subtitle_artifacts["timing_report_path"]),
                    ])
                checkpoint_store.complete_stage(
                    "altyazi_hazirlama",
                    {
                        "result_path": _checkpoint_relative_path(run_dir, subtitle_result_path),
                        "visual_video_path": _checkpoint_input_path(run_dir, visual_video_path),
                        "smart_frame_status": str(smart_frame_result.get("status") or ""),
                    },
                    subtitle_artifact_paths,
                )
            except Exception as exc:
                checkpoint_store.fail_stage("altyazi_hazirlama", exc)
                raise
        subtitle_ass_path = str(subtitle_artifacts.get("ass_path") or "") if subtitle_artifacts.get("enabled") else ""

        _release_tts_audio_for_video(tts_result, tts_manifest_path, cfg.sample_rate)

        base_output_video = os.path.join(run_dir, f"dubbed_{cfg.target_lang}_base_mux.mp4")
        video_mux_inputs = {
            "tts_manifest_path": _checkpoint_relative_path(run_dir, tts_manifest_path),
            "subtitle_result_path": _checkpoint_relative_path(run_dir, subtitle_result_path),
            "source_video_path": _checkpoint_input_path(run_dir, visual_video_path),
            "sample_rate": cfg.sample_rate,
            "final_audio_filter": SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER if cfg.tts_engine == "supertonic" else "",
            "video_output_policy": cfg.video_output_policy,
            "video_encoder_cq": cfg.video_encoder_cq,
            "max_output_bytes": cfg.max_output_bytes,
        }
        timeline_audio_path = os.path.join(run_dir, "audio_new_timeline.wav")
        video_mux_restored = checkpoint_store.can_restore("video_timeline_ve_final_mux", 13, 2, video_mux_inputs)
        if video_mux_restored:
            video_mux_payload = checkpoint_store.stage_payload("video_timeline_ve_final_mux")
            video_result_path = _checkpoint_absolute_path(run_dir, video_mux_payload["result_path"])
            base_output_video = _checkpoint_absolute_path(run_dir, video_mux_payload["base_output_video"])
            timeline_audio_path = _checkpoint_absolute_path(run_dir, video_mux_payload["timeline_audio_path"])
            video_result_payload = _read_pipeline_json(video_result_path)
            video_result = _restore_video_result(run_dir, dict(video_result_payload["video_result"]))
            segments = _segments_from_checkpoint_payload(video_result_payload["segments"])
            logger.info("Checkpoint kullanildi: video_timeline_ve_final_mux")
        else:
            checkpoint_store.begin_stage("video_timeline_ve_final_mux", 13, 2, video_mux_inputs)
            try:
                Path(timeline_audio_path).unlink(missing_ok=True)
                video_result = run_video_processor_subprocess(
                    input_video=visual_video_path,
                    segments=segments,
                    timing_infos=tts_result.timing_infos,
                    segment_audios=tts_result.segment_audios,
                    output_video=base_output_video,
                    work_dir=run_dir,
                    sample_rate=cfg.sample_rate,
                    subtitle_ass_path=subtitle_ass_path,
                    final_audio_filter=SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER if cfg.tts_engine == "supertonic" else "",
                    video_output_policy=cfg.video_output_policy,
                    video_encoder_cq=cfg.video_encoder_cq,
                    max_output_bytes=cfg.max_output_bytes,
                )
            except Exception as exc:
                checkpoint_store.fail_stage("video_timeline_ve_final_mux", exc)
                raise
        supertonic_final_audio_profile: Dict[str, str] = {}
        if cfg.tts_engine == "supertonic":
            supertonic_final_audio_profile = video_result.get("final_audio_profile", {})

        timeline = video_result.get("timeline", [])
        if timeline:
            timeline_map = {item["index"]: item for item in timeline if item.get("type") == "segment"}
            for seg in segments:
                if seg.index in timeline_map:
                    seg.start = timeline_map[seg.index]["new_start"]
                    seg.end = timeline_map[seg.index]["new_end"]
            logger.info("Segment zamanlari yeni timeline'a gore guncellendi: %d segment", len(timeline_map))

            segments_file = os.path.join(run_dir, "video_segments.json")
            segments_data = []
            for seg in segments:
                segments_data.append({
                    "index": seg.index,
                    "start": seg.start,
                    "end": seg.end,
                    "text": getattr(seg, "text", "")
                })
            with open(segments_file, "w", encoding="utf-8") as f:
                json.dump(segments_data, f, ensure_ascii=False, indent=2)

            cevirili_segments_path = os.path.join(run_dir, f"translated_segments_{cfg.target_lang}.txt")
            with open(cevirili_segments_path, "w", encoding="utf-8") as f:
                f.write(f"ORIJINAL VE CEVIRILMIS SEGMENTLER ({src_lang.upper()} -> {cfg.target_lang.upper()})\n")
                f.write("=" * 70 + "\n\n")
                for seg in segments:
                    orig_text = original_texts.get(seg.index, "")
                    f.write(f"{seg.index}. [{seg.start:.3f}s - {seg.end:.3f}s]\n")
                    f.write(f"   [{src_lang.upper()}] {orig_text}\n")
                    f.write(f"   [{cfg.target_lang.upper()}] {seg.text}\n\n")
                f.write(f"Toplam: {len(segments)} segment\n")
            logger.info("Cevirilmis segmentler yeni zamanlarla guncellendi: %s", cevirili_segments_path)

        if not video_mux_restored:
            video_result_path = _write_pipeline_json(
                run_dir,
                "pipeline_video_mux_result.json",
                {
                    "video_result": _portable_video_result(run_dir, video_result),
                    "segments": _segments_to_checkpoint_payload(segments),
                },
            )
            checkpoint_store.complete_stage(
                "video_timeline_ve_final_mux",
                {
                    "result_path": _checkpoint_relative_path(run_dir, video_result_path),
                    "base_output_video": _checkpoint_relative_path(run_dir, base_output_video),
                    "timeline_audio_path": _checkpoint_relative_path(run_dir, timeline_audio_path),
                },
                [video_result_path, base_output_video, timeline_audio_path, *_video_result_audio_artifacts(video_result)],
            )
        shutil.copy2(base_output_video, output_video)

        log_video_metadata(output_video, "ISLENMIŞ VIDEO (Encode sonrasi)", logger)

        video_duration = segments[-1].end if segments else 0.0
        source_video_duration = float(video_result.get("original_duration") or video_duration or 0.0)
        new_timeline_duration = float(video_result.get("new_duration") or video_duration or 0.0)
        background_artifacts: Dict[str, str] = {}
        background_inputs = {
            "enabled": background_preserved,
            "sample_rate": cfg.sample_rate,
            "new_timeline_duration": new_timeline_duration,
            "video_output_policy": cfg.video_output_policy,
            "max_output_bytes": cfg.max_output_bytes,
        }
        if background_preserved and cfg.tts_engine == "supertonic":
            background_inputs["background_gain_contract"] = SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER
        if not background_preserved:
            if not checkpoint_store.can_restore("arka_plan_miksi", 15, 2, background_inputs):
                checkpoint_store.skip_stage("arka_plan_miksi", 15, 2, background_inputs, "disabled_by_configuration")
        elif checkpoint_store.can_restore("arka_plan_miksi", 15, 2, background_inputs):
            background_payload = checkpoint_store.stage_payload("arka_plan_miksi")
            background_output_video = _checkpoint_absolute_path(run_dir, background_payload["output_video"])
            background_result_path = _checkpoint_absolute_path(run_dir, background_payload["result_path"])
            background_artifacts = _restore_background_audio_checkpoint_map(
                run_dir,
                _read_pipeline_json(background_result_path),
                background_payload,
            )
            shutil.copy2(background_output_video, output_video)
            logger.info("Checkpoint kullanildi: arka_plan_miksi")
        else:
            checkpoint_store.begin_stage("arka_plan_miksi", 15, 2, background_inputs)
            background_output_video = os.path.join(run_dir, f"dubbed_{cfg.target_lang}_background_stage.mp4")
            shutil.copy2(output_video, background_output_video)
            background_artifacts = _apply_preserved_background_audio(
                background_output_video,
                timeline,
                run_dir,
                cfg.sample_rate,
                new_timeline_duration,
                "96k" if cfg.video_output_policy == "max_mb" else "192k",
                cfg.max_output_bytes if cfg.video_output_policy == "max_mb" else 0,
                supertonic_constant_gain=cfg.tts_engine == "supertonic",
            )
            background_result_path = _write_pipeline_json(
                run_dir,
                "pipeline_background_result.json",
                _portable_checkpoint_path_fields(
                    run_dir,
                    background_artifacts,
                    ("background_audio", "background_audio_new_timeline", "background_mixed_audio", "dubbed_audio",
                     "background_raw_mixed_audio", "background_gain_report"),
                ),
            )
            background_audio_artifacts = _background_audio_checkpoint_map(run_dir, background_artifacts)
            checkpoint_store.complete_stage(
                "arka_plan_miksi",
                {
                    "output_video": _checkpoint_relative_path(run_dir, background_output_video),
                    "result_path": _checkpoint_relative_path(run_dir, background_result_path),
                    "audio_artifacts": background_audio_artifacts,
                },
                [
                    background_output_video,
                    background_result_path,
                    *[_checkpoint_absolute_path(run_dir, path) for path in background_audio_artifacts.values()],
                ],
            )
            shutil.copy2(background_output_video, output_video)
            log_video_metadata(output_video, "ISLENMIS VIDEO (Arka plan miks sonrasi)", logger)
        final_dubbed_audio = background_artifacts.get("dubbed_audio") or timeline_audio_path
        subtitle_mode = normalize_subtitle_mode(getattr(cfg, "subtitle_mode", "none"))
        subtitle_artifacts = subtitle_artifacts or {"enabled": False, "mode": subtitle_mode}
        one_pass_subtitles_ready = (
            bool(subtitle_artifacts.get("enabled"))
            and str(subtitle_artifacts.get("burn_strategy") or "") == "one_pass_final_mux"
        )
        final_subtitle_inputs = {
            "subtitle_result_path": _checkpoint_relative_path(run_dir, subtitle_result_path),
            "subtitle_mode": subtitle_mode,
            "tts_engine": cfg.tts_engine,
            "one_pass_subtitles_ready": one_pass_subtitles_ready,
            "background_enabled": background_preserved,
        }
        final_subtitle_restored = checkpoint_store.can_restore("final_altyazi_yakma", 16, 1, final_subtitle_inputs)
        if final_subtitle_restored:
            final_subtitle_payload = checkpoint_store.stage_payload("final_altyazi_yakma")
            output_video = _checkpoint_absolute_path(run_dir, final_subtitle_payload["output_video"])
            final_subtitle_result_path = _checkpoint_absolute_path(run_dir, final_subtitle_payload["result_path"])
            subtitle_artifacts = _read_pipeline_json(final_subtitle_result_path)
            logger.info("Checkpoint kullanildi: final_altyazi_yakma")
        else:
            checkpoint_store.begin_stage("final_altyazi_yakma", 16, 1, final_subtitle_inputs)

        if final_subtitle_restored:
            pass
        elif one_pass_subtitles_ready:
            log_video_metadata(output_video, f"ISLENMIS VIDEO ({cfg.tts_engine} tek gecis altyazi sonrasi)", logger)
            logger.info("%s %s altyazili video tek gecis final mux ile hazirlandi: %s", cfg.tts_engine, subtitle_mode, output_video)
        elif subtitle_mode != "none":
            raise RuntimeError(
                f"{cfg.tts_engine} altyazisi tek gecis final mux oncesinde hazirlanmadi; "
                "ikinci encode fallback'i yasaktir"
            )

        if not final_subtitle_restored:
            if os.path.abspath(output_video) != os.path.abspath(canonical_output_video):
                shutil.copy2(output_video, canonical_output_video)
            output_video = canonical_output_video
            final_subtitle_result_path = _write_pipeline_json(
                run_dir,
                "pipeline_final_subtitle_result.json",
                subtitle_artifacts,
            )
            checkpoint_store.complete_stage(
                "final_altyazi_yakma",
                {
                    "output_video": _checkpoint_relative_path(run_dir, output_video),
                    "result_path": _checkpoint_relative_path(run_dir, final_subtitle_result_path),
                },
                [output_video, final_subtitle_result_path],
            )

        final_validation_inputs = {
            "final_subtitle_result_path": _checkpoint_relative_path(run_dir, final_subtitle_result_path),
            "output_video": _checkpoint_relative_path(run_dir, output_video),
            "target_lang": cfg.target_lang,
            "video_output_policy": cfg.video_output_policy,
            "video_encoder_cq": cfg.video_encoder_cq,
            "max_output_bytes": cfg.max_output_bytes,
        }
        if checkpoint_store.can_restore("final_dogrulama_ve_meta", 17, 1, final_validation_inputs):
            final_payload = checkpoint_store.stage_payload("final_dogrulama_ve_meta")
            final_meta_path = _checkpoint_absolute_path(run_dir, final_payload["meta_path"])
            meta = _read_pipeline_json(final_meta_path)
            checkpoint_store.mark_pipeline_completed()
            logger.info("Checkpoint kullanildi: final_dogrulama_ve_meta")
            return meta
        checkpoint_store.begin_stage("final_dogrulama_ve_meta", 17, 1, final_validation_inputs)

        meta: Dict[str, object] = {
            "run_dir": run_dir,
            "source_video": video_path,
            "source_audio": wav_path,
            "clean_audio": demucs_clean_path or "",
            "dubbed_audio": final_dubbed_audio,
            "dubbed_video": output_video,
            "source_language": src_lang,
            "target_language": cfg.target_lang,
            "model_name": cfg.model_name,
            "compute_type": cfg.compute_type,
            "segment_count": len(segments),
            "tts_engine": cfg.tts_engine,
            "tts_voice": cfg.tts_voice_id,
            "tts_pitch": cfg.tts_pitch,
            "transcription_engine": cfg.transcription_engine,
            "transcription_preset": request_metadata.get("transcription_preset", ""),
            "transcription_preset_owner": request_metadata.get("transcription_preset_owner", ""),
            "preserve_background_audio": background_preserved,
            "auto_background_preservation": bool(cfg.auto_background_preservation),
            "subtitle_mode": subtitle_mode,
            "subtitle_artifacts": subtitle_artifacts,
            "video_duration": video_duration,
            "source_video_duration": source_video_duration,
            "new_timeline_duration": new_timeline_duration,
        }
        meta.update(_transcription_runtime_metadata(cfg))
        video_usage_report = getattr(translator, "last_video_usage_report", "") if translator is not None else ""
        if video_usage_report:
            meta["video_usage_report"] = video_usage_report
        if cfg.tts_engine == "supertonic":
            meta["supertonic_flow_mode"] = cfg.supertonic_flow_mode
            meta["supertonic_atempo_enabled"] = bool(getattr(cfg, "supertonic_atempo_enabled", False))
            meta["konusmaci_basina_ses"] = bool(getattr(cfg, "konusmaci_basina_ses", False))
            meta["supertonic_speaker_timeline_source"] = _supertonic_speaker_timeline_source(cfg)
            meta["supertonic_final_audio_profile"] = supertonic_final_audio_profile
            meta["supertonic_synthesis_contract"] = SUPERTONIC_SYNTHESIS_CONTRACT
        if background_artifacts:
            meta.update(background_artifacts)
        if cfg.ai_label:
            meta.update(yapay_zeka_etiketi_ekle(output_video))

        with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        file_size_mb = os.path.getsize(output_video) / (1024 * 1024) if os.path.exists(output_video) else 0
        original_duration = video_duration
        try:
            import subprocess
            result = subprocess.run(
                [ffprobe_yolu(), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", output_video],
                capture_output=True, text=True, timeout=10, **GIZLI_SUREC
            )
            if result.returncode == 0 and result.stdout.strip():
                new_duration = float(result.stdout.strip())
            else:
                new_duration = 0
        except Exception:
            new_duration = 0

        logger.info("")
        logger.info("=" * 60)
        logger.info("DUBLAJ TAMAMLANDI - BASARILI")
        logger.info("=" * 60)
        logger.info("Durum: BASARILI")
        logger.info("Cikti Dosyasi: %s", output_video)
        logger.info("Dosya Boyutu: %.2f MB", file_size_mb)
        if original_duration > 0:
            logger.info("Orijinal Video Suresi: %.2f saniye", original_duration)
        if new_duration > 0:
            logger.info("Dublajli Video Suresi: %.2f saniye", new_duration)
            duration_diff = new_duration - original_duration
            duration_diff_pct = (duration_diff / original_duration * 100) if original_duration > 0 else 0
            logger.info("Sure Farki: %+.2f saniye (%+.1f%%)", duration_diff, duration_diff_pct)
        logger.info("Segment Sayisi: %d", len(segments))
        logger.info("Kaynak Dil: %s", src_lang)
        logger.info("Hedef Dil: %s", cfg.target_lang)
        logger.info("TTS Motoru: %s", cfg.tts_engine)
        _log_ceviri_kimligi(logger, cfg, request_metadata)
        logger.info("=" * 60)
        logger.info("")

        checkpoint_store.complete_stage(
            "final_dogrulama_ve_meta",
            {"meta_path": _checkpoint_relative_path(run_dir, os.path.join(run_dir, "meta.json"))},
            [os.path.join(run_dir, "meta.json"), output_video],
        )
        checkpoint_store.mark_pipeline_completed()
        return meta

    except GozdenGecirmeBekleniyor:
        raise

    except Exception as exc:
        active_stage = str(checkpoint_store.state.get("active_stage") or "")
        if active_stage:
            checkpoint_store.fail_stage(active_stage, exc)
        logger.exception("Dublaj pipeline'inda beklenmeyen bir hata olustu.")
        raise

    finally:
        checkpoint_store.release()
        dubbed_audio = None
        if torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
                logger.info("CUDA cache temizlendi.")
            except Exception:
                logger.exception("CUDA cache temizlenirken hata olustu.")
        gc.collect()
        logger.info("GC calistirildi, bellek temizligi yapildi.")


def transcript_only_pipeline(
    source: str,
    base_dir: str,
    transcript_format: str = "plain",
    cfg: Optional[DubConfig] = None,
    request_metadata: Optional[Dict] = None
) -> Dict:
    if cfg is None:
        cfg = DubConfig()
    cfg.transcription_decoder_profile = resolve_transcription_decoder_profile(
        cfg.transcription_engine,
        cfg.model_name,
        cfg.compute_type,
        cfg.transcription_decoder_profile,
    )

    if request_metadata is None:
        request_metadata = {}
    _youtube_json3_on_denetim(source, cfg)

    temp_run_dir = ensure_run_dir(base_dir, video_title=None)
    setup_file_logging(temp_run_dir)
    logger.info("Video kaynagi: %s", source)
    logger.info("Gecici run klasoru: %s", temp_run_dir)
    logger.info("Transcript formati: %s", transcript_format)

    try:
        video_path, video_title, source_lang = run_with_internet_gateway(
            lambda route: prepare_source_video(source, temp_run_dir, logger=logger),
            "transcript_video_indirme_veya_kopyalama",
            logger,
            temp_run_dir,
        )

        from dublaj_hatti.bolum_10_kaynak_edinme.adim_10_dosya_adi_guvenligi.filename_sanitizer import sanitize_filename
        ts = os.path.basename(temp_run_dir).replace("run_", "")
        sanitized_title = sanitize_filename(video_title, keep_case=False, source_lang=source_lang)
        if len(sanitized_title) > 50:
            sanitized_title = sanitized_title[:50].rstrip('_')

        output_root = os.path.dirname(temp_run_dir)
        new_run_dir = os.path.join(output_root, f"{sanitized_title}_{ts}")

        if temp_run_dir != new_run_dir and not os.path.exists(new_run_dir):
            previous_handler = getattr(logger, "_file_handler", None)
            if previous_handler:
                logger.removeHandler(previous_handler)
                try:
                    previous_handler.close()
                except Exception:
                    pass
                logger._file_handler = None

            os.rename(temp_run_dir, new_run_dir)
            run_dir = new_run_dir
            video_path = os.path.join(run_dir, os.path.basename(video_path))

            setup_file_logging(run_dir)
            logger.info("Klasor yeniden adlandirildi: %s", run_dir)
        else:
            run_dir = temp_run_dir

        logger.info("=" * 60)
        logger.info("UYGULAMA BASLATILDI - SADECE TRANSCRIPT")
        logger.info("=" * 60)
        logger.info("Kaynak: %s", request_metadata.get("source", "BILINMIYOR"))
        logger.info("Baslatma Yontemi: %s", request_metadata.get("launch_method", "MANUEL"))
        logger.info("Istek Zamani: %s", request_metadata.get("request_time", "BILINMIYOR"))
        logger.info("Video URL: %s", source)
        logger.info("Platform: %s", request_metadata.get("platform", "TESPIT EDILECEK"))
        logger.info("Istek Modu: SADECE_TRANSCRIPT")
        logger.info("=" * 60)
        logger.info("")
        logger.info("=" * 60)
        _log_secilen_parametreler(logger, cfg, request_metadata, transcript_format=transcript_format)
        logger.info("=" * 60)
        logger.info("")
        logger.info("Transcript-only pipeline basladi. run_dir=%s", run_dir)

        log_video_metadata(video_path, "ORIJINAL VIDEO (Download sonrasi)", logger)

        wav_path, audio_for_asr, demucs_clean_path = _prepare_source_audio_for_transcription(video_path, cfg, run_dir)

        audio_for_transcription, asr_time_offset = _prepare_audio_for_asr_transcription(audio_for_asr, cfg, run_dir)

        segments, src_lang, alignment = run_with_internet_gateway(
            lambda route: transcribe_and_align(
                audio_for_transcription,
                cfg,
                run_dir,
                platform_lang=source_lang,
                source_url=source,
                asr_time_offset=asr_time_offset,
            ),
            "transcript_transkripsiyon",
            logger,
            run_dir,
        )

        logger.info("=" * 60)
        logger.info("DIL TESPITI SONUCLARI (TRANSKRIPSIYON TAMAMLANDI)")
        logger.info("=" * 60)
        logger.info("  [1] Platform metadata bilgisi: %s", source_lang if source_lang else "YOK")
        logger.info("  [2] Whisper tespiti (FINAL): %s", src_lang)
        logger.info("=" * 60)
        logger.info("  Segment sayisi: %d", len(segments))
        logger.info("=" * 60)

        transcript_path = ""
        if transcript_format == "plain":
            transcript_path = write_transcript_plain_text(segments, run_dir, src_lang)
        elif transcript_format == "srt":
            transcript_path = write_transcript_srt(segments, run_dir, src_lang)
        elif transcript_format == "timestamped":
            write_transcripts(segments, run_dir, source, src_lang, src_lang)
            transcript_path = os.path.join(run_dir, f"transcript_{src_lang.lower()}.txt")
        elif transcript_format == "paragraph":
            transcript_path = os.path.join(run_dir, f"full_paragraf_{src_lang}.txt")
        else:
            logger.warning("Bilinmeyen format: %s, plain text kullaniliyor", transcript_format)
            transcript_path = write_transcript_plain_text(segments, run_dir, src_lang)

        write_full_paragraph(segments, run_dir, src_lang)
        write_word_level_transcript(alignment, run_dir, source, src_lang)
        try:
            preview_artifacts = write_source_subtitle_preview(segments, alignment, run_dir, src_lang)
            if preview_artifacts:
                logger.info("Kaynak altyazi HTML onizlemesi hazirlandi: %s", preview_artifacts.get("html", ""))
        except Exception:
            logger.exception("Kaynak altyazi HTML onizlemesi olusturulamadi.")

        video_duration = segments[-1].end if segments else 0.0

        meta: Dict[str, object] = {
            "run_dir": run_dir,
            "source_video": video_path,
            "source_audio": wav_path,
            "clean_audio": demucs_clean_path or "",
            "transcript_file": transcript_path,
            "transcript_format": transcript_format,
            "source_language": src_lang,
            "segment_count": len(segments),
            "video_duration": video_duration,
        }
        meta.update(_transcription_runtime_metadata(cfg))

        with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        file_size_kb = os.path.getsize(transcript_path) / 1024 if os.path.exists(transcript_path) else 0

        logger.info("")
        logger.info("=" * 60)
        logger.info("TRANSCRIPT TAMAMLANDI - BASARILI")
        logger.info("=" * 60)
        logger.info("Durum: BASARILI")
        logger.info("Cikti Dosyasi: %s", transcript_path)
        logger.info("Dosya Boyutu: %.2f KB", file_size_kb)
        logger.info("Transcript Formati: %s", transcript_format)
        logger.info("Video Suresi: %.2f saniye", video_duration)
        logger.info("Segment Sayisi: %d", len(segments))
        logger.info("Kaynak Dil: %s", src_lang)
        logger.info("=" * 60)
        logger.info("")

        return meta

    except Exception:
        logger.exception("Transcript pipeline'inda beklenmeyen bir hata olustu.")
        raise

    finally:
        if torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
                logger.info("CUDA cache temizlendi.")
            except Exception:
                logger.exception("CUDA cache temizlenirken hata olustu.")
        gc.collect()
        logger.info("GC calistirildi, bellek temizligi yapildi.")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    example_path = input("Lokal video yolu girin: ")
    info = full_dub_pipeline(example_path.strip(), base_dir)
    print("Dublaj tamamlandı. Çıktı video:", info["dubbed_video"])
