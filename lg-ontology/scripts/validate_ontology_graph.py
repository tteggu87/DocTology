#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None

from _ontology_core_support import (
    SCHEMA_VERSION,
    build_paths,
    load_json,
    load_jsonl,
    load_yaml,
    sha256_file,
    sha256_text,
)


ALLOWED_STATUS_REVIEW = {
    "proposed": "needs_review",
    "accepted": "approved",
    "disputed": "conflict_open",
    "rejected": "rejected",
    "superseded": "archived",
}
ACCEPTED_REQUIRED_FIELDS = [
    "reviewed_by",
    "reviewed_at",
    "decision_by",
    "decision_at",
    "decision_note",
]
CLAIM_REQUIRED_FIELDS = [
    "claim_id",
    "subject_id",
    "predicate",
    "object_id",
    "subject_type",
    "object_type",
    "status",
    "confidence",
    "asserted_by",
    "source_document_id",
    "review_state",
]
EVIDENCE_REQUIRED_FIELDS = [
    "evidence_id",
    "claim_id",
    "source_document_id",
    "start_char",
    "end_char",
    "evidence_type",
    "support",
    "confidence",
    "excerpt",
    "captured_by",
]
SEGMENT_REQUIRED_FIELDS = [
    "segment_id",
    "document_id",
    "document_type",
    "text",
    "start_char",
    "end_char",
    "ordinal",
    "status",
    "text_hash",
    "segmenter_version",
]
DERIVED_REQUIRED_FIELDS = [
    "edge_id",
    "source_claim_id",
    "rule_key",
    "subject_id",
    "predicate",
    "object_id",
    "status",
    "derived_at",
]


class ValidationReport:
    def __init__(self, repo_root: Path, strictness: str) -> None:
        self.repo_root = repo_root
        self.strictness = strictness
        self.errors: list[dict[str, str]] = []
        self.warnings: list[dict[str, str]] = []

    def add_error(self, code: str, message: str, path: Path | None = None) -> None:
        self.errors.append(self._issue("error", code, message, path))

    def add_warning(self, code: str, message: str, path: Path | None = None) -> None:
        self.warnings.append(self._issue("warning", code, message, path))

    def _issue(self, level: str, code: str, message: str, path: Path | None) -> dict[str, str]:
        issue = {"level": level, "code": code, "message": message}
        if path is not None:
            issue["path"] = self.display_path(path)
        return issue

    def display_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.repo_root.resolve()).as_posix()
        except Exception:
            return path.as_posix()

    def status(self) -> str:
        if self.errors:
            return "failed"
        if self.warnings:
            return "passed_with_warnings"
        return "passed"

    def to_json(self) -> str:
        return json.dumps(
            {
                "repo_root": str(self.repo_root),
                "summary": {
                    "status": self.status(),
                    "errors": len(self.errors),
                    "warnings": len(self.warnings),
                },
                "errors": self.errors,
                "warnings": self.warnings,
            },
            indent=2,
        )

    def print_text(self) -> None:
        print(f"Repo root: {self.repo_root}")
        print(f"Status: {self.status()}")
        print(f"Errors: {len(self.errors)}")
        print(f"Warnings: {len(self.warnings)}")
        if self.errors:
            print("\nErrors:")
            for issue in self.errors:
                location = f" ({issue['path']})" if "path" in issue else ""
                print(f"- [{issue['code']}] {issue['message']}{location}")
        if self.warnings:
            print("\nWarnings:")
            for issue in self.warnings:
                location = f" ({issue['path']})" if "path" in issue else ""
                print(f"- [{issue['code']}] {issue['message']}{location}")


