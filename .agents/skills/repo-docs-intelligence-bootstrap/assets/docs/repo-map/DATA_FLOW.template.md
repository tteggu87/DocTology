---
status: Active
source_of_truth: No
last_updated: YYYY-MM-DD
superseded_by: N/A
---

# Data Flow

## Primary Flow

Describe the main request, job, file, event, or data flow through the repository.

```text
input -> parser/adapter -> core logic -> persistence/index/output
```

## Side Effects

List filesystem writes, database writes, network calls, generated indexes, caches, or external calls.

## Boundaries And Guards

State where validation, authorization, review gates, or source-of-truth boundaries apply.

## Known Flow Drift

List mismatches between documented flow and live code, or unclear ownership that still needs review.
