#!/usr/bin/env python3
"""Scaffold an Obsidian-first LLM Wiki workspace."""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path


def today() -> str:
    return dt.date.today().isoformat()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def source_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def read_source_repo_file(relative_path: str) -> str:
    path = source_repo_root() / relative_path
    if not path.exists():
        raise FileNotFoundError(
            f"Bootstrap expected DocTology reference file at {relative_path}. "
            "Run this repo-local bootstrap from a complete DocTology checkout."
        )
    return path.read_text(encoding="utf-8")


def ensure_safe_target(target: Path, force: bool) -> None:
    if not target.exists():
        target.mkdir(parents=True, exist_ok=True)
        return

    has_entries = any(target.iterdir())
    if has_entries and not force:
        raise SystemExit(
            f"Refusing to scaffold into non-empty directory: {target}\n"
            "Use --force only if you intentionally want to overwrite scaffold files."
        )


PROFILES = ["wiki-only", "wiki-plus-ontology"]


def wiki_only_agents_md() -> str:
    return """# AGENTS.md

This repository is an Obsidian-first LLM Wiki.

The human curates sources and asks questions.
The agent maintains the wiki.

## Mission

Maintain a persistent, high-signal markdown wiki that sits between raw sources and future reasoning.

Do not answer only in chat when the result belongs in the wiki.
Prefer to turn durable work into durable markdown pages.

## Architecture

There are three layers:

1. `raw/` contains immutable source material. Never modify source contents.
2. `wiki/` contains LLM-maintained pages. The agent may create, update, rename, merge, and cross-link these pages.
3. `AGENTS.md` defines the operating rules.

## Core Rules

1. Treat `raw/` as source of truth and `wiki/` as maintained synthesis.
2. Never edit files inside `raw/` unless the user explicitly asks.
3. Prefer many small linked pages over one giant dumping-ground page.
4. Use Obsidian wikilinks like `[[concept-name]]` whenever a stable concept, entity, person, project, or source page exists.
5. Preserve uncertainty. If a claim is weak, disputed, inferred, or contradicted, say so explicitly.
6. Cite the underlying source page from any claim-heavy wiki page.
7. When answering substantial questions, save the answer into `wiki/analyses/` unless the user asks for chat-only output.
8. Keep `wiki/_meta/index.md` and `wiki/_meta/log.md` current after meaningful work.

## Folder Semantics

- `wiki/sources/`: one page per source, including source metadata, summary, key claims, and links to affected pages
- `wiki/concepts/`: concepts, frameworks, recurring ideas, terminology
- `wiki/entities/`: organizations, products, systems, places, or domain objects
- `wiki/people/`: people and roles
- `wiki/projects/`: efforts, initiatives, cases, programs, or workstreams
- `wiki/timelines/`: chronological pages
- `wiki/analyses/`: saved answers, comparison memos, synthesis notes, decision memos
- `wiki/_meta/`: dashboard, index, log, and other operational pages

## Page Conventions

Every wiki page should start with YAML frontmatter when practical.

Recommended fields:

```yaml
---
title: Example Page
type: concept
status: active
created: 2026-04-08
updated: 2026-04-08
tags:
  - llm-wiki
sources:
  - "[[source-2026-04-08-example]]"
---
```

Guidelines:

- `title`: human-readable page title
- `type`: one of `source`, `concept`, `entity`, `person`, `project`, `timeline`, `analysis`, `meta`
- `status`: usually `active`, `draft`, `superseded`, or `open-question`; source pages may use lifecycle statuses such as `inbox`, `registered`, or `pending-synthesis`
- `sources`: wikilinks to source pages, not raw file paths
- Keep sections crisp and scannable
- Use headings instead of long uninterrupted prose

## Source Ingest Workflow

When the user asks to ingest a source:

1. Read the raw source from `raw/inbox/`, `raw/processed/`, or `raw/notes/`.
2. Locate the matching page in `wiki/sources/`. If it does not exist, create it.
3. Write or update:
   - concise summary
   - key facts
   - important claims
   - contradictions or uncertainties
   - open questions
   - links to affected wiki pages
4. Update every affected concept, entity, person, project, or timeline page.
5. Create missing pages when a concept or entity clearly deserves its own page.
6. Rebuild or refresh `wiki/_meta/index.md` if page inventory changed.
7. Append an entry to `wiki/_meta/log.md`.

If the local CLI `scripts/llm_wiki.py ingest` was used first, treat that as source registration only.

## Closed Wiki Ingest Pipeline

When the user asks to ingest a source, do not stop at source registration unless the user explicitly asks for registration only.

Default wiki-only ingest must follow this lifecycle:

1. Register the source.
2. Project source-backed synthesis into `wiki/sources/` and affected wiki pages.
3. Refresh `wiki/_meta/index.md`.
4. Append a clear entry to `wiki/_meta/log.md`.
5. Run structural validation or report why validation could not run.

This pipeline closes the lifecycle, not semantic judgment.

Do not use filename, keyword, directory, token-shape, graph, retrieval, or YAML shortcuts as hard gates for semantic routing. Inspect the source, existing wiki map, and relevant page bodies before choosing affected pages.

Semantic no-fallback rule: when source-page synthesis, affected-page selection, contradiction handling, or wiki projection requires agent or configured LLM judgment, an unavailable, failed, or invalid judgment must be reported as `failed`, `partial`, or `pending`. Do not replace it with lexical diagnostics, retrieval output, graph projection, structural validation, filename/keyword summaries, or deterministic fallback prose and call the semantic step complete. Transport fallback for the same configured LLM request is allowed; semantic fallback that changes the judgment owner is not.

## Query Workflow

When the user asks a question:

1. Read `wiki/_meta/index.md` first.
2. Identify likely relevant pages.
3. Read the smallest set of pages that can answer well.
4. Follow wikilinks. When a page you read contains `[[link-name]]` wikilinks relevant to the question, resolve and read those linked pages too. Wikilinks are not decoration; they are paths to evidence. For example, `[[concept-name]]` maps to `wiki/concepts/concept-name.md`, and `[[source-example]]` maps to `wiki/sources/source-example.md`.
5. Traverse recursively. If a linked page contains further relevant wikilinks, follow them to a reasonable depth of 2–3 hops. Stop when the question is answered or no more relevant links exist.
6. Synthesize an answer grounded in the wiki.
7. If the answer is durable, save it into `wiki/analyses/`.
8. Cross-link that analysis page from relevant pages if appropriate.
9. Append a `query` log entry for substantial work.

## Link Traversal Rules

- **Minimum depth.** For any question involving two or more concepts, follow at least 2 hops of relevant wikilinks before answering. Do not stop at the first page.
- **Fan-out.** When a page links to multiple concepts relevant to the question, read all of those linked pages, not just the first.
- **Refuse when evidence is absent.** If, after traversing up to 3 hops, no evidence supports an answer, explicitly state that the evidence is absent. Do not fabricate an answer.
- **Track the path.** Before answering, list every page read in traversal order.

## New Thread Bootstrap

When a new agent opens this repository in a fresh conversation:

1. Read `AGENTS.md` first.
2. Read `wiki/_meta/index.md` before answering wiki questions.
3. Read `wiki/_meta/log.md` if recent work or unfinished threads may matter.
4. Treat this repository as a persistent wiki workspace, not a one-shot chat scratchpad.
5. Prefer updating `wiki/` pages over leaving durable synthesis only in chat.

Default startup assumptions:

- This repo-specific `AGENTS.md` is the primary operating contract for future agents working inside this project.
- The local CLI in `scripts/llm_wiki.py` is support tooling, not the source of truth.
- If a future agent can answer from existing wiki pages, it should avoid rereading the full raw corpus unless needed for verification or coverage.

## AGENTS Vs Skills

For this repository:

- Prefer `AGENTS.md` for repo-specific workflow, page conventions, ingest/query rules, and maintenance behavior.
- Prefer a reusable skill only if the behavior should work across many repositories or outside this specific vault.
- Do not assume a custom skill will auto-activate in future conversations unless the environment explicitly exposes and triggers that skill.
- Therefore, if reliability for the next agent is the goal, encode the rule here in `AGENTS.md` and keep examples in `README.md` or `wiki/_meta/`.

## Lint Workflow

When the user asks for a health check:

Look for:

- broken wikilinks
- orphan pages
- duplicate pages with overlapping scope
- important concepts mentioned repeatedly but lacking pages
- stale summaries
- unsupported claims
- contradictions not yet surfaced

When possible, fix issues directly and record the pass in the log.

## Writing Style

- Be factual, compressed, and explicit
- Prefer synthesis over paraphrase
- Preserve provenance
- Use bullet lists when they make scanning easier
- Avoid hype language
- Distinguish fact, inference, and speculation

## Naming

- Use kebab-case filenames
- Keep names stable once linked widely
- Prefer descriptive filenames over cute ones

Examples:

- `wiki/sources/source-2026-04-08-karpathy-llm-wiki.md`
- `wiki/concepts/persistent-synthesis.md`
- `wiki/analyses/analysis-2026-04-08-rag-vs-llm-wiki.md`

## Maintenance Defaults

- If a new answer would be useful later, save it
- If a page is thin but necessary, create a stub instead of omitting it
- If a source changes the meaning of an older page, revise the older page
- If a source conflicts with earlier material, note the conflict explicitly

## Safe Boundaries

- Do not silently delete meaningful content
- If merging or renaming broad pages, preserve redirects or update all inbound links
- Do not overstate certainty
- Do not fabricate citations or source coverage

## Human Collaboration

Default assumption:

- The human wants the wiki to compound over time
- The agent should leave behind clean artifacts, not just temporary chat output

If unsure whether something belongs in the wiki, prefer asking:
`Should I save this as a wiki page?`
"""


