---
status: Active
source_of_truth: false
last_updated: 2026-09-07
superseded_by: N/A
---

# Impact summary

## Changed

New conversations default to native Pi in eligible wiki workspaces by explicit user request. Existing conversations remain unchanged, explicit wiki-reading choices survive reload, and project workspaces retain wiki reading. Choosing the default does not start a model until a question is submitted.

Native answers now connect explicit local source links to successful read excerpts from the active Pi session branch. Incremental native entries restore previous-turn sources without replaying browser history or adding a model call. References open the matched source snapshot, and the graph distinguishes read documents from cited ones. This confirms surviving-excerpt provenance, not semantic truth or full-file version identity.

The chat grid reserves a separate controls row and hides unsupported save actions in native mode. Markdown tables support alignment, escaped pipes, inline formatting and citation links within a horizontally scrollable table. Citation nodes and labels render above other graph layers. Prepared SQLite/ONNX states use a subtle green badge and status dot while preserving inference/usage caveats.

### Files

- `AGENTS.md`
- `dashboard/README.md`
- `dashboard/app.js`
- `dashboard/index.html`
- `dashboard/modules/graph.js`
- `dashboard/modules/history-codec.js`
- `dashboard/modules/markdown.js`
- `dashboard/modules/native-pi.js`
- `dashboard/modules/retrieval-status.js`
- `dashboard/style.css`
- `docs/ARCHITECTURE.md`
- `docs/CURRENT_STATE.md`
- `docs/repo-map/MODULES.md`
- `runtime/wiki_dashboard.py`
- `runtime/wiki_dashboard_native.py`
- `runtime/wiki_dashboard_native_citations.py`
- `tests/dashboard/dashboard_ui.test.cjs`
- `tests/test_wiki_dashboard_native_citations.py`
- `wiki/_meta/log.md`

## Checked Not Changed

Read-only chat remains available; eligible wiki workspaces default to native Pi for new conversations by user choice. Reusable loop gates, three source skills and installer retain their responsibilities. Native file writes are not wiki certification. No global skill install is part of this change.

## Legacy split

Studio remains in repository `runtime/` and `dashboard/`; no application copy or gate executable is installed into a vault or skill. Earlier migration outcomes remain historical in [migration evidence](evidence/2026-09-06-studio-runtime-separation.md).

## Wiki memory

[The log](../wiki/_meta/log.md) records the native boundary. The local re0 casebook retains lifecycle anti-patterns, negative tests and Windows parity as the next gate. Browser history is a display projection; losing it does not delete Pi history, but Studio cannot re-import that history in this slice.

## Remaining Drift

Actual Windows terminal/RPC parity remains unverified despite the user-authorized default change. Generic tool activity does not establish citation validity or retrieval method. Custom TUI interfaces are not universally supported. Existing SQLite ResourceWarnings remain in the Python suite.

## Validator Summary

Python 462 tests and JavaScript 163 tests passed; three-skill check passed. Real local Pi/browser checks cover a table with one cited and one read-only document, reference click-through, no-tool follow-up citation, and native resume. A separate code reviewer approved the excerpt-provenance contract and rendering changes. Synthetic rendering checks at 1152px and 760px verified unobstructed mode controls, separate message/composer rows and ready-state badge styles; these do not claim actual ONNX inference. Repo Docs validation reports zero errors and warnings with the changed-file list.
