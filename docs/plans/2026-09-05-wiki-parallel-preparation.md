---
title: Parallel source preparation in Wiki Studio
type: plan
plan_id: PLAN-2026-09-05-WIKI-PARALLEL-PREPARATION
status: completed
implementation_status: complete
source_of_truth: false
last_updated: 2026-09-06
superseded_by: N/A
related_evidence: ../evidence/2026-09-06-wiki-parallel-preparation.md
related_review: ../reviews/2026-09-06-wiki-parallel-preparation.md
---

# Parallel source preparation

## Delivered boundary

The user-selected existing-loop parallelization is complete. Explicit batches of two to twelve sources use three preparation workers by default and at most four. A single source keeps the existing path. There is no LangGraph, generic DAG framework, multiple canonical writer, or new completion authority.

Workers receive only `wiki_list`, `wiki_search`, `wiki_read`, `wiki_links`, source-owned `draft_write`, and `draft_submit`. Their writes remain inside their batch-state draft directories. The coordinator initially has those reads and `wiki_prepare_batch`; only the original built-ins return after every matching worker submits a fresh source-bound draft with complete required reads. Prepared drafts are not canonical mutation or completion.

Existing batch planning/linking, linked pre-mutation source runs, state-only reconciliation, one writer apply, representative question receipts, and snapshot seal remain the exclusive completion procedure. Source-specific stop/retry is explicit and hash-bound. Restart never resumes a worker automatically. Applied or stale batches cannot reprepare; a fresh batch is required when existing recovery cannot proceed. Authorized queue grouping preserves source provenance and retains siblings on retry.

## Verified outcome

The clean fixture proved concurrent first-attempt preparation: both workers reached `attempt1prepared`, read and drafted with distinct real PIDs, and had observed overlap. Integration reuse correctly stopped at a missing-index-link gate rather than certifying. A new existing-runtime corrective batch repaired only those links and certified through the usual procedure. The first recovery fixture is also certified.

The precise observations, checks, local deployment state, and limits are in the [verification record](../evidence/2026-09-06-wiki-parallel-preparation.md). The [accepted review](../reviews/2026-09-06-wiki-parallel-preparation.md) records the retained manual crash boundary and independent review disposition.
