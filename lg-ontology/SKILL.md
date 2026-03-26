---
name: lg-ontology
description: Extend lightweight-ontology-core into a lightweight graph workflow without replacing canonical JSONL truth. Use when documents, notes, research memos, repository guidance, finance notes, chat logs, or educational material already use lightweight ontology registries and you want graph projection, graph-style neighborhood/path inspection, Ladybug-ready exports, or baseline-vs-graph comparison tests. Trigger for requests to copy or adapt lightweight-ontology-core for graph exploration, prepare a Ladybug projection layer, inspect multi-hop neighborhoods, or compare direct JSONL reasoning against graph-assisted exploration. Do not use this to replace canonical JSONL with a graph DB or to design a full GraphRAG platform from scratch.
---

# LG Ontology

Use this skill to keep `lightweight-ontology-core` as the source of truth while adding a lightweight graph projection layer.
The goal is to improve graph-style inspection, path reasoning, and comparison testing without turning the canonical ontology into a graph-database-first system.

## Operating Model

Keep these layers separate:

- ontology definitions in YAML
- canonical extracted facts in JSONL
- canonical text-reference segments in JSONL
- derived edges in JSONL
- analytical mirror in DuckDB
- semantic retrieval in Chroma
- graph projection artifacts for graph-style querying
- optional Ladybug loading as a read-only graph layer

### Source Of Truth Hierarchy

Canonical:

- `intelligence/manifests/relations.yaml`
- `intelligence/manifests/document_types.yaml`
- `warehouse/jsonl/entities.jsonl`
- `warehouse/jsonl/documents.jsonl`
- `warehouse/jsonl/claims.jsonl`
- `warehouse/jsonl/claim_evidence.jsonl`
- `warehouse/jsonl/segments.jsonl`

Derived:

- `warehouse/jsonl/derived_edges.jsonl`
- `warehouse/ontology.duckdb`
- `warehouse/graph_projection/...`

Retrieval:

- `intelligence/retrieval/chroma_collection.yaml`
- `vector/chroma/`

Optional read-only graph serving layer:

- Ladybug or another embedded property graph loaded from projection artifacts

Do not promote graph projection outputs to canonical truth.

## What This Skill Adds Over The Core

Use this skill when the ontology core already exists and you need:

- graph-style neighborhood inspection around entities, claims, segments, and documents
- path-oriented reasoning such as `entity -> claim -> evidence -> segment -> document`
- lightweight multi-hop exploration before committing to a graph DB
- Ladybug-friendly export artifacts without changing ontology ownership
- baseline-vs-graph comparison tests to decide whether a graph layer is worth keeping

## Do Not Use This Skill For

- replacing canonical JSONL with a graph database
- auto-accepting facts because the graph looks connected
- full GraphRAG platform design from scratch
- broad ontology redesign before a domain adapter exists

## Bundled References

Read these references when needed:

- `references/claim-lifecycle.md`
- `references/chroma-integration.md`
- `references/repo-adapter-boundary.md`
- `references/graph-projection-model.md`
- `references/comparison-workflow.md`
- `references/pack-selection-guide.md`

## Starter Packs

`lg-ontology` stays generic. Starter packs are thin template helpers only.

Starter packs should live under:

- `assets/packs/<pack-name>/`

Current roadmap order:

1. `work-docs`
2. `education`
3. `finance`

Use starter packs to reduce schema-selection friction, not to turn `lg-ontology` into a domain bundle monolith.

## Bundled Scripts

Core scripts inherited from the ontology core:

- `scripts/validate_ontology_graph.py`
- `scripts/build_segments.py`
- `scripts/sync_segments_to_chroma.py`
- `scripts/retrieve_with_chroma.py`
- `scripts/materialize_derived_edges.py`
- `scripts/sync_claims_to_duckdb.py`

Graph workflow scripts added by this skill:

- `scripts/export_graph_projection.py`
- `scripts/compare_graph_modes.py`

## Workflow

### 1. Keep The Core Healthy First

Before any graph work, keep the ontology core valid.

Run:

```bash
python scripts/build_segments.py --repo-root <path>
python scripts/materialize_derived_edges.py --repo-root <path>
python scripts/sync_claims_to_duckdb.py --repo-root <path>
python scripts/validate_ontology_graph.py --repo-root <path>
```

Do not add a graph layer on top of broken canonical registries.

### 2. Export A Graph Projection

Generate graph-oriented node and edge artifacts from canonical JSONL plus derived edges.

Run:

```bash
python scripts/export_graph_projection.py --repo-root <path>
```

This writes graph projection artifacts under:

- `warehouse/graph_projection/nodes.jsonl`
- `warehouse/graph_projection/edges.jsonl`
- `warehouse/graph_projection/nodes/*.jsonl`
- `warehouse/graph_projection/edges/*.jsonl`
- `warehouse/graph_projection/summary.json`

Treat these files as derived outputs only.

### 3. Compare Baseline Reasoning Vs Graph-Style Expansion

Use the comparison script before deciding a graph layer is worth keeping.

Run:

```bash
python scripts/compare_graph_modes.py --repo-root <path> --query "<entity id or label>"
```

Use this to compare:

- direct canonical lookup around a seed entity
- graph-style neighborhood expansion
- extra reachable entities, claims, evidence rows, segments, and documents

Prefer this lightweight comparison before introducing Ladybug.

### 4. Add Ladybug Only If The Projection Proves Useful

If graph-style inspection clearly helps, load the projection artifacts into Ladybug as a read-only query layer.

The graph layer should serve:

- ad-hoc path queries
- neighborhood inspection
- lightweight multi-hop exploration
- graph-assisted context assembly

The graph layer should not own:

- fact approval
- provenance truth
- lifecycle decisions
- canonical edits

### 5. Keep Reporting Explicit

When you finish graph-layer work, report:

1. canonical ontology status
2. projection export status
3. projection counts by node and edge type
4. baseline-vs-graph comparison result
5. whether Ladybug is justified yet
6. contradictions or lifecycle concerns
7. next steps

## Projection Rules

Project these node families when useful:

- `Entity`
- `Document`
- `Segment`
- `Claim`
- `Evidence`

Project these edge families when useful:

- claim predicate edges from accepted claims
- derived relation edges
- claim-to-evidence edges
- evidence-to-segment edges
- claim-to-segment edges
- segment-to-document edges
- segment-to-entity mention edges

Keep `accepted` as the default fact graph.
Include non-accepted claims only when explicitly investigating review state or conflicts.

## Comparison Heuristic

Call the graph layer justified when at least one of these improves materially:

- multi-hop path inspection
- provenance chain explanation
- neighborhood expansion around seed entities
- graph-assisted context assembly
- analyst ergonomics for ad-hoc exploration

Do not call it justified just because it is visually pleasing or because the graph has many edges.

## Guardrails

Do not:

- treat graph projection artifacts as canonical
- bypass claim lifecycle rules because a graph query is convenient
- hide unresolved contradictions behind graph traversals
- replace the ontology core before comparison testing proves value
- add domain-specific relation sprawl to the base skill before an adapter exists

Use this skill as a graph-oriented extension of `lightweight-ontology-core`.
Keep canonical truth ownership in the ontology core.
