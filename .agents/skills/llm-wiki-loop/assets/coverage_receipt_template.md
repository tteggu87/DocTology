---
title: "Ingest coverage for {{title}}"
type: meta
status: applied
coverage_mode: full
raw_path: "{{raw_path}}"
source_sha256: "{{source_sha256}}"
source_units_total: 0
source_units_projected: 0
source_units_omitted: 0
source_units_deferred: 0
---

# Ingest Coverage: {{title}}

- Raw path: `{{raw_path}}`

Split the source by Markdown heading. When a section is too large or the source
has no useful headings, use deterministic bounded chunks. Every unit must occur
exactly once below.

## Projected Units

- `unit-id` -> `wiki/path.md#section` - preserved information

## Omitted Units

- None. If non-zero, list every unit and a concrete boilerplate/duplicate reason.

## Deferred Units

- None. A full run cannot finish ready while this section is non-empty.
