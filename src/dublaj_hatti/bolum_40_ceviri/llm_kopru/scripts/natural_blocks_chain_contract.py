from __future__ import annotations

import copy
from typing import Any

try:
    from . import hedef_dil
except ImportError:
    import hedef_dil


NATURAL_BLOCKS_PROMPT_MODE = "supertonic_natural_blocks_1"
NATURAL_BLOCKS_RETRY_MODE = "natural_blocks_chain_review_retry"
NATURAL_BLOCKS_COVERAGE_MIN_SOURCE_WORDS = 8
NATURAL_BLOCKS_COVERAGE_RATIO_DENOMINATOR = 4


def natural_blocks_word_count(value: str) -> int:
    return sum(
        1
        for token in str(value or "").split()
        if any(character.isalnum() for character in token)
    )


def natural_blocks_source_word_count(segment: dict[str, Any], source_lang: str = "en") -> int:
    try:
        source_word_count = int(segment.get("source_word_count") or 0)
    except (TypeError, ValueError):
        source_word_count = 0
    return source_word_count or hedef_dil.kelime_esdegeri(
        str(segment.get("text") or ""), source_lang, natural_blocks_word_count
    )


def natural_blocks_candidate_sanity_violations(
    job: dict[str, Any],
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    translations = result.get("translations")
    if not isinstance(translations, list):
        return []
    candidates_by_id = {
        str(item.get("id")): item.get("candidates")
        for item in translations
        if isinstance(item, dict)
    }
    segments_by_id = {
        str(segment.get("id")): segment
        for segment in job.get("segments", [])
        if isinstance(segment, dict)
    }
    violations = []
    for segment_id in natural_blocks_expected_ids(job):
        candidates = candidates_by_id.get(segment_id)
        if not isinstance(candidates, list) or not candidates:
            continue
        candidate = candidates[0]
        if not isinstance(candidate, str) or not any(character.isalnum() for character in candidate):
            violations.append({
                "field": "translations",
                "kind": "candidate_source_sanity",
                "message": "Natural Blocks adayi yalnizca bosluk veya noktalamadan olusamaz.",
                "failed_segment_ids": [segment_id],
                "candidate": str(candidate or ""),
            })
            continue
        segment = segments_by_id.get(segment_id, {})
        source_word_count = natural_blocks_source_word_count(segment, hedef_dil.is_kaynak_dili(job))
        candidate_word_count = hedef_dil.kelime_esdegeri(candidate, hedef_dil.is_hedef_dili(job), natural_blocks_word_count)
        if (
            source_word_count >= NATURAL_BLOCKS_COVERAGE_MIN_SOURCE_WORDS
            and candidate_word_count * NATURAL_BLOCKS_COVERAGE_RATIO_DENOMINATOR < source_word_count
        ):
            violations.append({
                "field": "translations",
                "kind": "candidate_catastrophic_coverage",
                "message": "Natural Blocks adayi kaynak segmente gore asiri kisa; tam anlam kapsami bagimsiz olarak dogrulanamadi.",
                "failed_segment_ids": [segment_id],
                "source_word_count": source_word_count,
                "candidate_word_count": candidate_word_count,
                "candidate": candidate,
            })
    return violations


def is_natural_blocks_job(job: dict[str, Any]) -> bool:
    options = job.get("options") if isinstance(job.get("options"), dict) else {}
    return str(options.get("prompt_mode") or "").strip() == NATURAL_BLOCKS_PROMPT_MODE


def natural_blocks_expected_ids(job: dict[str, Any]) -> list[str]:
    return [
        str(segment.get("id"))
        for segment in job.get("segments", [])
        if isinstance(segment, dict)
    ]


def natural_blocks_review_violations(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    if not is_natural_blocks_job(job):
        return []
    expected_ids = natural_blocks_expected_ids(job)
    violations = natural_blocks_candidate_sanity_violations(job, result)
    translations_by_id = {
        str(item.get("id")): item
        for item in result.get("translations", [])
        if isinstance(item, dict)
    }
    for segment_id in expected_ids:
        item = translations_by_id.get(segment_id)
        if not isinstance(item, dict):
            violations.append({
                "field": "translations",
                "kind": "missing_translation",
                "message": "Natural Blocks sonucu beklenen segment ID kaydini icermiyor.",
                "failed_segment_ids": [segment_id],
            })
            continue
        ownership = item.get("ownership_check")
        if not isinstance(ownership, dict):
            violations.append({
                "field": "ownership_check",
                "kind": "missing_ownership_check",
                "message": "Segment sahiplik denetimi eksik.",
                "failed_segment_ids": [segment_id],
            })
            continue
        failed_fields = []
        if ownership.get("status") != "pass":
            failed_fields.append("status")
        if ownership.get("source_coverage") != "complete":
            failed_fields.append("source_coverage")
        if ownership.get("neighbor_meaning_imported") is not False:
            failed_fields.append("neighbor_meaning_imported")
        if ownership.get("neighbor_meaning_exported") is not False:
            failed_fields.append("neighbor_meaning_exported")
        if failed_fields:
            violations.append({
                "field": "ownership_check",
                "kind": "ownership_check_failed",
                "failed_fields": failed_fields,
                "failed_segment_ids": [segment_id],
            })
    if not violations:
        return []
    failed_ids = sorted({
        segment_id
        for violation in violations
        for segment_id in (
            violation.get("missing", [])
            + violation.get("failed_segment_ids", [])
        )
    })
    return [{
        "kind": "natural_blocks_quality_review",
        "message": "Natural Blocks zincir kalite kontrolu gecemedi.",
        "failed_segment_ids": failed_ids or expected_ids,
        "violations": violations,
    }]


def build_natural_blocks_review_retry_job(
    job: dict[str, Any],
    result: dict[str, Any],
    violations: list[dict[str, Any]],
    attempt: int,
) -> dict[str, Any]:
    retry_job = copy.deepcopy(job)
    retry_job["job_id"] = f"{job['job_id']}_chain_review_retry_{attempt}"
    options = dict(retry_job.get("options") or {})
    options["mode"] = NATURAL_BLOCKS_RETRY_MODE
    options["contract_retry_attempt"] = attempt
    retry_job["options"] = options
    retry_job["natural_blocks_review_retry"] = {
        "failed_segment_ids": sorted({
            segment_id
            for violation in violations
            for segment_id in violation.get("failed_segment_ids", [])
        }),
        "violations": violations,
        "previous_translations": [
            {
                "id": str(item.get("id")),
                "candidate": str((item.get("candidates") or [""])[0]).strip(),
            }
            for item in result.get("translations", [])
            if isinstance(item, dict) and item.get("candidates")
        ],
    }
    retry_job["contract_retry_instruction"] = (
        "Natural Blocks ilk cevabi grup zinciri kalite kontrolunden gecemedi. "
        "Tum ana segments listesini bastan sona yeniden oku ve tum grup icin adaylari yeniden yaz. "
        "Her segmentin kaynak anlamini kendi ID'sinde tam koru; komsu ID'ye anlam tasima veya "
        "komsu ID'den anlam cekme. Adaylar ID sirasiyla birlestiginde tek, dogal ve eksiksiz "
        + hedef_dil.dil_adi_ascii(hedef_dil.is_hedef_dili(job))
        + " konusma olusturmali. Kelime sayisini doldurmak icin bilgi ekleme. "
        "Her translations kaydindaki ownership_check alanini o ID'nin gercek kaynak ve hedef "
        "anlamina gore yeniden kur. Basarisiz bir "
        "kontrolu pass olarak isaretlemek yerine once ceviriyi duzelt."
    )
    return retry_job


def replace_natural_blocks_retry_result(
    job: dict[str, Any],
    current_result: dict[str, Any],
    retry_result: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(current_result)
    current_by_id = {
        str(item.get("id")): item
        for item in current_result.get("translations", [])
        if isinstance(item, dict)
    }
    retry_by_id = {
        str(item.get("id")): item
        for item in retry_result.get("translations", [])
        if isinstance(item, dict)
    }
    result["translations"] = [
        copy.deepcopy(retry_by_id.get(segment_id) or current_by_id[segment_id])
        for segment_id in natural_blocks_expected_ids(job)
        if segment_id in retry_by_id or segment_id in current_by_id
    ]
    if retry_by_id:
        result["status"] = retry_result.get("status", result.get("status"))
    result["job_id"] = job.get("job_id")
    return result
