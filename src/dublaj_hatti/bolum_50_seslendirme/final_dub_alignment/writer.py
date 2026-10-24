from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any

DEBUG_DIR_NAME = "final_dub_alignment"
WORD_TIMING_METHOD = "final_timeline_clean_dub_audio_forced_alignment"
ENGINE_DEBUG_DIRS = {
    "edge": "edge_tts_timing_debug",
    "supertonic": "supertonic_timing_debug",
    "xtts": "xtts_timing_debug",
    "voxcpm2": "voxcpm2_timing_debug",
}


def write_final_dub_alignment_debug(
    run_dir: str,
    language: str,
    segments: list,
    words: list[dict[str, Any]],
    engine: str,
    debug_dir_name: str = DEBUG_DIR_NAME,
    timing_source: str = "final_dub_audio_forced_alignment",
    timing_method: str = WORD_TIMING_METHOD,
    video_filename: str | None = None,
    page_title: str = "Final Dub Alignment",
    page_hint: str | None = None,
) -> dict[str, str]:
    debug_dir = Path(run_dir) / debug_dir_name
    debug_dir.mkdir(parents=True, exist_ok=True)
    lang = str(language or "tr").strip().lower()[:2] or "tr"
    engine_key = str(engine or "").strip().lower()
    resolved_video_filename = _resolve_video_filename(video_filename, lang)
    resolved_page_title = str(page_title or "").strip()
    if not resolved_page_title:
        raise ValueError("page_title must not be empty")
    resolved_page_hint = str(page_hint).strip() if page_hint is not None else f"Final dub alignment - {engine_key}"
    if not resolved_page_hint:
        raise ValueError("page_hint must not be empty")
    segment_records = []
    for segment in segments:
        segment_records.append({
            "segment_index": int(getattr(segment, "index", 0) or 0),
            "start": round(float(getattr(segment, "start", 0.0) or 0.0), 6),
            "end": round(float(getattr(segment, "end", 0.0) or 0.0), 6),
            "text": str(getattr(segment, "text", "") or "").strip(),
            "speaker": str(getattr(segment, "speaker", "") or ""),
            "gender": str(getattr(segment, "gender", "") or ""),
            "engine": engine_key,
        })
    segment_indexes = {int(item["segment_index"]) for item in segment_records}
    word_records = []
    for item in words:
        segment_index = int(item.get("segment_index", 0) or 0)
        if segment_index not in segment_indexes:
            continue
        record = dict(item)
        record["segment_index"] = segment_index
        record["method"] = str(record.get("time_mapping") or WORD_TIMING_METHOD)
        record["engine"] = engine_key
        word_records.append(record)

    segment_records = sorted(segment_records, key=lambda item: (float(item.get("start", 0.0)), int(item.get("segment_index", 0))))
    word_records = sorted(word_records, key=lambda item: (float(item.get("start", 0.0)), float(item.get("end", 0.0))))
    paths = _write_debug_set(
        debug_dir,
        lang,
        segment_records,
        word_records,
        engine_key,
        "final_dub_alignment_debug",
        timing_source,
        timing_method,
        resolved_video_filename,
        resolved_page_title,
        resolved_page_hint,
    )
    engine_debug_name = ENGINE_DEBUG_DIRS.get(engine_key)
    if engine_debug_name:
        engine_dir = Path(run_dir) / engine_debug_name
        engine_paths = _write_debug_set(
            engine_dir,
            lang,
            segment_records,
            word_records,
            engine_key,
            "final_dub_alignment_debug",
            timing_source,
            timing_method,
            resolved_video_filename,
            resolved_page_title,
            resolved_page_hint,
        )
        paths.update({f"engine_{key}": value for key, value in engine_paths.items()})
        _copy_alignment_artifacts(debug_dir, engine_dir)
    return paths


def _write_debug_set(
    debug_dir: Path,
    lang: str,
    segment_records: list[dict[str, Any]],
    word_records: list[dict[str, Any]],
    engine_key: str,
    mode: str,
    timing_source: str,
    timing_method: str,
    video_filename: str,
    page_title: str,
    page_hint: str,
) -> dict[str, str]:
    debug_dir.mkdir(parents=True, exist_ok=True)
    segment_srt_path = debug_dir / f"segment_srt_{lang}.srt"
    word_srt_path = debug_dir / f"word_srt_{lang}.srt"
    word_timeline_path = debug_dir / f"word_timeline_{lang}.json"
    timing_report_path = debug_dir / f"timing_report_{lang}.json"
    html_path = debug_dir / f"index_{lang}.html"
    _write_srt(segment_srt_path, segment_records, "text")
    _write_srt(word_srt_path, word_records, "word")
    _write_json(word_timeline_path, word_records)
    _write_json(timing_report_path, {
        "mode": mode,
        "method": timing_method,
        "timing_source": timing_source,
        "engine": engine_key,
        "segment_count": len(segment_records),
        "word_count": len(word_records),
        "segments": segment_records,
    })
    _write_html(html_path, lang, segment_records, word_records, video_filename, page_title, page_hint)
    return {
        "debug_dir": str(debug_dir),
        "segment_srt_path": str(segment_srt_path),
        "word_srt_path": str(word_srt_path),
        "word_timeline_path": str(word_timeline_path),
        "timing_report_path": str(timing_report_path),
        "html_path": str(html_path),
    }