def ontology_agents_md() -> str:
    return """# AGENTS.md

This repository is an Obsidian-first LLM Wiki with a lightweight ontology layer.

The human curates sources and asks questions.
The agent maintains the wiki and the canonical ontology artifacts.

## Mission

Maintain a persistent, high-signal markdown wiki that sits between raw sources and future reasoning.

Do not answer only in chat when the result belongs in the wiki.
Prefer to turn durable work into durable markdown pages.
When ontology-backed ingest is available, keep the canonical ontology registry aligned with the wiki.

## Architecture

There are four layers:

1. `raw/` contains immutable source material. Never modify source contents.
2. `warehouse/jsonl/` contains canonical structured ontology truth.
3. `wiki/` contains LLM-maintained human-facing synthesis pages.
4. `AGENTS.md` plus `intelligence/` define the operating rules, vocabulary, dataset boundaries, and action contracts.

## Core Rules

1. Treat `raw/` as immutable source truth, `warehouse/jsonl/` as canonical structured truth, and `wiki/` as maintained human-facing synthesis.
2. Never edit files inside `raw/` unless the user explicitly asks.
3. Prefer many small linked pages over one giant dumping-ground page.
4. Use Obsidian wikilinks like `[[concept-name]]` whenever a stable concept, entity, person, project, or source page exists.
5. Preserve uncertainty. If a claim is weak, disputed, inferred, or contradicted, say so explicitly.
6. Cite the underlying source page from any claim-heavy wiki page.
7. When answering substantial questions, save the answer into `wiki/analyses/` unless the user asks for chat-only output.
8. Keep `wiki/_meta/index.md` and `wiki/_meta/log.md` current after meaningful work.

## Truth Priority

Use this order when evidence conflicts or layers disagree:

1. `raw/` = immutable source material
2. `warehouse/jsonl/...` = canonical structured ontology truth
3. `wiki/` = maintained human-facing synthesis
4. graph projection or retrieval outputs = optional derived aids, never canonical

The wiki is the default reading surface for humans.
The ontology registries are the default machine-truth surface for provenance, contradiction handling, and source coverage checks.

## Folder Semantics

- `raw/`: immutable source storage
- `warehouse/jsonl/`: canonical ontology outputs such as `messages.jsonl`, `documents.jsonl`, `entities.jsonl`, `claims.jsonl`, `claim_evidence.jsonl`, `segments.jsonl`, and `derived_edges.jsonl`
- `wiki/sources/`: one page per source, including source metadata, summary, key claims, and links to affected pages
- `wiki/concepts/`: concepts, frameworks, recurring ideas, terminology
- `wiki/entities/`: organizations, products, systems, places, or domain objects
- `wiki/people/`: people and roles
- `wiki/projects/`: efforts, initiatives, cases, programs, or workstreams
- `wiki/timelines/`: chronological pages
- `wiki/analyses/`: saved answers, comparison memos, synthesis notes, decision memos
- `wiki/_meta/`: dashboard, index, log, and other operational pages
- `intelligence/`: glossary and manifests that stabilize repo-local vocabulary, datasets, and action boundaries

## Page Conventions

Every wiki page should start with YAML frontmatter when practical.

Recommended fields:

```yaml
---
title: Example Page
type: concept
status: active
created: 2026-04-08
updated: 2026-04-08
tags:
  - llm-wiki
sources:
  - "[[source-2026-04-08-example]]"
---
```

Guidelines:

- `title`: human-readable page title
- `type`: one of `source`, `concept`, `entity`, `person`, `project`, `timeline`, `analysis`, `meta`
- `status`: usually `active`, `draft`, `superseded`, or `open-question`; source pages may use lifecycle statuses such as `inbox`, `registered`, or `pending-synthesis`
- `sources`: wikilinks to source pages, not raw file paths
- Keep sections crisp and scannable
- Use headings instead of long uninterrupted prose

## Source Ingest Workflow

When the user asks to ingest a source:

1. Read the raw source from `raw/inbox/`, `raw/processed/`, or `raw/notes/`.
2. If ontology-backed ingest is available, update canonical ontology registries first under `warehouse/jsonl/`.
3. Locate the matching page in `wiki/sources/`. If it does not exist, create it.
4. Write or update:
   - concise summary
   - key facts
   - important claims
   - contradictions or uncertainties
   - open questions
   - links to affected wiki pages
5. Update every affected concept, entity, person, project, or timeline page.
6. Create missing pages when a concept or entity clearly deserves its own page.
7. Rebuild or refresh `wiki/_meta/index.md` if page inventory changed.
8. Append an entry to `wiki/_meta/log.md`.

If ontology-backed ingest is not yet available, wiki-only ingest may continue, but preserve source boundaries and note that canonical ontology extraction is pending.

`scripts/llm_wiki.py ingest` is source registration only. It is not full ontology-backed ingest.

`scripts/llm_full_ingest.py --apply` is the minimal configured-LLM full growth loop. It may complete the source page, create or append affected wiki pages, append proposed JSONL records, refresh index/log, and write an ingest report. It must not modify `raw/`, create accepted truth, delete content, rename pages, merge pages, or auto-commit. Review the resulting `git diff` before committing.

`scripts/pipeline_check.py` is structural validation for the closed ingest lifecycle. It checks artifact presence and parseability; it must not be treated as semantic truth validation.

## Closed Ingest Pipeline

When the user asks to ingest a source, do not stop at source registration unless the user explicitly asks for registration only.

Default source ingest must follow this lifecycle:

1. Register the source.
2. Extract or update canonical machine-truth registries under `warehouse/jsonl/` when ontology-backed ingest applies.
3. Project source-backed synthesis into `wiki/sources/` and affected wiki pages.
4. Refresh `wiki/_meta/index.md`.
5. Append a clear entry to `wiki/_meta/log.md`.
6. Run structural validation or report why validation could not run.

This pipeline closes the lifecycle, not semantic judgment.

Do not use filename, keyword, directory, token-shape, graph, retrieval, or YAML shortcuts as hard gates for semantic routing. Inspect the source, existing wiki map, relevant page bodies, and canonical evidence before choosing affected pages.

Semantic no-fallback rule: when source-page synthesis, affected-page selection, claim extraction, contradiction handling, or wiki projection requires agent or configured LLM judgment, an unavailable, failed, or invalid judgment must be reported as `failed`, `partial`, or `pending`. Do not replace it with lexical diagnostics, retrieval output, graph projection, structural validation, filename/keyword summaries, or deterministic fallback prose and call the semantic step complete. Transport fallback for the same configured LLM request is allowed; semantic fallback that changes the judgment owner is not.

Weak, passing, or uncertain signals may stay on the source page instead of becoming standalone pages. Accepted claims require explicit review metadata and supporting evidence. Graph projection, retrieval output, and workbench previews are derived aids, not canonical truth.

## Query Workflow

When the user asks a question:

1. Read `wiki/_meta/index.md` first.
2. Identify likely relevant pages.
3. Read the smallest set of pages that can answer well.
4. Follow wikilinks. When a page you read contains `[[link-name]]` wikilinks relevant to the question, resolve and read those linked pages too. Wikilinks are not decoration; they are paths to evidence. For example, `[[concept-name]]` maps to `wiki/concepts/concept-name.md`, and `[[source-example]]` maps to `wiki/sources/source-example.md`.
5. Traverse recursively. If a linked page contains further relevant wikilinks, follow them to a reasonable depth of 2–3 hops. Stop when the question is answered or no more relevant links exist.
6. Use `warehouse/jsonl/...` for provenance checks, contradiction checks, claim validation, or exact source coverage when wiki pages are too thin or uncertain.
7. Synthesize an answer grounded in the wiki, with ontology-backed verification when needed.
8. If the answer is durable, save it into `wiki/analyses/`.
9. Cross-link that analysis page from relevant pages if appropriate.
10. Append a `query` log entry for substantial work.

## Link Traversal Rules

- **Minimum depth.** For any question involving two or more concepts, follow at least 2 hops of relevant wikilinks before answering. Do not stop at the first page.
- **Fan-out.** When a page links to multiple concepts relevant to the question, read all of those linked pages, not just the first.
- **Refuse when evidence is absent.** If, after traversing up to 3 hops, no evidence supports an answer, explicitly state that the evidence is absent. Do not fabricate an answer.
- **Track the path.** Before answering, list every page read in traversal order.

## Ontology-Aware Ingest And Query Defaults

- New source material enters through `raw/inbox/`.
- Repeated source processing should prefer an ontology-backed ingest skill over ad hoc manual steps.
- Direct ontology-core operation is reserved for tuning, debugging, or operator workflows.
- Important answers should still land in `wiki/analyses/` even when the ontology layer did most of the structured work.

## New Thread Bootstrap

When a new agent opens this repository in a fresh conversation:

1. Read `AGENTS.md` first.
2. Read `wiki/_meta/index.md` before answering wiki questions.
3. Read `wiki/_meta/log.md` if recent work or unfinished threads may matter.
4. Treat this repository as a persistent wiki workspace, not a one-shot chat scratchpad.
5. Prefer updating `wiki/` pages over leaving durable synthesis only in chat.

Default startup assumptions:

- This repo-specific `AGENTS.md` is the primary operating contract for future agents working inside this project.
- The local CLI in `scripts/llm_wiki.py` is support tooling, not the source of truth.
- If a future agent can answer from existing wiki pages, it should avoid rereading the full raw corpus unless needed for verification or coverage.

## AGENTS Vs Skills

For this repository:

- Prefer `AGENTS.md` for repo-specific workflow, page conventions, ingest/query rules, and maintenance behavior.
- Prefer a reusable skill only if the behavior should work across many repositories or outside this specific vault.
- Do not assume a custom skill will auto-activate in future conversations unless the environment explicitly exposes and triggers that skill.
- Therefore, if reliability for the next agent is the goal, encode the rule here in `AGENTS.md` and keep examples in `README.md` or `wiki/_meta/`.

## Lint Workflow

When the user asks for a health check:

Look for:

- broken wikilinks
- orphan pages
- duplicate pages with overlapping scope
- important concepts mentioned repeatedly but lacking pages
- stale summaries
- unsupported claims
- contradictions not yet surfaced

When possible, fix issues directly and record the pass in the log.

## Writing Style

- Be factual, compressed, and explicit
- Prefer synthesis over paraphrase
- Preserve provenance
- Use bullet lists when they make scanning easier
- Avoid hype language
- Distinguish fact, inference, and speculation

## Naming

- Use kebab-case filenames
- Keep names stable once linked widely
- Prefer descriptive filenames over cute ones

## Maintenance Defaults

- If a new answer would be useful later, save it
- If a page is thin but necessary, create a stub instead of omitting it
- If a source changes the meaning of an older page, revise the older page
- If a source conflicts with earlier material, note the conflict explicitly

## Safe Boundaries

- Do not silently delete meaningful content
- If merging or renaming broad pages, preserve redirects or update all inbound links
- Do not overstate certainty
- Do not fabricate citations or source coverage

## Human Collaboration

Default assumption:

- The human wants the wiki to compound over time
- The agent should leave behind clean artifacts, not just temporary chat output

If unsure whether something belongs in the wiki, prefer asking:
`Should I save this as a wiki page?`
"""


