---
title: Local Wiki Studio verification
type: evidence
evidence_id: EVIDENCE-2026-09-05-WIKI-DASHBOARD
date: 2026-09-05
subject: Agentic read-only Pi chat, source entry, and existing gate delegation
target_fingerprint: sha256:7129981a076db648072afaadbf9d9017d764eb096900c42193f59848761e13ac
status: Active
source_of_truth: false
last_updated: 2026-09-05
superseded_by: N/A
---

# Local Wiki Studio verification

## Current agentic read-only chat delivery

The current fingerprint hashes, in order: loop `SKILL.md`; sorted
`scripts/wiki_dashboard*.py`; sorted `scripts/wiki_dashboard*.mjs`; sorted files
in `dashboard/`; sorted `evals/*.cjs`; and sorted `tests/test_wiki_dashboard*.py`.
Each entry is UTF-8 repository-relative path, NUL, file bytes, NUL. The target is
the uncommitted worktree addition on the original base.

### Automated and independent checks

- Full Python suite: **293 tests pass** in the session-local PyYAML environment.
  Existing SQLite ResourceWarnings remain; no global dependency was changed.
- JavaScript contracts: **83 tests pass**, comprising 71 UI and 12 extension tests.
- Distribution, syntax, patch whitespace, and Repo Docs finalization checks pass.
- The installed Pi 0.82.1 accepted the isolated explicit extension, authenticated
  ready handshake, plain tool schemas, and RPC lifecycle. No model or provider
  override was passed for the live chat checks.
- Independent integration review found and rechecked cancellation behind tool
  I/O, stale citation evidence, lost polling handles, and post-stop validation
  delay. Focused tests verify the repairs. Parent checks also covered actual
  success/error envelopes, exhaustion, read offsets, unreadable inventory items,
  project scope, and interrupted HTTP bodies.
- Browser QA repaired native disclosure clicks and refresh state, plus reference
  cards collapsing when eight citations shared the visible panel. The latest
  page was reloaded and inspected after both UI repairs.

### Independent read-only chat and writer lanes

Read-only chats now coexist with manual or authorized queued wiki work. Tests
hold actual fake writer/chat subprocesses in both launch orders, verify separate
cancellation, and retain second-writer/upload/root-switch guards. A deterministic
writer RPC also changes a document after chat reads it: the chat finishes with a
visible stale-evidence state and removes outdated citations. This is live-read
behavior, not a frozen whole-vault snapshot. UI contracts cover new conversation
and submit availability for running, starting, stopping, and external wiki jobs.

A temporary browser fixture held its writer process alive while a fresh Pi chat
read one document through two actual tool calls and returned its independently
stored random code with a citation. The new-conversation button worked while the
writer was held. The writer was a controlled test process, not a second semantic
wiki builder; no claim of parallel source ingestion follows from this check.

The current handoff is **http://127.0.0.1:4329/**, with Pi's default model and the
existing user's workspace. Its browser-local history was copied from port 4327
without deleting the original. Host process-signal restrictions prevented closing
older instances; an intermediate instance at port 4328 lacks Pi in its launch
PATH and is not the handoff. The current launcher scopes the Homebrew PATH prefix
to its own environment, without changing global settings. Server metadata is
recorded in `state/dashboard-server.json`. The previously blocked `pdf만드는 법`
question was retried successfully on the new server: five calls, four reads,
and four references. All 24 current user raw/wiki files remained byte-identical
to the baseline taken after the user's own preceding writer had settled. The
held fixture writer was stopped through its own dashboard after verification.

### Reader and chat scrolling follow-up

The reader now keeps its title and close button outside an independently scrolling
body. At the live document bottom, the body was at 4570.4 of 4571 CSS pixels,
the outer dialog stayed at scroll zero, and X remained visible and closed it
without scrolling back up. Chat controls reached both ends of a long existing
conversation: zero at the top and 3539.2 of 3540 CSS pixels at the bottom. The
appropriate endpoint button disabled, and the controls occupied their own row
above the composer. Opening a document resets only its body scroll. Reduced
motion and short-content behavior have focused tests. A separate scoped reviewer
found no material regression. No model call or source mutation was needed for
this UI-only follow-up; the live page at port 4327 was reloaded with the new assets.

### Earlier agentic Pi and browser observations

1. A temporary synthetic wiki contained four linked evidence documents, a decoy,
   and a 15,204-character raw document whose final signature held a fresh random
   code absent from the question. The latest Pi run made **7 tool calls**, read
   **5 distinct documents**, continued the raw read after its first 10,000
   characters, returned the exact code, and cited all four linked sources.
   It finished in **25.22 seconds**; every fixture file remained byte-identical.
   An earlier run reached the same outcome with 6 calls and 4 distinct reads.
