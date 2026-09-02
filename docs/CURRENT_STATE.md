---
status: Active
source_of_truth: true
last_updated: 2026-09-02
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

The disposable wiki index is now `wiki-heading-index-v9`. Wiki and raw retrieval
always honor fenced-code-aware ATX heading boundaries, including on small
PPT-derived Markdown; the default 8 KiB maximum applies per section, and only an
oversized section uses paragraph/UTF-8-safe fallback. Wiki rebuilds persist the
existing deterministic document/heading nodes, and every chunk owns one
`node_id`, so body search hits retain their heading path and routing ranges while
identifying the exact derived structure node. Markdown remains canonical.

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
