from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from dublaj_hatti.bolum_00_omurga.runtime.whisperx_runtime import build_whisperx_subprocess_env, resolve_whisperx_python

WORKER_PATH = Path(__file__).resolve().with_name("worker.py")
GIZLI_SUREC: dict[str, Any] = {"creationflags": 0x08000000} if sys.platform == "win32" else {}  # konsol penceresi yok


class CtcHizalamaHatasi(RuntimeError):
    pass


def ctc_alignment_command(audio_path: str | Path, segments_json: str | Path, language: str,
                          cache_dir: str | Path, device: str = "cuda") -> list[str]:
    return [
        str(resolve_whisperx_python()), "-B", str(WORKER_PATH),
        "--audio_path", str(audio_path),
        "--segments_json", str(segments_json),
        "--language", str(language),
        "--device", str(device),
        "--cache_dir", str(cache_dir),
    ]


def _write_debug(debug_dir: Path, command: list[str], stdout: str, stderr: str) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    for name, content in (
        ("ctc_hizalama_komutu.txt", subprocess.list2cmdline(command)),
        ("ctc_hizalama_stdout.txt", stdout),
        ("ctc_hizalama_stderr.txt", stderr),
    ):
        text = content if content.endswith("\n") or not content else content + "\n"
        (debug_dir / name).write_text(text, encoding="utf-8", newline="\n")


def run_ctc_word_alignment(
    audio_path: str | Path,
    segments_json: str | Path,
    language: str,
    cache_dir: str | Path,
    timeout_seconds: float,
    device: str = "cuda",
    debug_dir: str | Path | None = None,
) -> dict[str, Any]:
    if not WORKER_PATH.is_file():
        raise CtcHizalamaHatasi(f"CTC hizalama worker'i bulunamadi: {WORKER_PATH}")
    command = ctc_alignment_command(audio_path, segments_json, language, cache_dir, device)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout_seconds, env=build_whisperx_subprocess_env(str(cache_dir)),
            **GIZLI_SUREC,
        )
    except subprocess.TimeoutExpired as error:
        raise CtcHizalamaHatasi(f"CTC hizalama zaman asimina ugradi: {timeout_seconds} sn") from error
    elapsed = round(time.monotonic() - started, 3)
    if debug_dir is not None:
        _write_debug(Path(debug_dir), command, completed.stdout or "", completed.stderr or "")
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        tail = (completed.stderr or "").strip().splitlines()[-1:] or ["stderr bos"]
        raise CtcHizalamaHatasi(
            f"CTC hizalama ciktisi okunamadi (code {completed.returncode}): {tail[0]}"
        ) from error
    if not data.get("success"):
        raise CtcHizalamaHatasi(str(data.get("error") or f"CTC hizalama basarisiz (code {completed.returncode})"))
    data["alignment_subprocess_seconds"] = elapsed
    data["command"] = command
    return data
