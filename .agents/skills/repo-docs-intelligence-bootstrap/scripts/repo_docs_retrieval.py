#!/usr/bin/env python3
"""Disposable SQLite FTS and Markdown-link index for Repo Docs memory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from bisect import bisect_right
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote


SCHEMA_VERSION = "repo-docs-heading-index-v3"
DEFAULT_DB = "state/repo_docs_index.sqlite"
DEFAULT_CHUNK_BYTES = 64 * 1024
MAX_RESULTS = 100
MAX_HOPS = 2
MAX_PAGES = 12
SQLITE_HEADER = b"SQLite format 3\x00"
DISCOVERY_TABLES = frozenset(
    {
        "index_metadata",
        "documents",
        "chunks",
        "markdown_links",
        "chunk_fts",
        "chunk_trigram",
    }
)
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$", re.MULTILINE)
LINK_START_RE = re.compile(r"(?<!!)\[([^]\n]+)\]\(")

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE index_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE documents (
  path TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  content_fingerprint TEXT NOT NULL,
  byte_size INTEGER NOT NULL
);
CREATE TABLE chunks (
  id TEXT PRIMARY KEY,
  document_path TEXT NOT NULL REFERENCES documents(path) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  heading_path TEXT NOT NULL,
  line_start INTEGER NOT NULL,
  line_end INTEGER NOT NULL,
  content TEXT NOT NULL,
  content_fingerprint TEXT NOT NULL,
  UNIQUE(document_path, chunk_index)
);
CREATE TABLE markdown_links (
  source_path TEXT NOT NULL REFERENCES documents(path) ON DELETE CASCADE,
  target_path TEXT,
  label TEXT NOT NULL,
  raw_target TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('resolved', 'missing', 'outside')),
  UNIQUE(source_path, label, raw_target)
);
CREATE INDEX markdown_links_source_idx ON markdown_links(source_path);
CREATE INDEX markdown_links_target_idx ON markdown_links(target_path);
CREATE VIRTUAL TABLE chunk_fts USING fts5(
  chunk_id UNINDEXED,
  document_path UNINDEXED,
  title,
  heading_path,
  content,
  tokenize = 'unicode61'
);
"""
TRIGRAM_SCHEMA = """
CREATE VIRTUAL TABLE chunk_trigram USING fts5(
  content,
  content = '',
  tokenize = 'trigram'
);
"""
TRIGRAM_FALLBACK_SCHEMA = """
CREATE VIRTUAL TABLE chunk_trigram USING fts5(
  content,
  content = '',
  tokenize = 'unicode61'
);
"""


class RetrievalError(RuntimeError):
    """Controlled CLI failure."""


@dataclass(frozen=True)
class Document:
    path: str
    title: str
    content_fingerprint: str
    byte_size: int
    text: str


@dataclass(frozen=True)
class Chunk:
    id: str
    document_path: str
    chunk_index: int
    heading_path: str
    line_start: int
    line_end: int
    content: str
    content_fingerprint: str


