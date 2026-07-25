---
name: llm-wiki-bootstrap
description: Use this skill when the user wants to scaffold a new Obsidian-first LLM Wiki workspace, bootstrap Andrej Karpathy-style LLM Wiki structure, create raw/wiki/AGENTS.md layout in a fresh project, or standardize a markdown-first knowledge vault with scripts, templates, and meta pages. Trigger on requests to set up an LLM wiki, knowledge vault, research wiki, persistent markdown memory repo, or repo-local AGENTS-driven wiki workflow, and not for existing wiki analysis-only work or ingest one source into an existing wiki.
---

# LLM Wiki Bootstrap

## Overview

Create a fresh markdown-first LLM Wiki workspace that is ready for Codex-style maintenance. The skill scaffolds the folder structure, `AGENTS.md`, starter `README.md`, local CLI, template files, meta pages, strict LLM-first contracts, and derived-state helpers so the next agent can operate the vault consistently.

The default profile is `llm-first-ontology`: a strict no-fallback LLM-first ontology scaffold with contract-only YAML, proposal lifecycle policy, proposal/review registries, ambient chat-agent semantic handoff, optional helper-LLM semantic workflows, and lightweight SQLite/DuckDB/drift helpers as rebuildable non-canonical state.

This is the recommended **start here** skill for DocTology-style wiki-first repos.

The generated repo-local `AGENTS.md` is the primary contract for future agents.
Do not introduce a competing top-level wiki schema file as a peer to `AGENTS.md`.

## When To Use

- The user wants a new project that behaves like an Obsidian-first LLM Wiki.
- The user wants `raw/`, `wiki/`, and repo-local `AGENTS.md` conventions set up quickly.
- The user wants a reusable bootstrap for future wiki-style projects instead of copying files by hand.
- The user wants a project-local operating contract that future agents can follow in new conversations.

Do not use this skill when the user only wants to ingest one source into an existing wiki. In that case, work inside the existing repo and follow its local `AGENTS.md`.

## Workflow

1. Confirm the target directory and whether it is new or already contains files.
2. If the directory is non-empty, avoid destructive overwrite unless the user explicitly wants replacement.
3. Choose the profile:
   - `llm-first-ontology` as the default for strict no-fallback LLM Wiki repos with contract-only YAML, proposal lifecycle, source/citation substrate, ambient chat-agent handoff, optional helper-LLM semantic workflows, and three-layer helper scripts
   - `wiki-only` only when the user explicitly wants a plain Obsidian-first wiki
   - `wiki-plus-ontology` only for legacy ontology-ready repos; it emits a deprecation warning
4. Run `scripts/bootstrap_llm_wiki.py <target-dir> --profile <profile>` from this skill.
5. Inspect the generated tree and verify that these exist:
   - `AGENTS.md`
   - `README.md`
   - `.gitignore`
   - `raw/`
   - `wiki/`
   - `scripts/llm_wiki.py`
   - `templates/source_page_template.md`
   - `wiki/_meta/index.md`, `dashboard.md`, `log.md`
   - for `llm-first-ontology`, also verify:
     - `wikiconfig.example.json`
     - `wikiconfig.json` ignored by `.gitignore`
     - `intelligence/contract_index.yaml`
     - `intelligence/policies/semantic_boundary.yaml`
     - `intelligence/policies/proposal_lifecycle.yaml`
     - `intelligence/manifests/semantic_workflows.yaml`
     - `intelligence/manifests/page_policy.yaml`
     - `intelligence/manifests/meta_surfaces.yaml`
     - `intelligence/manifests/relation_types.yaml`
     - `intelligence/manifests/registries.yaml`
     - `intelligence/packs/*/pack.yaml`
     - `scripts/llm_compile_source.py`
     - `scripts/llm_query.py`
     - `scripts/query_analysis.py`
     - `scripts/wiki_graph_navigation.py`
     - `scripts/validate_intelligence.py`
     - `scripts/validate_workbench_manifest.py`
     - `scripts/validate_profiles.py`
     - `scripts/validate_registries.py`
     - `scripts/validate_repo_docs_intelligence.py`
     - `scripts/proposal_review.py`
     - `state/`
     - `scripts/reindex_sqlite_operational.py`
     - `scripts/refresh_duckdb_analytics.py`
     - `scripts/verify_three_layer_drift.py`
     - `templates/llm-wiki-three-layer/sqlite_operational.schema.sql`
     - `templates/llm-wiki-three-layer/duckdb_analytical.schema.sql`
     - `warehouse/jsonl/`
