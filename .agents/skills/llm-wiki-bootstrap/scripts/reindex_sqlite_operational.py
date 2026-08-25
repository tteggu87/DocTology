#!/usr/bin/env python3
"""Rebuild the disposable SQLite retrieval index from Markdown wiki pages."""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import re
import sqlite3
import struct
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = (
    ROOT / "templates" / "llm-wiki-three-layer" / "sqlite_operational.schema.sql"
)
DEFAULT_CHUNK_THRESHOLD = 64 * 1024
SCHEMA_VERSION = "wiki-heading-index-v7"
FINITE_ATTESTATION_VERSION = "finite-nonzero-v2"
PAGE_TYPE_BY_DIR = {
    "concepts": "concept",
    "entities": "entity",
    "people": "person",
    "projects": "project",
    "timelines": "timeline",
    "analyses": "analysis",
    "sources": "source",
}
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
SQLITE_HEADER = b"SQLite format 3\x00"
EMBEDDING_COLUMNS = {
    "chunk_id",
    "chunk_hash",
    "model_identity",
    "tokenizer_identity",
    "preprocessing_identity",
    "dimensions",
    "vector",
    "vector_fingerprint",
    "created_at",
}


class RebuildError(RuntimeError):
    """Raised when a rebuild cannot safely publish its derived index."""


@dataclass(frozen=True)
class Page:
    id: str
    path: str
    title: str
    page_type: str
    updated_at: str
    checksum: str
    text: str
    byte_size: int


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    chunk_index: int
    heading_path: str
    line_start: int
    line_end: int
    byte_start: int
    byte_end: int
    content: str
    content_hash: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild state/wiki_index.sqlite from Markdown."
    )
    parser.add_argument(
        "--repo-root", required=True, help="Target wiki repository root."
    )
    parser.add_argument(
        "--chunk-threshold",
        type=int,
        default=DEFAULT_CHUNK_THRESHOLD,
        help="Maximum UTF-8 bytes per chunk (default: 65536).",
    )
    return parser.parse_args()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def split_frontmatter(text: str) -> tuple[list[str], str]:
    if not text.startswith("---\n"):
        return [], text
    lines = text.splitlines()
    try:
        end = lines[1:].index("---") + 1
    except ValueError:
        return [], text
    return lines[1:end], "\n".join(lines[end + 1 :])


def frontmatter_value(text: str, key: str) -> str | None:
    for line in split_frontmatter(text)[0]:
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip('"')
    return None


def frontmatter_list(text: str, key: str) -> list[str]:
    lines = split_frontmatter(text)[0]
    values: list[str] = []
    collecting = False
    for line in lines:
        if collecting and line.strip().startswith("- "):
            values.append(line.strip()[2:].strip().strip('"'))
            continue
        if collecting and line.strip():
            break
        if line.startswith(f"{key}:"):
            collecting = True
            inline = line.split(":", 1)[1].strip().strip("[]")
            values.extend(
                item.strip().strip('"') for item in inline.split(",") if item.strip()
            )
    return values


def extract_title(path: Path, text: str) -> str:
    return next(
        (line[2:].strip() for line in text.splitlines() if line.startswith("# ")),
        path.stem.replace("-", " ").title(),
    )


def fallback_page_id(relative_wiki_path: Path) -> str:
    original = relative_wiki_path.with_suffix("").as_posix()
    relative = unicodedata.normalize("NFKC", original).casefold()
    normalized = re.sub(
        r"[^\w]+",
        "-",
        relative,
    ).strip("-")
    normalized = normalized.replace("_", "-") or "wiki-page"
    return f"page-{normalized}-{sha256(original.encode('utf-8'))[:12]}"


def page_records(repo_root: Path) -> list[Page]:
    wiki_dir = repo_root / "wiki"
    records: list[Page] = []
    if not wiki_dir.exists():
        return records
    for path in sorted(wiki_dir.rglob("*.md")):
        rel = path.relative_to(wiki_dir)
        if (
            not rel.parts
            or rel.parts[0] == "_meta"
            or rel.parts[0] not in PAGE_TYPE_BY_DIR
        ):
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        page_id = frontmatter_value(text, "page_id") or fallback_page_id(rel)
        records.append(
            Page(
                page_id,
                path.relative_to(repo_root).as_posix(),
                frontmatter_value(text, "title") or extract_title(path, text),
                frontmatter_value(text, "page_type")
                or frontmatter_value(text, "type")
                or PAGE_TYPE_BY_DIR[rel.parts[0]],
                frontmatter_value(text, "updated_at")
                or frontmatter_value(text, "updated")
                or "",
                sha256(raw),
                text,
                len(raw),
            )
        )
    return records


