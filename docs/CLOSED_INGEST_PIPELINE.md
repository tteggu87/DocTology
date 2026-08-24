# Closed Ingest Pipeline

Updated: 2026-08-25

## Purpose

The closed ingest contract exists to prevent source processing from stopping at
registration.

`python3 scripts/llm_wiki.py ingest ...` is a **source registration** tool. It
creates or updates the source page stub and meta surfaces, but it is not the
whole ontology-backed ingest loop.

The user-facing entrypoint for the complete workflow is `llm-wiki-loop`. It
selects the repository's available execution lane and drives the existing
procedure and batch runtime; it does not depend on a second ontology skill.

A full ingest should close the artifact lifecycle:

1. register the source identity
2. append proposed JSONL records when ontology-backed ingest applies
3. project source-backed updates into the human-facing wiki
4. refresh meta pages
5. run profile-aware ontology integrity and structural validation
6. bind final review to the latest mutation state
7. report what changed, what was skipped, and what remains uncertain

The current configured automation path is:

```bash
python3 scripts/llm_full_ingest.py raw/inbox/source.md --apply
```

This path may write source pages, affected wiki pages, proposed JSONL records,
meta pages, and ingest reports. It must not modify `raw/`, create accepted
truth, delete content, rename pages, merge pages, or auto-commit.
Proposed JSONL records receive stable artifact IDs and content hashes so
re-running the same source-backed draft skips existing proposals instead of
duplicating them.

## Lifecycle

### 1. Source registration

- read source material from `raw/inbox/`, `raw/processed/`, or `raw/notes/`
- keep `raw/` immutable
- create or update the matching `wiki/sources/` page
- append `wiki/_meta/log.md`
- refresh `wiki/_meta/index.md`

### 2. Proposed JSONL append

When ontology-backed ingest applies automatically, append proposed records under
`warehouse/jsonl/` before broad wiki synthesis.

Typical targets include:

- `proposed_entities.jsonl`
- `proposed_claims.jsonl`
- `proposed_evidence.jsonl`
- optional `proposed_relations.jsonl`

Accepted/canonical registries remain review-gated. A later promotion workflow
may update canonical files such as `entities.jsonl`, `claims.jsonl`,
`claim_evidence.jsonl`, `segments.jsonl`, or `derived_edges.jsonl`, but the
automatic full ingest runner must not create accepted truth by itself.

Not every source requires every proposed registry. The report must distinguish:

- emitted
- appended
- skipped as already existing

### 3. Wiki projection

After source registration and applicable proposed updates, update the
human-facing wiki:

- `wiki/sources/`
- affected `wiki/concepts/`
- affected `wiki/entities/`
- affected `wiki/people/`
- affected `wiki/projects/`
- affected `wiki/timelines/`
- durable analyses under `wiki/analyses/` when useful

The wiki remains the human reading and synthesis surface. It is not a dump of
raw chunks or graph edges.

### 4. Meta refresh

Refresh operational surfaces after meaningful changes:

- `wiki/_meta/index.md`
- `wiki/_meta/log.md`

Optional review pages may be refreshed when the repository maintains them, but
they are still derived review aids rather than canonical truth.

### 5. Structural validation

Validation may check:

- JSONL parseability
- required fields
- duplicate IDs
- source and segment references
- broken wikilinks
- orphan pages
- stale pages
- index/log freshness
- derived-edge references to reviewed claim status

Validation must not claim to determine semantic truth.

## Semantic judgment boundary

The closed pipeline is a lifecycle contract, not a heuristic semantic router.

Allowed deterministic work:

- file discovery
- ID generation
- source registration
- line or segment reference bookkeeping
- JSONL syntax and required-field checks
- link integrity checks
- meta index/log refresh
- structural completion reporting

Forbidden deterministic work:

- filename keyword routing as semantic judgment
- token-shape routing as semantic judgment
- automatic page selection by regex as if it were understanding
- automatic claim acceptance without review metadata
- graph projection as canonical truth
- retrieval result as truth
- browser direct mutation of `raw/` or broad `warehouse/jsonl/` registries

The agent or a configured helper model may help decide affected pages, claims,
entities, contradictions, and open questions. Those judgments must remain
grounded in source evidence and repository rules.

## Configured full ingest runtime

`scripts/llm_full_ingest.py` is the minimal configured-LLM full growth runtime.
Its public modes are `dry_run` and `--apply`. `--apply` closes the growth loop
by completing the source page, creating or appending affected wiki pages,
appending proposed JSONL records, refreshing index/log, and writing an ingest
report.

Invalid semantic judgment output must fail before being reported as completed.
Affected page updates must use explicit allowed wiki paths and `create` or
`append` actions only.

## Automated graph ingest runtime

`scripts/wiki_growth_graph.py` is the strict automated graph ingest runtime for
source-page-first growth. In ingest modes it requires real LangGraph and a
configured ingest LLM. If either is unavailable, the graph runtime fails fast and
does not replace semantic work with deterministic fallback output.

This runtime does not remove the agent-operated semantic path. An agent may
still perform wiki growth directly by reading `AGENTS.md`, the wiki map, source
pages, and ontology evidence. That path is explicit agent work, not an automatic
fallback inside the graph runtime.

## Semantic no-fallback rule

If source-page synthesis, affected-page selection, claim extraction,
contradiction handling, or wiki projection requires agent or configured LLM
judgment, then missing, failed, timed-out, or invalid judgment output must be
reported as `failed`, `partial`, or `pending`.

Do not replace failed semantic judgment with deterministic fallback prose and
call the step complete. The following are allowed as diagnostics or structural
aids only:

- lexical previews
- filename or keyword summaries
- retrieval results
- graph projections
- YAML/manifest hints
- structural validation results

Those aids may explain what remains pending, but they must not become semantic
success, accepted claims, or automatic wiki projection.

Transport fallback is different: retrying the same configured LLM request
through another HTTP transport is allowed. Changing the semantic owner from
agent/configured LLM judgment to deterministic script output is not allowed.

## Claim review boundary

`warehouse/jsonl/claims.jsonl` may contain draft or pending claims. A claim
should be treated as accepted only when review metadata and supporting evidence
make that state explicit.

Derived edges may be materialized from canonical records, but the projection is
not the authority. When a projection conflicts with canonical JSONL, canonical
JSONL wins.

For ontology-capable profiles, `pipeline_check.py` must emit a passing
`ontology_integrity` check. Malformed registries, broken references, invalid
claim lifecycle pairs, accepted claims without human review/evidence, or
derived edges sourced from non-accepted claims block completion. Wiki-only
profiles report this check as `not_applicable`.

## Reporting contract

A closed ingest report should state:

- source registered
- proposed JSONL records emitted, appended, and skipped_existing
- wiki pages created or updated
- meta pages refreshed
- validation run and result
- unresolved uncertainties
- follow-up actions

Do not report registration-only work as a completed ontology-backed ingest.

## Relationship to stricter profiles

This contract is intentionally smaller than a strict LLM-first proposal system.
It does not require:

- a manifest-driven executor
- helper-model-only semantic paths
- automatic rejection of local agent processing

It does require that deterministic scripts stay structural and that semantic
judgment is not smuggled into filename, keyword, token, YAML, graph, retrieval,
or workbench shortcuts.
