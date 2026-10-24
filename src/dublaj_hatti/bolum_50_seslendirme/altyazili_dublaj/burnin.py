# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


VALID_SUBTITLE_MODES = {"none", "segment", "word", "rollup"}
FIXED_FONT_SIZE = 72
HORIZONTAL_CANVAS_WIDTH = 1920
HORIZONTAL_CANVAS_HEIGHT = 1080
HORIZONTAL_WIDTH_RATIO = 0.74
HORIZONTAL_BOX_HEIGHT = 104
HORIZONTAL_BOTTOM_MARGIN = 70
VERTICAL_CANVAS_WIDTH = 1080
VERTICAL_CANVAS_HEIGHT = 1920
VERTICAL_WIDTH_RATIO = 0.82
VERTICAL_BOX_HEIGHT = 108
VERTICAL_BOTTOM_MARGIN = 210
SQUARE_CANVAS_WIDTH = 1080
SQUARE_CANVAS_HEIGHT = 1080
SQUARE_WIDTH_RATIO = 0.78
SQUARE_BOX_HEIGHT = 104
SQUARE_BOTTOM_MARGIN = 110
FEMALE_BOX_STYLE = "BoxFemale"
MALE_BOX_STYLE = "Box"
VIDEO_FAMILY_HORIZONTAL = "horizontal"
VIDEO_FAMILY_VERTICAL = "vertical"
VIDEO_FAMILY_SQUARE = "square"


@dataclass(frozen=True)
class SubtitleStyle:
    canvas_width: int = SQUARE_CANVAS_WIDTH
    canvas_height: int = SQUARE_CANVAS_HEIGHT
    width_ratio: float = SQUARE_WIDTH_RATIO
    bottom_margin: int = SQUARE_BOTTOM_MARGIN
    horizontal_padding_ratio: float = 0.0
    max_lines: int = 1
    box_height: int = SQUARE_BOX_HEIGHT
    font_size: int = FIXED_FONT_SIZE


