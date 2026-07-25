# Three-Layer File Contract

This reference defines the preferred file-layer layout for a wiki-first, file-canonical LLM Wiki that supports an ontology-ready bootstrap plus rebuildable SQLite and DuckDB layers.

## Directory layout

```text
<repo>/
  AGENTS.md
  README.md
  intelligence/
    glossary.yaml
    manifests/
      actions.yaml
      datasets.yaml
  raw/
    inbox/
    processed/
    assets/
    notes/
  scripts/
    llm_wiki.py
    reindex_sqlite_operational.py
    refresh_duckdb_analytics.py
    verify_three_layer_drift.py
  state/
    wiki_index.sqlite
    wiki_analytics.duckdb
  templates/
    source_page_template.md
    llm-wiki-three-layer/
      sqlite_operational.schema.sql
      duckdb_analytical.schema.sql
  warehouse/
    jsonl/
      messages.jsonl
      documents.jsonl
      entities.jsonl
      claims.jsonl
      claim_evidence.jsonl
      segments.jsonl
      derived_edges.jsonl
  wiki/
    _meta/
      dashboard.md
      index.md
      log.md
    analyses/
    concepts/
    entities/
    people/
    projects/
    sources/
    timelines/
```

## Surface semantics

- `raw/` = immutable evidence-bearing source artifacts
- `wiki/` = maintained human-facing synthesis
- `intelligence/` = repo-local vocabulary, dataset roles, and action contracts
- `warehouse/jsonl/` = canonical structured machine-truth
- `state/` = rebuildable operational and local wiki analytics databases only
- `templates/llm-wiki-three-layer/` = lightweight schema support for local rebuild helpers

## Ownership summary

- files own canonical truth
- SQLite owns operational index state only
- Bootstrap DuckDB owns local wiki analytics mirror state only

## Guardrails

1. `raw/`, `wiki/`, and `warehouse/jsonl/` remain the canonical write surfaces
2. `state/` must remain rebuildable from canonical file inputs
3. raw sources should not be destructively overwritten
4. `warehouse/jsonl/` is canonical structured truth, not a disposable export layer
5. SQLite and DuckDB must never become the truth owner
