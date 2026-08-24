<p align="center">
  <img src="apps/workbench/public/doctology-logo.jpeg" alt="DocTology logo" width="460">
</p>

# DocTology

[English](README.md) | [한국어](README.ko.md)

DocTology is an **Obsidian-first LLM Wiki runtime and reusable skill pack**.

The core contract is intentionally simple:

- the human curates sources and asks questions
- the agent maintains the wiki
- scripts preserve source identity, indexes, and provenance
- ontology and graph layers are optional support surfaces, not the product face

DocTology is for building a knowledge system where an LLM can read a durable wiki, follow links, inspect source-backed evidence, and keep improving the knowledge base over time.

## What this is

DocTology is not just a notes repo, not just an ontology toolkit, and not just a graph experiment.

It is a way to build a repository where:

- **`raw/`** stores immutable source material
- **`warehouse/jsonl/`** stores canonical structured truth when ontology-backed ingest is useful
- **`wiki/`** stores human-readable synthesis that agents maintain with Obsidian links
- **`AGENTS.md`** is the repo-local operating contract for future agents
- **`intelligence/` YAML** is a thin contract/hint layer below AGENTS, wiki, and source evidence

The wiki is the primary reading and reasoning surface. YAML is not a second wiki and should not contain semantic conclusions.

## Who this is for

Use DocTology if you want:

- a readable knowledge base, not just a vector index or raw context dump
- an LLM-maintained wiki that can grow from repeated source ingest and questions
- stronger provenance than plain notes, without forcing heavy ontology or graph infrastructure on day one
- reusable skills for bootstrapping, ingesting, ontology maintenance, and operator workflows

![DocTology workbench question workspace](assets/readme/doctology-workbench-question-workspace.jpg)

_DocTology workbench question workspace — an optional read-and-review surface for the generated wiki, previews, and source/graph hints._

Workbench status: it is an optional review surface, not the source of truth or the primary LLM reasoning layer. Durable synthesis belongs in the wiki under the repo-local `AGENTS.md` contract.

![Reference example: knowledge growing into a wiki](assets/readme/doctology-reference-obsidian-notes-forming-a-wiki.jpg)

_Reference example — previously separate Obsidian notes forming visible structure, links, and neighborhoods._

## Default path

If you are unsure where to start, use the default DocTology path:

1. bootstrap a wiki-first workspace
2. put sources into `raw/inbox/`
3. ingest sources into source pages, citation anchors, and optional ontology JSONL
4. let the agent maintain the wiki under `AGENTS.md`
5. save durable answers into `wiki/analyses/`
6. add ontology, graph, or operator workflows only when provenance, contradiction handling, or repeated maintenance needs them

That default path is the product promise:

- readable wiki first
- source-backed evidence second
- ontology-backed verification when useful
- graph/operator complexity only when it earns its keep

## Which path am I on?

Use this practical chooser:

- Want to create a new wiki?
  - Use `llm-wiki-bootstrap`
- Want to add sources, grow the wiki, validate ontology, or certify a corpus?
  - Use `llm-wiki-loop`
- Want to organize codebase docs and AGENTS memory?
  - Use `repo-docs-intelligence-bootstrap`
- Want to refresh or validate existing ontology/wiki outputs?
  - Use `ontology-pipeline-operator`

Most users should begin with:

1. `llm-wiki-bootstrap`
2. repeated `llm-wiki-loop`

Ontology integrity is part of the wiki loop. The former standalone ontology and
graph skills are archived rather than exposed as parallel user workflows.

## If you are already operating a DocTology repo

1. Read `AGENTS.md` first.
2. Put new sources into `raw/inbox/`.
3. Run `python scripts/llm_full_ingest.py raw/inbox/source.md --apply` when configured helper LLM ingest is available.
4. Use `llm-wiki-loop` when the source needs ontology-aware synthesis, review, repair, or certification.
5. Review `git diff`, then run lint/status checks.
6. Use `ontology-pipeline-operator` when existing outputs need refresh or validation.

