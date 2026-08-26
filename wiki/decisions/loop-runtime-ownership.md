---
title: LLM Wiki loop runtime ownership
type: decision
source_of_truth: false
status: active
last_updated: 2026-08-27
canonical_decision: ../../docs/adr/ADR-0001-loop-runtime-ownership.md
implementation_status_mirror: verified
evidence_refs:
  - ../../docs/evidence/2026-08-27-loop-runtime-ownership.md
---

# LLM Wiki loop runtime ownership

The certified raw-to-wiki procedure, coverage receipt, batch certification, and
structural checker live inside `llm-wiki-loop`. The skill runs them against a
target `raw/` + `wiki/` repository through `--repo-root`; it does not install
gate code in that repository.

Invocation is anchored to the directory of the loaded `SKILL.md`, not the
current working directory. This keeps the same entrypoint reliable for both a
project-local skill and a globally installed copy.

`llm-wiki-bootstrap` remains the lightweight Obsidian scaffold and optional
SQLite retrieval owner. Its generated `AGENTS.md` routes certified ingest to the
loop skill. Missing loop runtime means `not_ready`, never an uncertified
`ready` claim.

See the canonical [ADR-0001](../../docs/adr/ADR-0001-loop-runtime-ownership.md).
