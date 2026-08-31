---
status: Active
source_of_truth: false
last_updated: 2026-09-01
superseded_by: N/A
---

# Modules

- `.agents/skills/llm-wiki-bootstrap/`: vault scaffolding, optional
  page-streamed wiki SQLite retrieval, separate incremental raw lexical
  retrieval with explicit wiki-miss fallback, deterministic raw heading-tree
  navigation, and bounded wiki ONNX vector refresh. It routes certified ingest
  to the loop rather than copying gates.
- `.agents/skills/llm-wiki-loop/`: agent-operated repeated wiki growth contract,
  self-contained procedure/batch/structural runtime, receipt assets, and a
  `--repo-root` entrypoint. Ordinary ingest compiles to coverage-preserving full
  mode and explicit summary requests remain opt-in. Derived heading structure
  may guide planning but never changes the coverage receipt boundary.
- `.agents/skills/repo-docs-intelligence-bootstrap/`: templates, validator,
  portable docs-index lifecycle, optional native SQLite readers, shared SQL,
  and dogfood tooling.
- `scripts/manage_skills.py`: inventory validation and installation only.
- `tests/`: product and distribution regression coverage.
