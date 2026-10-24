# -*- coding: utf-8 -*-
"""
WhisperX Subprocess Worker
Izole process olarak calisir, VRAM leak'ini OS temizler

WhisperX: Whisper + Forced Alignment (phoneme-based)
En iyi word-level timestamps ve segmentasyon

KULLANIM:
    python worker.py \
        --audio_path "audio.wav" \
        --model_name "base" \
        --device "cuda" \
        --compute_type "float32" \
        --language "auto" \
        --cache_dir "cache"

OUTPUT:
    JSON to STDOUT: {"success": true, "words": [...], "detected_language": "en"}
    Errors to STDERR
"""

import sys
import json
import argparse
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
import warnings
from time import perf_counter

try:
    from .decoder_profiles import (
        WHISPERX_DECODER_CONTRACT_VERSION,
        validate_whisperx_decoder_options,
        whisperx_decoder_options,
    )
except ImportError:
    from decoder_profiles import (
        WHISPERX_DECODER_CONTRACT_VERSION,
        validate_whisperx_decoder_options,
        whisperx_decoder_options,
    )

original_stdout = sys.stdout
sys.stdout = sys.stderr

warnings.filterwarnings("ignore")

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


ALIGN_MODEL_BY_LANGUAGE = {
    "id": "Galuh/wav2vec2-large-xlsr-indonesian",
}

# Neden: CUDA'da toplu 1, iki uzun dosyada 2'den ~%41 hizli, metin ayni; degistirmek 2->1->2 kontrolu ister. bkz. docs/engineering/pinned-values.md#transcription
CUDA_TRANSCRIBE_BATCH_SIZE = 1
CPU_TRANSCRIBE_BATCH_SIZE = 4
CUDA_TRANSCRIBE_BATCH_DECISION = "gtx_1050_ti_large_v3_turbo_float32_transcribe_batch1"
TRANSCRIPTION_VAD_PROVIDER = "pyannote"
TRANSCRIPTION_VAD_DEVICE = "cpu"
TRANSCRIPTION_VAD_CHUNK_SIZE = 30
TRANSCRIPTION_VAD_ONSET = 0.500
TRANSCRIPTION_VAD_OFFSET = 0.363
ALIGN_FAST_WILDCARD_ENV = "WHISPERX_ALIGN_FAST_WILDCARD"
ALIGN_FAST_WILDCARD_DECISION = "whisperx_alignment_get_trellis_fast_wildcard_no_frame_clone"


def normalize_language_code(lang_code: str) -> str:
    if not lang_code:
        return ""
    return lang_code.split("-")[0].split("_")[0].lower()


def get_custom_align_model_name(lang_code: str) -> str:
    return ALIGN_MODEL_BY_LANGUAGE.get(normalize_language_code(lang_code), "")


def get_env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in ("0", "false", "no", "off", "")


def get_transcribe_batch_size(device: str) -> int:
    return CUDA_TRANSCRIBE_BATCH_SIZE if device == "cuda" else CPU_TRANSCRIBE_BATCH_SIZE


DIARIZASYON_MODELI = "pyannote/speaker-diarization-community-1"
_KAPILI_IZLER = ("401", "403", "gated", "unauthorized", "forbidden", "access to model", "accept the user conditions")


def kapili_model_hatasi(exc: BaseException) -> str:
    """pyannote kapılı (gated) model erişim hatasını anlamlı mesaja çevirir; başka hata için boş döner."""
    metin = f"{type(exc).__name__} {exc}".lower()
    if not any(iz in metin for iz in _KAPILI_IZLER):
        return ""
    return (
        f"pyannote konuşmacı ayrımı modeli ({DIARIZASYON_MODELI}) Hugging Face'te kapılı (gated) ve erişim reddedildi "
        "(401/403). Token tek başına yetmez: (1) huggingface.co'da modelin sayfasında kullanım şartlarını kabul edin, "
        "(2) okuma yetkili bir token oluşturup HF_TOKEN ortam değişkenine yazın, (3) ilk indirme için DUBLAJ_CEVRIMICI=1 "
        "ile bir kez çalıştırın. Gerekmiyorsa ileri.pyannote_konusmaci_ayrimi=false yapın; varsayılan konuşmacı ayrımı "
        "(3D-Speaker) token istemez. / The pyannote diarization model is gated on Hugging Face and access was denied: "
        "accept its user conditions, set HF_TOKEN to a read token, run once with DUBLAJ_CEVRIMICI=1, or set "
        "ileri.pyannote_konusmaci_ayrimi=false (the default 3D-Speaker separation needs no token)."
    )


def create_cpu_pyannote_vad_model(torch_module, pyannote_class):
    return pyannote_class(
        torch_module.device(TRANSCRIPTION_VAD_DEVICE),
        token=None,
        chunk_size=TRANSCRIPTION_VAD_CHUNK_SIZE,
        vad_onset=TRANSCRIPTION_VAD_ONSET,
        vad_offset=TRANSCRIPTION_VAD_OFFSET,
    )


