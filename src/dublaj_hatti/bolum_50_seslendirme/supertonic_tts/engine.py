# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import os
import hashlib
from pathlib import Path
from time import perf_counter

import numpy as np

from .synthesis_profile import SUPERTONIC_TOTAL_STEPS, get_supertonic_synthesis_profile
from .runtime import (
    AVAILABLE_LANGS,
    SupertonicOnnxRuntime,
    deterministic_seed_from_hasher,
    load_voice_style,
)
from .speed_policy import (
    SUPERTONIC_SPEED_POLICY,
    SUPERTONIC_VOICE_SPEEDS,
    get_supertonic_voice_speed,
    validate_supertonic_voice_speed,
)


logger = logging.getLogger("dublaj_hatti")

DEFAULT_TOTAL_STEP = SUPERTONIC_TOTAL_STEPS
VOICE_IDS = set(SUPERTONIC_VOICE_SPEEDS)


def build_supertonic_seed_hasher_template(language, voice_id, total_step):
    selected_language = normalize_language(language)
    selected_voice_id = normalize_voice_id(voice_id)
    return hashlib.sha256(f"{selected_language}\n{selected_voice_id}\n{int(total_step)}\n".encode("utf-8"))


def _synthesize_audio(
    runtime,
    text,
    language,
    style,
    total_step,
    speed,
    seed,
    return_actual_chunks=False,
):
    return runtime.synthesize(
        text=text,
        lang=language,
        style=style,
        total_step=total_step,
        speed=speed,
        seed=seed,
        return_actual_chunks=return_actual_chunks,
    )