def agents_md(profile: str) -> str:
    if profile == "wiki-plus-ontology":
        return ontology_agents_md()
    return wiki_only_agents_md()


def readme(target: Path, profile: str) -> str:
    root = target.resolve()
    if profile == "wiki-plus-ontology":
        return f"""# LLM Wiki for Obsidian

An Obsidian-first, agent-maintained wiki with an optional lightweight ontology layer inspired by Andrej Karpathy's `LLM Wiki` idea:
[LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

This project gives you:

- A practical folder layout for raw sources, canonical ontology registries, and generated wiki pages
- A small local CLI for `ingest`, `reindex`, `lint`, `status`, and `log`
- An `AGENTS.md` file that tells Codex how to maintain the wiki
- Minimal intelligence manifests that define vocabulary, dataset roles, and action contracts
- Obsidian-friendly markdown pages, wikilinks, and stable metadata

## What This System Is

This is not a generic RAG chatbot.

It is a persistent knowledge base with four layers:

1. `raw/`: immutable source material you collect
2. `warehouse/jsonl/`: canonical structured ontology truth
3. `wiki/`: markdown pages the LLM creates and updates for humans
4. `AGENTS.md` plus `intelligence/`: the operating schema that tells the LLM how to work

You read and curate.
The LLM ingests, structures, cross-links, updates, and keeps the wiki healthy.

## Folder Layout

```text
{root.name}/
├── AGENTS.md
├── README.md
├── intelligence/
│   ├── glossary.yaml
│   └── manifests/
│       ├── actions.yaml
│       ├── datasets.yaml
│       └── pipelines.yaml
├── raw/
│   ├── inbox/
│   ├── processed/
│   ├── assets/
│   └── notes/
├── scripts/
│   ├── helper_llm.py
│   ├── llm_full_ingest.py
│   ├── llm_wiki.py
│   └── pipeline_check.py
├── templates/
│   ├── answer_receipt_template.md
│   └── source_page_template.md
├── warehouse/
│   └── jsonl/
└── wiki/
    ├── _meta/
    │   ├── dashboard.md
    │   ├── index.md
    │   └── log.md
    ├── analyses/
    ├── concepts/
    ├── entities/
    ├── people/
    ├── projects/
    ├── sources/
    └── timelines/
```

## Quick Start

### 1. Open This Folder As An Obsidian Vault

In Obsidian:

1. `Open folder as vault`
2. Select `{root}`

Recommended Obsidian settings:

- Files and Links -> `New link format`: `Relative path to file`
- Files and Links -> `Use [[Wikilinks]]`: enabled
- Files and Links -> `Attachment folder path`: `raw/assets`

### 2. Create A Virtual Environment

```bash
cd {root}
python3 -m venv .venv
source .venv/bin/activate
python scripts/llm_wiki.py status
```

No third-party Python packages are required for the local scaffold.

### 3. Add Sources

Drop files into `raw/inbox/`.

### 4. Register A Source

Run:

```bash
python scripts/llm_wiki.py ingest raw/inbox/my-source.md --title "My Source Title"
```

This is source registration only. It creates a source page stub, appends a log entry, and rebuilds the index.
It does not perform ontology-backed ingest by itself.

The full closed lifecycle is: `raw -> register -> warehouse/jsonl when applicable -> wiki projection -> meta refresh -> structural validation`.

### 5. Configure Helper LLM

Copy `wikiconfig.example.json` to `wikiconfig.json`, enable helper LLM calls, and
fill in an OpenAI-compatible chat model.

```bash
cp wikiconfig.example.json wikiconfig.json
python scripts/helper_llm.py --root . --check-config
```

### 6. Run Configured Full Ingest

When helper LLM config is ready, run:

```bash
python scripts/llm_full_ingest.py raw/inbox/my-source.md --apply
```

This is the default automated growth loop. It completes the source page, creates
or appends affected wiki pages, appends proposed JSONL records, refreshes
`wiki/_meta/index.md` and `wiki/_meta/log.md`, and writes an ingest report.

It must not modify `raw/`, create accepted truth, delete content, rename pages,
merge pages, or auto-commit. Review `git diff` after each apply.

Use `python scripts/pipeline_check.py raw/inbox/my-source.md` for structural
status after ingest. This check validates artifact shape, not semantic truth.

When a later answer required raw/source fallback or wiki repair, record the
trace with:

```bash
python scripts/llm_wiki.py answer-receipt "Question text" --used-raw raw/inbox/my-source.md --wiki-update wiki/analyses/example.md
```

### 7. Ask Me To Maintain The Wiki

Use prompts like:

- `Use AGENTS.md. Ingest raw/inbox/my-source.md with ontology-backed ingest and update the wiki.`
- `Use AGENTS.md. Answer my question from the wiki and verify uncertain claims against warehouse/jsonl/.`
- `Use AGENTS.md. Run a wiki health check and fix broken or missing cross-links.`

## Daily Workflow

1. Put a source into `raw/inbox/`
2. Register it with the CLI
3. Run `python scripts/llm_full_ingest.py raw/inbox/source.md --apply` when configured helper LLM ingest is available
4. Review changed wiki pages in Obsidian
5. Move the raw file into `raw/processed/` when you are happy

## Scaling Later

This starter kit intentionally avoids embeddings, vector infrastructure, and graph tooling by default.

You can later add:

- ontology extraction skills
- graph projection
- semantic retrieval
- git-based review workflows

Until then, the repo-local contracts and folder structure are enough to start compounding knowledge.
"""

    return f"""# LLM Wiki for Obsidian

An Obsidian-first, agent-maintained wiki inspired by Andrej Karpathy's `LLM Wiki` idea:
[LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

This project gives you:

- A practical folder layout for raw sources and generated wiki pages
- A small local CLI for `ingest`, `reindex`, `lint`, `status`, and `log`
- An `AGENTS.md` file that tells Codex how to maintain the wiki
- Obsidian-friendly markdown pages, wikilinks, and stable metadata

## What This System Is

This is not a generic RAG chatbot.

It is a persistent knowledge base with three layers:

1. `raw/`: immutable source material you collect
2. `wiki/`: markdown pages the LLM creates and updates
3. `AGENTS.md`: the operating schema that tells the LLM how to work

You read and curate.
The LLM ingests, cross-links, updates, and keeps the wiki healthy.

## Folder Layout

```text
{root.name}/
├── AGENTS.md
├── README.md
├── raw/
│   ├── inbox/
│   ├── processed/
│   ├── assets/
│   └── notes/
├── scripts/
│   └── llm_wiki.py
├── templates/
│   └── source_page_template.md
└── wiki/
    ├── _meta/
    │   ├── dashboard.md
    │   ├── index.md
    │   └── log.md
    ├── analyses/
    ├── concepts/
    ├── entities/
    ├── people/
    ├── projects/
    ├── sources/
    └── timelines/
```

## Quick Start

### 1. Open This Folder As An Obsidian Vault

In Obsidian:

1. `Open folder as vault`
2. Select `{root}`

Recommended Obsidian settings:

- Files and Links -> `New link format`: `Relative path to file`
- Files and Links -> `Use [[Wikilinks]]`: enabled
- Files and Links -> `Attachment folder path`: `raw/assets`

Helpful plugins:

- `Dataview`
- `Web Clipper`
- `Templater` (optional)
- `Marp` (optional for decks)

### 2. Create A Virtual Environment

```bash
cd {root}
python3 -m venv .venv
source .venv/bin/activate
python scripts/llm_wiki.py status
```

No third-party Python packages are required.

### 3. Add Sources

Drop files into `raw/inbox/`.

Examples:

- Markdown clipped from a web article
- Notes exported from Obsidian or Apple Notes
- Meeting transcripts
- Research summaries
- Plain text files

If a source is a PDF, web page, or image-heavy document, keep the raw file in `raw/inbox/` and either:

- also save a companion markdown/text note into `raw/notes/`, or
- ask me to read the file directly and write the wiki updates

### 4. Register A Source

Run:

```bash
python scripts/llm_wiki.py ingest raw/inbox/my-source.md --title "My Source Title"
```

This does three things:

- creates a source page in `wiki/sources/`
- appends an ingest entry to `wiki/_meta/log.md`
- rebuilds `wiki/_meta/index.md`

This is source registration only.
It does not auto-summarize the source or perform ontology-backed ingest.
That is deliberate: the LLM or a higher-level ingest skill should read the source and write the synthesis with context.

Full wiki ingest means the closed lifecycle: `raw -> register -> wiki projection -> meta refresh -> structural validation`.

### 5. Ask Me To Maintain The Wiki

Use prompts like:

- `Read raw/inbox/my-source.md and fully ingest it into the wiki.`
- `Update the relevant concept, entity, and project pages based on the new source.`
- `Create any missing pages that should exist after this ingest.`
- `Run a wiki health check and fix broken or missing cross-links.`
- `Answer my question using the wiki, then save the answer under wiki/analyses/.`

The operating rules I should follow are in `AGENTS.md`.

## Daily Workflow

### Ingest One Source Carefully

1. Put a source into `raw/inbox/`
2. Register it with the CLI
3. Ask me or an ontology-backed ingest skill to process it into the wiki
4. Review the changed pages in Obsidian
5. Move the raw file into `raw/processed/` when you are happy

### Batch Ingest

1. Put many files into `raw/inbox/`
2. Register each source with the CLI
3. Ask me or an ontology-backed ingest skill to process them one by one
4. Ask me to run `lint` and clean up gaps afterward

## Commands

### Status

```bash
python scripts/llm_wiki.py status
```

Shows counts for raw files, wiki pages, log entries, and index entries.

### Rebuild Index

```bash
python scripts/llm_wiki.py reindex
```

Recreates `wiki/_meta/index.md` from the current wiki pages.

### Lint

```bash
python scripts/llm_wiki.py lint
```

Checks for:

- broken wikilinks
- orphan pages
- pages without YAML frontmatter

### Append A Log Entry

```bash
python scripts/llm_wiki.py log query "Compared two vendors and created a summary page."
```

## How To Have Me Maintain The Wiki Well

When you want me to work on this wiki, point me at this project root and say exactly what mode you want:

- `Ingest mode`: read a new source and integrate it
- `Query mode`: answer a question from the wiki and save the answer back
- `Lint mode`: inspect the wiki for health issues and fix them
- `Refactor mode`: improve page structure, naming, and linking without changing factual content

Good maintenance prompts:

- `Use AGENTS.md. Ingest raw/inbox/2026-04-08-openai-agents.md into the wiki.`
- `Use AGENTS.md. Treat python scripts/llm_wiki.py ingest as source registration only, then run ontology-backed ingest.`
- `Use AGENTS.md. Compare the two project pages and save the result under wiki/analyses/.`
- `Use AGENTS.md. Run a lint pass, fix broken links, and update the dashboard.`
- `Use AGENTS.md. Read the last five log entries and continue the unfinished threads.`

## Suggested Ingest Routine

For best results, ask me to do this sequence on each source:

1. Read the raw source
2. Update the source page summary and metadata
3. Update affected overview, concept, entity, person, project, or timeline pages
4. Add or revise cross-links
5. Note contradictions, open questions, and follow-up leads
6. Rebuild index if new pages were created
7. Append a clear log entry

## Scaling Later

This starter kit intentionally avoids heavier infrastructure.

When the wiki grows, you can add:

- local search over markdown
- vector search
- Dataview dashboards
- graph analytics
- git-based review workflows

Until then, `index.md`, `log.md`, and the folder structure are enough to run today.
"""


