<p align="center">
  <img src="apps/workbench/public/doctology-logo.jpeg" alt="DocTology logo" width="460">
</p>

# DocTology

[English](README.md) | [한국어](README.ko.md)

DocTology는 **Obsidian-first LLM Wiki 런타임이자 재사용 가능한 스킬팩**입니다.

핵심 계약은 단순합니다.

- 사람은 source를 넣고 질문합니다
- 에이전트는 wiki를 유지합니다
- 스크립트는 source identity, index, provenance를 보존합니다
- ontology와 graph layer는 선택적 support surface이지 제품의 중심이 아닙니다

DocTology의 목적은 LLM이 durable wiki를 읽고, 링크를 따라가고, source-backed evidence를 확인하며, 시간이 지날수록 knowledge base를 더 좋게 유지하도록 만드는 것입니다.

## 이것이 무엇인가

DocTology는 단순한 노트 저장소도 아니고, ontology toolkit만도 아니며, graph 실험 레포만도 아닙니다.

이 프로젝트는 다음 구조의 저장소를 만들기 위한 방식입니다.

- **`raw/`** 는 immutable source material
- **`warehouse/jsonl/`** 은 ontology-backed ingest가 유용할 때 쓰는 canonical structured truth
- **`wiki/`** 는 에이전트가 Obsidian link로 유지하는 human-readable synthesis
- **`AGENTS.md`** 는 미래 에이전트를 위한 repo-local operating contract
- **`intelligence/` YAML** 은 AGENTS, wiki, source evidence보다 아래에 있는 얇은 contract/hint layer

wiki가 주된 읽기와 reasoning surface입니다. YAML은 두 번째 wiki가 아니며 semantic conclusion을 담으면 안 됩니다.

## 누가 써야 하나

다음이 필요하면 DocTology가 맞습니다.

- vector index나 raw context dump가 아니라 실제로 읽을 수 있는 knowledge base
- 반복적인 source ingest와 질문을 통해 자라는 LLM-maintained wiki
- 처음부터 무거운 ontology/graph 인프라를 강제하지 않는 provenance 구조
- bootstrap, ingest, ontology maintenance, operator workflow용 재사용 스킬

![DocTology 워크벤치 질문 작업공간](assets/readme/doctology-workbench-question-workspace.jpg)

_DocTology workbench question workspace — 생성된 wiki, preview, source/graph hint를 읽고 검토하는 선택형 surface입니다._

워크벤치 상태: workbench는 선택형 review surface이며, source of truth나 primary LLM reasoning layer가 아닙니다. Durable synthesis는 repo-local `AGENTS.md` 계약에 따라 wiki에 남아야 합니다.

![참고 예시: 지식이 위키로 자라나는 모습](assets/readme/doctology-reference-obsidian-notes-forming-a-wiki.jpg)

_참고 예시 — 서로 분리되어 있던 Obsidian 노트들이 구조, 링크, neighborhood를 만들며 자라나는 모습입니다._

## 기본 시작 경로

어디서 시작해야 할지 애매하다면 기본 경로는 이렇습니다.

1. wiki-first workspace를 bootstrap
2. source를 `raw/inbox/`에 넣기
3. source page, citation anchor, 선택적 ontology JSONL로 ingest
4. 에이전트가 `AGENTS.md`에 따라 wiki를 유지
5. durable answer는 `wiki/analyses/`에 저장
6. provenance, contradiction handling, 반복 유지보수가 필요해질 때만 ontology, graph, operator workflow 추가

DocTology의 기본 약속은 다음입니다.

- 먼저 readable wiki
- 그다음 source-backed evidence
- 필요할 때 ontology-backed verification
- 마지막에만 graph/operator complexity

## 내가 지금 어느 경로에 있나?

실용적인 구분법은 이렇습니다.

- 새 위키를 만들고 싶다
  - `llm-wiki-bootstrap`
- 새 자료를 넣고 싶다
  - `llm-wiki-ontology-ingest`
- claim, evidence, entity가 맞는지 보고 싶다
  - `lightweight-ontology-core`
- 관계망, 경로, 이웃 탐색을 하고 싶다
  - `lg-ontology`
