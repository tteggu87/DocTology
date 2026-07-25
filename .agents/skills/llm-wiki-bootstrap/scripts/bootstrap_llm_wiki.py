#!/usr/bin/env python3
"""Scaffold an Obsidian-first LLM Wiki workspace."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path


def today() -> str:
    return dt.date.today().isoformat()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def gitignore_text(profile: str) -> str:
    base = """.venv/
__pycache__/
*.pyc
.DS_Store
.omx/
.gstack/
"""
    if profile == "llm-first-ontology":
        base += """
# Local helper-model secrets. Keep wikiconfig.example.json in git instead.
wikiconfig.json
"""
    return base


def wikiconfig_example_json() -> str:
    return """{
  "_meta": {
    "purpose": "Example helper-model config for a strict LLM-first wiki.",
    "runtime_filename": "wikiconfig.json",
    "behavior_summary": [
      "llmWiki.enabled = false -> disable backend helper-model API calls. Semantic CLI commands emit agent handoff prompts/bundles for the surrounding chat LLM instead of claiming semantic success.",
      "llmWiki.enabled = true -> use models[0] as the backend helper LLM for strict compile/query workflows.",
      "This file does not switch the surrounding Codex/ChatGPT conversation to a different model. Agent-mediated chat-LLM processing must be explicit: emit the bundle/prompt, let the chat agent process it, then save a proposal or reviewed page intentionally."
    ]
  },
  "llmWiki": {
    "enabled": false,
    "_enabled_meaning": {
      "false": "No helper-model API calls from local scripts. Scripts emit agent handoff prompts/bundles for the surrounding chat agent.",
      "true": "Enable backend-only helper-model API calls through models[0]."
    }
  },
  "models": [
    {
      "title": "Helper Chat Model",
      "provider": "openai",
      "model": "gpt-4.1-mini",
      "apiKey": "YOUR_API_KEY",
      "apiBase": "https://api.openai.com/v1",
      "_note": "Current code uses models[0] only. Provider must currently be 'openai', but apiBase may point to any OpenAI-compatible endpoint."
    }
  ],
  "embeddingsProvider": {
    "provider": "openai",
    "model": "text-embedding-3-small",
    "apiKey": "YOUR_API_KEY",
    "apiBase": "https://api.openai.com/v1",
    "_note": "Parsed by the loader but not required by the strict compile/query path."
  },
  "rerankerProvider": {
    "provider": "openai",
    "model": "your-reranker-model",
    "apiKey": "YOUR_API_KEY",
    "apiBase": "https://example.invalid/v1",
    "_note": "Parsed by the loader but not required by the strict compile/query path."
  }
}
"""


def sqlite_operational_schema_sql() -> str:
    return """-- sqlite_operational.schema.sql
-- Purpose: operational index schema for a file-canonical LLM Wiki

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS pages (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  page_type TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  checksum TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS page_links (
  from_page_id TEXT NOT NULL,
  to_page_id TEXT,
  to_link_text TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('resolved', 'unresolved')),
  created_at TEXT NOT NULL,
  FOREIGN KEY (from_page_id) REFERENCES pages(id)
);

CREATE TABLE IF NOT EXISTS page_sources (
  page_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  relation_type TEXT NOT NULL CHECK (relation_type IN ('primary', 'supporting', 'mentioned')),
  PRIMARY KEY (page_id, source_id, relation_type),
  FOREIGN KEY (page_id) REFERENCES pages(id)
);

CREATE TABLE IF NOT EXISTS aliases (
  alias_text TEXT NOT NULL,
  target_type TEXT NOT NULL CHECK (target_type IN ('page', 'entity')),
  target_id TEXT NOT NULL,
  PRIMARY KEY (alias_text, target_type, target_id)
);

CREATE TABLE IF NOT EXISTS tags (
  page_id TEXT NOT NULL,
  tag TEXT NOT NULL,
  PRIMARY KEY (page_id, tag),
  FOREIGN KEY (page_id) REFERENCES pages(id)
);

CREATE TABLE IF NOT EXISTS memories (
  id TEXT PRIMARY KEY,
  memory_type TEXT NOT NULL CHECK (
    memory_type IN ('preference', 'active_context', 'agent_note', 'task_memory', 'working_fact')
  ),
  subject TEXT,
  content TEXT NOT NULL,
  source_ref TEXT,
  confidence REAL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  job_type TEXT NOT NULL CHECK (
    job_type IN ('register_source', 'reindex_sqlite', 'refresh_duckdb', 'extract_claims', 'audit_health')
  ),
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'success', 'failed')),
  started_at TEXT,
  finished_at TEXT,
  detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_pages_title ON pages(title);
CREATE INDEX IF NOT EXISTS idx_page_links_from ON page_links(from_page_id);
CREATE INDEX IF NOT EXISTS idx_page_links_to ON page_links(to_page_id);
CREATE INDEX IF NOT EXISTS idx_aliases_text ON aliases(alias_text);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""


def duckdb_analytical_schema_sql() -> str:
    return """-- duckdb_analytical.schema.sql
-- Purpose: analytical warehouse schema for a file-canonical LLM Wiki

CREATE TABLE IF NOT EXISTS sources (
  source_id VARCHAR PRIMARY KEY,
  source_type VARCHAR,
  uri VARCHAR,
  created_at TIMESTAMP,
  raw_checksum VARCHAR
);

CREATE TABLE IF NOT EXISTS page_coverage_snapshots (
  page_id VARCHAR,
  run_id VARCHAR,
  source_count BIGINT,
  claim_count BIGINT,
  entity_count BIGINT,
  freshness_score DOUBLE,
  coverage_score DOUBLE,
  captured_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
  run_id VARCHAR,
  phase VARCHAR,
  status VARCHAR,
  detail VARCHAR,
  page_id VARCHAR,
  severity VARCHAR,
  created_at TIMESTAMP
);
"""


