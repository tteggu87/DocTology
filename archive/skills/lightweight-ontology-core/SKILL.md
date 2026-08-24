---
name: lightweight-ontology-core
description: Use when documents, notes, research memos, story canon, or repository guidance need to be turned into a lightweight ontology with entities, relations, claims, evidence, segments, and derived edges for provenance-aware reasoning. Trigger for requests to extract structured facts from text, track contradictions or supersession, validate claim/evidence integrity, build stable segment registries, or add semantic retrieval without committing to a full RDF or OWL stack. Do not use this for plain repo docs cleanup, AGENTS sync, or current-state refresh without ontology extraction; use repo-docs-intelligence-bootstrap for that.
---

# Lightweight Ontology Core

Use this skill to build and maintain a lightweight claim-and-evidence ontology layer on top of documents.
The purpose is to improve reasoning quality without turning authoring into a heavyweight graph engineering project.

This skill owns canonical ontology generation.
It does not own repo-specific wiki export or markdown page conventions.
Those belong to downstream adapters.

## Use This Skill For

- extracting entities, relations, claims, and evidence from documents
- building stable text-reference segments for retrieval and provenance
- modeling provenance-aware facts that can later be validated or re-derived
- handling contradictions, supersession, and accepted-vs-proposed claim states
- materializing derived edges from accepted claims
- mirroring canonical JSONL data into DuckDB for analysis or querying
- adding semantic retrieval as a non-canonical recall layer

## Do Not Use This Skill For

- plain repo docs refresh or current-state cleanup with no ontology work
- AGENTS-only or docs-portal-only maintenance
- full RDF/OWL/SPARQL platform design
- automatic semantic contradiction detection beyond explicit v1 rules
- repo-specific wiki projection logic for one markdown vault

## Operating Model

This skill separates:

- ontology definitions in YAML
- canonical extracted facts in JSONL
- canonical text-reference segments in JSONL
- derived graph artifacts in JSONL
- analytical mirrors in DuckDB
- semantic retrieval state in Chroma
- execution and validation in Python

### Source Of Truth Hierarchy

Canonical:

- `intelligence/manifests/relations.yaml`
- `intelligence/manifests/document_types.yaml`
- `warehouse/jsonl/entities.jsonl`
- `warehouse/jsonl/documents.jsonl`
- `warehouse/jsonl/messages.jsonl` when the corpus is a chat log, sequential event stream, or conversation transcript
- `warehouse/jsonl/claims.jsonl`
- `warehouse/jsonl/claim_evidence.jsonl`

Canonical Reference Layer:

- `warehouse/jsonl/segments.jsonl`

Derived:

- `warehouse/jsonl/derived_edges.jsonl`

Mirror:

- `warehouse/ontology.duckdb`

Retrieval:

- `intelligence/retrieval/chroma_collection.yaml`
- `vector/chroma/`

### Template vs Generated Output

Templates live under `assets/...`.
Generated ontology data lives under `intelligence/...`, `warehouse/jsonl/...`, and `vector/chroma/...`.
Do not confuse template locations with generated output paths.

## Adapter Boundary

Keep this core repo-neutral.

This skill should stop at canonical ontology artifacts such as:

- `warehouse/jsonl/entities.jsonl`
- `warehouse/jsonl/documents.jsonl`
- `warehouse/jsonl/messages.jsonl`
- `warehouse/jsonl/claims.jsonl`
- `warehouse/jsonl/claim_evidence.jsonl`
- `warehouse/jsonl/segments.jsonl`
- `warehouse/jsonl/derived_edges.jsonl`

Do not bake repo-local wiki rules into this core.
For example, an Obsidian-first LLM Wiki may want:

- `wiki/sources/...`
- `wiki/people/...`
- `wiki/concepts/...`
- `wiki/projects/...`
- repo-specific `AGENTS.md` behavior

Those are adapter concerns, not ontology-core concerns.

For LLM Wiki repositories, use a downstream ingest adapter such as `llm-wiki-ontology-ingest` to project canonical ontology truth back into markdown pages.

## Claim Lifecycle

Allowed claim `status` values:

- `proposed`
- `accepted`
- `disputed`
- `rejected`
- `superseded`

Allowed `review_state` combinations:

- `proposed + needs_review`
- `accepted + approved`
- `disputed + conflict_open`
- `rejected + rejected`
- `superseded + archived`

Required metadata when `status=accepted`:

- `reviewed_by`
- `reviewed_at`
- `decision_by`
- `decision_at`
- `decision_note`

Rules:

- `accepted` claims must have at least one supporting evidence row
- `accepted` claims must have `review_state=approved`
- `decision_by` must use a human identifier convention such as `human:<id>`
- `asserted_by` may still be `extractor:*` or `human:*`
- `source_segment_id` remains optional for claims in v1
- `claim_evidence.source_segment_id` should resolve to a stable segment when present

## Minimal Relation Model

Start with repo-neutral minimal relations:

