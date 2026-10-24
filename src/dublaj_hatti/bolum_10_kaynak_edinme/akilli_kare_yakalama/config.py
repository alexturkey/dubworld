from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SMART_FRAME_CONFIG_KEY = "smart_frame_capture_enabled"


def smart_frame_capture_enabled(config: Mapping[str, Any]) -> bool:
    return bool(config.get(SMART_FRAME_CONFIG_KEY, False))
