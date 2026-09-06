---
status: Active
source_of_truth: false
last_updated: 2026-09-06
superseded_by: N/A
---

# Impact summary

## Changed

- Refreshed the Wiki Studio handoff as a sourced what/how/why record across chat, opt-in intake, parallel preparation, folder selection, retrieval observability, and modularization, including rejected alternatives, review lessons, verification limits, and publication scope.
- Refactored Wiki Studio into injected backend document/folder/HTTP responsibilities and explicit-input frontend factories. HTML is the canonical frontend loading/admission list, and tests execute the real scripts without startup-source rewriting. Existing state, history, execution, and completion boundaries remain intact.
- Added passive workspace SQLite/ONNX diagnostics and durable per-answer search-call composition. Configuration, file-stat freshness, stored vectors, actual chat routing, and citation evidence remain distinct; status does not activate retrieval engines or model work.
- Added native and bounded in-app folder selection to Wiki Studio connection, retaining manual entry and all existing connection/write guards. Folder selection does not upload content, connect automatically, invoke a model, or change OS security settings.
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

- `.agents/skills/llm-wiki-loop/dashboard/boot.js`
- `.agents/skills/llm-wiki-loop/dashboard/modules/graph.js`
- `.agents/skills/llm-wiki-loop/dashboard/modules/history-codec.js`
- `.agents/skills/llm-wiki-loop/dashboard/modules/markdown.js`
- `.agents/skills/llm-wiki-loop/dashboard/modules/retrieval-status.js`
- `.agents/skills/llm-wiki-loop/dashboard/modules/retrieval-usage.js`
- `.agents/skills/llm-wiki-loop/evals/frontend_modules.test.cjs`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_documents.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_folders.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_http.py`
- `docs/evidence/2026-09-06-dashboard-refactor.md`
- `docs/plans/2026-09-06-dashboard-refactor.md`
- `tests/test_wiki_dashboard_http.py`
- `tests/test_wiki_dashboard_modules.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_retrieval_status.py`
- `tests/test_wiki_dashboard_retrieval_status.py`
- `tests/test_wiki_dashboard_retrieval_integration.py`
- `docs/evidence/2026-09-06-wiki-retrieval-observability.md`
- `tests/test_wiki_dashboard_folder_picker.py`
- `docs/evidence/2026-09-06-wiki-folder-picker.md`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_batch.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_batch_tools.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_batch_extension.mjs`
- `.agents/skills/llm-wiki-loop/evals/batch_extension.test.cjs`
- `tests/test_wiki_dashboard_batch.py`
- `tests/test_wiki_dashboard_batch_tools.py`
- `tests/test_wiki_dashboard_parallel.py`
- `docs/adr/ADR-0003-wiki-parallel-preparation.md`
- `docs/plans/2026-09-05-wiki-parallel-preparation.md`
- `docs/evidence/2026-09-06-wiki-parallel-preparation.md`
- `docs/reviews/2026-09-06-wiki-parallel-preparation.md`
- `docs/reviews/2026-09-05-wiki-dashboard.md`
- `docs/reviews/README.md`
- `wiki/decisions/local-wiki-studio.md`

