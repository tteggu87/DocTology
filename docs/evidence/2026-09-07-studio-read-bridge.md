---
status: Active
source_of_truth: false
last_updated: 2026-09-07
superseded_by: N/A
---

# Studio read bridge and SQLite verification

The reported 15-second client abort was present in the extension. The server
had no matching per-request processing deadline, and read payloads repeatedly
scanned receipts and hashed unrelated raw sources. The document HTTP route
also held the application lock during payload I/O.

The repair adds server/client budgets of 30/35 seconds, disconnect detection,
one active HTTP operation per bridge, late-read evidence rollback, and closed
socket handling. Payload parsing reuses receipt metadata and checks only raw
sources relevant to the requested page. Named read targets are revalidated
against the approved surfaces and final citations retain exact byte/hash checks.
Document HTTP I/O now releases the app lock and rechecks the root before return.

The opt-in connection form (checked by default) prepares the Studio-owned
`state/studio_search.sqlite`, including wiki metadata and raw pages. Incremental
FTS updates use stable integer rowids; each search branch selects at most 120
candidates (240 combined), with explicit partial-result flags. The original
wiki index and vector lane are separate. No target-vault scripts execute.

## Reproductions

The focused regression suite covers late socket closes without server traceback,
a server timeout while file I/O is blocked, rejection of queued retries, late
candidate construction, late response construction and successful-call accounting,
preservation of prior evidence, source-receipt invalidation, current-path escape
checks, live index additions/edits/deletions, scoped candidate limits, unchanged
Markdown during connection, and document HTTP root changes without app-lock waits.
An independent reviewer reproduced and then rechecked candidate rollback, FTS
rowid updates, readiness wording, and scoped candidate limits.

## Real surface and timing observations

A local synthetic vault contained 635 raw files and 1,328 wiki files (including
639 receipts), totaling 1,963 indexed documents. An actual browser connection
showed SQLite preparation and the active chat badge. An actual Pi run on the
final runtime used one FTS search and one successful read, returned one numbered
reference, and finished in 10.616 seconds including model time.

A local timing sample measured:

| Operation | Observation |
| --- | --- |
| Cold Studio index | 0.260 seconds |
| Narrow `0686` literal scan | 1,963 document bodies, 0.289 seconds |
| Narrow `0686` FTS | 2 document bodies, 0.264 seconds |
| Broad `검증용 개념 0686` FTS | 123 candidate bodies, 0.271 seconds; explicitly limited |
| One numbered Markdown read | 0.164 seconds |

These are small synthetic file contents on local macOS storage, not a speed
claim for the user's other computer or a network drive. The main demonstrated
reduction is unnecessary file reads, not model latency. A blocked OS file read
still cannot be forcibly interrupted; the request times out and its late result
is discarded after the read returns. No live Windows run was performed.
