#!/usr/bin/env python3
"""Passive, bounded readiness facts for a generated wiki retrieval index.

This module deliberately does not import or execute the generated retrieval
runtime.  It only reads small SQLite metadata and filesystem stat data.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sqlite3
import time
from pathlib import Path
from urllib.parse import quote

VERSION = 1
SCHEMA_VERSION = "wiki-heading-index-v8"
SQLITE_HEADER = b"SQLite format 3\x00"
PAGE_DIRECTORIES = (
    "concepts", "entities", "people", "projects", "timelines", "analyses", "sources",
)
REQUIRED_TABLES = {"pages", "chunks", "chunk_fts", "chunk_embeddings", "index_metadata"}
MAX_PATHS = 10_000
MAX_ENTRIES = 50_000
SCAN_SECONDS = 0.75


def _base(root: Path | None, mode: str) -> dict:
    not_applicable = root is None or mode != "wiki"
    return {
        "version": VERSION,
        # Do not resolve a supplied root for project/not-applicable probes.
        "root": None if root is None else str(root),
        "checkedAt": time.time(),
        "sqlite": {
            "configured": None if not_applicable else False,
            "state": "not_applicable" if not_applicable else "off",
            "freshness": "unknown" if not_applicable else "stat",
            "pages": None,
            "chunks": None,
            "fts": None,
            "reasons": [],
        },
        "onnx": {
            "state": "not_applicable" if not_applicable else "not_configured",
            "packages": {name: False for name in ("onnxruntime", "tokenizers", "numpy")},
            "modelConfigured": False,
            "modelPresent": False,
            "tokenizerConfigured": False,
            "tokenizerPresent": False,
            "inferenceVerified": False,
        },
        "vectors": {"state": "not_applicable" if not_applicable else "none", "rows": None},
        # The dashboard chat does not invoke SQLite FTS or vectors merely because
        # an index happens to contain them.
        "chatMethods": {"grep": True, "fts": False, "wikilinks": True, "vector": False},
        "note": "Passive status only; current is metadata plus file-stat freshness, not retrieval health. Server environment only; CLI flags are unknown.",
    }


def _inside(root: Path, path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except (OSError, RuntimeError):
        return False


def _regular_inside(root: Path, path: Path) -> bool:
    try:
        return not path.is_symlink() and path.is_file() and _inside(root, path)
    except OSError:
        return False


def _configured(root: Path) -> bool:
    """Mirror the generated loop's script-presence posture without following escapes."""
    return _regular_inside(root, root / "scripts" / "wiki_retrieval.py")


def _artifact_present(value: str | None) -> bool:
    if not value:
        return False
    try:
        # Match canonical provider resolution: relative paths use this process CWD.
        path = Path(value).resolve()
        return path.is_file()
    except (OSError, RuntimeError, ValueError):
        return False


def _onnx_status(payload: dict) -> None:
    onnx = payload["onnx"]
    model = os.environ.get("WIKI_ONNX_MODEL")
    tokenizer = os.environ.get("WIKI_TOKENIZER")
    onnx["modelConfigured"] = bool(model)
    onnx["tokenizerConfigured"] = bool(tokenizer)
    onnx["modelPresent"] = _artifact_present(model)
    onnx["tokenizerPresent"] = _artifact_present(tokenizer)
    try:
        packages = {name: importlib.util.find_spec(name) is not None for name in onnx["packages"]}
    except Exception:
        # A broken import-path inspection says nothing about SQLite readiness.
        onnx["state"] = "unknown"
        onnx["packages"] = {name: None for name in onnx["packages"]}
        return
    onnx["packages"] = packages
    if not model and not tokenizer:
        onnx["state"] = "not_configured"
    elif not all(packages.values()):
        onnx["state"] = "runtime_missing"
    elif not (onnx["modelPresent"] and onnx["tokenizerPresent"]):
        onnx["state"] = "artifacts_missing"
    else:
        onnx["state"] = "configured"


