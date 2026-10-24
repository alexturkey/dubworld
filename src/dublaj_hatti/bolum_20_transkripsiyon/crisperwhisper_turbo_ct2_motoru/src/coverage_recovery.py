from __future__ import annotations

from typing import Optional

import numpy as np
import ctranslate2

from crisperwhisper.fallback import (
    _discrepant,
    decode_with_coverage_fallback as original_decode_with_coverage_fallback,
    is_undercovered,
    word_count,
)
from crisperwhisper.hallucination import find_token_loop


FAST_CANDIDATES = ((0.8, 7), (0.8, 8), (0.8, 6))
WINDOW_REPLAN_ALLOWED = False
WINDOW_REPLAN_MARKER = "OUTER_WINDOW_REPLAN_REQUIRED"


def decode_with_reordered_temperatures(*args, **kwargs):
    kwargs["temperatures"] = (0.8, 0.4, 0.6, 1.0)
    return original_decode_with_coverage_fallback(*args, **kwargs)


def decode_with_direct_coverage_recovery(
    engine,
    features,
    mel: Optional[np.ndarray],
    prompt_tokens: list[int],
    gen_ids: list[int],
    attention: Optional[np.ndarray],
    *,
    max_length: int,
    want_attention: bool,
    enabled: bool = True,
    ref_word_count: Optional[int] = None,
    ref_prompt_tokens: Optional[list[int]] = None,
    temperatures=(0.4, 0.6, 0.8, 1.0),
    suppress_tokens: Optional[list[int]] = None,
):
    if not enabled or not hasattr(engine, "generate_sampled"):
        return gen_ids, attention
    base_word_count = word_count(engine, gen_ids)
    if base_word_count > 1 or not is_undercovered(base_word_count, mel):
        return decode_with_reordered_temperatures(
            engine,
            features,
            mel,
            prompt_tokens,
            gen_ids,
            attention,
            max_length=max_length,
            want_attention=want_attention,
            enabled=enabled,
            ref_word_count=ref_word_count,
            ref_prompt_tokens=ref_prompt_tokens,
            temperatures=temperatures,
            suppress_tokens=suppress_tokens,
        )
    seed = 0
    for temperature in (0.8, 0.4, 0.6, 1.0):
        for _ in range(3):
            current_seed = seed
            seed += 1
            try:
                sampled_ids = engine.generate_sampled(
                    features,
                    prompt_tokens,
                    max_length=max_length,
                    temperature=temperature,
                    topk=0,
                    seed=current_seed,
                    suppress_tokens=suppress_tokens,
                )
            except Exception:
                continue
            if find_token_loop(sampled_ids, min_ngram=1, max_ngram=5) is not None:
                continue
            if is_undercovered(word_count(engine, sampled_ids), mel):
                continue
            sampled_attention = attention
            if want_attention:
                sampled_attention = engine.cross_attention_for_tokens(
                    features,
                    prompt_tokens,
                    sampled_ids,
                )
            return sampled_ids, sampled_attention
    return decode_with_reordered_temperatures(
        engine,
        features,
        mel,
        prompt_tokens,
        gen_ids,
        attention,
        max_length=max_length,
        want_attention=want_attention,
        enabled=enabled,
        ref_word_count=ref_word_count,
        ref_prompt_tokens=ref_prompt_tokens,
        temperatures=temperatures,
        suppress_tokens=suppress_tokens,
    )


def decode_with_outer_window_replan(
    engine,
    features,
    mel: Optional[np.ndarray],
    prompt_tokens: list[int],
    gen_ids: list[int],
    attention: Optional[np.ndarray],
    **kwargs,
):
    base_word_count = word_count(engine, gen_ids)
    if (
        WINDOW_REPLAN_ALLOWED
        and base_word_count <= 1
        and is_undercovered(base_word_count, mel)
    ):
        raise RuntimeError(WINDOW_REPLAN_MARKER)
    return decode_with_direct_coverage_recovery(
        engine,
        features,
        mel,
        prompt_tokens,
        gen_ids,
        attention,
        **kwargs,
    )


