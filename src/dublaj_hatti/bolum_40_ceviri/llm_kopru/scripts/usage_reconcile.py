from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

BRIDGE_ROOT = Path(__file__).resolve().parents[1]
USAGE_DIR = BRIDGE_ROOT / "runtime" / "usage"
VIDEO_LEDGER_FILE = USAGE_DIR / "video_usage_ledger.jsonl"
REPORT_JSON_FILE = USAGE_DIR / "cost_reconciliation_report.json"
REPORT_MD_FILE = USAGE_DIR / "cost_reconciliation_report.md"


def default_output_root() -> Path:
    """Output root of the pipeline: DUBLAJ_OUTPUT_DIR / OUTPUT_DIR (.env), else <repo>/cikti."""
    from dublaj_hatti.bolum_00_omurga.runtime.output_paths import configured_output_root

    return configured_output_root()


GEMINI_31_FLASH_LITE_INPUT_USD_PER_MILLION = 0.25
GEMINI_31_FLASH_LITE_OUTPUT_USD_PER_MILLION = 1.50


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                rows.append(data)
    return rows


def numeric(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def report_run_key(path: Path, report: dict[str, Any]) -> str:
    for key in ("run_dir", "output_dir", "run_path", "video_output_dir"):
        value = str(report.get(key) or "").strip()
        if value:
            return value
    try:
        return str(path.parents[1])
    except IndexError:
        return str(path)


def ledger_run_key(row: dict[str, Any]) -> str:
    for key in ("run_dir", "output_dir", "run_path", "video_output_dir"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return str(row.get("job_id") or row.get("video_id") or row.get("id") or "")


def extract_request_count(data: dict[str, Any]) -> int:
    for key in ("request_count", "requests_count", "gemini_request_count"):
        value = data.get(key)
        if value is not None:
            return integer(value)
    requests = data.get("requests")
    if isinstance(requests, list):
        return len(requests)
    totals = data.get("totals")
    if isinstance(totals, dict):
        return extract_request_count(totals)
    return 0


def extract_tokens(data: dict[str, Any]) -> dict[str, int]:
    totals = data.get("totals")
    if isinstance(totals, dict):
        nested = extract_tokens(totals)
        if any(nested.values()):
            return nested
    return {
        "input_tokens": integer(data.get("input_tokens") or data.get("prompt_tokens")),
        "output_tokens": integer(data.get("output_tokens") or data.get("candidate_tokens")),
        "total_tokens": integer(data.get("total_tokens")),
    }


def extract_cost_usd(data: dict[str, Any]) -> float:
    for key in ("estimated_usd", "total_usd", "cost_usd", "usd_cost", "estimated_cost_usd"):
        value = data.get(key)
        if value is not None:
            return numeric(value)
    cost = data.get("cost")
    if isinstance(cost, dict):
        return extract_cost_usd(cost)
    totals = data.get("totals")
    if isinstance(totals, dict):
        return extract_cost_usd(totals)
    tokens = extract_tokens(data)
    input_cost = tokens["input_tokens"] * GEMINI_31_FLASH_LITE_INPUT_USD_PER_MILLION / 1_000_000
    output_cost = tokens["output_tokens"] * GEMINI_31_FLASH_LITE_OUTPUT_USD_PER_MILLION / 1_000_000
    return input_cost + output_cost


def normalize_record(source: str, key: str, data: dict[str, Any], path: str = "") -> dict[str, Any]:
    tokens = extract_tokens(data)
    total_tokens = tokens["total_tokens"] or tokens["input_tokens"] + tokens["output_tokens"]
    return {
        "source": source,
        "run_key": key,
        "path": path,
        "request_count": extract_request_count(data),
        "input_tokens": tokens["input_tokens"],
        "output_tokens": tokens["output_tokens"],
        "total_tokens": total_tokens,
        "estimated_usd": round(extract_cost_usd(data), 8),
    }


def load_output_reports(output_root: Path) -> list[dict[str, Any]]:
    records = []
    if not output_root.exists():
        return records
    for path in output_root.glob("**/codex_bridge_translation/video_usage_report.json"):
        try:
            data = read_json(path)
        except Exception:  # noqa: S112 - unreadable or partial report is skipped; the ledger stays authoritative
            continue
        records.append(normalize_record("output_reports", report_run_key(path, data), data, str(path)))
    return records


def load_ledger(ledger_file: Path) -> list[dict[str, Any]]:
    records = []
    for row in read_jsonl(ledger_file):
        key = ledger_run_key(row)
        if not key:
            continue
        records.append(normalize_record("ledger", key, row, str(ledger_file)))
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "record_count": len(records),
        "request_count": sum(integer(row.get("request_count")) for row in records),
        "input_tokens": sum(integer(row.get("input_tokens")) for row in records),
        "output_tokens": sum(integer(row.get("output_tokens")) for row in records),
        "total_tokens": sum(integer(row.get("total_tokens")) for row in records),
        "estimated_usd": round(sum(numeric(row.get("estimated_usd")) for row in records), 8),
    }


def index_by_run(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed = {}
    for row in records:
        key = str(row.get("run_key") or "")
        if not key:
            continue
        if key not in indexed:
            indexed[key] = dict(row)
            continue
        target = indexed[key]
        for field in ("request_count", "input_tokens", "output_tokens", "total_tokens"):
            target[field] = integer(target.get(field)) + integer(row.get(field))
        target["estimated_usd"] = round(numeric(target.get("estimated_usd")) + numeric(row.get("estimated_usd")), 8)
    return indexed


def compare_records(ledger_records: list[dict[str, Any]], output_records: list[dict[str, Any]]) -> dict[str, Any]:
    ledger = index_by_run(ledger_records)
    output = index_by_run(output_records)
    ledger_keys = set(ledger)
    output_keys = set(output)
    different = []
    for key in sorted(ledger_keys & output_keys):
        left = ledger[key]
        right = output[key]
        fields = ["request_count", "input_tokens", "output_tokens", "total_tokens", "estimated_usd"]
        if any(left.get(field) != right.get(field) for field in fields):
            different.append({"run_key": key, "ledger": left, "output_report": right})
    status = "match"
    if ledger_keys != output_keys or different:
        status = "mismatch"
    return {
        "status": status,
        "only_in_ledger": sorted(ledger_keys - output_keys),
        "only_in_output_reports": sorted(output_keys - ledger_keys),
        "different": different,
    }


def load_billing_snapshot(path: Path | None) -> dict[str, Any]:
    if not path:
        return {"status": "not_provided"}
    try:
        data = read_json(path)
    except Exception as exc:
        return {"status": "read_error", "error": str(exc), "path": str(path)}
    billed_usd = extract_cost_usd(data)
    return {
        "status": "loaded",
        "path": str(path),
        "billed_usd": round(billed_usd, 8),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    output_root = Path(args.output_root) if args.output_root else default_output_root()
    ledger_file = Path(args.ledger_file)
    ledger_records = load_ledger(ledger_file)
    output_records = load_output_reports(output_root)
    comparison = compare_records(ledger_records, output_records)
    preferred_source = "output_reports" if output_records else "ledger"
    preferred_records = output_records if preferred_source == "output_reports" else ledger_records
    preferred_summary = summarize(preferred_records)
    preferred_summary["estimated_try"] = round(preferred_summary["estimated_usd"] * numeric(args.usd_try), 4)
    preferred_summary["remaining_credit_try"] = round(numeric(args.starting_credit_try) - preferred_summary["estimated_try"], 4)
    billing = load_billing_snapshot(Path(args.billing_snapshot) if args.billing_snapshot else None)
    if billing.get("status") == "loaded":
        billing["local_usd"] = preferred_summary["estimated_usd"]
        billing["difference_usd"] = round(numeric(billing.get("billed_usd")) - numeric(preferred_summary["estimated_usd"]), 8)
        billing["status"] = "compared"
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "output_root": str(output_root),
        "ledger_file": str(ledger_file),
        "usd_try": numeric(args.usd_try),
        "starting_credit_try": numeric(args.starting_credit_try),
        "preferred_source": preferred_source,
        "ledger": summarize(ledger_records),
        "output_reports": summarize(output_records),
        "comparison": comparison,
        "preferred_summary": preferred_summary,
        "google_billing_reconciliation": billing,
    }


def write_report(report: dict[str, Any]) -> None:
    USAGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORT_JSON_FILE, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    lines = [
        "# Cost Reconciliation Report",
        "",
        f"Generated at: {report['generated_at']}",
        f"Preferred source: {report['preferred_source']}",
        f"Comparison status: {report['comparison']['status']}",
        "",
        "| Source | Records | Requests | Input tokens | Output tokens | Total tokens | USD |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, label in (("ledger", "Ledger"), ("output_reports", "Output reports")):
        row = report[key]
        lines.append(
            f"| {label} | {row['record_count']} | {row['request_count']} | {row['input_tokens']} | "
            f"{row['output_tokens']} | {row['total_tokens']} | {row['estimated_usd']:.8f} |"
        )
    preferred = report["preferred_summary"]
    lines.extend([
        "",
        f"Estimated TRY: {preferred['estimated_try']:.4f}",
        f"Remaining credit TRY: {preferred['remaining_credit_try']:.4f}",
    ])
    with open(REPORT_MD_FILE, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--usd-try", type=float, default=46.0)
    parser.add_argument("--starting-credit-try", type=float, default=1000.0)
    parser.add_argument("--output-root", default="", help="default: DUBLAJ_OUTPUT_DIR or <repo>/cikti")
    parser.add_argument("--ledger-file", default=str(VIDEO_LEDGER_FILE))
    parser.add_argument("--billing-snapshot", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    write_report(report)
    print(f"Rapor yazildi: {REPORT_JSON_FILE}")
    print(f"Rapor yazildi: {REPORT_MD_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
