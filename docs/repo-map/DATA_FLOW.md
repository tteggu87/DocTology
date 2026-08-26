---
status: Active
source_of_truth: false
last_updated: 2026-08-26
superseded_by: N/A
---

# Data flow

`source skill directories -> manage_skills install -> target skill root`

The installer copies whole skill trees. A downstream bootstrap may then create a wiki repository, and that repository owns its Markdown and optional derived SQLite state. No downstream corpus flows back into DocTology.

For Repo Docs retrieval the downstream flow is:

`Markdown -> Python atomic rebuild -> disposable SQLite -> Python or native read adapter -> candidate Markdown paths -> canonical file verification`

`status` reads file stats, `doctor` reads content and verifies structure, while
search and traversal do neither freshness operation on their hot path.

For generated LLM Wiki raw retrieval the downstream flow is:

`raw/**/*.md -> incremental heading/chunk FTS -> state/raw_index.sqlite -> raw candidate offsets -> reopen canonical raw bytes`

Raw and wiki indexes publish and age independently. Raw has no vector or blended
ranking lane; stat status and exact doctor remain separate from unchecked search.