def glossary_yaml() -> str:
    return """terms:
  - key: raw_source
    definition: Immutable source material stored under raw/ and used as the original evidence surface.
    aliases: [source, raw file]
  - key: canonical_ontology
    definition: Structured machine-truth registries under warehouse/jsonl/ used for provenance-aware reasoning.
    aliases: [ontology registry, canonical structured truth]
  - key: wiki_page
    definition: Human-facing maintained markdown synthesis page under wiki/.
    aliases: [synthesis page, maintained page]
  - key: derived_output
    definition: Any artifact generated from canonical truth that is not itself canonical, such as graph projection or retrieval indexes.
    aliases: [projection, derived artifact]
  - key: entity
    definition: Named person, project, organization, concept, or domain object extracted into canonical registries.
  - key: claim
    definition: Structured statement extracted from a source and tracked with review state and provenance.
  - key: evidence
    definition: Supporting link between a claim and a source segment or source reference.
  - key: segment
    definition: Stable text-reference unit bridging documents, evidence, retrieval, and downstream synthesis.
  - key: analysis_page
    definition: Durable answer or synthesis note saved under wiki/analyses/.
  - key: ontology_backed_ingest
    definition: Repeated source-processing workflow that registers source identity, appends proposed ontology records during automatic ingest, and projects source-backed results into wiki pages before any accepted-truth promotion.
  - key: closed_ingest_pipeline
    definition: Artifact lifecycle contract for source ingest that continues beyond source registration into proposed JSONL appends, wiki projection, meta refresh, structural validation, and completion reporting.
  - key: source_registration_only
    definition: Lightweight source identity registration performed by scripts/llm_wiki.py ingest; it is not full ontology-backed ingest by itself.
  - key: configured_full_ingest
    definition: Configured helper-LLM runtime in scripts/llm_full_ingest.py that can dry-run or apply source-backed wiki growth and proposed JSONL output without semantic fallback.
  - key: proposed_ontology_record
    definition: Automatically generated entity, claim, evidence, or relation candidate stored as proposed/needs_review rather than accepted canonical truth.
  - key: proposed_record_id
    definition: Stable artifact identifier assigned to a proposed ontology record so repeated ingest can skip duplicates without semantic merging.
  - key: content_hash
    definition: Structural hash over source identity, record family, and field-specific source-backed text used for idempotent proposed JSONL writes.
  - key: idempotent_proposed_append
    definition: Append-or-skip behavior for proposed JSONL records where existing ids or content hashes prevent duplicate lines during repeated ingest.
  - key: structural_validation
    definition: Validation that checks artifact presence, parseability, required fields, link integrity, and provenance shape without judging semantic truth.
"""


