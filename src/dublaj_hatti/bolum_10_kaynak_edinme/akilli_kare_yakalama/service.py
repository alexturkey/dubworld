from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from dublaj_hatti.bolum_10_kaynak_edinme.akilli_kare_yakalama.detector import (
    build_luminance_profile,
    build_presence_profiles,
    build_profiles,
    calculate_source_crop,
    choose_temporal_consensus_box,
    detect_content_box,
    lock_box_to_full_width,
)
from dublaj_hatti.bolum_00_omurga.runtime.arac_yolu import ffmpeg_yolu, ffprobe_yolu

ALGORITHM_VERSION = "temporal_profiles_v6_static_panel_gate"
DEFAULT_SAMPLE_COUNT = 24
DEFAULT_ANALYSIS_WIDTH = 540
CONSENSUS_VALIDATION_SAMPLE_COUNT = 16
OUTPUT_FILE_NAME = "video_smart_frame.mp4"
ANALYSIS_FILE_NAME = "smart_frame_analysis.json"
PREVIEW_FILE_NAME = "smart_frame_preview.jpg"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def read_video_metadata(input_path):
    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        raise RuntimeError(f"Video acilamadi: {input_path}")
    metadata = {
        "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": float(capture.get(cv2.CAP_PROP_FPS)),
        "frame_count": int(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    capture.release()
    if metadata["width"] <= 0 or metadata["height"] <= 0 or metadata["frame_count"] <= 0:
        raise RuntimeError(f"Video metadata gecersiz: {input_path}")
    metadata["duration_seconds"] = (
        metadata["frame_count"] / metadata["fps"] if metadata["fps"] else 0.0
    )
    return metadata


def resize_frame(frame, analysis_width):
    frame_height, frame_width = frame.shape[:2]
    analysis_height = round(frame_height * analysis_width / frame_width)
    return cv2.resize(frame, (analysis_width, analysis_height), interpolation=cv2.INTER_AREA)


def read_sparse_samples(input_path, sample_count, analysis_width):
    metadata = read_video_metadata(input_path)
    capture = cv2.VideoCapture(str(input_path))
    frame_count = max(1, metadata["frame_count"])
    target_indices = sorted(
        set(np.linspace(0, frame_count - 1, max(2, sample_count)).round().astype(int).tolist())
    )
    samples = []
    for sample_index, frame_index in enumerate(target_indices):
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        success, frame = capture.read()
        if not success:
            continue
        time_seconds = frame_index / metadata["fps"] if metadata["fps"] else 0.0
        samples.append(
            {
                "index": sample_index,
                "time_seconds": round(float(time_seconds), 3),
                "frame": resize_frame(frame, analysis_width),
            }
        )
    capture.release()
    if not samples:
        raise RuntimeError("Hic frame alinamadi")
    return metadata, samples


def build_presence_map(frame):
    grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    saturation = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[:, :, 1]
    return 0.7 * (grayscale > 12).astype(np.float32) + 0.3 * (saturation > 15).astype(np.float32)


def measure_box_support(samples, selected_box):
    inside_scores = []
    outside_scores = []
    for sample in samples:
        presence = build_presence_map(sample["frame"])
        top = selected_box["top"]
        bottom = selected_box["bottom"]
        left = selected_box["left"]
        right = selected_box["right"]
        inside_scores.append(float(np.mean(presence[top : bottom + 1, left : right + 1])))
        outside_parts = []
        if top > 0:
            outside_parts.append(presence[:top])
        if bottom + 1 < presence.shape[0]:
            outside_parts.append(presence[bottom + 1 :])
        if left > 0:
            outside_parts.append(presence[:, :left])
        if right + 1 < presence.shape[1]:
            outside_parts.append(presence[:, right + 1 :])
        outside_scores.append(
            float(np.mean(np.concatenate([part.reshape(-1) for part in outside_parts])))
            if outside_parts
            else 0.0
        )
    inside_median = float(np.median(inside_scores))
    outside_median = float(np.median(outside_scores))
    return {
        "inside_presence_median": round(inside_median, 6),
        "outside_presence_median": round(outside_median, 6),
        "inside_outside_contrast": round(inside_median - outside_median, 6),
        "sample_support_fraction": round(float(np.mean(np.asarray(inside_scores) >= 0.55)), 6),
    }


def build_sample_analysis(input_path, metadata, samples):
    motion_profile, edge_profile, activity_profile = build_profiles(samples)
    row_profile, column_profile = build_presence_profiles(samples)
    luminance_profile = build_luminance_profile(samples)
    analysis_height = samples[0]["frame"].shape[0]
    detected_box = detect_content_box(
        row_profile,
        column_profile,
        samples[0]["frame"].shape[1],
        analysis_height,
        luminance_profile,
        activity_profile,
    )
    selected_box = lock_box_to_full_width(
        detected_box,
        samples[0]["frame"].shape[1],
    )
    crop_info = calculate_source_crop(
        selected_box,
        samples[0]["frame"].shape[1],
        analysis_height,
        metadata["width"],
        metadata["height"],
    )
    if crop_info["source_crop_left"] != 0 or crop_info["source_crop_width"] != metadata["width"]:
        raise RuntimeError("Dikey crop genislik kilidi ihlal edildi")
    support = measure_box_support(samples, detected_box)
    area_fraction = (
        detected_box["width"] * detected_box["height"]
    ) / (samples[0]["frame"].shape[1] * analysis_height)
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "input_path": str(Path(input_path).resolve()),
        "metadata": metadata,
        "sample_count": len(samples),
        "analysis_width": samples[0]["frame"].shape[1],
        "analysis_height": analysis_height,
        "horizontal_crop_policy": "source_width_locked",
        "detected_box": detected_box,
        "selected_box": selected_box,
        "crop_info": crop_info,
        "box_area_fraction": round(area_fraction, 6),
        "support": support,
        "profile_summary": {
            "motion_peak": round(float(np.max(motion_profile)), 6),
            "edge_peak": round(float(np.max(edge_profile)), 6),
            "activity_peak": round(float(np.max(activity_profile)), 6),
        },
    }


def analyze_video_content(
    input_path,
    sample_count=DEFAULT_SAMPLE_COUNT,
    analysis_width=DEFAULT_ANALYSIS_WIDTH,
):
    metadata, samples = read_sparse_samples(input_path, sample_count, analysis_width)
    primary_analysis = build_sample_analysis(input_path, metadata, samples)
    if sample_count == CONSENSUS_VALIDATION_SAMPLE_COUNT:
        primary_analysis["temporal_consensus"] = {
            "enabled": False,
            "reason": "primary_uses_validation_sample_count",
        }
        return primary_analysis, samples
    validation_metadata, validation_samples = read_sparse_samples(
        input_path,
        CONSENSUS_VALIDATION_SAMPLE_COUNT,
        analysis_width,
    )
    validation_analysis = build_sample_analysis(
        input_path,
        validation_metadata,
        validation_samples,
    )
    primary_box = primary_analysis["selected_box"]
    primary_detected_box = primary_analysis["detected_box"]
    primary_crop_info = primary_analysis["crop_info"]
    primary_support = primary_analysis["support"]
    selected_box, selection_reason = choose_temporal_consensus_box(
        primary_analysis,
        validation_analysis,
    )
    selected_box = lock_box_to_full_width(
        selected_box,
        primary_analysis["analysis_width"],
    )
    crop_info = calculate_source_crop(
        selected_box,
        primary_analysis["analysis_width"],
        primary_analysis["analysis_height"],
        metadata["width"],
        metadata["height"],
    )
    if crop_info["source_crop_left"] != 0 or crop_info["source_crop_width"] != metadata["width"]:
        raise RuntimeError("Dikey crop genislik kilidi ihlal edildi")
    primary_analysis["selected_box"] = selected_box
    primary_analysis["crop_info"] = crop_info
    primary_analysis["box_area_fraction"] = round(
        (selected_box["width"] * selected_box["height"])
        / (primary_analysis["analysis_width"] * primary_analysis["analysis_height"]),
        6,
    )
    primary_analysis["support"] = measure_box_support(samples, selected_box)
    primary_analysis["temporal_consensus"] = {
        "enabled": True,
        "primary_sample_count": len(samples),
        "validation_sample_count": len(validation_samples),
        "selection_reason": selection_reason,
        "horizontal_crop_policy": "source_width_locked",
        "primary_detected_box": primary_detected_box,
        "primary_selected_box": primary_box,
        "primary_crop_info": primary_crop_info,
        "primary_support": primary_support,
        "validation_detected_box": validation_analysis["detected_box"],
        "validation_selected_box": validation_analysis["selected_box"],
        "validation_crop_info": validation_analysis["crop_info"],
        "validation_support": validation_analysis["support"],
        "final_changed_from_primary": crop_info["filter"] != primary_crop_info["filter"],
    }
    return primary_analysis, samples


def crop_is_effectively_full_frame(crop_info, source_width, source_height):
    left = int(crop_info["source_crop_left"])
    top = int(crop_info["source_crop_top"])
    right = source_width - left - int(crop_info["source_crop_width"])
    bottom = source_height - top - int(crop_info["source_crop_height"])
    horizontal_tolerance = max(2, round(source_width * 0.005))
    vertical_tolerance = max(2, round(source_height * 0.005))
    return (
        left <= horizontal_tolerance
        and right <= horizontal_tolerance
        and top <= vertical_tolerance
        and bottom <= vertical_tolerance
    )


def make_preview(samples, selected_box, output_path):
    preview = samples[len(samples) // 2]["frame"].copy()
    cv2.rectangle(
        preview,
        (selected_box["left"], selected_box["top"]),
        (selected_box["right"], selected_box["bottom"]),
        (0, 255, 0),
        4,
    )
    if not cv2.imwrite(str(output_path), preview, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        raise RuntimeError(f"Onizleme yazilamadi: {output_path}")


def probe_media(media_path):
    command = [
        ffprobe_yolu(),
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_type,codec_name,width,height:format=duration",
        "-of",
        "json",
        str(media_path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        creationflags=NO_WINDOW,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])
    return json.loads(result.stdout)


def validate_output(input_path, output_path, crop_info):
    source_probe = probe_media(input_path)
    output_probe = probe_media(output_path)
    source_streams = source_probe.get("streams", [])
    output_streams = output_probe.get("streams", [])
    source_audio_count = sum(stream.get("codec_type") == "audio" for stream in source_streams)
    output_audio_count = sum(stream.get("codec_type") == "audio" for stream in output_streams)
    output_video_streams = [stream for stream in output_streams if stream.get("codec_type") == "video"]
    source_duration = float(source_probe.get("format", {}).get("duration", 0.0))
    output_duration = float(output_probe.get("format", {}).get("duration", 0.0))
    dimension_ok = (
        bool(output_video_streams)
        and output_video_streams[0].get("width") == crop_info["source_crop_width"]
        and output_video_streams[0].get("height") == crop_info["source_crop_height"]
    )
    duration_ok = abs(source_duration - output_duration) <= 0.25
    audio_ok = source_audio_count == output_audio_count
    validation = {
        "dimension_ok": dimension_ok,
        "duration_ok": duration_ok,
        "audio_ok": audio_ok,
        "source_audio_count": source_audio_count,
        "output_audio_count": output_audio_count,
        "source_duration": round(source_duration, 6),
        "output_duration": round(output_duration, 6),
        "actual_width": output_video_streams[0].get("width") if output_video_streams else None,
        "actual_height": output_video_streams[0].get("height") if output_video_streams else None,
    }
    validation["status"] = "ok" if dimension_ok and duration_ok and audio_ok else "failed"
    return validation


def create_crop_video(input_path, output_path, crop_info, video_preset="veryfast", crf=18):
    command = [
        ffmpeg_yolu(),
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        crop_info["filter"],
        "-c:v",
        "libx264",
        "-preset",
        video_preset,
        "-crf",
        str(crf),
        "-c:a",
        "copy",
        "-map_metadata",
        "0",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        creationflags=NO_WINDOW,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])


def write_json_atomic(output_path, value):
    output_path = Path(output_path)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with open(temporary_path, "w", encoding="utf-8", newline="\n") as file_handle:
        json.dump(value, file_handle, ensure_ascii=False, indent=2)
        file_handle.write("\n")
    os.replace(temporary_path, output_path)


def apply_smart_frame_capture(
    input_path,
    work_dir,
    enabled=True,
    logger=None,
    sample_count=DEFAULT_SAMPLE_COUNT,
    analysis_width=DEFAULT_ANALYSIS_WIDTH,
    video_preset="veryfast",
    crf=18,
):
    source_path = Path(input_path).resolve()
    if not enabled:
        return {
            "status": "disabled",
            "enabled": False,
            "crop_applied": False,
            "reason": "user_disabled",
            "input_path": str(source_path),
            "video_path": str(source_path),
        }
    if not source_path.is_file():
        raise FileNotFoundError(f"Kaynak video bulunamadi: {source_path}")
    output_dir = Path(work_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis_path = output_dir / ANALYSIS_FILE_NAME
    preview_path = output_dir / PREVIEW_FILE_NAME
    output_path = output_dir / OUTPUT_FILE_NAME
    temporary_output_path = output_dir / f"{OUTPUT_FILE_NAME}.tmp.mp4"
    if logger:
        logger.info("Akilli kare analizi baslatildi: %s", source_path)
    analysis = None
    try:
        analysis, samples = analyze_video_content(source_path, sample_count, analysis_width)
        make_preview(samples, analysis["selected_box"], preview_path)
        crop_info = analysis["crop_info"]
        metadata = analysis["metadata"]
        full_frame = crop_is_effectively_full_frame(
            crop_info,
            int(metadata["width"]),
            int(metadata["height"]),
        )
        if full_frame:
            result = {
                **analysis,
                "status": "unchanged",
                "enabled": True,
                "crop_applied": False,
                "reason": "full_frame_detected",
                "output_path": str(source_path),
                "video_path": str(source_path),
                "preview_path": str(preview_path),
                "validation": {"status": "not_required"},
                "processed_at": datetime.now().isoformat(timespec="seconds"),
            }
            write_json_atomic(analysis_path, result)
            result["analysis_path"] = str(analysis_path)
            if logger:
                logger.info("Akilli kare: kirpma gerekmiyor, kaynak video korunuyor")
            return result
        if temporary_output_path.exists():
            temporary_output_path.unlink()
        create_crop_video(source_path, temporary_output_path, crop_info, video_preset, crf)
        validation = validate_output(source_path, temporary_output_path, crop_info)
        if validation["status"] != "ok":
            raise RuntimeError("Cikti dogrulamasi basarisiz: " + json.dumps(validation, ensure_ascii=True))
        os.replace(temporary_output_path, output_path)
        result = {
            **analysis,
            "status": "cropped",
            "enabled": True,
            "crop_applied": True,
            "reason": "content_box_detected",
            "output_path": str(output_path),
            "video_path": str(output_path),
            "preview_path": str(preview_path),
            "validation": validation,
            "processed_at": datetime.now().isoformat(timespec="seconds"),
        }
        write_json_atomic(analysis_path, result)
        result["analysis_path"] = str(analysis_path)
        if logger:
            logger.info("Akilli kare uygulandi: %s", crop_info["filter"])
        return result
    except Exception as error:
        if temporary_output_path.exists():
            temporary_output_path.unlink()
        failure = {
            **(analysis or {}),
            "status": "failed",
            "enabled": True,
            "crop_applied": False,
            "input_path": str(source_path),
            "video_path": str(source_path),
            "error": str(error),
            "processed_at": datetime.now().isoformat(timespec="seconds"),
        }
        write_json_atomic(analysis_path, failure)
        raise
