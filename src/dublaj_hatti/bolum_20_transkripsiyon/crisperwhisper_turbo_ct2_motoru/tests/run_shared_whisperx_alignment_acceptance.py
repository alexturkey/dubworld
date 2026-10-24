import argparse
import json
import shutil
import sys
import time
from pathlib import Path


project = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(project / "src"))
from dublaj_hatti.bolum_00_omurga.runtime import crisperwhisper_turbo_ct2_runtime as runtime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source_run = args.source_run.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise RuntimeError("Acceptance output already exists; choose a new directory")
    output_dir.mkdir(parents=True)

    request = runtime._read_json(source_run / "crisperwhisper_turbo_ct2_request.json")
    ready = runtime._read_json(source_run / runtime.EXPECTED_ARTIFACTS["dubbing_ready"])
    audio_path = source_run / Path(request["audio_path"]).name
    if runtime._sha256_file(audio_path) != request["audio_sha256"]:
        raise RuntimeError("Reference audio identity mismatch")
    for key in ("dubbing_ready", "profile", "diagnostics"):
        shutil.copy2(source_run / runtime.EXPECTED_ARTIFACTS[key], output_dir / runtime.EXPECTED_ARTIFACTS[key])

    source_text = ready["text"]
    source_words = [dict(word) for word in ready["words"]]
    response = {
        "text": source_text,
        "words": source_words,
        "language": ready["language"],
        "physical_audio_seconds": float(request["audio_duration_seconds"]),
    }
    started = time.perf_counter()
    delivered = runtime.align_dubbing_delivery(audio_path, output_dir, response, 1800)
    seconds = round(time.perf_counter() - started, 3)
    words = delivered["words"]
    overlaps = [index for index, (left, right) in enumerate(zip(words, words[1:])) if float(left["end"]) > float(right["start"]) + 1e-6]
    longest = sorted(
        ({"index": index, "word": word["word"], "start": word["start"], "end": word["end"], "duration": float(word["end"]) - float(word["start"])} for index, word in enumerate(words)),
        key=lambda item: item["duration"],
        reverse=True,
    )[:10]
    checks = {
        "text_character_exact": delivered["text"] == source_text,
        "word_count_exact": len(words) == len(source_words),
        "word_strings_character_exact": [word["word"] for word in words] == [word["word"] for word in source_words],
        "no_overlap": not overlaps,
        "no_word_over_1_5_seconds": all(item["duration"] <= 1.5 for item in longest),
        "shared_worker_method": delivered["ctc_alignment"]["method"] == "ctc_kelime_hizalama_kutusu",
    }
    receipt = {
        "checks": checks,
        "seconds": seconds,
        "physical_audio_seconds": response["physical_audio_seconds"],
        "word_count": len(words),
        "overlap_indexes": overlaps,
        "longest_words": longest,
        "words_295_302": [
            {"index": index, "word": words[index]["word"], "start": words[index]["start"], "end": words[index]["end"]}
            for index in range(295, min(303, len(words)))
        ],
    }
    runtime._write_json_atomic(output_dir / "acceptance.json", receipt)
    print(json.dumps(receipt, ensure_ascii=True), flush=True)
    if not all(checks.values()):
        raise RuntimeError("Shared WhisperX alignment acceptance failed")


if __name__ == "__main__":
    main()
