from __future__ import annotations

import re
import unicodedata

import numpy as np

from .execution import SupertonicPreparedAudio
from .runtime import chunk_text


LONG_CANDIDATE_LANE_ALIGNMENT_SECONDS = 30.0


def normalize_tokens(text: str) -> list[str]:
    return [item for item in re.split(r"[^\w]+", str(text or "").casefold(), flags=re.UNICODE) if item]


def _single_missing_token_index(expected_tokens: list[str], actual_tokens: list[str]) -> int | None:
    if len(expected_tokens) != len(actual_tokens) + 1:
        return None
    for index, actual_token in enumerate(actual_tokens):
        if expected_tokens[index] != actual_token:
            if expected_tokens[index + 1 :] == actual_tokens[index:]:
                return index
            return None
    return len(expected_tokens) - 1


def _reconcile_single_missing_token(
    lane: dict,
    words: list[dict],
    word_token_groups: list[list[str]],
    sample_rate: int,
) -> tuple[list[dict], dict | None]:
    expected_tokens = list(lane["expected_tokens"])
    actual_tokens = [token for tokens in word_token_groups for token in tokens]
    if actual_tokens == expected_tokens:
        return words, None
    missing_index = _single_missing_token_index(expected_tokens, actual_tokens)
    if missing_index is None:
        raise RuntimeError(f"Supertonic aday lane kelime sirasi uyusmuyor: lane={lane['lane_id']}")
    missing_token = expected_tokens[missing_index]
    if len(missing_token) != 1 or any(len(tokens) != 1 for tokens in word_token_groups):
        raise RuntimeError(f"Supertonic aday lane kelime sirasi uyusmuyor: lane={lane['lane_id']}")
    if missing_index <= 0 or missing_index >= len(words):
        raise RuntimeError(f"Supertonic aday lane kelime sirasi uyusmuyor: lane={lane['lane_id']}")
    if sample_rate <= 0:
        raise RuntimeError(f"Supertonic aday lane kelime sirasi uyusmuyor: lane={lane['lane_id']}")
    left_word = words[missing_index - 1]
    right_word = words[missing_index]
    left_end_sample = int(round(float(left_word["end"]) * sample_rate))
    right_start_sample = int(round(float(right_word["start"]) * sample_rate))
    if right_start_sample <= left_end_sample:
        raise RuntimeError(f"Supertonic aday lane kelime sirasi uyusmuyor: lane={lane['lane_id']}")
    synthetic_word = {
        "word": missing_token,
        "start": left_end_sample / sample_rate,
        "end": right_start_sample / sample_rate,
        "source": "candidate_alignment_single_missing_token_local_gap",
        "time_mapping": "candidate_lane_local_gap",
        "synthetic": True,
        "boundary_action": "synthetic_missing_token_local_gap",
    }
    reconciled_words = [*words[:missing_index], synthetic_word, *words[missing_index:]]
    reconciliation = {
        "status": "single_missing_token_reconciled",
        "missing_token": missing_token,
        "missing_token_index": missing_index,
        "left_word": str(left_word.get("word") or ""),
        "right_word": str(right_word.get("word") or ""),
        "left_end_seconds": round(left_end_sample / sample_rate, 6),
        "right_start_seconds": round(right_start_sample / sample_rate, 6),
        "gap_samples": right_start_sample - left_end_sample,
        "gap_seconds": round((right_start_sample - left_end_sample) / sample_rate, 6),
        "source": "candidate_alignment_single_missing_token_local_gap",
    }
    return reconciled_words, reconciliation


def is_nonspoken_punctuation(text: str) -> bool:
    value = str(text or "").strip()
    return bool(value) and all(unicodedata.category(character)[0] in {"P", "S"} for character in value)


