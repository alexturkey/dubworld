from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


subscription_endpoint = "https://api.elevenlabs.io/v1/user/subscription"
subscription_source = "https://elevenlabs.io/docs/api-reference/user/subscription/get"


class ElevenLabsAccountError(RuntimeError):
    def __init__(
        self,
        code: str,
        status_code: int | None = None,
        required_permission: str = "",
    ):
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.required_permission = required_permission


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary_path, path)


def _integer(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _decimal_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_safe_subscription_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    period_character_count = _integer(payload.get("character_count"))
    period_character_limit = _integer(payload.get("character_limit"))
    period_character_remaining = None
    if period_character_count is not None and period_character_limit is not None:
        period_character_remaining = max(period_character_limit - period_character_count, 0)
    current_overage = payload.get("current_overage")
    safe_overage = None
    if isinstance(current_overage, dict):
        safe_overage = {
            "amount": _decimal_number(current_overage.get("amount")),
            "currency": str(current_overage.get("currency") or "").strip().lower() or None,
        }
    return {
        "schema_version": 3,
        "provider": "ElevenLabs",
        "status": "available",
        "fetched_at_utc": _utc_now(),
        "source_endpoint": subscription_endpoint,
        "source_documentation": subscription_source,
        "tier": str(payload.get("tier") or "").strip() or None,
        "subscription_status": str(payload.get("status") or "").strip() or None,
        "currency": str(payload.get("currency") or "").strip().lower() or None,
        "billing_period": str(payload.get("billing_period") or "").strip() or None,
        "period_character_count": period_character_count,
        "period_character_limit": period_character_limit,
        "period_character_remaining": period_character_remaining,
        "period_counter_semantics": "subscription_period_allocation_not_top_up_balance",
        "top_up_balance_usd": None,
        "top_up_balance_status": "not_exposed_by_public_subscription_api",
        "max_credit_limit_extension": payload.get("max_credit_limit_extension"),
        "next_credit_reset_unix": _integer(payload.get("next_character_count_reset_unix")),
        "current_overage": safe_overage,
    }


def _error_from_response(response: requests.Response) -> ElevenLabsAccountError:
    error_status = ""
    error_message = ""
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, dict):
        error_status = str(detail.get("status") or "").strip()
        error_message = str(detail.get("message") or "").strip()
    elif isinstance(detail, str):
        error_message = detail.strip()
    required_permission = ""
    permission_match = re.search(r"permission\s+([a-z0-9_]+)", error_message, flags=re.IGNORECASE)
    if permission_match:
        required_permission = permission_match.group(1).lower()
    if error_status == "missing_permissions":
        return ElevenLabsAccountError("missing_permissions", response.status_code, required_permission)
    if response.status_code == 401:
        return ElevenLabsAccountError("authentication_failed", response.status_code)
    if response.status_code == 403:
        return ElevenLabsAccountError("permission_denied", response.status_code, required_permission)
    if response.status_code == 429:
        return ElevenLabsAccountError("rate_limited", response.status_code)
    return ElevenLabsAccountError("provider_error", response.status_code)


def fetch_subscription_snapshot(api_key: str, timeout_seconds: float = 15.0) -> dict[str, Any]:
    if not api_key.strip():
        raise ElevenLabsAccountError("api_key_missing")
    try:
        response = requests.get(
            subscription_endpoint,
            headers={"xi-api-key": api_key},
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        raise ElevenLabsAccountError("connection_failed") from exc
    if response.status_code != 200:
        raise _error_from_response(response)
    try:
        payload = response.json()
    except ValueError as exc:
        raise ElevenLabsAccountError("invalid_json", response.status_code) from exc
    if not isinstance(payload, dict):
        raise ElevenLabsAccountError("invalid_payload", response.status_code)
    return build_safe_subscription_snapshot(payload)


def refresh_subscription_snapshot(
    output_dir: Path,
    api_key: str,
    timeout_seconds: float = 15.0,
) -> tuple[Path, dict[str, Any]]:
    snapshot_path = output_dir / "account_snapshot.json"
    try:
        snapshot = fetch_subscription_snapshot(api_key, timeout_seconds)
    except ElevenLabsAccountError as exc:
        snapshot = {
            "schema_version": 3,
            "provider": "ElevenLabs",
            "status": "unavailable",
            "fetched_at_utc": _utc_now(),
            "source_endpoint": subscription_endpoint,
            "source_documentation": subscription_source,
            "error_code": exc.code,
            "status_code": exc.status_code,
            "required_permission": exc.required_permission or None,
        }
    _atomic_write_json(snapshot_path, snapshot)
    return snapshot_path, snapshot
