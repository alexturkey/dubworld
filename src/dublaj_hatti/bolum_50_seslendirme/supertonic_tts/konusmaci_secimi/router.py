# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.cinsiyet_secimi.gender_worker import (
    MODEL_ID,
    MAX_AUDIO_SECONDS,
    SAMPLE_RATE,
    run_gender_worker,
)

from .audio_prepare import prepare_speaker_input_audio
from .diarization_adapter import run_3d_speaker_diarization
from .report import write_debug_reports, write_json, write_summary
from .voice_assignment import assign_voice_ids_to_speakers


logger = logging.getLogger("dublaj_hatti")
MIN_GENDER_SEGMENT_SECONDS = 0.30
MAX_GENDER_AUDIO_SECONDS = MAX_AUDIO_SECONDS
GENDER_SAMPLE_RATE = SAMPLE_RATE
MIN_SPEAKER_SPLIT_GROUP_SECONDS = 0.40


def append_progress(path: Path, stage: str, **details) -> None:
    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
    }
    payload.update(details)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def collect_progress_timings(path: Path) -> dict[str, float]:
    timings: dict[str, float] = {}
    if not path.is_file():
        return timings
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        stage = str(item.get("stage") or "")
        if stage == "vendor_import_started" and "elapsed_since_subprocess_start_seconds" in item:
            timings["subprocess_start_to_vendor_import"] = float(
                item["elapsed_since_subprocess_start_seconds"]
            )
        elif stage.endswith("_completed") and "elapsed_seconds" in item:
            key = stage.removesuffix("_completed")
            timings[key] = round(timings.get(key, 0.0) + float(item["elapsed_seconds"]), 6)
    return timings


def build_speaker_timeline_from_segment_words(segments) -> list[dict]:
    timeline = []
    previous_start = -1.0
    for segment in segments:
        for word in usable_segment_words(getattr(segment, "words", None)):
            speaker = str(word.get("speaker") or "").strip()
            if not speaker:
                continue
            start = float(word["start"])
            end = float(word["end"])
            if start < previous_start or end < start:
                raise ValueError("ElevenLabs speaker kelime zamanlari kronolojik degil")
            previous_start = start
            if timeline and timeline[-1]["speaker"] == speaker:
                timeline[-1]["end"] = max(float(timeline[-1]["end"]), end)
            else:
                timeline.append({"start": start, "end": end, "speaker": speaker})
    if not timeline:
        raise ValueError("ElevenLabs diarization acik olmasina ragmen speaker bilgisi uretmedi")
    return timeline