def parse_iso8601(value: object) -> datetime | None:
    if value in (None, "", "null"):
        return None
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def windows_overlap(
    left_from: datetime | None,
    left_to: datetime | None,
    right_from: datetime | None,
    right_to: datetime | None,
) -> bool:
    left_from = left_from or datetime.min.replace(tzinfo=timezone.utc)
    right_from = right_from or datetime.min.replace(tzinfo=timezone.utc)
    left_to = left_to or datetime.max.replace(tzinfo=timezone.utc)
    right_to = right_to or datetime.max.replace(tzinfo=timezone.utc)
    return left_from <= right_to and right_from <= left_to


def load_yaml_safe(path: Path, report: ValidationReport, required: bool = True) -> object | None:
    if not path.exists():
        if required:
            report.add_error("yaml.missing", "Required YAML file is missing.", path)
        return None
    try:
        return load_yaml(path)
    except Exception as exc:
        report.add_error("yaml.parse_failed", f"Failed to parse YAML: {exc}", path)
        return None


def load_json_safe(path: Path, report: ValidationReport) -> object | None:
    try:
        return load_json(path)
    except Exception as exc:
        report.add_error("json.parse_failed", f"Failed to parse JSON: {exc}", path)
        return None


def load_jsonl_safe(path: Path, report: ValidationReport, required: bool = True) -> list[dict[str, object]]:
    if not path.exists():
        if required:
            report.add_error("jsonl.missing", "Required JSONL file is missing.", path)
        return []
    try:
        return load_jsonl(path)
    except Exception as exc:
        report.add_error("jsonl.parse_failed", f"Failed to parse JSONL: {exc}", path)
        return []


def require_mapping(value: object, section_key: str, path: Path, report: ValidationReport) -> dict[str, object]:
    if not isinstance(value, dict):
        report.add_error("yaml.invalid_root", f"Expected mapping with `{section_key}` section.", path)
        return {}
    return value


def load_section_items(
    data: object,
    section_key: str,
    item_key: str,
    path: Path,
    report: ValidationReport,
) -> dict[str, dict[str, object]]:
    mapping = require_mapping(data, section_key, path, report)
    section = mapping.get(section_key)
    if not isinstance(section, list):
        report.add_error("yaml.invalid_section", f"`{section_key}` must be a list.", path)
        return {}
    items: dict[str, dict[str, object]] = {}
    for entry in section:
        if not isinstance(entry, dict):
            report.add_error("yaml.invalid_item", f"Each `{section_key}` entry must be a mapping.", path)
            continue
        raw_key = entry.get(item_key)
        if not raw_key:
            report.add_error("yaml.missing_key", f"Missing `{item_key}` in `{section_key}` entry.", path)
            continue
        key = str(raw_key)
        if key in items:
            report.add_error("yaml.duplicate_key", f"Duplicate `{item_key}` `{key}`.", path)
            continue
        items[key] = entry
    return items


def keyed_records(records: list[dict[str, object]], key_name: str, path: Path, report: ValidationReport) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for entry in records:
        raw_key = entry.get(key_name)
        if not raw_key:
            report.add_error("jsonl.missing_key", f"Missing `{key_name}` in record.", path)
            continue
        key = str(raw_key)
        if key in result:
            report.add_error("jsonl.duplicate_key", f"Duplicate `{key_name}` `{key}`.", path)
            continue
        result[key] = entry
    return result


def has_supporting_evidence(claim_id: str, evidence_rows: list[dict[str, object]]) -> bool:
    return any(str(row.get("support", "")).strip().lower() == "support" for row in evidence_rows)


def count_source_rows(path: Path, report: ValidationReport) -> int | None:
    if not path.exists():
        return None
    if path.suffix in {".yaml", ".yml"}:
        data = load_yaml_safe(path, report, required=False)
        if data is None:
            return None
        if isinstance(data, dict):
            list_values = [value for value in data.values() if isinstance(value, list)]
            if len(list_values) == 1:
                return len(list_values[0])
        if isinstance(data, list):
            return len(data)
        return 0
    if path.suffix == ".jsonl":
        return len(load_jsonl_safe(path, report, required=False))
    return 0