def datasets_yaml() -> str:
    return """datasets:
  - id: raw_inbox
    path: raw/inbox
    role: inbound source intake
    truth_class: source
    owner: human
  - id: raw_processed
    path: raw/processed
    role: reviewed source archive
    truth_class: source
    owner: human
  - id: warehouse_messages
    path: warehouse/jsonl/messages.jsonl
    role: canonical conversational or event-level registry when the corpus is sequential
    truth_class: canonical
    owner: ontology
  - id: warehouse_documents
    path: warehouse/jsonl/documents.jsonl
    role: canonical document registry
    truth_class: canonical
    owner: ontology
  - id: warehouse_entities
    path: warehouse/jsonl/entities.jsonl
    role: canonical entity registry
    truth_class: canonical
    owner: ontology
  - id: warehouse_claims
    path: warehouse/jsonl/claims.jsonl
    role: canonical claim registry
    truth_class: canonical
    owner: ontology
  - id: warehouse_claim_evidence
    path: warehouse/jsonl/claim_evidence.jsonl
    role: canonical evidence links
    truth_class: canonical
    owner: ontology
  - id: warehouse_segments
    path: warehouse/jsonl/segments.jsonl
    role: canonical text reference layer
    truth_class: canonical
    owner: ontology
  - id: warehouse_derived_edges
    path: warehouse/jsonl/derived_edges.jsonl
    role: derived graph-style edges
    truth_class: derived
    owner: ontology
  - id: wiki_sources
    path: wiki/sources
    role: human-facing source synthesis pages
    truth_class: human_facing
    owner: wiki
  - id: wiki_entities
    path: wiki/entities
    role: human-facing entity pages
    truth_class: human_facing
    owner: wiki
  - id: wiki_people
    path: wiki/people
    role: human-facing person pages
    truth_class: human_facing
    owner: wiki
  - id: wiki_concepts
    path: wiki/concepts
    role: human-facing concept pages
    truth_class: human_facing
    owner: wiki
  - id: wiki_projects
    path: wiki/projects
    role: human-facing project pages
    truth_class: human_facing
    owner: wiki
  - id: wiki_analyses
    path: wiki/analyses
    role: durable answer and synthesis pages
    truth_class: human_facing
    owner: wiki
  - id: graph_projection
    path: warehouse/graph_projection
    role: optional graph-style exploration layer exported from canonical truth
    truth_class: derived
    owner: graph
  - id: pipeline_manifest
    path: intelligence/manifests/pipelines.yaml
    role: declarative stage contract for closed ingest lifecycle expectations
    truth_class: contract
    owner: operator
"""


