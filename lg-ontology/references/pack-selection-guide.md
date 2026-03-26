# Pack Selection Guide

Use this guide to pick between `repo-docs-intelligence-bootstrap`, `lightweight-ontology-core`, and `lg-ontology`, and to choose the right starter pack when one exists.

## Tool Choice

- `repo-docs-intelligence-bootstrap`
  - Use when the folder first needs structure, source-of-truth alignment, glossary/manifests cleanup, or docs refresh.
- `lightweight-ontology-core`
  - Use when you want the canonical ontology only: entities, claims, evidence, segments, derived edges, and DuckDB mirror.
- `lg-ontology`
  - Use when you want canonical ontology plus graph projection, graph-style inspection, or baseline-vs-graph comparison.

## Recommended Prompt Shapes

- Structure first, then ontology:
  - `repo-docs -> core`
  - `repo-docs -> lg`
- Ontology only:
  - `core`
  - `lg`

## Copy-Paste Prompt Examples

- `[$repo-docs-intelligence-bootstrap](C:\Users\tteggu\.agents\skills\repo-docs-intelligence-bootstrap\SKILL.md) 로 구조화해주고 [$lg-ontology](C:\Users\tteggu\.codex\skills\lg-ontology\SKILL.md) 로 온톨로지화와 graph projection까지 해줘.`
- `[$lg-ontology](C:\Users\tteggu\.codex\skills\lg-ontology\SKILL.md) 를 사용하여 [<대상파일또는폴더>](<경로>) 온톨로지화와 graph projection까지 해줘.`

## Starter Packs

Starter packs are thin template helpers that reduce schema-selection friction.
Treat them as starter template sets, not blind merge overlays.

Current roadmap:

1. `work-docs`
   - Best for company email txt, reports, meeting-ish notes, and internal work documents.
   - Goal: action, decision, evidence, owner, and due-date oriented extraction.
2. `education`
   - Best for lecture notes, course materials, curriculum docs, and learning resources.
3. `finance`
   - Best for investment notes, company memos, thesis/risk tracking, and market research summaries.
   - Keep the first version narrow: thesis, risk, revision, and high-level causal claims only.

## Boundary Rules

- Do not treat starter packs as canonical truth themselves.
- Do not treat graph projection as canonical truth.
- Do not absorb `repo-docs-intelligence-bootstrap` behavior into `lg-ontology`.
- Keep `lightweight-ontology-core` as the minimal canonical ontology baseline.
- Choose either the base generic templates or a starter pack as your initial template set.
- Do not blindly merge pack relation files into the base generic relation file when keys overlap.
- If you intentionally combine templates, rename overlapping relation keys first and document the choice.

## Naming Guidance

- Prefer `work-docs` over broader names like `comms-docs` when the pack covers company email/report/meeting-like documents.
- Add a new pack only when prompt friction is repeated and the existing packs do not absorb the use case cleanly.
