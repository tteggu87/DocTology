---
title: LLM Wiki loop runtime ownership
type: adr
source_of_truth: true
decision_id: ADR-0001
decision_status: accepted
implementation_status: verified
date: 2026-08-27
last_updated: 2026-08-27
superseded_by: null
implementation_plan: null
implementation_refs:
  - ../../.agents/skills/llm-wiki-loop/scripts/wiki_loop.py
  - ../../.agents/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py
implementation_evidence:
  - ../evidence/2026-08-27-loop-runtime-ownership.md
related:
  - ../ARCHITECTURE.md
  - ../SKILLS_INTEGRATION.md
---

# ADR-0001: LLM Wiki loop runtime ownership

## Context

The initial bootstrap evolved from an Obsidian-first `AGENTS.md` scaffold into
a source-ingest harness that copied procedure, batch, and pipeline gate scripts
into every generated vault. `llm-wiki-loop` was added later as an operator for
that copied runtime, so it could not operate as a standalone skill without a
bootstrap-produced script bundle.

## Decision

`llm-wiki-loop` owns the executable gate runtime and runs it from its own skill
directory against `--repo-root`. It does not install, update, or delete runtime
files in a target repository.

The operator resolves the directory of the loaded `SKILL.md` and invokes the
entrypoint from that directory. It never assumes the current working directory
is the skill directory and never searches the target repository for the loop
entrypoint. The entrypoint then resolves sibling runtime modules from its own
file location, so project-local and globally installed copies behave the same.

`llm-wiki-bootstrap` owns the base Obsidian wiki scaffold and optional SQLite
retrieval only. Its generated `AGENTS.md` routes certified raw ingest, full
coverage, batch certification, and `ready` completion to `llm-wiki-loop`.

## Alternatives

- Keep copying gate scripts from bootstrap: preserves target self-containment
  but leaves loop non-standalone and duplicates ownership.
- Let bootstrap import loop assets during scaffold: creates a hidden skill
  dependency and makes bootstrap no longer self-contained.
- Install runtime scripts from loop into each target: preserves local copies but
  adds migration and overwrite policy that is unnecessary for this skill-first
  distribution model.

## Consequences

- A compatible `raw/` + `wiki/` repository can use `llm-wiki-loop` directly.
- Certified ingest requires the loop skill; a missing loop is `not_ready`, not
  permission to claim full coverage or `ready`.
- Target repositories retain only canonical Markdown and bounded run, batch,
  receipt, and optional SQLite state.
- Each run records loop runtime identity and contract digest so a changed
  procedure is detected as stale rather than silently reinterpreted.

## Implementation

Move the procedure, batch, and structural checker into `llm-wiki-loop`, expose
one skill-local `wiki_loop.py --repo-root` entrypoint, and remove copied gate
runtime files and loop-only assets from fresh bootstrap output.

## Verification

See [runtime ownership verification](../evidence/2026-08-27-loop-runtime-ownership.md).
