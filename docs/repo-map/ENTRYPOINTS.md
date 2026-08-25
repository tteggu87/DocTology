---
status: Active
source_of_truth: false
last_updated: 2026-08-25
superseded_by: N/A
---

# Entrypoints

- Canonical repository command: `python3 scripts/manage_skills.py check|install`.
- Skill entrypoints: each retained `.agents/skills/*/SKILL.md` and its documented sibling scripts.
- Verification: `python3 -m unittest discover -s tests` and the bundled Repo Docs validator.

There are no secondary launchers or active compatibility wrappers.