- 코드레포 docs와 AGENTS 기억을 정리하고 싶다
  - `repo-docs-intelligence-bootstrap`
- 이미 있는 ontology/wiki 산출물을 점검·갱신하고 싶다
  - `ontology-pipeline-operator`

대부분의 사용자는 다음 순서로 시작하면 됩니다.

1. `llm-wiki-bootstrap`
2. 반복적인 `llm-wiki-ontology-ingest`

나머지 스킬은 나중 단계의 정제 또는 선택적 확장 레이어입니다.

## 이미 DocTology repo를 운영 중이라면

1. 먼저 `AGENTS.md`를 읽습니다.
2. 새 source를 `raw/inbox/`에 넣습니다.
3. configured helper LLM ingest를 쓸 수 있으면 `python scripts/llm_full_ingest.py raw/inbox/source.md --apply`를 실행합니다.
4. 추가 검토나 수리가 필요하면 `llm-wiki-ontology-ingest` 또는 직접 에이전트 ingest로 보강합니다.
5. `git diff`를 검토한 뒤 lint/status를 확인합니다.
6. 기존 산출물 점검·갱신이 필요하면 `ontology-pipeline-operator`를 사용합니다.

절차 게이트가 필요한 ingest는 `scripts/wiki_workflow.py`로 source run을 먼저 시작합니다. 대량 source 작업은 `scripts/wiki_batch.py`로 manifest를 고정하고, worker draft를 staging한 뒤 단일 writer로 반영합니다. 이어서 `scripts/pipeline_check.py --strict --batch`와 대표 질문 receipt를 통과해 corpus fingerprint를 인증해야 합니다. 누락되거나 stale한 단계는 완료가 아닙니다.

`scripts/llm_wiki.py ingest`는 registration only입니다. `scripts/llm_full_ingest.py
--apply`는 최소 configured-LLM growth loop입니다: `raw -> register -> source
page -> affected wiki pages -> proposed JSONL -> meta refresh -> ingest report`.
자동 apply는 `raw/` 수정, accepted truth 생성, content 삭제, page rename,
page merge, auto-commit을 하지 않아야 합니다.

자동 graph ingest는 `scripts/wiki_growth_graph.py`를 사용합니다. 이 runtime은
real LangGraph와 configured ingest LLM을 요구하며, deterministic semantic
shortcut으로 fallback하지 않고 실패합니다. 단, 이 strict graph runtime 밖에서
agent가 `AGENTS.md`, wiki map, source page, evidence를 직접 읽어 처리하는 경로는
여전히 유효합니다.

## 어디서 시작할지 먼저 고르세요

### 1) LLM Wiki를 먼저 쓰고 싶나요?

`llm-wiki-bootstrap`으로 시작하세요.

흐름은 단순합니다.

- wiki bootstrap 실행
- 생성된 `raw/inbox/`에 문서 넣기
- source page와 ontology-backed provenance가 필요하면 `llm-wiki-ontology-ingest` 실행
- 에이전트가 먼저 wiki map을 읽고, 그다음 관련 page body와 source citation을 읽어 답변
- durable answer는 `wiki/analyses/`와 관련 concept/entity/person/project page에 반영

시작점은 항상 **wiki-first** 입니다.

### 2) wiki 아래 ontology 구조를 더 강하게 만들고 싶나요?

`lightweight-ontology-core`를 사용하세요.

이 단계는 다음을 위한 것입니다.

- entity
- claim
- evidence link
- segment
- relation vocabulary
- contradiction 또는 supersession handling

ontology layer는 wiki를 보조해야 합니다. 사람이 읽는 reasoning surface인 wiki를 대체하면 안 됩니다.

### 3) graph-style neighborhood 탐색이 필요한가요?

`lg-ontology`를 사용하세요.

이 단계는 선택 사항입니다. Canonical truth는 JSONL에 유지한 채 graph projection, multi-hop inspection, neighborhood/path exploration을 돕습니다.

Graph projection을 canonical truth로 취급하면 안 됩니다.

### 4) 개인 LLM Wiki가 아니라 프로젝트 전용 repo memory가 필요한가요?

