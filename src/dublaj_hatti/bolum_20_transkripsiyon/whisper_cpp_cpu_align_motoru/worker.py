from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from dublaj_hatti.bolum_20_transkripsiyon.whisper_cpp_cpu_align_motoru.config import build_config
    from dublaj_hatti.bolum_20_transkripsiyon.whisper_cpp_cpu_align_motoru.debug_report import now_iso, write_human_report, write_json
    from dublaj_hatti.bolum_20_transkripsiyon.whisper_cpp_cpu_align_motoru.result_converter import convert_result
    from dublaj_hatti.bolum_20_transkripsiyon.whisper_cpp_cpu_align_motoru.whisper_cpp_runner import run_whisper_cpp
    from dublaj_hatti.bolum_20_transkripsiyon.whisper_cpp_cpu_align_motoru.ctc_alignment_runner import run_ctc_alignment
else:
    from .config import build_config
    from .debug_report import now_iso, write_human_report, write_json
    from .result_converter import convert_result
    from .whisper_cpp_runner import run_whisper_cpp
    from .ctc_alignment_runner import run_ctc_alignment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="whisper.cpp CPU transcribe + CTC kelime hizalama worker")
    parser.add_argument("--audio_path", required=True)
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--language", default="en")
    parser.add_argument("--cache_dir", default="")
    parser.add_argument("--alignment_device", default="cuda")
    return parser.parse_args()


def run_worker(args: argparse.Namespace) -> dict:
    started = time.monotonic()
    audio_path = Path(args.audio_path).expanduser().resolve()
    run_dir = Path(args.run_dir).expanduser().resolve()
    debug_dir = run_dir / "whisper_cpp_cpu_align_motoru"
    debug_dir.mkdir(parents=True, exist_ok=True)
    config = build_config(
        language=args.language,
        cache_dir=args.cache_dir,
        alignment_device=args.alignment_device,
    )
    run_metadata = {
        "started_at": now_iso(),
        "audio_path": str(audio_path),
        "debug_dir": str(debug_dir),
        "engine": config.engine_id,
        "engine_display_name": config.engine_display_name,
        "experiment_root": str(config.experiment_root),
        "whisper_cli_path": str(config.whisper_cli_path),
        "model_path": str(config.model_path),
        "language": config.language,
        "alignment_device": config.alignment_device,
    }
    write_json(debug_dir / "profile.json", run_metadata)
    whisper_cpp_result = run_whisper_cpp(audio_path, debug_dir, config)
    alignment_result = run_ctc_alignment(
        audio_path,
        Path(whisper_cpp_result["alignment_input_path"]),
        debug_dir,
        config,
    )
    total_seconds = round(time.monotonic() - started, 3)
    result = convert_result(whisper_cpp_result, alignment_result, config, total_seconds)
    summary = dict(result["profile_summary"])
    summary.update({
        "status": "success",
        "whisper_cpp_seconds": whisper_cpp_result.get("seconds", 0),
        "alignment_seconds": alignment_result.get("alignment_subprocess_seconds", 0),
        "total_seconds": total_seconds,
        "finished_at": now_iso(),
    })
    write_json(debug_dir / "profile.json", summary)
    write_human_report(debug_dir, summary)
    return result


def main() -> int:
    args = parse_args()
    try:
        result = run_worker(args)
    except Exception as exc:
        error_result = {
            "success": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        try:
            debug_dir = Path(args.run_dir).expanduser().resolve() / "whisper_cpp_cpu_align_motoru"
            debug_dir.mkdir(parents=True, exist_ok=True)
            write_json(debug_dir / "error.json", error_result)
            write_human_report(debug_dir, {"status": "failed", "error": str(exc)})
        except Exception:
            pass
        print(json.dumps(error_result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