class SupertonicSegmentSynthesizer:
    def __init__(
        self,
        voice_id,
        language,
        speed=None,
        total_step=DEFAULT_TOTAL_STEP,
        intra_op_threads=None,
        inter_op_threads=None,
    ):
        self.voice_id = normalize_voice_id(voice_id)
        self.language = normalize_language(language)
        self.speed = (
            get_supertonic_voice_speed(self.voice_id)
            if speed is None
            else validate_supertonic_voice_speed(self.voice_id, speed)
        )
        self.total_step = total_step
        self.model_dir = resolve_model_dir()
        self.onnx_dir = resolve_onnx_dir()
        self.voice_style_path = resolve_voice_styles_dir() / f"{self.voice_id}.json"
        self.runtime = SupertonicOnnxRuntime(
            self.onnx_dir,
            intra_op_threads=intra_op_threads,
            inter_op_threads=inter_op_threads,
            cache_dir=resolve_runtime_cache_dir(),
        )
        self.style = load_voice_style(self.voice_style_path)
        self.seed_hasher_template = build_supertonic_seed_hasher_template(
            self.language,
            self.voice_id,
            self.total_step,
        )

    def synthesize_segments(self, segments, work_dir=None, return_actual_chunks=False):
        if work_dir is None:
            work_dir = os.getcwd()
        debug_dir = Path(work_dir) / "supertonic_tts"
        debug_dir.mkdir(parents=True, exist_ok=True)

        results = {}
        records = []
        successful = 0
        failed = 0

        for seg in segments:
            seg_started = perf_counter()
            seg_index = int(seg["index"])
            text = str(seg.get("text") or "")
            target_duration = float(seg.get("duration") or 0.0)
            if not text.strip():
                duration = max(target_duration, 0.1)
                silence = np.zeros(int(duration * self.runtime.sample_rate), dtype=np.float32)
                results[seg_index] = {
                    "wav_array": silence,
                    "sample_rate": self.runtime.sample_rate,
                    "debug": {
                        "status": "silence",
                        "reason": "empty_text",
                    },
                }
                records.append({
                    "segment_index": seg_index,
                    "status": "silence",
                    "reason": "empty_text",
                    "target_duration": round(target_duration, 3),
                    "raw_duration": round(duration, 3),
                })
                logger.warning("[SUPERTONIC] seg=%d bos metin, sessizlik eklendi", seg_index)
                continue

            seed = deterministic_seed_from_hasher(text, self.seed_hasher_template)
            try:
                synthesis_result = _synthesize_audio(
                    self.runtime,
                    text,
                    self.language,
                    self.style,
                    self.total_step,
                    self.speed,
                    seed,
                    return_actual_chunks=return_actual_chunks,
                )
                wav, predicted_duration, chunk_count, chunk_timeline = synthesis_result[:4]
                actual_chunks = synthesis_result[4] if return_actual_chunks else []
                inter_chunk_silence_seconds = float(synthesis_result[5]) if return_actual_chunks else 0.0
                audio = wav[0].astype(np.float32, copy=False)
                raw_duration = len(audio) / self.runtime.sample_rate
                elapsed = perf_counter() - seg_started
                debug = {
                    "status": "ok",
                    "voice_id": self.voice_id,
                    "language": self.language,
                    "seed": seed,
                    "speed": self.speed,
                    "synthesis_profile": get_supertonic_synthesis_profile(),
                    "total_step": self.total_step,
                    "chunk_count": chunk_count,
                    "chunk_timeline": chunk_timeline,
                    "predicted_duration": predicted_duration,
                    "raw_duration": raw_duration,
                    "target_duration": target_duration,
                    "elapsed_seconds": elapsed,
                }
                results[seg_index] = {
                    "wav_array": audio,
                    "sample_rate": self.runtime.sample_rate,
                    "debug": debug,
                    "actual_chunks": actual_chunks,
                    "inter_chunk_silence_seconds": inter_chunk_silence_seconds,
                }
                records.append({
                    "segment_index": seg_index,
                    "status": "ok",
                    "voice_id": self.voice_id,
                    "language": self.language,
                    "seed": seed,
                    "speed": self.speed,
                    "synthesis_profile": get_supertonic_synthesis_profile(),
                    "total_step": self.total_step,
                    "chunk_count": chunk_count,
                    "predicted_duration": round(predicted_duration, 6),
                    "raw_duration": round(raw_duration, 6),
                    "target_duration": round(target_duration, 6),
                    "duration_ratio": round(raw_duration / target_duration, 6) if target_duration > 0 else None,
                    "elapsed_seconds": round(elapsed, 3),
                })
                logger.debug(
                    "[SUPERTONIC] seg=%d OK voice=%s raw=%.3fs target=%.3fs seed=%d chunk=%d elapsed=%.2fs",
                    seg_index,
                    self.voice_id,
                    raw_duration,
                    target_duration,
                    seed,
                    chunk_count,
                    elapsed,
                )
                successful += 1
            except Exception as e:
                elapsed = perf_counter() - seg_started
                failed += 1
                records.append({
                    "segment_index": seg_index,
                    "status": "failed",
                    "voice_id": self.voice_id,
                    "language": self.language,
                    "error": str(e),
                    "elapsed_seconds": round(elapsed, 3),
                })
                logger.warning("[SUPERTONIC] seg=%d HATA: %s", seg_index, e)

        return results, records, successful, failed


