---
title: Parallel source preparation within the Wiki Studio batch
type: adr
decision_id: ADR-0003
decision_status: implemented
implementation_status: verified
date: 2026-09-06
implementation_plan: ../plans/2026-09-05-wiki-parallel-preparation.md
implementation_refs:
  - ../../.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_batch.py
  - ../../.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_batch_tools.py
  - ../../.agents/skills/llm-wiki-loop/scripts/wiki_dashboard_batch_extension.mjs
implementation_evidence:
  - ../evidence/2026-09-06-wiki-parallel-preparation.md
source_of_truth: true
last_updated: 2026-09-06
superseded_by: null
---

# ADR-0003: Parallel source preparation within the Wiki Studio batch

## Decision

For an explicit two-to-twelve-source Wiki Studio request, prepare source-owned drafts concurrently inside the existing loop batch. Use three workers by default and no more than four. Single-source work remains unchanged.

Workers and the coordinator are separate Pi runtime processes, not new kanban lanes. Workers receive four read-tool types, `wiki_list`, `wiki_search`, `wiki_read`, and `wiki_links`, plus source-owned `draft_write` and `draft_submit`. They can read their assigned raw source, existing wiki context, and the vault `AGENTS.md`; writes are batch-state drafts only. The coordinator initially has the read tools and `wiki_prepare_batch`; original built-ins return only after each matching worker submits a fresh, source-bound draft with complete required reads. Preparation is not semantic correctness or certification.

The existing plan/link/pre-mutation runs, state-only semantic reconciliation, one writer apply, question receipts, and snapshot seal remain the exclusive canonical completion authority. This implementation introduces neither LangGraph nor another completion authority.

## Consequences and operating boundary

Supervisor state persists under `state/dashboard_jobs/parallel/`. Stop/retry is explicit per source and hash-bound; restart does not automatically resume a model. Applied or stale batches cannot reprepare. Queue grouping keeps each individually authorized current-hash pending source and preserves sibling batch authority. Watch and `autoRun` stay separate off-by-default opt-ins; read-only chat stays independent.

Integration reuse is gate-bound: an original applied batch that is not ready stays blocked and unsealed. A new existing-runtime batch may perform a bounded manual semantic repair, then must complete the ordinary procedure. A hard crash between `start_run` persistence and supervisor checkpoint fails closed with an orphan candidate and requires manual inspect-and-link-run recovery. Automatic adoption, deletion, and duplicate creation are forbidden.

The implementation evidence and limits are in the [verification record](../evidence/2026-09-06-wiki-parallel-preparation.md), with review disposition in the [independent review](../reviews/2026-09-06-wiki-parallel-preparation.md).
