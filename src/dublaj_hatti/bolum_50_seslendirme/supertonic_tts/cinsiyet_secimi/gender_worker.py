# -*- coding: utf-8 -*-
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

MODEL_ID = "alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech"
SAMPLE_RATE = 16000
MAX_AUDIO_SECONDS = 30.0


def run_gender_worker(audio_path: str, requests: list[dict], mode: str) -> dict:
    from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import build_model_cache_env

    request = {
        "schema_version": 1,
        "audio_path": str(audio_path),
        "mode": str(mode),
        "requests": requests,
    }
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
    ]
    started_at_utc = datetime.now(timezone.utc).isoformat()
    started = perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(Path(__file__).resolve().parents[5]),
        env=build_model_cache_env(),
        shell=False,
        input=json.dumps(request, ensure_ascii=True, separators=(",", ":")),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    elapsed_seconds = round(perf_counter() - started, 6)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "worker failed").strip()
        raise RuntimeError(f"Supertonic gender worker failed (exit={completed.returncode}): {detail}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("Supertonic gender worker result JSON invalid") from error
    if not isinstance(result, dict) or result.get("schema_version") != 1:
        raise RuntimeError("Supertonic gender worker result contract invalid")
    result["returncode"] = completed.returncode
    result["subprocess_started_at_utc"] = started_at_utc
    result["subprocess_elapsed_seconds"] = elapsed_seconds
    result["process_exit_observed"] = completed.returncode is not None
    return result


def _predict_requests(payload: dict) -> dict:
    src_root = Path(__file__).resolve().parents[4]
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.cinsiyet_secimi.audio_slicer import (
        slice_segment_audio,
    )
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.cinsiyet_secimi.gender_classifier import (
        predict_segment_gender,
    )

    audio_path = str(payload["audio_path"])
    mode = str(payload.get("mode") or "segment")
    predictions = []
    timings = {"gender_model_load": 0.0, "gender_inference": 0.0}
    max_samples = int(MAX_AUDIO_SECONDS * SAMPLE_RATE)
    for request in payload.get("requests") or []:
        item = {"request_id": str(request.get("request_id") or "")}
        try:
            clips = []
            segment_errors = []
            if mode == "speaker":
                collected_samples = 0
                for segment in request.get("segments") or []:
                    if collected_samples >= max_samples:
                        break
                    try:
                        start = float(segment["start"])
                        end = float(segment["end"])
                        clip = slice_segment_audio(audio_path, start, end)
                        remaining_samples = max_samples - collected_samples
                        if clip.shape[1] > remaining_samples:
                            clip = clip[:, :remaining_samples]
                        clips.append(clip)
                        collected_samples += int(clip.shape[1])
                    except Exception as error:
                        segment_errors.append(
                            {
                                "segment_index": int(segment.get("segment_index", -1)),
                                "error": str(error),
                            }
                        )
            else:
                clips.append(
                    slice_segment_audio(
                        audio_path,
                        float(request["start"]),
                        float(request["end"]),
                    )
                )
            if not clips:
                raise ValueError("gender worker audio request empty")
            import torch

            audio = clips[0] if len(clips) == 1 else torch.cat(clips, dim=1)
            if mode == "speaker" and audio.shape[1] > max_samples:
                audio = audio[:, :max_samples]

            def timing_callback(stage: str, **details) -> None:
                if stage.endswith("_completed") and "elapsed_seconds" in details:
                    key = stage.removesuffix("_completed")
                    if key in timings:
                        timings[key] += float(details["elapsed_seconds"])

            prediction = predict_segment_gender(audio, timing_callback=timing_callback)
            item.update(
                {
                    "gender": str(prediction.gender),
                    "confidence": round(float(prediction.confidence), 6),
                    "segment_errors": segment_errors,
                }
            )
        except Exception as error:
            item.update({"gender": "unknown", "confidence": 0.0, "error": str(error)})
        predictions.append(item)
    return {
        "schema_version": 1,
        "mode": mode,
        "model_id": MODEL_ID,
        "sample_rate": SAMPLE_RATE,
        "max_audio_seconds": MAX_AUDIO_SECONDS if mode == "speaker" else None,
        "worker_pid": os.getpid(),
        "timings_seconds": {key: round(value, 6) for key, value in timings.items()},
        "predictions": predictions,
    }


def _main() -> int:
    try:
        payload = json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr):
            result = _predict_requests(payload)
        sys.stdout.write(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
        sys.stdout.write("\n")
        return 0
    except Exception as error:
        sys.stdout.write(
            json.dumps(
                {
                    "schema_version": 1,
                    "mode": str(payload.get("mode") if "payload" in locals() else ""),
                    "model_id": MODEL_ID,
                    "sample_rate": SAMPLE_RATE,
                    "max_audio_seconds": (
                        MAX_AUDIO_SECONDS
                        if "payload" in locals() and payload.get("mode") == "speaker"
                        else None
                    ),
                    "predictions": [],
                    "worker_error": str(error),
                },
                ensure_ascii=True,
                separators=(",", ":"),
            )
        )
        sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())
