---
status: Active
source_of_truth: true
last_updated: 2026-09-05
superseded_by: N/A
---

# Architecture

The repository is a skill pack, not a running knowledge system.

1. `.agents/skills/` contains the three canonical, self-contained products.
2. `scripts/manage_skills.py` validates or copies those products without interpreting their internals.
3. `tests/` exercises distribution, wiki bootstrap retrieval, standalone loop
   gates, and Repo Docs tooling.
4. `docs/`, `intelligence/`, and `wiki/` describe and remember this repository itself.

Generated wiki vaults are downstream products. Their Markdown is canonical; optional SQLite is disposable. Repo Docs repositories use relative Markdown links and a separate disposable docs index.

The generated vault contains the base wiki contract and optional retrieval
helpers, not copied loop executables. `llm-wiki-loop` owns the source procedure,
batch, and structural gate runtime and runs it from the skill directory against
the vault. The vault stores only canonical wiki changes plus bounded run, batch,
and receipt state. Multi-source batches prepare drafts outside `wiki/`, publish
once, and use one state-only snapshot seal to bind all source runs and the final
certification to the unchanged writer result.

The Repo Docs skill owns that index builder plus optional native SQLite read
adapters as sibling skill files. Python owns rebuild/status/doctor and remains
the portable fallback; the shell and PowerShell adapters share SQL and own no
freshness, mutation, or canonical-truth decisions.

An optional Wiki Studio is owned by the loop skill. `scripts/wiki_dashboard.py`
serves `dashboard/` on localhost and binds every read or write to the currently
connected root. `scripts/wiki_dashboard_automation.py` owns the opt-in watcher,
stable-file import, persistent sequential queue, and dispatch adapter;
`scripts/wiki_dashboard_save.py` owns bounded conversation preview, immutable raw
publication, and queue handoff. These modules and UI assets remain skill-owned
and are never copied into generated vaults.

Read-only chat uses in-memory Pi tool loops. The explicitly loaded
`wiki_dashboard_chat_extension.mjs` exposes only the four tools served by the
per-chat, authenticated localhost `wiki_dashboard_chat_tools.py` bridge. The
model lists, searches, reads, and follows approved local documents; built-in
shell/write tools and ambient extensions are disabled. Only actual reads create
numbered evidence, changed evidence is invalidated at completion, and citation
opening checks the current document hash. Workspace history stays in the browser
and numeric citations are not semantically verified claims. Explicit conversation approval creates only an unverified content-hashed
raw record. The watcher uses internal `raw/` paths in place and makes immutable
raw snapshots of independent external Markdown without changing the external
folder. Target `state/dashboard_automation/` stores watcher configuration,
baselines, and queue state; `state/dashboard_jobs/` stores execution connection
metadata. Neither is a new semantic verifier or completion ledger. Queue status
becomes completed only through current existing source-run and batch gates, and
interrupted work is surfaced for review rather than silently retried. Pi source
work uses local account permissions, not a sandbox, and its configured model may
be remote. The repository remains a three-skill pack rather than a root
application. See [usage](../.agents/skills/llm-wiki-loop/dashboard/README.md) and
[ADR-0002](adr/ADR-0002-local-wiki-dashboard.md).