2. An earlier backend and UI run at **http://127.0.0.1:4327/** connected the existing
   user `wiki-only` workspace. The exact previously failing question,
   `위키내용 요약해줘`, now began with `wiki_list`, discovered 15 inventory entries,
   read **9 documents** across **10 calls**, and returned a summary with
   **8 explicit references**. This is observed selective reading, not a claim
   that every inventory document was read.
3. A reference click opened the actual `my-pdf Document Build System` page;
   its reopened summary and implementation sections supported the inspected
   answer passages. The real graph still displayed 12 pages and 59 links.
   Tool activity remained expandable, and cited cards remained readable.
4. The 15 files under the user's wiki/raw/state surfaces matched their pre-chat
   hashes. Watch and automatic execution remained off; no watcher state was
   created. Model choice remained the blank **Pi 기본 모델** setting.

The final cancellation guard has focused reproductions and was loaded in the
latest browser backend. Synthetic model runs preceded that guard and the last
UI-only repairs; these repairs did not change normal tool schemas or retrieval.
Earlier preview ports are not the handoff. The task environment refused signals
to older preview processes, so no host security policy was weakened to close them.

### Interpretation and limits

This verifies working default-Pi tool integration and literal fixture outcomes,
not general retrieval recall or semantic answer quality. The Mandela audit flags
verifier/designer dependence in the synthetic fixture and tests. Its random
answer was not supplied in the question, and actual paths, bytes, tool calls,
read ranges, and returned code were checked, but a quality benchmark still needs
independently labelled, blinded cases. The real-corpus observation is one
question, not such a benchmark.

Only actual reads create evidence; final citations remain model assertions.
Hash checks detect document changes, not semantic correctness. Large-corpus
latency, Windows lifecycle behavior, public hosting, and a complete adversarial
security audit remain unverified. General shell/write/web tools, new completion
gates, global installation, commit, and push were not added or performed.

## Folder-watch and conversation-save delivery (historical)

That increment's fingerprint was
`sha256:daa7f7159c33c03cb071eeedbef7f54d494e6d7f720b36ce403a41556cf46a0a`.
It covered, in order: loop `SKILL.md`; `wiki_dashboard.py`,
`wiki_dashboard_automation.py`, `wiki_dashboard_save.py`; all dashboard assets
sorted by path; the UI test; and Python dashboard, chat, automation, save, and
source-entry tests. Each entry hashes its UTF-8 repository-relative path, NUL,
file bytes, NUL. This is an uncommitted worktree addition on the original base.

### Automated and independent checks

- Full Python suite: **273 tests pass**, using the session-local PyYAML environment.
  Existing SQLite ResourceWarnings remain; no global dependency was changed.
- JavaScript rendering/state contracts: **53 tests pass**.
- Three-skill distribution, syntax, and patch whitespace checks pass.
- Repo Docs changed-file validation: zero errors and zero warnings.
- Independent review repaired disabled auto-dispatch, changed-folder authority,
  failed retry controls, writer contention, surviving runner exclusion, partial
  save recovery, stale/restored completion, and inaccessible queue rows. The
  reviewer rechecked both final findings and their focused regressions.
- Browser-driven repairs preserve unsaved watch settings during refresh and keep
  the save approval button visible at the tested desktop zoom. A blind standalone
  usage read found only caller-specific path/runtime prerequisites and a missing
  revision cue; the guide now includes that cue and startup verification.

### Real model and browser observations

A bootstrap-generated temporary vault and a separate temporary external folder
were used, not the user's corpus. Real Pi sessions identify
`openai-codex/gpt-5.5` for both source executions.

1. With detection enabled and automatic execution disabled, a new external
   Markdown file became one pending row without a model job. Its immutable raw
   copy matched the external file exactly:
   `sha256:18254473a217e422116e91bd5ec8e34cb2c15a866a9e76304314e16894117061`.
2. Explicitly enabling automatic execution started the existing loop. The source
   reached current completion with **4 projected units, 0 omitted, 0 deferred**,
   two wiki pages, and all existing source gates. The external file was unchanged.
3. A real GPT chat summarized the resulting fictional library rules with an
   explicit source citation. It preserved the public-holiday exception, unknown
   Sunday status, and the fact that this was fictional test material.
