---
status: Active
source_of_truth: false
last_updated: 2026-09-06
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
