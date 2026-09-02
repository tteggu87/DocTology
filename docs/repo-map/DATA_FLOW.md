---
status: Active
source_of_truth: false
last_updated: 2026-09-02
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

For generated LLM Wiki wiki retrieval the derived routing flow is:

`wiki/**/*.md -> fenced-code-aware heading sections -> 8 KiB per-section chunks -> wiki-heading-index-v9 structure nodes + chunk node_id -> lexical/semantic candidate -> reopen canonical Markdown`

Small headed pages follow the same section path as large pages. Document roots
own headingless content and legitimate preambles; matching heading nodes own
section chunks. The derived tree and chunk ownership improve routing only and do
not replace Markdown or add a workflow ledger.
