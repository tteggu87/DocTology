---
name: llm-wiki-loop
description: Grow and certify an existing wiki-only Obsidian-first LLM Wiki from raw sources through planning, semantic synthesis, wiki projection, procedure gates, batch certification, bounded repair, and proposal-only improvement. Use for new source ingest, corpus builds, or repeated wiki growth; do not use to scaffold a new workspace, operate legacy ontology registries, or handle chat-only lookup with no wiki mutation.
---

# LLM Wiki Loop

Use this as the single public workflow for turning raw sources into a useful,
validated LLM Wiki. This public loop has one capability lane: `wiki-only`.
SQLite retrieval may be enabled or disabled, but it remains derived and never
changes the truth or completion boundary.

The target repository owns canonical Markdown, its local conventions, and
durable run/receipt state. This skill owns the executable procedure, batch, and
structural-check runtime. It runs that runtime from this skill directory with
`--repo-root`; it never installs, overwrites, or deletes target-repository
scripts.

Resolve `SKILL_DIR` to the directory containing this loaded `SKILL.md`. Always
invoke `"<SKILL_DIR>/scripts/wiki_loop.py"` explicitly, regardless of the
current working directory. Never look for or execute `scripts/wiki_loop.py`
inside the target repository, and never assume the current working directory is
the skill directory. This rule applies equally to a project-local skill and an
installed global skill.

`llm-wiki-bootstrap` creates the base `raw/`/`wiki/` workspace and optional
SQLite retrieval. This loop can then operate that workspace or any compatible
existing wiki-only repository.

Do not create a second workflow ledger or silently replace a missing semantic
judgment owner.

## Coverage Contract

Treat ordinary requests such as "ingest these files" or "turn these sources
into a wiki" as `coverage_mode=full`. Use `summary` only when the user explicitly
asks for a summary, overview, or reduced treatment. Full coverage preserves
information, not every original sentence.

For every source, account for each Markdown heading or bounded chunk. Preserve
definitions, facts, numbers, conditions, examples, claims, evidence,
exceptions, uncertainty, contradictions, and open questions. Map each unit to a
wiki page/section or mark it omitted with a concrete reason. Never compress an
unread remainder into a confident summary.

Write one applied receipt under `wiki/_meta/ingest_reports/` using this skill's
`assets/coverage_receipt_template.md`. A full run is not `ready` unless the
receipt matches the source hash, the projected/omitted/deferred counts equal the
total, and deferred is zero. If context or judgment runs out, keep the work
`partial`, `not_ready`, or `blocked` and resume in another bounded batch.

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
Run this skill's deterministic preflight first:

```bash
python3 "<SKILL_DIR>/scripts/wiki_loop.py" --repo-root <target-repo> preflight
```

Before reading runtime code, use the public CLI help when command details are
needed. Lane and nested help work without a valid target repository:

```bash
python3 "<SKILL_DIR>/scripts/wiki_loop.py" workflow --help
python3 "<SKILL_DIR>/scripts/wiki_loop.py" workflow start --help
python3 "<SKILL_DIR>/scripts/wiki_loop.py" batch --help
python3 "<SKILL_DIR>/scripts/wiki_loop.py" check --help
```

It verifies the target's `AGENTS.md`, `raw/`, `wiki/`, wiki-only boundary, and
optional SQLite posture. It may report legacy repo-local gate scripts, but this
loop never executes or modifies them. Use only this skill's `wiki_loop.py`
runtime entrypoint for procedure, batch, and structural gate commands.
When `scripts/raw_retrieval.py` exists, use its status/rebuild/search commands as
an optional routing aid for large raw corpora. Its `tree`, `ancestors`, and
`subtree` commands may provide heading paths or bounded context when helpful.
Reopen the returned canonical raw byte ranges before synthesis; the index is
not evidence or a substitute for source reading. Structure reads never rebuild
implicitly, so follow explicit rebuild guidance or read Markdown directly when
they report `state: stale`.

