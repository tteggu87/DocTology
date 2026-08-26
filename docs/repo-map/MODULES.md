---
status: Active
source_of_truth: false
last_updated: 2026-08-26
superseded_by: N/A
---

# Modules

- `.agents/skills/llm-wiki-bootstrap/`: vault scaffolding, optional
  page-streamed wiki SQLite retrieval, separate incremental raw lexical
  retrieval, bounded wiki ONNX vector refresh, and copied gate runtimes,
  including the full-coverage receipt gate.
- `.agents/skills/llm-wiki-loop/`: agent-operated repeated wiki growth contract;
  ordinary ingest compiles to coverage-preserving full mode and explicit summary
  requests remain opt-in.
- `.agents/skills/repo-docs-intelligence-bootstrap/`: templates, validator,
  portable docs-index lifecycle, optional native SQLite readers, shared SQL,
  and dogfood tooling.
- `scripts/manage_skills.py`: inventory validation and installation only.
- `tests/`: product and distribution regression coverage.