def _scan_fingerprint(root: Path, deadline: float) -> tuple[str | None, str | None]:
    """Return source stat hash or a non-sensitive reason; never read page content."""
    wiki = root / "wiki"
    if wiki.is_symlink() or (wiki.exists() and not wiki.is_dir()):
        return None, "source_unsafe"
    rows: list[str] = []
    entries = 0
    paths = 0
    try:
        for category in PAGE_DIRECTORIES:
            directory = wiki / category
            if directory.is_symlink():
                return None, "source_unsafe"
            if not directory.exists():
                continue
            if not directory.is_dir() or not _inside(root, directory):
                return None, "source_unsafe"
            stack = [directory]
            while stack:
                if time.monotonic() > deadline:
                    return None, "source_limit"
                current = stack.pop()
                with os.scandir(current) as iterator:
                    for entry in iterator:
                        entries += 1
                        if entries > MAX_ENTRIES or time.monotonic() > deadline:
                            return None, "source_limit"
                        if entry.is_symlink():
                            return None, "source_unsafe"
                        path = Path(entry.path)
                        if not _inside(root, path):
                            return None, "source_unsafe"
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(path)
                        elif entry.is_file(follow_symlinks=False) and path.suffix == ".md":
                            paths += 1
                            if paths > MAX_PATHS:
                                return None, "source_limit"
                            stat = path.stat()
                            rows.append(f"{path.relative_to(root).as_posix()}\0{stat.st_size}\0{stat.st_mtime_ns}")
    except (OSError, ValueError, RuntimeError):
        return None, "source_error"
    return hashlib.sha256("\n".join(sorted(rows)).encode()).hexdigest(), None


def _schema_fingerprint(root: Path) -> tuple[str | None, str | None]:
    path = root / "templates" / "llm-wiki-three-layer" / "sqlite_operational.schema.sql"
    if not _regular_inside(root, path):
        return None, "schema_unknown"
    try:
        # Bound the actual read, not merely a potentially racing stat result.
        with path.open("rb") as handle:
            schema = handle.read(1_000_001)
        if len(schema) > 1_000_000:
            return None, "schema_unknown"
        return hashlib.sha256(schema).hexdigest(), None
    except OSError:
        return None, "schema_unknown"


def _db_stat(path: Path) -> tuple[int, int, int, int, int]:
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _active_sidecars(path: Path) -> bool:
    return any((path.parent / f"{path.name}{suffix}").exists() for suffix in ("-wal", "-journal", "-shm"))


def _open_readonly(path: Path, deadline: float) -> sqlite3.Connection:
    encoded = quote(str(path.resolve()), safe="/")
    connection = sqlite3.connect(f"file:{encoded}?mode=ro&immutable=1", uri=True, timeout=0.1)
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA trusted_schema = OFF")
    connection.execute("PRAGMA busy_timeout = 100")
    connection.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 1000)
    return connection


