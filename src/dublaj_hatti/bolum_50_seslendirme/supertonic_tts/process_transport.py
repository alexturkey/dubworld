from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def encode_result(value, directory: Path, arrays: list | None = None):
    if arrays is None:
        arrays = []
    if isinstance(value, np.ndarray):
        if value.dtype != np.float32 or not np.isfinite(value).all():
            raise ValueError("Invalid Supertonic audio array")
        name = f"audio_{len(arrays):04d}.npy"
        arrays.append(name)
        path = directory / name
        np.save(path, value, allow_pickle=False)
        return {"type": "array", "file": name, "shape": list(value.shape),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if isinstance(value, dict):
        return {"type": "dict", "items": [[encode_result(k, directory, arrays),
                encode_result(v, directory, arrays)] for k, v in value.items()]}
    if isinstance(value, (list, tuple)):
        return {"type": "tuple" if isinstance(value, tuple) else "list",
                "items": [encode_result(v, directory, arrays) for v in value]}
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or isinstance(value, (str, int, float, bool)):
        return {"type": "scalar", "value": value}
    raise TypeError(f"Unsupported Supertonic result type: {type(value).__name__}")


def decode_result(value, directory: Path):
    kind = value["type"]
    if kind == "array":
        path = (directory / value["file"]).resolve()
        if path.parent != directory.resolve() or path.suffix != ".npy":
            raise ValueError("Invalid Supertonic audio path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != value["sha256"]:
            raise ValueError("Supertonic audio checksum mismatch")
        audio = np.load(path, allow_pickle=False)
        if audio.dtype != np.float32 or list(audio.shape) != value["shape"] or not np.isfinite(audio).all():
            raise ValueError("Invalid Supertonic audio array")
        return audio
    if kind == "dict":
        pairs = [(decode_result(k, directory), decode_result(v, directory)) for k, v in value["items"]]
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("Duplicate Supertonic result key")
        return result
    if kind in ("list", "tuple"):
        items = [decode_result(v, directory) for v in value["items"]]
        return tuple(items) if kind == "tuple" else items
    if kind == "scalar":
        return value["value"]
    raise ValueError("Unknown Supertonic result type")


def validate_result(result, segments) -> None:
    results = result[0] if isinstance(result, tuple) else result
    expected = [int(item["index"]) for item in segments]
    if len(set(expected)) != len(expected):
        raise ValueError("Duplicate Supertonic input segment")
    if not isinstance(results, dict) or set(results) != set(expected):
        raise RuntimeError("Supertonic synthesis returned incomplete segments")
    for item in results.values():
        audio = item["wav_array"]
        if not isinstance(audio, np.ndarray) or audio.dtype != np.float32 or audio.size == 0:
            raise RuntimeError("Invalid Supertonic waveform")
        if not np.isfinite(audio).all() or int(item["sample_rate"]) <= 0:
            raise RuntimeError("Invalid Supertonic audio samples")
