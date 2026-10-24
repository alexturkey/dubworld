from contextlib import contextmanager
import re


no_space_languages = frozenset({'ja', 'zh', 'yue', 'th', 'lo', 'my'})


class TranscriptCoverageError(RuntimeError):
    pass


def require_timed_text_coverage(text, words):
    decoded = ''.join(str(text or '').split())
    timed = ''.join(''.join(str(word['word']).split()) for word in words)
    if '\ufffd' in decoded or '\ufffd' in timed:
        raise TranscriptCoverageError('Native timing contains invalid Unicode')
    if decoded != timed:
        raise TranscriptCoverageError(
            f'Native timing text coverage mismatch: decoded={len(decoded)} timed={len(timed)}'
        )


def is_unspaced_character(character):
    value = ord(character)
    return (
        0x0e00 <= value <= 0x109f
        or 0x3040 <= value <= 0x30ff
        or 0x3400 <= value <= 0x9fff
        or 0xf900 <= value <= 0xfaff
        or 0x20000 <= value <= 0x323af
    )


def unicode_timing_groups(tokenizer, token_ids, source_groups):
    groups = []
    texts = []
    for source_group in source_groups:
        complete = tokenizer.decode([token_ids[index] for index in source_group]).strip()
        if '\ufffd' in complete:
            raise RuntimeError('Generated token group contains invalid Unicode')
        if not complete:
            continue
        if not any(is_unspaced_character(character) for character in complete):
            groups.append(list(source_group))
            texts.append(complete)
            continue
        pending = []
        latin = []
        latin_text = ''
        for index in source_group:
            pending.append(index)
            decoded = tokenizer.decode([token_ids[value] for value in pending])
            if '\ufffd' in decoded or decoded.count('[') > decoded.count(']'):
                continue
            if not any(is_unspaced_character(character) for character in decoded) and not decoded.startswith('['):
                latin.extend(pending)
                latin_text += decoded
                pending = []
                continue
            if latin and latin_text.strip():
                groups.append(latin)
                texts.append(latin_text.strip())
                latin = []
                latin_text = ''
            groups.append(pending)
            texts.append(decoded.strip())
            pending = []
        if pending:
            raise RuntimeError('Generated token group ends with incomplete Unicode or event')
        if latin and latin_text.strip():
            groups.append(latin)
            texts.append(latin_text.strip())
    return groups, texts


def content_units(text):
    without_events = re.sub(r'\[[^\[\]]*\]', '', text)
    return sum(character.isalnum() for character in without_events)


@contextmanager
def language_timing_context(model, language):
    if language.lower() not in no_space_languages:
        yield
        return
    import crisperwhisper.fallback as fallback
    import crisperwhisper.word_timing as timing
    from crisperwhisper.prompt import strip_prompt_artifacts
    import coverage_recovery

    tokenizer = model._engine.tokenizer
    original_groups = timing.group_tokens_into_words
    original_count = fallback.word_count
    original_recovery_count = coverage_recovery.word_count

    def grouped(token_ids, token_pieces):
        source_groups, _ = original_groups(token_ids, token_pieces)
        return unicode_timing_groups(tokenizer, token_ids, source_groups)

    def counted(engine, token_ids):
        return content_units(strip_prompt_artifacts(engine.decode_tokens(token_ids, skip_special=True)))

    timing.group_tokens_into_words = grouped
    fallback.word_count = counted
    coverage_recovery.word_count = counted
    try:
        yield
    finally:
        timing.group_tokens_into_words = original_groups
        fallback.word_count = original_count
        coverage_recovery.word_count = original_recovery_count
