import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import wave
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
MODEL_REPO = "nyralabs/CrisperWhisper2.0_medium"
MODEL_SNAPSHOT = "ca981a994a008f70b7ce343ef1e261ff7eadc1d9"
EXPECTED_MODEL_FILE_COUNT = 14
EXPECTED_MODEL_TOTAL_BYTES = 1533574881
EXPECTED_MODEL_WEIGHT_SHA256 = "9736594386F5DE3DB181DE8085F42BF44D4B9E26E29E6BEC9319AC865A1CE684"
EXPECTED_GPU = "NVIDIA GeForce GTX 1050 Ti"
EXPECTED_AUDIO_SHA256 = "90EE9CD6F3349769E1071CED4AE4E96EAF4682E3308742375A37142F8BDD5817"
# Saglik denetimi girdileri komut satirindan verilir (--short-audio, --long-audio); varsayilan yok.
SHORT_AUDIO = None
LONG_AUDIO = None
LONG_VIDEO = None
BASE_PYTHON = Path(sys.executable)
MAIN_PYTHON = Path(sys.executable)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temp_path.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run_command(command, env=None, check=True):
    result = subprocess.run(
        [str(item) for item in command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(map(str, command))}: {detail}")
    return result


def configure_cache(offline):
    cache_root = EXPERIMENT_ROOT / "model_cache"
    huggingface_root = cache_root / "huggingface"
    hub_root = huggingface_root / "hub"
    transformers_root = huggingface_root / "transformers"
    torch_root = cache_root / "torch"
    for path in (huggingface_root, hub_root, transformers_root, torch_root):
        path.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(huggingface_root)
    os.environ["HF_HUB_CACHE"] = str(hub_root)
    os.environ["TRANSFORMERS_CACHE"] = str(transformers_root)
    os.environ["TORCH_HOME"] = str(torch_root)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    else:
        os.environ.pop("HF_HUB_OFFLINE", None)
        os.environ.pop("TRANSFORMERS_OFFLINE", None)
    return {
        "root": str(cache_root),
        "hf_home": str(huggingface_root),
        "hf_hub_cache": str(hub_root),
        "transformers_cache": str(transformers_root),
        "torch_home": str(torch_root),
        "offline": offline,
    }


def package_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def redact_freeze_line(line):
    line = str(line).strip()
    if re.search(r"(?i)(https?|file|git\+https?|ssh)://", line):
        return "<origin-redacted>"
    if re.search(r"(?i)([A-Z]:[\\/]|\\\\)", line) and "==" not in line:
        return line.split(" @ ", 1)[0] + " @ <origin-redacted>"
    return line


def pip_snapshot(python_path):
    result = run_command([python_path, "-m", "pip", "--disable-pip-version-check", "freeze", "--all"])
    lines = sorted(
        [redact_freeze_line(line) for line in result.stdout.splitlines() if line.strip()],
        key=str.lower,
    )
    text = "\n".join(lines) + "\n"
    return {
        "python_executable": str(Path(python_path).resolve()),
        "python_version": platform.python_version() if Path(python_path).resolve() == Path(sys.executable).resolve() else None,
        "package_count": len(lines),
        "pip_freeze_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest().upper(),
        "pip_freeze": lines,
    }


def gpu_status():
    result = run_command(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version,memory.total,memory.used,memory.free,utilization.gpu",
            "--format=csv,noheader,nounits",
        ]
    )
    fields = [field.strip() for field in result.stdout.strip().split(",")]
    if len(fields) != 6:
        raise RuntimeError("Unexpected nvidia-smi GPU row")
    return {
        "name": fields[0],
        "driver_version": fields[1],
        "memory_total_mib": int(fields[2]),
        "memory_used_mib": int(fields[3]),
        "memory_free_mib": int(fields[4]),
        "utilization_percent": int(fields[5]),
    }


