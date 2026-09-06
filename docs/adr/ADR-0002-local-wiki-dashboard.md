---
title: Loop-owned local Wiki Studio
type: adr
status: Accepted
decision_id: ADR-0002
decision_status: accepted
implementation_status: verified
date: 2026-09-05
implementation_plan: ../plans/2026-09-05-wiki-dashboard.md
implementation_refs:
  - ../../.agents/skills/llm-wiki-loop/scripts/wiki_dashboard.py
  - ../../.agents/skills/llm-wiki-loop/dashboard/app.js
implementation_evidence:
  - ../evidence/2026-09-05-wiki-dashboard.md
source_of_truth: true
last_updated: 2026-09-05
superseded_by: null
---

# ADR-0002: Loop-owned local Wiki Studio

## Decision

The optional local dashboard belongs to `llm-wiki-loop`: its launcher lives in
the skill's `scripts/` directory, and its static UI and labelled example live in
`dashboard/`. DocTology continues to distribute exactly three self-contained
skills. There is no root application, fourth skill, hosted service, or copied
runtime in generated vaults.

Python's standard library serves the UI and controls a Pi RPC subprocess. The
existing loop remains the authority for procedure, coverage, and certification.
The dashboard never treats agent text or process termination as wiki completion.
Local process metadata and bounded visible events belong to downstream
`state/dashboard_jobs/`; existing source runs and batch manifests remain the
workflow records. Pi is the first execution adapter; LangGraph and hosted
observability are deferred until the product needs them.

## Consequences

Read-only visualization needs no JavaScript package installation or model call.
Execution needs a separately installed Pi providing `agent_settled`, tested with
0.82.1. This is a localhost application using the user's local account, not a
multi-user sandbox. Wiki content follows the configured model when the user
starts a task. No cloud deployment is required to operate a local CLI agent.

The UI shows real document links and source-bound coverage accounting, with
explicit empty, stale, disconnected, and example states. It checks the latest
source run and only the batches linked to that run when determining completion.

See [usage](../../.agents/skills/llm-wiki-loop/dashboard/README.md) and
[verification](../evidence/2026-09-05-wiki-dashboard.md).

Conversation is the primary UI surface. Chat uses a separate Pi RPC process
with built-in tools and ambient extension, skill, context, and prompt loading
disabled. One skill-owned read-only extension is loaded explicitly; sessions
are not persisted. Before a prompt, the backend requires an authenticated
loopback ready handshake. The main backend preserves Pi's ambient default model
unless the user explicitly overrides model or provider. The extension has only
four inventory- and root-bound read tools: `wiki_list`, `wiki_search`,
`wiki_read`, and `wiki_links`. General shell, write, and external-web tools
are intentionally absent.

The model independently reads inventory, links, and documents; generic overview
requests begin with inventory rather than a literal lexical query. Bounded usage
allows 64 calls, 24 distinct documents read, 160,000 returned characters,
10,000 characters per read, and 2 MB per file. The UI reports actual actions,
calls, read count, bounded trace, and truncation or budget pressure, without
showing model reasoning. Only actual reads are citation candidates. Numeric
claims need explicit references drawn from that subset. Discovery is neither
proof nor a read, and model citations are not semantic verification receipts.
Transient jobs remain in memory, history remains in the browser, and chat never
publishes into canonical wiki content. Source documents reopen through an
approved inventory with expected-root checks and verified raw-link navigation.
The existing source kanban and ingest controls remain a secondary write surface.
Read-only chats and wiki writers run concurrently with separate cancellation;
chat does not claim a writer slot. Writes still serialize and locally active
lanes prevent root switching. Concurrent reads use live documents, not a frozen
whole-vault snapshot; the UI discloses that distinction. Explicit multi-source
parallel preparation is governed by
[ADR-0003](ADR-0003-wiki-parallel-preparation.md); it does not change this
ADR's chat or writer-serialization boundary.
Actual Pi overview and linked-document checks are recorded in the bounded
[verification evidence](../evidence/2026-09-05-wiki-dashboard.md). They establish
working integration, not general semantic quality. Completion revalidates read
hashes; citation opening detects later document changes. Cancelled work skips
optional evidence I/O, and transport failures do not discard live job handles.
Explicitly approved folder watching and conversation capture feed that same
writer through a recoverable sequential queue. External files and conversations
are preserved under raw; browser-supplied conversations remain unverified data.
Neither queue status nor model output replaces the existing completion gates.
Automatic dispatch requires a persisted opt-in, and project mode denies these
source-entry writes.

Source projects with `AGENTS.md` and `wiki/` may connect in read-only project
mode, including read-only chat. This includes project docs, meta navigation, root documentation, and
skill documentation in an explicit readable inventory. It does not create raw
source state or authorize an incompatible workspace for ingest.
