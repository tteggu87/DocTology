---
title: DocTology maintenance log
type: meta
status: active
updated: 2026-09-02
---

# Maintenance log

- 2026-09-02: Upgraded the disposable generated wiki index to
  `wiki-heading-index-v9`. Fenced-code-aware headings now define wiki and raw
  chunks regardless of total file size, with 8 KiB enforced per section and
  fallback splitting limited to oversized sections. Wiki rebuilds persist the
  existing deterministic heading tree and attach each body-search chunk to one
  `node_id`; Markdown remains canonical and no new navigation or workflow layer
  was added.
- 2026-09-01: Hardened batch discovery so malformed source metadata or
  timestamps invalidate one manifest without interrupting the remaining list.
- 2026-09-01: Added lightweight read-only batch discovery. `batch list` supports
  bounded and active-only listings, summarizes source progress, surfaces invalid
  manifests, and marks freshness unchecked so agents run exact status before
  acting instead of repeating corpus hashes across every recorded batch.
- 2026-09-01: Improved batch workflow discovery without adding orchestration.
  Public help now shows the complete multi-source sequence and explains each
  subcommand; read-only batch status returns a deterministic advisory
  `next_action` for normal progress, handoff, interruption, stale state, and
  completion.
- 2026-09-01: Closed the multi-source direct-certification bypass. More than
  one non-deferred source now requires a current seal event covering the exact
  linked run set, while single-source direct certification remains compatible;
  a completed two-source no-seal regression guards the boundary.
- 2026-09-01: Added a multi-source batch snapshot seal to eliminate cascading
  source-run staleness. Linked runs now stop at the pre-mutation boundary while
  drafts remain under `state/`; one writer applies the merged wiki update, then
  a state-only review binds every source run to the unchanged batch corpus
  fingerprint, shares one retrieval refresh, and certifies immediately. Seal
  fails closed on post-apply mutation or incomplete source/question evidence;
  prepared run payloads make interrupted state commits resumable and stale
  attempts restore the original run records.
- 2026-09-01: Added `raw_retrieval.py rebuild --exact` so checksum-stale raw
  Markdown structure can recover even when content changes preserve file size
  and mtime. Ordinary rebuild remains stat-incremental.
- 2026-09-01: Added deterministic raw Markdown heading-tree navigation to the
  disposable SQLite index and documented its boundary across bootstrap and loop
  skills. Generated vaults expose `tree`, `ancestors`, and `subtree` only as
  checksum-checked planning aids; canonical Markdown reopening and the existing
  coverage receipt remain authoritative, with direct reading as the off,
  unavailable, or stale fallback.
- 2026-08-27: Moved the LLM Wiki procedure, batch, and structural gate runtime
  into `llm-wiki-loop`. Fresh bootstrap vaults retain the base wiki and optional
  SQLite only; certified ingest runs the skill-local runtime through
  `--repo-root` and writes only bounded state, receipts, and wiki changes. The
  invocation contract now anchors `wiki_loop.py` to the loaded skill directory,
  preventing project or global installs from resolving it inside the target
  repository by mistake. Exact `--repo-root` validation and nested `--root`
  rejection also prevent a child runtime from redirecting work to another
  repository after preflight. The public entrypoint now forwards lane and
  nested-command help to the skill-local parsers, so agents can discover CLI
  arguments without reading runtime code or requiring a valid target. Help
  retains the public `wiki_loop.py <lane>` name and hides the internal root
  transport option.
- 2026-08-26: Restored the original cropped DocTology logo and rewrote the root
  README around the human-facing Obsidian LLM Wiki, agent-facing Repo Docs,
  deterministic gates, optional SQLite, and copyable skill-first workflows.
  The removed workbench remains archived in Git history.
- 2026-08-26: Added explicit wiki-first raw fallback. Default wiki search is
  unchanged; `--raw-fallback` queries the separate raw lane only after a wiki
  lexical miss and remains non-fatal when raw derived state is unavailable.
- 2026-08-26: Added an independent raw Markdown lexical index to generated
  SQLite-enabled vaults. Incremental rebuilds update added/changed/removed files;
  search reopens canonical byte ranges, while stat status and exact doctor stay
  separate. Raw vectors and blended ranking remain intentionally absent.
- 2026-08-26: Made coverage-preserving ingest the default generated contract.
  Short ingest requests now compile to `full` heading/bounded-chunk accounting;
  `summary` requires explicit intent. Full final review must reference one
  applied source-hash receipt with balanced counts and zero deferred units.
- 2026-08-26: Made generated `wiki_workflow.py` process locks portable. Unix
  keeps `fcntl.flock`; Windows now uses the standard-library `msvcrt.locking`
  backend, locks byte zero directly without a first-use write race, and closes
  the acquired descriptor if claim persistence fails. Workflow startup and
  refresh serialization require no extra package.
- 2026-08-26: Applied the proven SQLite lifecycle split to the generated LLM
  Wiki implementation without importing Repo Docs-specific wrappers or trigram
  policy. Lexical/link discovery now opens one structural connection and marks
  candidates `freshness: unchecked`; `status` stays stat-based and `doctor`
  stays exact. Rebuilds stream page bodies and prior vector BLOBs, correct peer
  heading paths, preserve compatible ONNX vectors in bounded batches, and check
  an exact streamed fingerprint immediately before publication.
- 2026-08-26: Absorbed DuckCrab's derived Repo Docs SQLite fast-path into the
  canonical skill. Kept stat status, exact doctor, unchecked search/traversal,
  one-connection batch search, native shared-SQL adapters, and optional trigram
  discovery. Corrected long-document result starvation, raw FTS operator input,
  native failure exits, and rebuild publication-time drift detection; added
  `--no-trigram` as the only large-corpus storage switch. Independent review then
  corrected inclusive line ranges, normalized native error exits, removed
  quadratic line scans, and changed rebuild to document-streamed insertion plus
  a streamed final fingerprint. Focused 23/23 and full 135/135 tests passed;
  Windows PowerShell runtime dogfood remains unverified.
- 2026-08-25: Corrected generated wiki lint orphan detection. `_meta` navigation and self-links no longer count as inbound semantic links; `--strict-orphans` optionally turns orphan findings into a failing exit status.
- 2026-08-25: Reduced DocTology to three public skills. Moved the prior local workspace to a checksum-verified sibling legacy vault; removed active ontology, workbench, duplicated runtimes, and tracked archive surfaces; added one distribution manager and focused verification. Independent review also aligned the bootstrap command with `~/.codex/skills`, made clean-checkout validation warning-free, and hardened replacement of file and symlink destinations.