def read_document_text(repo_root: Path, document_row: dict[str, object], report: ValidationReport, documents_path: Path) -> str | None:
    raw_path = document_row.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        return None
    candidate = repo_root / raw_path
    if not candidate.exists():
        report.add_warning(
            "documents.missing_path",
            f"Document `{document_row.get('document_id')}` points to `{raw_path}`, which does not exist under the repo root.",
            documents_path,
        )
        return None
    try:
        return candidate.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return candidate.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        report.add_warning(
            "documents.read_failed",
            f"Document `{document_row.get('document_id')}` could not be read: {exc}",
            documents_path,
        )
        return None


def validate_document_types(document_types: dict[str, dict[str, object]], path: Path, report: ValidationReport) -> None:
    for key, item in document_types.items():
        default_claim_status = item.get("default_claim_status")
        if default_claim_status != "proposed":
            report.add_error(
                "document_types.invalid_default_claim_status",
                f"Document type `{key}` must use `default_claim_status: proposed` in v1.",
                path,
            )


def validate_documents(
    documents: dict[str, dict[str, object]],
    document_types: dict[str, dict[str, object]],
    path: Path,
    repo_root: Path,
    report: ValidationReport,
) -> dict[str, str | None]:
    document_texts: dict[str, str | None] = {}
    for document_id, row in documents.items():
        document_type = row.get("document_type")
        if not document_type:
            report.add_error("documents.missing_type", f"Document `{document_id}` is missing `document_type`.", path)
        elif str(document_type) not in document_types:
            report.add_error(
                "documents.unknown_type",
                f"Document `{document_id}` references unknown document type `{document_type}`.",
                path,
            )
        document_texts[document_id] = read_document_text(repo_root, row, report, path)
    return document_texts


def validate_segments(
    segments: dict[str, dict[str, object]],
    documents: dict[str, dict[str, object]],
    document_texts: dict[str, str | None],
    path: Path,
    report: ValidationReport,
) -> None:
    for segment_id, row in segments.items():
        for field in SEGMENT_REQUIRED_FIELDS:
            if row.get(field) in (None, ""):
                report.add_error("segments.missing_field", f"Segment `{segment_id}` is missing `{field}`.", path)

        document_id = str(row.get("document_id", ""))
        if document_id not in documents:
            report.add_error("segments.unknown_document", f"Segment `{segment_id}` references missing document `{document_id}`.", path)
            continue

        document_type = str(row.get("document_type", ""))
        expected_type = str(documents[document_id].get("document_type", ""))
        if document_type and expected_type and document_type != expected_type:
            report.add_error(
                "segments.document_type_mismatch",
                f"Segment `{segment_id}` uses document type `{document_type}` but the document registry says `{expected_type}`.",
                path,
            )

        try:
            start_char = int(row.get("start_char", -1))
            end_char = int(row.get("end_char", -1))
            int(row.get("ordinal", -1))
        except Exception:
            report.add_error("segments.invalid_numeric_field", f"Segment `{segment_id}` has invalid numeric fields.", path)
            continue

        if start_char > end_char:
            report.add_error("segments.invalid_offsets", f"Segment `{segment_id}` has `start_char > end_char`.", path)

        text_value = str(row.get("text", ""))
        if sha256_text(text_value) != str(row.get("text_hash", "")):
            report.add_error("segments.text_hash_mismatch", f"Segment `{segment_id}` has a stale or invalid `text_hash`.", path)

        document_text = document_texts.get(document_id)
        if document_text is None:
            continue
        if end_char > len(document_text):
            report.add_error("segments.out_of_bounds", f"Segment `{segment_id}` ends beyond the source document length.", path)
            continue
        if document_text[start_char:end_char] != text_value:
            report.add_error("segments.text_mismatch", f"Segment `{segment_id}` text does not match the source document span.", path)