def build_physical_record_sample_windows(lane: dict, lane_audio: SupertonicPreparedAudio) -> list[tuple[int, int]]:
    actual_chunk_texts = [str(value or "").strip() for value in getattr(lane_audio, "actual_chunk_texts", []) or []]
    chunk_sample_counts = [int(value) for value in getattr(lane_audio, "actual_chunk_sample_counts", []) or []]
    silence_samples = int(getattr(lane_audio, "inter_chunk_silence_source_samples", -1))
    source_sample_count = int(getattr(lane_audio, "physical_source_sample_count", 0))
    output_sample_count = len(lane_audio.wav_array)
    if not chunk_sample_counts or any(value <= 0 for value in chunk_sample_counts):
        raise RuntimeError(f"Supertonic aday lane gercek chunk ornek bilgisi yok: lane={lane['lane_id']}")
    expected_chunk_texts = [
        chunk
        for record in lane["records"]
        for chunk in chunk_text(str(record["spoken_text"]).strip(), 300)
    ]
    if actual_chunk_texts != expected_chunk_texts:
        raise RuntimeError(f"Supertonic aday lane gercek chunk metin sirasi uyusmuyor: lane={lane['lane_id']}")
    if silence_samples < 0 or source_sample_count <= 0 or output_sample_count <= 0:
        raise RuntimeError(f"Supertonic aday lane fiziksel WAV bilgisi gecersiz: lane={lane['lane_id']}")
    if sum(chunk_sample_counts) + silence_samples * max(0, len(chunk_sample_counts) - 1) != source_sample_count:
        raise RuntimeError(f"Supertonic aday lane fiziksel WAV toplami uyusmuyor: lane={lane['lane_id']}")
    record_chunk_counts = [len(chunk_text(str(record["spoken_text"]).strip(), 300)) for record in lane["records"]]
    if any(value <= 0 for value in record_chunk_counts) or sum(record_chunk_counts) != len(chunk_sample_counts):
        raise RuntimeError(f"Supertonic aday lane gercek chunk sirasi uyusmuyor: lane={lane['lane_id']}")
    chunk_starts = []
    source_cursor = 0
    for chunk_index, chunk_sample_count in enumerate(chunk_sample_counts):
        if chunk_index > 0:
            source_cursor += silence_samples
        chunk_starts.append(source_cursor)
        source_cursor += chunk_sample_count
    first_chunk_indices = []
    chunk_cursor = 0
    for record_chunk_count in record_chunk_counts:
        first_chunk_indices.append(chunk_cursor)
        chunk_cursor += record_chunk_count
    windows = []
    for record_index, first_chunk_index in enumerate(first_chunk_indices):
        source_start = chunk_starts[first_chunk_index]
        source_end = chunk_starts[first_chunk_indices[record_index + 1]] if record_index < len(first_chunk_indices) - 1 else source_sample_count
        output_start = int(round(source_start * output_sample_count / source_sample_count))
        output_end = int(round(source_end * output_sample_count / source_sample_count))
        output_end = max(output_end, output_start + 1)
        windows.append((output_start, min(output_end, output_sample_count)))
    if windows[0][0] != 0 or windows[-1][1] != output_sample_count:
        raise RuntimeError(f"Supertonic aday lane fiziksel WAV kenarlari eksik: lane={lane['lane_id']}")
    if any(windows[index][1] != windows[index + 1][0] for index in range(len(windows) - 1)):
        raise RuntimeError(f"Supertonic aday lane fiziksel WAV pencereleri bitisik degil: lane={lane['lane_id']}")
    return windows


def build_candidate_lanes(candidate_records: list[dict], round_label: str) -> list[dict]:
    ordered = sorted(candidate_records, key=lambda item: (int(item["candidate_number"]), float(item["start"]), int(item["segment_index"])))
    lanes = []
    current = None
    for record in ordered:
        candidate_number = int(record["candidate_number"])
        voice_id = str(record.get("voice_id") or "").strip().upper()
        speaker_id = str(record.get("speaker_id") or "").strip()
        segment_index = int(record["segment_index"])
        lane_key = (candidate_number, voice_id, speaker_id)
        contiguous = current is not None and segment_index == int(current["last_segment_index"]) + 1
        if current is None or current["lane_key"] != lane_key or not contiguous:
            current = {
                "lane_key": lane_key,
                "round_label": str(round_label),
                "candidate_number": candidate_number,
                "voice_id": voice_id,
                "speaker_id": speaker_id,
                "records": [],
                "last_segment_index": segment_index,
            }
            lanes.append(current)
        current["records"].append(record)
        current["last_segment_index"] = segment_index
    for lane_number, lane in enumerate(lanes, start=1):
        first_index = int(lane["records"][0]["segment_index"])
        last_index = int(lane["records"][-1]["segment_index"])
        lane["lane_id"] = f"{lane['round_label']}_c{lane['candidate_number']}_{lane['voice_id']}_{lane['speaker_id'] or 'none'}_{first_index}_{last_index}_{lane_number}"
        lane["spoken_text"] = "\n\n".join(str(record["spoken_text"]).strip() for record in lane["records"])
        lane["alignment_text"] = " ".join(str(record["spoken_text"]).strip() for record in lane["records"])
        lane["expected_tokens"] = normalize_tokens(lane["alignment_text"])
    return lanes


