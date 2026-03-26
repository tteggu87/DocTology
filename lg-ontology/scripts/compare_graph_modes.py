#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

from _ontology_core_support import build_paths, load_jsonl


def normalize(value: object) -> str:
    return str(value or "").strip().lower()


def load_bundle(repo_root: Path) -> dict[str, list[dict[str, object]]]:
    paths = build_paths(repo_root)
    return {
        "entities": load_jsonl(paths["entities"]),
        "documents": load_jsonl(paths["documents"]),
        "claims": load_jsonl(paths["claims"]),
        "evidence": load_jsonl(paths["claim_evidence"]),
        "segments": load_jsonl(paths["segments"]),
        "derived_edges": load_jsonl(paths["derived_edges"]),
    }


def find_seed_entities(bundle: dict[str, list[dict[str, object]]], query: str) -> list[dict[str, object]]:
    q = normalize(query)
    matches: list[dict[str, object]] = []
    for row in bundle["entities"]:
        entity_id = normalize(row.get("entity_id"))
        label = normalize(row.get("label"))
        aliases = [normalize(item) for item in row.get("aliases", []) if isinstance(item, str)] if isinstance(row.get("aliases"), list) else []
        if q in {entity_id, label} or q in aliases:
            matches.append(row)
            continue
        if q and (q in entity_id or q in label or any(q in alias for alias in aliases)):
            matches.append(row)
    return matches


def baseline_view(bundle: dict[str, list[dict[str, object]]], seed_ids: set[str]) -> dict[str, object]:
    claims = [
        row for row in bundle["claims"]
        if str(row.get("status", "")) == "accepted"
        and (str(row.get("subject_id", "")) in seed_ids or str(row.get("object_id", "")) in seed_ids)
    ]
    claim_ids = {str(row.get("claim_id", "")) for row in claims if row.get("claim_id")}
    evidence = [row for row in bundle["evidence"] if str(row.get("claim_id", "")) in claim_ids]

    segment_ids: set[str] = set()
    document_ids: set[str] = set()
    entity_ids = set(seed_ids)

    for row in claims:
        source_segment_id = str(row.get("source_segment_id", "")).strip()
        source_document_id = str(row.get("source_document_id", "")).strip()
        if source_segment_id:
            segment_ids.add(source_segment_id)
        if source_document_id:
            document_ids.add(source_document_id)
        for key in ("subject_id", "object_id"):
            value = str(row.get(key, "")).strip()
            if value:
                entity_ids.add(value)

    for row in evidence:
        source_segment_id = str(row.get("source_segment_id", "")).strip()
        source_document_id = str(row.get("source_document_id", "")).strip()
        if source_segment_id:
            segment_ids.add(source_segment_id)
        if source_document_id:
            document_ids.add(source_document_id)

    return {
        "seed_entities": sorted(seed_ids),
        "entities": sorted(entity_ids),
        "claims": sorted(claim_ids),
        "evidence": sorted(str(row.get("evidence_id", "")) for row in evidence if row.get("evidence_id")),
        "segments": sorted(segment_ids),
        "documents": sorted(document_ids),
        "counts": {
            "entities": len(entity_ids),
            "claims": len(claim_ids),
            "evidence": len(evidence),
            "segments": len(segment_ids),
            "documents": len(document_ids),
        },
    }


def build_graph(bundle: dict[str, list[dict[str, object]]]) -> tuple[dict[str, list[str]], dict[str, str]]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    node_kinds: dict[str, str] = {}

    for row in bundle["entities"]:
        entity_id = str(row.get("entity_id", "")).strip()
        if entity_id:
            node_kinds[f"entity:{entity_id}"] = "Entity"
    for row in bundle["documents"]:
        document_id = str(row.get("document_id", "")).strip()
        if document_id:
            node_kinds[f"document:{document_id}"] = "Document"
    for row in bundle["segments"]:
        segment_id = str(row.get("segment_id", "")).strip()
        if segment_id:
            node_kinds[f"segment:{segment_id}"] = "Segment"
    for row in bundle["claims"]:
        claim_id = str(row.get("claim_id", "")).strip()
        if claim_id:
            node_kinds[f"claim:{claim_id}"] = "Claim"
    for row in bundle["evidence"]:
        evidence_id = str(row.get("evidence_id", "")).strip()
        if evidence_id:
            node_kinds[f"evidence:{evidence_id}"] = "Evidence"

    def connect(left: str, right: str) -> None:
        adjacency[left].append(right)
        adjacency[right].append(left)

    for row in bundle["claims"]:
        if str(row.get("status", "")) != "accepted":
            continue
        claim_id = str(row.get("claim_id", "")).strip()
        subject_id = str(row.get("subject_id", "")).strip()
        object_id = str(row.get("object_id", "")).strip()
        source_segment_id = str(row.get("source_segment_id", "")).strip()
        if claim_id and subject_id:
            connect(f"entity:{subject_id}", f"claim:{claim_id}")
        if claim_id and object_id:
            connect(f"claim:{claim_id}", f"entity:{object_id}")
        if claim_id and source_segment_id:
            connect(f"claim:{claim_id}", f"segment:{source_segment_id}")

    for row in bundle["evidence"]:
        evidence_id = str(row.get("evidence_id", "")).strip()
        claim_id = str(row.get("claim_id", "")).strip()
        source_segment_id = str(row.get("source_segment_id", "")).strip()
        if claim_id and evidence_id:
            connect(f"claim:{claim_id}", f"evidence:{evidence_id}")
        if evidence_id and source_segment_id:
            connect(f"evidence:{evidence_id}", f"segment:{source_segment_id}")

    for row in bundle["segments"]:
        segment_id = str(row.get("segment_id", "")).strip()
        document_id = str(row.get("document_id", "")).strip()
        if segment_id and document_id:
            connect(f"segment:{segment_id}", f"document:{document_id}")
        entity_ids = row.get("entity_ids", [])
        if isinstance(entity_ids, list):
            for entity_id in entity_ids:
                value = str(entity_id).strip()
                if value:
                    connect(f"segment:{segment_id}", f"entity:{value}")

    for row in bundle["derived_edges"]:
        subject_id = str(row.get("subject_id", "")).strip()
        object_id = str(row.get("object_id", "")).strip()
        if subject_id and object_id:
            connect(f"entity:{subject_id}", f"entity:{object_id}")

    return adjacency, node_kinds