class SupertonicMultiVoiceSegmentSynthesizer:
    def __init__(
        self,
        language,
        speed=None,
        total_step=DEFAULT_TOTAL_STEP,
        intra_op_threads=None,
        inter_op_threads=None,
    ):
        self.language = normalize_language(language)
        self.speed = None if speed is None else float(speed)
        self.total_step = total_step
        self.model_dir = resolve_model_dir()
        self.onnx_dir = resolve_onnx_dir()
        self.voice_styles_dir = resolve_voice_styles_dir()
        self.runtime = SupertonicOnnxRuntime(
            self.onnx_dir,
            intra_op_threads=intra_op_threads,
            inter_op_threads=inter_op_threads,
            cache_dir=resolve_runtime_cache_dir(),
        )
        self.styles = {}
        self.seed_hasher_templates = {}

    def _style_for_voice(self, voice_id):
        selected_voice_id = normalize_voice_id(voice_id)
        if selected_voice_id not in self.styles:
            self.styles[selected_voice_id] = load_voice_style(self.voice_styles_dir / f"{selected_voice_id}.json")
        return selected_voice_id, self.styles[selected_voice_id]

    def _seed_for(self, text, voice_id):
        selected_voice_id = normalize_voice_id(voice_id)
        if selected_voice_id not in self.seed_hasher_templates:
            self.seed_hasher_templates[selected_voice_id] = build_supertonic_seed_hasher_template(
                self.language,
                selected_voice_id,
                self.total_step,
            )
        return deterministic_seed_from_hasher(text, self.seed_hasher_templates[selected_voice_id])

    def synthesize_segments(self, segments, work_dir=None):
        if work_dir is None:
            work_dir = os.getcwd()
        debug_dir = Path(work_dir) / "supertonic_tts"
        debug_dir.mkdir(parents=True, exist_ok=True)

        results = {}
        records = []
        successful = 0
        failed = 0

        for seg in segments:
            seg_started = perf_counter()
            seg_index = int(seg["index"])
            text = str(seg.get("text") or "")
            target_duration = float(seg.get("duration") or 0.0)
            voice_id, style = self._style_for_voice(seg.get("voice_id") or "F1")
            voice_speed = get_supertonic_voice_speed(voice_id)
            if self.speed is not None:
                voice_speed = validate_supertonic_voice_speed(voice_id, self.speed)
            if not text.strip():
                duration = max(target_duration, 0.1)
                silence = np.zeros(int(duration * self.runtime.sample_rate), dtype=np.float32)
                results[seg_index] = {
                    "wav_array": silence,
                    "sample_rate": self.runtime.sample_rate,
                    "debug": {
                        "status": "silence",
                        "reason": "empty_text",
                        "voice_id": voice_id,
                    },
                }
                records.append({
                    "segment_index": seg_index,
                    "status": "silence",
                    "reason": "empty_text",
                    "voice_id": voice_id,
                    "target_duration": round(target_duration, 3),
                    "raw_duration": round(duration, 3),
                })
                logger.warning("[SUPERTONIC] seg=%d bos metin, sessizlik eklendi", seg_index)
                continue

            seed = self._seed_for(text, voice_id)
            try:
                wav, predicted_duration, chunk_count, chunk_timeline = _synthesize_audio(
                    self.runtime,
                    text,
                    self.language,
                    style,
                    self.total_step,
                    voice_speed,
                    seed,
                )
                audio = wav[0].astype(np.float32, copy=False)
                raw_duration = len(audio) / self.runtime.sample_rate
                elapsed = perf_counter() - seg_started
                debug = {
                    "status": "ok",
                    "voice_id": voice_id,
                    "language": self.language,
                    "seed": seed,
                    "speed": voice_speed,
                    "synthesis_profile": get_supertonic_synthesis_profile(),
                    "total_step": self.total_step,
                    "chunk_count": chunk_count,
                    "chunk_timeline": chunk_timeline,
                    "predicted_duration": predicted_duration,
                    "raw_duration": raw_duration,
                    "target_duration": target_duration,
                    "elapsed_seconds": elapsed,
                }
                results[seg_index] = {
                    "wav_array": audio,
                    "sample_rate": self.runtime.sample_rate,
                    "debug": debug,
                }
                records.append({
                    "segment_index": seg_index,
                    "status": "ok",
                    "voice_id": voice_id,
                    "language": self.language,
                    "seed": seed,
                    "speed": voice_speed,
                    "synthesis_profile": get_supertonic_synthesis_profile(),
                    "total_step": self.total_step,
                    "chunk_count": chunk_count,
                    "predicted_duration": round(predicted_duration, 6),
                    "raw_duration": round(raw_duration, 6),
                    "target_duration": round(target_duration, 6),
                    "duration_ratio": round(raw_duration / target_duration, 6) if target_duration > 0 else None,
                    "elapsed_seconds": round(elapsed, 3),
                })
                logger.debug(
                    "[SUPERTONIC] seg=%d OK voice=%s raw=%.3fs target=%.3fs seed=%d chunk=%d elapsed=%.2fs",
                    seg_index,
                    voice_id,
                    raw_duration,
                    target_duration,
                    seed,
                    chunk_count,
                    elapsed,
                )
                successful += 1
            except Exception as e:
                elapsed = perf_counter() - seg_started
                failed += 1
                records.append({
                    "segment_index": seg_index,
                    "status": "failed",
                    "voice_id": voice_id,
                    "language": self.language,
                    "error": str(e),
                    "elapsed_seconds": round(elapsed, 3),
                })
                logger.warning("[SUPERTONIC] seg=%d HATA: %s", seg_index, e)

        return results, records, successful, failed


