---
status: Active
source_of_truth: false
last_updated: 2026-09-06
superseded_by: N/A
---

# Repository map

- `docs/repo-map/ENTRYPOINTS.md`: [Entrypoints](ENTRYPOINTS.md)
- `docs/repo-map/MODULES.md`: [Modules](MODULES.md)
- `docs/repo-map/DATA_FLOW.md`: [Data flow](DATA_FLOW.md)
- `docs/repo-map/SYMBOL_GRAPH.md`: [High-impact symbols](SYMBOL_GRAPH.md)

## Wiki Studio focused reading path

- [Current behavior and migration status](../CURRENT_STATE.md)
- [Architecture and state ownership](../ARCHITECTURE.md)
- [Studio UI usage and maintenance](../../dashboard/README.md)
- [`runtime/wiki_dashboard.py`](../../runtime/wiki_dashboard.py): localhost server, connected-root boundary, isolated read-only Pi chat, and existing-gate adapter
- [`runtime/wiki_dashboard_chat_tools.py`](../../runtime/wiki_dashboard_chat_tools.py): root- and current-inventory-bound `wiki_list`, `wiki_search`, `wiki_read`, and `wiki_links` read tools
- [`runtime/wiki_dashboard_automation.py`](../../runtime/wiki_dashboard_automation.py): opt-in watcher, immutable external snapshots, sequential queue, existing-gate reconciliation
- [`runtime/wiki_dashboard_save.py`](../../runtime/wiki_dashboard_save.py): bounded conversation preview, unverified raw record, explicit queue handoff
- [`runtime/wiki_loop_adapter.py`](../../runtime/wiki_loop_adapter.py): repository binding to the reusable loop gate runtime
- [Ownership decision and verification boundary](../adr/ADR-0004-studio-runtime-separation.md)
- [Decision memory and historical verification limits](../../wiki/decisions/local-wiki-studio.md)

The application files above are covered by [migration verification](../evidence/2026-09-06-studio-runtime-separation.md). Historical evidence may name the former `llm-wiki-loop` paths and remains evidence for that prior layout only.
