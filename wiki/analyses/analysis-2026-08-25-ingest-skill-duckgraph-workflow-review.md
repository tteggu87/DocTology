---
title: "LLM Wiki Ontology Ingest Skill DuckGraph-Style Redesign Review"
type: analysis
status: active
created: 2026-08-25
updated: 2026-08-25
tags:
  - doctology
  - llm-wiki-ontology-ingest
  - duckgraph
  - workflow-gate
  - controlled-improvement
sources: []
canonical_sources:
  - .agents/skills/llm-wiki-ontology-ingest/SKILL.md
  - .agents/skills/llm-wiki-bootstrap/SKILL.md
  - .agents/skills/llm-wiki-bootstrap/scripts/wiki_workflow.py
  - .agents/skills/llm-wiki-bootstrap/scripts/pipeline_check.py
  - .agents/skills/llm-wiki-bootstrap/scripts/wiki_batch.py
  - .agents/skills/lightweight-ontology-core/SKILL.md
  - ../duckcrab/.agents/skills/duckgraph/SKILL.md
  - ../duckcrab/docs/ADR_AUTOMATIC_ONTOLOGY_RUN_OBSERVATION_AND_FINALIZATION_GATE.md
  - ../duckcrab/docs/CONTROLLED_SELF_IMPROVEMENT_IMPLEMENTATION_PLAN.md
assumptions:
  - "The ingest skill should remain reusable across bootstrapped repositories."
unresolved_conflicts: []
---

# LLM Wiki Ontology Ingest Skill DuckGraph-Style Redesign Review

## Verdict

The current ingest skill has substantial overlap with the generated `AGENTS.md`, and its value has declined as the bootstrap runtime matured. It should not be deleted. It should be repositioned from a duplicated ingest recipe into a thin capability-aware operator that proposes a plan, drives the repository-owned gates, repairs bounded failures, and reports an honest terminal posture.

A DuckGraph-style proposal and repair loop is appropriate. A full DuckGraph controlled self-improvement system is currently over-engineering.

## Confirmed Overlap And Drift

The generated repository contract already owns:

- source registration and wiki projection rules
- ontology/wiki truth priority
- semantic no-fallback behavior
- fixed per-source procedure stages
- strict pending/failure checks
- immutable batch planning, one writer, corpus fingerprinting, and representative-question certification
- completion and stale-state rules

The ingest skill repeats most of the editorial and ontology workflow. It does not currently mention `wiki_workflow.py`, `wiki_batch.py`, `pipeline_check.py --strict`, or corpus certification. It also presents `llm_full_ingest.py --apply` as the normal route, while the default `llm-first-ontology` bootstrap centers `llm_compile_source.py`, proposal review, and the generated gate scripts and does not generate that full-ingest runner.

The remaining unique value is activation and orchestration across repositories: detect the profile, choose the available semantic owner and runner, translate blockers into the next action, and produce a consistent completion report.

## Recommended Ownership Boundary

```text
llm-wiki-bootstrap
  -> generates AGENTS.md, contracts, scripts, validators, and state layout

llm-wiki-ontology-ingest
  -> discovers capabilities, proposes the run plan, calls repo-owned tools,
     repairs bounded blockers, and refuses unsupported completion claims

lightweight-ontology-core
  -> owns ontology schemas, canonical JSONL integrity, segments, evidence,
     derived edges, and low-level ontology validation
```

The ingest skill must not ship a second workflow runtime or duplicate repository policy. The repository-local runtime remains authoritative.

## DuckGraph-Lite Workflow

### 1. Inspect and route

- Read `AGENTS.md`, index, log, profile contracts, and source state.
- Detect available scripts and helper-model configuration.
- Classify the request as single-source, bounded multi-source, or corpus batch.
- Select one semantic owner: ambient chat agent, configured helper LLM, or explicit human handoff. Never silently substitute another owner.

### 2. Propose a frozen plan

Present:

- source set and hashes
- selected execution lane
- expected wiki and ontology outputs
- single-source run or batch mode
- review/promotion boundary
- required structural and representative-question gates
- conditions that will end as `partial` or `blocked`

Reuse `wiki_workflow` run state and `wiki_batch` manifests. Do not add another plan ledger.

### 3. Execute through repository-owned gates

- Start the source run before semantic mutation.
- Use the local compile/full-ingest/manual-agent path that actually exists.
- Keep proposed ontology truth review-gated.
- For batches, stage drafts and serialize canonical writes.
- Finalize only after strict checks and the latest-state review pass.

### 4. Bounded repair loop

Read structured blocker codes and execute only the smallest missing or stale step. Separate owners:

- semantic failure -> same semantic owner retry or honest pending
- structural failure -> deterministic repair and revalidation
- stale fingerprint -> repeat review/certification only
- approval boundary -> stop for human decision
- missing capability -> blocked, no fallback success

Cap automatic repair attempts and preserve idempotent source/page identities.

### 5. Terminal report

Return exactly one posture: `ready`, `partial`, `not_ready`, or `blocked`, plus changed files, proposed/accepted state, evidence gaps, gate results, and the smallest next action.

## Runtime Enforcement Boundary

DuckGraph can intercept governed MCP writes at one common adapter boundary. DocTology permits ordinary filesystem edits by the ambient agent. Therefore an exact copy of DuckGraph's observer cannot fully prevent direct wiki writes without forcing all edits through a new writer API.

The appropriate current guarantee is completion enforcement:

- runners should automatically create and update procedure evidence where possible;
- batch apply remains the only certified multi-source canonical writer;
- direct edits may occur, but completion or corpus certification fails when required evidence is missing or stale.

