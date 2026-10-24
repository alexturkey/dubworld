from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write(text)
        if not text.endswith("\n"):
            file.write("\n")


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as file:
        file.write(text)
        if not text.endswith("\n"):
            file.write("\n")


def command_to_text(command: list[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def write_human_report(debug_dir: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Whisper.cpp CPU Align Motoru Raporu",
        "",
        f"- Durum: {summary.get('status', '')}",
        f"- Motor: {summary.get('engine_display_name', '')}",
        f"- Whisper.cpp model: {summary.get('model_filename', '')}",
        f"- Dil: {summary.get('language', '')}",
        f"- Hizalama cihazi: {summary.get('alignment_device', '')}",
        f"- Whisper.cpp sure: {summary.get('whisper_cpp_seconds', 0)} sn",
        f"- Alignment sure: {summary.get('alignment_seconds', 0)} sn",
        f"- Toplam sure: {summary.get('total_seconds', 0)} sn",
        f"- Kelime sayisi: {summary.get('total_words', 0)}",
        f"- Segment sayisi: {summary.get('total_segments', 0)}",
    ]
    error = summary.get("error")
    if error:
        lines.extend(["", "## Hata", "", str(error)])
    write_text(debug_dir / "human_report.md", "\n".join(lines))

