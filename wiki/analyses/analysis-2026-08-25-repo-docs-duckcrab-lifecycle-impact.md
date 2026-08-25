---
title: Repo Docs DuckCrab lifecycle 최종 영향 보고서
type: analysis
status: active
created: 2026-08-25
updated: 2026-08-25
tags:
  - repo-docs
  - compatibility
  - dogfood
sources: []
---

# Repo Docs DuckCrab lifecycle 최종 영향 보고서

## 결론

[[analysis-2026-08-25-repo-docs-duckcrab-lifecycle-absorption-plan]]의 범용
문서 lifecycle을 하나의 완전한 Repo Docs 프로필로 구현했다. Repo Docs를 선택하면
canonical docs, intelligence, repo-map, wiki memory와 함께 ADR·plan·evidence·review·archive·
wiki decision 역할 폴더와 README 골격을 항상 만든다. 실제 기록은 의미가 있을 때만 만들며,
기존 평면 ADR·plan과 성숙한 evidence·review·decision 폴더는 이동·키 변경·일괄
frontmatter 변환 없이 호환한다.

## 흡수한 범용 패턴

- code/tests → current docs/ADR → intelligence → plan/evidence/review → derived wiki → derived retrieval의 권위 순서
- 전체 역할 폴더 골격과 위험·재사용성 기반 실제 기록 생성의 분리
- 결정 상태와 구현 상태의 분리
- 구현·검증 근거가 있는 완료 주장과 stale plan 차단
- 파생 SQLite FTS/link index의 기본 제공·재생성 가능·비정본 경계
- 별도 activation 표식 없는 portable frontmatter 검증과 읽기 전용 호환성 dogfood

## 의도적으로 제외한 동작

- 특정 도메인의 BUILD/ASK/CHECK, Pack, MCP, ontology 용어와 절차
- 기존 문서 위치, manifest key, 상태 vocabulary의 자동 migration
- 새 canonical database, JSONL ontology, workflow engine, ONNX, RRF, ANN
- 빈 placeholder ADR/plan/evidence/review/decision을 자동 생성하는 방식
- 검색 결과를 truth 또는 validator 판정으로 승격하는 방식

## 변경된 표면

- `.agents/skills/repo-docs-intelligence-bootstrap/SKILL.md`
- lifecycle record template 5종과 역할 README template 7종
- `validate_repo_docs_intelligence.py`의 완전 프로필 골격·Markdown-link·portable lifecycle 검증
- `repo_docs_dogfood.py` 읽기 전용 inventory runner
- validator/dogfood compatibility tests
- 이 영향 보고서와 `wiki/_meta/index.md`, `wiki/_meta/log.md`

## 확인했지만 변경하지 않은 표면

- DuckCrab code, tests, `AGENTS.md`, canonical docs, intelligence, repo-map, wiki 전체
- DocTology `raw/`, `warehouse/jsonl/`, ingest runtime, wiki retrieval runtime
- 기존 eval fixture의 manifest keys와 DuckCrab flat/custom 문서 위치
- repo-docs retrieval schema와 FTS ranking behavior

## DuckCrab read-only dogfood

대상은 `/Users/hoyasung007hotmail.com/Documents/my_project/duckcrab`이며 실행 전후
관련 파일 fingerprint가 동일했다.

- canonical docs: 7/7
- flat ADR: 7
- implementation plan: 17
- evidence: 69
- review: 25
- repo-map: 5
- wiki decision: 34
- required surface missing: 0
- compatibility surface validation: PASS, issues 0
- repository-wide path/type/content fingerprint: unchanged (all regular files content-bound)
- dogfood runner: `passed_with_cautions`, `read_only=true`

Validator는 호환성 강제 오류 없이 DuckCrab 자체 drift만 보고했다. Dogfood는 기본적으로
validator 오류를 실패 처리한다. 이번 read-only 인증에서는 정확히
`wiki.broken_markdown_link`만 `--allow-validator-error-code`로 명시해 caution으로
수용했으며, 다른 오류 코드가 하나라도 나타나면 전체 dogfood가 실패한다.

- error 34: 실제로 해소되지 않는 `wiki.broken_markdown_link`
- warning 3: repo-map의 등록 entrypoint 가시성 부족
- warning 1: read-only dogfood에서 changed-file 입력을 생략해 drift suspicion 검사가 제한됨

## 검증 결과

- focused pytest: 46 passed
- full pytest: 198 passed, 26 subtests passed
- dependency-light unittest: validator 34, dogfood 4, retrieval 8 passed
- Ruff: all checks passed
- skill quick validation: valid
- Python compile: passed
- mature eval fixture validation: passed, errors 0, expected advisory warning 1
- DuckCrab required-surface dogfood: `passed_with_cautions`; inventory와 compatibility
  surface validation은 통과했고, 명시적으로 허용한 broken-link drift만 별도 보고
- `python -S`로 YAML manifest fixture를 직접 검증한 시도는 PyYAML 부재로 실패했으며,
  정상 interpreter fixture validation과 YAML 없는 dependency-light suites로 경계를 재검증했다.
- first independent code review: Critical 0, Important 4; false-pass, inventory-only,
  partial fingerprint, excluded report 문제를 모두 수정
- corrective fixed-profile review: Critical 0, Important 2; both scaffold/identity
  boundary findings fixed with regression tests
- final independent re-review: Critical 0, Important 0, Minor 0; CLEAN

## 남은 주의사항

- DuckCrab의 끊어진 wiki Markdown 링크 34건과 repo-map entrypoint 경고 3건은 이번
  read-only 범위에서 수정하지 않았다.
- legacy artifact는 이동시키지 않는다. 새 표준 lifecycle 검증 대상으로 작성하거나
  실질적으로 갱신할 때만 `type`, identity, status, reference 같은 portable field를 채운다.
- SQLite retrieval script는 프로필에 포함되지만 DB는 파생 캐시다. DB가 없거나 stale이어도
  canonical docs의 진실성과 validator 완료 여부는 바뀌지 않는다.
