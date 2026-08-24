---
name: repo-docs-intelligence-bootstrap
description: Use when a repository needs one lightweight repository memory profile that evolves with the codebase to reduce drift, prevent structural mistakes, and keep current repository truth plus durable working context explicit. Trigger for requests to refresh current-state or architecture docs from live code, classify or archive older docs, create or update a root AGENTS.md, introduce or maintain minimal glossary/manifests/handlers/policies/schemas/capabilities, or preserve analysis/plans/reviews in a small wiki memory layer without rewriting the runtime.
---

# Repo Docs + Intelligence Bootstrap

Use this skill when a repository has grown through experiments and now needs one lightweight docs, intelligence, agent-guidance, and wiki-memory profile to grow alongside the implementation.
Bootstrap is only the starting point; the real goal is ongoing alignment that keeps repository truth explicit, preserves why decisions were made, reduces drift, and prevents repeated structural mistakes.

## Use This Skill For

- refreshing repository docs so they match the live codebase
- reorganizing a messy or transitional docs tree around current vs legacy truth
- archiving or classifying superseded docs instead of silently deleting them
- creating or updating a root `AGENTS.md` aligned with current repository rules
- introducing or maintaining a minimal schema-first intelligence layer
- keeping glossary/manifests/handlers/policies/schemas/capabilities synchronized as the project evolves
- creating or maintaining a small `wiki/` memory layer for durable analyses, source notes, plans, reviews, and cross-session context

## Do Not Use This Skill For

- isolated bug fixes with no repository-wide documentation or contract impact
- small feature work that does not affect docs, guidance, or canonical contracts
- greenfield architecture design or speculative redesigns
- replacing the runtime with a manifest-driven execution system
- purely local ontology work that does not require repository-wide alignment

## What This Skill Optimizes For

- current documentation that matches real code
- archived or classified older docs instead of silent deletion
- a small schema-first intelligence layer that stays lightweight and useful
- a small wiki memory layer that preserves reasoning, decisions, open questions, and source context across sessions
- thin-wrapper / thick-core guidance
- an `AGENTS.md` file that captures repository working rules
- a repeatable validator-backed self-check loop instead of documentation by hope

This skill is for incremental refactors. Do not turn it into a greenfield rewrite.

## What This Skill Produces

The usual target output is:

- a `docs/README.md` portal
- current-state architecture docs that reflect actual code
- `docs/archive/` for superseded material with a status banner
- optional `docs/reviews/` and `docs/experiments/`
- optional `docs/repo-map/` for entrypoint, module, data-flow, and high-impact symbol reading maps
- a minimal `intelligence/` directory with glossary, manifests, handlers, policies, schemas, and capabilities
- a small `wiki/` memory layer with `_meta/index.md`, `_meta/log.md`, `analyses/`, `sources/`, `concepts/`, and `projects/`
- optional `scripts/pipeline_refresh.py` and `scripts/sync_current_state.py` when the repo needs a single entry and doc-sync path
- a root `AGENTS.md`
- an impact summary describing what changed, what stayed legacy, and what drift still remains
- a validator result summary from the repository-local validator when present, otherwise from this skill's bundled validator

## Unified Profile Contract

This skill has one default profile, not separate entrypoints.
When bootstrapping or refreshing a repository, keep these layers together:

- `AGENTS.md` is the repository operating contract for future agents.
- `docs/` is the current human-readable repository truth.
- `intelligence/` is the machine-readable contract layer when stable actions, datasets, policies, schemas, or capability bindings exist.
- `wiki/` is the durable memory layer for analyses, source notes, plans, reviews, decisions, open questions, and cross-session context.

The layers are intentionally asymmetric:

- code registration points are canonical for what exists and what runs
- `docs/` and active ADRs are canonical for current human-readable repository state
- `intelligence/` is canonical for reusable machine contracts
- `AGENTS.md` is canonical for agent workflow rules
- `wiki/` is derived memory and synthesis; it must cite code, docs, intelligence, or sources for runtime claims and must never override current truth

Do not offer a separate wiki-only mode from this skill.
Create the small wiki memory layer as part of the normal repo-docs profile, but keep it lightweight and subordinate to current docs and intelligence.