def konusmaci_seslerini_ata(
    segments,
    audio_path: str,
    run_dir: str,
    speaker_timeline: list[dict] | None = None,
    speaker_timeline_source: str = "local_3d_speaker",
    manual_voice_map: dict[str, str] | None = None,
) -> str:
    """Konusmacilari ayirir, her konusmacinin cinsiyetini tahmin eder ve havuzdan ses atar.

    Elle verilen harita (konusmaci -> ses) her zaman onceliklidir.
    """
    if not audio_path:
        raise ValueError("Supertonic speaker gender icin audio_path bos")
    started = perf_counter()
    work_dir = Path(run_dir) / "supertonic_tts" / "konusmaci_secimi"
    work_dir.mkdir(parents=True, exist_ok=True)
    speaker_audio = prepare_speaker_input_audio(audio_path, work_dir)
    local_3d_speaker_used = speaker_timeline is None
    if local_3d_speaker_used:
        speaker_timeline = run_3d_speaker_diarization(speaker_audio, work_dir)
    else:
        speaker_timeline = [dict(item) for item in speaker_timeline]
    if not speaker_timeline:
        raise ValueError("Supertonic speaker timeline bos")
    write_json(work_dir / "speaker_timeline.json", speaker_timeline)
    split_report = split_segments_by_speaker_timeline(segments, speaker_timeline)
    write_json(work_dir / "speaker_segment_split_report.json", split_report)
    assign_speakers_to_segments(segments, speaker_timeline)
    progress_path = work_dir / "3d_speaker_progress.jsonl"
    timing_path = progress_path if local_3d_speaker_used else None
    worker_metadata = {}
    speaker_gender_map = build_speaker_gender_map(segments, str(speaker_audio), timing_path, worker_metadata)
    write_json(work_dir / "speaker_gender_map.json", speaker_gender_map)
    speaker_voice_map = assign_voice_ids_to_speakers(speaker_gender_map, manual_voice_map or {})
    write_json(work_dir / "speaker_voice_map.json", speaker_voice_map)
    segment_plan = apply_voice_map_to_segments(segments, speaker_voice_map)
    write_json(work_dir / "segment_voice_plan.json", segment_plan)
    metadata = {
        "audio_path": audio_path,
        "speaker_input_audio": str(speaker_audio),
        "audio_source": "audio_for_asr",
        "speaker_timeline_source": speaker_timeline_source,
        "model_id": MODEL_ID,
        "elapsed_seconds": round(perf_counter() - started, 3),
        "min_gender_segment_seconds": MIN_GENDER_SEGMENT_SECONDS,
        "max_gender_audio_seconds": MAX_GENDER_AUDIO_SECONDS,
        "gender_sample_rate": GENDER_SAMPLE_RATE,
        "speaker_split_before_count": split_report["before_count"],
        "speaker_split_after_count": split_report["after_count"],
        "speaker_split_added_count": split_report["added_count"],
        "speaker_split_group_min_seconds": MIN_SPEAKER_SPLIT_GROUP_SECONDS,
        "timings_seconds": collect_progress_timings(progress_path) if local_3d_speaker_used else {},
        "worker_process_exit": bool(worker_metadata.get("process_exit_observed", False)),
        "worker_elapsed_seconds": worker_metadata.get("subprocess_elapsed_seconds"),
        "worker_pid": worker_metadata.get("worker_pid"),
        "worker_timings_seconds": worker_metadata.get("timings_seconds", {}),
    }
    write_json(work_dir / "metadata.json", metadata)
    reporting_started = perf_counter()
    if local_3d_speaker_used:
        append_progress(progress_path, "final_reporting_started")
    report = write_debug_reports(work_dir, speaker_timeline, speaker_gender_map, speaker_voice_map, segment_plan, metadata)
    summary_path = write_summary(work_dir, speaker_timeline, speaker_gender_map, speaker_voice_map, segment_plan, report)
    if local_3d_speaker_used:
        append_progress(
            progress_path,
            "final_reporting_completed",
            elapsed_seconds=round(perf_counter() - reporting_started, 6),
        )
        metadata["timings_seconds"] = collect_progress_timings(progress_path)
    write_json(work_dir / "metadata.json", metadata)
    report["metadata"] = metadata
    write_json(work_dir / "karar_raporu.json", report)
    logger.info("[KONUSMACI] Karar ozeti: %s", summary_path)
    return summary_path


def split_segments_by_speaker_timeline(segments, speaker_timeline: list[dict]) -> dict:
    before_count = len(segments)
    new_segments = []
    split_items = []
    for seg in segments:
        parts = build_speaker_split_parts(seg, speaker_timeline)
        if len(parts) <= 1:
            new_segments.append(seg)
            continue
        parent_index = int(getattr(seg, "index", len(new_segments) + 1) or len(new_segments) + 1)
        for part_index, part in enumerate(parts, start=1):
            new_seg = clone_segment_part(seg, part, len(new_segments) + 1, parent_index, part_index, len(parts))
            new_segments.append(new_seg)
        split_items.append(
            {
                "parent_segment_index": parent_index,
                "part_count": len(parts),
                "parts": [
                    {
                        "part_index": index + 1,
                        "start": round(float(part["start"]), 3),
                        "end": round(float(part["end"]), 3),
                        "speaker": part["speaker"],
                        "word_count": len(part["words"]),
                        "text": part["text"],
                    }
                    for index, part in enumerate(parts)
                ],
            }
        )
    if len(new_segments) != len(segments):
        for index, seg in enumerate(new_segments, start=1):
            setattr(seg, "index", index)
        segments[:] = new_segments
    return {
        "before_count": before_count,
        "after_count": len(segments),
        "added_count": len(segments) - before_count,
        "split_segment_count": len(split_items),
        "splits": split_items,
    }