def build_candidate_lane_alignment_windows(
    lane: dict,
    lane_audio: SupertonicPreparedAudio,
    sample_rate: int,
) -> list[dict]:
    output_sample_count = len(lane_audio.wav_array)
    if sample_rate <= 0 or output_sample_count <= 0:
        raise RuntimeError(f"Supertonic aday lane alignment WAV bilgisi gecersiz: lane={lane['lane_id']}")
    duration = output_sample_count / sample_rate
    if duration <= LONG_CANDIDATE_LANE_ALIGNMENT_SECONDS and len(lane["records"]) <= 1:
        return []
    actual_chunk_texts = [str(value or "").strip() for value in getattr(lane_audio, "actual_chunk_texts", []) or []]
    chunk_sample_counts = [int(value) for value in getattr(lane_audio, "actual_chunk_sample_counts", []) or []]
    silence_samples = int(getattr(lane_audio, "inter_chunk_silence_source_samples", -1))
    source_sample_count = int(getattr(lane_audio, "physical_source_sample_count", 0))
    expected_chunk_texts = [
        chunk
        for record in lane["records"]
        for chunk in chunk_text(str(record["spoken_text"]).strip(), 300)
    ]
    if not actual_chunk_texts or actual_chunk_texts != expected_chunk_texts:
        raise RuntimeError(f"Supertonic uzun aday lane gercek chunk metin sirasi uyusmuyor: lane={lane['lane_id']}")
    if len(chunk_sample_counts) != len(actual_chunk_texts) or any(value <= 0 for value in chunk_sample_counts):
        raise RuntimeError(f"Supertonic uzun aday lane gercek chunk WAV bilgisi gecersiz: lane={lane['lane_id']}")
    if silence_samples < 0 or source_sample_count <= 0:
        raise RuntimeError(f"Supertonic uzun aday lane fiziksel WAV bilgisi gecersiz: lane={lane['lane_id']}")
    if sum(chunk_sample_counts) + silence_samples * max(0, len(chunk_sample_counts) - 1) != source_sample_count:
        raise RuntimeError(f"Supertonic uzun aday lane fiziksel WAV toplami uyusmuyor: lane={lane['lane_id']}")
    cursor = 0
    windows = []
    for index, (text, chunk_sample_count) in enumerate(zip(actual_chunk_texts, chunk_sample_counts), start=1):
        if index > 1:
            cursor += silence_samples
        source_start = cursor
        cursor += chunk_sample_count
        source_end = cursor
        output_start = int(round(source_start * output_sample_count / source_sample_count))
        output_end = int(round(source_end * output_sample_count / source_sample_count))
        output_end = max(output_end, output_start + 1)
        windows.append({
            "index": index,
            "text": text,
            "start": output_start / sample_rate,
            "end": min(output_end / sample_rate, duration),
        })
    if cursor != source_sample_count:
        raise RuntimeError(f"Supertonic uzun aday lane gercek chunk WAV toplami nihai sesle uyusmuyor: lane={lane['lane_id']}")
    return windows