## Core Rules

### Search Before Code

Before writing anything new, search for:

- current entrypoints
- existing CLI surfaces
- existing schema SQL
- existing wrappers
- existing docs that can be reused or moved
- existing glossary or policy files
- existing `wiki/_meta/index.md`, `wiki/_meta/log.md`, analyses, plans, reviews, or source pages that explain prior decisions

Prefer reuse and relabeling over inventing a parallel structure.
When entrypoints disagree, verify the canonical surface from live registration points first, such as:

- `pyproject.toml` script entries
- package CLI modules like `pkg/cli.py`
- shell wrappers in `scripts/` or `bin/`
- imports that show whether a wrapper is only delegating to a deeper entrypoint

Do not promote a wrapper, bootstrap script, or operator convenience command to primary truth unless the repository actually treats it as canonical.
Make the official CLI or package-owned command the primary entrypoint when package metadata, imports, or registration points show that it is the real canonical surface.
Keep wrappers visible as a secondary transitional surface when operators still rely on them, but do not document them as the primary or canonical entrypoint.

### Impact Analysis First

Before changing docs, schema contracts, manifests, handlers, or graph/materialization code:

1. identify the live entrypoints
2. identify the current source-of-truth files
3. identify legacy paths that still matter
4. note what the change will replace and what it will not replace

Always leave an impact summary when structural changes are made.
If a legacy path is still imported, delegated to, or required by the current runtime, record it as intentional legacy or transitional support rather than hiding it as dead code.
Treat a still-live legacy path as visible current context even when it is no longer preferred, and never archive it away while it remains on the runtime path.
If a dependency is still live in imports, runtime delegation, or operator workflows, say that it is still live and intentionally legacy instead of implying it has already been removed.

### Schema First

If you are introducing a new behavior, define it in this order:

1. glossary term
2. action or dataset contract
3. policy or SQL contract
4. Python implementation link

Do not add Python orchestration first and invent the contract later.

### Update The Smallest Canonical Truth First

When a concept, action, boundary, or workflow changes, first update the smallest canonical artifact that names it clearly:

- glossary term
- manifest entry
- handler or policy contract
- schema excerpt
- then implementation and docs references

The ontology should stay lightweight. Add only what reduces ambiguity, drift, or repeated mistakes.
If an intelligence layer already exists, preserve current keys, term identities, dataset names, and capability bindings unless code evidence shows they are wrong.
Preserve existing keys and do not rename canonical keys just to make the structure feel cleaner.
Extend the existing layer in place before creating any new parallel manifest, glossary term, or replacement capability name.
Do not recreate the intelligence layer under a second set of keys when the current structure already captures the same meaning.

### Treat Drift As A Bug

Drift is not documentation debt to defer indefinitely.
If code, docs, manifests, policies, or `AGENTS.md` disagree on current truth, resolve the mismatch or explicitly record it in the same task.

### Prefer Living Alignment Over Big Design

Do not wait for a large redesign before correcting terminology, contracts, or repository guidance.
Make small, explicit updates that keep current truth aligned with real implementation.

### Keep Layers Separate

- YAML stores meaning, contracts, and relationships.
- SQL stores schema, canonical shapes, or materialized contract excerpts.
- policy files store gates and rule semantics.
- Python stores execution only.

Do not make YAML into a second programming language.

### Preserve Durable Working Context

For substantial repo-docs work, do not leave the reasoning only in chat.
Use the small wiki memory layer to preserve durable context:

- `wiki/_meta/index.md` lists high-signal pages and current reading routes.
- `wiki/_meta/log.md` records meaningful maintenance events, decisions, and follow-ups.
- `wiki/analyses/` stores reusable design reviews, drift analyses, plan reviews, and decision memos.
- `wiki/sources/` stores source notes for important external or internal material.
- `wiki/concepts/` and `wiki/projects/` store stable concepts and workstreams only when they will be reused.

Every claim-heavy wiki page should include enough provenance for the next agent to verify it.
Recommended frontmatter for analysis pages:

