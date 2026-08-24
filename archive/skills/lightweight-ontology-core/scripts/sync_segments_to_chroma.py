#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import chromadb
except Exception:  # pragma: no cover
    chromadb = None

from _ontology_core_support import (
    create_embedding_function,
    encode_metadata_value,
    get_chroma_persist_path,
    get_segment_source_path,
    load_jsonl,
    load_retrieval_config,
    sha256_file,
    write_json,
)


def batched(items: list[dict[str, object]], batch_size: int) -> list[list[dict[str, object]]]:
    return [items[index:index + batch_size] for index in range(0, len(items), batch_size)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync segment registry into Chroma.")
    parser.add_argument("--repo-root", required=True, help="Repository root containing ontology data.")
    parser.add_argument("--reset", action="store_true", help="Recreate the collection from scratch.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    if chromadb is None:
        print("chromadb is required to sync segments.", file=sys.stderr)
        return 1

    repo_root = Path(args.repo_root).resolve()
    config = load_retrieval_config(repo_root, required=True)
    segment_source = get_segment_source_path(repo_root, config)
    if not segment_source.exists():
        print(f"Missing segments source: {segment_source}", file=sys.stderr)
        return 1

    include_statuses = {str(value) for value in config["index"].get("include_statuses", [])}
    segments = load_jsonl(segment_source)
    if include_statuses:
        segments = [row for row in segments if str(row.get("status", "")) in include_statuses]

    persist_path = get_chroma_persist_path(repo_root, config)
    persist_path.mkdir(parents=True, exist_ok=True)
    embedding_function = create_embedding_function(config)
    client = chromadb.PersistentClient(path=str(persist_path))
    collection_name = str(config["collection"]["name"])

    if args.reset:
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": str(config["index"]["distance"])},
        embedding_function=embedding_function,
    )

    current_ids = {str(row["segment_id"]) for row in segments}
    try:
        existing = collection.get(include=[])
        existing_ids = set(existing.get("ids") or [])
    except Exception:
        existing_ids = set()
    stale_ids = sorted(existing_ids - current_ids)
    if stale_ids:
        collection.delete(ids=stale_ids)

    metadata_fields = [str(field) for field in config.get("metadata_fields", [])]
    batch_size = int(config["index"]["batch_size"])
    for batch in batched(segments, batch_size):
        ids = [str(row["segment_id"]) for row in batch]
        documents = [str(row.get("text", "")) for row in batch]
        metadatas = []
        for row in batch:
            metadata = {}
            for field in metadata_fields:
                if field in row:
                    metadata[field] = encode_metadata_value(row[field])
            metadatas.append(metadata)
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    index_meta = {
        "collection_name": collection_name,
        "embedding_provider": str(config["embedding"]["provider"]),
        "embedding_model": str(config["embedding"]["model"]),
        "segment_source": str(config["index"]["segment_source"]),
        "segment_source_hash": sha256_file(segment_source),
        "segment_count": len(segments),
        "segmenter_version": str(config["segmenter"]["version"]),
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(persist_path / "index_meta.json", index_meta)

    summary = {
        "repo_root": str(repo_root),
        "collection_name": collection_name,
        "segment_count": len(segments),
        "persist_directory": persist_path.as_posix(),
        "index_meta": (persist_path / "index_meta.json").as_posix(),
    }
    if args.format == "json":
        print(json.dumps(summary, indent=2))
    else:
        print(f"Repo root: {repo_root}")
        print(f"Collection: {collection_name}")
        print(f"Segments synced: {len(segments)}")
        print(f"Persist directory: {persist_path}")
        print(f"Index meta: {persist_path / 'index_meta.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
