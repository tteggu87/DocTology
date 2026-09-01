# Loop runtime contract

`llm-wiki-loop` owns the executable procedure, batch, and structural-check
runtime. It runs those scripts from this skill directory with `--repo-root`
pointing at a target wiki; it never copies or updates executable runtime files
inside that target.

The runner resolves the directory containing the loaded `SKILL.md` as
`SKILL_DIR` and invokes `<SKILL_DIR>/scripts/wiki_loop.py` explicitly. It must
not resolve that entrypoint relative to the current working directory or the
target repository. Once invoked, `wiki_loop.py` resolves all sibling runtime
modules from its own file location.

For discovery, `wiki_loop.py workflow --help`, `workflow start --help`,
`batch --help`, and `check --help` forward to the corresponding skill-local
parser while retaining the public `wiki_loop.py <lane>` command name and hiding
the internal root transport option. Help never validates or mutates a target
repository.

## Target requirements

The target must contain:

- `AGENTS.md`
- `raw/`
- `wiki/`

The public loop is wiki-only. A target with `warehouse/jsonl/` is outside this
runtime's contract and must be reported as `not_ready`.

## Durable target writes

The runtime may write only normal wiki work products and bounded state:

- canonical wiki pages and `wiki/_meta/` updates chosen by the semantic owner
- `wiki/_meta/ingest_reports/` coverage receipts
- `wiki/_meta/representative_questions.json` when batch certification needs an
  explicit question contract
- `state/wiki_runs/` and `state/wiki_batches/`

Multi-source batch seal keeps its final-review receipt, publish lock, prepared
run payloads, recovery metadata, shared retrieval-refresh result, and
certification below `state/wiki_batches/`. It commits each source-run binding to
that run's existing `state/wiki_runs/<run-id>.json`. These writes are outside the
canonical corpus fingerprint. An interrupted commit remains explicitly
`prepared` and is idempotently resumed while the corpus fingerprint is current;
stale recovery restores the original run payloads. Seal accepts only the exact
one-writer result fingerprint and does not mutate `wiki/`. A `refreshing`
journal entry is persisted before the sole retrieval refresh; after an
interruption, seal reads retrieval status instead of executing a second refresh.
Certification rejects any batch with more than one non-deferred source unless a
current seal event covers the exact linked run set and every source row carries
that seal fingerprint. Single-source direct certification remains compatible.
`batch status` is read-only and returns one deterministic `next_action` from the
manifest, seal-attempt, certification, and freshness state. The value is an
operator hint, not an automatic transition or replacement for validation.
`batch list` is also read-only but deliberately does not compute corpus
fingerprints. It scans manifest metadata, reports `freshness:
unchecked`, limits returned rows, and routes every valid result to exact `batch
status` before action. It never follows symlinked state, batch-root, batch, or
manifest paths.

It does not write `scripts/wiki_workflow.py`, `scripts/wiki_batch.py`,
`scripts/pipeline_check.py`, or a copy of its own template assets.

## Version boundary

Every source run records `runtime`, `runtime_version`, and a contract digest.
A different contract digest makes prior procedure evidence stale rather than
silently interpreting it under a changed runtime.

Runtime version 2 adds batch snapshot seal. A sealed source run retains its
source-specific completion fingerprint and also records the common batch corpus
fingerprint; neither substitutes for the final certification freshness check.

Existing repositories may retain older repo-local gate scripts. The loop reports
them as legacy runtime files but never executes, overwrites, or deletes them.