```yaml
---
title: Example Analysis
type: analysis
status: active
as_of_commit: SHORT_SHA
evidence_confidence: medium
canonical_sources:
  - docs/CURRENT_STATE.md
  - intelligence/manifests/actions.yaml
assumptions: []
unresolved_conflicts: []
---
```

Keep evidence confidence distinct from implementation readiness.
If context is thin, write the source register, assumption register, open questions, and recommended next checks instead of inventing certainty.

### Discover Before Generating Guidance

Before adding `AGENTS.md`, docs, repo maps, or wiki memory pages, discover real structure first:

- inspect package metadata, entrypoints, scripts, tests, CI, docs, intelligence, and existing wiki pages
- use LSP, codegraph, `rg`, or language-aware search when available to find symbols, references, central files, and non-obvious boundaries
- treat directory size as a hint, not proof of a separate operating contract
- create nested `AGENTS.md` only when a subdirectory is a distinct operational root with its own build/test/deploy rules or safety constraints

Do not generate many per-directory `AGENTS.md` files just because a tree is large.
If a directory is important but not a separate operating root, document it in `docs/`, `docs/repo-map/`, or `wiki/analyses/` instead.

### Keep Repo Maps Lightweight

Use `docs/repo-map/` when a repository is large enough that future agents need a stable reading route through code.
Repo maps are derived orientation docs, not an automatic source of runtime truth.

Good repo-map inputs:

- package metadata and registered entrypoints
- route, CLI, script, and wrapper registrations
- codegraph, LSP, AST-aware search, or targeted `rg` output
- current docs, intelligence manifests, tests, and live imports

The standard repo-map surface is:

- `docs/repo-map/README.md`
- `docs/repo-map/ENTRYPOINTS.md`
- `docs/repo-map/MODULES.md`
- `docs/repo-map/DATA_FLOW.md`
- `docs/repo-map/SYMBOL_GRAPH.md`

Keep `SYMBOL_GRAPH.md` as a high-impact symbol summary.
Do not claim it is a complete call graph unless the repository has a real generated graph artifact and validator for that artifact.
Do not add a repo-map generator, AST database, or language plugin unless the repo already has that machinery or the user explicitly asks for it.

## Workflow

### 1. Detect The Live Change Surface

Figure out:

- what the real package root is
- whether an official CLI already exists
- where wrappers live
- what the current docs layout looks like
- whether note graph and ontology truth graph are distinct or still mixed
- whether a declarative layer already exists in any form
- which current concepts, datasets, handlers, policies, or schemas are affected
- which legacy paths still matter and why
- which wiki analyses, logs, plans, or review pages already explain related decisions
- whether the repo has complexity that deserves `docs/repo-map/` or whether the small wiki index is enough

### 2. Analyze Impact Before Editing

Before changing code, docs, contracts, handlers, or schemas:

1. identify the live entrypoints
2. identify the current source-of-truth artifacts
3. identify what layers and datasets are affected
4. identify what will remain intentionally legacy
5. identify likely drift points if the change is applied incompletely

### 3. Refresh Current Docs And Classify Existing Material

Create or refresh current docs from code, not memory:

- `docs/README.md`
- `docs/CURRENT_STATE.md`
- `docs/ARCHITECTURE.md`
- `docs/LAYERS.md`
- `docs/SKILLS_INTEGRATION.md`
- `docs/ROADMAP.md`
- `docs/IMPACT_SUMMARY.md`

Then classify older material into:

- `docs/adr/`
- `docs/reviews/`
- `docs/experiments/`
- `docs/archive/`

Do not delete old docs unless they are obviously duplicated and the user explicitly wants deletion.

If a file goes to `docs/archive/`, prepend a status banner:

```md
> Status: Archived
> Source of Truth: No
> Last Updated: YYYY-MM-DD
> Superseded By: `docs/CURRENT_STATE.md`, `docs/ARCHITECTURE.md`
```

Always verify:

- official entrypoints
- package or script ownership
- schema authority
- whether legacy paths still exist
- default graph materializer and retrieval provider behavior
- whether imported legacy helpers are still on the live runtime path

If the repo is transitional, say so directly.
Do not archive, downplay, or relabel a still-imported path as historical just because it is no longer preferred.

