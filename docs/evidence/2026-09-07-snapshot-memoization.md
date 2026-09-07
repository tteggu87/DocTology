---
status: Active
source_of_truth: false
last_updated: 2026-09-07
superseded_by: N/A
---

# Studio performance: current costs and next decision

## Current guarantees

The [document catalog](../../runtime/wiki_dashboard_documents.py) caches parsed run JSON and project-status projections in a shared 2048-entry LRU, plus one graph. Projection keys cover the selected run, source, common wiki/AGENTS/warehouse files, procedure contract, resolved target paths and symlink metadata. Copies protect cached values from callers. Cache eviction can cause additional recomputation even when a dependency is unchanged.

The [dashboard](../../runtime/wiki_dashboard.py) calculates snapshots outside its main lock and publishes only a matching root/revision. Stat-equivalent snapshots are reused. Coverage reports and batch membership use indexes; exact coverage validation and current batch certification remain outside the projection memo. The [loop gates](../../.agents/skills/llm-wiki-loop/scripts/wiki_workflow.py) remain authoritative.

The existing implementation passed 433 Python and 144 JavaScript tests. The prior 635-source/510-run experiment measured a one-run update at 4.725 s before memoization and 0.412 s afterward, with identical source and graph output. This benefit applies while the useful entries remain cached; it is not a claim about all corpus sizes or initial loading.

## Real HTTP observations

Analysis baseline: commit `82bce10`, local macOS, synthetic vault with 635 raw files, 639 receipts, 1328 wiki files and 510 runs. Requests used the real dashboard and tool HTTP handlers. No production runtime files were modified for these measurements.

| Request | Unprofiled observation | Interpretation |
| --- | --- | --- |
| Connect with SQLite preparation | 5.661 s | Initial corpus preparation still dominates. |
| Unchanged `/api/state` | Median 13.5 ms across five requests; 907215 response bytes | Current server response is short, but the full static snapshot is transmitted repeatedly. |
| Narrow SQLite `wiki_search` | 257 ms | Few candidate bodies do not eliminate the full inventory/freshness work. |
| `wiki_read` | 178 ms | Payload metadata still builds a whole inventory. |
| `wiki_links` | 570 ms | Three catalog inventory constructions occur in one link request. |
| `wiki_list`, limit 40 | 261 ms | Pagination happens after all eligible titles are read. |

An instrumented corpus-change rebuild called the per-group relative-path sorting key 678300 times, exactly 510 groups × 1330 files. Instrumentation increases elapsed time, so its timings are not comparable with the unprofiled request timings above. The call count identifies duplicated CPU work after file hashing has already been shared.

## Controlled fingerprint experiment

A disposable-process prototype reuses relative-path sorting keys once per fingerprint invocation. A second variant also reuses each row's exact canonical JSON bytes. Neither changes the file set, ordering, hash format, or before/after/final file-change checks. Combining separate common/source hashes is excluded because it changes the original digest.

Each variant used three real HTTP cold connections with fresh application/catalog objects and SQLite preparation disabled in every trial. Thus these results must not be subtracted from the SQLite-enabled connection measurement to infer SQLite's cost.

| Variant | HTTP connection samples, seconds | Median |
| --- | --- | --- |
| Production baseline | 5.2847, 5.3466, 5.3514 | 5.3466 |
| Reuse relative-path keys | 1.4922, 1.4710, 1.4912 | 1.4912 |
| Reuse keys and canonical row bytes | 1.1972, 1.1998, 1.1932 | 1.1972 |

Every trial returned identical source, graph and batch payloads. Additional checks preserved Unicode/JSON-punctuation and empty-group digests; both baseline and prototype rejected a file changed during fingerprint calculation. The approximately 4.47× whole-connection gain is an experiment, not a shipped optimization or proof of the full gate suite on the prototype.

## Negative corpus for the next iteration

- **Compute-sharing gap:** reading a file hash once still leaves repeated path normalization, sorting-key construction and JSON serialization. Next gate: preserve exact digest bytes, symlink semantics and concurrent-change rejection while eliminating repeated formatting.
- **Pagination after full reads:** `wiki_list(limit=40)` opened 1328 full document bodies. Enlarging concept pages to approximately 200 KB raised bytes read from 335099 to 137735786; observed local HTTP time was 0.2664 versus 0.3026 s. This proves read amplification, not a measured improvement from a replacement. Next gate: normal first-page listing reads only page-sized title data, and never invents corpus-wide readability counts from unchecked metadata.
- **Shared-cache phase eviction:** with one selected run per source, changing one run recomputed one status at 1000 sources/runs, but 152 at 1100; the latter filled all 2048 entries. This proves competition between JSON and projection entries, not an optimal replacement policy. Next gate: compare equal memory budgets across 1000/1100/1500/2000 selected runs and repeated one-run edits. Prefer preserving costly projections and only the latest JSON stamp per path; blindly raising the limit or dividing it into two 1024-entry LRUs can merely move or worsen the threshold.
- **Search freshness on the critical path:** every search rebuilds/validates inventory and enters SQLite `BEGIN IMMEDIATE` through `ensure`, even when file bodies need no update. Next gate: share a validated inventory within one request first. Any longer-lived generation must detect external additions, text edits, deletions and symlink changes; successful commit must precede generation publication. Revalidating a found document alone cannot prevent missing new search results.
- **Full snapshot polling:** approximately 907 KB is returned each unchanged poll. A future small envelope can separate static source/graph revision from live job, queue and progress data. Next gate: browser measurements must justify the change; server restart, root switch and unknown revision must force a full snapshot, while stop/progress signals remain live. Static revision alone must never suppress dynamic updates.

## Decision

**Iterate in place.** Preserve the current gates, cancellation contract, dependency keys and snapshot publication boundary. The next implementation should be one narrow fingerprint-formatting optimization, followed by the full gate suite and the same HTTP equality/drift scenarios. Do not introduce a new runtime or another persistent cache for this step.

After that gate clears, evaluate request-local inventory/title reuse and cache retention policy. Treat full-snapshot polling as a later payload/browser concern: its measured 13.5 ms server response is not currently the main latency problem. Longer-lived search generations require new external-change evidence before implementation.

This analysis lap refreshes the performance record only. Local SSD synthetic timings do not predict another computer, a network drive or model response latency.
