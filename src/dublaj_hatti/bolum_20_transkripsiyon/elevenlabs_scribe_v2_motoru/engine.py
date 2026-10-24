from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

from .account import refresh_subscription_snapshot
from .analytics import reconcile_transcription_usage
from .config import (
    account_status_timeout_seconds,
    analytics_retry_count,
    analytics_retry_delay_seconds,
    analytics_timeout_seconds,
    endpoint,
    exchange_rate_timeout_seconds,
    get_api_key,
    limits_source,
    maximum_audio_seconds,
    maximum_file_bytes,
    minimum_upload_bytes_per_second,
    model_id,
    price_usd_per_audio_hour,
    pricing_source,
    request_timeout_seconds,
    upload_timeout_grace_seconds,
)
from .cost import ExchangeRateError, calculate_cost, calculate_try_cost, fetch_usd_try_rate
from dublaj_hatti.bolum_00_omurga.runtime.arac_yolu import ffprobe_yolu


class ElevenLabsScribeError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, response_body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary_path, path)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _audio_duration_seconds(path: Path) -> float:
    result = subprocess.run(
        [ffprobe_yolu(), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise ElevenLabsScribeError("ElevenLabs girdisinin suresi ffprobe ile olculemedi")
    duration = float(result.stdout.strip())
    if duration <= 0:
        raise ElevenLabsScribeError("ElevenLabs girdisinin suresi gecersiz")
    return duration


def _request_fingerprint(media_path: Path, language_code: str | None, diarize: bool) -> dict[str, Any]:
    return {
        "audio_sha256": _file_sha256(media_path),
        "model_id": model_id,
        "language_code": language_code or "auto",
        "diarize": bool(diarize),
        "timestamps_granularity": "word",
        "tag_audio_events": True,
    }


def _load_reusable_response(
    manifest_path: Path,
    response_path: Path,
    fingerprint: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if not manifest_path.is_file() or not response_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload = json.loads(response_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if manifest.get("fingerprint") != fingerprint or manifest.get("status") != "api_response_saved":
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("words"), list):
        return None
    return payload, manifest


def _classify_error(status_code: int, response_body: str) -> str:
    lowered = response_body.lower()
    if status_code == 400:
        return "request_invalid"
    if status_code == 401:
        return "authentication_failed"
    if status_code == 403:
        return "permission_or_billing_failed"
    if status_code == 429:
        if "too_many_concurrent_requests" in lowered:
            return "concurrency_limit"
        if "system_busy" in lowered:
            return "provider_busy"
        return "quota_or_rate_limit"
    if status_code in {500, 502, 503, 504}:
        return "temporary_provider_error"
    return "provider_error"


def _request_timeout(media_path: Path) -> tuple[float, float]:
    estimated_upload_seconds = media_path.stat().st_size / minimum_upload_bytes_per_second
    upload_socket_timeout = max(30.0, estimated_upload_seconds + upload_timeout_grace_seconds)
    return min(float(request_timeout_seconds), upload_socket_timeout), float(request_timeout_seconds)


def _request_transcription(api_key: str, media_path: Path, language_code: str | None, diarize: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    content_type = mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"
    data = {
        "model_id": model_id,
        "timestamps_granularity": "word",
        "diarize": "true" if diarize else "false",
        "tag_audio_events": "true",
    }
    if language_code and language_code != "auto":
        data["language_code"] = language_code
    attempts = 2
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request_started_ms = int(time.time() * 1000)
        try:
            with media_path.open("rb") as media_file:
                response = requests.post(
                    endpoint,
                    headers={"xi-api-key": api_key},
                    files={"file": (media_path.name, media_file, content_type)},
                    data=data,
                    timeout=_request_timeout(media_path),
                )
            request_completed_ms = int(time.time() * 1000)
        except requests.RequestException as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(2.0)
                continue
            raise ElevenLabsScribeError(f"ElevenLabs baglantisi basarisiz: {exc}") from exc
        response_text = response.text
        if response.status_code == 200:
            try:
                payload = response.json()
            except ValueError as exc:
                raise ElevenLabsScribeError("ElevenLabs gecersiz JSON cevabi dondurdu", 200, response_text[:2000]) from exc
            metadata = {
                "request_id": response.headers.get("request-id") or response.headers.get("x-request-id"),
                "trace_id": response.headers.get("x-trace-id"),
                "status_code": response.status_code,
                "attempt_count": attempt,
                "request_started_ms": request_started_ms,
                "request_completed_ms": request_completed_ms,
                "response_character_cost": response.headers.get("character-cost"),
            }
            return payload, metadata
        error_class = _classify_error(response.status_code, response_text)
        retryable = error_class in {"provider_busy", "concurrency_limit", "temporary_provider_error"}
        if retryable and attempt < attempts:
            time.sleep(2.0)
            continue
        try:
            error_payload = response.json()
            detail = error_payload.get("detail", error_payload)
            detail_text = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
        except ValueError:
            detail_text = response_text[:600]
        raise ElevenLabsScribeError(
            f"ElevenLabs istegi basarisiz [{error_class}]: {detail_text}",
            response.status_code,
            response_text[:2000],
        )
    raise ElevenLabsScribeError(f"ElevenLabs istegi basarisiz: {last_error}")


def _build_word_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for item in payload.get("words") or []:
        if str(item.get("type") or "word") != "word":
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        start = float(item.get("start") or 0.0)
        end = float(item.get("end") or start)
        if end < start:
            raise ElevenLabsScribeError("ElevenLabs kelime zamani gecersiz")
        speaker_id = str(item.get("speaker_id") or "").strip()
        records.append({"word": text, "start": start, "end": end, "speaker": speaker_id})
    return records


def _write_usage_report(
    output_dir: Path,
    payload: dict[str, Any],
    metadata: dict[str, Any],
    local_duration_seconds: float,
    reused_response: bool,
    account_snapshot_path: Path,
    account_snapshot: dict[str, Any],
    analytics_snapshot: dict[str, Any],
) -> Path:
    report_path = output_dir / "usage_report.json"
    existing_report: dict[str, Any] = {}
    if reused_response and report_path.is_file():
        try:
            existing_report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing_report = {}
    provider_duration = payload.get("audio_duration_secs")
    billed_duration = float(provider_duration) if provider_duration is not None else local_duration_seconds
    tariff_cost = calculate_cost(billed_duration, price_usd_per_audio_hour)
    analytics_status = str(analytics_snapshot.get("status") or "")
    if reused_response and analytics_status != "provider_verified" and existing_report:
        analytics_status = str(existing_report.get("provider_analytics_status") or analytics_status)
    provider_cost_usd = analytics_snapshot.get("cost_usd")
    if reused_response and provider_cost_usd is None:
        provider_cost_usd = existing_report.get("provider_reported_cost_usd")
    provider_credits_used = analytics_snapshot.get("credits_used")
    if reused_response and provider_credits_used is None:
        provider_credits_used = existing_report.get("provider_reported_credits_used")
    provider_billed_minutes = analytics_snapshot.get("billed_minutes")
    if reused_response and provider_billed_minutes is None:
        provider_billed_minutes = existing_report.get("provider_reported_billed_minutes")
    provider_verified = analytics_status == "provider_verified" and provider_cost_usd is not None
    report_cost_usd = float(provider_cost_usd) if provider_verified else tariff_cost.cost_usd
    report: dict[str, Any] = {
        "provider": "ElevenLabs",
        "model": model_id,
        "endpoint": endpoint,
        "request_count": int(existing_report.get("request_count") or 1),
        "request_id": existing_report.get("request_id") or metadata.get("request_id") or payload.get("transcription_id"),
        "trace_id": existing_report.get("trace_id") or metadata.get("trace_id"),
        "status_code": int(metadata.get("status_code") or 200),
        "attempt_count": int(existing_report.get("attempt_count") or metadata.get("attempt_count") or 0),
        "reused_saved_response": bool(reused_response),
        "saved_response_reuse_count": int(existing_report.get("saved_response_reuse_count") or 0) + (1 if reused_response else 0),
        "local_audio_duration_seconds": local_duration_seconds,
        "provider_audio_duration_seconds": provider_duration,
        "billed_audio_duration_seconds": billed_duration,
        "price_usd_per_audio_hour": price_usd_per_audio_hour,
        "currency": "USD",
        "tariff_calculated_cost_usd": tariff_cost.cost_usd,
        "provider_reported_cost_usd": provider_cost_usd,
        "provider_reported_credits_used": provider_credits_used,
        "provider_reported_billed_minutes": provider_billed_minutes,
        "provider_analytics_status": analytics_status or "not_requested",
        "provider_analytics_error_code": analytics_snapshot.get("error_code") or existing_report.get("provider_analytics_error_code"),
        "provider_analytics_attempt_count": analytics_snapshot.get("attempt_count") or existing_report.get("provider_analytics_attempt_count"),
        "provider_analytics_source": analytics_snapshot.get("usage_source") or existing_report.get("provider_analytics_source"),
        "cost_evidence_status": "provider_analytics_exact" if provider_verified else "official_tariff_calculation",
        "cost_usd": report_cost_usd,
        "estimated_cost_usd": tariff_cost.cost_usd,
        "pricing_source": pricing_source,
        "limits_source": limits_source,
        "maximum_file_bytes": maximum_file_bytes,
        "maximum_audio_seconds": maximum_audio_seconds,
        "rpm": "not published",
        "tpm": "not applicable",
        "rpd": "not published",
        "tpd_tph": "not applicable",
        "account_plan_limits": "subscription_endpoint_only" if account_snapshot.get("status") == "available" else "not verified",
        "account_snapshot_path": str(account_snapshot_path),
        "account_snapshot_status": account_snapshot.get("status"),
        "account_snapshot_error_code": account_snapshot.get("error_code"),
        "account_snapshot_required_permission": account_snapshot.get("required_permission"),
        "account_tier": account_snapshot.get("tier"),
        "account_subscription_status": account_snapshot.get("subscription_status"),
        "account_period_character_count": account_snapshot.get("period_character_count"),
        "account_period_character_limit": account_snapshot.get("period_character_limit"),
        "account_period_character_remaining": account_snapshot.get("period_character_remaining"),
        "account_period_counter_semantics": account_snapshot.get("period_counter_semantics"),
        "account_top_up_balance_usd": account_snapshot.get("top_up_balance_usd"),
        "account_top_up_balance_status": account_snapshot.get("top_up_balance_status"),
        "exchange_rate_error": "",
    }
    reusable_exchange_rate = existing_report.get("usd_try_rate") if reused_response else None
    if reusable_exchange_rate is not None:
        cost_try = calculate_try_cost(report_cost_usd, float(reusable_exchange_rate))
        tariff_cost_try = calculate_try_cost(tariff_cost.cost_usd, float(reusable_exchange_rate))
        report.update({
            "usd_try_rate": reusable_exchange_rate,
            "exchange_rate_date": existing_report.get("exchange_rate_date"),
            "exchange_rate_fetched_at": existing_report.get("exchange_rate_fetched_at"),
            "exchange_rate_source": existing_report.get("exchange_rate_source"),
            "cost_try": cost_try,
            "estimated_cost_try": tariff_cost_try,
        })
    else:
        try:
            exchange = fetch_usd_try_rate(exchange_rate_timeout_seconds)
            cost_try = calculate_try_cost(report_cost_usd, exchange.usd_try_rate)
            tariff_cost_try = calculate_try_cost(tariff_cost.cost_usd, exchange.usd_try_rate)
            report.update({
                "usd_try_rate": exchange.usd_try_rate,
                "exchange_rate_date": exchange.rate_date,
                "exchange_rate_fetched_at": exchange.fetched_at,
                "exchange_rate_source": exchange.source,
                "cost_try": cost_try,
                "estimated_cost_try": tariff_cost_try,
            })
        except ExchangeRateError as exc:
            report["exchange_rate_error"] = str(exc)
            report["cost_try"] = None
            report["estimated_cost_try"] = None
    _atomic_write_json(report_path, report)
    return report_path


def transcribe_audio(
    audio_path: str,
    run_dir: str,
    language_code: str | None = None,
    use_diarization: bool = False,
) -> dict[str, Any]:
    api_key = get_api_key()
    if not api_key:
        raise ElevenLabsScribeError("ELEVENLABS_API_KEY .env dosyasinda bulunamadi")
    media_path = Path(audio_path).resolve()
    if not media_path.is_file():
        raise ElevenLabsScribeError("ElevenLabs ses girdisi bulunamadi")
    if media_path.stat().st_size > maximum_file_bytes:
        raise ElevenLabsScribeError("ElevenLabs ses girdisi resmi guvenli dosya boyutu sinirini asiyor")
    local_duration = _audio_duration_seconds(media_path)
    if local_duration > maximum_audio_seconds:
        raise ElevenLabsScribeError("ElevenLabs ses girdisi 10 saatlik sure sinirini asiyor")
    normalized_language = str(language_code or "").strip().lower() or None
    output_dir = Path(run_dir).resolve() / "elevenlabs_scribe_v2"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "request_manifest.json"
    response_path = output_dir / "raw_response.json"
    fingerprint = _request_fingerprint(media_path, normalized_language, use_diarization)
    reusable_response = _load_reusable_response(manifest_path, response_path, fingerprint)
    reused_response = reusable_response is not None
    if reused_response:
        payload, saved_manifest = reusable_response
        metadata = {
            "status_code": 200,
            "attempt_count": 0,
            "request_id": saved_manifest.get("request_id") or payload.get("transcription_id"),
            "trace_id": saved_manifest.get("trace_id"),
            "request_started_ms": saved_manifest.get("request_started_ms"),
            "request_completed_ms": saved_manifest.get("request_completed_ms"),
        }
    else:
        _atomic_write_json(manifest_path, {"status": "requesting", "fingerprint": fingerprint})
        payload, metadata = _request_transcription(api_key, media_path, normalized_language, use_diarization)
        _atomic_write_json(response_path, payload)
        _atomic_write_json(
            manifest_path,
            {
                "status": "api_response_saved",
                "fingerprint": fingerprint,
                "request_id": metadata.get("request_id") or payload.get("transcription_id"),
                "trace_id": metadata.get("trace_id"),
                "request_started_ms": metadata.get("request_started_ms"),
                "request_completed_ms": metadata.get("request_completed_ms"),
                "status_code": metadata.get("status_code"),
            },
        )
    words = _build_word_records(payload)
    if not words:
        raise ElevenLabsScribeError("ElevenLabs Scribe v2 konusma kelimesi dondurmedi")
    account_snapshot_path, account_snapshot = refresh_subscription_snapshot(
        output_dir,
        api_key,
        account_status_timeout_seconds,
    )
    provider_duration = payload.get("audio_duration_secs")
    billed_duration = float(provider_duration) if provider_duration is not None else local_duration
    analytics_snapshot = {}
    existing_analytics_verified = False
    existing_usage_path = output_dir / "usage_report.json"
    if reused_response and existing_usage_path.is_file():
        try:
            existing_usage = json.loads(existing_usage_path.read_text(encoding="utf-8"))
            existing_analytics_verified = existing_usage.get("provider_analytics_status") == "provider_verified"
        except (OSError, json.JSONDecodeError):
            existing_analytics_verified = False
    if not existing_analytics_verified:
        analytics_snapshot = reconcile_transcription_usage(
            api_key,
            str(metadata.get("trace_id") or ""),
            metadata.get("request_started_ms"),
            metadata.get("request_completed_ms"),
            billed_duration,
            analytics_timeout_seconds,
            analytics_retry_count,
            analytics_retry_delay_seconds,
        )
    usage_report_path = _write_usage_report(
        output_dir,
        payload,
        metadata,
        local_duration,
        reused_response,
        account_snapshot_path,
        account_snapshot,
        analytics_snapshot,
    )
    return {
        "success": True,
        "words": words,
        "detected_language": str(payload.get("language_code") or normalized_language or "auto"),
        "raw_transcript": str(payload.get("text") or ""),
        "total_words": len(words),
        "usage_report_path": str(usage_report_path),
        "raw_response_path": str(response_path),
        "request_manifest_path": str(manifest_path),
        "account_snapshot_path": str(account_snapshot_path),
    }
