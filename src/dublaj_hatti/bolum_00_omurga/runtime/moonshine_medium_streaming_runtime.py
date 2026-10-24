from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import time
import wave
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
# Motor klasörü paketin içindedir (src/dublaj_hatti/bolum_20_transkripsiyon/...); paket kökünden bulunur,
# repo düzenine bağlı değildir. DUBLAJ_MOONSHINE_ROOT ile geçersiz kılınır.
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
MOTOR_ROOT = PACKAGE_ROOT / "bolum_20_transkripsiyon" / "moonshine_medium_streaming_motoru"
MOONSHINE_ROOT_ENV = "DUBLAJ_MOONSHINE_ROOT"
_GIZLI = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def motor_root() -> Path:
    configured = os.environ.get(MOONSHINE_ROOT_ENV, "").strip()
    return (Path(configured).expanduser() if configured else MOTOR_ROOT).resolve()
ENGINE_ID = "moonshine_medium_streaming_en"
MODEL_ID = "medium-streaming-en"
RUNTIME_CONTRACT_VERSION = "moonshine_medium_streaming_v1"
RESULT_SCHEMA_VERSION = 1
EXPECTED_MODEL_FILES = {
    "adapter.ort", "cross_kv.ort", "decoder_kv_with_attention.ort", "decoder_kv.ort",
    "encoder.ort", "frontend.ort", "streaming_config.json", "tokenizer.bin",
}
EXPECTED_NATIVE_FILES = {
    "moonshine.dll": "0889E76B2073344098E62076EE17BBD99F936821CE43CCC4188973BBCEB398AF",
    "onnxruntime.dll": "DEC964AB1EE36CC9B0AE247D13B376627992FC57DEC0454354017AB8FD84F1EA",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _python_path() -> Path:
    configured = os.environ.get("DUBLAJ_MOONSHINE_PYTHON", "").strip()
    path = Path(configured) if configured else motor_root() / ".venv" / "Scripts" / "python.exe"
    if not path.is_file():
        raise RuntimeError(f"Moonshine bagimsiz Python ortami bulunamadi: {path}")
    return path.resolve()


def _native_runtime_hashes() -> dict[str, str]:
    interpreter = _python_path()
    venv_root = interpreter.parent.parent
    native_root = venv_root / "Lib" / "site-packages" / "moonshine_voice"
    hashes = {
        name: _sha256(native_root / name)
        for name in EXPECTED_NATIVE_FILES
    }
    if hashes != EXPECTED_NATIVE_FILES:
        raise RuntimeError("Moonshine native DLL kimlikleri beklenen ortamla eslesmiyor")
    return hashes


def moonshine_contract_inputs() -> dict[str, Any]:
    runner = motor_root() / "src" / "run_experiment.py"
    model_root = motor_root() / "models" / "download.moonshine.ai" / "model" / MODEL_ID / "quantized"
    files = {p.name: _sha256(p) for p in sorted(model_root.iterdir()) if p.is_file()}
    if set(files) != EXPECTED_MODEL_FILES:
        raise RuntimeError(f"Moonshine model dosya kumesi gecersiz: {sorted(files)}")
    manifest = json.loads((motor_root() / "config" / "model_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("files") != files:
        raise RuntimeError("Moonshine model manifest hashleri eslesmiyor")
    return {
        "moonshine_runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "moonshine_runner_sha256": _sha256(runner),
        "moonshine_model_id": MODEL_ID,
        "moonshine_model_files_sha256": files,
        "moonshine_execution_mode": "offline",
        "moonshine_word_timestamps": True,
        "moonshine_result_schema_version": RESULT_SCHEMA_VERSION,
        "moonshine_python": str(_python_path()),
        "moonshine_package_version": "0.0.73",
        "moonshine_native_runtime_sha256": _native_runtime_hashes(),
        "moonshine_adapter_sha256": _sha256(Path(__file__).resolve()),
    }


def _validate_result(result: dict[str, Any], audio_path: Path) -> None:
    required = {
        "engine": "moonshine-voice",
        "package_version": "0.0.73",
        "model": MODEL_ID,
        "model_arch": "MEDIUM_STREAMING",
        "quantization": "official_quantized_ort",
        "device": "cpu",
    }
    for key, expected in required.items():
        if result.get(key) != expected:
            raise RuntimeError(f"Moonshine sonucunda {key} gecersiz")
    if result.get("execution_mode") != "offline":
        raise RuntimeError("Moonshine offline zorunlulugu ihlal edildi")
    if result.get("model") != MODEL_ID or result.get("word_timestamp_count", 0) <= 0:
        raise RuntimeError("Moonshine gecerli model veya native kelime zamani uretmedi")
    if not str(result.get("transcript") or "").strip():
        raise RuntimeError("Moonshine bos transkript uretmis")
    if result.get("audio_sha256") != _sha256(audio_path):
        raise RuntimeError("Moonshine sonucundaki ses kimligi eslesmiyor")
    with wave.open(str(audio_path), "rb") as handle:
        expected_rate = handle.getframerate()
        expected_duration = handle.getnframes() / expected_rate
    if result.get("sample_rate") != expected_rate:
        raise RuntimeError("Moonshine sample rate girdiden farkli")
    if not math.isfinite(float(result.get("audio_duration_seconds", float("nan")))):
        raise RuntimeError("Moonshine ses suresi sonlu degil")
    if abs(float(result["audio_duration_seconds"]) - expected_duration) > 1e-3:
        raise RuntimeError("Moonshine ses suresi girdiden farkli")
    reported = Path(str(result.get("audio_path", ""))).resolve()
    if reported != audio_path.resolve():
        raise RuntimeError("Moonshine sonucundaki ses yolu istenen girdiyi gostermiyor")
    words = result.get("word_timestamps")
    if not isinstance(words, list) or not words:
        raise RuntimeError("Moonshine native kelime zamanlari eksik")
    if int(result.get("word_timestamp_count") or 0) != len(words):
        raise RuntimeError("Moonshine native kelime sayisi tutarsiz")
    for index, word in enumerate(words):
        start = word.get("start")
        end = word.get("end")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise RuntimeError(f"Moonshine gecersiz zaman: {index}")
        if not math.isfinite(float(start)) or not math.isfinite(float(end)):
            raise RuntimeError(f"Moonshine sonlu olmayan zaman: {index}")
        if start < 0 or end < start or end > float(result["audio_duration_seconds"]) + 1e-3:
            raise RuntimeError(f"Moonshine zaman siniri disinda: {index}")


def invoke_moonshine(
    audio_path: str,
    run_dir: str,
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    audio = Path(audio_path).resolve()
    if not audio.is_file():
        raise FileNotFoundError(f"Moonshine ses girdisi bulunamadi: {audio}")
    run_root = Path(run_dir).resolve() / "moonshine_medium_streaming"
    run_root.mkdir(parents=True, exist_ok=True)
    model_root = motor_root() / "models" / "download.moonshine.ai" / "model" / MODEL_ID / "quantized"
    if {p.name for p in model_root.iterdir() if p.is_file()} != EXPECTED_MODEL_FILES:
        raise RuntimeError("Moonshine model dosya kumesi eksik veya fazla")
    manifest = json.loads((motor_root() / "config" / "model_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("files") != {p.name: _sha256(p) for p in model_root.iterdir() if p.is_file()}:
        raise RuntimeError("Moonshine model manifest hashleri eslesmiyor")
    native_hashes = _native_runtime_hashes()
    command = [
        str(_python_path()),
        "-B",
        str(motor_root() / "src" / "run_experiment.py"),
        "--audio", str(audio),
        "--model-dir", str(model_root),
        "--output-root", str(run_root),
        "--execution-mode", "offline",
    ]
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=str(motor_root()),
            **_GIZLI,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Moonshine transkripsiyon timeout") from exc
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(f"Moonshine subprocess basarisiz ({completed.returncode}): {completed.stderr[-2000:]}")
    try:
        announcements = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
        if not announcements:
            raise RuntimeError("Moonshine stdout bos")
        announcement = announcements[-1]
        announced_output = Path(announcement["output"]).resolve()
        if not announced_output.is_relative_to(run_root):
            raise RuntimeError("Moonshine output yolu izin verilen is kokunun disinda")
        raw_path = announced_output / "result.json"
        if not raw_path.is_file():
            raise RuntimeError("Moonshine result.json bulunamadi")
        result = json.loads(raw_path.read_text(encoding="utf-8"))
    except (ValueError, KeyError, OSError, IndexError) as exc:
        raise RuntimeError("Moonshine subprocess sonucu parse edilemedi") from exc
    _validate_result(result, audio)
    result["runtime_contract_version"] = RUNTIME_CONTRACT_VERSION
    result["result_schema_version"] = RESULT_SCHEMA_VERSION
    result["wall_seconds"] = elapsed
    result["runner_sha256"] = _sha256(motor_root() / "src" / "run_experiment.py")
    result["native_runtime_sha256"] = native_hashes
    result["artifacts"] = {
        "raw_result_path": str(raw_path),
        "transcript_path": str(raw_path.with_name("transcript.txt")),
        "result_sha256": _sha256(raw_path),
    }
    return result


__all__ = ["ENGINE_ID", "MODEL_ID", "RUNTIME_CONTRACT_VERSION", "invoke_moonshine", "moonshine_contract_inputs"]
