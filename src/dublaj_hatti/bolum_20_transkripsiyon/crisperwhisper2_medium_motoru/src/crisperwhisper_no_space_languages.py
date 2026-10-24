from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from difflib import SequenceMatcher
from math import ceil
from typing import Iterator

from crisperwhisper_longform import classify_timed_repetitions
from crisperwhisper_runtime_optimization import (
    OPTION12_INTENDED_CONSENSUS_SEEDS,
    OPTION12_PLAIN_CONSENSUS_SEED_COUNT,
)


NO_SPACE_LANGUAGE_CODES = frozenset({"ja", "lo", "my", "th", "yue", "zh"})
DEFAULT_LONGFORM_ROUTE = "dynamic_overlap_stitch"
NO_SPACE_LONGFORM_ROUTE = "continuation"
NO_SPACE_CHUNK_DURATION_SECONDS = 29.5
NO_SPACE_STRIDE_SECONDS = 24.5
NO_SPACE_CONTEXT_GROUPS = 64
NO_SPACE_MAX_NEW_TOKENS = 256
NO_SPACE_EXPECTED_MAX_TARGET_POSITIONS = 448
NO_SPACE_CONTEXT_BUDGET_POLICY = "live_model_limit_preserve_generation_budget"
NO_SPACE_CONTEXT_OVERFLOW_POLICY = "retain_recent_unicode_safe_token_suffix_or_no_context"
NO_SPACE_TOKEN_DECODE_POLICY = "decode_minimum_unicode_safe_token_groups"
NO_SPACE_COVERAGE_COUNT_MODE = "content_tokens"
NO_SPACE_FALLBACK_POLICY = "verbatim_intended_then_temperature_or_plain_transcribe_sibling"
NO_SPACE_LOOP_RECOVERY_POLICY = "reject_missing_or_non_increasing_timed_loop_then_temperature_safe_sibling_or_intended_continuation"
NO_SPACE_MIN_SPEECH_SECONDS = 5.0
NO_SPACE_MIN_CONTENT_TOKENS_PER_ACTIVE_SECOND = 0.5
NO_SPACE_MIN_SIBLING_CONTENT_TOKENS = 8
NO_SPACE_MAX_UNCOVERED_ACTIVE_TAIL_SECONDS = 3.0
NO_SPACE_ADAPTIVE_RETRY_CHUNK_DURATION_SECONDS = 15.0
NO_SPACE_ADAPTIVE_RETRY_OVERLAP_SECONDS = 5.0
NO_SPACE_ADAPTIVE_RETRY_STRIDE_SECONDS = (
    NO_SPACE_ADAPTIVE_RETRY_CHUNK_DURATION_SECONDS
    - NO_SPACE_ADAPTIVE_RETRY_OVERLAP_SECONDS
)
NO_SPACE_PLAIN_CONSENSUS_TEMPERATURE = 0.8
NO_SPACE_PLAIN_CONSENSUS_SEED_COUNT = OPTION12_PLAIN_CONSENSUS_SEED_COUNT
NO_SPACE_PLAIN_CONSENSUS_MINIMUM_FRACTION = 0.25
NO_SPACE_INTENDED_CONSENSUS_SEEDS = OPTION12_INTENDED_CONSENSUS_SEEDS
NO_SPACE_INTENDED_CONSENSUS_SEED_COUNT = len(NO_SPACE_INTENDED_CONSENSUS_SEEDS)
NO_SPACE_INTENDED_CONSENSUS_TEMPERATURE = 0.8
NO_SPACE_INTENDED_CONSENSUS_MINIMUM_CANDIDATES = 3
NO_SPACE_INTENDED_CONSENSUS_MAXIMUM_TOKEN_DENSITY = 1.5
NO_SPACE_INTENDED_CONSENSUS_POLICY = (
    "sparse_timed_sibling_median_length_then_bpe_rank"
)
NO_SPACE_ADAPTIVE_RETRY_POLICY = (
    "retry_same_compact_audio_with_overlap_and_deterministic_plain_consensus"
)
NO_SPACE_OVERLAP_SUFFIX_RECOVERY_POLICY = (
    "restore_unrecaptured_exact_timed_suffix_in_source_order"
)
NO_SPACE_OVERLAP_RECAPTURE_MIDPOINT_TOLERANCE_SECONDS = 0.5
NO_SPACE_SHORT_THRESHOLD_SECONDS = 30.0


class CrisperWhisperNoSpaceDiagnosticError(RuntimeError):
    def __init__(self, message: str, diagnostic: dict):
        super().__init__(message)
        self.diagnostic = diagnostic


def normalized_language_code(language: str) -> str:
    return str(language or "").strip().lower().replace("_", "-").split("-", 1)[0]


def select_longform_route(language: str) -> str:
    if normalized_language_code(language) in NO_SPACE_LANGUAGE_CODES:
        return NO_SPACE_LONGFORM_ROUTE
    return DEFAULT_LONGFORM_ROUTE


def uses_no_space_continuation(language: str) -> bool:
    return select_longform_route(language) == NO_SPACE_LONGFORM_ROUTE


def _model_max_target_positions(engine) -> int:
    model = getattr(engine, "model", None)
    config = getattr(model, "config", None)
    value = getattr(config, "max_target_positions", None)
    if value is None:
        raise RuntimeError("CrisperWhisper model max_target_positions is unavailable")
    maximum = int(value)
    if maximum != NO_SPACE_EXPECTED_MAX_TARGET_POSITIONS:
        raise RuntimeError(
            "CrisperWhisper model target capacity changed: "
            f"expected={NO_SPACE_EXPECTED_MAX_TARGET_POSITIONS}, actual={maximum}"
        )
    return maximum


def _decode_unicode_safe_suffix(engine, token_ids: list[int]) -> str | None:
    value = engine.tokenizer.decode(
        token_ids,
        clean_up_tokenization_spaces=False,
    ).strip()
    if not value or "\ufffd" in value:
        return None
    return value


def _minimum_unicode_safe_token_groups(tokenizer, token_ids, original_groups):
    groups = []
    texts = []
    for original_group in original_groups:
        pending = []
        for token_index in original_group:
            pending.append(token_index)
            decoded = tokenizer.decode(
                [token_ids[index] for index in pending],
                clean_up_tokenization_spaces=False,
            ).strip()
            if decoded and "\ufffd" not in decoded:
                groups.append(list(pending))
                texts.append(decoded)
                pending = []
        if pending:
            raise RuntimeError(
                "CrisperWhisper token group has an incomplete Unicode suffix"
            )
    return groups, texts