For procedure-gated ingest, start a source run with `scripts/wiki_workflow.py`. For large-source work, use `scripts/wiki_batch.py` to freeze the manifest, stage worker drafts, apply through one writer, run `scripts/pipeline_check.py --strict --batch`, record representative-question receipts, and certify the corpus fingerprint. Missing or stale stages are not completion.

`scripts/llm_wiki.py ingest` is registration only. `scripts/llm_full_ingest.py
--apply` is the minimal configured-LLM growth loop: `raw -> register -> source
page -> affected wiki pages -> proposed JSONL -> meta refresh -> ingest report`.
Automatic apply must not modify `raw/`, create accepted truth, delete content,
rename pages, merge pages, or auto-commit.

For automated graph ingest, use `scripts/wiki_growth_graph.py`. That runtime
requires real LangGraph and a configured ingest LLM, and fails fast instead of
falling back to deterministic semantic shortcuts. The agent-operated wiki
workflow remains available outside that strict graph runtime.

## Choose your starting path first

### 1) Do you want to start with an LLM Wiki?

Start with `llm-wiki-bootstrap`.

The flow is simple:

- run the wiki bootstrap
- put documents into the generated `raw/inbox/`
- run `llm-wiki-loop` to grow source pages, ontology-backed provenance, and affected wiki pages through one gated workflow
- ask the agent to answer from the wiki map first, then relevant page bodies and source citations
- let durable answers update `wiki/analyses/` and, when appropriate, affected concept/entity/person/project pages

The first step is always **wiki-first**.

### 2) Do you want project-specific repo memory instead of a personal LLM Wiki?

Use `repo-docs-intelligence-bootstrap`.

This is better for:

- capturing the current state of a codebase
- creating repo-local project memory for agents
- aligning docs, AGENTS, manifests, and lightweight intelligence contracts

This is an alternative starting bootstrap, not something to blindly stack on top of the wiki bootstrap.

## Caution

**Use only one bootstrap to start.**

Multiple bootstraps can overwrite `AGENTS.md` and blur the operating rules.

Choose first:

- do you want to grow an LLM Wiki?
- or do you want repo-focused intelligence / project memory?

Both matter, but the first bootstrap should be one clear choice.

## Core skill paths

The canonical repo-local skillset lives under `.agents/skills/`. Installed copies under `~/.codex/skills` are local installs only.

- `.agents/skills/llm-wiki-bootstrap`
  - start an Obsidian-first LLM Wiki
- `.agents/skills/llm-wiki-loop`
  - grow and certify raw sources, canonical ontology, and human-facing wiki pages through one loop
- `.agents/skills/repo-docs-intelligence-bootstrap`
  - bootstrap project-specific memory / repo intelligence
- `.agents/skills/ontology-pipeline-operator`
  - refresh existing ontology/wiki artifacts and repeated maintenance flows

Retired standalone ontology and graph skill packages are preserved under
`archive/skills/`; they are not active user-facing skills.

## Operating model

The DocTology core model is intentionally small:

```text
raw source
  ↓
source page and optional ontology JSONL
  ↓
LLM-maintained wiki pages
  ↓
saved analyses and cross-links
  ↓
better future answers
```

Responsibilities:

- deterministic scripts may register sources, keep IDs stable, refresh indexes, and validate basic structure
- the LLM agent performs semantic synthesis by reading the wiki, source pages, and relevant ontology evidence
- humans review broad rewrites, sensitive accepted claims, contradictions, and major ontology changes
- the pipeline closes artifact coverage, not semantic judgment

This keeps the system close to a Karpathy-style LLM Wiki: the LLM reads a structured, linked knowledge base instead of receiving only top-k chunks.

## YAML contract layer

YAML is useful, but it is subordinate.

There are two separate priority axes.

Truth / provenance priority:

1. `raw/` source material
2. `warehouse/jsonl/` canonical structured truth when ontology-backed ingest exists
3. source-backed wiki pages and citations
4. derived graph/retrieval/workbench previews

Operating guidance priority:

1. repo-local `AGENTS.md`
2. `wiki/_meta/index.md` and recent `wiki/_meta/log.md`
3. `intelligence/` YAML contracts and hints