def graph_view(bundle: dict[str, list[dict[str, object]]], seed_ids: set[str], max_hops: int) -> dict[str, object]:
    adjacency, node_kinds = build_graph(bundle)
    seeds = [f"entity:{entity_id}" for entity_id in sorted(seed_ids)]
    queue: deque[tuple[str, int]] = deque((seed, 0) for seed in seeds)
    visited = set(seeds)
    parents: dict[str, str] = {}

    while queue:
        current, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for neighbor in adjacency.get(current, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            parents[neighbor] = current
            queue.append((neighbor, depth + 1))

    by_kind: dict[str, list[str]] = defaultdict(list)
    for node_id in sorted(visited):
        kind = node_kinds.get(node_id, "Unknown")
        by_kind[kind].append(node_id.split(":", 1)[1] if ":" in node_id else node_id)

    sample_paths: list[str] = []
    for target in sorted(visited):
        if len(sample_paths) >= 6 or target in seeds:
            continue
        path = [target]
        cursor = target
        while cursor in parents:
            cursor = parents[cursor]
            path.append(cursor)
        if path[-1] not in seeds:
            continue
        path.reverse()
        sample_paths.append(" -> ".join(path))

    return {
        "seed_entities": sorted(seed_ids),
        "reachable": {kind: values for kind, values in sorted(by_kind.items())},
        "counts": {kind.lower(): len(values) for kind, values in sorted(by_kind.items())},
        "sample_paths": sample_paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare direct ontology lookup against graph-style neighborhood expansion.")
    parser.add_argument("--repo-root", required=True, help="Repository root containing ontology files.")
    parser.add_argument("--query", required=True, help="Entity id or label to inspect.")
    parser.add_argument("--max-hops", type=int, default=3, help="Maximum graph traversal depth.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        bundle = load_bundle(repo_root)
        seeds = find_seed_entities(bundle, args.query)
    except Exception as exc:
        print(f"Failed to build comparison bundle: {exc}", file=sys.stderr)
        return 1

    if not seeds:
        print(f"No entity matched query: {args.query}", file=sys.stderr)
        return 2

    seed_ids = {str(row.get("entity_id")) for row in seeds if row.get("entity_id")}
    baseline = baseline_view(bundle, seed_ids)
    graph = graph_view(bundle, seed_ids, args.max_hops)

    report = {
        "query": args.query,
        "seed_entities": sorted(seed_ids),
        "baseline": baseline,
        "graph": graph,
        "uplift": {
            "extra_entities": graph["counts"].get("entity", 0) - baseline["counts"]["entities"],
            "extra_claims": graph["counts"].get("claim", 0) - baseline["counts"]["claims"],
            "extra_evidence": graph["counts"].get("evidence", 0) - baseline["counts"]["evidence"],
            "extra_segments": graph["counts"].get("segment", 0) - baseline["counts"]["segments"],
            "extra_documents": graph["counts"].get("document", 0) - baseline["counts"]["documents"],
        },
    }

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Query: {report['query']}")
        print(f"Seed entities: {', '.join(report['seed_entities'])}")
        print("Baseline direct lookup:")
        for key, value in baseline["counts"].items():
            print(f"  - {key}: {value}")
        print("Graph-style expansion:")
        for key, value in graph["counts"].items():
            print(f"  - {key}: {value}")
        print("Uplift:")
        for key, value in report["uplift"].items():
            print(f"  - {key}: {value}")
        if graph["sample_paths"]:
            print("Sample paths:")
            for value in graph["sample_paths"]:
                print(f"  - {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