def validate_claims(
    claims: dict[str, dict[str, object]],
    relations: dict[str, dict[str, object]],
    entities: dict[str, dict[str, object]],
    documents: dict[str, dict[str, object]],
    segments: dict[str, dict[str, object]],
    evidence_by_claim: dict[str, list[dict[str, object]]],
    path: Path,
    report: ValidationReport,
) -> None:
    for claim_id, row in claims.items():
        for field in CLAIM_REQUIRED_FIELDS:
            if row.get(field) in (None, ""):
                report.add_error("claims.missing_field", f"Claim `{claim_id}` is missing `{field}`.", path)

        status = str(row.get("status", ""))
        review_state = str(row.get("review_state", ""))
        if status not in ALLOWED_STATUS_REVIEW:
            report.add_error("claims.invalid_status", f"Claim `{claim_id}` has invalid status `{status}`.", path)
            continue
        if review_state != ALLOWED_STATUS_REVIEW[status]:
            report.add_error(
                "claims.invalid_review_state",
                f"Claim `{claim_id}` must use `{status} + {ALLOWED_STATUS_REVIEW[status]}`.",
                path,
            )

        predicate = str(row.get("predicate", ""))
        if predicate not in relations:
            report.add_error("claims.unknown_relation", f"Claim `{claim_id}` uses unknown predicate `{predicate}`.", path)

        subject_id = str(row.get("subject_id", ""))
        object_id = str(row.get("object_id", ""))
        if subject_id and subject_id not in entities:
            report.add_error("claims.unknown_subject", f"Claim `{claim_id}` references missing subject entity `{subject_id}`.", path)
        if object_id and object_id not in entities:
            report.add_error("claims.unknown_object", f"Claim `{claim_id}` references missing object entity `{object_id}`.", path)

        source_document_id = str(row.get("source_document_id", ""))
        if source_document_id and source_document_id not in documents:
            report.add_error("claims.unknown_document", f"Claim `{claim_id}` references missing document `{source_document_id}`.", path)

        source_segment_id = row.get("source_segment_id")
        if source_segment_id not in (None, ""):
            if not isinstance(source_segment_id, str):
                report.add_error("claims.invalid_segment_id", f"Claim `{claim_id}` has non-string `source_segment_id`.", path)
            elif source_segment_id not in segments:
                report.add_error("claims.unknown_segment", f"Claim `{claim_id}` references missing segment `{source_segment_id}`.", path)
            elif source_document_id and str(segments[source_segment_id].get("document_id", "")) != source_document_id:
                report.add_error(
                    "claims.segment_document_mismatch",
                    f"Claim `{claim_id}` references segment `{source_segment_id}` from a different document.",
                    path,
                )

        if status == "accepted":
            for field in ACCEPTED_REQUIRED_FIELDS:
                if row.get(field) in (None, ""):
                    report.add_error(
                        "claims.accepted_missing_review_metadata",
                        f"Accepted claim `{claim_id}` is missing `{field}`.",
                        path,
                    )
            decision_by = str(row.get("decision_by", ""))
            if decision_by and not decision_by.startswith("human:"):
                report.add_error(
                    "claims.invalid_decision_actor",
                    f"Accepted claim `{claim_id}` must use a human decision identifier.",
                    path,
                )
            if not has_supporting_evidence(claim_id, evidence_by_claim.get(claim_id, [])):
                report.add_error(
                    "claims.accepted_without_evidence",
                    f"Accepted claim `{claim_id}` must have at least one supporting evidence row.",
                    path,
                )

        if status == "disputed":
            report.add_warning("claims.disputed", f"Claim `{claim_id}` remains disputed and needs manual resolution.", path)