- `.agents/skills/llm-wiki-loop/dashboard/README.md`
- `.agents/skills/llm-wiki-loop/dashboard/app.js`
- `.agents/skills/llm-wiki-loop/dashboard/example.json`
- `.agents/skills/llm-wiki-loop/dashboard/index.html`
- `.agents/skills/llm-wiki-loop/dashboard/style.css`
- `.agents/skills/llm-wiki-loop/evals/dashboard_ui.test.cjs`
- `.agents/skills/llm-wiki-loop/evals/chat_extension.test.cjs`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_chat_tools.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_chat_extension.mjs`
- `tests/test_wiki_dashboard_chat_tools.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_automation.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_save.py`
- `tests/test_wiki_dashboard_chat.py`
- `tests/test_wiki_dashboard_automation.py`
- `tests/test_wiki_dashboard_save.py`
- `tests/test_wiki_dashboard_entries.py`
- `docs/repo-map/README.md`
- `docs/adr/ADR-0002-local-wiki-dashboard.md`
- `docs/evidence/2026-09-05-wiki-dashboard.md`
- `docs/plans/2026-09-05-wiki-dashboard.md`
- `docs/plans/README.md`
- `tests/test_wiki_dashboard.py`

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

The pre-chat delivery baseline passed 198/198 tests, including the local dashboard, raw-index rebuild/search/doctor,
standalone loop-runtime, and
explicit wiki-first fallback checks,
full-mode receipt requirements, deferred-unit ready rejection, resumable partial
review, explicit summary opt-in, and prior Windows lock regressions. Changed
workflow Python passes `py_compile`; patch whitespace
passes `git diff --check`. Final repository validator and skill-distribution
results are recorded at handoff after the final mutation.

## Optional local Wiki Studio (2026-09-05)

Added the loop-owned bright dashboard with source kanban, Markdown graph,
coverage/verification details, source upload, document reading, and Pi RPC
start/steer/abort controls. No root runtime, hosted deployment, extra skill, or
LangGraph migration was introduced. See [verification](evidence/2026-09-05-wiki-dashboard.md).

The local dashboard now also connects DocTology itself through a read-only
project documentation graph and complete document library. Incompatible source
projects cannot start Pi ingest or upload through this mode.

## Wiki Studio handoff preservation

The derived handoff in [wiki decision memory](../wiki/decisions/local-wiki-studio.md)
records user intent, rationale, implementation, review repairs, limitations,
and resumption guidance. A [scoped review record](reviews/2026-09-05-wiki-dashboard.md)
preserves the four resolved findings. The docs portal, current state, review and
wiki indexes, and maintenance log now expose this route.

The earlier handoff-only pass changed documentation without changing runtime.
The subsequent chat-first implementation adds no-tools Pi chat, browser-local
history, explicit citation-to-graph highlighting, and root-bound wiki/raw document
navigation. Project-mode chat does not authorize ingest or create target state.
The existing source writer and completion gates are unchanged. Current test and
browser evidence, including limits, is maintained in the linked verification
record. That chat-first increment did not include folder watching or conversation
publication.

## Wiki Studio agentic read-only chat (2026-09-05)

Replaced one-shot excerpt selection with an actual Pi loop over approved list,
search, document-read, and link tools. Default model selection remains Pi-owned.
An authenticated per-job bridge and explicit extension provide no general shell,
write, or external-web tools. Read evidence, final citations, budget limits, and
actual activity are distinct; cancelled I/O, changed hashes, polling recovery,
and native disclosure controls have focused regressions. The reader keeps its
close header visible while its body scrolls, and chat has separate top/bottom
navigation above the composer. Read-only chat no longer takes a writer slot:
manual and authorized queued wiki work can run alongside it, with separate
cancellation and an explicit live-read notice. Writer serialization and root
switch guards remain intact. Existing source-entry
and completion gates remain unchanged. Real model/browser observations and
limits are in [current evidence](evidence/2026-09-05-wiki-dashboard.md).

## Wiki Studio source entry (2026-09-05)

Added separately approved Markdown watching and automatic dispatch, plus exact
conversation preview and immutable unverified raw capture. Both paths feed the
existing full-coverage loop instead of creating a new quality gate. Queue pages,
explicit retries, stale/restored completion, writer contention, and partial-save
recovery have bounded contracts. Claude execution and a new DAG engine remain
out of scope. Current verification and limits remain in the
[dashboard evidence](evidence/2026-09-05-wiki-dashboard.md).


## Parallel preparation delivery (2026-09-06)

Completed existing-loop parallel source preparation for explicit two-to-twelve-source Wiki Studio batches. Three workers are the default and four the maximum; workers retain source-owned reads and draft writes, while existing batch planning, pre-mutation runs, one writer apply, question receipts, and snapshot seal remain the sole completion authority. No LangGraph, new completion gate, or multiple canonical writer was added.

The clean fixture proved concurrent first-attempt preparation but correctly stopped after one apply when required ingest-report links were absent. Its original batch remains blocked and unsealed. A new existing-runtime batch repaired only the two links, then certified through the normal procedure. The completed [evidence](evidence/2026-09-06-wiki-parallel-preparation.md), [review](reviews/2026-09-06-wiki-parallel-preparation.md), [plan](plans/2026-09-05-wiki-parallel-preparation.md), and [ADR](adr/ADR-0003-wiki-parallel-preparation.md) record the current handoff, checks, local deployment observation, manual crash boundary, and synthetic-fixture limits.