def _copy_alignment_artifacts(source_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in ("alignment_job.json", "alignment_result.json", "alignment_report.json"):
        source = source_dir / name
        if source.exists():
            shutil.copy2(source, target_dir / name)


def _write_srt(path: Path, records: list[dict[str, Any]], text_key: str) -> None:
    lines = []
    for index, item in enumerate(records, start=1):
        text = str(item.get(text_key) or "").strip()
        if not text:
            continue
        lines.extend([
            str(index),
            f"{_srt_time(float(item['start']))} --> {_srt_time(float(item['end']))}",
            text,
            "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def _resolve_video_filename(video_filename: str | None, language: str) -> str:
    value = str(video_filename).strip() if video_filename is not None else f"dubbed_{language}.mp4"
    candidate = Path(value)
    if not value or candidate.is_absolute() or candidate.name != value or value in {".", ".."}:
        raise ValueError("video_filename must be a single relative filename")
    if "/" in value or "\\" in value or candidate.suffix.lower() != ".mp4":
        raise ValueError("video_filename must be a single MP4 filename")
    return value


def _write_html(
    path: Path,
    language: str,
    segments: list[dict[str, Any]],
    words: list[dict[str, Any]],
    video_filename: str,
    page_title: str,
    page_hint: str,
) -> None:
    lang = html.escape(language)
    title = html.escape(page_title)
    video_src = html.escape(f"../{video_filename}", quote=True)
    hint = html.escape(page_hint)
    words_json = json.dumps(words, ensure_ascii=False, separators=(",", ":"))
    segments_json = json.dumps(segments, ensure_ascii=False, separators=(",", ":"))
    text = f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#05070b;color:#f9fafb;font-family:Segoe UI,Arial,sans-serif}}
.stage{{position:fixed;inset:0;background:#05070b;display:flex;align-items:center;justify-content:center;overflow:hidden}}
video{{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:#05070b}}
.subtitle_box{{position:absolute;left:50%;bottom:8%;transform:translateX(-50%);width:min(82vw,1120px);height:92px;padding:0 22px;box-sizing:border-box;background:rgba(0,0,0,.72);border-radius:6px;display:flex;align-items:center;justify-content:flex-start;overflow:hidden;z-index:5;opacity:1}}
.subtitle_track{{white-space:nowrap;font-size:clamp(25px,3.1vw,52px);line-height:1;font-weight:700;color:#f9fafb;will-change:transform;transition:transform .16s linear}}
.subtitle_word{{display:inline-block;padding:4px 6px;margin:0 1px;border-radius:5px;transition:background .06s linear,color .06s linear,box-shadow .06s linear}}
.subtitle_word.active{{background:#facc15;color:#111827;box-shadow:0 0 0 2px rgba(250,204,21,.28)}}
.subtitle_box.hidden{{opacity:0}}
.hint{{position:absolute;top:12px;left:12px;z-index:6;color:#cbd5e1;background:rgba(0,0,0,.45);padding:6px 9px;border-radius:4px;font-size:13px}}
@media (max-width:700px){{.subtitle_box{{width:88vw;height:76px;bottom:10%;padding:0 16px}}.subtitle_track{{font-size:clamp(20px,5.5vw,34px)}}}}
</style>
</head>
<body>
<div class="stage">
  <video id="video" controls src="{video_src}"></video>
  <div class="hint">{hint}</div>
  <div id="subtitleBox" class="subtitle_box hidden"><div id="subtitleTrack" class="subtitle_track"></div></div>
</div>
<script>
const words = {words_json};
const segments = {segments_json};
const video = document.getElementById('video');
const subtitleBox = document.getElementById('subtitleBox');
const subtitleTrack = document.getElementById('subtitleTrack');
let currentSegmentIndex = null;
let activeWordGlobalIndex = -1;
let activeWordElement = null;
let rafId = 0;
let videoFrameCallbackId = 0;
function escapeHtml(value){{return String(value).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));}}
function activeSegment(time){{
  let low = 0;
  let high = segments.length - 1;
  while (low <= high){{
    const mid = (low + high) >> 1;
    const segment = segments[mid];
    if (time < segment.start) high = mid - 1;
    else if (time > segment.end) low = mid + 1;
    else return segment;
  }}
  return null;
}}
function activeWordIndex(time){{
  let low = 0;
  let high = words.length - 1;
  while (low <= high){{
    const mid = (low + high) >> 1;
    const word = words[mid];
    if (time < word.start) high = mid - 1;
    else if (time > word.end) low = mid + 1;
    else return mid;
  }}
  return -1;
}}
function wordsForSegment(segment){{return words.map((w,i)=>({{word:w,index:i}})).filter(item => item.word.segment_index === segment.segment_index);}}
function loadSegment(segment){{
  currentSegmentIndex = segment.segment_index;
  activeWordGlobalIndex = -1;
  activeWordElement = null;
  const segmentWords = wordsForSegment(segment);
  subtitleTrack.style.transform = 'translateX(0px)';
  subtitleTrack.innerHTML = segmentWords.map(item => '<span class="subtitle_word" data-global-index="' + item.index + '">' + escapeHtml(item.word.word) + '</span>').join(' ');
}}
function centerActiveWord(el){{
  const boxWidth = subtitleBox.clientWidth;
  const trackWidth = subtitleTrack.scrollWidth;
  if (trackWidth <= boxWidth){{
    subtitleTrack.style.transform = 'translateX(0px)';
    return;
  }}
  const wordCenter = el.offsetLeft + el.offsetWidth / 2;
  let x = (boxWidth / 2) - wordCenter;
  const minX = boxWidth - trackWidth - 22;
  if (x > 0) x = 0;
  if (x < minX) x = minX;
  subtitleTrack.style.transform = 'translateX(' + x.toFixed(1) + 'px)';
}}
function setActiveWord(globalIndex){{
  if (globalIndex === activeWordGlobalIndex) return;
  if (activeWordElement) activeWordElement.classList.remove('active');
  activeWordGlobalIndex = globalIndex;
  activeWordElement = null;
  if (globalIndex < 0) return;
  activeWordElement = subtitleTrack.querySelector('[data-global-index="' + globalIndex + '"]');
  if (!activeWordElement) return;
  activeWordElement.classList.add('active');
  centerActiveWord(activeWordElement);
}}
function render(){{
  const time = video.currentTime || 0;
  const segment = activeSegment(time);
  if (!segment){{
    subtitleBox.classList.add('hidden');
    currentSegmentIndex = null;
    setActiveWord(-1);
    return;
  }}
  subtitleBox.classList.remove('hidden');
  if (currentSegmentIndex !== segment.segment_index) loadSegment(segment);
  setActiveWord(activeWordIndex(time));
}}
function scheduleExactFrameLoop(){{
  if ('requestVideoFrameCallback' in HTMLVideoElement.prototype){{
    const onVideoFrame = () => {{
      render();
      if (!video.paused && !video.ended) videoFrameCallbackId = video.requestVideoFrameCallback(onVideoFrame);
    }};
    videoFrameCallbackId = video.requestVideoFrameCallback(onVideoFrame);
    return;
  }}
  const onAnimationFrame = () => {{
    render();
    if (!video.paused && !video.ended) rafId = requestAnimationFrame(onAnimationFrame);
  }};
  rafId = requestAnimationFrame(onAnimationFrame);
}}
function cancelExactFrameLoop(){{
  cancelAnimationFrame(rafId);
  if ('cancelVideoFrameCallback' in HTMLVideoElement.prototype && videoFrameCallbackId) video.cancelVideoFrameCallback(videoFrameCallbackId);
  rafId = 0;
  videoFrameCallbackId = 0;
}}
video.addEventListener('play', () => {{
  cancelExactFrameLoop();
  scheduleExactFrameLoop();
}});
video.addEventListener('pause', () => {{
  cancelExactFrameLoop();
  render();
}});
video.addEventListener('seeked', render);
video.addEventListener('loadedmetadata', render);
window.addEventListener('resize', () => {{ if (activeWordElement) centerActiveWord(activeWordElement); }});
render();
</script>
</body>
</html>
'''
    path.write_text(text, encoding="utf-8", newline="\n")
def _srt_time(seconds: float) -> str:
    seconds = max(float(seconds), 0.0)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    whole = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        whole += 1
        millis -= 1000
    return f"{hours:02d}:{minutes:02d}:{whole:02d},{millis:03d}"
