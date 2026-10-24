# -*- coding: utf-8 -*-
"""
Video Processor - Segment Bazli Video Hiz Ayarlama

Segment bazinda video hizini ayarlar.
Optimize edilmis parametreler kullanir:
- Batch size: 40/35/30
- FFmpeg preset: p2
- CQ kalite: 26

Kullanim:
    from dublaj_hatti.bolum_60_video_ve_encode.timeline_ve_final_encode.video_processor import process_video_with_segments

    result = process_video_with_segments(
        input_video="video.mp4",
        segments=segments,
        timing_infos=timing_infos,
        segment_audios=segment_audios,
        output_video="output.mp4",
        work_dir="work/",
        sample_rate=24000
    )
"""

import logging
import os
import json
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

import numpy as np
import soundfile as sf

from dublaj_hatti.bolum_60_video_ve_encode.kodlayici import nvenc_kullanilabilir
from dublaj_hatti.bolum_60_video_ve_encode.timeline_ve_final_encode.audio_files import audio_sample_count
from dublaj_hatti.bolum_00_omurga.runtime.arac_yolu import ffmpeg_yolu, ffprobe_yolu

logger = logging.getLogger("dublaj_hatti")
timeline_boundary_epsilon_seconds = 1e-6


@dataclass
class SegmentSpeedInfo:
    index: int
    original_start: float
    original_end: float
    original_duration: float
    tts_duration: float
    speed_factor: float
    action: str
    video_speed: float
    new_duration: float


@dataclass
class VideoStreamInfo:
    duration: float
    fps: float
    frame_count: int


@dataclass
class VideoProcessOptions:
    encoder_preset: str = "p2"
    encoder_cq: str = "26"
    output_policy: str = "cq"
    max_output_bytes: int = 0
    collect_profile: bool = False
    measured_audio_bytes: int = 0
    video_bitrate_override_kbps: int = 0

    def count_frames_for_step(self, step_name: str) -> bool:
        return False

    def decode_probes_for_step(self, step_name: str) -> bool:
        return not step_name.startswith("batch_")


def _parse_fraction(value: str) -> float:
    if not value:
        return 0.0
    if "/" not in value:
        return float(value)
    numerator, denominator = value.split("/", 1)
    denominator_value = float(denominator)
    if denominator_value == 0:
        return 0.0
    return float(numerator) / denominator_value


