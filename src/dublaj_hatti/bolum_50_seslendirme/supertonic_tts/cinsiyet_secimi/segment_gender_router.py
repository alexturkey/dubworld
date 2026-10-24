# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from datetime import datetime
from time import perf_counter

from .gender_worker import MODEL_ID, SAMPLE_RATE, run_gender_worker
from .report import write_gender_routing_report
from .voice_pair import SupertonicVoicePair


logger = logging.getLogger("dublaj_hatti")
MIN_SEGMENT_SECONDS = 0.30


def apply_supertonic_segment_gender_routing(segments, audio_path: str, voice_pair: SupertonicVoicePair, run_dir: str) -> str:
    if not audio_path:
        raise ValueError("Supertonic cinsiyet secimi icin audio_path bos")

    started_at = datetime.now()
    started_perf = perf_counter()
    records = []
    deferred_records = []
    reliable_records = []
    worker_requests = []
    worker_result = {}
    for seg in segments:
        start = float(getattr(seg, "start", 0.0) or 0.0)
        end = float(getattr(seg, "end", 0.0) or 0.0)
        duration = max(end - start, 0.0)
        record = {
            "segment_index": int(getattr(seg, "index", -1)),
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(duration, 3),
            "sample_rate": SAMPLE_RATE,
            "_segment": seg,
            "_start_raw": start,
            "_end_raw": end,
        }
        if duration < MIN_SEGMENT_SECONDS:
            gender = "unknown"
            voice_id = ""
            record["decision_source"] = "deferred"
            record["deferred_reason"] = "short_segment"
            deferred_records.append(record)
        else:
            worker_requests.append(
                {
                    "request_id": str(record["segment_index"]),
                    "start": start,
                    "end": end,
                }
            )
            record["decision_source"] = "pending_worker"
            record["gender"] = "unknown"
            record["voice_id"] = ""
        records.append(record)

    worker_error = None
    worker_predictions = {}
    if worker_requests:
        try:
            worker_result = run_gender_worker(
                audio_path,
                worker_requests,
                "segment",
            )
            worker_predictions = {
                str(item.get("request_id")): item
                for item in worker_result.get("predictions", [])
            }
        except Exception as error:
            worker_error = str(error)
            logger.warning("[SUPERTONIC_GENDER] worker hata: %s", error)

    for record in records:
        if record.get("decision_source") != "pending_worker":
            continue
        prediction = worker_predictions.get(str(record["segment_index"]))
        if worker_error:
            record["deferred_reason"] = "gender_error"
            record["error"] = worker_error
        elif not prediction or prediction.get("error"):
            record["deferred_reason"] = "gender_error"
            if prediction and prediction.get("error"):
                record["error"] = str(prediction["error"])
            else:
                record["error"] = "gender worker result missing"
        else:
            gender = str(prediction.get("gender") or "unknown")
            record["gender"] = gender
            record["voice_id"] = (
                voice_pair.male_voice_id if gender == "male" else voice_pair.female_voice_id
            )
            record["confidence"] = round(float(prediction.get("confidence") or 0.0), 6)
            record["decision_source"] = "model"
            _apply_record_to_segment(record)
            reliable_records.append(record)
            continue
        record["gender"] = "unknown"
        record["voice_id"] = ""
        record["decision_source"] = "deferred"
        deferred_records.append(record)

    for record in deferred_records:
        _resolve_deferred_record(record, reliable_records, voice_pair)
        _apply_record_to_segment(record)

    for record in records:
        record.pop("_segment", None)
        record.pop("_start_raw", None)
        record.pop("_end_raw", None)

    finished_at = datetime.now()
    metadata = {
        "started_at": started_at.isoformat(timespec="milliseconds"),
        "finished_at": finished_at.isoformat(timespec="milliseconds"),
        "elapsed_seconds": round(perf_counter() - started_perf, 3),
        "audio_path": audio_path,
        "audio_source": "audio_for_asr",
        "model_id": MODEL_ID,
        "sample_rate": SAMPLE_RATE,
        "min_segment_seconds": MIN_SEGMENT_SECONDS,
        "female_voice_id": voice_pair.female_voice_id,
        "male_voice_id": voice_pair.male_voice_id,
        "fallback_voice_id": voice_pair.fallback_voice_id,
        "worker_process_exit": bool(worker_result.get("process_exit_observed", False)),
        "worker_elapsed_seconds": worker_result.get("subprocess_elapsed_seconds"),
        "worker_pid": worker_result.get("worker_pid"),
        "worker_timings_seconds": worker_result.get("timings_seconds", {}),
    }
    report_path = write_gender_routing_report(run_dir, records, metadata=metadata)
    logger.info("[SUPERTONIC_GENDER] Segment cinsiyet yonlendirme raporu: %s", report_path)
    return report_path


def _apply_record_to_segment(record: dict) -> None:
    seg = record["_segment"]
    setattr(seg, "gender", record["gender"])
    setattr(seg, "supertonic_voice_id", record["voice_id"])


def _resolve_deferred_record(record: dict, reliable_records: list[dict], voice_pair: SupertonicVoicePair) -> None:
    nearest = _find_nearest_reliable_record(record, reliable_records)
    if nearest:
        record["gender"] = nearest["gender"]
        record["voice_id"] = nearest["voice_id"]
        record["decision_source"] = "nearest_reliable_neighbor"
        record["neighbor_segment_index"] = nearest["segment_index"]
        record["neighbor_distance_seconds"] = round(_record_distance_seconds(record, nearest), 3)
        record["inherited_from"] = nearest["decision_source"]
        return
    record["gender"] = "unknown"
    record["voice_id"] = voice_pair.fallback_voice_id
    record["decision_source"] = "fallback"
    record["fallback_reason"] = record.get("deferred_reason", "no_reliable_neighbor")


def _find_nearest_reliable_record(record: dict, reliable_records: list[dict]) -> dict | None:
    if not reliable_records:
        return None
    previous_records = [item for item in reliable_records if item["_end_raw"] <= record["_start_raw"]]
    next_records = [item for item in reliable_records if item["_start_raw"] >= record["_end_raw"]]
    candidates = []
    for item in previous_records:
        candidates.append((_record_distance_seconds(record, item), 0, item["segment_index"], item))
    for item in next_records:
        candidates.append((_record_distance_seconds(record, item), 1, item["segment_index"], item))
    if not candidates:
        candidates = [
            (_record_distance_seconds(record, item), 0, item["segment_index"], item)
            for item in reliable_records
        ]
    return sorted(candidates, key=lambda item: (item[0], item[1], item[2]))[0][3]


def _record_distance_seconds(record: dict, other: dict) -> float:
    if other["_end_raw"] <= record["_start_raw"]:
        return max(record["_start_raw"] - other["_end_raw"], 0.0)
    if other["_start_raw"] >= record["_end_raw"]:
        return max(other["_start_raw"] - record["_end_raw"], 0.0)
    return 0.0
