import argparse
import json
from pathlib import Path
import sys
import time

from run_native_acceptance import idle_gpu


project = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(project / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # motorun kendi src/
from dublaj_hatti.bolum_00_omurga.runtime import crisperwhisper_turbo_ct2_runtime as runtime
from dubbing_ready import build_dubbing_ready_result, load_acoustic_event_contract
from dublaj_hatti.bolum_30_hizalama_ve_segment.nihai_dublaj_segmentleri import nihai_dublaj_segmentlerini_olustur


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise RuntimeError("Acceptance output already exists; choose a new directory")
    source = args.source_run.resolve()
    source_path = source / runtime.EXPECTED_ARTIFACTS["raw"]
    old_raw = runtime._read_json(source_path)
    request = runtime._read_json(source / "crisperwhisper_turbo_ct2_request.json")
    audio_name = Path(request["audio_path"]).name
    audio_path = source / audio_name
    if runtime._sha256_file(audio_path) != request["audio_sha256"]:
        raise RuntimeError("Reference audio identity mismatch")
    source_hash = runtime._sha256_file(source_path)
    tokenizer = load_acoustic_event_contract(runtime.crisperwhisper_turbo_ct2_root() / "model_assets/ct2_float16_align")
    expected = build_dubbing_ready_result(old_raw, tokenizer)
    idle_gpu()
    print("START_FULL_DURATION_DELIVERY_ACCEPTANCE", flush=True)
    started = time.perf_counter()
    response, completed = runtime.invoke_crisperwhisper_turbo_ct2(
        audio_path, output,
        language_detection_mode=request["language_detection_mode"],
        platform_language=request["platform_language"],
    )
    raw = runtime._read_json(output / runtime.EXPECTED_ARTIFACTS["raw"])
    ready = runtime._read_json(output / runtime.EXPECTED_ARTIFACTS["dubbing_ready"])
    evidence = runtime._read_json(output / runtime.EXPECTED_ARTIFACTS["ctc_alignment"])
    runtime._validate_shared_alignment_words(response["words"], response["physical_audio_seconds"])
    final_segments, _, _ = nihai_dublaj_segmentlerini_olustur(response["words"])
    checks = {
        "raw_text_unchanged": raw["text"] == old_raw["text"],
        "raw_words_all_fields_unchanged": raw["words"] == old_raw["words"],
        "delivered_text_expected": response["text"] == expected["text"],
        "delivered_word_text_expected": [word["word"] for word in response["words"]] == [word["word"] for word in expected["words"]],
        "alignment_input_expected": evidence["source_words"] == expected["words"],
        "delivered_words_verified": response["words"] == evidence["words"],
        "delivered_segments_verified": ready["segments"] == response["segments"],
        "source_file_unchanged": runtime._sha256_file(source_path) == source_hash,
    }
    receipt = {
        "checks": checks,
        "seconds": time.perf_counter() - started,
        "physical_audio_seconds": response["physical_audio_seconds"],
        "raw_words": len(raw["words"]),
        "delivered_words": len(response["words"]),
        "removed_events": ready["dubbing_ready"]["removed_acoustic_events"],
        "normalized_fillers": ready["dubbing_ready"]["normalized_fillers"],
        "runtime": response["runtime_contract_version"],
        "final_segments": [{"text": segment.text, "start": segment.start, "end": segment.end} for segment in final_segments],
    }
    runtime._write_json_atomic(output / "acceptance.json", receipt)
    (output / "worker_stderr.txt").write_text(completed.stderr or "", encoding="utf-8", newline="\n")
    print(json.dumps(receipt, ensure_ascii=True), flush=True)
    if not all(checks.values()):
        raise RuntimeError("Delivery acceptance failed")


if __name__ == "__main__":
    main()
