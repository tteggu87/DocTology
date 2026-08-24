---
name: llm-wiki-ontology-ingest
description: Operate source ingest in an existing Obsidian-first LLM Wiki by detecting its repo-owned capabilities, selecting an available ingest lane, and preserving closed-pipeline and semantic no-fallback guarantees. Use for raw source ingest or refresh; do not use to scaffold a new repo or redesign ontology schemas.
---

# LLM Wiki Ontology Ingest

## Overview

This is the capability-aware ingest operator for an existing LLM Wiki.

Use it when the repository already has:

- `raw/`
- `wiki/`
- repo-local `AGENTS.md`
- optionally `warehouse/jsonl/`, `intelligence/`, and repo-owned ingest scripts

Responsibility is deliberately split:

- `llm-wiki-bootstrap` and the target repo's `AGENTS.md` own workspace contracts and runtime files.
- this skill inspects those capabilities, selects an available lane, and orchestrates the ingest.
- `lightweight-ontology-core` owns reusable ontology truth and provenance conventions.

Do not copy bootstrap contracts into the target repo or invent a second runtime.
It should feel simple to the human:

1. put a source in `raw/inbox/`
2. run ingest
3. ask questions from the improved wiki

Internally, this skill should:

1. honor the repo-local `AGENTS.md`
2. detect the repo's actual capability lane
3. select only repo-owned commands that exist
4. apply the lane's truth and review boundaries
5. refresh `wiki/_meta/index.md` and `wiki/_meta/log.md`

This skill does not require a top-level Hermes-style `SCHEMA.md`.
Repo-local `AGENTS.md` remains the governing contract.

## Use This Skill For

- ingesting a new raw source into an existing LLM Wiki repo
- updating the wiki with ontology-backed provenance when that capability exists
- wiki-only ingest when the repo has no ontology capability
- refreshing source, people, concept, entity, project, and analysis pages after new evidence arrives
- running the repeated source-processing workflow in ontology-backed LLM Wiki repos

## Do Not Use This Skill For

- scaffolding a brand-new repo from scratch
- repo-only docs cleanup with no source ingest
- ontology schema design or low-level validator debugging in isolation
- answering a question when no new source ingest is needed

For new repo setup, use [`llm-wiki-bootstrap`](../llm-wiki-bootstrap/SKILL.md).
For lower-level ontology work, use [`lightweight-ontology-core`](../lightweight-ontology-core/SKILL.md) directly.

## Inputs

- one or more new sources under `raw/inbox/`
- repo-local operating contract from `AGENTS.md`
- when present:
  - `intelligence/glossary.yaml`
  - `intelligence/manifests/datasets.yaml`
  - `intelligence/manifests/actions.yaml`

## Expected Outputs

Possible ontology outputs, only for lanes that define them:

- `warehouse/jsonl/proposed_entities.jsonl`
- `warehouse/jsonl/proposed_claims.jsonl`
- `warehouse/jsonl/proposed_evidence.jsonl`
- optional `warehouse/jsonl/proposed_relations.jsonl`
- accepted/canonical registries only after explicit review or a repo-specific promotion workflow

Wiki outputs:

- `wiki/sources/...`
- affected `wiki/people/...`
- affected `wiki/concepts/...`
- affected `wiki/entities/...`
- affected `wiki/projects/...`
- optional `wiki/analyses/...` when the ingest naturally produces a durable synthesis memo
- refreshed `wiki/_meta/index.md`
- appended `wiki/_meta/log.md`

## Closed Pipeline Contract

This skill must complete the full ingest lifecycle unless the user explicitly
requests a partial operation.

Required stages:

1. Register source identity.
2. Append applicable proposed JSONL records.
3. Project canonical/source-backed synthesis into wiki pages.
4. Refresh meta surfaces.
5. Validate structural integrity or report why validation could not run.
6. Report changed files, uncertainty, and remaining open questions.

This pipeline closes the lifecycle, not semantic judgment.

Do not replace semantic judgment with deterministic keyword routing. Use
deterministic scripts only for registration, indexing, logging, JSONL
integrity, and structural validation.

Semantic no-fallback rule: if source-page synthesis, affected-page selection,
claim extraction, contradiction handling, or wiki projection requires agent or
configured LLM judgment, unavailable, failed, or invalid judgment must be
reported as failed, partial, or pending. Do not replace it with lexical
diagnostics, retrieval output, graph projection, structural validation,
filename/keyword summaries, or deterministic fallback prose and call semantic
ingest complete. Transport fallback for the same configured LLM request is
allowed; semantic fallback that changes the judgment owner is not.

## Workflow

### 1. Read Local Repo Contracts First

Before doing anything:

