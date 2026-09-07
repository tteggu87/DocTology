---
status: Active
source_of_truth: false
last_updated: 2026-09-07
superseded_by: N/A
---

# Impact summary

## Changed

The chat mode settings now work on normal dashboard launches. Users select wiki reading or native Pi from the screen; no command-line flag is required. Selection creates a new conversation, persists through browser history, and closes an idle native session when returning to wiki reading. The legacy launch flag remains accepted for compatibility.

The UI-selected native Pi path keeps Pi's native process, tools and transcript across turns inside the existing Studio UI. Runtime owns session/turn identity, durable request receipts, native interaction forwarding and the existing writer lease for the live session. The UI displays native tools and reported statistics without verified-citation claims. See [operation and storage](../dashboard/README.md#pi-기본-세션-사용하기--실험).

Current architecture, maps and usage distinguish default read-only chat from native file-changing sessions. Lifecycle regressions preserve delayed-turn cleanup and canceled-start ownership failures found in review. The local cycle casebook records proof and next gates.

### Files

- `.re0/iteration/v1.1.0-provisional-native-pi-rpc/DESIGN.local.md`
- `.re0/iteration/v1.1.0-provisional-native-pi-rpc/EVIDENCE.local.md`
- `.re0/iteration/v1.1.0-provisional-native-pi-rpc/REF-decisions.local.md`
- `.re0/iteration/v1.1.0-provisional-native-pi-rpc/RETRO.local.md`
- `.re0/iteration/v1.1.0-provisional-native-pi-rpc/WORKFLOW.local.md`
- `AGENTS.md`
- `README.md`
- `dashboard/README.md`
- `dashboard/app.js`
- `dashboard/index.html`
- `dashboard/modules/history-codec.js`
- `dashboard/modules/native-pi.js`
- `dashboard/modules/retrieval-status.js`
- `dashboard/style.css`
- `docs/ARCHITECTURE.md`
- `docs/CURRENT_STATE.md`
- `docs/IMPACT_SUMMARY.md`
- `docs/repo-map/DATA_FLOW.md`
- `docs/repo-map/ENTRYPOINTS.md`
- `docs/repo-map/MODULES.md`
- `runtime/wiki_dashboard.py`
- `runtime/wiki_dashboard_http.py`
- `runtime/wiki_dashboard_native.py`
- `tests/dashboard/dashboard_ui.test.cjs`
- `tests/dashboard/frontend_modules.test.cjs`
- `tests/test_wiki_dashboard_native.py`
- `wiki/_meta/log.md`

## Checked Not Changed

The default isolated read-only chat, reusable loop gates, three source skills and installer retain their responsibilities. Native file writes are not wiki certification. No global install or default-mode switch is part of this slice.

## Legacy split

Studio remains in repository `runtime/` and `dashboard/`; no application copy or gate executable is installed into a vault or skill. Earlier migration outcomes remain historical in [migration evidence](evidence/2026-09-06-studio-runtime-separation.md).

## Wiki memory

[The log](../wiki/_meta/log.md) records the native boundary. The local re0 casebook retains lifecycle anti-patterns, negative tests and Windows parity as the next gate. Browser history is a display projection; losing it does not delete Pi history, but Studio cannot re-import that history in this slice.

## Remaining Drift

Actual Windows terminal/RPC parity and default cutover are unpassed. Generic tool activity does not establish citation validity or retrieval method. Custom TUI interfaces are not universally supported. Existing SQLite ResourceWarnings remain in the Python suite.

## Validator Summary

Python 456 tests and JavaScript 154 tests passed; three-skill check passed. Real local Pi/browser checks covered read/recall/write, native resume, supported dialogs, browser reload and abort. Separate architecture and acceptance reviews approved the bounded opt-in slice. Repo Docs validation reports zero errors and warnings with the changed-file list.