def load_whisperx_transcription_model(
    whisperx_module,
    model_name: str,
    device: str,
    compute_type: str,
    cache_dir: str,
    vad_model,
    decoder_profile: str,
):
    resolved_profile, requested_options = whisperx_decoder_options(
        model_name,
        compute_type,
        decoder_profile,
    )
    model = whisperx_module.load_model(
        model_name,
        device=device,
        compute_type=compute_type,
        download_root=str(Path(cache_dir) / "hub"),
        vad_model=vad_model,
        asr_options=requested_options,
    )
    effective_options = validate_whisperx_decoder_options(model, requested_options)
    return model, resolved_profile, requested_options, effective_options


def capture_worker_cuda_snapshot(device: str, torch_module=None, stage: str = "") -> dict:
    snapshot = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "stage": stage,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "device": device,
    }
    if torch_module is not None and device == "cuda":
        try:
            snapshot["cuda_available"] = bool(torch_module.cuda.is_available())
        except Exception as exc:
            snapshot["cuda_available"] = False
            snapshot["cuda_error"] = str(exc)
        if snapshot.get("cuda_available"):
            try:
                free_bytes, total_bytes = torch_module.cuda.mem_get_info()
                snapshot["cuda_free_bytes"] = int(free_bytes)
                snapshot["cuda_total_bytes"] = int(total_bytes)
            except Exception as exc:
                snapshot["cuda_mem_info_error"] = str(exc)
            for field_name, getter in (
                ("cuda_memory_allocated_bytes", torch_module.cuda.memory_allocated),
                ("cuda_memory_reserved_bytes", torch_module.cuda.memory_reserved),
                ("cuda_max_memory_allocated_bytes", torch_module.cuda.max_memory_allocated),
                ("cuda_max_memory_reserved_bytes", torch_module.cuda.max_memory_reserved),
            ):
                try:
                    snapshot[field_name] = int(getter())
                except Exception as exc:
                    snapshot[f"{field_name}_error"] = str(exc)
    if device == "cuda":
        try:
            smi_result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            snapshot["nvidia_smi_returncode"] = smi_result.returncode
            snapshot["nvidia_smi_stdout"] = smi_result.stdout.strip()
            if smi_result.stderr.strip():
                snapshot["nvidia_smi_stderr"] = smi_result.stderr.strip()
        except Exception as exc:
            snapshot["nvidia_smi_error"] = str(exc)
    return snapshot


def write_worker_profile(profile_path: str, result: dict) -> None:
    if not profile_path:
        return
    try:
        profile_file = Path(profile_path)
        profile_file.parent.mkdir(parents=True, exist_ok=True)
        profile_payload = {
            "success": bool(result.get("success")),
            "profile_steps": result.get("profile_steps", []),
            "profile_summary": result.get("profile_summary", {}),
        }
        for key in ("error", "traceback"):
            if result.get(key):
                profile_payload[key] = result[key]
        with profile_file.open("w", encoding="utf-8") as file:
            json.dump(profile_payload, file, ensure_ascii=False, indent=2)
        logger.info("WhisperX profil kaydedildi: %s", profile_file)
    except Exception as exc:
        logger.warning("WhisperX profil yazilamadi: %s", exc)


def apply_alignment_fast_wildcard_patch(whisperx_module, torch_module, enabled: bool) -> dict:
    report = {
        "enabled": bool(enabled),
        "decision": ALIGN_FAST_WILDCARD_DECISION,
        "status": "disabled"
    }
    if not enabled:
        return report

    try:
        alignment_module = getattr(whisperx_module, "alignment", None)
        if alignment_module is None:
            alignment_module = __import__("whisperx.alignment", fromlist=["alignment"])
    except Exception as exc:
        report["status"] = "import_failed"
        report["error"] = str(exc)
        return report

    original_get_trellis = getattr(alignment_module, "get_trellis", None)
    if original_get_trellis is None:
        report["status"] = "get_trellis_missing"
        return report

    if getattr(original_get_trellis, "_dublaj_hatti_fast_wildcard", False):
        report["status"] = "already_patched"
        return report

    def get_trellis_fast_wildcard(emission, tokens, blank_id=0):
        num_frame = emission.size(0)
        num_tokens = len(tokens)
        trellis = torch_module.zeros((num_frame, num_tokens), dtype=emission.dtype, device=emission.device)
        trellis[1:, 0] = torch_module.cumsum(emission[1:, blank_id], 0)
        trellis[0, 1:] = -float("inf")
        trellis[-num_tokens + 1:, 0] = float("inf")

        token_tail = tokens[1:]
        if isinstance(token_tail, torch_module.Tensor):
            token_tensor = token_tail.to(device=emission.device, dtype=torch_module.long)
        else:
            token_tensor = torch_module.tensor(token_tail, device=emission.device, dtype=torch_module.long)
        wildcard_mask = token_tensor == -1
        wildcard_exists = bool(wildcard_mask.any().item()) if token_tensor.numel() else False
        token_indexes = token_tensor.clamp(min=0)

        for t in range(num_frame - 1):
            frame_emission = emission[t]
            change_scores = frame_emission[token_indexes]
            if wildcard_exists:
                if blank_id == 0:
                    max_valid_score = frame_emission[1:].max()
                elif blank_id == frame_emission.numel() - 1:
                    max_valid_score = frame_emission[:-1].max()
                else:
                    max_valid_score = torch_module.cat((frame_emission[:blank_id], frame_emission[blank_id + 1:])).max()
                change_scores = torch_module.where(wildcard_mask, max_valid_score, change_scores)
            trellis[t + 1, 1:] = torch_module.maximum(
                trellis[t, 1:] + emission[t, blank_id],
                trellis[t, :-1] + change_scores,
            )
        return trellis

    get_trellis_fast_wildcard._dublaj_hatti_fast_wildcard = True
    alignment_module.get_trellis = get_trellis_fast_wildcard
    report["status"] = "patched"
    return report


