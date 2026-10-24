from __future__ import annotations

import numpy as np

WORD_BOUNDARY_POLICY = "ctc_speech_bounded_v2"
NO_SPACE_ALIGNMENT_LANGUAGES = frozenset({"ja", "zh"})
# Neden: konusma araligi +-150 ms ile 100 dk seste 1.5 sn ustu kelime 0; ham sessizlik esikleri 7 sesle ayarlandi. bkz. docs/engineering/pinned-values.md#word-alignment
SPEECH_PAD_SECONDS = 0.15
SAMPLE_RATE = 16000
MINIMUM_WINDOW_SAMPLES = 400
RAW_SILENCE_FRAME_SECONDS = 0.02
RAW_SILENCE_CONTEXT_SECONDS = 2.0
RAW_SILENCE_LEVEL_RATIO = 0.35
RAW_SILENCE_MINIMUM_CONTRAST_DB = 6.0


def bound_word_to_speech(start: float, end: float, speech_start: float, speech_end: float,
                         pad: float = SPEECH_PAD_SECONDS) -> tuple[float, float]:
    bounded_start = max(start, speech_start - pad)
    bounded_end = min(end, speech_end + pad)
    if bounded_end <= bounded_start:
        return round(speech_start, 3), round(speech_end, 3)
    return round(bounded_start, 3), round(bounded_end, 3)



