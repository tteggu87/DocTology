---
title: Wiki Studio desktop launcher verification
type: evidence
evidence_id: EVIDENCE-2026-09-06-WIKI-LAUNCHERS
date: 2026-09-06
status: Active
source_of_truth: false
last_updated: 2026-09-06
superseded_by: N/A
target_fingerprint: sha256:446b2678a9f0b3774799827cefd6ae6e183145ba8fb6054319a7896470033f22
---

# Desktop launcher verification

This is the pre-separation launcher record. Its fingerprint and skill-owned paths describe that historical layout; [runtime separation verification](2026-09-06-studio-runtime-separation.md) covers the current application paths. The guide link below points to current usage, not a reconstruction of this earlier target.

The [desktop guide](../../dashboard/README.md#더블클릭으로-실행) documents the root macOS `.command` and Windows `.bat` entry files. They forward to the loop skill's own launchers and existing Python server, without copying runtime or gate logic to the repository root.

## Verified

- Python 399 tests and JavaScript 134 tests passed; 14 Python tests specifically cover launchers, version/path handling, port selection, browser behavior, and startup cleanup. Three-skill distribution validation passed. Existing SQLite ResourceWarnings remain.
- From a different working directory, the actual macOS shell launcher started the real server on an ephemeral loopback port. `GET /api/state` reported the unconnected example mode. A Ctrl+C signal stopped it with exit code 0. No user workspace or model was involved. This verifies shell invocation, not Finder or OS-browser GUI automation.
- Quoted paths containing spaces/Unicode, argument forwarding, missing Python, nonzero exits, and executable permissions were tested. Windows command behavior was reviewed statically, not executed on a Windows machine.
- Real socket tests preserve an occupied listener and select a higher free port only with auto-port enabled. Permission errors are not treated as collisions. Direct Python CLI defaults still do not open a browser or choose another port automatically.
- Mocked browser tests verify the selected bound URL, startup ordering, and nonfatal browser failures. Existing desktop restrictions were not bypassed.
- Startup-worker failure now explicitly cleans up this application's resources. Independent review verified that persisted external runner records are not adopted or terminated by that cleanup.
- Windows launchers locally disable manager/legacy automatic runtime installation variables. This follows the [Python Windows launcher configuration](https://docs.python.org/3/using/windows.html#configuration); no global environment or system policy is changed. Platform-native line endings are declared in `.gitattributes`.

## Limits

Python 3.11+ must already be installed. AI features separately require Pi installation and authentication. Windows real-desktop/Pi-process behavior remains unverified. A different port has a different browser-local history; launchers do not migrate or delete it, reuse an unverified service, or kill an occupied process. Default startup chooses no workspace and does not enable watching or model work. An explicit `--repo-root` continues to respect that workspace's previously authorized automation configuration.

The fingerprint covers seven files, sorted by repository-relative POSIX path: `.gitattributes`, both root launchers, both skill launchers, `scripts/wiki_dashboard.py` within the loop skill, and `tests/test_wiki_dashboard_launchers.py`. Each path, NUL, working-file bytes, and NUL is fed to SHA-256. Shell permission bits are checked separately; BAT working-file bytes use CRLF.
