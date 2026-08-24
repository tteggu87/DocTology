# Archived DocTology Skills

These skill packages are preserved for history, recovery, and selective reuse.
They are intentionally outside `.agents/skills/` and are not active user-facing
skills.

Archived on 2026-08-25:

- `lightweight-ontology-core`: its minimum canonical ontology and validation
  contract moved into `llm-wiki-loop`; its scripts, fixtures, and templates are
  retained here for recovery or future extraction into a shared runtime package.
- `lg-ontology`: its graph projection, comparison scripts, packs, fixtures, and
  references are retained here. Graph projection is no longer part of the
  default LLM Wiki product flow.

Active replacement:

- `.agents/skills/llm-wiki-loop/`

Do not copy an archived skill back into the active skill directory without a
new product need, current tests, and an explicit review of overlap with the wiki
loop and bootstrap runtime.
