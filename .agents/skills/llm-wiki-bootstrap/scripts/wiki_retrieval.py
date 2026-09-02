#!/usr/bin/env python3
"""Query the disposable Markdown-derived SQLite wiki index."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import sqlite3
import struct
import sys
from collections import Counter, deque
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Sequence

import reindex_sqlite_operational as indexer


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_RESULT_LIMIT = 10
DEFAULT_NEIGHBOR_LIMIT = 5
DEFAULT_GRAPH_CAP = 50
MAX_GRAPH_CAP = 100
DEFAULT_MAX_SEQUENCE_LENGTH = 512
DEFAULT_EMBED_BATCH_SIZE = 8
DEFAULT_OUTPUT_INDEX = 0
DEFAULT_POOLING = "attention_mask_mean"
DEFAULT_PREPROCESSING_IDENTITY = (
    "preprocess:max_sequence_length=unspecified;output_index=0;pooling=provider"
)
MAX_SEQUENCE_LENGTH = 8192
MAX_EMBED_BATCH_SIZE = 128
REQUIRED_TABLES = {
    "pages",
    "documents",
    "structure_nodes",
    "chunks",
    "chunk_fts",
    "chunk_embeddings",
    "page_links",
    "page_sources",
    "tags",
    "index_metadata",
}
REQUIRED_METADATA = {
    "schema_version",
    "schema_fingerprint",
    "corpus_fingerprint",
    "source_stat_fingerprint",
    "semantic_cohort_fingerprint",
    "semantic_finite_attestation",
    "chunk_threshold_bytes",
    "structure_schema_version",
    "truth_source",
    "rebuildable",
}
SQLITE_HEADER = b"SQLite format 3\x00"


class IndexStateError(RuntimeError):
    """Raised when derived SQLite state cannot safely serve a query."""


class SemanticLaneUnavailable(RuntimeError):
    """Raised when optional local semantic retrieval cannot safely run."""


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


class OnnxSemanticProvider:
    """Lazy optional ONNX/tokenizer provider; imports happen only on embed()."""

    def __init__(
        self,
        model_path: Path,
        tokenizer_path: Path,
        max_sequence_length: int = DEFAULT_MAX_SEQUENCE_LENGTH,
        batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
        output_index: int = DEFAULT_OUTPUT_INDEX,
        pooling: str = DEFAULT_POOLING,
    ) -> None:
        if not 1 <= max_sequence_length <= MAX_SEQUENCE_LENGTH:
            raise SemanticLaneUnavailable(
                f"maximum sequence length must be between 1 and {MAX_SEQUENCE_LENGTH}"
            )
        if not 1 <= batch_size <= MAX_EMBED_BATCH_SIZE:
            raise SemanticLaneUnavailable(
                f"embedding batch size must be between 1 and {MAX_EMBED_BATCH_SIZE}"
            )
        if output_index < 0:
            raise SemanticLaneUnavailable("ONNX output index must be non-negative")
        if pooling not in ("attention_mask_mean", "cls"):
            raise SemanticLaneUnavailable("pooling must be attention_mask_mean or cls")
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self.max_sequence_length = max_sequence_length
        self.batch_size = batch_size
        self.output_index = output_index
        self.pooling = pooling
        self._session = None
        self._tokenizer = None
        self._numpy = None

    @staticmethod
    def _file_identity(kind: str, path: Path) -> str:
        if not path.is_file():
            raise SemanticLaneUnavailable(f"{kind} file is missing: {path}")
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise SemanticLaneUnavailable(
                f"cannot read {kind} file {path}: {exc}"
            ) from exc
        return f"{kind}:{path.name}:{digest}"

    @property
    def model_identity(self) -> str:
        return self._file_identity("onnx", self.model_path)

    @property
    def tokenizer_identity(self) -> str:
        return self._file_identity("tokenizer", self.tokenizer_path)

    @property
    def preprocessing_identity(self) -> str:
        return (
            f"preprocess:max_sequence_length={self.max_sequence_length};"
            f"output_index={self.output_index};pooling={self.pooling}"
        )

    def _load(self) -> None:
        if self._session is not None:
            return
        self.model_identity
        self.tokenizer_identity
        try:
            import numpy as np
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except Exception as exc:
            raise SemanticLaneUnavailable(
                "optional semantic dependencies are unavailable; install numpy, "
                "onnxruntime, and tokenizers"
            ) from exc
        try:
            self._session = ort.InferenceSession(
                str(self.model_path), providers=["CPUExecutionProvider"]
            )
            self._tokenizer = Tokenizer.from_file(str(self.tokenizer_path))
            self._tokenizer.enable_truncation(max_length=self.max_sequence_length)
            self._numpy = np
        except Exception as exc:
            raise SemanticLaneUnavailable(
                f"cannot load semantic artifacts: {exc}"
            ) from exc

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self._load()
        assert self._session is not None and self._tokenizer is not None
        assert self._numpy is not None
        results: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            results.extend(
                self._embed_batch(list(texts[start : start + self.batch_size]))
            )
        return results

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        assert self._session is not None and self._tokenizer is not None
        assert self._numpy is not None
        np = self._numpy
        try:
            encodings = self._tokenizer.encode_batch(texts)
        except Exception as exc:
            raise SemanticLaneUnavailable(f"tokenizer failed: {exc}") from exc
        try:
            clipped_ids = [
                list(item.ids[: self.max_sequence_length]) for item in encodings
            ]
            width = max((len(ids) for ids in clipped_ids), default=0)
            if width == 0:
                raise SemanticLaneUnavailable("tokenizer produced no input tokens")
            input_rows, mask_rows, type_rows = [], [], []
            for encoding, ids in zip(encodings, clipped_ids, strict=True):
                attention = encoding.attention_mask or []
                token_types = encoding.type_ids or []
                mask = list(attention[: len(ids)]) or [1] * len(ids)
                types = list(token_types[: len(ids)]) or [0] * len(ids)
                padding = width - len(ids)
                input_rows.append(ids + [0] * padding)
                mask_rows.append(mask + [0] * padding)
                type_rows.append(types + [0] * padding)
            available = {
                "input_ids": np.asarray(input_rows, dtype=np.int64),
                "attention_mask": np.asarray(mask_rows, dtype=np.int64),
                "token_type_ids": np.asarray(type_rows, dtype=np.int64),
            }
        except SemanticLaneUnavailable:
            raise
        except Exception as exc:
            raise SemanticLaneUnavailable(
                f"semantic preprocessing failed: {exc}"
            ) from exc
        try:
            inputs = self._session.get_inputs()
            feed = {
                item.name: available[item.name]
                for item in inputs
                if item.name in available
            }
        except Exception as exc:
            raise SemanticLaneUnavailable(
                f"ONNX input discovery failed: {exc}"
            ) from exc
        if "input_ids" not in feed:
            raise SemanticLaneUnavailable("ONNX model does not expose input_ids")
        try:
            outputs = self._session.run(None, feed)
        except Exception as exc:
            raise SemanticLaneUnavailable(f"ONNX inference failed: {exc}") from exc
        try:
            output = outputs[self.output_index]
            values = output.tolist()
            if output.ndim == 3:
                pooled = []
                for tokens, mask in zip(values, mask_rows, strict=True):
                    if self.pooling == "cls":
                        pooled.append(tokens[0])
                        continue
                    count = max(sum(mask), 1)
                    pooled.append(
                        [
                            sum(
                                token[index] * weight
                                for token, weight in zip(tokens, mask, strict=True)
                            )
                            / count
                            for index in range(len(tokens[0]))
                        ]
                    )
                values = pooled
            if output.ndim != 2 and not (output.ndim == 3 and values):
                raise ValueError(f"unexpected ONNX output shape: {output.shape}")
            if len(values) != len(texts):
                raise ValueError(f"unexpected ONNX output shape: {output.shape}")
            return [[float(value) for value in row] for row in values]
        except Exception as exc:
            raise SemanticLaneUnavailable(
                f"ONNX output processing failed: {exc}"
            ) from exc


def emit(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def validate_limit(value: int, label: str) -> int:
    if not 1 <= value <= MAX_GRAPH_CAP:
        raise IndexStateError(f"{label} must be between 1 and {MAX_GRAPH_CAP}")
    return value


def validate_cap(value: int) -> int:
    return validate_limit(value, "graph cap")


def database_path(repo_root: Path) -> Path:
    return repo_root / "state" / "wiki_index.sqlite"


def open_index(repo_root: Path) -> sqlite3.Connection:
    path = database_path(repo_root)
    if not path.is_file():
        raise IndexStateError(
            f"derived SQLite index is missing: {path}; run the rebuild command"
        )
    try:
        with path.open("rb") as handle:
            if handle.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
                raise IndexStateError("malformed derived SQLite index header")
    except OSError as exc:
        raise IndexStateError(f"cannot read derived SQLite index: {exc}") from exc
    connection = None
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection
    except sqlite3.Error as exc:
        if connection is not None:
            connection.close()
        raise IndexStateError(f"cannot open derived SQLite index: {exc}") from exc


def open_writable_index(repo_root: Path) -> sqlite3.Connection:
    path = database_path(repo_root)
    if not path.is_file():
        raise IndexStateError(
            f"derived SQLite index is missing: {path}; run the rebuild command"
        )
    connection = None
    try:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    except sqlite3.Error as exc:
        if connection is not None:
            connection.close()
        raise IndexStateError(f"cannot open derived SQLite index: {exc}") from exc


def metadata(
    connection: sqlite3.Connection, *, integrity_check: bool = False
) -> dict[str, str]:
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            raise IndexStateError(
                f"malformed derived SQLite index; missing: {', '.join(missing)}"
            )
        if integrity_check:
            quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
            if quick_check != "ok":
                raise IndexStateError(f"malformed derived SQLite index: {quick_check}")
        values = dict(connection.execute("SELECT key, value FROM index_metadata"))
        missing_metadata = sorted(REQUIRED_METADATA - values.keys())
        if missing_metadata:
            raise IndexStateError(
                "malformed derived SQLite metadata; missing: "
                + ", ".join(missing_metadata)
            )
        return values
    except sqlite3.Error as exc:
        raise IndexStateError(f"malformed derived SQLite index: {exc}") from exc


def expected_fingerprints(repo_root: Path, threshold: int) -> tuple[str, str]:
    schema = indexer.SCHEMA_PATH.read_text(encoding="utf-8")
    pages = indexer.page_records(repo_root)
    corpus = indexer.corpus_fingerprint(
        [indexer.page_metadata(page) for page in pages], threshold
    )
    return indexer.sha256(schema.encode()), corpus


def semantic_cohort_state(
    connection: sqlite3.Connection, chunk_count: int
) -> tuple[str, int, list[str]]:
    rows = connection.execute(
        """
        SELECT e.vector, e.vector_fingerprint, e.chunk_hash, c.content_hash,
               e.model_identity, e.tokenizer_identity, e.preprocessing_identity,
               e.dimensions
        FROM chunk_embeddings e
        LEFT JOIN chunks c ON c.id = e.chunk_id
        """
    ).fetchall()
    if not rows:
        return "unavailable", 0, []
    reasons: list[str] = []
    cohorts: dict[tuple[str, str, str], int] = {}
    valid_rows = 0
    for row in rows:
        identity = (
            row["model_identity"],
            row["tokenizer_identity"],
            row["preprocessing_identity"],
        )
        cohorts[identity] = cohorts.get(identity, 0) + 1
        payload = bytes(row["vector"])
        if (
            row["content_hash"] != row["chunk_hash"]
            or len(payload) != row["dimensions"] * 4
        ):
            reasons.append("vector_rows")
            continue
        if hashlib.sha256(payload).hexdigest() != row["vector_fingerprint"]:
            reasons.append("vector_fingerprints")
            continue
        try:
            unpack_vector(payload, int(row["dimensions"]))
        except (SemanticLaneUnavailable, TypeError, ValueError):
            reasons.append("vector_values")
            continue
        valid_rows += 1
    if any(count != chunk_count for count in cohorts.values()):
        reasons.append("vector_rows")
    reasons = list(dict.fromkeys(reasons))
    return ("unavailable" if reasons else "ready"), valid_rows, reasons


def lightweight_semantic_cohort_state(
    connection: sqlite3.Connection, chunk_count: int
) -> tuple[str, int, list[str]]:
    """Validate cohort metadata and counts without materializing vector BLOBs."""
    rows = connection.execute(
        """
        SELECT e.model_identity, e.tokenizer_identity, e.preprocessing_identity,
               count(*) row_count,
               sum(CASE WHEN c.content_hash = e.chunk_hash THEN 1 ELSE 0 END) current_rows,
               min(e.dimensions) min_dimensions, max(e.dimensions) max_dimensions,
               sum(CASE WHEN length(e.vector_fingerprint) = 64 THEN 1 ELSE 0 END)
                   fingerprint_metadata_rows
        FROM chunk_embeddings e
        LEFT JOIN chunks c ON c.id = e.chunk_id
        GROUP BY e.model_identity, e.tokenizer_identity, e.preprocessing_identity
        """
    ).fetchall()
    if not rows:
        return "unavailable", 0, []
    reasons: list[str] = []
    current_rows = 0
    for row in rows:
        row_count = int(row["row_count"])
        cohort_current = int(row["current_rows"] or 0)
        current_rows += cohort_current
        if row_count != chunk_count or cohort_current != chunk_count:
            reasons.append("vector_rows")
        if not row["min_dimensions"] or row["min_dimensions"] != row["max_dimensions"]:
            reasons.append("vector_metadata")
        if int(row["fingerprint_metadata_rows"] or 0) != row_count:
            reasons.append("vector_fingerprints")
    reasons = list(dict.fromkeys(reasons))
    return ("unavailable" if reasons else "ready"), current_rows, reasons


def lightweight_health(
    repo_root: Path, connection: sqlite3.Connection | None = None
) -> dict[str, object]:
    path = database_path(repo_root)
    owns_connection = connection is None
    if connection is None:
        connection = open_index(repo_root)
    try:
        values = metadata(connection)
        try:
            threshold = int(values["chunk_threshold_bytes"])
            if threshold <= 0:
                raise ValueError("chunk threshold must be positive")
            schema = indexer.SCHEMA_PATH.read_text(encoding="utf-8")
            stale_reasons = []
            if values.get("schema_version") != indexer.SCHEMA_VERSION:
                stale_reasons.append("schema_version")
            if values.get("schema_fingerprint") != indexer.sha256(schema.encode()):
                stale_reasons.append("schema_fingerprint")
            if values.get("source_stat_fingerprint") != indexer.source_stat_fingerprint(
                repo_root
            ):
                stale_reasons.append("source_stat_fingerprint")
            if values.get("truth_source") != "markdown":
                stale_reasons.append("truth_source")
            if values.get("rebuildable") != "true":
                stale_reasons.append("rebuildable")
            if values.get("structure_schema_version") != indexer.STRUCTURE_SCHEMA_VERSION:
                stale_reasons.append("structure_schema_version")
            page_count = connection.execute("SELECT count(*) FROM pages").fetchone()[0]
            chunk_count = connection.execute("SELECT count(*) FROM chunks").fetchone()[
                0
            ]
            semantic_lane, semantic_vectors, semantic_reasons = (
                lightweight_semantic_cohort_state(connection, chunk_count)
            )
            if values.get(
                "semantic_cohort_fingerprint"
            ) != indexer.semantic_cohort_fingerprint(connection):
                semantic_reasons.append("semantic_cohort_fingerprint")
                semantic_lane = "unavailable"
            if values.get(
                "semantic_finite_attestation"
            ) != indexer.semantic_finite_attestation(connection):
                semantic_reasons.append("vector_values")
                semantic_lane = "unavailable"
        except (KeyError, TypeError, ValueError, sqlite3.Error) as exc:
            raise IndexStateError(f"malformed derived SQLite metadata: {exc}") from exc
    finally:
        if owns_connection:
            connection.close()
    return {
        "index": str(path),
        "state": "stale" if stale_reasons else "ready",
        "stale_reasons": stale_reasons,
        "pages": page_count,
        "chunks": chunk_count,
        "truth_source": values.get("truth_source"),
        "rebuildable": values.get("rebuildable") == "true",
        "corpus_fingerprint": values.get("corpus_fingerprint"),
        "semantic_lane": semantic_lane,
        "semantic_vectors": semantic_vectors,
        "semantic_reasons": semantic_reasons,
        "semantic_cohort_fingerprint": values.get("semantic_cohort_fingerprint"),
        "readiness_check": "metadata_and_markdown_path_stat",
    }


def health(repo_root: Path) -> dict[str, object]:
    path = database_path(repo_root)
    with closing(open_index(repo_root)) as connection:
        values = metadata(connection, integrity_check=True)
        try:
            threshold = int(values["chunk_threshold_bytes"])
            schema_expected, corpus_expected = expected_fingerprints(
                repo_root, threshold
            )
            stale_reasons = []
            if values.get("schema_version") != indexer.SCHEMA_VERSION:
                stale_reasons.append("schema_version")
            if values.get("schema_fingerprint") != schema_expected:
                stale_reasons.append("schema_fingerprint")
            if values.get("corpus_fingerprint") != corpus_expected:
                stale_reasons.append("corpus_fingerprint")
            if values.get("truth_source") != "markdown":
                stale_reasons.append("truth_source")
            if values.get("rebuildable") != "true":
                stale_reasons.append("rebuildable")
            if values.get("structure_schema_version") != indexer.STRUCTURE_SCHEMA_VERSION:
                stale_reasons.append("structure_schema_version")
            expected_pages = indexer.page_records(repo_root)
            expected_nodes_by_document = {
                f"document-{page.id}": indexer.structure_nodes_for_page(page)
                for page in expected_pages
            }
            expected_chunks = []
            for page in expected_pages:
                nodes = expected_nodes_by_document[f"document-{page.id}"]
                expected_chunks.extend(
                    (chunk, indexer.structure_owner_node_id(nodes, chunk, page.path))
                    for chunk in indexer.chunks_for_page(page, threshold)
                )
            expected_page_rows = sorted(
                (
                    page.id,
                    page.path,
                    page.title,
                    page.page_type,
                    page.updated_at,
                    page.checksum,
                )
                for page in expected_pages
            )
            page_rows = sorted(
                tuple(row)
                for row in connection.execute(
                    "SELECT id, path, title, page_type, updated_at, checksum FROM pages"
                )
            )
            expected_document_rows = sorted(
                (
                    f"document-{page.id}",
                    page.id,
                    page.path,
                    page.title,
                    page.checksum,
                    page.byte_size,
                )
                for page in expected_pages
            )
            document_rows = sorted(
                tuple(row)
                for row in connection.execute(
                    "SELECT id, page_id, path, title, checksum, byte_size FROM documents"
                )
            )
            expected_structure_rows = sorted(
                (
                    node.node_id,
                    node.document_id,
                    node.parent_id,
                    node.ordinal,
                    node.depth,
                    node.title,
                    node.heading_path,
                    node.line_start,
                    node.line_end,
                    node.byte_start,
                    node.byte_end,
                    node.subtree_line_start,
                    node.subtree_line_end,
                    node.subtree_byte_start,
                    node.subtree_byte_end,
                )
                for nodes in expected_nodes_by_document.values()
                for node in nodes
            )
            structure_rows = sorted(
                tuple(row)
                for row in connection.execute(
                    """
                    SELECT node_id, document_id, parent_id, ordinal, depth, title,
                           heading_path, line_start, line_end, byte_start, byte_end,
                           subtree_line_start, subtree_line_end, subtree_byte_start,
                           subtree_byte_end
                    FROM structure_nodes
                    """
                )
            )
            expected_chunk_rows = sorted(
                (
                    chunk.id,
                    chunk.document_id,
                    node_id,
                    chunk.chunk_index,
                    chunk.heading_path,
                    chunk.line_start,
                    chunk.line_end,
                    chunk.byte_start,
                    chunk.byte_end,
                    chunk.content,
                    chunk.content_hash,
                )
                for chunk, node_id in expected_chunks
            )
            chunk_rows = sorted(
                tuple(row)
                for row in connection.execute(
                    """
                    SELECT id, document_id, node_id, chunk_index, heading_path, line_start,
                           line_end, byte_start, byte_end, content, content_hash
                    FROM chunks
                    """
                )
            )
            titles = {
                f"document-{page.id}": (page.title, page.path)
                for page in expected_pages
            }
            expected_fts_rows = sorted(
                (
                    chunk.id,
                    *titles[chunk.document_id],
                    chunk.heading_path,
                    chunk.content,
                )
                for chunk, _node_id in expected_chunks
            )
            fts_rows = sorted(
                tuple(row)
                for row in connection.execute(
                    "SELECT chunk_id, title, path, heading_path, content FROM chunk_fts"
                )
            )
            page_count = len(page_rows)
            chunk_count = len(chunk_rows)
            if page_rows != expected_page_rows:
                stale_reasons.append("page_rows")
            if document_rows != expected_document_rows:
                stale_reasons.append("document_rows")
            if structure_rows != expected_structure_rows:
                stale_reasons.append("structure_rows")
            if chunk_rows != expected_chunk_rows:
                stale_reasons.append("chunk_rows")
            if fts_rows != expected_fts_rows:
                stale_reasons.append("fts_rows")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                stale_reasons.append("foreign_keys")
            if connection.execute(
                """
                SELECT 1
                FROM structure_nodes child
                LEFT JOIN structure_nodes parent ON parent.node_id = child.parent_id
                WHERE child.parent_id IS NOT NULL
                  AND (
                    parent.node_id IS NULL
                    OR parent.document_id != child.document_id
                    OR parent.depth >= child.depth
                    OR parent.subtree_byte_start > child.subtree_byte_start
                    OR child.subtree_byte_end > parent.subtree_byte_end
                  )
                LIMIT 1
                """
            ).fetchone():
                stale_reasons.append("parent_references")
            if connection.execute(
                """
                SELECT 1
                FROM structure_nodes n
                JOIN documents d ON d.id = n.document_id
                WHERE n.line_start < 1 OR n.line_end < n.line_start
                   OR n.byte_start < 0 OR n.byte_end < n.byte_start
                   OR n.subtree_line_start < 1
                   OR n.subtree_line_end < n.subtree_line_start
                   OR n.subtree_byte_start < 0
                   OR n.subtree_byte_end < n.subtree_byte_start
                   OR n.byte_start < n.subtree_byte_start
                   OR n.byte_end > n.subtree_byte_end
                   OR n.subtree_byte_end > d.byte_size
                LIMIT 1
                """
            ).fetchone():
                stale_reasons.append("range_violations")
            if connection.execute(
                """
                SELECT 1
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                LEFT JOIN structure_nodes n ON n.node_id = c.node_id
                WHERE c.line_start < 1 OR c.line_end < c.line_start
                   OR c.byte_start < 0 OR c.byte_end < c.byte_start
                   OR c.byte_end > d.byte_size
                   OR n.node_id IS NULL OR n.document_id != c.document_id
                   OR n.heading_path != c.heading_path
                   OR NOT (
                     (n.byte_start <= c.byte_start AND c.byte_end <= n.byte_end)
                     OR (n.parent_id IS NULL
                         AND n.subtree_byte_start <= c.byte_start
                         AND c.byte_end <= n.subtree_byte_end)
                   )
                LIMIT 1
                """
            ).fetchone():
                stale_reasons.append("chunk_node_ownership")
            expected_link_rows = Counter(
                row[:4] for row in indexer.link_records(expected_pages)
            )
            link_rows = Counter(
                tuple(row)
                for row in connection.execute(
                    "SELECT from_page_id, to_page_id, to_link_text, status FROM page_links"
                )
            )
            expected_source_rows, expected_tag_rows = indexer.source_and_tag_records(
                expected_pages
            )
            source_rows = sorted(
                tuple(row)
                for row in connection.execute(
                    "SELECT page_id, source_id, relation_type FROM page_sources"
                )
            )
            tag_rows = sorted(
                tuple(row)
                for row in connection.execute("SELECT page_id, tag FROM tags")
            )
            if link_rows != expected_link_rows:
                stale_reasons.append("page_link_rows")
            if source_rows != sorted(set(expected_source_rows)):
                stale_reasons.append("page_source_rows")
            if tag_rows != sorted(set(expected_tag_rows)):
                stale_reasons.append("tag_rows")
            semantic_lane, current_embeddings, vector_reasons = semantic_cohort_state(
                connection, chunk_count
            )
            if values.get(
                "semantic_cohort_fingerprint"
            ) != indexer.semantic_cohort_fingerprint(connection):
                vector_reasons.append("semantic_cohort_fingerprint")
            if values.get(
                "semantic_finite_attestation"
            ) != indexer.semantic_finite_attestation(connection):
                vector_reasons.append("vector_values")
            stale_reasons.extend(vector_reasons)
            stale_reasons = list(dict.fromkeys(stale_reasons))
        except (KeyError, TypeError, ValueError, sqlite3.Error) as exc:
            raise IndexStateError(f"malformed derived SQLite metadata: {exc}") from exc
    return {
        "index": str(path),
        "state": "stale" if stale_reasons else "ready",
        "stale_reasons": stale_reasons,
        "pages": page_count,
        "chunks": chunk_count,
        "truth_source": values.get("truth_source"),
        "rebuildable": values.get("rebuildable") == "true",
        "semantic_lane": semantic_lane,
        "semantic_vectors": current_embeddings,
    }


def discovery_metadata(connection: sqlite3.Connection) -> dict[str, str]:
    """Accept a structurally compatible derived index without scanning Markdown."""
    values = metadata(connection)
    try:
        schema = indexer.SCHEMA_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise IndexStateError(f"cannot read SQLite schema contract: {exc}") from exc
    if values.get("schema_version") != indexer.SCHEMA_VERSION:
        raise IndexStateError("derived SQLite index schema is stale; run rebuild")
    if values.get("schema_fingerprint") != indexer.sha256(schema.encode()):
        raise IndexStateError("derived SQLite index schema is stale; run rebuild")
    if values.get("truth_source") != "markdown" or values.get("rebuildable") != "true":
        raise IndexStateError(
            "derived SQLite index metadata is incompatible; run rebuild"
        )
    return values


def open_discovery_index(repo_root: Path) -> sqlite3.Connection:
    """Open one reusable connection for candidate discovery or link traversal."""
    connection: sqlite3.Connection | None = None
    try:
        connection = open_index(repo_root)
        discovery_metadata(connection)
        return connection
    except (IndexStateError, sqlite3.Error):
        if connection is not None:
            connection.close()
        raise


def open_current_index(repo_root: Path) -> sqlite3.Connection:
    """Open one current index connection for operations that require fresh vectors."""
    connection = open_discovery_index(repo_root)
    try:
        state = lightweight_health(repo_root, connection)
        if state["state"] != "ready":
            reasons = ", ".join(state["stale_reasons"])
            raise IndexStateError(
                f"derived SQLite index is stale ({reasons}); run rebuild"
            )
        return connection
    except Exception:
        connection.close()
        raise


def require_ready(repo_root: Path) -> None:
    """Compatibility gate for callers that require current derived state."""
    with closing(open_current_index(repo_root)):
        pass


def resolve_page(connection: sqlite3.Connection, reference: str) -> sqlite3.Row:
    folded = reference.strip().casefold()
    rows = connection.execute(
        """
        SELECT id, path, title, page_type
        FROM pages
        WHERE lower(id) = ? OR lower(title) = ? OR lower(path) = ?
           OR lower(substr(path, 1, length(path) - 3)) = ?
        ORDER BY CASE
          WHEN lower(id) = ? THEN 0
          WHEN lower(title) = ? THEN 1
          WHEN lower(path) = ? THEN 2
          ELSE 3
        END, path
        LIMIT 2
        """,
        (folded, folded, folded, folded, folded, folded, folded),
    ).fetchall()
    if not rows:
        raise IndexStateError(f"page not found: {reference}")
    if len(rows) > 1 and rows[0]["title"].casefold() == rows[1]["title"].casefold():
        raise IndexStateError(f"ambiguous page reference: {reference}")
    return rows[0]


def adjacent_rows(connection: sqlite3.Connection, page_id: str) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT p.id, p.path, p.title, p.page_type,
               CASE WHEN links.from_page_id = ? THEN 'outgoing' ELSE 'incoming' END direction
        FROM page_links links
        JOIN pages p ON p.id = CASE
          WHEN links.from_page_id = ? THEN links.to_page_id ELSE links.from_page_id END
        WHERE links.status = 'resolved'
          AND (links.from_page_id = ? OR links.to_page_id = ?)
        ORDER BY p.path, direction
        """,
        (page_id, page_id, page_id, page_id),
    ).fetchall()


