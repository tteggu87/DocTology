#!/usr/bin/env python3
"""Initialize and refresh a lightweight DuckDB wiki analytics mirror from canonical exports."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

try:
    import duckdb
except ModuleNotFoundError:  # pragma: no cover
    duckdb = None


ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = ROOT / "templates" / "llm-wiki-three-layer" / "duckdb_analytical.schema.sql"
TABLE_COLUMNS = {
    "sources": ["source_id", "source_type", "uri", "created_at", "raw_checksum"],
    "page_coverage_snapshots": [
        "page_id",
        "run_id",
        "source_count",
        "claim_count",
        "entity_count",
        "freshness_score",
        "coverage_score",
        "captured_at",
    ],
    "audit_events": ["run_id", "phase", "status", "detail", "page_id", "severity", "created_at"],
}
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")
WIKI_PAGE_DIRS = {"sources", "concepts", "entities", "people", "projects", "timelines", "analyses"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh wiki_analytics.duckdb from canonical JSONL exports.")
    parser.add_argument("--repo-root", required=True, help="Target wiki repository root.")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def split_frontmatter(text: str) -> tuple[list[str], str]:
    if not text.startswith("---\n"):
        return [], text
    lines = text.splitlines()
    try:
        end_index = lines[1:].index("---") + 1
    except ValueError:
        return [], text
    return lines[1:end_index], "\n".join(lines[end_index + 1 :])


def frontmatter_value(text: str, key: str) -> str | None:
    frontmatter_lines, _ = split_frontmatter(text)
    for line in frontmatter_lines:
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip('"')
    return None


def frontmatter_list(text: str, key: str) -> list[str]:
    frontmatter_lines, _ = split_frontmatter(text)
    values: list[str] = []
    collecting = False
    for line in frontmatter_lines:
        stripped = line.strip()
        if collecting:
            if not stripped:
                continue
            if stripped.startswith("- "):
                values.append(stripped[2:].strip().strip('"'))
                continue
            break
        if line.startswith(f"{key}:"):
            collecting = True
            remainder = line.split(":", 1)[1].strip()
            if remainder:
                values.append(remainder.strip("[] ").strip('"'))
    return values


def page_snapshot_rows(repo_root: Path) -> list[dict]:
    wiki_dir = repo_root / "wiki"
    if not wiki_dir.exists():
        return []

    rows: list[dict] = []
    captured_at = dt.datetime.now(dt.timezone.utc).isoformat()
    run_id = f"wiki-analytics-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    for path in sorted(wiki_dir.rglob("*.md")):
        rel = path.relative_to(wiki_dir)
        if not rel.parts or rel.parts[0] == "_meta" or rel.parts[0] not in WIKI_PAGE_DIRS:
            continue
        text = path.read_text(encoding="utf-8")
        _, body = split_frontmatter(text)
        sources = frontmatter_list(text, "sources")
        updated = frontmatter_value(text, "updated") or frontmatter_value(text, "updated_at")
        body_links = WIKILINK_RE.findall(body)
        entity_links = sum(1 for link in body_links if link.startswith("entity-"))
        source_count = len(sources)
        freshness_score = 1.0 if updated else 0.5
        coverage_score = min(1.0, source_count / 2.0) if source_count else 0.0
        rows.append(
            {
                "page_id": frontmatter_value(text, "page_id") or f"page-{path.stem}",
                "run_id": run_id,
                "source_count": source_count,
                "claim_count": 0,
                "entity_count": entity_links,
                "freshness_score": freshness_score,
                "coverage_score": coverage_score,
                "captured_at": captured_at,
            }
        )
    return rows


def project_rows(table_name: str, rows: list[dict]) -> list[list[object]]:
    columns = TABLE_COLUMNS[table_name]
    projected: list[list[object]] = []
    for row in rows:
        if table_name == "sources":
            normalized = {
                "source_id": row.get("source_id") or row.get("document_id"),
                "source_type": row.get("source_type") or row.get("document_type"),
                "uri": row.get("canonical_uri") or row.get("uri") or row.get("raw_path"),
                "created_at": row.get("created_at") or row.get("ingested_at"),
                "raw_checksum": row.get("raw_checksum") or row.get("checksum"),
            }
        elif table_name == "page_coverage_snapshots":
            normalized = {column: row.get(column) for column in columns}
        elif table_name == "audit_events":
            normalized = {
                "run_id": row.get("run_id"),
                "phase": row.get("phase"),
                "status": row.get("status"),
                "detail": row.get("detail"),
                "page_id": row.get("page_id"),
                "severity": row.get("severity"),
                "created_at": row.get("created_at") or row.get("finished_at") or row.get("started_at"),
            }
        else:
            normalized = {column: row.get(column) for column in columns}
        projected.append([normalized.get(column) for column in columns])
    return projected


def load_rows(connection, table_name: str, rows: list[dict]) -> None:
    if not rows:
        return
    columns = TABLE_COLUMNS[table_name]
    placeholders = ", ".join(["?"] * len(columns))
    column_list = ", ".join(columns)
    values = project_rows(table_name, rows)
    connection.executemany(
        f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})",
        values,
    )


def main() -> int:
    if duckdb is None:
        raise SystemExit("duckdb is required to run refresh_duckdb_analytics.py")

    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    db_path = repo_root / "state" / "wiki_analytics.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(db_path))
    try:
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        for table in (
            "sources",
            "page_coverage_snapshots",
            "audit_events",
        ):
            connection.execute(f"DELETE FROM {table}")

        warehouse = repo_root / "warehouse" / "jsonl"
        source_rows = read_jsonl(warehouse / "documents.jsonl")
        page_rows = page_snapshot_rows(repo_root)
        run_rows = read_jsonl(warehouse / "audit_events.jsonl")

        load_rows(connection, "sources", source_rows)
        load_rows(connection, "page_coverage_snapshots", page_rows)
        load_rows(connection, "audit_events", run_rows)
    finally:
        connection.close()

    print(f"Refreshed DuckDB wiki analytics mirror: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
