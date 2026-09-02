# Scaffold Spec

This skill bootstraps one small, opinionated `wiki-only` workspace. The former
`llm-first-ontology` and `wiki-plus-ontology` profiles are archived and are not
active CLI choices.

SQLite retrieval is the only first-run option:

- `--sqlite on`: include the Markdown-derived SQLite schema, rebuild tool, and retrieval CLI.
- The generated retrieval contract keeps wiki search primary and exposes raw
  search as a separate fallback/verification lane; it never blends scores.
- `--sqlite off`: create the pure Markdown wiki without SQLite retrieval files.
- omitted in an interactive terminal: ask once, defaulting to yes.
- omitted outside a terminal: default to on without prompting.

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

With SQLite enabled, also generate:

```text
scripts/
  raw_retrieval.py
  reindex_sqlite_operational.py
  wiki_retrieval.py
templates/llm-wiki-three-layer/
  sqlite_operational.schema.sql
```

## Design Intent

- `raw/` is immutable source storage.
- `wiki/` is maintained synthesis and the complete knowledge truth surface.
- `state/wiki_index.sqlite` is optional, disposable, and rebuildable from Markdown.
- `state/raw_index.sqlite` is a separate optional lexical index for immutable
  `raw/**/*.md`; it stores chunk metadata/offsets plus one FTS copy, reopens raw
  bytes for results, and does not add vectors or canonical truth.
- Lexical SQLite search and bounded wikilink traversal are candidate discovery only:
  they report unchecked freshness and callers reopen canonical Markdown before
  treating a result as evidence. `status` is the cheap stat gate; `doctor` is
  the exact content/vector gate.
- Wiki and raw Markdown headings define chunks regardless of total file size.
  The default 8 KiB maximum applies to each section; only an oversized section
  falls back to paragraph and UTF-8-safe splitting.
- `AGENTS.md` is the repo-local contract for future agents.
- Certified source ingest is owned by `llm-wiki-loop`. The generated
  `AGENTS.md` routes full coverage, batch work, and `ready` completion to that
  standalone skill; its runtime remains inside the skill rather than being
  copied into the target repository.
- The reusable wiki workflow is enclosed by `LLM_WIKI_CONTRACT_START` and `LLM_WIKI_CONTRACT_END` markers.
- The scaffold contains no ontology JSONL, `intelligence/` contract layer, DuckDB, helper-model configuration, or proposal/review registry.
- The scaffold is usable without third-party Python dependencies.

## Safety Rules

- Do not overwrite non-empty targets unless the user explicitly approves and uses `--force`.
- Do not add ontology or analytical infrastructure by default.
- Do not assume embeddings or vector search are required.
- Do not treat SQLite as canonical semantic truth.
- Keep the generated README understandable for a human opening the repo for the first time.

## Suggested Follow-Up

1. Open the folder as an Obsidian vault.
2. Add the first source to `raw/inbox/`.
3. Ask Codex to use the repo-local `AGENTS.md`.
4. Register the source, then invoke `llm-wiki-loop` for certified synthesis.
5. If SQLite is enabled, run `python scripts/wiki_retrieval.py --repo-root . rebuild`.
6. Add any future ontology system only through a separate, explicit product decision.
