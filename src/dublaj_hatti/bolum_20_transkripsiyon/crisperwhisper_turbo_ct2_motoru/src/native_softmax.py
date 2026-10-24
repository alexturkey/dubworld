from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


implementation = "softmax_packed_256_v1"
kernel_policy = {"kernel": "softmax_packed_256", "variant": 2, "thread_cap": 256}
preload_marker = "DUBLAJ_CT2_NATIVE_PRELOADED"
source_names = {"softmax_shim.c", "softmax.ptx", "softmax_padded.cu", "softmax_packed.cu"}


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def owned_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise RuntimeError("Native Softmax path escapes motor root")
    return path


def verified_manifest(root: Path) -> dict:
    path = root / "config/native_softmax.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("implementation") != implementation:
        raise RuntimeError("Native Softmax manifest identity mismatch")
    if manifest.get("compute_capability") != [6, 1]:
        raise RuntimeError("Native Softmax compute capability policy mismatch")
    if any(type(manifest.get(key)) is not type(value) or manifest[key] != value for key, value in kernel_policy.items()):
        raise RuntimeError("Native Softmax kernel policy mismatch")
    if set(manifest.get("sources", {})) != source_names:
        raise RuntimeError("Native Softmax source set mismatch")
    for name, expected in manifest["sources"].items():
        if digest(root / "src/native" / name) != expected:
            raise RuntimeError(f"Native Softmax source SHA256 mismatch: {name}")
    if digest(owned_path(root, manifest["native_relative_path"])) != manifest["native_sha256"]:
        raise RuntimeError("Native Softmax CTranslate2 ABI SHA256 mismatch")
    return manifest


def ensure_compiled(root: Path, manifest: dict) -> Path:
    import fcntl

    directory = root / "runtime_cache/native_softmax" / manifest["shim_sha256"]
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / "softmax.so"
    with (directory / "build.lock").open("a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if destination.exists():
            if digest(destination) != manifest["shim_sha256"]:
                raise RuntimeError("Native Softmax installed shim SHA256 mismatch")
            return destination
        temporary = directory / f"softmax.{os.getpid()}.tmp.so"
        try:
            subprocess.run(
                ["cc", "-std=c11", "-O2", "-shared", "-fPIC", "-Wall", "-Wextra", "-Werror",
                 str(root / "src/native/softmax_shim.c"), "-ldl", "-o", str(temporary)],
                check=True, capture_output=True, text=True, encoding="utf-8", timeout=60,
            )
            if digest(temporary) != manifest["shim_sha256"]:
                raise RuntimeError("Native Softmax compiler output differs from validated shim")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return destination


def preload_environment(shim_path: Path, manifest: dict, environment: dict) -> dict:
    inherited = environment.get("LD_PRELOAD", "")
    if inherited and inherited != str(shim_path):
        raise RuntimeError("Native Softmax conflicting LD_PRELOAD")
    result = environment.copy()
    result["LD_PRELOAD"] = str(shim_path)
    result[preload_marker] = manifest["shim_sha256"]
    return result


def bootstrap(root: Path, entry: Path) -> None:
    if sys.platform != "linux":
        raise RuntimeError("Native Softmax requires the motor WSL Linux runtime")
    manifest = verified_manifest(root)
    shim_path = ensure_compiled(root, manifest)
    environment = preload_environment(shim_path, manifest, os.environ)
    if os.environ.get(preload_marker) != manifest["shim_sha256"]:
        os.execve(sys.executable, [sys.executable, "-B", str(entry), *sys.argv[1:]], environment)
    if os.environ.get("LD_PRELOAD") != str(shim_path):
        raise RuntimeError("Native Softmax preload marker has no matching library")
    if not hasattr(ctypes.CDLL(None), "ct2_softmax_prepare"):
        raise RuntimeError("Native Softmax preload was not loaded by the process loader")


class NativeSoftmax:
    def __init__(self, root: Path):
        self.root = root
        self.shim = None
        self.prepared = False
        self.prepare_seconds = 0.0
        self.manifest = None

    def prepare(self) -> None:
        started = time.perf_counter()
        if self.prepared:
            raise RuntimeError("Native Softmax was already prepared")
        self.manifest = verified_manifest(self.root)
        shim_path = self.root / "runtime_cache/native_softmax" / self.manifest["shim_sha256"] / "softmax.so"
        if os.environ.get(preload_marker) != self.manifest["shim_sha256"] or os.environ.get("LD_PRELOAD") != str(shim_path):
            raise RuntimeError("Native Softmax worker must start through worker_entry.py")
        self.native_library = ctypes.CDLL(str(owned_path(self.root, self.manifest["native_relative_path"])), mode=ctypes.RTLD_GLOBAL)
        self.driver = ctypes.CDLL("libcuda.so.1", mode=ctypes.RTLD_GLOBAL)
        capability = self.driver.cuDeviceComputeCapability
        capability.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.c_int]
        capability.restype = ctypes.c_int
        major, minor = ctypes.c_int(), ctypes.c_int()
        if capability(ctypes.byref(major), ctypes.byref(minor), 0) != 0:
            raise RuntimeError("Native Softmax GPU capability could not be verified")
        if [major.value, minor.value] != self.manifest["compute_capability"]:
            raise RuntimeError("Native Softmax GPU architecture is not validated")
        self.shim = ctypes.CDLL(None)
        self.shim.ct2_softmax_prepare.argtypes = [ctypes.c_char_p]
        self.shim.ct2_softmax_prepare.restype = None
        self.shim.ct2_softmax_select.argtypes = [ctypes.c_uint]
        self.shim.ct2_softmax_select.restype = None
        self.shim.ct2_softmax_close.argtypes = []
        self.shim.ct2_softmax_close.restype = None
        for name in ("ct2_softmax_changed", "ct2_softmax_fallback"):
            function = getattr(self.shim, name)
            function.argtypes = []
            function.restype = ctypes.c_ulong
        self.shim.ct2_softmax_prepare(str(self.root / "src/native/softmax.ptx").encode("utf-8"))
        self.shim.ct2_softmax_select(self.manifest["variant"])
        self.prepared = True
        self.prepare_seconds = time.perf_counter() - started

    def evidence(self) -> dict:
        if not self.prepared:
            raise RuntimeError("Native Softmax has not been prepared")
        changed = self.shim.ct2_softmax_changed()
        if changed <= 0:
            raise RuntimeError("Native Softmax did not execute")
        return {
            "implementation": implementation,
            **kernel_policy,
            "manifest_sha256": digest(self.root / "config/native_softmax.json"),
            "native_sha256": self.manifest["native_sha256"],
            "ptx_sha256": self.manifest["sources"]["softmax.ptx"],
            "shim_sha256": self.manifest["shim_sha256"],
            "compute_capability": self.manifest["compute_capability"],
            "changed_calls": changed,
            "fallback_calls": self.shim.ct2_softmax_fallback(),
            "prepare_seconds": self.prepare_seconds,
            "transcript_cache": False,
            "scope": "unmasked_nonlog_float32_gpu_softmax_width_1_to_2048",
        }

    def close(self) -> None:
        if self.prepared:
            self.shim.ct2_softmax_close()
            self.prepared = False