@contextmanager
def token_budgeted_continuation_prompts(model, language: str) -> Iterator[list[dict]]:
    from crisperwhisper.prompt import PromptBuilder

    engine = model._engine
    maximum = _model_max_target_positions(engine)
    prompt_limit = maximum - NO_SPACE_MAX_NEW_TOKENS
    if prompt_limit <= 0:
        raise RuntimeError(
            "CrisperWhisper no-space generation reserve leaves no prompt capacity"
        )
    original_verbatim = PromptBuilder.verbatim
    original_intended = PromptBuilder.intended
    diagnostics = []

    def bounded_prompt(original, mode, builder, hotwords=None, context=None):
        if normalized_language_code(builder.language) != normalized_language_code(language):
            return original(builder, hotwords=hotwords, context=context)
        context_value = "".join(str(context or "").split())
        context_ids = (
            list(builder._engine.encode_text(context_value)) if context_value else []
        )
        prompt = original(builder, hotwords=hotwords, context=context_value or None)
        retained_context = context_value or None
        retained_count = len(context_ids)
        trimmed = False
        if len(prompt) > prompt_limit:
            trimmed = True
            retained_context = None
            retained_count = 0
            for start in range(len(context_ids)):
                candidate = _decode_unicode_safe_suffix(
                    builder._engine,
                    context_ids[start:],
                )
                if candidate is None:
                    continue
                candidate_prompt = original(
                    builder,
                    hotwords=hotwords,
                    context=candidate,
                )
                if len(candidate_prompt) <= prompt_limit:
                    prompt = candidate_prompt
                    retained_context = candidate
                    retained_count = len(
                        builder._engine.encode_text(candidate)
                    )
                    break
            if retained_context is None:
                prompt = original(builder, hotwords=hotwords, context=None)
        if len(prompt) > prompt_limit:
            raise RuntimeError(
                "CrisperWhisper no-space prompt cannot preserve generation budget: "
                f"prompt={len(prompt)}, reserve={NO_SPACE_MAX_NEW_TOKENS}, "
                f"maximum={maximum}"
            )
        diagnostics.append(
            {
                "prompt_index": len(diagnostics),
                "mode": mode,
                "model_max_target_positions": maximum,
                "generation_token_reserve": NO_SPACE_MAX_NEW_TOKENS,
                "prompt_token_count": len(prompt),
                "original_context_token_count": len(context_ids),
                "retained_context_token_count": retained_count,
                "context_trimmed": trimmed,
                "context_omitted": bool(context_value and retained_context is None),
                "retained_context": retained_context,
                "capacity_validated": len(prompt) + NO_SPACE_MAX_NEW_TOKENS <= maximum,
            }
        )
        return prompt

    def verbatim(builder, hotwords=None, context=None):
        return bounded_prompt(
            original_verbatim,
            "verbatim",
            builder,
            hotwords=hotwords,
            context=context,
        )

    def intended(builder, hotwords=None, context=None):
        return bounded_prompt(
            original_intended,
            "intended",
            builder,
            hotwords=hotwords,
            context=context,
        )

    PromptBuilder.verbatim = verbatim
    PromptBuilder.intended = intended
    try:
        yield diagnostics
    finally:
        PromptBuilder.verbatim = original_verbatim
        PromptBuilder.intended = original_intended


@contextmanager
def complete_token_group_decoder(model) -> Iterator[None]:
    import crisperwhisper.word_timing as word_timing_module

    tokenizer = model._engine.tokenizer
    original = word_timing_module.group_tokens_into_words

    def decode_groups(token_ids, token_pieces):
        groups, _ = original(token_ids, token_pieces)
        return _minimum_unicode_safe_token_groups(tokenizer, token_ids, groups)

    word_timing_module.group_tokens_into_words = decode_groups
    try:
        yield
    finally:
        word_timing_module.group_tokens_into_words = original


def _content_token_count(engine, token_ids) -> int:
    return sum(int(token_id) not in engine.all_special_ids for token_id in token_ids)


