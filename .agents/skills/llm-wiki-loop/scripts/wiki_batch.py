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
    if not batch_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in batch_id):
        raise BatchError("batch id contains unsupported characters")
    return root.resolve() / "state" / "wiki_batches" / batch_id


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


def certification_checks(root: Path, manifest: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    blockers: list[str] = []
    source_results: list[dict[str, Any]] = []
    current = corpus_fingerprint(root, manifest)
    if manifest.get("procedure_contract_digest") != workflow.procedure_contract_digest():
        blockers.append("PROCEDURE_CONTRACT_STALE")
    if current != manifest.get("current_fingerprint"):
        blockers.append("CORPUS_FINGERPRINT_STALE")
    if manifest.get("apply_event") is None:
        blockers.append("MISSING_WRITER_APPLY")

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

    try:
        contract = question_contract(root)
    except Exception:
        blockers.append("REPRESENTATIVE_QUESTION_CONTRACT_MISSING")
        contract = {"cases": []}
    required = [item for item in contract.get("cases", []) if isinstance(item, dict) and item.get("required") is True]
    if not required:
        blockers.append("REPRESENTATIVE_QUESTIONS_NOT_FROZEN")
    for case in required:
        case_id = str(case.get("id") or "")
        receipt_path = batch_dir(root, str(manifest["batch_id"])) / "question_receipts" / f"{case_id}.json"
        if not receipt_path.exists():
            blockers.append(f"QUESTION_RECEIPT_MISSING:{case_id}")
            continue
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("corpus_fingerprint") != current:
            blockers.append(f"QUESTION_RECEIPT_STALE:{case_id}")
        if receipt.get("posture") != case.get("expected_posture"):
            blockers.append(f"QUESTION_POSTURE_MISMATCH:{case_id}")
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
        "sources": manifest.get("sources", []),
    }


def build_parser(prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Batch and corpus gate for LLM Wiki.",
        allow_abbrev=False,
    )
    parser.add_argument("--root", default=".", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan")
    plan.add_argument("--source", action="append", required=True)

    link = sub.add_parser("link-run")
    link.add_argument("--batch", required=True)
    link.add_argument("--source", required=True)
    link.add_argument("--run", required=True)

    defer = sub.add_parser("defer")
    defer.add_argument("--batch", required=True)
    defer.add_argument("--source", required=True)
    defer.add_argument("--reason", required=True)

    stage = sub.add_parser("stage")
    stage.add_argument("--batch", required=True)
    stage.add_argument("--source", required=True)
    stage.add_argument("--input-dir", required=True)

    apply = sub.add_parser("apply")
    apply.add_argument("--batch", required=True)
    apply.add_argument("--writer-id", required=True)

    question = sub.add_parser("question-receipt")
    question.add_argument("--batch", required=True)
    question.add_argument("--case-id", required=True)
    question.add_argument("--posture", choices=["supported", "partial", "abstain", "escalate"], required=True)
    question.add_argument("--evidence-ref", action="append", default=[])
    question.add_argument("--reviewer", required=True)
    question.add_argument("--corpus-fingerprint", required=True)

    certify = sub.add_parser("certify")
    certify.add_argument("--batch", required=True)

    status = sub.add_parser("status")
    status.add_argument("--batch", required=True)
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
        elif args.command == "certify":
            result = certify_batch(root, args.batch)
        else:
            result = batch_status(root, args.batch)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if args.command == "certify" and result.get("status") != "pass" else 0
    except (BatchError, workflow.WorkflowError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