def demux_verified_candidate_lane(lane: dict, lane_audio: SupertonicPreparedAudio, sample_rate: int) -> dict[tuple, SupertonicPreparedAudio]:
    words = []
    word_token_groups = []
    for word in list(getattr(lane_audio, "word_boundaries", []) or []):
        tokens = normalize_tokens(word.get("word", ""))
        if tokens:
            words.append(word)
            word_token_groups.append(tokens)
            continue
        if not is_nonspoken_punctuation(word.get("word", "")):
            raise RuntimeError(f"Supertonic aday lane hizalama kelimesi bos: lane={lane['lane_id']}")
    words, token_reconciliation = _reconcile_single_missing_token(
        lane,
        words,
        word_token_groups,
        sample_rate,
    )
    if token_reconciliation:
        lane_audio.word_boundaries = list(words)
        candidate_alignment = dict(getattr(lane_audio, "candidate_alignment", {}) or {})
        candidate_alignment["token_reconciliation"] = token_reconciliation
        candidate_alignment["word_count"] = len(words)
        setattr(lane_audio, "candidate_alignment", candidate_alignment)
        word_token_groups = [[token] for token in list(lane["expected_tokens"])]
    result = {}
    word_cursor = 0
    physical_windows = build_physical_record_sample_windows(lane, lane_audio)
    audio_duration = len(lane_audio.wav_array) / sample_rate
    chunk_timeline = list(getattr(lane_audio, "chunk_timeline", []) or [])
    record_chunk_counts = [len(chunk_text(str(record["spoken_text"]).strip(), 300)) for record in lane["records"]]
    if chunk_timeline and sum(record_chunk_counts) != len(chunk_timeline):
        raise RuntimeError(f"Supertonic aday lane chunk sirasi uyusmuyor: lane={lane['lane_id']}")
    chunk_cursor = 0
    for record_index, record in enumerate(lane["records"]):
        expected = normalize_tokens(record["spoken_text"])
        selected_words = []
        selected_tokens = []
        while word_cursor < len(words) and len(selected_tokens) < len(expected):
            selected_words.append(words[word_cursor])
            selected_tokens.extend(word_token_groups[word_cursor])
            word_cursor += 1
        if not expected or selected_tokens != expected:
            raise RuntimeError(f"Supertonic aday lane segment kelime sirasi uyusmuyor: lane={lane['lane_id']} segment={record['segment_id']}")
        active_start = float(selected_words[0]["start"])
        active_end = float(selected_words[-1]["end"])
        record_chunk_count = record_chunk_counts[record_index]
        next_chunk_start = None
        if chunk_timeline:
            if record_index < len(lane["records"]) - 1:
                next_chunk_start = float(chunk_timeline[chunk_cursor + record_chunk_count]["start"])
        physical_start_sample, physical_end_sample = physical_windows[record_index]
        physical_start = physical_start_sample / sample_rate
        physical_end = physical_end_sample / sample_rate
        cut_start = max(active_start - 0.05, physical_start)
        if record_index < len(lane["records"]) - 1:
            boundary_end = next_chunk_start if next_chunk_start is not None else float(words[word_cursor]["start"])
            cut_end = min(max(active_end + 0.08, boundary_end), audio_duration)
        else:
            cut_end = min(active_end + 0.08, audio_duration)
        cut_end = min(cut_end, physical_end)
        if cut_end <= cut_start:
            raise RuntimeError(f"Supertonic aday lane fiziksel sinir icinde gecersiz kesim: lane={lane['lane_id']} segment={record['segment_id']}")
        start_sample = int(round(cut_start * sample_rate))
        end_sample = max(int(round(cut_end * sample_rate)), start_sample + 1)
        wav_array = np.asarray(lane_audio.wav_array[start_sample:end_sample], dtype=np.float32)
        duration = len(wav_array) / sample_rate
        local_words = []
        for word in selected_words:
            word_start_sample = int(round(float(word["start"]) * sample_rate))
            word_end_sample = int(round(float(word["end"]) * sample_rate))
            local_start_sample = word_start_sample - start_sample
            local_end_sample = word_end_sample - start_sample
            local_words.append({
                **word,
                "start": round(local_start_sample / sample_rate, 6),
                "end": round(local_end_sample / sample_rate, 6),
                "demux_start_sample": local_start_sample,
                "demux_end_sample": local_end_sample,
            })
        _validate_demuxed_word_boundaries(local_words, duration, lane["lane_id"], record["segment_id"], sample_rate)
        prepared = SupertonicPreparedAudio(
            index=int(record["segment_index"]), wav_array=wav_array, start_time=0.0,
            raw_duration=duration, engine_raw_duration=duration, processed_duration=duration,
            trim_meta={"trim_source": "supertonic_actual_chunk_sample_boundaries_with_ac4c34a_buffers"},
        )
        setattr(prepared, "word_boundaries", local_words)
        setattr(prepared, "word_timing_source", "candidate_lane_forced_alignment")
        candidate_alignment = {
            "success": True, "source": "candidate_lane_forced_alignment", "word_count": len(local_words),
            "active_start_seconds": round(active_start, 6), "active_end_seconds": round(active_end, 6),
            "cut_start_seconds": round(cut_start, 6), "cut_end_seconds": round(cut_end, 6),
            "boundary_source": "ac4c34a_buffers_clamped_to_supertonic_actual_chunk_samples",
        }
        if token_reconciliation:
            candidate_alignment["token_reconciliation"] = token_reconciliation
        setattr(prepared, "candidate_alignment", candidate_alignment)
        setattr(prepared, "candidate_lane_provenance", {
            "lane_id": lane["lane_id"], "round_label": lane["round_label"], "candidate_number": lane["candidate_number"],
            "segment_index": int(record["segment_index"]), "voice_id": lane["voice_id"], "speaker_id": lane["speaker_id"],
            "source_audio_key": lane["audio_key"], "boundary_source": "supertonic_actual_chunk_samples",
            "physical_cut_start_seconds": round(physical_start, 6), "physical_cut_end_seconds": round(physical_end, 6),
        })
        result[record["audio_key"]] = prepared
        chunk_cursor += record_chunk_count
    if word_cursor != len(words):
        raise RuntimeError(f"Supertonic aday lane fazla kelime iceriyor: lane={lane['lane_id']}")
    return result


