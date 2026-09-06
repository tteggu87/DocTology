---
title: Wiki Studio delivery
type: plan
plan_id: PLAN-2026-09-05-WIKI-DASHBOARD
status: completed
source_of_truth: false
last_updated: 2026-09-05
superseded_by: N/A
---

# Wiki Studio delivery

## Scope

A bright local workspace connects a generated wiki to a live source kanban,
document-link graph, source coverage, verification steps, and Pi task controls.
No cloud host, extra skill product, LangGraph migration, or simulated completion.

## Implementation

- Implemented the loop-owned Python HTTP/RPC adapter and source-derived views.
- Implemented light UI, source selection, graph highlighting, document reading,
  search, upload, task submission, steering, cancellation, and execution history.
- Added real temporary-vault/HTTP tests and deterministic subprocess lifecycle
  tests, plus JavaScript rendering-contract tests.
- Independent read-only review identified Pi settlement/cancellation and two
  completion-display issues; fixes and regression tests are included.

## Chat-first workstream

Understood as: make conversation the primary surface, retain workspace navigation on the left, and show the full document graph with answer-cited wiki pages plus a navigable reference list on the right. Readers must be able to follow verified local links back to raw Markdown. Existing ingest execution and completion gates remain available as a secondary workspace.

- Implement bounded read-only Pi chat with explicit numeric citations and no file tools.
- Add the three-column conversation UI, local conversation history, cited-node highlighting, and reference/raw readers.
- Preserve project read-only behavior, existing source execution controls, and truthful completion reporting.
- Verify with isolated process/HTTP tests, rendering contracts, live model/browser checks, and an independent review.

The initial chat increment excluded watching and canonical conversation publication. The next workstream below now adds those two capabilities through the existing loop; Claude execution remains out of scope.

## Folder-watch and conversation-save workstream

Understood as: implement the two previously deferred features. Users explicitly enable Markdown folder detection and separately opt into automatic model execution. Saving a selected answer or conversation first shows an exact preview, then preserves it as an unverified conversation source and queues the existing full-coverage wiki loop. Neither queue bookkeeping nor model exit may certify wiki quality.

- Persist bounded, root-bound detection state and an idempotent work queue outside canonical wiki content.
- Import external selected-folder changes as immutable raw snapshots; never delete wiki content after source deletion.
- Keep automatic execution off until explicit opt-in; defer while the wiki writer is busy and do not auto-retry interrupted work. Read-only chat is an independent lane and does not postpone authorized writes.
- Connect conversation preview/commit to the same queue and existing completion gates.
- Exercise real browser navigation and an isolated source-to-verified-wiki cycle, with independent review and regression tests.

## Out-of-scope follow-up

The source-entry implementation and its bounded validation are complete. The next product decision is
whether to synchronize the global skill install or expand to a blinded real-corpus
quality evaluation; neither happens automatically.

## Agentic chat workstream

Understood as: replace one-shot lexical-excerpt chat with a real Pi tool loop that lists, searches, reads, and follows approved local document links across multiple hops. Generic whole-wiki questions must start from inventory/index discovery rather than literal matching of the request. Preserve Pi's environment-selected default model, scope all tools to approved read-only documents, and retain explicit approval plus the existing loop for writes.

The bridge is per-chat, authenticated, localhost-only, and memory-only. Only actual document reads create citation evidence; listing/searching/link discovery is not evidence of reading. Limits and actual tool activity stay visible without exposing model reasoning. There is no fixed graph-hop depth below the bounded call/read budget.

## Completion and follow-up boundary

Implementation and bounded validation are complete. Use the latest server recorded in ignored `state/dashboard-server.json`; see [current evidence](../evidence/2026-09-05-wiki-dashboard.md). Global installation or a blinded retrieval-quality benchmark requires a separate request.

The agentic increment passed 290 Python tests and 78 UI/extension tests. Actual Pi read a linked-document fixture through a long raw tail and answered the generic overview question in the connected user wiki. Independent review and browser checks repaired cancellation, stale evidence, polling recovery, disclosure-state loss, and compressed citation cards.

## Source-entry completion (historical)

Implemented both source-entry paths, root-bound queue pages, explicit automation,
retry/recovery, and current-gate completion. The final suite passes 273 Python and
53 UI tests. Independent review findings were repaired. In a temporary vault,
real GPT source and conversation runs passed the existing full gates; preview/raw
byte equality and wiki-to-raw browser navigation were checked. The final preview
uses port 4323 with the user's wiki connected and automatic execution OFF. See
[current evidence](../evidence/2026-09-05-wiki-dashboard.md) for the distinction
between individual successful cycles and final corpus certification.

## Chat-first completion (historical)

The full Python suite passed 217 tests and JavaScript contracts passed 33 tests.
Real GPT chat, citation-to-reader navigation, three-column desktop display, and
isolated raw-source navigation were exercised. Independent review findings were
repaired. See the current section of the [verification record](../evidence/2026-09-05-wiki-dashboard.md)
for scope and limitations.

## Previous delivery baseline

Implementation, independent review fixes, 198 Python tests, and eight UI rendering
contracts pass. The localhost preview now connects the actual DocTology project in read-only
mode, including its wiki, docs, skill references, and root documentation. See
[verification evidence](../evidence/2026-09-05-wiki-dashboard.md) for scope and limits.
