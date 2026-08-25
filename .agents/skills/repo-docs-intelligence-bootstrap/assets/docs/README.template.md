---
status: Active
source_of_truth: Yes
last_updated: YYYY-MM-DD
superseded_by: N/A
---

# Documentation Portal

Start here.

## Operating Intent

- Keep current repository truth explicit.
- Reduce drift between code, docs, contracts, and guidance.
- Make legacy material visible instead of hiding it.

## Current References

- [Current repository state](CURRENT_STATE.md)
- [Architecture](ARCHITECTURE.md)
- [Layer boundaries](LAYERS.md)
- [Repository map](repo-map/README.md)
- [Skill integration](SKILLS_INTEGRATION.md)
- [Roadmap](ROADMAP.md)
- [Impact summary](IMPACT_SUMMARY.md)

## Decision And Delivery Records

- [Architecture decisions](adr/README.md)
- [Plans and designs](plans/README.md)
- [Evidence](evidence/README.md)
- [Reviews](reviews/README.md)
- [Archive](archive/README.md)
- [Derived decision memory](../wiki/decisions/README.md) — non-canonical

## Derived Retrieval

- `scripts/repo_docs_retrieval.py` rebuilds disposable heading, FTS5,
  fingerprint, and Markdown-link state from `AGENTS.md`, `docs/**/*.md`, and
  `wiki/**/*.md` only.
- Search results are non-canonical discovery candidates. A missing or stale
  derived index does not change documentation truth or validator status.

## Legacy And Non-Current Material

- Keep experiments visibly classified and move only genuinely superseded
  material into the [archive](archive/README.md).
- Do not classify active reviews as legacy material.

## Review Questions

- What is the current source of truth?
- What remains intentionally legacy?
- What drift has been resolved, and what still needs follow-up?
