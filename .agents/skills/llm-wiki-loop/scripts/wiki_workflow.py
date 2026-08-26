#!/usr/bin/env python3
"""State-bound procedure gate for LLM Wiki source ingest.

The gate observes a fixed ingest procedure. It stores hashes and bounded
receipts only; it never performs semantic judgment or copies source bodies into
run state.
"""

from __future__ import annotations

import argparse
import datetime as dt
import errno
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

try:
    import fcntl as _fcntl
except ModuleNotFoundError:  # Windows
    _fcntl = None

try:
    import msvcrt as _msvcrt
except ModuleNotFoundError:  # Unix
    _msvcrt = None


PROCEDURE_ORDER = (
    "inspect_contract_and_index",
    "inspect_source_and_existing_scope",
    "semantic_plan_frozen",
    "register_or_resolve_source",
    "update_source_page",
    "update_affected_pages",
    "refresh_index_and_log",
    "validate_structure",
    "final_review_completed",
)
MUTATION_STAGES = frozenset(
    {
        "register_or_resolve_source",
        "update_source_page",
        "update_affected_pages",
        "refresh_index_and_log",
    }
)
PRE_MUTATION_STAGES = frozenset(PROCEDURE_ORDER[:3])
NA_REASONS = {
    "register_or_resolve_source": {"existing_source_unchanged"},
    "update_source_page": {"source_page_current"},
    "update_affected_pages": {"no_affected_page_promotion"},
    "refresh_index_and_log": {"meta_current_after_batch_apply"},
}
POSTURES = {"ready", "partial", "not_ready", "blocked"}
COVERAGE_MODES = {"full", "summary"}
RETRIEVAL_REFRESH_TIMEOUT_SECONDS = 300
SEMANTIC_REFRESH_STATUSES = {"ready", "partial", "pending", "unavailable"}
RUNTIME_NAME = "llm-wiki-loop"
RUNTIME_VERSION = 1


class WorkflowError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "AGENTS.md").exists():
            return candidate
    raise WorkflowError("AGENTS.md was not found above the requested root")


def canonical_digest(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def procedure_contract_digest() -> str:
    return canonical_digest(
        {
            "schema_version": 3,
            "runtime": RUNTIME_NAME,
            "runtime_version": RUNTIME_VERSION,
            "workflow": "INGEST",
            "stages": list(PROCEDURE_ORDER),
            "not_applicable_reasons": {key: sorted(value) for key, value in NA_REASONS.items()},
            "coverage_modes": sorted(COVERAGE_MODES),
        }
    )


def resolve_inside(root: Path, raw: str) -> Path:
    root = root.resolve()
    candidate = Path(raw)
    candidate = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise WorkflowError(f"path must live inside the repository: {raw}") from exc
    return candidate


def fingerprint_files(root: Path, source: str) -> list[Path]:
    root = root.resolve()
    paths: set[Path] = set()
    for relative in ("AGENTS.md", source):
        candidate = resolve_inside(root, relative)
        if candidate.is_file():
            paths.add(candidate)
    for pattern in ("wiki/**/*.md", "warehouse/jsonl/*.jsonl"):
        paths.update(path for path in root.glob(pattern) if path.is_file())
    return sorted(paths, key=lambda item: item.relative_to(root).as_posix())


def state_fingerprint(root: Path, source: str) -> str:
    root = root.resolve()
    rows = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": file_digest(path),
            "size": path.stat().st_size,
        }
        for path in fingerprint_files(root, source)
    ]
    return canonical_digest(rows)


