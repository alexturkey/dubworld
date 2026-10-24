# -*- coding: utf-8 -*-
"""
Video Processor Subprocess Worker
Izole process olarak calisir, VRAM leak'ini OS temizler

KULLANIM:
    python video_processor_worker.py --config "config.json"

CONFIG JSON FORMATI:
    {
        "input_video": "video.mp4",
        "output_video": "output.mp4",
        "work_dir": "work/",
        "sample_rate": 24000,
        "segments_file": "segments.json",
        "timing_infos_file": "timing_infos.json",
        "segment_audios_dir": "segment_audios/"
    }

OUTPUT:
    result.json dosyasi work_dir icinde olusturulur
    STDOUT'a sadece {"success": true/false, "result_file": "path"} yazilir
"""

import sys
import json
import argparse
import logging
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

original_stdout = sys.stdout
sys.stdout = sys.stderr

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def serialize_timeline_for_result(timeline: list) -> list:
    timeline_data = []
    for item in timeline:
        data = {
            "type": item["type"],
            "original_start": item["original_start"],
            "original_end": item["original_end"],
            "original_duration": item.get("original_duration"),
            "new_start": item["new_start"],
            "new_end": item["new_end"],
            "new_duration": item.get("new_duration"),
            "video_speed": item.get("video_speed", 1.0),
        }
        if item["type"] == "segment":
            data.update({
                "index": item["index"],
                "action": item.get("action", ""),
                "speed_factor": item.get("speed_factor", 1.0),
            })
        timeline_data.append(data)
    return timeline_data


def load_segment_audios(segment_audios_dir: str, sample_rate: int):
    from dublaj_hatti.bolum_60_video_ve_encode.timeline_ve_final_encode.audio_files import WavAudioFiles

    audios = WavAudioFiles.from_directory(segment_audios_dir, sample_rate)
    logger.info("[AUDIO-MEMORY] %d segment file references; samples read on demand", len(audios))
    return audios


def process_video(config: dict) -> dict:
    """
    Video isleme (subprocess icinde)

    Args:
        config: Konfigurasyon dict

    Returns:
        Islem sonucu dict
    """
    try:
        logger.info("[WORKER] Video isleme basliyor...")

        from dublaj_hatti.bolum_60_video_ve_encode.timeline_ve_final_encode.video_processor import (
            VideoProcessOptions,
            process_video_with_segments,
            write_speed_report
        )

        input_video = config["input_video"]
        output_video = config["output_video"]
        work_dir = config["work_dir"]
        sample_rate = config.get("sample_rate", 24000)
        segments_file = config["segments_file"]
        timing_infos_file = config["timing_infos_file"]
        segment_audios_dir = config["segment_audios_dir"]
        subtitle_ass_path = str(config.get("subtitle_ass_path") or "").strip() or None
        final_audio_filter = str(config.get("final_audio_filter") or "").strip()
        video_process_options = VideoProcessOptions(
            encoder_preset=str(config.get("video_encoder_preset", "p2")),
            encoder_cq=str(config.get("video_encoder_cq", "26")),
            output_policy=str(config.get("video_output_policy", "cq")),
            max_output_bytes=int(config.get("max_output_bytes", 0) or 0),
            collect_profile=bool(config.get("video_collect_profile", False))
        )

        logger.info("[WORKER] Giris video: %s", input_video)
        logger.info("[WORKER] Cikis video: %s", output_video)
        logger.info("[WORKER] Calisma dizini: %s", work_dir)
        logger.info(
            "[WORKER] Video options: preset=%s cq=%s output_policy=%s max_output_bytes=%s validation_policy=batch_metadata_final_decode_probes collect_profile=%s",
            video_process_options.encoder_preset,
            video_process_options.encoder_cq,
            video_process_options.output_policy,
            video_process_options.max_output_bytes,
            video_process_options.collect_profile
        )

        with open(segments_file, "r", encoding="utf-8") as f:
            segments_data = json.load(f)

        with open(timing_infos_file, "r", encoding="utf-8") as f:
            timing_infos = json.load(f)

        logger.info("[WORKER] %d segment, %d timing info yuklendi",
                    len(segments_data), len(timing_infos))

        from dataclasses import dataclass

        @dataclass
        class SegmentObj:
            index: int
            start: float
            end: float
            text: str = ""

        segments = []
        for seg in segments_data:
            segments.append(SegmentObj(
                index=seg["index"],
                start=seg["start"],
                end=seg["end"],
                text=seg.get("text", "")
            ))

        segment_audios = load_segment_audios(segment_audios_dir, sample_rate)

        logger.info("[WORKER] Video isleniyor...")

        video_result = process_video_with_segments(
            input_video=input_video,
            segments=segments,
            timing_infos=timing_infos,
            segment_audios=segment_audios,
            output_video=output_video,
            work_dir=work_dir,
            sample_rate=sample_rate,
            options=video_process_options,
            subtitle_ass_path=subtitle_ass_path,
            final_audio_filter=final_audio_filter,
        )

        speed_report_path = os.path.join(work_dir, "video_speed_report.txt")
        write_speed_report(
            video_result["speed_infos"],
            video_result["timeline"],
            speed_report_path
        )

        timeline_data = serialize_timeline_for_result(video_result["timeline"])

        result = {
            "success": True,
            "output_video": video_result["output_video"],
            "original_duration": video_result["original_duration"],
            "new_duration": video_result["new_duration"],
            "segments_processed": video_result["segments_processed"],
            "video_adjusted_segments": video_result["video_adjusted_segments"],
            "timeline": timeline_data,
            "profile_steps": video_result.get("profile_steps", []),
            "subtitle_ass_path": video_result.get("subtitle_ass_path", ""),
            "final_audio_profile": video_result.get("final_audio_profile", {}),
        }

        logger.info("[WORKER] Video isleme tamamlandi!")
        logger.info("[WORKER] Orijinal sure: %.2fs, Yeni sure: %.2fs",
                    result["original_duration"], result["new_duration"])

        return result

    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()

        logger.error("[WORKER] HATA: %s", error_msg)
        logger.error("[WORKER] Traceback:\n%s", error_trace)

        return {
            "success": False,
            "error": error_msg,
            "traceback": error_trace
        }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Video Processor Subprocess Worker"
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Konfigurasyon JSON dosyasi yolu"
    )

    return parser.parse_args()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Video Processor Worker Started")
    logger.info("=" * 60)

    args = parse_args()

    logger.info("Config dosyasi: %s", args.config)

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    result = process_video(config)

    result_file = os.path.join(config["work_dir"], "video_result.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info("Result dosyasi: %s", result_file)

    sys.stdout = original_stdout

    print(json.dumps({
        "success": result["success"],
        "result_file": result_file
    }, ensure_ascii=False))

    logger.info("=" * 60)
    logger.info("Video Processor Worker - OPTIMIZED Finished")
    logger.info("=" * 60)

    sys.exit(0 if result["success"] else 1)
