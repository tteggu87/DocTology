#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _ontology_core_support import (
    SUPPORTED_TEXT_SUFFIXES,
    build_paths,
    load_jsonl,
    load_retrieval_config,
    path_within,
    sha256_text,
    slugify,
    write_jsonl,
)


RST_HEADING_CHARS = {"=", "-", "~", "^", '"', "'", "`", ":", "+", "*", "#"}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def line_offsets(text: str) -> list[int]:
    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)
    return offsets


def detect_heading_markers(text: str, suffix: str) -> list[dict[str, object]]:
    lines = text.splitlines(keepends=True)
    offsets = line_offsets(text)
    markers: list[dict[str, object]] = []

    if suffix in {".md", ".markdown"}:
        for index, line in enumerate(lines):
            match = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
            if not match:
                continue
            markers.append({"start": offsets[index], "level": len(match.group(1)), "title": match.group(2).strip()})
        return markers

    if suffix == ".rst":
        char_levels = {"=": 1, "-": 2, "~": 3, "^": 4, '"': 5, "'": 6, "`": 7, ":": 8, "+": 9, "*": 10, "#": 11}
        for index in range(len(lines) - 1):
            title = lines[index].rstrip("\r\n")
            underline = lines[index + 1].rstrip("\r\n")
            if not title.strip():
                continue
            if not underline or len(set(underline)) != 1:
                continue
            if underline[0] not in RST_HEADING_CHARS:
                continue
            if len(underline) < len(title.strip()):
                continue
            markers.append({"start": offsets[index], "level": char_levels.get(underline[0], 6), "title": title.strip()})
        return markers

    return markers


def build_sections(text: str, suffix: str) -> list[dict[str, object]]:
    markers = detect_heading_markers(text, suffix)
    if not markers:
        return [{"start": 0, "end": len(text), "heading_path": []}]

    sections: list[dict[str, object]] = []
    first_start = int(markers[0]["start"])
    if first_start > 0 and text[:first_start].strip():
        sections.append({"start": 0, "end": first_start, "heading_path": []})

    stack: list[dict[str, object]] = []
    for index, marker in enumerate(markers):
        while stack and int(stack[-1]["level"]) >= int(marker["level"]):
            stack.pop()
        stack.append(marker)
        end = int(markers[index + 1]["start"]) if index + 1 < len(markers) else len(text)
        sections.append({"start": int(marker["start"]), "end": end, "heading_path": [str(item["title"]) for item in stack]})
    return sections


def paragraph_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    section = text[start:end]
    spans: list[tuple[int, int]] = []
    cursor = 0
    for match in re.finditer(r"\n\s*\n", section):
        chunk = section[cursor:match.start()]
        if chunk.strip():
            spans.append((start + cursor, start + match.start()))
        cursor = match.end()
    tail = section[cursor:]
    if tail.strip():
        spans.append((start + cursor, end))
    return spans


