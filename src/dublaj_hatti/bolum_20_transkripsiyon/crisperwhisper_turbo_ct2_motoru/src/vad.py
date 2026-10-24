from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class VadSettings:
    threshold: float = 0.15
    negative_threshold: float = 0.01
    minimum_speech_ms: int = 0
    minimum_silence_ms: int = 100
    speech_pad_ms: int = 600
    sample_rate: int = 16000
    frame_samples: int = 512


class SileroOnnxVad:
    def __init__(self, model_path: Path) -> None:
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 64), dtype=np.float32)
        self._sample_rate = np.array(16000, dtype=np.int64)
        self._input_audio = np.zeros((1, 576), dtype=np.float32)
        self._output_probability = np.zeros((1, 1), dtype=np.float32)
        self._next_state = np.zeros_like(self._state)
        self._binding = self._session.io_binding()
        for name, value in (
            ("input", self._input_audio),
            ("state", self._state),
            ("sr", self._sample_rate),
        ):
            self._binding.bind_cpu_input(name, value)
        for name, value in (
            ("output", self._output_probability),
            ("stateN", self._next_state),
        ):
            self._binding.bind_output(
                name,
                device_type="cpu",
                device_id=0,
                element_type=np.float32,
                shape=value.shape,
                buffer_ptr=value.ctypes.data,
            )

    def reset(self) -> None:
        self._state.fill(0.0)
        self._context.fill(0.0)

    def probability(self, frame: np.ndarray) -> float:
        self._input_audio[:, :64] = self._context
        self._input_audio[:, 64:] = np.asarray(frame, dtype=np.float32).reshape(1, 512)
        self._session.run_with_iobinding(self._binding)
        np.copyto(self._state, self._next_state)
        self._context = self._input_audio[:, -64:]
        return float(self._output_probability[0, 0])


def speech_regions(
    audio: np.ndarray,
    model_path: Path,
    settings: VadSettings,
) -> tuple[list[dict[str, int]], list[float]]:
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    model = SileroOnnxVad(model_path)
    frame = settings.frame_samples
    probabilities: list[float] = []
    for offset in range(0, len(samples), frame):
        chunk = samples[offset : offset + frame]
        if len(chunk) < frame:
            chunk = np.pad(chunk, (0, frame - len(chunk)))
        probabilities.append(model.probability(chunk))

    minimum_silence_samples = settings.sample_rate * settings.minimum_silence_ms // 1000
    minimum_speech_samples = settings.sample_rate * settings.minimum_speech_ms // 1000
    regions: list[dict[str, int]] = []
    active_start: int | None = None
    pending_end: int | None = None

    for frame_index, probability in enumerate(probabilities):
        position = frame_index * frame
        if probability >= settings.threshold:
            if active_start is None:
                active_start = position
            pending_end = None
            continue
        if active_start is None or probability >= settings.negative_threshold:
            continue
        if pending_end is None:
            pending_end = position
        if position - pending_end < minimum_silence_samples:
            continue
        end = min(pending_end, len(samples))
        if end - active_start >= minimum_speech_samples:
            regions.append({"start": active_start, "end": end})
        active_start = None
        pending_end = None

    if active_start is not None:
        end = len(samples)
        if end - active_start >= minimum_speech_samples:
            regions.append({"start": active_start, "end": end})

    pad = settings.sample_rate * settings.speech_pad_ms // 1000
    padded = [
        {
            "start": max(0, item["start"] - pad),
            "end": min(len(samples), item["end"] + pad),
            "core_start": item["start"],
            "core_end": item["end"],
        }
        for item in regions
    ]
    merged: list[dict[str, int]] = []
    for item in padded:
        if not merged or item["start"] > merged[-1]["end"]:
            merged.append(dict(item))
        else:
            merged[-1]["end"] = max(merged[-1]["end"], item["end"])
            merged[-1]["core_end"] = item["core_end"]
    if not merged:
        raise RuntimeError("Silero VAD did not find a speech region")
    return merged, probabilities


def compact_audio(
    audio: np.ndarray,
    regions: list[dict[str, int]],
    sample_rate: int,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    parts: list[np.ndarray] = []
    compact_spans: list[dict[str, Any]] = []
    compact_cursor = 0
    for region_index, region in enumerate(regions):
        source_start = int(region["start"])
        source_end = int(region["end"])
        if source_end <= source_start:
            continue
        part = samples[source_start:source_end]
        parts.append(part)
        compact_end = compact_cursor + len(part)
        compact_spans.append(
            {
                "region_index": region_index,
                "compact_start_sample": compact_cursor,
                "compact_end_sample": compact_end,
                "original_start_sample": source_start,
                "original_end_sample": source_end,
                "core_start_sample": int(region["core_start"]),
                "core_end_sample": int(region["core_end"]),
            }
        )
        compact_cursor = compact_end
    if not parts:
        raise RuntimeError("Silero VAD speech regions produced an empty compact timeline")
    return np.concatenate(parts), compact_spans