def longest_silent_run_seconds(samples, sample_rate: int, word_start: float, word_end: float) -> float | None:
    frame_length = int(sample_rate * RAW_SILENCE_FRAME_SECONDS)
    frame_count = len(samples) // frame_length
    if frame_length <= 0 or frame_count == 0:
        return None
    frames = np.asarray(samples[: frame_count * frame_length], dtype="float64").reshape(frame_count, frame_length)
    levels = 10.0 * np.log10(np.mean(frames * frames, axis=1) + 1e-12)
    floor, peak = np.percentile(levels, 10), np.percentile(levels, 95)
    if peak - floor < RAW_SILENCE_MINIMUM_CONTRAST_DB:
        return None
    silent = levels < floor + RAW_SILENCE_LEVEL_RATIO * (peak - floor)
    first = max(0, int(word_start * sample_rate) // frame_length)
    last = min(frame_count, -(-int(word_end * sample_rate) // frame_length))
    longest = current = 0
    for is_silent in silent[first:last]:
        current = current + 1 if is_silent else 0
        longest = max(longest, current)
    return round(longest * RAW_SILENCE_FRAME_SECONDS, 3)

def blank_id_of(dictionary: dict) -> int:
    for char, code in dictionary.items():
        if char in ("[pad]", "<pad>"):
            return code
    return 0


def segment_word_texts(text: str) -> list[str]:
    return [word for word in text.strip().split(" ") if word]


class CharacterRegroupError(RuntimeError):
    pass


def is_no_space_language(language: str | None) -> bool:
    code = str(language or "").strip().lower().split("-", 1)[0].split("_", 1)[0]
    return code in NO_SPACE_ALIGNMENT_LANGUAGES


def no_space_alignment_segments(input_segments: list[dict]) -> list[dict]:
    return [
        dict(segment, text="".join(segment_word_texts(str(segment.get("text") or ""))))
        for segment in input_segments
    ]


def source_word_texts(input_segments: list[dict]) -> list[str]:
    return [word for segment in input_segments for word in segment_word_texts(str(segment.get("text") or ""))]


def _close_regrouped_word(word: dict) -> None:
    timed = word.pop("timed_characters")
    word.pop("characters")
    if not timed:
        return
    word["start"] = min(float(character["start"]) for character in timed)
    word["end"] = max(float(character["end"]) for character in timed)
    scores = [float(character["score"]) for character in timed if character.get("score") is not None]
    if scores:
        word["score"] = round(sum(scores) / len(scores), 3)


def regroup_character_words(aligned_segments: list[dict], source_words: list[str]) -> int:
    word_index = 0
    current = None
    for segment in aligned_segments:
        grouped = []
        for character in segment.get("words") or []:
            piece = str(character.get("word") or "").strip()
            if not piece:
                continue
            if current is None:
                if word_index >= len(source_words):
                    raise CharacterRegroupError(
                        f"CTC no-space regroup has extra characters after {len(source_words)} source words: {piece!r}"
                    )
                current = {"word": source_words[word_index], "characters": "", "timed_characters": []}
                grouped.append(current)
            current["characters"] += piece
            if "start" in character and "end" in character:
                current["timed_characters"].append(character)
            if not current["word"].startswith(current["characters"]):
                raise CharacterRegroupError(
                    f"CTC no-space regroup mismatch at source word {word_index}: "
                    f"expected={current['word']!r} aligned={current['characters']!r}"
                )
            if current["characters"] == current["word"]:
                _close_regrouped_word(current)
                word_index += 1
                current = None
        segment["words"] = grouped
    if current is not None or word_index != len(source_words):
        raise CharacterRegroupError(
            f"CTC no-space regroup consumed {word_index} of {len(source_words)} source words"
        )
    return word_index


def speech_tokens_for_words(words: list[str], no_space: bool) -> tuple[list[str], list[int]]:
    chars, word_of_char = [], []
    for word_index, word in enumerate(words):
        if word_index and not no_space:
            chars.append("|")
            word_of_char.append(-1)
        for char in word.lower():
            chars.append(char)
            word_of_char.append(word_index)
    return chars, word_of_char


def _segment_emission(model, metadata, audio_tensor, start: float, end: float, device: str, torch):
    first = int(start * SAMPLE_RATE)
    last = int(end * SAMPLE_RATE)
    window = audio_tensor[:, first:last]
    lengths = None
    if window.shape[-1] < MINIMUM_WINDOW_SAMPLES:
        lengths = torch.as_tensor([window.shape[-1]]).to(device)
        window = torch.nn.functional.pad(window, (0, MINIMUM_WINDOW_SAMPLES - window.shape[-1]))
    with torch.inference_mode():
        if metadata["type"] == "torchaudio":
            emissions, _ = model(window.to(device), lengths=lengths)
        else:
            emissions = model(window.to(device)).logits
        emissions = torch.log_softmax(emissions, dim=-1)
    emission = emissions[0].cpu()
    return emission, (end - start) / emission.size(0)


def _segment_speech_spans(emission, seconds_per_frame: float, segment_start: float, text: str,
                          dictionary: dict, torch, audio_functional,
                          no_space: bool = False) -> list[tuple[float, float] | None]:
    words = segment_word_texts(text)
    blank_id = blank_id_of(dictionary)
    chars, word_of_char = speech_tokens_for_words(words, no_space)
    known = [char in dictionary and dictionary[char] != blank_id for char in chars]
    working = emission
    if not all(known):
        non_blank = torch.ones(emission.size(1), dtype=torch.bool)
        non_blank[blank_id] = False
        wildcard = emission[:, non_blank].max(dim=1).values.unsqueeze(1)
        working = torch.cat([emission, wildcard], dim=1)
    wildcard_id = working.size(1) - 1
    tokens = [dictionary[char] if is_known else wildcard_id for char, is_known in zip(chars, known)]
    if not tokens or len(tokens) > working.size(0):
        return [None] * len(words)
    aligned, scores = audio_functional.forced_align(
        working.unsqueeze(0), torch.tensor([tokens], dtype=torch.int32), blank=blank_id
    )
    spans = audio_functional.merge_tokens(aligned[0], scores[0].exp(), blank=blank_id)
    result: list[list[float] | None] = [None] * len(words)
    for span, word_index in zip(spans, word_of_char):
        if word_index < 0:
            continue
        span_start = segment_start + span.start * seconds_per_frame
        span_end = segment_start + span.end * seconds_per_frame
        if result[word_index] is None:
            result[word_index] = [span_start, span_end]
        else:
            result[word_index][1] = span_end
    return [(item[0], item[1]) if item else None for item in result]


def apply_speech_bounds(aligned_segments: list[dict], input_segments: list[dict], model, metadata,
                        audio, device: str, torch) -> dict:
    import torchaudio.functional as audio_functional

    audio_tensor = torch.from_numpy(audio).unsqueeze(0)
    dictionary = metadata["dictionary"]
    no_space = is_no_space_language(metadata.get("language"))
    speech: list[tuple[str, tuple[float, float] | None]] = []
    for segment in input_segments:
        words = segment_word_texts(str(segment.get("text") or ""))
        emission, seconds_per_frame = _segment_emission(
            model, metadata, audio_tensor, float(segment["start"]), float(segment["end"]), device, torch
        )
        spans = _segment_speech_spans(
            emission, seconds_per_frame, float(segment["start"]), str(segment.get("text") or ""),
            dictionary, torch, audio_functional, no_space=no_space,
        )
        speech.extend(zip(words, spans))
    timed_words = [
        word for segment in aligned_segments for word in segment.get("words", [])
        if "start" in word and "end" in word and str(word.get("word") or "").strip()
    ]
    report = {
        "policy": WORD_BOUNDARY_POLICY,
        "pad_seconds": SPEECH_PAD_SECONDS,
        "word_count": len(timed_words),
        "speech_span_count": len(speech),
        "bounded_words": 0,
        "relocated_words": 0,
        "unbounded_words": 0,
        "removed_seconds": 0.0,
        "status": "applied",
    }
    if len(timed_words) != len(speech) or any(
        str(word["word"]).strip() != text for word, (text, _span) in zip(timed_words, speech)
    ):
        report["status"] = "word_mismatch_unbounded"
        report["unbounded_words"] = len(timed_words)
        return report
    for word, (_text, span) in zip(timed_words, speech):
        if span is None:
            report["unbounded_words"] += 1
            continue
        word["speech_start"], word["speech_end"] = round(span[0], 3), round(span[1], 3)
        start, end = float(word["start"]), float(word["end"])
        bounded_start, bounded_end = bound_word_to_speech(start, end, span[0], span[1])
        if bounded_end <= start or bounded_start >= end:
            report["relocated_words"] += 1
        if abs(bounded_start - start) > 1e-6 or abs(bounded_end - end) > 1e-6:
            report["bounded_words"] += 1
            report["removed_seconds"] += max(0.0, (end - start) - (bounded_end - bounded_start))
            word["start"], word["end"] = bounded_start, bounded_end
    report["removed_seconds"] = round(report["removed_seconds"], 3)
    return report
