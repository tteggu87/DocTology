---
title: Wiki Studio retrieval observability verification
type: evidence
evidence_id: EVIDENCE-2026-09-06-WIKI-RETRIEVAL-OBSERVABILITY
target_fingerprint: sha256:91ddec8a353aeeaa39d0c2fb8fef68be6e23026043818762b377fcfb3126330d
date: 2026-09-06
status: Active
source_of_truth: false
last_updated: 2026-09-06
superseded_by: N/A
---

# Retrieval observability

## Implemented contract

The [usage guide](../../dashboard/README.md#검색-상태와-답변별-사용량) separates workspace configuration, metadata/stat freshness, server ONNX package/artifact presence, stored vector rows, and actual per-answer search calls. Status never activates a model or retrieval engine. Current chat remains Python literal search plus wiki-link discovery; FTS/vector are unconnected.

The new skill-owned adapter does not execute target-vault scripts or import model packages. It bounds directory and metadata reads, refuses active journals/WAL modes, uses an immutable read-only connection, and rejects database changes during inspection. It does not certify exact content, vector validity, or successful inference. The version-scoped stat projection intentionally keeps the loop skill self-contained; bootstrap remains the canonical producer of its index protocol.

Usage counts successful discovery calls over one answer's lifetime, including zero-hit queries. List/read calls are separate; failures and budget rejections are excluded. Integer percentages use largest fractional remainders to total 100. Zero denominators and old missing telemetry remain unavailable. Aggregates survive event-tail clipping and browser reload.

## Verification

- Python: 376 passed. JavaScript: 130 passed. Distribution and whitespace checks passed. Existing SQLite ResourceWarnings remain.
- A freshly bootstrapped temporary wiki with two pages and a real SQLite rebuild reported current stat freshness and FTS availability, while chat FTS/vector remained unconnected.
- An isolated scripted Pi RPC fixture called the actual localhost read tools: list once, literal search twice including an empty result, links once, and read once. The browser showed 67% literal / 33% wikilinks / 0% FTS / 0% vector and one independently tracked citation. Reload preserved the counters. This verifies transport, aggregation, persistence, and rendering, **not LLM behavior or answer quality**.
- The real connected workspace at `http://127.0.0.1:4337/` showed SQLite off and ONNX unconfigured. It preserved two existing conversations, with unknown usage on old answers rather than reconstructed percentages.
- All 24 user raw/wiki files stayed byte-identical. No test source or model request was sent through the user workspace. Watching and automatic execution were not enabled.
- Independent scoped code review found no blocker. Cold reading tightened the UI location, measurement window, and denominator in the guide. Consistency audit stayed read-only; no cross-skill consolidation was performed.

The stat test initially reused its own projection as an oracle. It now also compares against the canonical bootstrap indexer; the real rebuild fixture supplies a second independent producer. A separate 7:2:3 test catches confusing largest lane size with largest fractional remainder.

The fingerprint covers 30 files using the [dashboard evidence algorithm](2026-09-05-wiki-dashboard.md). Local deployment metadata remains in `state/dashboard-server.json`; source-only checks do not replace the browser observations above.