4. Watch and auto-run were turned off. Opening and retitling the conversation
   preview created no conversation directory. Approval saved exactly the displayed
   Markdown and explicitly queued the existing full loop despite watching being
   off. The raw capture hash was
   `sha256:4836c2d634e9cba4bbf844bdd7c2d943531a3ef51f0e34f41690de0c97713b24`.
5. The conversation run reached current completion with **9 projected units,
   0 omitted, 0 deferred**. The resulting source page distinguished unverified
   browser/model statements from the separately reopened raw evidence. Browser
   clicks opened the generated wiki page and then the preserved conversation raw.
   Both raw hashes remained unchanged after execution.
6. The later wiki mutation invalidated the first source's older completion
   snapshot. Its queue item correctly became `needs_attention`; the conversation
   item stayed completed. These are two observed successful source cycles, not a
   claim that the final two-source corpus is currently certified together.

These live source cycles ran on port 4322 before the final restored-gate and
queue-pagination repairs. Those final paths have focused independent regressions
and full-suite coverage. The final backend and UI were then launched on port
**4323**, connected to the user's existing `wiki-only` workspace: 12 real pages,
59 links, no watcher configuration, and both switches OFF. Merely connecting
created no watcher state and invoked no model. The final browser verified the
new queue-page controls and OFF disclosure. Earlier ports are not the handoff.

### Interpretation and limits

This is an integration test, not a semantic-quality benchmark. The tester authored
its synthetic source; the same model synthesized and performed the loop's semantic
review. Under the Mandela check, verifier/designer dependence prevents treating
passing gates or fixture results as independent evidence of general model quality.
Literal values, uncertainty, links, bytes, and state transitions were directly
checked. A broader quality claim would need independently labelled, blinded sources.

Crash/recovery, contention, oversized queues, and partial-save failures were
exercised with controlled tests, not live crash injection into the user's model
process. Large-corpus performance, Windows lifecycle behavior, public hosting,
and adversarial security remain unverified. Conversation captures are explicitly
`client_supplied_unverified`, not authenticated server-produced transcripts.
No new semantic verifier, Claude adapter, or DAG engine was added. Global skill
installation, commit, and push were not performed. The task environment could
not signal older preview processes, so a fresh port was used without weakening
host security policy.

## Chat-first delivery (historical)

Target: the uncommitted chat-first addition on the same base commit as the initial
delivery. The current fingerprint covers the launcher, sorted dashboard assets,
UI rendering test, original Python dashboard test, and new Python chat test,
using UTF-8 relative path, NUL, file bytes, NUL for each entry.

Executed after the backend repairs:

- Full Python suite: **217 tests pass**. The system Python lacked PyYAML for one
  pre-existing Repo Docs test; a session-local virtual environment with PyYAML
  passed the suite without changing global dependencies. Existing SQLite
  ResourceWarnings remain.
- Final JavaScript rendering/state contracts: **33 tests pass**.
- Distribution check: exactly three self-contained skills, pass.
- Repo Docs validator with the changed-file inventory: zero errors and zero warnings.
- Patch whitespace check: pass.
- Browser at `http://127.0.0.1:4319/`: the latest Python backend and static UI,
  connected to the existing `wiki-only` workspace, showed 12 real wiki pages
  and 59 document links. The three-column layout stayed visible at the user's
  desktop zoom; no narrow-phone browser test was performed.
- Official Pi OpenAI Codex browser OAuth completed. A real `gpt-5.5` response
  succeeded, and the user-requested Pi default was set to that provider/model.
  No API key or credential was copied into the repository or evidence.
- A real dashboard question about my-pdf/Typst/PDF quality produced an answer
  with three explicit source references. Citation clicks opened the matching
  local wiki body. The graph highlighted cited documents over actual links.
- A separate, clearly labelled temporary fixture copied the repository README
  as raw Markdown and linked it from a test wiki page. Browser navigation opened
  the wiki reader, its linked source, and the real raw body. No user corpus was
  altered. The workspace was restored after the check.
- Existing wiki-work navigation, source card, and task form were opened in that
  fixture without starting an ingest or writing a model-generated wiki page.

Independent code review found and repaired historical citation-number collisions,
chat startup losing its process handle on conversation switching, stale cross-root
reader responses, and unbounded output/history storage. Additional browser-driven
repairs restored functional graph zoom, kept sidebars visible at desktop zoom,
showed partial answers and elapsed time, and distinguished wiki/project empty
states. A separate cold reader of the standalone usage guide found minor startup
and success-criteria gaps; the guide now states the visible mode and verification
path.

### Interpretation and limits

