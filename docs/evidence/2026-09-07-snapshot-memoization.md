---
status: Active
source_of_truth: false
last_updated: 2026-09-07
superseded_by: N/A
---

# Snapshot performance audit and memoization

| Proposed optimization | Audit and result |
| --- | --- |
| Stat-based invalidation | Already present in dashboard snapshot reuse; now covers device identity, optional warehouse JSONL and resolved/internal-symlink identity. |
| Per-run project-status memoization | Added to the runtime catalog. Run file stat alone is insufficient: source, common wiki/AGENTS/warehouse files and the procedure contract also participate. |
| Compute outside lock, publish atomically | Already implemented with single-flight calculation, root/revision checks and guarded publication. Preserved. |
| Indexed coverage loop | Already reads/parses each report once and groups it by raw path. Preserved. |

Additional changes cache parsed run JSON, reuse the last graph when its pages
are unchanged, and index batch membership by source/run. A 2048-entry LRU memo
and one graph bound retained entries; deepcopy prevents callers from mutating
cached values. Full coverage validation and live batch certification checks
remain outside the run projection memo. Standalone loop gates are unchanged.

## Verification

Python 433 tests and JavaScript 144 tests passed. Skill inventory and Repo Docs
checks reported no errors or warnings. New regressions verify one-run misses,
source-specific invalidation, whole-wiki/contract/warehouse invalidation, copy
isolation and legal internal symlink retargets between identical-inode hardlinks.
An independent reviewer reproduced the symlink edge, then verified the fix
against exact gate fingerprints.

A synthetic local macOS vault contained 635 raw sources, 639 receipts, 1328 wiki
files and 510 runs. Comparing with commit `f0c27f0`, one sample measured:

| Scenario | Before | After |
| --- | --- | --- |
| Cold snapshot | 4.701 s | 4.879 s |
| Only one run record changed | 4.725 s | 0.412 s |

Source status and graph payloads matched exactly. The approximately 11.5x gain
applies to this incremental-update case, not initial loading, model response
latency, or all wiki changes. Common wiki changes still invalidate affected
status fingerprints. This is a synthetic local timing sample, not a benchmark
of the user's other computer.