def generated_helper_script(name: str) -> str:
    source = (Path(__file__).resolve().parent / name).read_text(encoding="utf-8")
    return source.replace("Path(__file__).resolve().parents[4]", "Path(__file__).resolve().parent.parent")


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


PROFILES = ["wiki-only", "wiki-plus-ontology", "llm-first-ontology"]


def wiki_only_agents_md() -> str:
    return """# AGENTS.md

This repository is an Obsidian-first LLM Wiki.

The human curates sources and asks questions.
The agent maintains the wiki.

<!-- LLM_WIKI_CONTRACT_START -->

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

## Page Creation And Promotion Thresholds

- Create or refresh a `wiki/sources/` page for an explicit source that should remain verifiable or reusable.
- Create or promote a concept, entity, person, project, or timeline page only when it is stable enough for future reuse, appears across multiple sources or canonical surfaces, or the user explicitly asks to preserve it.
- A passing mention is not enough for a standalone page. Keep it in the source page until its scope becomes durable.
- Before creating a page, search for an existing page with overlapping scope. Extend or merge the existing page instead of creating a duplicate.
- Use `wiki/analyses/` for durable comparisons, decisions, synthesized answers, plan reviews, and unresolved tradeoffs.
- A thin stub is acceptable only when the page is required as a navigation or evidence path and its missing evidence is stated explicitly.

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
- `status`: usually `active`, `draft`, `superseded`, or `open-question`
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

<!-- LLM_WIKI_CONTRACT_END -->
"""


def ontology_agents_md() -> str:
    return """# AGENTS.md

This repository is an Obsidian-first LLM Wiki with a lightweight ontology layer.

The human curates sources and asks questions.
The agent maintains the wiki and the canonical ontology artifacts.

<!-- LLM_WIKI_CONTRACT_START -->

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

## Page Creation And Promotion Thresholds

- Create or refresh a `wiki/sources/` page for an explicit source that should remain verifiable or reusable.
- Create or promote a concept, entity, person, project, or timeline page only when it is stable enough for future reuse, appears across multiple sources or canonical surfaces, or the user explicitly asks to preserve it.
- A passing mention is not enough for a standalone semantic page. Keep it in the source page or ontology citation substrate until its scope becomes durable.
- Before creating a page, search for an existing page with overlapping scope. Extend or merge the existing page instead of creating a duplicate.
- Use `wiki/analyses/` for durable comparisons, decisions, synthesized answers, plan reviews, and unresolved tradeoffs.
- A thin stub is acceptable only when the page is required as a navigation or evidence path and its missing evidence is stated explicitly.

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
- `status`: usually `active`, `draft`, `superseded`, or `open-question`
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

<!-- LLM_WIKI_CONTRACT_END -->
"""