def get_video_stream_info(video_path: str, count_frames: bool = True) -> VideoStreamInfo:
    cmd = [
        ffprobe_yolu(),
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=duration,nb_frames,nb_read_frames,avg_frame_rate,r_frame_rate:format=duration",
        "-of", "json",
        video_path
    ]
    if count_frames:
        cmd.insert(5, "-count_frames")
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    streams = data.get("streams") or []
    if not streams:
        raise RuntimeError(f"Video stream bulunamadi: {video_path}")

    stream = streams[0]
    format_info = data.get("format") or {}
    format_duration = float(format_info.get("duration") or 0.0)
    duration = float(stream.get("duration") or 0.0)
    if duration <= 0 and format_duration > 0:
        duration = format_duration
    fps = _parse_fraction(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/0")
    frame_text = stream.get("nb_read_frames") or stream.get("nb_frames") or "0"
    frame_count = int(float(frame_text))

    return VideoStreamInfo(duration=duration, fps=fps, frame_count=frame_count)


def validate_video_stream(
    video_path: str,
    expected_duration: float,
    count_frames: bool = True
) -> VideoStreamInfo:
    info = get_video_stream_info(video_path, count_frames=count_frames)
    min_duration = max(0.1, expected_duration * 0.95)
    min_frames = 1
    frame_count_available = info.frame_count > 0
    if frame_count_available and info.fps > 0 and expected_duration > 1.0:
        min_frames = int(expected_duration * info.fps * 0.80)

    if (
        info.duration < min_duration
        or (frame_count_available and info.frame_count < min_frames)
        or (count_frames and not frame_count_available)
    ):
        raise RuntimeError(
            "Video stream dogrulamasi basarisiz: "
            f"path={video_path} "
            f"video_duration={info.duration:.3f}s "
            f"beklenen_duration={expected_duration:.3f}s "
            f"frames={info.frame_count} "
            f"min_frames={min_frames} "
            f"fps={info.fps:.3f}"
        )

    logger.info(
        "Video stream dogrulandi: path=%s video_duration=%.3fs beklenen=%.3fs frames=%d fps=%.3f",
        video_path,
        info.duration,
        expected_duration,
        info.frame_count,
        info.fps
    )
    return info


def validate_video_decode_probes(
    video_path: str,
    duration: float,
    probe_duration: float = 0.75,
) -> List[float]:
    effective_probe_duration = min(probe_duration, max(0.1, duration))
    probe_starts = sorted({
        0.0,
        max(0.0, (duration - effective_probe_duration) / 2.0),
        max(0.0, duration - effective_probe_duration),
    })
    for probe_start in probe_starts:
        subprocess.run([
            ffmpeg_yolu(),
            "-hide_banner",
            "-loglevel", "error",
            "-xerror",
            "-ss", f"{probe_start:.6f}",
            "-i", video_path,
            "-t", f"{effective_probe_duration:.6f}",
            "-map", "0:v:0",
            "-an",
            "-f", "null",
            os.devnull,
        ], capture_output=True, text=True, check=True)
    return probe_starts


def calculate_segment_speeds(
    segments: List,
    timing_infos: List
) -> List[SegmentSpeedInfo]:
    """
    Her segment icin hiz faktorunu ve aksiyonu hesaplar.

    Args:
        segments: Segment listesi (start, end, index)
        timing_infos: TTS timing bilgileri

    Returns:
        SegmentSpeedInfo listesi
    """
    speed_infos = []

    timing_map = {}
    for info in timing_infos:
        if isinstance(info, dict):
            seg_idx = info.get('segment_index')
        else:
            seg_idx = getattr(info, 'segment_index', None)
        if seg_idx is not None:
            timing_map[seg_idx] = info

    for seg in segments:
        original_duration = seg.end - seg.start

        timing = timing_map.get(seg.index)
        if timing:
            if isinstance(timing, dict):
                tts_duration = timing.get('tts_processed_duration', timing.get('tts_raw_duration', original_duration))
            else:
                tts_duration = getattr(timing, 'tts_processed_duration', getattr(timing, 'tts_raw_duration', original_duration))
        else:
            tts_duration = original_duration

        if original_duration > 0:
            speed_factor = tts_duration / original_duration
        else:
            speed_factor = 1.0

        if speed_factor < 1.0:
            action = "video_speedup"
        elif speed_factor > 1.0:
            action = "video_slowdown"
        else:
            action = "no_change"

        video_speed = 1.0 / speed_factor if speed_factor > 0 else 1.0
        new_duration = tts_duration

        speed_infos.append(SegmentSpeedInfo(
            index=seg.index,
            original_start=seg.start,
            original_end=seg.end,
            original_duration=original_duration,
            tts_duration=tts_duration,
            speed_factor=speed_factor,
            action=action,
            video_speed=video_speed,
            new_duration=new_duration
        ))

    return speed_infos


def calculate_new_timeline(
    speed_infos: List[SegmentSpeedInfo],
    total_video_duration: float
) -> List[Dict]:
    """
    Yeni zaman cizelgesini hesaplar.
    Segment arasi bosluklari (konusma olmayan) korur.

    Args:
        speed_infos: Hiz bilgileri
        total_video_duration: Toplam video suresi

    Returns:
        Yeni timeline listesi
    """
    timeline = []
    cumulative_offset = 0.0

    sorted_infos = sorted(speed_infos, key=lambda x: x.original_start)

    prev_end = 0.0

    for info in sorted_infos:
        original_start = float(info.original_start)
        original_end = float(info.original_end)
        boundary_was_normalized = abs(original_start - prev_end) <= timeline_boundary_epsilon_seconds
        if boundary_was_normalized:
            original_start = prev_end
        original_duration = original_end - original_start if boundary_was_normalized else info.original_duration

        if original_start > prev_end:
            gap_start = prev_end
            gap_end = original_start
            gap_duration = gap_end - gap_start

            timeline.append({
                "type": "gap",
                "original_start": gap_start,
                "original_end": gap_end,
                "original_duration": gap_duration,
                "new_start": prev_end + cumulative_offset,
                "new_end": prev_end + cumulative_offset + gap_duration,
                "new_duration": gap_duration,
                "video_speed": 1.0
            })

        new_start = original_start + cumulative_offset
        duration_diff = info.new_duration - original_duration
        cumulative_offset += duration_diff
        new_end = new_start + info.new_duration

        timeline.append({
            "type": "segment",
            "index": info.index,
            "original_start": original_start,
            "original_end": original_end,
            "original_duration": original_duration,
            "new_start": new_start,
            "new_end": new_end,
            "new_duration": info.new_duration,
            "video_speed": info.video_speed,
            "action": info.action,
            "speed_factor": info.speed_factor
        })

        prev_end = original_end

    if total_video_duration - prev_end > timeline_boundary_epsilon_seconds:
        gap_duration = total_video_duration - prev_end
        timeline.append({
            "type": "gap",
            "original_start": prev_end,
            "original_end": total_video_duration,
            "original_duration": gap_duration,
            "new_start": prev_end + cumulative_offset,
            "new_end": prev_end + cumulative_offset + gap_duration,
            "new_duration": gap_duration,
            "video_speed": 1.0
        })

    return timeline


def format_ffmpeg_time(value: float) -> str:
    normalized_value = 0.0 if abs(value) <= timeline_boundary_epsilon_seconds else value
    formatted_value = f"{normalized_value:.9f}".rstrip("0").rstrip(".")
    return formatted_value if "." in formatted_value else f"{formatted_value}.0"


def get_video_duration(video_path: str) -> float:
    """Video suresini saniye olarak dondurur."""
    return get_video_stream_info(video_path, count_frames=False).duration


def build_ffmpeg_filter_complex(
    timeline: List[Dict],
    total_new_duration: float,
    time_offset: float = 0.0,
    subtitle_filter: Optional[str] = None,
    subtitle_time_offset: float = 0.0,
) -> str:
    """
    FFmpeg filter_complex stringi olusturur.
    Her segment icin ayri hiz filtresi uygular.

    Args:
        timeline: Zaman cizelgesi
        total_new_duration: Yeni toplam sure

    Returns:
        FFmpeg filter_complex stringi
    """
    video_filters = []

    segment_count = 0

    for i, item in enumerate(timeline):
        start = item["original_start"] - time_offset
        end = item["original_end"] - time_offset
        video_speed = item["video_speed"]

        pts_factor = 1.0 / video_speed if video_speed != 0 else 1.0

        trim_filter = (
            f"[0:v]trim=start={format_ffmpeg_time(start)}:end={format_ffmpeg_time(end)},"
            "setpts=PTS-STARTPTS"
        )

        if video_speed != 1.0:
            trim_filter += f",setpts={pts_factor}*PTS"

        trim_filter += f"[v{i}]"
        video_filters.append(trim_filter)

        segment_count += 1

    video_concat_inputs = "".join([f"[v{i}]" for i in range(segment_count)])

    concat_filter = f"{video_concat_inputs}concat=n={segment_count}:v=1:a=0[concatv]"

    all_filters = video_filters + [concat_filter]
    duration_filter = (
        f"[concatv]tpad=stop_mode=clone:stop_duration={total_new_duration:.6f},"
        f"trim=duration={total_new_duration:.6f},setpts=PTS-STARTPTS"
    )
    if subtitle_filter:
        all_filters.append(
            f"{duration_filter}[timelinev]"
        )
        all_filters.append(
            f"[timelinev]setpts=PTS+{subtitle_time_offset:.6f}/TB,"
            f"{subtitle_filter},setpts=PTS-STARTPTS[outv]"
        )
    else:
        all_filters.append(f"{duration_filter}[outv]")

    return ";".join(all_filters)


def _atempo_filter_chain(speed: float) -> str:
    if speed <= 0:
        speed = 1.0
    factors = []
    remaining = float(speed)
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def build_ffmpeg_audio_filter_complex(
    timeline: List[Dict],
    sample_rate: int,
) -> str:
    audio_filters = []
    segment_count = 0

    for i, item in enumerate(timeline):
        start = item["original_start"]
        end = item["original_end"]
        video_speed = item.get("video_speed", 1.0)

        trim_filter = f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS"
        if video_speed != 1.0:
            trim_filter += f",{_atempo_filter_chain(video_speed)}"
        trim_filter += f"[a{i}]"
        audio_filters.append(trim_filter)
        segment_count += 1

    audio_concat_inputs = "".join([f"[a{i}]" for i in range(segment_count)])
    concat_filter = f"{audio_concat_inputs}concat=n={segment_count}:v=0:a=1,aresample={sample_rate},aformat=channel_layouts=mono[outa]"

    return ";".join(audio_filters + [concat_filter])


def apply_timeline_to_audio(
    input_audio: str,
    timeline: List[Dict],
    output_audio: str,
    work_dir: str,
    sample_rate: int = 24000,
    expected_duration: Optional[float] = None,
) -> str:
    logger.info("Audio timeline uygulaniyor: %s", input_audio)
    if not timeline:
        raise RuntimeError("Audio timeline uygulanamadi: timeline bos")

    filter_complex = build_ffmpeg_audio_filter_complex(timeline, sample_rate)
    filter_script_path = os.path.join(work_dir, "background_audio_timeline_filter.txt")
    with open(filter_script_path, "w", encoding="utf-8") as f:
        f.write(filter_complex)

    cmd = [
        ffmpeg_yolu(),
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", input_audio,
        "-/filter_complex", filter_script_path,  # ffmpeg 7+ (eski -filter_complex_script 9.x’te yok)
        "-map", "[outa]",
        "-ar", str(sample_rate),
        "-ac", "1",
    ]
    if expected_duration and expected_duration > 0:
        cmd.extend(["-t", f"{expected_duration:.6f}"])
    cmd.append(output_audio)
    subprocess.run(cmd, check=True)
    logger.info("Audio timeline tamamlandi: %s", output_audio)
    return output_audio


def build_new_audio_mix(
    segment_audios: Dict[int, np.ndarray],
    timeline: List[Dict],
    total_duration: float,
    sample_rate: int
) -> np.ndarray:
    """
    TTS ses segmentlerini yeni timeline'a gore yerlestirir.

    Args:
        segment_audios: {segment_index: audio_array} dict
        timeline: Yeni zaman cizelgesi
        total_duration: Toplam sure
        sample_rate: Ornekleme hizi

    Returns:
        Mix edilmis audio array
    """
    total_samples = int(np.ceil(total_duration * sample_rate)) + 1
    mix = np.zeros(total_samples, dtype=np.float32)

    for item in timeline:
        if item["type"] != "segment":
            continue

        seg_idx = item["index"]
        new_start = item["new_start"]

        if seg_idx not in segment_audios:
            continue

        audio = segment_audios[seg_idx]
        start_sample = int(new_start * sample_rate)
        end_sample = start_sample + len(audio)

        if end_sample > len(mix):
            end_sample = len(mix)
            audio = audio[:end_sample - start_sample]

        mix[start_sample:end_sample] += audio
        del audio

    max_val = np.float32(0)
    for offset in range(0, len(mix), 65536):
        max_val = np.maximum(max_val, np.max(np.abs(mix[offset:offset + 65536])))
    if max_val > 0.99:
        mix /= max_val
        mix *= 0.95

    return mix


def calculate_adaptive_batch_size(total_segments: int) -> int:
    """
    Segment sayisina gore optimal batch size hesaplar (OPTIMIZE).

    Normal: 30/25/20
    Optimize: 40/35/30 (daha buyuk batch, daha az concat overhead)

    Args:
        total_segments: Toplam segment sayisi

    Returns:
        Optimal batch size
    """
    if total_segments <= 40:
        return total_segments
    elif total_segments <= 100:
        return 40
    elif total_segments <= 200:
        return 35
    else:
        return 30


def calculate_timeline_duration(timeline_items: List[Dict]) -> float:
    return sum(item.get("new_duration", 0.0) for item in timeline_items)


def build_timeline_batch_ranges(
    timeline: List[Dict],
    batch_size: int,
    min_tail_duration: float = 5.0
) -> List[Tuple[int, int]]:
    ranges = [
        (start_idx, min(start_idx + batch_size, len(timeline)))
        for start_idx in range(0, len(timeline), batch_size)
    ]
    if len(ranges) > 1:
        tail_start, tail_end = ranges[-1]
        tail_duration = calculate_timeline_duration(timeline[tail_start:tail_end])
        if tail_duration < min_tail_duration:
            prev_start, _ = ranges[-2]
            ranges[-2] = (prev_start, tail_end)
            ranges.pop()
    return ranges


def order_batch_jobs_by_expected_duration(
    timeline: List[Dict],
    batch_ranges: List[Tuple[int, int]],
) -> List[Tuple[int, Tuple[int, int]]]:
    batch_jobs = list(enumerate(batch_ranges))
    batch_jobs.sort(
        key=lambda value: sum(
            item.get("new_duration", 0.0)
            for item in timeline[value[1][0]:value[1][1]]
        ),
        reverse=True,
    )
    return batch_jobs


def escape_ffmpeg_filter_path(path: str) -> str:
    return path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def subtitle_filter_value(subtitle_ass_path: Optional[str]) -> Optional[str]:
    if not subtitle_ass_path:
        return None
    return f"subtitles='{escape_ffmpeg_filter_path(subtitle_ass_path)}'"


def is_size_limited_output(options: VideoProcessOptions) -> bool:
    return options.output_policy == "max_mb" and options.max_output_bytes > 0


def max_output_container_reserve_bytes(options: VideoProcessOptions) -> int:
    if not is_size_limited_output(options):
        return 0
    return max(1_000_000, int(options.max_output_bytes * 0.01))


def target_video_bitrate_kbps(options: VideoProcessOptions, duration: float) -> int:
    if not is_size_limited_output(options):
        raise ValueError("Maksimum boyut politikasi etkin degil")
    if duration <= 0:
        raise ValueError("Maksimum boyut icin nihai video suresi pozitif olmali")
    if options.video_bitrate_override_kbps > 0:
        return options.video_bitrate_override_kbps
    if options.measured_audio_bytes <= 0:
        raise ValueError("Maksimum boyut icin gercek AAC ses boyutu olculmeli")
    container_reserve_bytes = max_output_container_reserve_bytes(options)
    video_budget_bytes = options.max_output_bytes - container_reserve_bytes - options.measured_audio_bytes
    video_bitrate = int((video_budget_bytes * 8) / duration)
    if video_bitrate < 100_000:
        raise ValueError("Secilen maksimum boyut bu video suresi icin cok dusuk")
    return max(100, video_bitrate // 1000)


def final_audio_bitrate(options: VideoProcessOptions) -> str:
    return "96k" if is_size_limited_output(options) else "192k"


def final_audio_encode_args(options: VideoProcessOptions) -> List[str]:
    if is_size_limited_output(options):
        return ["-c:a", "copy"]
    return ["-c:a", "aac", "-b:a", final_audio_bitrate(options)]


def command_with_video_bitrate(command: List[str], bitrate_kbps: int) -> List[str]:
    updated = list(command)
    replacements = {
        "-b:v": f"{bitrate_kbps}k",
        "-maxrate": f"{bitrate_kbps}k",
        "-minrate": f"{bitrate_kbps}k",
        "-bufsize": f"{bitrate_kbps * 2}k",
    }
    for flag, value in replacements.items():
        if flag not in updated:
            raise ValueError(f"Video bitrate argumani bulunamadi: {flag}")
        updated[updated.index(flag) + 1] = value
    return updated


def corrected_video_bitrate_kbps(
    options: VideoProcessOptions,
    duration: float,
    actual_output_bytes: int,
) -> int:
    current_bitrate = target_video_bitrate_kbps(options, duration)
    excess_bytes = max(0, actual_output_bytes - options.max_output_bytes)
    retry_safety_bytes = max(250_000, int(options.max_output_bytes * 0.002))
    bitrate_reduction = int(np.ceil(((excess_bytes + retry_safety_bytes) * 8) / duration / 1000))
    corrected_bitrate = current_bitrate - max(1, bitrate_reduction)
    if corrected_bitrate < 100:
        raise RuntimeError("Maksimum boyut duzeltmesi video bitrate'ini kullanilamaz seviyeye dusurdu")
    return corrected_bitrate


def video_encode_args(options: VideoProcessOptions, duration: float) -> List[str]:
    if not nvenc_kullanilabilir():
        return cpu_video_encode_args(options, duration)
    if is_size_limited_output(options):
        bitrate_kbps = target_video_bitrate_kbps(options, duration)
        return [
            "-c:v", "h264_nvenc",
            "-preset", options.encoder_preset,
            "-rc", "cbr",
            "-b:v", f"{bitrate_kbps}k",
            "-maxrate", f"{bitrate_kbps}k",
            "-minrate", f"{bitrate_kbps}k",
            "-bufsize", f"{bitrate_kbps * 2}k",
            "-bf", "0",
        ]
    return [
        "-c:v", "h264_nvenc",
        "-preset", options.encoder_preset,
        "-cq", options.encoder_cq,
    ]


def cpu_video_encode_args(options: VideoProcessOptions, duration: float) -> List[str]:
    """NVENC yoksa birincil yol: aynı kalite ayarı (cq -> crf) libx264 ile."""
    if is_size_limited_output(options):
        return fallback_video_encode_args(options, duration)
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(options.encoder_cq)]


def fallback_video_encode_args(options: VideoProcessOptions, duration: float) -> List[str]:
    if is_size_limited_output(options):
        bitrate_kbps = target_video_bitrate_kbps(options, duration)
        return [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-b:v", f"{bitrate_kbps}k",
            "-maxrate", f"{bitrate_kbps}k",
            "-minrate", f"{bitrate_kbps}k",
            "-bufsize", f"{bitrate_kbps * 2}k",
        ]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]


