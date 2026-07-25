# Scaffold Spec

This skill bootstraps a small, opinionated LLM Wiki workspace.
It supports three profiles:

- `wiki-only`
- `llm-first-ontology` (default)
- `wiki-plus-ontology` (deprecated legacy compatibility)

## Generated Tree

```text
<target>/
  AGENTS.md
  README.md
  raw/
    inbox/
    processed/
    assets/
    notes/
  scripts/
    llm_wiki.py
  templates/
    source_page_template.md
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

## Generated Tree: llm-first-ontology

```text
<target>/
  AGENTS.md
  README.md
  intelligence/
    glossary.yaml
    contract_index.yaml
    manifests/
      actions.yaml
      datasets.yaml
      meta_surfaces.yaml
      page_policy.yaml
      registries.yaml
      relation_types.yaml
      semantic_workflows.yaml
      source_families.yaml
      workbench.yaml
    packs/
    policies/
    registry/
    schemas/
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
  templates/
    source_page_template.md
    llm-wiki-three-layer/
      sqlite_operational.schema.sql
      duckdb_analytical.schema.sql
  warehouse/
    graph_projection/
    jsonl/
      documents.jsonl
      content_units.jsonl
      source_versions.jsonl
      compile_proposals.jsonl
      review_events.jsonl
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

## Design Intent

- `raw/` is immutable source storage.
- `wiki/` is maintained synthesis.
- `warehouse/jsonl/` is optional canonical structured truth for ontology-ready repos.
- `state/` holds rebuildable operational and analytical DB state only.
- file-layer surfaces remain the canonical truth even when later operational or analytical DB layers are introduced.
- `AGENTS.md` is the repo-local contract for future agents.
- The reusable wiki workflow in `AGENTS.md` is enclosed by `LLM_WIKI_CONTRACT_START` and `LLM_WIKI_CONTRACT_END` markers so later repo-guidance refreshes can preserve it.
- `intelligence/` is optional repo-local vocabulary plus dataset/action contracts.
- `scripts/llm_wiki.py` handles lightweight maintenance tasks.
- the default `llm-first-ontology` scaffold ships lightweight SQLite/DuckDB rebuild helpers plus schema templates.
- The scaffold should be immediately usable without third-party Python dependencies.

## Three-Layer Extension Path

When this scaffold later grows into a longer-lived LLM Wiki system, prefer the staged three-layer path:

1. file-first canonical wiki surface
2. SQLite operational index
3. DuckDB analytical warehouse

Supporting references:

- `references/three-layer-taxonomy.md`
- `references/three-layer-file-contract.md`
- `templates/llm-wiki-three-layer/`

Those materials are still guidance and template surfaces. The scaffold ships lightweight local rebuild helpers, not a heavy always-on runtime stack.

## Safety Rules

- Do not overwrite non-empty targets unless the user explicitly approves and the command uses `--force`.
- Do not add heavy infra by default.
- Do not assume embeddings or vector search are required.
- Do not treat ontology-ready scaffolding as a requirement for every repo.
- Do not replace or truncate an existing marked wiki contract when another tool refreshes repository guidance.
- Keep the generated README understandable for a human opening the repo for the first time.

## Suggested Follow-Up

After scaffolding:

1. Open the folder as an Obsidian vault.
2. Add the first source to `raw/inbox/`.
3. Ask Codex to use the repo-local `AGENTS.md`.
4. Register the source with the local CLI.
5. If the repo uses `llm-first-ontology`, run strict LLM-first compile/query or ontology-backed ingest from there.
6. If the user later wants a longer-lived architecture, consult the three-layer references before adding SQLite or DuckDB.