def decode_with_batched_recovery(
    engine,
    features,
    mel: Optional[np.ndarray],
    prompt_tokens: list[int],
    gen_ids: list[int],
    attention: Optional[np.ndarray],
    *,
    max_length: int,
    want_attention: bool,
    enabled: bool = True,
    ref_word_count: Optional[int] = None,
    ref_prompt_tokens: Optional[list[int]] = None,
    temperatures=(0.4, 0.6, 0.8, 1.0),
    suppress_tokens: Optional[list[int]] = None,
):
    if not enabled or ref_prompt_tokens is None:
        return gen_ids, attention
    base_word_count = word_count(engine, gen_ids)
    if not is_undercovered(base_word_count, mel):
        return gen_ids, attention
    sibling_ids = engine.generate(
        features,
        [list(ref_prompt_tokens)],
        max_length=max_length,
        suppress_tokens=suppress_tokens,
    )[0]
    sibling_word_count = word_count(engine, sibling_ids)
    if not _discrepant(base_word_count, sibling_word_count):
        return gen_ids, attention
    ctranslate2.set_random_seed(0)
    max_prompt = len(prompt_tokens)
    ct2_max_length = max(max_length * 2, max_length + max_prompt - 1)
    mel_array = mel[0] if getattr(mel, "ndim", 2) == 3 else mel
    batched_features = ctranslate2.StorageView.from_array(
        np.repeat(np.expand_dims(mel_array, 0), 3, axis=0).astype(np.float32)
    )
    results = engine.model.generate(
        batched_features,
        [list(prompt_tokens) for _ in range(3)],
        max_length=ct2_max_length,
        beam_size=1,
        suppress_blank=False,
        suppress_tokens=engine._resolve_suppress(suppress_tokens),
        sampling_temperature=0.8,
        sampling_topk=0,
        return_scores=False,
        return_no_speech_prob=False,
    )
    candidates = [
        [int(token) for token in result.sequences_ids[0]]
        for result in results
    ]
    valid_candidates = [
        candidate
        for candidate in candidates
        if find_token_loop(candidate, min_ngram=1, max_ngram=5) is None
        and not _discrepant(word_count(engine, candidate), sibling_word_count)
    ]
    if not valid_candidates:
        return original_decode_with_coverage_fallback(
            engine,
            features,
            mel,
            prompt_tokens,
            gen_ids,
            attention,
            max_length=max_length,
            want_attention=want_attention,
            enabled=enabled,
            ref_word_count=ref_word_count,
            ref_prompt_tokens=ref_prompt_tokens,
            temperatures=temperatures,
            suppress_tokens=suppress_tokens,
        )
    selected = max(valid_candidates, key=lambda value: word_count(engine, value))
    selected_attention = attention
    if want_attention:
        selected_attention = engine.cross_attention_for_tokens(
            features,
            prompt_tokens,
            selected,
        )
    return selected, selected_attention


def decode_with_sibling_recovery(
    engine,
    features,
    mel: Optional[np.ndarray],
    prompt_tokens: list[int],
    gen_ids: list[int],
    attention: Optional[np.ndarray],
    *,
    max_length: int,
    want_attention: bool,
    enabled: bool = True,
    ref_word_count: Optional[int] = None,
    ref_prompt_tokens: Optional[list[int]] = None,
    temperatures=(0.4, 0.6, 0.8, 1.0),
    suppress_tokens: Optional[list[int]] = None,
):
    if not enabled or ref_prompt_tokens is None:
        return gen_ids, attention
    base_word_count = word_count(engine, gen_ids)
    if not is_undercovered(base_word_count, mel):
        return gen_ids, attention
    sibling_ids = engine.generate(
        features,
        [list(ref_prompt_tokens)],
        max_length=max_length,
        suppress_tokens=suppress_tokens,
    )[0]
    sibling_word_count = word_count(engine, sibling_ids)
    if not _discrepant(base_word_count, sibling_word_count):
        return gen_ids, attention
    sibling_attention = attention
    if want_attention:
        sibling_attention = engine.cross_attention_for_tokens(
            features,
            ref_prompt_tokens,
            sibling_ids,
        )
    return sibling_ids, sibling_attention


def decode_with_fast_candidate(
    engine,
    features,
    mel: Optional[np.ndarray],
    prompt_tokens: list[int],
    gen_ids: list[int],
    attention: Optional[np.ndarray],
    *,
    max_length: int,
    want_attention: bool,
    enabled: bool = True,
    ref_word_count: Optional[int] = None,
    ref_prompt_tokens: Optional[list[int]] = None,
    temperatures=(0.4, 0.6, 0.8, 1.0),
    suppress_tokens: Optional[list[int]] = None,
):
    if not enabled or not hasattr(engine, "generate_sampled"):
        return gen_ids, attention
    base_word_count = word_count(engine, gen_ids)
    sibling_word_count = ref_word_count
    if sibling_word_count is not None:
        if not _discrepant(base_word_count, sibling_word_count):
            return gen_ids, attention
    else:
        if not is_undercovered(base_word_count, mel):
            return gen_ids, attention
        if ref_prompt_tokens is not None:
            try:
                sibling_ids = engine.generate(
                    features,
                    [list(ref_prompt_tokens)],
                    max_length=max_length,
                    suppress_tokens=suppress_tokens,
                )[0]
                sibling_word_count = word_count(engine, sibling_ids)
                if not _discrepant(base_word_count, sibling_word_count):
                    return gen_ids, attention
            except Exception:
                sibling_word_count = None
    for temperature, seed in FAST_CANDIDATES:
        try:
            sampled_ids = engine.generate_sampled(
                features,
                prompt_tokens,
                max_length=max_length,
                temperature=temperature,
                topk=0,
                seed=seed,
                suppress_tokens=suppress_tokens,
            )
        except Exception:
            continue
        if find_token_loop(sampled_ids, min_ngram=1, max_ngram=5) is not None:
            continue
        sampled_word_count = word_count(engine, sampled_ids)
        recovered = (
            not _discrepant(sampled_word_count, sibling_word_count)
            if sibling_word_count is not None
            else not is_undercovered(sampled_word_count, mel)
        )
        if not recovered:
            continue
        sampled_attention = attention
        if want_attention:
            sampled_attention = engine.cross_attention_for_tokens(
                features,
                prompt_tokens,
                sampled_ids,
            )
        return sampled_ids, sampled_attention
    return original_decode_with_coverage_fallback(
        engine,
        features,
        mel,
        prompt_tokens,
        gen_ids,
        attention,
        max_length=max_length,
        want_attention=want_attention,
        enabled=enabled,
        ref_word_count=ref_word_count,
        ref_prompt_tokens=ref_prompt_tokens,
        temperatures=temperatures,
        suppress_tokens=suppress_tokens,
    )
