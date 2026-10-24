# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from unicodedata import normalize

import numpy as np
import onnxruntime as ort


AVAILABLE_LANGS = {
    "ar", "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr", "hi",
    "hr", "hu", "id", "it", "ja", "ko", "lt", "lv", "na", "nl", "pl", "pt",
    "ro", "ru", "sk", "sl", "sv", "tr", "uk", "vi",
}
EMOJI_PATTERN = re.compile(
    "[\U0001f600-\U0001f64f"
    "\U0001f300-\U0001f5ff"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f"
    "\U0001f780-\U0001f7ff"
    "\U0001f800-\U0001f8ff"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001fa6f"
    "\U0001fa70-\U0001faff"
    "\u2600-\u26ff"
    "\u2700-\u27bf]+",
    flags=re.UNICODE,
)
TEXT_TRANSLATION_TABLE = str.maketrans({
    "_": " ",
    "[": " ",
    "]": " ",
    "|": " ",
    "/": " ",
    "#": " ",
    "`": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2013": "-",
    "\u2014": "-",
})
WHITESPACE_PATTERN = re.compile(r"\s+")
TEXT_TERMINAL_PATTERN = re.compile(r"[.!?;:,'\"')\]}…。｣』】〉》›»]$")
TEXT_PUNCTUATION_PATTERNS = (
    (re.compile(r" ,"), ","),
    (re.compile(r" \."), "."),
    (re.compile(r" !"), "!"),
    (re.compile(r" \?"), "?"),
    (re.compile(r" ;"), ";"),
    (re.compile(r" :"), ":"),
)
PARAGRAPH_SPLIT_PATTERN = re.compile(r"\n\s*\n+")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")


class SupertonicStyle:
    def __init__(self, style_ttl: np.ndarray, style_dp: np.ndarray):
        self.ttl = style_ttl
        self.dp = style_dp


class SupertonicTextProcessor:
    def __init__(self, unicode_indexer_path: Path):
        with open(unicode_indexer_path, "r", encoding="utf-8") as f:
            self.indexer = json.load(f)
        self.indexer_lookup = np.asarray(self.indexer, dtype=np.int64)

    def preprocess_text(self, text: str, lang: str) -> str:
        lang = lang if lang in AVAILABLE_LANGS else "na"
        text = normalize("NFKD", text)
        text = self.remove_emoji(text)
        text = text.translate(TEXT_TRANSLATION_TABLE)
        text = WHITESPACE_PATTERN.sub(" ", text).strip()
        for pattern, replacement in TEXT_PUNCTUATION_PATTERNS:
            text = pattern.sub(replacement, text)
        if text and not TEXT_TERMINAL_PATTERN.search(text):
            text += "."
        return f"<{lang}>{text}</{lang}>"

    def remove_emoji(self, text: str) -> str:
        return EMOJI_PATTERN.sub("", text)

    def prepare_texts(self, text_list: list[str], lang_list: list[str]) -> list[str]:
        return [
            self.preprocess_text(text, lang)
            for text, lang in zip(text_list, lang_list)
        ]

    def encode_prepared_texts(self, prepared: list[str]) -> tuple[np.ndarray, np.ndarray]:
        if len(prepared) == 1:
            text = prepared[0]
            length = len(text)
            values = np.frombuffer(text.encode("utf-32le"), dtype=np.uint16, count=length * 2)[::2]
            text_ids = self.indexer_lookup[values].reshape(1, length)
            return text_ids, length_to_mask(np.array([length], dtype=np.int64))
        lengths = np.array([len(text) for text in prepared], dtype=np.int64)
        text_ids = np.zeros((len(prepared), lengths.max()), dtype=np.int64)
        for row, text in enumerate(prepared):
            values = np.frombuffer(text.encode("utf-32le"), dtype=np.uint16, count=len(text) * 2)[::2]
            text_ids[row, : len(values)] = self.indexer_lookup[values]
        return text_ids, length_to_mask(lengths)

    def __call__(self, text_list: list[str], lang_list: list[str]) -> tuple[np.ndarray, np.ndarray]:
        return self.encode_prepared_texts(self.prepare_texts(text_list, lang_list))


