---
name: llm-wiki-bootstrap
description: Use this skill when the user wants to scaffold a new Obsidian-first LLM Wiki workspace, bootstrap Andrej Karpathy-style LLM Wiki structure, create raw/wiki/AGENTS.md layout in a fresh project, or standardize a markdown-first knowledge vault with scripts, templates, and meta pages. Trigger on requests to set up an LLM wiki, knowledge vault, research wiki, persistent markdown memory repo, or repo-local AGENTS-driven wiki workflow, and not for existing wiki analysis-only work or ingest one source into an existing wiki.
---

# LLM Wiki Bootstrap

## Overview

Create a fresh markdown-first LLM Wiki workspace that is ready for Codex-style maintenance. The skill has one active product shape: `wiki-only`. It scaffolds the folder structure, `AGENTS.md`, starter `README.md`, local CLI, template files, and meta pages so the next agent can operate the vault consistently.

Certified source ingest is intentionally owned by `llm-wiki-loop`, not this
scaffold. The generated `AGENTS.md` routes full-coverage or `ready` ingest to
that standalone skill; bootstrap does not install gate executables in the vault.

SQLite retrieval is an independent optional choice. It is disposable, derived from Markdown, and never changes the wiki-only truth boundary. The archived `llm-first-ontology` and `wiki-plus-ontology` profiles are not active bootstrap choices.

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
3. Ask whether to enable the optional local SQLite retrieval index. Recommend yes for large or growing vaults; choose no for the smallest pure-Markdown scaffold.
4. Run `scripts/bootstrap_llm_wiki.py <target-dir> --sqlite on|off` from this skill. Interactive runs ask when the flag is omitted; non-interactive runs default to `on`.
5. Inspect the generated tree and verify that these exist:
   - `AGENTS.md`
   - `README.md`
   - `.gitignore`
   - `raw/`
   - `wiki/`
   - `scripts/llm_wiki.py`
   - `templates/source_page_template.md`
   - `wiki/_meta/index.md`, `dashboard.md`, `log.md`
   - when SQLite is enabled, also verify:
     - `scripts/reindex_sqlite_operational.py`
     - `scripts/wiki_retrieval.py`
     - `scripts/raw_retrieval.py`
     - `templates/llm-wiki-three-layer/sqlite_operational.schema.sql`
6. Spot-check the generated repo contract:
   - `AGENTS.md` includes a startup ritual for future agents
   - `AGENTS.md` keeps `wiki/_meta/index.md` and `wiki/_meta/log.md` central
   - `AGENTS.md` requires relevant wikilink traversal, bounded recursive fan-out, and an explicit reading path
   - `AGENTS.md` includes page-role, source-ingest, duplicate-avoidance, and page-promotion thresholds
   - the reusable wiki contract is enclosed by `<!-- LLM_WIKI_CONTRACT_START -->` and `<!-- LLM_WIKI_CONTRACT_END -->`
   - the scaffold contains no `warehouse/jsonl/` or `intelligence/` ontology layer
7. Tell the user what was created and what the next maintenance prompt should look like.

## Default Command

```bash
python3 ~/.codex/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py /absolute/path/to/new-project
```

To make automation explicit:

```bash
python3 ~/.codex/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py /absolute/path/to/new-project --sqlite on
python3 ~/.codex/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py /absolute/path/to/new-project --sqlite off
```

Add `--force` only when the user explicitly wants overwrites.

## What The Script Generates

- Obsidian-first folder layout
- repo-local `AGENTS.md`
- starter `README.md`
- minimal CLI for `ingest`, `reindex`, `lint`, `status`, `log`
- source-page template
- starter dashboard, index, and log pages
- optional Markdown-derived SQLite/FTS5 retrieval helpers
- an independent incremental lexical index for `raw/**/*.md` when SQLite is enabled; no raw vectors or blended ranking
- optional deterministic raw heading-tree navigation for planning; canonical Markdown remains the source read for synthesis
- explicit routing to `llm-wiki-loop` for certified full-coverage ingest, receipts, batch certification, and completion posture

