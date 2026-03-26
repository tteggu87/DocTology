#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import chromadb
except Exception:  # pragma: no cover
    chromadb = None

from _ontology_core_support import create_embedding_function, decode_metadata_value, get_chroma_persist_path, load_retrieval_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieve ontology segments with Chroma.")
    parser.add_argument("--repo-root", required=True, help="Repository root containing ontology data.")
    parser.add_argument("--query", required=True, help="Natural-language retrieval query.")
    parser.add_argument("--top-k", type=int, help="Number of segment results to return.")
    parser.add_argument("--document-type", help="Optional document type filter.")
    parser.add_argument("--status", help="Optional segment status filter.")
    args = parser.parse_args()

    if chromadb is None:
        print("chromadb is required to query segments.", file=sys.stderr)
        return 1

    repo_root = Path(args.repo_root).resolve()
    config = load_retrieval_config(repo_root, required=True)
    persist_path = get_chroma_persist_path(repo_root, config)
    if not persist_path.exists():
        print(f"Missing Chroma persist directory: {persist_path}", file=sys.stderr)
        return 1

    client = chromadb.PersistentClient(path=str(persist_path))
    collection = client.get_collection(
        name=str(config["collection"]["name"]),
        embedding_function=create_embedding_function(config),
    )

    filters = []
    if args.document_type:
        filters.append({"document_type": args.document_type})
    if args.status:
        filters.append({"status": args.status})
    where = None
    if len(filters) == 1:
        where = filters[0]
    elif len(filters) > 1:
        where = {"$and": filters}

    top_k = args.top_k or int(config["index"]["top_k_default"])
    result = collection.query(
        query_texts=[args.query],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    rows = []
    for index, segment_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) and isinstance(metadatas[index], dict) else {}
        rows.append(
            {
                "segment_id": segment_id,
                "document_id": metadata.get("document_id"),
                "text": documents[index] if index < len(documents) else "",
                "distance": distances[index] if index < len(distances) else None,
                "entity_ids": decode_metadata_value(metadata.get("entity_ids")),
                "claim_ids": decode_metadata_value(metadata.get("claim_ids")),
                "tags": decode_metadata_value(metadata.get("tags")),
                "document_type": metadata.get("document_type"),
                "status": metadata.get("status"),
            }
        )

    print(json.dumps({"query": args.query, "count": len(rows), "results": rows}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
