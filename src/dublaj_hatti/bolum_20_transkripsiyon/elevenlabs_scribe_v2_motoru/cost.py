from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import requests

money_quant = Decimal("0.000001")
frankfurter_usd_try_url = "https://api.frankfurter.dev/v2/rate/USD/TRY?providers=ECB"
exchange_rate_source = "Frankfurter / ECB"


class ExchangeRateError(RuntimeError):
    pass


@dataclass(frozen=True)
class CostResult:
    duration_seconds: float
    rate_usd_per_hour: float
    cost_usd: float


@dataclass(frozen=True)
class ExchangeRateResult:
    usd_try_rate: float
    rate_date: str
    fetched_at: str
    source: str


def calculate_cost(duration_seconds: float, rate_usd_per_hour: float) -> CostResult:
    duration = max(Decimal(str(duration_seconds)), Decimal("0"))
    rate = max(Decimal(str(rate_usd_per_hour)), Decimal("0"))
    base = ((duration / Decimal("3600")) * rate).quantize(money_quant, rounding=ROUND_HALF_UP)
    return CostResult(
        duration_seconds=float(duration),
        rate_usd_per_hour=float(rate),
        cost_usd=float(base),
    )


def fetch_usd_try_rate(timeout_seconds: float) -> ExchangeRateResult:
    try:
        response = requests.get(frankfurter_usd_try_url, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ExchangeRateError(f"USD/TRY kuru alinamadi: {exc}") from exc
    if payload.get("base") != "USD" or payload.get("quote") != "TRY":
        raise ExchangeRateError("Kur servisi beklenmeyen doviz cifti dondurdu")
    try:
        rate = Decimal(str(payload.get("rate")))
    except (InvalidOperation, TypeError) as exc:
        raise ExchangeRateError("Kur servisi gecersiz kur dondurdu") from exc
    if rate <= 0:
        raise ExchangeRateError("Kur servisi sifir veya negatif kur dondurdu")
    rate_date = str(payload.get("date") or "").strip()
    if not rate_date:
        raise ExchangeRateError("Kur servisinin yanitinda kur tarihi yok")
    # Local time zone of the machine (with its UTC offset), not a hard-coded region.
    fetched_at = datetime.now().astimezone().isoformat(timespec="seconds")
    return ExchangeRateResult(float(rate), rate_date, fetched_at, exchange_rate_source)


def calculate_try_cost(cost_usd: float, usd_try_rate: float) -> float:
    rate = Decimal(str(usd_try_rate))
    base = (Decimal(str(cost_usd)) * rate).quantize(money_quant, rounding=ROUND_HALF_UP)
    return float(base)
