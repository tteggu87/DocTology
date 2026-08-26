---
status: Active
source_of_truth: false
last_updated: 2026-08-27
superseded_by: N/A
---

# Entrypoints

- Canonical repository command: `python3 scripts/manage_skills.py check|install`.
- Skill entrypoints: each retained `.agents/skills/*/SKILL.md` and its documented sibling scripts.
- Verification: `python3 -m unittest discover -s tests` and the bundled Repo Docs validator.
- Standalone LLM Wiki loop: `llm-wiki-loop/scripts/wiki_loop.py --repo-root
  <vault> preflight|workflow|batch|check` runs the loop-owned gates without
  copying executables into the vault.
- Downstream LLM Wiki raw retrieval: `scripts/raw_retrieval.py` owns incremental
  rebuild, stat status, lexical search, and exact doctor for `raw/**/*.md`.
- Downstream wiki query fallback: `scripts/wiki_retrieval.py search
  --raw-fallback` invokes raw lexical lookup only after a wiki lexical miss.
- Downstream Repo Docs retrieval: `scripts/repo_docs_retrieval.py` owns portable
  rebuild/status/doctor/search/batch/traversal; `repo_docs_query.sh` and
  `repo_docs_query.ps1` are optional native read wrappers over shared SQL.

There are no root secondary launchers. The native query wrappers are
self-contained downstream skill assets, not DocTology root entrypoints.
