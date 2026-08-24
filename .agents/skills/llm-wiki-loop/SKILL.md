---
name: llm-wiki-loop
description: Grow and certify an existing Obsidian-first LLM Wiki from raw sources through planning, ontology-aware synthesis, wiki projection, procedure gates, batch certification, bounded repair, and proposal-only improvement. Use for new source ingest, corpus builds, or repeated wiki growth; do not use to scaffold a new workspace or for chat-only lookup with no wiki mutation.
---

# LLM Wiki Loop

Use this as the single public workflow for turning raw sources into a useful,
validated LLM Wiki. The human should not need to select a separate ontology
skill before running the loop.

The target repository owns its contracts and runtime:

- `llm-wiki-bootstrap` creates `AGENTS.md`, scripts, validators, and state layout.
- this skill detects those capabilities, freezes a plan, drives the available
  runtime, repairs bounded blockers, and reports an honest terminal posture.
- repo-local `AGENTS.md` remains authoritative when conventions differ.

Do not create a second workflow ledger or silently replace a missing semantic
judgment owner.

## Use This Skill For

- processing one or more sources under `raw/`
- growing source, concept, entity, person, project, timeline, or analysis pages
- updating canonical ontology registries when the selected profile supports them
- running strict source or corpus completion gates
- repairing stale or incomplete wiki runs from structured blockers

## Do Not Use This Skill For

- scaffolding a new workspace; use `llm-wiki-bootstrap`
- chat-only questions that do not require durable wiki work
- automatic truth approval, schema sprawl, or graph-database platform design
- treating graph, retrieval, DuckDB, or visualization output as canonical truth

## Truth And Judgment Boundaries

Always preserve this priority:

1. `raw/` is immutable source truth.
2. `warehouse/jsonl/` is canonical machine truth when the profile enables it.
3. `wiki/` is the maintained human-facing synthesis layer.
4. retrieval, graph, DuckDB, and other projections are derived aids.

For ontology-capable work, read
[references/ontology-contract.md](references/ontology-contract.md) before
writing registries or validating completion. It contains the minimum claim,
evidence, segment, lifecycle, and derived-edge rules required by this loop.

Semantic no-fallback rule: source synthesis, affected-page selection, claim
extraction, contradiction handling, and wiki projection require the semantic
owner declared by the repository. If that owner is unavailable or invalid,
report `partial`, `not_ready`, or `blocked`. Lexical routing, retrieval output,
graph projection, structural validation, or deterministic summaries cannot
stand in for semantic judgment.

## Workflow

### 1. Inspect The Workspace

Read:

1. repo-root `AGENTS.md`
2. `wiki/_meta/index.md`
3. recent relevant entries in `wiki/_meta/log.md`
4. only the smallest relevant files under `intelligence/`

Inventory repo-owned scripts and inspect their local help or documentation.
Select only commands whose files exist; never invent a runner or flags.

### 2. Select One Capability Lane

- **`llm-first-ontology`**: strict semantic boundary and proposal/review
  lifecycle. Semantic updates remain review-gated until the local contract
  accepts them.
- **`wiki-plus-ontology`**: canonical ontology registries exist without the
  strict LLM-first proposal boundary. Build machine truth and then project it
  to the wiki as the local contract permits.
- **`wiki-only`**: raw and wiki surfaces exist without canonical ontology.
  Complete the wiki lifecycle and report ontology work as `not_applicable`.

Detect the lane from explicit repository contracts and capability files, not
from source filenames, keywords, content, retrieval results, or YAML guesses.
A missing required runtime blocks that lane; it does not authorize silent
downgrade to another lane.

### 3. Freeze The Plan And Open The Gate

Before semantic mutation, present a compact plan with:

- fixed source set and single-source or batch scope
- selected lane and evidence for it
- semantic judgment owner and available runner
- expected JSONL and wiki write surfaces
- validation, final-review, and certification commands
- conditions that will end as `partial`, `not_ready`, or `blocked`

For a single source, start `scripts/wiki_workflow.py` before mutation and reuse
`state/wiki_runs/`. Record the fixed stages in order. The semantic plan must
precede mutation, and final review must bind to the latest mutation fingerprint.