def synthesize_segments_multi_voice(
    segments,
    language,
    work_dir=None,
    speed=None,
    total_step=DEFAULT_TOTAL_STEP,
    intra_op_threads=None,
    inter_op_threads=None,
):
    if work_dir is None:
        work_dir = os.getcwd()
    selected_speeds = {}
    for item in segments:
        voice_id = normalize_voice_id(item.get("voice_id") or "F1")
        item_speed = item.get("speed")
        if item_speed is None:
            raise RuntimeError(f"Supertonic segment hizi yok: segment={item.get('index', '')}")
        selected_speeds[voice_id] = validate_supertonic_voice_speed(voice_id, item_speed)
    if not segments:
        raise RuntimeError("Supertonic sabit profil hizi icin segment bulunamadi")
    debug_dir = Path(work_dir) / "supertonic_tts"
    debug_dir.mkdir(parents=True, exist_ok=True)

    selected_language = normalize_language(language)
    model_dir = resolve_model_dir()
    voice_ids = sorted({normalize_voice_id(item.get("voice_id") or "F1") for item in segments})

    logger.info("=" * 60)
    logger.info("[SUPERTONIC] COKLU SES SESLENDIRME BASLIYOR")
    logger.info("Toplam segment: %d", len(segments))
    logger.info("Dil: %s", selected_language)
    logger.info("Voices: %s", ", ".join(voice_ids))
    logger.info(
        "Speed policy: %s (%s)",
        SUPERTONIC_SPEED_POLICY,
        ", ".join(f"{voice_id}={selected_speeds[voice_id]:.2f}" for voice_id in sorted(selected_speeds)),
    )
    logger.info("Total step: %d", total_step)
    if intra_op_threads or inter_op_threads:
        logger.info("ONNX threads: intra=%s inter=%s", intra_op_threads, inter_op_threads)
    logger.info("Debug klasoru: %s", debug_dir)
    logger.info("=" * 60)

    started = perf_counter()
    synthesizer = SupertonicMultiVoiceSegmentSynthesizer(
        language=selected_language,
        speed=speed,
        total_step=total_step,
        intra_op_threads=intra_op_threads,
        inter_op_threads=inter_op_threads,
    )
    results, records, successful, failed = synthesizer.synthesize_segments(segments, work_dir)

    summary = {
        "status": "completed" if failed == 0 else "partial",
        "segment_count": len(segments),
        "successful_count": successful,
        "failed_count": failed,
        "voice_id": voice_ids[0] if len(voice_ids) == 1 else "multiple",
        "voice_ids": voice_ids,
        "language": selected_language,
        "speed_policy": SUPERTONIC_SPEED_POLICY,
        "voice_speeds": selected_speeds,
        "speed_values": sorted(set(selected_speeds.values())),
        "synthesis_profile": get_supertonic_synthesis_profile(),
        "total_step": total_step,
        "model_dir": str(model_dir),
        "elapsed_seconds": round(perf_counter() - started, 3),
    }

    write_debug(debug_dir, summary, records)
    logger.info("[SUPERTONIC] Coklu ses tamamlandi: basarili=%d hatali=%d", successful, failed)
    logger.info("[SUPERTONIC] Debug: %s", debug_dir)
    logger.info("=" * 60)
    return results