def utf8_offsets(text: str) -> list[int]:
    offsets = [0]
    total = 0
    for character in text:
        total += len(character.encode("utf-8"))
        offsets.append(total)
    return offsets


def newline_offsets(text: str) -> list[int]:
    offsets = [0]
    total = 0
    for character in text:
        total += character == "\n"
        offsets.append(total)
    return offsets


def section_spans(text: str) -> list[tuple[int, int, str]]:
    headings: list[tuple[int, str]] = []
    stack: list[str] = []
    for match in re.finditer(r"^#{1,6}[ \t]+.+?$", text, re.MULTILINE):
        parsed = HEADING_RE.match(match.group(0))
        if parsed:
            level, title = len(parsed.group(1)), parsed.group(2).strip()
            stack = stack[: level - 1]
            stack.append(title)
            headings.append((match.start(), " > ".join(stack)))
    if not headings:
        return [(0, len(text), "")]
    spans = [(0, headings[0][0], "")] if headings[0][0] else []
    spans.extend(
        (
            start,
            headings[index + 1][0] if index + 1 < len(headings) else len(text),
            heading,
        )
        for index, (start, heading) in enumerate(headings)
    )
    return spans


def split_oversized(
    text: str,
    start: int,
    end: int,
    threshold: int,
    byte_offsets: list[int],
) -> list[tuple[int, int]]:
    """Prefer paragraph boundaries, then split an indivisible paragraph safely."""
    boundaries = [
        start + match.end() for match in re.finditer(r"\n[ \t]*\n", text[start:end])
    ] + [end]
    spans: list[tuple[int, int]] = []
    group_start = start
    last = start
    for boundary in boundaries:
        if byte_offsets[boundary] - byte_offsets[group_start] <= threshold:
            last = boundary
            continue
        if last > group_start:
            spans.append((group_start, last))
            group_start = last
        while byte_offsets[boundary] - byte_offsets[group_start] > threshold:
            cut = group_start
            while (
                cut < boundary
                and byte_offsets[cut + 1] - byte_offsets[group_start] <= threshold
            ):
                cut += 1
            if cut == group_start:
                raise ValueError("chunk threshold is smaller than one UTF-8 character")
            spans.append((group_start, cut))
            group_start = cut
        last = boundary
    if group_start < end:
        spans.append((group_start, end))
    return spans


def chunks_for_page(page: Page, threshold: int) -> list[Chunk]:
    if threshold <= 0:
        raise ValueError("chunk threshold must be positive")
    byte_offsets = utf8_offsets(page.text)
    newline_counts = newline_offsets(page.text)
    spans = [(0, len(page.text), "")]
    if page.byte_size > threshold:
        spans = []
        for start, end, heading in section_spans(page.text):
            split = (
                [(start, end)]
                if byte_offsets[end] - byte_offsets[start] <= threshold
                else split_oversized(page.text, start, end, threshold, byte_offsets)
            )
            spans.extend((a, b, heading) for a, b in split if a < b)
    chunks: list[Chunk] = []
    for index, (start, end, heading) in enumerate(spans):
        content = page.text[start:end]
        content_hash = sha256(content.encode("utf-8"))
        line_start = newline_counts[start] + 1
        line_end = max(
            line_start,
            newline_counts[end] + (0 if end and page.text[end - 1] == "\n" else 1),
        )
        chunks.append(
            Chunk(
                f"chunk-{sha256(f'{page.id}:{index}:{content_hash}'.encode())[:24]}",
                f"document-{page.id}",
                index,
                heading,
                line_start,
                line_end,
                byte_offsets[start],
                byte_offsets[end],
                content,
                content_hash,
            )
        )
    return chunks