def begin_profile_step(device: str, torch_module=None):
    if torch_module is not None and device == "cuda":
        try:
            if torch_module.cuda.is_available():
                torch_module.cuda.synchronize()
                torch_module.cuda.reset_peak_memory_stats()
        except Exception:
            pass
    return perf_counter()


def end_profile_step(profile_steps, step_name: str, started: float, device: str, torch_module=None, **extra):
    if torch_module is not None and device == "cuda":
        try:
            if torch_module.cuda.is_available():
                torch_module.cuda.synchronize()
        except Exception:
            pass
    entry = {
        "step": step_name,
        "seconds": round(perf_counter() - started, 3)
    }
    if torch_module is not None and device == "cuda":
        try:
            if torch_module.cuda.is_available():
                entry["cuda_peak_allocated_mb"] = round(torch_module.cuda.max_memory_allocated() / (1024 * 1024), 1)
                entry["cuda_peak_reserved_mb"] = round(torch_module.cuda.max_memory_reserved() / (1024 * 1024), 1)
        except Exception:
            pass
    entry.update(extra)
    profile_steps.append(entry)


def fix_overlaps(words):
    """Kelime zamanlarini metin sirasina gore monoton hale getir."""
    fixed = 0
    min_duration = 0.01
    for i, word in enumerate(words):
        start = float(word["start"])
        end = float(word["end"])
        next_start = float(words[i + 1]["start"]) if i + 1 < len(words) else None
        if end < start:
            if next_start is not None and next_start >= start:
                word["end"] = max(start + min_duration, next_start)
            elif next_start is not None:
                word["start"] = max(next_start - min_duration, 0.0)
                word["end"] = next_start
            else:
                word["end"] = start + min_duration
            fixed += 1
    for i in range(len(words) - 1):
        end_i   = words[i]["end"]
        start_n = words[i + 1]["start"]
        if end_i > start_n:
            mid = round((end_i + start_n) / 2.0, 3)
            words[i]["end"]       = mid
            words[i + 1]["start"] = mid
            fixed += 1
    return words, fixed


def build_aligned_word_payload(word_obj):
    word_data = {
        "word": word_obj["word"],
        "start": float(word_obj["start"]),
        "end": float(word_obj["end"]),
        "speaker": word_obj.get("speaker", ""),
    }
    if word_obj.get("score") is not None:
        word_data["score"] = float(word_obj["score"])
    return word_data


def build_aligned_result_payloads(result):
    words = []
    segments_data = []
    for segment_idx, segment in enumerate(result["segments"]):
        segment_words = []

        if "words" in segment and segment["words"]:
            for word_obj in segment["words"]:
                if "start" not in word_obj or "end" not in word_obj:
                    logger.warning(f"[WORKER] Segment {segment_idx}: kelimede timestamp yok, atlaniyor")
                    continue
                word_data = build_aligned_word_payload(word_obj)
                words.append(word_data)
                segment_words.append(word_data)
        else:
            logger.warning(f"[WORKER] Segment {segment_idx}: kelime bulunamadi")

        segments_data.append({
            "index": segment_idx,
            "start": float(segment["start"]),
            "end": float(segment["end"]),
            "text": segment["text"].strip(),
            "words": segment_words,
            "speaker": segment.get("speaker", "")
        })

    words, fixed = fix_overlaps(words)
    if fixed > 0:
        logger.info(f"[WORKER] fix_overlaps: {fixed} cift duzeltildi")
    else:
        logger.info("[WORKER] fix_overlaps: cakisma yok")

    word_idx = 0
    for seg in segments_data:
        for i in range(len(seg["words"])):
            if word_idx < len(words):
                seg["words"][i] = words[word_idx]
                word_idx += 1
    return words, segments_data


