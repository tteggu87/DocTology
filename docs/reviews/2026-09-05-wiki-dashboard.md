---
title: Wiki Studio 독립 리뷰와 수정 결과
type: review
review_id: REVIEW-2026-09-05-WIKI-DASHBOARD
status: resolved
date: 2026-09-05
source_of_truth: false
reviewed_target: dashboard additions on base d791a9767accc10bfaf194b4b1f93f299b860246
target_fingerprint: sha256:7129981a076db648072afaadbf9d9017d764eb096900c42193f59848761e13ac
related_decisions:
  - ../adr/ADR-0002-local-wiki-dashboard.md
evidence_refs:
  - ../evidence/2026-09-05-wiki-dashboard.md
---

# Wiki Studio 독립 리뷰와 수정 결과

## Independent reader and writer review

A scoped reviewer inspected launch, cancellation, shared locks, automation, and
citation freshness. Its initial concern that concurrent mutation would silently
fail chat was retracted after tracing the explicit live-read contract and terminal
invalidation behavior. No concrete blocker remained in the inspected paths. A
new deterministic subprocess regression verifies mutation between read and settle:
chat finishes, flags stale evidence, and drops obsolete references while the writer
stays alive. Parallel semantic source building is not implemented or claimed.
A blind guide read raised general environment/recovery prerequisites, not a
concurrency-contract blocker; the guide names those prerequisites and boundaries.

## Reader and chat scroll review

A separate scoped reviewer checked the fixed reader header, independent body
scrolling, top/bottom controls, observer/event handling, accessibility, and focused
UI tests. No material regression was found. Live browser checks confirmed both
chat endpoints and that X closes the reader from the document bottom; see
[current evidence](../evidence/2026-09-05-wiki-dashboard.md).

## Agentic chat review

An independent integration reader reviewed the main adapter, read-only bridge,
Pi extension, UI, and focused tests. All four material findings were repaired
and independently rechecked:

- In-flight tool I/O blocked cancellation. Separate operation/state locks,
  immediate revocation, and asynchronous shutdown preserve stop and status access.
- Changed evidence survived as a valid citation. Terminal hash/inventory checks
  invalidate stale reads, and citation opening rejects mismatched current bytes.
- A transient poll failure discarded a live job. Bounded retries retain its
  identity, reconnect and stop controls; only confirmed missing/root mismatch
  clears it. Manual stop also retrieves the terminal state after polling pauses.
- Post-stop evidence validation delayed `stopped`. Cancelled validation discards
  cached citations without filesystem/helper I/O; focused reproductions verify it.

The final affected-path review reported no remaining material blocker. Parent
integration checks repaired wrapped HTTP results and budget errors, preserved
read content during response bounding, and hardened inventory/offset behavior.
Actual browser review then fixed disclosure rerender loss and compressed citation
cards. A blind complete usage-guide read found minor prerequisite and recovery
assumptions; the guide now links the loop contract and explains budget recovery.
These checks are bounded engineering evidence, not a semantic-quality benchmark
or complete security audit. See [current verification](../evidence/2026-09-05-wiki-dashboard.md).

## Source-entry follow-up review

Independent read-only integration review found and confirmed repairs for:

- OFF or changed-folder configuration could still authorize old queued work.
  Auto dispatch now requires enabled state and matching folder generation.
- Writer contention became a terminal failure, while the displayed retry failed.
  Contention stays pending; explicit retries validate the current source and runner.
- A surviving Pi could outlive its dashboard's lease. Active persisted runners
  now exclude new execution, upload, save, and external import under writer locks.
- Raw publication followed by failed queue handoff lost structured recovery data.
  HTTP 409 carries the saved path, and the UI retries the exact preview.
- Stale completion could remain falsely green or never recover. Reconciliation
  demotes stale gates, restores passing current gates, and avoids redundant models.
- The newest 100 queue rows could hide other actionable work. Bounded previous/next
  pages expose all rows while preserving total counts and dirty form inputs.

Additional parent/UI checks repaired dormant-worker writes, dropped conversation
handling instructions, refresh-erased settings, commit/close races, and a clipped
approval footer. Focused regressions, final suite counts, and real source-cycle
observations are in [current evidence](../evidence/2026-09-05-wiki-dashboard.md).
The independent final pass verified gate restoration and pagination as repaired.