def bounded_neighbors(
    connection: sqlite3.Connection, page_id: str, hops: int, limit: int
) -> list[dict[str, object]]:
    queue: deque[tuple[str, int]] = deque([(page_id, 0)])
    visited = {page_id}
    results: list[dict[str, object]] = []
    while queue and len(results) < limit:
        current, distance = queue.popleft()
        if distance >= hops:
            continue
        for row in adjacent_rows(connection, current):
            target_id = row["id"]
            if target_id in visited:
                continue
            visited.add(target_id)
            next_distance = distance + 1
            results.append(
                {
                    "page_id": target_id,
                    "path": row["path"],
                    "title": row["title"],
                    "page_type": row["page_type"],
                    "distance": next_distance,
                    "direction": row["direction"] if distance == 0 else "traversed",
                }
            )
            if len(results) >= limit:
                break
            queue.append((target_id, next_distance))
    return results


def fts_expression(query: str) -> str | None:
    terms = re.findall(r"[\w-]+", query, flags=re.UNICODE)
    if not terms:
        return None
    return " AND ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)


def lexical_rows(
    connection: sqlite3.Connection, query: str, limit: int
) -> list[dict[str, object]]:
    folded = query.strip().casefold()
    exact = connection.execute(
        """
        WITH ranked AS (
          SELECT c.id chunk_id, c.node_id, p.id page_id, p.path, p.title, c.chunk_index,
                 c.heading_path, c.line_start, c.line_end, c.byte_start, c.byte_end,
                 CASE WHEN lower(p.title) = ? THEN 0 ELSE 1 END exact_priority,
                 row_number() OVER (
                   PARTITION BY p.id ORDER BY c.chunk_index
                 ) page_rank
          FROM pages p
          JOIN documents d ON d.page_id = p.id
          JOIN chunks c ON c.document_id = d.id
          WHERE lower(p.title) = ? OR lower(p.path) = ?
        )
        SELECT chunk_id, node_id, page_id, path, title, chunk_index, heading_path,
               line_start, line_end, byte_start, byte_end
        FROM ranked
        WHERE page_rank = 1
        ORDER BY exact_priority, path, chunk_index
        LIMIT ?
        """,
        (folded, folded, folded, limit),
    ).fetchall()
    results = [
        dict(row) | {"match_kind": "exact", "lexical_score": None} for row in exact
    ]
    seen_pages = {row["page_id"] for row in exact}
    expression = fts_expression(query)
    if expression and len(results) < limit:
        try:
            rows = connection.execute(
                """
                WITH matched AS (
                  SELECT c.id chunk_id, c.node_id, p.id page_id, p.path, p.title, c.chunk_index,
                         c.heading_path, c.line_start, c.line_end, c.byte_start, c.byte_end,
                         bm25(chunk_fts) lexical_score
                  FROM chunk_fts
                  JOIN chunks c ON c.id = chunk_fts.chunk_id
                  JOIN documents d ON d.id = c.document_id
                  JOIN pages p ON p.id = d.page_id
                  WHERE chunk_fts MATCH ?
                ), ranked AS (
                  SELECT *, row_number() OVER (
                    PARTITION BY page_id ORDER BY lexical_score, chunk_index
                  ) page_rank
                  FROM matched
                )
                SELECT chunk_id, node_id, page_id, path, title, chunk_index, heading_path,
                       line_start, line_end, byte_start, byte_end, lexical_score
                FROM ranked
                WHERE page_rank = 1
                ORDER BY lexical_score, path, chunk_index
                LIMIT ?
                """,
                (expression, limit + len(results)),
            ).fetchall()
        except sqlite3.Error as exc:
            raise IndexStateError(f"lexical search failed: {exc}") from exc
        for row in rows:
            if row["page_id"] not in seen_pages:
                results.append(dict(row) | {"match_kind": "fts"})
                seen_pages.add(row["page_id"])
                if len(results) >= limit:
                    break
    return results


