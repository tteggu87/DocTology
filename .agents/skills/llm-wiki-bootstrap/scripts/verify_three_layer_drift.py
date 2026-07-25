#!/usr/bin/env python3
"""Verify basic drift signals across file, SQLite, and bootstrap wiki analytics DuckDB layers."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

try:
    import duckdb
except ModuleNotFoundError:  # pragma: no cover
    duckdb = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify coarse drift across three-layer wiki architecture.")
    parser.add_argument("--repo-root", required=True, help="Target wiki repository root.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    wiki_dir = repo_root / "wiki"
    warehouse_dir = repo_root / "warehouse" / "jsonl"
    sqlite_path = repo_root / "state" / "wiki_index.sqlite"
    duckdb_path = repo_root / "state" / "wiki_analytics.duckdb"

    page_count = 0
    if wiki_dir.exists():
        for path in wiki_dir.rglob("*.md"):
            rel = path.relative_to(wiki_dir)
            if rel.parts and rel.parts[0] != "_meta":
                page_count += 1
    jsonl_paths = sorted(warehouse_dir.glob("*.jsonl")) if warehouse_dir.exists() else []
    jsonl_rows = 0
    for path in jsonl_paths:
        with path.open(encoding="utf-8") as handle:
            jsonl_rows += sum(1 for line in handle if line.strip())
    sqlite_exists = sqlite_path.exists()
    duckdb_exists = duckdb_path.exists()

    issues: list[str] = []
    if page_count and not sqlite_exists:
        issues.append("pages_exist_but_sqlite_missing")
    if jsonl_rows and not duckdb_exists:
        issues.append("canonical_jsonl_exists_but_wiki_analytics_duckdb_missing")

    if sqlite_exists:
        connection = sqlite3.connect(sqlite_path)
        try:
            cursor = connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='pages'")
            if cursor.fetchone()[0] == 0:
                issues.append("sqlite_pages_table_missing")
        finally:
            connection.close()

    if duckdb_exists:
        if duckdb is None:
            issues.append("duckdb_dependency_missing")
        else:
            connection = duckdb.connect(str(duckdb_path), read_only=True)
            try:
                rows = connection.execute(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='sources'"
                ).fetchone()
                if not rows or rows[0] == 0:
                    issues.append("wiki_analytics_duckdb_sources_table_missing")
                page_rows = connection.execute(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='page_coverage_snapshots'"
                ).fetchone()
                if not page_rows or page_rows[0] == 0:
                    issues.append("wiki_analytics_duckdb_page_coverage_table_missing")
            finally:
                connection.close()

    if issues:
        print("DRIFT_ISSUES")
        for item in issues:
            print(f"- {item}")
        return 1

    print("DRIFT_OK")
    print(f"- pages: {page_count}")
    print(f"- canonical_jsonl_rows: {jsonl_rows}")
    print(f"- sqlite: {'present' if sqlite_exists else 'missing'}")
    print(f"- duckdb: {'present' if duckdb_exists else 'missing'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
