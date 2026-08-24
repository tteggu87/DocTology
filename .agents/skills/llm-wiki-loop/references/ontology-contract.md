# Ontology Contract For The Wiki Loop

Read this reference only for ontology-capable lanes.

## Canonical Layers

- Canonical vocabulary: `intelligence/manifests/relations.yaml` and
  `intelligence/manifests/document_types.yaml` when present
- Canonical registries: `documents.jsonl`, `messages.jsonl` when applicable,
  `entities.jsonl`, `claims.jsonl`, and `claim_evidence.jsonl`
- Canonical reference layer: `segments.jsonl`
- Derived only: `derived_edges.jsonl`, DuckDB mirrors, retrieval indexes, and
  graph projections

Do not let wiki summaries, retrieval results, graph edges, or analytical mirrors
replace canonical JSONL truth.

## Claim Lifecycle

Allowed status and review-state pairs:

- `proposed + needs_review`
- `accepted + approved`
- `disputed + conflict_open`
- `rejected + rejected`
- `superseded + archived`

An accepted claim requires:

- `reviewed_by` and `reviewed_at`
- `decision_by`, `decision_at`, and `decision_note`
- a human decision identifier such as `human:<id>`
- at least one supporting evidence row

Automatic source processing writes proposals unless the repository defines an
explicit human-reviewed promotion workflow.

## Evidence And Segments

- Every evidence row must resolve to an existing claim and document.
- A referenced segment must exist and belong to the same document.
- Segment offsets and text hashes must match the immutable source span.
- Evidence offsets must stay inside the referenced segment and document.
- Conversational or sequential corpora must preserve full-fidelity messages and
  participant coverage; top-N summaries are presentation only.

## Derived Outputs

- Materialize certified/active derived edges only from accepted claims and
  declared rules. Exploratory projections must remain explicitly draft.
- Never hand-edit a derived edge as canonical truth.
- DuckDB, Chroma, and graph projections are optional derived aids.
- Stale optional mirrors may warn or fail according to the selected strictness,
  but they never become semantic fallback.

## Minimum Integrity Gate

For an ontology-capable lane, `ontology_integrity` passes only when:

1. required JSONL files parse as object-per-line registries
2. registry IDs are unique
3. claim, evidence, document, entity, and segment references resolve
4. lifecycle pairs are valid
5. accepted claims have human review metadata and supporting evidence
6. certified derived edges reference accepted claims; draft projections remain
   marked draft and non-canonical

This gate validates integrity and provenance shape. It does not decide whether a
semantic claim is true.
