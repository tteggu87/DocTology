---
title: DocTology maintenance log
type: meta
status: active
updated: 2026-09-06
---

# Maintenance log

- 2026-09-05: Interpreted the reported blocked new chat as a request to separate read-only chat from wiki writes, not to remove writer serialization. Removed cross-lane exclusion, preserved root/writer boundaries, and verified separate stops plus concurrent document mutation. A real Pi read completed alongside a held fixture writer. Multiple semantic source-card builders remain a separate, unimplemented expansion requested for consideration. See [evidence](../../docs/evidence/2026-09-05-wiki-dashboard.md).

- 2026-09-05: Fixed reader scrolling so its title and close button remain visible while only the body scrolls. Added non-overlapping chat top/bottom controls with overflow and endpoint states, reduced-motion support, and independent reader reset. Scoped review, regression tests, and actual end-to-end scrolling passed; see [evidence](../../docs/evidence/2026-09-05-wiki-dashboard.md).

- 2026-09-05: Implemented read-only agentic Pi chat with an authenticated
  loopback handshake, ambient model selection, four scoped exploration tools,
  actual-read citations, and visible budgets/activity. Independent review repaired
  cancellation, post-stop validation, stale citations, and lost polling handles;
  browser QA repaired disclosure state and compressed reference cards. Actual Pi
  answered a linked-document fixture and the user wiki's generic summary query
  without target writes. General shell/write/web tools remain absent, and
  watch/save opt-ins plus existing loop gates are unchanged. Final checks and
  limits are in [evidence](../../docs/evidence/2026-09-05-wiki-dashboard.md).

- 2026-09-05: Documented Wiki Studio’s opt-in Markdown watcher, sequential queue,
  and explicit conversation-to-unverified-raw save path. Watching and `autoRun`
  stay separate; external files are snapshotted without source mutation, while
  all compilation and completion still use the existing full-coverage gates.
  Regression coverage includes disabled dispatch, stale/restored completion,
  cross-dashboard contention, surviving runners, explicit retry, preview recovery,
  and bounded queue pages. Live integration and its limits are recorded in
  [evidence](../../docs/evidence/2026-09-05-wiki-dashboard.md); see
  [usage](../../dashboard/README.md) for operation.

- 2026-09-05: Reoriented Wiki Studio around conversation, with workspace/history
  on the left and answer-cited graph/reference navigation on the right. Added
  bounded no-tools Pi chat, current-turn citation mapping, root-bound document
  reads and verified raw-source navigation. Browser history is not wiki truth.
  Existing ingest gates and kanban remain separate. GPT chat and reference
  opening were exercised against a real local wiki; raw navigation was checked
  in an isolated fixture. See [verification](../../docs/evidence/2026-09-05-wiki-dashboard.md).

- 2026-09-05: Preserved the complete Wiki Studio handoff in
  [decision memory](../decisions/local-wiki-studio.md), covering the user intent,
  why Pi RPC and existing gates were chosen, the project/ingest mode distinction,
  implementation surfaces, verified versus unverified behavior, and next checks.
  Recorded four resolved findings in the [review](../../docs/reviews/2026-09-05-wiki-dashboard.md).
  Bounded reading route: AGENTS → docs portal → current state → wiki index/log
  → ADR-0002 → dashboard verification. No runtime, model call, or global install
  changed in this documentation-only pass.

- 2026-09-05: Connected the real DocTology project wiki through a read-only
  dashboard mode that includes wiki meta pages, docs, and skill references.
  Added inbound/outbound document links, full document inventory, relative-link
  navigation, and tests proving project mode cannot create ingest state.

- 2026-09-05: Added the optional loop-owned local Wiki Studio with a light
  kanban, Markdown link graph, source coverage, verification details, and Pi RPC
  start/steer/abort controls. Existing gates remain the completion authority.
  Added focused integration and rendering tests; independent review corrected
  settlement/cancellation protocol and historical-batch/failed-validation display.
  See [verification](../../docs/evidence/2026-09-05-wiki-dashboard.md).

- 2026-09-01: Hardened batch discovery so malformed source metadata or
  timestamps invalidate one manifest without interrupting the remaining list.
- 2026-09-01: Added lightweight read-only batch discovery. `batch list` supports
  bounded and active-only listings, summarizes source progress, surfaces invalid
  manifests, and marks freshness unchecked so agents run exact status before
  acting instead of repeating corpus hashes across every recorded batch.
- 2026-09-01: Improved batch workflow discovery without adding orchestration.
  Public help now shows the complete multi-source sequence and explains each
  subcommand; read-only batch status returns a deterministic advisory
  `next_action` for normal progress, handoff, interruption, stale state, and
  completion.
- 2026-09-01: Closed the multi-source direct-certification bypass. More than
  one non-deferred source now requires a current seal event covering the exact
  linked run set, while single-source direct certification remains compatible;
  a completed two-source no-seal regression guards the boundary.