@dataclass(frozen=True)
class Link:
    source_path: str
    target_path: str | None
    label: str
    raw_target: str
    status: str


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def markdown_paths(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    agents = repo_root / "AGENTS.md"
    if agents.is_file():
        paths.append(agents)
    for directory in (repo_root / "docs", repo_root / "wiki"):
        if directory.is_dir():
            paths.extend(path for path in directory.rglob("*.md") if path.is_file())
    return sorted(set(paths), key=lambda path: path.relative_to(repo_root).as_posix())


def title_for(path: Path, text: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else path.stem.replace("-", " ").title()


def document_for(repo_root: Path, path: Path) -> Document:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RetrievalError(f"Markdown is not UTF-8: {path}") from exc
    return Document(
        path.relative_to(repo_root).as_posix(),
        title_for(path, text),
        digest(raw),
        len(raw),
        text,
    )


def documents(repo_root: Path) -> list[Document]:
    return [document_for(repo_root, path) for path in markdown_paths(repo_root)]


def corpus_fingerprint(records: list[Document]) -> str:
    material = "\n".join(
        f"{record.path}\0{record.content_fingerprint}\0{record.byte_size}"
        for record in records
    )
    return digest(material.encode("utf-8"))


def corpus_fingerprint_from_disk(repo_root: Path) -> str:
    """Stream an exact corpus fingerprint without retaining document bodies."""
    records = []
    for path in markdown_paths(repo_root):
        content_digest = hashlib.sha256()
        byte_size = 0
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                content_digest.update(block)
                byte_size += len(block)
        records.append(
            f"{path.relative_to(repo_root).as_posix()}\0{content_digest.hexdigest()}\0{byte_size}"
        )
    return digest("\n".join(records).encode("utf-8"))


def source_stat_fingerprint(repo_root: Path) -> str:
    """Return a cheap source-change marker without reading Markdown bodies."""
    records = []
    for path in markdown_paths(repo_root):
        try:
            stat = path.stat()
        except OSError as exc:
            raise RetrievalError(f"Markdown changed during stat scan: {path}") from exc
        records.append(
            f"{path.relative_to(repo_root).as_posix()}\0{stat.st_size}\0{stat.st_mtime_ns}"
        )
    return digest("\n".join(records).encode("utf-8"))


def split_span(
    text: str, start: int, end: int, byte_limit: int
) -> list[tuple[int, int]]:
    if byte_limit <= 0:
        raise RetrievalError("chunk byte limit must be positive")
    spans: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        byte_count = 0
        cut = cursor
        while cut < end:
            width = len(text[cut].encode("utf-8"))
            if byte_count + width > byte_limit:
                break
            byte_count += width
            cut += 1
        if cut == cursor:
            raise RetrievalError("chunk byte limit is smaller than one UTF-8 character")
        if cut < end:
            paragraph = text.rfind("\n\n", cursor, cut)
            if paragraph > cursor:
                cut = paragraph + 2
        spans.append((cursor, cut))
        cursor = cut
    return spans


def chunks_for(document: Document, byte_limit: int) -> list[Chunk]:
    line_starts = [0]
    line_starts.extend(
        index + 1 for index, character in enumerate(document.text) if character == "\n"
    )

    def line_at(offset: int) -> int:
        return bisect_right(line_starts, offset)

    headings: list[tuple[int, int, str]] = []
    stack: list[tuple[int, str]] = []
    for match in HEADING_RE.finditer(document.text):
        level = len(match.group(1))
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, match.group(2).strip()))
        headings.append((match.start(), level, " > ".join(title for _, title in stack)))
    sections: list[tuple[int, int, str]] = []
    if not headings:
        sections = [(0, len(document.text), "")]
    else:
        if headings[0][0]:
            sections.append((0, headings[0][0], ""))
        sections.extend(
            (
                start,
                headings[index + 1][0]
                if index + 1 < len(headings)
                else len(document.text),
                heading,
            )
            for index, (start, _level, heading) in enumerate(headings)
        )
    chunks: list[Chunk] = []
    for start, end, heading in sections:
        for chunk_start, chunk_end in split_span(document.text, start, end, byte_limit):
            content = document.text[chunk_start:chunk_end]
            fingerprint = digest(content.encode("utf-8"))
            index = len(chunks)
            chunks.append(
                Chunk(
                    id=f"chunk-{digest(f'{document.path}:{index}:{fingerprint}'.encode())[:24]}",
                    document_path=document.path,
                    chunk_index=index,
                    heading_path=heading,
                    line_start=line_at(chunk_start),
                    line_end=line_at(chunk_end - 1),
                    content=content,
                    content_fingerprint=fingerprint,
                )
            )
    if not chunks:
        fingerprint = digest(b"")
        chunks.append(
            Chunk(
                f"chunk-{digest(f'{document.path}:0:{fingerprint}'.encode())[:24]}",
                document.path,
                0,
                "",
                1,
                1,
                "",
                fingerprint,
            )
        )
    return chunks