def validate_evidence(
    evidence_rows: dict[str, dict[str, object]],
    claims: dict[str, dict[str, object]],
    documents: dict[str, dict[str, object]],
    segments: dict[str, dict[str, object]],
    document_texts: dict[str, str | None],
    path: Path,
    report: ValidationReport,
) -> dict[str, list[dict[str, object]]]:
    evidence_by_claim: dict[str, list[dict[str, object]]] = {}
    for evidence_id, row in evidence_rows.items():
        for field in EVIDENCE_REQUIRED_FIELDS:
            if row.get(field) in (None, ""):
                report.add_error("evidence.missing_field", f"Evidence `{evidence_id}` is missing `{field}`.", path)

        claim_id = str(row.get("claim_id", ""))
        if claim_id not in claims:
            report.add_error("evidence.unknown_claim", f"Evidence `{evidence_id}` references missing claim `{claim_id}`.", path)
        else:
            evidence_by_claim.setdefault(claim_id, []).append(row)

        source_document_id = str(row.get("source_document_id", ""))
        if source_document_id and source_document_id not in documents:
            report.add_error("evidence.unknown_document", f"Evidence `{evidence_id}` references missing document `{source_document_id}`.", path)

        source_segment_id = row.get("source_segment_id")
        if source_segment_id not in (None, ""):
            if not isinstance(source_segment_id, str):
                report.add_error("evidence.invalid_segment_id", f"Evidence `{evidence_id}` has non-string `source_segment_id`.", path)
            elif source_segment_id not in segments:
                report.add_error("evidence.unknown_segment", f"Evidence `{evidence_id}` references missing segment `{source_segment_id}`.", path)
            else:
                segment = segments[source_segment_id]
                if source_document_id and str(segment.get("document_id", "")) != source_document_id:
                    report.add_error(
                        "evidence.segment_document_mismatch",
                        f"Evidence `{evidence_id}` references segment `{source_segment_id}` from a different document.",
                        path,
                    )
                try:
                    start_char = int(row.get("start_char", -1))
                    end_char = int(row.get("end_char", -1))
                except Exception:
                    report.add_error("evidence.invalid_offsets", f"Evidence `{evidence_id}` has non-integer offsets.", path)
                    continue
                if start_char > end_char:
                    report.add_error("evidence.invalid_offsets", f"Evidence `{evidence_id}` has `start_char > end_char`.", path)
                segment_start = int(segment.get("start_char", -1))
                segment_end = int(segment.get("end_char", -1))
                if start_char < segment_start or end_char > segment_end:
                    report.add_error(
                        "evidence.out_of_segment_bounds",
                        f"Evidence `{evidence_id}` points outside segment `{source_segment_id}`.",
                        path,
                    )
                document_text = document_texts.get(source_document_id)
                if document_text is not None and end_char > len(document_text):
                    report.add_error(
                        "evidence.out_of_document_bounds",
                        f"Evidence `{evidence_id}` ends beyond the source document length.",
                        path,
                    )

    return evidence_by_claim


def validate_derived_edges(
    derived_edges: dict[str, dict[str, object]],
    claims: dict[str, dict[str, object]],
    relations: dict[str, dict[str, object]],
    inference_rules: dict[str, dict[str, object]],
    path: Path,
    report: ValidationReport,
) -> None:
    for edge_id, row in derived_edges.items():
        for field in DERIVED_REQUIRED_FIELDS:
            if row.get(field) in (None, ""):
                report.add_error("derived.missing_field", f"Derived edge `{edge_id}` is missing `{field}`.", path)

        source_claim_id = str(row.get("source_claim_id", ""))
        if source_claim_id not in claims:
            report.add_error("derived.unknown_source_claim", f"Derived edge `{edge_id}` references missing claim `{source_claim_id}`.", path)
        elif str(claims[source_claim_id].get("status")) != "accepted":
            report.add_error(
                "derived.non_accepted_source_claim",
                f"Derived edge `{edge_id}` references non-accepted claim `{source_claim_id}`.",
                path,
            )

        predicate = str(row.get("predicate", ""))
        if predicate and predicate not in relations:
            report.add_error("derived.unknown_predicate", f"Derived edge `{edge_id}` uses unknown predicate `{predicate}`.", path)

        rule_key = str(row.get("rule_key", ""))
        if rule_key and rule_key not in inference_rules:
            report.add_error("derived.unknown_rule", f"Derived edge `{edge_id}` references unknown rule `{rule_key}`.", path)


