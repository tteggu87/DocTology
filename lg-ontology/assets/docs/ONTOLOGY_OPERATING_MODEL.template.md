---
Status: Draft
Source of Truth: No
Last Updated: YYYY-MM-DD
Canonical Layer: intelligence/manifests/*.yaml + warehouse/jsonl/*.jsonl
---

# Ontology Operating Model

## Purpose

Use this document to explain how the repository turns text into a lightweight ontology without promoting every helper artifact to source truth.

## Canonical Artifacts

- `intelligence/manifests/relations.yaml`
- `intelligence/manifests/document_types.yaml`
- `warehouse/jsonl/entities.jsonl`
- `warehouse/jsonl/documents.jsonl`
- `warehouse/jsonl/claims.jsonl`
- `warehouse/jsonl/claim_evidence.jsonl`

## Canonical Reference Artifacts

- `warehouse/jsonl/segments.jsonl`

## Derived, Mirror, And Retrieval Artifacts

- `warehouse/jsonl/derived_edges.jsonl`
- `warehouse/ontology.duckdb`
- `vector/chroma/`

Derived edges are disposable materialized output.
DuckDB is a query mirror only.
Chroma is a retrieval index only.

## Claim Lifecycle

- `proposed + needs_review`
- `accepted + approved`
- `disputed + conflict_open`
- `rejected + rejected`
- `superseded + archived`

`accepted` claims require human review metadata and at least one supporting evidence row.

## Review Rules

- Extractors may create `proposed` claims.
- Humans decide whether a claim becomes `accepted`.
- Validation fails if accepted claims lack evidence or decision metadata.
- Retrieval results may suggest candidates, but they do not change claim state.

## Validation Loop

Run:

```bash
python scripts/build_segments.py --repo-root <path>
python scripts/sync_segments_to_chroma.py --repo-root <path>
python scripts/validate_ontology_graph.py --repo-root <path>
python scripts/materialize_derived_edges.py --repo-root <path>
python scripts/sync_claims_to_duckdb.py --repo-root <path>
```

Use strict validation when DuckDB and Chroma freshness must match the current canonical files.

## Current Vs Future Scope

- v1 supports explicit contradictions and exclusive-object conflicts only.
- v1 does not perform free-form semantic contradiction detection.
- v1 uses Chroma as recall assistance only, not as canonical truth.
- Future adapters may add domain packs, but the core relation set should stay small.

## Unresolved Drift

- Record any known mismatch between text, claims, evidence, segments, retrieval state, and derived edges here.
