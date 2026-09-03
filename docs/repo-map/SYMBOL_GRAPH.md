---
status: Active
source_of_truth: false
last_updated: 2026-09-01
superseded_by: N/A
---

# High-impact symbols

- `scripts.manage_skills.SKILLS`: fixes the public inventory.
- `scripts.manage_skills.validate_source`: rejects missing or extra active skills.
- `scripts.manage_skills.install`: synchronizes each complete skill tree.
- `bootstrap_llm_wiki.scaffold`: creates downstream wiki workspaces.
- `wiki_loop.preflight`: validates a target wiki-only repository and reports
  legacy local gate files without installing or executing them.
- `wiki_loop.dispatch`: runs the loop-owned procedure, batch, or structural
  checker against the exact `--repo-root`, rejects nested root overrides, and
  relies on non-abbreviating child parsers so shortened flags cannot redirect
  the target after preflight.
- `wiki_loop.show_help`: forwards public lane and nested-command help to the
  skill-local parsers with public command names and without preflighting or
  touching a target repository.
- `wiki_workflow.start_run`: freezes `full` coverage by default or an explicit
  user-requested `summary` mode into the source run.
- `wiki_workflow.validate_full_coverage_receipt`: binds full final review to one
  applied raw-source receipt with balanced accounting and no deferred units.
- `wiki_workflow.prepare_batch_completion`: prepares the post-apply procedure and
  review stages for one preplanned source without mutating canonical wiki files.
- `wiki_batch.seal_batch`: validates one writer result, records a state-only
  batch review, completes every linked source run with one shared retrieval
  refresh, and immediately certifies the unchanged corpus fingerprint.
- `wiki_batch.batch_next_action`: maps current batch freshness and manifest state
  to one read-only operator hint without executing a transition.
- `wiki_batch.list_batches`: discovers output-bounded manifest summaries without
  corpus hashing or symlink traversal and routes valid results to exact batch
  status.
- `raw_retrieval.rebuild`: transactionally updates added, changed, or removed
  `raw/**/*.md` documents by stat identity; `--exact` also repairs checksum drift
  when file size and mtime were preserved.
- `reindex_sqlite_operational.structure_nodes_for_page`: deterministically maps
  fenced-code-aware Markdown headings to document, ancestor, and subtree ranges.
- `raw_retrieval.search`: queries raw FTS, then reopens the canonical source byte
  range and labels changed spans stale instead of returning stored text as truth.
- `raw_retrieval.tree`, `raw_retrieval.ancestors`, and `raw_retrieval.subtree`:
  expose checksum-checked optional structure context without implicit rebuilds.
- `raw_retrieval.doctor`: hashes raw documents and reconstructs chunk/FTS rows
  for exact derived-state verification.
- `wiki_retrieval.raw_fallback_lane`: lazily loads optional raw retrieval after
  an empty wiki lexical result and returns a separate candidate/unavailable lane.
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
