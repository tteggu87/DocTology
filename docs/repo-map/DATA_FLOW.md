---
status: Active
source_of_truth: false
last_updated: 2026-09-06
superseded_by: N/A
---

# Data flow

`source skill directories -> manage_skills install -> target skill root`

The installer copies whole skill trees and never installs the Studio application.
A downstream bootstrap may create a wiki repository, which owns its Markdown and
optional derived SQLite state. No downstream corpus flows back into DocTology.

For certified LLM Wiki ingest, reusable loop gates retain the executable path:

`target raw/wiki -> llm-wiki-loop gates --repo-root -> run/batch/receipt state + canonical wiki changes`

The Studio reaches that same path without copying it:

`Studio runtime -> runtime/wiki_loop_adapter.py -> repository loop skill root -> unchanged loop gates -> target raw/wiki/state`

Multi-source certification retains one publish boundary:

`source runs through semantic plan -> state-only drafts -> one writer apply -> current question receipts -> state-only batch seal -> certification`

The seal writes no wiki Markdown. No procedure, batch, or pipeline executable is
copied into the target vault.

The optional Studio paths remain separate:

`chat + bounded history -> authenticated loopback handshake -> isolated Pi RPC + four inventory reads -> actual-read citation subset -> browser history + graph highlighting`

`wiki-work request -> Studio runtime -> Pi RPC -> loop adapter -> reusable loop gates -> target raw/wiki/state`

`opt-in watched Markdown or approved conversation -> immutable/raw-bound queue item -> existing full loop -> current gate-derived status`

Chat remains read-only. The Studio has no shell, write, network, or equivalent
terminal capability in its chat extension. Process records remain operational
state, never a completion ledger. The [migration evidence](../evidence/2026-09-06-studio-runtime-separation.md) verifies the moved paths and preserved boundaries; earlier evidence retains the former skill-owned layout.