`repo-docs-intelligence-bootstrap`을 사용하세요.

이 경로는 다음에 더 맞습니다.

- 코드베이스의 current state 기록
- 에이전트가 읽을 repo-local project memory 생성
- docs, AGENTS, manifests, lightweight intelligence contract 정렬

이것은 wiki bootstrap 위에 무조건 얹는 단계가 아니라, 대체 시작점입니다.

## 주의

**부트스트랩은 하나만 사용하세요.**

여러 부트스트랩을 연속 실행하면 `AGENTS.md`가 덮어쓰기되고 운영 규칙이 흐려질 수 있습니다.

먼저 선택해야 합니다.

- LLM Wiki를 키우고 싶은가?
- 아니면 repo-focused intelligence / project memory를 만들고 싶은가?

둘 다 중요하지만 첫 bootstrap은 하나의 명확한 선택이어야 합니다.

## 핵심 skill 경로

Canonical repo-local skillset은 `.agents/skills/` 아래에 있습니다. `~/.codex/skills` 아래 installed copy는 로컬 설치본일 뿐입니다.

- `.agents/skills/llm-wiki-bootstrap`
  - Obsidian-first LLM Wiki 시작
- `.agents/skills/llm-wiki-ontology-ingest`
  - inbox 문서를 ontology-backed wiki로 ingest
- `.agents/skills/lightweight-ontology-core`
  - wiki 아래 canonical ontology truth 정리
- `.agents/skills/lg-ontology`
  - ontology graph / neighborhood exploration 확장
- `.agents/skills/repo-docs-intelligence-bootstrap`
  - project-specific memory / repo intelligence bootstrap
- `.agents/skills/ontology-pipeline-operator`
  - 기존 ontology/wiki artifact와 반복 유지보수 flow refresh

## 운영 모델

DocTology의 핵심 모델은 의도적으로 작습니다.

```text
raw source
  ↓
source page and optional ontology JSONL
  ↓
LLM-maintained wiki pages
  ↓
saved analyses and cross-links
  ↓
better future answers
```

역할 구분:

- deterministic script는 source 등록, stable ID, index refresh, basic validation을 담당
- LLM agent는 wiki, source page, 관련 ontology evidence를 읽고 semantic synthesis를 수행
- 사람은 broad rewrite, 민감한 accepted claim, contradiction, 큰 ontology 변경을 검토
- 파이프라인은 의미 판단을 닫는 것이 아니라, 산출물 생명주기를 닫습니다.

이 구조는 Karpathy식 LLM Wiki에 가깝습니다. LLM은 top-k chunk만 받는 것이 아니라 구조화되고 링크된 knowledge base를 읽습니다.

## YAML contract layer

YAML은 유용하지만 하위 계층입니다.

여기에는 서로 다른 두 우선순위 축이 있습니다.

Truth / provenance 우선순위:

1. `raw/` source material
2. ontology-backed ingest가 있을 때 `warehouse/jsonl/` canonical structured truth
3. source-backed wiki page와 citation
4. derived graph/retrieval/workbench preview

운영 지침 우선순위:

1. repo-local `AGENTS.md`
2. `wiki/_meta/index.md`와 최근 `wiki/_meta/log.md`
3. `intelligence/` YAML contract와 hint

YAML은 vocabulary, dataset boundary, profile, validation hint를 정의할 수 있습니다. 하지만 두 번째 semantic wiki나 deterministic reasoning engine이 되면 안 됩니다.

## Helper LLM

`wikiconfig.json`은 로컬 전용 설정 파일입니다. 커밋되는 템플릿은 `wikiconfig.example.json`입니다.

Helper LLM은 경계가 분명한 작업을 빠르게 처리하는 선택적 accelerator입니다. Helper LLM이 꺼져 있거나 없으면 주변 chat agent가 직접 다음을 읽고 semantic work를 수행할 수 있습니다.

- `AGENTS.md`
- `wiki/_meta/index.md`
- 관련 wiki page
- source page
- 필요 시 `warehouse/jsonl/` evidence

