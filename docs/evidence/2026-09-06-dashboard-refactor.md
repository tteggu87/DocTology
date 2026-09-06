---
title: Wiki Studio modular refactor verification
type: evidence
evidence_id: EVIDENCE-2026-09-06-DASHBOARD-REFACTOR
date: 2026-09-06
status: Active
source_of_truth: false
last_updated: 2026-09-06
superseded_by: N/A
target_fingerprint: sha256:9f0a93009f256be42e697c6feac82b7359fbe3b247c0a00e5f0e5fe05acc7df3
---

# Modular refactor verification

The [maintenance map](../../dashboard/README.md#유지보수와-확장-경계) defines the current ownership and extension points. This is a behavior-preserving decomposition, not a new engine, framework, or completion authority.

## Checks

- Python: 385 passed using the existing QA environment with PyYAML. JavaScript: 134 passed. Distribution validation passed; whitespace checks passed. Existing SQLite ResourceWarnings remain.
- Fourteen fixed-fixture document, candidate, and snapshot comparisons matched the captured pre-refactor implementation. This is bounded equivalence evidence, not a proof for all inputs.
- Existing UI contracts now load the actual HTML-declared scripts without rewriting application source. Separate module tests invoke every exported helper/render path without app globals. Cold boot executes the external bootstrap twice and observes one session/state fetch and one refresh interval.
- HTTP tests fetch every declared production asset with matching bytes, MIME, and CSP. Arbitrary files, unsafe/duplicate declarations, and undeclared assets remain denied. Independent scoped backend review found no blocker in dependency direction, compatibility, root/lock checks, authentication, or partial-save responses.
- Live browser at `http://127.0.0.1:4341/`: two preserved conversations, 19 graph documents/78 links, citation document opening, SQLite/ONNX details, and bounded in-app folder browsing. No page errors were observed. This pass did not invoke a real model or a native OS dialog.
- All 24 user raw/wiki files remained byte-identical. CSS and the HTML body matched the baseline exactly. Script declarations changed, not visual markup.

## Repairs and limits

Regression testing caught a missing Unicode import in the chat error classifier; it was restored. A pre-existing retry test waited for a terminal worker label before cleanup finished; it now waits for the existing `retryEligible`/`cleanupPending` contract. Production retry gates were not relaxed.

Initial module-load-only tests missed hidden app globals in graph rendering and status normalization. The dependencies were made explicit/local and the isolated tests now execute those paths. New module logic was formatted for reading rather than compressed to reduce line counts. Cold reading clarified dependency origins, registry scope, and restart requirements in the guide.

Shared application state and asynchronous lifecycle remain in the composition files intentionally; they were not distributed across new globals. No performance improvement or fully decoupled application architecture is claimed. Existing model, writer, cancellation, recovery, and completion gates remain unchanged.

The previous server was left untouched because process inspection was unavailable in this execution environment. Its legacy asset handler does not serve the new module URLs; use the new address. Deployment metadata is in `state/dashboard-server.json`.

## Fingerprint

The 42-file fingerprint uses the previous ordered groups: skill `SKILL.md`, sorted `scripts/wiki_dashboard*.py`, sorted `scripts/wiki_dashboard*.mjs`, **all recursively sorted files in `dashboard/`**, sorted `evals/*.cjs`, and sorted `tests/test_wiki_dashboard*.py`. Feed each repository-relative POSIX path, NUL, file bytes, and NUL into SHA-256. Recursive asset coverage replaces the previous immediate-directory enumeration so new modules cannot escape the build fingerprint.
