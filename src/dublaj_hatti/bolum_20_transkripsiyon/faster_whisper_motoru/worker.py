# -*- coding: utf-8 -*-
"""
faster-whisper Subprocess Worker
Izole process olarak calisir, VRAM leak'ini OS temizler

Native faster-whisper word timestamps kullanir

KULLANIM:
    python worker.py \
        --audio_path "audio.wav" \
        --model_name "base" \
        --device "cuda" \
        --compute_type "int8" \
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
from pathlib import Path
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

warnings.filterwarnings("ignore")

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)
DISTIL_ENGLISH_CONFIDENCE_THRESHOLD = 0.90
DISTIL_ENGLISH_ONLY_MODELS = {"distil-large-v3", "distil-large-v3.5"}


def should_use_vad_filter(model_name: str) -> bool:
    normalized_model_name = str(model_name or "").strip().lower()
    return normalized_model_name not in DISTIL_ENGLISH_ONLY_MODELS


def prepare_model_feature_extractor(model, model_name: str, feature_extractor_factory=None) -> bool:
    normalized_model_name = str(model_name or "").strip().lower()
    mel_filters = getattr(model.feature_extractor, "mel_filters", None)
    mel_filter_shape = getattr(mel_filters, "shape", ())
    current_feature_size = int(mel_filter_shape[0]) if mel_filter_shape else 80
    if normalized_model_name not in DISTIL_ENGLISH_ONLY_MODELS or current_feature_size == 128:
        return False
    if feature_extractor_factory is None:
        from faster_whisper.feature_extractor import FeatureExtractor
        feature_extractor_factory = FeatureExtractor
    model.feature_extractor = feature_extractor_factory(feature_size=128)
    return True


def transcribe_audio(
    audio_path: str,
    model_name: str,
    device: str,
    compute_type: str,
    language: str,
    cache_dir: str
) -> dict:
    """
    faster-whisper transcription (subprocess icinde)

    Args:
        audio_path: Path to audio file
        model_name: faster-whisper model name (tiny, base, small, medium)
        device: Device (cuda/cpu)
        compute_type: Compute type (int8/float32/float16)
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
    try:
        import os

        os.environ['HF_HOME'] = cache_dir
        os.environ['TRANSFORMERS_CACHE'] = str(Path(cache_dir) / "hub")
        os.environ['HF_HUB_CACHE'] = str(Path(cache_dir) / "hub")

        logger.info("[WORKER] faster-whisper transkripsiyon basliyor...")
        logger.info(f"[WORKER] Ses dosyasi: {audio_path}")
        logger.info(f"[WORKER] Model: {model_name}, Cihaz: {device}, Compute: {compute_type}")

        import faster_whisper
        import torch
        import random
        import numpy as np

        # DETERMINISTIC MODE - Her subprocess için sabit seed
        random.seed(42)
        np.random.seed(42)
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        # PyTorch deterministic operations
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

        # CUDA deterministic algorithms (kritik!)
        torch.use_deterministic_algorithms(True, warn_only=True)

        # Environment variables for determinism
        os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'

        logger.info("[WORKER] Deterministik mod: TAM (seed=42, algorithms=True)")

        logger.info(f"[WORKER] Cache dizini: {cache_dir}")

        auto_detect = language in (None, "", "auto")

        if auto_detect:
            logger.info("[WORKER] Dil: otomatik tespit")
        else:
            logger.info(f"[WORKER] Dil: {language}")

        logger.info(f"[WORKER] faster-whisper modeli yukleniyor...")
        model = faster_whisper.WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            cpu_threads=1,
            num_workers=1,
            download_root=str(Path(cache_dir) / "hub")
        )
        if prepare_model_feature_extractor(model, model_name):
            logger.info("[WORKER] Distil-Large-v3 feature extractor: 128 mel")
        logger.info("[WORKER] Model yuklendi: cpu_threads=1, num_workers=1 (deterministik)")

        logger.info("[WORKER] Ses dosyasi yukleniyor...")
        audio = faster_whisper.audio.decode_audio(audio_path, sampling_rate=16000)
        logger.info("[WORKER] Ses dosyasi yuklendi")

        logger.info("[WORKER] Transkripsiyon yapiliyor (word_timestamps=True)...")

        lang_param = None if auto_detect else language

        vad_parameters = {
            'threshold': 0.5,
            'min_speech_duration_ms': 0,
            'max_speech_duration_s': float('inf'),
            'min_silence_duration_ms': 500,
            'speech_pad_ms': 300
        }
        use_vad_filter = should_use_vad_filter(model_name)
        active_vad_parameters = vad_parameters if use_vad_filter else None

        logger.info("[WORKER] VAD filtresi: %s", "AKTIF" if use_vad_filter else "KAPALI")
        if active_vad_parameters:
            logger.info(f"[WORKER] VAD parameters: {active_vad_parameters}")
        logger.info("[WORKER] Tam deterministik transkripsiyon parametreleri")

        if str(model_name or "").strip().lower() in DISTIL_ENGLISH_ONLY_MODELS and auto_detect:
            from faster_whisper.vad import VadOptions
            detected_language, language_probability, all_language_probs = model.detect_language(
                audio=audio,
                vad_filter=True,
                vad_parameters=VadOptions(**vad_parameters),
                language_detection_segments=3,
                language_detection_threshold=DISTIL_ENGLISH_CONFIDENCE_THRESHOLD,
            )
            language_probabilities = dict(all_language_probs)
            english_probability = float(language_probabilities.get("en", 0.0))
            non_english_probabilities = [item for item in all_language_probs if item[0] != "en"]
            best_non_english_language = non_english_probabilities[0][0] if non_english_probabilities else ""
            best_non_english_probability = float(non_english_probabilities[0][1]) if non_english_probabilities else 0.0
            logger.info(
                "[WORKER] Distil English gate: detected=%s english_probability=%.6f threshold=%.2f",
                detected_language,
                english_probability,
                DISTIL_ENGLISH_CONFIDENCE_THRESHOLD,
            )
            if detected_language != "en" or english_probability < DISTIL_ENGLISH_CONFIDENCE_THRESHOLD:
                logger.warning("[WORKER] Distil English gate: fallback required")
                return {
                    "success": True,
                    "fallback_required": True,
                    "fallback_trigger": "distil_language_gate",
                    "detected_language": detected_language,
                    "english_probability": english_probability,
                    "best_non_english_language": best_non_english_language,
                    "best_non_english_probability": best_non_english_probability,
                    "total_words": 0,
                    "total_segments": 0,
                }
            lang_param = "en"

        segments_generator, info = model.transcribe(
            audio,
            language=lang_param,
            task="transcribe",
            word_timestamps=True,
            vad_filter=use_vad_filter,
            vad_parameters=active_vad_parameters,
            initial_prompt="",
            condition_on_previous_text=False,
            temperature=0.0,
            beam_size=5,
            best_of=5,
            patience=1.0,
            length_penalty=1.0,
            repetition_penalty=1.0,
            no_repeat_ngram_size=0,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6
        )

        segments_list = list(segments_generator)

        detected_language = info.language
        logger.info(f"[WORKER] Transkripsiyon tamamlandi: {len(segments_list)} segment")
        logger.info(f"[WORKER] Tespit edilen dil: {detected_language}")

        words = []
        segments_data = []

        for segment_idx, segment in enumerate(segments_list):
            segment_words = []

            if hasattr(segment, 'words') and segment.words:
                for word_obj in segment.words:
                    word_data = {
                        "word": word_obj.word,
                        "start": float(word_obj.start),
                        "end": float(word_obj.end)
                    }
                    words.append(word_data)
                    segment_words.append(word_data)
            else:
                logger.warning(f"[WORKER] Segment {segment_idx}: kelime bulunamadi")

            segments_data.append({
                "index": segment_idx,
                "start": float(segment.start),
                "end": float(segment.end),
                "text": segment.text.strip(),
                "words": segment_words
            })

        logger.info(f"[WORKER] SUCCESS! Extracted {len(words)} words, {len(segments_data)} segments")

        return {
            "success": True,
            "words": words,
            "segments": segments_data,
            "detected_language": detected_language,
            "total_words": len(words),
            "total_segments": len(segments_data)
        }

    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()

        logger.error(f"[WORKER] FAILED: {error_msg}")
        logger.error(f"[WORKER] Traceback:\n{error_trace}")

        return {
            "success": False,
            "error": error_msg,
            "traceback": error_trace
        }