### 2. Confirm The Wiki-Only Contract

Confirm from repo-local `AGENTS.md` and preflight that:

- Markdown under `wiki/` is the complete maintained knowledge truth surface
- `llm-wiki-loop` owns the deterministic gates and can operate this target
- SQLite is either `on` or `off`; both are valid and neither changes canonical
  truth

Do not infer another product lane from source filenames, keywords, legacy
directories, retrieval output, or YAML. A failed preflight makes the run
`not_ready`; it does not authorize a prose checklist or an improvised
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
- coverage mode (`full` by default), source-unit inventory strategy, and receipt path

For a single source, start the skill runtime before mutation and reuse
`state/wiki_runs/`:

```bash
python3 "<SKILL_DIR>/scripts/wiki_loop.py" --repo-root <target-repo> workflow start \
  --workflow ingest --source raw/inbox/<source>
```

Record the fixed stages in order. The semantic plan must precede mutation, and
final review must bind to the latest mutation fingerprint. Use the default
`--coverage-mode full`; pass `summary` only for explicit summary requests.

For a batch, use `wiki_loop.py ... batch plan` to freeze the manifest and reuse
`state/wiki_batches/`. Worker drafts stay in the batch draft area; exactly one
writer may apply canonical files. Start and link every non-deferred source run,
record exactly the three pre-mutation stages through `semantic_plan_frozen`, and
then stop those runs while workers prepare drafts. Do not complete one source
run and mutate the wiki for the next source. Freeze and tailor
`wiki/_meta/representative_questions.json` before `batch plan`; adding or
changing that canonical contract after planning intentionally stales the batch.

### 4. Register The Source Boundary

Resolve or create source identity without modifying `raw/`.

Search the wiki first for existing coverage and affected pages. If wiki lexical
results are empty, `wiki_retrieval.py search --raw-fallback` may consult the
separate raw lane. Use direct `raw_retrieval.py search` when planning coverage,
checking thin wiki pages, or verifying exact source facts. Keep the two result
lanes separate; never fuse their scores. If SQLite or the raw index is off,
continue with canonical Markdown discovery instead of blocking the wiki loop.

Use the repository's source-registration command when needed, remembering that
registration is not semantic synthesis. Create or refresh the source page,
preserve provenance and uncertainty, and keep raw contents immutable. Do not
claim ontology-backed completion or create a parallel canonical store.

The semantic owner may use heading node paths, ancestors, or subtrees only when
they help plan or recover source context. Reopen canonical Markdown before any
synthesis. If SQLite is off, unavailable, or stale, fall back to direct Markdown
reading without weakening the run. Structure nodes and tree leaves are not
source units, do not create a tree coverage ledger, and do not replace the
existing heading/bounded-chunk inventory or applied coverage receipt.

### 5. Project Into The Wiki

Update the source page and every clearly affected durable page. Prefer extending
existing scope over creating duplicates for weak or passing mentions. Preserve
uncertainty and contradictions and cite the source page from claim-heavy pages.

For full coverage, work through the frozen source-unit inventory in bounded
batches and update the ingest receipt as units are projected or intentionally
omitted. A concise overview may lead the source page, but it never substitutes
for unit accounting and affected-page projection.

Refresh `wiki/_meta/index.md` and append `wiki/_meta/log.md` after meaningful
work.

### 6. Validate The Latest State

Run the skill runtime's structural gate:

```bash
python3 "<SKILL_DIR>/scripts/wiki_loop.py" --repo-root <target-repo> check \
  --source raw/inbox/<source>
```

For the active wiki-only contract, its `ontology_integrity` field must be
`not_applicable`; this explicit result proves the gate did not silently
introduce or depend on ontology truth. An ontology-required result signals an
incompatible legacy contract and keeps this loop `not_ready`.

Complete the procedure run only after structural validation and final review
both bind to the latest state. Any later relevant mutation makes those receipts
stale.