1. read repo-root `AGENTS.md`
2. read `wiki/_meta/index.md`
3. read the newest relevant entries in `wiki/_meta/log.md`
4. if present, read only the smallest relevant contract surfaces:
   - `intelligence/contract_index.yaml`
   - `intelligence/policies/semantic_boundary.yaml`
   - `intelligence/policies/proposal_lifecycle.yaml`
   - `intelligence/glossary.yaml`
   - `intelligence/manifests/datasets.yaml`
   - `intelligence/manifests/actions.yaml`

Treat the repo-local contract as authoritative for page style, truth priority, and save behavior.
Treat this as a startup ritual, not an optional nicety.

### 2. Detect Capabilities And Select One Lane

Inspect repo contracts, directories, and executable paths before proposing commands. Do not classify a lane from source filenames, keywords, document content, retrieval results, or YAML field guesses.

Select exactly one available lane:

- **`llm-first-ontology`**: the repo declares a strict semantic boundary or proposal/review lifecycle. Semantic changes remain proposals until the repo-owned review contract accepts them; missing required runtime is a blocker, not permission to choose a weaker lane.
- **`wiki-plus-ontology`**: the repo has canonical ontology registries and ontology-aware ingest conventions, but no strict LLM-first proposal boundary. Update machine truth using `lightweight-ontology-core` conventions, then project source-backed synthesis as the local contract permits.
- **`wiki-only`**: the repo has raw/wiki surfaces but no canonical ontology contract. Complete the source-page and wiki lifecycle without claiming ontology-backed ingest; explicitly report ontology extraction as not applicable or unavailable.

Capability detection selects mechanics, not meaning. Source-page synthesis, affected-page selection, claim extraction, contradiction handling, and promotion still require the judgment owner declared by the repo.

Build an availability list before execution:

1. enumerate relevant repo-owned scripts and inspect their `--help` or local documentation
2. select only commands whose files exist in the target repo
3. do not assume `scripts/llm_full_ingest.py`, `scripts/llm_compile_source.py`, or any legacy runner exists
4. when no full runner exists, orchestrate the repo's available registration, semantic, projection, meta-refresh, and validation surfaces without fabricating a replacement command
5. if a required semantic capability is unavailable, stop that step with `partial`, `pending`, or `failed` status rather than changing lanes silently

### 3. Confirm Source Scope

Work from sources already present in `raw/inbox/`, `raw/processed/`, or `raw/notes/`.
Prefer explicit filenames from the user when possible.

If a source has not been registered into `wiki/sources/` yet, create or refresh the source page stub before deeper synthesis work.
Before creating any new page, check whether the scope already exists so the ingest does not create duplicates for passing mentions or overlapping topics.

Important:

- if the repo documents `scripts/llm_wiki.py ingest` as source registration only, do not present it as full ingest
- use `scripts/llm_full_ingest.py` only when that file exists and the repo contract identifies it as the appropriate lane
- never invent flags; inspect the selected command's local help or documentation first
- repo-owned apply commands must not exceed the mutation and promotion authority granted by `AGENTS.md`

### 4. Freeze The Plan And Open The Repo-Owned Gate

Before semantic mutation, present a compact plan containing:

- selected capability lane and the evidence used to select it
- fixed source set and whether it is a single-source or batch run
- available semantic judgment owner and selected repo-owned runner
- expected canonical and wiki write surfaces
- validation, final-review, and certification commands that actually exist

Do not create a separate skill-owned workflow ledger. Reuse `state/wiki_runs/`
and `state/wiki_batches/` when the repo provides them.

For a single source, start a run with `scripts/wiki_workflow.py` before semantic
mutation. Record the repo-defined stages in order, run structural validation,
and bind final review to the latest mutation fingerprint. A missing or stale
stage leaves the run active or incomplete.

For a large source set, use `scripts/wiki_batch.py` to freeze the manifest and
keep worker output in its draft area. Exactly one writer may apply canonical
files. When the repo provides these gates, require all of the following before
certification:

1. every non-deferred source has a completed source run
2. `scripts/pipeline_check.py --strict --batch <manifest>` passes
3. required representative-question receipts match the current corpus
4. the final corpus fingerprint is certified after the last mutation

Do not weaken a missing gate by substituting a checklist or prose assertion.
If these runtime files are absent, follow the local contract's available
validation path and report that strict procedure or batch certification was
unavailable.

### 5. Build Truth Appropriate To The Lane

For `llm-first-ontology`, use the repo-owned semantic compile/proposal path and preserve human-review boundaries.

For `wiki-plus-ontology`, use [`lightweight-ontology-core`](../lightweight-ontology-core/SKILL.md) concepts and conventions to draft or update ontology truth as allowed by the repo contract.

For `wiki-only`, skip ontology mutation and state clearly that no canonical ontology layer was updated.

For either ontology-capable lane, preserve or create the registries required by its repo contract, commonly:

- document/message registration
- entity registry updates
- claim extraction
- claim-to-evidence links
- stable segment references
- derived edges only as derived outputs