Native chat attestation was not added: browser records are deliberately labelled
`client_supplied_unverified`, including their limits in the raw Markdown. This is
an explicit provenance limitation, not a claim that local history is authenticated.
The review does not establish model quality or a complete security audit.

## Chat-first follow-up review

A separate read-only reviewer inspected the chat server, frontend and tests.
Four concrete findings were repaired before handoff:

- Historical numeric citations could collide with current candidate numbers.
  Historical assistant markers are stripped before prompting; only current-turn
  evidence numbers are valid.
- Conversation switching during startup could discard a live process handle.
  New conversation, switching and history clearing are guarded during generation.
- A slow document response could appear after changing roots. Reader requests
  carry expected-root identity; root changes invalidate and close pending readers.
- Output and browser history were unbounded. Server output and stored history
  now have independent caps with visible failure/truncation reporting.

The focused regressions and latest browser evidence are recorded in
[verification](../evidence/2026-09-05-wiki-dashboard.md). Browser follow-up also
repaired desktop panel visibility, partial answer display, graph zoom, old-turn
citation clicks, and graph layout stability. The initial review fingerprint was
`sha256:7bda4a98b9a1bd6a31f1d7fdde11dc87cce5e274c6177739f421baba828eba3d`.
The frontmatter and current verification identify the latest delivery.

## Initial review scope (historical)

2026-09-05 대화의 독립 `dashboard_review` 작업자가 새 로컬 대시보드의
Pi RPC 제어·위키 완료 판정·파일 접근 경계를 읽기 전용으로 검토했다.
아래는 당시 리뷰 메시지와 수정 결과를 인수인계용으로 보존한 기록이다.
새로운 브라우저 QA나 별도의 모델 합성 실험을 수행한 기록은 아니다.
구현 대상의 내용 해시는 [검증 기록](../evidence/2026-09-05-wiki-dashboard.md)에 있다.

## Findings

| 심각도 | 발견 사항 | 수용한 수정 | 회귀 검사 |
| --- | --- | --- | --- |
| P1 | `agent_end`는 재시도·압축·대기 작업 전에도 발생해 프로세스가 조기 종료됨 | `agent_settled`까지 기다리고 일시적 모델 오류는 재시도 결과와 함께 판단 | `test_rpc_waits_through_agent_end_and_retry_until_settled` |
| P2 | 설치된 Pi에서 `clear_queue`가 Unknown command를 반환하여 정상 중단이 실패로 처리됨 | 지원하는 `abort` 사용 | `test_steer_stop_and_duplicate_writer_lock` |
| P2 | 원문 경로만으로 과거 배치를 모두 묶으면 옛 stale 배치가 새 run의 완료를 막음 | 현재 run_id에 연결된 배치만 완료 판정에 사용 | `test_current_run_is_not_blocked_by_unrelated_historical_batch`, `test_linked_batch_must_be_certified_before_done` |
| P2 | `completed_stages`는 실패 결과가 기록된 단계도 포함하는데 UI가 성공으로 표시함 | `STRUCTURAL_VALIDATION_FAILED`를 확인해 해당 단계를 실패로 표시 | UI의 `failed structural validation is never rendered as a successful step` |

## Disposition

네 항목 모두 수용·수정했다. 후속 읽기 리뷰에서 수정 확인과 추가 P0/P1/P2
결함 없음이 보고됐다. 이후 프로젝트 읽기 모드도 추가 검토했으며,
실제 저장소 투영 결과 41개 문서·53개 연결, 문서 목록에 제한된 조회,
서버 측 변경 동작 차단을 확인하고 중요한 추가 결함을 보고하지 않았다.

리뷰 승인은 읽은 코드와 확인한 RPC/API 범위의 판단이다. 보안 완전성,
모든 Pi 버전과의 호환성, 브라우저 사용성 또는 위키 합성 품질을 보증하지 않는다.

## Verification

- [Python 회귀 테스트](../../tests/test_wiki_dashboard.py)
- [UI 렌더링 계약](../../.agents/skills/llm-wiki-loop/evals/dashboard_ui.test.cjs)
- [검증 명령·환경·미검증 범위](../evidence/2026-09-05-wiki-dashboard.md)
- [다음 작업자 인수인계](../../wiki/decisions/local-wiki-studio.md)
