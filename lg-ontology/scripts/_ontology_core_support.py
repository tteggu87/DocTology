from __future__ import annotations

import hashlib
import json
import math
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


SCHEMA_VERSION = "lightweight-ontology-core/v1"
SUPPORTED_TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".rst"}
RETRIEVAL_DEFAULTS: dict[str, Any] = {
    "collection": {
        "name": "ontology_segments",
        "persist_directory": "vector/chroma",
    },
    "embedding": {
        "provider": "openai",
        "model": "text-embedding-3-small",
        "api_env": "OPENAI_API_KEY",
    },
    "index": {
        "distance": "cosine",
        "batch_size": 64,
        "top_k_default": 8,
        "segment_source": "warehouse/jsonl/segments.jsonl",
        "include_statuses": ["active"],
    },
    "metadata_fields": [
        "segment_id",
        "document_id",
        "document_type",
        "status",
        "entity_ids",
        "claim_ids",
        "tags",
    ],
    "segmenter": {
        "max_chars": 1200,
        "overlap_chars": 150,
        "version": "segmenter-v1",
    },
}


def build_paths(repo_root: Path) -> dict[str, Path]:
    return {
        "relations": repo_root / "intelligence" / "manifests" / "relations.yaml",
        "document_types": repo_root / "intelligence" / "manifests" / "document_types.yaml",
        "inference": repo_root / "intelligence" / "rules" / "inference.yaml",
        "shapes": repo_root / "intelligence" / "shapes" / "core.shapes.yaml",
        "context": repo_root / "intelligence" / "context" / "context.jsonld",
        "retrieval_config": repo_root / "intelligence" / "retrieval" / "chroma_collection.yaml",
        "entities": repo_root / "warehouse" / "jsonl" / "entities.jsonl",
        "documents": repo_root / "warehouse" / "jsonl" / "documents.jsonl",
        "claims": repo_root / "warehouse" / "jsonl" / "claims.jsonl",
        "claim_evidence": repo_root / "warehouse" / "jsonl" / "claim_evidence.jsonl",
        "segments": repo_root / "warehouse" / "jsonl" / "segments.jsonl",
        "derived_edges": repo_root / "warehouse" / "jsonl" / "derived_edges.jsonl",
        "duckdb": repo_root / "warehouse" / "ontology.duckdb",
        "chroma_dir": repo_root / "vector" / "chroma",
        "index_meta": repo_root / "vector" / "chroma" / "index_meta.json",
    }


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_yaml(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError("PyYAML is required to load YAML files.")
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise RuntimeError(f"JSONL line in {path} did not decode to an object.")
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent(path)
    payload = "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "untitled"


def relative_path(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def path_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def load_retrieval_config(repo_root: Path, required: bool = False) -> dict[str, Any]:
    paths = build_paths(repo_root)
    config = deepcopy(RETRIEVAL_DEFAULTS)
    if paths["retrieval_config"].exists():
        loaded = load_yaml(paths["retrieval_config"])
        if not isinstance(loaded, dict):
            raise RuntimeError("Retrieval config must decode to a mapping.")
        config = deep_merge(config, loaded)
    elif required:
        raise RuntimeError(f"Missing retrieval config: {paths['retrieval_config']}")

    config.setdefault("collection", {})
    config.setdefault("embedding", {})
    config.setdefault("index", {})
    config.setdefault("segmenter", {})
    return config


def get_segment_source_path(repo_root: Path, config: dict[str, Any]) -> Path:
    return repo_root / str(config["index"]["segment_source"])


def get_chroma_persist_path(repo_root: Path, config: dict[str, Any]) -> Path:
    return repo_root / str(config["collection"]["persist_directory"])


def encode_metadata_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def decode_metadata_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if not value or value[0] not in "[{":
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


class HashEmbeddingFunction:
    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def name(self) -> str:
        return "hash"

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in input]

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self.__call__(input)

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self.__call__(input)

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[a-z0-9_]+", text.lower()) or ["__empty__"]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for offset in range(0, len(digest) - 1, 2):
                index = digest[offset] % self.dimensions
                sign = 1.0 if digest[offset + 1] % 2 == 0 else -1.0
                vector[index] += sign
        norm = math.sqrt(sum(component * component for component in vector)) or 1.0
        return [component / norm for component in vector]


class OpenAIEmbeddingFunction:
    def __init__(self, model: str, api_env: str) -> None:
        if OpenAI is None:
            raise RuntimeError("The `openai` package is required for OpenAI embeddings.")
        api_key = os.getenv(api_env)
        if not api_key:
            raise RuntimeError(f"Environment variable `{api_env}` is required for OpenAI embeddings.")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def name(self) -> str:
        return f"openai:{self.model}"

    def __call__(self, input: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.model, input=input)
        return [item.embedding for item in response.data]

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self.__call__(input)

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self.__call__(input)


def create_embedding_function(config: dict[str, Any]) -> Any:
    provider = str(config["embedding"]["provider"]).lower()
    model = str(config["embedding"]["model"])
    api_env = str(config["embedding"]["api_env"])
    if provider == "openai":
        return OpenAIEmbeddingFunction(model=model, api_env=api_env)
    if provider == "hash":
        return HashEmbeddingFunction()
    raise RuntimeError(f"Unsupported embedding provider `{provider}`.")
