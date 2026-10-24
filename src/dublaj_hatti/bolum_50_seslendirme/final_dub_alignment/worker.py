from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import huggingface_home


ALIGN_MODEL_BY_LANGUAGE = {
    "id": "Galuh/wav2vec2-large-xlsr-indonesian",
}


def normalize_language_code(language: str) -> str:
    value = str(language or "tr").strip().lower().replace("_", "-")
    if not value:
        return "tr"
    return value.split("-")[0]


def get_custom_align_model_name(lang_code: str) -> str:
    return ALIGN_MODEL_BY_LANGUAGE.get(normalize_language_code(lang_code), "")


def apply_wildcard_token_index_patch(whisperx_module, torch_module) -> None:
    if os.environ.get("WHISPERX_ALIGN_FAST_WILDCARD", "1").strip().lower() in {"0", "false", "no", "off", ""}:
        return
    if not hasattr(whisperx_module, "alignment"):
        return
    alignment_module = whisperx_module.alignment
    current = alignment_module.get_wildcard_emission
    if getattr(current, "_dublaj_hatti_token_index_patch", False):
        return

    def get_wildcard_emission(frame_emission, tokens, blank_id):
        token_ids = torch_module.as_tensor(tokens, dtype=torch_module.long, device=frame_emission.device)
        wildcard_mask = token_ids == -1
        regular_scores = frame_emission[token_ids.clamp(min=0)]
        valid_scores = frame_emission.clone()
        valid_scores[blank_id] = float("-inf")
        return torch_module.where(wildcard_mask, valid_scores.max(), regular_scores)

    get_wildcard_emission._dublaj_hatti_token_index_patch = True
    alignment_module.get_wildcard_emission = get_wildcard_emission


def align_final_dub(job: dict) -> dict:
    started = perf_counter()
    try:
        cache_dir = str(job.get("cache_dir") or huggingface_home())
        os.environ["HF_HOME"] = cache_dir
        os.environ["TRANSFORMERS_CACHE"] = str(Path(cache_dir) / "hub")
        os.environ["HF_HUB_CACHE"] = str(Path(cache_dir) / "hub")
        os.environ["TORCH_HOME"] = str(Path(cache_dir).parent / "torch")

        import torch
        import whisperx

        language = normalize_language_code(job.get("language", "tr"))
        requested_device = str(job.get("device") or "auto").strip().lower()
        if requested_device in {"", "auto"}:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            device = requested_device
        if device == "cuda" and not torch.cuda.is_available():
            device = "cpu"
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        torch.use_deterministic_algorithms(True, warn_only=True)

        align_model_name = get_custom_align_model_name(language)
        if align_model_name:
            model_a, metadata = whisperx.load_align_model(
                language_code=language,
                device=device,
                model_name=align_model_name,
                model_dir=str(Path(cache_dir) / "hub"),
            )
        else:
            model_a, metadata = whisperx.load_align_model(
                language_code=language,
                device=device,
            )
        apply_wildcard_token_index_patch(whisperx, torch)

        audio_path = str(job.get("audio_path") or "")
        input_segments = []
        segment_lookup = {}
        for item in job.get("segments", []) or []:
            segment_index = _read_segment_index(item)
            text = str(item.get("text") or "").strip()
            start = max(float(item.get("start", 0.0) or 0.0), 0.0)
            end = max(float(item.get("end", start) or start), start + 0.01)
            if segment_index is None or not text:
                continue
            input_segments.append({
                "start": start,
                "end": end,
                "text": text,
                "segment_index": segment_index,
            })
            segment_lookup[segment_index] = {
                "start": start,
                "end": end,
                "text": text,
            }

        if not audio_path or not input_segments:
            raise RuntimeError("Final dub alignment girdisi eksik")

        aligned = whisperx.align(
            input_segments,
            model_a,
            metadata,
            audio_path,
            device,
            return_char_alignments=False,
        )

        words = []
        segment_reports = {}
        for aligned_segment in aligned.get("segments", []) or []:
            segment_index = _read_segment_index(aligned_segment)
            if segment_index not in segment_lookup:
                segment_index = _match_segment_index(aligned_segment, segment_lookup)
            if segment_index is None:
                continue
            segment_reports.setdefault(segment_index, {
                "segment_index": segment_index,
                "word_count": 0,
                "success": False,
                "error": "",
            })
            segment_start = float(segment_lookup.get(segment_index, {}).get("start", 0.0) or 0.0)
            segment_end = float(segment_lookup.get(segment_index, {}).get("end", segment_start) or segment_start)
            for word in aligned_segment.get("words", []) or []:
                word_text = str(word.get("word") or "").strip()
                if not word_text or "start" not in word or "end" not in word:
                    continue
                start = max(float(word.get("start", 0.0) or 0.0), segment_start)
                end = min(max(float(word.get("end", start) or start), start + 0.01), segment_end)
                words.append({
                    "word": word_text,
                    "start": round(start, 6),
                    "end": round(end, 6),
                    "raw_start": round(start, 6),
                    "raw_end": round(end, 6),
                    "segment_index": segment_index,
                    "source": "final_dub_audio_forced_alignment",
                    "official_boundary": False,
                    "time_mapping": "final_timeline_clean_dub_audio_forced_alignment",
                })
                segment_reports[segment_index]["word_count"] += 1
                segment_reports[segment_index]["success"] = True

        del model_a
        if device == "cuda":
            torch.cuda.empty_cache()

        return {
            "success": bool(words),
            "language": language,
            "device": device,
            "custom_align_model": align_model_name,
            "audio_path": audio_path,
            "segment_count": len(input_segments),
            "word_count": len(words),
            "elapsed_seconds": round(perf_counter() - started, 3),
            "words": words,
            "segments": list(segment_reports.values()),
            "error": "" if words else "no_aligned_words",
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "elapsed_seconds": round(perf_counter() - started, 3),
            "words": [],
            "segments": [],
        }


def _read_segment_index(item: dict) -> int | None:
    value = item.get("segment_index")
    if value is None:
        return None
    try:
        segment_index = int(value)
    except (TypeError, ValueError):
        return None
    return segment_index if segment_index >= 0 else None


def _match_segment_index(aligned_segment: dict, segment_lookup: dict[int, dict]) -> int | None:
    start = float(aligned_segment.get("start", 0.0) or 0.0)
    end = float(aligned_segment.get("end", start) or start)
    middle = (start + end) / 2.0
    for segment_index, item in segment_lookup.items():
        if float(item["start"]) <= middle <= float(item["end"]):
            return int(segment_index)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    job = json.loads(Path(args.job).read_text(encoding="utf-8"))
    result = align_final_dub(job)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return 0 if result.get("success") else 2


if __name__ == "__main__":
    raise SystemExit(main())