Fake-RPC tests validate process/state/protocol handling, not model reasoning.
Designer-authored fixtures and UI contracts are not independent semantic-quality
benchmarks. The live query and literal document reopening establish a working
integration only; they do not establish retrieval recall, semantic citation
accuracy across a corpus, production security, comparative model quality, or
large-corpus latency. Candidate discovery is bounded lexical matching. A numeric
citation remains a model assertion, not a new quality gate.

Automatic folder monitoring, Claude execution, canonical conversation-to-wiki
publishing, and a new DAG execution engine are not implemented. Existing ingest
and certification logic is preserved, but no full real-model ingest was run in
this chat-first pass. Global skill installation, commit, and push were not done.

The older localhost processes could not be signalled by this task's execution
sandbox, so the final preview uses port 4319; ignored server lifecycle metadata
points to that current preview. Older sections below describe the initial
kanban-first delivery and are historical, including their no-browser-QA limit.

## Initial kanban-first delivery (historical)

Target: the uncommitted dashboard addition on base
`d791a9767accc10bfaf194b4b1f93f299b860246`. Implementation ownership is recorded in
[ADR-0002](../adr/ADR-0002-local-wiki-dashboard.md).

Environment: macOS, Python 3.14, local Node.js, installed Pi 0.82.1.

## Executed checks

- `python3 -m unittest discover -s tests -p test_wiki_dashboard.py`: 15 tests pass.
  Temporary real Markdown vaults cover read-only projection, source hash staleness,
  duplicate receipts, valid completion invalidated by a later mutation, current
  versus historical batch association, graph links, malformed records, upload,
  traversal/symlink/overwrite rejection, and HTTP Origin/token/Host protection.
- RPC test subprocesses cover start, additional instructions, cancellation,
  automatic retry past `agent_end`, final `agent_settled`, persisted history,
  concurrent writer rejection, and process completion without wiki completion.
- `node --test .agents/skills/llm-wiki-loop/evals/dashboard_ui.test.cjs`: eight tests
  pass for coordinated selection, failed validation display, unknown/stale
  progress, HTML escaping, empty search, and execution/completion separation.
- Installed Pi: `get_state` succeeded over real stdio RPC without calling a model.
  The model setting was available and streaming was false; no credentials were
  read into the report. Reviewer independently confirmed `clear_queue` is absent
  from this installed protocol; the adapter uses `abort` and `agent_settled`.
- Local preview returned HTTP 200 at `http://127.0.0.1:4317`; an in-app opening was
  requested. The app reported that opening as queued.

Independent follow-up review confirmed all four reported issues were repaired
and found no additional P0/P1/P2 defect within its read-only scope.

## Limits

No browser screenshots or interaction QA were requested or run. JavaScript tests
verify rendered contracts, not pixel appearance. No autonomous full-source model
synthesis was run against a user corpus, and no comparative model-quality or
cost claim is made. The default preview uses clearly labelled, inert example
data. Large-corpus latency, Windows process-tree cancellation, and multi-user
hosting are unverified. Global installation was not requested or synchronized.

## Repository checks

- `python3 -m unittest discover -s tests`: **198 tests pass**. Existing retrieval
  tests still emit their previously documented SQLite ResourceWarnings.
- `python3 scripts/manage_skills.py check`: passes; exactly three self-contained skills.
- `python3 -m py_compile` and `node --check`: pass.
- `git diff --check`: passes.
- Repo Docs validator with `--changed-files state/dashboard-changed-files.txt`:
  **zero errors and zero warnings**.

The initial fingerprint was `sha256:7bda4a98b9a1bd6a31f1d7fdde11dc87cce5e274c6177739f421baba828eba3d`.
It hashed the launcher, all dashboard assets, the UI
rendering test, and the Python dashboard integration test in that order, using
UTF-8 repository-relative path, NUL, bytes, NUL for each file. Dashboard assets
are sorted by path; the remaining entries follow the order listed here.


## Real project connection

The dashboard is connected to the DocTology repository in read-only project
mode: 41 documents (8 wiki, 23 docs, 8 skill documentation, 2 root documents)
and 53 Markdown links were read through the live local API. Document responses
for the wiki index, current state, loop skill and root README succeeded.
Two additional Python tests verify project mode creates no ingest state and
restricts document reads to the explicit inventory; two JavaScript tests cover
project statistics/relationships and safe relative-link navigation. Full suite:
198 Python tests pass, eight JavaScript rendering contracts pass. Independent
read-only review verified the live projection and found no important defect.
The localhost service was relaunched independently of the terminal session with
an explicit project root; local lifecycle metadata is under ignored state/.
