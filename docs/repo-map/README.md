---
status: Active
source_of_truth: false
last_updated: 2026-09-05
superseded_by: N/A
---

# Repository map

- `docs/repo-map/ENTRYPOINTS.md` — [Entrypoints](ENTRYPOINTS.md)
- `docs/repo-map/MODULES.md` — [Modules](MODULES.md)
- `docs/repo-map/DATA_FLOW.md` — [Data flow](DATA_FLOW.md)
- `docs/repo-map/SYMBOL_GRAPH.md` — [High-impact symbols](SYMBOL_GRAPH.md)

## Wiki Studio focused reading path

- [Current behavior and limits](../CURRENT_STATE.md)
- [Architecture and state ownership](../ARCHITECTURE.md)
- [Local usage](../../.agents/skills/llm-wiki-loop/dashboard/README.md)
- [`wiki_dashboard.py`](../../.agents/skills/llm-wiki-loop/scripts/wiki_dashboard.py): localhost server, connected-root boundary, isolated read-only Pi chat, and ingest adapter
- [`wiki_dashboard_chat_tools.py`](../../.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_chat_tools.py): root- and current-inventory-bound `wiki_list`, `wiki_search`, `wiki_read`, and `wiki_links` read tools
- [`wiki_dashboard_automation.py`](../../.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_automation.py): opt-in watcher, immutable external snapshots, sequential queue, existing-gate reconciliation
- [`wiki_dashboard_save.py`](../../.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_save.py): bounded conversation preview, unverified raw record, explicit queue handoff
- [Decision memory and verification limits](../../wiki/decisions/local-wiki-studio.md)

The dashboard runtime files are distributed inside `llm-wiki-loop`; target vaults receive only their own raw, wiki, and bounded state, not copied dashboard executables.