def gpu_processes():
    result = run_command(
        [
            "nvidia-smi",
            "--query-compute-apps=pid,process_name,used_memory",
            "--format=csv,noheader,nounits",
        ],
        check=False,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def wav_info(path):
    with wave.open(str(path), "rb") as audio:
        return {
            "path": str(Path(path).resolve()),
            "size_bytes": Path(path).stat().st_size,
            "sha256": sha256_file(path),
            "duration_seconds": audio.getnframes() / float(audio.getframerate()),
            "sample_rate": audio.getframerate(),
            "channels": audio.getnchannels(),
            "sample_width_bytes": audio.getsampwidth(),
            "frame_count": audio.getnframes(),
        }


def media_duration(path):
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ]
    )
    return float(result.stdout.strip())


def executable_version(command):
    result = run_command([command, "-version"])
    return result.stdout.splitlines()[0] if result.stdout.splitlines() else ""


def require_experiment_root(path):
    resolved = Path(path).resolve()
    if resolved != EXPERIMENT_ROOT:
        raise RuntimeError(f"All experiment operations must stay under {EXPERIMENT_ROOT}")
    return resolved


def preflight(args):
    require_experiment_root(args.project_root)
    short_audio = Path(args.short_audio).resolve()
    long_audio = Path(args.long_audio).resolve()
    long_video = Path(args.long_video).resolve()
    setup_dir = EXPERIMENT_ROOT / "output" / "crisperwhisper2_medium_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    short = wav_info(short_audio)
    long = wav_info(long_audio)
    video = {
        "path": str(long_video),
        "size_bytes": long_video.stat().st_size,
        "sha256": sha256_file(long_video),
        "duration_seconds": media_duration(long_video),
    }
    gpu = gpu_status()
    free_bytes = shutil.disk_usage(EXPERIMENT_ROOT).free
    main_snapshot = pip_snapshot(args.main_python)
    checks = {
        "base_python_executable": Path(sys.executable).resolve() == Path(args.base_python).resolve(),
        "python_3_10_11": platform.python_version() == "3.10.11",
        "python_64bit": platform.architecture()[0] == "64bit",
        "short_audio_duration": abs(short["duration_seconds"] - 46.0) <= 0.01,
        "short_audio_format": short["sample_rate"] == 16000 and short["channels"] == 1 and short["sample_width_bytes"] == 2,
        "long_audio_sha256": long["sha256"] == EXPECTED_AUDIO_SHA256,
        "long_audio_duration": abs(long["duration_seconds"] - 2515.88) <= 0.01,
        "long_audio_format": long["sample_rate"] == 16000 and long["channels"] == 1 and long["sample_width_bytes"] == 2,
        "long_video_duration": abs(video["duration_seconds"] - 2514.88) <= 0.01,
        "gpu_model": gpu["name"] == EXPECTED_GPU,
        "gpu_free_for_start": gpu["memory_free_mib"] >= 3800 and gpu["memory_used_mib"] <= 256,
        "no_compute_process": not gpu_processes(),
        "c_drive_free_gib": free_bytes >= 12 * 1024**3,
        "ffmpeg_available": bool(executable_version("ffmpeg")),
        "ffprobe_available": bool(executable_version("ffprobe")),
        "main_python_exists": Path(args.main_python).is_file(),
        "experiment_venv_absent": not (EXPERIMENT_ROOT / ".venv").exists(),
    }
    report = {
        "success": all(checks.values()),
        "created_at": now_iso(),
        "project_root": str(EXPERIMENT_ROOT),
        "policy": {
            "synthetic_tests": False,
            "real_physical_media_required": True,
            "main_application_mutation": False,
        },
        "python": {
            "executable": str(Path(sys.executable).resolve()),
            "version": platform.python_version(),
            "architecture": platform.architecture()[0],
            "base_python_requested": str(Path(args.base_python).resolve()),
        },
        "short_audio": short,
        "long_audio": long,
        "long_video": video,
        "gpu": gpu,
        "gpu_processes": gpu_processes(),
        "c_drive_free_bytes": free_bytes,
        "c_drive_free_gib": free_bytes / 1024**3,
        "ffmpeg": executable_version("ffmpeg"),
        "ffprobe": executable_version("ffprobe"),
        "main_venv_before": main_snapshot,
        "historical_comparison_outputs_present": (EXPERIMENT_ROOT / "output" / "candidate_word_timeline_karsilastirmasi").exists(),
        "checks": checks,
    }
    write_json(Path(args.output), report)
    print(f"PREFLIGHT_SUCCESS={str(report['success']).lower()}", flush=True)
    print(f"PREFLIGHT_REPORT={Path(args.output).resolve()}", flush=True)
    if not report["success"]:
        failed = [key for key, value in checks.items() if not value]
        raise RuntimeError("Preflight failed: " + ", ".join(failed))