def _validate_demuxed_word_boundaries(
    words: list[dict],
    duration: float,
    lane_id: str,
    segment_id: str,
    sample_rate: int,
) -> None:
    duration_samples = int(round(duration * sample_rate))
    for word_index, word in enumerate(words):
        start_sample = int(word.get("demux_start_sample", round(float(word.get("start", 0.0) or 0.0) * sample_rate)))
        end_sample = int(word.get("demux_end_sample", round(float(word.get("end", 0.0) or 0.0) * sample_rate)))
        if start_sample < 0 and word_index == 0 and start_sample >= -1:
            start_sample = 0
            word["boundary_action"] = "+".join(
                item for item in (str(word.get("boundary_action", "none")), "demux_sample_clamped") if item and item != "none"
            ) or "demux_sample_clamped"
            word["demux_start_sample"] = start_sample
            word["start"] = 0.0
        start = start_sample / sample_rate
        end = end_sample / sample_rate
        word["start"] = round(start, 6)
        word["end"] = round(end, 6)
        if start_sample < 0 or start_sample >= duration_samples or end_sample <= start_sample:
            raise RuntimeError(
                f"Supertonic demux kelime zamani gecersiz: lane={lane_id} segment={segment_id} word={word.get('word', '')} "
                f"start={start:.9f} end={end:.9f} duration={duration:.9f} "
                f"start_sample={start_sample} end_sample={end_sample} duration_samples={duration_samples}"
            )
        if end_sample > duration_samples + 1:
            raise RuntimeError(
                f"Supertonic demux kelime zamani fiziksel WAV disinda: lane={lane_id} segment={segment_id} word={word.get('word', '')} "
                f"start={start:.9f} end={end:.9f} duration={duration:.9f} "
                f"start_sample={start_sample} end_sample={end_sample} duration_samples={duration_samples}"
            )
        if end_sample > duration_samples:
            end_sample = duration_samples
            word["demux_end_sample"] = end_sample
            word["end"] = round(duration, 6)
            word["boundary_action"] = "+".join(
                item for item in (str(word.get("boundary_action", "none")), "demux_sample_clamped") if item and item != "none"
            ) or "demux_sample_clamped"
        if end_sample <= start_sample:
            raise RuntimeError(
                f"Supertonic demux kelime zamani fiziksel WAV sinirinda gecersiz: lane={lane_id} segment={segment_id} word={word.get('word', '')} "
                f"start={start:.9f} end={end_sample / sample_rate:.9f} duration={duration:.9f} "
                f"start_sample={start_sample} end_sample={end_sample} duration_samples={duration_samples}"
            )
