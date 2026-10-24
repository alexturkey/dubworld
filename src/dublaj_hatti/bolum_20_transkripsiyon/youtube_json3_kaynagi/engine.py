"""YouTube json3 altyazı kaynağı (`youtube_translate` transkripsiyon motoru, isteğe bağlı, extras `youtube`).

Videonun YouTube otomatik altyazısının (json3) kelimelerini metin olarak alır, kelime zamanını kendi CTC
hizalamamızla (wav2vec2) yeniden üretir; json3 zamanları yalnız hizalama penceresi ipucudur. Ses tanıma
çalışmaz, bu yüzden hızlıdır. Yalnız hakkınız olan ya da izinli içerik; platform şartları size aittir.
"""

from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import huggingface_home

# soundfile ve CTC kutusu (numpy/torch zinciri) tembel yüklenir: ayrıştırıcı ve iz seçimi yalnız stdlib ile sınanabilir.

ALIGNMENT_TIMEOUT_MIN_SECONDS = 120
ALIGNMENT_TIMEOUT_FIXED_MARGIN_SECONDS = 90
ALIGNMENT_TIMEOUT_PER_AUDIO_MINUTE_SECONDS = 8
MAX_AUTO_REPAIR_ADJUSTMENT_SECONDS = 0.3
KURULUM_IPUCU = "YouTube altyazı kaynağı için yt-dlp kurulu değil: pip install .[youtube]"
MIN_REPAIRED_WORD_DURATION_SECONDS = 0.01


class YouTubeJson3Error(RuntimeError):
    pass


@dataclass
class YouTubeCaptionTrack:
    language: str
    source: str
    url: str
    ext: str


YOUTUBE_ALAN_ADLARI = ("youtube.com", "youtu.be")


def is_youtube_url(url: str) -> bool:
    # Tam alan adı ya da alt alan adı (www., m.); "youtube.com.example" gibi taklit adlar reddedilir.
    host = (urlparse(str(url or "").strip()).hostname or "").lower()
    return any(host == alan or host.endswith("." + alan) for alan in YOUTUBE_ALAN_ADLARI)


def probe_youtube_json3(url: str, logger: object | None = None) -> dict[str, Any]:
    if not is_youtube_url(url):
        return {"ok": False, "reason": "not_youtube"}
    try:
        info = _extract_info(url)
        track, words, _ = _select_strict_json3_track(info)
        return {
            "ok": bool(words),
            "reason": "ok" if words else "no_word_timestamps",
            "language": track.language,
            "source": track.source,
            "format": track.ext,
            "word_count": len(words),
        }
    except Exception as exc:
        if logger:
            logger.info("[YOUTUBE_TRANSLATE] Uygun degil: %s", exc)
        return {"ok": False, "reason": str(exc)}


