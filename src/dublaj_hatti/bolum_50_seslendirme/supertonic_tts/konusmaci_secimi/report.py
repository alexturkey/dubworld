# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, data) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def build_speaker_totals(speaker_timeline: list[dict]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for item in speaker_timeline:
        speaker = str(item.get("speaker") or "")
        if not speaker:
            continue
        duration = max(float(item.get("end") or 0.0) - float(item.get("start") or 0.0), 0.0)
        totals[speaker] = round(totals.get(speaker, 0.0) + duration, 3)
    return dict(sorted(totals.items()))


def build_speaker_rename_map(speaker_timeline: list[dict]) -> dict[str, str]:
    rename_map: dict[str, str] = {}
    for item in speaker_timeline:
        raw_speaker = str(item.get("raw_speaker") or "")
        speaker = str(item.get("speaker") or "")
        if raw_speaker and speaker and raw_speaker not in rename_map:
            rename_map[raw_speaker] = speaker
    return rename_map


def build_segment_assignment_stats(segment_plan: list[dict]) -> dict:
    decision_counts: dict[str, int] = {}
    voice_counts: dict[str, int] = {}
    gender_counts: dict[str, int] = {}
    speaker_counts: dict[str, int] = {}
    unassigned_segments = 0
    for item in segment_plan:
        decision_source = str(item.get("decision_source") or "unknown")
        voice_id = str(item.get("supertonic_voice_id") or "unknown")
        gender = str(item.get("gender") or "unknown")
        speaker = str(item.get("speaker") or "")
        decision_counts[decision_source] = decision_counts.get(decision_source, 0) + 1
        voice_counts[voice_id] = voice_counts.get(voice_id, 0) + 1
        gender_counts[gender] = gender_counts.get(gender, 0) + 1
        if speaker:
            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
        else:
            unassigned_segments += 1
    return {
        "total_segments": len(segment_plan),
        "assigned_segments": len(segment_plan) - unassigned_segments,
        "unassigned_segments": unassigned_segments,
        "decision_source_counts": dict(sorted(decision_counts.items())),
        "speaker_counts": dict(sorted(speaker_counts.items())),
        "gender_counts": dict(sorted(gender_counts.items())),
        "voice_counts": dict(sorted(voice_counts.items())),
    }


def write_speaker_timeline_text(path: Path, speaker_timeline: list[dict]) -> str:
    lines = []
    for item in speaker_timeline:
        start = float(item.get("start") or 0.0)
        end = float(item.get("end") or 0.0)
        speaker = str(item.get("speaker") or "")
        raw_speaker = str(item.get("raw_speaker") or "")
        raw_text = f" raw={raw_speaker}" if raw_speaker else ""
        lines.append(f"{format_time(start)} - {format_time(end)}  {speaker}{raw_text}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return str(path)


def write_debug_reports(
    work_dir: Path,
    speaker_timeline: list[dict],
    speaker_gender_map: dict,
    speaker_voice_map: dict,
    segment_plan: list[dict],
    metadata: dict,
) -> dict:
    speaker_totals = build_speaker_totals(speaker_timeline)
    speaker_rename_map = build_speaker_rename_map(speaker_timeline)
    assignment_stats = build_segment_assignment_stats(segment_plan)
    report = {
        "metadata": metadata,
        "speaker_count": len(speaker_voice_map),
        "speaker_timeline_segment_count": len(speaker_timeline),
        "dub_segment_count": len(segment_plan),
        "speaker_totals": speaker_totals,
        "speaker_rename_map": speaker_rename_map,
        "speaker_gender_map": speaker_gender_map,
        "speaker_voice_map": speaker_voice_map,
        "segment_assignment_stats": assignment_stats,
    }
    write_json(work_dir / "speaker_totals.json", speaker_totals)
    write_json(work_dir / "speaker_rename_map.json", speaker_rename_map)
    write_json(work_dir / "segment_assignment_stats.json", assignment_stats)
    write_json(work_dir / "karar_raporu.json", report)
    write_speaker_timeline_text(work_dir / "speaker_timeline.txt", speaker_timeline)
    return report


def format_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    minutes = millis // 60000
    rest = millis % 60000
    secs = rest // 1000
    ms = rest % 1000
    return f"{minutes:02d}:{secs:02d}.{ms:03d}"


def write_summary(work_dir: Path, speaker_timeline: list[dict], speaker_gender_map: dict, speaker_voice_map: dict, segment_plan: list[dict], report: dict | None = None) -> str:
    speaker_totals = (report or {}).get("speaker_totals") or build_speaker_totals(speaker_timeline)
    assignment_stats = (report or {}).get("segment_assignment_stats") or build_segment_assignment_stats(segment_plan)
    lines = [
        "# Supertonic Konusmaci Cinsiyet Secimi",
        "",
        f"Bulunan speaker: {len(speaker_voice_map)}",
        f"Speaker timeline segmenti: {len(speaker_timeline)}",
        f"Dublaj segmenti: {len(segment_plan)}",
        f"Atanan dublaj segmenti: {assignment_stats.get('assigned_segments', 0)}",
        f"Atanamayan dublaj segmenti: {assignment_stats.get('unassigned_segments', 0)}",
        "",
        "Speaker sureleri:",
    ]
    for speaker, duration in sorted(speaker_totals.items()):
        lines.append(f"- {speaker}: {float(duration):.3f} sn")
    lines.extend([
        "",
        "Speaker ses haritasi:",
    ])
    for speaker, item in sorted(speaker_voice_map.items()):
        lines.append(
            f"- {speaker}: gender={item.get('gender', 'unknown')} voice={item.get('voice_id', '')} source={item.get('decision_source', '')}"
        )
    lines.extend([
        "",
        "Segment karar kaynaklari:",
    ])
    for source, count in sorted(assignment_stats.get("decision_source_counts", {}).items()):
        lines.append(f"- {source}: {count}")
    path = work_dir / "karar_ozeti.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)