def _frequency_ranked_consensus_candidate(candidates: list[dict]) -> dict | None:
    if len(candidates) < NO_SPACE_INTENDED_CONSENSUS_MINIMUM_CANDIDATES:
        return None
    ordered_counts = sorted(candidate["count"] for candidate in candidates)
    median_count = ordered_counts[len(ordered_counts) // 2]
    minimum_distance = min(
        abs(candidate["count"] - median_count) for candidate in candidates
    )
    return min(
        (
            candidate
            for candidate in candidates
            if abs(candidate["count"] - median_count) == minimum_distance
        ),
        key=lambda candidate: (
            candidate["mean_content_token_id"],
            candidate["seed"],
        ),
    )


def _text_content_token_count(engine, value: str) -> int:
    token_ids = engine.tokenizer.encode(str(value or ""), add_special_tokens=False)
    if hasattr(token_ids, "tolist"):
        token_ids = token_ids.tolist()
    return _content_token_count(engine, list(token_ids))


def _generated_loop(engine, token_ids) -> dict | None:
    from crisperwhisper.hallucination import find_token_loop
    from crisperwhisper.prompt import strip_prompt_artifacts

    ids = [int(token_id) for token_id in token_ids]
    token_loop = find_token_loop(ids, min_ngram=1, max_ngram=5, reps=5)
    if token_loop is not None:
        start, gram = token_loop
        return {
            "kind": "token_ngram",
            "start_token_index": int(start),
            "ngram_size": len(gram),
            "repeat_count": 5,
        }
    text = strip_prompt_artifacts(engine.decode_tokens(ids, skip_special=True))
    units = text.split()
    previous = ""
    run_length = 0
    run_start = 0
    for index, unit in enumerate(units):
        if unit and unit == previous:
            run_length += 1
        else:
            previous = unit
            run_length = 1 if unit else 0
            run_start = index
        if run_length == 5:
            return {
                "kind": "decoded_unit",
                "value": unit,
                "start_unit_index": run_start,
                "repeat_count": run_length,
            }
    return None


def _minimum_recovery_content_tokens(active_seconds: float, sibling_count: int) -> int:
    if active_seconds < NO_SPACE_MIN_SPEECH_SECONDS:
        return 1
    active_floor = ceil(
        NO_SPACE_MIN_CONTENT_TOKENS_PER_ACTIVE_SECOND * active_seconds
    )
    sibling_floor = ceil(
        NO_SPACE_MIN_CONTENT_TOKENS_PER_ACTIVE_SECOND * sibling_count
    )
    return max(1, active_floor, sibling_floor)


def _speech_active_timing_bounds(mel):
    import numpy as np

    if mel is None:
        return None, None
    values = mel[0] if getattr(mel, "ndim", 2) == 3 else mel
    if not getattr(values, "size", 0):
        return None, None
    energy = values.mean(axis=0).astype(np.float32)
    floor = float(np.percentile(energy, 10))
    peak = float(np.percentile(energy, 95))
    if peak - floor < 1e-3:
        return None, None
    threshold = floor + 0.2 * (peak - floor)
    active_indices = np.flatnonzero(energy > threshold)
    if not active_indices.size:
        return None, None
    return (
        float(active_indices[0]) * 0.01,
        float(active_indices[-1] + 1) * 0.01,
    )


def _timed_tail_coverage(engine, gen_ids, attention, mel):
    from crisperwhisper.word_timing import extract_word_timings

    _, active_end = _speech_active_timing_bounds(mel)
    words = extract_word_timings(
        engine,
        gen_ids,
        attention,
        mel,
        keep_unplaceable=False,
    )
    last_timed_end = float(words[-1].end) if words else None
    uncovered_tail = (
        max(0.0, float(active_end) - last_timed_end)
        if active_end is not None and last_timed_end is not None
        else None
    )
    return {
        "active_end_second": active_end,
        "last_timed_end_second": last_timed_end,
        "uncovered_active_tail_seconds": uncovered_tail,
        "timed_group_count": len(words),
        "covered": bool(
            uncovered_tail is not None
            and uncovered_tail <= NO_SPACE_MAX_UNCOVERED_ACTIVE_TAIL_SECONDS
        ),
    }


def _decode_with_language_aware_coverage_fallback(
    engine,
    features,
    mel,
    prompt_tokens,
    gen_ids,
    attention,
    *,
    max_length: int,
    want_attention: bool,
    enabled: bool,
    ref_prompt_tokens,
    temperatures,
    suppress_tokens,
    base_mode: str,
    language: str,
    maximum_uncovered_active_tail_seconds: float = (
        NO_SPACE_MAX_UNCOVERED_ACTIVE_TAIL_SECONDS
    ),
    plain_sampling_consensus_enabled: bool = False,
):
    from crisperwhisper.fallback import SAMPLES_PER_TEMP, SAMPLING_TOPK, speech_active_seconds
    active_seconds = float(speech_active_seconds(mel) or 0.0)
    base_count = _content_token_count(engine, gen_ids)
    base_loop = _generated_loop(engine, gen_ids)
    sibling_mode = "intended" if base_mode == "verbatim" else "verbatim"
    diagnostic = {
        "count_mode": NO_SPACE_COVERAGE_COUNT_MODE,
        "speech_active_seconds": active_seconds,
        "base_content_token_count": base_count,
        "sibling_content_token_count": 0,
        "selected_content_token_count": base_count,
        "base_mode": base_mode,
        "sibling_mode": sibling_mode,
        "selected_source": f"{base_mode}_greedy",
        "selected_temperature": None,
        "selected_seed": None,
        "triggered": False,
        "empty_dual_consensus": False,
        "sample_attempt_count": 0,
        "sample_loop_rejection_count": 0,
        "sample_error_count": 0,
        "base_loop": base_loop,
        "sibling_loop": None,
        "plain_content_token_count": 0,
        "plain_loop": None,
        "plain_prompt_token_count": 0,
        "plain_recovery_floor": 0,
        "plain_fallback_attempted": False,
        "loop_recovery_triggered": base_loop is not None,
        "loop_sample_rejection_count": 0,
        "maximum_uncovered_active_tail_seconds": (
            maximum_uncovered_active_tail_seconds
        ),
        "plain_sampling_consensus_enabled": plain_sampling_consensus_enabled,
        "plain_sampling_consensus_temperature": None,
        "plain_sampling_consensus_seed_count": 0,
        "plain_sampling_consensus_candidate_count": 0,
        "plain_sampling_consensus_cluster_size": 0,
        "plain_sampling_consensus_minimum_cluster_size": 0,
        "plain_sampling_consensus_cluster_seeds": [],
        "intended_sampling_consensus_enabled": False,
        "intended_sampling_consensus_candidate_count": 0,
        "intended_sampling_consensus_selected_seed": None,
        "intended_sampling_consensus_selected_mean_content_token_id": None,
        "base_timing_coverage": None,
        "sibling_timing_coverage": None,
        "plain_timing_coverage": None,
    }

    def timed_tail_coverage(token_ids, attention_value):
        value = dict(
            _timed_tail_coverage(
                engine,
                token_ids,
                attention_value,
                mel,
            )
        )
        uncovered_tail = value.get("uncovered_active_tail_seconds")
        value["maximum_uncovered_active_tail_seconds"] = (
            maximum_uncovered_active_tail_seconds
        )
        value["covered"] = bool(
            uncovered_tail is not None
            and float(uncovered_tail)
            <= float(maximum_uncovered_active_tail_seconds)
        )
        return value

    base_timing_covered = True
    if want_attention and base_count:
        base_timing = timed_tail_coverage(gen_ids, attention)
        diagnostic["base_timing_coverage"] = base_timing
        base_timing_covered = bool(base_timing["covered"])

    def recover_with_plain_prompt():
        if diagnostic["plain_fallback_attempted"]:
            return None
        plain_prompt_tokens = list(engine.get_decoder_prefix(language))
        diagnostic["plain_prompt_token_count"] = len(plain_prompt_tokens)
        diagnostic["plain_fallback_attempted"] = True
        plain_ids = engine.generate(
            features,
            [plain_prompt_tokens],
            max_length=max_length,
            suppress_tokens=suppress_tokens,
        )[0]
        plain_count = _content_token_count(engine, plain_ids)
        plain_loop = _generated_loop(engine, plain_ids)
        plain_floor = max(
            NO_SPACE_MIN_SIBLING_CONTENT_TOKENS,
            ceil(NO_SPACE_MIN_CONTENT_TOKENS_PER_ACTIVE_SECOND * active_seconds),
        )
        diagnostic["plain_content_token_count"] = plain_count
        diagnostic["plain_loop"] = plain_loop
        diagnostic["plain_recovery_floor"] = plain_floor
        if (
            plain_loop is None
            and plain_count >= plain_floor
            and not plain_sampling_consensus_enabled
        ):
            recovered_attention = attention
            plain_timing_covered = True
            if want_attention:
                recovered_attention = engine.cross_attention_for_tokens(
                    features,
                    plain_prompt_tokens,
                    plain_ids,
                )
                plain_timing = timed_tail_coverage(plain_ids, recovered_attention)
                diagnostic["plain_timing_coverage"] = plain_timing
                plain_timing_covered = bool(plain_timing["covered"])
            if plain_timing_covered:
                diagnostic["selected_content_token_count"] = plain_count
                diagnostic["selected_source"] = "plain_transcribe_sibling_fallback"
                diagnostic["triggered"] = True
                return plain_ids, recovered_attention
        if not plain_sampling_consensus_enabled:
            return None

        candidates = []
        for consensus_seed in range(NO_SPACE_PLAIN_CONSENSUS_SEED_COUNT):
            sampled_ids = engine.generate_sampled(
                features,
                plain_prompt_tokens,
                max_length=max_length,
                temperature=NO_SPACE_PLAIN_CONSENSUS_TEMPERATURE,
                topk=0,
                seed=consensus_seed,
                suppress_tokens=suppress_tokens,
            )
            sampled_loop = _generated_loop(engine, sampled_ids)
            sampled_count = _content_token_count(engine, sampled_ids)
            if sampled_loop is not None or sampled_count < plain_floor:
                continue
            sampled_text = engine.decode_tokens(sampled_ids, skip_special=True)
            normalized_text = "".join(str(sampled_text or "").split())
            if not normalized_text or "\ufffd" in normalized_text:
                continue
            candidates.append(
                {
                    "seed": consensus_seed,
                    "ids": sampled_ids,
                    "count": sampled_count,
                    "normalized_text": normalized_text,
                }
            )

        minimum_cluster_size = max(
            3,
            ceil(
                NO_SPACE_PLAIN_CONSENSUS_SEED_COUNT
                * NO_SPACE_PLAIN_CONSENSUS_MINIMUM_FRACTION
            ),
        )
        diagnostic["plain_sampling_consensus_temperature"] = (
            NO_SPACE_PLAIN_CONSENSUS_TEMPERATURE
        )
        diagnostic["plain_sampling_consensus_seed_count"] = (
            NO_SPACE_PLAIN_CONSENSUS_SEED_COUNT
        )
        diagnostic["plain_sampling_consensus_candidate_count"] = len(candidates)
        diagnostic["plain_sampling_consensus_minimum_cluster_size"] = (
            minimum_cluster_size
        )

        def consensus_match(left, right):
            matcher = SequenceMatcher(
                None,
                left["normalized_text"],
                right["normalized_text"],
            )
            matching_count = sum(
                block.size for block in matcher.get_matching_blocks()
            )
            shorter_count = min(
                len(left["normalized_text"]),
                len(right["normalized_text"]),
            )
            containment = (
                matching_count / shorter_count if shorter_count else 0.0
            )
            return matcher.ratio() >= 0.82 or containment >= 0.85

        selected_cluster = []
        for anchor in candidates:
            cluster = [
                candidate
                for candidate in candidates
                if consensus_match(anchor, candidate)
            ]
            if len(cluster) < minimum_cluster_size:
                continue
            cluster_score = (
                len(cluster),
                sum(candidate["count"] for candidate in cluster) / len(cluster),
            )
            selected_score = (
                len(selected_cluster),
                sum(candidate["count"] for candidate in selected_cluster)
                / len(selected_cluster)
                if selected_cluster
                else 0.0,
            )
            if cluster_score > selected_score:
                selected_cluster = cluster
        diagnostic["plain_sampling_consensus_cluster_size"] = len(
            selected_cluster
        )
        diagnostic["plain_sampling_consensus_cluster_seeds"] = [
            candidate["seed"] for candidate in selected_cluster
        ]
        if not selected_cluster:
            return None

        ordered_counts = sorted(candidate["count"] for candidate in selected_cluster)
        median_count = ordered_counts[len(ordered_counts) // 2]
        for candidate in sorted(
            selected_cluster,
            key=lambda value: (
                abs(value["count"] - median_count),
                value["seed"],
            ),
        ):
            recovered_attention = attention
            consensus_timing_covered = True
            if want_attention:
                recovered_attention = engine.cross_attention_for_tokens(
                    features,
                    plain_prompt_tokens,
                    candidate["ids"],
                )
                consensus_timing = timed_tail_coverage(
                    candidate["ids"],
                    recovered_attention,
                )
                consensus_timing_covered = bool(consensus_timing["covered"])
                if consensus_timing_covered:
                    diagnostic["plain_timing_coverage"] = consensus_timing
            if not consensus_timing_covered:
                continue
            diagnostic["selected_content_token_count"] = candidate["count"]
            diagnostic["selected_source"] = "plain_deterministic_sampling_consensus"
            diagnostic["selected_temperature"] = (
                NO_SPACE_PLAIN_CONSENSUS_TEMPERATURE
            )
            diagnostic["selected_seed"] = candidate["seed"]
            diagnostic["triggered"] = True
            return candidate["ids"], recovered_attention
        return None

    def recover_sparse_intended_sibling(
        sibling_ids,
        sibling_count,
        sibling_attention,
        sibling_floor,
    ):
        if not plain_sampling_consensus_enabled or active_seconds <= 0.0:
            return None
        sibling_density = sibling_count / active_seconds
        if sibling_density > NO_SPACE_INTENDED_CONSENSUS_MAXIMUM_TOKEN_DENSITY:
            return None
        sibling_text = engine.decode_tokens(sibling_ids, skip_special=True)
        normalized_sibling = "".join(sibling_text.split())
        candidates = []
        diagnostic["intended_sampling_consensus_enabled"] = True
        sampled_batch = None
        if hasattr(engine, "generate_sampled_batch"):
            sampled_batch = engine.generate_sampled_batch(
                features,
                list(ref_prompt_tokens),
                seeds=NO_SPACE_INTENDED_CONSENSUS_SEEDS,
                max_length=max_length,
                temperature=NO_SPACE_INTENDED_CONSENSUS_TEMPERATURE,
                topk=0,
                suppress_tokens=suppress_tokens,
            )
        for consensus_seed in NO_SPACE_INTENDED_CONSENSUS_SEEDS:
            if sampled_batch is None:
                sampled_ids = engine.generate_sampled(
                    features,
                    list(ref_prompt_tokens),
                    max_length=max_length,
                    temperature=NO_SPACE_INTENDED_CONSENSUS_TEMPERATURE,
                    topk=0,
                    seed=consensus_seed,
                    suppress_tokens=suppress_tokens,
                )
            else:
                sampled_ids = list(sampled_batch[consensus_seed])
            sampled_count = _content_token_count(engine, sampled_ids)
            if _generated_loop(engine, sampled_ids) is not None:
                continue
            sampled_text = engine.decode_tokens(sampled_ids, skip_special=True)
            normalized_sampled = "".join(sampled_text.split())
            matcher = SequenceMatcher(
                None,
                normalized_sibling,
                normalized_sampled,
            )
            matching_count = sum(
                block.size for block in matcher.get_matching_blocks()
            )
            shorter_count = min(
                len(normalized_sibling),
                len(normalized_sampled),
            )
            containment = matching_count / shorter_count if shorter_count else 0.0
            if (
                sampled_count < sibling_floor
                or (matcher.ratio() < 0.82 and containment < 0.85)
            ):
                continue
            content_ids = [
                int(token_id)
                for token_id in sampled_ids
                if int(token_id) not in engine.all_special_ids
            ]
            candidates.append(
                {
                    "seed": consensus_seed,
                    "ids": sampled_ids,
                    "count": sampled_count,
                    "mean_content_token_id": sum(content_ids) / len(content_ids),
                }
            )
        diagnostic["intended_sampling_consensus_candidate_count"] = len(candidates)
        selected = _frequency_ranked_consensus_candidate(candidates)
        if selected is None:
            return None
        selected_attention = sibling_attention
        if want_attention:
            selected_attention = engine.cross_attention_for_tokens(
                features,
                ref_prompt_tokens,
                selected["ids"],
            )
            selected_timing = timed_tail_coverage(
                selected["ids"],
                selected_attention,
            )
            if not selected_timing["covered"]:
                return None
            diagnostic["sibling_timing_coverage"] = selected_timing
        diagnostic["intended_sampling_consensus_selected_seed"] = selected["seed"]
        diagnostic["intended_sampling_consensus_selected_mean_content_token_id"] = (
            selected["mean_content_token_id"]
        )
        return selected["ids"], selected_attention, selected["count"]

    if not enabled or not hasattr(engine, "generate_sampled"):
        diagnostic["selected_source"] = f"{base_mode}_fallback_unavailable"
        return gen_ids, attention, diagnostic
    if base_loop is None and base_count and base_timing_covered and (
        active_seconds < NO_SPACE_MIN_SPEECH_SECONDS
        or base_count >= NO_SPACE_MIN_CONTENT_TOKENS_PER_ACTIVE_SECOND * active_seconds
    ):
        return gen_ids, attention, diagnostic

    sibling_ids = engine.generate(
        features,
        [list(ref_prompt_tokens)],
        max_length=max_length,
        suppress_tokens=suppress_tokens,
    )[0]
    sibling_count = _content_token_count(engine, sibling_ids)
    sibling_loop = _generated_loop(engine, sibling_ids)
    diagnostic["sibling_content_token_count"] = sibling_count
    diagnostic["sibling_loop"] = sibling_loop
    sibling_attention = None
    sibling_timing_covered = False
    if want_attention and sibling_count and sibling_loop is None:
        sibling_attention = engine.cross_attention_for_tokens(
            features,
            ref_prompt_tokens,
            sibling_ids,
        )
        sibling_timing = timed_tail_coverage(sibling_ids, sibling_attention)
        diagnostic["sibling_timing_coverage"] = sibling_timing
        sibling_timing_covered = bool(sibling_timing["covered"])
    if base_count == 0 and sibling_count == 0 and base_loop is None:
        diagnostic["empty_dual_consensus"] = True
        plain_recovery = recover_with_plain_prompt()
        if plain_recovery is not None:
            plain_ids, recovered_attention = plain_recovery
            return plain_ids, recovered_attention, diagnostic
        diagnostic["selected_source"] = "dual_mode_empty_consensus"
        return gen_ids, attention, diagnostic
    if base_loop is not None and sibling_loop is not None:
        plain_recovery = recover_with_plain_prompt()
        if plain_recovery is not None:
            plain_ids, recovered_attention = plain_recovery
            return plain_ids, recovered_attention, diagnostic
    if not base_timing_covered:
        sibling_floor = _minimum_recovery_content_tokens(
            active_seconds,
            sibling_count,
        )
        if (
            sibling_loop is None
            and sibling_count >= sibling_floor
            and sibling_timing_covered
        ):
            adjudicated = recover_sparse_intended_sibling(
                sibling_ids,
                sibling_count,
                sibling_attention,
                sibling_floor,
            )
            if adjudicated is not None:
                sibling_ids, sibling_attention, sibling_count = adjudicated
                diagnostic["selected_source"] = (
                    f"{sibling_mode}_timed_sampling_consensus"
                )
            else:
                diagnostic["selected_source"] = (
                    f"{sibling_mode}_timed_sibling_fallback"
                )
            diagnostic["selected_content_token_count"] = sibling_count
            diagnostic["triggered"] = True
            return sibling_ids, sibling_attention, diagnostic
        plain_recovery = recover_with_plain_prompt()
        if plain_recovery is not None:
            plain_ids, recovered_attention = plain_recovery
            return plain_ids, recovered_attention, diagnostic
        raise CrisperWhisperNoSpaceDiagnosticError(
            "CrisperWhisper no-space window leaves an uncovered active tail",
            {
                **diagnostic,
                "failure_phase": "no_space_coverage_fallback",
                "failure_type": "timed_tail_undercoverage",
            },
        )
    if base_loop is None and base_timing_covered and (
        sibling_count < NO_SPACE_MIN_SIBLING_CONTENT_TOKENS
        or base_count >= NO_SPACE_MIN_CONTENT_TOKENS_PER_ACTIVE_SECOND * sibling_count
    ):
        return gen_ids, attention, diagnostic

    best_ids = gen_ids
    best_count = base_count
    best_prompt = prompt_tokens
    seed = 0
    recovered = False
    for temperature in temperatures:
        if recovered:
            break
        for _ in range(SAMPLES_PER_TEMP):
            current_seed = seed
            seed += 1
            diagnostic["sample_attempt_count"] += 1
            try:
                sampled = engine.generate_sampled(
                    features,
                    prompt_tokens,
                    max_length=max_length,
                    temperature=float(temperature),
                    topk=SAMPLING_TOPK,
                    seed=current_seed,
                    suppress_tokens=suppress_tokens,
                )
            except Exception:
                diagnostic["sample_error_count"] += 1
                continue
            sampled_loop = _generated_loop(engine, sampled)
            if sampled_loop is not None:
                diagnostic["sample_loop_rejection_count"] += 1
                if base_loop is not None:
                    diagnostic["loop_sample_rejection_count"] += 1
                continue
            sampled_count = _content_token_count(engine, sampled)
            if sampled_count > best_count:
                best_ids = sampled
                best_count = sampled_count
                diagnostic["selected_temperature"] = float(temperature)
                diagnostic["selected_seed"] = current_seed
                diagnostic["selected_source"] = f"{base_mode}_temperature_fallback"
            recovery_floor = _minimum_recovery_content_tokens(
                active_seconds,
                sibling_count,
            )
            if sampled_count >= recovery_floor:
                recovered = True
                break

    if not recovered:
        if sibling_loop is not None:
            plain_recovery = recover_with_plain_prompt()
            if plain_recovery is not None:
                plain_ids, recovered_attention = plain_recovery
                return plain_ids, recovered_attention, diagnostic
            if base_loop is not None:
                raise CrisperWhisperNoSpaceDiagnosticError(
                    "CrisperWhisper no-space window loop recovery failed: "
                    f"base={base_loop}, sibling={sibling_loop}",
                    {
                        **diagnostic,
                        "failure_phase": "no_space_coverage_fallback",
                        "failure_type": "dual_mode_token_loop",
                    },
                )
            raise CrisperWhisperNoSpaceDiagnosticError(
                "CrisperWhisper no-space intended sibling contains a token loop: "
                f"{sibling_loop}",
                {
                    **diagnostic,
                    "failure_phase": "no_space_coverage_fallback",
                    "failure_type": "sibling_token_loop",
                },
            )
        if base_loop is not None and sibling_count < _minimum_recovery_content_tokens(
            active_seconds,
            sibling_count,
        ):
            plain_recovery = recover_with_plain_prompt()
            if plain_recovery is not None:
                plain_ids, recovered_attention = plain_recovery
                return plain_ids, recovered_attention, diagnostic
            raise CrisperWhisperNoSpaceDiagnosticError(
                "CrisperWhisper no-space window loop recovery has insufficient safe content: "
                f"active_seconds={active_seconds:.3f}, sibling_content_tokens={sibling_count}",
                {
                    **diagnostic,
                    "failure_phase": "no_space_coverage_fallback",
                    "failure_type": "insufficient_loop_recovery_content",
                },
            )
        best_ids = sibling_ids
        best_count = sibling_count
        best_prompt = ref_prompt_tokens
        diagnostic["selected_source"] = f"{sibling_mode}_sibling_fallback"
        diagnostic["selected_temperature"] = None
        diagnostic["selected_seed"] = None
    diagnostic["selected_content_token_count"] = best_count
    diagnostic["triggered"] = True
    recovered_attention = attention
    if want_attention:
        if best_ids is sibling_ids and sibling_attention is not None:
            recovered_attention = sibling_attention
        else:
            recovered_attention = engine.cross_attention_for_tokens(
                features,
                best_prompt,
                best_ids,
            )
    return best_ids, recovered_attention, diagnostic


def _continuation_window_count(
    duration_seconds: float,
    chunk_duration_seconds: float,
    stride_seconds: float,
) -> int:
    if duration_seconds <= chunk_duration_seconds:
        return 1
    return 1 + ceil(
        (duration_seconds - chunk_duration_seconds) / stride_seconds
    )


@contextmanager
def language_aware_coverage_fallback(
    language: str,
    base_mode: str,
    *,
    compact_duration_seconds: float | None = None,
    chunk_duration_seconds: float = NO_SPACE_CHUNK_DURATION_SECONDS,
    stride_seconds: float = NO_SPACE_STRIDE_SECONDS,
    overlap_tail_coverage_enabled: bool = False,
    plain_sampling_consensus_enabled: bool = False,
) -> Iterator[list[dict]]:
    import crisperwhisper.longform.continuation as continuation_module
    from crisperwhisper.fallback import FALLBACK_TEMPERATURES

    original = continuation_module.decode_with_coverage_fallback
    diagnostics = []
    total_window_count = (
        _continuation_window_count(
            compact_duration_seconds,
            chunk_duration_seconds,
            stride_seconds,
        )
        if compact_duration_seconds is not None
        else None
    )

    def decode_with_fallback(
        engine,
        features,
        mel,
        prompt_tokens,
        gen_ids,
        attention,
        *,
        max_length,
        want_attention,
        enabled=True,
        ref_word_count=None,
        ref_prompt_tokens=None,
        temperatures=FALLBACK_TEMPERATURES,
        suppress_tokens=None,
    ):
        if (
            normalized_language_code(language) not in NO_SPACE_LANGUAGE_CODES
            or ref_word_count is not None
            or ref_prompt_tokens is None
        ):
            return original(
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
        window_index = len(diagnostics)
        is_final_window = bool(
            total_window_count is not None
            and window_index >= total_window_count - 1
        )
        maximum_uncovered_tail_seconds = (
            max(
                NO_SPACE_MAX_UNCOVERED_ACTIVE_TAIL_SECONDS,
                chunk_duration_seconds - stride_seconds,
            )
            if overlap_tail_coverage_enabled and not is_final_window
            else NO_SPACE_MAX_UNCOVERED_ACTIVE_TAIL_SECONDS
        )
        try:
            recovered_ids, recovered_attention, diagnostic = (
                _decode_with_language_aware_coverage_fallback(
                    engine,
                    features,
                    mel,
                    prompt_tokens,
                    gen_ids,
                    attention,
                    max_length=max_length,
                    want_attention=want_attention,
                    enabled=enabled,
                    ref_prompt_tokens=ref_prompt_tokens,
                    temperatures=temperatures,
                    suppress_tokens=suppress_tokens,
                    base_mode=base_mode,
                    language=language,
                    maximum_uncovered_active_tail_seconds=(
                        maximum_uncovered_tail_seconds
                    ),
                    plain_sampling_consensus_enabled=(
                        plain_sampling_consensus_enabled
                    ),
                )
            )
        except CrisperWhisperNoSpaceDiagnosticError as error:
            error.diagnostic.update(
                {
                    "window_index": window_index,
                    "window_count": total_window_count,
                    "is_final_window": is_final_window,
                    "local_compact_second": window_index * stride_seconds,
                }
            )
            diagnostics.append(dict(error.diagnostic))
            raise
        diagnostic["window_index"] = window_index
        diagnostic["window_count"] = total_window_count
        diagnostic["is_final_window"] = is_final_window
        diagnostics.append(diagnostic)
        return recovered_ids, recovered_attention

    continuation_module.decode_with_coverage_fallback = decode_with_fallback
    try:
        yield diagnostics
    finally:
        continuation_module.decode_with_coverage_fallback = original


def _transcribe_short_no_space(model, compact_signal, language: str, profile: dict, sample_rate: int):
    verbatim = model.transcribe(
        compact_signal,
        sr=sample_rate,
        language=language,
        mode="verbatim",
        temperature_fallback=bool(profile["temperature_fallback"]),
        max_new_tokens=NO_SPACE_MAX_NEW_TOKENS,
        speculative_decoding=False,
        hallucination_mitigation=bool(profile["hallucination_mitigation"]),
        word_timestamps=True,
    )
    verbatim_text = str(verbatim.text or "").strip()
    base_count = _text_content_token_count(model._engine, verbatim_text)
    selected = verbatim
    selected_source = "verbatim_greedy"
    sibling_count = 0
    if base_count == 0:
        intended = model.transcribe(
            compact_signal,
            sr=sample_rate,
            language=language,
            mode="intended",
            temperature_fallback=bool(profile["temperature_fallback"]),
            max_new_tokens=NO_SPACE_MAX_NEW_TOKENS,
            speculative_decoding=False,
            hallucination_mitigation=bool(profile["hallucination_mitigation"]),
            word_timestamps=True,
        )
        intended_text = str(intended.text or "").strip()
        sibling_count = _text_content_token_count(model._engine, intended_text)
        if sibling_count >= NO_SPACE_MIN_SIBLING_CONTENT_TOKENS:
            selected = intended
            selected_source = "intended_sibling_fallback"
    diagnostic = {
        "window_index": 0,
        "count_mode": NO_SPACE_COVERAGE_COUNT_MODE,
        "speech_active_seconds": None,
        "base_content_token_count": base_count,
        "sibling_content_token_count": sibling_count,
        "selected_content_token_count": sibling_count
        if selected_source == "intended_sibling_fallback"
        else base_count,
        "selected_source": selected_source,
        "selected_temperature": None,
        "selected_seed": None,
        "triggered": selected_source == "intended_sibling_fallback",
        "empty_dual_consensus": base_count == 0 and sibling_count == 0,
        "sample_attempt_count": 0,
        "sample_loop_rejection_count": 0,
        "sample_error_count": 0,
        "base_loop": None,
        "sibling_loop": None,
        "loop_recovery_triggered": False,
        "loop_sample_rejection_count": 0,
    }
    return selected, [diagnostic]


def _recover_unrecaptured_overlap_suffixes(
    transcription,
    window_word_timings: dict[int, list],
    stride_seconds: float,
    continuation_module,
) -> list[dict]:
    recovery_audit = []
    recovered_words_by_window = {}
    ordered_window_indexes = sorted(window_word_timings)
    for position, window_index in enumerate(ordered_window_indexes[:-1]):
        next_window_index = ordered_window_indexes[position + 1]
        if next_window_index != window_index + 1:
            continue
        local_words = window_word_timings[window_index]
        keep_index = continuation_module._overlap_drop_index(
            local_words,
            stride_sec=stride_seconds,
            drop_words=2,
            timestamp_aware_drop=True,
            is_last=False,
        )
        next_offset = next_window_index * stride_seconds
        next_words = [
            (
                value,
                float(value.start) + next_offset,
                float(value.end) + next_offset,
            )
            for value in window_word_timings[next_window_index]
            if value.start is not None and value.end is not None
        ]
        current_offset = window_index * stride_seconds
        for value in local_words[keep_index:]:
            if value.start is None or value.end is None:
                continue
            start = float(value.start) + current_offset
            end = float(value.end) + current_offset
            midpoint = (start + end) / 2.0
            recaptured = any(
                str(value.word) == str(next_value.word)
                and abs(midpoint - ((next_start + next_end) / 2.0))
                <= NO_SPACE_OVERLAP_RECAPTURE_MIDPOINT_TOLERANCE_SECONDS
                for next_value, next_start, next_end in next_words
            )
            recovery_audit.append(
                {
                    "window_index": window_index,
                    "word": value.word,
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "recaptured_by_next_window": recaptured,
                }
            )
            if recaptured:
                continue
            recovered_words_by_window.setdefault(window_index, []).append(
                type(value)(
                    word=value.word,
                    start=round(start, 3),
                    end=round(end, 3),
                )
            )
    merged_words = sorted(
        list(transcription.words or []),
        key=lambda value: (float(value.start), float(value.end)),
    )
    for window_index in sorted(recovered_words_by_window):
        recovered_group = recovered_words_by_window[window_index]
        insertion_start = float(recovered_group[0].start)
        insertion_index = next(
            (
                index
                for index, existing_word in enumerate(merged_words)
                if float(existing_word.start) >= insertion_start
            ),
            len(merged_words),
        )
        merged_words[insertion_index:insertion_index] = recovered_group
    transcription.words = merged_words
    continuation_module.monotonize_words(transcription.words)
    transcription.text = " ".join(value.word for value in transcription.words)
    return recovery_audit


def _transcribe_long_no_space_once(
    model,
    compact_signal,
    language: str,
    profile: dict,
    sample_rate: int,
    mode: str,
    *,
    chunk_duration_seconds: float,
    stride_seconds: float,
    overlap_tail_coverage_enabled: bool,
    plain_sampling_consensus_enabled: bool,
):
    import crisperwhisper.longform.continuation as continuation_module
    import crisperwhisper.word_timing as word_timing_module

    compact_duration_seconds = len(compact_signal) / sample_rate
    original_extract_word_timings = word_timing_module.extract_word_timings
    window_word_timings = {}
    with token_budgeted_continuation_prompts(model, language) as prompt_budgets:
        with language_aware_coverage_fallback(
            language,
            mode,
            compact_duration_seconds=compact_duration_seconds,
            chunk_duration_seconds=chunk_duration_seconds,
            stride_seconds=stride_seconds,
            overlap_tail_coverage_enabled=overlap_tail_coverage_enabled,
            plain_sampling_consensus_enabled=plain_sampling_consensus_enabled,
        ) as coverage_fallbacks:
            def record_window_word_timings(*args, **kwargs):
                values = original_extract_word_timings(*args, **kwargs)
                if kwargs.get("keep_unplaceable"):
                    window_index = max(len(coverage_fallbacks) - 1, 0)
                    window_word_timings[window_index] = list(values)
                return values

            word_timing_module.extract_word_timings = record_window_word_timings
            try:
                transcription = model.transcribe(
                    compact_signal,
                    sr=sample_rate,
                    language=language,
                    mode=mode,
                    longform_strategy=NO_SPACE_LONGFORM_ROUTE,
                    chunk_duration=chunk_duration_seconds,
                    stride=stride_seconds,
                    context_words=NO_SPACE_CONTEXT_GROUPS,
                    temperature_fallback=bool(profile["temperature_fallback"]),
                    max_new_tokens=NO_SPACE_MAX_NEW_TOKENS,
                    speculative_decoding=False,
                    hallucination_mitigation=bool(profile["hallucination_mitigation"]),
                    word_timestamps=True,
                )
            finally:
                word_timing_module.extract_word_timings = original_extract_word_timings
    recovery_audit = _recover_unrecaptured_overlap_suffixes(
        transcription,
        window_word_timings,
        stride_seconds,
        continuation_module,
    )
    return (
        transcription,
        list(coverage_fallbacks),
        list(prompt_budgets),
        recovery_audit,
    )


def _transcription_has_empty_continuation_chunk(transcription) -> bool:
    chunks = list(transcription.chunks or [])
    return bool(
        not str(transcription.text or "").strip()
        or any(not str(_chunk_value(chunk, "text") or "").strip() for chunk in chunks)
    )


def _transcribe_long_no_space(
    model,
    compact_signal,
    language: str,
    profile: dict,
    sample_rate: int,
    mode: str,
):
    initial_failure = None
    try:
        transcription, coverage_fallbacks, prompt_budgets, recovery_audit = (
            _transcribe_long_no_space_once(
                model,
                compact_signal,
                language,
                profile,
                sample_rate,
                mode,
                chunk_duration_seconds=NO_SPACE_CHUNK_DURATION_SECONDS,
                stride_seconds=NO_SPACE_STRIDE_SECONDS,
                overlap_tail_coverage_enabled=False,
                plain_sampling_consensus_enabled=False,
            )
        )
    except CrisperWhisperNoSpaceDiagnosticError as error:
        if error.diagnostic.get("failure_type") != "timed_tail_undercoverage":
            raise
        initial_failure = dict(error.diagnostic)
    else:
        if not _transcription_has_empty_continuation_chunk(transcription):
            return (
                transcription,
                coverage_fallbacks,
                prompt_budgets,
                {
                    "adaptive_window_retry_triggered": False,
                    "chunk_duration_seconds": NO_SPACE_CHUNK_DURATION_SECONDS,
                    "stride_seconds": NO_SPACE_STRIDE_SECONDS,
                    "overlap_seconds": (
                        NO_SPACE_CHUNK_DURATION_SECONDS - NO_SPACE_STRIDE_SECONDS
                    ),
                    "overlap_suffix_recovery_policy": (
                        NO_SPACE_OVERLAP_SUFFIX_RECOVERY_POLICY
                    ),
                    "overlap_suffix_recovery_count": sum(
                        not value["recaptured_by_next_window"]
                        for value in recovery_audit
                    ),
                    "overlap_suffix_recovery": recovery_audit,
                    "initial_failure": None,
                },
            )
        initial_failure = {
            "failure_phase": "no_space_continuation",
            "failure_type": "empty_continuation_chunk",
            "detected_language": normalized_language_code(language),
        }

    try:
        transcription, coverage_fallbacks, prompt_budgets, recovery_audit = (
            _transcribe_long_no_space_once(
                model,
                compact_signal,
                language,
                profile,
                sample_rate,
                mode,
                chunk_duration_seconds=(
                    NO_SPACE_ADAPTIVE_RETRY_CHUNK_DURATION_SECONDS
                ),
                stride_seconds=NO_SPACE_ADAPTIVE_RETRY_STRIDE_SECONDS,
                overlap_tail_coverage_enabled=True,
                plain_sampling_consensus_enabled=True,
            )
        )
    except CrisperWhisperNoSpaceDiagnosticError as error:
        error.diagnostic["adaptive_window_retry"] = {
            "triggered": True,
            "policy": NO_SPACE_ADAPTIVE_RETRY_POLICY,
            "chunk_duration_seconds": (
                NO_SPACE_ADAPTIVE_RETRY_CHUNK_DURATION_SECONDS
            ),
            "stride_seconds": NO_SPACE_ADAPTIVE_RETRY_STRIDE_SECONDS,
            "overlap_seconds": NO_SPACE_ADAPTIVE_RETRY_OVERLAP_SECONDS,
            "initial_failure": initial_failure,
        }
        raise
    for diagnostic in coverage_fallbacks:
        diagnostic["adaptive_window_retry"] = {
            "triggered": True,
            "policy": NO_SPACE_ADAPTIVE_RETRY_POLICY,
            "chunk_duration_seconds": (
                NO_SPACE_ADAPTIVE_RETRY_CHUNK_DURATION_SECONDS
            ),
            "stride_seconds": NO_SPACE_ADAPTIVE_RETRY_STRIDE_SECONDS,
            "overlap_seconds": NO_SPACE_ADAPTIVE_RETRY_OVERLAP_SECONDS,
        }
    return (
        transcription,
        coverage_fallbacks,
        prompt_budgets,
        {
            "adaptive_window_retry_triggered": True,
            "policy": NO_SPACE_ADAPTIVE_RETRY_POLICY,
            "chunk_duration_seconds": (
                NO_SPACE_ADAPTIVE_RETRY_CHUNK_DURATION_SECONDS
            ),
            "stride_seconds": NO_SPACE_ADAPTIVE_RETRY_STRIDE_SECONDS,
            "overlap_seconds": NO_SPACE_ADAPTIVE_RETRY_OVERLAP_SECONDS,
            "plain_consensus_temperature": NO_SPACE_PLAIN_CONSENSUS_TEMPERATURE,
            "plain_consensus_seed_count": NO_SPACE_PLAIN_CONSENSUS_SEED_COUNT,
            "plain_consensus_minimum_fraction": (
                NO_SPACE_PLAIN_CONSENSUS_MINIMUM_FRACTION
            ),
            "overlap_suffix_recovery_policy": (
                NO_SPACE_OVERLAP_SUFFIX_RECOVERY_POLICY
            ),
            "overlap_suffix_recovery_count": sum(
                not value["recaptured_by_next_window"]
                for value in recovery_audit
            ),
            "overlap_suffix_recovery": recovery_audit,
            "initial_failure": initial_failure,
        },
    )


def _word_value(word, key: str):
    if isinstance(word, dict):
        return word.get(key)
    return getattr(word, key, None)


def _chunk_value(chunk, key: str):
    if isinstance(chunk, dict):
        return chunk.get(key)
    return getattr(chunk, key, None)


def _compact_timed_entries(transcription) -> list[dict]:
    compact_words = []
    for word in list(transcription.words or []):
        value = str(_word_value(word, "word") or "").strip()
        start = _word_value(word, "start")
        end = _word_value(word, "end")
        if not value or start is None or end is None:
            continue
        compact_words.append(
            {
                "word": value,
                "compact_start": float(start),
                "compact_end": float(end),
            }
        )
    return compact_words


def _exact_repetition_runs(words: list[dict]) -> list[dict]:
    findings = []
    index = 0
    while index < len(words):
        value = str(words[index].get("word") or "").strip()
        if not value:
            index += 1
            continue
        cursor = index + 1
        while cursor < len(words) and str(
            words[cursor].get("word") or ""
        ).strip() == value:
            cursor += 1
        repeat_count = cursor - index
        if repeat_count >= 5:
            findings.append(
                {
                    "word": value,
                    "phrase": [value],
                    "start_index": index,
                    "repeat_count": repeat_count,
                    "occurrence_start_seconds": [
                        word.get("compact_start") for word in words[index:cursor]
                    ],
                }
            )
        index = cursor
    _, rejected = classify_timed_repetitions(findings)
    return rejected


def _adjacent_chunk_overlap(previous: str, current: str) -> int:
    maximum = min(len(previous), len(current))
    for length in range(maximum, 0, -1):
        if previous[-length:] == current[:length]:
            return length
    return 0


def transcribe_no_space_language(model, compact_signal, language: str, profile: dict, sample_rate: int):
    if not uses_no_space_continuation(language):
        raise RuntimeError(f"No-space continuation route does not accept language: {language!r}")
    model_max_target_positions = _model_max_target_positions(model._engine)
    prompt_budgets = []
    rejected_continuation_attempts = []
    selected_continuation_mode = "verbatim"
    longform_contract = {
        "adaptive_window_retry_triggered": False,
        "chunk_duration_seconds": NO_SPACE_CHUNK_DURATION_SECONDS,
        "stride_seconds": NO_SPACE_STRIDE_SECONDS,
        "overlap_seconds": (
            NO_SPACE_CHUNK_DURATION_SECONDS - NO_SPACE_STRIDE_SECONDS
        ),
        "initial_failure": None,
    }
    short_audio = len(compact_signal) / sample_rate <= NO_SPACE_SHORT_THRESHOLD_SECONDS
    with complete_token_group_decoder(model):
        if short_audio:
            transcription, coverage_fallbacks = _transcribe_short_no_space(
                model,
                compact_signal,
                language,
                profile,
                sample_rate,
            )
            if coverage_fallbacks[0]["selected_source"] == "intended_sibling_fallback":
                selected_continuation_mode = "intended_short_fallback"
        else:
            (
                transcription,
                coverage_fallbacks,
                prompt_budgets,
                longform_contract,
            ) = _transcribe_long_no_space(
                model,
                compact_signal,
                language,
                profile,
                sample_rate,
                "verbatim",
            )

    transcript_text = "".join(str(transcription.text or "").split())
    if not transcript_text:
        raise CrisperWhisperNoSpaceDiagnosticError(
            "CrisperWhisper no-space continuation returned empty text",
            {
                "failure_phase": "no_space_continuation",
                "failure_type": "empty_transcript",
                "detected_language": normalized_language_code(language),
                "selected_route": NO_SPACE_LONGFORM_ROUTE,
                "local_compact_second": 0.0,
                "coverage_fallbacks": coverage_fallbacks,
                "prompt_budgets": prompt_budgets,
            },
        )
    if "\ufffd" in transcript_text:
        raise RuntimeError("CrisperWhisper no-space continuation returned replacement characters")

    compact_words = _compact_timed_entries(transcription)
    if not compact_words:
        raise RuntimeError("CrisperWhisper no-space continuation returned no timed entries")
    replacement_count = sum(word["word"].count("\ufffd") for word in compact_words)
    if replacement_count:
        raise RuntimeError("CrisperWhisper no-space timed entries contain replacement characters")
    repetitions = _exact_repetition_runs(compact_words)
    if repetitions and not short_audio:
        rejected_continuation_attempts.append(
            {
                "mode": "verbatim",
                "reason": "repeated_timed_entries",
                "repetitions": repetitions,
                "coverage_fallbacks": coverage_fallbacks,
                "prompt_budgets": prompt_budgets,
            }
        )
        with complete_token_group_decoder(model):
            (
                recovered,
                recovered_coverage,
                recovered_prompts,
                recovered_longform_contract,
            ) = _transcribe_long_no_space(
                model,
                compact_signal,
                language,
                profile,
                sample_rate,
                "intended",
            )
        recovered_text = str(recovered.text or "").strip()
        recovered_words = _compact_timed_entries(recovered)
        recovered_replacements = sum(
            word["word"].count("\ufffd") for word in recovered_words
        )
        recovered_repetitions = _exact_repetition_runs(recovered_words)
        if (
            not recovered_text
            or "\ufffd" in recovered_text
            or not recovered_words
            or recovered_replacements
            or recovered_repetitions
        ):
            raise RuntimeError(
                "CrisperWhisper no-space whole-continuation loop recovery failed: "
                f"words={len(recovered_words)}, replacements={recovered_replacements}, "
                f"repetitions={recovered_repetitions[:5]}"
            )
        transcription = recovered
        transcript_text = recovered_text
        compact_words = recovered_words
        coverage_fallbacks = recovered_coverage
        prompt_budgets = recovered_prompts
        longform_contract = recovered_longform_contract
        replacement_count = 0
        repetitions = []
        selected_continuation_mode = "intended_loop_recovery"
    if repetitions:
        raise RuntimeError(f"CrisperWhisper no-space continuation repeated timed entries: {repetitions[:5]}")

    raw_chunks = list(transcription.chunks or [])
    if raw_chunks and len(coverage_fallbacks) != len(raw_chunks):
        raise RuntimeError(
            "CrisperWhisper no-space coverage diagnostics do not match continuation chunks"
        )
    attempts = []
    windows = []
    chunk_texts = []
    for position, chunk in enumerate(raw_chunks):
        text = str(_chunk_value(chunk, "text") or "").strip()
        coverage = coverage_fallbacks[position]
        if not text:
            raise CrisperWhisperNoSpaceDiagnosticError(
                f"CrisperWhisper no-space continuation returned empty chunk: {position}",
                {
                    "failure_phase": "no_space_continuation",
                    "failure_type": "empty_chunk",
                    "detected_language": normalized_language_code(language),
                    "selected_route": NO_SPACE_LONGFORM_ROUTE,
                    "local_compact_second": float(
                        _chunk_value(chunk, "start_sec") or 0.0
                    ),
                    "failed_chunk_index": position,
                    "failed_chunk": {
                        "chunk_index": int(_chunk_value(chunk, "chunk_idx") or position),
                        "start_seconds": float(
                            _chunk_value(chunk, "start_sec") or 0.0
                        ),
                        "end_seconds": float(
                            _chunk_value(chunk, "end_sec") or 0.0
                        ),
                        "is_last": bool(_chunk_value(chunk, "is_last")),
                    },
                    "coverage_fallbacks": coverage_fallbacks,
                    "prompt_budgets": prompt_budgets,
                },
            )
        chunk_texts.append(text)
        start_seconds = float(_chunk_value(chunk, "start_sec") or 0.0)
        end_seconds = float(_chunk_value(chunk, "end_sec") or 0.0)
        window = {
            "window_index": int(_chunk_value(chunk, "chunk_idx") or position),
            "attempt_index": 0,
            "start_seconds": start_seconds,
            "end_seconds": end_seconds,
            "duration_seconds": max(0.0, end_seconds - start_seconds),
            "word_count": 1,
            "timestamp_repair_count": 0,
            "timestamp_repairs": [],
            "timestamp_drop_count": 0,
            "timestamp_drops": [],
            "end_kind": "final" if bool(_chunk_value(chunk, "is_last")) else "continuation_stride",
            "accepted": True,
            "coverage_fallback": coverage,
        }
        attempts.append(window)
        windows.append(window)
    if not windows:
        duration_seconds = len(compact_signal) / sample_rate
        window = {
            "window_index": 0,
            "attempt_index": 0,
            "start_seconds": 0.0,
            "end_seconds": duration_seconds,
            "duration_seconds": duration_seconds,
            "word_count": len(compact_words),
            "timestamp_repair_count": 0,
            "timestamp_repairs": [],
            "timestamp_drop_count": 0,
            "timestamp_drops": [],
            "end_kind": "final",
            "accepted": True,
            "coverage_fallback": coverage_fallbacks[0],
        }
        attempts.append(window)
        windows.append(window)

    overlaps = [
        _adjacent_chunk_overlap(previous, current)
        for previous, current in zip(chunk_texts, chunk_texts[1:])
    ]
    excessive_overlaps = [
        {"transition_index": index + 1, "overlap_character_count": count}
        for index, count in enumerate(overlaps)
        if count >= 8
    ]
    if excessive_overlaps:
        raise RuntimeError(
            f"CrisperWhisper no-space continuation duplicated chunk text: {excessive_overlaps[:5]}"
        )

    transitions = [
        {
            "window_index": int(window["window_index"]),
            "method": "continuation_context",
            "seam_seconds": float(window["start_seconds"]),
            "validated": True,
            "anchor_word_count": 0,
            "adjacent_exact_overlap_character_count": overlaps[index - 1],
        }
        for index, window in enumerate(windows)
        if index > 0
    ]
    route = {
        "detected_language": normalized_language_code(language),
        "selected_route": NO_SPACE_LONGFORM_ROUTE,
        "language_group": sorted(NO_SPACE_LANGUAGE_CODES),
        "chunk_duration_seconds": longform_contract["chunk_duration_seconds"],
        "stride_seconds": longform_contract["stride_seconds"],
        "overlap_seconds": longform_contract["overlap_seconds"],
        "adaptive_window_retry": longform_contract,
        "context_groups": NO_SPACE_CONTEXT_GROUPS,
        "context_budget_policy": NO_SPACE_CONTEXT_BUDGET_POLICY,
        "context_overflow_policy": NO_SPACE_CONTEXT_OVERFLOW_POLICY,
        "expected_max_target_positions": NO_SPACE_EXPECTED_MAX_TARGET_POSITIONS,
        "model_max_target_positions": model_max_target_positions,
        "generation_token_reserve": NO_SPACE_MAX_NEW_TOKENS,
        "max_new_tokens": NO_SPACE_MAX_NEW_TOKENS,
        "token_decode_policy": NO_SPACE_TOKEN_DECODE_POLICY,
        "coverage_count_mode": NO_SPACE_COVERAGE_COUNT_MODE,
        "fallback_policy": NO_SPACE_FALLBACK_POLICY,
        "maximum_uncovered_active_tail_seconds": (
            NO_SPACE_MAX_UNCOVERED_ACTIVE_TAIL_SECONDS
        ),
        "loop_recovery_policy": NO_SPACE_LOOP_RECOVERY_POLICY,
        "selected_continuation_mode": selected_continuation_mode,
        "whole_continuation_loop_recovery_count": len(
            rejected_continuation_attempts
        ),
        "rejected_continuation_attempts": rejected_continuation_attempts,
        "prompt_budgets": prompt_budgets,
        "trimmed_prompt_count": sum(
            bool(item["context_trimmed"]) for item in prompt_budgets
        ),
        "omitted_context_count": sum(
            bool(item["context_omitted"]) for item in prompt_budgets
        ),
        "coverage_fallbacks": coverage_fallbacks,
        "fallback_source_counts": dict(
            Counter(item["selected_source"] for item in coverage_fallbacks)
        ),
        "replacement_character_count": replacement_count,
        "maximum_adjacent_exact_overlap_character_count": max(overlaps, default=0),
    }
    return compact_words, windows, {"attempts": attempts, "transitions": transitions}, route
