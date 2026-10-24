from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# Neden: sesin model ici hizina dokunmadan sure uydurur; bandi degistirmek gercek sure ve perde testini ister. bkz. docs/engineering/pinned-values.md#duration-matching
SUPERTONIC_ATEMPO_MIN_FACTOR = 0.90
SUPERTONIC_ATEMPO_MAX_FACTOR = 1.25


@dataclass(frozen=True)
class SupertonicAtempoPlan:
    segment_id: int
    candidate_number: int
    candidate_key: Any
    pre_atempo_processed_duration: float
    target_duration: float
    requested_atempo_factor: float


@dataclass(frozen=True)
class _EligibleCandidate:
    plan: SupertonicAtempoPlan
    distance_from_one: float


def _required_value(candidate: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in candidate:
            return candidate[name]
    raise ValueError(f"Supertonic atempo aday alani eksik: {names[0]}")


def _positive_finite_float(value: Any, field_name: str) -> float:
    numeric_value = float(value)
    if not math.isfinite(numeric_value) or numeric_value <= 0.0:
        raise ValueError(f"Supertonic atempo {field_name} pozitif ve sonlu olmali")
    return numeric_value


def _eligible_candidate(candidate: Mapping[str, Any]) -> _EligibleCandidate | None:
    segment_id = int(_required_value(candidate, ("segment_id", "segment_index")))
    candidate_number = int(_required_value(candidate, ("candidate_number",)))
    processed_duration = _positive_finite_float(
        _required_value(candidate, ("processed_duration", "pre_atempo_processed_duration")),
        "processed_duration",
    )
    target_duration = _positive_finite_float(
        _required_value(candidate, ("target_duration",)),
        "target_duration",
    )
    raw_factor = processed_duration / target_duration
    if raw_factor < SUPERTONIC_ATEMPO_MIN_FACTOR or raw_factor > SUPERTONIC_ATEMPO_MAX_FACTOR:
        return None
    requested_factor = round(raw_factor, 6)
    candidate_key = candidate.get("candidate_key", candidate.get("key"))
    plan = SupertonicAtempoPlan(
        segment_id=segment_id,
        candidate_number=candidate_number,
        candidate_key=candidate_key,
        pre_atempo_processed_duration=processed_duration,
        target_duration=target_duration,
        requested_atempo_factor=requested_factor,
    )
    return _EligibleCandidate(
        plan=plan,
        distance_from_one=abs(requested_factor - 1.0),
    )


def plan_supertonic_atempo_candidates(
    candidate_inputs: Sequence[Mapping[str, Any]],
) -> list[SupertonicAtempoPlan]:
    eligible_by_segment: dict[int, list[_EligibleCandidate]] = {}
    for candidate in candidate_inputs:
        if not isinstance(candidate, Mapping):
            raise TypeError("Supertonic atempo aday girdisi mapping olmali")
        eligible = _eligible_candidate(candidate)
        if eligible is None:
            continue
        eligible_by_segment.setdefault(eligible.plan.segment_id, []).append(eligible)

    plans: list[SupertonicAtempoPlan] = []
    for segment_id in sorted(eligible_by_segment):
        selected = min(
            eligible_by_segment[segment_id],
            key=lambda item: (item.distance_from_one, item.plan.candidate_number),
        ).plan
        if selected.requested_atempo_factor == 1.0:
            continue
        plans.append(selected)
    return plans
