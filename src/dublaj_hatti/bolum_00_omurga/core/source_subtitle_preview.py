# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from typing import Any, Dict, List


def _srt_timestamp(seconds: float) -> str:
    value = max(0.0, float(seconds or 0.0))
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    whole_seconds = int(value % 60)
    millis = int(round((value - int(value)) * 1000))
    if millis >= 1000:
        whole_seconds += 1
        millis -= 1000
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{millis:03d}"


def _write_srt(entries: List[Dict[str, Any]], path: str, text_key: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for index, item in enumerate(entries, start=1):
            f.write(f"{index}\n")
            f.write(f"{_srt_timestamp(item['start'])} --> {_srt_timestamp(item['end'])}\n")
            f.write(f"{item[text_key]}\n\n")


def _collect_word_records(segments: List[Any], alignment: Dict[str, Any], src_lang: str) -> List[Dict[str, Any]]:
    words_by_segment: Dict[int, List[Dict[str, Any]]] = {}
    for idx, seg in enumerate(segments, start=1):
        segment_index = int(getattr(seg, "index", idx) or idx)
        seg_words = getattr(seg, "words", None) or []
        if seg_words:
            words_by_segment[segment_index] = seg_words

    if not words_by_segment:
        for idx, aligned_seg in enumerate(alignment.get("segments") or [], start=1):
            segment_index = idx
            if idx - 1 < len(segments):
                segment_index = int(getattr(segments[idx - 1], "index", idx) or idx)
            seg_words = aligned_seg.get("words") or []
            if seg_words:
                words_by_segment[segment_index] = seg_words

    records: List[Dict[str, Any]] = []
    src_lang_lower = (src_lang or "source").lower()
    for idx, seg in enumerate(segments, start=1):
        segment_index = int(getattr(seg, "index", idx) or idx)
        segment_text = getattr(seg, "text", "") or ""
        segment_start = float(getattr(seg, "start", 0.0) or 0.0)
        for word in words_by_segment.get(segment_index, []):
            word_text = str(word.get("word", "")).strip()
            if not word_text:
                continue
            start = float(word.get("start", segment_start) or segment_start)
            end = float(word.get("end", start) or start)
            records.append({
                "word": word_text,
                "start": start,
                "end": end,
                "segment_index": segment_index,
                "segment_text": segment_text,
                "source": "asr_word_timeline",
                "language": src_lang_lower,
            })
    records.sort(key=lambda item: (float(item["start"]), float(item["end"])))
    return records


def _collect_segment_records(segments: List[Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for idx, seg in enumerate(segments, start=1):
        segment_index = int(getattr(seg, "index", idx) or idx)
        records.append({
            "segment_index": segment_index,
            "start": float(getattr(seg, "start", 0.0) or 0.0),
            "end": float(getattr(seg, "end", 0.0) or 0.0),
            "text": getattr(seg, "text", "") or "",
        })
    records.sort(key=lambda item: (float(item["start"]), float(item["end"])))
    return records


def _build_html(src_lang: str, segments_json: str, words_json: str) -> str:
    return f'''<!doctype html>
<html lang="{src_lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Source Subtitle Preview</title>
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
  <video id="video" controls src="../video_run.mp4"></video>
  <div class="hint">Source subtitle preview</div>
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


def write_source_subtitle_preview(segments: List[Any], alignment: Dict[str, Any], run_dir: str, src_lang: str) -> Dict[str, str]:
    if not segments:
        return {}

    src_lang_lower = (src_lang or "source").lower()
    preview_dir = os.path.join(run_dir, "source_subtitle_preview")
    os.makedirs(preview_dir, exist_ok=True)

    segment_records = _collect_segment_records(segments)
    word_records = _collect_word_records(segments, alignment, src_lang_lower)
    if not word_records:
        return {}

    segment_srt_path = os.path.join(preview_dir, f"source_segments_{src_lang_lower}.srt")
    word_srt_path = os.path.join(preview_dir, f"source_words_{src_lang_lower}.srt")
    report_path = os.path.join(preview_dir, f"source_timing_report_{src_lang_lower}.json")
    html_path = os.path.join(preview_dir, f"index_{src_lang_lower}.html")

    _write_srt(segment_records, segment_srt_path, "text")
    _write_srt(word_records, word_srt_path, "word")

    report = {
        "mode": "source_subtitle_preview",
        "method": "source_segments_and_asr_word_timeline",
        "source_language": src_lang_lower,
        "segment_count": len(segment_records),
        "word_count": len(word_records),
        "segments": segment_records,
        "words": word_records,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    words_json = json.dumps(word_records, ensure_ascii=False, separators=(",", ":"))
    segments_json = json.dumps(segment_records, ensure_ascii=False, separators=(",", ":"))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(_build_html(src_lang_lower, segments_json, words_json))

    return {
        "preview_dir": preview_dir,
        "html": html_path,
        "source_segments_srt": segment_srt_path,
        "source_words_srt": word_srt_path,
        "report": report_path,
    }