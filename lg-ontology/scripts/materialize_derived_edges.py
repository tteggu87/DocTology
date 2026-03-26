#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


def build_paths(repo_root: Path) -> dict[str, Path]:
    return {
        "relations": repo_root / "intelligence" / "manifests" / "relations.yaml",
        "inference": repo_root / "intelligence" / "rules" / "inference.yaml",
        "claims": repo_root / "warehouse" / "jsonl" / "claims.jsonl",
        "derived_edges": repo_root / "warehouse" / "jsonl" / "derived_edges.jsonl",
    }


def load_yaml(path: Path) -> object:
    if yaml is None:
        raise RuntimeError("PyYAML is required to load YAML files.")
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def load_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise RuntimeError(f"JSONL line in {path} did not decode to an object.")
        records.append(item)
    return records


def section_items(data: object, section_key: str, item_key: str) -> dict[str, dict[str, object]]:
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected mapping with `{section_key}` section.")
    section = data.get(section_key)
    if not isinstance(section, list):
        raise RuntimeError(f"`{section_key}` must be a list.")
    result: dict[str, dict[str, object]] = {}
    for item in section:
        if not isinstance(item, dict):
            raise RuntimeError(f"Each `{section_key}` entry must be a mapping.")
        key = str(item.get(item_key, "")).strip()
        if not key:
            raise RuntimeError(f"Missing `{item_key}` in `{section_key}` entry.")
        result[key] = item
    return result


def build_edge_id(rule_key: str, claim_id: str) -> str:
    return f"edge.{rule_key}.{claim_id}"


def materialize(repo_root: Path) -> tuple[int, Path]:
    paths = build_paths(repo_root)
    relations = section_items(load_yaml(paths["relations"]), "relations", "key")
    inference_rules = section_items(load_yaml(paths["inference"]), "rules", "key")
    claims = load_jsonl(paths["claims"])

    edges: list[dict[str, object]] = []
    for claim in claims:
        if claim.get("status") != "accepted":
            continue
        for rule_key, rule in inference_rules.items():
            if not rule.get("materialize", True):
                continue
            if rule.get("accepted_only", True) and claim.get("status") != "accepted":
                continue
            if rule.get("source_predicate") != claim.get("predicate"):
                continue

            derive_predicate = str(rule.get("derive_predicate", "")).strip()
            if derive_predicate not in relations:
                raise RuntimeError(
                    f"Rule `{rule_key}` derives unknown predicate `{derive_predicate}`."
                )

            subject_from = str(rule.get("subject_from", "subject"))
            object_from = str(rule.get("object_from", "object"))
            subject_id = claim.get("subject_id") if subject_from == "subject" else claim.get("object_id")
            object_id = claim.get("subject_id") if object_from == "subject" else claim.get("object_id")

            edge = {
                "edge_id": build_edge_id(rule_key, str(claim.get("claim_id"))),
                "source_claim_id": claim.get("claim_id"),
                "rule_key": rule_key,
                "subject_id": subject_id,
                "predicate": derive_predicate,
                "object_id": object_id,
                "status": "derived",
                "derived_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            if "confidence" in claim:
                edge["confidence"] = claim.get("confidence")
            if "valid_from" in claim:
                edge["valid_from"] = claim.get("valid_from")
            if "valid_to" in claim:
                edge["valid_to"] = claim.get("valid_to")
            edges.append(edge)

    deduped: dict[str, dict[str, object]] = {}
    for edge in edges:
        deduped[str(edge["edge_id"])] = edge

    output_path = paths["derived_edges"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(deduped[key], ensure_ascii=False, sort_keys=True)
        for key in sorted(deduped.keys())
    ]
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines), output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize derived ontology edges from accepted claims.")
    parser.add_argument("--repo-root", required=True, help="Repository root containing ontology files.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        count, output_path = materialize(repo_root)
    except Exception as exc:
        print(f"Failed to materialize derived edges: {exc}", file=sys.stderr)
        return 1

    print(f"Materialized {count} derived edge(s) to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
