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


SCHEMA_VERSION = "raw-heading-structure-index-v2"
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

CREATE TABLE IF NOT EXISTS raw_structure_nodes (
  node_id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  parent_id TEXT,
  ordinal INTEGER NOT NULL,
  depth INTEGER NOT NULL,
  title TEXT NOT NULL,
  heading_path TEXT NOT NULL,
  line_start INTEGER NOT NULL,
  line_end INTEGER NOT NULL,
  byte_start INTEGER NOT NULL,
  byte_end INTEGER NOT NULL,
  subtree_line_start INTEGER NOT NULL,
  subtree_line_end INTEGER NOT NULL,
  subtree_byte_start INTEGER NOT NULL,
  subtree_byte_end INTEGER NOT NULL,
  UNIQUE (document_id, ordinal),
  FOREIGN KEY (document_id) REFERENCES raw_documents(id) ON DELETE CASCADE,
  FOREIGN KEY (parent_id) REFERENCES raw_structure_nodes(node_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS raw_chunks (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  heading_path TEXT NOT NULL,
  line_start INTEGER NOT NULL,
  line_end INTEGER NOT NULL,
  byte_start INTEGER NOT NULL,
  byte_end INTEGER NOT NULL,
  content_hash TEXT NOT NULL,
  UNIQUE (document_id, chunk_index),
  FOREIGN KEY (document_id) REFERENCES raw_documents(id) ON DELETE CASCADE,
  FOREIGN KEY (node_id) REFERENCES raw_structure_nodes(node_id) ON DELETE CASCADE
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

CREATE INDEX IF NOT EXISTS idx_raw_chunks_node
  ON raw_chunks(node_id);

CREATE INDEX IF NOT EXISTS idx_raw_structure_document
  ON raw_structure_nodes(document_id, ordinal);

CREATE INDEX IF NOT EXISTS idx_raw_structure_parent
  ON raw_structure_nodes(parent_id, ordinal);
"""

STRUCTURE_FIELDS = (
    "node_id",
    "document_id",
    "parent_id",
    "ordinal",
    "depth",
    "title",
    "heading_path",
    "line_start",
    "line_end",
    "byte_start",
    "byte_end",
    "subtree_line_start",
    "subtree_line_end",
    "subtree_byte_start",
    "subtree_byte_end",
)


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
    return "document-raw-page-" + sha256(relative.encode("utf-8"))[:24]


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


def structure_owner_node_id(nodes: list[Any], item: Any, relative: str) -> str:
    owners = [
        node
        for node in nodes
        if node.heading_path == item.heading_path
        and (
            (node.byte_start <= item.byte_start and item.byte_end <= node.byte_end)
            or (
                node.parent_id is None
                and node.subtree_byte_start <= item.byte_start
                and item.byte_end <= node.subtree_byte_end
            )
        )
    ]
    if len(owners) != 1:
        raise RawRetrievalError(
            f"raw chunk does not have exactly one structure owner: "
            f"{relative}#{item.chunk_index}"
        )
    return str(owners[0].node_id)


def insert_document(
    connection: sqlite3.Connection,
    repo_root: Path,
    path: Path,
    threshold: int,
) -> tuple[int, int]:
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
    nodes = chunker.structure_nodes_for_page(page)
    connection.executemany(
        """
        INSERT INTO raw_structure_nodes(
          node_id, document_id, parent_id, ordinal, depth, title, heading_path,
          line_start, line_end, byte_start, byte_end, subtree_line_start,
          subtree_line_end, subtree_byte_start, subtree_byte_end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tuple(getattr(node, field) for field in STRUCTURE_FIELDS) for node in nodes),
    )

    chunks = chunker.chunks_for_page(page, threshold)
    for item in chunks:
        cursor = connection.execute(
            """
            INSERT INTO raw_chunks(
              id, document_id, node_id, chunk_index, heading_path, line_start,
              line_end, byte_start, byte_end, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.id,
                doc_id,
                structure_owner_node_id(nodes, item, relative),
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
    return len(chunks), len(nodes)


def prepare_rebuild(database: Path) -> sqlite3.Connection:
    if database.exists():
        if not sqlite_header_ok(database):
            database.unlink()
        else:
            connection = connect(database)
            try:
                values = dict(
                    connection.execute(
                        "SELECT key, value FROM raw_index_metadata "
                        "WHERE key = 'schema_version'"
                    )
                )
            except sqlite3.Error:
                values = {}
            finally:
                connection.close()
            if values.get("schema_version") != SCHEMA_VERSION:
                database.unlink()

    connection = connect(database)
    try:
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
        prior_structure_version = dict(
            connection.execute(
                "SELECT key, value FROM raw_index_metadata "
                "WHERE key = 'structure_schema_version'"
            )
        ).get("structure_schema_version")
        force = (
            prior_threshold != str(threshold)
            or prior_structure_version != chunker.STRUCTURE_SCHEMA_VERSION
        )

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
        structure_node_count = connection.execute(
            "SELECT count(*) FROM raw_structure_nodes"
        ).fetchone()[0]
        fts_count = connection.execute("SELECT count(*) FROM raw_chunk_fts").fetchone()[0]
        if chunk_count != fts_count:
            raise RawRetrievalError("raw chunk and FTS row counts diverged")
        values = {
            "schema_version": SCHEMA_VERSION,
            "truth_source": "raw/**/*.md",
            "chunk_bytes": str(threshold),
            "structure_schema_version": chunker.STRUCTURE_SCHEMA_VERSION,
            "stat_fingerprint": stat_fingerprint(repo_root),
            "document_count": str(document_count),
            "chunk_count": str(chunk_count),
            "structure_node_count": str(structure_node_count),
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
            "structure_nodes": structure_node_count,
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
              c.node_id,
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
                    "node_id": row["node_id"],
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


def normalize_raw_path(raw_path: str) -> str:
    candidate = Path(raw_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise RawRetrievalError("raw path must be a repository-relative Markdown path")
    normalized = candidate.as_posix()
    if not normalized.startswith("raw/") or not normalized.endswith(".md"):
        raise RawRetrievalError("raw path must match raw/**/*.md")
    return normalized


def structure_row(row: sqlite3.Row) -> dict[str, Any]:
    return {field: row[field] for field in STRUCTURE_FIELDS}


def indexed_document_by_path(
    connection: sqlite3.Connection, raw_path: str
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT id, path, checksum FROM raw_documents WHERE path = ?",
        (normalize_raw_path(raw_path),),
    ).fetchone()
    if row is None:
        raise RawRetrievalError("raw path is not indexed; run rebuild")
    return row


def indexed_node(connection: sqlite3.Connection, node_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT n.*, d.path, d.checksum
        FROM raw_structure_nodes n
        JOIN raw_documents d ON d.id = n.document_id
        WHERE n.node_id = ?
        """,
        (node_id,),
    ).fetchone()
    if row is None:
        raise RawRetrievalError("structure node is not indexed; run rebuild")
    return row


def current_document_bytes(repo_root: Path, document: sqlite3.Row) -> bytes | None:
    try:
        raw = (repo_root / str(document["path"])).read_bytes()
    except FileNotFoundError:
        return None
    return raw if sha256(raw) == document["checksum"] else None


def stale_structure_payload(path: str) -> dict[str, Any]:
    return {
        "state": "stale",
        "freshness": "content",
        "path": path,
        "guidance": "run raw_retrieval.py rebuild before structure lookup",
        "canonical": False,
    }


def tree(repo_root: Path, database: Path, raw_path: str) -> dict[str, Any]:
    connection = open_read_only(database)
    try:
        metadata(connection)
        document = indexed_document_by_path(connection, raw_path)
        if current_document_bytes(repo_root, document) is None:
            return stale_structure_payload(str(document["path"]))
        nodes = connection.execute(
            "SELECT * FROM raw_structure_nodes WHERE document_id = ? ORDER BY ordinal",
            (document["id"],),
        ).fetchall()
        return {
            "state": "ready",
            "freshness": "content",
            "path": document["path"],
            "nodes": [structure_row(row) for row in nodes],
            "canonical": False,
        }
    finally:
        connection.close()


def ancestors(repo_root: Path, database: Path, node_id: str) -> dict[str, Any]:
    connection = open_read_only(database)
    try:
        metadata(connection)
        node = indexed_node(connection, node_id)
        if current_document_bytes(repo_root, node) is None:
            return stale_structure_payload(str(node["path"]))

        parents: list[sqlite3.Row] = []
        parent_id = node["parent_id"]
        seen = {node_id}
        while parent_id is not None:
            if parent_id in seen:
                raise RawRetrievalError("structure parent cycle detected; run rebuild")
            seen.add(parent_id)
            parent = connection.execute(
                "SELECT * FROM raw_structure_nodes WHERE node_id = ?",
                (parent_id,),
            ).fetchone()
            if parent is None or parent["document_id"] != node["document_id"]:
                raise RawRetrievalError("structure parent is invalid; run rebuild")
            parents.append(parent)
            parent_id = parent["parent_id"]
        parents.reverse()
        return {
            "state": "ready",
            "freshness": "content",
            "path": node["path"],
            "node": structure_row(node),
            "ancestors": [structure_row(parent) for parent in parents],
            "canonical": False,
        }
    finally:
        connection.close()


def subtree(repo_root: Path, database: Path, node_id: str) -> dict[str, Any]:
    connection = open_read_only(database)
    try:
        metadata(connection)
        node = indexed_node(connection, node_id)
        raw = current_document_bytes(repo_root, node)
        if raw is None:
            return stale_structure_payload(str(node["path"]))
        start = int(node["subtree_byte_start"])
        end = int(node["subtree_byte_end"])
        if not 0 <= start <= end <= len(raw):
            raise RawRetrievalError("structure subtree range is invalid; run rebuild")
        nodes = connection.execute(
            """
            SELECT * FROM raw_structure_nodes
            WHERE document_id = ? AND byte_start >= ? AND subtree_byte_end <= ?
            ORDER BY ordinal
            """,
            (node["document_id"], start, end),
        ).fetchall()
        return {
            "state": "ready",
            "freshness": "content",
            "path": node["path"],
            "node": structure_row(node),
            "nodes": [structure_row(row) for row in nodes],
            "content": raw[start:end].decode("utf-8"),
            "canonical": False,
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
        if values.get("structure_schema_version") != chunker.STRUCTURE_SCHEMA_VERSION:
            stale_reasons.append("structure_schema_version")
        for relative in sorted(set(stored) & set(current)):
            path = current[relative]
            raw = path.read_bytes()
            row = stored[relative]
            if sha256(raw) != row["checksum"]:
                stale_reasons.append(f"document_checksum:{relative}")
                continue
            if len(raw) != row["byte_size"]:
                stale_reasons.append(f"document_metadata:{relative}")
            page = page_for_raw(repo_root, path)
            expected_nodes = chunker.structure_nodes_for_page(page)
            actual_nodes = connection.execute(
                f"SELECT {', '.join(STRUCTURE_FIELDS)} "
                "FROM raw_structure_nodes WHERE document_id = ? ORDER BY ordinal",
                (row["id"],),
            ).fetchall()
            expected_node_rows = [
                tuple(getattr(node, field) for field in STRUCTURE_FIELDS)
                for node in expected_nodes
            ]
            if [tuple(item) for item in actual_nodes] != expected_node_rows:
                stale_reasons.append(f"structure_rows:{relative}")

            expected_chunks = chunker.chunks_for_page(page, threshold)
            actual_chunks = connection.execute(
                """
                SELECT c.node_id, c.chunk_index, c.heading_path, c.line_start,
                       c.line_end, c.byte_start, c.byte_end, c.content_hash,
                       f.heading_path AS fts_heading_path, f.content AS fts_content
                FROM raw_chunks c
                LEFT JOIN raw_chunk_fts f ON f.rowid = c.rowid
                WHERE c.document_id = ? ORDER BY c.chunk_index
                """,
                (row["id"],),
            ).fetchall()
            expected_rows = [
                (
                    structure_owner_node_id(expected_nodes, item, relative),
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
                for item in expected_chunks
            ]
            if [tuple(item) for item in actual_chunks] != expected_rows:
                stale_reasons.append(f"chunk_rows:{relative}")
        chunk_count = connection.execute("SELECT count(*) FROM raw_chunks").fetchone()[0]
        structure_node_count = connection.execute(
            "SELECT count(*) FROM raw_structure_nodes"
        ).fetchone()[0]
        fts_count = connection.execute("SELECT count(*) FROM raw_chunk_fts").fetchone()[0]
        if chunk_count != fts_count:
            stale_reasons.append("fts_rows")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            stale_reasons.append("foreign_keys")
        invalid_containment = connection.execute(
            """
            SELECT count(*) FROM raw_structure_nodes
            WHERE ordinal < 0 OR depth < 0
               OR line_start < 1 OR line_end < line_start
               OR byte_start < 0 OR byte_end < byte_start
               OR subtree_line_start < 1
               OR subtree_line_end < subtree_line_start
               OR subtree_byte_start < 0
               OR subtree_byte_end < subtree_byte_start
               OR subtree_line_start > line_start
               OR line_end > subtree_line_end
               OR subtree_byte_start > byte_start
               OR byte_end > subtree_byte_end
            """
        ).fetchone()[0]
        if invalid_containment:
            stale_reasons.append("node_containment")
        invalid_parents = connection.execute(
            """
            SELECT count(*)
            FROM raw_structure_nodes child
            LEFT JOIN raw_structure_nodes parent ON parent.node_id = child.parent_id
            WHERE (child.parent_id IS NULL AND (child.ordinal != 0 OR child.depth != 0))
               OR (child.parent_id IS NOT NULL AND (
                    parent.node_id IS NULL
                    OR parent.document_id != child.document_id
                    OR parent.ordinal >= child.ordinal
                    OR parent.depth >= child.depth
                    OR parent.subtree_byte_start > child.subtree_byte_start
                    OR child.subtree_byte_end > parent.subtree_byte_end
               ))
            """
        ).fetchone()[0]
        if invalid_parents:
            stale_reasons.append("parent_references")
        invalid_chunk_nodes = connection.execute(
            """
            SELECT count(*)
            FROM raw_chunks chunk
            LEFT JOIN raw_structure_nodes node ON node.node_id = chunk.node_id
            WHERE node.node_id IS NULL
               OR node.document_id != chunk.document_id
               OR NOT (
                    (chunk.byte_start >= node.byte_start AND chunk.byte_end <= node.byte_end)
                    OR (
                        node.parent_id IS NULL
                        AND chunk.byte_start >= node.subtree_byte_start
                        AND chunk.byte_end <= node.subtree_byte_end
                    )
               )
            """
        ).fetchone()[0]
        if invalid_chunk_nodes:
            stale_reasons.append("chunk_node_references")
        if values.get("document_count") != str(len(stored)):
            stale_reasons.append("document_count")
        if values.get("chunk_count") != str(chunk_count):
            stale_reasons.append("chunk_count")
        if values.get("structure_node_count") != str(structure_node_count):
            stale_reasons.append("structure_node_count")
        stale_reasons = list(dict.fromkeys(stale_reasons))
        return {
            "state": "stale" if stale_reasons else "ready",
            "freshness": "exact",
            "stale_reasons": stale_reasons,
            "documents": len(stored),
            "chunks": chunk_count,
            "structure_nodes": structure_node_count,
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
    tree_parser = commands.add_parser("tree")
    tree_parser.add_argument("raw_path")
    ancestors_parser = commands.add_parser("ancestors")
    ancestors_parser.add_argument("node_id")
    subtree_parser = commands.add_parser("subtree")
    subtree_parser.add_argument("node_id")
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
        elif args.command == "tree":
            payload = tree(repo_root, database, args.raw_path)
        elif args.command == "ancestors":
            payload = ancestors(repo_root, database, args.node_id)
        elif args.command == "subtree":
            payload = subtree(repo_root, database, args.node_id)
        else:
            payload = doctor(repo_root, database)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if payload.get("state") == "stale" else 0
    except (RawRetrievalError, OSError, UnicodeError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"state": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