def package_aligned_result(result, detected_language, profile_steps, profile_summary_base, device, torch_module):
    step_started = begin_profile_step(device, torch_module)
    words, segments_data = build_aligned_result_payloads(result)

    unique_speakers = set(w.get("speaker", "") for w in words if w.get("speaker"))
    logger.info(f"[WORKER] BASARILI! {len(words)} kelime, {len(segments_data)} segment, {len(unique_speakers)} konusmaci")
    for spk in sorted(unique_speakers):
        spk_word_count = sum(1 for w in words if w.get("speaker") == spk)
        logger.info(f"[WORKER]   {spk}: {spk_word_count} kelime")
    end_profile_step(
        profile_steps,
        "result_packaging",
        step_started,
        device,
        torch_module,
        word_count=len(words),
        segment_count=len(segments_data),
        speaker_count=len(unique_speakers)
    )

    profile_summary = dict(profile_summary_base)
    profile_summary.update({
        "detected_language": detected_language,
        "total_words": len(words),
        "total_segments": len(segments_data),
    })

    return {
        "success": True,
        "words": words,
        "segments": segments_data,
        "detected_language": detected_language,
        "total_words": len(words),
        "total_segments": len(segments_data),
        "total_speakers": len(unique_speakers),
        "profile_steps": profile_steps,
        "profile_summary": profile_summary
    }


def load_alignment_model(whisperx_module, detected_language, device, cache_dir, profile_steps, torch_module):
    logger.info("[WORKER] Hizalama modeli yukleniyor...")
    align_model_name = get_custom_align_model_name(detected_language)
    step_started = begin_profile_step(device, torch_module)
    if align_model_name:
        logger.info(f"[WORKER] Ozel hizalama modeli: {detected_language} -> {align_model_name}")
        model_a, metadata = whisperx_module.load_align_model(
            language_code=detected_language,
            device=device,
            model_name=align_model_name,
            model_dir=str(Path(cache_dir) / "hub")
        )
    else:
        model_a, metadata = whisperx_module.load_align_model(
            language_code=detected_language,
            device=device
        )
    logger.info("[WORKER] Hizalama modeli yuklendi")
    end_profile_step(
        profile_steps,
        "align_model_load",
        step_started,
        device,
        torch_module,
        detected_language=detected_language,
        custom_model=align_model_name or ""
    )
    return model_a, metadata, align_model_name


def align_provided_segments(
    audio_path: str,
    segments_json: str,
    model_name: str,
    device: str,
    compute_type: str,
    language: str,
    cache_dir: str
) -> dict:
    profile_steps = []
    worker_started = perf_counter()
    try:
        os.environ['HF_HOME'] = cache_dir
        os.environ['TRANSFORMERS_CACHE'] = str(Path(cache_dir) / "hub")
        os.environ['HF_HUB_CACHE'] = str(Path(cache_dir) / "hub")
        os.environ['TORCH_HOME'] = str(Path(cache_dir).parent / "torch")

        logger.info("[WORKER] WhisperX alignment-only basliyor...")
        logger.info(f"[WORKER] Ses dosyasi: {audio_path}")
        logger.info(f"[WORKER] Alignment segmentleri: {segments_json}")
        logger.info(f"[WORKER] Cihaz: {device}, Compute: {compute_type}, Dil: {language}")

        step_started = begin_profile_step(device)
        import whisperx
        import torch
        end_profile_step(profile_steps, "import_dependencies", step_started, device)

        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        torch.use_deterministic_algorithms(True, warn_only=True)
        with open(segments_json, "r", encoding="utf-8") as fh:
            provided_segments = json.load(fh)
        if not isinstance(provided_segments, list) or not provided_segments:
            raise RuntimeError("Alignment segment listesi bos")

        detected_language = normalize_language_code(language) or "en"
        model_a, metadata, align_model_name = load_alignment_model(
            whisperx,
            detected_language,
            device,
            cache_dir,
            profile_steps,
            torch
        )

        align_fast_wildcard_enabled = get_env_bool(ALIGN_FAST_WILDCARD_ENV, False)
        align_fast_wildcard_report = apply_alignment_fast_wildcard_patch(
            whisperx,
            torch,
            align_fast_wildcard_enabled
        )
        logger.info("[WORKER] Alignment fast wildcard: %s", align_fast_wildcard_report.get("status"))

        step_started = begin_profile_step(device, torch)
        result = whisperx.align(
            provided_segments,
            model_a,
            metadata,
            audio_path,
            device,
            return_char_alignments=False
        )
        logger.info("[WORKER] Alignment-only tamamlandi")
        end_profile_step(profile_steps, "align_words", step_started, device, torch, segment_count=len(result["segments"]))

        step_started = begin_profile_step(device, torch)
        del model_a
        if device == "cuda":
            torch.cuda.empty_cache()
        logger.info("[WORKER] Alignment modeli VRAM'den temizlendi")
        end_profile_step(profile_steps, "align_model_cleanup", step_started, device, torch)

        return package_aligned_result(
            result,
            detected_language,
            profile_steps,
            {
                "engine": "whisperx",
                "mode": "alignment_only",
                "model_name": model_name,
                "compute_type": compute_type,
                "device": device,
                "language": language,
                "alignment_model_name": align_model_name or "",
                "alignment_fast_wildcard": align_fast_wildcard_report,
                "total_worker_seconds": round(perf_counter() - worker_started, 3)
            },
            device,
            torch
        )
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()

        logger.error(f"[WORKER] FAILED: {error_msg}")
        logger.error(f"[WORKER] Traceback:\n{error_trace}")

        return {
            "success": False,
            "error": error_msg,
            "traceback": error_trace,
            "profile_steps": profile_steps,
            "profile_summary": {
                "engine": "whisperx",
                "mode": "alignment_only",
                "model_name": model_name,
                "compute_type": compute_type,
                "device": device,
                "language": language,
                "total_worker_seconds": round(perf_counter() - worker_started, 3)
            }
        }


