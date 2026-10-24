import argparse
import json
import logging
import os
import sys
import warnings
from pathlib import Path
from time import perf_counter

try:
    from .ctc_konusma_siniri import (
        NO_SPACE_ALIGNMENT_LANGUAGES,
        SPEECH_PAD_SECONDS,
        WORD_BOUNDARY_POLICY,
        apply_speech_bounds,
        is_no_space_language,
        no_space_alignment_segments,
        regroup_character_words,
        source_word_texts,
    )
except ImportError:
    from ctc_konusma_siniri import (
        NO_SPACE_ALIGNMENT_LANGUAGES,
        SPEECH_PAD_SECONDS,
        WORD_BOUNDARY_POLICY,
        apply_speech_bounds,
        is_no_space_language,
        no_space_alignment_segments,
        regroup_character_words,
        source_word_texts,
    )

original_stdout = sys.stdout
sys.stdout = sys.stderr
warnings.filterwarnings("ignore")
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

ALIGN_MODEL_BY_LANGUAGE = {
    "id": "Galuh/wav2vec2-large-xlsr-indonesian",
}


def normalize_language_code(lang_code: str) -> str:
    return str(lang_code or "").strip().lower().split("-", 1)[0].split("_", 1)[0]


def fix_overlaps(words: list[dict]) -> int:
    fixed = 0
    minimum_duration = 0.01
    for index, word in enumerate(words):
        start, end = float(word["start"]), float(word["end"])
        next_start = float(words[index + 1]["start"]) if index + 1 < len(words) else None
        if end < start:
            if next_start is not None and next_start >= start:
                word["end"] = max(start + minimum_duration, next_start)
            elif next_start is not None:
                word["start"] = max(next_start - minimum_duration, 0.0)
                word["end"] = next_start
            else:
                word["end"] = start + minimum_duration
            fixed += 1
    for current, following in zip(words, words[1:]):
        if current["end"] > following["start"]:
            middle = round((current["end"] + following["start"]) / 2.0, 3)
            current["end"] = middle
            following["start"] = middle
            fixed += 1
    return fixed


def measured_speech_span(word: dict) -> list[float] | None:
    if word.get("speech_start") is None or word.get("speech_end") is None:
        return None
    return [float(word["speech_start"]), float(word["speech_end"])]


def aligned_payload(result: dict) -> tuple[list[dict], list[dict], list[list[float] | None]]:
    words, segments, speech_spans = [], [], []
    for segment_index, segment in enumerate(result["segments"]):
        segment_words = []
        for word in segment.get("words") or []:
            if "start" not in word or "end" not in word:
                continue
            payload = {"word": word["word"], "start": float(word["start"]), "end": float(word["end"]), "speaker": word.get("speaker", "")}
            if word.get("score") is not None:
                payload["score"] = float(word["score"])
            words.append(payload)
            speech_spans.append(measured_speech_span(word))
            segment_words.append(payload)
        segments.append({
            "index": segment_index,
            "start": float(segment["start"]),
            "end": float(segment["end"]),
            "text": str(segment["text"]).strip(),
            "words": segment_words,
            "speaker": segment.get("speaker", ""),
        })
    return words, segments, speech_spans


def load_alignment_model(whisperx, language: str, device: str, cache_dir: str):
    custom_model = ALIGN_MODEL_BY_LANGUAGE.get(language, "")
    if custom_model:
        model, metadata = whisperx.load_align_model(
            language_code=language, device=device, model_name=custom_model, model_dir=str(Path(cache_dir) / "hub")
        )
    else:
        model, metadata = whisperx.load_align_model(language_code=language, device=device)
    return model, metadata, custom_model


def require_matching_no_space_languages(whisperx_languages) -> None:
    if frozenset(whisperx_languages) != NO_SPACE_ALIGNMENT_LANGUAGES:
        raise RuntimeError(
            "WhisperX no-space language set changed: "
            f"whisperx={sorted(whisperx_languages)} box={sorted(NO_SPACE_ALIGNMENT_LANGUAGES)}"
        )


