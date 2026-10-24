# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def write_gender_routing_report(run_dir: str, records: Iterable[dict], metadata: dict | None = None) -> str:
    record_list = list(records)
    metadata = dict(metadata or {})
    report_dir = Path(run_dir) / "supertonic_tts" / "cinsiyet_secimi"
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "karar_raporu.json"
    summary = _build_summary(record_list)
    payload = {
        "mode": "supertonic_segment_gender_routing",
        "metadata": metadata,
        "summary": summary,
        "segments": record_list,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    _write_markdown_summary(report_dir / "karar_ozeti.md", metadata, summary, record_list)
    return str(path)


def _build_summary(records: list[dict]) -> dict:
    summary = {
        "segment_count": len(records),
        "model_decision_count": 0,
        "neighbor_inherited_count": 0,
        "fallback_count": 0,
        "female_count": 0,
        "male_count": 0,
        "unknown_count": 0,
    }
    for record in records:
        source = str(record.get("decision_source") or "")
        gender = str(record.get("gender") or "unknown")
        if source == "model":
            summary["model_decision_count"] += 1
        elif source == "nearest_reliable_neighbor":
            summary["neighbor_inherited_count"] += 1
        elif source == "fallback":
            summary["fallback_count"] += 1
        if gender == "female":
            summary["female_count"] += 1
        elif gender == "male":
            summary["male_count"] += 1
        else:
            summary["unknown_count"] += 1
    return summary


def _write_markdown_summary(path: Path, metadata: dict, summary: dict, records: list[dict]) -> None:
    lines = [
        "# Supertonic Cinsiyet Secimi Karar Ozeti",
        "",
        "## Islem Bilgisi",
        "",
        f"- Baslangic: {metadata.get('started_at', '')}",
        f"- Bitis: {metadata.get('finished_at', '')}",
        f"- Sure: {metadata.get('elapsed_seconds', '')} saniye",
        f"- Kaynak ses: `{metadata.get('audio_path', '')}`",
        f"- Kaynak tipi: {metadata.get('audio_source', '')}",
        f"- Model: {metadata.get('model_id', '')}",
        f"- Kisa segment esigi: {metadata.get('min_segment_seconds', '')} saniye",
        f"- Kadin sesi: {metadata.get('female_voice_id', '')}",
        f"- Erkek sesi: {metadata.get('male_voice_id', '')}",
        f"- Fallback sesi: {metadata.get('fallback_voice_id', '')}",
        "",
        "## Ozet",
        "",
        f"- Segment sayisi: {summary['segment_count']}",
        f"- Model karari: {summary['model_decision_count']}",
        f"- Komsudan devralan: {summary['neighbor_inherited_count']}",
        f"- Fallback: {summary['fallback_count']}",
        f"- Female: {summary['female_count']}",
        f"- Male: {summary['male_count']}",
        f"- Unknown: {summary['unknown_count']}",
        "",
        "## Segment Kararlari",
        "",
        "| Segment | Sure | Kaynak | Gender | Voice | Detay |",
        "|---:|---:|---|---|---|---|",
    ]
    for record in records:
        detail = ""
        if record.get("decision_source") == "model":
            detail = f"confidence={record.get('confidence', '')}"
        elif record.get("decision_source") == "nearest_reliable_neighbor":
            detail = (
                f"neighbor={record.get('neighbor_segment_index', '')}, "
                f"distance={record.get('neighbor_distance_seconds', '')}s"
            )
        elif record.get("fallback_reason"):
            detail = str(record.get("fallback_reason"))
        lines.append(
            f"| {record.get('segment_index', '')} "
            f"| {record.get('duration', '')} "
            f"| {record.get('decision_source', '')} "
            f"| {record.get('gender', '')} "
            f"| {record.get('voice_id', '')} "
            f"| {detail} |"
        )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