def transcribe_audio(
    audio_path: str,
    model_name: str,
    device: str,
    compute_type: str,
    language: str,
    cache_dir: str,
    diarize: bool = False,
    skip_alignment: bool = False,
    decoder_profile: str = "",
) -> dict:
    """
    WhisperX transcription + alignment (subprocess icinde)

    Args:
        audio_path: Path to audio file
        model_name: Whisper model name (tiny, base, small, medium, large)
        device: Device (cuda/cpu)
        compute_type: Compute type (float32/float16/int8)
        language: Language code (auto/en/tr/...)
        cache_dir: HuggingFace cache directory

    Returns:
        {
            "success": bool,
            "words": List[Dict] (if success),
            "segments": List[Dict] (if success),
            "detected_language": str (if success),
            "total_words": int (if success),
            "error": str (if failed),
            "traceback": str (if failed)
        }
    """
    profile_steps = []
    worker_cuda_snapshots = []
    worker_started = perf_counter()
    active_step = "startup"
    active_step_started = worker_started
    resolved_decoder_profile = ""
    requested_decoder_options = {}
    effective_decoder_options = {}
    try:
        os.environ['HF_HOME'] = cache_dir
        os.environ['TRANSFORMERS_CACHE'] = str(Path(cache_dir) / "hub")
        os.environ['HF_HUB_CACHE'] = str(Path(cache_dir) / "hub")
        os.environ['TORCH_HOME'] = str(Path(cache_dir).parent / "torch")

        logger.info("[WORKER] WhisperX transkripsiyon basliyor...")
        logger.info(f"[WORKER] Ses dosyasi: {audio_path}")
        logger.info(f"[WORKER] Model: {model_name}, Cihaz: {device}, Compute: {compute_type}")

        active_step = "import_dependencies"
        active_step_started = perf_counter()
        step_started = begin_profile_step(device)
        import whisperx
        import torch
        from whisperx.vads import Pyannote
        end_profile_step(profile_steps, "import_dependencies", step_started, device)

        active_step = "torch_deterministic_setup"
        active_step_started = perf_counter()
        step_started = begin_profile_step(device, torch)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        torch.use_deterministic_algorithms(True, warn_only=True)
        logger.info("[WORKER] PyTorch deterministik mod: AKTIF")
        end_profile_step(profile_steps, "torch_deterministic_setup", step_started, device, torch)

        logger.info(f"[WORKER] Cache dizini: {cache_dir}")

        auto_detect = language in (None, "", "auto")

        if auto_detect:
            logger.info("[WORKER] Dil: otomatik tespit")
            lang_param = None
        else:
            logger.info(f"[WORKER] Dil: {language}")
            lang_param = language

        logger.info(f"[WORKER] WhisperX modeli yukleniyor...")
        active_step = "whisper_model_load"
        active_step_started = perf_counter()
        step_started = begin_profile_step(device, torch)
        vad_model = create_cpu_pyannote_vad_model(torch, Pyannote)
        (
            model,
            resolved_decoder_profile,
            requested_decoder_options,
            effective_decoder_options,
        ) = load_whisperx_transcription_model(
            whisperx,
            model_name,
            device,
            compute_type,
            cache_dir,
            vad_model,
            decoder_profile,
        )
        logger.info("[WORKER] Pyannote VAD: CPU")
        logger.info("[WORKER] Decoder profile: %s", resolved_decoder_profile)
        logger.info("[WORKER] Decoder options: %s", effective_decoder_options)
        logger.info("[WORKER] Model yuklendi")
        end_profile_step(
            profile_steps,
            "whisper_model_load",
            step_started,
            device,
            torch,
            decoder_contract_version=WHISPERX_DECODER_CONTRACT_VERSION,
            decoder_profile=resolved_decoder_profile,
            requested_decoder_options=requested_decoder_options,
            effective_decoder_options=effective_decoder_options,
        )

        logger.info("[WORKER] Transkripsiyon yapiliyor...")
        batch_size = get_transcribe_batch_size(device)
        active_step = "whisper_transcribe"
        active_step_started = perf_counter()
        worker_cuda_snapshots.append(
            capture_worker_cuda_snapshot(device, torch, "before_whisper_transcribe")
        )
        step_started = begin_profile_step(device, torch)
        result = model.transcribe(
            audio_path,
            batch_size=batch_size,
            language=lang_param
        )

        detected_language = result.get("language", "en")
        logger.info(f"[WORKER] Transkripsiyon tamamlandi: {len(result['segments'])} segment")
        logger.info(f"[WORKER] Tespit edilen dil: {detected_language}")
        end_profile_step(
            profile_steps,
            "whisper_transcribe",
            step_started,
            device,
            torch,
            batch_size=batch_size,
            batch_decision=CUDA_TRANSCRIBE_BATCH_DECISION if device == "cuda" else "cpu_default_batch4",
            detected_language=detected_language,
            segment_count=len(result["segments"]),
            language_mode="auto" if auto_detect else "direct"
        )

        active_step = "whisper_model_cleanup"
        active_step_started = perf_counter()
        step_started = begin_profile_step(device, torch)
        del model
        if device == "cuda":
            torch.cuda.empty_cache()
        logger.info("[WORKER] Whisper modeli VRAM'den temizlendi")
        end_profile_step(profile_steps, "whisper_model_cleanup", step_started, device, torch)

        if skip_alignment:
            segments_data = [
                {
                    "index": segment_idx,
                    "start": float(segment["start"]),
                    "end": float(segment["end"]),
                    "text": str(segment["text"]).strip(),
                    "words": [],
                    "speaker": "",
                }
                for segment_idx, segment in enumerate(result["segments"])
                if str(segment.get("text") or "").strip()
            ]
            if not segments_data:
                raise RuntimeError("WhisperX hizalamasiz transkripsiyon bos segment uretti")
            return {
                "success": True,
                "words": [],
                "segments": segments_data,
                "detected_language": detected_language,
                "total_words": 0,
                "total_segments": len(segments_data),
                "total_speakers": 0,
                "profile_steps": profile_steps,
                "profile_summary": {
                    "engine": "whisperx",
                    "model_name": model_name,
                    "compute_type": compute_type,
                    "device": device,
                    "language": language,
                    "detected_language": detected_language,
                    "transcribe_batch_size": batch_size,
                    "alignment_skipped": True,
                    "decoder_contract_version": WHISPERX_DECODER_CONTRACT_VERSION,
                    "decoder_profile": resolved_decoder_profile,
                    "requested_decoder_options": requested_decoder_options,
                    "effective_decoder_options": effective_decoder_options,
                    "transcription_vad_provider": TRANSCRIPTION_VAD_PROVIDER,
                    "transcription_vad_device": TRANSCRIPTION_VAD_DEVICE,
                    "transcription_vad_chunk_size": TRANSCRIPTION_VAD_CHUNK_SIZE,
                    "transcription_vad_onset": TRANSCRIPTION_VAD_ONSET,
                    "transcription_vad_offset": TRANSCRIPTION_VAD_OFFSET,
                    "worker_pid": os.getpid(),
                    "worker_parent_pid": os.getppid(),
                    "cuda_snapshots": worker_cuda_snapshots,
                    "total_worker_seconds": round(perf_counter() - worker_started, 3),
                },
            }

        logger.info("[WORKER] Hizalama modeli yukleniyor...")
        align_model_name = get_custom_align_model_name(detected_language)
        active_step = "align_model_load"
        active_step_started = perf_counter()
        step_started = begin_profile_step(device, torch)
        if align_model_name:
            logger.info(f"[WORKER] Ozel hizalama modeli: {detected_language} -> {align_model_name}")
            model_a, metadata = whisperx.load_align_model(
                language_code=detected_language,
                device=device,
                model_name=align_model_name,
                model_dir=str(Path(cache_dir) / "hub")
            )
        else:
            model_a, metadata = whisperx.load_align_model(
                language_code=detected_language,
                device=device
            )
        logger.info("[WORKER] Hizalama modeli yuklendi")
        end_profile_step(
            profile_steps,
            "align_model_load",
            step_started,
            device,
            torch,
            detected_language=detected_language,
            custom_model=align_model_name or ""
        )

        align_fast_wildcard_enabled = get_env_bool(ALIGN_FAST_WILDCARD_ENV, False)
        align_fast_wildcard_report = apply_alignment_fast_wildcard_patch(
            whisperx,
            torch,
            align_fast_wildcard_enabled
        )
        logger.info("[WORKER] Alignment fast wildcard: %s", align_fast_wildcard_report.get("status"))

        logger.info("[WORKER] Kelimeler hizalaniyor...")
        active_step = "align_words"
        active_step_started = perf_counter()
        step_started = begin_profile_step(device, torch)
        result = whisperx.align(
            result["segments"],
            model_a,
            metadata,
            audio_path,
            device,
            return_char_alignments=False
        )
        logger.info("[WORKER] Hizalama tamamlandi")
        end_profile_step(profile_steps, "align_words", step_started, device, torch, segment_count=len(result["segments"]))

        active_step = "align_model_cleanup"
        active_step_started = perf_counter()
        step_started = begin_profile_step(device, torch)
        del model_a
        if device == "cuda":
            torch.cuda.empty_cache()
        logger.info("[WORKER] Alignment modeli VRAM'den temizlendi")
        end_profile_step(profile_steps, "align_model_cleanup", step_started, device, torch)

        if diarize:
            logger.info("[WORKER] Diarization basliyor...")
            active_step = "diarization"
            active_step_started = perf_counter()
            step_started = begin_profile_step(device, torch)
            try:
                diarize_model = whisperx.DiarizationPipeline(
                    device=device
                )
            except Exception as exc:
                anlamli = kapili_model_hatasi(exc)
                if anlamli:
                    raise RuntimeError(anlamli) from exc
                raise
            diarize_model.model.instantiate({
                "clustering": {
                    "method": "centroid",
                    "min_cluster_size": 6,
                    "threshold": 0.55,
                },
                "segmentation": {
                    "min_duration_off": 0.0,
                },
            })
            logger.info("[WORKER] Diarization parametreleri: threshold=0.55, min_cluster_size=6, max_speakers=12")
            diarize_segments = diarize_model(audio_path, min_speakers=2, max_speakers=12)
            result = whisperx.assign_word_speakers(diarize_segments, result)
            logger.info("[WORKER] Diarization tamamlandi")
            end_profile_step(profile_steps, "diarization", step_started, device, torch, min_speakers=2, max_speakers=12)

            speaker_first_time = {}
            for seg in result["segments"]:
                spk = seg.get("speaker", "")
                if spk and spk not in speaker_first_time:
                    speaker_first_time[spk] = seg["start"]
            chronological_order = sorted(speaker_first_time.keys(), key=lambda s: speaker_first_time[s])
            rename_map = {old: f"SPEAKER_{idx:02d}" for idx, old in enumerate(chronological_order)}

            if rename_map:
                for seg in result["segments"]:
                    old_spk = seg.get("speaker", "")
                    if old_spk in rename_map:
                        seg["speaker"] = rename_map[old_spk]
                    if "words" in seg:
                        for w in seg["words"]:
                            old_w_spk = w.get("speaker", "")
                            if old_w_spk in rename_map:
                                w["speaker"] = rename_map[old_w_spk]
                logger.info("[WORKER] Speaker etiketleri kronolojik siraya gore yeniden atandi:")
                for old, new in rename_map.items():
                    logger.info("[WORKER]   %s → %s (ilk konusma: %.2fs)", old, new, speaker_first_time[old])

            del diarize_model
            if device == "cuda":
                torch.cuda.empty_cache()
            logger.info("[WORKER] Diarization modeli VRAM'den temizlendi")
        else:
            logger.info("[WORKER] Diarization devre disi (--diarize flag verilmedi)")

        active_step = "result_packaging"
        active_step_started = perf_counter()
        step_started = begin_profile_step(device, torch)
        words, segments_data = build_aligned_result_payloads(result)

        unique_speakers = set(w.get("speaker", "") for w in words if w.get("speaker"))
        logger.info(f"[WORKER] BASARILI! {len(words)} kelime, {len(segments_data)} segment, {len(unique_speakers)} konusmaci")
        for spk in sorted(unique_speakers):
            spk_word_count = sum(1 for w in words if w.get("speaker") == spk)
            logger.info(f"[WORKER]   {spk}: {spk_word_count} kelime")
        end_profile_step(
            profile_steps,
            "result_packaging",
            step_started,
            device,
            torch,
            word_count=len(words),
            segment_count=len(segments_data),
            speaker_count=len(unique_speakers)
        )

        return {
            "success": True,
            "words": words,
            "segments": segments_data,
            "detected_language": detected_language,
            "total_words": len(words),
            "total_segments": len(segments_data),
            "total_speakers": len(unique_speakers),
            "profile_steps": profile_steps,
            "profile_summary": {
                "engine": "whisperx",
                "model_name": model_name,
                "compute_type": compute_type,
                "device": device,
                "language": language,
                "detected_language": detected_language,
                "transcribe_batch_size": batch_size,
                "transcribe_batch_decision": CUDA_TRANSCRIBE_BATCH_DECISION if device == "cuda" else "cpu_default_batch4",
                "optimization_source_step": "whisper_transcribe",
                "decoder_contract_version": WHISPERX_DECODER_CONTRACT_VERSION,
                "decoder_profile": resolved_decoder_profile,
                "requested_decoder_options": requested_decoder_options,
                "effective_decoder_options": effective_decoder_options,
                "transcription_vad_provider": TRANSCRIPTION_VAD_PROVIDER,
                "transcription_vad_device": TRANSCRIPTION_VAD_DEVICE,
                "transcription_vad_chunk_size": TRANSCRIPTION_VAD_CHUNK_SIZE,
                "transcription_vad_onset": TRANSCRIPTION_VAD_ONSET,
                "transcription_vad_offset": TRANSCRIPTION_VAD_OFFSET,
                "alignment_fast_wildcard": align_fast_wildcard_report,
                "worker_pid": os.getpid(),
                "worker_parent_pid": os.getppid(),
                "cuda_snapshots": worker_cuda_snapshots,
                "total_worker_seconds": round(perf_counter() - worker_started, 3)
            }
        }

    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        torch_module = locals().get("torch")
        failure_snapshot = capture_worker_cuda_snapshot(
            device,
            torch_module,
            f"{active_step}_failure"
        )
        worker_cuda_snapshots.append(failure_snapshot)
        failed_step = {
            "step": active_step,
            "status": "failed",
            "seconds": round(perf_counter() - active_step_started, 3),
            "error": error_msg,
            "cuda_snapshot": failure_snapshot,
        }
        profile_steps.append(failed_step)
        failure_type = "cuda_oom" if "out of memory" in error_msg.lower() else "exception"

        logger.error(f"[WORKER] FAILED: {error_msg}")
        logger.error(f"[WORKER] Traceback:\n{error_trace}")

        return {
            "success": False,
            "error": error_msg,
            "traceback": error_trace,
            "profile_steps": profile_steps,
            "profile_summary": {
                "engine": "whisperx",
                "model_name": model_name,
                "compute_type": compute_type,
                "device": device,
                "language": language,
                "worker_pid": os.getpid(),
                "worker_parent_pid": os.getppid(),
                "failure_stage": active_step,
                "failure_type": failure_type,
                "decoder_contract_version": WHISPERX_DECODER_CONTRACT_VERSION,
                "decoder_profile_requested": decoder_profile,
                "decoder_profile": resolved_decoder_profile,
                "requested_decoder_options": requested_decoder_options,
                "effective_decoder_options": effective_decoder_options,
                "transcription_vad_provider": TRANSCRIPTION_VAD_PROVIDER,
                "transcription_vad_device": TRANSCRIPTION_VAD_DEVICE,
                "transcription_vad_chunk_size": TRANSCRIPTION_VAD_CHUNK_SIZE,
                "transcription_vad_onset": TRANSCRIPTION_VAD_ONSET,
                "transcription_vad_offset": TRANSCRIPTION_VAD_OFFSET,
                "cuda_snapshots": worker_cuda_snapshots,
                "total_worker_seconds": round(perf_counter() - worker_started, 3)
            }
        }


