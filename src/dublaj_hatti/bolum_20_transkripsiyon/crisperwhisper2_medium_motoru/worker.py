from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    configured_root = os.environ.get("CRISPERWHISPER_EXPERIMENT_ROOT", "").strip()
    if not configured_root:
        raise RuntimeError("CRISPERWHISPER_EXPERIMENT_ROOT tanimli degil")
    experiment_src = Path(configured_root).resolve() / "src"
    if not experiment_src.is_dir():
        raise FileNotFoundError(f"CrisperWhisper deney source klasoru bulunamadi: {experiment_src}")
    sys.path.insert(0, str(experiment_src))
    from crisperwhisper_api_service import main as api_main

    return api_main()


if __name__ == "__main__":
    raise SystemExit(main())