### 4. Maintain Repo Map When It Reduces Drift

Create or refresh `docs/repo-map/` when entrypoints, module boundaries, data flow, or high-impact symbols are hard to reconstruct from the main docs.

Use the bundled repo-map templates:

- `assets/docs/repo-map/README.template.md`
- `assets/docs/repo-map/ENTRYPOINTS.template.md`
- `assets/docs/repo-map/MODULES.template.md`
- `assets/docs/repo-map/DATA_FLOW.template.md`
- `assets/docs/repo-map/SYMBOL_GRAPH.template.md`

Minimum repo-map expectations:

- `README.md` links the four focused map files
- `ENTRYPOINTS.md` names canonical entrypoints and secondary wrappers
- `MODULES.md` maps major module responsibilities and still-live legacy modules
- `DATA_FLOW.md` summarizes primary flow, side effects, and gates
- `SYMBOL_GRAPH.md` lists only high-impact symbols with caller/callee/risk notes
- `wiki/_meta/index.md` links `docs/repo-map/README.md` when a repo-map exists

### 5. Maintain Small Wiki Memory

Create or refresh the small wiki memory scaffold:

- `wiki/_meta/index.md`
- `wiki/_meta/log.md`
- `wiki/analyses/`
- `wiki/sources/`
- `wiki/concepts/`
- `wiki/projects/`

Use `wiki/_meta/index.md` as the durable reading map for future sessions.
Use `wiki/_meta/log.md` for chronological maintenance notes.
Use `wiki/analyses/` whenever the task produced reusable reasoning: plan review, architecture decision, drift analysis, refactor rationale, source comparison, or unresolved tradeoff.

Do not write every passing thought into the wiki.
Create a standalone concept, project, or source page when it is stable enough to be useful in a future session, appears across multiple canonical surfaces, or the user explicitly wants it preserved.
If a wiki page discusses current runtime behavior, cite the relevant code, docs, intelligence, or source page.
If a wiki claim conflicts with current docs or intelligence, mark the wiki page stale or open-question and update the canonical surface first.

### 6. Maintain Minimal Intelligence Artifacts

Keep the intelligence layer minimal, current, and useful.
Update or extend only the artifacts needed to express the change clearly and reduce repeated confusion.

The minimum useful set is:

- `intelligence/glossary.yaml`
- `intelligence/manifests/actions.yaml`
- `intelligence/manifests/entities.yaml`
- `intelligence/manifests/datasets.yaml`
- `intelligence/handlers/*.yaml`
- `intelligence/policies/*.yaml`
- `intelligence/schemas/*.sql`
- `intelligence/registry/capabilities.yaml`

Recommended minimum pattern:

- glossary defines canonical terms, aliases, deprecations, and layer meanings
- entities define the named things the repository reasons about
- datasets define canonical data shapes, owners, and freshness expectations
- actions map reusable contracts to current Python callables
- handlers describe event chains and impact flow, even if they are documented-only
- policies describe repository rules, gates, and stopping conditions
- SQL files mirror current contract excerpts and point to the authoritative implementation
- capability bindings connect action keys to Python execution points
- if the repo already has multiple ontology/report scripts, add a single-entry pipeline contract instead of leaving operators to memorize command order

Do not expand the ontology for completeness alone.
Only add artifacts that reduce ambiguity, drift, or implementation mistakes.
When an action already has Python implementation but lacks schema-first context, prefer filling the missing glossary, dataset, policy, or schema contracts around that action instead of inventing a new runtime abstraction.

### 7. Keep Python Linking Minimal

If you add Python support, keep it small.

Good examples:

- a registry loader that reads the intelligence files
- a CLI command that describes actions, capabilities, or handlers
- a helper that resolves action keys to Python callables
- a capability binding that maps an action contract to a pure implementation function

Bad examples:

- replacing the whole runtime with a new manifest executor
- rewriting orchestration around YAML

Good repo-level maintenance additions:

- a thin `pipeline_refresh.py` that calls existing focused scripts in the canonical order
- a thin `sync_current_state.py` that regenerates current-state and impact docs from live artifacts