def process_video_with_segments(
    input_video: str,
    segments: List,
    timing_infos: List,
    segment_audios: Dict[int, np.ndarray],
    output_video: str,
    work_dir: str,
    sample_rate: int = 24000,
    options: Optional[VideoProcessOptions] = None,
    subtitle_ass_path: Optional[str] = None,
    final_audio_filter: str = "",
) -> Dict:
    """
    Video'yu segment bazinda hiz ayarlayarak isler.
    TTS seslerini yeni timeline'a gore yerlestirir.

    BATCH PROCESSING: Segment'leri gruplara bolup incremental isler.

    Args:
        input_video: Giris video yolu
        segments: Segment listesi
        timing_infos: TTS timing bilgileri
        segment_audios: Her segment icin TTS ses arrayi {index: audio}
        output_video: Cikis video yolu
        work_dir: Calisma dizini
        sample_rate: Ses ornekleme hizi
        options: Video isleme secenekleri
        subtitle_ass_path: Tek gecis altyazi ASS yolu
        final_audio_filter: Final mux oncesi audio_new_timeline.wav uzerine uygulanacak FFmpeg audio filter

    Returns:
        Islem sonucu bilgileri
    """
    if options is None:
        options = VideoProcessOptions()

    profile_steps = []
    max_output_profile: Dict[str, object] = {}
    subtitle_filter = subtitle_filter_value(subtitle_ass_path)

    def run_profiled_step(step_name: str, command: List[str], **kwargs):
        started = time.perf_counter()
        result = subprocess.run(command, **kwargs)
        elapsed = time.perf_counter() - started
        if options.collect_profile:
            profile_steps.append({
                "step": step_name,
                "seconds": round(elapsed, 3)
            })
        return result

    def validate_profiled(step_name: str, video_path: str, expected_duration: float):
        count_frames = options.count_frames_for_step(step_name)
        started = time.perf_counter()
        result = validate_video_stream(
            video_path,
            expected_duration,
            count_frames=count_frames
        )
        full_frame_fallback = False
        if result.frame_count <= 0:
            result = validate_video_stream(
                video_path,
                expected_duration,
                count_frames=True,
            )
            full_frame_fallback = True
        decode_probe_starts = []
        if options.decode_probes_for_step(step_name):
            decode_probe_starts = validate_video_decode_probes(
                video_path,
                result.duration,
            )
        elapsed = time.perf_counter() - started
        if options.collect_profile:
            profile_steps.append({
                "step": step_name,
                "seconds": round(elapsed, 3),
                "count_frames": count_frames,
                "full_frame_fallback": full_frame_fallback,
                "decode_probe_starts": [round(value, 3) for value in decode_probe_starts],
                "duration": round(result.duration, 3),
                "fps": round(result.fps, 3),
                "frame_count": result.frame_count
            })
        return result

    def enforce_max_output_size(
        step_name: str,
        command: List[str],
        expected_duration: float,
    ) -> List[str]:
        if not is_size_limited_output(options):
            return command
        actual_output_bytes = os.path.getsize(output_video)
        max_output_profile.update({
            "max_output_bytes": options.max_output_bytes,
            "first_output_bytes": actual_output_bytes,
            "first_video_bitrate_kbps": target_video_bitrate_kbps(options, expected_duration),
        })
        if actual_output_bytes <= options.max_output_bytes:
            max_output_profile.update({
                "retry_performed": False,
                "final_output_bytes": actual_output_bytes,
            })
            logger.info(
                "Maksimum MB kontrolu basarili: gercek=%d sinir=%d",
                actual_output_bytes,
                options.max_output_bytes,
            )
            return command
        corrected_bitrate = corrected_video_bitrate_kbps(
            options,
            expected_duration,
            actual_output_bytes,
        )
        retry_command = command_with_video_bitrate(command, corrected_bitrate)
        logger.warning(
            "Maksimum MB siniri asildi, yalniz video bitrate dusuruluyor: gercek=%d sinir=%d yeni_video_bitrate=%dk",
            actual_output_bytes,
            options.max_output_bytes,
            corrected_bitrate,
        )
        run_profiled_step(f"{step_name}_size_retry", retry_command, check=True)
        validate_profiled(f"{step_name}_size_retry_validate", output_video, expected_duration)
        retry_output_bytes = os.path.getsize(output_video)
        max_output_profile.update({
            "retry_performed": True,
            "retry_video_bitrate_kbps": corrected_bitrate,
            "final_output_bytes": retry_output_bytes,
        })
        if retry_output_bytes > options.max_output_bytes:
            raise RuntimeError(
                "Nihai video maksimum boyut sinirini tek video bitrate duzeltmesinden sonra da asti: "
                f"gercek={retry_output_bytes} sinir={options.max_output_bytes}"
            )
        logger.info(
            "Maksimum MB video bitrate duzeltmesi basarili: gercek=%d sinir=%d",
            retry_output_bytes,
            options.max_output_bytes,
        )
        return retry_command

    logger.info("Video segment bazli hiz ayarlama basliyor...")

    video_duration = get_video_duration(input_video)
    logger.info("Video suresi: %.2f saniye", video_duration)

    speed_infos = calculate_segment_speeds(segments, timing_infos)

    video_adjusted_count = sum(1 for s in speed_infos if s.action != "audio_adjust")
    logger.info(
        "Toplam %d segment, %d tanesinde video hizi ayarlanacak",
        len(speed_infos), video_adjusted_count
    )

    timeline = calculate_new_timeline(speed_infos, video_duration)

    total_new_duration = timeline[-1]["new_end"] if timeline else video_duration

    debug_path = os.path.join(work_dir, "segment_placement_debug.txt")
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write("SEGMENT YERLESTIRME DEBUG RAPORU\n")
        f.write("=" * 80 + "\n\n")
        f.write("Bu dosya her segmentin:\n")
        f.write("  - Orijinal video pozisyonunu\n")
        f.write("  - TTS ses suresi\n")
        f.write("  - YENİ video pozisyonunu (ses BURAYA yerlestirilecek)\n")
        f.write("  - Segment ses dosyasi bilgisini gosterir\n")
        f.write("=" * 80 + "\n\n")

        for item in timeline:
            if item["type"] != "segment":
                continue
            seg_idx = item["index"]
            orig_start = item["original_start"]
            orig_end = item["original_end"]
            orig_dur = item["original_duration"]
            new_start = item["new_start"]
            new_end = item["new_end"]
            new_dur = item["new_duration"]

            sample_count = audio_sample_count(segment_audios, seg_idx)
            if sample_count is not None:
                audio_dur = sample_count / sample_rate
                audio_status = f"MEVCUT ({audio_dur:.3f}s)"
            else:
                audio_dur = 0
                audio_status = "YOK!"

            f.write(f"SEGMENT {seg_idx}:\n")
            f.write(f"  Orijinal pozisyon : [{orig_start:7.3f}s - {orig_end:7.3f}s] (sure: {orig_dur:.3f}s)\n")
            f.write(f"  TTS ses suresi    : {new_dur:.3f}s\n")
            f.write(f"  YENİ pozisyon     : [{new_start:7.3f}s - {new_end:7.3f}s] << SES BURAYA YERLESTIRILECEK\n")
            f.write(f"  Ses dosyasi       : segment_{seg_idx}.wav - {audio_status}\n")
            f.write(f"  Video hizi        : {item.get('video_speed', 1.0):.2f}x\n")
            f.write("\n")

        f.write("=" * 80 + "\n")
        f.write(f"TOPLAM: {len([i for i in timeline if i['type'] == 'segment'])} segment\n")
        f.write(f"Orijinal video suresi: {timeline[0]['original_start']:.2f}s - {video_duration:.2f}s\n")
        f.write(f"Yeni video suresi    : 0.00s - {total_new_duration:.2f}s\n")

    logger.info("Segment yerlestirme debug raporu: %s", debug_path)

    new_audio = build_new_audio_mix(segment_audios, timeline, total_new_duration, sample_rate)
    new_audio_path = os.path.join(work_dir, "audio_new_timeline.wav")
    sf.write(new_audio_path, new_audio, sample_rate, subtype="FLOAT" if final_audio_filter else "PCM_16")
    del new_audio
    logger.info("Yeni timeline'a gore ses olusturuldu: %s", new_audio_path)

    final_audio_profile: Dict[str, str] = {}
    measured_audio_path = ""
    if str(final_audio_filter or "").strip():
        raw_audio_path = os.path.join(work_dir, "audio_new_timeline_before_final_profile.wav")
        profiled_audio_path = os.path.join(work_dir, "audio_new_timeline_profiled.wav")
        import shutil
        shutil.copy2(new_audio_path, raw_audio_path)
        profile_details = {}
        from dublaj_hatti.bolum_50_seslendirme.supertonic_tts import (
            SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER, resolve_supertonic_final_audio_profile,
        )
        if final_audio_filter == SUPERTONIC_FINAL_AUDIO_PROFILE_FILTER:
            profile_details = resolve_supertonic_final_audio_profile(raw_audio_path)
            final_audio_filter = profile_details["filter"]
        if is_size_limited_output(options):
            measured_audio_path = os.path.join(work_dir, "audio_new_timeline_max_mb.m4a")
            audio_filter_complex = f"[0:a]{final_audio_filter},asplit=2[pcm][aac]"
            cmd_audio_profile = [
                ffmpeg_yolu(),
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-i", new_audio_path,
                "-filter_complex", audio_filter_complex,
                "-map", "[pcm]",
                "-ar", str(sample_rate),
                "-ac", "1",
                "-c:a", "pcm_s24le",
                profiled_audio_path,
                "-map", "[aac]",
                "-ar", str(sample_rate),
                "-ac", "1",
                "-c:a", "aac",
                "-b:a", final_audio_bitrate(options),
                measured_audio_path,
            ]
            run_profiled_step("final_audio_profile_and_max_mb_audio_encode", cmd_audio_profile, check=True)
        else:
            cmd_audio_profile = [
                ffmpeg_yolu(),
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-i", new_audio_path,
                "-af", final_audio_filter,
                "-ar", str(sample_rate),
                "-ac", "1",
                "-c:a", "pcm_s24le",
                profiled_audio_path,
            ]
            run_profiled_step("final_audio_profile", cmd_audio_profile, check=True)
        os.replace(profiled_audio_path, new_audio_path)
        final_audio_profile = {
            **profile_details,
            "mode": "pre_final_mux",
            "filter": final_audio_filter,
            "raw_audio": raw_audio_path,
            "profiled_audio": new_audio_path,
            "timeline_audio": new_audio_path,
        }
        logger.info("Final audio profile mux oncesi uygulandi: %s", final_audio_filter)

    final_audio_input_path = new_audio_path
    if is_size_limited_output(options):
        if not measured_audio_path:
            measured_audio_path = os.path.join(work_dir, "audio_new_timeline_max_mb.m4a")
            cmd_measured_audio = [
                ffmpeg_yolu(),
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-i", new_audio_path,
                "-map", "0:a:0",
                "-vn",
                "-c:a", "aac",
                "-b:a", final_audio_bitrate(options),
                "-ar", str(sample_rate),
                "-ac", "1",
                measured_audio_path,
            ]
            run_profiled_step("max_mb_audio_encode", cmd_measured_audio, check=True)
        options.measured_audio_bytes = os.path.getsize(measured_audio_path)
        final_audio_input_path = measured_audio_path
        container_reserve_bytes = max_output_container_reserve_bytes(options)
        max_output_profile.update({
            "measured_audio_path": measured_audio_path,
            "measured_audio_bytes": options.measured_audio_bytes,
            "container_reserve_bytes": container_reserve_bytes,
            "video_budget_bytes": (
                options.max_output_bytes
                - container_reserve_bytes
                - options.measured_audio_bytes
            ),
            "video_bitrate_kbps": target_video_bitrate_kbps(options, total_new_duration),
        })
        logger.info(
            "Maksimum MB gercek ses butcesi hazir: ses=%d rezerv=%d video_bitrate=%dk",
            options.measured_audio_bytes,
            container_reserve_bytes,
            max_output_profile["video_bitrate_kbps"],
        )

    needs_video_processing = any(
        item.get("video_speed", 1.0) != 1.0
        for item in timeline
        if item["type"] == "segment"
    )

    if not needs_video_processing and not subtitle_filter and not is_size_limited_output(options):
        logger.info("Video hiz ayari gerekmiyor, sadece ses birlestiriliyor")
        cmd = [
            ffmpeg_yolu(),
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", input_video,
            "-i", new_audio_path,
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            output_video
        ]
        run_profiled_step("copy_video_mux", cmd, check=True)
        validate_profiled("copy_video_validate", output_video, total_new_duration)
    elif not needs_video_processing:
        logger.info("Video hiz ayari gerekmiyor, final video politikasi uygulanacak")
        cmd = [
            ffmpeg_yolu(),
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", input_video,
            "-i", final_audio_input_path,
        ]
        if subtitle_filter:
            cmd.extend(["-vf", subtitle_filter])
        cmd.extend([
            *video_encode_args(options, total_new_duration),
            "-map", "0:v:0",
            "-map", "1:a:0",
            *final_audio_encode_args(options),
            "-shortest",
            output_video
        ])
        successful_output_command = cmd
        try:
            run_profiled_step("copy_video_subtitle_mux", cmd, check=True)
            validate_profiled("copy_video_subtitle_validate", output_video, total_new_duration)
        except subprocess.CalledProcessError:
            fallback_cmd = [
                ffmpeg_yolu(),
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-i", input_video,
                "-i", final_audio_input_path,
            ]
            if subtitle_filter:
                fallback_cmd.extend(["-vf", subtitle_filter])
            fallback_cmd.extend([
                *fallback_video_encode_args(options, total_new_duration),
                "-map", "0:v:0",
                "-map", "1:a:0",
                *final_audio_encode_args(options),
                "-shortest",
                output_video
            ])
            run_profiled_step("copy_video_subtitle_mux_fallback_libx264", fallback_cmd, check=True)
            validate_profiled("copy_video_subtitle_fallback_validate", output_video, total_new_duration)
            successful_output_command = fallback_cmd
        enforce_max_output_size(
            "copy_video_subtitle_mux",
            successful_output_command,
            total_new_duration,
        )
    else:
        logger.info("Video hiz ayari uygulanacak...")

        batch_size = calculate_adaptive_batch_size(len(timeline))
        batch_ranges = build_timeline_batch_ranges(timeline, batch_size)
        total_batches = len(batch_ranges)

        logger.info("BATCH PROCESSING: %d segment, batch_size=%d, total_batches=%d",
                    len(timeline), batch_size, total_batches)

        def process_batch(batch_idx: int, batch_range: Tuple[int, int]) -> str:
            start_idx, end_idx = batch_range
            batch_timeline = timeline[start_idx:end_idx]

            logger.info("Batch %d/%d: segment %d-%d islenimi (%d segment)",
                        batch_idx + 1, total_batches, start_idx, end_idx - 1, len(batch_timeline))

            batch_start = min(item["original_start"] for item in batch_timeline)
            batch_end = max(item["original_end"] for item in batch_timeline)

            batch_new_start = min(item["new_start"] for item in batch_timeline)
            batch_expected_duration = sum(
                item.get("new_duration", 0.0)
                for item in batch_timeline
            )
            filter_complex = build_ffmpeg_filter_complex(
                batch_timeline,
                batch_expected_duration,
                time_offset=batch_start,
                subtitle_filter=subtitle_filter,
                subtitle_time_offset=batch_new_start,
            )

            temp_video = os.path.join(work_dir, f"temp_batch_{batch_idx}.mp4")
            filter_script_path = os.path.join(work_dir, f"filter_batch_{batch_idx}.txt")

            with open(filter_script_path, "w", encoding="utf-8") as f:
                f.write(filter_complex)

            cmd = [
                ffmpeg_yolu(),
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-ss", str(batch_start),
                "-to", str(batch_end),
                "-i", input_video,
                "-/filter_complex", filter_script_path,  # ffmpeg 7+ (eski -filter_complex_script 9.x’te yok)
                "-map", "[outv]",
                *video_encode_args(options, total_new_duration),
                "-an",
                temp_video
            ]

            try:
                run_profiled_step(
                    f"batch_{batch_idx}_encode_nvenc",
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True
                )
                validate_profiled(
                    f"batch_{batch_idx}_validate",
                    temp_video,
                    batch_expected_duration
                )
                logger.info("Batch %d/%d tamamlandi", batch_idx + 1, total_batches)
            except subprocess.CalledProcessError as e:
                logger.error("FFmpeg hatasi (Batch %d): %s", batch_idx + 1, e.stderr)
                raise
            except Exception as e:
                logger.error("Batch %d video stream bozuk: %s", batch_idx + 1, e)
                logger.info("Batch %d h264_nvenc ile tekrar uretiliyor", batch_idx + 1)
                run_profiled_step(
                    f"batch_{batch_idx}_retry_nvenc",
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True
                )
                try:
                    validate_profiled(
                        f"batch_{batch_idx}_retry_validate",
                        temp_video,
                        batch_expected_duration
                    )
                    logger.info("Batch %d/%d h264_nvenc tekrar denemesi ile tamamlandi", batch_idx + 1, total_batches)
                    return temp_video
                except Exception as retry_error:
                    logger.error("Batch %d h264_nvenc tekrar denemesi basarisiz: %s", batch_idx + 1, retry_error)

                logger.info("Batch %d CPU libx264 yedek yontem ile tekrar uretiliyor", batch_idx + 1)
                fallback_video = os.path.join(work_dir, f"temp_batch_{batch_idx}_libx264.mp4")
                fallback_cmd = [
                    ffmpeg_yolu(),
                    "-hide_banner",
                    "-loglevel", "error",
                    "-y",
                    "-ss", str(batch_start),
                    "-to", str(batch_end),
                    "-i", input_video,
                    "-/filter_complex", filter_script_path,  # ffmpeg 7+ (eski -filter_complex_script 9.x’te yok)
                    "-map", "[outv]",
                    *fallback_video_encode_args(options, total_new_duration),
                    "-an",
                    fallback_video
                ]
                run_profiled_step(
                    f"batch_{batch_idx}_fallback_libx264",
                    fallback_cmd,
                    check=True,
                    capture_output=True,
                    text=True
                )
                validate_profiled(
                    f"batch_{batch_idx}_fallback_validate",
                    fallback_video,
                    batch_expected_duration
                )
                if os.path.exists(temp_video):
                    os.remove(temp_video)
                temp_video = fallback_video
                logger.info("Batch %d/%d CPU libx264 yedek yontem ile tamamlandi", batch_idx + 1, total_batches)
            return temp_video

        batch_workers = min(3, total_batches) if subtitle_filter and total_batches > 1 else 1
        logger.info("Batch paralellik: worker=%d", batch_workers)
        if batch_workers > 1:
            batch_jobs = order_batch_jobs_by_expected_duration(timeline, batch_ranges)
            logger.info(
                "Batch calisma sirasi: %s",
                ",".join(str(value[0] + 1) for value in batch_jobs),
            )
            with ThreadPoolExecutor(max_workers=batch_workers) as executor:
                batch_futures = {
                    batch_idx: executor.submit(process_batch, batch_idx, batch_range)
                    for batch_idx, batch_range in batch_jobs
                }
                batch_results = {}
                failed_batch_indices = []
                for batch_idx in range(total_batches):
                    try:
                        batch_results[batch_idx] = batch_futures[batch_idx].result()
                    except Exception as error:
                        logger.error(
                            "Paralel batch %d basarisiz, sirali yeniden denenecek: %s",
                            batch_idx + 1,
                            error,
                        )
                        failed_batch_indices.append(batch_idx)
            for batch_idx in failed_batch_indices:
                batch_results[batch_idx] = process_batch(batch_idx, batch_ranges[batch_idx])
            batch_videos = [batch_results[batch_idx] for batch_idx in range(total_batches)]
        else:
            batch_videos = [
                process_batch(batch_idx, batch_range)
                for batch_idx, batch_range in enumerate(batch_ranges)
            ]

        try:
            import torch
            import gc
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("CUDA cache temizlendi (Tum batchler)")
            gc.collect()
        except Exception:
            pass

        if total_batches > 1:
            logger.info("Batch videolari birlestiriliyor: %d adet", len(batch_videos))
            concat_list_path = os.path.join(work_dir, "concat_list.txt")
            with open(concat_list_path, "w", encoding="utf-8") as f:
                for video_path in batch_videos:
                    f.write(f"file '{video_path}'\n")

            final_temp_video = os.path.join(work_dir, "final_concat.mp4")
            cmd_concat = [
                ffmpeg_yolu(),
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_path,
                "-c", "copy",
                final_temp_video
            ]
            run_profiled_step("concat_batches", cmd_concat, check=True)
            logger.info("Batch birlestirme tamamlandi")
        else:
            final_temp_video = batch_videos[0]

        cmd_final = [
            ffmpeg_yolu(),
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", final_temp_video,
            "-i", final_audio_input_path,
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            *final_audio_encode_args(options),
            "-shortest",
            output_video,
        ]
        active_final_command = cmd_final
        try:
            run_profiled_step("final_mux", cmd_final, check=True)
        except subprocess.CalledProcessError:
            logger.info("Final video stream copy mux basarisiz, CPU libx264 yedek yontem deneniyor")
            cmd_final_encode_fallback = [
                ffmpeg_yolu(),
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-i", final_temp_video,
                "-i", final_audio_input_path,
            ]
            cmd_final_encode_fallback.extend([
                *fallback_video_encode_args(options, total_new_duration),
                "-map", "0:v:0",
                "-map", "1:a:0",
                *final_audio_encode_args(options),
                "-shortest",
                output_video
            ])
            run_profiled_step("final_mux_copy_fallback_libx264", cmd_final_encode_fallback, check=True)
            active_final_command = cmd_final_encode_fallback

        try:
            validate_profiled("final_validate", output_video, total_new_duration)
        except Exception as e:
            logger.error("Final video stream bozuk: %s", e)
            logger.info("Final video birlestirme ayni yontemle tekrar uretiliyor")
            run_profiled_step("final_mux_retry", active_final_command, check=True)
            final_retry_ok = False
            try:
                validate_profiled("final_retry_validate", output_video, total_new_duration)
                logger.info("Final video birlestirme tekrar denemesi ile tamamlandi")
                final_retry_ok = True
            except Exception as retry_error:
                logger.error("Final video birlestirme tekrar denemesi basarisiz: %s", retry_error)

            if not final_retry_ok:
                logger.info("Final video birlestirme CPU libx264 yedek yontem ile tekrar uretiliyor")
                cmd_final_fallback = [
                    ffmpeg_yolu(),
                    "-hide_banner",
                    "-loglevel", "error",
                    "-y",
                    "-i", final_temp_video,
                    "-i", final_audio_input_path,
                ]
                cmd_final_fallback.extend([
                    *fallback_video_encode_args(options, total_new_duration),
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    *final_audio_encode_args(options),
                    "-shortest",
                    output_video
                ])
                run_profiled_step("final_mux_fallback_libx264", cmd_final_fallback, check=True)
                validate_profiled("final_fallback_validate", output_video, total_new_duration)
                active_final_command = cmd_final_fallback

        size_retry_command = [
            ffmpeg_yolu(),
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", final_temp_video,
            "-i", final_audio_input_path,
            *video_encode_args(options, total_new_duration),
            "-map", "0:v:0",
            "-map", "1:a:0",
            *final_audio_encode_args(options),
            "-shortest",
            output_video,
        ] if is_size_limited_output(options) else active_final_command
        enforce_max_output_size(
            "final_mux",
            size_retry_command,
            total_new_duration,
        )

        for temp_file in batch_videos:
            if os.path.exists(temp_file):
                os.remove(temp_file)

        concat_list_path = os.path.join(work_dir, "concat_list.txt")
        if os.path.exists(concat_list_path):
            os.remove(concat_list_path)

        final_concat = os.path.join(work_dir, "final_concat.mp4")
        if os.path.exists(final_concat):
            os.remove(final_concat)

    logger.info("Video isleme tamamlandi: %s", output_video)

    try:
        import torch
        import gc
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            logger.info("CUDA cache temizlendi (video_processor)")
        gc.collect()
        logger.info("GC calistirildi (video_processor)")
    except Exception as e:
        logger.warning("CUDA temizlik hatasi (gorulmezden gelindi): %s", e)

    return {
        "success": True,
        "output_video": output_video,
        "original_duration": video_duration,
        "new_duration": total_new_duration,
        "segments_processed": len(speed_infos),
        "video_adjusted_segments": video_adjusted_count,
        "timeline": timeline,
        "speed_infos": speed_infos,
        "profile_steps": profile_steps,
        "subtitle_ass_path": subtitle_ass_path if subtitle_filter else "",
        "final_audio_profile": final_audio_profile,
        "max_output_profile": max_output_profile,
    }