def validate_contradictions(claims: dict[str, dict[str, object]], relations: dict[str, dict[str, object]], path: Path, report: ValidationReport) -> None:
    accepted_claims = [row for row in claims.values() if row.get("status") == "accepted"]
    for row in accepted_claims:
        if row.get("predicate") == "contradicts":
            report.add_warning(
                "claims.explicit_contradiction",
                f"Accepted claim `{row.get('claim_id')}` explicitly marks a contradiction.",
                path,
            )

    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in accepted_claims:
        predicate = str(row.get("predicate", ""))
        relation = relations.get(predicate, {})
        if not relation or not relation.get("exclusive_object"):
            continue
        grouped.setdefault((str(row.get("subject_id")), predicate), []).append(row)

    for (subject_id, predicate), rows in grouped.items():
        for index, left in enumerate(rows):
            for right in rows[index + 1:]:
                if left.get("object_id") == right.get("object_id"):
                    continue
                if windows_overlap(
                    parse_iso8601(left.get("valid_from")),
                    parse_iso8601(left.get("valid_to")),
                    parse_iso8601(right.get("valid_from")),
                    parse_iso8601(right.get("valid_to")),
                ):
                    report.add_warning(
                        "claims.exclusive_object_conflict",
                        (
                            f"Accepted claims `{left.get('claim_id')}` and `{right.get('claim_id')}` "
                            f"conflict under exclusive predicate `{predicate}` for subject `{subject_id}`."
                        ),
                        path,
                    )


def validate_optional_outputs(paths: dict[str, Path], report: ValidationReport) -> None:
    for key in ("shapes", "context"):
        if not paths[key].exists():
            report.add_warning(
                "optional.output_missing",
                f"Optional generated file `{report.display_path(paths[key])}` is missing.",
                paths[key],
            )


def validate_retrieval_config(paths: dict[str, Path], report: ValidationReport) -> None:
    if not paths["retrieval_config"].exists():
        report.add_warning("retrieval.config_missing", "Retrieval config is missing.", paths["retrieval_config"])
        return
    load_yaml_safe(paths["retrieval_config"], report, required=True)


def validate_retrieval_index(paths: dict[str, Path], report: ValidationReport) -> None:
    if not paths["segments"].exists():
        return
    if not paths["index_meta"].exists():
        if report.strictness == "strict":
            report.add_error("retrieval.index_missing", "Chroma index metadata is missing.", paths["index_meta"])
        else:
            report.add_warning("retrieval.index_missing", "Chroma index metadata is missing.", paths["index_meta"])
        return

    payload = load_json_safe(paths["index_meta"], report)
    if not isinstance(payload, dict):
        return

    current_hash = sha256_file(paths["segments"])
    if payload.get("segment_source_hash") != current_hash:
        message = "Chroma index metadata is stale relative to `segments.jsonl`."
        if report.strictness == "strict":
            report.add_error("retrieval.index_stale", message, paths["index_meta"])
        else:
            report.add_warning("retrieval.index_stale", message, paths["index_meta"])