### 8. Synchronize Code, Docs, Guidance, And Memory In The Same Task

When code changes, update the corresponding docs and intelligence artifacts in the same task.

You must always check whether these files need updates:

- `docs/CURRENT_STATE.md` when behavior, entrypoints, providers, defaults, or runtime flow changes
- `docs/ARCHITECTURE.md` when component roles, data flow, or storage responsibilities change
- `docs/LAYERS.md` when boundaries between Raw/Core/Derived/Search/Graph/Serve change
- `docs/repo-map/ENTRYPOINTS.md` when entrypoints, scripts, routes, or wrappers change and a repo-map exists
- `docs/repo-map/MODULES.md` and `docs/repo-map/SYMBOL_GRAPH.md` when broad module ownership or high-impact symbols change and a repo-map exists
- `docs/SKILLS_INTEGRATION.md` when CLI, skill wrappers, or external entrypoints change
- `docs/IMPACT_SUMMARY.md` and `docs/CURRENT_STATE.md` when ontology/report/graph counts or canonical execution paths change
- `docs/ROADMAP.md` when phased cleanup or deferred drift changes materially
- `docs/IMPACT_SUMMARY.md` when structural changes or validator findings need explicit reporting
- `intelligence/glossary.yaml` when a new domain term or canonical concept is introduced or renamed
- `intelligence/manifests/actions.yaml` when an action is added, removed, renamed, or its contract changes
- `intelligence/manifests/entities.yaml` when the set of named entities changes
- `intelligence/manifests/datasets.yaml` when a canonical dataset or shape changes
- `intelligence/handlers/*.yaml` when event chains or orchestration flow changes
- `intelligence/policies/*.yaml` when gate, policy, or rule semantics change
- `intelligence/registry/capabilities.yaml` when Python capability bindings change
- `intelligence/schemas/*.sql` when canonical schema, views, or materialization logic changes
- `AGENTS.md` when working style, repository rules, or documentation expectations drift from current practice
- `wiki/_meta/index.md` when page inventory or durable reading routes change
- `wiki/_meta/log.md` when meaningful repo-docs maintenance, drift resolution, or plan/review work occurs
- `wiki/analyses/*.md` when the work produced reusable reasoning, decisions, rejected alternatives, unresolved conflicts, or source-backed findings

Do not finish a refactor after updating code only.
If a repo already has current docs or intelligence artifacts, explicitly note which files were checked and intentionally left unchanged so the reader can distinguish stable truth from missed work.

### 9. Add Or Refresh AGENTS.md

Create a root `AGENTS.md` if missing, or update it if drifted.

Include:

- working style
- repository rules
- documentation rules
- definition of done

Keep it aligned with the actual architecture and docs structure.

### 10. Run The Validator As A Self-Check

Run the validator against the repository root after structural changes.
Prefer the repository-local validator when the target repository carries one:

```bash
python scripts/validate_repo_docs_intelligence.py --repo-root <path>
```

If the target repository does not have `scripts/validate_repo_docs_intelligence.py`, use this skill's bundled skill validator from the installed or source skill directory:

```bash
python <repo-docs-intelligence-bootstrap-skill-dir>/scripts/validate_repo_docs_intelligence.py --repo-root <path>
```

If you can derive a changed-file list from the environment, pass it with `--changed-files <path>`.
Do not claim success if the validator reports hard failures.
If the validator reports warnings, surface them under remaining drift or cautions.
If neither the repository-local validator nor the bundled skill validator can be run, say why and fall back to a manual drift check rather than implying validator-clean alignment.

For ordinary inspection, the validator remains advisory: warnings identify likely drift without blocking exploratory work.
For completion, run the hard final gate after the last intended mutation:

```bash
python scripts/validate_repo_docs_intelligence.py \
  --repo-root <path> \
  --changed-files <newline-delimited-path-list> \
  --finalize
```

`--finalize` requires a normalized, duplicate-free changed-file list. In a Git repository, that list must exactly match the current tracked and untracked Git changes, excluding the list itself and the receipt. It also requires every validator warning to be resolved, non-placeholder required sections in `docs/IMPACT_SUMMARY.md`, and every changed path to be named under `## Changed`.

