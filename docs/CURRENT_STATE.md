---
status: Active
source_of_truth: true
last_updated: 2026-09-06
superseded_by: N/A
---

# Current state

DocTology distributes exactly three skills: `llm-wiki-bootstrap`, `llm-wiki-loop`, and `repo-docs-intelligence-bootstrap`.

The canonical management entrypoint is `python3 scripts/manage_skills.py`. `check` validates the source inventory; `install` synchronizes it to a target skill root. Skill-owned scripts remain inside each skill and are copied with the skill.

The repository has no active ontology operator, root ontology pipeline, workbench, canonical corpus, or tracked archive. Optional SQLite in generated wiki vaults is derived retrieval state owned by `llm-wiki-bootstrap`.

Verification uses `python3 -m unittest discover -s tests` and the validator bundled in `repo-docs-intelligence-bootstrap`.

Repo Docs retrieval now separates cheap stat freshness, exact doctor verification,
and unchecked candidate discovery. Its Python fallback returns one best heading
chunk per document, supports one-connection `search-batch`, and checks Markdown
again immediately before atomic index publication. Optional POSIX and PowerShell
wrappers call native SQLite over shared search/traversal SQL without adding a
daemon. Rebuild includes a contentless trigram literal index by default;
`--no-trigram` retains compact token FTS for multi-gigabyte repositories.
SQLite builds without the trigram tokenizer fall back to that compact profile.

Generated LLM Wiki retrieval now uses the same operational split without copying
Repo Docs-specific trigram or native-wrapper policy: lexical search and bounded
wikilink traversal reuse one structural connection and return unchecked
candidates, `status` remains stat-based, and `doctor` remains content/vector
exact. Rebuilds stream page bodies, preserve compatible ONNX vectors in bounded
batches, correct peer-heading paths, and compare a streamed exact fingerprint
immediately before replacing the disposable index.

SQLite-enabled generated vaults also include `raw_retrieval.py`. It maintains a
separate incremental `state/raw_index.sqlite` over `raw/**/*.md`, stores chunk
metadata/offsets without a duplicate regular content column, uses lexical FTS
only, and reopens canonical raw byte ranges for results. Raw `status` is
stat-based, `search` is unchecked candidate discovery, and `doctor` is exact.
Wiki search remains the unchanged default path. Explicit `search
--raw-fallback` consults the raw index only after an empty wiki lexical result,
keeps candidates in a separate lane, and reports `unavailable` without failing
the wiki query when optional raw state is absent.

Generated wiki lint treats `_meta` navigation links and self-links as non-semantic for orphan detection. Orphans are advisory unless `lint --strict-orphans` is requested.

The raw index also stores a deterministic Markdown heading tree. `tree`,
`ancestors`, and `subtree` are read-only, checksum-checked navigation aids that
reopen canonical byte ranges; stale structure returns `rebuild --exact` guidance and no
structure or content. The wiki loop may use these paths when helpful, but direct
Markdown reading remains the fallback and the existing coverage receipt remains
the only source-accounting boundary.

The standalone LLM Wiki loop runtime uses `fcntl.flock` on Unix and
`msvcrt.locking` on Windows, preserving run-finalization and SQLite-refresh
serialization without adding a runtime dependency. It runs from
`llm-wiki-loop`, never installs gate files in a target vault, and records its
runtime identity plus contract digest in source runs.

Certified wiki ingest defaults to coverage-preserving `full` mode. The generated
base `AGENTS.md` routes full coverage, batch work, and `ready` completion to
`llm-wiki-loop`; the loop operates any compatible wiki-only target through its
own runtime. Explicit `summary` is the only reduced path. Full final review
requires one applied ingest receipt bound to the raw source hash, balanced
projected/omitted/deferred counts, and zero deferred units.

