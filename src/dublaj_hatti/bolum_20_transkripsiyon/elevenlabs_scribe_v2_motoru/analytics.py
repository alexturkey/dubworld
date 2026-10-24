from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import requests


requests_endpoint = "https://api.elevenlabs.io/v1/workspace/analytics/requests"
usage_endpoint = "https://api.elevenlabs.io/v1/workspace/analytics/query/usage-by-product-over-time"
requests_source = "https://elevenlabs.io/docs/api-reference/analytics/workspace/requests"
usage_source = "https://elevenlabs.io/docs/api-reference/analytics/workspace/usage"


def _rows_as_dicts(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    columns = payload.get("columns")
    rows = payload.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        return []
    names = [str(column) for column in columns]
    return [dict(zip(names, row)) for row in rows if isinstance(row, list)]


def _timestamp_milliseconds(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _post_json(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    response = requests.post(
        url,
        headers={"xi-api-key": api_key, "content-type": "application/json"},
        json=payload,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict):
        raise ValueError("invalid_payload")
    return result


def _find_request_event(
    api_key: str,
    trace_id: str,
    request_started_ms: int,
    request_completed_ms: int,
    timeout_seconds: float,
) -> dict[str, Any] | None:
    payload = _post_json(
        requests_endpoint,
        api_key,
        {
            "start_time": max(request_started_ms - 30_000, 1_577_836_800_000),
            "end_time": request_completed_ms + 30_000,
            "limit": 100,
            "search": "/v1/speech-to-text",
        },
        timeout_seconds,
    )
    matches = [
        row
        for row in _rows_as_dicts(payload)
        if str(row.get("trace_id") or "") == trace_id
        and str(row.get("path_pattern") or row.get("path") or "") == "/v1/speech-to-text"
        and int(row.get("response_code") or 0) == 200
    ]
    return matches[0] if len(matches) == 1 else None


def _find_usage_row(
    api_key: str,
    event_timestamp_ms: int,
    request_completed_ms: int,
    expected_duration_seconds: float,
    timeout_seconds: float,
) -> dict[str, Any] | None:
    payload = _post_json(
        usage_endpoint,
        api_key,
        {
            "start_time": event_timestamp_ms - 5_000,
            "end_time": max(request_completed_ms + 5_000, event_timestamp_ms + 20_000),
            "interval_seconds": 1,
            "group_by": ["product_type"],
            "time_zone": "UTC",
        },
        timeout_seconds,
    )
    matches = []
    for row in _rows_as_dicts(payload):
        minutes = _number(row.get("total_minutes"))
        usage_count = _number(row.get("usage_count"))
        if str(row.get("product_type") or "").upper() != "STT":
            continue
        if minutes is None or usage_count != 1.0:
            continue
        if abs(minutes * 60.0 - expected_duration_seconds) <= 0.05:
            matches.append(row)
    return matches[0] if len(matches) == 1 else None


def reconcile_transcription_usage(
    api_key: str,
    trace_id: str,
    request_started_ms: int | None,
    request_completed_ms: int | None,
    expected_duration_seconds: float,
    timeout_seconds: float,
    retry_count: int,
    retry_delay_seconds: float,
) -> dict[str, Any]:
    base = {
        "status": "unavailable",
        "evidence": "provider_workspace_analytics",
        "requests_endpoint": requests_endpoint,
        "usage_endpoint": usage_endpoint,
        "requests_source": requests_source,
        "usage_source": usage_source,
    }
    if not api_key or not trace_id or request_started_ms is None or request_completed_ms is None:
        return {**base, "error_code": "request_identity_missing"}
    last_error = "analytics_record_not_ready"
    for attempt in range(1, max(int(retry_count), 1) + 1):
        try:
            event = _find_request_event(
                api_key,
                trace_id,
                request_started_ms,
                request_completed_ms,
                timeout_seconds,
            )
            event_timestamp_ms = _timestamp_milliseconds(event.get("timestamp")) if event else None
            usage = (
                _find_usage_row(
                    api_key,
                    event_timestamp_ms,
                    request_completed_ms,
                    expected_duration_seconds,
                    timeout_seconds,
                )
                if event_timestamp_ms is not None
                else None
            )
            if event is not None and usage is not None:
                return {
                    **base,
                    "status": "provider_verified",
                    "attempt_count": attempt,
                    "trace_id": trace_id,
                    "event_timestamp": event.get("timestamp"),
                    "event_id": event.get("event_id"),
                    "latency_seconds": _number(event.get("latency_seconds")),
                    "credits_used": _number(usage.get("total_usage")),
                    "billed_minutes": _number(usage.get("total_minutes")),
                    "cost_usd": _number(usage.get("total_cost")),
                    "usage_count": _number(usage.get("usage_count")),
                }
        except (requests.RequestException, ValueError, TypeError):
            last_error = "analytics_request_failed"
        if attempt < max(int(retry_count), 1):
            time.sleep(max(float(retry_delay_seconds), 0.0))
    return {**base, "error_code": last_error, "attempt_count": max(int(retry_count), 1)}
