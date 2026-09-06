---
status: Active
source_of_truth: true
last_updated: 2026-09-06
superseded_by: N/A
---

# Layer boundaries

- **Studio application runtime:** `runtime/`; composes the localhost service and the loop-gate adapter.
- **Studio UI:** `dashboard/`; static UI assets only.
- **Reusable product source:** the three `.agents/skills/*` directories.
- **Loop gates:** `llm-wiki-loop` owns reusable procedure, coverage, batch, receipt, seal, and certification gates, not the Studio application.
- **Distribution adapter:** `scripts/manage_skills.py`; validates and installs only the three skills.
- **Verification:** `tests/`, with Studio JavaScript evaluations under `tests/dashboard/`.
- **Repository truth:** `AGENTS.md`, `docs/`, and minimal `intelligence/` contracts.
- **Derived memory:** `wiki/`; useful for resumption, never runtime authority.
- **Downstream state:** files created in target repositories, including optional SQLite indexes. DocTology does not own that state after installation.
- **Derived Repo Docs search:** stat status, exact doctor, document-deduplicated token/trigram FTS, and bounded Markdown-link traversal. Native SQLite wrappers are optional read adapters; returned candidates remain unchecked until their canonical Markdown is opened.

The Studio preserves the existing security, chat, writer, and gate contracts.
Its downstream process history is operational state, never a second coverage or
workflow ledger. The migration in [ADR-0004](adr/ADR-0004-studio-runtime-separation.md)
is implemented; see [migration verification](evidence/2026-09-06-studio-runtime-separation.md).
