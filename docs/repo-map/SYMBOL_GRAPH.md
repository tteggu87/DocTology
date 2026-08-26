---
status: Active
source_of_truth: false
last_updated: 2026-08-26
superseded_by: N/A
---

# High-impact symbols

- `scripts.manage_skills.SKILLS`: fixes the public inventory.
- `scripts.manage_skills.validate_source`: rejects missing or extra active skills.
- `scripts.manage_skills.install`: synchronizes each complete skill tree.
- `bootstrap_llm_wiki.scaffold`: creates downstream wiki workspaces.
- `repo_docs_retrieval.rebuild`: creates and atomically publishes derived Repo Docs state.
- `repo_docs_retrieval.health`: owns shallow stat and deep exact verification.
- `repo_docs_retrieval.search_results`: enforces one best chunk per document.
- `repo_docs_retrieval.require_ready`: opens one schema-compatible query connection without source hashing.

This is a focused impact map, not a complete generated call graph.
