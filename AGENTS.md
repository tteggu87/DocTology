# AGENTS.md

This repository is an Obsidian-first LLM Wiki.

The human curates sources and asks questions.
The agent maintains the wiki.

## Mission

Maintain a persistent, high-signal markdown wiki that sits between raw sources and future reasoning.

Do not answer only in chat when the result belongs in the wiki.
Prefer to turn durable work into durable markdown pages.

## Architecture

There are four layers:

1. `raw/` contains immutable source material. Never modify source contents.
2. `warehouse/jsonl/` contains canonical structured ontology truth such as messages, entities, claims, evidence, segments, and derived edges.
3. `wiki/` contains LLM-maintained human-facing synthesis pages. The agent may create, update, and cross-link these pages. Rename, merge, or deletion operations require explicit human intent and must not be performed by automatic ingest.
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

Use this priority order when layers disagree or when the next step is ambiguous:

1. `raw/` = immutable source material
2. `warehouse/jsonl/...` = canonical structured ontology truth
3. `wiki/` = maintained human-facing synthesis
4. graph projection or retrieval outputs = optional derived aids, never canonical

The wiki is the default reading surface for the human.
The ontology registries are the default machine-truth surface for provenance, contradiction handling, and exact source coverage.

## Folder Semantics

- `warehouse/jsonl/`: canonical structured ontology outputs such as `messages.jsonl`, `documents.jsonl`, `entities.jsonl`, `claims.jsonl`, `claim_evidence.jsonl`, `segments.jsonl`, and `derived_edges.jsonl`
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

## Page Thresholds

Use these thresholds before creating or splitting pages:

- Create a new page when a concept, entity, person, project, or timeline is clearly central to one source or recurs across multiple sources.
- Prefer updating an existing page when the new source extends scope that is already covered.
- Do not create a dedicated page for a passing mention, minor aside, or weakly evidenced fragment.
- Create a thin stub when something is clearly durable but still underdeveloped.
- Split or refactor a page when it becomes too large to scan quickly or starts mixing several distinct topics.

## Source Ingest Workflow

When the user asks to ingest a source:

1. Read the raw source from `raw/inbox/`, `raw/processed/`, or `raw/notes/`.
2. If ontology-backed ingest is available, update the canonical ontology registries first under `warehouse/jsonl/`.
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

If ontology-backed ingest is not yet available, the agent may continue with wiki-only ingest, but should preserve the same source boundaries and note that canonical ontology extraction is pending.

`scripts/llm_wiki.py ingest` is source registration only. It is not full ontology-backed ingest.

`scripts/llm_full_ingest.py --apply` is the minimal configured-LLM full growth loop. It may complete the source page, create or append affected wiki pages, append proposed JSONL records, refresh index/log, and write an ingest report. It must not modify `raw/`, create accepted truth, delete content, rename pages, merge pages, or auto-commit. Review the resulting `git diff` before committing.

`scripts/wiki_growth_graph.py` is the strict automated graph ingest runtime. It requires real LangGraph and a configured ingest LLM for ingest modes, fails fast when either is unavailable, and must not fall back to deterministic semantic drafting. This does not remove the agent-operated semantic workflow: an agent may still read `AGENTS.md`, the wiki map, source pages, and evidence directly, but that path is not an automatic script fallback.

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
6. Use `warehouse/jsonl/...` for provenance checks, contradiction checks, claim validation, or exact source coverage when the wiki alone is too thin or uncertain.
7. Synthesize an answer grounded in the wiki, with ontology-backed verification when needed.
8. If the answer is durable, save it into `wiki/analyses/`.
9. Cross-link that analysis page from relevant pages if appropriate.
10. Append a `query` log entry for substantial work.

## Link Traversal Rules

- **Minimum depth.** For any question involving two or more concepts, follow at least 2 hops of relevant wikilinks before answering. Do not stop at the first page.
- **Fan-out.** When a page links to multiple concepts relevant to the question, read all of those linked pages, not just the first.
- **Refuse when evidence is absent.** If, after traversing up to 3 hops, no evidence supports an answer, explicitly state that the evidence is absent. Do not fabricate an answer.
- **Track the path.** Before answering, list every page read in traversal order.