def agents_md(profile: str) -> str:
    if profile == "llm-first-ontology":
        return """# AGENTS.md

This repository is an Obsidian-first LLM Wiki with a strict LLM-first ontology contract layer.

<!-- LLM_WIKI_CONTRACT_START -->

## Strict LLM-First Semantic Rule

Semantic judgment has exactly one default path: LLM-first compile/query over wiki, ontology, source evidence, and citation anchors.

The preferred autonomous path is the surrounding chat agent reading the repo contracts, wiki, ontology, and citation anchors directly. A configured helper LLM in `wikiconfig.json` is an optional backend accelerator for bounded compile/query work, not the only semantic path.

Deterministic code may read files, generate IDs, calculate line ranges, create citation anchors, project source pages, refresh indexes/navigation pages, and validate structure.

Deterministic code must not generate semantic answer drafts, choose meaning-bearing page updates as truth, silently fall back to regex/page heuristics, or treat unreviewed compile proposals as query evidence.

If no helper LLM is configured, local scripts must emit an agent handoff bundle/prompt rather than claim semantic success. The surrounding chat agent may then perform the LLM-first semantic work and save a proposal or reviewed page intentionally.

Compile output is a human-review proposal. It must not automatically modify active concept, entity, project, timeline, or analysis pages.

## Wiki Page Roles And Promotion Thresholds

- `wiki/sources/` registers explicit sources, citation coverage, source metadata, key claims, contradictions, uncertainty, and links to affected pages.
- `wiki/concepts/`, `wiki/entities/`, `wiki/people/`, `wiki/projects/`, and `wiki/timelines/` contain stable reusable semantic pages.
- `wiki/analyses/` contains durable comparisons, decisions, synthesized answers, plan reviews, compile proposals, and unresolved tradeoffs.
- Create or promote a standalone semantic page only when it is stable enough for future reuse, appears across multiple sources or canonical surfaces, or the user explicitly asks to preserve it.
- A passing mention is not enough. Before creating a page, search for overlapping scope and extend or propose a merge into the existing page.
- A thin stub is acceptable only when it is required as a navigation or evidence path and its missing evidence is explicit.

## Source Registration And Semantic Promotion Workflow

When a source is ingested:

1. Register the immutable source and citation anchors in the canonical file-layer substrate.
2. Create or refresh its `wiki/sources/` page with summary, key facts, important claims, contradictions or uncertainty, open questions, and affected-page links.
3. Identify affected semantic pages and check for overlapping scope before proposing new pages.
4. Save meaning-bearing changes as an LLM compile proposal with human-review-required status.
5. Do not automatically rewrite active concept, entity, person, project, timeline, or durable analysis pages.
6. Refresh `wiki/_meta/index.md` when page inventory or reading routes change.
7. Append a clear entry to `wiki/_meta/log.md` after meaningful ingest or review work.

## Query Workflow

When the user asks a question:

1. Read `wiki/_meta/index.md` first.
2. Identify likely relevant pages.
3. Read the smallest set of pages that can answer well.
4. Follow wikilinks. When a page you read contains `[[link-name]]` wikilinks relevant to the question, resolve and read those linked pages too. Wikilinks are not decoration; they are paths to evidence. For example, `[[concept-name]]` maps to `wiki/concepts/concept-name.md`, and `[[source-example]]` maps to `wiki/sources/source-example.md`.
5. Traverse recursively. If a linked page contains further relevant wikilinks, follow them to a reasonable depth of 2–3 hops. Stop when the question is answered or no more relevant links exist.
6. Use `warehouse/jsonl/...` for provenance checks, contradiction checks, claim validation, or exact source coverage when wiki pages are too thin or uncertain.
7. Synthesize an answer grounded in the wiki, with ontology-backed verification when needed.
8. Save durable answers according to the Durable Answer Rule below.

## Link Traversal Rules

- **Minimum depth.** For any question involving two or more concepts, follow at least 2 hops of relevant wikilinks before answering. Do not stop at the first page.
- **Fan-out.** When a page links to multiple concepts relevant to the question, read all of those linked pages, not just the first.
- **Refuse when evidence is absent.** If, after traversing up to 3 hops, no evidence supports an answer, explicitly state that the evidence is absent. Do not fabricate an answer.
- **Track the path.** Before answering, list every page read in traversal order.

## Durable Answer Rule

Durable query answers must be saved automatically under `wiki/analyses/` when writes are available. Use `scripts/query_analysis.py` or an equivalent bounded write to include the question, answer, evidence basis, uncertainty, and proposed wiki updates.

Automatic durable-answer saving may update `wiki/analyses/`, `wiki/_meta/index.md`, and `wiki/_meta/log.md`.
It must not automatically rewrite active concept, entity, person, project, or timeline pages.
Meaning-bearing active page changes belong in proposed updates or compile proposals until reviewed.

## Startup Ritual

Before substantial work:

1. Read this `AGENTS.md`.
2. Read `intelligence/contract_index.yaml`.
3. Read `wiki/_meta/index.md` if it exists.
4. Read recent entries in `wiki/_meta/log.md` if they exist.
5. Prefer wiki pages and meta surfaces before raw files.

## Layer Contract

- `raw/` is immutable source truth.
- `warehouse/jsonl/` is provenance and citation substrate.
- `wiki/` is the LLM/human primary reasoning surface.
- `intelligence/` is contract-only YAML, not a second wiki.
- Python owns execution, validation, IDs, line ranges, and bookkeeping.
- LLM owns semantic judgment.
- Human review owns active truth approval.

<!-- LLM_WIKI_CONTRACT_END -->
"""
    if profile == "wiki-plus-ontology":
        return ontology_agents_md()
    return wiki_only_agents_md()


def readme(target: Path, profile: str) -> str:
    root = target.resolve()
    if profile == "llm-first-ontology":
        return f"""# LLM-First Ontology Wiki

This workspace was bootstrapped with the strict `llm-first-ontology` profile.

It is not a heuristic analyzer and not a simple RAG chatbot.

## Layers

- `raw/`: immutable source material
- `warehouse/jsonl/`: provenance and citation substrate
- `wiki/`: Obsidian-first LLM/human reasoning surface
- `intelligence/`: contract-only YAML for policies, workflows, registries, relation vocabulary, and meta surfaces
- `scripts/`: thin execution and validation surfaces

## Validation

Run:

```bash
python3 scripts/validate_intelligence.py
python3 scripts/validate_workbench_manifest.py
python3 scripts/validate_profiles.py
python3 scripts/validate_registries.py
python3 scripts/validate_repo_docs_intelligence.py
```

## Strict LLM smoke

Without a helper LLM, semantic workflows emit agent handoff bundles/prompts and do not claim semantic success:

```bash
python3 scripts/llm_query.py "smoke test"
python3 scripts/llm_compile_source.py --source-page wiki/sources/<source>.md
```

Explicit prompt inspection is allowed:

```bash
python3 scripts/llm_query.py "smoke test" --emit-selection-prompt
python3 scripts/llm_compile_source.py --source-page wiki/sources/<source>.md --emit-bundle
```

## Next step

Put sources under `{root}/raw/inbox/`, create source pages/citation anchors, then use LLM compile proposals for semantic updates.
"""
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
│       └── datasets.yaml
├── raw/
│   ├── inbox/
│   ├── processed/
│   ├── assets/
│   └── notes/
├── scripts/
│   ├── llm_wiki.py
│   ├── reindex_sqlite_operational.py
│   ├── refresh_duckdb_analytics.py
│   └── verify_three_layer_drift.py
├── state/
├── templates/
│   ├── source_page_template.md
│   └── llm-wiki-three-layer/
│       ├── duckdb_analytical.schema.sql
│       └── sqlite_operational.schema.sql
├── warehouse/
│   └── jsonl/
│       ├── messages.jsonl
│       ├── documents.jsonl
│       ├── entities.jsonl
│       ├── claims.jsonl
│       ├── claim_evidence.jsonl
│       ├── segments.jsonl
│       └── derived_edges.jsonl
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

No third-party Python packages are required for the local scaffold, though DuckDB refresh needs the `duckdb` package when you actually run it.

### 3. Add Sources

Drop files into `raw/inbox/`.

### 4. Register A Source

Run:

```bash
python scripts/llm_wiki.py ingest raw/inbox/my-source.md --title "My Source Title"
```

This is source registration only. It creates a source page stub, appends a log entry, and rebuilds the index.
It does not perform ontology-backed ingest by itself.

