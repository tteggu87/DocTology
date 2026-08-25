---
status: Active
source_of_truth: true
last_updated: 2026-08-25
superseded_by: N/A
---

# Architecture

The repository is a skill pack, not a running knowledge system.

1. `.agents/skills/` contains the three canonical, self-contained products.
2. `scripts/manage_skills.py` validates or copies those products without interpreting their internals.
3. `tests/` exercises distribution, wiki bootstrap retrieval and gates, and Repo Docs tooling.
4. `docs/`, `intelligence/`, and `wiki/` describe and remember this repository itself.

Generated wiki vaults are downstream products. Their Markdown is canonical; optional SQLite is disposable. Repo Docs repositories use relative Markdown links and a separate disposable docs index.