## Answer Receipt Workflow

When a query reveals that the wiki was insufficient and the agent had to inspect
source pages, raw files, or JSONL hints, leave an answer receipt unless the user
explicitly wants chat-only output.

An answer receipt records:

- the question
- wiki pages actually read
- source pages actually read
- raw files revisited because wiki context was insufficient
- JSONL or ontology hints consulted
- wiki pages created or updated after the answer
- uncertainties and follow-up work

Use:

```bash
python scripts/llm_wiki.py answer-receipt "Question text" \
  --used-wiki wiki/_meta/index.md \
  --used-raw raw/inbox/source.md \
  --wiki-update wiki/analyses/example.md
```

This is structural logging only. It must not become semantic routing, retrieval
ranking, answer generation, or a deterministic fallback. The LLM still decides
what to read, what the answer means, and whether the wiki needs repair.

## Ontology-Aware Ingest And Query Defaults

When ontology-backed ingest is available, treat the default repeated workflow as:

1. source enters `raw/inbox/`
2. ontology-backed ingest updates canonical registries under `warehouse/jsonl/`
3. wiki pages are updated from source plus canonical registries
4. meta pages are refreshed

For repeated user-facing source processing, prefer the ontology-backed ingest skill over ad hoc manual steps.
Reserve direct ontology-core operation for tuning, debugging, or operator workflows.

## New Thread Bootstrap

When a new agent opens this repository in a fresh conversation:

1. Read `AGENTS.md` first.
2. Read `wiki/_meta/index.md` before answering wiki questions.
3. Read `wiki/_meta/log.md` if recent work or unfinished threads may matter.
4. Treat this repository as a persistent wiki workspace, not a one-shot chat scratchpad.
5. Prefer updating `wiki/` pages over leaving durable synthesis only in chat.

Startup ritual:

1. Read rules: `AGENTS.md`
2. Read map: `wiki/_meta/index.md`
3. Read recent activity: the newest relevant entries in `wiki/_meta/log.md`
4. When ingesting or validating truth, read the smallest relevant `intelligence/` and `warehouse/jsonl/` files needed for provenance

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

Conventions surface:

- Do not add a top-level `SCHEMA.md` for this repo.
- Defer `wiki/_meta/conventions.md` unless repeated drift remains after `AGENTS.md`, local skills, and lint already cover the issue.
- If a wiki-local conventions page is later added, it is editorial guidance only and remains subordinate to `AGENTS.md`.

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
- If one ingest, refactor, or cleanup would touch many broad existing pages, surface the scope before making a sweeping rewrite

## Workbench Boundary

If this repository gains a local GUI or operator workbench:

- Treat it as an optional interface, not a new source of truth.
- Keep the planned frontend under `apps/workbench/`.
- Keep the planned Python adapter under `scripts/workbench_api.py`.
- Let the frontend read repo state through explicit adapter contracts instead of direct filesystem ownership assumptions such as `vault/*`.
- Do not let browser code hold model API keys or other model secrets.
- Do not let the browser mutate `raw/` or `warehouse/jsonl/` directly.
- If helper-model config is introduced, load it on the backend only.
- If `wikiconfig.json` is used, treat it as a repo-root input file only, not as browser-owned config and not as a parent-crawled workspace setting.
- Helper-model outputs must remain draft-only until a backend-gated save or review path explicitly accepts them.
- Keep graph views read-only and clearly subordinate to canonical truth.
- Prefer dashboard, page, source, warehouse, and doctor surfaces before any graph-first workflow.

## Human Collaboration

Default assumption:

- The human wants the wiki to compound over time
- The agent should leave behind clean artifacts, not just temporary chat output

If unsure whether something belongs in the wiki, prefer asking:
`Should I save this as a wiki page?`
