#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from _ontology_core_support import build_paths, ensure_parent, load_jsonl, write_json


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_parent(path)
    payload = "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def node(node_id: str, node_type: str, source_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "node_id": node_id,
        "node_type": node_type,
        "source_id": source_id,
        "payload": payload,
    }


def edge(edge_id: str, edge_type: str, from_id: str, to_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "edge_id": edge_id,
        "edge_type": edge_type,
        "from_id": from_id,
        "to_id": to_id,
        "payload": payload,
    }


def project(repo_root: Path, output_dir: Path, include_nonaccepted: bool) -> dict[str, object]:
    paths = build_paths(repo_root)
    entities = load_jsonl(paths["entities"])
    documents = load_jsonl(paths["documents"])
    claims = load_jsonl(paths["claims"])
    evidence_rows = load_jsonl(paths["claim_evidence"])
    segments = load_jsonl(paths["segments"])
    derived_edges = load_jsonl(paths["derived_edges"])

    nodes_by_family: dict[str, list[dict[str, object]]] = {
        "entities": [],
        "documents": [],
        "segments": [],
        "claims": [],
        "evidence": [],
    }
    edges_by_family: dict[str, list[dict[str, object]]] = {
        "claim_predicates": [],
        "derived_relations": [],
        "claim_evidence": [],
        "evidence_segments": [],
        "claim_segments": [],
        "segment_documents": [],
        "segment_mentions": [],
    }

    for row in entities:
        entity_id = str(row.get("entity_id", "")).strip()
        if entity_id:
            nodes_by_family["entities"].append(node(f"entity:{entity_id}", "Entity", entity_id, row))

    for row in documents:
        document_id = str(row.get("document_id", "")).strip()
        if document_id:
            nodes_by_family["documents"].append(node(f"document:{document_id}", "Document", document_id, row))

    for row in segments:
        segment_id = str(row.get("segment_id", "")).strip()
        if not segment_id:
            continue
        nodes_by_family["segments"].append(node(f"segment:{segment_id}", "Segment", segment_id, row))

        document_id = str(row.get("document_id", "")).strip()
        if document_id:
            edges_by_family["segment_documents"].append(
                edge(
                    f"edge.segment_document.{segment_id}.{document_id}",
                    "SEGMENT_DOCUMENT",
                    f"segment:{segment_id}",
                    f"document:{document_id}",
                    {"segment_id": segment_id, "document_id": document_id},
                )
            )

        for entity_id in row.get("entity_ids", []) if isinstance(row.get("entity_ids"), list) else []:
            value = str(entity_id).strip()
            if not value:
                continue
            edges_by_family["segment_mentions"].append(
                edge(
                    f"edge.segment_mentions.{segment_id}.{value}",
                    "MENTIONS",
                    f"segment:{segment_id}",
                    f"entity:{value}",
                    {"segment_id": segment_id, "entity_id": value},
                )
            )

    for row in claims:
        claim_id = str(row.get("claim_id", "")).strip()
        if not claim_id:
            continue
        nodes_by_family["claims"].append(node(f"claim:{claim_id}", "Claim", claim_id, row))

        status = str(row.get("status", ""))
        if include_nonaccepted or status == "accepted":
            subject_id = str(row.get("subject_id", "")).strip()
            object_id = str(row.get("object_id", "")).strip()
            predicate = str(row.get("predicate", "")).strip()
            if subject_id and object_id and predicate:
                edges_by_family["claim_predicates"].append(
                    edge(
                        f"edge.claim_predicate.{claim_id}",
                        predicate,
                        f"entity:{subject_id}",
                        f"entity:{object_id}",
                        {
                            "claim_id": claim_id,
                            "predicate": predicate,
                            "status": status,
                            "confidence": row.get("confidence"),
                            "review_state": row.get("review_state"),
                        },
                    )
                )

        source_segment_id = str(row.get("source_segment_id", "")).strip()
        if source_segment_id:
            edges_by_family["claim_segments"].append(
                edge(
                    f"edge.claim_segment.{claim_id}.{source_segment_id}",
                    "CLAIM_SEGMENT",
                    f"claim:{claim_id}",
                    f"segment:{source_segment_id}",
                    {"claim_id": claim_id, "segment_id": source_segment_id},
                )
            )

    for row in evidence_rows:
        evidence_id = str(row.get("evidence_id", "")).strip()
        claim_id = str(row.get("claim_id", "")).strip()
        if not evidence_id:
            continue
        nodes_by_family["evidence"].append(node(f"evidence:{evidence_id}", "Evidence", evidence_id, row))

        if claim_id:
            edges_by_family["claim_evidence"].append(
                edge(
                    f"edge.claim_evidence.{claim_id}.{evidence_id}",
                    "HAS_EVIDENCE",
                    f"claim:{claim_id}",
                    f"evidence:{evidence_id}",
                    {"claim_id": claim_id, "evidence_id": evidence_id},
                )
            )

        source_segment_id = str(row.get("source_segment_id", "")).strip()
        if source_segment_id:
            edges_by_family["evidence_segments"].append(
                edge(
                    f"edge.evidence_segment.{evidence_id}.{source_segment_id}",
                    "EVIDENCE_SEGMENT",
                    f"evidence:{evidence_id}",
                    f"segment:{source_segment_id}",
                    {"evidence_id": evidence_id, "segment_id": source_segment_id},
                )
            )

    for row in derived_edges:
        edge_id = str(row.get("edge_id", "")).strip()
        subject_id = str(row.get("subject_id", "")).strip()
        object_id = str(row.get("object_id", "")).strip()
        predicate = str(row.get("predicate", "")).strip()
        if edge_id and subject_id and object_id and predicate:
            edges_by_family["derived_relations"].append(
                edge(
                    f"edge.derived.{edge_id}",
                    predicate,
                    f"entity:{subject_id}",
                    f"entity:{object_id}",
                    row,
                )
            )

    all_nodes = [item for family in nodes_by_family.values() for item in family]
    all_edges = [item for family in edges_by_family.values() for item in family]

    write_jsonl(output_dir / "nodes.jsonl", all_nodes)
    write_jsonl(output_dir / "edges.jsonl", all_edges)

    for family, rows in nodes_by_family.items():
        write_jsonl(output_dir / "nodes" / f"{family}.jsonl", rows)
    for family, rows in edges_by_family.items():
        write_jsonl(output_dir / "edges" / f"{family}.jsonl", rows)

    summary = {
        "output_dir": output_dir.as_posix(),
        "node_counts": Counter({family: len(rows) for family, rows in nodes_by_family.items()}),
        "edge_counts": Counter({family: len(rows) for family, rows in edges_by_family.items()}),
        "total_nodes": len(all_nodes),
        "total_edges": len(all_edges),
        "include_nonaccepted": include_nonaccepted,
    }
    write_json(output_dir / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Export lightweight ontology registries into graph projection artifacts.")
    parser.add_argument("--repo-root", required=True, help="Repository root containing ontology files.")
    parser.add_argument(
        "--output-dir",
        help="Optional output directory. Defaults to <repo-root>/warehouse/graph_projection.",
    )
    parser.add_argument(
        "--include-nonaccepted",
        action="store_true",
        help="Include non-accepted claim predicate edges in the fact graph projection.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else repo_root / "warehouse" / "graph_projection"

    try:
        summary = project(repo_root, output_dir, args.include_nonaccepted)
    except Exception as exc:
        print(f"Failed to export graph projection: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Output: {summary['output_dir']}")
        print(f"Total nodes: {summary['total_nodes']}")
        print(f"Total edges: {summary['total_edges']}")
        print("Node counts:")
        for key, value in sorted(summary["node_counts"].items()):
            print(f"  - {key}: {value}")
        print("Edge counts:")
        for key, value in sorted(summary["edge_counts"].items()):
            print(f"  - {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