def build_speaker_split_parts(seg, speaker_timeline: list[dict]) -> list[dict]:
    words = usable_segment_words(getattr(seg, "words", None))
    if not words:
        return []
    groups = []
    current_words = []
    current_speaker = ""
    for word in words:
        speaker = speaker_for_word_range(float(word["start"]), float(word["end"]), speaker_timeline, current_speaker)
        if not speaker:
            speaker = current_speaker or speaker_for_range(float(getattr(seg, "start", 0.0) or 0.0), float(getattr(seg, "end", 0.0) or 0.0), speaker_timeline)
        word_item = dict(word)
        word_item["speaker"] = speaker
        if current_words and speaker and current_speaker and speaker != current_speaker:
            groups.append({"speaker": current_speaker, "words": current_words})
            current_words = [word_item]
            current_speaker = speaker
        else:
            current_words.append(word_item)
            if speaker:
                current_speaker = speaker
    if current_words:
        groups.append({"speaker": current_speaker, "words": current_words})
    groups = merge_short_speaker_groups(groups)
    unique_speakers = {group["speaker"] for group in groups if group["speaker"]}
    if len(unique_speakers) <= 1:
        return []
    return [part_from_group(group) for group in groups if group.get("words")]


def speaker_for_word_range(start: float, end: float, speaker_timeline: list[dict], previous_speaker: str = "") -> str:
    best_speaker = ""
    best_overlap = 0.0
    previous_speaker = str(previous_speaker or "")
    for item in speaker_timeline:
        speaker = str(item.get("speaker") or "")
        overlap = max(0.0, min(end, float(item["end"])) - max(start, float(item["start"])))
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = speaker
        elif overlap == best_overlap and overlap > 0.0 and speaker == previous_speaker:
            best_speaker = speaker
    return best_speaker


def usable_segment_words(words) -> list[dict]:
    if not isinstance(words, list):
        return []
    usable = []
    for word in words:
        if not isinstance(word, dict):
            continue
        text = str(word.get("word", "") or "").strip()
        if not text or "start" not in word or "end" not in word:
            continue
        usable.append(dict(word))
    return usable


def merge_short_speaker_groups(groups: list[dict]) -> list[dict]:
    merged = [group for group in groups if group.get("words")]
    changed = True
    while changed and len(merged) > 1:
        changed = False
        for index, group in enumerate(list(merged)):
            duration = group_duration(group)
            if duration >= MIN_SPEAKER_SPLIT_GROUP_SECONDS:
                continue
            target_index = short_group_merge_target(index, merged)
            if target_index is None:
                continue
            merged[target_index]["words"] = sorted(
                merged[target_index]["words"] + group["words"],
                key=lambda item: (float(item["start"]), float(item["end"])),
            )
            del merged[index]
            changed = True
            break
    return merged


def short_group_merge_target(index: int, groups: list[dict]) -> int | None:
    previous_index = index - 1 if index > 0 else None
    next_index = index + 1 if index + 1 < len(groups) else None
    if previous_index is None:
        return next_index
    if next_index is None:
        return previous_index
    previous_duration = group_duration(groups[previous_index])
    next_duration = group_duration(groups[next_index])
    if next_duration > previous_duration:
        return next_index
    return previous_index


def group_duration(group: dict) -> float:
    words = group.get("words") or []
    if not words:
        return 0.0
    return max(float(words[-1]["end"]) - float(words[0]["start"]), 0.0)


