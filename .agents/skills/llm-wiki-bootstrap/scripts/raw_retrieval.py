#!/usr/bin/env python3
"""Disposable lexical retrieval index for immutable raw Markdown sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import reindex_sqlite_operational as chunker


SCHEMA_VERSION = "raw-heading-index-v1"
DEFAULT_DB = "state/raw_index.sqlite"
DEFAULT_CHUNK_BYTES = 64 * 1024
MAX_RESULTS = 100
SQLITE_HEADER = b"SQLite format 3\x00"


class RawRetrievalError(RuntimeError):
    pass


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS raw_documents (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  mtime_ns INTEGER NOT NULL,
  checksum TEXT NOT NULL,
  indexed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_chunks (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  heading_path TEXT NOT NULL,
  line_start INTEGER NOT NULL,
  line_end INTEGER NOT NULL,
  byte_start INTEGER NOT NULL,
  byte_end INTEGER NOT NULL,
  content_hash TEXT NOT NULL,
  UNIQUE (document_id, chunk_index),
  FOREIGN KEY (document_id) REFERENCES raw_documents(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS raw_chunk_fts USING fts5(
  heading_path,
  content,
  tokenize = 'unicode61'
);

CREATE TABLE IF NOT EXISTS raw_index_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_chunks_document
  ON raw_chunks(document_id, chunk_index);
"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_digest(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(encoded.encode("utf-8"))


def database_path(repo_root: Path, override: str | None) -> Path:
    candidate = Path(override) if override else Path(DEFAULT_DB)
    return candidate if candidate.is_absolute() else repo_root / candidate


def raw_markdown_paths(repo_root: Path) -> list[Path]:
    raw_root = repo_root / "raw"
    if not raw_root.is_dir():
        return []
    return sorted(
        (path for path in raw_root.rglob("*.md") if path.is_file()),
        key=lambda path: path.relative_to(repo_root).as_posix(),
    )


def stat_rows(repo_root: Path) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for path in raw_markdown_paths(repo_root):
        stat = path.stat()
        rows.append(
            {
                "path": path.relative_to(repo_root).as_posix(),
                "byte_size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        )
    return rows


def stat_fingerprint(repo_root: Path) -> str:
    return canonical_digest(stat_rows(repo_root))


def document_id(relative: str) -> str:
    return "raw-document-" + sha256(relative.encode("utf-8"))[:24]


def page_for_raw(repo_root: Path, path: Path) -> chunker.Page:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    relative = path.relative_to(repo_root).as_posix()
    checksum = sha256(raw)
    return chunker.Page(
        "raw-page-" + sha256(relative.encode("utf-8"))[:24],
        relative,
        chunker.extract_title(path, text),
        "raw",
        "",
        checksum,
        text,
        len(raw),
    )


def sqlite_header_ok(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(len(SQLITE_HEADER)) == SQLITE_HEADER
    except OSError:
        return False


def connect(database: Path) -> sqlite3.Connection:
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def open_read_only(database: Path) -> sqlite3.Connection:
    if not database.is_file():
        raise RawRetrievalError("raw index is missing; run rebuild")
    if not sqlite_header_ok(database):
        raise RawRetrievalError("raw index is not a SQLite database; run rebuild")
    uri = f"file:{quote(str(database.resolve()))}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def metadata(connection: sqlite3.Connection) -> dict[str, str]:
    try:
        values = dict(connection.execute("SELECT key, value FROM raw_index_metadata"))
    except sqlite3.Error as exc:
        raise RawRetrievalError(f"malformed raw index: {exc}") from exc
    if values.get("schema_version") != SCHEMA_VERSION:
        raise RawRetrievalError("raw index schema is stale; run rebuild")
    return values


def delete_document(connection: sqlite3.Connection, doc_id: str) -> None:
    rowids = [
        row[0]
        for row in connection.execute(
            "SELECT rowid FROM raw_chunks WHERE document_id = ?", (doc_id,)
        )
    ]
    connection.executemany(
        "DELETE FROM raw_chunk_fts WHERE rowid = ?", ((rowid,) for rowid in rowids)
    )
    connection.execute("DELETE FROM raw_documents WHERE id = ?", (doc_id,))


def insert_document(
    connection: sqlite3.Connection,
    repo_root: Path,
    path: Path,
    threshold: int,
) -> int:
    page = page_for_raw(repo_root, path)
    relative = path.relative_to(repo_root).as_posix()
    stat = path.stat()
    doc_id = document_id(relative)
    connection.execute(
        """
        INSERT INTO raw_documents(
          id, path, title, byte_size, mtime_ns, checksum, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            relative,
            page.title,
            stat.st_size,
            stat.st_mtime_ns,
            page.checksum,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    chunks = chunker.chunks_for_page(page, threshold)
    for item in chunks:
        cursor = connection.execute(
            """
            INSERT INTO raw_chunks(
              id, document_id, chunk_index, heading_path, line_start, line_end,
              byte_start, byte_end, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.id,
                doc_id,
                item.chunk_index,
                item.heading_path,
                item.line_start,
                item.line_end,
                item.byte_start,
                item.byte_end,
                item.content_hash,
            ),
        )
        connection.execute(
            "INSERT INTO raw_chunk_fts(rowid, heading_path, content) VALUES (?, ?, ?)",
            (cursor.lastrowid, item.heading_path, item.content),
        )
    return len(chunks)


def prepare_rebuild(database: Path) -> sqlite3.Connection:
    if database.exists() and not sqlite_header_ok(database):
        database.unlink()
    connection = connect(database)
    try:
        connection.executescript(SCHEMA_SQL)
        values = dict(
            connection.execute(
                "SELECT key, value FROM raw_index_metadata WHERE key = 'schema_version'"
            )
        )
        if values and values.get("schema_version") != SCHEMA_VERSION:
            connection.close()
            database.unlink()
            connection = connect(database)
            connection.executescript(SCHEMA_SQL)
        return connection
    except BaseException:
        connection.close()
        raise


def rebuild(repo_root: Path, database: Path, threshold: int) -> dict[str, Any]:
    if threshold <= 0:
        raise RawRetrievalError("chunk bytes must be positive")
    connection = prepare_rebuild(database)
    changed = 0
    unchanged = 0
    removed = 0
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = {
            row["path"]: row
            for row in connection.execute(
                "SELECT id, path, byte_size, mtime_ns FROM raw_documents"
            )
        }
        current_paths = raw_markdown_paths(repo_root)
        current_names = {path.relative_to(repo_root).as_posix() for path in current_paths}
        prior_threshold = dict(
            connection.execute(
                "SELECT key, value FROM raw_index_metadata WHERE key = 'chunk_bytes'"
            )
        ).get("chunk_bytes")
        force = prior_threshold != str(threshold)

        for relative, row in existing.items():
            if relative not in current_names:
                delete_document(connection, str(row["id"]))
                removed += 1

        for path in current_paths:
            relative = path.relative_to(repo_root).as_posix()
            stat = path.stat()
            row = existing.get(relative)
            is_changed = (
                force
                or row is None
                or int(row["byte_size"]) != stat.st_size
                or int(row["mtime_ns"]) != stat.st_mtime_ns
            )
            if not is_changed:
                unchanged += 1
                continue
            if row is not None:
                delete_document(connection, str(row["id"]))
            insert_document(connection, repo_root, path, threshold)
            changed += 1

        document_count = connection.execute(
            "SELECT count(*) FROM raw_documents"
        ).fetchone()[0]
        chunk_count = connection.execute("SELECT count(*) FROM raw_chunks").fetchone()[0]
        fts_count = connection.execute("SELECT count(*) FROM raw_chunk_fts").fetchone()[0]
        if chunk_count != fts_count:
            raise RawRetrievalError("raw chunk and FTS row counts diverged")
        values = {
            "schema_version": SCHEMA_VERSION,
            "truth_source": "raw/**/*.md",
            "chunk_bytes": str(threshold),
            "stat_fingerprint": stat_fingerprint(repo_root),
            "document_count": str(document_count),
            "chunk_count": str(chunk_count),
            "built_at": datetime.now(timezone.utc).isoformat(),
        }
        connection.executemany(
            "INSERT OR REPLACE INTO raw_index_metadata(key, value) VALUES (?, ?)",
            values.items(),
        )
        connection.commit()
        return {
            "state": "ready",
            "database": database.relative_to(repo_root).as_posix()
            if database.is_relative_to(repo_root)
            else str(database),
            "documents": document_count,
            "chunks": chunk_count,
            "changed_files": changed,
            "unchanged_files": unchanged,
            "removed_files": removed,
            "chunk_bytes": threshold,
            "canonical": False,
        }
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def status(repo_root: Path, database: Path) -> dict[str, Any]:
    connection = open_read_only(database)
    try:
        values = metadata(connection)
        current = stat_fingerprint(repo_root)
        ready = values.get("stat_fingerprint") == current
        return {
            "state": "ready" if ready else "stale",
            "freshness": "stat",
            "documents": connection.execute(
                "SELECT count(*) FROM raw_documents"
            ).fetchone()[0],
            "chunks": connection.execute("SELECT count(*) FROM raw_chunks").fetchone()[0],
            "stored_stat_fingerprint": values.get("stat_fingerprint"),
            "current_stat_fingerprint": current,
            "canonical": False,
        }
    finally:
        connection.close()


def fts_query(query: str) -> str:
    tokens = re.findall(r"[\w-]+", query, re.UNICODE)
    if not tokens:
        raise RawRetrievalError("search query must contain a word")
    return " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


def search(repo_root: Path, database: Path, query: str, limit: int) -> dict[str, Any]:
    if not 1 <= limit <= MAX_RESULTS:
        raise RawRetrievalError(f"limit must be between 1 and {MAX_RESULTS}")
    connection = open_read_only(database)
    try:
        metadata(connection)
        rows = connection.execute(
            """
            SELECT
              c.id AS chunk_id,
              d.path,
              d.title,
              c.heading_path,
              c.line_start,
              c.line_end,
              c.byte_start,
              c.byte_end,
              c.content_hash,
              bm25(raw_chunk_fts) AS rank
            FROM raw_chunk_fts
            JOIN raw_chunks c ON c.rowid = raw_chunk_fts.rowid
            JOIN raw_documents d ON d.id = c.document_id
            WHERE raw_chunk_fts MATCH ?
            ORDER BY rank, d.path, c.chunk_index
            LIMIT ?
            """,
            (fts_query(query), limit),
        ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            source = repo_root / str(row["path"])
            raw = source.read_bytes()
            start, end = int(row["byte_start"]), int(row["byte_end"])
            current = raw[start:end] if end <= len(raw) else b""
            current_hash = sha256(current)
            results.append(
                {
                    "lane": "raw",
                    "candidate_status": "source_candidate"
                    if current_hash == row["content_hash"]
                    else "stale_candidate",
                    "path": row["path"],
                    "title": row["title"],
                    "heading_path": row["heading_path"],
                    "line_start": row["line_start"],
                    "line_end": row["line_end"],
                    "byte_start": start,
                    "byte_end": end,
                    "content": current.decode("utf-8", errors="replace"),
                    "rank": row["rank"],
                }
            )
        return {
            "query": query,
            "freshness": "unchecked",
            "lane": "raw",
            "canonical": False,
            "results": results,
        }
    finally:
        connection.close()


def doctor(repo_root: Path, database: Path) -> dict[str, Any]:
    connection = open_read_only(database)
    stale_reasons: list[str] = []
    try:
        values = metadata(connection)
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            stale_reasons.append("sqlite_integrity")
        stored = {
            row["path"]: row
            for row in connection.execute(
                "SELECT id, path, byte_size, mtime_ns, checksum FROM raw_documents"
            )
        }
        current = {
            path.relative_to(repo_root).as_posix(): path
            for path in raw_markdown_paths(repo_root)
        }
        if set(stored) != set(current):
            stale_reasons.append("document_paths")
        threshold = int(values.get("chunk_bytes", DEFAULT_CHUNK_BYTES))
        for relative in sorted(set(stored) & set(current)):
            path = current[relative]
            raw = path.read_bytes()
            row = stored[relative]
            if sha256(raw) != row["checksum"]:
                stale_reasons.append(f"document_checksum:{relative}")
                continue
            expected = chunker.chunks_for_page(page_for_raw(repo_root, path), threshold)
            actual = connection.execute(
                """
                SELECT c.chunk_index, c.heading_path, c.line_start, c.line_end,
                       c.byte_start, c.byte_end, c.content_hash,
                       f.heading_path AS fts_heading_path, f.content AS fts_content
                FROM raw_chunks c
                LEFT JOIN raw_chunk_fts f ON f.rowid = c.rowid
                WHERE c.document_id = ? ORDER BY c.chunk_index
                """,
                (row["id"],),
            ).fetchall()
            expected_rows = [
                (
                    item.chunk_index,
                    item.heading_path,
                    item.line_start,
                    item.line_end,
                    item.byte_start,
                    item.byte_end,
                    item.content_hash,
                    item.heading_path,
                    item.content,
                )
                for item in expected
            ]
            if [tuple(item) for item in actual] != expected_rows:
                stale_reasons.append(f"chunk_rows:{relative}")
        chunk_count = connection.execute("SELECT count(*) FROM raw_chunks").fetchone()[0]
        fts_count = connection.execute("SELECT count(*) FROM raw_chunk_fts").fetchone()[0]
        if chunk_count != fts_count:
            stale_reasons.append("fts_rows")
        return {
            "state": "stale" if stale_reasons else "ready",
            "freshness": "exact",
            "stale_reasons": stale_reasons,
            "documents": len(stored),
            "chunks": chunk_count,
            "canonical": False,
        }
    finally:
        connection.close()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--repo-root", default=".")
    result.add_argument("--database")
    commands = result.add_subparsers(dest="command", required=True)
    rebuild_parser = commands.add_parser("rebuild")
    rebuild_parser.add_argument("--chunk-bytes", type=int, default=DEFAULT_CHUNK_BYTES)
    commands.add_parser("status")
    search_parser = commands.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=10)
    commands.add_parser("doctor")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    database = database_path(repo_root, args.database)
    try:
        if args.command == "rebuild":
            payload = rebuild(repo_root, database, args.chunk_bytes)
        elif args.command == "status":
            payload = status(repo_root, database)
        elif args.command == "search":
            payload = search(repo_root, database, args.query, args.limit)
        else:
            payload = doctor(repo_root, database)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if payload.get("state") == "stale" else 0
    except (RawRetrievalError, OSError, UnicodeError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"state": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
