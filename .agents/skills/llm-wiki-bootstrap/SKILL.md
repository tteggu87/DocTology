---
name: llm-wiki-bootstrap
description: Use this skill when the user wants to scaffold a new Obsidian-first LLM Wiki workspace, bootstrap Andrej Karpathy-style LLM Wiki structure, create raw/wiki/AGENTS.md layout in a fresh project, or standardize a markdown-first knowledge vault with scripts, templates, and meta pages. Trigger on requests to set up an LLM wiki, knowledge vault, research wiki, persistent markdown memory repo, or repo-local AGENTS-driven wiki workflow, and not for existing wiki analysis-only work or ingest one source into an existing wiki.
---

# LLM Wiki Bootstrap

## Overview

Create a fresh markdown-first LLM Wiki workspace that is ready for Codex-style maintenance. The skill scaffolds the folder structure, `AGENTS.md`, starter `README.md`, local CLI, template files, and meta pages so the next agent can operate the vault consistently. It now supports both a plain wiki scaffold and an ontology-ready scaffold.

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
   - `wiki-only` for a plain Obsidian-first wiki
   - `wiki-plus-ontology` when the repo should also start with `warehouse/jsonl/` and minimal intelligence manifests
4. Run `scripts/bootstrap_llm_wiki.py <target-dir> --profile <profile>` from this skill.
5. Inspect the generated tree and verify that these exist:
   - `AGENTS.md`
   - `README.md`
   - `raw/`
   - `wiki/`
   - `scripts/llm_wiki.py`
   - `templates/source_page_template.md`
   - `wiki/_meta/index.md`, `dashboard.md`, `log.md`
   - for `wiki-plus-ontology`, also verify:
     - `intelligence/glossary.yaml`
     - `intelligence/manifests/datasets.yaml`
     - `intelligence/manifests/actions.yaml`
     - `warehouse/jsonl/`
6. Spot-check the generated repo contract:
   - `AGENTS.md` includes a startup ritual for future agents
   - `AGENTS.md` keeps `wiki/_meta/index.md` and `wiki/_meta/log.md` central
   - `AGENTS.md` requires relevant wikilink traversal, bounded recursive fan-out, and an explicit reading path
   - ontology-ready scaffolds describe `warehouse/jsonl/` as canonical truth
7. Tell the user what was created and what the next maintenance prompt should look like.

## Default Command

```bash
python3 .agents/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py /absolute/path/to/new-project --profile wiki-only
```

For an ontology-ready scaffold:

```bash
python3 .agents/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py /absolute/path/to/new-project --profile wiki-plus-ontology
```

If the skill is installed outside this repository, run the same script from the
installed skill directory. Keep the generated repo-local `AGENTS.md` as the
primary operating contract.

Add `--force` only when the user explicitly wants overwrites.

## What The Script Generates

- Obsidian-first folder layout
- repo-local `AGENTS.md`
- starter `README.md`
- minimal CLI for `ingest`, `reindex`, `lint`, `status`, `log`
- source-page template
- starter dashboard, index, and log pages
- optional ontology-ready `warehouse/jsonl/` and `intelligence/` starter files

## Generated Contract Expectations

- The scaffold should teach future agents to read `AGENTS.md`, `wiki/_meta/index.md`, and recent `wiki/_meta/log.md` before substantial work.
- The scaffold should teach future agents to treat relevant wikilinks as evidence paths, follow them recursively for 2–3 hops when needed, and report the pages read in traversal order.
- The scaffold should teach page-threshold discipline so passing mentions do not immediately become standalone pages.
- If the scaffold is ontology-ready, it should describe `warehouse/jsonl/` as canonical structured truth and `wiki/` as human-facing synthesis.
- If a later wiki-local conventions page is ever added, it must remain subordinate to `AGENTS.md`.

## Customization Guidance

- If the user already has a preferred wiki policy, edit the generated `AGENTS.md` after bootstrap instead of bloating the bootstrap script with many flags.
- Keep the scaffold opinionated and small. This skill is for the first 80 percent, not every possible customization switch.
- Prefer the profile flag over adding many one-off scaffold flags.
- For details on generated files and safety boundaries, read `references/scaffold-spec.md`.

## Validation

After changes to this skill:

1. Run quick validation.
2. Run the bootstrap script in a temporary directory for `wiki-only`.
3. Run the bootstrap script in a second temporary directory for `wiki-plus-ontology`.
4. Verify the expected files exist for both profiles.
5. Spot-check `AGENTS.md`, `README.md`, and `scripts/llm_wiki.py`.
6. Confirm the generated wording does not imply markdown pages are canonical truth in ontology-ready repos.

Prefer deterministic script validation over vague chat-only claims.