For a batch, use `scripts/wiki_batch.py` to freeze the manifest and reuse
`state/wiki_batches/`. Worker drafts stay in the batch draft area; exactly one
writer may apply canonical files.

### 4. Register And Build Canonical Truth

Resolve or create source identity without modifying `raw/`.

For ontology-capable lanes, create or update the registries declared by the
local contract, commonly:

- `documents.jsonl` and full-fidelity `messages.jsonl` when applicable
- `entities.jsonl`
- `claims.jsonl`
- `claim_evidence.jsonl`
- `segments.jsonl`
- `derived_edges.jsonl`; certified/active edges derive only from accepted truth,
  while any exploratory projection stays explicitly draft

Automatic extraction remains `proposed + needs_review`. Never auto-promote a
claim to accepted truth. Preserve stable evidence and segment references and do
not use presentation summaries as the participant, activity, or provenance
source of truth.

For `wiki-only`, skip ontology mutation and continue without claiming
ontology-backed completion.

### 5. Project Into The Wiki

Update the source page and every clearly affected durable page. Prefer extending
existing scope over creating duplicates for weak or passing mentions. Preserve
uncertainty and contradictions and cite the source page from claim-heavy pages.

Refresh `wiki/_meta/index.md` and append `wiki/_meta/log.md` after meaningful
work. In strict LLM-first workspaces, do not apply active semantic page changes
when the repository requires reviewed proposals.

### 6. Validate The Latest State

Run the repository's structural pipeline gate. In ontology-capable lanes, the
gate must also emit an `ontology_integrity` result over the current canonical
registries. It must reject malformed JSONL, broken claim/evidence/document/
segment references, invalid lifecycle pairs, accepted claims without human
review metadata or supporting evidence, and derived edges sourced from
non-accepted claims.

For `wiki-only`, `ontology_integrity` must be `not_applicable`. Missing ontology
integrity evidence in an ontology-capable lane is `not_ready`, not success.

Complete the procedure run only after structural validation and final review
both bind to the latest state. Any later relevant mutation makes those receipts
stale.

### 7. Certify A Batch

When the repository provides the generated batch runtime, require:

1. every non-deferred source has a completed current source run
2. `scripts/pipeline_check.py --strict --batch <manifest>` passes
3. the one-writer apply event covers canonical mutations
4. required representative-question receipts match the current corpus
5. the final corpus fingerprint is certified after the last mutation

Do not replace a missing gate with prose or a checklist and call the batch
ready.

### 8. Repair From Structured Blockers

Make the smallest targeted repair, then rerun the same gate. Examples include
completing a missing source run, resolving a conflicting draft before the
single writer applies it, repairing broken evidence links, rerunning final
review after mutation, or refreshing a stale question receipt.

Limit automatic repair to three attempts per stable blocker in one run. Stop
earlier when repair needs new user authority, unavailable semantic judgment, a
source-scope change, or edits to `raw/`. Never change lanes or relax a gate to
manufacture success.

### 9. Learn By Proposal Only

Treat an isolated failure as local repair. Propose a reusable improvement only
when the same stable failure and component recur in at least three independent
runs with one procedure contract digest. Retries inside one run count once.

The proposal may contain bounded operational metadata, run IDs, contract digest,
scope, risk, and expected tests. It must not contain raw/private source bodies,
credentials, accepted canonical truth, or automatic approval. Human review is
required before changing a skill, `AGENTS.md`, policy, validator, or runtime.

Do not add automatic canaries, rollback machinery, daemons, runtime
self-modification, gate relaxation, or truth promotion to this loop.

## Completion Posture

Return exactly one posture:

- `ready`: every required semantic, ontology, structural, procedure, review,
  and batch gate passes against the latest state
- `partial`: useful artifacts exist, but an explicitly deferred optional part remains
- `not_ready`: required work or current evidence is missing, stale, or invalid
- `blocked`: completion requires unavailable judgment, new authority, or an external change

Report the selected lane, source set, JSONL and wiki changes, claim lifecycle
counts, evidence coverage, ontology and structural gate results, final-review
freshness, batch certification when applicable, blocker codes, uncertainties,
and changed files.