def write_speed_report(
    speed_infos: List[SegmentSpeedInfo],
    timeline: List[Dict],
    output_path: str
) -> None:
    """
    Hiz ayarlama raporunu dosyaya yazar.

    Args:
        speed_infos: Hiz bilgileri
        timeline: Zaman cizelgesi
        output_path: Rapor dosya yolu
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("VIDEO HIZ AYARLAMA RAPORU\n")
        f.write("=" * 70 + "\n\n")

        f.write("SEGMENT BAZLI HIZ BILGILERI\n")
        f.write("-" * 70 + "\n")
        f.write(f"{'Seg':>4} | {'Orijinal':>12} | {'TTS':>8} | {'Faktor':>8} | {'Aksiyon':>15} | {'Video Hiz':>10}\n")
        f.write("-" * 70 + "\n")

        for info in speed_infos:
            f.write(
                f"{info.index:>4} | "
                f"{info.original_duration:>10.2f}s | "
                f"{info.tts_duration:>6.2f}s | "
                f"{info.speed_factor:>7.2f}x | "
                f"{info.action:>15} | "
                f"{info.video_speed:>9.2f}x\n"
            )

        f.write("\n" + "=" * 70 + "\n")
        f.write("ZAMAN CIZELGESI\n")
        f.write("-" * 70 + "\n")

        for item in timeline:
            if item["type"] == "segment":
                f.write(
                    f"SEGMENT {item['index']:>3}: "
                    f"[{item['original_start']:>6.2f}s - {item['original_end']:>6.2f}s] -> "
                    f"[{item['new_start']:>6.2f}s - {item['new_end']:>6.2f}s] "
                    f"(video: {item['video_speed']:.2f}x)\n"
                )
            else:
                f.write(
                    f"GAP        : "
                    f"[{item['original_start']:>6.2f}s - {item['original_end']:>6.2f}s] -> "
                    f"[{item['new_start']:>6.2f}s - {item['new_end']:>6.2f}s] "
                    f"(degismedi)\n"
                )

        f.write("\n" + "=" * 70 + "\n")
