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

from _ontology_core_support import SCHEMA_VERSION, build_paths, load_jsonl, load_yaml, relative_path, sha256_file


def section_list(data: object, section_key: str) -> list[dict[str, object]]:
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected mapping with `{section_key}` section.")
    section = data.get(section_key)
    if not isinstance(section, list):
        raise RuntimeError(f"`{section_key}` must be a list.")
    normalized: list[dict[str, object]] = []
    for item in section:
        if not isinstance(item, dict):
            raise RuntimeError(f"Each `{section_key}` entry must be a mapping.")
        normalized.append(item)
    return normalized


def create_table(connection: duckdb.DuckDBPyConnection, table_name: str, columns: list[tuple[str, str]]) -> None:
    column_sql = ", ".join(f"{name} {dtype}" for name, dtype in columns)
    connection.execute(f"drop table if exists {table_name}")
    connection.execute(f"create table {table_name} ({column_sql})")


def insert_rows(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    columns: list[str],
    rows: list[tuple[object, ...]],
) -> None:
    if not rows:
        return
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"insert into {table_name} ({', '.join(columns)}) values ({placeholders})"
    connection.executemany(sql, rows)


def sync(repo_root: Path) -> Path:
    if duckdb is None:
        raise RuntimeError("duckdb is required to create the mirror.")

    paths = build_paths(repo_root)
    if not paths["relations"].exists() or not paths["document_types"].exists():
        raise RuntimeError("Missing required manifest YAML files.")

    relations = section_list(load_yaml(paths["relations"]), "relations")
    document_types = section_list(load_yaml(paths["document_types"]), "document_types")
    entities = load_jsonl(paths["entities"])
    documents = load_jsonl(paths["documents"])
    claims = load_jsonl(paths["claims"])
    evidence = load_jsonl(paths["claim_evidence"])
    segments = load_jsonl(paths["segments"])
    derived_edges = load_jsonl(paths["derived_edges"])

    paths["duckdb"].parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(paths["duckdb"]))

    create_table(connection, "relations", [("relation_key", "varchar"), ("label", "varchar"), ("group_name", "varchar"), ("payload_json", "varchar")])
    insert_rows(
        connection,
        "relations",
        ["relation_key", "label", "group_name", "payload_json"],
        [(str(item.get("key", "")), str(item.get("label", "")), str(item.get("group", "")), json.dumps(item, ensure_ascii=False, sort_keys=True)) for item in relations],
    )

    create_table(connection, "document_types", [("document_type_key", "varchar"), ("label", "varchar"), ("default_claim_status", "varchar"), ("payload_json", "varchar")])
    insert_rows(
        connection,
        "document_types",
        ["document_type_key", "label", "default_claim_status", "payload_json"],
        [(str(item.get("key", "")), str(item.get("label", "")), str(item.get("default_claim_status", "")), json.dumps(item, ensure_ascii=False, sort_keys=True)) for item in document_types],
    )

    create_table(connection, "entities", [("entity_id", "varchar"), ("entity_type", "varchar"), ("label", "varchar"), ("status", "varchar"), ("payload_json", "varchar")])
    insert_rows(
        connection,
        "entities",
        ["entity_id", "entity_type", "label", "status", "payload_json"],
        [(str(item.get("entity_id", "")), str(item.get("entity_type", "")), str(item.get("label", "")), str(item.get("status", "")), json.dumps(item, ensure_ascii=False, sort_keys=True)) for item in entities],
    )

    create_table(connection, "documents", [("document_id", "varchar"), ("path", "varchar"), ("document_type", "varchar"), ("status", "varchar"), ("payload_json", "varchar")])
    insert_rows(
        connection,
        "documents",
        ["document_id", "path", "document_type", "status", "payload_json"],
        [(str(item.get("document_id", "")), str(item.get("path", "")), str(item.get("document_type", "")), str(item.get("status", "")), json.dumps(item, ensure_ascii=False, sort_keys=True)) for item in documents],
    )

    create_table(connection, "claims", [("claim_id", "varchar"), ("subject_id", "varchar"), ("predicate", "varchar"), ("object_id", "varchar"), ("status", "varchar"), ("review_state", "varchar"), ("source_document_id", "varchar"), ("payload_json", "varchar")])
    insert_rows(
        connection,
        "claims",
        ["claim_id", "subject_id", "predicate", "object_id", "status", "review_state", "source_document_id", "payload_json"],
        [(str(item.get("claim_id", "")), str(item.get("subject_id", "")), str(item.get("predicate", "")), str(item.get("object_id", "")), str(item.get("status", "")), str(item.get("review_state", "")), str(item.get("source_document_id", "")), json.dumps(item, ensure_ascii=False, sort_keys=True)) for item in claims],
    )

    create_table(connection, "claim_evidence", [("evidence_id", "varchar"), ("claim_id", "varchar"), ("source_document_id", "varchar"), ("support", "varchar"), ("payload_json", "varchar")])
    insert_rows(
        connection,
        "claim_evidence",
        ["evidence_id", "claim_id", "source_document_id", "support", "payload_json"],
        [(str(item.get("evidence_id", "")), str(item.get("claim_id", "")), str(item.get("source_document_id", "")), str(item.get("support", "")), json.dumps(item, ensure_ascii=False, sort_keys=True)) for item in evidence],
    )

    create_table(connection, "segments", [("segment_id", "varchar"), ("document_id", "varchar"), ("document_type", "varchar"), ("status", "varchar"), ("ordinal", "bigint"), ("payload_json", "varchar")])
    insert_rows(
        connection,
        "segments",
        ["segment_id", "document_id", "document_type", "status", "ordinal", "payload_json"],
        [(str(item.get("segment_id", "")), str(item.get("document_id", "")), str(item.get("document_type", "")), str(item.get("status", "")), int(item.get("ordinal", 0)), json.dumps(item, ensure_ascii=False, sort_keys=True)) for item in segments],
    )

    create_table(connection, "derived_edges", [("edge_id", "varchar"), ("source_claim_id", "varchar"), ("rule_key", "varchar"), ("subject_id", "varchar"), ("predicate", "varchar"), ("object_id", "varchar"), ("status", "varchar"), ("payload_json", "varchar")])
    insert_rows(
        connection,
        "derived_edges",
        ["edge_id", "source_claim_id", "rule_key", "subject_id", "predicate", "object_id", "status", "payload_json"],
        [(str(item.get("edge_id", "")), str(item.get("source_claim_id", "")), str(item.get("rule_key", "")), str(item.get("subject_id", "")), str(item.get("predicate", "")), str(item.get("object_id", "")), str(item.get("status", "")), json.dumps(item, ensure_ascii=False, sort_keys=True)) for item in derived_edges],
    )

    create_table(connection, "_mirror_meta", [("source_path", "varchar"), ("source_hash", "varchar"), ("row_count", "bigint"), ("synced_at", "timestamp"), ("schema_version", "varchar")])

    synced_at = datetime.now(timezone.utc)
    source_rows: list[tuple[object, ...]] = []
    source_files = [
        ("relations", relations),
        ("document_types", document_types),
        ("entities", entities),
        ("documents", documents),
        ("claims", claims),
        ("claim_evidence", evidence),
        ("segments", segments),
    ]
    if paths["derived_edges"].exists():
        source_files.append(("derived_edges", derived_edges))

    for name, records in source_files:
        path = paths[name]
        source_rows.append((relative_path(repo_root, path), sha256_file(path), len(records), synced_at, SCHEMA_VERSION))

    insert_rows(connection, "_mirror_meta", ["source_path", "source_hash", "row_count", "synced_at", "schema_version"], source_rows)
    connection.close()
    return paths["duckdb"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Mirror canonical ontology files into DuckDB.")
    parser.add_argument("--repo-root", required=True, help="Repository root containing ontology data.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        db_path = sync(repo_root)
    except Exception as exc:
        print(f"Failed to sync ontology mirror: {exc}", file=sys.stderr)
        return 1

    print(f"Synced ontology mirror to {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
