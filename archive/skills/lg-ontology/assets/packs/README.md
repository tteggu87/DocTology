# Starter Pack Layout

Starter packs live under `assets/packs/<pack-name>/`.

Each starter pack should begin with only these thin template files:

- `relations.template.yaml`
- `document_types.template.yaml`
- `inference.template.yaml`

Packs are allowed to narrow setup friction for common document families.
Packs are not allowed to replace the generic `lg-ontology` operating model or absorb `repo-docs-intelligence-bootstrap`.

Use a starter pack as an initial template set.
Do not blindly merge a pack's relation file into the base generic relation file when keys overlap.
If you intentionally combine them, rename the overlapping keys first and document the merged meaning explicitly.

Current roadmap order:

1. `work-docs`
2. `education`
3. `finance`

If a pack starts needing deep extraction rules, large eval coverage, or domain-specific lifecycle logic, split it into a separate adapter skill instead of expanding `lg-ontology` indefinitely.
