import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time


project = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(project / "src"))
from dublaj_hatti.bolum_00_omurga.runtime import crisperwhisper_turbo_ct2_runtime as runtime
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # motorun kendi src/
from dubbing_ready import build_dubbing_ready_result, load_acoustic_event_contract


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def idle_gpu():
    database = project / "bot_data.db"
    if database.exists():
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        try:
            count = connection.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','preparing','processing','deferred')").fetchone()[0]
        finally:
            connection.close()
        if count:
            raise RuntimeError("Main application has unfinished work; defer acceptance")
    result = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"], text=True)
    memory, utilization = map(int, result.strip().split(","))
    if memory > 64 or utilization > 5:
        raise RuntimeError("GPU is busy; defer acceptance")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope-registry", type=Path, required=True)
    parser.add_argument("--reference-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", nargs="+", required=True)
    args = parser.parse_args()
    scopes = read(args.scope_registry)["samples"]
    references = read(args.reference_report)["rows"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = args.output_dir / "acceptance.json"
    if receipt_path.exists():
        raise RuntimeError("Acceptance output already exists; choose a new directory")
    receipt = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "entry": str(runtime.resolve_worker_path()),
        "source_contract": runtime.crisperwhisper_turbo_ct2_contract_inputs(),
        "scope_sha256": runtime._sha256_file(args.scope_registry),
        "reference_report_sha256": runtime._sha256_file(args.reference_report),
        "timing_contract": "public_adapter_entry_through_validated_response; fresh_worker; no_transcript_cache",
        "rows": [],
    }
    runtime._write_json_atomic(receipt_path, receipt)
    try:
        for sample_id in args.samples:
            idle_gpu()
            sample = scopes[sample_id]
            audio = Path(sample["audio_path"])
            if runtime._sha256_file(audio) != sample["audio_sha256"]:
                raise RuntimeError("Acceptance audio identity changed")
            candidates = [row for row in references if row["sample"] == sample_id and row["quality_exact"]]
            if not candidates:
                raise RuntimeError(f"No accepted reference for {sample_id}")
            reference = next((row for row in candidates if row["mode"] == "baseline"), candidates[0])
            reference_root = Path(reference["run"])
            if reference["mode"] != "baseline":
                reference_root = Path(read(reference_root / "run_manifest.json")["baseline"])
            reference_request = read(reference_root / "raw_results/crisperwhisper_turbo_ct2_request.json")
            if reference_request["audio_sha256"] != sample["audio_sha256"]:
                raise RuntimeError("Reference audio identity mismatch")
            expected = read(reference_root / "raw_results/crisperwhisper_turbo_ct2_response.json")
            native_reference = expected["runtime_contract_version"] != runtime.RUNTIME_CONTRACT_VERSION
            if native_reference:
                prepared = build_dubbing_ready_result(
                    expected,
                    load_acoustic_event_contract(runtime.crisperwhisper_turbo_ct2_root() / "model_assets/ct2_float16_align"),
                )
                expected = {**expected, **{key: prepared[key] for key in ("text", "words", "segments")}}
            result_dir = args.output_dir / sample_id
            if result_dir.exists():
                raise RuntimeError("Acceptance sample output already exists")
            print(f"START {sample_id}", flush=True)
            started = time.perf_counter()
            response, completed = runtime.invoke_crisperwhisper_turbo_ct2(
                audio, result_dir, language_detection_mode=sample.get("language_detection_mode", "global_first_window"),
            )
            seconds = time.perf_counter() - started
            (result_dir / "worker_stdout.txt").write_text(completed.stdout or "", encoding="utf-8", newline="\n")
            (result_dir / "worker_stderr.txt").write_text(completed.stderr or "", encoding="utf-8", newline="\n")
            fields = reference["quality_fields"]
            compared = response
            if native_reference:
                prepared_native = build_dubbing_ready_result(
                    read(result_dir / runtime.EXPECTED_ARTIFACTS["raw"]),
                    load_acoustic_event_contract(runtime.crisperwhisper_turbo_ct2_root() / "model_assets/ct2_float16_align"),
                )
                compared = {**response, **{key: prepared_native[key] for key in ("text", "words", "segments")}}
            mismatches = [key for key in fields if expected[key] != compared[key]]
            row = {
                "sample": sample_id,
                "adapter_seconds": seconds,
                "quality_fields": fields,
                "comparison_surface": "native_prepared_before_ctc" if native_reference else "verified_ctc_delivery",
                "mismatches": mismatches,
                "quality_exact": not mismatches,
                "word_count": len(response["words"]),
                "native_softmax": response["runtime_identity"]["native_softmax"],
                "worker_timings": response["timings"],
                "reference_response_sha256": runtime._sha256_file(reference_root / "raw_results/crisperwhisper_turbo_ct2_response.json"),
                "response_sha256": runtime._sha256_file(result_dir / "crisperwhisper_turbo_ct2_response.json"),
                "gpu_after": subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True).strip(),
            }
            receipt["rows"].append(row)
            runtime._write_json_atomic(receipt_path, receipt)
            print(json.dumps(row, ensure_ascii=True), flush=True)
            if mismatches:
                raise RuntimeError(f"Exact quality mismatch: {sample_id} {mismatches}")
        if runtime.crisperwhisper_turbo_ct2_contract_inputs() != receipt["source_contract"]:
            raise RuntimeError("Production sources changed during acceptance")
        receipt["status"] = "passed"
    except Exception as error:
        receipt["status"] = "failed"
        receipt["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
        runtime._write_json_atomic(receipt_path, receipt)


if __name__ == "__main__":
    main()
