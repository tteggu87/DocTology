---
title: Repo Docs SQLite absorption verification
type: evidence
evidence_id: EVIDENCE-REPO-DOCS-SQLITE-2026-08-26
date: 2026-08-26
subject: DuckCrab-derived Repo Docs retrieval hardening
target_fingerprint: 3097ecfa6f990daf72bbb797a2c2dc9963f4c9a30ff83738be8aa22c130f0fbe
related_decisions: []
related_plans: []
---

# Repo Docs SQLite absorption verification

## Claim And Scope

The self-contained Repo Docs skill now separates cheap stat freshness, explicit
content-exact doctor verification, and unchecked candidate discovery. It also
adds optional native SQLite readers without adding a daemon, vector lane, rank
fusion, or canonical database. This evidence verifies behavior and regression
boundaries; it does not claim cross-platform or multi-gigabyte latency.

## Commands And Results

| Command | Result | Scope |
| --- | --- | --- |
| `python3 -m unittest tests.test_repo_docs_retrieval` | 23/23 pass | focused retrieval, 2MB chunking, native SQL contract, compact mode, and failure behavior |
| `python3 -m unittest discover -s tests` | 135/135 pass | full DocTology regression suite |
| `ruff check ...repo_docs_retrieval.py tests/test_repo_docs_retrieval.py` | pass | changed Python quality |
| `bash -n .../repo_docs_query.sh` | pass | POSIX wrapper syntax |
| `git diff --check` | pass | patch whitespace |

## Corrected Adoption Boundaries

- Exact SQL window ranking returns one best chunk per document. A synthetic
  221-chunk case proves that a long document no longer hides a second matching
  document.
- Native `--terms` quotes every whitespace-delimited token. `OR`, `NOT`, and
  similar input are searched as terms rather than accepted as raw FTS operators.
- Native traversal returns exit code 2 for a missing or ambiguous start, matching
  the Python failure contract.
- Rebuild compares both content and stat fingerprints immediately before atomic
  replacement, preserving the previous index when Markdown changes mid-build.
  It inserts one document and its chunks at a time and streams the final exact
  fingerprint instead of retaining duplicate full-corpus snapshots.
- `--no-trigram` leaves token FTS queryable while avoiding trigram postings for a
  storage-sensitive corpus. Missing trigram-tokenizer support selects that same
  compact fallback instead of failing the rebuild.

## Limitations

- PowerShell execution was not tested because `pwsh` is unavailable on this Mac;
  its adapter shares the verified SQL contract but still needs Windows-host dogfood.
- The default trigram index trades derived disk space for substring discovery.
  Re-measure before assuming a suitable size or latency at multi-gigabyte scale.
- `status` can miss same-size content with restored mtime by design. `doctor` is
  the exact source-content path, and all search output remains non-canonical.
- Contentless trigram verification checks rowid coverage plus SQLite structural
  integrity; it does not claim semantic reconstruction of every trigram posting.
- The full suite passes but emits pre-existing SQLite `ResourceWarning` messages
  from other wiki retrieval tests; this patch does not broaden scope to those tests.

## Target Binding

The fingerprint is SHA-256 of the bundled
[`repo_docs_retrieval.py`](../../.agents/skills/repo-docs-intelligence-bootstrap/scripts/repo_docs_retrieval.py).
Native behavior is additionally fixed by sibling wrapper and SQL tests.
