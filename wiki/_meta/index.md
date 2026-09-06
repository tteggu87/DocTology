---
title: DocTology repository memory
type: meta
status: active
updated: 2026-09-06
---

# Repository memory index

Canonical reading starts at the [documentation portal](../../docs/README.md), [current state](../../docs/CURRENT_STATE.md), and [repository map](../../docs/repo-map/README.md).

This wiki is derived repository memory. It contains no personal corpus and does not override code, tests, `AGENTS.md`, or current docs.

Current structural evidence is indexed from the [documentation portal](../../docs/README.md); this repository keeps the reusable SQLite absorption record canonical under `docs/evidence/` rather than duplicating it as an ignored local analysis page.

Current decision memory includes [LLM Wiki loop runtime ownership](../decisions/loop-runtime-ownership.md), backed by [ADR-0001](../../docs/adr/ADR-0001-loop-runtime-ownership.md).

## Wiki Studio 작업 이어받기

[대시보드 배경·설계 이유·구현·검증 범위·다음 판단](../decisions/local-wiki-studio.md)부터
읽고, 연결된 ADR과 검증 기록을 확인한다. 대화·감시·병렬 준비·폴더 선택·검색 관측·리팩토링을 무엇을·어떻게·왜 했는지와 재발 방지 원칙을 정리했다. 현재 프로젝트 문서 읽기 모드와 별도 LLM Wiki의 원문 작업 모드를 구분한다.