Keep `warehouse/jsonl/...` canonical and machine-oriented.
Do not let wiki summaries become the canonical truth layer.
For automatic ingest, write records as proposed/needs_review unless the user has
explicitly requested and reviewed accepted promotion.

### 6. Project Back Into The Wiki

Once the selected lane's truth or proposal step is complete:

1. update the source page in `wiki/sources/`
2. refresh affected concept, people, entity, project, and timeline pages
3. create thin stubs for important missing pages instead of skipping them
4. preserve uncertainty and contradictions explicitly
5. cite the relevant source page from claim-heavy pages

Keep the wiki human-facing and easy to scan.
Do not dump raw JSONL into markdown pages.
Do not let duplicate or weakly justified pages accumulate when an existing page can be extended instead.

In `llm-first-ontology`, do not apply active semantic page changes automatically when the repo requires a reviewed proposal.

### 7. Refresh Meta Pages

After meaningful ingest work:

1. refresh `wiki/_meta/index.md`
2. append a clear log entry to `wiki/_meta/log.md`

If the ingest changed how the repo should be interpreted, update `AGENTS.md` or a durable analysis page rather than leaving that insight only in chat.

### 8. Repair Only From Gate Evidence

When a gate blocks completion, use its structured blocker to make the smallest
targeted repair, then rerun the same gate. Typical repairs include completing a
missing source run, resolving a conflicting draft before the single writer
applies it, rerunning final review after a mutation, or refreshing a stale
question receipt against the current corpus fingerprint.

Keep this repair loop bounded to three attempts per stable blocker in one run.
Stop earlier when the repair would require new user authority, unavailable
semantic judgment, a source-scope change, or edits to `raw/`. After the bound,
leave the run open and report the blocker; do not change lanes, relax the gate,
or call the ingest complete.

### 9. Learn By Proposal, Never By Self-Modification

Treat one isolated failure as a local repair case. Create a reusable improvement
proposal only when the same stable failure code and affected component recur in
at least three independent runs with the same procedure contract digest. Runs
from one batch count independently only when they have distinct run IDs and
source scopes; repeated retries inside one run count once.

The proposal is advisory and must contain only bounded operational metadata:

- stable failure code and affected component
- distinct run IDs and their shared contract digest
- symptom stated without raw/private source excerpts
- proposed instruction, validator, or test change
- expected tests, scope, risk, and `status: proposed`

Store it only in the review location authorized by the target repo. If the repo
defines no improvement-proposal location, report the candidate in the final
handoff instead of inventing a new state store. A human must review and approve
the proposal before any skill, `AGENTS.md`, policy, validator, or runtime change.
Never include raw source bodies, private excerpts, credentials, or accepted
canonical truth in an improvement proposal.

Do not add automatic canary deployment, rollback machinery, daemon scheduling,
runtime self-modification, automatic gate relaxation, or automatic truth
promotion. Those are separate systems, not ingest completion features.

## User-Facing Routine

The normal human workflow should look like this:

1. scaffold once with [`llm-wiki-bootstrap`](../llm-wiki-bootstrap/SKILL.md)
2. place a source in `raw/inbox/`
3. run this skill so it selects an available repo-owned ingest lane
4. ask a question from the wiki

The human should not need to call `lightweight-ontology-core` directly for normal ingest.
That lower-level skill remains available for advanced tuning, debugging, or operator workflows.

## Completion Posture

Use exactly one final posture:

- `ready`: every required semantic, structural, procedure, review, and batch certification gate passes against the latest state
- `partial`: useful in-scope artifacts exist, but an explicitly identified optional or user-deferred part remains
- `not_ready`: required work or evidence is missing, stale, or invalid and can still be repaired in the current scope
- `blocked`: completion requires unavailable semantic judgment, new authority, or an external state change

The ingest is `ready` only when, for the selected lane:

- source coverage is reflected in `wiki/sources/`
- ontology truth or reviewed proposals are updated when the lane supports them
- affected wiki pages are refreshed or created
- uncertainty is preserved
- `wiki/_meta/index.md` and `wiki/_meta/log.md` reflect the new work
- the completion report distinguishes proposed JSONL emitted, appended, and skipped_existing counts

## Completion Report

Report:

1. Source registered
2. Proposed JSONL records emitted, appended, and skipped_existing
3. Wiki pages updated or created
4. Claims proposed, accepted, disputed, or left pending
5. Evidence coverage
6. Validation result
7. Open questions and uncertainty
8. Files changed
9. Completion posture and any gate blocker codes

## Notes

- Prefer `ingest` language with the user; keep `adapter` or `bridge` as internal mental models only.
- Prefer repo-local `AGENTS.md` over generic habits when they conflict.
- A `wiki-only` lane is a valid capability, not a semantic fallback. Say what is unavailable and do not report the result as completed ontology-backed ingest.
- Keep `warehouse/jsonl/` as canonical truth and treat markdown pages as the human-facing projection layer.