Creating a filesystem daemon, universal write proxy, or mandatory MCP layer would damage DocTology's terminal-agent simplicity and is not justified now.

## Improvement Loop Assessment

### Appropriate now

- same-run blocker diagnosis and bounded repair
- stable failure codes and recurrence fingerprints
- proposal-only improvement artifacts after the same failure recurs across independent runs
- exact binding to skill/runtime digest and source run references
- human-reviewed changes to the ingest skill, templates, or gates
- tests using frozen public fixtures and regression cases

### Appropriate later, after evidence

- held-out baseline versus candidate evaluation
- low-risk canary for project-local references or templates
- automatic rollback with exact snapshots

### Over-engineering now

- automatic editing of root `SKILL.md`, generated `AGENTS.md`, or gate runtime
- automatic acceptance of ontology or wiki truth
- background daemon or scheduler
- autonomous runtime coding loop, worktree candidates, or automatic merge
- hidden-corpus evaluation that risks copying private raw content into improvement artifacts
- a second Run Review/EventStore parallel to existing wiki run and batch state

## Minimal Improvement Evidence Contract

An initial proposal-only loop needs only bounded metadata:

- failure code and stage
- distinct run IDs and run-state fingerprints
- skill/runtime contract digest
- affected component owner: skill, template, gate, runner, or corpus-specific content
- proposed change scope and allowed paths
- expected regression tests
- no raw source text, generated claims, private questions, or credentials

A non-critical one-run failure remains a local repair. A reusable skill improvement candidate should require recurrence across at least three independent runs or an equivalent explicitly critical invariant failure. Canonical content errors remain corpus repair, not skill-edit evidence.

## Implementation Priority

1. Rewrite the ingest skill around capability detection, planning, gate orchestration, and bounded repair.
2. Remove the unconditional `llm_full_ingest.py` happy path; route to the actual repo-local lane.
3. Add contract tests proving the skill names the source and batch gates and respects the local profile.
4. Integrate procedure observation directly into canonical runners where practical so agents do not manually manufacture receipts.
5. Add stable failure fingerprints and proposal-only repeated-failure reports.
6. Defer held-out auto-canary and rollback until real repeated failures justify them.

## Applicability Judgment

| Candidate | Judgment |
| --- | --- |
| Workflow proposal before execution | Strong fit |
| Runtime-gated completion and recovery | Strong fit; mostly already available |
| Single front-door operator UX | Strong fit |
| Bounded same-run repair loop | Strong fit |
| Repeated-failure proposal-only learning | Reasonable next phase |
| Held-out evaluation | Conditional; needs good fixtures |
| Automatic canary/rollback | Premature |
| Runtime self-modification | Over-engineering |

## Final Decision

Keep the skill, but change its product role. The best target is not “DuckGraph copied into DocTology.” It is “DuckGraph's plan–observe–repair–certify discipline applied through the LLM Wiki's existing file-native gates, with proposal-only learning and no automatic truth or runtime mutation.”

## Follow-up: Should Lightweight Ontology Core Be Merged?

Merge the normal user experience and active skill surface, while preserving the
retired implementation packages as archives.

- `llm-wiki-loop` is the single front door for ordinary source work and carries
  the minimum ontology invariants needed to finish a run.
- `pipeline_check.py` owns the profile-aware `ontology_integrity` gate inside
  the same source and batch workflow.
- `lightweight-ontology-core` and `lg-ontology` are no longer active skills.
  Their scripts, fixtures, templates, packs, and references remain recoverable
  under `archive/skills/`.
- The loop does not absorb optional graph, Chroma, DuckDB, or pack machinery;
  those remain archived until a new product need justifies reactivation.

The practical product shape is one public workflow without skill chaining:

```text
user -> llm-wiki-loop
          -> ontology build/validate when supported
          -> wiki projection
          -> source procedure gate
          -> batch/corpus certification when applicable
```

Because DocTology's active product path is now wiki-first and no independent
non-wiki ontology workflow is being maintained, archive the standalone core
skill instead of keeping it as a second discovery target. Preserve its package
for recovery, while the ordinary documentation exposes only the wiki loop.

## Implementation Result: One Wiki Loop

Implemented on 2026-08-25 with a stronger consolidation than the initial
follow-up suggested:

- renamed the active source-growth skill to `llm-wiki-loop`
- embedded the minimum ontology lifecycle, evidence, segment, and derived-edge
  contract as a routed reference inside the loop
- added profile-aware `ontology_integrity` validation to the existing
  `pipeline_check.py` source and batch gate
- archived `lightweight-ontology-core` and `lg-ontology` outside the active
  skill directory while preserving their scripts, templates, fixtures, packs,
  and references
- removed the three retired global skill installs from active discovery and
  installed the new loop

This makes bootstrap plus wiki loop the normal product flow. The archived
packages are recovery material, not chained runtime dependencies.

This extends [[analysis-2026-08-24-doctology-duckcrab-gate-validation]], [[analysis-2026-08-24-doctology-gate-implementation-plan]], and [[analysis-2026-06-01-doctology-better-evolution-options]].

## Reading Path

Pages read in traversal order: [[index]] → [[analysis-2026-08-24-doctology-gate-implementation-plan]] → [[analysis-2026-08-24-doctology-duckcrab-gate-validation]] → [[analysis-2026-06-01-doctology-better-evolution-options]] → [[analysis-2026-06-01-doctology-profile-evolution-strategy]] → [[analysis-2026-08-24-repo-docs-vs-wiki-gate-architecture]] → [[log]].
