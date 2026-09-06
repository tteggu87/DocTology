---
title: DocTology-owned Wiki Studio runtime separation
type: adr
status: Accepted
decision_id: ADR-0004
decision_status: accepted
implementation_status: verified
implementation_refs:
  - ../../runtime/wiki_dashboard.py
  - ../../runtime/wiki_loop_adapter.py
  - ../../dashboard/index.html
date: 2026-09-06
supersedes: ADR-0002-local-wiki-dashboard.md
implementation_evidence:
  - ../evidence/2026-09-06-studio-runtime-separation.md
source_of_truth: true
last_updated: 2026-09-06
superseded_by: null
---

# ADR-0004: DocTology-owned Wiki Studio runtime separation

## Decision

DocTology is a Studio application plus exactly three reusable skills:
`llm-wiki-bootstrap`, `llm-wiki-loop`, and
`repo-docs-intelligence-bootstrap`. `scripts/manage_skills.py` continues to
validate and install only those three skills. It does not install the Studio
application.

The repository owns the Studio runtime in `runtime/`, its static UI in
`dashboard/`, and its dashboard JavaScript evaluations in `tests/dashboard/`.
The root `Wiki-Studio.command` and `Wiki-Studio.bat` remain thin compatibility
forwarders, now forwarding to `runtime/start_dashboard.command` and
`runtime/start_dashboard.bat`. There are no copied application files under the
loop skill after migration.

`llm-wiki-loop` owns reusable procedure, coverage, batch, and certification
gates only. `runtime/wiki_loop_adapter.py` binds the Studio to the repository's
loop skill root and invokes those gates without moving, duplicating, or changing
their contracts.

## Preserved contracts

This change preserves the existing chat boundary: the isolated read-only path
has only inventory-bound `wiki_list`, `wiki_search`, `wiki_read`, and
`wiki_links` tools. It preserves the security boundary, including loopback
handshake and root, origin, token, and expected-root checks. It preserves the
writer boundary and all existing procedure, coverage, batch, receipt, seal, and
certification gates. Studio process state remains operational state, not a
second completion authority.

## Status and verification

The ownership migration is implemented and verified in the linked evidence. Earlier
Studio evidence, test counts, file fingerprints, and skill-relative commands
remain historical observations of the pre-migration layout; they do not verify
the new paths. The new layout is verified in
[the migration evidence](../evidence/2026-09-06-studio-runtime-separation.md)
with runtime, UI, tests, launchers, adapter, links, and unchanged gate behavior checked.

## Consequences

Current documentation must point to repository-owned `runtime/` and
`dashboard/` paths. Historical records may name the removed loop-skill paths
when necessary to preserve their observed scope, but must label those paths and
commands as historical. Generated vaults still receive no Studio runtime or UI
files.
