from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np

MODEL_CACHE_ENV = "DUBLAJ_3D_SPEAKER_MODEL_CACHE_DIR"
# Voice activity detection is Silero VAD from faster-whisper (no separate model files; see vendor infer_diarization.py).
MODEL_REQUIREMENTS = (
    {
        "model_id": "iic/speech_campplus_sv_zh_en_16k-common_advanced",
        "revision": "v1.0.0",
        "required_files": ("configuration.json", "config.yaml", "campplus_cn_en_common.pt"),
        "expected_files": {
            "configuration.json": {
                "size_bytes": 587,
                "sha256": "d1ae364ff71e84ef5918ba30b0f8c2f28d2fdfdac4003b60ce0877b3f4630048",
            },
            "config.yaml": {
                "size_bytes": 537,
                "sha256": "17342041bd5b22f6fd7e32f6e7a267b0bf65f018c0a721bada6547e3d28fbfc9",
            },
            "campplus_cn_en_common.pt": {
                "size_bytes": 28044640,
                "sha256": "92f29b94e6948786a26778c9e302525d185bb08c8b9f5252ed98776902840199",
            },
        },
    },
)


class ModelPreparationError(RuntimeError):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category


class WorkerStageError(RuntimeError):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_model_cache_root() -> Path:
    explicit = str(os.getenv(MODEL_CACHE_ENV, "") or "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    src_root = Path(__file__).resolve().parents[4]
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import modelscope_model_cache_root

    return modelscope_model_cache_root().resolve()


def inspect_cached_model(cache_root: Path, requirement: dict) -> dict:
    model_dir = cache_root / Path(requirement["model_id"])
    files = []
    errors = []
    for relative_name in requirement["required_files"]:
        path = model_dir / relative_name
        item = {"name": relative_name, "exists": path.is_file()}
        if path.is_file():
            expected = requirement["expected_files"][relative_name]
            size_bytes = path.stat().st_size
            item["size_bytes"] = size_bytes
            item["expected_size_bytes"] = expected["size_bytes"]
            item["size_valid"] = size_bytes == expected["size_bytes"]
            if size_bytes <= 0:
                errors.append(f"empty file: {relative_name}")
            else:
                sha256 = _sha256(path)
                item["sha256"] = sha256
                item["expected_sha256"] = expected["sha256"]
                item["sha256_valid"] = sha256 == expected["sha256"]
            if not item["size_valid"]:
                errors.append(
                    f"size mismatch: {relative_name} expected={expected['size_bytes']} actual={size_bytes}"
                )
            if size_bytes > 0 and not item["sha256_valid"]:
                errors.append(f"sha256 mismatch: {relative_name}")
            if relative_name == "configuration.json":
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                    item["json_valid"] = True
                except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                    item["json_valid"] = False
                    errors.append(f"invalid configuration.json: {type(exc).__name__}: {exc}")
        else:
            errors.append(f"missing file: {relative_name}")
        files.append(item)
    revision_path = model_dir / ".mv"
    cached_revision = ""
    if revision_path.is_file():
        cached_revision = revision_path.read_text(encoding="utf-8", errors="replace").strip()
    return {
        "model_id": requirement["model_id"],
        "requested_revision": requirement["revision"],
        "cached_revision_metadata": cached_revision,
        "model_dir": str(model_dir),
        "files": files,
        "valid": not errors,
        "validation_errors": errors,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _append_progress(path: Path, stage: str, **details) -> None:
    payload = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "stage": stage,
    }
    payload.update(details)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def read_progress_timings(path: Path) -> dict[str, float]:
    timings: dict[str, float] = {}
    if not path.is_file():
        return timings
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        stage = str(item.get("stage") or "")
        if stage == "vendor_import_started" and "elapsed_since_subprocess_start_seconds" in item:
            timings["subprocess_start_to_vendor_import"] = float(
                item["elapsed_since_subprocess_start_seconds"]
            )
        elif stage.endswith("_completed") and "elapsed_seconds" in item:
            timings[stage.removesuffix("_completed")] = float(item["elapsed_seconds"])
    return timings


def download_required_model(requirement: dict, cache_root: Path, evidence_dir: Path) -> str:
    if os.environ.get("HF_HUB_OFFLINE") == "1" and os.environ.get("DUBLAJ_CEVRIMICI") != "1":
        raise RuntimeError(
            f"Konuşmacı modeli eksik ya da bozuk: {requirement['model_id']}. "
            "Kurulum: scripts/kur.ps1 -Adim modeller (çalışma anında indirme kapalı; açmak için DUBLAJ_CEVRIMICI=1)"
        )
    from modelscope.hub.snapshot_download import snapshot_download

    src_root = Path(__file__).resolve().parents[4]
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from dublaj_hatti.bolum_00_omurga.runtime.internet_gateway import run_with_internet_gateway

    return run_with_internet_gateway(
        lambda _route: snapshot_download(
            requirement["model_id"],
            revision=requirement["revision"],
            cache_dir=str(cache_root),
        ),
        operation_name=f"3d_speaker_model_download:{requirement['model_id']}",
        evidence_dir=evidence_dir,
    )


def repair_model_cache_after_load_failure(
    cache_root: Path,
    diagnostic_path: Path,
    initial_load_error: Exception,
) -> dict:
    report = {
        "schema_version": 1,
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "cache_root": str(cache_root),
        "network_attempted": False,
        "validation_performed": True,
        "repair_performed": False,
        "initial_load_error_type": type(initial_load_error).__name__,
        "initial_load_error_message": str(initial_load_error),
        "models": [],
        "status": "diagnosing_after_direct_load_failure",
    }
    try:
        local_reports = [inspect_cached_model(cache_root, item) for item in MODEL_REQUIREMENTS]
        report["models"] = local_reports
        invalid_requirements = [
            requirement
            for requirement, model_report in zip(MODEL_REQUIREMENTS, local_reports, strict=True)
            if not model_report["valid"]
        ]
        if not invalid_requirements:
            report["status"] = "local_files_valid_load_failed"
            report["model_source"] = "local_cache"
            return report

        report["network_attempted"] = True
        report["status"] = "downloading_missing_or_invalid_models"
        _write_json(diagnostic_path, report)
        for requirement in invalid_requirements:
            try:
                download_required_model(requirement, cache_root, diagnostic_path.parent)
            except Exception as exc:
                raise ModelPreparationError(
                    "model_download_failed",
                    f"model={requirement['model_id']} revision={requirement['revision']} "
                    f"error={type(exc).__name__}: {exc}",
                ) from exc

        report["models"] = [inspect_cached_model(cache_root, item) for item in MODEL_REQUIREMENTS]
        invalid_after_download = [item for item in report["models"] if not item["valid"]]
        if invalid_after_download:
            details = "; ".join(
                f"{item['model_id']}: {', '.join(item['validation_errors'])}"
                for item in invalid_after_download
            )
            raise ModelPreparationError("local_model_invalid_after_download", details)
        report["status"] = "ready_for_single_retry"
        report["model_source"] = "downloaded_or_repaired_cache"
        report["repair_performed"] = True
        return report
    except Exception as exc:
        report["status"] = "failed"
        report["error_category"] = getattr(exc, "category", "model_cache_check_failed")
        report["error_type"] = type(exc).__name__
        report["error_message"] = str(exc)
        raise
    finally:
        _write_json(diagnostic_path, report)


def use_deterministic_local_model_paths(vendor_module) -> None:
    def resolve_local_model(model_id, model_revision=None, cache_dir=None):
        if not cache_dir:
            raise RuntimeError("3D-Speaker deterministic local cache root is missing")
        return str(Path(cache_dir) / Path(model_id))

    vendor_module.download_model_from_modelscope = resolve_local_model


def construct_diarization(vendor_module, model_cache_root: Path, progress_path: Path):
    return vendor_module.Diarization3Dspeaker(
        device=None,
        speaker_num=None,
        model_cache_dir=str(model_cache_root),
        progress_callback=lambda stage, **details: _append_progress(progress_path, stage, **details),
    )


def load_diarization_with_local_repair(vendor_module, diagnostic_path: Path, progress_path: Path):
    model_cache_root = resolve_model_cache_root()
    use_deterministic_local_model_paths(vendor_module)
    _append_progress(
        progress_path,
        "direct_local_model_load_started",
        cache_root=str(model_cache_root),
    )
    try:
        diarization = construct_diarization(vendor_module, model_cache_root, progress_path)
    except Exception as initial_error:
        _append_progress(
            progress_path,
            "direct_local_model_load_failed",
            error_type=type(initial_error).__name__,
            error_message=str(initial_error),
        )
        model_report = repair_model_cache_after_load_failure(
            model_cache_root,
            diagnostic_path,
            initial_error,
        )
        if not model_report["repair_performed"]:
            raise ModelPreparationError(
                "model_load_failed_local_files_valid",
                "model_load_failed_local_files_valid: deterministic local model load failed "
                "but exact size/hash validation passed; "
                f"error={type(initial_error).__name__}: {initial_error}",
            ) from initial_error
        _append_progress(progress_path, "model_repair_completed_single_retry_started")
        try:
            diarization = construct_diarization(vendor_module, model_cache_root, progress_path)
        except Exception as retry_error:
            model_report["status"] = "model_load_failed_after_repair"
            model_report["retry_load_error_type"] = type(retry_error).__name__
            model_report["retry_load_error_message"] = str(retry_error)
            model_report["load_attempt_count"] = 2
            _write_json(diagnostic_path, model_report)
            raise ModelPreparationError(
                "model_load_failed_after_repair",
                "3D-Speaker model load failed after one repair retry; "
                f"error={type(retry_error).__name__}: {retry_error}",
            ) from retry_error
        model_report["status"] = "ready_after_repair"
        model_report["load_attempt_count"] = 2
        _write_json(diagnostic_path, model_report)
        _append_progress(progress_path, "model_load_completed_after_repair", device=str(diarization.device))
        return diarization, model_cache_root, model_report

    model_report = {
        "schema_version": 1,
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "cache_root": str(model_cache_root),
        "network_attempted": False,
        "validation_performed": False,
        "repair_performed": False,
        "models": [],
        "status": "ready_from_direct_local_load",
        "model_source": "local_cache",
        "load_attempt_count": 1,
    }
    _write_json(diagnostic_path, model_report)
    _append_progress(progress_path, "direct_local_model_load_completed", device=str(diarization.device))
    return diarization, model_cache_root, model_report


def load_vendor_module(vendor_script: Path, progress_path: Path):
    vendor_root = vendor_script.parents[2]
    if str(vendor_root) not in sys.path:
        sys.path.insert(0, str(vendor_root))
    subprocess_started = float(
        os.getenv("DUBLAJ_3D_SPEAKER_SUBPROCESS_STARTED_MONOTONIC", perf_counter())
    )
    _append_progress(
        progress_path,
        "vendor_import_started",
        elapsed_since_subprocess_start_seconds=round(perf_counter() - subprocess_started, 6),
    )
    started = perf_counter()
    spec = importlib.util.spec_from_file_location("dublaj_hatti_3d_speaker_vendor", vendor_script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"3D-Speaker vendor module yuklenemedi: {vendor_script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _append_progress(
        progress_path,
        "vendor_import_completed",
        elapsed_seconds=round(perf_counter() - started, 6),
    )
    return module


def prepare_cuda_context(vendor_module, progress_path: Path) -> None:
    started = perf_counter()
    _append_progress(progress_path, "cuda_context_preparation_started")
    device = "cpu"
    if vendor_module.torch.cuda.is_available():
        vendor_module.torch.cuda.init()
        vendor_module.torch.cuda.synchronize()
        device = "cuda"
    _append_progress(
        progress_path,
        "cuda_context_preparation_completed",
        elapsed_seconds=round(perf_counter() - started, 6),
        device=device,
    )


def apply_audio_only_clustering_policy(
    diarization,
    min_cluster_size: int,
    merge_cos: float,
    ahc_rescue_threshold: float,
) -> dict:
    cluster = diarization.cluster
    cluster.min_cluster_size = int(min_cluster_size)
    cluster.mer_cos = float(merge_cos)
    return {
        "input_mode": "audio_only",
        "speaker_count_mode": "automatic",
        "min_cluster_size": int(cluster.min_cluster_size),
        "merge_cos": float(cluster.mer_cos),
        "ahc_rescue_threshold": float(ahc_rescue_threshold),
        "clustering_strategy": "spectral_then_ahc_if_single",
        "overlap_enabled": False,
        "video_analysis_enabled": False,
        "model_load_count": 1,
    }


def speaker_count_from_labels(labels) -> int:
    if len(labels) == 0:
        return 0
    return len(np.unique(labels))


def select_audio_only_labels(primary_labels, embeddings, cluster, ahc_rescue_threshold: float, ahc_factory):
    primary_speaker_count = speaker_count_from_labels(primary_labels)
    if primary_speaker_count != 1:
        return primary_labels, "spectral", primary_speaker_count
    rescue_labels = ahc_factory(fix_cos_thr=ahc_rescue_threshold)(embeddings)
    if cluster.mer_cos is not None:
        rescue_labels = cluster.merge_by_cos(rescue_labels, embeddings, cluster.mer_cos)
    return rescue_labels, "spectral_then_ahc_rescue", primary_speaker_count


def run_audio_only_diarization(
    vendor_module,
    diarization,
    audio_path: Path,
    ahc_rescue_threshold: float,
    progress_path: Path | None = None,
):
    from speakerlab.process.cluster import AHCluster

    if progress_path:
        _append_progress(progress_path, "audio_load_started", audio_path=str(audio_path))
    try:
        wave = vendor_module.load_audio(str(audio_path), None, diarization.fs)
    except Exception as exc:
        raise WorkerStageError(
            "audio_load_failed",
            f"audio={audio_path} error={type(exc).__name__}: {exc}",
        ) from exc
    if progress_path:
        _append_progress(progress_path, "audio_load_completed", sample_count=int(wave.shape[-1]))
        _append_progress(progress_path, "vad_started")
    try:
        vad_time = diarization.do_vad(wave)
    except Exception as exc:
        raise WorkerStageError("vad_failed", f"error={type(exc).__name__}: {exc}") from exc
    chunks = [chunk for start, end in vad_time for chunk in diarization.chunk(start, end)]
    if progress_path:
        _append_progress(
            progress_path,
            "vad_completed",
            speech_region_count=len(vad_time),
            chunk_count=len(chunks),
        )
    if not chunks:
        raise WorkerStageError("no_speech_detected", "VAD returned no speech chunks")
    if progress_path:
        _append_progress(progress_path, "embedding_extraction_started", chunk_count=len(chunks))
    try:
        embeddings = diarization.do_emb_extraction(chunks, wave)
    except Exception as exc:
        raise WorkerStageError(
            "embedding_extraction_failed",
            f"chunk_count={len(chunks)} error={type(exc).__name__}: {exc}",
        ) from exc
    if progress_path:
        _append_progress(
            progress_path,
            "embedding_extraction_completed",
            embedding_count=len(embeddings),
        )
        _append_progress(progress_path, "speaker_clustering_started")
    try:
        primary_labels = diarization.cluster(embeddings, speaker_num=None)
        labels, strategy, primary_speaker_count = select_audio_only_labels(
            primary_labels,
            embeddings,
            diarization.cluster,
            ahc_rescue_threshold,
            AHCluster,
        )
    except Exception as exc:
        raise WorkerStageError(
            "speaker_clustering_failed",
            f"embedding_count={len(embeddings)} error={type(exc).__name__}: {exc}",
        ) from exc
    if progress_path:
        _append_progress(
            progress_path,
            "speaker_clustering_completed",
            primary_speaker_count=primary_speaker_count,
            final_speaker_count=speaker_count_from_labels(labels),
            strategy=strategy,
        )
    raw_segments = [
        [chunk[0], chunk[1], int(label)]
        for chunk, label in zip(chunks, labels, strict=True)
    ]
    segments = vendor_module.compressed_seg(raw_segments)
    return segments, {
        "chunk_count": len(chunks),
        "primary_speaker_count": primary_speaker_count,
        "raw_speaker_count": speaker_count_from_labels(labels),
        "clustering_strategy_used": strategy,
    }


def run_worker(args) -> dict:
    vendor_script = Path(args.vendor_script).resolve()
    audio_path = Path(args.wav).resolve()
    output_dir = Path(args.out_dir).resolve()
    if not vendor_script.exists():
        raise FileNotFoundError(f"3D-Speaker vendor script bulunamadi: {vendor_script}")
    if not audio_path.exists():
        raise FileNotFoundError(f"3D-Speaker ses girdisi bulunamadi: {audio_path}")
    if args.min_cluster_size < 0:
        raise ValueError("min_cluster_size negatif olamaz")
    if not 0.0 < args.merge_cos <= 1.0:
        raise ValueError("merge_cos 0 ile 1 araliginda olmali")
    if not 0.0 < args.ahc_rescue_threshold <= 1.0:
        raise ValueError("ahc_rescue_threshold 0 ile 1 araliginda olmali")
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnostic_path = Path(args.model_diagnostic_path).resolve()
    progress_path = Path(args.progress_path).resolve()
    progress_path.unlink(missing_ok=True)
    vendor_module = load_vendor_module(vendor_script, progress_path)
    prepare_cuda_context(vendor_module, progress_path)
    _append_progress(progress_path, "model_construction_started", device="automatic")
    diarization, model_cache_root, model_report = load_diarization_with_local_repair(
        vendor_module,
        diagnostic_path,
        progress_path,
    )
    _append_progress(progress_path, "model_construction_completed", device=str(diarization.device))
    policy = apply_audio_only_clustering_policy(
        diarization,
        args.min_cluster_size,
        args.merge_cos,
        args.ahc_rescue_threshold,
    )
    segments, diagnostics = run_audio_only_diarization(
        vendor_module,
        diarization,
        audio_path,
        args.ahc_rescue_threshold,
        progress_path,
    )
    output_path = output_dir / f"{audio_path.stem}.json"
    try:
        diarization.save_diar_output(str(output_path), audio_path.stem, segments)
    except Exception as exc:
        raise WorkerStageError(
            "diarization_output_write_failed",
            f"output={output_path} error={type(exc).__name__}: {exc}",
        ) from exc
    result = dict(policy)
    result.update(diagnostics)
    result.update(
        {
            "output_path": str(output_path),
            "timeline_segment_count": len(segments),
            "speaker_count": len({int(item[2]) for item in segments}),
            "model_cache_root": str(model_cache_root),
            "model_source": model_report["model_source"],
            "model_network_attempted": model_report["network_attempted"],
            "timings_seconds": read_progress_timings(progress_path),
        }
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wav", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--vendor_script", required=True)
    parser.add_argument("--min_cluster_size", required=True, type=int)
    parser.add_argument("--merge_cos", required=True, type=float)
    parser.add_argument("--ahc_rescue_threshold", required=True, type=float)
    parser.add_argument("--model_diagnostic_path", required=True)
    parser.add_argument("--failure_path", required=True)
    parser.add_argument("--progress_path", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        result = run_worker(args)
    except Exception as exc:
        category = getattr(exc, "category", "worker_failed")
        failure = {
            "schema_version": 1,
            "failed_at_utc": datetime.now(UTC).isoformat(),
            "category": category,
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        _write_json(Path(args.failure_path).resolve(), failure)
        print(
            f"3D-Speaker error category={category} type={type(exc).__name__} message={exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