def actions_yaml() -> str:
    return """actions:
  - id: register_source
    description: Register a raw source into the wiki without full ontology extraction.
    inputs:
      - raw/inbox/*
    reads:
      - raw/inbox
      - templates/source_page_template.md
    writes:
      - wiki/sources
      - wiki/_meta/index.md
      - wiki/_meta/log.md
    notes:
      - This is lighter than ontology-backed ingest and may be used when canonical extraction is not yet available.
      - This is source registration only; do not report it as completed ontology-backed ingest by itself.
  - id: ingest_with_ontology
    description: Update canonical ontology registries first, then refresh wiki pages and meta outputs.
    inputs:
      - raw/inbox/*
    reads:
      - raw/inbox
      - warehouse/jsonl
      - wiki
      - intelligence/glossary.yaml
      - intelligence/manifests/datasets.yaml
      - intelligence/manifests/actions.yaml
    writes:
      - warehouse/jsonl/messages.jsonl
      - warehouse/jsonl/documents.jsonl
      - warehouse/jsonl/entities.jsonl
      - warehouse/jsonl/claims.jsonl
      - warehouse/jsonl/claim_evidence.jsonl
      - warehouse/jsonl/segments.jsonl
      - warehouse/jsonl/derived_edges.jsonl
      - wiki/sources
      - wiki/entities
      - wiki/people
      - wiki/concepts
      - wiki/projects
      - wiki/analyses
      - wiki/_meta/index.md
      - wiki/_meta/log.md
    notes:
      - This is the intended repeated user-facing ingest workflow once the ontology-backed ingest skill exists.
      - Close the lifecycle across source registration, proposed JSONL appends, wiki projection, meta refresh, structural validation, and completion reporting.
      - Agent or helper-model judgment may choose affected pages, claims, relations, contradictions, and uncertainties; filename, keyword, token-shape, retrieval, graph, or YAML shortcuts must not decide semantic truth.
  - id: answer_query
    description: Answer using wiki pages first, with ontology-backed verification when provenance or contradictions matter.
    inputs:
      - user question
    reads:
      - wiki/_meta/index.md
      - wiki
      - warehouse/jsonl
    writes:
      - wiki/analyses
      - wiki/_meta/log.md
    notes:
      - Prefer wiki as the human-facing answer surface and use ontology registries for provenance, contradictions, and coverage checks.
"""


def pipelines_yaml() -> str:
    return """pipelines:
  - id: ontology_backed_ingest
    description: Closed artifact lifecycle for source ingest in an ontology-backed LLM Wiki.
    current_configured_runtime: scripts/llm_full_ingest.py --apply
    semantic_judgment_owner: agent_or_configured_helper_model
    semantic_no_fallback: true
    deterministic_script_scope:
      - file_discovery
      - source_registration
      - id_generation
      - jsonl_parseability
      - required_field_validation
      - link_integrity
      - index_refresh
      - log_append
      - structural_completion_reporting
    forbidden:
      - filename_keyword_semantic_routing
      - token_shape_semantic_routing
      - regex_page_selection_as_understanding
      - auto_accept_claims_without_review_metadata
      - graph_projection_as_canonical_truth
      - retrieval_result_as_truth
      - yaml_as_semantic_wiki
      - manifest_as_runtime_executor
      - semantic_fallback_to_deterministic_summary
      - semantic_success_without_agent_or_configured_llm_judgment
      - structural_validation_as_semantic_completion
    stages:
      - id: register_source
        required: true
        deterministic: true
        notes:
          - scripts/llm_wiki.py ingest covers this stage, not the whole pipeline.
      - id: append_proposed_jsonl
        required_when: ontology_backed_ingest_applies
        agent_judgment_required: true
        notes:
          - Automatic full ingest appends proposed/needs_review records only.
          - Proposed records receive stable artifact ids and content_hash values for source-scoped idempotent append-or-skip.
          - Accepted canonical promotion remains a separate review-gated workflow.
          - Report emitted, appended, and skipped_existing for each relevant registry family.
          - If agent or configured LLM judgment is unavailable, failed, or invalid, report pending/partial/failed instead of substituting deterministic output.
      - id: project_to_wiki
        required: true
        agent_judgment_required: true
        notes:
          - Configured full ingest may create or append affected pages, but must not delete, rename, merge, or overwrite pages.
          - Lexical previews, retrieval output, graph output, and YAML hints may inform diagnostics but must not become semantic fallback success.
      - id: refresh_meta
        required: true
        deterministic: true
      - id: validate
        required: true
        deterministic: true
        structural_only: true
        notes:
          - Validation must not upgrade failed, partial, or pending semantic work into completion.
    reporting:
      required_sections:
        - source_registered
        - proposed_jsonl_records_emitted_appended_skipped_existing
        - wiki_pages_created_or_updated
        - meta_pages_refreshed
        - validation_result
        - unresolved_uncertainties
        - follow_up_actions
"""