def build_youtube_json3_transcript(
    url: str,
    run_dir: str,
    audio_path: str,
    device: str = "cuda",
    cache_dir: str | None = None,
    logger: object | None = None,
) -> dict[str, Any]:
    if not is_youtube_url(url):
        raise YouTubeJson3Error("URL YouTube degil")
    if not audio_path or not os.path.exists(audio_path):
        raise YouTubeJson3Error("YouTube JSON3 alignment icin ses dosyasi gerekli")

    info = _extract_info(url)
    track, words, json3_text = _select_strict_json3_track(info)
    if not words:
        raise YouTubeJson3Error("JSON3 icinde temiz kelime bulunamadi")

    audio_duration = _get_audio_duration(audio_path)
    alignment_input_segments = _build_alignment_input_segments(words, audio_duration)
    if not alignment_input_segments:
        raise YouTubeJson3Error("JSON3 alignment segmentleri olusturulamadi")

    json3_dir = os.path.join(run_dir, "youtube_json3_transkripsiyon_kaynagi")
    os.makedirs(json3_dir, exist_ok=True)

    raw_json3_path = os.path.join(json3_dir, "raw_youtube.json3")
    clean_words_json_path = os.path.join(json3_dir, "clean_youtube_words.json")
    clean_transcript_path = os.path.join(json3_dir, "clean_youtube_transcript.txt")
    alignment_input_path = os.path.join(json3_dir, "alignment_input_segments.json")
    words_json_path = os.path.join(json3_dir, "aligned_word_timeline.json")
    words_txt_path = os.path.join(json3_dir, "aligned_word_timeline.txt")
    segments_json_path = os.path.join(json3_dir, "aligned_segments.json")
    segments_txt_path = os.path.join(json3_dir, "aligned_segments.txt")
    quality_report_path = os.path.join(json3_dir, "alignment_quality_report.json")
    report_path = os.path.join(json3_dir, "report.json")

    _write_text(raw_json3_path, json3_text)
    _write_json(clean_words_json_path, words)
    _write_text(clean_transcript_path, " ".join(word["word"] for word in words))
    _write_json(alignment_input_path, alignment_input_segments)

    if cache_dir is None:
        cache_dir = str(huggingface_home())
    os.makedirs(cache_dir, exist_ok=True)

    worker_result = _run_ctc_alignment(
        audio_path=audio_path,
        segments_json_path=alignment_input_path,
        language=track.language,
        device=device,
        cache_dir=cache_dir,
        audio_duration=audio_duration,
        logger=logger,
    )
    if not worker_result.get("success"):
        raise YouTubeJson3Error(f"CTC kelime hizalama basarisiz: {worker_result.get('error', 'bilinmeyen hata')}")

    aligned_words = worker_result.get("words") or []
    quality_report = _validate_aligned_words(words, aligned_words)
    original_aligned_words = [dict(word) for word in aligned_words]
    raw_timing_report = _inspect_word_timeline(aligned_words)
    aligned_words, timing_repair_count = _repair_aligned_word_timeline(aligned_words)
    final_timing_report = _inspect_word_timeline(aligned_words)
    max_adjustment_seconds = _calculate_max_timing_adjustment_seconds(original_aligned_words, aligned_words)
    if final_timing_report["negative_duration_count"] or final_timing_report["overlap_count"]:
        raise YouTubeJson3Error(
            "YouTube JSON3 alignment zaman normalizasyonu basarisiz: "
            f"negative={final_timing_report['negative_duration_count']} overlap={final_timing_report['overlap_count']}"
        )
    if max_adjustment_seconds > MAX_AUTO_REPAIR_ADJUSTMENT_SECONDS:
        raise YouTubeJson3Error(
            "YouTube JSON3 alignment zaman duzeltmesi guvenli siniri asti: "
            f"{max_adjustment_seconds * 1000:.0f}ms"
        )
    quality_report.update({
        "raw_negative_duration_count": raw_timing_report["negative_duration_count"],
        "raw_overlap_count": raw_timing_report["overlap_count"],
        "timing_repair_count": timing_repair_count,
        "max_timing_adjustment_ms": round(max_adjustment_seconds * 1000.0, 3),
        "final_negative_duration_count": final_timing_report["negative_duration_count"],
        "final_overlap_count": final_timing_report["overlap_count"],
    })
    _write_json(quality_report_path, quality_report)

    aligned_segments = worker_result.get("segments") or []
    _sync_segments_with_flat_words(aligned_segments, aligned_words)
    _write_json(words_json_path, aligned_words)
    _write_word_timeline_txt(words_txt_path, aligned_words)
    _write_json(segments_json_path, aligned_segments)
    _write_segments_txt(segments_txt_path, aligned_segments)

    report = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "url": url,
        "video_id": info.get("id", ""),
        "title": info.get("title", ""),
        "language": track.language,
        "track_source": track.source,
        "track_format": track.ext,
        "json3_word_count": len(words),
        "aligned_word_count": len(aligned_words),
        "alignment_input_segment_count": len(alignment_input_segments),
        "aligned_segment_count": len(aligned_segments),
        "timing_repair_count": timing_repair_count,
        "word_timing_source": "ctc_kelime_hizalama",
        "json3_timing_role": "alignment_window_hint_only",
        "raw_json3_path": raw_json3_path,
        "clean_words_json_path": clean_words_json_path,
        "alignment_input_path": alignment_input_path,
        "words_json_path": words_json_path,
        "segments_json_path": segments_json_path,
        "quality_report_path": quality_report_path,
        "profile_summary": worker_result.get("profile_summary") or {},
    }
    _write_json(report_path, report)

    if logger:
        if timing_repair_count:
            logger.info("[YOUTUBE_TRANSLATE] Alignment zaman tamiri: %d kelime/cift", timing_repair_count)
        logger.info("[YOUTUBE_TRANSLATE] JSON3 + CTC kelime hizalama hazir: dil=%s kelime=%d segment=%d", track.language, len(aligned_words), len(aligned_segments))
        logger.info("[YOUTUBE_TRANSLATE] Rapor klasoru: %s", json3_dir)

    return {
        "segments": aligned_segments,
        "aligned": {"segments": aligned_segments},
        "detected_language": track.language,
        "words": aligned_words,
        "report": report,
    }