def sliding_spans(start: int, end: int, max_chars: int, overlap: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        next_end = min(cursor + max_chars, end)
        spans.append((cursor, next_end))
        if next_end >= end:
            break
        cursor = max(cursor + 1, next_end - overlap)
    return spans


def split_section(text: str, section: dict[str, object], max_chars: int, overlap: int) -> list[dict[str, object]]:
    start = int(section["start"])
    end = int(section["end"])
    spans = paragraph_spans(text, start, end)
    if not spans and text[start:end].strip():
        spans = [(start, end)]

    chunks: list[dict[str, object]] = []
    current_start: int | None = None
    current_end: int | None = None

    def flush_current() -> None:
        nonlocal current_start, current_end
        if current_start is None or current_end is None:
            return
        if text[current_start:current_end].strip():
            chunks.append({"start": current_start, "end": current_end, "heading_path": list(section["heading_path"])})
        current_start = None
        current_end = None

    for span_start, span_end in spans:
        if span_end - span_start > max_chars:
            flush_current()
            for piece_start, piece_end in sliding_spans(span_start, span_end, max_chars, overlap):
                if text[piece_start:piece_end].strip():
                    chunks.append({"start": piece_start, "end": piece_end, "heading_path": list(section["heading_path"])})
            continue
        if current_start is None:
            current_start = span_start
            current_end = span_end
            continue
        if span_end - current_start <= max_chars:
            current_end = span_end
        else:
            flush_current()
            current_start = span_start
            current_end = span_end

    flush_current()
    return chunks


def build_links(
    claims: list[dict[str, object]],
    evidence_rows: list[dict[str, object]],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    claims_by_segment: dict[str, set[str]] = {}
    entities_by_segment: dict[str, set[str]] = {}
    claim_index = {str(row.get("claim_id", "")): row for row in claims if row.get("claim_id")}

    for row in claims:
        segment_id = row.get("source_segment_id")
        claim_id = row.get("claim_id")
        if not isinstance(segment_id, str) or not claim_id:
            continue
        claims_by_segment.setdefault(segment_id, set()).add(str(claim_id))
        for key in ("subject_id", "object_id"):
            value = row.get(key)
            if value:
                entities_by_segment.setdefault(segment_id, set()).add(str(value))

    for row in evidence_rows:
        segment_id = row.get("source_segment_id")
        claim_id = row.get("claim_id")
        if not isinstance(segment_id, str) or not claim_id:
            continue
        claims_by_segment.setdefault(segment_id, set()).add(str(claim_id))
        claim = claim_index.get(str(claim_id))
        if claim is None:
            continue
        for key in ("subject_id", "object_id"):
            value = claim.get(key)
            if value:
                entities_by_segment.setdefault(segment_id, set()).add(str(value))

    return claims_by_segment, entities_by_segment


def build_segments_for_document(
    document: dict[str, object],
    repo_root: Path,
    config: dict[str, object],
    claims_by_segment: dict[str, set[str]],
    entities_by_segment: dict[str, set[str]],
) -> list[dict[str, object]]:
    path = repo_root / str(document.get("path", ""))
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_TEXT_SUFFIXES:
        return []

    text = read_text(path)
    segmenter = config["segmenter"]
    max_chars = int(segmenter["max_chars"])
    overlap = int(segmenter["overlap_chars"])
    segmenter_version = str(segmenter["version"])

    pieces: list[dict[str, object]] = []
    for section in build_sections(text, suffix):
        pieces.extend(split_section(text, section, max_chars, overlap))

    segments: list[dict[str, object]] = []
    document_id = str(document["document_id"])
    document_type = str(document.get("document_type", "general_note"))
    status = str(document.get("status", "active"))
    for ordinal, piece in enumerate(pieces, start=1):
        segment_id = f"seg:{document_id}:{ordinal:03d}"
        segment_text = text[int(piece["start"]):int(piece["end"])]
        heading_path = list(piece["heading_path"])
        tags = [document_type] + [slugify(item) for item in heading_path]
        segment = {
            "segment_id": segment_id,
            "document_id": document_id,
            "document_type": document_type,
            "text": segment_text,
            "start_char": int(piece["start"]),
            "end_char": int(piece["end"]),
            "ordinal": ordinal,
            "status": status,
            "text_hash": sha256_text(segment_text),
            "segmenter_version": segmenter_version,
        }
        if heading_path:
            segment["heading_path"] = heading_path
        claim_ids = sorted(claims_by_segment.get(segment_id, set()))
        if claim_ids:
            segment["claim_ids"] = claim_ids
        entity_ids = sorted(entities_by_segment.get(segment_id, set()))
        if entity_ids:
            segment["entity_ids"] = entity_ids
        if tags:
            segment["tags"] = sorted(dict.fromkeys(tag for tag in tags if tag))
        segments.append(segment)
    return segments


def main() -> int:
    parser = argparse.ArgumentParser(description="Build stable segments for lightweight ontology retrieval.")
    parser.add_argument("--repo-root", required=True, help="Repository root containing ontology registries.")
    parser.add_argument("--docs-dir", help="Optional docs folder filter.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    docs_dir = Path(args.docs_dir).resolve() if args.docs_dir else None
    paths = build_paths(repo_root)
    if not paths["documents"].exists():
        print("Missing documents registry: warehouse/jsonl/documents.jsonl", file=sys.stderr)
        return 1

    config = load_retrieval_config(repo_root, required=False)
    documents = load_jsonl(paths["documents"])
    claims = load_jsonl(paths["claims"])
    evidence_rows = load_jsonl(paths["claim_evidence"])
    claims_by_segment, entities_by_segment = build_links(claims, evidence_rows)

    segments: list[dict[str, object]] = []
    scanned_documents = 0
    for document in documents:
        path_value = document.get("path")
        if not isinstance(path_value, str):
            continue
        candidate = (repo_root / path_value).resolve()
        if docs_dir is not None and not path_within(candidate, docs_dir):
            continue
        if not candidate.exists() or candidate.suffix.lower() not in SUPPORTED_TEXT_SUFFIXES:
            continue
        scanned_documents += 1
        segments.extend(build_segments_for_document(document, repo_root, config, claims_by_segment, entities_by_segment))

    write_jsonl(paths["segments"], segments)

    summary = {
        "repo_root": str(repo_root),
        "documents_scanned": scanned_documents,
        "segments_written": len(segments),
        "output": paths["segments"].as_posix(),
    }
    if args.format == "json":
        print(json.dumps(summary, indent=2))
    else:
        print(f"Repo root: {repo_root}")
        print(f"Documents scanned: {scanned_documents}")
        print(f"Segments written: {len(segments)}")
        print(f"Output: {paths['segments']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
