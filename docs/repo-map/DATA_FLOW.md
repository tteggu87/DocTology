---
status: Active
source_of_truth: false
last_updated: 2026-09-05
superseded_by: N/A
---

# Data flow

`source skill directories -> manage_skills install -> target skill root`

The installer copies whole skill trees. A downstream bootstrap may then create a wiki repository, and that repository owns its Markdown and optional derived SQLite state. No downstream corpus flows back into DocTology.

For certified LLM Wiki ingest, the loop owns the executable path:

`target raw/wiki -> llm-wiki-loop runtime --repo-root -> run/batch/receipt state + canonical wiki changes`

Multi-source certification uses one publish boundary:

`source runs through semantic plan -> state-only drafts -> one writer apply -> current question receipts -> state-only batch seal -> certification`

The seal writes no wiki Markdown. It binds every source run and the final
certificate to the same writer result and reuses one retrieval refresh.

No procedure, batch, or pipeline executable is copied into the target vault.

For Repo Docs retrieval the downstream flow is:

`Markdown -> Python atomic rebuild -> disposable SQLite -> Python or native read adapter -> candidate Markdown paths -> canonical file verification`

`status` reads file stats, `doctor` reads content and verifies structure, while
search and traversal do neither freshness operation on their hot path.

For generated LLM Wiki raw retrieval the downstream flow is:

`raw/**/*.md -> incremental heading/chunk FTS + heading tree -> state/raw_index.sqlite -> candidate offsets or optional structure context -> reopen canonical raw bytes`

Raw and wiki indexes publish and age independently. Raw has no vector or blended
ranking lane; stat status and exact doctor remain separate from unchecked search.
Structure navigation checks the current checksum and returns no structure or
content when stale; direct Markdown reading remains available.

The optional composition is one-way:

`wiki lexical search -> hit: wiki lane | miss + --raw-fallback: separate raw lane`

An absent raw index does not block the wiki result.

Optional local dashboard has separate read and write paths:

`chat + bounded history -> authenticated loopback ready handshake -> isolated Pi RPC + wiki_list/wiki_search/wiki_read/wiki_links -> actual-read citation subset -> browser history + graph highlighting`

`reference click + expected root + read hash -> approved current document inventory -> matching Markdown body + verified wiki/raw links`

The chat extension is read-only: it has no shell, write, network, or equivalent
terminal capability. Generic overviews start from inventory. Actual actions,
calls, read count, bounded trace, truncation, and budget pressure are visible,
but not model reasoning. Discovery is neither a read nor proof, and citations
are not semantic certification.

`wiki-work request -> localhost adapter -> Pi RPC -> loop-owned skill -> target raw/wiki/state`

`opt-in watched Markdown -> stable in-place source or immutable external snapshot -> sequential queue`

`browser conversation -> exact preview -> explicit approval -> unverified immutable raw -> sequential queue`

`authorized queue item -> shared writer exclusion -> existing full loop -> current gate-derived status`

Queue pages are bounded projections. Interruptions require explicit retry, and
stale or restored gates update the displayed result without inventing a verifier.

`existing runs + receipts + batch status + wiki links -> derived kanban/graph`

Pi activity is displayed separately from gate completion. Process records and
Pi sessions live in target `state/dashboard_jobs/`; the dashboard serves no
public endpoint and does not copy target content into this repository.