def source_template() -> str:
    return """---
title: "{{title}}"
type: source
status: inbox
created: "{{date}}"
updated: "{{date}}"
raw_path: "{{raw_path}}"
tags:
  - source
  - llm-wiki
---

# {{title}}

## Source Metadata

- Raw path: `{{raw_path}}`
- Registered: `{{date}}`

## Summary

TBD.

## Key Facts

- TBD

## Important Claims

- TBD

## Contradictions Or Uncertainty

- TBD

## Open Questions

- TBD

## Affected Pages

- TBD
"""


def dashboard_md(date: str) -> str:
    return f"""---
title: Dashboard
type: meta
status: active
created: {date}
updated: {date}
---

# Dashboard

## Current Focus

- Add sources to `raw/inbox/`
- Register them with `python scripts/llm_wiki.py ingest ...`
- Ask the LLM to integrate them into the wiki

## Useful Commands

```bash
python scripts/llm_wiki.py status
python scripts/llm_wiki.py reindex
python scripts/llm_wiki.py lint
```

## Review Rhythm

- After each ingest: inspect updated pages
- Weekly: run lint
- Monthly: refactor naming and archive stale work
"""


def index_md(date: str) -> str:
    return f"""---
title: "Index"
type: meta
status: active
created: {date}
updated: {date}
---

# Index

This file is rebuilt by `python scripts/llm_wiki.py reindex`.

## Meta

- [[dashboard]] - Add sources to `raw/inbox/`
- [[log]] - Created the Obsidian-first project structure
"""


def log_md(date: str) -> str:
    return f"""---
title: Log
type: meta
status: active
created: {date}
updated: {date}
---

# Log

## [{date}] setup | Initialized LLM Wiki scaffold

- Created the Obsidian-first project structure
- Added `AGENTS.md`, CLI tools, templates, and meta pages
"""


def llm_wiki_py() -> str:
    asset = Path(__file__).resolve().parents[1] / "assets" / "llm_wiki.py"
    if asset.exists():
        return asset.read_text(encoding="utf-8")
    return """#!/usr/bin/env python3
\"\"\"Minimal local tooling for an Obsidian-first LLM Wiki.

The `ingest` command performs source registration only.
It does not run ontology-backed extraction or full wiki synthesis.
\"\"\"

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = ROOT / "wiki"
META_DIR = WIKI_DIR / "_meta"
RAW_DIR = ROOT / "raw"
TEMPLATE_PATH = ROOT / "templates" / "source_page_template.md"

VALID_PAGE_DIRS = [
    "analyses",
    "concepts",
    "entities",
    "people",
    "projects",
    "sources",
    "timelines",
]


def today() -> str:
    return dt.date.today().isoformat()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "untitled"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def iter_markdown_pages() -> list[Path]:
    return sorted(path for path in WIKI_DIR.rglob("*.md") if path.is_file())


def page_title_from_content(path: Path, content: str) -> str:
    match = re.search(r'^title:\\s*"?(.*?)"?\\s*$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    heading = re.search(r"^#\\s+(.+)$", content, re.MULTILINE)
    if heading:
        return heading.group(1).strip()
    return path.stem.replace("-", " ").title()


def page_type_from_path(path: Path) -> str:
    try:
        return path.relative_to(WIKI_DIR).parts[0]
    except ValueError:
        return "unknown"


def extract_summary(content: str) -> str:
    lines = [line.strip() for line in content.splitlines()]
    for line in lines:
        if not line or line.startswith("---") or line.startswith("#") or line.startswith("title:"):
            continue
        if line.startswith("type:") or line.startswith("status:") or line.startswith("created:") or line.startswith("updated:"):
            continue
        if line.startswith("- "):
            return line[2:].strip()
        return line
    return "No summary yet."


def has_frontmatter(content: str) -> bool:
    return content.startswith("---\\n")


def wikilinks(content: str) -> list[str]:
    return re.findall(r"\\[\\[([^\\]|#]+)", content)


def page_lookup() -> dict[str, Path]:
    lookup: dict[str, Path] = {}
    for path in iter_markdown_pages():
        lookup[path.stem] = path
    return lookup


def rebuild_index() -> Path:
    pages_by_section: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for path in iter_markdown_pages():
        rel = path.relative_to(WIKI_DIR)
        content = read_text(path)
        if rel == Path("_meta/index.md"):
            continue
        title = page_title_from_content(path, content)
        summary = extract_summary(content)
        section = page_type_from_path(path)
        pages_by_section[section].append((path.stem, title, summary))

    lines = [
        "---",
        'title: "Index"',
        "type: meta",
        "status: active",
        f"created: {today()}",
        f"updated: {today()}",
        "---",
        "",
        "# Index",
        "",
        "This file is rebuilt by `python scripts/llm_wiki.py reindex`.",
        "",
    ]

    ordered_sections = ["_meta"] + VALID_PAGE_DIRS
    for section in ordered_sections:
        entries = sorted(pages_by_section.get(section, []), key=lambda item: item[1].lower())
        if not entries:
            continue
        heading = "Meta" if section == "_meta" else section.replace("-", " ").title()
        lines.extend([f"## {heading}", ""])
        for stem, title, summary in entries:
            lines.append(f"- [[{stem}]] - {summary}")
        lines.append("")

    out = META_DIR / "index.md"
    write_text(out, "\\n".join(lines).rstrip() + "\\n")
    return out


def append_log(kind: str, title: str, bullets: list[str]) -> Path:
    path = META_DIR / "log.md"
    existing = read_text(path) if path.exists() else "---\\ntitle: Log\\ntype: meta\\nstatus: active\\ncreated: {}\\nupdated: {}\\n---\\n\\n# Log\\n".format(today(), today())
    entry_lines = [
        "",
        f"## [{today()}] {kind} | {title}",
        "",
    ]
    for bullet in bullets:
        entry_lines.append(f"- {bullet}")
    entry_lines.append("")
    write_text(path, existing.rstrip() + "\\n" + "\\n".join(entry_lines))
    return path


def ingest_source(raw_path_str: str, title: str | None) -> int:
    raw_path = (ROOT / raw_path_str).resolve() if not Path(raw_path_str).is_absolute() else Path(raw_path_str).resolve()
    if not raw_path.exists():
        print(f"Source not found: {raw_path}", file=sys.stderr)
        return 1

    if ROOT not in raw_path.parents and raw_path != ROOT:
        print("Source path must live inside this project.", file=sys.stderr)
        return 1

    source_title = title or raw_path.stem.replace("-", " ").replace("_", " ").title()
    filename = f"source-{today()}-{slugify(source_title)}.md"
    source_page = WIKI_DIR / "sources" / filename
    relative_raw_path = raw_path.relative_to(ROOT).as_posix()

    template = read_text(TEMPLATE_PATH)
    content = (
        template.replace("{{title}}", source_title)
        .replace("{{date}}", today())
        .replace("{{raw_path}}", relative_raw_path)
    )

    if source_page.exists():
        print(f"Source page already exists: {source_page.relative_to(ROOT)}")
    else:
        write_text(source_page, content)
        print(f"Created source page: {source_page.relative_to(ROOT)}")

    append_log(
        "ingest",
        source_title,
        [
            f"Registered source at `{relative_raw_path}`",
            f"Created or reused `[[{source_page.stem}]]`",
            "Pending LLM synthesis or ontology-backed ingest into the broader wiki",
        ],
    )
    rebuild_index()
    return 0


def lint_wiki() -> int:
    lookup = page_lookup()
    broken: list[tuple[Path, str]] = []
    orphans: list[Path] = []
    no_frontmatter: list[Path] = []
    inbound: dict[str, int] = defaultdict(int)

    for path in iter_markdown_pages():
        content = read_text(path)
        if not has_frontmatter(content):
            no_frontmatter.append(path)
        for link in wikilinks(content):
            if link in lookup:
                inbound[link] += 1
            else:
                broken.append((path, link))

    for stem, path in lookup.items():
        rel = path.relative_to(WIKI_DIR)
        if rel.parts[0] == "_meta":
            continue
        if inbound.get(stem, 0) == 0:
            orphans.append(path)

    print("Lint results")
    print(f"- Broken wikilinks: {len(broken)}")
    print(f"- Orphan pages: {len(orphans)}")
    print(f"- Missing frontmatter: {len(no_frontmatter)}")
    print("")

    if broken:
        print("Broken wikilinks:")
        for path, link in broken:
            print(f"- {path.relative_to(ROOT)} -> [[{link}]]")
        print("")

    if orphans:
        print("Orphan pages:")
        for path in orphans:
            print(f"- {path.relative_to(ROOT)}")
        print("")

    if no_frontmatter:
        print("Pages missing frontmatter:")
        for path in no_frontmatter:
            print(f"- {path.relative_to(ROOT)}")
        print("")

    return 1 if broken or no_frontmatter else 0


def status() -> int:
    markdown_pages = iter_markdown_pages()
    raw_files = [path for path in RAW_DIR.rglob("*") if path.is_file()]
    log_path = META_DIR / "log.md"
    index_path = META_DIR / "index.md"
    log_entries = 0
    index_entries = 0

    if log_path.exists():
        log_entries = len(re.findall(r"^##\\s+\\[", read_text(log_path), re.MULTILINE))
    if index_path.exists():
        index_entries = len(re.findall(r"^- \\[\\[", read_text(index_path), re.MULTILINE))

    print("LLM Wiki status")
    print(f"- Root: {ROOT}")
    print(f"- Raw files: {len(raw_files)}")
    print(f"- Wiki pages: {len(markdown_pages)}")
    print(f"- Log entries: {log_entries}")
    print(f"- Index entries: {index_entries}")
    return 0


def log_command(kind: str, title: str, bullets: list[str]) -> int:
    append_log(kind, title, bullets or ["No details recorded."])
    print(f"Appended {kind} entry to wiki/_meta/log.md")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local tooling for an Obsidian-first LLM Wiki. `ingest` is source registration only."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser(
        "ingest",
        help="Register a raw source and create a source page stub. This is not ontology-backed ingest.",
    )
    ingest.add_argument("path", help="Path to the raw source, absolute or relative to project root.")
    ingest.add_argument("--title", help="Human-readable title for the source page.")

    sub.add_parser("reindex", help="Rebuild wiki/_meta/index.md")
    sub.add_parser("lint", help="Check for broken links, orphans, and missing frontmatter.")
    sub.add_parser("status", help="Show counts and basic wiki health metrics.")

    log_parser = sub.add_parser("log", help="Append a structured log entry.")
    log_parser.add_argument("kind", help="Entry type such as ingest, query, lint, or refactor.")
    log_parser.add_argument("title", help="Short title for the log entry.")
    log_parser.add_argument(
        "details",
        nargs="*",
        help="Optional bullet items for the log entry.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        return ingest_source(args.path, args.title)
    if args.command == "reindex":
        out = rebuild_index()
        print(f"Rebuilt {out.relative_to(ROOT)}")
        return 0
    if args.command == "lint":
        return lint_wiki()
    if args.command == "status":
        return status()
    if args.command == "log":
        return log_command(args.kind, args.title, args.details)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
"""


