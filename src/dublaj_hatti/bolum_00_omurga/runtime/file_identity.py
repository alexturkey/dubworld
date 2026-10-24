from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict


def file_identity(value: Any) -> Dict[str, Any]:
    raw_path = str(value or "").strip()
    if not raw_path:
        return {}
    path = Path(raw_path).expanduser()
    identity: Dict[str, Any] = {
        "path": str(path.resolve(strict=False)),
        "exists": path.is_file(),
    }
    if not identity["exists"]:
        return identity
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    identity.update({
        "size": int(stat.st_size),
        "sha256": digest.hexdigest(),
    })
    return identity