def normalize_vector(values: Sequence[float]) -> list[float]:
    vector = [float(value) for value in values]
    if not vector or any(not math.isfinite(value) for value in vector):
        raise SemanticLaneUnavailable("embedding vector must contain finite values")
    magnitude = math.hypot(*vector)
    if not math.isfinite(magnitude) or magnitude <= 0:
        raise SemanticLaneUnavailable(
            "embedding vector magnitude must be finite and positive"
        )
    return [value / magnitude for value in vector]


def pack_vector(vector: Sequence[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def unpack_vector(payload: bytes, dimensions: int) -> list[float]:
    expected = dimensions * 4
    if len(payload) != expected:
        raise SemanticLaneUnavailable(
            f"stored vector byte length {len(payload)} does not match dimensions {dimensions}"
        )
    vector = list(struct.unpack(f"<{dimensions}f", payload))
    if any(not math.isfinite(value) for value in vector):
        raise SemanticLaneUnavailable("stored vector must contain finite values")
    magnitude = math.hypot(*vector)
    if not math.isfinite(magnitude) or magnitude <= 0:
        raise SemanticLaneUnavailable(
            "stored vector must have finite non-zero magnitude"
        )
    return vector


def persist_embeddings(
    connection: sqlite3.Connection,
    embedder: Embedder,
    model_identity: str,
    tokenizer_identity: str,
    preprocessing_identity: str = DEFAULT_PREPROCESSING_IDENTITY,
) -> dict[str, int]:
    chunk_count = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
    if not chunk_count:
        return {"embedded_chunks": 0, "reused_chunks": 0, "dimensions": 0}
    reusable_ids: set[str] = set()
    reused_dimensions: set[int] = set()
    for row in connection.execute(
        """
        SELECT c.id, c.content_hash, e.chunk_hash, e.dimensions, e.vector,
               e.vector_fingerprint
        FROM chunks c
        LEFT JOIN chunk_embeddings e
          ON e.chunk_id = c.id AND e.model_identity = ?
         AND e.tokenizer_identity = ? AND e.preprocessing_identity = ?
        ORDER BY c.id
        """,
        (model_identity, tokenizer_identity, preprocessing_identity),
    ):
        if row["chunk_hash"] is not None:
            try:
                payload = bytes(row["vector"])
                dimensions = int(row["dimensions"])
            except (TypeError, ValueError):
                continue
            if (
                row["chunk_hash"] == row["content_hash"]
                and dimensions > 0
                and len(payload) == dimensions * 4
                and hashlib.sha256(payload).hexdigest() == row["vector_fingerprint"]
            ):
                try:
                    unpack_vector(payload, dimensions)
                except SemanticLaneUnavailable:
                    continue
                reusable_ids.add(str(row["id"]))
                reused_dimensions.add(dimensions)
    if len(reused_dimensions) > 1:
        reusable_ids.clear()
        reused_dimensions.clear()
    dimensions = next(iter(reused_dimensions), 0)
    now = datetime.now(timezone.utc).isoformat()
    embedded_chunks = 0

    def store_batch(batch: list[sqlite3.Row]) -> int:
        nonlocal dimensions
        vectors = list(embedder.embed([row["content"] for row in batch]))
        if len(vectors) != len(batch):
            raise SemanticLaneUnavailable(
                f"embedder returned {len(vectors)} vectors for {len(batch)} chunks"
            )
        normalized = [normalize_vector(vector) for vector in vectors]
        batch_dimensions = {len(vector) for vector in normalized}
        if len(batch_dimensions) != 1:
            raise SemanticLaneUnavailable("embedder returned inconsistent dimensions")
        batch_dimension = batch_dimensions.pop()
        if dimensions and batch_dimension != dimensions:
            raise SemanticLaneUnavailable(
                "new embedding dimensions do not match reusable semantic cohort"
            )
        dimensions = batch_dimension
        rows = []
        for chunk, vector in zip(batch, normalized, strict=True):
            packed = pack_vector(vector)
            rows.append(
                (
                    chunk["id"],
                    chunk["content_hash"],
                    model_identity,
                    tokenizer_identity,
                    preprocessing_identity,
                    dimensions,
                    packed,
                    hashlib.sha256(packed).hexdigest(),
                    now,
                )
            )
        connection.executemany(
            """
            DELETE FROM chunk_embeddings
            WHERE chunk_id = ? AND model_identity = ? AND tokenizer_identity = ?
              AND preprocessing_identity = ?
            """,
            [
                (row["id"], model_identity, tokenizer_identity, preprocessing_identity)
                for row in batch
            ],
        )
        connection.executemany(
            """
            INSERT INTO chunk_embeddings(
              chunk_id, chunk_hash, model_identity, tokenizer_identity,
              preprocessing_identity, dimensions, vector, vector_fingerprint, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return len(rows)

    with connection:
        connection.execute(
            """
            DELETE FROM chunk_embeddings
            WHERE model_identity != ? OR tokenizer_identity != ?
              OR preprocessing_identity != ?
            """,
            (model_identity, tokenizer_identity, preprocessing_identity),
        )
        connection.execute(
            """
            DELETE FROM chunk_embeddings AS e
            WHERE model_identity = ? AND tokenizer_identity = ?
              AND preprocessing_identity = ?
              AND NOT EXISTS (SELECT 1 FROM chunks c WHERE c.id = e.chunk_id)
            """,
            (model_identity, tokenizer_identity, preprocessing_identity),
        )
        batch: list[sqlite3.Row] = []
        for chunk in connection.execute(
            "SELECT id, content, content_hash FROM chunks ORDER BY id"
        ):
            if str(chunk["id"]) in reusable_ids:
                continue
            batch.append(chunk)
            if len(batch) == MAX_EMBED_BATCH_SIZE:
                embedded_chunks += store_batch(batch)
                batch.clear()
        if batch:
            embedded_chunks += store_batch(batch)
        connection.execute(
            """
            INSERT INTO index_metadata(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (
                "semantic_cohort_fingerprint",
                indexer.semantic_cohort_fingerprint(connection),
            ),
        )
        connection.execute(
            """
            INSERT INTO index_metadata(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (
                "semantic_finite_attestation",
                indexer.attest_semantic_vectors(connection),
            ),
        )
    return {
        "embedded_chunks": embedded_chunks,
        "reused_chunks": len(reusable_ids),
        "dimensions": dimensions,
    }


def semantic_rows(
    connection: sqlite3.Connection,
    query_vector: Sequence[float],
    model_identity: str,
    tokenizer_identity: str,
    limit: int,
    preprocessing_identity: str = DEFAULT_PREPROCESSING_IDENTITY,
) -> list[dict[str, object]]:
    query = normalize_vector(query_vector)
    dimensions = len(query)
    rows = connection.execute(
        """
        SELECT e.vector, e.vector_fingerprint, c.id chunk_id, c.node_id, p.id page_id,
               p.path, p.title, c.chunk_index, c.heading_path, c.line_start,
               c.line_end, c.byte_start, c.byte_end
        FROM chunk_embeddings e
        JOIN chunks c ON c.id = e.chunk_id AND c.content_hash = e.chunk_hash
        JOIN documents d ON d.id = c.document_id
        JOIN pages p ON p.id = d.page_id
        WHERE e.model_identity = ? AND e.tokenizer_identity = ?
          AND e.preprocessing_identity = ?
          AND e.dimensions = ?
        """,
        (model_identity, tokenizer_identity, preprocessing_identity, dimensions),
    ).fetchall()
    chunk_count = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
    if not rows:
        raise SemanticLaneUnavailable(
            "no current vectors match the model, tokenizer, and query dimensions"
        )
    if len(rows) != chunk_count:
        raise SemanticLaneUnavailable(
            f"semantic vector cohort is incomplete ({len(rows)}/{chunk_count} chunks)"
        )
    results = []
    for row in rows:
        packed = bytes(row["vector"])
        if hashlib.sha256(packed).hexdigest() != row["vector_fingerprint"]:
            raise SemanticLaneUnavailable(
                "semantic vector cohort contains a corrupt vector fingerprint"
            )
        stored = unpack_vector(packed, dimensions)
        score = sum(left * right for left, right in zip(query, stored, strict=True))
        result = dict(row)
        result.pop("vector")
        result.pop("vector_fingerprint")
        result["semantic_score"] = score
        results.append(result)
    results.sort(
        key=lambda item: (-item["semantic_score"], item["path"], item["chunk_index"])
    )
    if not results:
        raise SemanticLaneUnavailable(
            "all matching stored vectors failed fingerprint validation"
        )
    return results[:limit]


def semantic_provider(args: argparse.Namespace) -> OnnxSemanticProvider:
    model = args.model_path or os.environ.get("WIKI_ONNX_MODEL")
    tokenizer = args.tokenizer_path or os.environ.get("WIKI_TOKENIZER")
    if not model or not tokenizer:
        raise SemanticLaneUnavailable(
            "configure --model-path and --tokenizer-path (or WIKI_ONNX_MODEL and WIKI_TOKENIZER)"
        )
    try:
        max_sequence_length = int(
            os.environ.get("WIKI_ONNX_MAX_SEQUENCE_LENGTH", args.max_sequence_length)
        )
        batch_size = int(os.environ.get("WIKI_ONNX_BATCH_SIZE", args.batch_size))
        output_index = int(os.environ.get("WIKI_ONNX_OUTPUT_INDEX", args.output_index))
        pooling = os.environ.get("WIKI_ONNX_POOLING", args.pooling)
    except (TypeError, ValueError) as exc:
        raise SemanticLaneUnavailable(f"invalid ONNX bounds: {exc}") from exc
    return OnnxSemanticProvider(
        Path(model).resolve(),
        Path(tokenizer).resolve(),
        max_sequence_length=max_sequence_length,
        batch_size=batch_size,
        output_index=output_index,
        pooling=pooling,
    )


def prepare_lane_rows(
    lexical: list[dict[str, object]], semantic: list[dict[str, object]]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Label independent lanes and deterministically remove cross-lane duplicates."""
    prepared: list[list[dict[str, object]]] = []
    prior_chunks: set[str] = set()
    prior_pages: set[str] = set()
    for lane, rows in (("lexical", lexical), ("semantic", semantic)):
        lane_rows: list[dict[str, object]] = []
        lane_chunks: set[str] = set()
        for row in rows:
            chunk_id = str(row["chunk_id"])
            page_id = str(row["page_id"])
            if (
                chunk_id in lane_chunks
                or chunk_id in prior_chunks
                or page_id in prior_pages
            ):
                continue
            lane_chunks.add(chunk_id)
            item = dict(row)
            item["lane"] = lane
            item["lane_rank"] = len(lane_rows) + 1
            item["candidate_role"] = (
                "lexical_candidate" if lane == "lexical" else "similarity_candidate"
            )
            item["provenance"] = {
                "truth_source": "markdown",
                "index": "state/wiki_index.sqlite",
                "page_id": page_id,
                "chunk_id": chunk_id,
                "path": item["path"],
                "heading_path": item["heading_path"],
                "line_start": item["line_start"],
                "line_end": item["line_end"],
                "byte_start": item["byte_start"],
                "byte_end": item["byte_end"],
            }
            lane_rows.append(item)
        prepared.append(lane_rows)
        prior_chunks.update(str(row["chunk_id"]) for row in lane_rows)
        prior_pages.update(str(row["page_id"]) for row in lane_rows)
    return prepared[0], prepared[1]


def attach_lane_neighbors(
    connection: sqlite3.Connection,
    lanes: Sequence[list[dict[str, object]]],
    hops: int,
    neighbor_limit: int,
    graph_cap: int,
) -> None:
    """Attach bounded links while deduplicating neighbor pages across all lanes."""
    anchor_pages = {str(row["page_id"]) for lane_rows in lanes for row in lane_rows}
    seen_neighbor_pages: set[str] = set()
    remaining = graph_cap
    for lane_rows in lanes:
        for row in lane_rows:
            neighbors = []
            if hops and remaining:
                candidates = bounded_neighbors(
                    connection,
                    str(row["page_id"]),
                    hops,
                    remaining,
                )
                for candidate in candidates:
                    page_id = str(candidate["page_id"])
                    if page_id in anchor_pages or page_id in seen_neighbor_pages:
                        continue
                    candidate["provenance"] = {
                        "truth_source": "markdown",
                        "relation": "resolved_wikilink",
                        "anchor_page_id": row["page_id"],
                        "page_id": page_id,
                    }
                    neighbors.append(candidate)
                    seen_neighbor_pages.add(page_id)
                    remaining -= 1
                    if len(neighbors) >= neighbor_limit or remaining == 0:
                        break
            row["neighbors"] = neighbors


def semantic_candidates(
    connection: sqlite3.Connection, args: argparse.Namespace
) -> list[dict[str, object]]:
    provider = semantic_provider(args)
    query_vectors = list(provider.embed([args.query]))
    if len(query_vectors) != 1:
        raise SemanticLaneUnavailable("embedder did not return one query vector")
    return semantic_rows(
        connection,
        query_vectors[0],
        provider.model_identity,
        provider.tokenizer_identity,
        args.limit,
        provider.preprocessing_identity,
    )


def command_rebuild(repo_root: Path, args: argparse.Namespace) -> int:
    pages, chunks, path = indexer.rebuild(repo_root, args.chunk_threshold)
    emit({"operation": "rebuild", "index": str(path), "pages": pages, "chunks": chunks})
    return 0


def refresh_retrieval(
    repo_root: Path,
    args: argparse.Namespace,
    provider_factory=None,
) -> dict[str, object]:
    """Refresh lexical state and opportunistically complete one semantic cohort."""
    pages, chunks, path = indexer.rebuild(repo_root, args.chunk_threshold)
    model = args.model_path or os.environ.get("WIKI_ONNX_MODEL")
    tokenizer = args.tokenizer_path or os.environ.get("WIKI_TOKENIZER")
    semantic_status = "unavailable"
    semantic_reason = "model and tokenizer artifacts are not configured"
    embedding_result = {"embedded_chunks": 0, "reused_chunks": 0, "dimensions": 0}
    requested_identity: tuple[str, str, str] | None = None

    if model or tokenizer:
        try:
            provider = (provider_factory or semantic_provider)(args)
            requested_identity = (
                provider.model_identity,
                provider.tokenizer_identity,
                provider.preprocessing_identity,
            )
            with closing(open_writable_index(repo_root)) as connection:
                metadata(connection)
                embedding_result = persist_embeddings(
                    connection,
                    provider,
                    *requested_identity,
                )
            semantic_status = "ready"
            semantic_reason = None
        except SemanticLaneUnavailable as exc:
            semantic_reason = str(exc)
            current = 0
            if requested_identity is not None:
                with closing(open_index(repo_root)) as connection:
                    current = connection.execute(
                        """
                        SELECT count(*) FROM chunk_embeddings
                        WHERE model_identity = ? AND tokenizer_identity = ?
                          AND preprocessing_identity = ?
                        """,
                        requested_identity,
                    ).fetchone()[0]
            semantic_status = "partial" if 0 < current < chunks else "unavailable"

    readiness = lightweight_health(repo_root)
    if semantic_status == "ready" and readiness["semantic_lane"] != "ready":
        semantic_status = "partial" if readiness["semantic_vectors"] else "pending"
        semantic_reason = "semantic cohort did not pass bounded readiness"
    payload: dict[str, object] = {
        "operation": "refresh",
        "index": str(path),
        "pages": pages,
        "chunks": chunks,
        "retrieval_ready": readiness["state"] == "ready",
        "retrieval_status": "ready" if readiness["state"] == "ready" else "partial",
        "lexical_status": "ready" if readiness["state"] == "ready" else "partial",
        "semantic_status": semantic_status,
        "corpus_fingerprint": readiness["corpus_fingerprint"],
        "semantic_cohort_fingerprint": readiness["semantic_cohort_fingerprint"],
        "readiness_check": readiness["readiness_check"],
        **embedding_result,
    }
    if semantic_reason:
        payload["semantic_reason"] = semantic_reason
    return payload


def command_refresh(repo_root: Path, args: argparse.Namespace) -> int:
    emit(refresh_retrieval(repo_root, args))
    return 0


def command_status(repo_root: Path, _args: argparse.Namespace) -> int:
    payload = lightweight_health(repo_root)
    emit(payload)
    return 0 if payload["state"] == "ready" else 1


def raw_fallback_lane(
    repo_root: Path, query: str, limit: int
) -> dict[str, object]:
    """Query the optional raw index without making it a wiki prerequisite."""
    script = Path(__file__).with_name("raw_retrieval.py")
    unavailable: dict[str, object] = {
        "status": "unavailable",
        "score_kind": "bm25",
        "freshness": "unavailable",
        "candidate_role": "raw_source_candidate_reopen_before_use",
        "anchors": [],
    }
    if not script.is_file():
        unavailable["reason"] = "raw retrieval helper is not installed"
        return unavailable
    try:
        spec = importlib.util.spec_from_file_location("wiki_raw_fallback", script)
        if spec is None or spec.loader is None:
            raise RuntimeError("raw retrieval helper could not be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        payload = module.search(
            repo_root,
            module.database_path(repo_root, None),
            query,
            limit,
        )
    except Exception as exc:
        unavailable["reason"] = str(exc)
        return unavailable
    anchors = payload["results"]
    return {
        "status": "candidate" if anchors else "empty",
        "score_kind": "bm25",
        "freshness": payload["freshness"],
        "candidate_role": "raw_source_candidate_reopen_before_use",
        "anchors": anchors,
    }


def command_search(repo_root: Path, args: argparse.Namespace) -> int:
    validate_limit(args.limit, "search limit")
    validate_limit(args.neighbor_limit, "neighbor limit")
    cap = validate_cap(args.graph_cap)
    if args.hops not in (0, 1, 2):
        raise IndexStateError("search hops must be 0, 1, or 2")
    lexical: list[dict[str, object]] = []
    semantic: list[dict[str, object]] = []
    semantic_status = "not_requested"
    semantic_reason = None
    lexical_freshness = (
        "unchecked" if args.mode in ("lexical", "both") else "not_requested"
    )
    semantic_freshness = "not_requested"
    with closing(open_discovery_index(repo_root)) as connection:
        if args.mode in ("lexical", "both"):
            lexical = lexical_rows(connection, args.query, args.limit)
        if args.mode in ("semantic", "both"):
            readiness = lightweight_health(repo_root, connection)
            if readiness["state"] != "ready":
                semantic_freshness = "stale"
                reasons = ", ".join(readiness["stale_reasons"])
                semantic_reason = (
                    "semantic retrieval requires a current derived index "
                    f"({reasons}); run rebuild"
                )
                if args.mode == "semantic":
                    raise IndexStateError(semantic_reason)
                semantic_status = "unavailable"
            else:
                semantic_freshness = "stat"
                try:
                    semantic = semantic_candidates(connection, args)
                    semantic_status = "ready"
                except SemanticLaneUnavailable as exc:
                    if args.mode == "semantic":
                        raise
                    semantic_status = "unavailable"
                    semantic_reason = str(exc)
        lexical, semantic = prepare_lane_rows(lexical, semantic)
        attach_lane_neighbors(
            connection,
            (lexical, semantic),
            args.hops,
            args.neighbor_limit,
            cap,
        )
    lanes = {
        "lexical": {
            "status": "candidate"
            if args.mode in ("lexical", "both")
            else "not_requested",
            "score_kind": "exact_then_bm25",
            "freshness": lexical_freshness,
            "candidate_role": "verify_against_canonical_markdown",
            "anchors": lexical,
        },
        "semantic": {
            "status": semantic_status,
            "score_kind": "cosine",
            "freshness": semantic_freshness,
            "candidate_role": "similarity_candidate_not_evidence",
            "anchors": semantic,
        },
    }
    if semantic_reason:
        lanes["semantic"]["reason"] = semantic_reason
    if getattr(args, "raw_fallback", False):
        if args.mode not in ("lexical", "both"):
            raise IndexStateError("raw fallback requires lexical or both mode")
        if lexical:
            lanes["raw"] = {
                "status": "not_needed",
                "score_kind": "bm25",
                "freshness": "not_requested",
                "candidate_role": "raw_source_candidate_reopen_before_use",
                "anchors": [],
            }
        else:
            lanes["raw"] = raw_fallback_lane(repo_root, args.query, args.limit)
    emit(
        {
            "operation": "query",
            "query": args.query,
            "mode": args.mode,
            "default_link_hops": args.hops,
            "graph_cap": cap,
            "freshness": (
                "unchecked" if lexical_freshness == "unchecked" else semantic_freshness
            ),
            "canonical": False,
            "deduplication": "one_best_lexical_chunk_per_page_then_semantic",
            "semantic_lane": semantic_status,
            "lanes": lanes,
            "results": lexical if args.mode == "lexical" else [],
        }
    )
    return 0


def command_embed(repo_root: Path, args: argparse.Namespace) -> int:
    require_ready(repo_root)
    provider = semantic_provider(args)
    with closing(open_writable_index(repo_root)) as connection:
        metadata(connection)
        result = persist_embeddings(
            connection,
            provider,
            provider.model_identity,
            provider.tokenizer_identity,
            provider.preprocessing_identity,
        )
    emit(
        {
            "operation": "embed",
            "semantic_lane": "ready",
            "model_identity": provider.model_identity,
            "tokenizer_identity": provider.tokenizer_identity,
            "preprocessing_identity": provider.preprocessing_identity,
            **result,
        }
    )
    return 0


def command_semantic(repo_root: Path, args: argparse.Namespace) -> int:
    validate_limit(args.limit, "semantic limit")
    with closing(open_current_index(repo_root)) as connection:
        provider = semantic_provider(args)
        query_vectors = list(provider.embed([args.query]))
        if len(query_vectors) != 1:
            raise SemanticLaneUnavailable("embedder did not return one query vector")
        results = semantic_rows(
            connection,
            query_vectors[0],
            provider.model_identity,
            provider.tokenizer_identity,
            args.limit,
            provider.preprocessing_identity,
        )
    emit(
        {
            "operation": "semantic_search",
            "semantic_lane": "ready",
            "query": args.query,
            "freshness": "stat",
            "canonical": False,
            "results": results,
        }
    )
    return 0


def command_neighbors(repo_root: Path, args: argparse.Namespace) -> int:
    cap = validate_cap(args.limit)
    if args.hops not in (1, 2):
        raise IndexStateError("neighbors hops must be 1 or 2")
    with closing(open_discovery_index(repo_root)) as connection:
        origin = resolve_page(connection, args.page)
        results = bounded_neighbors(connection, origin["id"], args.hops, cap)
    emit(
        {
            "operation": "neighbors",
            "origin": dict(origin),
            "hops": args.hops,
            "freshness": "unchecked",
            "canonical": False,
            "results": results,
        }
    )
    return 0


def command_path(repo_root: Path, args: argparse.Namespace) -> int:
    cap = validate_cap(args.graph_cap)
    if not 1 <= args.max_depth <= 10:
        raise IndexStateError("path max depth must be between 1 and 10")
    with closing(open_discovery_index(repo_root)) as connection:
        start = resolve_page(connection, args.from_page)
        goal = resolve_page(connection, args.to_page)
        queue: deque[tuple[str, list[str]]] = deque([(start["id"], [start["id"]])])
        visited = {start["id"]}
        found: list[str] | None = None
        while queue and len(visited) <= cap:
            current, current_path = queue.popleft()
            if current == goal["id"]:
                found = current_path
                break
            if len(current_path) - 1 >= args.max_depth:
                continue
            for row in adjacent_rows(connection, current):
                target_id = row["id"]
                if target_id in visited or len(visited) >= cap:
                    continue
                visited.add(target_id)
                queue.append((target_id, [*current_path, target_id]))
        pages = []
        if found:
            placeholders = ",".join("?" for _ in found)
            rows = connection.execute(
                f"SELECT id, path, title, page_type FROM pages WHERE id IN ({placeholders})",
                found,
            ).fetchall()
            by_id = {row["id"]: dict(row) for row in rows}
            pages = [by_id[page_id] for page_id in found]
    emit(
        {
            "operation": "path",
            "found": found is not None,
            "max_depth": args.max_depth,
            "graph_cap": cap,
            "visited": len(visited),
            "freshness": "unchecked",
            "canonical": False,
            "pages": pages,
        }
    )
    return 0 if found else 1


def command_doctor(repo_root: Path, _args: argparse.Namespace) -> int:
    payload = health(repo_root)
    payload["operation"] = "doctor"
    emit(payload)
    return 0 if payload["state"] == "ready" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT), help="Wiki repository root.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    rebuild = subparsers.add_parser(
        "rebuild", help="Rebuild the derived index from Markdown."
    )
    rebuild.add_argument(
        "--chunk-threshold", type=int, default=indexer.DEFAULT_CHUNK_THRESHOLD
    )
    rebuild.set_defaults(handler=command_rebuild)

    refresh = subparsers.add_parser(
        "refresh",
        help="Atomically rebuild lexical state and incrementally refresh optional ONNX vectors.",
    )
    refresh.add_argument(
        "--chunk-threshold", type=int, default=indexer.DEFAULT_CHUNK_THRESHOLD
    )
    refresh.add_argument("--model-path")
    refresh.add_argument("--tokenizer-path")
    refresh.add_argument(
        "--max-sequence-length", type=int, default=DEFAULT_MAX_SEQUENCE_LENGTH
    )
    refresh.add_argument("--batch-size", type=int, default=DEFAULT_EMBED_BATCH_SIZE)
    refresh.add_argument("--output-index", type=int, default=DEFAULT_OUTPUT_INDEX)
    refresh.add_argument(
        "--pooling", choices=("attention_mask_mean", "cls"), default=DEFAULT_POOLING
    )
    refresh.set_defaults(handler=command_refresh)

    subparsers.add_parser(
        "status", help="Report index readiness and drift."
    ).set_defaults(handler=command_status)

    search = subparsers.add_parser(
        "search", help="Query separate lexical and optional semantic retrieval lanes."
    )
    search.add_argument("query")
    search.add_argument(
        "--mode", choices=("lexical", "semantic", "both"), default="lexical"
    )
    search.add_argument("--limit", type=int, default=DEFAULT_RESULT_LIMIT)
    search.add_argument(
        "--hops",
        type=int,
        default=1,
        help="Bounded link expansion: 0, 1 (default), or explicit 2.",
    )
    search.add_argument("--neighbor-limit", type=int, default=DEFAULT_NEIGHBOR_LIMIT)
    search.add_argument("--graph-cap", type=int, default=DEFAULT_GRAPH_CAP)
    search.add_argument(
        "--raw-fallback",
        action="store_true",
        help="Query the separate raw lexical index only when wiki lexical search is empty.",
    )
    search.add_argument("--model-path")
    search.add_argument("--tokenizer-path")
    search.add_argument(
        "--max-sequence-length", type=int, default=DEFAULT_MAX_SEQUENCE_LENGTH
    )
    search.add_argument("--batch-size", type=int, default=DEFAULT_EMBED_BATCH_SIZE)
    search.add_argument("--output-index", type=int, default=DEFAULT_OUTPUT_INDEX)
    search.add_argument(
        "--pooling", choices=("attention_mask_mean", "cls"), default=DEFAULT_POOLING
    )
    search.set_defaults(handler=command_search)

    embed = subparsers.add_parser(
        "embed", help="Build optional ONNX embeddings for current Markdown chunks."
    )
    embed.add_argument("--model-path")
    embed.add_argument("--tokenizer-path")
    embed.add_argument(
        "--max-sequence-length", type=int, default=DEFAULT_MAX_SEQUENCE_LENGTH
    )
    embed.add_argument("--batch-size", type=int, default=DEFAULT_EMBED_BATCH_SIZE)
    embed.add_argument("--output-index", type=int, default=DEFAULT_OUTPUT_INDEX)
    embed.add_argument(
        "--pooling", choices=("attention_mask_mean", "cls"), default=DEFAULT_POOLING
    )
    embed.set_defaults(handler=command_embed)

    semantic = subparsers.add_parser(
        "semantic", help="Run exact cosine search over current optional ONNX vectors."
    )
    semantic.add_argument("query")
    semantic.add_argument("--limit", type=int, default=DEFAULT_RESULT_LIMIT)
    semantic.add_argument("--model-path")
    semantic.add_argument("--tokenizer-path")
    semantic.add_argument(
        "--max-sequence-length", type=int, default=DEFAULT_MAX_SEQUENCE_LENGTH
    )
    semantic.add_argument("--batch-size", type=int, default=DEFAULT_EMBED_BATCH_SIZE)
    semantic.add_argument("--output-index", type=int, default=DEFAULT_OUTPUT_INDEX)
    semantic.add_argument(
        "--pooling", choices=("attention_mask_mean", "cls"), default=DEFAULT_POOLING
    )
    semantic.set_defaults(handler=command_semantic)

    neighbors = subparsers.add_parser(
        "neighbors", help="Inspect bounded resolved wikilink neighbors."
    )
    neighbors.add_argument("page")
    neighbors.add_argument("--hops", type=int, choices=(1, 2), default=1)
    neighbors.add_argument("--limit", type=int, default=DEFAULT_GRAPH_CAP)
    neighbors.set_defaults(handler=command_neighbors)

    path = subparsers.add_parser("path", help="Find an explicit bounded wikilink path.")
    path.add_argument("from_page")
    path.add_argument("to_page")
    path.add_argument("--max-depth", type=int, default=2)
    path.add_argument("--graph-cap", type=int, default=DEFAULT_GRAPH_CAP)
    path.set_defaults(handler=command_path)

    subparsers.add_parser(
        "doctor", help="Validate schema, integrity, and Markdown drift."
    ).set_defaults(handler=command_doctor)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    try:
        return args.handler(repo_root, args)
    except SemanticLaneUnavailable as exc:
        emit({"semantic_lane": "unavailable", "reason": str(exc)})
        return 1
    except (
        IndexStateError,
        indexer.RebuildError,
        OSError,
        sqlite3.Error,
        ValueError,
    ) as exc:
        print(f"wiki retrieval error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
