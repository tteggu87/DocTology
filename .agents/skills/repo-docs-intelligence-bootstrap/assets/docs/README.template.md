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
- Add a descriptive link to the repo-map index when it is activated.
- [Skill integration](SKILLS_INTEGRATION.md)
- [Roadmap](ROADMAP.md)
- [Impact summary](IMPACT_SUMMARY.md)

## Activated Lifecycle Indexes

- When ADRs exist, add a descriptive relative Markdown link to the repository's active ADR index or location. Preserve flat or custom ADR layouts.
- Add plan, evidence, and review index links only when those optional surfaces exist.
- Add a derived wiki-decision index only when it exists, and label it non-canonical.

## Optional Derived Retrieval

- Leave Repo Docs retrieval off unless measured document scale or repeated long-document reads justify it.
- When active, `scripts/repo_docs_retrieval.py` rebuilds disposable heading, FTS5, fingerprint, and Markdown-link state from `AGENTS.md`, `docs/**/*.md`, and `wiki/**/*.md` only.
- Search results are non-canonical discovery candidates. A missing or stale optional index does not change documentation truth or validator status.

## Legacy And Non-Current Material

- Add experiment or archive links only when those locations exist.
- Do not classify active reviews as legacy material.

## Review Questions

- What is the current source of truth?
- What remains intentionally legacy?
- What drift has been resolved, and what still needs follow-up?
