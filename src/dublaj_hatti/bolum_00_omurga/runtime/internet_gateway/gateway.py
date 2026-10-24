from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import threading
import time
from typing import Any, Callable, Optional, TypeVar
from urllib.parse import urlparse


T = TypeVar("T")

EGRESS_PROXY_ENV = "DUBLAJ_EGRESS_PROXY"
EGRESS_MODE_ENV = "DUBLAJ_EGRESS_MODE"
DIRECT_RECHECK_SECONDS_ENV = "DUBLAJ_DIRECT_RECHECK_SECONDS"
DIRECT_PROBE_HOST_ENV = "DUBLAJ_DIRECT_PROBE_HOST"
DIRECT_PROBE_PORT_ENV = "DUBLAJ_DIRECT_PROBE_PORT"

_PROXY_ENV_NAMES = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
_NO_PROXY_ENV_NAMES = ("NO_PROXY", "no_proxy")
_LOCAL_BYPASS_HOSTS = ("127.0.0.1", "localhost", "::1", "host.docker.internal")
_NETWORK_ERRNOS = {11001, 11002, 11004, 10050, 10051, 10064, 10065, -2, -3}
_NETWORK_TEXT_MARKERS = (
    "failed to resolve",
    "could not resolve host",
    "getaddrinfo failed",
    "name or service not known",
    "temporary failure in name resolution",
    "nodename nor servname provided",
    "network is unreachable",
    "no route to host",
    "a socket operation was attempted to an unreachable network",
    "the network location cannot be reached",
)


@dataclass(frozen=True)
class InternetRoute:
    name: str
    proxy_url: Optional[str]


def _exception_chain(error: BaseException) -> list[BaseException]:
    result: list[BaseException] = []
    pending: list[BaseException] = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(current)
        for candidate in (
            getattr(current, "__cause__", None),
            getattr(current, "__context__", None),
            getattr(current, "reason", None),
        ):
            if isinstance(candidate, BaseException):
                pending.append(candidate)
    return result


def is_network_path_failure(error: BaseException) -> bool:
    for current in _exception_chain(error):
        errno_value = getattr(current, "errno", None)
        if isinstance(errno_value, int) and errno_value in _NETWORK_ERRNOS:
            return True
        text = str(current).lower()
        if any(marker in text for marker in _NETWORK_TEXT_MARKERS):
            return True
    return False


