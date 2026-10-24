"""İş soyağacı: her iş klasörüne `job_lineage.json` yazar (kök iş, ebeveyn, kuşak, ilişki, ebeveynin
oluşturma anındaki durumu ve manifest özeti). Kaynak: iş deposundaki `jobs` tablosu (kaynak projedeki
Telegram'dan bağımsız karşılığı)."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

JOB_LINEAGE_SCHEMA_VERSION = 1
JOB_LINEAGE_FILENAME = "job_lineage.json"


class JobLineageError(RuntimeError):
    pass


def _as_job_id(value: Any) -> int:
    try:
        job_id = int(value)
    except (TypeError, ValueError) as exc:
        raise JobLineageError("Lineage job_id sayi olmali") from exc
    if job_id <= 0:
        raise JobLineageError("Lineage job_id pozitif olmali")
    return job_id


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise JobLineageError(f"Lineage JSON BOM iceremez: {path}")
        value = json.loads(raw.decode("utf-8"))
    except JobLineageError:
        raise
    except Exception as exc:
        raise JobLineageError(f"Lineage JSON okunamadi: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise JobLineageError("Lineage kok degeri nesne olmali")
    return value


def _manifest_digest(run_dir: Path) -> str:
    manifest_path = run_dir / "pipeline_state.json"
    try:
        return hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise JobLineageError(f"Pipeline manifest okunamadi: {manifest_path}") from exc


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    try:
        with open(temporary_path, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _relationship(row: dict[str, Any]) -> str:
    source_job_id = row.get("source_job_id")
    if source_job_id in (None, "", 0, "0"):
        return "fresh"
    source_status = str(row.get("resume_source_status") or "").strip().lower()
    if source_status == "failed":
        return "resumed_from_failed"
    if source_status == "completed":
        return "rerun_from_completed"
    raise JobLineageError("Child resume_source_status failed veya completed olmali")


def _row_dict(row: sqlite3.Row | tuple[Any, ...] | dict[str, Any], columns: list[str]) -> dict[str, Any]:
    if isinstance(row, sqlite3.Row):
        return dict(row)
    if isinstance(row, dict):
        return dict(row)
    return dict(zip(columns, row, strict=False))


def load_job_ancestry(connection: sqlite3.Connection, job_id: int | str) -> list[dict[str, Any]]:
    current_id = _as_job_id(job_id)
    visited: set[int] = set()
    rows: list[dict[str, Any]] = []
    while True:
        if current_id in visited:
            raise JobLineageError("DB lineage dongusu veya tekrar eden job_id bulundu")
        visited.add(current_id)
        cursor = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (current_id,))
        row = cursor.fetchone()
        if row is None:
            raise JobLineageError(f"DB lineage parent isi bulunamadi: {current_id}")
        item = _row_dict(row, [str(column[0]) for column in cursor.description or ()])
        item["job_id"] = _as_job_id(item.get("job_id"))
        item["relationship"] = _relationship(item)
        rows.append(item)
        parent_id = item.get("source_job_id")
        if parent_id in (None, "", 0, "0"):
            break
        current_id = _as_job_id(parent_id)
    rows.reverse()
    root_id = int(rows[0]["job_id"])
    if rows[0]["relationship"] != "fresh" or rows[0].get("source_job_id") not in (None, "", 0, "0"):
        raise JobLineageError("Lineage kok isi fresh ve parentsiz olmali")
    for index, row in enumerate(rows):
        expected_parent = rows[index - 1]["job_id"] if index else None
        actual_parent = row.get("source_job_id")
        actual_parent = None if actual_parent in (None, "", 0, "0") else _as_job_id(actual_parent)
        if actual_parent != expected_parent:
            raise JobLineageError("DB lineage parent baglantisi zincirle uyusmuyor")
        if int(row["job_id"]) == root_id and index != 0:
            raise JobLineageError("DB lineage duplicate root job_id")
    return rows


def _ensure_run_owner(connection: sqlite3.Connection, job_id: int, run_dir: Path) -> None:
    cursor = connection.execute(
        "SELECT job_id, run_dir FROM jobs WHERE COALESCE(run_dir, '') != '' ORDER BY job_id"
    )
    owners = {
        _as_job_id(row[0])
        for row in cursor.fetchall()
        if str(row[1] or "").strip() and Path(str(row[1])).resolve() == run_dir
    }
    if owners - {job_id}:
        raise JobLineageError(f"Run klasoru birden fazla yeni job'a ait: {run_dir}")


def build_job_lineage(
    connection: sqlite3.Connection,
    job_id: int | str,
    run_dir: str | Path,
) -> dict[str, Any]:
    target_job_id = _as_job_id(job_id)
    target_dir = Path(run_dir).resolve()
    _ensure_run_owner(connection, target_job_id, target_dir)
    rows = load_job_ancestry(connection, target_job_id)
    job = rows[-1]
    if int(job["job_id"]) != target_job_id:
        raise JobLineageError("DB lineage hedef job_id uyusmuyor")
    state = _read_json(target_dir / "pipeline_state.json")
    if str(state.get("job_id") or "") != str(target_job_id):
        raise JobLineageError("Pipeline manifest job_id lineage ile uyusmuyor")
    pipeline_status = str(state.get("status") or "")
    if not pipeline_status:
        raise JobLineageError("Pipeline manifest status bos olamaz")
    root_id = int(rows[0]["job_id"])
    ancestry = []
    for index, row in enumerate(rows):
        parent_id = None if index == 0 else int(rows[index - 1]["job_id"])
        ancestry_item = {
            "job_id": int(row["job_id"]),
            "parent_job_id": parent_id,
            "generation": index,
            "relationship": str(row["relationship"]),
        }
        if index > 0:
            parent = rows[index - 1]
            parent_status = str(row.get("resume_source_status") or "") or str(parent.get("status") or "")
            parent_manifest_sha256 = str(row.get("resume_source_manifest_digest") or "")
            parent_run_dir = str(parent.get("run_dir") or "").strip()
            if parent_status not in {"failed", "completed"}:
                raise JobLineageError("Parent status-at-creation gecersiz")
            if not parent_manifest_sha256:
                raise JobLineageError("Parent manifest digest DB kaydinda yok")
            if not parent_run_dir:
                raise JobLineageError("Parent run_dir bos")
            parent_dir = Path(parent_run_dir).resolve()
            parent_state = _read_json(parent_dir / "pipeline_state.json")
            parent_pipeline_status = str(row.get("resume_source_pipeline_status") or "") or str(parent_state.get("status") or "")
            if not parent_pipeline_status:
                raise JobLineageError("Parent pipeline status-at-creation bos")
            if _manifest_digest(parent_dir) != parent_manifest_sha256:
                raise JobLineageError("Parent manifest digest DB kaydiyla uyusmuyor")
            ancestry_item.update({
                "parent_status_at_creation": parent_status,
                "parent_pipeline_status_at_creation": parent_pipeline_status,
                "parent_manifest_sha256": parent_manifest_sha256,
            })
        ancestry.append(ancestry_item)
    parent = rows[-2] if len(rows) > 1 else None
    current_edge = ancestry[-1] if parent is not None else {}
    parent_status = current_edge.get("parent_status_at_creation")
    parent_pipeline_status = current_edge.get("parent_pipeline_status_at_creation")
    parent_manifest_sha256 = current_edge.get("parent_manifest_sha256")
    return {
        "schema_version": JOB_LINEAGE_SCHEMA_VERSION,
        "lineage_id": f"job:{root_id}",
        "job_id": target_job_id,
        "root_job_id": root_id,
        "parent_job_id": None if parent is None else int(parent["job_id"]),
        "generation": len(rows) - 1,
        "relationship": str(job["relationship"]),
        "job_status": str(job.get("status") or ""),
        "pipeline_status": pipeline_status,
        "resume_after_stage": str(job.get("resume_after_stage") or ""),
        "run_dir": str(target_dir),
        "parent_status_at_creation": parent_status,
        "parent_pipeline_status_at_creation": parent_pipeline_status,
        "parent_manifest_sha256": parent_manifest_sha256,
        "ancestry": ancestry,
        "evidence": {
            "source": "is_deposu/jobs",
            "parent_status_at_creation": parent_status,
            "parent_pipeline_status_at_creation": parent_pipeline_status,
            "parent_manifest_sha256": parent_manifest_sha256,
        },
    }


def validate_job_lineage(payload: dict[str, Any]) -> None:
    if int(payload.get("schema_version") or 0) != JOB_LINEAGE_SCHEMA_VERSION:
        raise JobLineageError("Lineage schema surumu desteklenmiyor")
    job_id = _as_job_id(payload.get("job_id"))
    root_id = _as_job_id(payload.get("root_job_id"))
    ancestry = payload.get("ancestry")
    payload_generation = payload.get("generation")
    if not isinstance(ancestry, list) or not ancestry or payload_generation is None or int(payload_generation) != len(ancestry) - 1:
        raise JobLineageError("Lineage ancestry/generation gecersiz")
    ids = [int(item.get("job_id")) for item in ancestry if isinstance(item, dict)]
    if len(ids) != len(ancestry) or len(ids) != len(set(ids)) or ids[-1] != job_id or ids[0] != root_id:
        raise JobLineageError("Lineage ancestry job_id zinciri gecersiz")
    for index, item in enumerate(ancestry):
        expected_parent = None if index == 0 else ids[index - 1]
        actual_parent = item.get("parent_job_id")
        item_generation = item.get("generation")
        if actual_parent != expected_parent or item_generation is None or int(item_generation) != index:
            raise JobLineageError("Lineage ancestry parent/generation gecersiz")
        if index > 0:
            if item.get("parent_status_at_creation") not in {"failed", "completed"}:
                raise JobLineageError("Lineage ancestry parent status gecersiz")
            if not str(item.get("parent_pipeline_status_at_creation") or ""):
                raise JobLineageError("Lineage ancestry parent pipeline status bos")
            if not str(item.get("parent_manifest_sha256") or ""):
                raise JobLineageError("Lineage ancestry parent digest bos")
    relationship = str(payload.get("relationship") or "")
    if relationship not in {"fresh", "resumed_from_failed", "rerun_from_completed"}:
        raise JobLineageError("Lineage relationship gecersiz")
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        raise JobLineageError("Lineage evidence nesne olmali")
    if len(ancestry) == 1:
        if payload.get("parent_job_id") is not None or relationship != "fresh":
            raise JobLineageError("Fresh lineage parent ve relationship gecersiz")
    else:
        if payload.get("parent_job_id") != ids[-2]:
            raise JobLineageError("Child lineage parent_job_id gecersiz")
        if not str(evidence.get("parent_manifest_sha256") or ""):
            raise JobLineageError("Child lineage parent digest bos")
        if payload.get("parent_status_at_creation") not in {"failed", "completed"}:
            raise JobLineageError("Child lineage parent status bos veya gecersiz")
        if not str(payload.get("parent_pipeline_status_at_creation") or ""):
            raise JobLineageError("Child lineage parent pipeline status bos")
        if payload.get("parent_manifest_sha256") != evidence.get("parent_manifest_sha256"):
            raise JobLineageError("Child lineage parent digest kopyalari uyusmuyor")


def write_job_lineage(
    db_path: str | Path,
    job_id: int | str,
    run_dir: str | Path,
) -> Path:
    target_dir = Path(run_dir).resolve()
    connection = sqlite3.connect(str(db_path), timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        payload = build_job_lineage(connection, job_id, target_dir)
        validate_job_lineage(payload)
        destination = target_dir / JOB_LINEAGE_FILENAME
        _atomic_write_json(destination, payload)
        written = _read_json(destination)
        validate_job_lineage(written)
        return destination
    finally:
        connection.close()


def read_job_lineage(run_dir: str | Path) -> dict[str, Any]:
    payload = _read_json(Path(run_dir).resolve() / JOB_LINEAGE_FILENAME)
    validate_job_lineage(payload)
    return payload
