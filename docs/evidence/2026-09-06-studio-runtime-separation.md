---
title: DocTology Studio runtime separation verification
type: evidence
evidence_id: EVIDENCE-2026-09-06-STUDIO-RUNTIME-SEPARATION
date: 2026-09-06
status: Active
source_of_truth: false
last_updated: 2026-09-06
superseded_by: N/A
related_decision: ../adr/ADR-0004-studio-runtime-separation.md
target_fingerprint: sha256:a052b9f1c23761edb75628fd08605491d07b2af0aa98e38c18659ff94e2365dc
---

# Studio runtime separation verification

## Result

[ADR-0004](../adr/ADR-0004-studio-runtime-separation.md) is implemented. DocTology owns `runtime/`, `dashboard/`, and `tests/dashboard/`; the loop skill retains gates and no app source, UI, launchers, or JS evaluations. The root desktop files forward to runtime-owned launchers. This is an ownership/dependency migration, not a replacement workflow engine.

The runtime's sole skill-location binding is `wiki_loop_adapter.py`. Writer `--skill` selects the actual loop skill; the trusted prompt names its actual Python gate entrypoint. Runtime extensions stay in `runtime/`. No new Pi CLI flag or completion gate was added.

## Verification

- Python: `python -m unittest discover -s tests -q` in the existing PyYAML QA environment, **402 passed**. JavaScript: `node --test tests/dashboard/*.test.cjs`, **134 passed**. Existing SQLite ResourceWarnings remain.
- `python3 scripts/manage_skills.py check` passed. Installing all three skills into a fresh temporary directory and invoking the copied loop's `wiki_loop.py --help` worked without any Studio files. The user's global skill installation was not changed.
- The four original loop implementation files remained byte-identical. The loop's `SKILL.md` intentionally replaces app-specific guidance with a one-way application-integration boundary; gate code and completion contracts were not moved or rewritten.
- Ten UI assets, excluding the updated README, were byte-identical to their committed pre-move versions. Production HTML script ordering and HTTP allowlisting remain authoritative.
- Ownership tests reject app remnants/back-imports in the loop skill. Writer-argument tests inspect the actual existing Pi invocation and prompt. Project inventory reads root `dashboard/README.md` and `runtime/README.md`, retains ordinary skill contracts, and does not expose arbitrary files.
- Independent code review found no runtime, writer-path, adapter-direction, gate-location, static-serving, or launcher-path blocker. Stale ADR implementation links found by review were corrected separately from historical fingerprints.
- The real root launcher started the new application at `http://127.0.0.1:4343/` with Pi detected, watcher OFF, and auto-run OFF. Browser inspection confirmed 19 documents, 78 links, restored conversations, and citation-document opening, with no observed page errors.
- Both existing conversations were restored to the new origin. The 104,617-character browser-local record matched exactly before further interaction. All 24 user raw/wiki files remained byte-identical. No model prompt or source-writing job was submitted during migration.

## Review lessons and limits

A proposed test incorrectly expected a nonexistent Pi `--gate-path` option; the correct contract is the gate command inside `--append-system-prompt`. Another test confused a reusable `SKILL.md` with the removed skill-internal dashboard guide. Those test expectations were corrected rather than changing production behavior to satisfy invented requirements.

The first direct test launch inherited a PATH without Homebrew and did not detect Pi. Launching through the actual root command supplied the intended process-local tool paths and restored detection. Process inspection/signalling for existing background instances was denied by this environment, so they were not forcibly stopped. The intermediate 4342 instance and older addresses are not the final handoff. Current local metadata is in ignored `state/dashboard-server.json`; URL/PID values are observations, not permanent identifiers.

Windows BAT contracts remain statically checked, not Windows real-desktop or Pi-process validation. This pass does not claim model quality, model authentication success, a performance improvement, or new FTS/vector chat routing. Existing chat/writer/cancellation/recovery contracts have regression coverage; a fresh real-model ingest was not performed.

## Fingerprint scope

Sort the 50 repository-relative POSIX paths from: root `.gitattributes`, both root desktop launchers, loop `SKILL.md`, runtime `*.py`, `*.mjs`, `*.command`, `*.bat` and `README.md`, all recursive dashboard files, `tests/test_wiki_dashboard*.py`, and `tests/dashboard/*.cjs`. Feed each path, NUL, working-file bytes, and NUL into SHA-256. Shell permissions are tested separately; BAT working files retain CRLF. The four unchanged gate implementation hashes were compared independently. Earlier evidence fingerprints remain evidence for their original layouts.