def _validated_proxy_url(value: str) -> Optional[str]:
    proxy_url = str(value or "").strip()
    if not proxy_url:
        return None
    parsed = urlparse(proxy_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{EGRESS_PROXY_ENV} gecersiz proxy URL'i iceriyor")
    return proxy_url


class InternetGateway:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._baseline_no_proxy_env = {name: os.environ.get(name) for name in _NO_PROXY_ENV_NAMES}
        self._fallback_proxy = _validated_proxy_url(os.getenv(EGRESS_PROXY_ENV, ""))
        requested_mode = str(os.getenv(EGRESS_MODE_ENV, "direct") or "direct").strip().lower()
        if requested_mode not in {"direct", "warp"}:
            raise ValueError(f"{EGRESS_MODE_ENV} yalniz direct veya warp olabilir")
        if requested_mode == "warp" and not self._fallback_proxy:
            raise ValueError(f"{EGRESS_MODE_ENV}=warp icin {EGRESS_PROXY_ENV} zorunludur")
        self._route = InternetRoute("warp", self._fallback_proxy) if requested_mode == "warp" else InternetRoute("direct", None)
        self._last_direct_probe_at = 0.0
        self._apply_process_route(self._route)

    def current_route(self) -> InternetRoute:
        with self._lock:
            if self._route.name == "warp" and self._should_recheck_direct():
                self._last_direct_probe_at = time.monotonic()
                if self._direct_ipv4_available():
                    self._activate(InternetRoute("direct", None))
            return self._route

    def run(
        self,
        operation: Callable[[InternetRoute], T],
        operation_name: str,
        logger: Optional[object] = None,
        evidence_dir: Optional[str | Path] = None,
    ) -> T:
        first_route = self.current_route()
        try:
            return operation(first_route)
        except Exception as error:
            if not is_network_path_failure(error):
                raise
            alternate = self._alternate_route(first_route)
            if alternate is None or alternate == first_route:
                raise
            self._activate(alternate)
            self._record_transition(
                operation_name,
                first_route,
                alternate,
                error,
                logger,
                evidence_dir,
            )
            return operation(alternate)

    def _alternate_route(self, failed_route: InternetRoute) -> Optional[InternetRoute]:
        if failed_route.name == "direct":
            if self._fallback_proxy:
                return InternetRoute("warp", self._fallback_proxy)
            return None
        self._last_direct_probe_at = time.monotonic()
        if self._direct_ipv4_available():
            return InternetRoute("direct", None)
        return None

    def _activate(self, route: InternetRoute) -> None:
        with self._lock:
            self._route = route
            if route.name == "warp":
                self._last_direct_probe_at = time.monotonic()
            self._apply_process_route(route)

    def _apply_process_route(self, route: InternetRoute) -> None:
        if route.proxy_url:
            for name in _PROXY_ENV_NAMES:
                os.environ[name] = route.proxy_url
            for name in _NO_PROXY_ENV_NAMES:
                current = self._baseline_no_proxy_env.get(name) or ""
                values = [item.strip() for item in current.split(",") if item.strip()]
                for host in _LOCAL_BYPASS_HOSTS:
                    if host not in values:
                        values.append(host)
                os.environ[name] = ",".join(values)
            return
        for name in _PROXY_ENV_NAMES:
            os.environ.pop(name, None)
        for name, value in self._baseline_no_proxy_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def _should_recheck_direct(self) -> bool:
        raw_interval = str(os.getenv(DIRECT_RECHECK_SECONDS_ENV, "60") or "60").strip()
        try:
            interval = max(5.0, float(raw_interval))
        except ValueError:
            interval = 60.0
        return time.monotonic() - self._last_direct_probe_at >= interval

    def _direct_ipv4_available(self) -> bool:
        host = str(os.getenv(DIRECT_PROBE_HOST_ENV, "1.1.1.1") or "1.1.1.1").strip()
        try:
            port = int(str(os.getenv(DIRECT_PROBE_PORT_ENV, "443") or "443").strip())
        except ValueError:
            port = 443
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.settimeout(2.0)
                probe.connect((host, port))
            return True
        except OSError:
            return False

    def _record_transition(
        self,
        operation_name: str,
        previous_route: InternetRoute,
        new_route: InternetRoute,
        error: BaseException,
        logger: Optional[object],
        evidence_dir: Optional[str | Path],
    ) -> None:
        message = (
            "[INTERNET_GATEWAY] network path changed: operation=%s from=%s to=%s reason=%s"
        )
        if logger:
            logger.warning(
                message,
                operation_name,
                previous_route.name,
                new_route.name,
                type(error).__name__,
            )
        if not evidence_dir:
            return
        evidence_path = Path(evidence_dir) / "internet_gateway_events.jsonl"
        payload = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "operation": operation_name,
            "from_route": previous_route.name,
            "to_route": new_route.name,
            "error_type": type(error).__name__,
            "classification": "dns_or_ipv4_egress",
            "action": "retry_same_operation",
        }
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with evidence_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


_GATEWAY: Optional[InternetGateway] = None
_GATEWAY_LOCK = threading.Lock()


def _gateway() -> InternetGateway:
    global _GATEWAY
    if _GATEWAY is None:
        with _GATEWAY_LOCK:
            if _GATEWAY is None:
                _GATEWAY = InternetGateway()
    return _GATEWAY


def current_internet_route() -> InternetRoute:
    return _gateway().current_route()


def run_with_internet_gateway(
    operation: Callable[[InternetRoute], T],
    operation_name: str,
    logger: Optional[object] = None,
    evidence_dir: Optional[str | Path] = None,
) -> T:
    return _gateway().run(operation, operation_name, logger, evidence_dir)