def part_from_group(group: dict) -> dict:
    words = group["words"]
    return {
        "start": float(words[0]["start"]),
        "end": float(words[-1]["end"]),
        "speaker": str(group.get("speaker") or ""),
        "text": " ".join(str(word.get("word", "") or "").strip() for word in words).strip(),
        "words": list(words),
    }


def clone_segment_part(source_seg, part: dict, index: int, parent_index: int, part_index: int, part_count: int):
    cls = type(source_seg)
    kwargs = {
        "index": index,
        "start": float(part["start"]),
        "end": float(part["end"]),
        "text": part["text"],
        "gender": str(getattr(source_seg, "gender", "") or ""),
        "speaker": part["speaker"],
        "pitch": str(getattr(source_seg, "pitch", "+0Hz") or "+0Hz"),
        "protected_terms": getattr(source_seg, "protected_terms", None),
        "words": list(part["words"]),
    }
    try:
        new_seg = cls(**kwargs)
    except TypeError:
        new_seg = cls(
            index=kwargs["index"],
            start=kwargs["start"],
            end=kwargs["end"],
            text=kwargs["text"],
        )
        for key, value in kwargs.items():
            setattr(new_seg, key, value)
    setattr(new_seg, "parent_segment_index", parent_index)
    setattr(new_seg, "speaker_split_part_index", part_index)
    setattr(new_seg, "speaker_split_part_count", part_count)
    return new_seg


def assign_speakers_to_segments(segments, speaker_timeline: list[dict]) -> None:
    for seg in segments:
        start = float(getattr(seg, "start", 0.0) or 0.0)
        end = float(getattr(seg, "end", 0.0) or 0.0)
        speaker = speaker_for_range(start, end, speaker_timeline)
        if speaker:
            setattr(seg, "speaker", speaker)


def speaker_for_range(start: float, end: float, speaker_timeline: list[dict]) -> str:
    best_speaker = ""
    best_overlap = 0.0
    for item in speaker_timeline:
        overlap = max(0.0, min(end, float(item["end"])) - max(start, float(item["start"])))
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = str(item["speaker"])
    return best_speaker