def link_records(pages: list[Page]) -> list[tuple[str, str | None, str, str, str]]:
    candidates: dict[str, list[str]] = {}
    for page in pages:
        relative_wiki_path = (
            Path(page.path).relative_to("wiki").with_suffix("").as_posix()
        )
        for key in {
            Path(page.path).stem.casefold(),
            relative_wiki_path.casefold(),
            page.title.casefold(),
        }:
            candidates.setdefault(key, []).append(page.id)
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for page in pages:
        for link in WIKILINK_RE.findall(split_frontmatter(page.text)[1]):
            matches = candidates.get(link.strip().casefold(), [])
            target = matches[0] if len(matches) == 1 else None
            rows.append(
                (
                    page.id,
                    target,
                    link.strip(),
                    "resolved" if target else "unresolved",
                    now,
                )
            )
    return rows


def source_and_tag_records(
    pages: list[Page],
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str]]]:
    sources: list[tuple[str, str, str]] = []
    tags: list[tuple[str, str]] = []
    for page in pages:
        for value in frontmatter_list(page.text, "sources"):
            match = WIKILINK_RE.search(value)
            if match:
                sources.append((page.id, match.group(1), "primary"))
        tags.extend((page.id, tag) for tag in frontmatter_list(page.text, "tags"))
    return sources, tags


def source_stat_fingerprint(repo_root: Path) -> str:
    rows = []
    wiki_dir = repo_root / "wiki"
    for path in sorted(wiki_dir.rglob("*.md")):
        rel = path.relative_to(wiki_dir)
        if (
            not path.is_file()
            or not rel.parts
            or rel.parts[0] == "_meta"
            or rel.parts[0] not in PAGE_TYPE_BY_DIR
        ):
            continue
        stat = path.stat()
        rows.append(
            f"{path.relative_to(repo_root).as_posix()}\0{stat.st_size}\0{stat.st_mtime_ns}"
        )
    return sha256("\n".join(rows).encode())


def prepare_existing_index_for_replace(db_path: Path) -> None:
    """Quiesce an existing WAL database or fail before publishing a replacement."""
    if not db_path.is_file():
        return
    with db_path.open("rb") as handle:
        if handle.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
            # Disposable non-SQLite state cannot be busy. A validated temporary
            # index may replace it without opening it as a live database.
            return
    connection = sqlite3.connect(db_path, timeout=0, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 0")
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
        if journal_mode.casefold() == "wal":
            busy, log_frames, checkpointed = connection.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)"
            ).fetchone()
            if busy or log_frames != checkpointed:
                raise sqlite3.OperationalError(
                    "active WAL state is busy; refusing to publish rebuilt index"
                )
            next_mode = str(
                connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
            )
            if next_mode.casefold() != "delete":
                raise sqlite3.OperationalError(
                    "could not safely exit WAL mode before index replacement"
                )
        connection.execute("BEGIN EXCLUSIVE")
        connection.execute("COMMIT")
    except sqlite3.OperationalError as exc:
        raise sqlite3.OperationalError(
            f"existing derived index is busy; prior index was not replaced: {exc}"
        ) from exc
    finally:
        connection.close()