def validate_mirror(paths: dict[str, Path], report: ValidationReport) -> None:
    duckdb_path = paths["duckdb"]
    if not duckdb_path.exists():
        report.add_warning("mirror.missing", "DuckDB mirror is missing.", duckdb_path)
        return
    if duckdb is None:
        report.add_warning("mirror.dependency_missing", "duckdb is required to validate the mirror.", duckdb_path)
        return

    try:
        connection = duckdb.connect(str(duckdb_path), read_only=True)
    except Exception as exc:
        report.add_error("mirror.open_failed", f"Failed to open DuckDB mirror: {exc}", duckdb_path)
        return

    try:
        rows = connection.execute("select source_path, source_hash, row_count, schema_version from _mirror_meta").fetchall()
    except Exception as exc:
        report.add_error("mirror.meta_missing", f"Failed to read `_mirror_meta`: {exc}", duckdb_path)
        connection.close()
        return
    connection.close()

    meta_by_path = {
        str(source_path): {
            "source_hash": str(source_hash),
            "row_count": int(row_count),
            "schema_version": str(schema_version),
        }
        for source_path, source_hash, row_count, schema_version in rows
    }

    source_names = [
        "relations",
        "document_types",
        "entities",
        "documents",
        "claims",
        "claim_evidence",
        "segments",
        "derived_edges",
    ]
    for name in source_names:
        path = paths[name]
        if not path.exists():
            continue
        relative = report.display_path(path)
        expected = {
            "source_hash": sha256_file(path),
            "row_count": count_source_rows(path, report),
            "schema_version": SCHEMA_VERSION,
        }
        actual = meta_by_path.get(relative)
        if actual is None:
            message = f"Mirror metadata is missing source `{relative}`."
        elif actual != expected:
            message = f"Mirror metadata for `{relative}` is stale or inconsistent."
        else:
            continue

        if report.strictness == "strict":
            report.add_error("mirror.stale", message, duckdb_path)
        else:
            report.add_warning("mirror.stale", message, duckdb_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate lightweight ontology graph integrity.")
    parser.add_argument("--repo-root", required=True, help="Repository root to validate.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strictness", choices=["relaxed", "strict"], default="relaxed")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    report = ValidationReport(repo_root, args.strictness)
    paths = build_paths(repo_root)

    validate_optional_outputs(paths, report)
    validate_retrieval_config(paths, report)

    relations_data = load_yaml_safe(paths["relations"], report)
    document_type_data = load_yaml_safe(paths["document_types"], report)
    inference_data = load_yaml_safe(paths["inference"], report, required=False)

    relations = load_section_items(relations_data, "relations", "key", paths["relations"], report) if relations_data is not None else {}
    document_types = load_section_items(document_type_data, "document_types", "key", paths["document_types"], report) if document_type_data is not None else {}
    inference_rules = load_section_items(inference_data, "rules", "key", paths["inference"], report) if inference_data is not None else {}

    validate_document_types(document_types, paths["document_types"], report)

    entities_records = load_jsonl_safe(paths["entities"], report)
    documents_records = load_jsonl_safe(paths["documents"], report)
    claims_records = load_jsonl_safe(paths["claims"], report)
    evidence_records = load_jsonl_safe(paths["claim_evidence"], report)
    segments_records = load_jsonl_safe(paths["segments"], report, required=False)
    derived_records = load_jsonl_safe(paths["derived_edges"], report, required=False)

    entities = keyed_records(entities_records, "entity_id", paths["entities"], report)
    documents = keyed_records(documents_records, "document_id", paths["documents"], report)
    claims = keyed_records(claims_records, "claim_id", paths["claims"], report)
    evidence = keyed_records(evidence_records, "evidence_id", paths["claim_evidence"], report)
    segments = keyed_records(segments_records, "segment_id", paths["segments"], report)
    derived_edges = keyed_records(derived_records, "edge_id", paths["derived_edges"], report)

    document_texts = validate_documents(documents, document_types, paths["documents"], repo_root, report)
    validate_segments(segments, documents, document_texts, paths["segments"], report)
    evidence_by_claim = validate_evidence(evidence, claims, documents, segments, document_texts, paths["claim_evidence"], report)
    validate_claims(claims, relations, entities, documents, segments, evidence_by_claim, paths["claims"], report)
    validate_derived_edges(derived_edges, claims, relations, inference_rules, paths["derived_edges"], report)
    validate_contradictions(claims, relations, paths["claims"], report)
    validate_retrieval_index(paths, report)
    validate_mirror(paths, report)

    if args.format == "json":
        print(report.to_json())
    else:
        report.print_text()

    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