def build_speaker_gender_map(
    segments,
    audio_path: str,
    progress_path: Path | None = None,
    worker_metadata: dict | None = None,
) -> dict[str, dict]:
    records: dict[str, list[dict]] = {}
    worker_requests: dict[str, list[dict]] = {}
    for seg in segments:
        speaker = str(getattr(seg, "speaker", "") or "").strip()
        if not speaker:
            continue
        start = float(getattr(seg, "start", 0.0) or 0.0)
        end = float(getattr(seg, "end", 0.0) or 0.0)
        duration = max(end - start, 0.0)
        records.setdefault(speaker, [])
        if duration < MIN_GENDER_SEGMENT_SECONDS:
            records[speaker].append({"start": start, "end": end, "decision_source": "skipped_short"})
            continue
        worker_requests.setdefault(speaker, []).append(
            {"start": start, "end": end, "segment_index": int(getattr(seg, "index", -1))}
        )
        records[speaker].append(
            {
                "segment_index": int(getattr(seg, "index", -1)),
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(duration, 3),
                "decision_source": "included_for_speaker_model",
            }
        )
    worker_predictions: dict[str, dict] = {}
    worker_error = None
    if worker_requests:
        requests = [
            {"request_id": speaker, "segments": items}
            for speaker, items in sorted(worker_requests.items())
        ]
        try:
            worker_result = run_gender_worker(
                audio_path,
                requests,
                "speaker",
            )
            if worker_metadata is not None:
                worker_metadata.update(
                    {
                        "process_exit_observed": worker_result.get("process_exit_observed", False),
                        "subprocess_elapsed_seconds": worker_result.get("subprocess_elapsed_seconds"),
                        "worker_pid": worker_result.get("worker_pid"),
                        "timings_seconds": worker_result.get("timings_seconds", {}),
                    }
                )
            worker_predictions = {
                str(item.get("request_id")): item
                for item in worker_result.get("predictions", [])
            }
        except Exception as error:
            worker_error = str(error)
            logger.warning("[KONUSMACI] worker hata: %s", error)
    result = {}
    for speaker in sorted(records):
        prediction = worker_predictions.get(speaker)
        if not worker_requests.get(speaker):
            gender = "unknown"
            confidence = 0.0
            decision_source = "fallback_no_gender_vote"
        else:
            gender = str((prediction or {}).get("gender") or "unknown")
            confidence = float((prediction or {}).get("confidence") or 0.0)
            if worker_error:
                gender = "unknown"
                decision_source = "speaker_model_error"
                records[speaker].append(
                    {"gender": "unknown", "decision_source": "speaker_model_error", "error": worker_error}
                )
            elif prediction and prediction.get("error"):
                gender = "unknown"
                decision_source = "speaker_model_error"
                records[speaker].append(
                    {
                        "gender": "unknown",
                        "decision_source": "speaker_model_error",
                        "error": str(prediction["error"]),
                    }
                )
            else:
                if not prediction:
                    gender = "unknown"
                    decision_source = "speaker_model_error"
                    records[speaker].append(
                        {
                            "gender": "unknown",
                            "decision_source": "speaker_model_error",
                            "error": "gender worker result missing",
                        }
                    )
                else:
                    decision_source = "speaker_model"
                for segment_error in (prediction or {}).get("segment_errors", []):
                    segment_index = int(segment_error.get("segment_index", -1))
                    for record in records[speaker]:
                        if int(record.get("segment_index", -2)) == segment_index:
                            record["gender"] = "unknown"
                            record["decision_source"] = "gender_error"
                            record["error"] = str(segment_error.get("error") or "gender audio slice failed")
                            break
            if gender not in {"female", "male"}:
                gender = "unknown"
        result[speaker] = {
            "speaker": speaker,
            "gender": gender,
            "confidence": round(float(confidence), 6),
            "decision_source": decision_source,
            "segments": records[speaker],
        }
    return result


def apply_voice_map_to_segments(segments, speaker_voice_map: dict[str, dict]) -> list[dict]:
    segment_items = []
    fallback_voice_id = "F1"
    for seg in segments:
        speaker = str(getattr(seg, "speaker", "") or "").strip()
        voice_info = speaker_voice_map.get(speaker, {})
        voice_id = str(voice_info.get("voice_id") or "")
        gender = str(voice_info.get("gender") or "unknown")
        segment_items.append((seg, speaker, voice_id, gender))

    valid_positions = [idx for idx, item in enumerate(segment_items) if item[2]]
    plan = []
    for idx, item in enumerate(segment_items):
        seg, speaker, voice_id, gender = item
        decision_source = "speaker_voice_map"
        if not voice_id:
            nearest_idx = _nearest_index(idx, valid_positions)
            if nearest_idx is not None:
                voice_id = segment_items[nearest_idx][2]
                gender = segment_items[nearest_idx][3]
                decision_source = "nearest_segment_fallback"
            else:
                voice_id = fallback_voice_id
                decision_source = "default_fallback"
        setattr(seg, "gender", gender)
        setattr(seg, "supertonic_voice_id", voice_id)
        plan.append(
            {
                "segment_index": int(getattr(seg, "index", -1)),
                "start": round(float(getattr(seg, "start", 0.0) or 0.0), 3),
                "end": round(float(getattr(seg, "end", 0.0) or 0.0), 3),
                "speaker": speaker,
                "gender": gender,
                "supertonic_voice_id": voice_id,
                "decision_source": decision_source,
            }
        )
    return plan


def _nearest_index(index: int, candidates: list[int]) -> int | None:
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: (abs(candidate - index), candidate))
