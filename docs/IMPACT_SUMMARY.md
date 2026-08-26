---
status: Active
source_of_truth: false
last_updated: 2026-08-26
superseded_by: N/A
---

# Impact summary

## Changed

- Upgraded the canonical Repo Docs retrieval script to schema v3 with stat-only
  status, exact doctor, unchecked one-connection discovery, exact one-result-per-
  document ranking, source line ranges, batch query attribution, peer-heading
  correction, duplicate-link removal, partial SQLite-header reads, and a final
  pre-publication Markdown drift check.
- Added self-contained POSIX and PowerShell native SQLite query adapters over one
  shared search/traversal SQL contract. Strict term input is quoted rather than
  interpreted as raw FTS syntax, and native error exits match Python behavior.
- Added default contentless trigram literal discovery plus the single
  `rebuild --no-trigram` compact-storage choice; no vector, RRF, daemon, MCP,
  workflow engine, or canonical database was introduced.
- Expanded focused retrieval regression coverage from 7 to 23 tests and recorded
  bounded implementation evidence plus a derived absorption analysis.
- Aligned generated LLM Wiki SQLite with the same lifecycle split while retaining
  its independent ONNX lane: one-connection unchecked lexical/link discovery,
  stat-current semantic use, exact `doctor`, one best lexical chunk per page,
  peer-heading correction, page-streamed rebuild/publication verification, and
  bounded vector reuse/embedding batches.
- Corrected generated wiki orphan detection so automatic `_meta` index links and self-links cannot hide disconnected pages; added optional strict failure behavior and regression coverage.
- Replaced the mixed ontology/wiki/workbench repository surface with exactly three self-contained skills under `.agents/skills/`.
- Added `scripts/manage_skills.py`, focused tests, CI, current Repo Docs, minimal intelligence contracts, and small repository memory.
- Removed the active ontology operator, root pipeline copies, workbench, tracked archive, and obsolete launchers and tests.

### Files

- `.agents/skills/repo-docs-intelligence-bootstrap/SKILL.md`
- `.agents/skills/llm-wiki-bootstrap/references/scaffold-spec.md`
- `.agents/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py`
- `.agents/skills/llm-wiki-bootstrap/scripts/reindex_sqlite_operational.py`
- `.agents/skills/llm-wiki-bootstrap/scripts/wiki_retrieval.py`
- `.agents/skills/repo-docs-intelligence-bootstrap/assets/AGENTS.template.md`
- `.agents/skills/repo-docs-intelligence-bootstrap/assets/docs/README.template.md`
- `.agents/skills/repo-docs-intelligence-bootstrap/scripts/repo_docs_query.ps1`
- `.agents/skills/repo-docs-intelligence-bootstrap/scripts/repo_docs_query.sh`
- `.agents/skills/repo-docs-intelligence-bootstrap/scripts/repo_docs_retrieval.py`
- `.agents/skills/repo-docs-intelligence-bootstrap/scripts/repo_docs_search.sql`
- `.agents/skills/repo-docs-intelligence-bootstrap/scripts/repo_docs_traverse.sql`
- `docs/ARCHITECTURE.md`
- `docs/CURRENT_STATE.md`
- `docs/IMPACT_SUMMARY.md`
- `docs/repo-map/MODULES.md`
- `docs/repo-map/SYMBOL_GRAPH.md`
- `docs/LAYERS.md`
- `docs/README.md`
- `docs/ROADMAP.md`
- `docs/SKILLS_INTEGRATION.md`
- `docs/evidence/2026-08-26-repo-docs-sqlite-absorption.md`
- `docs/evidence/README.md`
- `docs/repo-map/DATA_FLOW.md`
- `docs/repo-map/ENTRYPOINTS.md`
- `docs/repo-map/MODULES.md`
- `docs/repo-map/SYMBOL_GRAPH.md`
- `tests/test_repo_docs_retrieval.py`
- `tests/test_wiki_sqlite_index.py`
- `tests/test_wiki_sqlite_retrieval.py`
- `tests/test_wiki_sqlite_semantic.py`
- `wiki/_meta/index.md`
- `wiki/_meta/log.md`

## Checked Not Changed

- `llm-wiki-bootstrap` remains a separate Obsidian-first retrieval implementation;
  it absorbs only the shared lifecycle lessons, not Repo Docs native Markdown-link
  SQL, trigram policy, daemon, or vector-ANN complexity.
- `scripts/manage_skills.py` remains a thin whole-tree distributor, so the new
  sibling wrappers and SQL files require no root installer logic.
- `AGENTS.md`, intelligence contracts, and the three-skill product boundary remain
  unchanged because retrieval stays derived and skill-owned.
- The retained skill products were preserved except for correcting the bootstrap command path from the obsolete `~/.agents/skills` location to the installed `~/.codex/skills` location.
- Git history and existing `archive/branches/*` tags remain the recovery path for removed tracked experiments.

## Legacy split

The prior local workspace, including ignored raw, warehouse, and wiki data, was copied and checksum-verified at `../DocTology-legacy-vault-20260825` before cleanup. It is not part of the public repository.

## Wiki memory

`wiki/_meta/index.md` points back to the canonical evidence route, and
`wiki/_meta/log.md` records the implementation boundary. No duplicate analysis
page was added under the locally excluded `wiki/analyses/` tree. The previous
ontology analyses remain in the legacy vault and Git history.

## Remaining Drift

PowerShell syntax and shared SQL are covered, but actual `pwsh`/`sqlite3.exe`
execution and latency still require a Windows host. Multi-gigabyte trigram size
and latency are deliberately unclaimed; use `--no-trigram` until measured when
storage is constrained. The full suite also exposes pre-existing SQLite
`ResourceWarning` messages in other wiki retrieval tests. No runtime legacy
remains active. The repository has no license file; redistribution terms remain
undefined until the owner selects one.

## Validator Summary

The Repo Docs retrieval suite passes 23/23 and the full suite passes 135/135.
Changed Python passes Ruff; the POSIX wrapper passes `bash -n`; patch whitespace
passes `git diff --check`. Final repository validator and skill-distribution
results are recorded at handoff after the final mutation.
