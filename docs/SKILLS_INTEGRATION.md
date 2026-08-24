# Skills Integration

Updated: 2026-05-08

## Repo-local source of truth

For this repository, `AGENTS.md` is the primary working contract.

That means:

- the wiki maintenance workflow lives here, not only in reusable skills
- future agents should read `AGENTS.md`, then `wiki/_meta/index.md`, then recent `wiki/_meta/log.md`
- durable repo behavior should be encoded in this repository before depending on external skill memory

## Relevant reusable skills

- `.agents/skills/repo-docs-intelligence-bootstrap`
  - use for repository-level docs and intelligence alignment
- `.agents/skills/llm-wiki-loop`
  - use for source planning, ontology-aware synthesis, wiki growth, repair, and source/corpus certification
- `.agents/skills/ontology-pipeline-operator`
  - use when refreshing existing ontology artifacts and repeated maintenance flows

The repo-local skillset lives under `.agents/skills/`. Installed copies under
`~/.codex/skills` are local conveniences only; they are not the canonical
checked-in skill surface for this repository.

## Current repo/runtime fit

- `scripts/llm_wiki.py` is support tooling but still a real local entrypoint
- `scripts/llm_wiki.py ingest` is source registration only, not full ontology-backed ingest by itself
- `scripts/llm_full_ingest.py --apply` is the current configured-LLM full growth path
- `scripts/incremental_ingest.py` is the current repeated-export ingest path
- `scripts/workbench_api.py` is the compatibility shell for the local workbench adapter
- reusable skills should align to these live paths instead of inventing new ones

## Closed wiki loop contract

When the wiki loop processes a new source for this repository, it should close the
artifact lifecycle instead of stopping at registration:

1. register or update the source page
2. append applicable proposed JSONL records
3. update affected human-facing wiki pages
4. refresh meta pages
5. run structural validation
6. report proposed JSONL emitted/appended/skipped_existing counts plus changed wiki/meta artifacts

The skill may use agent or helper-model judgment for affected pages, claims,
relations, contradictions, and uncertainty. It must not turn filename keywords,
token shape, retrieval hits, graph projection, or YAML contracts into semantic
truth.

Automatic source processing must not promote proposed records to accepted
canonical truth. Accepted claim/entity/evidence promotion requires a separate
review gate with explicit metadata.

The former `lightweight-ontology-core` and `lg-ontology` packages are preserved
under `archive/skills/` and are no longer active workflow choices. Minimum
ontology lifecycle and integrity rules now live inside `llm-wiki-loop`; graph
projection is outside the default product flow.

## What skills should not do here

- they should not rewrite the truth hierarchy
- they should not promote graph projection to canonical truth
- they should not treat the browser workbench as the primary ownership surface
- they should not create a second manifest/runtime system parallel to the existing Python paths
- they should not treat `intelligence/` YAML as a second semantic wiki
- they should not report source-registration-only work as completed ontology-backed ingest
