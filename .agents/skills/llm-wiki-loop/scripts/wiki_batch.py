#!/usr/bin/env python3
"""Batch planner, single-writer apply, and corpus certification for LLM Wiki."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any


class BatchError(RuntimeError):
    pass


def load_sibling(name: str):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"wiki_batch_{name}", path)
    if spec is None or spec.loader is None:
        raise BatchError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


workflow = load_sibling("wiki_workflow")
pipeline_check = load_sibling("pipeline_check")

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100
BATCH_WORKFLOW_HELP = """Multi-source workflow:
  1. Freeze representative questions before planning.
  2. plan the fixed source set.
  3. start and link one run per source; stop after semantic_plan_frozen.
  4. let workers write only source-owned drafts under state/.
  5. stage every draft, then apply once with one writer.
  6. record representative-question receipts against the applied fingerprint.
  7. seal once; seal completes linked runs and certifies automatically.
  8. list discovers recorded batches without hashing the corpus.
  9. status verifies one batch and reports its deterministic next_action.
"""


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def canonical_digest(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def find_repo_root(start: Path) -> Path:
    return workflow.find_repo_root(start).resolve()


def resolve_inside(root: Path, raw: str) -> Path:
    return workflow.resolve_inside(root.resolve(), raw)


def batch_dir(root: Path, batch_id: str) -> Path:
    if not valid_batch_id(batch_id):
        raise BatchError("batch id contains unsupported characters")
    return root.resolve() / "state" / "wiki_batches" / batch_id


def valid_batch_id(batch_id: str) -> bool:
    return bool(batch_id) and not any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for character in batch_id
    )


def publish_lock_path(root: Path) -> Path:
    return root.resolve() / "state" / "wiki_batches" / ".publish.lock"


def manifest_path(root: Path, batch_id: str) -> Path:
    return batch_dir(root, batch_id) / "manifest.json"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_manifest(root: Path, batch_id: str) -> tuple[Path, dict[str, Any]]:
    path = manifest_path(root, batch_id)
    if not path.exists():
        raise BatchError(f"batch not found: {batch_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BatchError("batch manifest must be a JSON object")
    return path, payload


def corpus_files(root: Path, manifest: dict[str, Any]) -> list[Path]:
    paths: set[Path] = set()
    for relative in ("AGENTS.md", "wiki/_meta/representative_questions.json"):
        candidate = root / relative
        if candidate.is_file():
            paths.add(candidate.resolve())
    for row in manifest.get("sources", []):
        if isinstance(row, dict) and row.get("path"):
            candidate = resolve_inside(root, str(row["path"]))
            if candidate.is_file():
                paths.add(candidate)
    for pattern in ("wiki/**/*.md", "warehouse/jsonl/*.jsonl"):
        paths.update(path.resolve() for path in root.glob(pattern) if path.is_file())
    return sorted(paths, key=lambda item: item.relative_to(root).as_posix())


def corpus_fingerprint(root: Path, manifest: dict[str, Any]) -> str:
    root = root.resolve()
    rows = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": file_digest(path),
            "size": path.stat().st_size,
        }
        for path in corpus_files(root, manifest)
    ]
    return canonical_digest(rows)


def source_row(manifest: dict[str, Any], source: str) -> dict[str, Any]:
    for row in manifest.get("sources", []):
        if isinstance(row, dict) and row.get("path") == source:
            return row
    raise BatchError(f"source is not in the batch manifest: {source}")


def plan_batch(root: Path, sources: list[str]) -> dict[str, Any]:
    root = root.resolve()
    if not sources:
        raise BatchError("at least one --source is required")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in sources:
        path = resolve_inside(root, raw)
        if not path.is_file():
            raise BatchError(f"source not found: {raw}")
        relative = path.relative_to(root).as_posix()
        if relative in seen:
            continue
        seen.add(relative)
        rows.append(
            {
                "path": relative,
                "sha256": file_digest(path),
                "size": path.stat().st_size,
                "disposition": "pending",
                "reason": None,
                "run_id": None,
                "staged_files": [],
            }
        )
    batch_id = "batch-" + dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "batch_id": batch_id,
        "status": "planned",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "procedure_contract_digest": workflow.procedure_contract_digest(),
        "sources": rows,
        "apply_event": None,
        "seal_attempt": None,
        "seal_event": None,
        "certification": None,
    }
    fingerprint = corpus_fingerprint(root, payload)
    payload["baseline_fingerprint"] = fingerprint
    payload["current_fingerprint"] = fingerprint
    write_json(manifest_path(root, batch_id), payload)
    (batch_dir(root, batch_id) / "drafts").mkdir(parents=True, exist_ok=True)
    return payload


def link_run(root: Path, batch_id: str, source: str, run_id: str) -> dict[str, Any]:
    path, manifest = load_manifest(root, batch_id)
    _run_path, run = workflow.load_run(root, run_id)
    row = source_row(manifest, source)
    if run.get("source") != source:
        raise BatchError("workflow run source does not match batch source")
    row["run_id"] = run_id
    row["disposition"] = "running"
    manifest["updated_at"] = utc_now()
    write_json(path, manifest)
    return manifest


def defer_source(root: Path, batch_id: str, source: str, reason: str) -> dict[str, Any]:
    if not reason.strip():
        raise BatchError("deferred source requires a reason")
    path, manifest = load_manifest(root, batch_id)
    row = source_row(manifest, source)
    row["disposition"] = "deferred_with_reason"
    row["reason"] = reason.strip()
    manifest["updated_at"] = utc_now()
    write_json(path, manifest)
    return manifest


def allowed_target(relative: Path) -> bool:
    text = relative.as_posix()
    if text.startswith("wiki/") and relative.suffix == ".md":
        return True
    return text.startswith("warehouse/jsonl/proposed_") and relative.suffix == ".jsonl"


def stage_draft(root: Path, batch_id: str, source: str, input_dir: str) -> dict[str, Any]:
    root = root.resolve()
    path, manifest = load_manifest(root, batch_id)
    row = source_row(manifest, source)
    source_dir = resolve_inside(root, input_dir)
    if not source_dir.is_dir():
        raise BatchError("draft input must be a directory inside the repository")
    key = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    destination_root = batch_dir(root, batch_id) / "drafts" / key
    staged: list[dict[str, str]] = []
    for draft in sorted(item for item in source_dir.rglob("*") if item.is_file()):
        resolved = draft.resolve()
        try:
            relative = resolved.relative_to(source_dir.resolve())
        except ValueError as exc:
            raise BatchError(f"draft escapes input directory: {draft}") from exc
        if not allowed_target(relative):
            raise BatchError(f"draft target is outside allowed canonical paths: {relative}")
        target = destination_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(resolved, target)
        staged.append({"path": relative.as_posix(), "sha256": file_digest(target)})
    if not staged:
        raise BatchError("draft input contained no allowed files")
    row["staged_files"] = staged
    row["draft_key"] = key
    row["disposition"] = "staged"
    manifest["updated_at"] = utc_now()
    write_json(path, manifest)
    return {"batch_id": batch_id, "source": source, "staged_files": staged}


def collect_staged(root: Path, manifest: dict[str, Any]) -> list[tuple[Path, bytes, str]]:
    selected: dict[str, tuple[Path, bytes, str]] = {}
    for row in manifest.get("sources", []):
        if not isinstance(row, dict) or not row.get("staged_files"):
            continue
        draft_root = batch_dir(root, str(manifest["batch_id"])) / "drafts" / str(row["draft_key"])
        for item in row["staged_files"]:
            relative = str(item["path"])
            draft = draft_root / relative
            content = draft.read_bytes()
            digest = "sha256:" + hashlib.sha256(content).hexdigest()
            if digest != item["sha256"]:
                raise BatchError(f"staged draft changed after registration: {relative}")
            if relative in selected and selected[relative][2] != digest:
                raise BatchError(f"conflicting staged drafts target the same canonical path: {relative}")
            selected[relative] = (root / relative, content, digest)
    return [selected[key] for key in sorted(selected)]


def apply_batch(root: Path, batch_id: str, writer_id: str) -> dict[str, Any]:
    root = root.resolve()
    publish_descriptor = workflow.acquire_refresh_claim(
        publish_lock_path(root), f"apply-{batch_id}", blocking=True
    )
    assert publish_descriptor is not None
    try:
        path, manifest = load_manifest(root, batch_id)
        if manifest.get("apply_event") is not None:
            raise BatchError("batch already has a writer apply event")
        if manifest.get("procedure_contract_digest") != workflow.procedure_contract_digest():
            raise BatchError("batch procedure contract is stale; create a new plan")
        current = corpus_fingerprint(root, manifest)
        if current != manifest.get("current_fingerprint"):
            raise BatchError("unobserved_mutation: canonical state changed outside the batch writer")
        staged = collect_staged(root, manifest)
        if not staged:
            raise BatchError("batch has no staged canonical files")

        lock_path = batch_dir(root, batch_id) / "writer.lock"
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise BatchError("another writer owns this batch") from exc
        try:
            os.write(descriptor, writer_id.encode("utf-8"))
            os.close(descriptor)
            applied: list[dict[str, str]] = []
            for target, content, digest in staged:
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + f".{os.getpid()}.tmp")
                temporary.write_bytes(content)
                os.replace(temporary, target)
                applied.append({"path": target.relative_to(root).as_posix(), "sha256": digest})
            new_fingerprint = corpus_fingerprint(root, manifest)
            manifest["apply_event"] = {
                "writer_id": writer_id,
                "applied_at": utc_now(),
                "previous_fingerprint": current,
                "result_fingerprint": new_fingerprint,
                "files": applied,
            }
            manifest["current_fingerprint"] = new_fingerprint
            manifest["status"] = "applied"
            manifest["updated_at"] = utc_now()
            write_json(path, manifest)
            return manifest["apply_event"]
        finally:
            if lock_path.exists():
                lock_path.unlink()
    finally:
        workflow.release_refresh_claim(publish_descriptor)


def question_contract(root: Path) -> dict[str, Any]:
    path = root / "wiki" / "_meta" / "representative_questions.json"
    if not path.exists():
        raise BatchError("representative question contract is missing")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise BatchError("representative question contract requires a cases list")
    return payload


def record_question(
    root: Path,
    batch_id: str,
    case_id: str,
    posture: str,
    evidence_refs: list[str],
    reviewer: str,
    fingerprint: str,
) -> dict[str, Any]:
    _path, manifest = load_manifest(root, batch_id)
    current = corpus_fingerprint(root, manifest)
    if fingerprint != current or fingerprint != manifest.get("current_fingerprint"):
        raise BatchError("question receipt fingerprint is stale")
    contract = question_contract(root)
    case = next((item for item in contract["cases"] if isinstance(item, dict) and item.get("id") == case_id), None)
    if case is None:
        raise BatchError(f"unknown representative question: {case_id}")
    expected = str(case.get("expected_posture") or "")
    if posture != expected:
        raise BatchError(f"question posture mismatch: expected {expected}, received {posture}")
    if posture == "supported" and not evidence_refs:
        raise BatchError("supported representative questions require evidence references")
    evidence = workflow.relative_refs(root, evidence_refs)
    receipt = {
        "schema_version": 1,
        "batch_id": batch_id,
        "case_id": case_id,
        "posture": posture,
        "reviewer": reviewer,
        "corpus_fingerprint": fingerprint,
        "evidence": evidence,
        "recorded_at": utc_now(),
    }
    write_json(batch_dir(root, batch_id) / "question_receipts" / f"{case_id}.json", receipt)
    return receipt


def representative_question_blockers(
    root: Path, manifest: dict[str, Any], current: str
) -> list[str]:
    blockers: list[str] = []
    try:
        contract = question_contract(root)
    except Exception:
        return ["REPRESENTATIVE_QUESTION_CONTRACT_MISSING"]
    required = [
        item
        for item in contract.get("cases", [])
        if isinstance(item, dict) and item.get("required") is True
    ]
    if not required:
        blockers.append("REPRESENTATIVE_QUESTIONS_NOT_FROZEN")
    for case in required:
        case_id = str(case.get("id") or "")
        receipt_path = (
            batch_dir(root, str(manifest["batch_id"]))
            / "question_receipts"
            / f"{case_id}.json"
        )
        if not receipt_path.exists():
            blockers.append(f"QUESTION_RECEIPT_MISSING:{case_id}")
            continue
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict):
            blockers.append(f"QUESTION_RECEIPT_SCHEMA_INVALID:{case_id}")
            continue
        if receipt.get("schema_version") != 1:
            blockers.append(f"QUESTION_RECEIPT_SCHEMA_INVALID:{case_id}")
        if receipt.get("batch_id") != manifest.get("batch_id"):
            blockers.append(f"QUESTION_RECEIPT_BATCH_MISMATCH:{case_id}")
        if receipt.get("case_id") != case_id:
            blockers.append(f"QUESTION_RECEIPT_CASE_MISMATCH:{case_id}")
        if not str(receipt.get("reviewer") or "").strip():
            blockers.append(f"QUESTION_REVIEWER_MISSING:{case_id}")
        if receipt.get("corpus_fingerprint") != current:
            blockers.append(f"QUESTION_RECEIPT_STALE:{case_id}")
        if receipt.get("posture") != case.get("expected_posture"):
            blockers.append(f"QUESTION_POSTURE_MISMATCH:{case_id}")
        evidence = receipt.get("evidence")
        if not isinstance(evidence, list):
            blockers.append(f"QUESTION_EVIDENCE_INVALID:{case_id}")
            evidence = []
        if receipt.get("posture") == "supported" and not evidence:
            blockers.append(f"QUESTION_EVIDENCE_MISSING:{case_id}")
        for item in evidence:
            if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
                blockers.append(f"QUESTION_EVIDENCE_INVALID:{case_id}")
                continue
            try:
                evidence_path = resolve_inside(root, str(item["path"]))
            except Exception:
                blockers.append(f"QUESTION_EVIDENCE_INVALID:{case_id}")
                continue
            if not evidence_path.is_file() or file_digest(evidence_path) != item["sha256"]:
                blockers.append(f"QUESTION_EVIDENCE_STALE:{case_id}")
    return blockers


def source_seal_plans(
    root: Path, manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    apply_event = manifest.get("apply_event")
    if not isinstance(apply_event, dict):
        raise BatchError("batch seal requires one writer apply event")
    applied = {
        str(item.get("path")): str(item.get("sha256"))
        for item in apply_event.get("files", [])
        if isinstance(item, dict) and item.get("path")
    }
    plans: list[dict[str, Any]] = []
    for row in manifest.get("sources", []):
        if not isinstance(row, dict):
            raise BatchError("batch source row must be an object")
        source = str(row.get("path") or "")
        if row.get("disposition") == "deferred_with_reason" and row.get("reason"):
            continue
        run_id = str(row.get("run_id") or "")
        if not run_id:
            raise BatchError(f"batch seal requires a linked source run: {source}")
        _run_path, run = workflow.load_run(root, run_id)
        if run.get("source") != source or run.get("status") != "active":
            raise BatchError(f"batch seal requires an active matching run: {source}")
        if run.get("contract_digest") != workflow.procedure_contract_digest():
            raise BatchError(f"source run contract is stale: {source}")
        if workflow.next_missing_stage(run) != "register_or_resolve_source":
            raise BatchError(
                f"source run must stop after its three pre-mutation stages: {source}"
            )
        source_path = resolve_inside(root, source)
        source_digest = file_digest(source_path)
        if source_digest != row.get("sha256") or source_digest != run.get("source_sha256"):
            raise BatchError(f"source changed after batch planning: {source}")

        staged = row.get("staged_files")
        if not isinstance(staged, list) or not staged:
            raise BatchError(f"source has no staged files: {source}")
        staged_map = {
            str(item.get("path")): str(item.get("sha256"))
            for item in staged
            if isinstance(item, dict) and item.get("path")
        }
        for relative, digest in staged_map.items():
            if applied.get(relative) != digest:
                raise BatchError(
                    f"source staged file is absent from the writer apply: {source}:{relative}"
                )

        structural = pipeline_check.check_source(root, source)
        source_page = str(structural.get("source_page") or "")
        report = str(structural.get("ingest_report") or "")
        if not source_page or staged_map.get(source_page) != applied.get(source_page):
            raise BatchError(f"source page was not applied by this batch: {source}")
        if run.get("coverage_mode", "full") == "full":
            if not report or staged_map.get(report) != applied.get(report):
                raise BatchError(f"full source receipt was not applied by this batch: {source}")

        report_path = root / report if report else None
        skipped_affected = bool(
            report_path and pipeline_check.report_has_skipped_affected_pages(report_path)
        )
        affected_applied = bool(
            report_path
            and pipeline_check.report_status(report_path) == "applied"
            and pipeline_check.report_has_applied_affected_pages(report_path)
        )
        ignored_pending = {"broader_wiki_projection"}
        if run.get("coverage_mode", "full") == "summary" and not report:
            ignored_pending.add("ingest_report_exists")
        blockers = [
            item
            for item in pipeline_check.strict_blockers(structural)
            if item.get("name") not in ignored_pending
        ]
        if skipped_affected:
            blockers.append(
                {"name": "broader_wiki_projection", "status": "pending"}
            )
        if blockers:
            names = ",".join(sorted({str(item.get("name")) for item in blockers}))
            raise BatchError(f"source structural gate is incomplete: {source}:{names}")

        final_refs = [source_page]
        if report:
            final_refs.append(report)
        workflow.validate_full_coverage_receipt(root, run, final_refs, "ready")
        plans.append(
            {
                "row": row,
                "source": source,
                "run_id": run_id,
                "source_run": run,
                "mutation_refs": sorted(staged_map),
                "final_refs": final_refs,
                "no_affected_page_promotion": not affected_applied,
            }
        )
    if not plans:
        raise BatchError("batch seal requires at least one non-deferred source")
    return plans


def seal_result(
    root: Path, manifest: dict[str, Any], certification: dict[str, Any]
) -> dict[str, Any]:
    event = manifest.get("seal_event") or manifest.get("seal_attempt") or {}
    review_path = resolve_inside(root, str(event["review_path"]))
    if file_digest(review_path) != event.get("review_digest"):
        raise BatchError("batch final review receipt changed after sealing")
    return {
        "status": certification["status"],
        "batch_id": manifest["batch_id"],
        "corpus_fingerprint": event["corpus_fingerprint"],
        "review": json.loads(review_path.read_text(encoding="utf-8")),
        "source_runs": event["source_runs"],
        "retrieval_refresh": event["retrieval_refresh"],
        "certification": certification,
    }


def restore_seal_backups(root: Path, attempt: dict[str, Any]) -> None:
    review_path = resolve_inside(root, str(attempt["review_path"]))
    if file_digest(review_path) != attempt.get("review_digest"):
        raise BatchError("batch final review receipt changed during recovery")
    for item in attempt.get("prepared_runs", []):
        run_id = str(item["run_id"])
        live_path = workflow.run_path(root, run_id)
        backup_path = resolve_inside(root, str(item["backup_path"]))
        prepared_path = resolve_inside(root, str(item["prepared_path"]))
        if file_digest(backup_path) != item.get("backup_digest"):
            raise BatchError(f"source run backup changed: {run_id}")
        if file_digest(prepared_path) != item.get("prepared_digest"):
            raise BatchError(f"prepared source run changed: {run_id}")
        live_digest = file_digest(live_path)
        allowed = {str(item["backup_digest"]), str(item["prepared_digest"])}
        if live_digest not in allowed:
            raise BatchError(f"source run changed outside seal recovery: {run_id}")
        backup = json.loads(backup_path.read_text(encoding="utf-8"))
        workflow.write_json(live_path, backup)


def commit_seal_attempt(
    root: Path, path: Path, manifest: dict[str, Any]
) -> dict[str, Any]:
    attempt = manifest.get("seal_attempt")
    if not isinstance(attempt, dict) or attempt.get("status") != "prepared":
        raise BatchError("batch has no recoverable prepared seal attempt")
    current = corpus_fingerprint(root, manifest)
    if current != attempt.get("corpus_fingerprint"):
        restore_seal_backups(root, attempt)
        attempt["status"] = "stale"
        manifest["status"] = "blocked"
        manifest["updated_at"] = utc_now()
        write_json(path, manifest)
        raise BatchError("batch seal fingerprint is stale")
    question_blockers = representative_question_blockers(root, manifest, current)
    if question_blockers:
        raise BatchError("batch seal blocked: " + ",".join(sorted(question_blockers)))

    review_path = resolve_inside(root, str(attempt["review_path"]))
    if file_digest(review_path) != attempt.get("review_digest"):
        raise BatchError("batch final review receipt changed before commit")
    for item in attempt.get("prepared_runs", []):
        run_id = str(item["run_id"])
        prepared_path = resolve_inside(root, str(item["prepared_path"]))
        if file_digest(prepared_path) != item.get("prepared_digest"):
            raise BatchError(f"prepared source run changed: {run_id}")
        backup_path = resolve_inside(root, str(item["backup_path"]))
        if file_digest(backup_path) != item.get("backup_digest"):
            raise BatchError(f"source run backup changed: {run_id}")
        live_path = workflow.run_path(root, run_id)
        live_digest = file_digest(live_path)
        if live_digest == item.get("prepared_digest"):
            continue
        if live_digest != item.get("backup_digest"):
            raise BatchError(f"source run changed outside prepared seal: {run_id}")
        prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
        workflow.write_json(live_path, prepared)

    if corpus_fingerprint(root, manifest) != attempt.get("corpus_fingerprint"):
        restore_seal_backups(root, attempt)
        attempt["status"] = "stale"
        manifest["status"] = "blocked"
        manifest["updated_at"] = utc_now()
        write_json(path, manifest)
        raise BatchError("batch seal fingerprint changed during commit")

    for row in manifest.get("sources", []):
        if isinstance(row, dict) and row.get("run_id") in attempt["source_runs"]:
            row["disposition"] = "completed"
            row["sealed_fingerprint"] = attempt["corpus_fingerprint"]
    manifest["seal_event"] = {
        key: attempt[key]
        for key in (
            "sealed_at",
            "reviewer",
            "review_path",
            "review_digest",
            "corpus_fingerprint",
            "source_runs",
            "retrieval_refresh",
        )
    }
    attempt["status"] = "committed"
    manifest["status"] = "sealed"
    manifest["updated_at"] = utc_now()
    write_json(path, manifest)
    certification = certify_batch(root, str(manifest["batch_id"]))
    _latest_path, latest = load_manifest(root, str(manifest["batch_id"]))
    return seal_result(root, latest, certification)


def prepare_seal_runs(
    root: Path,
    path: Path,
    manifest: dict[str, Any],
    plans: list[dict[str, Any]],
    refresh: dict[str, Any],
) -> dict[str, Any]:
    attempt = manifest.get("seal_attempt")
    if not isinstance(attempt, dict) or attempt.get("status") != "refreshing":
        raise BatchError("batch has no refreshing seal attempt")
    current = corpus_fingerprint(root, manifest)
    if current != attempt.get("corpus_fingerprint"):
        attempt["status"] = "stale"
        manifest["status"] = "blocked"
        manifest["updated_at"] = utc_now()
        write_json(path, manifest)
        raise BatchError("batch seal fingerprint is stale")

    prepared_runs: list[dict[str, str]] = []
    attempt_root = batch_dir(root, str(manifest["batch_id"])) / "seal_attempt"
    for plan in plans:
        prepared = workflow.prepare_batch_completion(
            root,
            plan["source_run"],
            batch_id=str(manifest["batch_id"]),
            batch_fingerprint=current,
            mutation_refs=plan["mutation_refs"],
            final_refs=[*plan["final_refs"], str(attempt["review_path"])],
            no_affected_page_promotion=plan["no_affected_page_promotion"],
        )
        completed = workflow.prepare_completed_run(root, prepared, refresh)
        backup_path = attempt_root / "backups" / f"{plan['run_id']}.json"
        prepared_path = attempt_root / "prepared" / f"{plan['run_id']}.json"
        write_json(backup_path, plan["source_run"])
        write_json(prepared_path, completed)
        prepared_runs.append(
            {
                "run_id": plan["run_id"],
                "backup_path": backup_path.relative_to(root).as_posix(),
                "backup_digest": file_digest(backup_path),
                "prepared_path": prepared_path.relative_to(root).as_posix(),
                "prepared_digest": file_digest(prepared_path),
            }
        )

    attempt["status"] = "prepared"
    attempt["prepared_runs"] = prepared_runs
    attempt["retrieval_refresh"] = refresh
    manifest["updated_at"] = utc_now()
    write_json(path, manifest)
    return commit_seal_attempt(root, path, manifest)


def seal_batch(
    root: Path,
    batch_id: str,
    reviewer: str,
    review_refs: list[str],
) -> dict[str, Any]:
    root = root.resolve()
    if not reviewer.strip():
        raise BatchError("batch seal requires a reviewer")
    if not review_refs:
        raise BatchError("batch seal requires bounded review evidence")
    publish_descriptor = workflow.acquire_refresh_claim(
        publish_lock_path(root), f"seal-{batch_id}", blocking=True
    )
    assert publish_descriptor is not None
    try:
        path, manifest = load_manifest(root, batch_id)
        attempt = manifest.get("seal_attempt")
        if isinstance(attempt, dict) and attempt.get("status") == "refreshing":
            if attempt.get("reviewer") != reviewer.strip():
                raise BatchError("refreshing seal attempt belongs to another reviewer")
            current = corpus_fingerprint(root, manifest)
            if current != attempt.get("corpus_fingerprint"):
                attempt["status"] = "stale"
                manifest["status"] = "blocked"
                manifest["updated_at"] = utc_now()
                write_json(path, manifest)
                raise BatchError("batch seal fingerprint is stale")
            review_path = resolve_inside(root, str(attempt["review_path"]))
            if file_digest(review_path) != attempt.get("review_digest"):
                raise BatchError("batch final review receipt changed during refresh")
            question_blockers = representative_question_blockers(root, manifest, current)
            if question_blockers:
                raise BatchError(
                    "batch seal blocked: " + ",".join(sorted(question_blockers))
                )
            plans = source_seal_plans(root, manifest)
            refresh = workflow.run_retrieval_status(root)
            return prepare_seal_runs(root, path, manifest, plans, refresh)
        if isinstance(attempt, dict) and attempt.get("status") == "prepared":
            if attempt.get("reviewer") != reviewer.strip():
                raise BatchError("prepared seal attempt belongs to another reviewer")
            return commit_seal_attempt(root, path, manifest)
        if manifest.get("seal_event") is not None:
            certification = certify_batch(root, batch_id)
            _latest_path, latest = load_manifest(root, batch_id)
            return seal_result(root, latest, certification)
        if isinstance(attempt, dict) and attempt.get("status") == "stale":
            raise BatchError("stale seal attempt requires a new batch")
        if manifest.get("procedure_contract_digest") != workflow.procedure_contract_digest():
            raise BatchError("batch procedure contract is stale; create a new plan")
        apply_event = manifest.get("apply_event")
        if not isinstance(apply_event, dict):
            raise BatchError("batch seal requires one writer apply event")
        current = corpus_fingerprint(root, manifest)
        if (
            current != manifest.get("current_fingerprint")
            or current != apply_event.get("result_fingerprint")
        ):
            raise BatchError("batch seal fingerprint is stale")
        question_blockers = representative_question_blockers(root, manifest, current)
        if question_blockers:
            raise BatchError("batch seal blocked: " + ",".join(sorted(question_blockers)))
        review_evidence = workflow.relative_refs(root, review_refs)
        plans = source_seal_plans(root, manifest)

        review = {
            "schema_version": 1,
            "batch_id": batch_id,
            "reviewer": reviewer.strip(),
            "posture": "ready",
            "reviewed_fingerprint": current,
            "sources": [plan["source"] for plan in plans],
            "evidence": review_evidence,
            "recorded_at": utc_now(),
        }
        review_path = batch_dir(root, batch_id) / "final_review.json"
        write_json(review_path, review)
        review_relative = review_path.relative_to(root).as_posix()

        manifest["seal_attempt"] = {
            "status": "refreshing",
            "created_at": utc_now(),
            "sealed_at": utc_now(),
            "reviewer": reviewer.strip(),
            "review_path": review_relative,
            "review_digest": file_digest(review_path),
            "corpus_fingerprint": current,
            "source_runs": [plan["run_id"] for plan in plans],
            "prepared_runs": [],
            "retrieval_refresh": None,
        }
        manifest["status"] = "sealing"
        manifest["updated_at"] = utc_now()
        write_json(path, manifest)

        refresh_descriptor = workflow.acquire_refresh_claim(
            workflow.retrieval_refresh_lock_path(root), batch_id, blocking=True
        )
        assert refresh_descriptor is not None
        try:
            refresh = workflow.run_retrieval_refresh(root)
        finally:
            workflow.release_refresh_claim(refresh_descriptor)
        return prepare_seal_runs(root, path, manifest, plans, refresh)
    finally:
        workflow.release_refresh_claim(publish_descriptor)


def certification_checks(root: Path, manifest: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    blockers: list[str] = []
    source_results: list[dict[str, Any]] = []
    current = corpus_fingerprint(root, manifest)
    active_rows = [
        row
        for row in manifest.get("sources", [])
        if isinstance(row, dict)
        and not (
            row.get("disposition") == "deferred_with_reason" and row.get("reason")
        )
    ]
    if manifest.get("procedure_contract_digest") != workflow.procedure_contract_digest():
        blockers.append("PROCEDURE_CONTRACT_STALE")
    if current != manifest.get("current_fingerprint"):
        blockers.append("CORPUS_FINGERPRINT_STALE")
    if manifest.get("apply_event") is None:
        blockers.append("MISSING_WRITER_APPLY")
    seal_event = manifest.get("seal_event")
    if len(active_rows) > 1:
        if not isinstance(seal_event, dict):
            blockers.append("MULTI_SOURCE_SEAL_MISSING")
        else:
            expected_runs = {
                str(row["run_id"])
                for row in active_rows
                if row.get("run_id")
            }
            raw_sealed_runs = seal_event.get("source_runs")
            if not isinstance(raw_sealed_runs, list):
                blockers.append("MULTI_SOURCE_SEAL_RUNS_INVALID")
                sealed_runs: set[str] = set()
            else:
                sealed_runs = {str(run_id) for run_id in raw_sealed_runs}
            if seal_event.get("corpus_fingerprint") != current:
                blockers.append("MULTI_SOURCE_SEAL_STALE")
            if sealed_runs != expected_runs:
                blockers.append("MULTI_SOURCE_SEAL_RUNS_MISMATCH")
            if any(
                row.get("sealed_fingerprint") != current for row in active_rows
            ):
                blockers.append("MULTI_SOURCE_RUN_SEAL_STALE")
    if isinstance(seal_event, dict):
        try:
            review_path = resolve_inside(root, str(seal_event["review_path"]))
            if file_digest(review_path) != seal_event.get("review_digest"):
                blockers.append("BATCH_FINAL_REVIEW_STALE")
        except Exception:
            blockers.append("BATCH_FINAL_REVIEW_INVALID")

    for row in manifest.get("sources", []):
        source = str(row.get("path") or "")
        if row.get("disposition") == "deferred_with_reason" and row.get("reason"):
            source_results.append({"source": source, "status": "deferred"})
            continue
        run_id = row.get("run_id")
        if not run_id:
            blockers.append(f"SOURCE_RUN_MISSING:{source}")
            source_results.append({"source": source, "status": "blocked"})
            continue
        try:
            _run_path, run = workflow.load_run(root, str(run_id))
            procedure = workflow.project_status(root, run)
        except Exception:
            blockers.append(f"SOURCE_RUN_INVALID:{source}")
            source_results.append({"source": source, "status": "blocked"})
            continue
        structural = pipeline_check.apply_procedure_context(
            root,
            pipeline_check.check_source(root, source),
            str(run_id),
        )
        source_blockers = pipeline_check.strict_blockers(structural)
        if run.get("status") != "completed" or procedure.get("status") != "pass":
            blockers.append(f"SOURCE_PROCEDURE_INCOMPLETE:{source}")
        if source_blockers:
            blockers.append(f"SOURCE_PIPELINE_INCOMPLETE:{source}")
        source_results.append(
            {
                "source": source,
                "status": "pass" if not source_blockers and procedure.get("status") == "pass" else "blocked",
                "procedure": procedure,
                "pipeline": structural,
            }
        )

    blockers.extend(representative_question_blockers(root, manifest, current))
    return sorted(set(blockers)), source_results


def certify_batch(root: Path, batch_id: str) -> dict[str, Any]:
    root = root.resolve()
    path, manifest = load_manifest(root, batch_id)
    blockers, source_results = certification_checks(root, manifest)
    fingerprint = corpus_fingerprint(root, manifest)
    certification = {
        "schema_version": 1,
        "batch_id": batch_id,
        "status": "pass" if not blockers else "blocked",
        "created_at": utc_now(),
        "procedure_contract_digest": workflow.procedure_contract_digest(),
        "corpus_fingerprint": fingerprint,
        "source_results": source_results,
        "blockers": blockers,
    }
    certification["certification_digest"] = canonical_digest(certification)
    cert_path = batch_dir(root, batch_id) / "certification.json"
    write_json(cert_path, certification)
    manifest["certification"] = {
        "path": cert_path.relative_to(root).as_posix(),
        "digest": certification["certification_digest"],
        "status": certification["status"],
        "corpus_fingerprint": fingerprint,
    }
    manifest["status"] = "certified" if not blockers else "blocked"
    manifest["updated_at"] = utc_now()
    write_json(path, manifest)
    return certification


def batch_next_action(manifest: dict[str, Any], stale: bool) -> str:
    if stale:
        return "create_new_batch"
    attempt = (
        manifest.get("seal_attempt")
        if isinstance(manifest.get("seal_attempt"), dict)
        else {}
    )
    if attempt.get("status") == "stale":
        return "create_new_batch"
    if attempt.get("status") in {"refreshing", "prepared"}:
        return "resume_seal"
    certification = (
        manifest.get("certification")
        if isinstance(manifest.get("certification"), dict)
        else {}
    )
    if manifest.get("status") == "certified" and certification.get("status") == "pass":
        return "done"
    if manifest.get("status") == "blocked":
        return "inspect_blockers"
    active_rows = [
        row
        for row in manifest.get("sources", [])
        if isinstance(row, dict)
        and not (
            row.get("disposition") == "deferred_with_reason" and row.get("reason")
        )
    ]
    if manifest.get("apply_event") is not None:
        if manifest.get("seal_event") is not None:
            return "resume_seal"
        return (
            "record_questions_then_seal"
            if len(active_rows) > 1
            else "complete_source_then_certify"
        )
    if active_rows and all(
        row.get("run_id") and row.get("staged_files") for row in active_rows
    ):
        return "apply_once"
    return "link_runs_and_stage_drafts" if active_rows else "inspect_blockers"


def batch_source_counts(manifest: dict[str, Any]) -> dict[str, int]:
    sources = manifest.get("sources")
    if (
        not isinstance(sources, list)
        or not sources
        or any(not isinstance(row, dict) for row in sources)
    ):
        raise ValueError("manifest sources must be a non-empty list of objects")
    rows = sources
    return {
        "total": len(rows),
        "linked": sum(bool(row.get("run_id")) for row in rows),
        "staged": sum(bool(row.get("staged_files")) for row in rows),
        "deferred": sum(
            row.get("disposition") == "deferred_with_reason" and bool(row.get("reason"))
            for row in rows
        ),
    }


def list_batches(root: Path, *, active_only: bool, limit: int) -> dict[str, Any]:
    if not 1 <= limit <= MAX_LIST_LIMIT:
        raise BatchError(f"list limit must be between 1 and {MAX_LIST_LIMIT}")
    root = root.resolve()
    state_directory = root / "state"
    directory = state_directory / "wiki_batches"
    if state_directory.is_symlink() or directory.is_symlink():
        raise BatchError("batch list refuses symlinked state paths")
    items: list[dict[str, Any]] = []
    if directory.is_dir():
        for candidate in directory.iterdir():
            manifest_path = candidate / "manifest.json"
            if (
                candidate.is_symlink()
                or manifest_path.is_symlink()
                or not candidate.is_dir()
                or not manifest_path.is_file()
            ):
                continue
            try:
                manifest_path.resolve().relative_to(directory.resolve())
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(manifest, dict):
                    raise ValueError("manifest is not an object")
                if not valid_batch_id(candidate.name):
                    raise ValueError("batch id contains unsupported characters")
                if manifest.get("batch_id") != candidate.name:
                    raise ValueError("manifest batch id does not match its directory")
                updated_at = manifest.get("updated_at")
                if not isinstance(updated_at, str):
                    raise ValueError("manifest updated_at must be a string")
                parsed_updated_at = dt.datetime.fromisoformat(updated_at)
                if (
                    parsed_updated_at.tzinfo is None
                    or parsed_updated_at.utcoffset() is None
                ):
                    raise ValueError("manifest updated_at must include a timezone")
                source_counts = batch_source_counts(manifest)
            except (OSError, ValueError, json.JSONDecodeError):
                items.append(
                    {
                        "batch_id": candidate.name,
                        "status": "invalid",
                        "updated_at": None,
                        "next_action": "inspect_manifest",
                        "source_counts": {
                            "total": 0,
                            "linked": 0,
                            "staged": 0,
                            "deferred": 0,
                        },
                    }
                )
                continue
            status = str(manifest.get("status") or "unknown")
            if active_only and status == "certified":
                continue
            certification = (
                manifest.get("certification")
                if isinstance(manifest.get("certification"), dict)
                else None
            )
            items.append(
                {
                    "batch_id": str(manifest.get("batch_id") or candidate.name),
                    "status": status,
                    "updated_at": updated_at,
                    "next_action": "run_status",
                    "source_counts": source_counts,
                    "certification_status": (
                        certification.get("status") if certification else None
                    ),
                }
            )
    items.sort(
        key=lambda item: (str(item.get("updated_at") or ""), str(item["batch_id"])),
        reverse=True,
    )
    available = len(items)
    selected = items[:limit]
    return {
        "schema_version": 1,
        "freshness": "unchecked",
        "active_only": active_only,
        "limit": limit,
        "count": len(selected),
        "available": available,
        "batches": selected,
    }


def batch_status(root: Path, batch_id: str) -> dict[str, Any]:
    _path, manifest = load_manifest(root, batch_id)
    current = corpus_fingerprint(root, manifest)
    certification = manifest.get("certification") if isinstance(manifest.get("certification"), dict) else None
    canonical_stale = manifest.get("current_fingerprint") != current
    certification_stale = bool(certification and certification.get("corpus_fingerprint") != current)
    contract_stale = manifest.get("procedure_contract_digest") != workflow.procedure_contract_digest()
    stale = canonical_stale or certification_stale or contract_stale
    return {
        "batch_id": batch_id,
        "status": "stale" if stale else manifest.get("status"),
        "current_fingerprint": current,
        "recorded_fingerprint": manifest.get("current_fingerprint"),
        "certification": certification,
        "canonical_state_stale": canonical_stale,
        "certification_stale": certification_stale,
        "procedure_contract_stale": contract_stale,
        "next_action": batch_next_action(manifest, stale),
        "sources": manifest.get("sources", []),
    }


def build_parser(prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Batch and corpus gate for LLM Wiki.",
        epilog=BATCH_WORKFLOW_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument("--root", default=".", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Freeze one batch source set and baseline.")
    plan.add_argument(
        "--source", action="append", required=True,
        help="Repository-relative raw source; repeat for every source.",
    )

    link = sub.add_parser("link-run", help="Link one pre-mutation source run.")
    link.add_argument("--batch", required=True, help="Batch id from plan.")
    link.add_argument("--source", required=True, help="Source already frozen in the batch.")
    link.add_argument("--run", required=True, help="Run stopped after semantic_plan_frozen.")

    defer = sub.add_parser("defer", help="Defer one source with a bounded reason.")
    defer.add_argument("--batch", required=True, help="Batch id from plan.")
    defer.add_argument("--source", required=True, help="Source already frozen in the batch.")
    defer.add_argument("--reason", required=True, help="Concrete reason for deferral.")

    stage = sub.add_parser("stage", help="Register one state-only source draft.")
    stage.add_argument("--batch", required=True, help="Batch id from plan.")
    stage.add_argument("--source", required=True, help="Source that owns this draft.")
    stage.add_argument("--input-dir", required=True, help="Draft directory inside the repository.")

    apply = sub.add_parser("apply", help="Apply all staged canonical files exactly once.")
    apply.add_argument("--batch", required=True, help="Batch whose drafts are complete.")
    apply.add_argument("--writer-id", required=True, help="Identity of the sole canonical writer.")

    question = sub.add_parser(
        "question-receipt", help="Record one representative-question result."
    )
    question.add_argument("--batch", required=True, help="Applied batch id.")
    question.add_argument("--case-id", required=True, help="Frozen question case id.")
    question.add_argument(
        "--posture", choices=["supported", "partial", "abstain", "escalate"],
        required=True, help="Observed answer posture.",
    )
    question.add_argument(
        "--evidence-ref", action="append", default=[],
        help="Current evidence file; repeat as needed.",
    )
    question.add_argument("--reviewer", required=True, help="Reviewer identity.")
    question.add_argument(
        "--corpus-fingerprint", required=True,
        help="Current applied corpus fingerprint.",
    )

    seal = sub.add_parser(
        "seal", help="Finalize linked runs and certify one unchanged snapshot."
    )
    seal.add_argument("--batch", required=True, help="Applied batch id.")
    seal.add_argument("--reviewer", required=True, help="Final reviewer identity.")
    seal.add_argument(
        "--review-ref", action="append", required=True,
        help="Reviewed current file; repeat as needed.",
    )

    certify = sub.add_parser(
        "certify", help="Recheck certification; multi-source batches require seal."
    )
    certify.add_argument("--batch", required=True, help="Batch id to certify.")

    listing = sub.add_parser(
        "list", help="Discover recorded batches; run status before acting."
    )
    listing.add_argument(
        "--active-only", action="store_true",
        help="Exclude batches recorded as certified.",
    )
    listing.add_argument(
        "--limit", type=int, default=DEFAULT_LIST_LIMIT,
        help=f"Maximum rows to return (1-{MAX_LIST_LIMIT}; default {DEFAULT_LIST_LIMIT}).",
    )

    status = sub.add_parser("status", help="Report freshness and deterministic next_action.")
    status.add_argument("--batch", required=True, help="Batch id to inspect.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = find_repo_root(Path(args.root))
        if args.command == "plan":
            result = plan_batch(root, args.source)
        elif args.command == "link-run":
            result = link_run(root, args.batch, args.source, args.run)
        elif args.command == "defer":
            result = defer_source(root, args.batch, args.source, args.reason)
        elif args.command == "stage":
            result = stage_draft(root, args.batch, args.source, args.input_dir)
        elif args.command == "apply":
            result = apply_batch(root, args.batch, args.writer_id)
        elif args.command == "question-receipt":
            result = record_question(
                root, args.batch, args.case_id, args.posture, args.evidence_ref,
                args.reviewer, args.corpus_fingerprint,
            )
        elif args.command == "seal":
            result = seal_batch(
                root, args.batch, args.reviewer, args.review_ref,
            )
        elif args.command == "certify":
            result = certify_batch(root, args.batch)
        elif args.command == "list":
            result = list_batches(root, active_only=args.active_only, limit=args.limit)
        else:
            result = batch_status(root, args.batch)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if args.command in {"seal", "certify"} and result.get("status") != "pass" else 0
    except (BatchError, workflow.WorkflowError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