def environment(args):
    require_experiment_root(args.project_root)
    package_names = {
        "crisperwhisper": "crisperwhisper",
        "ctranslate2": "ctranslate2",
        "torch": "torch",
        "transformers": "transformers",
        "huggingface_hub": "huggingface-hub",
        "numpy": "numpy",
        "accelerate": "accelerate",
        "tokenizers": "tokenizers",
    }
    report = {
        "success": False,
        "created_at": now_iso(),
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "policy": {"synthetic_tests": False, "physical_model_load_is_required": True},
    }
    try:
        import ctranslate2
        import torch
        import transformers
        import crisperwhisper

        pip_check = run_command([sys.executable, "-m", "pip", "check"], check=False)
        gpu = gpu_status()
        report.update(
            {
                "packages": {key: package_version(value) for key, value in package_names.items()},
                "imports": {
                    "torch": torch.__version__,
                    "transformers": transformers.__version__,
                    "ctranslate2": getattr(ctranslate2, "__version__", package_version("ctranslate2")),
                    "crisperwhisper": package_version("crisperwhisper"),
                },
                "pip_check": {"returncode": pip_check.returncode, "stdout": pip_check.stdout, "stderr": pip_check.stderr},
                "torch_cuda_version": torch.version.cuda,
                "cuda_available": bool(torch.cuda.is_available()),
                "gpu": gpu,
                "compute_capability": list(torch.cuda.get_device_capability(0)) if torch.cuda.is_available() else None,
                "cache_environment": configure_cache(offline=False),
                "synthetic_tensor_test": "not_run_by_user_policy",
            }
        )
        expected = {
            "crisperwhisper": "2.0.1",
            "ctranslate2": "4.8.1",
            "torch": "2.6.0+cu118",
            "transformers": "5.14.1",
            "huggingface_hub": "1.26.0",
            "numpy": "2.2.6",
            "accelerate": "1.14.0",
            "tokenizers": "0.22.2",
        }
        report["checks"] = {
            "imports": True,
            "pip_check": pip_check.returncode == 0,
            "versions": all(report["packages"].get(key) == value for key, value in expected.items()),
            "torch_cuda_11_8": torch.version.cuda == "11.8",
            "cuda_available": bool(torch.cuda.is_available()),
            "gpu_model": gpu["name"] == EXPECTED_GPU,
            "compute_capability": list(torch.cuda.get_device_capability(0)) == [6, 1] if torch.cuda.is_available() else False,
        }
        report["success"] = all(report["checks"].values())
    except Exception as error:
        report["error_type"] = type(error).__name__
        report["error_message"] = str(error)
        report["traceback"] = traceback.format_exc()
    write_json(Path(args.output), report)
    print(f"ENVIRONMENT_SUCCESS={str(report['success']).lower()}", flush=True)
    print(f"ENVIRONMENT_REPORT={Path(args.output).resolve()}", flush=True)
    if not report["success"]:
        raise RuntimeError(report.get("error_message", "Environment health check failed"))


