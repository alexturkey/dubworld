from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import textwrap
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

from dublaj_hatti.bolum_00_omurga.full_metin_dublaji import synthesize_full_text_supertonic
from dublaj_hatti.bolum_00_omurga.runtime.arac_yolu import ffmpeg_yolu


QUOTE_CHARACTERS = '"\'“”‘’«»‹›„‟‚‛`'
SPACING_SYMBOLS = "[]{}()<>|/_#@*+=&%$€£¥\\"
ALLOWED_PUNCTUATION = ".,?!-"
WHITESPACE_PATTERN = re.compile(r"\s+")
REPEATED_PUNCTUATION_PATTERN = re.compile(r"([.,?!])\1+")
PUNCTUATION_SEQUENCE_PATTERN = re.compile(r"[.,?!](?:\s*[.,?!])+")
CHAPTER_PATTERN = re.compile(r"(?i)\bBÖLÜM\s+([0-9]+)\s+")


@dataclass(frozen=True)
class TextToSpeechArtifacts:
    integrated_text_path: Path
    original_wav_path: Path
    clean_mp3_path: Path
    chunk_directory_path: Path
    chunk_manifest_path: Path
    sample_rate: int
    sample_count: int
    chunk_count: int

    @property
    def duration(self) -> float:
        return self.sample_count / self.sample_rate


@dataclass(frozen=True)
class RebuiltTextToSpeechArtifacts:
    original_wav_path: Path
    clean_mp3_path: Path
    chunk_manifest_path: Path
    sample_rate: int
    sample_count: int
    chunk_count: int

    @property
    def duration(self) -> float:
        return self.sample_count / self.sample_rate


def _collapse_punctuation_sequence(match: re.Match) -> str:
    values = [character for character in match.group(0) if character in ".,?!"]
    if "?" in values:
        return "?"
    if "!" in values:
        return "!"
    if "." in values:
        return "."
    return ","


def prepare_text_for_speech(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"([.!?])\s*\n\s*\n+", r"\1 ", value)
    value = re.sub(r"\n\s*\n+", ". ", value)
    value = value.replace("\n", " ")
    value = CHAPTER_PATTERN.sub(lambda match: f"BÖLÜM {match.group(1)}. ", value)
    translation = {ord(character): None for character in QUOTE_CHARACTERS}
    translation.update({ord(character): " " for character in SPACING_SYMBOLS})
    translation.update({ord("–"): ",", ord("—"): ",", ord("…"): ".", ord(";"): ",", ord(":"): "."})
    value = value.translate(translation)
    filtered = []
    for character in value:
        if character.isalnum() or character.isspace() or character in ALLOWED_PUNCTUATION:
            filtered.append(character)
        else:
            filtered.append(" ")
    value = WHITESPACE_PATTERN.sub(" ", "".join(filtered)).strip()
    value = re.sub(r"\s+([.,?!])", r"\1", value)
    value = PUNCTUATION_SEQUENCE_PATTERN.sub(_collapse_punctuation_sequence, value)
    value = re.sub(r"([.,?!])(?=[^\s])", r"\1 ", value)
    value = REPEATED_PUNCTUATION_PATTERN.sub(r"\1", value)
    value = re.sub(r"(?<!\w)-(?!\w)|(?<!\w)-|-(?!\w)", " ", value)
    value = WHITESPACE_PATTERN.sub(" ", value).strip()
    if value and value[-1] not in ".?!":
        value += "."
    if not value:
        raise ValueError("Seslendirilecek metin bos olamaz")
    return value


def format_integrated_text(text: str, width: int | None = None) -> str:
    spoken_text = prepare_text_for_speech(text)
    if width is None:
        return spoken_text + "\n"
    if width < 40 or width > 50:
        raise ValueError("Butunlesik metin genisligi 40 ile 50 arasinda olmali")
    return textwrap.fill(
        spoken_text,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    ) + "\n"