6. Spot-check the generated repo contract:
   - `AGENTS.md` includes a startup ritual for future agents
   - `AGENTS.md` keeps `wiki/_meta/index.md` and `wiki/_meta/log.md` central
   - `AGENTS.md` requires relevant wikilink traversal, bounded recursive fan-out, and an explicit reading path
   - `AGENTS.md` includes page-role, source-ingest, duplicate-avoidance, and page-promotion thresholds
   - the reusable wiki contract is enclosed by `<!-- LLM_WIKI_CONTRACT_START -->` and `<!-- LLM_WIKI_CONTRACT_END -->`
   - ontology-ready scaffolds describe `warehouse/jsonl/` as canonical truth
7. Tell the user what was created and what the next maintenance prompt should look like.

## Default Command

```bash
python3 ~/.agents/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py /absolute/path/to/new-project
```

For an explicit strict ontology-ready scaffold:

```bash
python3 ~/.agents/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py /absolute/path/to/new-project --profile llm-first-ontology
```

`llm-first-ontology` is also the default when `--profile` is omitted. `wiki-plus-ontology` remains available only for deprecated legacy compatibility.

For the legacy ontology-ready scaffold:

```bash
python3 ~/.agents/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py /absolute/path/to/new-project --profile wiki-plus-ontology
```

For an explicit plain wiki scaffold:

```bash
python3 ~/.agents/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py /absolute/path/to/new-project --profile wiki-only
```

Add `--force` only when the user explicitly wants overwrites.

## What The Script Generates

- Obsidian-first folder layout
- repo-local `AGENTS.md`
- starter `README.md`
- minimal CLI for `ingest`, `reindex`, `lint`, `status`, `log`
- source-page template
- starter dashboard, index, and log pages
- default strict ontology-ready `warehouse/jsonl/`, `intelligence/`, LLM compile/query scripts, proposal review CLI, validators, `state/`, and lightweight SQLite/DuckDB helper files
- durable query-answer persistence helper under `scripts/query_analysis.py`
- `wikiconfig.example.json` plus a local ignored `wikiconfig.json` placeholder with `llmWiki.enabled=false`; disabled helper mode emits agent handoff bundles/prompts rather than semantic success

## Three-Layer Follow-On Guidance

If the user wants to evolve the generated wiki into a longer-lived operating model, the next preferred path is:

1. keep files canonical
2. add SQLite later as an operational index
3. add DuckDB later as an analytical warehouse

Use these repo-local materials for that transition:

- `references/three-layer-taxonomy.md`
- `references/three-layer-file-contract.md`
- `templates/llm-wiki-three-layer/`

The default `llm-first-ontology` bootstrap ships lightweight local SQLite/DuckDB rebuild helpers and schema templates for ontology-ready repos, but it still avoids heavy always-on runtime infrastructure.

## Generated Contract Expectations

- The scaffold should teach future agents to read `AGENTS.md`, `wiki/_meta/index.md`, and recent `wiki/_meta/log.md` before substantial work.
- The scaffold should teach future agents to treat relevant wikilinks as evidence paths, follow them recursively for 2–3 hops when needed, and report the pages read in traversal order.
- The scaffold should teach page-threshold discipline so passing mentions do not immediately become standalone pages.
- The scaffold should teach source registration before semantic promotion, overlapping-scope checks before page creation, and `wiki/_meta/index.md` plus `wiki/_meta/log.md` refresh after meaningful work.
- The generated wiki workflow must stay inside the `LLM_WIKI_CONTRACT` managed markers so later repository-guidance tools can preserve it.
- If the scaffold is ontology-ready, it should describe `warehouse/jsonl/` as canonical structured truth and `wiki/` as human-facing synthesis.
- If a later wiki-local conventions page is ever added, it must remain subordinate to `AGENTS.md`.

## Customization Guidance

- If the user already has a preferred wiki policy, edit the generated `AGENTS.md` after bootstrap instead of bloating the bootstrap script with many flags.
- If another tool later updates an existing `AGENTS.md`, it must preserve the complete `LLM_WIKI_CONTRACT` managed block. Update that block only when the task explicitly changes wiki workflow.
- Keep the scaffold opinionated and small. This skill is for the first 80 percent, not every possible customization switch.
- Prefer the profile flag over adding many one-off scaffold flags.
- For details on generated files and safety boundaries, read `references/scaffold-spec.md`.

## Validation

After changes to this skill:

1. Run quick validation.
2. Run the bootstrap script in a temporary directory for default `llm-first-ontology`.
3. Run the generated validators and three-layer helper smoke in that temporary directory.
4. Run the bootstrap script in a second temporary directory for `wiki-only`.
5. Run the bootstrap script in a third temporary directory for legacy `wiki-plus-ontology`.
6. Verify the expected files exist for all profiles.
7. Spot-check `AGENTS.md`, `README.md`, and `scripts/llm_wiki.py`.
8. Confirm the generated wording does not imply markdown pages, SQLite, or DuckDB are canonical semantic truth.

Prefer deterministic script validation over vague chat-only claims.