def helper_llm_py() -> str:
    return read_source_repo_file("scripts/helper_llm.py")


def llm_full_ingest_py() -> str:
    return read_source_repo_file("scripts/llm_full_ingest.py")


def pipeline_check_py() -> str:
    return read_source_repo_file("scripts/pipeline_check.py")


def wikiconfig_example_json() -> str:
    return read_source_repo_file("wikiconfig.example.json")


def answer_receipt_template() -> str:
    return read_source_repo_file("templates/answer_receipt_template.md")


def gitignore_text() -> str:
    return """.venv/
__pycache__/
*.pyc
.DS_Store
wikiconfig.json
"""


def scaffold(target: Path, force: bool, profile: str) -> None:
    date = today()
    ensure_safe_target(target, force)

    directories = [
        target / "raw" / "inbox",
        target / "raw" / "processed",
        target / "raw" / "assets",
        target / "raw" / "notes",
        target / "scripts",
        target / "templates",
        target / "wiki" / "_meta",
        target / "wiki" / "analyses",
        target / "wiki" / "concepts",
        target / "wiki" / "entities",
        target / "wiki" / "people",
        target / "wiki" / "projects",
        target / "wiki" / "sources",
        target / "wiki" / "timelines",
    ]

    if profile == "wiki-plus-ontology":
        directories.extend(
            [
                target / "intelligence" / "manifests",
                target / "warehouse" / "jsonl",
            ]
        )

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    write_text(target / "AGENTS.md", agents_md(profile))
    write_text(target / "README.md", readme(target, profile))
    write_text(target / ".gitignore", gitignore_text())
    write_text(target / "scripts" / "llm_wiki.py", llm_wiki_py())
    write_text(target / "templates" / "source_page_template.md", source_template())
    write_text(target / "templates" / "answer_receipt_template.md", answer_receipt_template())
    write_text(target / "wiki" / "_meta" / "dashboard.md", dashboard_md(date))
    write_text(target / "wiki" / "_meta" / "index.md", index_md(date))
    write_text(target / "wiki" / "_meta" / "log.md", log_md(date))
    if profile == "wiki-plus-ontology":
        write_text(target / "wikiconfig.example.json", wikiconfig_example_json())
        write_text(target / "scripts" / "helper_llm.py", helper_llm_py())
        write_text(target / "scripts" / "llm_full_ingest.py", llm_full_ingest_py())
        write_text(target / "scripts" / "pipeline_check.py", pipeline_check_py())
        write_text(target / "intelligence" / "glossary.yaml", glossary_yaml())
        write_text(target / "intelligence" / "manifests" / "datasets.yaml", datasets_yaml())
        write_text(target / "intelligence" / "manifests" / "actions.yaml", actions_yaml())
        write_text(target / "intelligence" / "manifests" / "pipelines.yaml", pipelines_yaml())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scaffold an Obsidian-first LLM Wiki workspace.")
    parser.add_argument("target", help="Target directory for the new workspace.")
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        default="wiki-only",
        help="Scaffold profile. Use wiki-plus-ontology for canonical ontology starter files.",
    )
    parser.add_argument("--force", action="store_true", help="Allow writing scaffold files into a non-empty directory.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    target = Path(args.target).expanduser().resolve()
    scaffold(target, args.force, args.profile)
    print(f"Scaffolded LLM Wiki workspace at {target} with profile={args.profile}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
