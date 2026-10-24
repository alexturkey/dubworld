from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any


@dataclass
class SupertonicAtempoReportRecord:
    segment_id: int
    candidate_number: int
    pre_atempo_processed_duration: float
    target_duration: float
    requested_atempo_factor: float
    atempo_applied: bool
    required_atempo_factor: float | None = None
    factor_clamped: bool = False
    atempo_output_duration: float | None = None
    post_atempo_processed_duration: float | None = None
    post_atempo_video_speed: float | None = None
    pre_atempo_alignment: dict[str, Any] | None = None
    word_timing_scale: float | None = None
    skip_reason: str = ""
    candidate_key: Any = None


def _record_to_dict(record: Mapping[str, Any] | SupertonicAtempoReportRecord) -> dict[str, Any]:
    if is_dataclass(record) and not isinstance(record, type):
        return asdict(record)
    if isinstance(record, Mapping):
        return dict(record)
    raise TypeError("Supertonic atempo rapor kaydi mapping veya dataclass olmali")


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Supertonic atempo rapor degeri JSON uyumlu degil: {type(value).__name__}")


def write_supertonic_atempo_report(
    report_dir: str | Path,
    records: Sequence[Mapping[str, Any] | SupertonicAtempoReportRecord],
    summary: Mapping[str, Any] | None = None,
) -> str:
    report_directory = Path(report_dir)
    report_directory.mkdir(parents=True, exist_ok=True)
    record_payloads = [_record_to_dict(record) for record in records]
    summary_payload = {
        "record_count": len(record_payloads),
        "applied_segment_count": sum(bool(item.get("atempo_applied")) for item in record_payloads),
        "word_timing_rescaled_count": sum(bool(item.get("atempo_applied")) for item in record_payloads),
    }
    if summary is not None:
        summary_payload.update(dict(summary))
    report_payload = {
        "schema_version": "supertonic_atempo_v1",
        "summary": summary_payload,
        "records": record_payloads,
    }
    report_path = report_directory / "report.json"
    with report_path.open("w", encoding="utf-8", newline="\n") as report_file:
        json.dump(
            report_payload,
            report_file,
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        )
        report_file.write("\n")
    return str(report_path)