def align_with_source_words(whisperx, input_segments: list[dict], model, metadata, audio, device: str,
                            language: str) -> tuple[dict, int]:
    if not is_no_space_language(language):
        return whisperx.align(input_segments, model, metadata, audio, device, return_char_alignments=False), 0
    from whisperx.alignment import LANGUAGES_WITHOUT_SPACES

    require_matching_no_space_languages(LANGUAGES_WITHOUT_SPACES)
    result = whisperx.align(
        no_space_alignment_segments(input_segments), model, metadata, audio, device, return_char_alignments=False
    )
    regrouped = regroup_character_words(result["segments"], source_word_texts(input_segments))
    return result, regrouped


def align(audio_path: str, segments_json: str, language: str, device: str, cache_dir: str) -> dict:
    started = perf_counter()
    steps = {}
    os.environ["HF_HOME"] = cache_dir
    os.environ["TRANSFORMERS_CACHE"] = str(Path(cache_dir) / "hub")
    os.environ["HF_HUB_CACHE"] = str(Path(cache_dir) / "hub")
    os.environ["TORCH_HOME"] = str(Path(cache_dir).parent / "torch")

    step = perf_counter()
    import torch
    import whisperx
    steps["import_seconds"] = round(perf_counter() - step, 3)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True, warn_only=True)
    input_segments = json.loads(Path(segments_json).read_text(encoding="utf-8"))
    if not isinstance(input_segments, list) or not input_segments:
        raise RuntimeError("Alignment segment listesi bos")
    normalized_language = normalize_language_code(language) or "en"

    step = perf_counter()
    model, metadata, custom_model = load_alignment_model(whisperx, normalized_language, device, cache_dir)
    audio = whisperx.load_audio(audio_path)
    steps["model_load_seconds"] = round(perf_counter() - step, 3)

    step = perf_counter()
    result, regrouped_words = align_with_source_words(
        whisperx, input_segments, model, metadata, audio, device, normalized_language
    )
    steps["align_seconds"] = round(perf_counter() - step, 3)

    step = perf_counter()
    bounding = apply_speech_bounds(result["segments"], input_segments, model, metadata, audio, device, torch)
    steps["speech_bounding_seconds"] = round(perf_counter() - step, 3)

    del model
    if device == "cuda":
        torch.cuda.empty_cache()
    words, segments, speech_spans = aligned_payload(result)
    overlap_fixes = fix_overlaps(words)
    logger.info("[CTC_HIZALAMA] kelime=%d sinirlanan=%d tasinan=%d cakisma_duzeltme=%d",
                len(words), bounding["bounded_words"], bounding["relocated_words"], overlap_fixes)
    return {
        "success": True,
        "words": words,
        "speech_spans": speech_spans,
        "segments": segments,
        "detected_language": normalized_language,
        "total_words": len(words),
        "total_segments": len(segments),
        "profile_summary": {
            "engine": "ctc_kelime_hizalama",
            "mode": "alignment_only",
            "device": device,
            "language": normalized_language,
            "alignment_model_name": custom_model,
            "word_boundary_policy": WORD_BOUNDARY_POLICY,
            "no_space_character_regrouping": is_no_space_language(normalized_language),
            "regrouped_source_words": regrouped_words,
            "speech_pad_seconds": SPEECH_PAD_SECONDS,
            "speech_bounding": bounding,
            "overlap_fixes": overlap_fixes,
            "steps": steps,
            "total_worker_seconds": round(perf_counter() - started, 3),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio_path", required=True)
    parser.add_argument("--segments_json", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--cache_dir", required=True)
    args = parser.parse_args()
    try:
        payload = align(args.audio_path, args.segments_json, args.language, args.device, args.cache_dir)
        code = 0
    except Exception as error:
        import traceback
        logger.error("[CTC_HIZALAMA] HATA: %s", error)
        payload = {"success": False, "error": f"{type(error).__name__}: {error}", "traceback": traceback.format_exc()}
        code = 1
    original_stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    original_stdout.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