Reference the applied ingest receipt in `final_review_completed`. Do not use
`ready` when its source hash is stale, counts do not balance, or deferred units
remain.

### 7. Certify A Batch

For a batch, require:

1. every non-deferred source has a completed current source run
2. `wiki_loop.py ... check --strict --batch <manifest>` passes
3. the one-writer apply event covers canonical mutations
4. required representative-question receipts match the current corpus
5. the final corpus fingerprint is certified after the last mutation

Use the snapshot-seal path for multi-source work. After the one writer applies
the complete merged draft, record all required representative-question
receipts against its result fingerprint, then seal once:

```bash
python3 "<SKILL_DIR>/scripts/wiki_loop.py" --repo-root <target-repo> batch seal \
  --batch <batch-id> --reviewer <reviewer-id> \
  --review-ref wiki/sources/<reviewed-page>.md
```

`batch seal` verifies that no canonical file changed after the writer apply,
requires every full-mode source's applied coverage receipt, writes one bounded
`state/wiki_batches/<batch-id>/final_review.json`, binds all linked source runs
to the same batch corpus fingerprint, refreshes optional retrieval at most once,
and immediately certifies the batch. Seal does not mutate `wiki/`. A missing or
stale question receipt, review reference, source receipt, staged file, source
run, or corpus fingerprint fails closed before certification.

`batch certify` independently enforces this boundary: more than one
non-deferred source requires a current seal event covering exactly those source
runs. The legacy direct-certification path remains valid for a single
non-deferred source.

Use `batch --help` to recover the complete multi-source command order at any
execution boundary. Use `batch status --batch <batch-id>` after interruption or
handoff; its deterministic `next_action` is advisory routing derived from the
current manifest (`link_runs_and_stage_drafts`, `apply_once`,
`complete_source_then_certify`, `record_questions_then_seal`, `resume_seal`,
`done`, `create_new_batch`, or `inspect_blockers`). It never executes the action
or weakens a gate.

When the batch id is unknown, use `batch list` or `batch list --active-only` to
discover recent manifests. Listing is intentionally lightweight: it does not
hash the corpus and reports `freshness: unchecked` plus `next_action:
run_status`. Always run exact `batch status --batch <batch-id>` before acting on
a listed batch. An invalid manifest is returned as `status: invalid` with
`next_action: inspect_manifest` instead of hiding the batch or failing the whole
listing.

If `wiki/_meta/representative_questions.json` is absent, create its target-local
question contract from this skill's `assets/representative_questions_template.json`
and tailor it to the corpus before `batch plan`. Do not leave the placeholder
text as evidence.

Do not replace a missing gate with prose or a checklist and call the batch
ready.

### 8. Repair From Structured Blockers

Make the smallest targeted repair, then rerun the same gate. Examples include
completing missing pre-mutation source stages, resolving a conflicting draft
before the single writer applies it, repairing broken evidence links, creating
a new batch after post-apply mutation, or refreshing a stale question receipt.

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

## Application Integration

This skill owns synthesis procedure, coverage, batch state, and certification,
not a web application. DocTology may call this skill through its own runtime
adapter, but the skill remains independently installable and executable.
Application chat, HTTP, browser UI, launchers, and source-worker supervision
are not distributed with this skill. External callers must use these same
gates; a prepared draft or successful process exit never certifies a wiki.

## Completion Posture

Return exactly one posture:

- `ready`: every required semantic, structural, procedure, review, and batch
  gate passes against the latest state
- `partial`: useful artifacts exist, but an explicitly deferred optional part remains
- `not_ready`: required work or current evidence is missing, stale, or invalid
- `blocked`: completion requires unavailable judgment, new authority, or an external change

Report the confirmed wiki-only contract, source set, wiki changes, SQLite
posture, structural gate and explicit `ontology_integrity: not_applicable`
result, runtime version and contract digest, final-review freshness, batch
certification when applicable, blocker codes, uncertainties, and changed files.

For target-write and version details, read
[the loop runtime contract](references/runtime-contract.md).
