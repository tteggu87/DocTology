---
title: Wiki Studio parallel preparation independent review
type: review
review_id: REVIEW-2026-09-06-WIKI-PARALLEL-PREPARATION
status: accepted
date: 2026-09-06
implementation_status: complete
source_of_truth: false
reviewed_target: Parallel source preparation additions under the existing Wiki Studio batch procedure
target_fingerprint: sha256:21f099b61aa1e695ceb71e352cef1171ca543a3b7a4c4146bf71a01b5354b262
related_decisions:
  - ../adr/ADR-0003-wiki-parallel-preparation.md
evidence_refs:
  - ../evidence/2026-09-06-wiki-parallel-preparation.md
related_plan: ../plans/2026-09-05-wiki-parallel-preparation.md
---

# Wiki Studio parallel preparation independent review

## Disposition

Accepted. The implementation preserves existing-loop completion authority and completes the requested parallel-preparation feature. The review does not certify general model quality, latency, or throughput.

## Confirmed repairs and boundaries

- Production inventory now includes required `AGENTS.md`; production-helper and source-comparison checks cover the mismatch that mocked helpers concealed.
- Stop/retry/publication races, old-attempt-map clobbering, and hidden live-process cleanup were repaired. While a stubborn process is live, the attempt map remains, `cleanupPending` is true, and retry is ineligible; a repeat close after actual exit clears the state.
- A normal partial-link-planning fault retains its batch and source-run IDs, then repairs links without duplicates.
- Resume receives exact frozen JSON. Regenerated plans remain rejected; immutability was not weakened.
- `통합 재개` reuses prepared workers in the same batch and restores only original built-ins at writer handoff.

The clean fixture’s integration resume correctly remained not ready when the index lacked ingest-report links. Its original applied batch was preserved, not resealed or rewritten. A fresh existing-runtime corrective batch performed a manual semantic repair limited to the two missing index links, then certified through the usual procedure. That is evidence of the gate, not a bypass.

## Retained manual boundary

A hard crash between `start_run` persistence and the supervisor checkpoint fails closed with an orphan candidate. Recovery is manual inspect-and-link-run; no automatic adoption, deletion, or duplicate creation is allowed.

## Evidence quality

The closed-source raw/wiki comparison found no material omission, unsupported addition, or changed condition. The fixture has two four-unit receipts, each with four projected, zero omitted, and zero deferred. The review records N=2 synthetic evidence only.

Mandela risks remain: verifier-designer dependence and shared-hallucination risk. Cross-module production-helper tests, real PIDs and reads, and independent raw/wiki comparison reduce coupling, but no independent quality or latency benchmark is claimed. The SSOT audit limits and single completion authority remain consistent; no broad consolidation is warranted.

See the [verification record](../evidence/2026-09-06-wiki-parallel-preparation.md).