def parse_args():
    parser = argparse.ArgumentParser(
        description="faster-whisper Subprocess Worker - Isolated transcription process"
    )

    parser.add_argument(
        "--audio_path",
        required=True,
        help="Path to audio file (WAV format recommended)"
    )

    parser.add_argument(
        "--model_name",
        default="base",
        help="faster-whisper model name (tiny/base/small/medium/distil-large-v3.5, default: base)"
    )

    parser.add_argument(
        "--device",
        default="cuda",
        help="Device (cuda/cpu, default: cuda)"
    )

    parser.add_argument(
        "--compute_type",
        default="int8",
        help="Compute type (int8/float32/float16, default: int8)"
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

    return parser.parse_args()


if __name__ == "__main__":
    original_stdout = sys.stdout
    sys.stdout = sys.stderr

    logger.info("=" * 60)
    logger.info("faster-whisper Subprocess Worker Started")
    logger.info("=" * 60)

    args = parse_args()

    result = transcribe_audio(
        audio_path=args.audio_path,
        model_name=args.model_name,
        device=args.device,
        compute_type=args.compute_type,
        language=args.language,
        cache_dir=args.cache_dir
    )

    sys.stdout = original_stdout

    print(json.dumps(result, ensure_ascii=False, indent=2))

    logger.info("=" * 60)
    logger.info("faster-whisper Subprocess Worker Finished")
    logger.info("=" * 60)

    sys.exit(0 if result["success"] else 1)
