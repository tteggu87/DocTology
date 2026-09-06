---
status: Active
source_of_truth: false
last_updated: 2026-08-26
superseded_by: N/A
---

# Roadmap

Keep the reusable skill inventory at three skills. Wiki Studio is a repository-owned application in `runtime/` and `dashboard/`, not a fourth installable skill. Future work should improve a core skill or the Studio only when tests demonstrate a concrete gap. Do not restore ontology profiles, duplicated Studio runtimes, or application copies inside skills without an explicit product decision.

Repo Docs SQLite remains lexical and disposable. Do not add vectors, rank fusion,
a daemon, or another database without a measured retrieval-quality gap. Re-run
storage and latency dogfood before changing the default trigram policy for a
materially larger corpus or a different operating system.
