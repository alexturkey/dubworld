from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import sys
from threading import Event, Thread
from time import perf_counter
import traceback

import psutil


def watch_parent(parent_pid: int, parent_created: float, finished: Event) -> None:
    while not finished.wait(0.25):
        try:
            parent = psutil.Process(parent_pid)
            if parent.create_time() == parent_created and parent.is_running():
                continue
        except psutil.Error:
            pass
        os._exit(72)


def dispatch(operation: str, payload: dict):
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts import engine, parallel

    if operation == "segments":
        return engine.synthesize_segments(**payload)
    if operation == "multi_voice":
        return engine.synthesize_segments_multi_voice(**payload)
    if operation == "single_request":
        params = dict(payload)
        segments = params.pop("segments")
        work_dir = params.pop("work_dir")
        return_actual_chunks = params.pop("return_actual_chunks")
        return engine.SupertonicSegmentSynthesizer(**params).synthesize_segments(
            segments, work_dir=work_dir, return_actual_chunks=return_actual_chunks,
        )
    if operation == "parallel":
        params = dict(payload)
        reuse = params.pop("reuse_runtime")
        return parallel.synthesize_supertonic_voice_segments_parallel(
            engine.synthesize_segments,
            runtime_context=parallel.SupertonicRuntimeContext() if reuse else None,
            **params,
        )
    raise ValueError("Unknown Supertonic worker operation")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    args = parser.parse_args()
    request_path = Path(args.request).resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    finished = Event()
    Thread(target=watch_parent, args=(request["parent_pid"], request["parent_created"], finished), daemon=True).start()
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.process_transport import encode_result, validate_result, write_json
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.synthesis_profile import SUPERTONIC_SYNTHESIS_CONTRACT

    directory = request_path.parent
    started = perf_counter()
    response = {"schema": 1, "request_id": request["request_id"], "contract": SUPERTONIC_SYNTHESIS_CONTRACT,
                "worker_pid": os.getpid()}
    write_json(directory / "started.json", {"worker_pid": os.getpid(), "created": psutil.Process().create_time()})
    try:
        if request["schema"] != 1 or request["contract"] != SUPERTONIC_SYNTHESIS_CONTRACT:
            raise ValueError("Supertonic worker contract mismatch")
        result = dispatch(request["operation"], request["payload"])
        segments = request["payload"].get("segments", request["payload"].get("voice_segments"))
        validate_result(result, segments)
        response.update(status="ok", result=encode_result(result, directory))
    except Exception as error:
        response.update(status="error", error_type=type(error).__name__, error=str(error))
        traceback.print_exc()
    response["elapsed_seconds"] = perf_counter() - started
    response["memory"] = psutil.Process().memory_info()._asdict()
    write_json(directory / "response.json", response)
    finished.set()
    return 0 if response["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
