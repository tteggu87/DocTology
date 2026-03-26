# Chroma Integration

## Purpose

Chroma is an optional semantic retrieval layer for `lightweight-ontology-core`.
It is not a source of truth.

## Layering Rule

Keep the stack separated:

- YAML manifests define vocabulary and rules
- canonical JSONL stores semantic truth
- `segments.jsonl` stores stable text-reference units
- `derived_edges.jsonl` stores regenerated graph projections
- `ontology.duckdb` stores a query mirror
- `vector/chroma/` stores semantic retrieval state

## What Chroma Owns

Chroma should only help with:

- recalling relevant text segments for a question
- finding better evidence candidates before claim authoring
- surfacing linked `entity_ids` or `claim_ids` from nearby segments
- recovering likely text context when wording or aliases vary

## What Chroma Must Not Own

Do not let Chroma decide:

- canonical fact storage
- accepted vs proposed claim status
- contradiction resolution
- derived edge materialization
- source-of-truth precedence

## Segment Registry Rule

`warehouse/jsonl/segments.jsonl` is the bridge between raw document text and semantic retrieval.
Treat it as a stable text-reference registry, not as semantic truth by itself.

Each segment should keep:

- a stable `segment_id`
- the owning `document_id`
- raw segment text
- character offsets into the source document
- a `text_hash`
- a `segmenter_version`

## Freshness Rule

The retrieval index must be rebuildable.
Track index freshness with `vector/chroma/index_meta.json`.

In relaxed validation:

- missing or stale Chroma state is a warning

In strict validation:

- missing or stale Chroma state is an error

This keeps semantic retrieval helpful without allowing it to drift away from canonical registries.