class SupertonicOnnxRuntime:
    def __init__(
        self,
        onnx_dir: Path,
        intra_op_threads: int | None = None,
        inter_op_threads: int | None = None,
        cache_dir: Path | None = None,
    ):
        self.onnx_dir = Path(onnx_dir)
        self.cache_dir = Path(cache_dir) if cache_dir is not None else self.onnx_dir.parent / ".cache"
        self.intra_op_threads = intra_op_threads
        self.inter_op_threads = inter_op_threads
        self.cfgs = load_runtime_json(self.onnx_dir / "tts.json")
        self.text_processor = load_text_processor(self.onnx_dir / "unicode_indexer.json")
        self.dp_ort = self.create_cached_session(self.onnx_dir / "duration_predictor.onnx", "duration_predictor.onnx")
        self.text_enc_ort = self.create_cached_session(self.onnx_dir / "text_encoder.onnx", "text_encoder.onnx")
        self.vector_est_ort = None
        self.vocoder_ort = self.create_cached_session(self.onnx_dir / "vocoder.onnx", "vocoder.onnx")
        self.dp_output_names = [self.dp_ort.get_outputs()[0].name]
        self.text_enc_output_names = [self.text_enc_ort.get_outputs()[0].name]
        self.vector_est_output_names = ["denoised_latent"]
        self.vocoder_output_names = [self.vocoder_ort.get_outputs()[0].name]
        self.sample_rate = int(self.cfgs["ae"]["sample_rate"])
        self.base_chunk_size = int(self.cfgs["ae"]["base_chunk_size"])
        self.chunk_compress_factor = int(self.cfgs["ttl"]["chunk_compress_factor"])
        self.ldim = int(self.cfgs["ttl"]["latent_dim"])
        self.single_batch_latent_masks = {}
        self.run_options = ort.RunOptions()
        self.run_options.only_execute_path_to_fetches = True
        self.run_options.log_severity_level = 3
        self.run_options.log_verbosity_level = 0

    def create_session_options(self, intra_op_threads: int | None, inter_op_threads: int | None):
        opts = ort.SessionOptions()
        if intra_op_threads is not None and intra_op_threads > 0:
            opts.intra_op_num_threads = int(intra_op_threads)
        if inter_op_threads is not None and inter_op_threads > 0:
            opts.inter_op_num_threads = int(inter_op_threads)
        opts.log_severity_level = 3
        opts.log_verbosity_level = 0
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.execution_order = ort.ExecutionOrder.PRIORITY_BASED
        opts.enable_mem_pattern = False
        opts.enable_mem_reuse = False
        opts.add_session_config_entry("session.intra_op.allow_spinning", "0")
        opts.add_session_config_entry("session.inter_op.allow_spinning", "0")
        opts.add_session_config_entry("session.dynamic_block_base", "4")
        opts.add_session_config_entry("session.set_denormal_as_zero", "1")
        return opts

    def create_disabled_session_options(self):
        opts = self.create_session_options(self.intra_op_threads, self.inter_op_threads)
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        return opts

    def optimized_cache_dir(self) -> Path:
        raw_key = {
            "ort_version": ort.__version__,
            "provider": "CPUExecutionProvider",
            "graph": "ORT_ENABLE_ALL",
            "execution_order": "PRIORITY_BASED",
            "spin": "0",
            "dynamic_block_base": "4",
            "denormal_as_zero": "1",
            "mem_pattern": False,
            "mem_reuse": False,
            "intra": self.intra_op_threads,
            "inter": self.inter_op_threads,
        }
        key = hashlib.sha1(json.dumps(raw_key, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        path = self.cache_dir / "optimized_onnx" / key
        path.mkdir(parents=True, exist_ok=True)
        return path

    def optimized_cache_metadata(self, source_path: Path) -> dict:
        stat = source_path.stat()
        return {
            "source_name": source_path.name,
            "source_size": stat.st_size,
            "source_mtime_ns": stat.st_mtime_ns,
            "ort_version": ort.__version__,
            "provider": "CPUExecutionProvider",
            "graph": "ORT_ENABLE_ALL",
            "execution_order": "PRIORITY_BASED",
            "spin": "0",
            "dynamic_block_base": "4",
            "denormal_as_zero": "1",
            "mem_pattern": False,
            "mem_reuse": False,
            "intra": self.intra_op_threads,
            "inter": self.inter_op_threads,
        }

    def optimized_cache_is_valid(self, cache_path: Path, metadata_path: Path, source_path: Path) -> bool:
        if not cache_path.exists() or not metadata_path.exists():
            return False
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                stored = json.load(f)
        except Exception:
            return False
        return stored == self.optimized_cache_metadata(source_path)

    def write_optimized_cache_metadata(self, metadata_path: Path, source_path: Path):
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.optimized_cache_metadata(source_path), f, ensure_ascii=False, indent=2)

    def remove_optimized_cache_files(self, cache_path: Path, metadata_path: Path):
        for path in (cache_path, metadata_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass

    def try_acquire_cache_lock(self, lock_path: Path) -> int | None:
        try:
            return os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            return None

    def release_cache_lock(self, lock_path: Path, lock_fd: int):
        try:
            os.close(lock_fd)
        finally:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    def load_cached_session(self, cache_path: Path):
        return ort.InferenceSession(
            str(cache_path),
            sess_options=self.create_disabled_session_options(),
            providers=["CPUExecutionProvider"],
        )

    def create_uncached_session(self, source_path: Path):
        return ort.InferenceSession(
            str(source_path),
            sess_options=self.create_session_options(self.intra_op_threads, self.inter_op_threads),
            providers=["CPUExecutionProvider"],
        )

    def create_cached_session(self, source_path: Path, cache_name: str):
        source_path = Path(source_path)
        cache_dir = self.optimized_cache_dir()
        cache_path = cache_dir / cache_name
        metadata_path = cache_path.with_suffix(cache_path.suffix + ".json")
        lock_path = cache_path.with_suffix(cache_path.suffix + ".lock")
        if self.optimized_cache_is_valid(cache_path, metadata_path, source_path):
            try:
                return self.load_cached_session(cache_path)
            except Exception:
                self.remove_optimized_cache_files(cache_path, metadata_path)
        lock_fd = self.try_acquire_cache_lock(lock_path)
        if lock_fd is not None:
            try:
                if self.optimized_cache_is_valid(cache_path, metadata_path, source_path):
                    return self.load_cached_session(cache_path)
                self.remove_optimized_cache_files(cache_path, metadata_path)
                opts = self.create_session_options(self.intra_op_threads, self.inter_op_threads)
                opts.optimized_model_filepath = str(cache_path)
                opts.log_severity_level = 3
                session = ort.InferenceSession(str(source_path), sess_options=opts, providers=["CPUExecutionProvider"])
                if cache_path.exists():
                    self.write_optimized_cache_metadata(metadata_path, source_path)
                return session
            except Exception:
                self.remove_optimized_cache_files(cache_path, metadata_path)
                return self.create_uncached_session(source_path)
            finally:
                self.release_cache_lock(lock_path, lock_fd)
        for _ in range(240):
            if self.optimized_cache_is_valid(cache_path, metadata_path, source_path):
                try:
                    return self.load_cached_session(cache_path)
                except Exception:
                    break
            if not lock_path.exists():
                break
            time.sleep(0.25)
        return self.create_uncached_session(source_path)

    def load_json(self, path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def sample_noisy_latent(self, duration: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
        bsz = len(duration)
        wav_len_max = duration.max() * self.sample_rate
        chunk_size = self.base_chunk_size * self.chunk_compress_factor
        latent_len = ((wav_len_max + chunk_size - 1) / chunk_size).astype(np.int32)
        latent_dim = self.ldim * self.chunk_compress_factor
        noisy_latent = rng.standard_normal((bsz, latent_dim, int(latent_len)), dtype=np.float32)
        if bsz == 1:
            latent_len_int = int(latent_len)
            latent_mask = self.single_batch_latent_masks.get(latent_len_int)
            if latent_mask is None:
                latent_mask = np.ones((1, 1, latent_len_int), dtype=np.float32)
                self.single_batch_latent_masks[latent_len_int] = latent_mask
            return noisy_latent, latent_mask
        wav_lengths = (duration * self.sample_rate).astype(np.int64)
        latent_mask = get_latent_mask(wav_lengths, self.base_chunk_size, self.chunk_compress_factor)
        noisy_latent *= latent_mask
        return noisy_latent, latent_mask

    def get_vector_estimator(self):
        if self.vector_est_ort is None:
            from .k15_solver import create_k15_vector_session

            self.vector_est_ort = create_k15_vector_session(self)
            self.vector_est_output_names = [self.vector_est_ort.get_outputs()[0].name]
        return self.vector_est_ort

    def infer(
        self,
        text_list: list[str],
        lang_list: list[str],
        style: SupertonicStyle,
        total_step: int,
        speed: float,
        seed: int,
    ):
        from .k15_solver import infer_k15

        return infer_k15(self, text_list, lang_list, style, total_step, speed, seed)

    def synthesize(
        self,
        text: str,
        lang: str,
        style: SupertonicStyle,
        total_step: int,
        speed: float,
        seed: int,
        silence_duration: float = 0.3,
        return_actual_chunks: bool = False,
    ):
        chunks = chunk_text(text, 120 if lang in ("ko", "ja") else 300)
        wav_parts = []
        duration_cat = 0.0
        chunk_timeline = []
        actual_chunks = []
        silence = None
        for index, chunk in enumerate(chunks):
            wav, duration = self.infer(
                [chunk],
                [lang],
                style,
                total_step,
                speed,
                (seed + index) % (2 ** 32),
            )
            if wav_parts:
                if silence is None:
                    silence = np.zeros((1, int(silence_duration * self.sample_rate)), dtype=np.float32)
                wav_parts.append(silence)
                duration_cat += silence_duration
            chunk_start = duration_cat
            wav_parts.append(wav)
            actual_chunks.append({"text": chunk, "wav_array": wav[0].astype(np.float32, copy=False)})
            duration_cat += float(duration[0])
            chunk_timeline.append({
                "text": chunk,
                "start": chunk_start,
                "end": duration_cat,
            })
        wav_cat = wav_parts[0] if len(wav_parts) == 1 else np.concatenate(wav_parts, axis=1)
        if return_actual_chunks:
            return wav_cat, duration_cat, len(chunks), chunk_timeline, actual_chunks, silence_duration
        return wav_cat, duration_cat, len(chunks), chunk_timeline


def load_voice_style(path: Path) -> SupertonicStyle:
    return _load_voice_style_cached(str(Path(path)))


def load_runtime_json(path: Path) -> dict:
    return _load_runtime_json_cached(str(Path(path)))


def load_text_processor(path: Path) -> SupertonicTextProcessor:
    return _load_text_processor_cached(str(Path(path)))


@lru_cache(maxsize=8)
def _load_runtime_json_cached(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=8)
def _load_text_processor_cached(path: str) -> SupertonicTextProcessor:
    return SupertonicTextProcessor(Path(path))


@lru_cache(maxsize=16)
def _load_voice_style_cached(path: str) -> SupertonicStyle:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    ttl_dims = data["style_ttl"]["dims"]
    dp_dims = data["style_dp"]["dims"]
    ttl = np.array(data["style_ttl"]["data"], dtype=np.float32).reshape(ttl_dims[1], ttl_dims[2])
    dp = np.array(data["style_dp"]["data"], dtype=np.float32).reshape(dp_dims[1], dp_dims[2])
    return SupertonicStyle(ttl.reshape(1, ttl_dims[1], ttl_dims[2]), dp.reshape(1, dp_dims[1], dp_dims[2]))


def deterministic_seed(text: str, lang: str, voice_id: str, total_step: int, speed: float) -> int:
    payload = f"{lang}\n{voice_id}\n{total_step}\n{speed:.6f}\n{text}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "little")


def deterministic_seed_from_prefix(text: str, prefix: bytes) -> int:
    return int.from_bytes(hashlib.sha256(prefix + text.encode("utf-8")).digest()[:4], "little")


def deterministic_seed_from_hasher(text: str, hasher_template) -> int:
    hasher = hasher_template.copy()
    hasher.update(text.encode("utf-8"))
    return int.from_bytes(hasher.digest()[:4], "little")


def length_to_mask(lengths: np.ndarray, max_len: int | None = None) -> np.ndarray:
    max_len = max_len or int(lengths.max())
    ids = np.arange(max_len, dtype=lengths.dtype)
    mask = np.less(ids, lengths[:, None]).astype(np.float32, copy=False)
    return mask.reshape(-1, 1, max_len)


def get_latent_mask(wav_lengths: np.ndarray, base_chunk_size: int, chunk_compress_factor: int) -> np.ndarray:
    latent_size = base_chunk_size * chunk_compress_factor
    latent_lengths = (wav_lengths + latent_size - 1) // latent_size
    return length_to_mask(latent_lengths)


def chunk_text(text: str, max_len: int = 300) -> list[str]:
    stripped = text.strip()
    if len(stripped) <= max_len and "\n" not in stripped:
        return [stripped]
    paragraphs = [item.strip() for item in PARAGRAPH_SPLIT_PATTERN.split(stripped) if item.strip()]
    chunks = []
    for paragraph in paragraphs:
        sentences = SENTENCE_SPLIT_PATTERN.split(paragraph.strip())
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= max_len:
                current += (" " if current else "") + sentence
            else:
                if current:
                    chunks.append(current.strip())
                current = sentence
        if current:
            chunks.append(current.strip())
    return chunks or [stripped]
