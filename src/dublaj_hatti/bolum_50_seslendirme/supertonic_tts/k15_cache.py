import hashlib
import json
import os
import platform
import tempfile
import time
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from threading import Lock

from .synthesis_profile import get_supertonic_synthesis_profile


cache_thread_lock = Lock()


@lru_cache(maxsize=32)
def cached_file_hash(path, size, mtime_ns):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_hash(path):
    stat = path.stat()
    return cached_file_hash(str(path.resolve()), stat.st_size, stat.st_mtime_ns)


@contextmanager
def cache_process_lock(path, timeout_seconds=60):
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Supertonic K15 cache lock timeout")
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def cache_identity(runtime, source):
    return {
        "schema_version": 1,
        "source_sha256": file_hash(source),
        "runtime": runtime.optimized_cache_metadata(source),
        "recipe": get_supertonic_synthesis_profile(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }


def cache_is_valid(path, manifest_path, identity):
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return (
            manifest.get("identity") == identity
            and path.stat().st_size > 0
            and manifest.get("sha256") == file_hash(path)
        )
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def build_vector_cache(runtime, source, path, manifest_path, identity):
    import onnx
    import onnxruntime as ort

    from .k15_solver import prepare_k15_vector_model

    with tempfile.TemporaryDirectory(prefix="k15_build_", dir=path.parent) as directory:
        staging = Path(directory)
        staged_model = staging / "vector.onnx"
        options = runtime.create_session_options(runtime.intra_op_threads, runtime.inter_op_threads)
        options.optimized_model_filepath = str(staged_model)
        model = prepare_k15_vector_model(onnx.load(str(source)))
        session = ort.InferenceSession(
            model.SerializeToString(), sess_options=options, providers=["CPUExecutionProvider"],
        )
        del session, model
        if not staged_model.is_file() or staged_model.stat().st_size == 0:
            raise RuntimeError("Supertonic K15 optimized model was not written")
        manifest = {"identity": identity, "sha256": file_hash(staged_model)}
        staged_manifest = staging / "manifest.json"
        staged_manifest.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        os.replace(staged_model, path)
        os.replace(staged_manifest, manifest_path)


def create_cached_k15_vector_session(runtime):
    source = runtime.onnx_dir / "vector_estimator.onnx"
    with cache_thread_lock:
        identity = cache_identity(runtime, source)
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()[:24]
        directory = runtime.cache_dir / "k15_vector" / key
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "vector_cfg5.onnx"
        manifest_path = directory / "manifest.json"
        with cache_process_lock(directory / "build.lock"):
            if not cache_is_valid(path, manifest_path, identity):
                build_vector_cache(runtime, source, path, manifest_path, identity)
    return runtime.load_cached_session(path)