Multi-source ingest now has a snapshot seal path. All linked source runs stop
after their three pre-mutation stages while drafts remain under `state/`; one
writer applies the merged canonical files, question receipts bind to that
result, and `batch seal` records one state-only review, completes every source
run against the unchanged snapshot, refreshes retrieval once, and immediately
certifies. A post-apply mutation fails seal instead of forcing sequential
source-by-source revalidation. Seal prepares complete run payloads before live
state replacement; an interrupted commit is explicitly resumable, while a
stale prepared attempt restores the original source-run state. A pre-refresh
journal marker prevents an interrupted seal from running retrieval refresh more
than once and recovers its posture through a read-only status check. Batch
certification also enforces this boundary directly: multiple non-deferred
sources cannot certify without a current seal covering the exact run set. Public
batch help now shows the complete command order and subcommand purposes, while
read-only batch status returns a deterministic advisory `next_action` for
handoff and interruption recovery without adding an orchestration runtime.
Read-only batch list discovers recent or active manifests without repeated
corpus hashing, isolates malformed manifest metadata, and explicitly routes each
unchecked valid result through exact status.

The loop skill includes an optional localhost Wiki Studio with conversation as
its primary surface. Its chat backend launches a separate Pi RPC process with
built-in tools and ambient extension, skill, context, and prompt loading disabled.
It explicitly loads one skill-owned read-only extension, disables session
persistence, then waits for an authenticated loopback ready handshake before
sending a prompt. The main backend preserves Pi's ambient default model unless a
user explicitly chooses a model or provider. The chat extension exposes only
four root- and current-inventory-bound read tools: `wiki_list`, `wiki_search`,
`wiki_read`, and `wiki_links`. Project documents are supported by that same
read-only inventory. There are no general shell, write, or external-web tools.

The model independently chooses document, link, and content reads. A generic
overview begins with an inventory rather than a literal lexical search. Calls,
distinct documents read, and returned characters are capped, with a 64-call,
24-document, 160,000-character, 10,000-character-per-read, and 2 MB-per-file
boundary; truncation and budget pressure are surfaced in the UI. The UI shows
actual actions, calls, read count, and a bounded trace, but never model
reasoning. Actual Pi runs exercised a generic overview and linked-document
question; the bounded results and limits are in the [verification record](evidence/2026-09-05-wiki-dashboard.md).
Only actual reads become citation candidates, and only explicitly cited reads
appear as references. Changed evidence is invalidated at completion; opening
an old citation checks the current document hash. Cancellation remains responsive
during tool I/O, while transient polling failures retain the job and stop control.
Discovery is neither proof nor a read, and citations are not semantic certification.
Read-only chat and wiki writes run independently with separate cancellation;
only writers serialize. Concurrent reads are live, not a frozen whole-vault
snapshot, and the UI signals ongoing wiki work. Root switching remains blocked
while either locally owned lane is active.

Browser-local history and this read-only chat remain non-canonical. A user may
approve an exact ten-minute conversation preview as an unverified,
content-hashed raw source. The save path accepts at most 40 messages, 100,000
total supplied characters including references, and 24 references per message,
resolves only current approved document IDs, then queues the immutable record
for the existing full-coverage loop gates. It never writes conversation claims
directly into canonical wiki pages.

The same skill now owns an opt-in Markdown folder watcher and sequential queue.
Watching and `autoRun` are independent and both default off. The connected
`raw/` tree or one of its subfolders may be watched in place; an independent
external folder is copied into immutable `raw/inbox/watched/` snapshots without
modifying or deleting the external files. Scans cap Markdown at 2 MB per file
and 500 files, require two stable observations, and exclude existing files by
default. Explicit manual runs and approved conversation saves may dispatch while
watching is disabled. Queue completion still requires the current raw hash and
existing source-run and batch gates; interruptions never silently retry.
Disabling detection pauses automatic dispatch. Changed-folder rows require a
fresh manual request. Stale completion is demoted and restored passing gates
restore completion without another model call. The queue has bounded 100-row
pages; writer contention waits, and surviving persisted Pi runners exclude new
writes after a dashboard restart. Verification scope is recorded in the
[dashboard evidence](evidence/2026-09-05-wiki-dashboard.md).

The dashboard also connects this source repository in read-only project mode.
Its real wiki/meta, docs, root project documents, and skill references form one
document graph and library. No raw directory, ingest progress, or persisted
execution state is invented for a repository that only contains project
documentation. Read-only chat remains available, while watch and conversation
save are denied. Claude execution remains unimplemented. The localhost process
must remain running on the currently connected root; task agents use local
account permissions rather than a sandbox, and the selected Pi model may be a
cloud service. Generated vaults receive content and bounded state only, never a
copy of the dashboard runtime or its skill-owned automation/save modules. See
[usage](../.agents/skills/llm-wiki-loop/dashboard/README.md) and
[the ownership decision](adr/ADR-0002-local-wiki-dashboard.md).

