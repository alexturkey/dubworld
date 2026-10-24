from __future__ import annotations

import json

from .account import ElevenLabsAccountError, fetch_subscription_snapshot
from .config import account_status_timeout_seconds, get_api_key


def main() -> int:
    try:
        snapshot = fetch_subscription_snapshot(get_api_key(), account_status_timeout_seconds)
    except ElevenLabsAccountError as exc:
        print(json.dumps({
            "status": "unavailable",
            "error_code": exc.code,
            "status_code": exc.status_code,
            "required_permission": exc.required_permission or None,
        }, ensure_ascii=True, indent=2))
        return 2
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
