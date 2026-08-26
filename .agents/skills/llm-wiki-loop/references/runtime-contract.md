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

It does not write `scripts/wiki_workflow.py`, `scripts/wiki_batch.py`,
`scripts/pipeline_check.py`, or a copy of its own template assets.

## Version boundary

Every source run records `runtime`, `runtime_version`, and a contract digest.
A different contract digest makes prior procedure evidence stale rather than
silently interpreting it under a changed runtime.

Existing repositories may retain older repo-local gate scripts. The loop reports
them as legacy runtime files but never executes, overwrites, or deletes them.