## Three-Layer Follow-On Guidance

If the user wants to evolve the generated wiki into a longer-lived operating model, the next preferred path is:

1. keep Markdown canonical
2. enable or rebuild SQLite when retrieval scale requires it
3. add other analytical or ontology systems only as separate, evidence-backed products

Use these repo-local materials for that transition:

- `references/three-layer-taxonomy.md`
- `references/three-layer-file-contract.md`
- `templates/llm-wiki-three-layer/`

The active bootstrap does not generate canonical ontology JSONL, DuckDB, helper-model configuration, or proposal/review registries.

## Generated Contract Expectations

- The scaffold should teach future agents to read `AGENTS.md`, `wiki/_meta/index.md`, and recent `wiki/_meta/log.md` before substantial work.
- The scaffold should teach future agents to treat relevant wikilinks as evidence paths, follow them recursively for 2–3 hops when needed, and report the pages read in traversal order.
- The scaffold should teach page-threshold discipline so passing mentions do not immediately become standalone pages.
- The scaffold should teach source registration before semantic promotion, overlapping-scope checks before page creation, and `wiki/_meta/index.md` plus `wiki/_meta/log.md` refresh after meaningful work.
- The generated wiki workflow must stay inside the `LLM_WIKI_CONTRACT` managed markers so later repository-guidance tools can preserve it.
- The generated contract must block source completion on missing/stale procedure stages and block batch completion on pending sources, unobserved writes, writer conflicts, or stale corpus/question fingerprints.
- The generated contract must route certified raw ingest to `llm-wiki-loop`; if it is unavailable, the agent must not claim full coverage or `ready` completion.
- The scaffold must describe Markdown as canonical and SQLite as optional derived state when enabled.
- With SQLite enabled, the scaffold must teach wiki-first lookup, explicit raw
  fallback only after an empty wiki lexical result, and direct raw search for
  thin-page verification or ingest coverage without blended ranking.
- With SQLite enabled, the scaffold must describe raw `tree`, `ancestors`, and
  `subtree` as optional navigation, require canonical Markdown reopening before
  synthesis, and explain explicit `rebuild --exact` or direct-reading fallback for stale
  structure state. Tree leaves are not coverage units or a second ledger.
- If a later wiki-local conventions page is ever added, it must remain subordinate to `AGENTS.md`.

## Customization Guidance

- If the user already has a preferred wiki policy, edit the generated `AGENTS.md` after bootstrap instead of bloating the bootstrap script with many flags.
- If another tool later updates an existing `AGENTS.md`, it must preserve the complete `LLM_WIKI_CONTRACT` managed block. Update that block only when the task explicitly changes wiki workflow.
- Keep the scaffold opinionated and small. This skill is for the first 80 percent, not every possible customization switch.
- Keep SQLite as the only first-run feature choice; do not reintroduce ontology profiles into the normal bootstrap.
- For details on generated files and safety boundaries, read `references/scaffold-spec.md`.

## Validation

After changes to this skill:

1. Run quick validation.
2. Run the bootstrap script in a temporary directory with `--sqlite on`.
3. Rebuild and query the generated SQLite index, including raw tree, ancestor,
   and subtree navigation against canonical Markdown.
4. Run the bootstrap script in a second temporary directory with `--sqlite off`.
5. Verify SQLite scripts/schema/database are absent in the off scaffold and ontology folders are absent in both.
6. Verify `--profile` and archived ontology profile names are not active CLI choices.
7. Spot-check `AGENTS.md`, `README.md`, and `scripts/llm_wiki.py`.
8. Verify a generated vault contains no loop gate executables and its `AGENTS.md` routes certified ingest to `llm-wiki-loop`.
9. Run the standalone loop runtime against that vault through its `preflight`, source procedure, and batch tests.
10. Confirm the generated wording does not imply markdown pages, SQLite, or DuckDB are canonical semantic truth.

Prefer deterministic script validation over vague chat-only claims.
