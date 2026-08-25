---
status: Active
source_of_truth: true
last_updated: 2026-08-25
superseded_by: N/A
---

# Layer boundaries

- **Product source:** the three `.agents/skills/*` directories.
- **Distribution adapter:** `scripts/manage_skills.py`; no skill logic lives here.
- **Verification:** `tests/` and CI.
- **Repository truth:** `AGENTS.md`, `docs/`, and minimal `intelligence/` contracts.
- **Derived memory:** `wiki/`; useful for resumption, never runtime authority.
- **Downstream state:** files created in target repositories, including optional SQLite indexes. DocTology does not own that state after installation.
