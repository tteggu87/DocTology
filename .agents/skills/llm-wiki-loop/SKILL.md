---
name: llm-wiki-loop
description: Grow and certify an existing wiki-only Obsidian-first LLM Wiki from raw sources through planning, semantic synthesis, wiki projection, procedure gates, batch certification, bounded repair, and proposal-only improvement. Use for new source ingest, corpus builds, or repeated wiki growth; do not use to scaffold a new workspace, operate legacy ontology registries, or handle chat-only lookup with no wiki mutation.
---

# LLM Wiki Loop

Use this as the single public workflow for turning raw sources into a useful,
validated LLM Wiki. This public loop has one capability lane: `wiki-only`.
SQLite retrieval may be enabled or disabled, but it remains derived and never
changes the truth or completion boundary.

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
- running strict source or corpus completion gates
- repairing stale or incomplete wiki runs from structured blockers

## Do Not Use This Skill For

- scaffolding a new workspace; use `llm-wiki-bootstrap`
- operating canonical ontology JSONL or an archived ontology bootstrap profile;
  use the repository's dedicated operator contract when one exists
- chat-only questions that do not require durable wiki work
- automatic truth approval, schema sprawl, or graph-database platform design
- treating graph, retrieval, DuckDB, or visualization output as canonical truth

## Truth And Judgment Boundaries

Always preserve this priority:

1. `raw/` is immutable source truth.
2. `wiki/` is the maintained synthesis and knowledge truth surface.
3. SQLite retrieval, graph views, analytics, and other projections are derived
   aids that may be deleted and rebuilt.

Do not create or mutate `warehouse/jsonl/` or an `intelligence/` ontology layer
through this skill. If an existing repository contract requires those writes,
this public loop is not the correct operator; report `not_ready` instead of
silently downgrading the repository's contract.

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

Inventory repo-owned scripts and inspect their local help or documentation.
Select only commands whose files exist; never invent a runner or flags.

### 2. Confirm The Wiki-Only Contract

Confirm from repo-local `AGENTS.md` and generated scripts that:

- Markdown under `wiki/` is the complete maintained knowledge truth surface
- `scripts/wiki_workflow.py`, `scripts/wiki_batch.py`, and
  `scripts/pipeline_check.py` own the deterministic gates
- SQLite is either `on` or `off`; both are valid and neither changes canonical
  truth

Do not infer another product lane from source filenames, keywords, legacy
directories, retrieval output, or YAML. Missing required gate scripts make the
run `not_ready`; they do not authorize a prose checklist or an improvised
replacement. If the repository explicitly requires ontology mutation, stop and
route to its dedicated operator contract.

### 3. Freeze The Plan And Open The Gate

Before semantic mutation, present a compact plan with:

- fixed source set and single-source or batch scope
- evidence that the repository uses the active wiki-only contract
- semantic judgment owner and available runner
- expected wiki and meta-page write surfaces
- SQLite posture (`on`, `off`, or `stale`) as non-canonical operational state
- validation, final-review, and certification commands
- conditions that will end as `partial`, `not_ready`, or `blocked`

For a single source, start `scripts/wiki_workflow.py` before mutation and reuse
`state/wiki_runs/`. Record the fixed stages in order. The semantic plan must
precede mutation, and final review must bind to the latest mutation fingerprint.

For a batch, use `scripts/wiki_batch.py` to freeze the manifest and reuse
`state/wiki_batches/`. Worker drafts stay in the batch draft area; exactly one
writer may apply canonical files.

### 4. Register The Source Boundary

Resolve or create source identity without modifying `raw/`.

Use the repository's source-registration command when needed, remembering that
registration is not semantic synthesis. Create or refresh the source page,
preserve provenance and uncertainty, and keep raw contents immutable. Do not
claim ontology-backed completion or create a parallel canonical store.

### 5. Project Into The Wiki

Update the source page and every clearly affected durable page. Prefer extending
existing scope over creating duplicates for weak or passing mentions. Preserve
uncertainty and contradictions and cite the source page from claim-heavy pages.

Refresh `wiki/_meta/index.md` and append `wiki/_meta/log.md` after meaningful
work.

### 6. Validate The Latest State

Run the repository's structural pipeline gate. For the active wiki-only
contract, its `ontology_integrity` field must be `not_applicable`; this explicit
result proves the gate did not silently introduce or depend on ontology truth.
An ontology-required result signals an incompatible legacy contract and keeps
this loop `not_ready`.

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
source-scope change, or edits to `raw/`. Never invent another product lane or
relax a gate to manufacture success.

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

- `ready`: every required semantic, structural, procedure, review, and batch
  gate passes against the latest state
- `partial`: useful artifacts exist, but an explicitly deferred optional part remains
- `not_ready`: required work or current evidence is missing, stale, or invalid
- `blocked`: completion requires unavailable judgment, new authority, or an external change

Report the confirmed wiki-only contract, source set, wiki changes, SQLite
posture, structural gate and explicit `ontology_integrity: not_applicable`
result, final-review freshness, batch certification when applicable, blocker
codes, uncertainties, and changed files.
