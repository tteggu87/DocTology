---
status: Active
source_of_truth: false
last_updated: 2026-09-06
superseded_by: N/A
---

# Impact summary

## Changed

- Moved the application from the loop skill into repository-owned runtime/ and dashboard/, with JavaScript evaluations under tests/dashboard/. No compatibility application copies remain in the skill.
- Added the one-way wiki_loop_adapter.py binding. Runtime extensions stay in runtime/; Pi still receives the actual loop skill and gate entrypoint. Procedure and completion authority were not duplicated.
- Root macOS/Windows entry files forward to runtime-owned launchers. The pending desktop launcher work includes version checks, optional browser opening, bounded port selection, and native line-ending rules.
- Updated the loop skill's guidance, AGENTS, current architecture, repo maps, ADR-0004, and the sourced wiki handoff. ADR-0002 is historical; its original locations and fingerprints are not presented as current runtime paths.
- Refreshed this current impact summary rather than retaining obsolete claims that AGENTS and application ownership were unchanged. Earlier feature history remains in Git, the wiki log, and its evidence records.

### Files

The list includes removed source paths and their new destinations relative to the current Git baseline.

- `.agents/skills/llm-wiki-loop/SKILL.md`
- `.agents/skills/llm-wiki-loop/dashboard/README.md`
- `.agents/skills/llm-wiki-loop/dashboard/app.js`
- `.agents/skills/llm-wiki-loop/dashboard/boot.js`
- `.agents/skills/llm-wiki-loop/dashboard/example.json`
- `.agents/skills/llm-wiki-loop/dashboard/index.html`
- `.agents/skills/llm-wiki-loop/dashboard/modules/graph.js`
- `.agents/skills/llm-wiki-loop/dashboard/modules/history-codec.js`
- `.agents/skills/llm-wiki-loop/dashboard/modules/markdown.js`
- `.agents/skills/llm-wiki-loop/dashboard/modules/retrieval-status.js`
- `.agents/skills/llm-wiki-loop/dashboard/modules/retrieval-usage.js`
- `.agents/skills/llm-wiki-loop/dashboard/style.css`
- `.agents/skills/llm-wiki-loop/evals/batch_extension.test.cjs`
- `.agents/skills/llm-wiki-loop/evals/chat_extension.test.cjs`
- `.agents/skills/llm-wiki-loop/evals/dashboard_ui.test.cjs`
- `.agents/skills/llm-wiki-loop/evals/frontend_modules.test.cjs`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_automation.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_batch.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_batch_extension.mjs`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_batch_tools.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_chat_extension.mjs`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_chat_tools.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_documents.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_folders.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_http.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_retrieval_status.py`
- `.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_save.py`
- `.gitattributes`
- `AGENTS.md`
- `README.ko.md`
- `README.md`
- `Wiki-Studio.bat`
- `Wiki-Studio.command`
- `dashboard/README.md`
- `dashboard/app.js`
- `dashboard/boot.js`
- `dashboard/example.json`
- `dashboard/index.html`
- `dashboard/modules/graph.js`
- `dashboard/modules/history-codec.js`
- `dashboard/modules/markdown.js`
- `dashboard/modules/retrieval-status.js`
- `dashboard/modules/retrieval-usage.js`
- `dashboard/style.css`
- `docs/ARCHITECTURE.md`
- `docs/CURRENT_STATE.md`
- `docs/IMPACT_SUMMARY.md`
- `docs/LAYERS.md`
- `docs/README.md`
- `docs/ROADMAP.md`
- `docs/adr/ADR-0002-local-wiki-dashboard.md`
- `docs/adr/ADR-0003-wiki-parallel-preparation.md`
- `docs/adr/ADR-0004-studio-runtime-separation.md`
- `docs/adr/README.md`
- `docs/evidence/2026-09-06-dashboard-refactor.md`
- `docs/evidence/2026-09-06-studio-runtime-separation.md`
- `docs/evidence/2026-09-06-wiki-launchers.md`
- `docs/evidence/2026-09-06-wiki-retrieval-observability.md`
- `docs/evidence/README.md`
- `docs/plans/2026-09-06-dashboard-refactor.md`
- `docs/repo-map/DATA_FLOW.md`
- `docs/repo-map/ENTRYPOINTS.md`
- `docs/repo-map/MODULES.md`
- `docs/repo-map/README.md`
- `docs/reviews/2026-09-05-wiki-dashboard.md`
- `runtime/README.md`
- `runtime/start_dashboard.bat`
- `runtime/start_dashboard.command`
- `runtime/wiki_dashboard.py`
- `runtime/wiki_dashboard_automation.py`
- `runtime/wiki_dashboard_batch.py`
- `runtime/wiki_dashboard_batch_extension.mjs`
- `runtime/wiki_dashboard_batch_tools.py`
- `runtime/wiki_dashboard_chat_extension.mjs`
- `runtime/wiki_dashboard_chat_tools.py`
- `runtime/wiki_dashboard_documents.py`
- `runtime/wiki_dashboard_folders.py`
- `runtime/wiki_dashboard_http.py`
- `runtime/wiki_dashboard_retrieval_status.py`
- `runtime/wiki_dashboard_save.py`
- `runtime/wiki_loop_adapter.py`
- `tests/dashboard/batch_extension.test.cjs`
- `tests/dashboard/chat_extension.test.cjs`
- `tests/dashboard/dashboard_ui.test.cjs`
- `tests/dashboard/frontend_modules.test.cjs`
- `tests/test_wiki_dashboard.py`
- `tests/test_wiki_dashboard_automation.py`
- `tests/test_wiki_dashboard_batch.py`
- `tests/test_wiki_dashboard_batch_tools.py`
- `tests/test_wiki_dashboard_chat.py`
- `tests/test_wiki_dashboard_chat_tools.py`
- `tests/test_wiki_dashboard_entries.py`
- `tests/test_wiki_dashboard_folder_picker.py`
- `tests/test_wiki_dashboard_http.py`
- `tests/test_wiki_dashboard_launchers.py`
- `tests/test_wiki_dashboard_modules.py`
- `tests/test_wiki_dashboard_parallel.py`
- `tests/test_wiki_dashboard_retrieval_integration.py`
- `tests/test_wiki_dashboard_retrieval_status.py`
- `tests/test_wiki_dashboard_save.py`
- `wiki/_meta/index.md`
- `wiki/_meta/log.md`
- `wiki/decisions/README.md`
- `wiki/decisions/local-wiki-studio.md`

## Checked Not Changed

- All four loop implementation files remain byte-identical. The other two skills and the three-skill installer implementation are unchanged.
- Ten UI assets are byte-identical to the pre-move committed assets; their README and locations changed.
- Host/Origin/token/root checks, isolated chat, explicit automation, one canonical writer, source provenance, and existing completion gates remain in force.
- User raw/wiki files (24) and existing browser conversations (2) were preserved. No model prompt or canonical write was performed during migration.

## Legacy split

The removed skill-internal app paths are not supported startup locations. Historical evidence keeps its original scope. Existing legacy ontology/workbench archives remain outside the active repository; this change does not restore them.

## Wiki memory

[The handoff](../wiki/decisions/local-wiki-studio.md) explains why calling a gate does not make the caller application part of that gate's skill. It links the corrected ownership, implementation, checks, and limits rather than duplicating runtime policy.

## Remaining Drift

Windows launcher/Pi-process behavior is not real-desktop tested. Existing SQLite ResourceWarnings remain. Background process inspection/signalling was restricted, so older services were preserved; use the latest local URL recorded in ignored state/dashboard-server.json. Global skills were not updated; a fresh temporary installation was used to test independence.

## Validator Summary

Python 402 and JavaScript 134 passed. Three-skill distribution checks and a copied standalone loop CLI passed. Browser and preservation checks are recorded in [migration evidence](evidence/2026-09-06-studio-runtime-separation.md). Repo Docs finalization verifies the complete changed-file set after the final documentation update.
