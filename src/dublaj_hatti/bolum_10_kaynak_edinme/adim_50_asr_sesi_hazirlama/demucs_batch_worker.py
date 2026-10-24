import argparse
import gc
import json
import math
import time
from pathlib import Path

import torch
import torchaudio

from demucs.apply import BagOfModels, TensorChunk
from demucs.audio import prevent_clip
from demucs.pretrained import get_model
from demucs.separate import load_track
from demucs.utils import center_trim


def _load_single_model(model_name: str):
    model = get_model(model_name)
    if isinstance(model, BagOfModels):
        expected_weights = [[1.0] * len(model.sources)]
        if len(model.models) != 1 or model.weights != expected_weights:
            raise RuntimeError("Demucs batch worker tek modelli paket gerektirir")
        model = model.models[0]
    model.cpu()
    model.eval()
    return model


def _progress_printer(completed: int, total: int) -> None:
    percent = min(100, int(completed * 100 / max(1, total)))
    print(f"Demucs batch progress: {percent}%", flush=True)


def _required_chunk_output(
    chunk_output: torch.Tensor,
    vocals_index: int,
) -> torch.Tensor:
    vocals = chunk_output[:, vocals_index:vocals_index + 1]
    non_vocal_indexes = [
        index for index in range(chunk_output.shape[1]) if index != vocals_index
    ]
    no_vocals = chunk_output[:, non_vocal_indexes].sum(dim=1, keepdim=True)
    return torch.cat((vocals, no_vocals), dim=1)


