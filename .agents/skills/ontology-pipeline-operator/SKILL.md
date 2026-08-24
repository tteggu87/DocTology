---
name: ontology-pipeline-operator
description: Operate and maintain a repository that already uses the DocTology stack. Use when refreshing canonical JSONL, wiki projections, reports, graph artifacts, current-state docs, or validators, or when consolidating repeated maintenance commands after `llm-wiki-loop` or repo-docs bootstrap has already produced a working repository. Do not use for new source growth that belongs in the wiki loop.
---

# Ontology Pipeline Operator

Use this skill after a repository already has a DocTology-style structure.
This skill is for operating, refreshing, and regression-checking that structure, not for inventing the ontology from scratch.
It may operate either:

- a repository with existing canonical JSONL, reports, or graph projections
- an Obsidian-first LLM Wiki repository that already uses `llm-wiki-loop`

## Use This Skill For

- rebuilding canonical ontology outputs after source documents change
- keeping reports, graph projection, and docs sync on one canonical execution path
- comparing raw-source mode and jsonl-only mode when report quality is questioned
- catching regressions where graph consumers silently fall back to claims or top-N summaries
- wiring a thin `pipeline_refresh.py` or equivalent single-entry operator command
- wiring a thin docs sync script such as `sync_current_state.py`
- wiring a thin wiki maintenance entry such as `scripts/pipeline_refresh.py` that coordinates ontology refresh plus wiki/meta refresh
- checking whether an LLM Wiki repo is still honoring `raw -> canonical ontology -> wiki -> meta` ordering

## Do Not Use This Skill For

- greenfield repo bootstrap with no ontology layer yet
- new source growth that belongs in `llm-wiki-loop`
- replacing `repo-docs-intelligence-bootstrap` or `llm-wiki-bootstrap`
- turning YAML into a full runtime executor
- promoting graph projection artifacts to canonical truth
- treating source-registration-only CLI commands as if they already perform full ontology-backed ingest

## First Checks

Before editing anything, find:

- the current raw-source SSOT
- the current exploration SSOT
- the current report entrypoint
- the current wiki-facing ingest entrypoint, if the repo is an LLM Wiki
- whether docs sync exists
- whether validators already check relation-family and docs drift
- whether `scripts/llm_wiki.py ingest` or an equivalent local CLI is only source registration
- whether `warehouse/jsonl/` and wiki/meta paths both exist

If the repo already has a canonical single-entry script, prefer strengthening it over inventing a second one.

## Operating Model

Treat these as separate layers:

- raw source truth
- canonical JSONL or equivalent registries
- derived edges
- graph projection
- human-facing wiki pages when the repo is an LLM Wiki
- reports
- current-state / impact docs
- validators
- AGENTS/intelligence contracts

When the corpus is conversational or sequential:

- keep a full-fidelity `messages.jsonl` or equivalent event registry
- do not use `claims` as the speaker/activity SSOT
- preserve full participant coverage in segments

When the repo is an LLM Wiki:

- treat `warehouse/jsonl/` as canonical machine-truth
- treat `wiki/` as human-facing synthesis
- refresh `wiki/_meta/index.md` and `wiki/_meta/log.md` after meaningful pipeline work
- do not let source registration alone masquerade as full ontology-backed ingest

## Recommended Workflow

### 1. Rebuild canonical outputs

Use the repo's existing extraction script or entrypoint first.

### 2. Rebuild wiki projection when applicable

If the repo is an LLM Wiki, run the existing ingest adapter or projection step after canonical outputs update.
Prefer strengthening the repo's existing `llm-wiki-loop` path over inventing a parallel wiki exporter.

### 3. Rebuild derived graph artifacts

Re-materialize derived edges and re-export graph projection.

### 4. Rebuild reports

If both raw and structured modes exist, regenerate both when quality is in doubt.

### 5. Sync docs and meta

Regenerate `CURRENT_STATE`, `IMPACT_SUMMARY`, or their equivalents from live artifacts.
For LLM Wiki repos, also refresh wiki meta pages if the normal ingest flow does not already do so.

### 6. Validate

Run validators last so they check the final current state, not an intermediate one.

For LLM Wiki repos, validation must check the closed ingest lifecycle:

1. raw source registration is present
2. proposed JSONL records report emitted, appended, and skipped_existing counts when configured full ingest applies
3. affected wiki pages were refreshed
4. `wiki/_meta/index.md` and `wiki/_meta/log.md` were refreshed
5. structural validation ran, or the missing validator is reported as an operational risk

Validation checks structure and provenance shape. It must not judge semantic
truth, source relevance, or page type correctness.

Do not report success when validation output is missing. Report missing
validation, stale meta pages, or source-registration-only results under
remaining operational risks.

## What To Add When Missing

If the repo lacks them, consider adding:

- `scripts/pipeline_refresh.py`
- `scripts/sync_current_state.py`
- docs drift validation
- relation-family regression checks
- raw-vs-structured comparison notes for reports
- a thin wiki refresh step that explicitly separates source registration from ontology-backed ingest
- missing `warehouse/jsonl/` or graph projection directories when the contracts already assume them

Keep these additions thin and execution-oriented.

## Report Back With

1. canonical entrypoint used or added
2. wiki/projection/docs entrypoints used or added
3. outputs refreshed
4. validation result
5. raw vs structured quality difference, if relevant
6. remaining operational risks
7. whether any source-registration-only step was intentionally left incomplete