def run_path(root: Path, run_id: str) -> Path:
    root = root.resolve()
    if not run_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in run_id):
        raise WorkflowError("run id contains unsupported characters")
    return root / "state" / "wiki_runs" / f"{run_id}.json"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def acquire_refresh_claim(
    path: Path, run_id: str, *, blocking: bool = False
) -> int | None:
    """Acquire a process-bound claim, recovering leftover lock files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if _fcntl is not None:
            operation = _fcntl.LOCK_EX | (0 if blocking else _fcntl.LOCK_NB)
            try:
                _fcntl.flock(descriptor, operation)
            except BlockingIOError:
                os.close(descriptor)
                return None
        elif _msvcrt is not None:
            while True:
                os.lseek(descriptor, 0, os.SEEK_SET)
                try:
                    _msvcrt.locking(descriptor, _msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                        raise
                    if not blocking:
                        os.close(descriptor)
                        return None
                    time.sleep(0.05)
        else:
            raise WorkflowError("this platform has no supported file-lock backend")
        claim = {
            "run_id": run_id,
            "owner_pid": os.getpid(),
            "claimed_at": utc_now(),
        }
        encoded = (
            json.dumps(claim, ensure_ascii=False, sort_keys=True) + "\n"
        ).encode("utf-8")
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, encoded)
        os.ftruncate(descriptor, len(encoded))
        os.fsync(descriptor)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def release_refresh_claim(descriptor: int) -> None:
    try:
        if _fcntl is not None:
            _fcntl.flock(descriptor, _fcntl.LOCK_UN)
        elif _msvcrt is not None:
            os.lseek(descriptor, 0, os.SEEK_SET)
            _msvcrt.locking(descriptor, _msvcrt.LK_UNLCK, 1)
    finally:
        os.close(descriptor)


def retrieval_refresh_lock_path(root: Path) -> Path:
    """Return the one repo-global lock protecting the shared derived index."""
    return root.resolve() / "state" / "wiki_index.refresh.lock"


def run_finish_lock_path(root: Path, run_id: str) -> Path:
    """Return the run-local lock protecting finalization state transitions."""
    path = run_path(root, run_id)
    return path.with_name(path.name + ".finish.lock")


def fallback_semantic_status(payload: dict[str, Any]) -> str:
    status = payload.get("semantic_status", payload.get("semantic_lane"))
    if status == "unavailable" and int(payload.get("semantic_vectors") or 0) > 0:
        return "partial"
    if status in SEMANTIC_REFRESH_STATUSES:
        return str(status)
    return "unavailable"


def load_run(root: Path, run_id: str) -> tuple[Path, dict[str, Any]]:
    path = run_path(root, run_id)
    if not path.exists():
        raise WorkflowError(f"run not found: {run_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WorkflowError("run state must be a JSON object")
    return path, payload


def relative_refs(root: Path, refs: list[str]) -> list[dict[str, str]]:
    root = root.resolve()
    evidence: list[dict[str, str]] = []
    for raw in refs:
        path = resolve_inside(root, raw)
        if not path.is_file():
            raise WorkflowError(f"receipt reference is not a file: {raw}")
        evidence.append({"path": path.relative_to(root).as_posix(), "sha256": file_digest(path)})
    return evidence


def start_run(root: Path, source: str, coverage_mode: str = "full") -> dict[str, Any]:
    root = root.resolve()
    if coverage_mode not in COVERAGE_MODES:
        raise WorkflowError(f"unsupported coverage mode: {coverage_mode}")
    source_path = resolve_inside(root, source)
    if not source_path.is_file():
        raise WorkflowError(f"source not found: {source}")
    source_relative = source_path.relative_to(root).as_posix()
    run_id = "wiki-" + dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    fingerprint = state_fingerprint(root, source_relative)
    payload: dict[str, Any] = {
        "schema_version": 3,
        "runtime": RUNTIME_NAME,
        "runtime_version": RUNTIME_VERSION,
        "run_id": run_id,
        "workflow": "INGEST",
        "status": "active",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "source": source_relative,
        "source_sha256": file_digest(source_path),
        "coverage_mode": coverage_mode,
        "contract_digest": procedure_contract_digest(),
        "baseline_fingerprint": fingerprint,
        "last_observed_fingerprint": fingerprint,
        "first_mutation_sequence": None,
        "latest_mutation_sequence": None,
        "sequence": 0,
        "stages": {},
    }
    write_json(run_path(root, run_id), payload)
    return payload


def frontmatter_values(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise WorkflowError("coverage receipt requires YAML frontmatter")
    frontmatter = text.split("---", 2)[1]
    values: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate_full_coverage_receipt(
    root: Path, payload: dict[str, Any], refs: list[str], posture: str
) -> None:
    if payload.get("coverage_mode", "full") != "full":
        return
    receipts: list[Path] = []
    for raw in refs:
        path = resolve_inside(root, raw)
        relative = path.relative_to(root.resolve()).as_posix()
        if relative.startswith("wiki/_meta/ingest_reports/ingest-") and path.suffix == ".md":
            receipts.append(path)
    if len(receipts) != 1:
        raise WorkflowError(
            "full coverage final review requires exactly one ingest report reference"
        )

    values = frontmatter_values(receipts[0])
    expected = {
        "status": "applied",
        "coverage_mode": "full",
        "raw_path": str(payload["source"]),
        "source_sha256": str(payload["source_sha256"]),
    }
    for field, value in expected.items():
        if values.get(field) != value:
            raise WorkflowError(f"coverage receipt {field} must be {value!r}")

    counts: dict[str, int] = {}
    for field in (
        "source_units_total",
        "source_units_projected",
        "source_units_omitted",
        "source_units_deferred",
    ):
        try:
            counts[field] = int(values[field])
        except (KeyError, ValueError) as exc:
            raise WorkflowError(f"coverage receipt requires integer {field}") from exc
        if counts[field] < 0:
            raise WorkflowError(f"coverage receipt {field} must be non-negative")
    if counts["source_units_total"] <= 0:
        raise WorkflowError("coverage receipt must account for at least one source unit")
    accounted = (
        counts["source_units_projected"]
        + counts["source_units_omitted"]
        + counts["source_units_deferred"]
    )
    if accounted != counts["source_units_total"]:
        raise WorkflowError("coverage receipt unit counts do not balance")
    if counts["source_units_deferred"] and posture == "ready":
        raise WorkflowError("ready final review cannot leave deferred source units")


def next_missing_stage(payload: dict[str, Any]) -> str | None:
    stages = payload.get("stages") if isinstance(payload.get("stages"), dict) else {}
    return next((stage for stage in PROCEDURE_ORDER if stage not in stages), None)


def record_stage(
    root: Path,
    run_id: str,
    stage: str,
    *,
    refs: list[str],
    na_reason: str | None,
    result: str | None,
    posture: str | None,
    reviewed_fingerprint: str | None,
) -> dict[str, Any]:
    root = root.resolve()
    path, payload = load_run(root, run_id)
    if payload.get("status") != "active":
        raise WorkflowError("only active runs accept new stage evidence")
    if payload.get("contract_digest") != procedure_contract_digest():
        raise WorkflowError("procedure contract is stale; start a new run")
    expected = next_missing_stage(payload)
    if stage != expected:
        raise WorkflowError(f"stage order violation: expected {expected!r}, received {stage!r}")
    if na_reason is not None and na_reason not in NA_REASONS.get(stage, set()):
        raise WorkflowError(f"unsupported not-applicable reason for {stage}: {na_reason}")

    current_fingerprint = state_fingerprint(root, str(payload["source"]))
    previous_fingerprint = str(payload["last_observed_fingerprint"])
    if stage == "semantic_plan_frozen":
        if current_fingerprint != str(payload["baseline_fingerprint"]):
            raise WorkflowError("semantic plan must be frozen before the first wiki mutation")
        if not refs:
            raise WorkflowError("semantic plan receipt requires bounded artifact references")
    if stage == "validate_structure" and result not in {"passed", "failed"}:
        raise WorkflowError("validate_structure requires --result passed|failed")
    if stage == "final_review_completed":
        if posture not in POSTURES:
            raise WorkflowError("final review requires a valid --posture")
        validate_full_coverage_receipt(root, payload, refs, posture)
        if reviewed_fingerprint != current_fingerprint:
            raise WorkflowError("final review must bind to the current wiki fingerprint")
        if payload.get("latest_mutation_sequence") is None:
            raise WorkflowError("final review requires at least one observed mutation")

    sequence = int(payload.get("sequence") or 0) + 1
    if stage in MUTATION_STAGES:
        changed = current_fingerprint != previous_fingerprint
        if not changed and na_reason is None:
            raise WorkflowError(f"{stage} requires an observed mutation or bounded --na-reason")
        if changed:
            payload["first_mutation_sequence"] = payload.get("first_mutation_sequence") or sequence
            payload["latest_mutation_sequence"] = sequence

    entry: dict[str, Any] = {
        "stage_id": stage,
        "sequence": sequence,
        "recorded_at": utc_now(),
        "contract_digest": procedure_contract_digest(),
        "state_fingerprint": current_fingerprint,
        "references": relative_refs(root, refs),
    }
    if na_reason is not None:
        entry["not_applicable_reason"] = na_reason
    if result is not None:
        entry["result"] = result
    if posture is not None:
        entry["posture"] = posture
    if reviewed_fingerprint is not None:
        entry["reviewed_fingerprint"] = reviewed_fingerprint
        entry["reviewed_mutation_sequence"] = payload.get("latest_mutation_sequence")

    payload.setdefault("stages", {})[stage] = entry
    payload["sequence"] = sequence
    payload["last_observed_fingerprint"] = current_fingerprint
    payload["updated_at"] = utc_now()
    write_json(path, payload)
    return project_status(root, payload)


def project_status(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    stages = payload.get("stages") if isinstance(payload.get("stages"), dict) else {}
    missing = [stage for stage in PROCEDURE_ORDER if stage not in stages]
    stale: list[str] = []
    blockers: list[str] = []
    current_contract = procedure_contract_digest()
    current_fingerprint = state_fingerprint(root, str(payload["source"]))
    first_mutation = payload.get("first_mutation_sequence")
    latest_mutation = payload.get("latest_mutation_sequence")

    for stage, entry in stages.items():
        if not isinstance(entry, dict) or entry.get("contract_digest") != current_contract:
            stale.append(stage)
            continue
        sequence = int(entry.get("sequence") or 0)
        if stage in PRE_MUTATION_STAGES and first_mutation is not None and sequence >= int(first_mutation):
            stale.append(stage)
        if stage in {"validate_structure", "final_review_completed"} and latest_mutation is not None and sequence <= int(latest_mutation):
            stale.append(stage)

    validation = stages.get("validate_structure") if isinstance(stages.get("validate_structure"), dict) else {}
    if validation and validation.get("result") != "passed":
        blockers.append("STRUCTURAL_VALIDATION_FAILED")
    review = stages.get("final_review_completed") if isinstance(stages.get("final_review_completed"), dict) else {}
    if review:
        if review.get("reviewed_fingerprint") != current_fingerprint:
            stale.append("final_review_completed")
        if review.get("reviewed_mutation_sequence") != latest_mutation:
            stale.append("final_review_completed")
        if review.get("posture") != "ready":
            blockers.append("FINAL_REVIEW_NOT_READY")
    if missing:
        blockers.append("PROCEDURE_STAGE_MISSING")
    if stale:
        blockers.append("PROCEDURE_STAGE_STALE")

    wiki_complete = not blockers
    refresh = payload.get("retrieval_refresh")
    if not isinstance(refresh, dict):
        refresh = {
            "retrieval_ready": False,
            "retrieval_status": "pending",
            "semantic_status": "pending",
        }
    completion_fingerprint = payload.get("completion_fingerprint")
    if (
        payload.get("status") == "completed"
        and completion_fingerprint != current_fingerprint
    ):
        refresh = {
            **refresh,
            "retrieval_ready": False,
            "retrieval_status": "stale",
            "semantic_status": "pending",
            "reason": "wiki changed after the recorded retrieval refresh",
        }
    return {
        "schema_version": 1,
        "runtime": RUNTIME_NAME,
        "runtime_version": RUNTIME_VERSION,
        "workflow": "INGEST",
        "run_id": payload["run_id"],
        "source": payload["source"],
        "coverage_mode": payload.get("coverage_mode", "full"),
        "status": "pass" if not blockers else "blocked",
        "run_status": payload.get("status"),
        "contract_digest": current_contract,
        "completed_stages": [stage for stage in PROCEDURE_ORDER if stage in stages and stage not in stale],
        "missing_stages": missing,
        "stale_stages": sorted(set(stale)),
        "blockers": sorted(set(blockers)),
        "latest_mutation_sequence": latest_mutation,
        "current_fingerprint": current_fingerprint,
        "reviewed_fingerprint": review.get("reviewed_fingerprint") if review else None,
        "wiki_complete": wiki_complete,
        "retrieval_ready": bool(refresh.get("retrieval_ready", False)),
        "retrieval_status": refresh.get("retrieval_status", "pending"),
        "semantic_status": refresh.get("semantic_status", "pending"),
        "retrieval_refresh": refresh,
    }


def run_retrieval_refresh(root: Path) -> dict[str, Any]:
    script = root / "scripts" / "wiki_retrieval.py"
    if not script.is_file():
        return {
            "retrieval_ready": False,
            "retrieval_status": "not_enabled",
            "semantic_status": "unavailable",
            "reason": "SQLite retrieval helpers are not installed",
        }
    completed = None
    failure_reason = "retrieval refresh failed"
    try:
        completed = subprocess.run(
            [sys.executable, str(script), "--repo-root", str(root), "refresh"],
            check=False,
            capture_output=True,
            text=True,
            timeout=RETRIEVAL_REFRESH_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        failure_reason = str(exc)
    try:
        result = (
            json.loads(completed.stdout)
            if completed and completed.stdout.strip()
            else {}
        )
    except json.JSONDecodeError:
        result = {}
    if completed and completed.returncode == 0 and isinstance(result, dict):
        return result
    reason = (
        (completed.stderr or completed.stdout or failure_reason).strip()
        if completed
        else failure_reason
    )
    try:
        status = subprocess.run(
            [sys.executable, str(script), "--repo-root", str(root), "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        status = None
    try:
        status_payload = (
            json.loads(status.stdout) if status and status.stdout.strip() else {}
        )
    except json.JSONDecodeError:
        status_payload = {}
    semantic_status = fallback_semantic_status(status_payload)
    if status and status.returncode == 0 and status_payload.get("state") == "ready":
        return {
            **status_payload,
            "retrieval_ready": True,
            "retrieval_status": "ready",
            "semantic_status": semantic_status,
            "reason": reason[:1000],
        }
    return {
        **status_payload,
        "retrieval_ready": False,
        "retrieval_status": (
            "partial" if status_payload.get("state") in {"stale", "partial"} else "failed"
        ),
        "semantic_status": semantic_status,
        "reason": reason[:1000],
    }


def finish_run(root: Path, run_id: str) -> dict[str, Any]:
    root = root.resolve()
    run_descriptor = acquire_refresh_claim(
        run_finish_lock_path(root, run_id), run_id, blocking=True
    )
    assert run_descriptor is not None
    try:
        path, payload = load_run(root, run_id)
        projection = project_status(root, payload)
        if projection["status"] != "pass":
            return projection
        existing_refresh = payload.get("retrieval_refresh")
        if (
            isinstance(existing_refresh, dict)
            and existing_refresh.get("retrieval_status") != "pending"
        ):
            return projection
        payload["status"] = "completed"
        payload.setdefault("completed_at", utc_now())
        payload["updated_at"] = utc_now()
        payload["completion_fingerprint"] = projection["current_fingerprint"]
        if not isinstance(existing_refresh, dict):
            payload["retrieval_refresh"] = {
                "retrieval_ready": False,
                "retrieval_status": "pending",
                "semantic_status": "pending",
            }
        write_json(path, payload)

        claim_path = retrieval_refresh_lock_path(root)
        descriptor = acquire_refresh_claim(claim_path, run_id)
        if descriptor is None:
            _latest_path, latest = load_run(root, run_id)
            return project_status(root, latest)
        try:
            _latest_path, payload = load_run(root, run_id)
            projection = project_status(root, payload)
            if projection["status"] != "pass":
                return projection
            existing_refresh = payload.get("retrieval_refresh")
            if (
                isinstance(existing_refresh, dict)
                and existing_refresh.get("retrieval_status") != "pending"
            ):
                return projection
            attempt = (
                int(existing_refresh.get("attempt") or 0) + 1
                if isinstance(existing_refresh, dict)
                else 1
            )
            payload["updated_at"] = utc_now()
            payload["retrieval_refresh"] = {
                "retrieval_ready": False,
                "retrieval_status": "pending",
                "semantic_status": "pending",
                "attempt": attempt,
                "started_at": utc_now(),
                "owner_pid": os.getpid(),
            }
            write_json(path, payload)
            refresh = run_retrieval_refresh(root)
            _latest_path, latest = load_run(root, run_id)
            latest["retrieval_refresh"] = {
                **refresh,
                "attempt": attempt,
                "completed_at": utc_now(),
            }
            latest["updated_at"] = utc_now()
            write_json(path, latest)
            return project_status(root, latest)
        finally:
            release_refresh_claim(descriptor)
    finally:
        release_refresh_claim(run_descriptor)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DuckCrab-style procedure gate for LLM Wiki ingest.",
        allow_abbrev=False,
    )
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--workflow", choices=["ingest"], default="ingest")
    start.add_argument("--source", required=True)
    start.add_argument(
        "--coverage-mode",
        choices=sorted(COVERAGE_MODES),
        default="full",
        help="full is the default; summary requires explicit user intent",
    )

    stage = sub.add_parser("stage")
    stage.add_argument("--run", required=True)
    stage.add_argument("--stage", required=True, choices=PROCEDURE_ORDER)
    stage.add_argument("--ref", action="append", default=[])
    stage.add_argument("--na-reason")
    stage.add_argument("--result", choices=["passed", "failed"])
    stage.add_argument("--posture", choices=sorted(POSTURES))
    stage.add_argument("--reviewed-fingerprint")

    status = sub.add_parser("status")
    status.add_argument("--run", required=True)

    finish = sub.add_parser("finish")
    finish.add_argument("--run", required=True)

    fingerprint = sub.add_parser("fingerprint")
    fingerprint.add_argument("--source", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = find_repo_root(Path(args.root))
        if args.command == "start":
            result = start_run(root, args.source, args.coverage_mode)
        elif args.command == "stage":
            result = record_stage(
                root,
                args.run,
                args.stage,
                refs=args.ref,
                na_reason=args.na_reason,
                result=args.result,
                posture=args.posture,
                reviewed_fingerprint=args.reviewed_fingerprint,
            )
        elif args.command == "status":
            _path, payload = load_run(root, args.run)
            result = project_status(root, payload)
        elif args.command == "finish":
            result = finish_run(root, args.run)
        else:
            result = {"source": args.source, "fingerprint": state_fingerprint(root, args.source)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if args.command == "finish" and result.get("status") != "pass" else 0
    except (WorkflowError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
