from __future__ import annotations

import argparse
import functools
import json
import os
import sys
import traceback
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from dublaj_hatti.bolum_50_seslendirme.final_dub_alignment.worker import (
    apply_wildcard_token_index_patch,
    get_custom_align_model_name,
    normalize_language_code,
)


def cache_whisperx_sentence_splitters(alignment_module) -> None:
    if not hasattr(alignment_module.nltk_load, "cache_info"):
        alignment_module.nltk_load = functools.lru_cache(maxsize=None)(alignment_module.nltk_load)


def resolve_candidate_segment_index(aligned_segment: dict, candidate_segments: list[dict]) -> int:
    explicit_index = int(aligned_segment.get("segment_index", 0) or 0)
    if any(int(item["segment_index"]) == explicit_index for item in candidate_segments):
        return explicit_index
    start = float(aligned_segment.get("start", 0.0) or 0.0)
    end = max(float(aligned_segment.get("end", start) or start), start)
    middle = (start + end) / 2.0
    for candidate in candidate_segments:
        if float(candidate["start"]) <= middle <= float(candidate["end"]):
            return int(candidate["segment_index"])
    return 0


def align_candidate_batch(job: dict) -> dict:
    started = perf_counter()
    try:
        cache_dir = str(job.get("cache_dir") or "")
        os.environ["HF_HOME"] = cache_dir
        os.environ["TRANSFORMERS_CACHE"] = str(Path(cache_dir) / "hub")
        os.environ["HF_HUB_CACHE"] = str(Path(cache_dir) / "hub")
        os.environ["TORCH_HOME"] = str(Path(cache_dir).parent / "torch")

        import torch
        import whisperx
        import whisperx.alignment

        cache_whisperx_sentence_splitters(whisperx.alignment)

        language = normalize_language_code(job.get("language", "tr")) or "tr"
        requested_device = str(job.get("device") or "auto").strip().lower()
        device = "cuda" if requested_device in {"", "auto"} and torch.cuda.is_available() else requested_device
        if device == "cuda" and not torch.cuda.is_available():
            device = "cpu"
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        torch.use_deterministic_algorithms(True, warn_only=True)

        audio_path = str(job.get("audio_path") or "")
        candidate_segments = [
            {
                "segment_index": int(item.get("segment_index", 0) or 0),
                "start": max(float(item.get("start", 0.0) or 0.0), 0.0),
                "end": max(float(item.get("end", 0.0) or 0.0), 0.01),
                "text": str(item.get("text") or "").strip(),
            }
            for item in job.get("segments", []) or []
            if int(item.get("segment_index", 0) or 0) > 0 and str(item.get("text") or "").strip()
        ]
        if not audio_path or not candidate_segments:
            raise RuntimeError("Aday alignment girdisi eksik")

        alignment_input = candidate_segments
        words = []
        custom_align_model = ""
        if alignment_input:
            custom_align_model = get_custom_align_model_name(language)
            if custom_align_model:
                model_a, metadata = whisperx.load_align_model(
                    language_code=language,
                    device=device,
                    model_name=custom_align_model,
                    model_dir=str(Path(cache_dir) / "hub"),
                )
            else:
                model_a, metadata = whisperx.load_align_model(language_code=language, device=device)
            apply_wildcard_token_index_patch(whisperx, torch)
            aligned = whisperx.align(
                alignment_input,
                model_a,
                metadata,
                audio_path,
                device,
                return_char_alignments=False,
            )
            for aligned_segment in aligned.get("segments", []) or []:
                segment_index = resolve_candidate_segment_index(aligned_segment, alignment_input)
                if segment_index <= 0:
                    continue
                for word in aligned_segment.get("words", []) or []:
                    if "start" not in word or "end" not in word:
                        continue
                    word_text = str(word.get("word") or "").strip()
                    if word_text:
                        words.append({
                            "word": word_text,
                            "start": round(float(word["start"]), 6),
                            "end": round(float(word["end"]), 6),
                            "segment_index": segment_index,
                            "source": "candidate_audio_forced_alignment",
                            "time_mapping": "candidate_batch_audio_forced_alignment",
                        })
            del model_a
            if device == "cuda":
                torch.cuda.empty_cache()
        return {
            "success": True,
            "language": language,
            "device": device,
            "model_name": str(job.get("model_name") or "large-v3-turbo"),
            "compute_type": str(job.get("compute_type") or "float32"),
            "custom_align_model": custom_align_model,
            "words": words,
            "word_count": len(words),
            "elapsed_seconds": round(perf_counter() - started, 3),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "words": [],
            "elapsed_seconds": round(perf_counter() - started, 3),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    job = json.loads(Path(args.job).read_text(encoding="utf-8"))
    result = align_candidate_batch(job)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return 0 if result.get("success") else 2


if __name__ == "__main__":
    raise SystemExit(main())
