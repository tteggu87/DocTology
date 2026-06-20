---
status: Active
source_of_truth: No
last_updated: YYYY-MM-DD
superseded_by: N/A
---

# Symbol Graph

This is a high-impact symbol summary, not a complete call graph.
Use codegraph, LSP, AST-aware search, or targeted `rg` results as evidence.

## High-Impact Symbols

| Symbol | Role | Called By | Calls | Change Risk |
| --- | --- | --- | --- | --- |
| `package.module:function` | Replace with live role. | caller summary | callee summary | low / medium / high |

## Cross-Cutting Dependencies

List config loaders, persistence writers, index builders, policy gates, route registrars, or shared adapters.

## Risk Notes

State which symbols require extra tests, manual QA, or docs/intelligence updates when changed.