def synthesize_segments(
    segments,
    voice_id,
    language,
    work_dir=None,
    speed=None,
    total_step=DEFAULT_TOTAL_STEP,
    intra_op_threads=None,
    inter_op_threads=None,
    return_actual_chunks=False,
):
    if work_dir is None:
        work_dir = os.getcwd()
    debug_dir = Path(work_dir) / "supertonic_tts"
    debug_dir.mkdir(parents=True, exist_ok=True)

    selected_voice_id = normalize_voice_id(voice_id)
    selected_language = normalize_language(language)
    model_dir = resolve_model_dir()

    logger.info("=" * 60)
    logger.info("[SUPERTONIC] SESLENDIRME BASLIYOR")
    logger.info("Toplam segment: %d", len(segments))
    logger.info("Dil: %s", selected_language)
    logger.info("Voice: %s", selected_voice_id)
    selected_speed = get_supertonic_voice_speed(selected_voice_id) if speed is None else validate_supertonic_voice_speed(selected_voice_id, speed)
    logger.info("Speed policy: %s", SUPERTONIC_SPEED_POLICY)
    logger.info("Speed: %.3f", selected_speed)
    logger.info("Total step: %d", total_step)
    if intra_op_threads or inter_op_threads:
        logger.info("ONNX threads: intra=%s inter=%s", intra_op_threads, inter_op_threads)
    logger.info("Debug klasoru: %s", debug_dir)
    logger.info("=" * 60)

    started = perf_counter()
    synthesizer = SupertonicSegmentSynthesizer(
        voice_id=selected_voice_id,
        language=selected_language,
        speed=selected_speed,
        total_step=total_step,
        intra_op_threads=intra_op_threads,
        inter_op_threads=inter_op_threads,
    )
    results, records, successful, failed = synthesizer.synthesize_segments(
        segments,
        work_dir,
        return_actual_chunks=return_actual_chunks,
    )

    summary = {
        "status": "completed" if failed == 0 else "partial",
        "segment_count": len(segments),
        "successful_count": successful,
        "failed_count": failed,
        "voice_id": selected_voice_id,
        "language": selected_language,
        "speed": selected_speed,
        "speed_policy": SUPERTONIC_SPEED_POLICY,
        "synthesis_profile": get_supertonic_synthesis_profile(),
        "total_step": total_step,
        "model_dir": str(model_dir),
        "elapsed_seconds": round(perf_counter() - started, 3),
    }

    write_debug(debug_dir, summary, records)
    logger.info("[SUPERTONIC] Tamamlandi: basarili=%d hatali=%d", successful, failed)
    logger.info("[SUPERTONIC] Debug: %s", debug_dir)
    logger.info("=" * 60)
    return results


def normalize_voice_id(voice_id):
    value = str(voice_id or "").strip().upper()
    return value if value in VOICE_IDS else "F1"


def normalize_language(language):
    value = str(language or "tr").strip().lower()[:2]
    return value if value in AVAILABLE_LANGS else "na"


def resolve_model_dir():
    project_root = Path(__file__).resolve().parents[3]
    repository_root = Path(__file__).resolve().parents[4]
    package_assets = Path(__file__).resolve().parent / "assets"
    runtime_assets = repository_root / "runtime_assets" / "tts_motorlari" / "supertonic_tts"
    env_root = os.environ.get("SUPERTONIC_ASSETS_DIR", "").strip()
    roots = []
    if env_root:
        roots.append(Path(env_root))
    roots.append(runtime_assets)
    roots.append(package_assets)
    roots.extend([
        project_root / "supertonic_assets",
        project_root / "supertonic_voice_model_profiles",
    ])
    for root in roots:
        model_dir = root / "supertonic3"
        if model_dir.exists():
            return model_dir
    checked = ", ".join(str(root / "supertonic3") for root in roots)
    raise FileNotFoundError(f"Supertonic model klasoru bulunamadi: {checked}")


def resolve_onnx_dir():
    model_dir = resolve_model_dir()
    candidates = [
        model_dir / "models" / "onnx",
        model_dir / "onnx",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"Supertonic ONNX klasoru bulunamadi: {model_dir}")


def resolve_voice_styles_dir():
    model_dir = resolve_model_dir()
    candidates = [
        model_dir / "voices" / "voice_styles",
        model_dir / "voice_styles",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"Supertonic voice style klasoru bulunamadi: {model_dir}")


def resolve_runtime_cache_dir():
    model_dir = resolve_model_dir()
    cache_dir = model_dir / "runtime_cache"
    if cache_dir.exists():
        return cache_dir
    return model_dir / ".cache"


def write_debug(debug_dir, summary, records):
    summary_path = Path(debug_dir) / "summary.json"
    records_path = Path(debug_dir) / "segments.jsonl"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(records_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