def encode_metadata_clean_mp3(source_wav_path: str | Path, output_mp3_path: str | Path) -> Path:
    source_path = Path(source_wav_path)
    output_path = Path(output_mp3_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts import render_supertonic_constant_gain

    listening_path = output_path.with_suffix(".wav")
    render_supertonic_constant_gain(source_path, listening_path)
    subprocess.run(
        [
            ffmpeg_yolu(),
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", str(listening_path),
            "-map_metadata", "-1",
            "-fflags", "+bitexact",
            "-flags:a", "+bitexact",
            "-vn",
            "-ac", "1",
            "-ar", "44100",
            "-c:a", "libmp3lame",
            "-b:a", "96k",
            "-write_xing", "0",
            "-id3v2_version", "0",
            "-write_id3v1", "0",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError("Metadata temiz MP3 uretilemedi")
    return output_path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source_file:
        for block in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, data: dict) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(text.encode("utf-8"))


def persist_synthesis_chunks(
    synthesis,
    output_dir: str | Path,
    voice_id: str,
    language: str,
    base_name: str,
    integrated_text_path: str | Path,
) -> tuple[Path, Path]:
    output_root = Path(output_dir).resolve()
    chunk_directory = output_root / f"{base_name}_ses_parcalari"
    chunk_directory.mkdir(parents=True, exist_ok=True)
    sample_rate = int(synthesis.sample_rate)
    silence_samples = int(synthesis.inter_chunk_silence_samples)
    chunks = tuple(synthesis.actual_chunks)
    if sample_rate <= 0 or silence_samples < 0 or not chunks:
        raise RuntimeError("Kalici Supertonic parca bilgisi gecersiz")
    if int(synthesis.chunk_count) != len(chunks):
        raise RuntimeError("Supertonic parca sayisi gercek parcalarla uyusmuyor")
    cursor = 0
    manifest_chunks = []
    for index, chunk in enumerate(chunks, start=1):
        audio = np.asarray(chunk.audio, dtype=np.float32).reshape(-1)
        text = str(chunk.text or "").strip()
        if not text or audio.size <= 0 or not np.isfinite(audio).all():
            raise RuntimeError(f"Supertonic parca bilgisi gecersiz: {index}")
        if index > 1:
            cursor += silence_samples
        start_sample = cursor
        file_name = f"parca_{index:04d}.wav"
        text_file_name = f"parca_{index:04d}.txt"
        chunk_path = chunk_directory / file_name
        text_path = chunk_directory / text_file_name
        sf.write(chunk_path, audio, sample_rate, subtype="FLOAT")
        text_path.write_bytes((text + "\n").encode("utf-8"))
        cursor += len(audio)
        manifest_chunks.append({
            "index": index,
            "text": text,
            "file": f"{chunk_directory.name}/{file_name}",
            "text_file": f"{chunk_directory.name}/{text_file_name}",
            "sample_count": len(audio),
            "duration": len(audio) / sample_rate,
            "start": start_sample / sample_rate,
            "end": cursor / sample_rate,
            "sha256": _file_sha256(chunk_path),
        })
    if cursor != len(synthesis.audio):
        raise RuntimeError("Kalici parca toplami birlesik Supertonic sesiyle uyusmuyor")
    manifest_path = output_root / f"{base_name}_ses_parcalari_manifest.json"
    integrated_path = Path(integrated_text_path).resolve()
    try:
        integrated_relative = integrated_path.relative_to(output_root).as_posix()
    except ValueError:
        integrated_relative = integrated_path.name
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts import get_supertonic_synthesis_profile

    _write_json(manifest_path, {
        "schema_version": 1,
        "synthesis_profile": get_supertonic_synthesis_profile(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "voice_id": str(voice_id),
        "language": str(language),
        "sample_rate": sample_rate,
        "chunk_count": len(manifest_chunks),
        "inter_chunk_silence_samples": silence_samples,
        "inter_chunk_silence_seconds": silence_samples / sample_rate,
        "total_sample_count": cursor,
        "total_duration": cursor / sample_rate,
        "integrated_text_file": integrated_relative,
        "original_wav_file": f"{base_name}_orijinal.wav",
        "clean_mp3_file": f"{base_name}_temiz.mp3",
        "listening_wav_file": f"{base_name}_temiz.wav",
        "gain_report_file": f"{base_name}_temiz.gain.json",
        "chunks": manifest_chunks,
    })
    return chunk_directory, manifest_path


def _resolve_manifest_chunk_path(manifest_root: Path, value: str) -> Path:
    chunk_path = (manifest_root / value).resolve()
    try:
        chunk_path.relative_to(manifest_root)
    except ValueError as exc:
        raise ValueError("Manifest parca yolu output klasoru disinda") from exc
    return chunk_path


def rebuild_text_to_speech_from_manifest(
    manifest_path: str | Path,
    output_dir: str | Path | None = None,
    base_name: str | None = None,
) -> RebuiltTextToSpeechArtifacts:
    manifest_file = Path(manifest_path).resolve()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
    if int(manifest.get("schema_version") or 0) != 1:
        raise ValueError("Ses parcalari manifest surumu desteklenmiyor")
    manifest_root = manifest_file.parent
    output_root = Path(output_dir).resolve() if output_dir else manifest_root
    output_root.mkdir(parents=True, exist_ok=True)
    sample_rate = int(manifest.get("sample_rate") or 0)
    silence_samples = int(manifest.get("inter_chunk_silence_samples") or 0)
    chunks = list(manifest.get("chunks") or [])
    if sample_rate <= 0 or silence_samples < 0 or not chunks:
        raise ValueError("Ses parcalari manifest bilgisi gecersiz")
    expected_indexes = list(range(1, len(chunks) + 1))
    if [int(chunk.get("index") or 0) for chunk in chunks] != expected_indexes:
        raise ValueError("Ses parcalari manifest sirasi gecersiz")
    resolved_base_name = str(base_name or Path(str(manifest.get("original_wav_file") or "metinden_seslendirme_orijinal.wav")).stem.removesuffix("_orijinal"))
    original_wav_path = output_root / f"{resolved_base_name}_orijinal.wav"
    temporary_wav_path = output_root / f"{resolved_base_name}_orijinal.tmp.wav"
    cursor = 0
    updated_chunks = []
    try:
        with sf.SoundFile(temporary_wav_path, mode="w", samplerate=sample_rate, channels=1, subtype="FLOAT") as output_file:
            for index, chunk in enumerate(chunks, start=1):
                chunk_path = _resolve_manifest_chunk_path(manifest_root, str(chunk.get("file") or ""))
                if not chunk_path.is_file():
                    raise FileNotFoundError(f"Ses parcasi bulunamadi: {chunk_path}")
                audio, actual_sample_rate = sf.read(chunk_path, dtype="float32", always_2d=False)
                audio = np.asarray(audio, dtype=np.float32)
                if audio.ndim == 2 and audio.shape[1] == 1:
                    audio = audio[:, 0]
                if audio.ndim != 1 or audio.size <= 0 or int(actual_sample_rate) != sample_rate:
                    raise ValueError(f"Ses parcasi formati gecersiz: {chunk_path.name}")
                if not np.isfinite(audio).all():
                    raise ValueError(f"Ses parcasi sayisal veri hatasi: {chunk_path.name}")
                if index > 1 and silence_samples:
                    output_file.write(np.zeros(silence_samples, dtype=np.float32))
                    cursor += silence_samples
                start_sample = cursor
                output_file.write(audio)
                cursor += len(audio)
                updated_chunk = dict(chunk)
                updated_chunk.update({
                    "sample_count": len(audio),
                    "duration": len(audio) / sample_rate,
                    "start": start_sample / sample_rate,
                    "end": cursor / sample_rate,
                    "sha256": _file_sha256(chunk_path),
                })
                updated_chunks.append(updated_chunk)
        temporary_wav_path.replace(original_wav_path)
    except Exception:
        temporary_wav_path.unlink(missing_ok=True)
        raise
    clean_mp3_path = encode_metadata_clean_mp3(
        original_wav_path,
        output_root / f"{resolved_base_name}_temiz.mp3",
    )
    manifest.update({
        "last_rebuilt_at": datetime.now().isoformat(timespec="seconds"),
        "chunk_count": len(updated_chunks),
        "total_sample_count": cursor,
        "total_duration": cursor / sample_rate,
        "original_wav_file": original_wav_path.name,
        "clean_mp3_file": clean_mp3_path.name,
        "listening_wav_file": clean_mp3_path.with_suffix(".wav").name,
        "gain_report_file": clean_mp3_path.with_suffix(".gain.json").name,
        "chunks": updated_chunks,
    })
    _write_json(manifest_file, manifest)
    return RebuiltTextToSpeechArtifacts(
        original_wav_path=original_wav_path,
        clean_mp3_path=clean_mp3_path,
        chunk_manifest_path=manifest_file,
        sample_rate=sample_rate,
        sample_count=cursor,
        chunk_count=len(updated_chunks),
    )


def regenerate_manifest_chunk(
    manifest_path: str | Path,
    chunk_index: int,
    replacement_text: str | None = None,
) -> Path:
    manifest_file = Path(manifest_path).resolve()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
    if int(manifest.get("schema_version") or 0) != 1:
        raise ValueError("Ses parcalari manifest surumu desteklenmiyor")
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts import get_supertonic_synthesis_profile

    if manifest.get("synthesis_profile") != get_supertonic_synthesis_profile():
        raise ValueError("Eski motor parcalari K15 ile karistirilamaz; metnin tamamini yeniden uretin")
    chunks = list(manifest.get("chunks") or [])
    index = int(chunk_index)
    if index < 1 or index > len(chunks):
        raise ValueError("Yeniden uretilecek ses parcasi numarasi gecersiz")
    manifest_root = manifest_file.parent
    chunk = chunks[index - 1]
    text_file_value = str(chunk.get("text_file") or "")
    text_file_path = _resolve_manifest_chunk_path(manifest_root, text_file_value) if text_file_value else None
    if replacement_text is None and text_file_path and text_file_path.is_file():
        source_text = text_file_path.read_text(encoding="utf-8-sig")
    else:
        source_text = replacement_text if replacement_text is not None else str(chunk.get("text") or "")
    spoken_text = prepare_text_for_speech(source_text)
    voice_id = str(manifest.get("voice_id") or "").strip()
    language = str(manifest.get("language") or "").strip()
    sample_rate = int(manifest.get("sample_rate") or 0)
    if not voice_id or not language or sample_rate <= 0:
        raise ValueError("Tek parca yeniden uretim manifest bilgisi eksik")
    synthesis = synthesize_full_text_supertonic(spoken_text, voice_id, language, str(manifest_root))
    if int(synthesis.sample_rate) != sample_rate or int(synthesis.chunk_count) != 1:
        raise RuntimeError("Tek parca yeniden uretimi bir Supertonic parcasi vermedi")
    chunk_path = _resolve_manifest_chunk_path(manifest_root, str(chunk.get("file") or ""))
    sf.write(chunk_path, np.asarray(synthesis.audio, dtype=np.float32), sample_rate, subtype="FLOAT")
    if text_file_path is None:
        text_file_path = chunk_path.with_suffix(".txt")
        chunk["text_file"] = text_file_path.relative_to(manifest_root).as_posix()
    text_file_path.write_bytes((spoken_text + "\n").encode("utf-8"))
    chunk.update({
        "text": spoken_text,
        "sample_count": len(synthesis.audio),
        "duration": len(synthesis.audio) / sample_rate,
        "sha256": _file_sha256(chunk_path),
        "regenerated_at": datetime.now().isoformat(timespec="seconds"),
    })
    chunks[index - 1] = chunk
    manifest["chunks"] = chunks
    _write_json(manifest_file, manifest)
    return chunk_path


def synthesize_text_to_speech(
    text: str,
    output_dir: str | Path,
    voice_id: str,
    language: str = "tr",
    base_name: str = "metinden_seslendirme",
    wrap_width: int | None = None,
) -> TextToSpeechArtifacts:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    integrated_text = format_integrated_text(text, wrap_width)
    integrated_text_path = output_root / f"{base_name}_v2.txt"
    integrated_text_path.write_bytes(integrated_text.encode("utf-8"))
    spoken_text = prepare_text_for_speech(integrated_text)
    synthesis = synthesize_full_text_supertonic(spoken_text, voice_id, language, str(output_root))
    chunk_directory_path, chunk_manifest_path = persist_synthesis_chunks(
        synthesis,
        output_root,
        voice_id,
        language,
        base_name,
        integrated_text_path,
    )
    original_wav_path = output_root / f"{base_name}_orijinal.wav"
    sf.write(original_wav_path, synthesis.audio, synthesis.sample_rate, subtype="FLOAT")
    clean_mp3_path = encode_metadata_clean_mp3(
        original_wav_path,
        output_root / f"{base_name}_temiz.mp3",
    )
    return TextToSpeechArtifacts(
        integrated_text_path=integrated_text_path,
        original_wav_path=original_wav_path,
        clean_mp3_path=clean_mp3_path,
        chunk_directory_path=chunk_directory_path,
        chunk_manifest_path=chunk_manifest_path,
        sample_rate=synthesis.sample_rate,
        sample_count=len(synthesis.audio),
        chunk_count=synthesis.chunk_count,
    )


def synthesize_text_file(
    input_path: str | Path,
    output_dir: str | Path,
    voice_id: str,
    language: str = "tr",
    base_name: str = "metinden_seslendirme",
    wrap_width: int | None = None,
) -> TextToSpeechArtifacts:
    source_text = Path(input_path).read_text(encoding="utf-8-sig")
    return synthesize_text_to_speech(
        source_text,
        output_dir,
        voice_id,
        language=language,
        base_name=base_name,
        wrap_width=wrap_width,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path", nargs="?")
    parser.add_argument("output_dir", nargs="?")
    parser.add_argument("--voice-id", default="M5")
    parser.add_argument("--language", default="tr")
    parser.add_argument("--base-name")
    parser.add_argument("--wrap-width", type=int)
    parser.add_argument("--rebuild-manifest")
    parser.add_argument("--rebuild-output-dir")
    parser.add_argument("--regenerate-chunk", type=int)
    parser.add_argument("--replacement-text-file")
    args = parser.parse_args()
    if args.rebuild_manifest:
        if args.regenerate_chunk is not None:
            replacement_text = None
            if args.replacement_text_file:
                replacement_text = Path(args.replacement_text_file).read_text(encoding="utf-8-sig")
            regenerated_path = regenerate_manifest_chunk(
                args.rebuild_manifest,
                args.regenerate_chunk,
                replacement_text=replacement_text,
            )
            print(f"regenerated_chunk_path={regenerated_path}")
        result = rebuild_text_to_speech_from_manifest(
            args.rebuild_manifest,
            output_dir=args.rebuild_output_dir,
            base_name=args.base_name,
        )
        print(f"original_wav_path={result.original_wav_path}")
        print(f"clean_mp3_path={result.clean_mp3_path}")
        print(f"chunk_manifest_path={result.chunk_manifest_path}")
        print(f"duration={result.duration:.3f}")
        print(f"chunk_count={result.chunk_count}")
        return
    if not args.input_path or not args.output_dir:
        parser.error("input_path ve output_dir gerekli")
    result = synthesize_text_file(
        args.input_path,
        args.output_dir,
        args.voice_id,
        language=args.language,
        base_name=args.base_name or "metinden_seslendirme",
        wrap_width=args.wrap_width,
    )
    print(f"integrated_text_path={result.integrated_text_path}")
    print(f"original_wav_path={result.original_wav_path}")
    print(f"clean_mp3_path={result.clean_mp3_path}")
    print(f"chunk_directory_path={result.chunk_directory_path}")
    print(f"chunk_manifest_path={result.chunk_manifest_path}")
    print(f"duration={result.duration:.3f}")
    print(f"chunk_count={result.chunk_count}")


if __name__ == "__main__":
    main()
