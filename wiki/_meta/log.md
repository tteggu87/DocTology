---
title: DocTology maintenance log
type: meta
status: active
updated: 2026-08-26
---

# Maintenance log

- 2026-08-26: Absorbed DuckCrab's derived Repo Docs SQLite fast-path into the
  canonical skill. Kept stat status, exact doctor, unchecked search/traversal,
  one-connection batch search, native shared-SQL adapters, and optional trigram
  discovery. Corrected long-document result starvation, raw FTS operator input,
  native failure exits, and rebuild publication-time drift detection; added
  `--no-trigram` as the only large-corpus storage switch. Independent review then
  corrected inclusive line ranges, normalized native error exits, removed
  quadratic line scans, and changed rebuild to document-streamed insertion plus
  a streamed final fingerprint. Focused 23/23 and full 135/135 tests passed;
  Windows PowerShell runtime dogfood remains unverified.
- 2026-08-25: Corrected generated wiki lint orphan detection. `_meta` navigation and self-links no longer count as inbound semantic links; `--strict-orphans` optionally turns orphan findings into a failing exit status.
- 2026-08-25: Reduced DocTology to three public skills. Moved the prior local workspace to a checksum-verified sibling legacy vault; removed active ontology, workbench, duplicated runtimes, and tracked archive surfaces; added one distribution manager and focused verification. Independent review also aligned the bootstrap command with `~/.codex/skills`, made clean-checkout validation warning-free, and hardened replacement of file and symlink destinations.