For explicitly requested multi-source Wiki Studio work, the dashboard now
uses parallel source preparation inside the existing batch procedure. Batches
contain two to twelve sources, default to three preparation workers, and cap at
four; one source keeps the existing path. A source worker has only the four
inventory-bound reads plus source-owned `draft_write` and `draft_submit`, which
can write only its batch-state draft directory. The coordinator initially has
those reads and `wiki_prepare_batch`; built-in tools restore only after every
matching worker is prepared. Source hashes, complete required reads, draft
hashes, and per-source provenance bind a prepared draft, but preparation is not
canonical mutation or completion.

Existing batch plan/linking, three pre-mutation stages per source run, semantic conflict
reconciliation in state, one writer apply, question receipts, and snapshot seal
remain the sole completion authority. The supervisor persists under
`state/dashboard_jobs/parallel/`. Per-source stop/retry is explicit and
hash-bound; dashboard restart never resumes workers automatically. Applied or
stale batches cannot reprepare and must use their existing batch-status/recovery
path or a fresh batch. Auto queue grouping is limited to individually authorized
current-hash pending entries, preserves source provenance, and retains parallel
siblings on retry rather than falling back to legacy single-source writes.
Watching and `autoRun` remain independent opt-ins, default off. Read-only chat
remains independent, Pi keeps its ambient default unless explicitly overridden,
and a capability flag hides parallel controls when an older server does not
support them. The clean fixture proved concurrent first-attempt preparation, but
its integration reuse correctly stopped at a missing-index-link gate. Its original
batch remains blocked and unsealed; a new existing-runtime corrective batch
repaired only those links and certified through the existing procedure. This is
gate enforcement and fresh-batch repair, not a bypass. Current observations,
local deployment state, and limits are in the [parallel preparation
verification](evidence/2026-09-06-wiki-parallel-preparation.md).
For the dashboard workstream background, rejected/deferred alternatives,
review repairs, and the next verification priorities, read the
[derived handoff](../wiki/decisions/local-wiki-studio.md). This does not change
the runtime or its completion gates.

## Dashboard module boundaries

The dashboard entrypoint composes an injected document catalog, passive folder helpers, and an independent HTTP transport. Frontend history codecs, Markdown, graph logic, and retrieval presentation use explicit-input factories, while application state, storage, and asynchronous lifecycle guards stay in `app.js`. HTML declares the deferred script order and admitted HTTP assets; external boot runs once. This changes neither UI behavior nor execution authority. The [verification](evidence/2026-09-06-dashboard-refactor.md) records regression and live-browser checks. See the [maintenance map](../.agents/skills/llm-wiki-loop/dashboard/README.md#유지보수와-확장-경계).

## Local folder selection

Wiki Studio connection supports native macOS/Windows folder selection and a bounded in-app folder browser when the desktop picker is unavailable. The in-app browser visits one directory at a time, returns only non-hidden non-symlink directory names and paths, and exposes truncation rather than implying an exhaustive listing. Picking a folder only fills the connection form; the original workspace validation, live-work guards, token, Host, and Origin checks remain authoritative. Manual path entry remains available. This changes neither canonical files nor watcher/model opt-ins. Native desktop limits and the verified click-only fallback are recorded in the [folder selection evidence](evidence/2026-09-06-wiki-folder-picker.md).

## Retrieval observability in Wiki Studio

Workspace badges expose passive SQLite configuration/stat freshness and server-environment ONNX package/artifact presence. The skill-owned adapter never executes target-vault code, loads a model, rebuilds an index, or writes SQLite sidecars. Unknown schemas, journals, changing databases, and bounded-check failures remain unknown. Stored vector rows are not semantic readiness.

Per-answer retrieval usage is aggregated independently of the visible event tail and saved with browser-local messages. Percentages describe successful search/link calls, not answer contribution, quality, coverage, or citations. Current chat uses Python literal search and wiki-link discovery; FTS/vector remain unconnected to chat even when separately configured. Older answers retain unknown usage. Existing model defaults, writer gates, and watcher opt-ins are unchanged. See the [retrieval observability verification](evidence/2026-09-06-wiki-retrieval-observability.md) for the real-index fixture, measured tool calls, current local state, and limits.
