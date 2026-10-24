# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import os
import sys
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

from dublaj_hatti.bolum_40_ceviri.gorunum_adlari import (
    BRIDGE_ORKESTRATORU_ADI,
    FULL_TEXT_SUPPORTED_BRIDGE_BACKENDS,
    bridge_backend_kutu_adi,
    bridge_backend_normalize,
)
from dublaj_hatti.bolum_40_ceviri.llm_kopru.scripts import hedef_dil
from .quality import filter_source_like_translations, is_source_like_translation


logger = logging.getLogger("dublaj_hatti")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
BACKEND_MOTORLARI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PYTHON = Path(sys.executable)
TIMING_REPAIR_MIN_RATIO = 0.70
TIMING_REPAIR_MAX_RATIO = 1.35
TIMING_REPAIR_MIN_TARGET_SECONDS = 2.5
TIMING_REPAIR_MAX_ROUNDS = 1
TURKISH_AVERAGE_WORD_SECONDS = 0.43  # tr olcumu; dil bazli tablo: hedef_dil.KONUSMA_HIZI (tr ayni deger)
DEFAULT_GROUP_SIZE = 10
DEFAULT_CONTEXT_SIZE = 2
DEFAULT_MAX_PARALLEL_JOBS = 7
DEFAULT_GROUP_TRANSIENT_BACKOFF_SECONDS = (2.0, 4.0, 6.0, 8.0, 16.0, 32.0)
DEFAULT_TIMING_PROFILE_MAX_WORKERS = 8
DEFAULT_REPAIR_GROUP_SIZE = 8
DEFAULT_REPAIR_MAX_PARALLEL_JOBS = 4
DEFAULT_REPAIR_FAST_CANDIDATE_COUNT = 5
REPAIR_FULL_CANDIDATE_TARGET_SECONDS = 12.0
SUPERTONIC_WHOLE_CHAIN_MASTER_MODE = "supertonic_whole_chain_master"
SUPERTONIC_WHOLE_CHAIN_CANDIDATES_MODE = "supertonic_whole_chain_candidates"
SUPERTONIC_WHOLE_CHAIN_REPAIR_MODE = "supertonic_whole_chain_repair"
GEMINI_31_FLASH_LITE_INPUT_USD_PER_MILLION = 0.25
GEMINI_31_FLASH_LITE_OUTPUT_USD_PER_MILLION = 1.50
CODEX_GPT_5_6_LUNA_INPUT_USD_PER_MILLION = 1.00
CODEX_GPT_5_6_LUNA_OUTPUT_USD_PER_MILLION = 6.00


def _bridge_backend() -> str:
    backend = os.getenv("CODEX_BRIDGE_WORKER_BACKEND") or os.getenv("CODEX_BRIDGE_BACKEND") or ""
    return bridge_backend_normalize(backend)


def _backend_box_name(backend: str | None = None) -> str:
    return bridge_backend_kutu_adi(backend or _bridge_backend())


def _backend_bridge_root(backend: str | None = None) -> Path:
    return BACKEND_MOTORLARI_ROOT / _backend_box_name(backend)


def _backend_worker_script(backend: str | None = None) -> Path:
    return _backend_bridge_root(backend) / "scripts" / "bridge_worker.py"


class CeviriOrkestratoruDeferredError(RuntimeError):
    def __init__(
        self,
        message: str,
        error_type: str = "temporary",
        retry_after_at: str = "",
        retry_after_seconds: int = 0,
        retry_reason: str = "",
        details: dict | None = None,
    ):
        super().__init__(message)
        self.error_type = str(error_type or "temporary")
        self.retry_after_at = str(retry_after_at or "")
        self.retry_after_seconds = int(retry_after_seconds or 0)
        self.retry_reason = str(retry_reason or "")
        self.details = details or {}


class CeviriEksikSegmentError(RuntimeError):
    pass


class CeviriOrkestratoruGroupTransientError(CeviriOrkestratoruDeferredError):
    pass


class CeviriOrkestratoruGroupTimeoutError(CeviriOrkestratoruGroupTransientError):
    pass


def parse_ceviri_orkestratoru_error_text(text: str) -> dict:
    marker = "CODEX_BRIDGE_ERROR "
    raw_text = str(text or "")
    marker_index = raw_text.find(marker)
    if marker_index < 0:
        return {}
    payload_text = raw_text[marker_index + len(marker):].strip()
    if "\n" in payload_text:
        payload_text = payload_text.splitlines()[0].strip()
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _payload_owned_by_backend(payload: dict, backend_box: str) -> dict:
    owned_payload = dict(payload)
    message = str(owned_payload.get("message") or "Ceviri motoru hatasi")
    prefix = f"[{backend_box}]"
    owned_payload["message"] = message if message.startswith(prefix) else f"{prefix} {message}"
    owned_payload["backend_box"] = backend_box
    return owned_payload


def _deferred_error_from_payload(payload: dict, fallback_message: str) -> CeviriOrkestratoruDeferredError:
    message = str(payload.get("message") or fallback_message or "Ceviri orkestratoru gecici hata")
    error_type = str(payload.get("error_type") or "temporary")
    retry_after_at = str(payload.get("retry_after_at") or "")
    retry_after_seconds = int(payload.get("retry_after_seconds") or 0)
    retry_reason = str(payload.get("retry_reason") or "")
    if error_type == "codex_timeout":
        error_class = CeviriOrkestratoruGroupTimeoutError
    elif payload.get("retryable"):
        error_class = CeviriOrkestratoruGroupTransientError
    else:
        error_class = CeviriOrkestratoruDeferredError
    return error_class(
        message,
        error_type=error_type,
        retry_after_at=retry_after_at,
        retry_after_seconds=retry_after_seconds,
        retry_reason=retry_reason,
        details=payload,
    )


