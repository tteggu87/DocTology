# Graph Projection Model

`lg-ontology` keeps `lightweight-ontology-core` as canonical truth and derives a graph-friendly projection.

## Purpose

Use the projection layer to make graph-shaped reasoning easier without changing source-of-truth ownership.

## Node Families

- `Entity`
  - from `entities.jsonl`
- `Document`
  - from `documents.jsonl`
- `Segment`
  - from `segments.jsonl`
- `Claim`
  - from `claims.jsonl`
- `Evidence`
  - from `claim_evidence.jsonl`

## Edge Families

- claim predicate edges
  - from `claims.jsonl`
  - default: accepted claims only
- derived relation edges
  - from `derived_edges.jsonl`
- `HAS_EVIDENCE`
  - `Claim -> Evidence`
- `EVIDENCE_SEGMENT`
  - `Evidence -> Segment`
- `CLAIM_SEGMENT`
  - `Claim -> Segment`
- `SEGMENT_DOCUMENT`
  - `Segment -> Document`
- `MENTIONS`
  - `Segment -> Entity`

## Ownership Rule

Canonical:

- ontology manifests
- JSONL registries
- claim lifecycle status

Derived:

- graph projection node files
- graph projection edge files
- summary counts
- graph-oriented neighborhood caches

Optional query-time only:

- BFS result packs
- answer-specific path chains
- reranked graph neighborhoods

## Good Uses

- inspect 1-3 hop neighborhoods
- show provenance chains
- compare baseline direct lookup against graph expansion
- feed a read-only embedded graph such as Ladybug

## Bad Uses

- editing accepted facts in the graph layer
- hiding review state
- treating projected paths as stronger evidence than source documents