즉 helper LLM은 main agent-maintained wiki loop를 대체하지 않습니다.

Semantic no-fallback 원칙: helper/configured LLM 호출이 실패하면 해당 단계는 failed, partial, pending으로 보고합니다. deterministic fallback 문장을 대신 넣고 full ingest 완료라고 부르면 안 됩니다.

로컬 helper 설정은 먼저 probe로 확인합니다.

```bash
python scripts/helper_llm.py --root . --check-config
python scripts/helper_llm.py --root . --probe-chat
python scripts/helper_llm.py --root . --probe-embedding
```

가장 단순한 full growth loop는 `scripts/llm_wiki.py ingest`를 registration-only로 유지한 채 다음 runner를 사용합니다.

```bash
python scripts/llm_full_ingest.py raw/inbox/example.md --mode dry_run
python scripts/llm_full_ingest.py raw/inbox/example.md --apply
python scripts/wiki_growth_graph.py check --source raw/inbox/example.md
```

strict LangGraph source-page runtime은 graph-runtime 디버깅용으로 계속 사용할 수 있습니다.

```bash
python scripts/wiki_growth_graph.py ingest raw/inbox/example.md --mode draft
python scripts/wiki_growth_graph.py ingest raw/inbox/example.md --mode apply-source-page
```

`--apply`는 source page 완성, affected wiki page 생성/append, proposed JSONL
기록, index/log 갱신, ingest report 작성을 수행합니다. Accepted-claim
promotion은 계속 review-gated입니다.

나중에 질문 과정에서 raw/source fallback이나 wiki 보완이 필요했다면,
semantic heuristic을 추가하지 않고 trace만 기록합니다.

```bash
python scripts/llm_wiki.py answer-receipt "Question text" \
  --used-wiki wiki/_meta/index.md \
  --used-raw raw/inbox/example.md \
  --wiki-update wiki/analyses/example.md
```

Answer receipt는 context receipt이지 answer generator나 page-selection rule이
아닙니다. 무엇을 읽고 답을 어떻게 해석할지는 여전히 agent가 판단합니다.

## Reference runtime에 대해

로컬 runtime은 reference implementation이지 제품 전체가 아닙니다.

유용한 entrypoint:

- `scripts/llm_wiki.py` — source registration, answer receipt, indexing, lint, status check
- `scripts/helper_llm.py` — 로컬 `wikiconfig.json` probe와 OpenAI-compatible helper 호출
- `scripts/wiki_growth_graph.py` — strict LangGraph source-page growth runtime
- `scripts/pipeline_check.py` — pending-aware structural route check
- `scripts/wiki_workflow.py` — 고정 단계 source 절차 완료 및 stale review 검증
- `scripts/wiki_batch.py` — 불변 batch 계획, 단일 writer 반영, corpus fingerprint 및 대표 질문 인증
- `scripts/llm_full_ingest.py` — configured-LLM full growth dry-run/apply
- `scripts/incremental_ingest.py` — 반복 export-style ingest path
- `scripts/workbench_api.py` — local workbench adapter용 compatibility shell
- `apps/workbench/` — 선택형 GUI/read-review surface

이 저장소의 핵심은 다음 운영 방식입니다.

> readable source-backed wiki를 만들고, agent가 유지하게 하며, reasoning quality와 provenance가 좋아질 때만 ontology/graph machinery를 추가한다.

## 부록: 스킬 호출 원칙

스킬은 보조 도구입니다. DocTology의 중심은 여전히 다음입니다.

- `AGENTS.md`
- `wiki/`
- `raw/`
- `warehouse/jsonl/`

스킬을 사용할 때는 repo-local contract를 명시하는 것이 좋습니다.

```text
Use <skill-name>.
Follow the repo-local AGENTS.md.
Do not replace the wiki with YAML or graph outputs.
Keep wiki/ as the human-facing synthesis surface.
```

예시:

```text
Use llm-wiki-ontology-ingest.
Follow the repo-local AGENTS.md.
Process sources from raw/inbox.
Update source pages, affected concept/project pages, and JSONL provenance when useful.
Refresh wiki/_meta/index.md and wiki/_meta/log.md.
```
