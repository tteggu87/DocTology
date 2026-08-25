---
status: Active
source_of_truth: true
last_updated: 2026-08-25
superseded_by: N/A
---

# Current state

DocTology distributes exactly three skills: `llm-wiki-bootstrap`, `llm-wiki-loop`, and `repo-docs-intelligence-bootstrap`.

The canonical management entrypoint is `python3 scripts/manage_skills.py`. `check` validates the source inventory; `install` synchronizes it to a target skill root. Skill-owned scripts remain inside each skill and are copied with the skill.

The repository has no active ontology operator, root ontology pipeline, workbench, canonical corpus, or tracked archive. Optional SQLite in generated wiki vaults is derived retrieval state owned by `llm-wiki-bootstrap`.

Verification uses `python3 -m unittest discover -s tests` and the validator bundled in `repo-docs-intelligence-bootstrap`.
