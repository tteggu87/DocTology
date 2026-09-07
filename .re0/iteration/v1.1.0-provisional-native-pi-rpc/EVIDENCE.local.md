# Native Pi slice evidence — 2026-09-07

Decision: keep the opt-in slice; no default cutover. Baseline commit d2a9e3b, local macOS, Pi 0.82.1, gpt-5.5 / medium. Windows parity remains unpassed.

| Gate | Result | Evidence |
| --- | --- | --- |
| G1 | local pass | Native command is installed Pi plus --mode rpc, optional model/resume; no --no-* resource/tool suppression. Native read/write/bash observed. |
| G2 | local pass | First three browser turns share PID 55967, native session 01a07aaf-ef92-70d7-97da-c5bd693826af. Explicit close/restart resumes same session with PID 59766; recall succeeds without tools. |
| G3 | local pass | 21 focused protocol/lifecycle cases; actual reload during response recovers result; actual bash sleep20 stopped through UI. |
| G4 | local pass | Writer contention, root switch, stale generation, resume mismatch, canceled startup/cleanup failure and late-turn state-request regressions. |
| G5 | local pass | Real existing three-column browser surface, native history after reload, generic tools and disabled unsupported citation/save controls; 152 JS tests. |
| G6 | local pass, bounded | Real confirm/select/input/editor roundtrip with explicit QA extension; masked option maps to original value. Input wait exceeds 30 seconds without killing request. Unsupported cases covered by protocol tests. |
| G7 | local pass, bounded | First three turns show cacheRead 4608 / 9216 / 24064 cumulative, tools 1 / 0 / 2. FTS/vector/link remain unmeasured, not zero. No universal secret scrub claim. |
| G8 | pass | 456 Python tests and three-skill check pass. Gate and skill code unmodified; native write is not certification. |
| G9 | pass | AGENTS mechanism, user README, current architecture/state/maps and wiki log reflect native scope. Repo Docs errors 0 / warnings 0 with changed-file input. |
| G10-local | pass | Native process, real browser and filesystem evidence plus separate architecture review approved; separate acceptance reviewer approved the bounded scope. |
| G10-Windows | unpassed | No actual Windows execution available. macOS evidence does not establish Windows parity or permit default cutover. |

## Observable scenario

Synthetic vault: `state/native-pi-qa/vault`. First prompt reads `wiki/concepts/native-start.md`; the marker is WIKI-QA-7319-ZK and the link is native-linked. Second prompt asks for the marker without tools and gets it. Third prompt asks to read the linked document and write only `state/native-session-note.md`; the file independently contains the linked sentence and remembered marker. No browser history text is sent on native followups.

Then explicitly close, restart the owned QA server, retain the native session ID, run supported extension dialogs, and reload the browser during another marker-recall turn. The answer appears once with no tool call. A later bash sleep20 turn is stopped and its registry status is stopped; process remains available; a subsequent no-tool marker recall succeeds on the same PID 59766.

## Local evidence files

- `state/native-full-tests.log`: 456 tests, OK; pre-existing SQLite ResourceWarnings remain.
- `state/native-ui-full.log`: 152 tests, pass.
- `state/native-focused-tests.log`: native lifecycle cases (final full suite includes all 21).
- `state/native-skills-check.log`, `state/native-docs-validation.log`.
- `state/native-browser-proof.txt`, `state/native-session-proof.json`, synthetic note and server registry. These ignored local files supplement this durable summary; no private full Pi transcript is copied into the repository.
- `tests/test_wiki_dashboard_native.py` and `tests/dashboard/dashboard_ui.test.cjs` retain reproducible negative cases independent of the paid model.

## Negative corpus and limits

The initial project-local QA extension was not loaded because native Pi requires project trust; the unknown slash command reached the model. This is not an interaction pass. The later test server explicitly supplied `-e` for the synthetic extension without changing global trust. First-three-turn continuity used native defaults; the dialog run has this stated resource difference. No universal TUI-extension equivalence is claimed.

Review reproduced two lifecycle defect families: a delayed prior-turn control failure could close the next turn; canceled startup could lose child ownership on failed termination. Fixed with a dispatch barrier, captured settled identity, and retained in-memory plus durable PID ownership until verified cleanup. Deterministic regressions cover both. Review approval is scoped architecture evidence, not Windows or product-quality proof.

Mandela audit: these developer-designed synthetic scenarios demonstrate session/protocol contracts only. They are not a held-out answer-quality benchmark or a performance comparison. The independent observations are Pi process/session records, native tool events, on-disk output and browser behavior; fixture instructions are not evidence of production reasoning quality. Cache counts are observed totals, not an efficiency claim.

## Final review

The architecture reviewer approved after reproducing and rechecking the lifecycle fixes (21 native tests). A separate acceptance reviewer approved the local opt-in slice against code, test logs, browser transcript and native session summary. The latter explicitly distinguishes native session resume from full UI history restoration; the limitation is retained in the usage guide.