def _env_int(name: str, default: int, minimum: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return max(minimum, int(default))
    try:
        return max(minimum, int(raw_value))
    except ValueError:
        logger.warning("Ceviri orkestratoru ayar gecersiz, varsayilan kullaniliyor: %s=%s", name, raw_value)
        return max(minimum, int(default))


def _env_float_tuple(name: str, default: tuple[float, ...]) -> tuple[float, ...]:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    values = []
    for item in raw_value.split(","):
        text = item.strip()
        if not text:
            continue
        try:
            values.append(max(0.0, float(text)))
        except ValueError:
            logger.warning("Ceviri orkestratoru ayar gecersiz, varsayilan kullaniliyor: %s=%s", name, raw_value)
            return default
    return tuple(values) or default


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _voice_engine_for_tts(tts_engine: str) -> str:
    return "supertonic_tts"


class BridgeMotorOrkestratoruTranslator:
    def __init__(
        self,
        target_lang: str,
        source_lang: str = "en",
        candidate_count: int = 5,
        repair_candidate_count: int = 0,
        timeout_seconds: int = 900,
        timing_selection: bool = False,
        tts_voice_id: str = "",
        tts_rate: str = "+0%",
        tts_pitch: str = "+0Hz",
        tts_volume: str = "+0%",
        tts_speed_factor: float = 1.0,
        tts_engine: str = "supertonic",
        group_size: int = DEFAULT_GROUP_SIZE,
        context_size: int = DEFAULT_CONTEXT_SIZE,
        max_parallel_jobs: int = DEFAULT_MAX_PARALLEL_JOBS,
        fixed_group_size: bool = False,
        prompt_mode: str = "",
        bridge_backend: str = "",
    ):
        self.target_lang = target_lang
        self.source_lang = source_lang
        self.candidate_count = max(1, min(int(candidate_count or 5), 10))
        self.repair_candidate_count = max(0, min(int(repair_candidate_count or 0), 10))
        self.timeout_seconds = int(timeout_seconds or 900)
        self.timing_selection = timing_selection
        self.tts_voice_id = tts_voice_id
        self.tts_rate = tts_rate
        self.tts_pitch = tts_pitch
        self.tts_volume = tts_volume
        self.tts_speed_factor = max(float(tts_speed_factor or 1.0), 0.1)
        self.tts_engine = str(tts_engine or "supertonic").strip().lower()
        self.group_size = max(1, int(group_size)) if fixed_group_size else _env_int("CODEX_BRIDGE_GROUP_SIZE", group_size, 1)
        self.prompt_mode = str(prompt_mode or "").strip()
        self.bridge_backend = bridge_backend_normalize(bridge_backend) if str(bridge_backend or "").strip() else ""
        self.context_size = _env_int("CODEX_BRIDGE_CONTEXT_SIZE", context_size, 0)
        self.max_parallel_jobs = _env_int("CODEX_BRIDGE_MAX_PARALLEL_JOBS", max_parallel_jobs, 1)
        self.group_transient_backoff_seconds = _env_float_tuple(
            "CODEX_BRIDGE_GROUP_TRANSIENT_BACKOFF_SECONDS",
            DEFAULT_GROUP_TRANSIENT_BACKOFF_SECONDS,
        )
        self.group_transient_retries = _env_int(
            "CODEX_BRIDGE_GROUP_TRANSIENT_RETRIES",
            len(self.group_transient_backoff_seconds),
            0,
        )
        self.timing_profile_max_workers = _env_int(
            "CODEX_TIMING_PROFILE_MAX_WORKERS",
            DEFAULT_TIMING_PROFILE_MAX_WORKERS,
            1,
        )
        self.repair_group_size = _env_int("CODEX_BRIDGE_REPAIR_GROUP_SIZE", DEFAULT_REPAIR_GROUP_SIZE, 1)
        self.repair_max_parallel_jobs = _env_int(
            "CODEX_BRIDGE_REPAIR_MAX_PARALLEL_JOBS",
            DEFAULT_REPAIR_MAX_PARALLEL_JOBS,
            1,
        )
        self.repair_fast_candidate_count = _env_int(
            "CODEX_BRIDGE_REPAIR_FAST_CANDIDATE_COUNT",
            DEFAULT_REPAIR_FAST_CANDIDATE_COUNT,
            1,
        )
        self.last_video_usage_report = ""
        self.canonical_target_by_id: Dict[str, str] = {}
        self.current_target_by_id: Dict[str, str] = {}

    def _whole_chain_repair_enabled(self) -> bool:
        return (
            self.tts_engine in {"supertonic", "supertonic_tts"}
            and self.prompt_mode == SUPERTONIC_WHOLE_CHAIN_CANDIDATES_MODE
        )

    def _group_transient_backoff_seconds(self, retry_index: int) -> float:
        if not self.group_transient_backoff_seconds:
            return 0.0
        index = min(max(int(retry_index or 0), 0), len(self.group_transient_backoff_seconds) - 1)
        return self.group_transient_backoff_seconds[index]

    def _voice_payload(self) -> dict:
        payload = {
            "engine": _voice_engine_for_tts(self.tts_engine),
            "voice_id": self.tts_voice_id,
            "rate": self.tts_rate,
            "pitch": self.tts_pitch,
            "volume": self.tts_volume,
            "tts_speed_factor": self.tts_speed_factor,
        }
        return payload

    def _python_executable(self) -> Path:
        env_python = os.getenv("CODEX_BRIDGE_PYTHON", "").strip()
        if env_python:
            return Path(env_python)
        return DEFAULT_PYTHON

    def _segment_id(self, seg, fallback: int):
        return getattr(seg, "index", getattr(seg, "id", fallback))

    def _segment_text(self, seg) -> str:
        return str(getattr(seg, "text", "")).strip()

    def _segment_source_text(self, seg) -> str:
        source_text = str(getattr(seg, "original_source_text", "") or "").strip()
        if source_text:
            return source_text
        return self._segment_text(seg)

    def _segment_duration(self, seg) -> float:
        start = float(getattr(seg, "start", getattr(seg, "start_time", 0.0)) or 0.0)
        end = float(getattr(seg, "end", getattr(seg, "end_time", start)) or start)
        return max(end - start, 0.0)

    def _fragment_hints(self, text: str, previous_text: str, next_text: str) -> dict:
        stripped = text.strip()
        previous = previous_text.strip()
        next_value = next_text.strip()
        starts_lowercase = bool(stripped[:1] and stripped[:1].islower())
        previous_ends_open = previous.endswith(("...", ",", "and", "or", "but"))
        current_ends_open = stripped.endswith(("...", ",", "and", "or", "but"))
        next_starts_lowercase = bool(next_value[:1] and next_value[:1].islower())
        return {
            "previous_text": previous,
            "next_text": next_value,
            "starts_lowercase": starts_lowercase,
            "previous_ends_open": previous_ends_open,
            "current_ends_open": current_ends_open,
            "next_starts_lowercase": next_starts_lowercase,
            "likely_fragment": starts_lowercase or previous_ends_open or current_ends_open or next_starts_lowercase,
        }

    def _meaning_safe_minimum_words(self, source_word_count: int, profile_min_words: int) -> int:
        source_word_count = max(1, int(source_word_count or 1))
        profile_min_words = max(1, int(profile_min_words or 1))
        if source_word_count >= 120:
            ratio = 0.35
        elif source_word_count >= 80:
            ratio = 0.40
        else:
            ratio = 0.55
        return max(1, min(profile_min_words, round(source_word_count * ratio)))

    def _meaning_safe_maximum_words(self, source_word_count: int, profile_max_words: int, meaning_safe_minimum: int) -> int:
        source_word_count = max(1, int(source_word_count or 1))
        profile_max_words = max(1, int(profile_max_words or 1))
        meaning_safe_minimum = max(1, int(meaning_safe_minimum or 1))
        meaning_max = max(meaning_safe_minimum, round(source_word_count * 1.15))
        return max(meaning_safe_minimum, min(profile_max_words, meaning_max))

    def _duration_strategy_text(self, source_word_count: int, profile_min_words: int) -> str:
        meaning_safe_minimum = self._meaning_safe_minimum_words(source_word_count, profile_min_words)
        if meaning_safe_minimum < profile_min_words:
            return (
                "Anlam sadakati timing hedefinden önce gelir. Bu segment kaynak anlamı kısa veya sınırlı olduğu için "
                "hedef süreyi doldurmak amacıyla kaynakta olmayan yorum, sonuç, genelleme, duygu, gelecek etkisi "
                "veya komşu segment fikri ekleme. " + hedef_dil.dil_adi(self.target_lang)
                + " replik doğal ve sadık kalsın; gerekirse hedef süre kısa kalsın."
            )
        return (
            "Anlam sadakati timing hedefinden önce gelir. Kaynakta bulunan özne, nesne, eylem, sayı, örnek ve ilişkiyi "
            + hedef_dil.dil_adi(self.target_lang, "de")
            + " doğal kur; hedef süreyi doldurmak için kaynakta olmayan yorum, sonuç, genelleme, duygu, "
            "gelecek etkisi veya komşu segment fikri ekleme."
        )

    def _timing_contract_text(self, source_word_count: int, profile_min_words: int) -> str:
        meaning_safe_minimum = self._meaning_safe_minimum_words(source_word_count, profile_min_words)
        if meaning_safe_minimum < profile_min_words:
            return (
                "Bu segmentte anlam sadakati ana kalite şartıdır. Kelime alt sınırı kaynak anlamını bozmadan "
                "mümkün olan güvenli alt sınırdır; süreyi doldurmak için yeni bilgi eklemek geçersizdir."
            )
        return (
            "Bu segmentte anlam sadakati ana kalite şartıdır. Timing hedefi yardımcı seçim sinyalidir; "
            "kaynakta olmayan bilgi ekleyen aday geçersizdir."
        )

    def _build_context_segment(self, seg, fallback: int) -> dict:
        entry = {
            "id": self._segment_id(seg, fallback),
            "text": self._segment_text(seg),
        }
        duration = self._segment_duration(seg)
        if duration > 0:
            entry.update({
                "start": float(getattr(seg, "start", getattr(seg, "start_time", 0.0)) or 0.0),
                "end": float(getattr(seg, "end", getattr(seg, "end_time", duration)) or duration),
                "duration": round(duration, 3),
            })
        return entry

    def _build_source_discourse_segments(self, segments: List) -> List[dict]:
        return [
            {
                "id": self._segment_id(seg, fallback_id),
                "text": self._segment_source_text(seg),
            }
            for fallback_id, seg in enumerate(segments)
            if self._segment_source_text(seg)
        ]

    def _build_job(
        self,
        segments: List,
        job_id: str,
        context_before: List | None = None,
        context_after: List | None = None,
        discourse_segments: List | None = None,
        group_number: int | None = None,
        total_groups: int | None = None,
    ) -> dict:
        context_before = context_before or []
        context_after = context_after or []
        job_segments = []
        for fallback_id, seg in enumerate(segments):
            duration = self._segment_duration(seg)
            text = self._segment_text(seg)
            if self._whole_chain_repair_enabled():
                entry = {
                    "id": self._segment_id(seg, fallback_id),
                    "text": text,
                }
                if duration > 0:
                    entry["target_duration"] = round(duration, 3)
                job_segments.append(entry)
                continue
            if fallback_id > 0:
                previous_text = self._segment_text(segments[fallback_id - 1])
            elif context_before:
                previous_text = self._segment_text(context_before[-1])
            else:
                previous_text = ""
            if fallback_id + 1 < len(segments):
                next_text = self._segment_text(segments[fallback_id + 1])
            elif context_after:
                next_text = self._segment_text(context_after[0])
            else:
                next_text = ""
            entry = {
                "id": self._segment_id(seg, fallback_id),
                "text": text,
                "context": self._fragment_hints(text, previous_text, next_text),
            }
            if duration > 0:
                raw_target = round(duration * self.tts_speed_factor, 3)
                target_words = max(1, round(raw_target / hedef_dil.saniye_per_kelime(self.target_lang)))
                source_word_count = hedef_dil.kelime_esdegeri(text, self.source_lang)
                profile_min_words = max(1, round(target_words * 0.87))
                profile_max_words = max(profile_min_words, round(target_words * 1.13))
                soft_min_words = max(1, round(target_words * 0.75))
                soft_max_words = max(soft_min_words, round(target_words * 1.25))
                meaning_safe_minimum = self._meaning_safe_minimum_words(source_word_count, profile_min_words)
                meaning_safe_maximum = self._meaning_safe_maximum_words(source_word_count, profile_max_words, meaning_safe_minimum)
                source_limited = meaning_safe_minimum < profile_min_words
                entry.update({
                    "start": float(getattr(seg, "start", getattr(seg, "start_time", 0.0)) or 0.0),
                    "end": float(getattr(seg, "end", getattr(seg, "end_time", duration)) or duration),
                    "duration": round(duration, 3),
                    "raw_tts_target_duration": raw_target,
                    "timing_acceptance": {"min_ratio": 0.9, "max_ratio": 1.15},
                    "hedef_kelime": target_words,
                    "kelime_aralik": f"{soft_min_words}-{soft_max_words}",
                    "target_word_count": target_words,
                    "profile_target_word_count": target_words,
                    "profile_required_word_range": f"{profile_min_words}-{profile_max_words}",
                    "source_word_count": source_word_count,
                    "minimum_fill_word_count": meaning_safe_minimum if source_limited else profile_min_words,
                    "maximum_fill_word_count": meaning_safe_maximum if source_limited else profile_max_words,
                    "hard_minimum_word_count": meaning_safe_minimum,
                    "recommended_word_range": (
                        f"{meaning_safe_minimum}-{meaning_safe_maximum}"
                        if source_limited
                        else f"{profile_min_words}-{profile_max_words}"
                    ),
                    "invalid_if_below_word_count": meaning_safe_minimum,
                    "candidate_word_count_targets": [
                        meaning_safe_minimum,
                        min(meaning_safe_minimum + 2, meaning_safe_maximum),
                    ],
                    "too_short_below_words": meaning_safe_minimum,
                    "timing_feasibility": "timing_guided",
                    "meaning_safety_contract": "Her aday sadece bu segmentin kaynak anlamını taşır; komşu segment bağlamdır, çeviri malzemesi değildir.",
                    "timing_contract": self._timing_contract_text(source_word_count, profile_min_words),
                    "duration_strategy": self._duration_strategy_text(source_word_count, profile_min_words),
                    "fragment_guidance": "Önceki/sonraki context ile bağlantıyı koru." if self._fragment_hints(text, previous_text, next_text).get("likely_fragment") else "",
                })
            job_segments.append(entry)

        options = {
            "candidate_count": 1 if self._whole_chain_repair_enabled() else self.candidate_count,
        }
        if self.prompt_mode:
            options["prompt_mode"] = (
                SUPERTONIC_WHOLE_CHAIN_MASTER_MODE
                if self._whole_chain_repair_enabled()
                else self.prompt_mode
            )
        if group_number is not None and total_groups is not None:
            options.update({
                "main_only": True,
                "group_number": group_number,
                "total_groups": total_groups,
                "context_before_count": len(context_before),
                "context_after_count": len(context_after),
            })

        job = {
            "job_id": job_id,
            "task_type": "translation_candidates",
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "voice": self._voice_payload(),
            "options": options,
            "segments": job_segments,
        }
        if context_before or context_after:
            job["context_before"] = [self._build_context_segment(seg, idx) for idx, seg in enumerate(context_before)]
            job["context_after"] = [self._build_context_segment(seg, idx) for idx, seg in enumerate(context_after)]
        if discourse_segments:
            job["discourse_segments"] = self._build_source_discourse_segments(discourse_segments)
        return job

    def _build_supertonic_whole_chain_candidate_job(
        self,
        segments: List,
        canonical_by_id: Dict[str, List[str]],
        job_id: str,
        discourse_segments: List,
        group_number: int | None = None,
        total_groups: int | None = None,
    ) -> dict:
        candidate_segments = []
        canonical_target_segments = []
        for fallback_id, seg in enumerate(segments):
            seg_id = str(self._segment_id(seg, fallback_id))
            values = canonical_by_id.get(seg_id, [])
            canonical_text = str(values[0] if values else self._segment_text(seg)).strip()
            entry = {
                "id": self._segment_id(seg, fallback_id),
                "text": canonical_text,
            }
            duration = self._segment_duration(seg)
            if duration > 0:
                entry["target_duration"] = round(duration, 3)
            candidate_segments.append(entry)
            canonical_target_segments.append({"id": seg_id, "text": canonical_text})
        for index, entry in enumerate(candidate_segments):
            entry["context_before"] = canonical_target_segments[index - 1]["text"] if index > 0 else ""
            entry["context_after"] = canonical_target_segments[index + 1]["text"] if index + 1 < len(canonical_target_segments) else ""
        options = {
            "candidate_count": self.candidate_count,
            "mode": "whole_chain_initial_candidates",
            "prompt_mode": SUPERTONIC_WHOLE_CHAIN_CANDIDATES_MODE,
        }
        if group_number is not None and total_groups is not None:
            options.update({
                "main_only": True,
                "group_number": group_number,
                "total_groups": total_groups,
            })
        return {
            "job_id": job_id,
            "task_type": "translation_candidates",
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "voice": self._voice_payload(),
            "options": options,
            "canonical_target_segments": canonical_target_segments,
            "segments": candidate_segments,
            "discourse_segments": self._build_source_discourse_segments(discourse_segments),
        }

    def _write_job(self, run_dir: str, job: dict, log_subdir: str = "") -> Path:
        job_dir = Path(run_dir) / "codex_bridge_translation"
        if log_subdir:
            job_dir = job_dir / log_subdir
        job_dir.mkdir(parents=True, exist_ok=True)
        job_path = job_dir / f"{job['job_id']}.json"
        payload = json.dumps(job, ensure_ascii=False, indent=2)
        job_path.write_text(payload, encoding="utf-8")
        (job_dir / "request.json").write_text(payload, encoding="utf-8")
        return job_path

    def _run_bridge(self, job_path: Path, run_dir: str, log_subdir: str = "", result_filename: str = "result.json") -> Path:
        python_exe = self._python_executable()
        bridge_backend = self.bridge_backend or _bridge_backend()
        backend_bridge_root = _backend_bridge_root(bridge_backend)
        worker_script = _backend_worker_script(bridge_backend)
        backend_box = _backend_box_name(bridge_backend)
        if not python_exe.exists():
            raise FileNotFoundError(f"Ceviri orkestratoru Python bulunamadi: {python_exe}")
        if not worker_script.exists():
            raise FileNotFoundError(f"[{backend_box}] Ceviri motoru worker bulunamadi: {worker_script}")

        command = [
            str(python_exe),
            "-B",
            str(worker_script),
            "--job",
            str(job_path),
            "--timeout",
            str(self.timeout_seconds),
            "--keep-job",
        ]
        started = time.time()
        try:
            result = subprocess.run(
                command,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=self.timeout_seconds + 60,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env={
                    **os.environ,
                    "CODEX_BRIDGE_WORKER_BACKEND": bridge_backend,
                    "CODEX_BRIDGE_BACKEND": bridge_backend,
                },
            )
        except subprocess.TimeoutExpired as exc:
            retry_after_seconds = 600
            payload = {
                "message": f"[{backend_box}] Ceviri motoru worker timeout: {self.timeout_seconds + 60}s",
                "backend_box": backend_box,
                "error_type": "codex_timeout",
                "retryable": True,
                "retry_after_at": "",
                "retry_after_seconds": retry_after_seconds,
                "retry_reason": "worker_timeout",
            }
            raise _deferred_error_from_payload(payload, str(exc)) from exc
        duration = time.time() - started
        log_dir = Path(run_dir) / "codex_bridge_translation"
        if log_subdir:
            log_dir = log_dir / log_subdir
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "worker_stdout.txt").write_text(result.stdout or "", encoding="utf-8")
        (log_dir / "worker_stderr.txt").write_text(result.stderr or "", encoding="utf-8")
        (log_dir / "worker_command.json").write_text(json.dumps({
            "command": command,
            "returncode": result.returncode,
            "duration_seconds": round(duration, 3),
            "bridge_backend": bridge_backend,
            "backend_box": backend_box,
            "backend_bridge_root": str(backend_bridge_root),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        if result.returncode != 0:
            combined_output = f"{result.stderr or ''}\n{result.stdout or ''}"
            payload = parse_ceviri_orkestratoru_error_text(combined_output)
            if payload:
                payload = _payload_owned_by_backend(payload, backend_box)
            if payload.get("retryable"):
                raise _deferred_error_from_payload(payload, combined_output)
            if payload:
                raise RuntimeError(
                    f"{payload['message']} (error_type={payload.get('error_type') or 'bilinmiyor'})"
                )
            raise RuntimeError(f"[{backend_box}] Ceviri motoru basarisiz oldu: {result.stderr or result.stdout}")

        result_lines = (result.stdout or "").strip().splitlines()
        result_path_text = result_lines[-1].strip() if result_lines else ""
        result_path = Path(result_path_text)
        if not result_path_text or not result_path.exists():
            raise FileNotFoundError(f"[{backend_box}] Ceviri motoru result bulunamadi: {result_path_text or 'bos stdout'}")

        local_result_path = log_dir / result_filename
        shutil.copy2(result_path, local_result_path)
        self._write_result_usage_summaries(local_result_path, log_dir)
        return local_result_path

    def _usage_cost_usd(self, model: str, input_tokens: int, output_tokens: int) -> float | None:
        prices = self._usage_prices_per_million(model)
        if prices is None:
            return None
        input_price, output_price = prices
        input_cost = input_tokens * input_price / 1_000_000
        output_cost = output_tokens * output_price / 1_000_000
        return round(input_cost + output_cost, 8)

    def _usage_prices_per_million(self, model: str) -> tuple[float, float] | None:
        normalized_model = str(model or "").lower()
        if normalized_model == "gpt-5.6-luna":
            return CODEX_GPT_5_6_LUNA_INPUT_USD_PER_MILLION, CODEX_GPT_5_6_LUNA_OUTPUT_USD_PER_MILLION
        if normalized_model == "gemini-3.1-flash-lite":
            return GEMINI_31_FLASH_LITE_INPUT_USD_PER_MILLION, GEMINI_31_FLASH_LITE_OUTPUT_USD_PER_MILLION
        return None

    def _usage_summary_from_meta(
        self,
        source_result: Path,
        meta: dict,
        usage_kind: str,
        retry_attempt: int,
    ) -> dict:
        model = str(meta.get("model") or "")
        input_tokens = _safe_int(meta.get("input_tokens"))
        cached_input_tokens = _safe_int(meta.get("cached_input_tokens"))
        output_tokens = _safe_int(meta.get("output_tokens"))
        reasoning_output_tokens = _safe_int(meta.get("reasoning_output_tokens"))
        total_tokens = _safe_int(meta.get("total_tokens")) or input_tokens + output_tokens
        return {
            "source_result": str(source_result),
            "usage_kind": usage_kind,
            "retry_attempt": retry_attempt,
            "backend": str(meta.get("backend") or ""),
            "model": model,
            "reasoning_effort": str(meta.get("reasoning_effort") or ""),
            "execution_mode": str(meta.get("execution_mode") or ""),
            "duration_seconds": _safe_float(meta.get("duration_seconds")),
            "estimated_input_tokens": _safe_int(meta.get("estimated_input_tokens")),
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "output_tokens": output_tokens,
            "reasoning_output_tokens": reasoning_output_tokens,
            "total_tokens": total_tokens,
            "token_usage_available": bool(meta.get("token_usage_available")),
            "token_usage_source": str(meta.get("token_usage_source") or ""),
            "pricing_status": str(meta.get("pricing_status") or ""),
            "usage_metadata": meta.get("usage_metadata") if isinstance(meta.get("usage_metadata"), dict) else {},
            "rate_limit_headers": meta.get("rate_limit_headers") if isinstance(meta.get("rate_limit_headers"), dict) else {},
        }

    def _write_usage_summary_file(self, path: Path, summary: dict) -> None:
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_result_usage_summaries(self, result_path: Path, log_dir: Path) -> None:
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Ceviri motoru usage summary okunamadi: result=%s error=%s", result_path, exc)
            return
        meta = result.get("_bridge_meta")
        if not isinstance(meta, dict):
            return
        contract_retry = meta.get("contract_retry")
        if isinstance(contract_retry, dict):
            for run in contract_retry.get("runs", []):
                if not isinstance(run, dict):
                    continue
                retry_meta = run.get("meta")
                if not isinstance(retry_meta, dict):
                    continue
                attempt = _safe_int(run.get("attempt"))
                summary = self._usage_summary_from_meta(result_path, retry_meta, "contract_retry", attempt)
                self._write_usage_summary_file(
                    log_dir / f"result_contract_retry_{attempt}_usage_summary.json",
                    summary,
                )
        summary = self._usage_summary_from_meta(result_path, meta, "primary", 0)
        self._write_usage_summary_file(log_dir / "result_usage_summary.json", summary)

    def _usage_phase_for_summary(self, summary_path: Path, bridge_dir: Path) -> str:
        relative_parts = summary_path.relative_to(bridge_dir).parts
        if relative_parts and (
            str(relative_parts[0]).startswith("timing_repair_r")
            or str(relative_parts[0]).startswith("real_tts_repair_r")
        ):
            return "real_tts_repair"
        if relative_parts and str(relative_parts[0]).startswith("group_"):
            return "main_translation_group"
        return "main_translation"

    def _empty_usage_bucket(self) -> dict:
        return {
            "request_count": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_output_tokens": 0,
            "total_tokens": 0,
            "duration_seconds": 0.0,
            "estimated_cost_usd": 0.0,
            "pricing_status": "priced_configured",
        }

    def _add_usage_to_bucket(self, bucket: dict, request: dict) -> None:
        bucket["request_count"] += 1
        bucket["input_tokens"] += _safe_int(request.get("input_tokens"))
        bucket["cached_input_tokens"] += _safe_int(request.get("cached_input_tokens"))
        bucket["output_tokens"] += _safe_int(request.get("output_tokens"))
        bucket["reasoning_output_tokens"] += _safe_int(request.get("reasoning_output_tokens"))
        bucket["total_tokens"] += _safe_int(request.get("total_tokens"))
        bucket["duration_seconds"] = round(bucket["duration_seconds"] + _safe_float(request.get("duration_seconds")), 3)
        if request.get("estimated_cost_usd") is None:
            bucket["estimated_cost_usd"] = None
            bucket["pricing_status"] = "not_available_exact_model_price_not_verified"
        elif bucket.get("estimated_cost_usd") is not None:
            bucket["estimated_cost_usd"] = round(
                _safe_float(bucket.get("estimated_cost_usd")) + _safe_float(request.get("estimated_cost_usd")),
                8,
            )

    def _write_video_usage_report(
        self,
        run_dir: str,
        job_id: str,
        result_label: str,
        segment_count: int,
    ) -> str:
        bridge_dir = Path(run_dir) / "codex_bridge_translation"
        summary_paths = sorted(bridge_dir.glob("**/result*_usage_summary.json"))
        if not summary_paths:
            return ""
        requests = []
        totals = {
            "request_count": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_output_tokens": 0,
            "total_tokens": 0,
            "estimated_input_tokens": 0,
            "duration_seconds": 0.0,
            "estimated_cost_usd": 0.0,
            "pricing_status": "priced_configured",
        }
        by_phase: dict[str, dict] = {}
        by_model: dict[str, dict] = {}
        by_model_reasoning_effort: dict[str, dict] = {}
        for summary_path in summary_paths:
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Ceviri motoru usage summary gecersiz: path=%s error=%s", summary_path, exc)
                continue
            model = str(summary.get("model") or "unknown")
            input_tokens = _safe_int(summary.get("input_tokens"))
            cached_input_tokens = _safe_int(summary.get("cached_input_tokens"))
            output_tokens = _safe_int(summary.get("output_tokens"))
            reasoning_output_tokens = _safe_int(summary.get("reasoning_output_tokens"))
            total_tokens = _safe_int(summary.get("total_tokens")) or input_tokens + output_tokens
            request = {
                "phase": self._usage_phase_for_summary(summary_path, bridge_dir),
                "summary_path": str(summary_path),
                "source_result": str(summary.get("source_result") or ""),
                "usage_kind": str(summary.get("usage_kind") or ""),
                "retry_attempt": _safe_int(summary.get("retry_attempt")),
                "backend": str(summary.get("backend") or ""),
                "model": model,
                "reasoning_effort": str(summary.get("reasoning_effort") or ""),
                "execution_mode": str(summary.get("execution_mode") or ""),
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_input_tokens,
                "output_tokens": output_tokens,
                "reasoning_output_tokens": reasoning_output_tokens,
                "total_tokens": total_tokens,
                "estimated_input_tokens": _safe_int(summary.get("estimated_input_tokens")),
                "duration_seconds": _safe_float(summary.get("duration_seconds")),
                "estimated_cost_usd": self._usage_cost_usd(model, input_tokens, output_tokens),
                "pricing_status": str(summary.get("pricing_status") or "priced_configured"),
                "token_usage_available": bool(summary.get("token_usage_available")),
                "token_usage_source": str(summary.get("token_usage_source") or ""),
            }
            prices = self._usage_prices_per_million(model)
            if prices is not None:
                request["input_per_million"] = prices[0]
                request["output_per_million"] = prices[1]
                request["currency"] = "USD"
            requests.append(request)
            totals["request_count"] += 1
            totals["input_tokens"] += request["input_tokens"]
            totals["cached_input_tokens"] += request["cached_input_tokens"]
            totals["output_tokens"] += request["output_tokens"]
            totals["reasoning_output_tokens"] += request["reasoning_output_tokens"]
            totals["total_tokens"] += request["total_tokens"]
            totals["estimated_input_tokens"] += request["estimated_input_tokens"]
            totals["duration_seconds"] = round(totals["duration_seconds"] + request["duration_seconds"], 3)
            if request["estimated_cost_usd"] is None:
                totals["estimated_cost_usd"] = None
                totals["pricing_status"] = "not_available_exact_model_price_not_verified"
            elif totals["estimated_cost_usd"] is not None:
                totals["estimated_cost_usd"] = round(totals["estimated_cost_usd"] + request["estimated_cost_usd"], 8)
            phase_bucket = by_phase.setdefault(request["phase"], self._empty_usage_bucket())
            model_bucket = by_model.setdefault(model, self._empty_usage_bucket())
            reasoning_key = f"{model}|{request['reasoning_effort'] or 'unspecified'}"
            reasoning_bucket = by_model_reasoning_effort.setdefault(reasoning_key, self._empty_usage_bucket())
            self._add_usage_to_bucket(phase_bucket, request)
            self._add_usage_to_bucket(model_bucket, request)
            self._add_usage_to_bucket(reasoning_bucket, request)
        report = {
            "schema_version": 1,
            "created_at": int(time.time()),
            "run_dir": str(run_dir),
            "job_id": f"final_{Path(run_dir).name}",
            "source_job_id": job_id,
            "result_label": result_label,
            "segment_count": segment_count,
            "candidate_count": self.candidate_count,
            "group_size": self.group_size,
            "context_size": self.context_size,
            "totals": totals,
            "by_phase": by_phase,
            "by_model": by_model,
            "by_model_reasoning_effort": by_model_reasoning_effort,
            "requests": requests,
            "pricing_note": "Only models with configured and verified token prices receive an estimated USD cost. Unverified models retain null cost values.",
        }
        report_path = bridge_dir / "video_usage_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self._append_video_usage_ledger(report)
        return str(report_path)

    def _append_video_usage_ledger(self, report: dict) -> None:
        usage_dir = _backend_bridge_root(self.bridge_backend or _bridge_backend()) / "runtime" / "usage"
        usage_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = usage_dir / "video_usage_ledger.jsonl"
        row = {
            "schema_version": 1,
            "created_at": int(time.time()),
            "run_dir": report.get("run_dir"),
            "job_id": report.get("job_id"),
            "result_label": report.get("result_label"),
            "segment_count": report.get("segment_count"),
            **(report.get("totals") if isinstance(report.get("totals"), dict) else {}),
        }
        with open(ledger_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _clean_candidates(self, seg, candidates: List[str], label: str) -> List[str]:
        candidates = [str(item).strip() for item in candidates if str(item).strip()]
        if not candidates:
            return []
        accepted, rejected = filter_source_like_translations(self._segment_text(seg), candidates)
        if rejected:
            logger.warning(
                "Ceviri motoru source-like aday reddedildi: seg=%s label=%s rejected=%d accepted=%d",
                self._segment_id(seg, 0),
                label,
                len(rejected),
                len(accepted),
            )
        return accepted

    def _rank_candidates(self, seg, candidates: List[str], timing_context=None) -> str:
        candidates = self._clean_candidates(seg, candidates, "final_selection")
        return candidates[0] if candidates else ""

    def _repair_candidate_count_for_segments(self, repair_segments: List[dict]) -> int:
        if self.repair_candidate_count > 0:
            return self.repair_candidate_count
        if not repair_segments:
            return self.candidate_count
        max_target = max(float(item.get("raw_tts_target_duration") or 0.0) for item in repair_segments)
        has_coverage_problem = any("coverage_unresolved" in str(item.get("problem", "")) for item in repair_segments)
        if has_coverage_problem or max_target >= REPAIR_FULL_CANDIDATE_TARGET_SECONDS:
            return self.candidate_count
        return max(1, min(self.candidate_count, self.repair_fast_candidate_count))

    def _build_timing_repair_job(
        self,
        base_job: dict,
        repair_segments: List[dict],
        repair_round: int,
        job_id: str,
        candidate_count: int,
        chunk_number: int | None = None,
        total_chunks: int | None = None,
    ) -> dict:
        options = {
            "candidate_count": candidate_count,
            "mode": "timing_repair",
            "repair_round": repair_round,
        }
        if chunk_number is not None and total_chunks is not None:
            options.update({
                "chunk_number": chunk_number,
                "total_chunks": total_chunks,
                "parallel_repair": True,
            })

        return {
            "job_id": job_id,
            "task_type": "translation_candidates",
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "voice": base_job.get("voice", {}),
            "options": options,
            "repair_instruction": (
                "Önceki adaylar hedef süreye, kelime-zaman kapsamasına veya anlam bütünlüğüne uymadığı için reddedildi. "
                "Sadece verilen problemli segmentler için yeniden tam aday sayısı kadar aday üret. "
                "Problem too_short ise kaynak anlamını koruyarak daha dolu, doğal "
                + hedef_dil.dil_adi(self.target_lang)
                + " replikler yaz. "
                "Problem too_long ise anlamı koruyarak daha kompakt replikler yaz. "
                "previous_candidates alanındaki adayları kopyalama; belirgin şekilde farklı sürelerde yeni adaylar üret. "
                "raw_tts_target_duration ana hedeftir; duration sadece orijinal video süresidir. "
                "Süreyi sadece kaynakta zaten bulunan özne, nesne, yer, eylem ve bağlamı daha açık söyleyerek doldur. "
                "Kaynakta açık karşılığı yoksa çünkü, bu yüzden, dolayısıyla, zaten, yalnızca, sadece, aslında gibi neden, kesinlik veya vurgu ekleyen kelimeler kullanma. "
                "Kaynakta olmayan yorum veya bilgi ekleme."
            ),
            "segments": repair_segments,
        }

    def _chunk_repair_segments(self, repair_segments: List[dict]) -> List[List[dict]]:
        fast_segments = []
        full_segments = []
        for item in repair_segments:
            if self._repair_candidate_count_for_segments([item]) < self.candidate_count:
                fast_segments.append(item)
            else:
                full_segments.append(item)

        chunks = []
        for bucket in (full_segments, fast_segments):
            chunks.extend(
                bucket[index:index + self.repair_group_size]
                for index in range(0, len(bucket), self.repair_group_size)
            )
        return chunks

    def _run_parallel_timing_repair(
        self,
        run_dir: str,
        base_job: dict,
        repair_segments: List[dict],
        repair_round: int,
        segment_by_id: Dict[str, object],
    ) -> Tuple[Dict[str, List[str]], dict]:
        chunks = self._chunk_repair_segments(repair_segments)
        total_chunks = len(chunks)
        max_workers = min(self.repair_max_parallel_jobs, total_chunks)
        repair_root = Path(run_dir) / "codex_bridge_translation" / f"timing_repair_r{repair_round}"
        repair_root.mkdir(parents=True, exist_ok=True)

        summary = {
            "round": repair_round,
            "status": "success",
            "total_problem_segments": len(repair_segments),
            "chunk_count": total_chunks,
            "repair_group_size": self.repair_group_size,
            "max_parallel_jobs": self.repair_max_parallel_jobs,
            "actual_parallel_jobs": max_workers,
            "repaired_count": 0,
            "failed_chunks": [],
            "candidate_counts": {},
            "chunks": [],
        }
        logger.info(
            "Ceviri orkestratoru timing repair paralel plan: round=%d problemli=%d chunk=%d worker=%d group_size=%d",
            repair_round,
            len(repair_segments),
            total_chunks,
            max_workers,
            self.repair_group_size,
        )

        def process_chunk(chunk_number: int, chunk_segments: List[dict]) -> dict:
            candidate_count = self._repair_candidate_count_for_segments(chunk_segments)
            log_subdir = f"timing_repair_r{repair_round}" if total_chunks == 1 else f"timing_repair_r{repair_round}/chunk_{chunk_number:03d}"
            job_id = f"{base_job['job_id']}_timing_repair_r{repair_round}"
            if total_chunks > 1:
                job_id = f"{job_id}_c{chunk_number:03d}"
            repair_job = self._build_timing_repair_job(
                base_job,
                chunk_segments,
                repair_round,
                job_id,
                candidate_count,
                chunk_number=chunk_number if total_chunks > 1 else None,
                total_chunks=total_chunks if total_chunks > 1 else None,
            )
            repair_dir = repair_root if total_chunks == 1 else repair_root / f"chunk_{chunk_number:03d}"
            repair_dir.mkdir(parents=True, exist_ok=True)
            repair_path = repair_dir / "request.json"
            repair_path.write_text(json.dumps(repair_job, ensure_ascii=False, indent=2), encoding="utf-8")
            result_path = self._run_bridge(
                repair_path,
                run_dir,
                log_subdir=log_subdir,
                result_filename="result.json",
            )
            data = json.loads(result_path.read_text(encoding="utf-8"))
            translations = data.get("translations") or []
            cleaned_by_id = {}
            repaired_count = 0
            for item in translations:
                item_id = str(item.get("id"))
                if item_id not in segment_by_id:
                    continue
                cleaned = self._clean_candidates(
                    segment_by_id[item_id],
                    item.get("candidates", []),
                    f"timing_repair_response_r{repair_round}_c{chunk_number}",
                )
                if cleaned:
                    cleaned_by_id[item_id] = cleaned
                    repaired_count += 1
            return {
                "chunk_number": chunk_number,
                "segment_count": len(chunk_segments),
                "candidate_count": candidate_count,
                "repaired_count": repaired_count,
                "by_id": cleaned_by_id,
                "result_path": str(result_path),
            }

        repaired_by_id: Dict[str, List[str]] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_chunk, chunk_number, chunk_segments): chunk_number
                for chunk_number, chunk_segments in enumerate(chunks, start=1)
            }
            for future in as_completed(futures):
                chunk_number = futures[future]
                try:
                    result = future.result()
                    repaired_by_id.update(result["by_id"])
                    summary["repaired_count"] += result["repaired_count"]
                    key = str(result["candidate_count"])
                    summary["candidate_counts"][key] = summary["candidate_counts"].get(key, 0) + result["segment_count"]
                    summary["chunks"].append({
                        "chunk_number": result["chunk_number"],
                        "segment_count": result["segment_count"],
                        "candidate_count": result["candidate_count"],
                        "repaired_count": result["repaired_count"],
                        "result_path": result["result_path"],
                    })
                    logger.info(
                        "Ceviri orkestratoru timing repair chunk tamamlandi: round=%d chunk=%d/%d segment=%d aday=%d yenilenen=%d",
                        repair_round,
                        result["chunk_number"],
                        total_chunks,
                        result["segment_count"],
                        result["candidate_count"],
                        result["repaired_count"],
                    )
                except Exception as exc:
                    summary["status"] = "partial"
                    summary["failed_chunks"].append(chunk_number)
                    error_dir = repair_root / f"chunk_{chunk_number:03d}"
                    error_dir.mkdir(parents=True, exist_ok=True)
                    (error_dir / "error.txt").write_text(f"Hata: {exc}\n", encoding="utf-8")
                    logger.warning(
                        "Ceviri orkestratoru timing repair chunk basarisiz: round=%d chunk=%d/%d error=%s",
                        repair_round,
                        chunk_number,
                        total_chunks,
                        exc,
                    )

        summary["chunks"] = sorted(summary["chunks"], key=lambda item: item["chunk_number"])
        (repair_root / "parallel_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return repaired_by_id, summary

    def _real_tts_repair_goal(self, problem: str) -> dict:
        if problem == "too_long_audio":
            return {
                "problem": problem,
                "action": "compress",
                "target": f"produce shorter natural {hedef_dil.dil_adi_en(self.target_lang)} candidates that land under maximum_safe_processed_duration",
                "use_fields": [
                    "maximum_safe_processed_duration",
                    "preferred_processed_duration",
                    "excess_seconds_over_safe_maximum",
                    "previous_candidate_timings",
                ],
                "avoid": [
                    "same_or_longer_length",
                    "same_sentence_skeleton",
                    "neighbor_segment_meaning",
                    "new_fact_or_comment",
                ],
            }
        return {
            "problem": problem,
            "action": "strong_expand",
            "target": f"produce fuller natural {hedef_dil.dil_adi_en(self.target_lang)} candidates that land above minimum_safe_processed_duration",
            "use_fields": [
                "minimum_safe_processed_duration",
                "preferred_processed_duration",
                "missing_seconds_to_safe_minimum",
                "repair_minimum_word_count",
                "repair_target_word_count",
                "repair_recommended_word_range",
                "previous_candidate_timings",
            ],
            "avoid": [
                "same_sentence_skeleton",
                "synonym_only_changes",
                "neighbor_segment_meaning",
                "new_fact_or_comment",
            ],
        }

    def _build_real_tts_repair_segment(
        self,
        seg,
        problem_segment: dict,
        candidates: List[str],
        source_context_before: str = "",
        source_context_after: str = "",
    ) -> dict:
        seg_id = str(problem_segment.get("segment_id") or self._segment_id(seg, 0))
        source_duration = float(problem_segment.get("source_duration") or self._segment_duration(seg) or 0.0)
        preferred_duration = max(source_duration, 0.1)
        minimum_safe_duration = preferred_duration / 1.15
        maximum_safe_duration = preferred_duration / 0.90
        selected_duration = float(
            problem_segment.get("selected_processed_duration")
            or problem_segment.get("selected_duration")
            or 0.0
        )
        problem = str(problem_segment.get("problem") or problem_segment.get("status") or "").strip()
        if problem not in {"too_short_audio", "too_long_audio"}:
            problem = "too_short_audio" if selected_duration < minimum_safe_duration else "too_long_audio"
        previous_timings = []
        for item in problem_segment.get("candidates") or []:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            duration = float(item.get("processed_duration") or item.get("duration") or 0.0)
            previous_timings.append({
                "text": text,
                "spoken_text": str(item.get("spoken_text") or text),
                "duration": round(duration, 3),
                "target_duration": round(preferred_duration, 3),
                "video_speed": round(float(item.get("video_speed") or (preferred_duration / duration if duration else 0.0)), 3),
                "status": str(item.get("status") or ""),
            })
        all_previous_timings = []
        seen_previous_texts = set()
        for item in problem_segment.get("all_previous_candidate_timings") or []:
            text = str(item.get("text") or "").strip()
            if not text or text in seen_previous_texts:
                continue
            duration = float(item.get("duration") or item.get("processed_duration") or 0.0)
            all_previous_timings.append({
                "round": str(item.get("round") or ""),
                "candidate_number": item.get("candidate_number"),
                "text": text,
                "spoken_text": str(item.get("spoken_text") or text),
                "duration": round(duration, 3),
                "target_duration": round(float(item.get("target_duration") or preferred_duration), 3),
                "video_speed": round(float(item.get("video_speed") or (preferred_duration / duration if duration else 0.0)), 3),
                "status": str(item.get("status") or ""),
            })
            seen_previous_texts.add(text)
        if all_previous_timings:
            previous_timings = all_previous_timings
        selected_text = str(problem_segment.get("selected_text") or self._segment_text(seg)).strip()
        previous_candidates = [item["text"] for item in previous_timings] or candidates
        previous_max_word_count = max(
            [hedef_dil.kelime_esdegeri(str(item), self.target_lang) for item in previous_candidates]
            or [hedef_dil.kelime_esdegeri(selected_text, self.target_lang)]
        )
        target_words = max(1, round(preferred_duration / hedef_dil.saniye_per_kelime(self.target_lang)))
        repair_minimum_words = previous_max_word_count + 2 if problem == "too_short_audio" else max(1, round(target_words * 0.65))
        repair_target_words = max(repair_minimum_words, target_words)
        repair_max_words = max(repair_target_words, repair_minimum_words + 2)
        missing_seconds = max(0.0, minimum_safe_duration - selected_duration)
        excess_seconds = max(0.0, selected_duration - maximum_safe_duration)
        return {
            "id": self._segment_id(seg, int(seg_id) if seg_id.isdigit() else 0),
            "text": selected_text,
            "original_source_text": self._segment_source_text(seg),
            "source_context_before": str(source_context_before or "").strip(),
            "source_context_after": str(source_context_after or "").strip(),
            "repair_mode": "target_language_rewrite",
            "text_role": "current_target_language_line",
            "repair_goal": self._real_tts_repair_goal(problem),
            "duration": round(preferred_duration, 3),
            "raw_tts_target_duration": round(preferred_duration * self.tts_speed_factor, 3),
            "final_tts_target_duration": round(preferred_duration, 3),
            "best_candidate_duration": round(selected_duration, 3),
            "actual_processed_duration": round(selected_duration, 3),
            "actual_video_speed": round(float(problem_segment.get("video_speed") or (preferred_duration / selected_duration if selected_duration else 0.0)), 3),
            "minimum_safe_processed_duration": round(minimum_safe_duration, 3),
            "maximum_safe_processed_duration": round(maximum_safe_duration, 3),
            "preferred_processed_duration": round(preferred_duration, 3),
            "missing_seconds_to_safe_minimum": round(missing_seconds, 3),
            "excess_seconds_over_safe_maximum": round(excess_seconds, 3),
            "problem": problem,
            "repair_intensity": "strong_expand" if problem == "too_short_audio" else "compress",
            "previous_max_word_count": previous_max_word_count,
            "previous_candidates": previous_candidates,
            "previous_candidate_timings": previous_timings,
            "all_previous_candidate_count": len(previous_timings),
            "best_previous_candidate_timing": problem_segment.get("best_previous_candidate_timing") or {},
            "hedef_kelime": target_words,
            "kelime_aralik": f"{max(1, round(target_words * 0.75))}-{max(1, round(target_words * 1.25))}",
            "timing_acceptance": {"min_ratio": 0.9, "max_ratio": 1.15},
            "target_word_count": target_words,
            "profile_target_word_count": target_words,
            "profile_required_word_range": f"{max(1, round(target_words * 0.87))}-{max(1, round(target_words * 1.13))}",
            "source_word_count": hedef_dil.kelime_esdegeri(selected_text, self.target_lang),
            "minimum_fill_word_count": max(1, round(target_words * 0.87)),
            "maximum_fill_word_count": max(1, round(target_words * 1.13)),
            "hard_minimum_word_count": max(1, round(target_words * 0.87)),
            "recommended_word_range": f"{max(1, round(target_words * 0.87))}-{max(1, round(target_words * 1.13))}",
            "invalid_if_below_word_count": max(1, round(target_words * 0.87)),
            "candidate_word_count_targets": [
                max(1, round(target_words * 0.87)),
                target_words,
                max(1, round(target_words * 1.13)),
                repair_target_words,
            ],
            "too_short_below_words": max(1, round(target_words * 0.87)),
            "timing_feasibility": "timing_limited",
            "timing_contract": "Bu segmentte video timing hedefi ana kalite şartıdır; mevcut "
            + hedef_dil.dil_adi(self.target_lang)
            + " replik hedef süreye göre yeniden kurulmalıdır.",
            "duration_strategy": "Mevcut "
            + hedef_dil.dil_adi(self.target_lang)
            + " repliğin anlamını koru; problem too_short_audio ise daha dolu, problem too_long_audio ise daha kompakt doğal "
            + hedef_dil.dil_adi(self.target_lang)
            + " adaylar üret.",
            "fragment_guidance": "",
            "repair_minimum_word_count": repair_minimum_words,
            "repair_target_word_count": repair_target_words,
            "repair_recommended_word_range": f"{repair_minimum_words}-{repair_max_words}",
            "repair_word_count_strategy": "Gerçek TTS ölçümünden gelen önceki aday sürelerini kullan; aynı cümle iskeletini tekrar etme.",
        }

    def _build_real_tts_repair_job(
        self,
        repair_segments: List[dict],
        repair_round: int,
        job_id: str,
        candidate_count: int,
        discourse_segments: List[dict] | None = None,
        chunk_number: int | None = None,
        total_chunks: int | None = None,
    ) -> dict:
        options = {
            "candidate_count": candidate_count,
            "mode": "timing_repair",
            "repair_round": repair_round,
            "measurement_source": "real_final_tts",
        }
        if chunk_number is not None and total_chunks is not None:
            options.update({
                "chunk_number": chunk_number,
                "total_chunks": total_chunks,
                "parallel_repair": True,
            })
        job = {
            "job_id": job_id,
            "task_type": "translation_candidates",
            "source_lang": self.target_lang,
            "target_lang": self.target_lang,
            "voice": self._voice_payload(),
            "options": options,
            "repair_instruction": (
                "Bu iş baştan bağımsız çeviri değildir; hedef dildeki mevcut repliği zamanlama için yeniden kurma işidir. "
                "segments[].text alanı mevcut hedef dil repliğidir. "
                "segments[].original_source_text ana kaynak dil metnidir ve anlamı güvenle açmak için kullanılmalıdır. "
                "segments[].source_context_before ve segments[].source_context_after sadece bağlamdır; komşu segment bilgisini bu segmente taşıma. "
                "Önceki adaylar gerçek final TTS zincirinde ölçüldü: seçili TTS motoru, motor içi hız ayarı ve final WAV süresi. "
                "previous_candidate_timings alanında bu segment için o ana kadar üretilmiş tüm ölçülmüş adaylar bulunabilir. "
                "previous_candidate_timings alanındaki duration değeri final işlenmiş ses süresidir. "
                "best_previous_candidate_timing varsa şu ana kadarki en iyi ölçülmüş adaydır; yeni adaylar bu adayı tekrar etmek yerine daha iyi süre uyumu hedeflemelidir. "
                "Süre alanlarını yardımcı hedef olarak kullan; süreye uymak için ana anlamı, niyeti veya doğal "
                + hedef_dil.dil_adi(self.target_lang, "yi")
                + " bozma. "
                "too_short_audio için önce kaynakta bulunan fakat mevcut replikte sıkışmış anlamı doğal biçimde aç. "
                "too_long_audio için önce gereksiz dolgu ve tekrarları çıkararak anlamı koruyan kompakt "
                + hedef_dil.dil_adi(self.target_lang)
                + " kur. "
                "Aynı cümle iskeletini, aynı kelime dizilimini veya sadece eş anlamlı kelime değişimini kullanma. "
                "Kaynak anlam dışına çıkma, yeni bilgi ve yeni olay ekleme. Repair yalnızca süre iyileşti diye başarılı sayılmaz; "
                "bütün konuşmanın niyeti, neden-sonuç ilişkisi, öznesi, tutumu ve doğal akışı korunmalıdır."
            ),
            "segments": repair_segments,
        }
        if discourse_segments:
            job["discourse_segments"] = discourse_segments
        return job

    def _build_supertonic_whole_chain_repair_segment(
        self,
        seg,
        problem_segment: dict,
        candidates: List[str],
        target_context_before: str = "",
        target_context_after: str = "",
    ) -> dict:
        seg_id = str(problem_segment.get("segment_id") or self._segment_id(seg, 0))
        target_duration = max(
            float(problem_segment.get("source_duration") or self._segment_duration(seg) or 0.0),
            0.1,
        )
        current_duration = float(
            problem_segment.get("selected_processed_duration")
            or problem_segment.get("selected_duration")
            or 0.0
        )
        problem = str(problem_segment.get("problem") or problem_segment.get("status") or "").strip()
        if problem not in {"too_short_audio", "too_long_audio"}:
            problem = "too_short_audio" if current_duration < target_duration / 1.15 else "too_long_audio"
        current_text = str(
            problem_segment.get("selected_text")
            or self.current_target_by_id.get(seg_id)
            or self._segment_text(seg)
        ).strip()
        canonical_text = str(self.canonical_target_by_id.get(seg_id) or current_text).strip()
        previous_candidates = []
        seen = set()
        for item in problem_segment.get("all_previous_candidate_timings") or problem_segment.get("candidates") or []:
            text = str(item.get("text") or "").strip()
            if not text or text in seen:
                continue
            duration = float(item.get("duration") or item.get("processed_duration") or 0.0)
            previous_candidates.append({
                "text": text,
                "duration": round(duration, 3),
                "status": str(item.get("status") or ""),
            })
            seen.add(text)
        for text in candidates:
            clean_text = str(text or "").strip()
            if clean_text and clean_text not in seen:
                previous_candidates.append({"text": clean_text})
                seen.add(clean_text)
        return {
            "id": self._segment_id(seg, int(seg_id) if seg_id.isdigit() else 0),
            "canonical_text": canonical_text,
            "text": current_text,
            "context_before": str(target_context_before or "").strip(),
            "context_after": str(target_context_after or "").strip(),
            "problem": problem,
            "target_duration": round(target_duration, 3),
            "current_duration": round(current_duration, 3),
            "safe_duration_range": {
                "minimum": round(target_duration / 1.15, 3),
                "maximum": round(target_duration / 0.90, 3),
            },
            "previous_candidates": previous_candidates,
        }

    def _build_supertonic_whole_chain_repair_job(
        self,
        repair_segments: List[dict],
        repair_round: int,
        job_id: str,
        candidate_count: int,
        canonical_target_segments: List[dict],
        current_target_segments: List[dict],
        discourse_segments: List[dict],
        chunk_number: int | None = None,
        total_chunks: int | None = None,
    ) -> dict:
        options = {
            "candidate_count": candidate_count,
            "mode": "whole_chain_timing_repair",
            "repair_round": repair_round,
            "measurement_source": "real_final_tts",
            "prompt_mode": SUPERTONIC_WHOLE_CHAIN_REPAIR_MODE,
        }
        if chunk_number is not None and total_chunks is not None:
            options.update({
                "chunk_number": chunk_number,
                "total_chunks": total_chunks,
                "parallel_repair": True,
            })
        return {
            "job_id": job_id,
            "task_type": "translation_candidates",
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "voice": self._voice_payload(),
            "options": options,
            "canonical_target_segments": canonical_target_segments,
            "current_target_segments": current_target_segments,
            "segments": repair_segments,
            "discourse_segments": discourse_segments,
        }

    def repair_candidates_with_real_tts(
        self,
        segments: List,
        by_id: Dict[str, List[str]],
        problem_segments: List[dict],
        run_dir: str,
        repair_round: int,
        current_target_by_id: Dict[str, str] | None = None,
    ) -> Tuple[Dict[str, List[str]], dict]:
        self.set_current_target_chain(current_target_by_id or {})
        segment_by_id = {str(self._segment_id(seg, fallback_id)): seg for fallback_id, seg in enumerate(segments)}
        ordered_segment_ids = [str(self._segment_id(seg, fallback_id)) for fallback_id, seg in enumerate(segments)]
        target_context_by_id = {}
        for index, seg_id in enumerate(ordered_segment_ids):
            before_id = ordered_segment_ids[index - 1] if index > 0 else ""
            after_id = ordered_segment_ids[index + 1] if index + 1 < len(ordered_segment_ids) else ""
            target_context_by_id[seg_id] = {
                "before": self.current_target_by_id.get(before_id, "") if before_id else "",
                "after": self.current_target_by_id.get(after_id, "") if after_id else "",
            }
        source_context_by_id = {}
        for fallback_id, seg in enumerate(segments):
            seg_id = str(self._segment_id(seg, fallback_id))
            source_context_by_id[seg_id] = {
                "before": self._segment_source_text(segments[fallback_id - 1]) if fallback_id > 0 else "",
                "after": self._segment_source_text(segments[fallback_id + 1]) if fallback_id + 1 < len(segments) else "",
            }
        repair_segments = []
        discourse_segments = self._build_source_discourse_segments(segments)
        for problem_segment in problem_segments:
            seg_id = str(problem_segment.get("segment_id") or "").strip()
            if not seg_id or seg_id not in segment_by_id:
                continue
            candidates = self._clean_candidates(
                segment_by_id[seg_id],
                by_id.get(seg_id, []),
                f"real_tts_repair_precheck_r{repair_round}",
            )
            if self._whole_chain_repair_enabled():
                target_context = target_context_by_id.get(seg_id, {})
                repair_segments.append(self._build_supertonic_whole_chain_repair_segment(
                    segment_by_id[seg_id],
                    problem_segment,
                    candidates,
                    target_context.get("before", ""),
                    target_context.get("after", ""),
                ))
            else:
                source_context = source_context_by_id.get(seg_id, {})
                repair_segments.append(self._build_real_tts_repair_segment(
                    segment_by_id[seg_id],
                    problem_segment,
                    candidates,
                    source_context.get("before", ""),
                    source_context.get("after", ""),
                ))

        repair_root = Path(run_dir) / "codex_bridge_translation" / f"real_tts_repair_r{repair_round}"
        repair_root.mkdir(parents=True, exist_ok=True)
        summary = {
            "status": "success",
            "round": repair_round,
            "mode": "supertonic_whole_chain_repair" if self._whole_chain_repair_enabled() else "real_tts_timing_repair",
            "total_problem_segments": len(repair_segments),
            "chunk_count": 0,
            "max_parallel_jobs": self.repair_max_parallel_jobs,
            "actual_parallel_jobs": 0,
            "failed_chunks": [],
            "chunks": [],
            "repaired_count": 0,
        }
        if not repair_segments:
            (repair_root / "parallel_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            return by_id, summary

        chunks = self._chunk_repair_segments(repair_segments)
        canonical_target_segments = [
            {
                "id": str(self._segment_id(seg, fallback_id)),
                "text": str(
                    self.canonical_target_by_id.get(str(self._segment_id(seg, fallback_id)))
                    or self.current_target_by_id.get(str(self._segment_id(seg, fallback_id)))
                    or self._segment_text(seg)
                ).strip(),
            }
            for fallback_id, seg in enumerate(segments)
        ]
        current_target_segments = [
            {
                "id": str(self._segment_id(seg, fallback_id)),
                "text": str(
                    self.current_target_by_id.get(str(self._segment_id(seg, fallback_id)))
                    or self.canonical_target_by_id.get(str(self._segment_id(seg, fallback_id)))
                    or self._segment_text(seg)
                ).strip(),
            }
            for fallback_id, seg in enumerate(segments)
        ]
        total_chunks = len(chunks)
        max_workers = min(self.repair_max_parallel_jobs, total_chunks)
        summary["chunk_count"] = total_chunks
        summary["actual_parallel_jobs"] = max_workers
        logger.info(
            "Ceviri orkestratoru gercek TTS repair plan: round=%d problemli=%d chunk=%d worker=%d",
            repair_round,
            len(repair_segments),
            total_chunks,
            max_workers,
        )

        def process_chunk(chunk_number: int, chunk_segments: List[dict]) -> dict:
            candidate_count = self._repair_candidate_count_for_segments(chunk_segments)
            log_subdir = f"real_tts_repair_r{repair_round}" if total_chunks == 1 else f"real_tts_repair_r{repair_round}/chunk_{chunk_number:03d}"
            job_id = f"codex_bridge_real_tts_repair_r{repair_round}_{int(time.time())}"
            if total_chunks > 1:
                job_id = f"{job_id}_c{chunk_number:03d}"
            if self._whole_chain_repair_enabled():
                repair_job = self._build_supertonic_whole_chain_repair_job(
                    chunk_segments,
                    repair_round,
                    job_id,
                    candidate_count,
                    canonical_target_segments,
                    current_target_segments,
                    discourse_segments,
                    chunk_number=chunk_number if total_chunks > 1 else None,
                    total_chunks=total_chunks if total_chunks > 1 else None,
                )
            else:
                repair_job = self._build_real_tts_repair_job(
                    chunk_segments,
                    repair_round,
                    job_id,
                    candidate_count,
                    discourse_segments=discourse_segments,
                    chunk_number=chunk_number if total_chunks > 1 else None,
                    total_chunks=total_chunks if total_chunks > 1 else None,
                )
            repair_dir = repair_root if total_chunks == 1 else repair_root / f"chunk_{chunk_number:03d}"
            repair_dir.mkdir(parents=True, exist_ok=True)
            repair_path = repair_dir / "request.json"
            repair_path.write_text(json.dumps(repair_job, ensure_ascii=False, indent=2), encoding="utf-8")
            result_path = self._run_bridge(
                repair_path,
                run_dir,
                log_subdir=log_subdir,
                result_filename="result.json",
            )
            data = json.loads(result_path.read_text(encoding="utf-8"))
            translations = data.get("translations") or []
            cleaned_by_id = {}
            repaired_count = 0
            for item in translations:
                item_id = str(item.get("id"))
                if item_id not in segment_by_id:
                    continue
                cleaned = self._clean_candidates(
                    segment_by_id[item_id],
                    item.get("candidates", []),
                    f"real_tts_repair_r{repair_round}",
                )
                if cleaned:
                    cleaned_by_id[item_id] = cleaned
                    repaired_count += 1
            return {
                "chunk_number": chunk_number,
                "segment_count": len(chunk_segments),
                "repaired_count": repaired_count,
                "by_id": cleaned_by_id,
                "result_path": str(result_path),
            }

        repaired_by_id: Dict[str, List[str]] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_chunk, chunk_number, chunk_segments): chunk_number
                for chunk_number, chunk_segments in enumerate(chunks, start=1)
            }
            for future in as_completed(futures):
                chunk_number = futures[future]
                try:
                    result = future.result()
                    repaired_by_id.update(result["by_id"])
                    summary["repaired_count"] += result["repaired_count"]
                    summary["chunks"].append({
                        "chunk_number": result["chunk_number"],
                        "segment_count": result["segment_count"],
                        "repaired_count": result["repaired_count"],
                        "result_path": result["result_path"],
                    })
                    logger.info(
                        "Ceviri orkestratoru gercek TTS repair chunk tamamlandi: round=%d chunk=%d/%d segment=%d yenilenen=%d",
                        repair_round,
                        result["chunk_number"],
                        total_chunks,
                        result["segment_count"],
                        result["repaired_count"],
                    )
                except Exception as exc:
                    summary["status"] = "partial"
                    summary["failed_chunks"].append(chunk_number)
                    error_dir = repair_root / f"chunk_{chunk_number:03d}"
                    error_dir.mkdir(parents=True, exist_ok=True)
                    (error_dir / "error.txt").write_text(f"Hata: {exc}\n", encoding="utf-8")
                    logger.warning(
                        "Ceviri orkestratoru gercek TTS repair chunk basarisiz: round=%d chunk=%d/%d error=%s",
                        repair_round,
                        chunk_number,
                        total_chunks,
                        exc,
                    )
        for seg_id, repaired_candidates in repaired_by_id.items():
            current = by_id.setdefault(str(seg_id), [])
            for candidate in repaired_candidates:
                text = str(candidate or "").strip()
                if text and text not in current:
                    current.append(text)
        summary["chunks"] = sorted(summary["chunks"], key=lambda item: item["chunk_number"])
        (repair_root / "parallel_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return by_id, summary

    def _read_candidates_result(self, result_path: Path) -> Dict[str, List[str]]:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        if data.get("status") not in {"success", "partial"}:
            raise RuntimeError(f"Ceviri motoru result basarisiz: {data.get('status')} {data.get('notes', '')}")
        translations = data.get("translations") or []
        by_id: Dict[str, List[str]] = {}
        for item in translations:
            by_id[str(item.get("id"))] = [str(candidate).strip() for candidate in item.get("candidates", []) if str(candidate).strip()]
        return by_id

    def _capture_canonical_target_chain(self, segments: List, by_id: Dict[str, List[str]]) -> None:
        if not self._whole_chain_repair_enabled() or self.canonical_target_by_id:
            return
        for fallback_id, seg in enumerate(segments):
            seg_id = str(self._segment_id(seg, fallback_id))
            candidates = by_id.get(seg_id, [])
            if candidates:
                self.canonical_target_by_id[seg_id] = str(candidates[0]).strip()

    def _anchor_candidates_to_canonical(
        self,
        canonical_by_id: Dict[str, List[str]],
        candidates_by_id: Dict[str, List[str]],
    ) -> Dict[str, List[str]]:
        anchored = {}
        for seg_id, canonical_values in canonical_by_id.items():
            canonical_text = str(canonical_values[0] if canonical_values else "").strip()
            values = []
            for text in [canonical_text, *(candidates_by_id.get(str(seg_id), []) or [])]:
                clean_text = str(text or "").strip()
                if clean_text and clean_text not in values:
                    values.append(clean_text)
            anchored[str(seg_id)] = values[:self.candidate_count]
        return anchored

    def set_current_target_chain(self, values: Dict[str, str]) -> None:
        if not self._whole_chain_repair_enabled():
            return
        for seg_id, text in (values or {}).items():
            clean_text = str(text or "").strip()
            if clean_text:
                self.current_target_by_id[str(seg_id)] = clean_text

    def _select_translations(
        self,
        segments: List,
        by_id: Dict[str, List[str]],
        timing_context=None,
    ) -> List[str]:
        results = []
        missing_ids = []
        for fallback_id, seg in enumerate(segments):
            seg_id = str(self._segment_id(seg, fallback_id))
            candidates = by_id.get(seg_id, [])
            if not any(str(candidate or "").strip() for candidate in candidates):
                missing_ids.append(seg_id)
                continue
            selected = self._rank_candidates(seg, candidates, timing_context)
            if selected and not is_source_like_translation(self._segment_text(seg), selected):
                results.append(selected)
            else:
                logger.warning("Ceviri motoru adaylari kaynakla ayni, kaynak korunuyor: seg=%s", seg_id)
                results.append(self._segment_text(seg))
        if missing_ids:
            raise CeviriEksikSegmentError(
                f"Ceviri motoru {len(missing_ids)}/{len(segments)} segment icin ceviri dondurmedi: "
                f"{', '.join(missing_ids[:10])}"
            )
        return results

    def _parse_result(self, result_path: Path, segments: List, run_dir: str = "", base_job: dict | None = None) -> List[str]:
        by_id = self._read_candidates_result(result_path)
        self._capture_canonical_target_chain(segments, by_id)

        timing_context = None

        self.last_candidates_by_id = {str(key): list(value) for key, value in by_id.items()}
        return self._select_translations(segments, by_id, timing_context)

    def _chunk_segments(self, segments: List) -> List[dict]:
        chunks = []
        total = len(segments)
        for start in range(0, total, self.group_size):
            end = min(start + self.group_size, total)
            before_start = max(0, start - self.context_size)
            after_end = min(total, end + self.context_size)
            chunks.append({
                "group_number": len(chunks) + 1,
                "segments": segments[start:end],
                "context_before": segments[before_start:start],
                "context_after": segments[end:after_end],
            })
        return chunks

    def _translate_parallel_candidates(self, segments: List, run_dir: str, base_job_id: str) -> Tuple[Dict[str, List[str]], dict]:
        started_total = time.time()
        chunks = self._chunk_segments(segments)
        total_groups = len(chunks)
        max_workers = min(self.max_parallel_jobs, total_groups)
        motor_adi = _backend_box_name(self.bridge_backend or _bridge_backend())
        logger.info("=" * 60)
        logger.info("BRIDGE MOTOR ORKESTRATORU PARALEL CEVIRI PLANI")
        logger.info("=" * 60)
        logger.info("Ceviri Orkestratoru: %s", BRIDGE_ORKESTRATORU_ADI)
        logger.info("Ceviri Motoru: %s", motor_adi)
        logger.info(
            "Toplam segment: %d",
            len(segments),
        )
        logger.info(
            "Grup sayisi: %d",
            total_groups,
        )
        logger.info(
            "Grup boyutu: %d ana segment",
            self.group_size,
        )
        logger.info(
            "Baglam: %d once + %d sonra",
            self.context_size,
            self.context_size,
        )
        logger.info(
            "Paralel job: %d",
            max_workers,
        )
        logger.info(
            "Aday sayisi: %d",
            self.candidate_count,
        )
        for chunk in chunks:
            main_ids = [self._segment_id(seg, idx) for idx, seg in enumerate(chunk["segments"])]
            before_ids = [self._segment_id(seg, idx) for idx, seg in enumerate(chunk["context_before"])]
            after_ids = [self._segment_id(seg, idx) for idx, seg in enumerate(chunk["context_after"])]
            logger.info(
                "Grup %03d plan: main=%s-%s main_count=%d before=%s after=%s",
                chunk["group_number"],
                main_ids[0],
                main_ids[-1],
                len(main_ids),
                before_ids,
                after_ids,
            )
        logger.info("=" * 60)
        logger.info(
            "Ceviri orkestratoru paralel ceviri: motor=%s segment=%d grup=%d grup_boyutu=%d baglam=%d worker=%d",
            motor_adi,
            len(segments),
            total_groups,
            self.group_size,
            self.context_size,
            max_workers,
        )

        def process_chunk(chunk: dict) -> dict:
            started_group = time.time()
            group_number = chunk["group_number"]
            log_subdir = f"group_{group_number:03d}"
            job_id = f"{base_job_id}_g{group_number:03d}"
            main_ids = [self._segment_id(seg, idx) for idx, seg in enumerate(chunk["segments"])]
            before_ids = [self._segment_id(seg, idx) for idx, seg in enumerate(chunk["context_before"])]
            after_ids = [self._segment_id(seg, idx) for idx, seg in enumerate(chunk["context_after"])]
            logger.info(
                "Ceviri motoru grubu %d/%d basliyor: main=%s-%s main_count=%d before=%s after=%s",
                group_number,
                total_groups,
                main_ids[0],
                main_ids[-1],
                len(main_ids),
                before_ids,
                after_ids,
            )
            job = self._build_job(
                chunk["segments"],
                job_id,
                context_before=chunk["context_before"],
                context_after=chunk["context_after"],
                discourse_segments=segments,
                group_number=group_number,
                total_groups=total_groups,
            )
            transient_events = []
            retry_attempt = 0
            while True:
                job_path = self._write_job(run_dir, job, log_subdir=log_subdir)
                try:
                    result_path = self._run_bridge(job_path, run_dir, log_subdir=log_subdir)
                    by_id = self._read_candidates_result(result_path)
                    canonical_by_id = {}
                    if self._whole_chain_repair_enabled():
                        canonical_by_id = {str(key): list(value) for key, value in by_id.items()}
                        candidate_job = self._build_supertonic_whole_chain_candidate_job(
                            chunk["segments"],
                            canonical_by_id,
                            f"{job_id}_candidates",
                            segments,
                            group_number=group_number,
                            total_groups=total_groups,
                        )
                        candidate_log_subdir = f"{log_subdir}/whole_chain_candidates"
                        candidate_job_path = self._write_job(run_dir, candidate_job, log_subdir=candidate_log_subdir)
                        result_path = self._run_bridge(
                            candidate_job_path,
                            run_dir,
                            log_subdir=candidate_log_subdir,
                            result_filename="result.json",
                        )
                        by_id = self._read_candidates_result(result_path)
                        by_id = self._anchor_candidates_to_canonical(canonical_by_id, by_id)
                        job = candidate_job
                    expected_ids = {str(self._segment_id(seg, fallback_id)) for fallback_id, seg in enumerate(chunk["segments"])}
                    filtered = {seg_id: candidates for seg_id, candidates in by_id.items() if seg_id in expected_ids}
                    missing_ids = sorted(expected_ids - set(filtered))
                    empty_candidate_ids = sorted(
                        seg_id for seg_id in expected_ids if seg_id in filtered and not filtered[seg_id]
                    )
                    incomplete_ids = sorted(set(missing_ids) | set(empty_candidate_ids))
                    if incomplete_ids:
                        raise CeviriOrkestratoruGroupTransientError(
                            f"Ceviri motoru grubu eksik veya bos aday dondurdu: {incomplete_ids[:10]}",
                            error_type="translation_result_incomplete",
                            retry_reason="missing_or_empty_candidates",
                            details={
                                "missing_ids": missing_ids,
                                "empty_candidate_ids": empty_candidate_ids,
                            },
                        )
                    break
                except CeviriOrkestratoruGroupTransientError as exc:
                    event = {
                        "group_number": group_number,
                        "attempt": retry_attempt + 1,
                        "error_type": exc.error_type,
                        "retry_reason": exc.retry_reason,
                        "retry_after_seconds": exc.retry_after_seconds,
                    }
                    if retry_attempt >= self.group_transient_retries:
                        event["status"] = "exhausted"
                        transient_events.append(event)
                        logger.error(
                            "Ceviri motoru grubu %d/%d gecici hata retry limiti doldu: type=%s reason=%s",
                            group_number,
                            total_groups,
                            exc.error_type,
                            exc.retry_reason,
                        )
                        raise
                    wait_seconds = self._group_transient_backoff_seconds(retry_attempt)
                    event["status"] = "retrying"
                    event["wait_seconds"] = wait_seconds
                    transient_events.append(event)
                    retry_attempt += 1
                    logger.warning(
                        "Ceviri motoru grubu %d/%d gecici hata aldi, %.3fs sonra tekrar denenecek: attempt=%d/%d type=%s reason=%s",
                        group_number,
                        total_groups,
                        wait_seconds,
                        retry_attempt,
                        self.group_transient_retries,
                        exc.error_type,
                        exc.retry_reason,
                    )
                    if wait_seconds > 0:
                        time.sleep(wait_seconds)
            context_ids = {str(seg_id) for seg_id in before_ids + after_ids}
            extra_ids = sorted(set(by_id) - expected_ids)
            context_returned_ids = sorted(set(extra_ids) & context_ids)
            unknown_extra_ids = sorted(set(extra_ids) - context_ids)
            if context_returned_ids:
                logger.info(
                    "Ceviri motoru grubu %d ana segment disi baglam id filtrelendi: %s",
                    group_number,
                    context_returned_ids[:10],
                )
            if unknown_extra_ids:
                logger.warning(
                    "Ceviri motoru grubu %d beklenmeyen id dondurdu, filtrelendi: %s",
                    group_number,
                    unknown_extra_ids[:10],
                )
            filtered = {seg_id: candidates for seg_id, candidates in by_id.items() if seg_id in expected_ids}
            elapsed = time.time() - started_group
            return {
                "group_number": group_number,
                "job": job,
                "by_id": filtered,
                "canonical_by_id": canonical_by_id,
                "missing_ids": missing_ids,
                "extra_ids": extra_ids,
                "context_returned_ids": context_returned_ids,
                "unknown_extra_ids": unknown_extra_ids,
                "result_path": str(result_path),
                "duration_seconds": round(elapsed, 3),
                "main_start_id": main_ids[0],
                "main_end_id": main_ids[-1],
                "main_count": len(main_ids),
                "context_before_ids": before_ids,
                "context_after_ids": after_ids,
                "candidate_segment_count": len(filtered),
                "transient_retry_count": retry_attempt,
                "transient_events": transient_events,
            }

        merged: Dict[str, List[str]] = {}
        canonical_merged: Dict[str, str] = {}
        group_jobs = []
        group_summaries = []
        failed_groups = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_chunk, chunk): chunk for chunk in chunks}
            for future in as_completed(futures):
                chunk = futures[future]
                group_number = chunk["group_number"]
                try:
                    result = future.result()
                    group_jobs.append(result["job"])
                    group_summaries.append({
                        "group_number": result["group_number"],
                        "main_start_id": result["main_start_id"],
                        "main_end_id": result["main_end_id"],
                        "main_count": result["main_count"],
                        "context_before_ids": result["context_before_ids"],
                        "context_after_ids": result["context_after_ids"],
                        "candidate_segment_count": result["candidate_segment_count"],
                        "missing_ids": result["missing_ids"],
                        "extra_ids": result["extra_ids"],
                        "context_returned_ids": result["context_returned_ids"],
                        "unknown_extra_ids": result["unknown_extra_ids"],
                        "duration_seconds": result["duration_seconds"],
                        "result_path": result["result_path"],
                        "transient_retry_count": result["transient_retry_count"],
                        "transient_events": result["transient_events"],
                    })
                    for seg_id, candidates in result["by_id"].items():
                        if seg_id in merged:
                            logger.warning("Ceviri motoru duplicate segment id: seg=%s group=%d", seg_id, group_number)
                        merged[seg_id] = candidates
                    for seg_id, candidates in result["canonical_by_id"].items():
                        if candidates:
                            canonical_merged[str(seg_id)] = str(candidates[0]).strip()
                    if result["missing_ids"]:
                        logger.warning("Ceviri motoru grubu %d eksik segment id: %s", group_number, result["missing_ids"][:10])
                    logger.info(
                        "Ceviri motoru grubu %d/%d tamamlandi: sure=%.3fs aday_segment=%d eksik=%d fazla=%d result=%s",
                        group_number,
                        total_groups,
                        result["duration_seconds"],
                        result["candidate_segment_count"],
                        len(result["missing_ids"]),
                        len(result["extra_ids"]),
                        result["result_path"],
                    )
                except Exception as exc:
                    failed_groups.append(group_number)
                    logger.error("Ceviri motoru grubu %d/%d basarisiz: %s", group_number, total_groups, exc)

        expected_all = {str(self._segment_id(seg, fallback_id)) for fallback_id, seg in enumerate(segments)}
        missing_all = sorted(expected_all - set(merged))
        if missing_all:
            logger.warning("Ceviri orkestratoru paralel sonuc eksik id sayisi=%d ilk=%s", len(missing_all), missing_all[:10])
        elapsed_total = time.time() - started_total
        summary = {
            "job_id": base_job_id,
            "status": "failed" if failed_groups else "success",
            "total_segments": len(segments),
            "translated_candidate_segments": len(merged),
            "group_size": self.group_size,
            "context_size": self.context_size,
            "max_parallel_jobs": self.max_parallel_jobs,
            "actual_parallel_jobs": max_workers,
            "group_count": total_groups,
            "missing_ids": missing_all,
            "failed_groups": failed_groups,
            "duration_seconds": round(elapsed_total, 3),
            "groups": sorted(group_summaries, key=lambda item: item["group_number"]),
        }
        summary_path = Path(run_dir) / "codex_bridge_translation" / "parallel_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("=" * 60)
        logger.info("BRIDGE MOTOR ORKESTRATORU PARALEL CEVIRI SONUCU")
        logger.info("=" * 60)
        logger.info("Ceviri Orkestratoru: %s", BRIDGE_ORKESTRATORU_ADI)
        logger.info("Ceviri Motoru: %s", motor_adi)
        logger.info("Job ID: %s", base_job_id)
        logger.info("Toplam segment: %d", len(segments))
        logger.info("Aday donen segment: %d", len(merged))
        logger.info("Grup sayisi: %d", total_groups)
        logger.info("Basarisiz grup: %s", failed_groups if failed_groups else "YOK")
        logger.info("Eksik id sayisi: %d", len(missing_all))
        if missing_all:
            logger.info("Eksik id ilk: %s", missing_all[:10])
        logger.info("Toplam sure: %.3fs", elapsed_total)
        logger.info("Ozet dosyasi: %s", summary_path)
        logger.info("=" * 60)

        if failed_groups:
            raise RuntimeError(f"Ceviri orkestratoru paralel grup basarisiz: {failed_groups}")

        if self._whole_chain_repair_enabled():
            self.canonical_target_by_id = canonical_merged

        base_job = {
            "job_id": base_job_id,
            "task_type": "translation_candidates",
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "voice": self._voice_payload(),
            "options": {
                "candidate_count": self.candidate_count,
                "group_size": self.group_size,
                "context_size": self.context_size,
                "max_parallel_jobs": self.max_parallel_jobs,
                **({"prompt_mode": self.prompt_mode} if self.prompt_mode else {}),
            },
            "segments": [item for job in sorted(group_jobs, key=lambda value: value.get("options", {}).get("group_number", 0)) for item in job.get("segments", [])],
        }
        return merged, base_job

    def translate_segments(self, segments: List, output_dir: str = None) -> List[str]:
        if not segments:
            return []
        run_dir = output_dir or str(PROJECT_ROOT / "output" / f"codex_bridge_{int(time.time())}")
        job_id = f"codex_bridge_{Path(run_dir).name}_{int(time.time())}"
        motor_adi = _backend_box_name(self.bridge_backend or _bridge_backend())
        logger.info(
            "Ceviri orkestratoru basliyor: orkestrator=%s motor=%s segment=%d job=%s",
            BRIDGE_ORKESTRATORU_ADI,
            motor_adi,
            len(segments),
            job_id,
        )
        if len(segments) <= self.group_size:
            job = self._build_job(segments, job_id)
            job_path = self._write_job(run_dir, job)
            result_path = self._run_bridge(job_path, run_dir)
            if self._whole_chain_repair_enabled():
                canonical_by_id = self._read_candidates_result(result_path)
                self._capture_canonical_target_chain(segments, canonical_by_id)
                candidate_job = self._build_supertonic_whole_chain_candidate_job(
                    segments,
                    canonical_by_id,
                    f"{job_id}_candidates",
                    segments,
                )
                candidate_job_path = self._write_job(run_dir, candidate_job, log_subdir="whole_chain_candidates")
                candidate_result_path = self._run_bridge(
                    candidate_job_path,
                    run_dir,
                    log_subdir="whole_chain_candidates",
                    result_filename="result.json",
                )
                by_id = self._read_candidates_result(candidate_result_path)
                by_id = self._anchor_candidates_to_canonical(canonical_by_id, by_id)
                timing_context = None
                self.last_candidates_by_id = {str(key): list(value) for key, value in by_id.items()}
                translated = self._select_translations(segments, by_id, timing_context)
                result_label = str(candidate_result_path)
            else:
                translated = self._parse_result(result_path, segments, run_dir, job)
                result_label = str(result_path)
        else:
            by_id, base_job = self._translate_parallel_candidates(segments, run_dir, job_id)
            self._capture_canonical_target_chain(segments, by_id)
            timing_context = None
            self.last_candidates_by_id = {str(key): list(value) for key, value in by_id.items()}
            translated = self._select_translations(segments, by_id, timing_context)
            result_label = "parallel_groups"
        self.set_current_target_chain({
            str(self._segment_id(seg, fallback_id)): translated[fallback_id]
            for fallback_id, seg in enumerate(segments)
            if fallback_id < len(translated)
        })
        self.last_video_usage_report = self._write_video_usage_report(
            run_dir,
            job_id,
            result_label,
            len(segments),
        )
        logger.info(
            "Ceviri orkestratoru tamamlandi: orkestrator=%s motor=%s segment=%d result=%s",
            BRIDGE_ORKESTRATORU_ADI,
            motor_adi,
            len(translated),
            result_label,
        )
        return translated


class FullTextBridgeTranslator(BridgeMotorOrkestratoruTranslator):
    def __init__(
        self,
        target_lang: str,
        source_lang: str,
        timeout_seconds: int = 900,
        bridge_backend: str = "",
    ):
        super().__init__(
            target_lang=target_lang,
            source_lang=source_lang,
            candidate_count=1,
            repair_candidate_count=0,
            timeout_seconds=timeout_seconds,
            timing_selection=False,
            tts_engine="supertonic",
            prompt_mode="full_text_translation",
            bridge_backend=bridge_backend,
        )

    def translate_full_text(self, source_text: str, output_dir: str) -> str:
        normalized_source_text = str(source_text or "").strip()
        if not normalized_source_text:
            raise ValueError("Full metin cevirisi icin kaynak metin bos olamaz")
        run_dir = str(output_dir)
        job_id = f"full_text_translation_{Path(run_dir).name}_{int(time.time())}"
        bridge_backend = self.bridge_backend or _bridge_backend()
        if bridge_backend not in FULL_TEXT_SUPPORTED_BRIDGE_BACKENDS:
            raise ValueError(
                "Full Metin Dublaji yalniz su ceviri motorlariyla calisir: "
                + ", ".join(sorted(FULL_TEXT_SUPPORTED_BRIDGE_BACKENDS))
            )
        job = {
            "job_id": job_id,
            "task_type": "full_text_translation",
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "source_text": normalized_source_text,
            "options": {"prompt_mode": "full_text_translation"},
        }
        job_path = self._write_job(run_dir, job, log_subdir="full_text_translation")
        result_path = self._run_bridge(
            job_path,
            run_dir,
            log_subdir="full_text_translation",
            result_filename="result.json",
        )
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("status") != "success":
            raise RuntimeError(f"Full metin cevirisi basarisiz: {result.get('status')}")
        translated_text = str(result.get("translated_text") or "").strip()
        if not translated_text:
            raise RuntimeError("Full metin cevirisi bos sonuc dondurdu")
        self.last_video_usage_report = self._write_video_usage_report(
            run_dir,
            job_id,
            str(result_path),
            1,
        )
        logger.info(
            "Full metin cevirisi tamamlandi: motor=%s kaynak_metin_karakter=%d ceviri_metin_karakter=%d",
            _backend_box_name(bridge_backend),
            len(normalized_source_text),
            len(translated_text),
        )
        return translated_text