def prose_without_code(text: str) -> str:
    lines: list[str] = []
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^[ \t]{0,3}(```+|~~~+)", line)
        if marker:
            token = marker.group(1)[0]
            fence = None if fence == token else token if fence is None else fence
            lines.append("\n" if line.endswith("\n") else "")
            continue
        if fence:
            lines.append("\n" if line.endswith("\n") else "")
            continue
        lines.append(re.sub(r"`[^`\n]*`", "", line))
    return "".join(lines)


def markdown_link_pairs(text: str) -> list[tuple[str, str]]:
    text = prose_without_code(text)
    pairs: list[tuple[str, str]] = []
    for match in LINK_START_RE.finditer(text):
        label = match.group(1).strip()
        cursor = match.end()
        if cursor < len(text) and text[cursor] == "<":
            close = text.find(">", cursor + 1)
            if close < 0 or close + 1 >= len(text) or text[close + 1] != ")":
                continue
            target = text[cursor + 1 : close]
        else:
            depth = 0
            escaped = False
            start = cursor
            while cursor < len(text):
                character = text[cursor]
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == "(":
                    depth += 1
                elif character == ")":
                    if depth == 0:
                        break
                    depth -= 1
                cursor += 1
            if cursor >= len(text):
                continue
            target = text[start:cursor].strip()
        if label and target:
            pairs.append((label, target))
    return pairs


def resolve_link(repo_root: Path, source: str, target: str) -> tuple[str | None, str]:
    target = target.split("#", 1)[0].split("?", 1)[0].strip()
    if (
        not target
        or target.startswith("//")
        or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target)
    ):
        return None, "skip"
    candidate = ((repo_root / source).parent / unquote(target)).resolve()
    try:
        relative = candidate.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None, "outside"
    return relative, "resolved" if candidate.is_file() else "missing"


def links_for(repo_root: Path, records: list[Document]) -> list[Link]:
    rows: list[Link] = []
    for document in records:
        for label, raw_target in markdown_link_pairs(document.text):
            target_path, status = resolve_link(repo_root, document.path, raw_target)
            if status == "skip":
                continue
            rows.append(Link(document.path, target_path, label, raw_target, status))
    return rows


def database_path(repo_root: Path, override: str | None) -> Path:
    path = Path(override or DEFAULT_DB)
    return path if path.is_absolute() else repo_root / path


def rebuild(
    repo_root: Path, db_path: Path, byte_limit: int, trigram: bool = True
) -> dict[str, object]:
    paths = markdown_paths(repo_root)
    stat_fingerprint = source_stat_fingerprint(repo_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{db_path.stem}.", suffix=".tmp", dir=db_path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    trigram_enabled = trigram
    corpus_rows: list[str] = []
    chunk_count = 0
    link_count = 0
    try:
        connection = sqlite3.connect(temporary)
        try:
            connection.executescript(SCHEMA)
            if trigram:
                try:
                    connection.executescript(TRIGRAM_SCHEMA)
                except sqlite3.OperationalError as exc:
                    if "no such tokenizer" not in str(exc).lower():
                        raise
                    connection.executescript(TRIGRAM_FALLBACK_SCHEMA)
                    trigram_enabled = False
            else:
                connection.executescript(TRIGRAM_FALLBACK_SCHEMA)
            for path in paths:
                document = document_for(repo_root, path)
                chunks = chunks_for(document, byte_limit)
                links = list(dict.fromkeys(links_for(repo_root, [document])))
                connection.execute(
                    "INSERT INTO documents VALUES (?, ?, ?, ?)",
                    (
                        document.path,
                        document.title,
                        document.content_fingerprint,
                        document.byte_size,
                    ),
                )
                connection.executemany(
                    "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [tuple(asdict(row).values()) for row in chunks],
                )
                connection.executemany(
                    "INSERT OR IGNORE INTO markdown_links VALUES (?, ?, ?, ?, ?)",
                    [tuple(asdict(row).values()) for row in links],
                )
                connection.executemany(
                    "INSERT INTO chunk_fts VALUES (?, ?, ?, ?, ?)",
                    [
                        (
                            row.id,
                            row.document_path,
                            document.title,
                            row.heading_path,
                            row.content,
                        )
                        for row in chunks
                    ],
                )
                corpus_rows.append(
                    f"{document.path}\0{document.content_fingerprint}\0{document.byte_size}"
                )
                chunk_count += len(chunks)
            if trigram_enabled:
                connection.execute(
                    "INSERT INTO chunk_trigram(rowid, content) "
                    "SELECT rowid, content FROM chunks"
                )
            corpus_fingerprint_value = digest("\n".join(corpus_rows).encode("utf-8"))
            link_count = connection.execute(
                "SELECT count(*) FROM markdown_links"
            ).fetchone()[0]
            metadata = {
                "schema_version": SCHEMA_VERSION,
                "truth_source": "AGENTS.md, docs/**/*.md, wiki/**/*.md",
                "canonical": "false",
                "corpus_fingerprint": corpus_fingerprint_value,
                "source_stat_fingerprint": stat_fingerprint,
                "trigram_index": "enabled" if trigram_enabled else "disabled",
                "document_count": str(len(paths)),
                "chunk_count": str(chunk_count),
                "link_count": str(link_count),
                "chunk_byte_limit": str(byte_limit),
            }
            connection.executemany(
                "INSERT INTO index_metadata VALUES (?, ?)", metadata.items()
            )
            connection.commit()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RetrievalError(
                    f"temporary index failed integrity check: {integrity}"
                )
        finally:
            connection.close()
        final_stat_fingerprint = source_stat_fingerprint(repo_root)
        if (
            corpus_fingerprint_value != corpus_fingerprint_from_disk(repo_root)
            or stat_fingerprint != final_stat_fingerprint
        ):
            raise RetrievalError(
                "Markdown changed during rebuild; prior index was not replaced"
            )
        os.replace(temporary, db_path)
        Path(f"{db_path}-wal").unlink(missing_ok=True)
        Path(f"{db_path}-shm").unlink(missing_ok=True)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "state": "ready",
        "database": str(db_path),
        "documents": len(paths),
        "chunks": chunk_count,
        "links": link_count,
        "corpus_fingerprint": corpus_fingerprint_value,
        "source_stat_fingerprint": stat_fingerprint,
        "trigram_index": "enabled" if trigram_enabled else "disabled",
        "canonical": False,
    }


def open_read_only(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise RetrievalError(
            "derived retrieval index is not enabled or has not been built"
        )
    with db_path.open("rb") as handle:
        header = handle.read(len(SQLITE_HEADER))
    if header != SQLITE_HEADER:
        raise RetrievalError("derived retrieval index is malformed")
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def health(repo_root: Path, db_path: Path, deep: bool = False) -> dict[str, object]:
    """Check stat freshness normally and content-exact integrity when deep."""
    if not db_path.exists():
        return {"state": "off", "database": str(db_path), "canonical": False}
    try:
        connection = open_read_only(db_path)
    except (OSError, sqlite3.Error, RetrievalError) as exc:
        return {
            "state": "malformed",
            "database": str(db_path),
            "error": str(exc),
            "canonical": False,
        }
    reasons: list[str] = []
    try:
        metadata = dict(connection.execute("SELECT key, value FROM index_metadata"))
        if metadata.get("schema_version") != SCHEMA_VERSION:
            reasons.append("schema_version")
        try:
            current_stat_fingerprint = source_stat_fingerprint(repo_root)
        except RetrievalError:
            reasons.append("source_stat_fingerprint")
        else:
            if metadata.get("source_stat_fingerprint") != current_stat_fingerprint:
                reasons.append("source_stat_fingerprint")
        counts = {
            "documents": connection.execute(
                "SELECT count(*) FROM documents"
            ).fetchone()[0],
            "chunks": connection.execute("SELECT count(*) FROM chunks").fetchone()[0],
            "links": connection.execute(
                "SELECT count(*) FROM markdown_links"
            ).fetchone()[0],
            "fts": connection.execute("SELECT count(*) FROM chunk_fts").fetchone()[0],
            "trigram": connection.execute(
                "SELECT count(*) FROM chunk_trigram"
            ).fetchone()[0],
        }
        if counts["chunks"] != counts["fts"]:
            reasons.append("fts_rows")
        trigram_enabled = metadata.get("trigram_index") == "enabled"
        if counts["trigram"] != (counts["chunks"] if trigram_enabled else 0):
            reasons.append("trigram_rows")
        for key in ("documents", "chunks", "links"):
            if str(counts[key]) != metadata.get(
                f"{key[:-1] if key.endswith('s') else key}_count"
            ):
                reasons.append(f"{key}_count")
        if deep:
            current = documents(repo_root)
            if metadata.get("corpus_fingerprint") != corpus_fingerprint(current):
                reasons.append("corpus_fingerprint")
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                reasons.append("integrity")
            if metadata.get("canonical") != "false":
                reasons.append("canonical_marker")
            if metadata.get("truth_source") != "AGENTS.md, docs/**/*.md, wiki/**/*.md":
                reasons.append("truth_source")
            indexed_documents = {
                row["path"]: (
                    row["title"],
                    row["content_fingerprint"],
                    row["byte_size"],
                )
                for row in connection.execute(
                    "SELECT path, title, content_fingerprint, byte_size FROM documents"
                )
            }
            expected_documents = {
                row.path: (row.title, row.content_fingerprint, row.byte_size)
                for row in current
            }
            if indexed_documents != expected_documents:
                reasons.append("document_rows")
            indexed_chunks = {
                tuple(row)
                for row in connection.execute(
                    """SELECT id, document_path, chunk_index, heading_path,
                              line_start, line_end, content, content_fingerprint
                       FROM chunks"""
                )
            }
            try:
                byte_limit = int(metadata.get("chunk_byte_limit", "0"))
                expected_chunks = {
                    tuple(asdict(chunk).values())
                    for document in current
                    for chunk in chunks_for(document, byte_limit)
                }
            except (TypeError, ValueError, RetrievalError):
                expected_chunks = set()
                reasons.append("chunk_byte_limit")
            if indexed_chunks != expected_chunks:
                reasons.append("chunk_rows")
            for row in connection.execute(
                "SELECT content, content_fingerprint FROM chunks"
            ):
                if digest(row["content"].encode("utf-8")) != row["content_fingerprint"]:
                    reasons.append("chunk_fingerprint")
                    break
            mismatch = connection.execute(
                """SELECT 1 FROM chunks c LEFT JOIN chunk_fts f ON f.chunk_id = c.id
                   WHERE f.chunk_id IS NULL OR f.content != c.content LIMIT 1"""
            ).fetchone()
            if mismatch:
                reasons.append("fts_payload")
            if trigram_enabled:
                trigram_mismatch = connection.execute(
                    """SELECT 1 FROM chunks c
                       LEFT JOIN chunk_trigram t ON t.rowid = c.rowid
                       WHERE t.rowid IS NULL LIMIT 1"""
                ).fetchone()
                if trigram_mismatch:
                    reasons.append("trigram_rowids")
            indexed_links = {
                tuple(row)
                for row in connection.execute(
                    "SELECT source_path, target_path, label, raw_target, status FROM markdown_links"
                )
            }
            expected_links = {
                tuple(asdict(row).values()) for row in links_for(repo_root, current)
            }
            if indexed_links != expected_links:
                reasons.append("link_rows")
        return {
            "state": "stale" if reasons else "ready",
            "database": str(db_path),
            **counts,
            "stale_reasons": sorted(set(reasons)),
            "freshness": "content" if deep else "stat",
            "trigram_index": metadata.get("trigram_index", "unknown"),
            "canonical": False,
        }
    except sqlite3.Error as exc:
        return {
            "state": "malformed",
            "database": str(db_path),
            "error": str(exc),
            "canonical": False,
        }
    finally:
        connection.close()


def require_ready(repo_root: Path, db_path: Path) -> sqlite3.Connection:
    """Open a structurally compatible discovery index without source hashing."""
    if not db_path.exists():
        raise RetrievalError("derived retrieval index is not enabled; run rebuild")
    connection: sqlite3.Connection | None = None
    try:
        connection = open_read_only(db_path)
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if not DISCOVERY_TABLES.issubset(tables):
            raise RetrievalError("derived retrieval index is missing discovery tables")
        metadata = dict(connection.execute("SELECT key, value FROM index_metadata"))
        if metadata.get("schema_version") != SCHEMA_VERSION:
            raise RetrievalError("derived retrieval index schema is stale")
        return connection
    except (OSError, sqlite3.Error, RetrievalError) as exc:
        if connection is not None:
            connection.close()
        raise RetrievalError(
            "derived retrieval index is malformed or incompatible; run rebuild"
        ) from exc


def fts_query(query: str) -> str:
    tokens = re.findall(r"[\w-]+", query, re.UNICODE)
    if not tokens:
        raise RetrievalError("search query must contain a word")
    return " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


def search_results(
    connection: sqlite3.Connection, query: str, limit: int
) -> list[dict[str, object]]:
    """Return exactly one best-ranked matching chunk per document."""
    rows = connection.execute(
        """WITH matched AS (
             SELECT chunk_fts.document_path, chunk_fts.title,
                    chunk_fts.heading_path, chunk_fts.content,
                    chunks.line_start, chunks.line_end, chunks.chunk_index,
                    bm25(chunk_fts) AS score
             FROM chunk_fts JOIN chunks ON chunks.id = chunk_fts.chunk_id
             WHERE chunk_fts MATCH ?
           ), ranked AS (
             SELECT *, row_number() OVER (
               PARTITION BY document_path ORDER BY score, chunk_index
             ) AS document_rank
             FROM matched
           )
           SELECT document_path, title, heading_path, content,
                  line_start, line_end, score
           FROM ranked WHERE document_rank = 1
           ORDER BY score, document_path LIMIT ?""",
        (fts_query(query), limit),
    ).fetchall()
    return [
        {
            "path": row["document_path"],
            "title": row["title"],
            "heading_path": row["heading_path"],
            "line_start": row["line_start"],
            "line_end": row["line_end"],
            "score": row["score"],
            "snippet": row["content"][:320],
        }
        for row in rows
    ]


def search(repo_root: Path, db_path: Path, query: str, limit: int) -> dict[str, object]:
    connection = require_ready(repo_root, db_path)
    try:
        return {
            "query": query,
            "results": search_results(connection, query, limit),
            "freshness": "unchecked",
            "canonical": False,
        }
    finally:
        connection.close()


def search_batch(
    repo_root: Path, db_path: Path, queries: list[str], limit: int
) -> dict[str, object]:
    """Search related questions with one connection and document attribution."""
    if not queries:
        raise RetrievalError("search batch requires at least one query")
    connection = require_ready(repo_root, db_path)
    try:
        query_results = []
        documents_by_path: dict[str, dict[str, object]] = {}
        for query in queries:
            results = search_results(connection, query, limit)
            query_results.append({"query": query, "results": results})
            for result in results:
                path = str(result["path"])
                existing = documents_by_path.get(path)
                if existing is None:
                    documents_by_path[path] = {**result, "queries": [query]}
                else:
                    existing["queries"].append(query)
        return {
            "queries": query_results,
            "documents": list(documents_by_path.values()),
            "freshness": "unchecked",
            "canonical": False,
        }
    finally:
        connection.close()


def traverse(
    repo_root: Path, db_path: Path, start: str, hops: int, limit: int
) -> dict[str, object]:
    connection = require_ready(repo_root, db_path)
    try:
        matched = connection.execute(
            "SELECT path, title FROM documents WHERE path = ? OR lower(title) = lower(?) ORDER BY path LIMIT 2",
            (start, start),
        ).fetchall()
        if len(matched) != 1:
            raise RetrievalError("start document is missing or ambiguous")
        start_path = matched[0]["path"]
        queue: deque[tuple[str, int]] = deque([(start_path, 0)])
        seen = {start_path}
        results: list[dict[str, object]] = []
        while queue and len(results) < limit:
            source, depth = queue.popleft()
            if depth >= hops:
                continue
            rows = connection.execute(
                """SELECT l.target_path, l.label, d.title FROM markdown_links l
                   JOIN documents d ON d.path = l.target_path
                   WHERE l.source_path = ? AND l.status = 'resolved'
                   ORDER BY l.target_path""",
                (source,),
            ).fetchall()
            for row in rows:
                target = row["target_path"]
                if target in seen:
                    continue
                seen.add(target)
                results.append(
                    {
                        "path": target,
                        "title": row["title"],
                        "label": row["label"],
                        "depth": depth + 1,
                    }
                )
                queue.append((target, depth + 1))
                if len(results) >= limit:
                    break
        return {
            "start": start_path,
            "hops": hops,
            "limit": limit,
            "results": results,
            "freshness": "unchecked",
            "canonical": False,
        }
    finally:
        connection.close()


def bounded(value: int, name: str, maximum: int) -> int:
    if value < 1 or value > maximum:
        raise RetrievalError(f"{name} must be between 1 and {maximum}")
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--repo-root", default=".")
    result.add_argument("--database")
    commands = result.add_subparsers(dest="command", required=True)
    rebuild_parser = commands.add_parser("rebuild")
    rebuild_parser.add_argument("--chunk-bytes", type=int, default=DEFAULT_CHUNK_BYTES)
    rebuild_parser.add_argument(
        "--no-trigram",
        action="store_true",
        help="skip the larger substring index and retain token FTS only",
    )
    commands.add_parser("status")
    search_parser = commands.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=10)
    batch_parser = commands.add_parser("search-batch")
    batch_parser.add_argument("query", nargs="+")
    batch_parser.add_argument("--limit", type=int, default=10)
    traverse_parser = commands.add_parser("traverse")
    traverse_parser.add_argument("start")
    traverse_parser.add_argument("--hops", type=int, default=MAX_HOPS)
    traverse_parser.add_argument("--limit", type=int, default=MAX_PAGES)
    commands.add_parser("doctor")
    return result


def main() -> int:
    args = parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    db_path = database_path(repo_root, args.database)
    try:
        if args.command == "rebuild":
            payload = rebuild(
                repo_root, db_path, args.chunk_bytes, trigram=not args.no_trigram
            )
        elif args.command == "status":
            payload = health(repo_root, db_path)
        elif args.command == "doctor":
            payload = health(repo_root, db_path, deep=True)
        elif args.command == "search":
            payload = search(
                repo_root,
                db_path,
                args.query,
                bounded(args.limit, "limit", MAX_RESULTS),
            )
        elif args.command == "search-batch":
            payload = search_batch(
                repo_root,
                db_path,
                args.query,
                bounded(args.limit, "limit", MAX_RESULTS),
            )
        else:
            payload = traverse(
                repo_root,
                db_path,
                args.start,
                bounded(args.hops, "hops", MAX_HOPS),
                bounded(args.limit, "limit", MAX_PAGES),
            )
    except (OSError, sqlite3.Error, RetrievalError) as exc:
        print(f"repo docs retrieval error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return (
        1
        if args.command == "doctor" and payload["state"] in {"stale", "malformed"}
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