### 5. Run Ontology-Backed Ingest

If you install `llm-wiki-ontology-ingest` later, use that skill after source registration so the repo can:

- update `warehouse/jsonl/...`
- refresh affected wiki pages
- keep provenance-aware structured truth aligned with human-facing synthesis

### 6. Rebuild SQLite Or Refresh Wiki Analytics DuckDB

Run:

```bash
python scripts/reindex_sqlite_operational.py --repo-root .
python scripts/refresh_duckdb_analytics.py --repo-root .
python scripts/verify_three_layer_drift.py --repo-root .
```

These helpers are rebuildable support tools.
They do not replace canonical file truth under `raw/`, `warehouse/jsonl/`, or `wiki/`.
The bootstrap-layer DuckDB is a local wiki analytics mirror, not the ontology-core mirror contract.

### 7. Ask Me To Maintain The Wiki

Use prompts like:

- `Use AGENTS.md. Ingest raw/inbox/my-source.md with ontology-backed ingest and update the wiki.`
- `Use AGENTS.md. Answer my question from the wiki and verify uncertain claims against warehouse/jsonl/.`
- `Use AGENTS.md. Run a wiki health check and fix broken or missing cross-links.`

## Daily Workflow

1. Put a source into `raw/inbox/`
2. Register it with the CLI
3. Run ontology-backed ingest if available
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
    definition: Repeated source-processing workflow that updates canonical registries first and then projects results into wiki pages.
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
    value = re.sub(r"[^0-9a-z가-힣ㄱ-ㅎㅏ-ㅣ]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
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


def llm_first_contract_files() -> dict[str, str]:
    return {
        "intelligence/contract_index.yaml": """version: 1
purpose: "Index of deterministic contracts for the LLM-first wiki/ontology workspace."
rules:
  yaml_role: contract_only
  yaml_must_not_contain: [semantic_judgment, answer_drafts, source_summaries, reasoning_claims]
read_order:
  - intelligence/policies/semantic_boundary.yaml
  - intelligence/policies/proposal_lifecycle.yaml
  - intelligence/manifests/semantic_workflows.yaml
  - intelligence/manifests/page_policy.yaml
  - intelligence/manifests/meta_surfaces.yaml
  - intelligence/manifests/relation_types.yaml
  - intelligence/manifests/registries.yaml
contract_groups:
  core:
    - intelligence/glossary.yaml
    - intelligence/policies/semantic_boundary.yaml
    - intelligence/policies/proposal_lifecycle.yaml
    - intelligence/manifests/semantic_workflows.yaml
  query:
    - intelligence/manifests/page_policy.yaml
    - intelligence/manifests/meta_surfaces.yaml
  ontology:
    - intelligence/manifests/relation_types.yaml
    - intelligence/manifests/registries.yaml
  sources:
    - intelligence/manifests/source_families.yaml
    - intelligence/packs/*/pack.yaml
  workbench:
    - intelligence/manifests/workbench.yaml
  docs_intelligence:
    - intelligence/manifests/actions.yaml
    - intelligence/manifests/datasets.yaml
    - intelligence/manifests/entities.yaml
    - intelligence/registry/capabilities.yaml
""",
        "intelligence/policies/semantic_boundary.yaml": """version: 1
purpose: "Boundary between deterministic infrastructure and LLM semantic judgment."
yaml_role: contract_only
semantic_fallback_allowed: false
semantic_llm_required_for_semantic_workflows: true
helper_llm_required_for_semantic_workflows: false
agent_llm_handoff_allowed: true
deterministic_code_allowed: [read_files, compute_ids, compute_line_ranges, create_citation_anchors, project_source_pages, update_indexes, validate_contracts]
deterministic_code_forbidden: [infer_semantic_truth, draft_answers, select_evidence_as_truth, apply_compile_results_to_active_wiki_without_human_review]
content_units:
  role: citation_anchor
  forbidden_role: rag_answer_chunk
compile_proposals:
  status: draft
  human_review_required: true
  query_evidence_allowed_before_review: false
prompt_bundle_emission:
  explicit_flag_required: true
agent_handoff_bundle_emission:
  default_when_helper_missing: true
  not_semantic_success: true
""",
        "intelligence/policies/proposal_lifecycle.yaml": """version: 1
purpose: "Lifecycle policy for LLM-generated compile proposals."
proposal_lifecycle:
  compile_proposal:
    initial_status: draft
    analysis_method: llm_compile_proposal
    trust_level: human_review_required
    queryable_before_review: false
    allowed_transitions:
      draft: [accepted, rejected]
      accepted: [applied]
      rejected: []
      applied: []
""",
        "intelligence/manifests/semantic_workflows.yaml": """version: 1
purpose: "Strict LLM-first semantic workflow contract."
workflows:
  compile_source:
    cli: scripts/llm_compile_source.py
    function: scripts.llm_compile_source:compile_source
    requires_semantic_llm: true
    helper_llm_required: false
    agent_llm_handoff_allowed: true
    missing_helper_behavior: agent_handoff_bundle
    fallback_allowed: false
    explicit_prompt_flags: [--emit-bundle]
    output_status: draft
    output_analysis_method: llm_compile_proposal
  query:
    cli: scripts/llm_query.py
    function: scripts.llm_query:llm_query
    requires_semantic_llm: true
    helper_llm_required: false
    agent_llm_handoff_allowed: true
    missing_helper_behavior: agent_handoff_bundle
    fallback_allowed: false
    explicit_prompt_flags: [--emit-selection-prompt]
    selection_stage:
      uses_page_bodies: false
    answer_stage:
      uses_page_bodies: true
""",
        "intelligence/manifests/page_policy.yaml": """version: 1
purpose: "Runtime filtering policy for pages that may become query evidence."
queryable:
  denied_sections: [_meta]
  denied_status: [draft, superseded]
  denied_analysis_methods: [llm_compile_proposal]
  require_human_review_before_query_evidence: true
""",
        "intelligence/manifests/meta_surfaces.yaml": """version: 1
purpose: "Map-first wiki surfaces that help LLMs navigate before reading bodies."
surfaces:
  wiki_index:
    path: wiki/_meta/index.md
    used_by: [query_selection, compile]
    max_chars: 16000
  wiki_moc:
    path: wiki/_meta/moc.md
    used_by: [query_selection, compile]
    max_chars: 16000
  wiki_link_map:
    path: wiki/_meta/link-map.md
    used_by: [query_selection, compile]
    max_chars: 16000
  source_coverage:
    path: wiki/_meta/source-coverage.md
    used_by: [query_selection, query_answer, compile]
    max_chars: 8000
  orphan_review:
    path: wiki/_meta/orphan-review.md
    used_by: [query_answer, compile]
    max_chars: 8000
  contradiction_review:
    path: wiki/_meta/contradiction-review.md
    used_by: [query_answer, compile]
    max_chars: 8000
""",
        "intelligence/manifests/relation_types.yaml": """version: 1
purpose: "Vocabulary contract for relation labels; not a store of asserted facts."
yaml_role: vocabulary_only
relation_types:
  supports:
    class: semantic
    inverse: supported_by
    from: [claim, concept, source]
    to: [claim, concept, source]
    evidence_required: true
    approval_required: true
  documents:
    class: mechanical
    inverse: documented_by
    from: [source, document]
    to: [concept, entity, project]
    evidence_required: true
    approval_required: false
  depends_on:
    class: semantic
    inverse: depended_on_by
    from: [concept, project, analysis]
    to: [concept, project, source]
    evidence_required: false
    approval_required: true
""",
        "intelligence/manifests/registries.yaml": """version: 1
purpose: "Canonical JSONL registry shape contract."
registries:
  documents:
    path: warehouse/jsonl/documents.jsonl
    key: document_id
    required_fields: [document_id, raw_path]
  content_units:
    path: warehouse/jsonl/content_units.jsonl
    key: unit_id
    required_fields: [unit_id, document_id, source_family_id, profile_id, unit_kind, sequence, text]
    references:
      document_id: {registry: documents, key: document_id}
      profile_id: {registry: profiles, key: profile_id}
  source_versions:
    path: warehouse/jsonl/source_versions.jsonl
    key: source_version_id
    required_fields: [document_id, raw_path, content_hash, source_family_id, ingested_at]
    references:
      document_id: {registry: documents, key: document_id}
      profile_id: {registry: profiles, key: profile_id}
  compile_proposals:
    path: warehouse/jsonl/compile_proposals.jsonl
    key: proposal_id
    required_fields: [proposal_id, proposal_path, status, analysis_method, trust_level, created_at]
  review_events:
    path: warehouse/jsonl/review_events.jsonl
    key: review_event_id
    required_fields: [review_event_id, target_type, target_id, action, reviewed_at]
    references:
      target_id: {registry: compile_proposals, key: proposal_id}
""",
        "intelligence/manifests/source_families.yaml": """version: 1
source_families:
  - key: generic-md-note
    status: generic
    match:
      extensions: [.md, .txt]
""",
        "intelligence/glossary.yaml": """terms:
  - key: strict_llm_first_semantic_workflow
    definition: Semantic compile/query path that must use an LLM. A configured helper LLM may run locally; when no helper is configured, the workflow emits an agent handoff bundle for the surrounding chat LLM instead of falling back to deterministic answer drafts.
  - key: contract_layer
    definition: YAML-backed policy/schema/workflow surface; not a second wiki and not a semantic truth store.
  - key: compile_proposal
    definition: Draft LLM compile output requiring human review before active wiki updates.
""",
        "intelligence/manifests/actions.yaml": """actions:
  - key: compile_source_with_llm
    description: Create a human-review compile proposal through strict helper-LLM workflow.
  - key: answer_query_with_llm_wiki
    description: Answer through strict helper-LLM wiki/ontology query workflow.
  - key: reindex_wiki_operational_index
    description: Rebuild the derived SQLite operational index from canonical wiki files.
  - key: refresh_wiki_analytics_mirror
    description: Refresh the derived DuckDB wiki analytics mirror from canonical JSONL and wiki files.
  - key: verify_three_layer_drift
    description: Check coarse drift across file truth, SQLite operational state, and DuckDB analytics state.
""",
        "intelligence/manifests/datasets.yaml": """datasets:
  - key: raw_inbox
    path: raw/inbox/
    truth_class: source
  - key: wiki_sources
    path: wiki/sources/
    truth_class: human_facing
  - key: contract_index
    path: intelligence/contract_index.yaml
    truth_class: contract
  - key: sqlite_operational_index
    path: state/wiki_index.sqlite
    truth_class: derived_operational
  - key: duckdb_wiki_analytics_mirror
    path: state/wiki_analytics.duckdb
    truth_class: derived_analytics
  - key: three_layer_schema_templates
    path: templates/llm-wiki-three-layer/
    truth_class: contract
""",
        "intelligence/manifests/entities.yaml": "entities: []\n",
        "intelligence/manifests/workbench.yaml": """version: 1
workbench:
  status: optional
  mutation_policy:
    - raw is immutable except on explicit user instruction
    - warehouse/jsonl remains canonical and must not be edited directly from the browser
""",
        "intelligence/registry/capabilities.yaml": """capabilities:
  - key: llm.source.compile
    action: compile_source_with_llm
    implementation: scripts/llm_compile_source.py:compile_source
  - key: llm.query.answer
    action: answer_query_with_llm_wiki
    implementation: scripts/llm_query.py:llm_query
  - key: wiki.operational.reindex
    action: reindex_wiki_operational_index
    implementation: scripts/reindex_sqlite_operational.py:main
  - key: wiki.analytics.refresh
    action: refresh_wiki_analytics_mirror
    implementation: scripts/refresh_duckdb_analytics.py:main
  - key: wiki.three_layer.verify_drift
    action: verify_three_layer_drift
    implementation: scripts/verify_three_layer_drift.py:main
""",
        "intelligence/packs/generic-md-note/pack.yaml": """profile_id: generic-analysis
pack_id: generic-analysis
version: 0.1.0
status: built_in
source_families: [generic-md-note]
unit_kinds: [paragraph]
observation_types: [common.open_question]
analysis_outputs: [generic.compile_proposal]
capabilities:
  parse:
    python: scripts.generic_ingest:parse_generic_source
  compile:
    python: scripts.llm_compile_source:compile_source
""",
    }


def llm_first_script_files() -> dict[str, str]:
    return {
        "scripts/llm_query.py": """#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def llm_query(root: Path, question: str, emit_selection_prompt: bool = False):
    if emit_selection_prompt:
        return {"status": "selection_prompt", "mode": "llm_query", "message": "Explicit selection prompt emission only; this is not semantic success.", "question": question}
    return {"status": "agent_handoff", "mode": "llm_query", "message": "No enabled helper LLM found. Hand this prompt to the current chat agent/LLM. This is not semantic success.", "question": question}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--emit-selection-prompt", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(llm_query(ROOT, args.question, args.emit_selection_prompt), ensure_ascii=False, indent=2))
        return 0
    except RuntimeError as error:
        print(json.dumps({"status": "error", "message": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
""",
        "scripts/llm_compile_source.py": """#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def compile_source(root: Path, source_page: str, emit_bundle: bool = False):
    if emit_bundle:
        return {"status": "prompt_bundle", "mode": "llm_compile_source", "source_page": source_page, "message": "Explicit prompt bundle emission only; this is not semantic success."}
    return {"status": "agent_handoff", "mode": "llm_compile_source", "source_page": source_page, "message": "No enabled helper LLM found. Hand this bundle to the current chat agent/LLM. This is not semantic success."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-page", required=True)
    parser.add_argument("--emit-bundle", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(compile_source(ROOT, args.source_page, args.emit_bundle), ensure_ascii=False, indent=2))
        return 0
    except RuntimeError as error:
        print(json.dumps({"status": "error", "message": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
""",
        "scripts/query_analysis.py": """#!/usr/bin/env python3
import argparse, datetime as dt, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def today():
    return dt.date.today().isoformat()

def slugify(value):
    return re.sub(r"[^A-Za-z0-9가-힣]+", "-", value.strip().lower()).strip("-")[:72] or "query-answer"

def unique_path(question):
    base = f"analysis-{today()}-{slugify(question)}"
    path = ROOT / "wiki/analyses" / f"{base}.md"
    index = 2
    while path.exists():
        path = ROOT / "wiki/analyses" / f"{base}-{index}.md"
        index += 1
    return path

def save_query_analysis(question, answer, sources=None, evidence_mix=None):
    sources = sources or []
    evidence_mix = evidence_mix or {}
    path = unique_path(question)
    path.parent.mkdir(parents=True, exist_ok=True)
    source_lines = "\\n".join(f"- {source}" for source in sources) or "- none recorded"
    mix_lines = "\\n".join(f"- {key}: {value}" for key, value in evidence_mix.items()) or "- not recorded"
    path.write_text(f'''---
title: "Query answer - {question[:80].replace('"', "'")}"
type: analysis
status: active
analysis_method: chat_agent_llm
trust_level: evidence_grounded
created: {today()}
updated: {today()}
tags:
  - llm-wiki
  - query-answer
---

# Query answer - {question}

## Question

{question}

## Answer

{answer.strip()}

## Evidence Mix

{mix_lines}

## Sources

{source_lines}

## Proposed Wiki Updates

_Candidates only. Active semantic pages require review._
''', encoding="utf-8")
    index_path = ROOT / "wiki/_meta/index.md"
    if index_path.exists():
        text = index_path.read_text(encoding="utf-8")
        line = f"- [[{path.stem}]] - Saved durable query answer."
        if f"[[{path.stem}]]" not in text:
            text = text.replace("## Analyses\\n\\n", "## Analyses\\n\\n" + line + "\\n", 1) if "## Analyses\\n\\n" in text else text + "\\n\\n## Analyses\\n\\n" + line + "\\n"
            index_path.write_text(text, encoding="utf-8")
    log_path = ROOT / "wiki/_meta/log.md"
    if log_path.exists():
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\\n## [{today()}] query | {question[:80]}\\n\\n- Saved [[{path.stem}]] in wiki/analyses/.\\n- Active semantic page updates remain proposed updates pending review.\\n")
    return path.relative_to(ROOT).as_posix()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--evidence-mix")
    args = parser.parse_args()
    evidence_mix = json.loads(args.evidence_mix) if args.evidence_mix else {}
    answer = sys.stdin.read()
    print(json.dumps({"status": "ok", "analysis_path": save_query_analysis(args.question, answer, args.source, evidence_mix)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
""",
        "scripts/validate_intelligence.py": """#!/usr/bin/env python3
from pathlib import Path
import sys, yaml

ROOT = Path(__file__).resolve().parent.parent

def require(ok, msg):
    if not ok:
        raise SystemExit(msg)

idx = yaml.safe_load((ROOT / "intelligence/contract_index.yaml").read_text()) or {}
for path in idx.get("read_order", []):
    require((ROOT / path).exists(), f"missing contract: {path}")
for group, patterns in (idx.get("contract_groups", {}) or {}).items():
    for pattern in patterns:
        matches = list(ROOT.glob(pattern)) if "*" in pattern else [ROOT / pattern]
        require(any(p.exists() for p in matches), f"missing contract group file: {group} {pattern}")
boundary = yaml.safe_load((ROOT / "intelligence/policies/semantic_boundary.yaml").read_text()) or {}
require(boundary.get("semantic_fallback_allowed") is False, "semantic fallback must be false")
require(boundary.get("semantic_llm_required_for_semantic_workflows") is True, "semantic LLM must be required")
require(boundary.get("helper_llm_required_for_semantic_workflows") is False, "helper LLM must be optional")
require(boundary.get("agent_llm_handoff_allowed") is True, "agent LLM handoff must be allowed")
workflows = yaml.safe_load((ROOT / "intelligence/manifests/semantic_workflows.yaml").read_text()) or {}
for name, wf in (workflows.get("workflows", {}) or {}).items():
    require(wf.get("requires_semantic_llm") is True, f"{name} must require semantic LLM")
    require(wf.get("helper_llm_required") is False, f"{name} helper LLM must be optional")
    require(wf.get("agent_llm_handoff_allowed") is True, f"{name} must allow agent handoff")
    require(wf.get("missing_helper_behavior") == "agent_handoff_bundle", f"{name} missing helper behavior mismatch")
    require(wf.get("fallback_allowed") is False, f"{name} must not allow fallback")
print("OK intelligence")
""",
        "scripts/validate_workbench_manifest.py": """#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
assert (ROOT / "intelligence/manifests/workbench.yaml").exists()
print("OK workbench manifest")
""",
        "scripts/validate_profiles.py": """#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
assert list((ROOT / "intelligence/packs").glob("*/pack.yaml"))
print("OK profiles=1")
""",
        "scripts/validate_registries.py": """#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
for name in ("documents.jsonl", "content_units.jsonl", "source_versions.jsonl", "compile_proposals.jsonl", "review_events.jsonl"):
    assert (ROOT / "warehouse/jsonl" / name).exists()
print("OK registries")
""",
        "scripts/proposal_review.py": """#!/usr/bin/env python3
import argparse, json, re, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_DIR = ROOT / "warehouse/jsonl"

def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\\n")

def proposal_id(path: Path) -> str:
    return "proposal-" + re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")

def proposal_status(path: Path) -> str:
    text = read_text(path)
    match = re.search(r"^status:\\s*([^\\n]+)", text, re.MULTILINE)
    return match.group(1).strip().strip('"') if match else "draft"

def replace_status(path: Path, status: str) -> None:
    text = read_text(path)
    if re.search(r"^status:\\s*[^\\n]+", text, re.MULTILINE):
        text = re.sub(r"^status:\\s*[^\\n]+", f"status: {status}", text, count=1, flags=re.MULTILINE)
    elif text.startswith("---\\n"):
        text = text.replace("---\\n", f"---\\nstatus: {status}\\n", 1)
    else:
        text = f"---\\nstatus: {status}\\n---\\n\\n{text}"
    write_text(path, text)

def record_proposal(path: Path, status: str) -> str:
    pid = proposal_id(path)
    append_jsonl(REGISTRY_DIR / "compile_proposals.jsonl", {
        "proposal_id": pid,
        "proposal_path": str(path.relative_to(ROOT)),
        "status": status,
        "analysis_method": "llm_compile_proposal",
        "trust_level": "human_review_required",
        "created_at": now(),
    })
    return pid

def record_event(pid: str, action: str) -> None:
    append_jsonl(REGISTRY_DIR / "review_events.jsonl", {
        "review_event_id": "review-" + uuid.uuid4().hex[:12],
        "target_type": "compile_proposal",
        "target_id": pid,
        "action": action,
        "reviewed_at": now(),
    })

def set_status(path: Path, status: str) -> int:
    current = proposal_status(path)
    allowed = {"draft": {"accepted", "rejected"}, "accepted": {"applied"}, "rejected": set(), "applied": set()}
    if status not in allowed.get(current, set()):
        raise SystemExit(f"invalid transition: {current} -> {status}")
    replace_status(path, status)
    pid = record_proposal(path, status)
    record_event(pid, status)
    print(json.dumps({"status": "ok", "proposal_id": pid, "proposal_status": status}, ensure_ascii=False))
    return 0

def apply_reviewed(path: Path, target: Path, content_file: Path) -> int:
    if proposal_status(path) != "accepted":
        raise SystemExit("proposal must be accepted before apply")
    target = target.resolve()
    if ROOT not in target.parents or "wiki" not in target.relative_to(ROOT).parts:
        raise SystemExit("target must be inside this repo's wiki/")
    write_text(target, read_text(content_file))
    replace_status(path, "applied")
    pid = record_proposal(path, "applied")
    record_event(pid, "applied")
    print(json.dumps({"status": "ok", "proposal_id": pid, "target": str(target.relative_to(ROOT))}, ensure_ascii=False))
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(description="Review and apply human-approved LLM compile proposals.")
    sub = parser.add_subparsers(dest="command", required=True)
    status_parser = sub.add_parser("set-status")
    status_parser.add_argument("proposal")
    status_parser.add_argument("--status", required=True, choices=["accepted", "rejected"])
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("proposal")
    apply_parser.add_argument("--target", required=True)
    apply_parser.add_argument("--content-file", required=True)
    args = parser.parse_args()
    if args.command == "set-status":
        return set_status((ROOT / args.proposal).resolve(), args.status)
    if args.command == "apply":
        return apply_reviewed((ROOT / args.proposal).resolve(), (ROOT / args.target).resolve(), Path(args.content_file).resolve())
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
""",
        "scripts/validate_repo_docs_intelligence.py": """#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
for path in ("AGENTS.md", "README.md", "intelligence/contract_index.yaml"):
    assert (ROOT / path).exists()
print("OK repo docs intelligence")
""",
        "scripts/generic_ingest.py": """#!/usr/bin/env python3
print("generic ingest scaffold placeholder: implement repo-specific parsing before use")
""",
        "scripts/wiki_graph_navigation.py": """#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
for name in ("moc.md", "link-map.md", "orphan-review.md", "contradiction-review.md", "source-coverage.md"):
    (ROOT / "wiki/_meta" / name).write_text(f"# {name}\\n", encoding="utf-8")
print("OK wiki graph navigation")
""",
    }


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

    if profile == "llm-first-ontology":
        directories.extend(
            [
                target / "docs",
                target / "intelligence" / "manifests",
                target / "intelligence" / "packs" / "generic-md-note",
                target / "intelligence" / "policies",
                target / "intelligence" / "registry",
                target / "intelligence" / "schemas",
                target / "state",
                target / "templates" / "llm-wiki-three-layer",
                target / "warehouse" / "jsonl",
                target / "warehouse" / "graph_projection",
            ]
        )

    if profile == "wiki-plus-ontology":
        directories.extend(
            [
                target / "intelligence" / "manifests",
                target / "state",
                target / "templates" / "llm-wiki-three-layer",
                target / "warehouse" / "jsonl",
            ]
        )

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    write_text(target / "AGENTS.md", agents_md(profile))
    write_text(target / "README.md", readme(target, profile))
    write_text(target / ".gitignore", gitignore_text(profile))
    write_text(target / "scripts" / "llm_wiki.py", llm_wiki_py())
    write_text(target / "templates" / "source_page_template.md", source_template())
    write_text(target / "wiki" / "_meta" / "dashboard.md", dashboard_md(date))
    write_text(target / "wiki" / "_meta" / "index.md", index_md(date))
    write_text(target / "wiki" / "_meta" / "log.md", log_md(date))
    if profile == "llm-first-ontology":
        write_text(target / "wikiconfig.example.json", wikiconfig_example_json())
        write_text(target / "wikiconfig.json", wikiconfig_example_json())
        for rel_path, content in llm_first_contract_files().items():
            write_text(target / rel_path, content)
        for rel_path, content in llm_first_script_files().items():
            write_text(target / rel_path, content)
        write_text(target / "scripts" / "reindex_sqlite_operational.py", generated_helper_script("reindex_sqlite_operational.py"))
        write_text(target / "scripts" / "refresh_duckdb_analytics.py", generated_helper_script("refresh_duckdb_analytics.py"))
        write_text(target / "scripts" / "verify_three_layer_drift.py", generated_helper_script("verify_three_layer_drift.py"))
        write_text(target / "templates" / "llm-wiki-three-layer" / "sqlite_operational.schema.sql", sqlite_operational_schema_sql())
        write_text(target / "templates" / "llm-wiki-three-layer" / "duckdb_analytical.schema.sql", duckdb_analytical_schema_sql())
        write_text(target / "docs" / "README.md", "# Docs Portal\n\nStart with `../AGENTS.md` and `../intelligence/contract_index.yaml`.\n")
        write_text(target / "docs" / "LLM_FIRST_ONTOLOGY_BOOTSTRAP_PROFILE.md", "# LLM-First Ontology Bootstrap Profile\n\nThis repo was generated with the strict LLM-first ontology profile.\n")
        for name in ("documents.jsonl", "content_units.jsonl", "source_versions.jsonl", "compile_proposals.jsonl", "review_events.jsonl"):
            write_text(target / "warehouse" / "jsonl" / name, "")
    if profile == "wiki-plus-ontology":
        print(
            "Warning: profile=wiki-plus-ontology is deprecated; use profile=llm-first-ontology for strict no-fallback LLM Wiki repos.",
            file=sys.stderr,
        )
        write_text(target / "intelligence" / "glossary.yaml", glossary_yaml())
        write_text(target / "intelligence" / "manifests" / "datasets.yaml", datasets_yaml())
        write_text(target / "intelligence" / "manifests" / "actions.yaml", actions_yaml())
        write_text(target / "scripts" / "reindex_sqlite_operational.py", generated_helper_script("reindex_sqlite_operational.py"))
        write_text(target / "scripts" / "refresh_duckdb_analytics.py", generated_helper_script("refresh_duckdb_analytics.py"))
        write_text(target / "scripts" / "verify_three_layer_drift.py", generated_helper_script("verify_three_layer_drift.py"))
        write_text(target / "templates" / "llm-wiki-three-layer" / "sqlite_operational.schema.sql", sqlite_operational_schema_sql())
        write_text(target / "templates" / "llm-wiki-three-layer" / "duckdb_analytical.schema.sql", duckdb_analytical_schema_sql())
        for name in (
            "messages.jsonl",
            "documents.jsonl",
            "entities.jsonl",
            "claims.jsonl",
            "claim_evidence.jsonl",
            "segments.jsonl",
            "derived_edges.jsonl",
        ):
            write_text(target / "warehouse" / "jsonl" / name, "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scaffold an Obsidian-first LLM Wiki workspace.")
    parser.add_argument("target", help="Target directory for the new workspace.")
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        default="llm-first-ontology",
        help="Scaffold profile. Defaults to llm-first-ontology for strict no-fallback LLM Wiki repos. wiki-plus-ontology is the deprecated legacy ontology scaffold.",
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