def carry_forward_embeddings(
    connection: sqlite3.Connection, existing_path: Path
) -> int:
    """Copy compatible current vectors from the prior disposable index."""
    if not existing_path.is_file():
        return 0
    with existing_path.open("rb") as handle:
        if handle.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
            return 0
    source = sqlite3.connect(f"file:{existing_path}?mode=ro", uri=True, timeout=0)
    source.row_factory = sqlite3.Row
    try:
        columns = {
            row[1] for row in source.execute("PRAGMA table_info(chunk_embeddings)")
        }
        if columns != EMBEDDING_COLUMNS:
            return 0
        rows = source.execute(
            """
            SELECT chunk_id, chunk_hash, model_identity, tokenizer_identity,
                   preprocessing_identity, dimensions, vector,
                   vector_fingerprint, created_at
            FROM chunk_embeddings
            ORDER BY model_identity, tokenizer_identity,
                     preprocessing_identity, chunk_id
            """
        ).fetchall()
    finally:
        source.close()

    current_chunks = dict(connection.execute("SELECT id, content_hash FROM chunks"))
    cohort_dimensions: dict[tuple[str, str, str], set[int]] = {}
    candidates: list[tuple[object, ...]] = []
    for row in rows:
        identity = (
            str(row["model_identity"]),
            str(row["tokenizer_identity"]),
            str(row["preprocessing_identity"]),
        )
        try:
            dimensions = int(row["dimensions"])
            vector = bytes(row["vector"])
        except (TypeError, ValueError):
            continue
        if (
            all(identity)
            and dimensions > 0
            and current_chunks.get(row["chunk_id"]) == row["chunk_hash"]
        ):
            cohort_dimensions.setdefault(identity, set()).add(dimensions)
        if (
            not all(identity)
            or dimensions <= 0
            or current_chunks.get(row["chunk_id"]) != row["chunk_hash"]
            or len(vector) != dimensions * 4
            or sha256(vector) != row["vector_fingerprint"]
            or not usable_vector_payload(vector, dimensions)
        ):
            continue
        candidates.append(
            (
                row["chunk_id"],
                row["chunk_hash"],
                *identity,
                dimensions,
                vector,
                row["vector_fingerprint"],
                row["created_at"],
            )
        )

    compatible = [
        row
        for row in candidates
        if len(cohort_dimensions[(str(row[2]), str(row[3]), str(row[4]))]) == 1
    ]
    connection.executemany(
        """
        INSERT INTO chunk_embeddings(
          chunk_id, chunk_hash, model_identity, tokenizer_identity,
          preprocessing_identity, dimensions, vector, vector_fingerprint, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        compatible,
    )
    return len(compatible)


def semantic_cohort_fingerprint(connection: sqlite3.Connection) -> str:
    """Hash semantic row metadata without materializing vector BLOBs."""
    digest = hashlib.sha256()
    found = False
    for row in connection.execute(
        """
        SELECT chunk_id, chunk_hash, model_identity, tokenizer_identity,
               preprocessing_identity, dimensions, vector_fingerprint
        FROM chunk_embeddings
        ORDER BY model_identity, tokenizer_identity, preprocessing_identity,
                 chunk_id
        """
    ):
        found = True
        digest.update("\0".join(str(value) for value in row).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest() if found else "none"


def semantic_finite_attestation(connection: sqlite3.Connection) -> str:
    """Return the bounded metadata token written after full vector validation."""
    return f"{FINITE_ATTESTATION_VERSION}:{semantic_cohort_fingerprint(connection)}"


def usable_vector_payload(payload: bytes, dimensions: int) -> bool:
    """Accept only structurally valid, finite vectors with non-zero magnitude."""
    if dimensions <= 0 or len(payload) != dimensions * 4:
        return False
    try:
        values = struct.unpack(f"<{dimensions}f", payload)
    except struct.error:
        return False
    if any(not math.isfinite(value) for value in values):
        return False
    magnitude = math.hypot(*values)
    return math.isfinite(magnitude) and magnitude > 0


def attest_semantic_vectors(connection: sqlite3.Connection) -> str:
    """Validate every stored vector before minting a lightweight readiness token."""
    for dimensions, payload, fingerprint in connection.execute(
        "SELECT dimensions, vector, vector_fingerprint FROM chunk_embeddings"
    ):
        try:
            dimensions = int(dimensions)
            payload = bytes(payload)
        except (TypeError, ValueError):
            raise RebuildError("semantic vector attestation found malformed data") from None
        if sha256(payload) != fingerprint or not usable_vector_payload(
            payload, dimensions
        ):
            raise RebuildError(
                "semantic vector attestation requires finite non-zero vectors"
            )
    return semantic_finite_attestation(connection)


def rebuild(repo_root: Path, threshold: int) -> tuple[int, int, Path]:
    if threshold <= 0:
        raise ValueError("chunk threshold must be positive")
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    stat_fingerprint = source_stat_fingerprint(repo_root)
    pages = page_records(repo_root)
    chunks = [chunk for page in pages for chunk in chunks_for_page(page, threshold)]
    if stat_fingerprint != source_stat_fingerprint(repo_root):
        raise RebuildError("Markdown changed during rebuild; refusing to publish index")
    db_path = repo_root / "state" / "wiki_index.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".wiki_index.", suffix=".sqlite.tmp", dir=db_path.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    temporary_path.unlink()
    try:
        connection = sqlite3.connect(temporary_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(schema)
            connection.executemany(
                "INSERT INTO pages VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (p.id, p.path, p.title, p.page_type, p.updated_at, p.checksum)
                    for p in pages
                ],
            )
            connection.executemany(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (f"document-{p.id}", p.id, p.path, p.title, p.checksum, p.byte_size)
                    for p in pages
                ],
            )
            connection.executemany(
                "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        c.id,
                        c.document_id,
                        c.chunk_index,
                        c.heading_path,
                        c.line_start,
                        c.line_end,
                        c.byte_start,
                        c.byte_end,
                        c.content,
                        c.content_hash,
                    )
                    for c in chunks
                ],
            )
            titles = {f"document-{p.id}": (p.title, p.path) for p in pages}
            connection.executemany(
                "INSERT INTO chunk_fts VALUES (?, ?, ?, ?, ?)",
                [
                    (c.id, *titles[c.document_id], c.heading_path, c.content)
                    for c in chunks
                ],
            )
            connection.executemany(
                "INSERT INTO page_links VALUES (?, ?, ?, ?, ?)", link_records(pages)
            )
            sources, tags = source_and_tag_records(pages)
            connection.executemany(
                "INSERT OR IGNORE INTO page_sources VALUES (?, ?, ?)", sources
            )
            connection.executemany("INSERT OR IGNORE INTO tags VALUES (?, ?)", tags)
            carry_forward_embeddings(connection, db_path)
            corpus = "\n".join(
                [
                    SCHEMA_VERSION,
                    str(threshold),
                    *(f"{p.path}\0{p.checksum}" for p in pages),
                ]
            )
            connection.executemany(
                "INSERT INTO index_metadata VALUES (?, ?)",
                [
                    ("schema_version", SCHEMA_VERSION),
                    ("schema_fingerprint", sha256(schema.encode())),
                    ("corpus_fingerprint", sha256(corpus.encode())),
                    ("source_stat_fingerprint", stat_fingerprint),
                    (
                        "semantic_cohort_fingerprint",
                        semantic_cohort_fingerprint(connection),
                    ),
                    (
                        "semantic_finite_attestation",
                        attest_semantic_vectors(connection),
                    ),
                    ("chunk_threshold_bytes", str(threshold)),
                    ("truth_source", "markdown"),
                    ("rebuildable", "true"),
                ],
            )
            connection.commit()
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("temporary index failed SQLite quick_check")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise sqlite3.DatabaseError("temporary index failed foreign_key_check")
            counts = {
                "pages": connection.execute("SELECT count(*) FROM pages").fetchone()[0],
                "documents": connection.execute(
                    "SELECT count(*) FROM documents"
                ).fetchone()[0],
                "chunks": connection.execute("SELECT count(*) FROM chunks").fetchone()[
                    0
                ],
                "chunk_fts": connection.execute(
                    "SELECT count(*) FROM chunk_fts"
                ).fetchone()[0],
            }
            if counts != {
                "pages": len(pages),
                "documents": len(pages),
                "chunks": len(chunks),
                "chunk_fts": len(chunks),
            }:
                raise sqlite3.DatabaseError(f"temporary index is incomplete: {counts}")
            journal_mode = str(
                connection.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
            )
            if journal_mode.casefold() != "delete":
                raise sqlite3.DatabaseError(
                    "temporary index could not exit WAL mode before publication"
                )
        finally:
            connection.close()
        prepare_existing_index_for_replace(db_path)
        os.replace(temporary_path, db_path)
        Path(f"{db_path}-wal").unlink(missing_ok=True)
        Path(f"{db_path}-shm").unlink(missing_ok=True)
    finally:
        for path in (
            temporary_path,
            Path(f"{temporary_path}-wal"),
            Path(f"{temporary_path}-shm"),
        ):
            path.unlink(missing_ok=True)
    return len(pages), len(chunks), db_path


def main() -> int:
    args = parse_args()
    try:
        page_count, chunk_count, db_path = rebuild(
            Path(args.repo_root).resolve(), args.chunk_threshold
        )
    except (RebuildError, OSError, sqlite3.Error, ValueError) as exc:
        print(f"wiki index rebuild error: {exc}", file=sys.stderr)
        return 2
    print(f"Rebuilt derived SQLite index: {db_path}")
    print(f"Indexed pages: {page_count}; chunks: {chunk_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
