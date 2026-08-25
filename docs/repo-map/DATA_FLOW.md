---
status: Active
source_of_truth: false
last_updated: 2026-08-25
superseded_by: N/A
---

# Data flow

`source skill directories -> manage_skills install -> target skill root`

The installer copies whole skill trees. A downstream bootstrap may then create a wiki repository, and that repository owns its Markdown and optional derived SQLite state. No downstream corpus flows back into DocTology.
