---
status: Active
source_of_truth: true
last_updated: 2026-09-05
superseded_by: N/A
---

# Layer boundaries

- **Product source:** the three `.agents/skills/*` directories.
- **Distribution adapter:** `scripts/manage_skills.py`; no skill logic lives here.
- **Verification:** `tests/` and CI.
- **Repository truth:** `AGENTS.md`, `docs/`, and minimal `intelligence/` contracts.
- **Derived memory:** `wiki/`; useful for resumption, never runtime authority.
- **Downstream state:** files created in target repositories, including optional SQLite indexes. DocTology does not own that state after installation.
- **Derived Repo Docs search:** stat status, exact doctor, document-deduplicated
  token/trigram FTS, and bounded Markdown-link traversal. Native SQLite wrappers
  are optional read adapters; returned candidates remain unchecked until their
  canonical Markdown is opened.

- **Optional loop UI:** `llm-wiki-loop/dashboard/` and its sibling launcher adapt
  existing wiki state into local views and Pi task controls. Their downstream
  process history is operational state, never a second coverage or workflow ledger.