- `depends_on`
- `supports`
- `documents`
- `implemented_by`
- `contradicts`
- `supersedes`

Add `exclusive_object` to relation schemas so v1 conflict detection stays explicit and deterministic.
Do not ship fiction-specific defaults like `parent_of` in the base template.

## v1 Contradiction Rules

Treat the following as hard contradiction candidates:

1. accepted claims whose predicate is explicitly `contradicts`
2. accepted claims under relations marked `exclusive_object: true` where the same subject/predicate has overlapping validity with different objects
3. accepted claims with mutually exclusive objects when the relation schema explicitly declares exclusivity

Do not attempt free-form semantic contradiction detection in v1.

## Bundled Assets

Use these templates when useful:

- `assets/docs/ONTOLOGY_OPERATING_MODEL.template.md`
- `assets/intelligence/relations.template.yaml`
- `assets/intelligence/document_types.template.yaml`
- `assets/rules/inference.template.yaml`
- `assets/shapes/core.template.yaml`
- `assets/context/context.template.jsonld`
- `assets/warehouse/entities.template.jsonl`
- `assets/warehouse/documents.template.jsonl`
- `assets/warehouse/claims.template.jsonl`
- `assets/warehouse/claim_evidence.template.jsonl`
- `assets/warehouse/segments.template.jsonl`
- `assets/warehouse/derived_edges.template.jsonl`
- `assets/retrieval/chroma_collection.template.yaml`
- `assets/schemas/warehouse_core.template.sql`

Read these references when you need more detail:

- `references/claim-lifecycle.md`
- `references/chroma-integration.md`
- `references/repo-adapter-boundary.md`

## Bundled Scripts

- `scripts/validate_ontology_graph.py`
- `scripts/build_segments.py`
- `scripts/sync_segments_to_chroma.py`
- `scripts/retrieve_with_chroma.py`
- `scripts/materialize_derived_edges.py`
- `scripts/sync_claims_to_duckdb.py`

## Workflow

### 1. Define The Minimal Vocabulary

Before extracting claims, define:

- relation types in `relations.yaml`
- document types in `document_types.yaml`
- any core constraints needed for v1

Keep the vocabulary small and stable.

### 2. Create Canonical Registries

Create or update:

- `entities.jsonl`
- `documents.jsonl`
- `claims.jsonl`
- `claim_evidence.jsonl`

Treat these JSONL files as canonical fact storage.
If the source is conversational or sequential, also keep a full-fidelity `messages.jsonl` or equivalent event registry.
Do not let `claims.jsonl` or top-N segment summaries become the activity or speaker-discovery source of truth.

### 3. Build Stable Segment References

Generate `segments.jsonl` from registered text documents.
Treat segments as stable text-reference units that bridge documents, evidence, and retrieval.
If the source is a chat or event stream, preserve the full participant set or participant counts in segment metadata.
Do not truncate canonical participant coverage down to presentation-friendly top-N lists.

Run:

```bash
python scripts/build_segments.py --repo-root <path>
```

### 4. Sync Retrieval State When Needed

When semantic retrieval is useful, sync segments into Chroma.
Chroma is only a candidate recall layer.

Run:

```bash
python scripts/sync_segments_to_chroma.py --repo-root <path>
python scripts/retrieve_with_chroma.py --repo-root <path> --query "<text>"
```

Do not treat retrieval results as accepted facts.

### 5. Materialize Derived Edges

Generate `derived_edges.jsonl` only from accepted claims and declared inference rules.
Do not hand-edit derived edges as if they were source truth.
If the corpus includes conversational interaction, preserve interaction edge families explicitly when they are part of the accepted contract,
for example author, mention, reply, and co-occurrence edges.

### 6. Mirror To DuckDB

Mirror canonical JSONL plus derived edges and segments into `ontology.duckdb`.
DuckDB is for querying and analytics, not for editing canonical truth.

### 7. Validate Before Claiming Success

Run:

```bash
python scripts/validate_ontology_graph.py --repo-root <path>
```

Use `--strictness strict` when you want DuckDB or Chroma freshness mismatches to fail.
Do not claim success if canonical integrity, segment linkage, or accepted-claim rules fail.

## Reporting Format

When you finish ontology work, report:

1. vocabulary changes
2. canonical registry changes
3. segment registry changes
4. retrieval sync status
5. derived edge changes
6. mirror sync status
7. validation result
8. contradictions or unresolved disputes
9. next steps

## Guardrails

Do not:

- mark derived edges as canonical
- mark Chroma or its index metadata as canonical
- auto-accept claims without human review metadata
- let `document_types.default_claim_status` default to `accepted`
- silently ignore broken claim/evidence/entity/document links
- silently ignore broken segment/evidence links or stale retrieval state
- broaden the core relation set with domain-specific defaults before an adapter exists
- let reports or downstream tooling regress from full registries back to claim-only fallback for speaker/activity analysis

Use this skill as a reusable ontology core.
Keep repo-specific governance in `repo-docs-intelligence-bootstrap`.