YAML may define vocabulary, dataset boundaries, profiles, and validation hints. It must not become a second semantic wiki or a deterministic reasoning engine.

## Helper LLMs

`wikiconfig.json` is a local-only configuration file. Use `wikiconfig.example.json` as the committed template.

Helper LLMs are optional accelerators for bounded tasks. If helper LLMs are disabled or absent, the surrounding chat agent can still perform semantic work directly by reading:

- `AGENTS.md`
- `wiki/_meta/index.md`
- relevant wiki pages
- source pages
- `warehouse/jsonl/` evidence when needed

In other words, helper LLMs should not replace the main agent-maintained wiki loop.

Semantic no-fallback principle: if the helper/configured LLM call fails, report the step as failed, partial, or pending. Do not replace it with deterministic fallback prose and call full ingest complete.

Probe local helper configuration before using it:

```bash
python scripts/helper_llm.py --root . --check-config
python scripts/helper_llm.py --root . --probe-chat
python scripts/helper_llm.py --root . --probe-embedding
```

For the simplest full growth loop, keep `scripts/llm_wiki.py ingest` as registration-only and use:

```bash
python scripts/llm_full_ingest.py raw/inbox/example.md --mode dry_run
python scripts/llm_full_ingest.py raw/inbox/example.md --apply
python scripts/wiki_growth_graph.py check --source raw/inbox/example.md
```

The strict LangGraph source-page runtime remains available for graph-runtime debugging:

```bash
python scripts/wiki_growth_graph.py ingest raw/inbox/example.md --mode draft
python scripts/wiki_growth_graph.py ingest raw/inbox/example.md --mode apply-source-page
```

`--apply` completes source pages, creates or appends affected wiki pages, writes
proposed JSONL records, refreshes index/log, and writes an ingest report.
Accepted-claim promotion remains intentionally review-gated.

When a later question requires raw/source fallback or wiki repair, record the
trace without adding semantic heuristics:

```bash
python scripts/llm_wiki.py answer-receipt "Question text" \
  --used-wiki wiki/_meta/index.md \
  --used-raw raw/inbox/example.md \
  --wiki-update wiki/analyses/example.md
```

Answer receipts are context receipts, not answer generators or page-selection
rules. The agent still decides what to read and what the answer means.

## About the reference runtime

The included local runtime is a reference implementation, not the whole product.

Useful entry points include:

- `scripts/llm_wiki.py` for source registration, answer receipts, indexing, linting, and status checks
- `scripts/helper_llm.py` for local `wikiconfig.json` probes and OpenAI-compatible helper calls
- `scripts/wiki_growth_graph.py` for strict LangGraph source-page growth runtime
- `scripts/pipeline_check.py` for pending-aware structural route checks
- `scripts/wiki_workflow.py` for fixed-stage source procedure completion and stale-review detection
- `scripts/wiki_batch.py` for immutable batch plans, one-writer apply, corpus fingerprints, and representative-question certification
- `scripts/llm_full_ingest.py` for configured-LLM full growth dry-run/apply
- `scripts/incremental_ingest.py` for repeated export-style ingest paths
- `scripts/workbench_api.py` as a compatibility shell for local workbench adapters
- `apps/workbench/` as an optional GUI/read-review surface

The main point of this repository is the operating pattern:

> build a readable source-backed wiki, let agents maintain it, and add ontology or graph machinery only when it improves provenance and reasoning quality.

## Appendix: Skill invocation rule

Skills are support tools. The center of DocTology remains:

- `AGENTS.md`
- `wiki/`
- `raw/`
- `warehouse/jsonl/`

When using a skill, keep the repo-local contract explicit:

```text
Use <skill-name>.
Follow the repo-local AGENTS.md.
Do not replace the wiki with YAML or graph outputs.
Keep wiki/ as the human-facing synthesis surface.
```

Example:

```text
Use llm-wiki-loop.
Follow the repo-local AGENTS.md.
Process sources from raw/inbox.
Update canonical JSONL and affected wiki pages when the selected profile supports them.
Run the source or batch gate and report the final completion posture.
```
