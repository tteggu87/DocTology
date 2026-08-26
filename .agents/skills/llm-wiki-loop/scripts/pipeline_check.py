#!/usr/bin/env python3
"""Structural route checker for DocTology source ingest.

This checker is intentionally structural. It reports whether a source has been
registered, projected to a source page, reported, indexed, logged, and connected
to broader wiki/proposed-JSONL growth artifacts. It never claims accepted
semantic truth.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ONTOLOGY_REGISTRIES = {
    "documents.jsonl": "document_id",
    "entities.jsonl": "entity_id",
    "claims.jsonl": "claim_id",
    "claim_evidence.jsonl": ("evidence_id", ("claim_id", "segment_id", "char_start", "char_end")),
    "segments.jsonl": "segment_id",
    "derived_edges.jsonl": ("edge_id", ("source", "target", "label", "source_claim_id")),
}

LLM_FIRST_REGISTRIES = {
    "documents.jsonl": "document_id",
    "content_units.jsonl": "unit_id",
    "source_versions.jsonl": "source_version_id",
    "compile_proposals.jsonl": "proposal_id",
    "review_events.jsonl": "review_event_id",
}

ALLOWED_STATUS_REVIEW = {
    "proposed": "needs_review",
    "accepted": "approved",
    "disputed": "conflict_open",
    "rejected": "rejected",
    "superseded": "archived",
}

ACCEPTED_REVIEW_FIELDS = (
    "reviewed_by",
    "reviewed_at",
    "decision_by",
    "decision_at",
    "decision_note",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "AGENTS.md").exists():
            return candidate
    return current


def relative_to_root(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def check_item(name: str, status: str, message: str = "", **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"name": name, "status": status}
    if message:
        item["message"] = message
    item.update(extra)
    return item


def read_jsonl_registry(
    path: Path,
    id_spec: str | tuple[str, tuple[str, ...]],
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    if not path.exists():
        return rows, [f"MISSING_REGISTRY:{path.name}"]
    for line_number, raw in enumerate(read_text(path).splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"INVALID_JSON:{path.name}:{line_number}:{exc.msg}")
            continue
        if not isinstance(row, dict):
            errors.append(f"NON_OBJECT_ROW:{path.name}:{line_number}")
            continue
        rows.append(row)
        id_field = id_spec if isinstance(id_spec, str) else id_spec[0]
        value = row.get(id_field)
        if value in (None, "") and not isinstance(id_spec, str):
            composite_fields = id_spec[1]
            composite_values = [row.get(field) for field in composite_fields]
            if all(value not in (None, "") for value in composite_values):
                value = "|".join(str(value) for value in composite_values)
        if value in (None, ""):
            errors.append(f"MISSING_ID:{path.name}:{line_number}:{id_field}")
            continue
        identity = str(value)
        if identity in seen:
            errors.append(f"DUPLICATE_ID:{path.name}:{identity}")
        seen.add(identity)
    return rows, errors


def ontology_failure_check(errors: list[str], profile: str) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    reason_samples: dict[str, str] = {}
    for error in errors:
        family = error.split(":", 1)[0]
        reason_counts[family] = reason_counts.get(family, 0) + 1
        reason_samples.setdefault(family, error)
    return check_item(
        "ontology_integrity",
        "failed",
        f"{len(errors)} ontology integrity blocker(s)",
        profile=profile,
        reason_counts=dict(sorted(reason_counts.items())),
        reason_codes=[reason_samples[family] for family in sorted(reason_samples)],
    )


def ontology_integrity_check(root: Path) -> dict[str, Any]:
    jsonl_dir = root / "warehouse" / "jsonl"
    if not jsonl_dir.exists():
        return check_item("ontology_integrity", "not_applicable", "wiki-only workspace")

    llm_first = (jsonl_dir / "content_units.jsonl").exists()
    registry_contract = LLM_FIRST_REGISTRIES if llm_first else ONTOLOGY_REGISTRIES
    registries: dict[str, list[dict[str, Any]]] = {}
    errors: list[str] = []
    for filename, id_spec in registry_contract.items():
        rows, row_errors = read_jsonl_registry(jsonl_dir / filename, id_spec)
        registries[filename] = rows
        errors.extend(row_errors)

    document_ids = {str(row["document_id"]) for row in registries["documents.jsonl"] if row.get("document_id")}
    if llm_first:
        proposal_ids = {
            str(row["proposal_id"])
            for row in registries["compile_proposals.jsonl"]
            if row.get("proposal_id")
        }
        for row in registries["content_units.jsonl"]:
            unit_id = str(row.get("unit_id") or "<missing>")
            document_id = str(row.get("document_id") or "")
            if document_id and document_id not in document_ids:
                errors.append(f"CONTENT_UNIT_UNKNOWN_DOCUMENT:{unit_id}:{document_id}")
        for row in registries["source_versions.jsonl"]:
            version_id = str(row.get("source_version_id") or "<missing>")
            document_id = str(row.get("document_id") or "")
            if document_id and document_id not in document_ids:
                errors.append(f"SOURCE_VERSION_UNKNOWN_DOCUMENT:{version_id}:{document_id}")
        for row in registries["review_events.jsonl"]:
            event_id = str(row.get("review_event_id") or "<missing>")
            target_id = str(row.get("target_id") or "")
            if target_id and target_id not in proposal_ids:
                errors.append(f"REVIEW_EVENT_UNKNOWN_PROPOSAL:{event_id}:{target_id}")
        if errors:
            return ontology_failure_check(errors, "llm-first-ontology")
        return check_item(
            "ontology_integrity",
            "ok",
            "LLM-first canonical registries and proposal/review references are structurally valid",
            profile="llm-first-ontology",
        )

    entity_ids = {str(row["entity_id"]) for row in registries["entities.jsonl"] if row.get("entity_id")}
    segment_ids = {str(row["segment_id"]) for row in registries["segments.jsonl"] if row.get("segment_id")}
    claims = {str(row["claim_id"]): row for row in registries["claims.jsonl"] if row.get("claim_id")}
    evidence_by_claim: dict[str, list[dict[str, Any]]] = {}

    for row in registries["segments.jsonl"]:
        segment_id = str(row.get("segment_id") or "<missing>")
        document_id = str(row.get("document_id") or row.get("source_document_id") or "")
        if document_id and document_id not in document_ids:
            errors.append(f"SEGMENT_UNKNOWN_DOCUMENT:{segment_id}:{document_id}")

    for row in registries["claim_evidence.jsonl"]:
        claim_id = str(row.get("claim_id") or "")
        if not claim_id or claim_id not in claims:
            errors.append(f"EVIDENCE_UNKNOWN_CLAIM:{claim_id or '<missing>'}")
        else:
            evidence_by_claim.setdefault(claim_id, []).append(row)
        document_id = str(row.get("source_document_id") or row.get("document_id") or "")
        if document_id and document_id not in document_ids:
            errors.append(f"EVIDENCE_UNKNOWN_DOCUMENT:{claim_id or '<missing>'}:{document_id}")
        segment_id = str(row.get("source_segment_id") or row.get("segment_id") or "")
        if segment_id and segment_id not in segment_ids:
            errors.append(f"EVIDENCE_UNKNOWN_SEGMENT:{claim_id or '<missing>'}:{segment_id}")

    accepted_claim_ids: set[str] = set()
    for claim_id, row in claims.items():
        status_value = row.get("status")
        review_state = str(row.get("review_state") or "")
        if status_value not in (None, ""):
            status = str(status_value)
            expected_review = ALLOWED_STATUS_REVIEW.get(status)
            if expected_review is None:
                errors.append(f"CLAIM_INVALID_STATUS:{claim_id}:{status}")
            elif review_state != expected_review:
                errors.append(f"CLAIM_INVALID_REVIEW_STATE:{claim_id}:{status}:{review_state or '<missing>'}")
        elif review_state and review_state not in set(ALLOWED_STATUS_REVIEW.values()):
            errors.append(f"CLAIM_INVALID_REVIEW_STATE:{claim_id}:legacy:{review_state}")

        accepted = str(status_value or "") == "accepted" or review_state == "approved"
        if accepted:
            accepted_claim_ids.add(claim_id)
            for field in ACCEPTED_REVIEW_FIELDS:
                if row.get(field) in (None, ""):
                    errors.append(f"ACCEPTED_CLAIM_MISSING_REVIEW:{claim_id}:{field}")
            decision_by = str(row.get("decision_by") or "")
            if decision_by and not decision_by.startswith("human:"):
                errors.append(f"ACCEPTED_CLAIM_NON_HUMAN_DECISION:{claim_id}")
            if not evidence_by_claim.get(claim_id):
                errors.append(f"ACCEPTED_CLAIM_WITHOUT_EVIDENCE:{claim_id}")

        for field in ("subject_id", "object_id"):
            entity_id = str(row.get(field) or "")
            if entity_id and entity_id not in entity_ids:
                errors.append(f"CLAIM_UNKNOWN_ENTITY:{claim_id}:{field}:{entity_id}")
        document_id = str(row.get("source_document_id") or row.get("document_id") or "")
        if document_id and document_id not in document_ids:
            errors.append(f"CLAIM_UNKNOWN_DOCUMENT:{claim_id}:{document_id}")
        segment_id = str(row.get("source_segment_id") or row.get("segment_id") or "")
        if segment_id and segment_id not in segment_ids:
            errors.append(f"CLAIM_UNKNOWN_SEGMENT:{claim_id}:{segment_id}")

    for index, row in enumerate(registries["derived_edges.jsonl"], start=1):
        source_claim_id = str(row.get("source_claim_id") or "")
        if not source_claim_id or source_claim_id not in claims:
            errors.append(f"DERIVED_UNKNOWN_CLAIM:{index}:{source_claim_id or '<missing>'}")
        edge_status = str(row.get("status") or row.get("relation_state") or "")
        requires_accepted_source = edge_status not in {"draft", "proposed", "needs_review"}
        if source_claim_id in claims and requires_accepted_source and source_claim_id not in accepted_claim_ids:
            errors.append(f"DERIVED_FROM_NON_ACCEPTED_CLAIM:{index}:{source_claim_id}")

    if errors:
        return ontology_failure_check(errors, "wiki-plus-ontology")
    return check_item(
        "ontology_integrity",
        "ok",
        "canonical JSONL registries and lifecycle references are structurally valid",
    )


def resolve_source(root: Path, source: str) -> Path:
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = root / source_path
    return source_path.resolve()


def source_rel_or_display(root: Path, source_path: Path) -> str:
    try:
        return relative_to_root(root, source_path)
    except Exception:
        return str(source_path)


def source_is_inside_repo(root: Path, source_path: Path) -> bool:
    try:
        source_path.relative_to(root.resolve())
    except ValueError:
        return False
    return True


def source_is_under_raw(root: Path, source_path: Path) -> bool:
    try:
        rel = source_path.relative_to(root.resolve()).as_posix()
    except ValueError:
        return False
    return rel == "raw" or rel.startswith("raw/")


def find_source_page(root: Path, raw_path: Path) -> Path | None:
    sources_dir = root / "wiki" / "sources"
    if not sources_dir.exists():
        return None
    try:
        relative = relative_to_root(root, raw_path)
    except Exception:
        return None
    patterns = [
        f'raw_path: "{relative}"',
        f"raw_path: {relative}",
        f"- Raw path: `{relative}`",
        f"Raw path: `{relative}`",
    ]
    for path in sorted(sources_dir.glob("*.md")):
        try:
            text = read_text(path)
        except Exception:
            continue
        if any(pattern in text for pattern in patterns):
            return path
    return None


def find_handoff(root: Path, raw_path: Path) -> Path | None:
    handoff_dir = root / "wiki" / "_meta" / "handoff"
    if not handoff_dir.exists():
        return None
    try:
        relative = relative_to_root(root, raw_path)
    except Exception:
        return None
    for path in sorted(handoff_dir.glob("handoff-*.md"), reverse=True):
        try:
            text = read_text(path)
        except Exception:
            continue
        if f'raw_path: "{relative}"' in text or f"raw_path: {relative}" in text:
            return path
    return None


def find_ingest_report(root: Path, raw_path: Path, source_page: Path | None) -> Path | None:
    reports_dir = root / "wiki" / "_meta" / "ingest_reports"
    if not reports_dir.exists():
        return None
    try:
        relative = relative_to_root(root, raw_path)
    except Exception:
        relative = raw_path.name
    source_stem = source_page.stem if source_page else ""
    patterns = [
        f"- Raw path: `{relative}`",
        f"Raw path: `{relative}`",
    ]
    if source_stem:
        patterns.append(f"[[{source_stem}]]")
    for path in sorted(reports_dir.glob("ingest-*.md"), reverse=True):
        try:
            text = read_text(path)
        except Exception:
            continue
        if any(pattern in text for pattern in patterns):
            return path
    return None


def proposed_jsonl_files_for_source(root: Path, raw_path: Path, source_page: Path | None) -> list[Path]:
    jsonl_dir = root / "warehouse" / "jsonl"
    if not jsonl_dir.exists():
        return []
    try:
        raw_rel = relative_to_root(root, raw_path)
    except Exception:
        raw_rel = ""
    source_rel = relative_to_root(root, source_page) if source_page is not None else ""
    source_stem = source_page.stem if source_page is not None else ""
    needles = [needle for needle in [raw_rel, source_rel, source_stem] if needle]
    matches: list[Path] = []
    for path in sorted(jsonl_dir.glob("proposed_*.jsonl")):
        try:
            text = read_text(path)
        except Exception:
            continue
        if any(needle in text for needle in needles):
            matches.append(path)
    return matches


def report_has_applied_affected_pages(report: Path | None) -> bool:
    if report is None or not report.exists():
        return False
    text = read_text(report)
    marker = "## Applied Affected Pages"
    if marker not in text:
        return False
    after = text.split(marker, 1)[1]
    section = after.split("\n## ", 1)[0]
    return "- `" in section and "None applied" not in section


def report_status(report: Path | None) -> str | None:
    if report is None or not report.exists():
        return None
    text = read_text(report)
    if not text.startswith("---\n"):
        return None
    frontmatter = text.split("---", 2)[1]
    for line in frontmatter.splitlines():
        if line.startswith("status:"):
            return line.split(":", 1)[1].strip().strip('"')
    return None


def source_page_synthesis_check(source_page: Path) -> dict[str, Any]:
    text = read_text(source_page)
    status = report_status(source_page) or "missing"
    placeholder_count = text.count("TBD")
    pending_statuses = {"inbox", "registered", "pending", "pending-wiki-projection"}
    if status in pending_statuses or placeholder_count:
        reasons: list[str] = []
        if status in pending_statuses:
            reasons.append(f"status={status}")
        if placeholder_count:
            reasons.append(f"TBD markers={placeholder_count}")
        return check_item(
            "source_page_synthesized",
            "pending",
            "source page synthesis is incomplete: " + ", ".join(reasons),
        )
    return check_item("source_page_synthesized", "ok", f"status={status}")


def report_has_skipped_affected_pages(report: Path | None) -> bool:
    if report is None or not report.exists():
        return False
    text = read_text(report)
    marker = "## Skipped Affected Pages"
    if marker not in text:
        return False
    after = text.split(marker, 1)[1]
    section = after.split("\n## ", 1)[0]
    return "- `" in section and "None skipped" not in section


def index_mentions(root: Path, path: Path | None) -> bool:
    if path is None:
        return False
    index_path = root / "wiki" / "_meta" / "index.md"
    if not index_path.exists():
        return False
    return f"[[{path.stem}]]" in read_text(index_path)


def log_mentions(root: Path, raw_path: Path, source_page: Path | None, report: Path | None) -> bool:
    log_path = root / "wiki" / "_meta" / "log.md"
    if not log_path.exists():
        return False
    text = read_text(log_path)
    try:
        raw_rel = relative_to_root(root, raw_path)
    except Exception:
        raw_rel = ""
    needles = [f"`{raw_rel}`"] if raw_rel else []
    if source_page is not None:
        needles.append(f"[[{source_page.stem}]]")
    if report is not None:
        needles.append(f"[[{report.stem}]]")
    return any(needle and needle in text for needle in needles)


def aggregate_status(checks: list[dict[str, Any]]) -> str:
    if any(item["status"] == "failed" for item in checks):
        return "failed"
    if any(item["status"] == "pending" for item in checks):
        return "pending"
    if any(item["status"] == "warning" for item in checks):
        return "warning"
    return "ok"


def check_source(root: Path, source: str) -> dict[str, Any]:
    root = root.resolve()
    source_path = resolve_source(root, source)
    source_display = source_rel_or_display(root, source_path)
    checks: list[dict[str, Any]] = []

    if not (root / "AGENTS.md").exists():
        checks.append(check_item("repo_contract_exists", "failed", "AGENTS.md is required"))
    else:
        checks.append(check_item("repo_contract_exists", "ok"))

    if not source_is_inside_repo(root, source_path):
        checks.append(check_item("source_inside_repo", "failed", "source must live inside the repo"))
    else:
        checks.append(check_item("source_inside_repo", "ok"))

    if not source_path.exists():
        checks.append(check_item("source_exists", "failed", "source path does not exist", path=source_display))
        status = aggregate_status(checks)
        return {
            "status": status,
            "semantic_status": "not_started",
            "source": source_display,
            "source_page_stage": "failed",
            "checks": checks,
        }

    checks.append(check_item("source_exists", "ok", path=source_display))

    if source_is_under_raw(root, source_path):
        checks.append(check_item("source_under_raw", "ok"))
    else:
        checks.append(check_item("source_under_raw", "warning", "recommended source location is raw/**"))

    source_page = find_source_page(root, source_path)
    handoff = find_handoff(root, source_path)
    report = find_ingest_report(root, source_path, source_page)
    proposed_jsonl_files = proposed_jsonl_files_for_source(root, source_path, source_page)
    applied_report = report_status(report) == "applied"
    report_has_skips = report_has_skipped_affected_pages(report)
    ontology_check = ontology_integrity_check(root)

    if source_page is None:
        if handoff is not None:
            checks.append(
                check_item(
                    "source_page_exists",
                    "pending",
                    "handoff exists, but source page projection is pending",
                    handoff=relative_to_root(root, handoff),
                )
            )
        else:
            checks.append(check_item("source_page_exists", "pending", "source registration/projection is pending"))
        checks.append(check_item("ingest_report_exists", "pending", "source-page ingest report is pending"))
        checks.append(check_item("index_mentions_source_page", "pending", "source page is pending"))
        checks.append(check_item("log_mentions_source", "pending", "source page/log closure is pending"))
        checks.append(check_item("jsonl_projection", "pending", "proposed JSONL projection is pending"))
        checks.append(check_item("broader_wiki_projection", "pending", "affected wiki projection is pending"))
        checks.append(ontology_check)
        status = aggregate_status(checks)
        return {
            "status": status,
            "semantic_status": "pending",
            "source": source_display,
            "source_page_stage": "pending",
            "source_page": None,
            "handoff": relative_to_root(root, handoff) if handoff else None,
            "checks": checks,
        }

    source_page_rel = relative_to_root(root, source_page)
    checks.append(check_item("source_page_exists", "ok", path=source_page_rel))
    checks.append(source_page_synthesis_check(source_page))

    if report is None:
        checks.append(check_item("ingest_report_exists", "pending", "source-page ingest report is pending"))
    else:
        checks.append(check_item("ingest_report_exists", "ok", path=relative_to_root(root, report)))

    checks.append(
        check_item(
            "index_mentions_source_page",
            "ok" if index_mentions(root, source_page) else "pending",
            "" if index_mentions(root, source_page) else "wiki/_meta/index.md does not mention the source page yet",
        )
    )
    if report is not None:
        checks.append(
            check_item(
                "index_mentions_ingest_report",
                "ok" if index_mentions(root, report) else "pending",
                "" if index_mentions(root, report) else "wiki/_meta/index.md does not mention the ingest report yet",
            )
        )

    checks.append(
        check_item(
            "log_mentions_source",
            "ok" if log_mentions(root, source_path, source_page, report) else "pending",
            "" if log_mentions(root, source_path, source_page, report) else "wiki/_meta/log.md does not mention this source stage yet",
        )
    )
    ontology_enabled = (root / "warehouse" / "jsonl").exists()
    if proposed_jsonl_files:
        checks.append(
            check_item(
                "jsonl_projection",
                "ok",
                "proposed JSONL records exist; accepted truth is still review-gated",
                paths=[relative_to_root(root, path) for path in proposed_jsonl_files],
            )
        )
    elif ontology_enabled:
        checks.append(check_item("jsonl_projection", "pending", "proposed JSONL records are pending or source was too thin"))
    else:
        checks.append(check_item("jsonl_projection", "not_applicable", "wiki-only workspace"))
    checks.append(ontology_check)

    if report_has_applied_affected_pages(report) and applied_report and not report_has_skips:
        checks.append(check_item("broader_wiki_projection", "ok", "applied ingest report lists affected wiki page updates"))
    elif report_has_skips:
        checks.append(check_item("broader_wiki_projection", "pending", "ingest report contains skipped affected page updates"))
    elif report_has_applied_affected_pages(report):
        checks.append(check_item("broader_wiki_projection", "pending", "affected wiki updates exist, but report is not applied"))
    else:
        checks.append(check_item("broader_wiki_projection", "pending", "affected wiki projection is pending or source-page-only"))
    checks.append(check_item("review_gate", "ok", "accepted truth remains intentionally review-gated"))

    source_page_stage = "ok" if report is not None and index_mentions(root, source_page) else "pending"
    status = aggregate_status(checks)
    semantic_status = (
        "growth_loop_applied"
        if proposed_jsonl_files and report_has_applied_affected_pages(report) and applied_report and not report_has_skips
        else "pending_broader_projection"
    )
    return {
        "status": status,
        "semantic_status": semantic_status,
        "source": source_display,
        "source_page_stage": source_page_stage,
        "source_page": source_page_rel,
        "handoff": relative_to_root(root, handoff) if handoff else None,
        "ingest_report": relative_to_root(root, report) if report else None,
        "proposed_jsonl_files": [relative_to_root(root, path) for path in proposed_jsonl_files],
        "checks": checks,
    }


def strict_blockers(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in result.get("checks", [])
        if item.get("status") in {"failed", "pending"}
    ]


def apply_procedure_context(root: Path, result: dict[str, Any], run_id: str | None) -> dict[str, Any]:
    if not run_id:
        return result
    run_path = root / "state" / "wiki_runs" / f"{run_id}.json"
    if not run_path.exists():
        result.setdefault("checks", []).append(check_item("procedure_run", "failed", "linked run is missing"))
        result["status"] = aggregate_status(result["checks"])
        return result
    try:
        run = json.loads(read_text(run_path))
    except Exception as exc:
        result.setdefault("checks", []).append(check_item("procedure_run", "failed", f"invalid linked run: {exc}"))
        result["status"] = aggregate_status(result["checks"])
        return result
    if run.get("status") != "completed" or run.get("source") != result.get("source"):
        result.setdefault("checks", []).append(check_item("procedure_run", "pending", "linked source run is not completed"))
        result["status"] = aggregate_status(result["checks"])
        return result

    workflow_path = Path(__file__).resolve().parent / "wiki_workflow.py"
    try:
        spec = importlib.util.spec_from_file_location("pipeline_check_wiki_workflow", workflow_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("workflow module loader is unavailable")
        workflow_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(workflow_module)
        projection = workflow_module.project_status(root, run)
    except Exception as exc:
        result.setdefault("checks", []).append(check_item("procedure_run", "failed", f"linked run validation failed: {exc}"))
        result["status"] = aggregate_status(result["checks"])
        return result
    if projection.get("status") != "pass":
        result.setdefault("checks", []).append(
            check_item(
                "procedure_run",
                "pending",
                "linked source run is stale or incomplete",
                missing_stages=projection.get("missing_stages", []),
                stale_stages=projection.get("stale_stages", []),
            )
        )
        result["status"] = aggregate_status(result["checks"])
        return result

    stages = run.get("stages") if isinstance(run.get("stages"), dict) else {}
    result.setdefault("checks", []).append(check_item("procedure_run", "ok", f"completed current run {run_id}"))
    if not (root / "warehouse" / "jsonl").exists():
        for item in result["checks"]:
            if item.get("name") == "ingest_report_exists" and item.get("status") == "pending":
                item.update(status="not_applicable", message="completed procedure run is the durable wiki-only receipt")
    affected = stages.get("update_affected_pages") if isinstance(stages.get("update_affected_pages"), dict) else {}
    if affected.get("not_applicable_reason") == "no_affected_page_promotion":
        for item in result["checks"]:
            if item.get("name") == "broader_wiki_projection" and item.get("status") == "pending":
                item.update(status="not_applicable", message="procedure review declared no affected-page promotion")
    result["status"] = aggregate_status(result["checks"])
    return result


def check_batch(root: Path, manifest_path: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = manifest_path if manifest_path.is_absolute() else root / manifest_path
    try:
        manifest = json.loads(read_text(manifest_path))
    except Exception as exc:
        return {
            "status": "failed",
            "semantic_status": "not_started",
            "batch_manifest": source_rel_or_display(root, manifest_path),
            "sources": [],
            "checks": [check_item("batch_manifest", "failed", f"invalid batch manifest: {exc}")],
        }
    rows = manifest.get("sources") if isinstance(manifest, dict) else None
    if not isinstance(rows, list) or not rows:
        return {
            "status": "failed",
            "semantic_status": "not_started",
            "batch_manifest": source_rel_or_display(root, manifest_path),
            "sources": [],
            "checks": [check_item("batch_manifest", "failed", "manifest requires a non-empty sources list")],
        }

    results: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, str):
            source = row
            disposition = "pass"
        elif isinstance(row, dict):
            source = str(row.get("path") or "")
            disposition = str(row.get("disposition") or "pass")
        else:
            source = ""
            disposition = "pass"
        if disposition == "deferred_with_reason" and isinstance(row, dict) and row.get("reason"):
            results.append(
                {
                    "status": "deferred",
                    "semantic_status": "deferred_with_reason",
                    "source": source,
                    "checks": [check_item("source_disposition", "not_applicable", str(row["reason"]))],
                }
            )
            continue
        if not source:
            results.append(
                {
                    "status": "failed",
                    "semantic_status": "not_started",
                    "source": source,
                    "checks": [check_item("source_identity", "failed", "source path is required")],
                }
            )
            continue
        source_result = check_source(root, source)
        run_id = str(row.get("run_id") or "") if isinstance(row, dict) else ""
        results.append(apply_procedure_context(root, source_result, run_id or None))

    statuses = [str(item.get("status")) for item in results]
    status = "failed" if "failed" in statuses else "pending" if "pending" in statuses else "warning" if "warning" in statuses else "ok"
    return {
        "status": status,
        "semantic_status": "batch_ready" if status in {"ok", "warning"} else "batch_incomplete",
        "batch_manifest": source_rel_or_display(root, manifest_path),
        "sources": results,
        "checks": [
            check_item("batch_source_count", "ok", str(len(results))),
            check_item(
                "batch_terminal_sources",
                "ok" if status in {"ok", "warning"} else status,
                f"ok={statuses.count('ok')}, deferred={statuses.count('deferred')}, pending={statuses.count('pending')}, failed={statuses.count('failed')}",
            ),
        ],
    }


def render_human(result: dict[str, Any]) -> str:
    if "sources" in result:
        lines = [
            f"Status: {result.get('status')}",
            f"Semantic status: {result.get('semantic_status')}",
            f"Batch manifest: {result.get('batch_manifest')}",
            "",
            "Sources:",
        ]
        for item in result.get("sources", []):
            lines.append(f"- {item.get('source')}: {item.get('status')} ({item.get('semantic_status')})")
        return "\n".join(lines)
    lines = [
        f"Status: {result.get('status')}",
        f"Semantic status: {result.get('semantic_status')}",
        f"Source: {result.get('source')}",
        f"Source-page stage: {result.get('source_page_stage')}",
        "",
        "Checks:",
    ]
    for item in result.get("checks", []):
        line = f"- {item['name']}: {item['status']}"
        if item.get("message"):
            line += f" — {item['message']}"
        lines.append(line)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DocTology structural source ingest route checker.",
        allow_abbrev=False,
    )
    parser.add_argument("--root", default=".", help="DocTology repo root. Defaults to current directory.")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--source", help="Source path to inspect.")
    scope.add_argument("--batch", help="Batch manifest JSON to inspect.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero for pending as well as failed work.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = find_repo_root(Path(args.root))
    result = check_batch(root, Path(args.batch)) if args.batch else check_source(root, args.source)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_human(result))
    if args.strict:
        return 1 if result.get("status") not in {"ok", "warning"} else 0
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
