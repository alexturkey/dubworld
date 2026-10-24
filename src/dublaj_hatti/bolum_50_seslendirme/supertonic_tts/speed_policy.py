from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType


SUPERTONIC_SPEED_POLICY = "fixed_voice_profile_v1"
DEFAULT_SUPERTONIC_VOICE_ID = "F1"
# Neden: hiz model ici sentez parametresi; her deger 5/5 Turkce okuma testiyle kabul edildi, degisirse kelime duser. bkz. docs/engineering/pinned-values.md#supertonic-voices
SUPERTONIC_VOICE_SPEEDS = MappingProxyType({
    "F1": 1.30,
    "F2": 1.15,
    "F3": 1.30,
    "F4": 1.00,
    "F5": 1.15,
    "M1": 1.15,
    "M2": 1.00,
    "M3": 1.00,
    "M4": 1.15,
    "M5": 1.25,
})


def get_supertonic_voice_speed(voice_id: str) -> float:
    selected_voice_id = str(voice_id or "").strip().upper()
    if selected_voice_id not in SUPERTONIC_VOICE_SPEEDS:
        raise RuntimeError(f"Gecersiz Supertonic ses profili: {voice_id}")
    return float(SUPERTONIC_VOICE_SPEEDS[selected_voice_id])


def validate_supertonic_voice_speed(voice_id: str, speed: float) -> float:
    expected_speed = get_supertonic_voice_speed(voice_id)
    actual_speed = float(speed)
    if abs(actual_speed - expected_speed) > 0.000001:
        raise RuntimeError(
            f"Supertonic profil hizi uyusmuyor: voice={str(voice_id).strip().upper()} "
            f"expected={expected_speed:.2f} actual={actual_speed:.6f}"
        )
    return expected_speed


def _resolve_segment_voice_id(segment, default_voice_id: str) -> str:
    segment_voice_id = str(getattr(segment, "supertonic_voice_id", "") or "").strip().upper()
    if segment_voice_id in SUPERTONIC_VOICE_SPEEDS:
        return segment_voice_id
    selected_default = str(default_voice_id or "").strip().upper()
    if selected_default in SUPERTONIC_VOICE_SPEEDS:
        return selected_default
    return DEFAULT_SUPERTONIC_VOICE_ID


def calculate_supertonic_voice_speed_plan(segments, default_voice_id: str = DEFAULT_SUPERTONIC_VOICE_ID) -> dict[int, dict]:
    plan = {}
    for segment in segments:
        segment_id = int(segment.index)
        voice_id = _resolve_segment_voice_id(segment, default_voice_id)
        plan[segment_id] = {
            "segment_id": segment_id,
            "voice_id": voice_id,
            "speed": get_supertonic_voice_speed(voice_id),
        }
    if len(plan) != len(segments):
        raise RuntimeError("Supertonic sabit profil hiz plani segmentleri birebir kapsamiyor")
    return plan


def apply_supertonic_voice_speed_plan(
    segments,
    run_dir: str,
    default_voice_id: str = DEFAULT_SUPERTONIC_VOICE_ID,
) -> dict[int, dict]:
    plan = calculate_supertonic_voice_speed_plan(segments, default_voice_id)
    for segment in segments:
        item = plan[int(segment.index)]
        setattr(segment, "supertonic_speed", float(item["speed"]))
        setattr(segment, "supertonic_speed_voice_id", item["voice_id"])
        setattr(segment, "supertonic_speed_policy", SUPERTONIC_SPEED_POLICY)
    output_path = Path(run_dir) / "supertonic_tts" / "voice_speed_plan.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({
            "policy": SUPERTONIC_SPEED_POLICY,
            "profile_speeds": dict(SUPERTONIC_VOICE_SPEEDS),
            "segment_count": len(plan),
            "segments": [plan[index] for index in sorted(plan)],
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return plan


def get_supertonic_segment_speed(segment, voice_id: str | None = None) -> float:
    selected_voice_id = str(
        voice_id
        or getattr(segment, "supertonic_speed_voice_id", "")
        or getattr(segment, "supertonic_voice_id", "")
        or ""
    ).strip().upper()
    if selected_voice_id not in SUPERTONIC_VOICE_SPEEDS:
        raise RuntimeError(f"Supertonic segment ses profili yok: segment={getattr(segment, 'index', '')}")
    value = getattr(segment, "supertonic_speed", None)
    if value is None:
        raise RuntimeError(f"Supertonic segment hiz plani yok: segment={getattr(segment, 'index', '')}")
    planned_voice_id = str(getattr(segment, "supertonic_speed_voice_id", "") or "").strip().upper()
    if planned_voice_id and planned_voice_id != selected_voice_id:
        raise RuntimeError(
            f"Supertonic segment hiz profili degisti: segment={getattr(segment, 'index', '')} "
            f"planned={planned_voice_id} selected={selected_voice_id}"
        )
    return validate_supertonic_voice_speed(selected_voice_id, float(value))
