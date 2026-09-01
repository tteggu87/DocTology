---
status: Active
source_of_truth: true
last_updated: 2026-08-27
superseded_by: N/A
---

# Architecture

The repository is a skill pack, not a running knowledge system.

1. `.agents/skills/` contains the three canonical, self-contained products.
2. `scripts/manage_skills.py` validates or copies those products without interpreting their internals.
3. `tests/` exercises distribution, wiki bootstrap retrieval, standalone loop
   gates, and Repo Docs tooling.
4. `docs/`, `intelligence/`, and `wiki/` describe and remember this repository itself.

Generated wiki vaults are downstream products. Their Markdown is canonical; optional SQLite is disposable. Repo Docs repositories use relative Markdown links and a separate disposable docs index.

The generated vault contains the base wiki contract and optional retrieval
helpers, not copied loop executables. `llm-wiki-loop` owns the source procedure,
batch, and structural gate runtime and runs it from the skill directory against
the vault. The vault stores only canonical wiki changes plus bounded run, batch,
and receipt state. Multi-source batches prepare drafts outside `wiki/`, publish
once, and use one state-only snapshot seal to bind all source runs and the final
certification to the unchanged writer result.

The Repo Docs skill owns that index builder plus optional native SQLite read
adapters as sibling skill files. Python owns rebuild/status/doctor and remains
the portable fallback; the shell and PowerShell adapters share SQL and own no
freshness, mutation, or canonical-truth decisions.