def classify_video_family(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return VIDEO_FAMILY_SQUARE
    ratio = width / height
    if ratio > 1.10:
        return VIDEO_FAMILY_HORIZONTAL
    if ratio < 0.90:
        return VIDEO_FAMILY_VERTICAL
    return VIDEO_FAMILY_SQUARE


def is_vertical_9_16_video(width: int, height: int) -> bool:
    return classify_video_family(width, height) == VIDEO_FAMILY_VERTICAL


def calculate_design_canvas_width(width: int, height: int, canvas_height: int, fallback_width: int) -> int:
    if width <= 0 or height <= 0:
        return fallback_width
    return max(1, int(round(canvas_height * width / height)))


def resolve_subtitle_style_for_video(width: int, height: int, style: SubtitleStyle) -> SubtitleStyle:
    video_family = classify_video_family(width, height)
    if video_family == VIDEO_FAMILY_HORIZONTAL:
        return SubtitleStyle(
            canvas_width=calculate_design_canvas_width(
                width,
                height,
                HORIZONTAL_CANVAS_HEIGHT,
                HORIZONTAL_CANVAS_WIDTH,
            ),
            canvas_height=HORIZONTAL_CANVAS_HEIGHT,
            width_ratio=HORIZONTAL_WIDTH_RATIO,
            bottom_margin=HORIZONTAL_BOTTOM_MARGIN,
            horizontal_padding_ratio=style.horizontal_padding_ratio,
            max_lines=style.max_lines,
            box_height=HORIZONTAL_BOX_HEIGHT,
            font_size=style.font_size,
        )
    if video_family == VIDEO_FAMILY_VERTICAL:
        return SubtitleStyle(
            canvas_width=calculate_design_canvas_width(
                width,
                height,
                VERTICAL_CANVAS_HEIGHT,
                VERTICAL_CANVAS_WIDTH,
            ),
            canvas_height=VERTICAL_CANVAS_HEIGHT,
            width_ratio=VERTICAL_WIDTH_RATIO,
            bottom_margin=VERTICAL_BOTTOM_MARGIN,
            horizontal_padding_ratio=style.horizontal_padding_ratio,
            max_lines=style.max_lines,
            box_height=VERTICAL_BOX_HEIGHT,
            font_size=style.font_size,
        )
    return SubtitleStyle(
        canvas_width=calculate_design_canvas_width(
            width,
            height,
            style.canvas_height,
            style.canvas_width,
        ),
        canvas_height=style.canvas_height,
        width_ratio=style.width_ratio,
        bottom_margin=style.bottom_margin,
        horizontal_padding_ratio=style.horizontal_padding_ratio,
        max_lines=style.max_lines,
        box_height=style.box_height,
        font_size=style.font_size,
    )


def normalize_subtitle_mode(value: str | None) -> str:
    mode = str(value or "none").strip().lower()
    return mode if mode in VALID_SUBTITLE_MODES else "none"


def burn_subtitles_into_video(
    input_video: str,
    output_video: str,
    run_dir: str,
    language: str,
    mode: str,
    timeline: list[dict[str, Any]] | None = None,
    *,
    engine: str,
    debug_dir_name: str,
    engine_label: str,
    timing_contract_path: str = "",
) -> dict[str, Any]:
    report = prepare_subtitle_burnin_assets(
        input_video=input_video,
        output_video=output_video,
        run_dir=run_dir,
        language=language,
        mode=mode,
        timeline=timeline,
        burn_strategy="post_encode_burnin",
        engine=engine,
        debug_dir_name=debug_dir_name,
        engine_label=engine_label,
        timing_contract_path=timing_contract_path,
    )
    if not report.get("enabled"):
        return report
    Path(output_video).parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg_subtitle_burn(input_video, str(report["ass_path"]), output_video)
    return report


def prepare_subtitle_burnin_assets(
    input_video: str,
    output_video: str,
    run_dir: str,
    language: str,
    mode: str,
    timeline: list[dict[str, Any]] | None = None,
    burn_strategy: str = "one_pass_final_mux",
    *,
    engine: str,
    debug_dir_name: str,
    engine_label: str,
    timing_contract_path: str,
) -> dict[str, Any]:
    mode = normalize_subtitle_mode(mode)
    if mode == "none":
        return {"enabled": False, "mode": "none", "output_video": input_video}

    from .timing_contract import load_subtitle_timing_contract

    debug_dir = Path(run_dir) / debug_dir_name
    lang = str(language or "tr").strip().lower()[:2] or "tr"
    contract = load_subtitle_timing_contract(
        timing_contract_path,
        run_dir=run_dir,
        expected_engine=engine,
        expected_language=lang,
    )
    timeline_path = Path(contract["word_timeline_path"])
    words = attach_segment_gender_to_words(
        adjust_words_to_video_timeline(json.loads(timeline_path.read_text(encoding="utf-8")), timeline or []),
        debug_dir,
        lang,
    )
    timing_source = str(contract["timing_source"])
    timing_report_path = Path(contract["timing_report_path"])

    if not words:
        raise RuntimeError(f"{engine_label} altyazi timing dosyasi bos: {timeline_path}")

    width, height = probe_video_size(input_video)
    ass_path = debug_dir / f"burnin_{mode}_{lang}.ass"
    report_path = debug_dir / f"burnin_{mode}_{lang}.json"
    style = resolve_subtitle_style_for_video(width, height, SubtitleStyle())
    video_family = classify_video_family(width, height)
    rollup_report = None
    if mode == "rollup":
        from .rollup import build_ass, rollup_contract_inputs

        canvas_height = 1080
        canvas_width = round(width / height * canvas_height)
        duration = max(float(word["end"]) for word in words) + 1.0
        if timeline:
            duration = max(float(item["new_end"]) for item in timeline)
        runtime_contract = rollup_contract_inputs()
        ass_text, rollup_report = build_ass(
            words, canvas_width, canvas_height, duration, runtime_contract["rollup_profile"]
        )
        rollup_report["runtime_contract"] = runtime_contract
        pages = []
    else:
        pages = build_subtitle_pages(words, mode, style)
        ass_text = build_ass_subtitles(pages, width, height, style)
    ass_path.write_text(ass_text, encoding="utf-8", newline="\n")
    report = {
        "enabled": True,
        "mode": mode,
        "input_video": input_video,
        "output_video": output_video,
        "ass_path": str(ass_path),
        "timeline_path": str(timeline_path),
        "timing_source": timing_source,
        "timing_method": str(contract["timing_method"]),
        "timing_contract_path": str(contract["contract_path"]),
        "timing_report_path": str(timing_report_path),
        "timing_contract_schema_version": int(contract["schema_version"]),
        "video_width": width,
        "video_height": height,
        "page_count": len(pages),
        "design_canvas_width": style.canvas_width,
        "design_canvas_height": style.canvas_height,
        "width_ratio": style.width_ratio,
        "bottom_margin": style.bottom_margin,
        "video_family": video_family,
        "is_vertical_9_16": is_vertical_9_16_video(width, height),
        "layout_mode": "container_based_subtitle_layout",
        "container_max_lines": style.max_lines,
        "container_padding_ratio": style.horizontal_padding_ratio,
        "fixed_box_height": style.box_height,
        "fixed_font_size": style.font_size,
        "burn_strategy": burn_strategy,
    }
    if rollup_report is not None:
        report.update({
            "page_count": rollup_report["line_count"],
            "design_canvas_width": canvas_width,
            "design_canvas_height": canvas_height,
            "width_ratio": rollup_report["width_ratio"],
            "bottom_margin": rollup_report["bottom_margin"],
            "layout_mode": "multiline_rollup",
            "container_max_lines": rollup_report["row_count"],
            "container_padding_ratio": rollup_report["horizontal_padding"] / rollup_report["container_width"],
            "fixed_box_height": rollup_report["container_height"],
            "fixed_font_size": rollup_report["font_size"],
            "rollup": rollup_report,
        })
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return report


def adjust_words_to_video_timeline(words: list[dict[str, Any]], timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not timeline:
        return words
    segment_map = {
        int(item["index"]): item
        for item in timeline
        if item.get("type") == "segment" and "index" in item
    }
    adjusted = []
    for word in words:
        item = dict(word)
        segment_index = int(item.get("segment_index", 0))
        segment_info = segment_map.get(segment_index)
        if segment_info:
            original_start = float(segment_info.get("original_start", 0.0))
            new_start = float(segment_info.get("new_start", original_start))
            item["start"] = round(new_start + max(float(item.get("start", 0.0)) - original_start, 0.0), 6)
            item["end"] = round(new_start + max(float(item.get("end", 0.0)) - original_start, 0.0), 6)
            item["video_timeline_adjusted"] = True
        adjusted.append(item)
    return adjusted


def attach_segment_gender_to_words(words: list[dict[str, Any]], debug_dir: Path, lang: str) -> list[dict[str, Any]]:
    report_path = debug_dir / f"timing_report_{lang}.json"
    if not report_path.exists():
        return words
    report = json.loads(report_path.read_text(encoding="utf-8"))
    segment_gender = {
        int(item.get("segment_index", 0) or 0): str(item.get("gender", "") or "").strip().lower()
        for item in report.get("segments", [])
    }
    result = []
    for word in words:
        item = dict(word)
        gender = str(item.get("gender", "") or "").strip().lower()
        if not gender:
            gender = segment_gender.get(int(item.get("segment_index", 0) or 0), "")
        item["gender"] = gender
        result.append(item)
    return result


def probe_video_size(video_path: str) -> tuple[int, int]:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    streams = data.get("streams") or []
    if not streams:
        raise RuntimeError(f"Video stream bulunamadi: {video_path}")
    width = int(streams[0].get("width") or 0)
    height = int(streams[0].get("height") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Video boyutu okunamadi: {video_path}")
    return width, height


def build_subtitle_pages(words: list[dict[str, Any]], mode: str, style: SubtitleStyle) -> list[dict[str, Any]]:
    mode = normalize_subtitle_mode(mode)
    sorted_words = sorted(words, key=lambda item: (int(item.get("segment_index", 0)), float(item.get("start", 0.0))))
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in sorted_words:
        grouped.setdefault(int(item.get("segment_index", 0)), []).append(item)
    pages = []
    for segment_index in sorted(grouped):
        segment_words = grouped[segment_index]
        if not segment_words:
            continue
        start = float(segment_words[0].get("start", 0.0))
        end = float(segment_words[-1].get("end", start + 0.1))
        pages.append({
            "segment_index": segment_index,
            "page_index": 0,
            "start": start,
            "end": max(end, start + 0.1),
            "gender": resolve_page_gender(segment_words),
            "words": segment_words,
            "lines": split_words_evenly(segment_words, style.max_lines),
        })
    return pages


def resolve_page_gender(words: list[dict[str, Any]]) -> str:
    for word in words:
        gender = str(word.get("gender", "") or "").strip().lower()
        if gender:
            return gender
    return ""


def build_ass_subtitles(pages: list[dict[str, Any]], width: int, height: int, style: SubtitleStyle) -> str:
    style = resolve_subtitle_style_for_video(width, height, style)
    canvas_width = style.canvas_width
    canvas_height = style.canvas_height
    box_width = int(canvas_width * style.width_ratio)
    box_height = style.box_height
    box_left = int((canvas_width - box_width) / 2)
    box_top = int(canvas_height - style.bottom_margin - box_height)
    box_right = box_left + box_width
    box_bottom = box_top + box_height
    text_left = box_left + int(box_width * style.horizontal_padding_ratio)
    text_right = box_right - int(box_width * style.horizontal_padding_ratio)
    text_width = max(1, text_right - text_left)
    text_x = int(canvas_width / 2)
    font_size = calculate_fixed_font_size(box_height, style)
    line_y_positions = calculate_line_y_positions(box_top, box_height, style.max_lines)
    events = []
    for page in pages:
        for visual_page in split_page_by_box_width(page, text_width, font_size):
            start = float(visual_page["start"])
            end = float(visual_page["end"])
            visual_font_size = int(visual_page.get("font_size", font_size))
            box_style = subtitle_box_style_for_gender(str(visual_page.get("gender", "") or ""))
            events.append(_ass_event(0, start, end, box_style, _ass_box(box_left, box_top, box_right, box_bottom)))
            layout_lines = [visual_page["words"]]
            intervals = build_page_intervals(visual_page)
            for interval_start, interval_end, active_key in intervals:
                cursor = 0
                for line_index, line_words in enumerate(layout_lines):
                    text = build_line_text(visual_page, line_words, cursor, active_key)
                    override = f"{{\\an5\\pos({text_x},{line_y_positions[line_index]})\\fs{visual_font_size}\\clip({box_left},{box_top},{box_right},{box_bottom})}}"
                    events.append(_ass_event(1, interval_start, interval_end, "Text", override + text))
                    cursor += len(line_words)
    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {canvas_width}",
        f"PlayResY: {canvas_height}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Text,Arial,{font_size},&H00FFFFFF,&H0000FFFF,&H90000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,5,0,0,0,1",
        "Style: Box,Arial,20,&H90000000,&H90000000,&H90000000,&H90000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        "Style: BoxFemale,Arial,20,&H90A34FFF,&H90A34FFF,&H90A34FFF,&H90A34FFF,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    return "\n".join(header + events) + "\n"


def calculate_fixed_font_size(box_height: int, style: SubtitleStyle) -> int:
    return style.font_size


def split_page_by_box_width(page: dict[str, Any], box_width: int, font_size: int) -> list[dict[str, Any]]:
    words = list(page["words"])
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for word in words:
        candidate = current + [word]
        if not current or measure_text_width(candidate, font_size) <= box_width:
            current = candidate
            continue
        chunks.append(current)
        current = [word]
    if current:
        chunks.append(current)

    visual_pages = []
    for chunk_index, chunk in enumerate(chunks):
        next_chunk = chunks[chunk_index + 1] if chunk_index + 1 < len(chunks) else None
        start = float(chunk[0].get("start", page["start"]))
        end = float(chunk[-1].get("end", page["end"]))
        if next_chunk:
            next_start = float(next_chunk[0].get("start", end))
            end = max(start + 0.1, min(end, next_start))
        chunk_font_size = font_size
        if len(chunk) == 1 and measure_text_width(chunk, chunk_font_size) > box_width:
            chunk_font_size = calculate_single_word_fit_font_size(chunk, box_width, font_size)
        visual_pages.append({
            "segment_index": int(page["segment_index"]),
            "page_index": int(page["page_index"]) * 1000 + chunk_index,
            "start": start,
            "end": max(end, start + 0.1),
            "gender": str(page.get("gender", "") or ""),
            "words": chunk,
            "lines": [chunk],
            "font_size": chunk_font_size,
        })
    return visual_pages


def subtitle_box_style_for_gender(gender: str) -> str:
    return FEMALE_BOX_STYLE if str(gender or "").strip().lower() == "female" else MALE_BOX_STYLE


def estimate_text_width(words: list[dict[str, Any]], font_size: int) -> float:
    return measure_text_width(words, font_size)


def measure_text_width(words: list[dict[str, Any]], font_size: int) -> float:
    text = " ".join(str(word.get("word") or "") for word in words)
    if not text:
        return 0.0
    font = load_subtitle_font(font_size)
    image = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(image)
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return float(right - left)


def calculate_single_word_fit_font_size(words: list[dict[str, Any]], box_width: int, font_size: int) -> int:
    size = int(font_size)
    while size > 10 and measure_text_width(words, size) > box_width:
        size -= 1
    return max(10, size)


@lru_cache(maxsize=64)
def load_subtitle_font(font_size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("arial.ttf", int(font_size))


def split_words_evenly(words: list[dict[str, Any]], max_lines: int) -> list[list[dict[str, Any]]]:
    if not words:
        return [[]]
    line_count = min(max_lines, max(len(words), 1))
    chunk_size = max(1, int((len(words) + line_count - 1) / line_count))
    return [words[index:index + chunk_size] for index in range(0, len(words), chunk_size)][:max_lines]


def calculate_line_y_positions(box_top: int, box_height: int, line_count: int) -> list[int]:
    if line_count <= 1:
        return [int(box_top + box_height / 2)]
    return [
        int(box_top + (box_height * (index + 0.5) / line_count))
        for index in range(line_count)
    ]


def build_page_intervals(page: dict[str, Any]) -> list[tuple[float, float, str]]:
    points = {float(page["start"]), float(page["end"])}
    for word in page["words"]:
        points.add(max(float(page["start"]), float(word.get("start", page["start"]))))
        points.add(min(float(page["end"]), float(word.get("end", page["end"]))))
    sorted_points = sorted(point for point in points if float(page["start"]) <= point <= float(page["end"]))
    intervals = []
    for start, end in zip(sorted_points, sorted_points[1:]):
        if end <= start:
            continue
        active_key = ""
        middle = (start + end) / 2
        for index, word in enumerate(page["words"]):
            if float(word.get("start", 0.0)) <= middle <= float(word.get("end", 0.0)):
                active_key = _word_key(page, index)
                break
        intervals.append((start, end, active_key))
    return intervals or [(float(page["start"]), float(page["end"]), "")]


def build_line_text(
    page: dict[str, Any],
    line_words: list[dict[str, Any]],
    start_index: int,
    active_key: str,
) -> str:
    parts = []
    for offset, word in enumerate(line_words):
        key = _word_key(page, start_index + offset)
        text = escape_ass_text(str(word.get("word") or ""))
        if key == active_key:
            parts.append(r"{\c&H00FFFF&\bord4\3c&H000000&}" + text + r"{\c&HFFFFFF&\bord2}")
        else:
            parts.append(text)
    return " ".join(parts)


def run_ffmpeg_subtitle_burn(input_video: str, ass_path: str, output_video: str) -> None:
    filter_value = f"subtitles='{escape_ffmpeg_filter_path(ass_path)}'"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", input_video,
        "-vf", filter_value,
        "-c:v", "h264_nvenc",
        "-preset", "p2",
        "-cq", "26",
        "-c:a", "copy",
        output_video,
    ]
    from dublaj_hatti.bolum_60_video_ve_encode.kodlayici import nvenc_kullanilabilir

    if not nvenc_kullanilabilir():
        i = cmd.index("h264_nvenc")
        cmd[i - 1:i + 5] = ["-c:v", "libx264", "-preset", "medium", "-crf", "26"]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        fallback = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", input_video,
            "-vf", filter_value,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "copy",
            output_video,
        ]
        subprocess.run(fallback, check=True, capture_output=True, text=True)


def escape_ffmpeg_filter_path(path: str) -> str:
    value = os.path.abspath(path).replace("\\", "/")
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    return value


def escape_ass_text(value: str) -> str:
    return value.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", " ")


def _word_key(page: dict[str, Any], index: int) -> str:
    return f"{int(page['segment_index'])}:{int(page['page_index'])}:{index}"


def _ass_event(layer: int, start: float, end: float, style: str, text: str) -> str:
    return f"Dialogue: {layer},{_ass_time(start)},{_ass_time(end)},{style},,0,0,0,,{text}"


def _ass_box(left: int, top: int, right: int, bottom: int) -> str:
    return rf"{{\p1\pos(0,0)}}m {left} {top} l {right} {top} l {right} {bottom} l {left} {bottom}"


def _ass_time(seconds: float) -> str:
    seconds = max(float(seconds), 0.0)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    whole = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        whole += 1
        centis -= 100
    return f"{hours:d}:{minutes:02d}:{whole:02d}.{centis:02d}"