- 2026-09-01: Added a multi-source batch snapshot seal to eliminate cascading
  source-run staleness. Linked runs now stop at the pre-mutation boundary while
  drafts remain under `state/`; one writer applies the merged wiki update, then
  a state-only review binds every source run to the unchanged batch corpus
  fingerprint, shares one retrieval refresh, and certifies immediately. Seal
  fails closed on post-apply mutation or incomplete source/question evidence;
  prepared run payloads make interrupted state commits resumable and stale
  attempts restore the original run records.
- 2026-09-01: Added `raw_retrieval.py rebuild --exact` so checksum-stale raw
  Markdown structure can recover even when content changes preserve file size
  and mtime. Ordinary rebuild remains stat-incremental.
- 2026-09-01: Added deterministic raw Markdown heading-tree navigation to the
  disposable SQLite index and documented its boundary across bootstrap and loop
  skills. Generated vaults expose `tree`, `ancestors`, and `subtree` only as
  checksum-checked planning aids; canonical Markdown reopening and the existing
  coverage receipt remain authoritative, with direct reading as the off,
  unavailable, or stale fallback.
- 2026-08-27: Moved the LLM Wiki procedure, batch, and structural gate runtime
  into `llm-wiki-loop`. Fresh bootstrap vaults retain the base wiki and optional
  SQLite only; certified ingest runs the skill-local runtime through
  `--repo-root` and writes only bounded state, receipts, and wiki changes. The
  invocation contract now anchors `wiki_loop.py` to the loaded skill directory,
  preventing project or global installs from resolving it inside the target
  repository by mistake. Exact `--repo-root` validation and nested `--root`
  rejection also prevent a child runtime from redirecting work to another
  repository after preflight. The public entrypoint now forwards lane and
  nested-command help to the skill-local parsers, so agents can discover CLI
  arguments without reading runtime code or requiring a valid target. Help
  retains the public `wiki_loop.py <lane>` name and hides the internal root
  transport option.
- 2026-08-26: Restored the original cropped DocTology logo and rewrote the root
  README around the human-facing Obsidian LLM Wiki, agent-facing Repo Docs,
  deterministic gates, optional SQLite, and copyable skill-first workflows.
  The removed workbench remains archived in Git history.
- 2026-08-26: Added explicit wiki-first raw fallback. Default wiki search is
  unchanged; `--raw-fallback` queries the separate raw lane only after a wiki
  lexical miss and remains non-fatal when raw derived state is unavailable.
- 2026-08-26: Added an independent raw Markdown lexical index to generated
  SQLite-enabled vaults. Incremental rebuilds update added/changed/removed files;
  search reopens canonical byte ranges, while stat status and exact doctor stay
  separate. Raw vectors and blended ranking remain intentionally absent.
- 2026-08-26: Made coverage-preserving ingest the default generated contract.
  Short ingest requests now compile to `full` heading/bounded-chunk accounting;
  `summary` requires explicit intent. Full final review must reference one
  applied source-hash receipt with balanced counts and zero deferred units.
- 2026-08-26: Made generated `wiki_workflow.py` process locks portable. Unix
  keeps `fcntl.flock`; Windows now uses the standard-library `msvcrt.locking`
  backend, locks byte zero directly without a first-use write race, and closes
  the acquired descriptor if claim persistence fails. Workflow startup and
  refresh serialization require no extra package.
- 2026-08-26: Applied the proven SQLite lifecycle split to the generated LLM
  Wiki implementation without importing Repo Docs-specific wrappers or trigram
  policy. Lexical/link discovery now opens one structural connection and marks
  candidates `freshness: unchecked`; `status` stays stat-based and `doctor`
  stays exact. Rebuilds stream page bodies and prior vector BLOBs, correct peer
  heading paths, preserve compatible ONNX vectors in bounded batches, and check
  an exact streamed fingerprint immediately before publication.
- 2026-08-26: Absorbed DuckCrab's derived Repo Docs SQLite fast-path into the
  canonical skill. Kept stat status, exact doctor, unchecked search/traversal,
  one-connection batch search, native shared-SQL adapters, and optional trigram
  discovery. Corrected long-document result starvation, raw FTS operator input,
  native failure exits, and rebuild publication-time drift detection; added
  `--no-trigram` as the only large-corpus storage switch. Independent review then
  corrected inclusive line ranges, normalized native error exits, removed
  quadratic line scans, and changed rebuild to document-streamed insertion plus
  a streamed final fingerprint. Focused 23/23 and full 135/135 tests passed;
  Windows PowerShell runtime dogfood remains unverified.
- 2026-08-25: Corrected generated wiki lint orphan detection. `_meta` navigation and self-links no longer count as inbound semantic links; `--strict-orphans` optionally turns orphan findings into a failing exit status.
- 2026-08-25: Reduced DocTology to three public skills. Moved the prior local workspace to a checksum-verified sibling legacy vault; removed active ontology, workbench, duplicated runtimes, and tracked archive surfaces; added one distribution manager and focused verification. Independent review also aligned the bootstrap command with `~/.codex/skills`, made clean-checkout validation warning-free, and hardened replacement of file and symlink destinations.

