---
status: Active
source_of_truth: false
last_updated: 2026-08-26
superseded_by: N/A
---

# High-impact symbols

- `scripts.manage_skills.SKILLS`: fixes the public inventory.
- `scripts.manage_skills.validate_source`: rejects missing or extra active skills.
- `scripts.manage_skills.install`: synchronizes each complete skill tree.
- `bootstrap_llm_wiki.scaffold`: creates downstream wiki workspaces.
- `wiki_workflow.start_run`: freezes `full` coverage by default or an explicit
  user-requested `summary` mode into the source run.
- `wiki_workflow.validate_full_coverage_receipt`: binds full final review to one
  applied raw-source receipt with balanced accounting and no deferred units.
- `raw_retrieval.rebuild`: transactionally updates only added, changed, or
  removed `raw/**/*.md` documents in a separate lexical index.
- `raw_retrieval.search`: queries raw FTS, then reopens the canonical source byte
  range and labels changed spans stale instead of returning stored text as truth.
- `raw_retrieval.doctor`: hashes raw documents and reconstructs chunk/FTS rows
  for exact derived-state verification.
- `reindex_sqlite_operational.rebuild`: streams generated-wiki page bodies,
  retains only page metadata, and checks exact source content before atomic
  publication.
- `reindex_sqlite_operational.carry_forward_embeddings`: preserves only valid
  current vectors from the prior disposable index without materializing its BLOBs.
- `wiki_retrieval.open_discovery_index`: opens one schema-compatible connection
  for unchecked lexical and wikilink candidate discovery.
- `wiki_retrieval.open_current_index`: adds stat readiness for semantic-only
  operations that require current Markdown-bound vectors.
- `wiki_retrieval.persist_embeddings`: batches missing ONNX embeddings while
  retaining a single valid vector cohort.
- `repo_docs_retrieval.rebuild`: creates and atomically publishes derived Repo Docs state.
- `repo_docs_retrieval.health`: owns shallow stat and deep exact verification.
- `repo_docs_retrieval.search_results`: enforces one best chunk per document.
- `repo_docs_retrieval.require_ready`: opens one schema-compatible query connection without source hashing.

This is a focused impact map, not a complete generated call graph.