def parse_args():
    parser = argparse.ArgumentParser(
        description="WhisperX Subprocess Worker - Isolated transcription + alignment process"
    )

    parser.add_argument(
        "--audio_path",
        required=True,
        help="Path to audio file (WAV format recommended)"
    )

    parser.add_argument(
        "--model_name",
        default="base",
        help="Whisper model name (tiny/base/small/medium/large, default: base)"
    )

    parser.add_argument(
        "--device",
        default="cuda",
        help="Device (cuda/cpu, default: cuda)"
    )

    parser.add_argument(
        "--compute_type",
        default="int8",
        help="Compute type (float32/float16/int8, default: int8) — GTX 1050 Ti OOM onlemek uzere"
    )

    parser.add_argument(
        "--language",
        default="auto",
        help="Language code (auto/en/tr/..., default: auto)"
    )

    parser.add_argument(
        "--cache_dir",
        required=True,
        help="HuggingFace cache directory"
    )

    parser.add_argument(
        "--diarize",
        action="store_true",
        default=False,
        help="Konusmaci ayristirma (diarization) aktif et"
    )

    parser.add_argument(
        "--skip_alignment",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--align_segments_json",
        default="",
        help="Hazir segment metinlerini WhisperX forced alignment ile hizala"
    )

    parser.add_argument(
        "--profile_path",
        default="",
        help="Worker profil JSON dosyasi"
    )

    parser.add_argument(
        "--decoder_profile",
        default="",
        help="WhisperX decoder profile contract",
    )

    return parser.parse_args()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("WhisperX Subprocess Worker Started")
    logger.info("=" * 60)

    args = parse_args()

    if args.align_segments_json:
        result = align_provided_segments(
            audio_path=args.audio_path,
            segments_json=args.align_segments_json,
            model_name=args.model_name,
            device=args.device,
            compute_type=args.compute_type,
            language=args.language,
            cache_dir=args.cache_dir
        )
    else:
        result = transcribe_audio(
            audio_path=args.audio_path,
            model_name=args.model_name,
            device=args.device,
            compute_type=args.compute_type,
            language=args.language,
            cache_dir=args.cache_dir,
            diarize=args.diarize,
            skip_alignment=args.skip_alignment,
            decoder_profile=args.decoder_profile,
        )

    write_worker_profile(args.profile_path, result)

    sys.stdout = original_stdout

    print(json.dumps(result, ensure_ascii=False, indent=2))

    logger.info("=" * 60)
    logger.info("WhisperX Subprocess Worker Finished")
    logger.info("=" * 60)

    sys.exit(0 if result["success"] else 1)
