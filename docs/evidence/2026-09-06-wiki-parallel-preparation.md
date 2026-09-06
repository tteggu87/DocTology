---
title: Wiki Studio parallel preparation verification
type: evidence
evidence_id: EVIDENCE-2026-09-06-WIKI-PARALLEL-PREPARATION
date: 2026-09-06
subject: Parallel source preparation, existing batch-gate delegation, and bounded repair
target_fingerprint: sha256:21f099b61aa1e695ceb71e352cef1171ca543a3b7a4c4146bf71a01b5354b262
status: completed
implementation_status: complete
source_of_truth: false
last_updated: 2026-09-06
superseded_by: N/A
related_plan: ../plans/2026-09-05-wiki-parallel-preparation.md
related_decision: ../adr/ADR-0003-wiki-parallel-preparation.md
---

# Wiki Studio parallel preparation verification

## Result

The requested existing-loop parallelization is complete. Two source workers prepared concurrently inside the existing batch procedure; canonical completion still required the established plan, linked pre-mutation runs, one writer apply, question receipts, and snapshot seal. No LangGraph, new completion authority, or multiple canonical writers was introduced.

The final implementation target contains 26 files, fingerprinted with the same path, NUL, bytes, NUL algorithm as the 2026-09-05 dashboard evidence. Checks recorded 342 passing Python tests, 106 passing Node tests, `manage_skills.py check`, and `git diff --check`. Existing SQLite `ResourceWarning`s remained; a local PyYAML virtual environment was used without changing global dependencies.

## Concurrent preparation and gate behavior

In the clean two-source fixture, both Pi workers reached `attempt1prepared`. A 159-sample trace recorded both workers reading and drafting with distinct real PIDs and `readCount > 0`, including 80.69 seconds of observed engineering overlap. This proves concurrent first-attempt preparation, not a speedup benchmark.

`통합 재개` reused both prepared drafts in the same batch and restored only the original built-ins at writer handoff. It performed one apply, then correctly stopped as not ready because `wiki/_meta/index.md` lacked required ingest-report links. The original batch, `batch-20260905T170131Z-8d1475bc`, remains blocked and unsealed with its original apply fingerprint unchanged.

This is negative gate proof: the implementation did not bypass certification. The clean fixture was not an unassisted Pi end-to-end success.

## Bounded corrective batch

A new existing-runtime batch, `batch-20260905T173849Z-10667dd4`, performed bounded manual semantic repair. Reviewer `manual-semantic-repair-qa` added only the two ingest-report wiki links to `wiki/_meta/index.md`; it did not edit the old batch receipt or state and did not start model workers.

The corrective batch independently reported `certified`, `next_action: done`, and strict-check `status: ok`, `semantic_status: batch_ready`. Its final corpus fingerprint is `sha256:880d7cd5613a5105f36155ebb0ab7b16687c9256d077dabe0fd2be05c94d674e`. Both four-unit receipts were fresh and raw files remained unchanged. This establishes repair through a fresh batch and the existing seal, not a gate bypass.

The earlier recovery fixture remains independently certified as documented in the first fixture record: `batch-20260905T160110Z-b4e7b82b` is `certified` with `next_action: done`, strict-check `ok`, and `batch_ready`.

## Local deployment observation

The current local dashboard is `http://127.0.0.1:4333/` (PID 78422). The 24 user raw/wiki files matched their pre-launch hashes. Both browser-local conversations restored from port 4329 were byte-identical at 104,617 characters. Browser inspection confirmed watcher and `autoRun` off, the Pi default-model selection blank, and older local servers preserved.

## Limits

The fixtures are synthetic and bounded. They do not establish general model quality, semantic quality, latency, throughput, public deployment, or a speedup claim. Mandela risks that remain are verifier-designer and shared-hallucination dependence; production-helper cross-module tests, real-PID traces, and an independent raw/wiki reviewer reduce those risks but do not create an independent model-quality benchmark.

See the [completed plan](../plans/2026-09-05-wiki-parallel-preparation.md) and [implemented decision](../adr/ADR-0003-wiki-parallel-preparation.md).
