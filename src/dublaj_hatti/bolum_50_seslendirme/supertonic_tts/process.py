from __future__ import annotations

import os
import logging
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from uuid import uuid4

import psutil

from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import build_model_cache_env
from .process_transport import decode_result, read_json, validate_result, write_json
from .synthesis_profile import SUPERTONIC_SYNTHESIS_CONTRACT, SUPERTONIC_TOTAL_STEPS

logger = logging.getLogger("dublaj_hatti")


def terminate_worker(process: subprocess.Popen) -> None:
    try:
        children = psutil.Process(process.pid).children(recursive=True)
    except psutil.Error:
        children = []
    for child in reversed(children):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    if process.poll() is None:
        process.kill()
    process.wait()
    _, alive = psutil.wait_procs(children, timeout=5)
    if alive:
        raise RuntimeError("Supertonic worker did not exit")


def run_synthesis_request(operation: str, payload: dict, work_dir=None, timeout=None):
    request_id = uuid4().hex
    directory = Path(work_dir or os.getcwd()).resolve() / "supertonic_tts" / "process_runs" / request_id
    directory.mkdir(parents=True, exist_ok=False)
    request_path = directory / "request.json"
    parent = psutil.Process()
    request = {"schema": 1, "request_id": request_id, "contract": SUPERTONIC_SYNTHESIS_CONTRACT,
               "parent_pid": parent.pid, "parent_created": parent.create_time(), "operation": operation,
               "payload": payload}
    write_json(request_path, request)
    environment = build_model_cache_env()
    environment["PYTHONUTF8"] = "1"
    started = perf_counter()
    lifecycle = {"request_id": request_id, "operation": operation, "worker_exited": False}
    process = None
    try:
        with (directory / "stdout.log").open("w", encoding="utf-8") as stdout, (directory / "stderr.log").open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen(
                [sys.executable, "-B", str(Path(__file__).with_name("process_worker.py")), "--request", str(request_path)],
                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            lifecycle["launcher_pid"] = process.pid
            logger.info("[SUPERTONIC] Worker started operation=%s pid=%d diagnostics=%s", operation, process.pid, directory)
            try:
                process.wait(timeout=timeout)
            finally:
                if process.poll() is None:
                    terminate_worker(process)
            lifecycle["return_code"] = process.returncode
        if process.returncode != 0:
            raise RuntimeError(f"Supertonic worker failed ({process.returncode}); diagnostics: {directory}")
        response = read_json(directory / "response.json")
        if (response.get("schema"), response.get("request_id"), response.get("contract"), response.get("status")) != (
            1, request_id, SUPERTONIC_SYNTHESIS_CONTRACT, "ok",
        ):
            raise RuntimeError("Invalid Supertonic worker response")
        result = decode_result(response["result"], directory)
        validate_result(result, payload.get("segments", payload.get("voice_segments")))
        return result
    finally:
        lifecycle["elapsed_seconds"] = perf_counter() - started
        lifecycle["return_code"] = process.returncode if process is not None else None
        lifecycle["worker_exited"] = process is not None and process.poll() is not None
        if (directory / "started.json").exists():
            worker = read_json(directory / "started.json")
            lifecycle["worker_pid"] = worker["worker_pid"]
            try:
                remaining = psutil.Process(worker["worker_pid"])
                lifecycle["worker_exited"] = remaining.create_time() != worker["created"]
            except psutil.NoSuchProcess:
                lifecycle["worker_exited"] = True
        write_json(directory / "lifecycle.json", lifecycle)
        logger.info("[SUPERTONIC] Worker finished operation=%s exited=%s elapsed=%.3fs",
                    operation, lifecycle["worker_exited"], lifecycle["elapsed_seconds"])
        if process is not None and not lifecycle["worker_exited"]:
            raise RuntimeError(f"Supertonic worker remains alive; diagnostics: {directory}")


def synthesize_segments(segments, voice_id, language, work_dir=None, speed=None,
                        total_step=SUPERTONIC_TOTAL_STEPS, intra_op_threads=None,
                        inter_op_threads=None, return_actual_chunks=False):
    payload = dict(segments=segments, voice_id=voice_id, language=language,
                   work_dir=str(work_dir) if work_dir is not None else None, speed=speed,
                   total_step=total_step, intra_op_threads=intra_op_threads,
                   inter_op_threads=inter_op_threads, return_actual_chunks=return_actual_chunks)
    return run_synthesis_request("segments", payload, work_dir)


def synthesize_segments_multi_voice(segments, language, work_dir=None, speed=None,
                                    total_step=SUPERTONIC_TOTAL_STEPS, intra_op_threads=None, inter_op_threads=None):
    payload = dict(segments=segments, language=language, work_dir=str(work_dir) if work_dir is not None else None,
                   speed=speed, total_step=total_step, intra_op_threads=intra_op_threads, inter_op_threads=inter_op_threads)
    return run_synthesis_request("multi_voice", payload, work_dir)


def synthesize_single_request(segments, voice_id, language, work_dir, return_actual_chunks=True):
    return run_synthesis_request("single_request", dict(segments=segments, voice_id=voice_id, language=language,
                                 work_dir=str(work_dir), return_actual_chunks=return_actual_chunks), work_dir)


def synthesize_supertonic_voice_segments_parallel(synthesize_segments, voice_segments, voice_id, language,
                                                measure_work_dir, runtime_context=None, return_actual_chunks=False):
    return run_synthesis_request("parallel", dict(voice_segments=voice_segments, voice_id=voice_id, language=language,
                                 measure_work_dir=str(measure_work_dir), reuse_runtime=runtime_context is not None,
                                 return_actual_chunks=return_actual_chunks), measure_work_dir)
