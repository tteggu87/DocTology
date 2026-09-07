---
status: Active
source_of_truth: false
last_updated: 2026-09-07
superseded_by: N/A
---

# Modules

- `runtime/`: repository-owned Wiki Studio backend, launchers, chat bridge,
  watcher/queue and conversation-save adapters, and `wiki_loop_adapter.py`.
- `dashboard/`: repository-owned static UI assets and its usage guide.
- `tests/dashboard/`: Studio JavaScript evaluations.
- `.agents/skills/llm-wiki-bootstrap/`: vault scaffolding and optional derived retrieval.
- `.agents/skills/llm-wiki-loop/`: reusable agent-operated procedure, coverage,
  batch, receipt, seal, and certification gates. It has no Studio application
  copy after the approved migration.
- `.agents/skills/repo-docs-intelligence-bootstrap/`: templates, validator,
  portable docs-index lifecycle, optional native SQLite readers, shared SQL, and dogfood tooling.
- `scripts/manage_skills.py`: three-skill inventory validation and installation only.
- `tests/`: application and distribution regression coverage.

The Studio runtime retains isolated read-only Pi chat with inventory-bound
`wiki_list`, `wiki_search`, `wiki_read`, and `wiki_links` tools. It delegates all
wiki completion authority to the loop gates through `runtime/wiki_loop_adapter.py`.
Frontend factories use explicit inputs; application state, storage, and lifecycle
guards remain in `dashboard/app.js`, with `dashboard/boot.js` as the single
startup entry. The [maintenance map](../../dashboard/README.md#유지보수와-확장-경계)
identifies extension points and test boundaries.

This map records approved ownership, not completed verification. Earlier
skill-relative paths and counts in historical plans and evidence remain prior
layout observations.

Studio read progress lives in `runtime/wiki_dashboard_progress.py`: bounded
in-memory events, cooperative cancellation and serialized result publication.
`wiki_dashboard.py` owns connection IDs, root generations and one background
snapshot, including separate checking/rebuilding phases; `wiki_dashboard_documents.py` owns report indexing and per-file stat progress. The UI keeps routine checks in the header and reserves the layout-changing notice for rebuilds, failures, interruptions and stalls. The loop's `project_status_many` and `batch_status_many` reuse exact
hash observations within a single call, without persisting them as gate truth.
The automation adapter shares one verification view per reconciliation tick.
Chat tools report active scans/reads; Pi lifecycle signals join them in the UI.

`runtime/wiki_dashboard_index.py` owns the disposable Studio FTS index covering
the admitted chat inventory. Connection preparation and search updates run
outside the app lock; the loop skill's index and gates retain their ownership.
`wiki_dashboard_chat_tools.py` owns request deadlines, cooperative cancellation,
current target admission and citation rollback; the JS extension waits beyond
the server deadline. The document catalog caches parsed receipts and limits
raw hash checks to relevant targets.

The document catalog owns bounded run JSON/status projection memoization and one
cached graph. Keys cover actual dependency file identities, resolved symlink
targets and the procedure contract; consumer copies isolate cached values.
The dashboard still computes outside its main lock and atomically publishes
only a current root/revision. Exact gate code remains in the loop skill.
