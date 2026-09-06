---
status: Active
source_of_truth: false
last_updated: 2026-09-05
superseded_by: N/A
---

# Modules

- `.agents/skills/llm-wiki-bootstrap/`: vault scaffolding, optional
  page-streamed wiki SQLite retrieval, separate incremental raw lexical
  retrieval with explicit wiki-miss fallback, deterministic raw heading-tree
  navigation, and bounded wiki ONNX vector refresh. It routes certified ingest
  to the loop rather than copying gates.
- `.agents/skills/llm-wiki-loop/`: agent-operated repeated wiki growth contract,
  self-contained procedure/batch/structural runtime, receipt assets, and a
  `--repo-root` entrypoint. Ordinary ingest compiles to coverage-preserving full
  mode and explicit summary requests remain opt-in. Derived heading structure
  may guide planning but never changes the coverage receipt boundary. Its batch
  runtime stages outside the wiki, applies once, and seals all source runs plus
  certification against one unchanged corpus snapshot.
- `.agents/skills/repo-docs-intelligence-bootstrap/`: templates, validator,
  portable docs-index lifecycle, optional native SQLite readers, shared SQL,
  and dogfood tooling.
- `scripts/manage_skills.py`: inventory validation and installation only.
- `tests/`: product and distribution regression coverage.

The loop skill also owns `dashboard/` UI assets and `scripts/wiki_dashboard.py`.
Sibling `wiki_dashboard_automation.py` owns opt-in discovery, immutable imports,
paginated queue state, and current-gate reconciliation; `wiki_dashboard_save.py`
owns memory-only previews and approved unverified raw capture. Both delegate
execution to the same adapter and existing gates.
The adapter owns isolated read-only Pi chat, root- and current-inventory-bound
`wiki_list`, `wiki_search`, `wiki_read`, and `wiki_links` tools, and the separate
ingest process. The backend waits for an authenticated loopback ready handshake
before prompting and preserves Pi's ambient default model unless explicitly
overridden. It intentionally provides no shell, write, network, or equivalent
terminal capability. Reads, citations, budgets, and traces are bounded and
visible without exposing reasoning; only actual reads can support citations,
which remain non-semantic. It reuses workflow and batch status rather than
implementing new gates. UI history is browser-local; references and highlighted
paths derive from current answer citations and actual links. Rendering contracts
are exercised by `evals/dashboard_ui.test.cjs`; `tests/test_wiki_dashboard_chat.py`
covers chat and evidence navigation.

The dashboard composition root delegates catalog operations to `wiki_dashboard_documents.py`, folder selection to `wiki_dashboard_folders.py`, and HTTP/admitted assets to `wiki_dashboard_http.py`. The catalog receives the existing workflow/batch dependencies. Frontend factories in `dashboard/modules/` take explicit inputs; `app.js` owns shared state, storage, and lifecycle guards, with `boot.js` as the single startup entry. The [maintenance map](../../.agents/skills/llm-wiki-loop/dashboard/README.md#유지보수와-확장-경계) identifies extension points and test boundaries.
