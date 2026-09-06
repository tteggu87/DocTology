---
title: Wiki Studio folder selection verification
type: evidence
evidence_id: EVIDENCE-2026-09-06-WIKI-FOLDER-PICKER
target_fingerprint: sha256:2e6cc2d2adf9a231a4f3efc0ddcc274c02458872a1fa6c8ec2f103d524981561
date: 2026-09-06
status: Active
source_of_truth: false
last_updated: 2026-09-06
superseded_by: N/A
---

# Wiki Studio folder selection verification

## Scope

Connection no longer requires typing a path. The native macOS/Windows picker only returns a folder. If native desktop access fails, a bounded in-app browser opens automatically; a direct in-app action is also available. Selection fills the existing form. Only its explicit connection action runs the unchanged workspace validation and live-work guards.

The browser visits one directory at a time, excludes files, hidden entries, and symlink entries, scans at most 5,000 entries, and returns at most 200 sorted directories with a truncation notice. No recursive search, file-content collection, upload, model invocation, or canonical write is part of selection.

## Verified observations

- Target fingerprint covers 27 files using the [dashboard evidence algorithm](2026-09-05-wiki-dashboard.md).
- Full Python suite: 357 passed. JavaScript contracts: 118 passed. Skill distribution and patch whitespace checks passed. Existing SQLite ResourceWarnings remain.
- Native command, cancellation, errors, timeout, Unicode paths, serialization, passive selection, and HTTP token/Origin protection have regression checks. Windows native invocation is mocked, not Windows desktop dogfood.
- The current restricted macOS process cannot reach the native window service. Native picker success is therefore **not** claimed for this environment.
- At `http://127.0.0.1:4336/`, an actual native failure automatically opened the in-app folder browser. Clicking the current wiki, choosing the folder, and submitting connected the existing workspace without typing any path.
- Both existing browser-local conversations were preserved. All 24 user raw/wiki files remained byte-identical across the checked connection flow. No test source was added to the user vault.

## Operational scope ledger

Security-policy weakening and elevated privileges were excluded. No administrator execution, security configuration change, quarantine removal, or installed login agent was used. Ordinary desktop launch attempts did not produce a confirmed GUI server; the final solution uses the bounded in-app browser instead. The unsuccessful temporary service definition was removed. This evidence record is the durable archive of that excluded/abandoned scope, not a launch instruction.

Older localhost instances were preserved where this environment did not allow signaling them. The latest local handoff is recorded in `state/dashboard-server.json`; opening a selector does not enable watching or automatic model work.
