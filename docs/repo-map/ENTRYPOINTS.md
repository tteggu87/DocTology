---
status: Active
source_of_truth: false
last_updated: 2026-09-01
superseded_by: N/A
---

# Entrypoints

- Canonical repository command: `python3 scripts/manage_skills.py check|install`.
- Skill entrypoints: each retained `.agents/skills/*/SKILL.md` and its documented sibling scripts.
- Verification: `python3 -m unittest discover -s tests` and the bundled Repo Docs validator.
- Standalone LLM Wiki loop: `llm-wiki-loop/scripts/wiki_loop.py --repo-root
  <vault> preflight|workflow|batch|check` runs the loop-owned gates without
  copying executables into the vault.
- Multi-source snapshot completion: `wiki_loop.py --repo-root <vault> batch
  seal --batch <id> --reviewer <id> --review-ref <path>` finalizes and certifies
  one already-applied, unchanged batch without modifying `wiki/`.
- Batch discovery and handoff: `wiki_loop.py batch --help` shows the fixed
  command sequence, `batch list [--active-only]` discovers unchecked manifests,
  and `batch status --batch <id>` returns exact freshness plus a deterministic
  advisory `next_action`.
- Downstream LLM Wiki raw retrieval: `scripts/raw_retrieval.py` owns incremental
  rebuild, stat status, lexical search, exact doctor, and checksum-checked
  `tree`, `ancestors`, and `subtree` navigation for `raw/**/*.md`.
- Downstream wiki query fallback: `scripts/wiki_retrieval.py search
  --raw-fallback` invokes raw lexical lookup only after a wiki lexical miss.
- Downstream Repo Docs retrieval: `scripts/repo_docs_retrieval.py` owns portable
  rebuild/status/doctor/search/batch/traversal; `repo_docs_query.sh` and
  `repo_docs_query.ps1` are optional native read wrappers over shared SQL.

There are no root secondary launchers. The native query wrappers are
self-contained downstream skill assets, not DocTology root entrypoints.