def _split_batched(model, mix: torch.Tensor, batch_size: int, overlap: float):
    if batch_size < 1:
        raise ValueError(f"Gecersiz Demucs batch boyutu: {batch_size}")
    if not 0 <= overlap < 1:
        raise ValueError(f"Gecersiz Demucs overlap: {overlap}")
    device = torch.device("cuda")
    model.to(device)
    model.eval()
    batch, channels, length = mix.shape
    segment_length = int(model.samplerate * model.segment)
    stride = int((1 - overlap) * segment_length)
    offsets = list(range(0, length, stride))
    weight = torch.cat(
        [
            torch.arange(1, segment_length // 2 + 1, device=device),
            torch.arange(segment_length - segment_length // 2, 0, -1, device=device),
        ]
    )
    weight = weight / weight.max()
    weight_cpu = weight.to(mix.device)
    output = torch.zeros(batch, 2, channels, length, device=mix.device)
    sum_weight = torch.zeros(length, device=mix.device)
    vocals_index = model.sources.index("vocals")
    group_total = math.ceil(len(offsets) / batch_size)
    with torch.inference_mode():
        for group_index, group_start in enumerate(range(0, len(offsets), batch_size), start=1):
            group_offsets = offsets[group_start:group_start + batch_size]
            chunks = [TensorChunk(mix, offset, segment_length) for offset in group_offsets]
            padded = torch.cat(
                [chunk.padded(model.valid_length(chunk.length)) for chunk in chunks],
                dim=0,
            ).to(device)
            group_output = model(padded)
            for item_index, (offset, chunk) in enumerate(zip(group_offsets, chunks)):
                chunk_output = center_trim(
                    group_output[item_index:item_index + 1],
                    chunk.length,
                )
                required_output = _required_chunk_output(chunk_output, vocals_index)
                chunk_length = required_output.shape[-1]
                output[..., offset:offset + segment_length] += (
                    weight[:chunk_length] * required_output
                ).to(mix.device)
                sum_weight[offset:offset + segment_length] += weight_cpu[:chunk_length]
            del padded, group_output
            _progress_printer(group_index, group_total)
    if torch.any(sum_weight <= 0):
        raise RuntimeError("Demucs batch gecis agirligi bos aralik birakti")
    output /= sum_weight
    allocation = {
        "output_stem_count": output.shape[1],
        "output_accumulator_bytes": output.numel() * output.element_size(),
        "sum_weight_bytes": sum_weight.numel() * sum_weight.element_size(),
        "input_mix_bytes": mix.numel() * mix.element_size(),
    }
    del sum_weight, weight_cpu, weight
    return output, allocation


def _separate_with_oom_fallback(
    model,
    mix: torch.Tensor,
    requested_batch_size: int,
    overlap: float,
):
    try:
        torch.cuda.reset_peak_memory_stats()
        sources, allocation = _split_batched(model, mix, requested_batch_size, overlap)
        torch.cuda.synchronize()
        return sources, allocation, requested_batch_size, False
    except torch.cuda.OutOfMemoryError:
        if requested_batch_size <= 1:
            raise
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        print("Demucs batch CUDA OOM: batch_size=1 ile tekrar deneniyor", flush=True)
        sources, allocation = _split_batched(model, mix, 1, overlap)
        torch.cuda.synchronize()
        return sources, allocation, 1, True


def _prepare_and_write_wav(
    wav: torch.Tensor,
    path: Path,
    samplerate: int,
) -> dict:
    prepare_started = time.perf_counter()
    prepared = prevent_clip(wav, mode="rescale")
    prepare_seconds = time.perf_counter() - prepare_started
    write_started = time.perf_counter()
    torchaudio.save(
        str(path),
        prepared,
        sample_rate=samplerate,
        encoding="PCM_S",
        bits_per_sample=16,
    )
    write_seconds = time.perf_counter() - write_started
    del prepared
    return {
        "prepare_seconds": prepare_seconds,
        "write_seconds": write_seconds,
    }


def _save_two_stems(model, sources: torch.Tensor, output_dir: Path) -> tuple[dict, dict]:
    if sources.ndim != 3 or sources.shape[0] != 2:
        raise ValueError(f"Demucs iki-stem ciktisi gecersiz: shape={tuple(sources.shape)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    timings = {}
    vocals_path = output_dir / "vocals.wav"
    no_vocals_path = output_dir / "no_vocals.wav"
    vocals_timing = _prepare_and_write_wav(
        sources[0],
        vocals_path,
        model.samplerate,
    )
    no_vocals_timing = _prepare_and_write_wav(
        sources[1],
        no_vocals_path,
        model.samplerate,
    )
    timings["vocals_prepare_seconds"] = vocals_timing["prepare_seconds"]
    timings["vocals_write_seconds"] = vocals_timing["write_seconds"]
    timings["no_vocals_prepare_seconds"] = no_vocals_timing["prepare_seconds"]
    timings["no_vocals_write_seconds"] = no_vocals_timing["write_seconds"]
    outputs = {
        "vocals": str(vocals_path),
        "no_vocals": str(no_vocals_path),
    }
    return outputs, timings


def run_worker(
    input_path: Path,
    output_root: Path,
    model_name: str,
    batch_size: int,
    overlap: float,
) -> dict:
    started = time.perf_counter()
    timings = {}
    model_started = time.perf_counter()
    model = _load_single_model(model_name)
    timings["model_load_seconds"] = time.perf_counter() - model_started

    audio_started = time.perf_counter()
    wav = load_track(input_path, model.audio_channels, model.samplerate)
    timings["audio_load_seconds"] = time.perf_counter() - audio_started
    reference = wav.mean(0)
    normalize_started = time.perf_counter()
    reference_mean = reference.mean()
    reference_std = reference.std()
    wav -= reference_mean
    wav /= reference_std
    del reference
    timings["normalize_seconds"] = time.perf_counter() - normalize_started

    inference_started = time.perf_counter()
    sources, allocation, actual_batch_size, oom_fallback = _separate_with_oom_fallback(
        model,
        wav[None],
        batch_size,
        overlap,
    )
    timings["inference_seconds"] = time.perf_counter() - inference_started
    peak_memory_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
    sources = sources[0]
    del wav

    denormalize_started = time.perf_counter()
    sources[0] *= reference_std
    sources[0] += reference_mean
    non_vocal_count = len(model.sources) - 1
    sources[1] *= reference_std
    sources[1] += non_vocal_count * reference_mean
    del reference_mean, reference_std
    timings["denormalize_seconds"] = time.perf_counter() - denormalize_started

    output_dir = output_root / model_name / input_path.stem
    save_started = time.perf_counter()
    outputs, save_timings = _save_two_stems(model, sources, output_dir)
    timings.update(save_timings)
    timings["save_total_seconds"] = time.perf_counter() - save_started
    timings["save_seconds"] = timings["save_total_seconds"]

    cleanup_started = time.perf_counter()
    del sources, model
    gc.collect()
    torch.cuda.empty_cache()
    timings["explicit_cleanup_seconds"] = time.perf_counter() - cleanup_started
    timings["total_seconds"] = time.perf_counter() - started
    report = {
        "input": str(input_path),
        "output_root": str(output_root),
        "model": model_name,
        "overlap": overlap,
        "shifts": 0,
        "requested_batch_size": batch_size,
        "actual_batch_size": actual_batch_size,
        "oom_fallback": oom_fallback,
        "output_mode": "two_stems",
        "timings": {key: round(value, 3) for key, value in timings.items()},
        "allocation": allocation,
        "peak_torch_cuda_memory_mb": round(peak_memory_mb, 3),
        "outputs": outputs,
    }
    report_path = output_root / "demucs_batch_report.json"
    with open(report_path, "w", encoding="utf-8") as report_file:
        json.dump(report, report_file, ensure_ascii=False, indent=2)
        report_file.write("\n")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--model", default="htdemucs")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--overlap", type=float, default=0.25)
    args = parser.parse_args()
    run_worker(
        Path(args.input),
        Path(args.output_root),
        args.model,
        args.batch_size,
        args.overlap,
    )


if __name__ == "__main__":
    main()