def model_files(snapshot_path):
    records = []
    for path in sorted(Path(snapshot_path).rglob("*")):
        if not path.is_file() or ".cache" in path.parts:
            continue
        if path.is_symlink():
            raise RuntimeError(f"Model snapshot contains a symlink: {path}")
        records.append(
            {
                "path": path.relative_to(snapshot_path).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return records


def download_model(args):
    require_experiment_root(args.project_root)
    cache_environment = configure_cache(offline=False)
    snapshot_path = EXPERIMENT_ROOT / "model_cache" / "huggingface" / "models--nyralabs--CrisperWhisper2.0_medium" / MODEL_SNAPSHOT
    manifest_path = Path(args.output)
    report = {
        "success": False,
        "created_at": now_iso(),
        "repo_id": MODEL_REPO,
        "requested_revision": MODEL_SNAPSHOT,
        "snapshot_path": str(snapshot_path),
        "cache_environment": cache_environment,
    }
    try:
        from huggingface_hub import HfApi, snapshot_download

        model_info = HfApi().model_info(MODEL_REPO, revision=MODEL_SNAPSHOT)
        resolved_revision = str(model_info.sha)
        if resolved_revision != MODEL_SNAPSHOT:
            raise RuntimeError(f"Model revision mismatch: {resolved_revision}")
        snapshot_path.mkdir(parents=True, exist_ok=True)
        snapshot_download(
            repo_id=MODEL_REPO,
            revision=MODEL_SNAPSHOT,
            local_dir=str(snapshot_path),
        )
        files = model_files(snapshot_path)
        weight = next((item for item in files if item["path"] == "model.safetensors"), None)
        report.update(
            {
                "resolved_revision": resolved_revision,
                "file_count": len(files),
                "total_size_bytes": sum(item["size_bytes"] for item in files),
                "files": files,
                "temporary_files": [
                    str(path)
                    for path in snapshot_path.rglob("*")
                    if path.is_file() and re.search(r"(?i)(\.incomplete|\.partial|\.tmp)$", path.name)
                ],
                "weight": weight,
            }
        )
        report["checks"] = {
            "revision": resolved_revision == MODEL_SNAPSHOT,
            "snapshot_folder": snapshot_path.name == MODEL_SNAPSHOT,
            "file_count": len(files) == EXPECTED_MODEL_FILE_COUNT,
            "total_size": report["total_size_bytes"] == EXPECTED_MODEL_TOTAL_BYTES,
            "weight_present": weight is not None,
            "weight_hash": bool(weight and weight["sha256"] == EXPECTED_MODEL_WEIGHT_SHA256),
            "no_temporary_files": not report["temporary_files"],
        }
        report["success"] = all(report["checks"].values())
    except Exception as error:
        report["error_type"] = type(error).__name__
        report["error_message"] = str(error)
        report["traceback"] = traceback.format_exc()
    write_json(manifest_path, report)
    print(f"MODEL_DOWNLOAD_SUCCESS={str(report['success']).lower()}", flush=True)
    print(f"MODEL_MANIFEST={manifest_path.resolve()}", flush=True)
    print(f"MODEL_SNAPSHOT_PATH={snapshot_path}", flush=True)
    if not report["success"]:
        raise RuntimeError(report.get("error_message", "Model integrity check failed"))


def model_runtime_evidence(model, torch):
    candidates = [model]
    for name in ("model", "_model", "transformer", "_transformer", "network", "engine", "_engine"):
        value = getattr(model, name, None)
        if value is not None:
            candidates.append(value)
            for nested_name in ("model", "_model", "network"):
                nested_value = getattr(value, nested_name, None)
                if nested_value is not None:
                    candidates.append(nested_value)
    for candidate in candidates:
        parameters = getattr(candidate, "parameters", None)
        if not callable(parameters):
            continue
        try:
            first = next(parameters())
        except StopIteration:
            continue
        except Exception:
            continue
        return {
            "parameter_dtype": str(first.dtype),
            "parameter_device": str(first.device),
            "parameter_device_type": getattr(first.device, "type", None),
        }
    return {
        "parameter_dtype": None,
        "parameter_device": None,
        "parameter_device_type": None,
    }


def offline_load(args):
    require_experiment_root(args.project_root)
    snapshot_path = Path(args.snapshot).resolve()
    report = {
        "success": False,
        "created_at": now_iso(),
        "snapshot_path": str(snapshot_path),
        "snapshot_id": snapshot_path.name,
        "offline": True,
        "policy": {"synthetic_inference": False, "real_model_load_required": True},
    }
    try:
        cache_environment = configure_cache(offline=True)
        import torch
        from crisperwhisper import CrisperWhisperModel

        if snapshot_path.name != MODEL_SNAPSHOT or not (snapshot_path / "model.safetensors").is_file():
            raise RuntimeError("Exact local model snapshot is missing")
        torch.cuda.empty_cache()
        load_started = time.perf_counter()
        model = CrisperWhisperModel(
            str(snapshot_path),
            backend="transformers",
            device="cuda",
            compute_type="float16",
        )
        load_seconds = time.perf_counter() - load_started
        runtime = model_runtime_evidence(model, torch)
        gpu = gpu_status()
        report.update(
            {
                "cache_environment": cache_environment,
                "backend": getattr(model, "backend", "transformers"),
                "requested_device": "cuda",
                "requested_compute_type": "float16",
                "actual_runtime": runtime,
                "load_seconds": load_seconds,
                "gpu": gpu,
                "gpu_memory_allocated_mib": torch.cuda.memory_allocated(0),
                "gpu_peak_memory_allocated_mib": torch.cuda.max_memory_allocated(0),
            }
        )
        report["checks"] = {
            "snapshot": snapshot_path.name == MODEL_SNAPSHOT,
            "backend": report["backend"] == "transformers",
            "cuda_available": bool(torch.cuda.is_available()),
            "gpu_model": gpu["name"] == EXPECTED_GPU,
            "dtype": runtime["parameter_dtype"] == "torch.float16",
            "device": runtime["parameter_device_type"] == "cuda",
            "gpu_memory_allocated": report["gpu_memory_allocated_mib"] > 0,
        }
        report["success"] = all(report["checks"].values())
        del model
        torch.cuda.empty_cache()
    except Exception as error:
        report["error_type"] = type(error).__name__
        report["error_message"] = str(error)
        report["traceback"] = traceback.format_exc()
    write_json(Path(args.output), report)
    print(f"OFFLINE_LOAD_SUCCESS={str(report['success']).lower()}", flush=True)
    print(f"OFFLINE_LOAD_REPORT={Path(args.output).resolve()}", flush=True)
    if not report["success"]:
        raise RuntimeError(report.get("error_message", "Offline model load failed"))


def serialize_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    if hasattr(value, "model_dump"):
        return serialize_value(value.model_dump())
    if hasattr(value, "__dict__"):
        return {
            str(key): serialize_value(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return str(value)


def word_value(value):
    if isinstance(value, dict):
        word = value.get("word")
        start = value.get("start")
        end = value.get("end")
        probability = value.get("probability")
    else:
        word = getattr(value, "word", None)
        start = getattr(value, "start", None)
        end = getattr(value, "end", None)
        probability = getattr(value, "probability", None)
    if word is None or start is None or end is None:
        raise RuntimeError("Model returned an incomplete word timestamp")
    result = {"word": str(word), "start": float(start), "end": float(end)}
    if probability is not None:
        result["probability"] = float(probability)
    return result


def normalized_token(value):
    return "".join(re.findall(r"[a-z0-9]+", str(value).lower()))


def pathological_loops(words):
    tokens = [normalized_token(item["word"]) for item in words]
    found = []
    for size, threshold in ((1, 8), (2, 8), (3, 4), (4, 3), (5, 3)):
        index = 0
        while index + size * threshold <= len(tokens):
            ngram = tokens[index : index + size]
            if not all(ngram):
                index += 1
                continue
            repeats = 1
            while tokens[index + size * repeats : index + size * (repeats + 1)] == ngram:
                repeats += 1
            if repeats >= threshold:
                found.append({"start_word_index": index, "ngram_size": size, "repeat_count": repeats, "ngram": ngram})
                index += size * repeats
            else:
                index += 1
    return found


def timing_errors(words, audio_duration):
    errors = []
    previous_start = -1.0
    previous_end = None
    for index, word in enumerate(words):
        start = word["start"]
        end = word["end"]
        if not word["word"].strip():
            errors.append({"index": index, "reason": "empty_word"})
        if start < previous_start:
            errors.append({"index": index, "reason": "non_monotonic_start"})
        if previous_end is not None and start < previous_end - 1e-9:
            errors.append({
                "index": index,
                "reason": "overlap_with_previous_word",
                "overlap_seconds": previous_end - start,
            })
        if end < start:
            errors.append({"index": index, "reason": "end_before_start"})
        if start < -0.001 or end > audio_duration + 0.05:
            errors.append({"index": index, "reason": "outside_audio"})
        previous_start = start
        previous_end = end
    return errors


def disfluency_summary(words):
    fillers = []
    cutoffs = []
    repeats = []
    previous = None
    for index, item in enumerate(words):
        word = item["word"]
        token = normalized_token(word)
        if re.fullmatch(r"\s*\[(?:UM|UH|AH)\]\s*|\s*(?:um|uh|ah)[.,!?;:]*\s*", word, re.IGNORECASE):
            fillers.append({"index": index, "word": word})
        if re.search(r"[A-Za-z][A-Za-z']*-$", word.strip()):
            cutoffs.append({"index": index, "word": word})
        if previous and token and token == previous:
            repeats.append({"index": index, "word": word})
        previous = token
    return {
        "filler_count": len(fillers),
        "cutoff_count": len(cutoffs),
        "adjacent_repeat_count": len(repeats),
        "total_count": len(fillers) + len(cutoffs) + len(repeats),
        "fillers": fillers,
        "cutoffs": cutoffs,
        "adjacent_repeats": repeats,
    }


def compare_main_venv(args):
    preflight_report = read_json(args.preflight)
    before = preflight_report["main_venv_before"]
    after = pip_snapshot(args.main_python)
    report = {
        "success": before["pip_freeze"] == after["pip_freeze"],
        "created_at": now_iso(),
        "before": before,
        "after": after,
        "policy": {"main_venv_mutation": False},
    }
    write_json(Path(args.output), report)
    print(f"MAIN_VENV_UNCHANGED={str(report['success']).lower()}", flush=True)
    if not report["success"]:
        raise RuntimeError("Main venv package snapshot changed")


def build_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project-root", type=Path, default=EXPERIMENT_ROOT)

    preflight_parser = subparsers.add_parser("preflight", parents=[common])
    preflight_parser.add_argument("--base-python", type=Path, default=BASE_PYTHON)
    preflight_parser.add_argument("--main-python", type=Path, default=MAIN_PYTHON)
    preflight_parser.add_argument("--short-audio", type=Path, default=SHORT_AUDIO)
    preflight_parser.add_argument("--long-audio", type=Path, default=LONG_AUDIO)
    preflight_parser.add_argument("--long-video", type=Path, default=LONG_VIDEO)
    preflight_parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "output" / "crisperwhisper2_medium_setup" / "preflight.json")
    preflight_parser.set_defaults(function=preflight)

    environment_parser = subparsers.add_parser("environment", parents=[common])
    environment_parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "output" / "crisperwhisper2_medium_setup" / "environment.json")
    environment_parser.set_defaults(function=environment)

    download_parser = subparsers.add_parser("download", parents=[common])
    download_parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "output" / "crisperwhisper2_medium_setup" / "model_manifest.json")
    download_parser.set_defaults(function=download_model)

    load_parser = subparsers.add_parser("offline-load", parents=[common])
    load_parser.add_argument("--snapshot", type=Path, required=True)
    load_parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "output" / "crisperwhisper2_medium_setup" / "offline_load.json")
    load_parser.set_defaults(function=offline_load)

    compare_parser = subparsers.add_parser("compare-main-venv", parents=[common])
    compare_parser.add_argument("--preflight", type=Path, required=True)
    compare_parser.add_argument("--main-python", type=Path, default=MAIN_PYTHON)
    compare_parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "output" / "crisperwhisper2_medium_setup" / "main_venv_unchanged.json")
    compare_parser.set_defaults(function=compare_main_venv)
    return parser


def main():
    args = build_parser().parse_args()
    try:
        args.function(args)
    except Exception as error:
        print(f"ERROR_TYPE={type(error).__name__}", flush=True)
        print(f"ERROR_MESSAGE={str(error).encode('ascii', errors='backslashreplace').decode('ascii')}", flush=True)
        raise


if __name__ == "__main__":
    main()