def _sqlite_status(payload: dict, root: Path) -> None:
    sqlite = payload["sqlite"]
    vectors = payload["vectors"]
    sqlite["configured"] = _configured(root)
    if not sqlite["configured"]:
        # No configured index was inspected; do not infer that vectors are absent.
        vectors["state"] = "unknown"
        return
    path = root / "state" / "wiki_index.sqlite"
    if path.is_symlink() or not _inside(root, path):
        sqlite.update(state="unknown", freshness="unknown", reasons=["db_unsafe"])
        vectors["state"] = "unknown"
        return
    if not path.is_file():
        sqlite.update(state="missing", freshness="unknown", reasons=["db_missing"])
        vectors["state"] = "unknown"
        return
    if _active_sidecars(path):
        sqlite.update(state="unknown", freshness="unknown", reasons=["db_active_journal"])
        vectors["state"] = "unknown"
        return
    try:
        with path.open("rb") as handle:
            header = handle.read(100)
            if header[:len(SQLITE_HEADER)] != SQLITE_HEADER:
                sqlite.update(state="error", freshness="unknown", reasons=["db_header"])
                vectors["state"] = "unknown"
                return
            # Read-only immutable access deliberately refuses WAL modes rather
            # than pretending the live journal is a health signal.
            if len(header) < 20 or header[18] != 1 or header[19] != 1:
                sqlite.update(state="unknown", freshness="unknown", reasons=["db_journal_mode"])
                vectors["state"] = "unknown"
                return
        before_stat = _db_stat(path)
    except OSError:
        sqlite.update(state="error", freshness="unknown", reasons=["db_read"])
        vectors["state"] = "unknown"
        return

    deadline = time.monotonic() + SCAN_SECONDS
    connection = None
    try:
        connection = _open_readonly(path, deadline)
        placeholders = ",".join("?" for _ in REQUIRED_TABLES)
        tables = {
            row[0] for row in connection.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name IN ({placeholders})",
                tuple(sorted(REQUIRED_TABLES)),
            )
        }
        if not REQUIRED_TABLES.issubset(tables):
            sqlite.update(state="unknown", freshness="unknown", reasons=["required_tables"])
            vectors["state"] = "unknown"
            return
        metadata_rows = connection.execute(
            "SELECT substr(key, 1, 129), substr(value, 1, 129) FROM index_metadata LIMIT 129"
        ).fetchall()
        if len(metadata_rows) > 128 or any(
            not isinstance(key, str) or not isinstance(value, str) or len(key) > 128 or len(value) > 128
            for key, value in metadata_rows
        ):
            sqlite.update(state="unknown", freshness="unknown", reasons=["metadata_malformed"])
            vectors["state"] = "unknown"
            return
        metadata = dict(metadata_rows)
        sqlite["pages"] = int(connection.execute("SELECT count(*) FROM pages").fetchone()[0])
        sqlite["chunks"] = int(connection.execute("SELECT count(*) FROM chunks").fetchone()[0])
        vector_rows = int(connection.execute("SELECT count(*) FROM chunk_embeddings").fetchone()[0])
        vectors.update(state="stored" if vector_rows else "none", rows=vector_rows)
        try:
            fts_sql = connection.execute(
                "SELECT substr(sql, 1, 4096) FROM sqlite_master WHERE type='table' AND name='chunk_fts'"
            ).fetchone()[0] or ""
            connection.execute("SELECT rowid FROM chunk_fts LIMIT 0").fetchall()
            sqlite["fts"] = "virtual table" in fts_sql.casefold() and "using fts" in fts_sql.casefold()
        except (sqlite3.Error, TypeError):
            sqlite["fts"] = False

        expected_schema, schema_reason = _schema_fingerprint(root)
        if schema_reason:
            sqlite.update(state="unknown", freshness="unknown", reasons=[schema_reason])
            return
        if metadata.get("schema_version") != SCHEMA_VERSION:
            sqlite.update(state="unknown", freshness="unknown", reasons=["schema_version"])
            return
        if metadata.get("schema_fingerprint") != expected_schema:
            sqlite.update(state="unknown", freshness="unknown", reasons=["schema_fingerprint"])
            return
        if metadata.get("truth_source") != "markdown" or metadata.get("rebuildable") != "true":
            sqlite.update(state="unknown", freshness="unknown", reasons=["metadata_truth"])
            return
        actual_stat, reason = _scan_fingerprint(root, deadline)
        if reason:
            sqlite.update(state="unknown", freshness="unknown", reasons=[reason])
            return
        if _active_sidecars(path) or _db_stat(path) != before_stat:
            sqlite.update(state="unknown", freshness="unknown", reasons=["db_changed"], pages=None, chunks=None, fts=None)
            vectors.update(state="unknown", rows=None)
        elif metadata.get("source_stat_fingerprint") == actual_stat:
            sqlite.update(state="current", freshness="stat", reasons=[])
        else:
            sqlite.update(state="stale", freshness="stat", reasons=["source_stat"])
    except (sqlite3.Error, OSError, ValueError, OverflowError):
        sqlite.update(state="error", freshness="unknown", reasons=["db_query"])
        vectors["state"] = "unknown"
    finally:
        if connection is not None:
            connection.close()


def inspect_status(root: Path | None, mode: str = "wiki") -> dict:
    """Return safe, bounded operational facts. This function never raises for status failures."""
    payload = _base(root, mode)
    if root is None or mode != "wiki":
        return payload
    try:
        resolved = root.resolve()
        payload["root"] = str(resolved)
        if not resolved.is_dir() or resolved.is_symlink():
            payload["sqlite"].update(configured=False, state="off", freshness="unknown", reasons=["root_invalid"])
            payload["vectors"] = {"state": "unknown", "rows": None}
            _onnx_status(payload)
            return payload
        _onnx_status(payload)
        _sqlite_status(payload, resolved)
    except Exception:
        # Status is advisory. Do not let an unusual filesystem or environment
        # condition leak details or crash the dashboard.
        payload["sqlite"].update(state="error", freshness="unknown", reasons=["status_error"])
        payload["vectors"] = {"state": "unknown", "rows": None}
    return payload