def parse_youtube_json3_words(json3_text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(json3_text)
    except json.JSONDecodeError as exc:
        raise YouTubeJson3Error(f"JSON3 parse edilemedi: {exc}") from exc

    raw_words: list[dict[str, Any]] = []
    raw_index = 0
    for event in payload.get("events") or []:
        event_start_ms = event.get("tStartMs")
        if event_start_ms is None:
            continue
        event_start = float(event_start_ms) / 1000.0
        for seg in event.get("segs") or []:
            text = html.unescape(str(seg.get("utf8") or "")).strip()
            if not text or _is_non_speech_token(text):
                continue
            parts = [part for part in text.split() if part]
            start = event_start + (float(seg.get("tOffsetMs") or 0.0) / 1000.0)
            for part in parts:
                raw_index += 1
                raw_words.append({
                    "word": part,
                    "start": start,
                    "raw_index": raw_index,
                    "source_text": text,
                })

    if not raw_words:
        return []

    raw_words.sort(key=lambda item: (float(item["start"]), int(item["raw_index"])))
    words: list[dict[str, Any]] = []
    for word in raw_words:
        text = str(word["word"]).strip()
        if not _normalize_word_key(text):
            continue
        words.append({
            "word": text,
            "start_hint": float(word["start"]),
            "start_hint_role": "alignment_window_hint_only",
            "official_boundary": False,
            "source": "youtube_json3_text",
        })

    for index, word in enumerate(words, start=1):
        word["index"] = index
    return words


def _yt_dlp():
    try:
        import yt_dlp
    except ImportError as exc:
        raise YouTubeJson3Error(KURULUM_IPUCU) from exc
    return yt_dlp


def _extract_info(url: str) -> dict[str, Any]:
    yt_dlp = _yt_dlp()
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        return ydl.extract_info(url, download=False)


def _select_strict_json3_track(info: dict[str, Any]) -> tuple[YouTubeCaptionTrack, list[dict[str, Any]], str]:
    candidates = _iter_json3_tracks(info)
    if not candidates:
        raise YouTubeJson3Error("YouTube JSON3 otomatik altyazisi bulunamadi")

    track = candidates[0]
    json3_text = _download_track_text(track.url)
    words = parse_youtube_json3_words(json3_text)
    if not words:
        raise YouTubeJson3Error(f"JSON3 var ama temiz kelime yok: {track.language}")
    return track, words, json3_text


def _get_audio_duration(audio_path: str) -> float:
    import soundfile as sf

    try:
        info = sf.info(audio_path)
    except Exception as exc:
        raise YouTubeJson3Error(f"Ses suresi okunamadi: {exc}") from exc
    duration = float(getattr(info, "duration", 0.0) or 0.0)
    if duration <= 0.0:
        raise YouTubeJson3Error("Ses suresi gecersiz")
    return duration


def _build_alignment_input_segments(words: list[dict[str, Any]], audio_duration: float) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    max_group_duration = 18.0
    max_group_words = 80
    gap_split_threshold = 2.5
    previous_hint: float | None = None
    for word in words:
        current_hint = float(word["start_hint"])
        if current:
            group_start = float(current[0]["start_hint"])
            gap = current_hint - float(previous_hint if previous_hint is not None else group_start)
            if gap > gap_split_threshold or current_hint - group_start > max_group_duration or len(current) >= max_group_words:
                groups.append(current)
                current = []
        current.append(word)
        previous_hint = current_hint
        if _is_sentence_end_word(str(word.get("word", ""))):
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    segments: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        start = max(0.0, float(group[0]["start_hint"]) - 0.25)
        if index + 1 < len(groups):
            end = float(groups[index + 1][0]["start_hint"])
        else:
            end = audio_duration
        end = min(audio_duration, max(end, float(group[-1]["start_hint"]) + 0.25))
        segments.append({
            "index": index,
            "start": round(start, 3),
            "end": round(end, 3),
            "text": " ".join(str(word["word"]).strip() for word in group if str(word.get("word", "")).strip()),
        })
    return segments


def _repair_aligned_word_timeline(words: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    repaired_words = [dict(word) for word in words]
    fixed = 0
    for _index, word in enumerate(repaired_words):
        start = float(word["start"])
        end = float(word["end"])
        if end < start + MIN_REPAIRED_WORD_DURATION_SECONDS:
            word["end"] = start + MIN_REPAIRED_WORD_DURATION_SECONDS
            fixed += 1

    for index in range(len(repaired_words) - 1):
        current = repaired_words[index]
        next_word = repaired_words[index + 1]
        current_start = float(current["start"])
        current_end = float(current["end"])
        next_start = float(next_word["start"])
        next_end = float(next_word["end"])
        if current_end > next_start:
            lower_boundary = current_start + MIN_REPAIRED_WORD_DURATION_SECONDS
            upper_boundary = next_end - MIN_REPAIRED_WORD_DURATION_SECONDS
            if lower_boundary <= upper_boundary:
                midpoint = (current_end + next_start) / 2.0
                boundary = min(max(midpoint, lower_boundary), upper_boundary)
                current["end"] = round(boundary, 3)
                next_word["start"] = round(boundary, 3)
            else:
                next_word["start"] = current_end
                next_word["end"] = max(next_end, current_end + MIN_REPAIRED_WORD_DURATION_SECONDS)
            fixed += 1
        if float(next_word["end"]) < float(next_word["start"]) + MIN_REPAIRED_WORD_DURATION_SECONDS:
            next_word["end"] = float(next_word["start"]) + MIN_REPAIRED_WORD_DURATION_SECONDS
            fixed += 1

    return repaired_words, fixed


def _inspect_word_timeline(words: list[dict[str, Any]]) -> dict[str, int]:
    negative_duration_count = 0
    overlap_count = 0
    for word in words:
        if float(word["end"]) < float(word["start"]):
            negative_duration_count += 1
    for current, next_word in zip(words, words[1:], strict=False):
        if float(current["end"]) > float(next_word["start"]):
            overlap_count += 1
    return {
        "negative_duration_count": negative_duration_count,
        "overlap_count": overlap_count,
    }


def _calculate_max_timing_adjustment_seconds(
    original_words: list[dict[str, Any]],
    repaired_words: list[dict[str, Any]],
) -> float:
    max_adjustment = 0.0
    for original, repaired in zip(original_words, repaired_words, strict=False):
        max_adjustment = max(
            max_adjustment,
            abs(float(original["start"]) - float(repaired["start"])),
            abs(float(original["end"]) - float(repaired["end"])),
        )
    return max_adjustment


def _sync_segments_with_flat_words(segments: list[dict[str, Any]], words: list[dict[str, Any]]) -> None:
    word_index = 0
    for segment in segments:
        segment_words = segment.get("words") or []
        for index in range(len(segment_words)):
            if word_index < len(words):
                segment_words[index] = words[word_index]
                word_index += 1
        if segment_words:
            segment["start"] = float(segment_words[0]["start"])
            segment["end"] = float(segment_words[-1]["end"])


def _run_ctc_alignment(
    audio_path: str,
    segments_json_path: str,
    language: str,
    device: str,
    cache_dir: str,
    audio_duration: float,
    logger: object | None = None,
) -> dict[str, Any]:
    from dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama import (
        CtcHizalamaHatasi,
        run_ctc_word_alignment,
    )

    timeout_seconds = _calculate_alignment_timeout_seconds(audio_duration)
    if logger:
        logger.info("[YOUTUBE_TRANSLATE] CTC hizalama timeout: %d sn (ses=%.2f sn)", timeout_seconds, audio_duration)
    try:
        return run_ctc_word_alignment(audio_path, segments_json_path, language, cache_dir, timeout_seconds, device=device)
    except CtcHizalamaHatasi as exc:
        raise YouTubeJson3Error(str(exc)) from exc


def _calculate_alignment_timeout_seconds(audio_duration: float) -> int:
    audio_minutes = max(float(audio_duration), 0.0) / 60.0
    calculated = ALIGNMENT_TIMEOUT_FIXED_MARGIN_SECONDS + (audio_minutes * ALIGNMENT_TIMEOUT_PER_AUDIO_MINUTE_SECONDS)
    return int(max(ALIGNMENT_TIMEOUT_MIN_SECONDS, round(calculated)))


def _validate_aligned_words(expected_words: list[dict[str, Any]], aligned_words: list[dict[str, Any]]) -> dict[str, Any]:
    expected = [_normalize_compare_word(word.get("word", "")) for word in expected_words]
    aligned = [_normalize_compare_word(word.get("word", "")) for word in aligned_words]
    expected = [word for word in expected if word]
    aligned = [word for word in aligned if word]
    first_mismatch = None
    for index, expected_word in enumerate(expected):
        aligned_word = aligned[index] if index < len(aligned) else ""
        if expected_word != aligned_word:
            first_mismatch = {
                "index": index + 1,
                "expected": expected_word,
                "aligned": aligned_word,
            }
            break
    if len(expected) != len(aligned) or first_mismatch is not None:
        raise YouTubeJson3Error(
            "JSON3 kelime listesi ile CTC hizalama kelime listesi uyusmadi: "
            f"json3={len(expected)} aligned={len(aligned)} first_mismatch={first_mismatch}"
        )
    missing_times = [
        index + 1
        for index, word in enumerate(aligned_words)
        if "start" not in word or "end" not in word
    ]
    if missing_times:
        raise YouTubeJson3Error(f"CTC kelime hizalama eksik kelime zamani uretti: {missing_times[:10]}")
    return {
        "ok": True,
        "expected_word_count": len(expected),
        "aligned_word_count": len(aligned),
        "first_mismatch": None,
        "missing_time_count": 0,
    }


def _iter_json3_tracks(info: dict[str, Any]) -> list[YouTubeCaptionTrack]:
    preferred = _normalize_lang(info.get("language") or info.get("original_language") or "en")
    candidates: list[YouTubeCaptionTrack] = []
    for lang, tracks in (info.get("automatic_captions") or {}).items():
        for track in tracks or []:
            ext = str(track.get("ext") or "").lower()
            track_url = str(track.get("url") or "")
            if ext == "json3" and track_url:
                candidates.append(YouTubeCaptionTrack(language=_normalize_lang(lang), source="automatic", url=track_url, ext=ext))

    def score(candidate: YouTubeCaptionTrack) -> tuple[int, str]:
        lang_score = 0 if candidate.language == preferred else 1 if candidate.language == "en" else 2
        return lang_score, candidate.language

    return sorted(candidates, key=score)


def _download_track_text(url: str) -> str:
    yt_dlp = _yt_dlp()
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        response = ydl.urlopen(url)
        data = response.read()
    return data.decode("utf-8", errors="replace")


def _word_start(word: dict[str, Any]) -> float:
    if "start" in word:
        return float(word["start"])
    return float(word["start_hint"])


def _word_end(word: dict[str, Any]) -> float:
    if "end" in word:
        return float(word["end"])
    return _word_start(word)


def _is_non_speech_token(text: str) -> bool:
    stripped = str(text or "").strip().lower()
    if not stripped:
        return True
    if re.fullmatch(r"\[[^\]]+\]", stripped):
        return True
    if re.fullmatch(r"\([^)]*\)", stripped):
        return True
    return stripped in {"♪", "♫"}


def _is_sentence_end_word(word: str) -> bool:
    return bool(re.search(r"[.!?][\"')\]]*$", str(word or "").strip()))


def _normalize_word_key(word: str) -> str:
    return re.sub(r"\s+", " ", str(word or "").strip().lower())


def _normalize_compare_word(word: str) -> str:
    value = str(word or "").strip().lower()
    value = re.sub(r"^[^\w']+|[^\w']+$", "", value, flags=re.UNICODE)
    return value


def _normalize_lang(lang: str) -> str:
    return str(lang or "en").split("-")[0].lower()


def _write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _write_word_timeline_txt(path: str, words: list[dict[str, Any]]) -> None:
    lines = []
    for index, word in enumerate(words, start=1):
        lines.append(f"{index:04d}. {_word_start(word):.3f} --> {_word_end(word):.3f} | {word['word']}")
    _write_text(path, "\n".join(lines))


def _write_segments_txt(path: str, segments: list[dict[str, Any]]) -> None:
    lines = []
    for segment in segments:
        lines.append(
            f"{int(segment['index']):04d}. {float(segment['start']):.3f} --> {float(segment['end']):.3f} | "
            f"{len(segment.get('words') or [])} kelime | {segment['text']}"
        )
    _write_text(path, "\n".join(lines))