The successful gate writes one state-bound receipt at `state/repo_docs_finalize.json` by default. This is a completion receipt, not a workflow ledger. If any listed file changes after finalization, the receipt becomes stale. Check it without rewriting it with:

```bash
python scripts/validate_repo_docs_intelligence.py \
  --repo-root <path> \
  --changed-files <newline-delimited-path-list> \
  --verify-finalized
```

Do not finalize before the last docs or code mutation, do not hand-edit the receipt, and do not report completion when receipt verification is stale.

Registered Python entrypoints are checked from `pyproject.toml` (`project.scripts`, `project.gui-scripts`, and Poetry scripts). Their targets must resolve, and each registration must remain visible in `docs/CURRENT_STATE.md` plus `docs/repo-map/ENTRYPOINTS.md` when that repo map exists. Keep secondary wrappers visible separately; registration evidence decides the canonical surface.

### 11. Report Drift Status

## Reporting Format

When you finish, report in this order:

1. repository analysis summary
2. docs structure changes
3. intelligence layer changes
4. wiki memory changes
5. legacy vs current split
6. validator summary
7. drift resolved vs remaining
8. cautions
9. next steps

Before ending the task, explicitly report:

1. which docs/intelligence files were updated
2. which were checked but did not need changes
3. which wiki memory files were updated or intentionally left unchanged
4. any remaining drift or legacy exceptions
5. validator errors or warnings, or why the validator was not run

Minimum impact summary content:

- changed files or newly created artifacts
- checked-but-unchanged files
- current vs intentional legacy split
- wiki memory pages created or refreshed
- remaining drift, warnings, or follow-up work
- validator status, including unresolved warnings

## Guardrails

Do not:

- claim a CLI or package surface exists if it does not
- claim wrappers are thin if they still own logic
- claim a wrapper is canonical when package metadata or direct imports show otherwise
- silently hide legacy paths still used in production
- archive or describe a still-imported path as dead, removed, or superseded
- create speculative manifests for runtime features that do not exist
- rename existing action, dataset, entity, glossary, or capability keys without code evidence
- overdesign the intelligence layer
- expand the ontology without a concrete ambiguity, drift, or reuse problem to solve
- ignore validator warnings and still report the repository as fully aligned
- treat `wiki/` as canonical runtime truth
- put a runtime, schema, or entrypoint claim only in `wiki/` without updating or citing the corresponding code, docs, or intelligence surface
- create nested `AGENTS.md` files from directory size alone

## Bundled Templates

Use these bundled files when useful:

- `assets/AGENTS.template.md`
- `assets/docs/README.template.md`
- `assets/docs/CURRENT_STATE.template.md`
- `assets/docs/ARCHITECTURE.template.md`
- `assets/docs/LAYERS.template.md`
- `assets/docs/SKILLS_INTEGRATION.template.md`
- `assets/docs/ROADMAP.template.md`
- `assets/docs/IMPACT_SUMMARY.template.md`
- `assets/docs/repo-map/README.template.md`
- `assets/docs/repo-map/ENTRYPOINTS.template.md`
- `assets/docs/repo-map/MODULES.template.md`
- `assets/docs/repo-map/DATA_FLOW.template.md`
- `assets/docs/repo-map/SYMBOL_GRAPH.template.md`
- `assets/wiki/_meta/index.template.md`
- `assets/wiki/_meta/log.template.md`
- `assets/wiki/analyses/analysis.template.md`
- `assets/intelligence/glossary.template.yaml`
- `assets/intelligence/actions.template.yaml`
- `assets/intelligence/entities.template.yaml`
- `assets/intelligence/datasets.template.yaml`
- `assets/intelligence/handler.template.yaml`
- `assets/intelligence/policy.template.yaml`
- `assets/intelligence/capabilities.template.yaml`
- `assets/intelligence/schema.template.sql`

## Bundled Scripts

- `scripts/validate_repo_docs_intelligence.py`

Adapt the templates to the repo. Do not paste them blindly.
Use the validator as a guardrail, not as a substitute for impact analysis.