- 2026-09-06: Completed Wiki Studio parallel preparation within the existing batch procedure. The clean fixture proved concurrent first-attempt preparation, then correctly stopped at a missing-index-link gate. Its original batch remains blocked and unsealed; a new existing-runtime batch repaired only the two required index links and certified through the ordinary seal. No LangGraph, new completion authority, or multiple canonical writer was added. See the [implemented ADR](../../docs/adr/ADR-0003-wiki-parallel-preparation.md), [completed plan](../../docs/plans/2026-09-05-wiki-parallel-preparation.md), [verification](../../docs/evidence/2026-09-06-wiki-parallel-preparation.md), and [accepted review](../../docs/reviews/2026-09-06-wiki-parallel-preparation.md).

- 2026-09-06: Interpreted local-wiki connection feedback as choosing an existing folder without typing, not uploading a directory or creating a wiki. Added native selection plus a bounded in-app fallback for restricted desktop environments. Verified click-only connection with existing guards and unchanged user files; see [folder selection evidence](../../docs/evidence/2026-09-06-wiki-folder-picker.md). No administrator or security-policy changes were made.

- 2026-09-06: Added Wiki Studio retrieval observability without changing retrieval routing. Workspace status separates SQLite configuration/stat freshness, ONNX environment/artifact presence, and stored vector rows. Per-answer percentages count successful discovery calls, not evidence contribution; old missing telemetry remains unknown. A real-index fixture and actual tool-bridge calls verified the UI and persistence without user-vault test data. See [verification](../../docs/evidence/2026-09-06-wiki-retrieval-observability.md).

- 2026-09-06: Refactored Wiki Studio behind its existing behavior: injected document catalog, folder helpers, and HTTP transport; explicit-input frontend factories and one external bootstrap. HTML owns script order and asset admission. Module-only rendering tests caught hidden app globals before release. Existing retry tests now wait for actual cleanup eligibility rather than terminal labels alone. No writer or completion gate was changed. See [maintenance boundaries](../../dashboard/README.md#유지보수와-확장-경계).

- 2026-09-06: 사용자 요청에 따라 Wiki Studio 전체 작업을 하나의 [최신 인수인계](../decisions/local-wiki-studio.md)로 정리했다. 무엇을·어떻게·왜 했는지, 보류한 대안, 구현 경계, 리뷰에서 잡은 오류, 단계별 검증과 한계를 정본 근거에 연결했다. 초기 관측 수치와 최신 상태를 분리하고 커밋 전 소스·테스트·문서 전체를 검증하는 배포 범위를 명시했다. 사용자 코퍼스·브라우저 대화·실행 state는 Git 대상에서 제외한다.

- 2026-09-06: 더블클릭용 루트 `Wiki-Studio.command` / `Wiki-Studio.bat`와 스킬 소유 실행기를 추가했다. Python 3.11 확인 후 기존 서버를 예시 모드로 열고, 브라우저·포트 자동 선택은 명시적 CLI 옵션으로 재사용한다. 현재 작업 디렉터리와 무관하게 실행하며 기존 서비스·사용자 파일·설정은 변경하지 않는다. macOS 셸의 실제 HTTP 시작과 Ctrl+C 종료, Windows 정적 계약을 구분해 검증했다. 위치와 실행법은 [실행 안내](../../dashboard/README.md#더블클릭으로-실행)에 정리했다.

- 2026-09-06: Recorded the user-approved Studio ownership migration in [ADR-0004](../../docs/adr/ADR-0004-studio-runtime-separation.md). Current documentation now assigns the application backend and launchers to `runtime/`, UI to `dashboard/`, and Studio JavaScript evaluations to `tests/dashboard/`; `llm-wiki-loop` retains only reusable gates through `runtime/wiki_loop_adapter.py`. This record is documentation-only and **not verified yet**. Earlier test counts, fingerprints, commands, and skill-relative paths remain historical observations of the previous layout; verification belongs in the new migration evidence record.

- 2026-09-06: Recorded the user-approved Studio ownership migration in [ADR-0004](../../docs/adr/ADR-0004-studio-runtime-separation.md). Current documentation assigns the application backend and launchers to `runtime/`, UI to `dashboard/`, and Studio JavaScript evaluations to `tests/dashboard/`; `llm-wiki-loop` retains only reusable gates through `runtime/wiki_loop_adapter.py`. This record is documentation-only and **not verified yet**. Earlier test counts, fingerprints, commands, and skill-relative paths remain historical observations of the previous layout; verification belongs in the new migration evidence record.

- 2026-09-06: [ADR-0004](../../docs/adr/ADR-0004-studio-runtime-separation.md)의 소유권 분리를 구현·검증했다. 앱은 `runtime/`·`dashboard/`, JS 검사는 `tests/dashboard/`, 게이트는 독립 루프 스킬에 남는다. Python 402·JavaScript 134 검사와 임시 설치본의 독립 loop CLI, 실제 루트 실행기·브라우저를 확인했다. 게이트 구현 4개·사용자 위키 24개 파일과 대화 2개를 보존했다. 핵심 교훈은 “게이트 호출”과 “앱 소유권”을 혼동하지 않는 것이다. 세부 범위는 [검증 기록](../../docs/evidence/2026-09-06-studio-runtime-separation.md)을 따른다.
