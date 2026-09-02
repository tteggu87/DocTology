---
status: Active
source_of_truth: false
last_updated: 2026-09-02
superseded_by: N/A
---

# Impact summary

## Changed

- Restored the original cropped DocTology logo and rebuilt the concise GitHub
  front door around the two actual use cases: human-facing Obsidian LLM Wiki
  and agent-facing Repo Docs, joined by deterministic gates and derived SQLite.
  The removed workbench surface remains inactive.
- Moved the LLM Wiki procedure, batch, and structural gate runtime into the
  standalone `llm-wiki-loop` skill. Fresh bootstrap vaults keep only the base
  wiki and optional retrieval helpers; certified ingest invokes the loop through
  `--repo-root` and records no copied gate executables.
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
- Upgraded generated wiki retrieval to `wiki-heading-index-v9`: fenced-code-aware
  headings define chunks even for small PPT-derived Markdown, 8 KiB is a
  per-section maximum, deterministic document/heading nodes are persisted, and
  each lexical or semantic body hit carries its owning `node_id` without changing
  the Markdown-canonical boundary or adding a navigation runtime.
- Made generated workflow process locks portable without adding a dependency:
  Unix uses `fcntl.flock`, Windows uses one-byte `msvcrt.locking`, and both keep
  the existing run-finalization and SQLite-refresh serialization contract.
- Changed ordinary wiki ingest from implicit concise summarization to
  coverage-preserving `full` mode. Generated `AGENTS.md` and `llm-wiki-loop`
  now compile short ingest requests into heading/bounded-chunk accounting;
  explicit summary remains opt-in, and full final review requires a matching,
  balanced receipt with zero deferred units.
- Added a separate, incremental `raw/**/*.md` lexical index for SQLite-enabled
  vaults. It updates only stat-changed paths, keeps chunk content out of regular
  tables, reopens canonical byte ranges for results, and deliberately adds no
  raw ONNX, RRF, ANN, daemon, or canonical database.
- Added explicit wiki-first `--raw-fallback`. It invokes raw FTS only after a
  wiki lexical miss, preserves default wiki search, keeps rankings separate,
  and treats a missing raw index as non-fatal.
- Corrected generated wiki orphan detection so automatic `_meta` index links and self-links cannot hide disconnected pages; added optional strict failure behavior and regression coverage.
- Replaced the mixed ontology/wiki/workbench repository surface with exactly three self-contained skills under `.agents/skills/`.
- Added `scripts/manage_skills.py`, focused tests, CI, current Repo Docs, minimal intelligence contracts, and small repository memory.
- Removed the active ontology operator, root pipeline copies, workbench, tracked archive, and obsolete launchers and tests.

### Files

- `README.md`
- `branding/doctology-logo-cropped.jpeg`
- `.agents/skills/llm-wiki-bootstrap/SKILL.md`
- `.agents/skills/llm-wiki-loop/SKILL.md`
- `.agents/skills/repo-docs-intelligence-bootstrap/SKILL.md`
- `.agents/skills/llm-wiki-bootstrap/references/scaffold-spec.md`
- `.agents/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py`
- `.agents/skills/llm-wiki-bootstrap/scripts/reindex_sqlite_operational.py`
- `.agents/skills/llm-wiki-bootstrap/scripts/raw_retrieval.py`
- `.agents/skills/llm-wiki-bootstrap/scripts/wiki_retrieval.py`
- `.agents/skills/llm-wiki-loop/assets/coverage_receipt_template.md`
- `.agents/skills/llm-wiki-loop/assets/representative_questions_template.json`
- `.agents/skills/llm-wiki-loop/references/runtime-contract.md`
- `.agents/skills/llm-wiki-loop/scripts/wiki_loop.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_workflow.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_batch.py`
- `.agents/skills/llm-wiki-loop/scripts/pipeline_check.py`
- `.agents/skills/repo-docs-intelligence-bootstrap/assets/AGENTS.template.md`
- `.agents/skills/repo-docs-intelligence-bootstrap/assets/docs/README.template.md`
- `.agents/skills/repo-docs-intelligence-bootstrap/scripts/repo_docs_query.ps1`
- `.agents/skills/repo-docs-intelligence-bootstrap/scripts/repo_docs_query.sh`
- `.agents/skills/repo-docs-intelligence-bootstrap/scripts/repo_docs_retrieval.py`
- `.agents/skills/repo-docs-intelligence-bootstrap/scripts/repo_docs_search.sql`
- `.agents/skills/repo-docs-intelligence-bootstrap/scripts/repo_docs_traverse.sql`
- `.codex/ralph/prd.json`
- `.codex/ralph/progress.txt`
- `docs/ARCHITECTURE.md`
- `docs/adr/ADR-0001-loop-runtime-ownership.md`
- `docs/adr/README.md`
- `docs/CURRENT_STATE.md`
- `docs/IMPACT_SUMMARY.md`
- `docs/repo-map/MODULES.md`
- `docs/repo-map/SYMBOL_GRAPH.md`
- `docs/repo-map/DATA_FLOW.md`
- `docs/repo-map/ENTRYPOINTS.md`
- `docs/LAYERS.md`
- `docs/README.md`
- `docs/ROADMAP.md`
- `docs/SKILLS_INTEGRATION.md`
- `docs/evidence/2026-08-26-repo-docs-sqlite-absorption.md`
- `docs/evidence/2026-08-27-loop-runtime-ownership.md`
- `docs/evidence/README.md`
- `docs/repo-map/DATA_FLOW.md`
- `docs/repo-map/ENTRYPOINTS.md`
- `docs/repo-map/MODULES.md`
- `docs/repo-map/SYMBOL_GRAPH.md`
- `tests/test_repo_docs_retrieval.py`
- `tests/test_wiki_batch_gate.py`
- `tests/test_wiki_raw_retrieval.py`
- `tests/test_wiki_sqlite_index.py`
- `tests/test_wiki_sqlite_retrieval.py`
- `tests/test_wiki_sqlite_semantic.py`
- `tests/test_wiki_workflow_gate.py`
- `wiki/_meta/index.md`
- `wiki/_meta/log.md`
- `wiki/decisions/README.md`
- `wiki/decisions/loop-runtime-ownership.md`

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
execution, workflow locking, and latency still require a Windows host.
Multi-gigabyte trigram size and latency are deliberately unclaimed; use
`--no-trigram` until measured when storage is constrained. The full suite also exposes pre-existing SQLite
`ResourceWarning` messages in other wiki retrieval tests. No runtime legacy
remains active. The repository has no license file; redistribution terms remain
undefined until the owner selects one.

## Validator Summary

The full suite passes 191/191, including raw-index rebuild/search/doctor,
standalone loop-runtime, and
explicit wiki-first fallback checks,
full-mode receipt requirements, deferred-unit ready rejection, resumable partial
review, explicit summary opt-in, and prior Windows lock regressions. Changed
workflow Python passes `py_compile`; patch whitespace
passes `git diff --check`. Final repository validator and skill-distribution
results are recorded at handoff after the final mutation.
