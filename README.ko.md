# DocTology

DocTology는 아래 세 가지 에이전트 스킬만 배포하는 작은 저장소입니다.

| 스킬 | 역할 |
| --- | --- |
| `llm-wiki-bootstrap` | Obsidian 우선 Markdown 위키를 만들고 선택적으로 파생 SQLite 검색을 설치합니다. |
| `llm-wiki-loop` | 의미 판단과 절차 게이트를 거쳐 기존 위키를 성장·검증합니다. |
| `repo-docs-intelligence-bootstrap` | 코드와 저장소 문서·계약·장기 작업 기억을 맞춥니다. |

활성 온톨로지 프로필, canonical JSONL warehouse, GUI workbench, 개인 코퍼스는 포함하지 않습니다. 과거 구현은 Git 이력과 archive 태그로 복구할 수 있습니다.

## 설치·동기화

```bash
python3 scripts/manage_skills.py check
python3 scripts/manage_skills.py install
```

기본 설치 위치는 `~/.codex/skills`입니다. 다른 위치는 `--target PATH`, 변경 미리보기는 `--dry-run`을 사용합니다.

## 검증

```bash
python3 -m unittest discover -s tests
git -c core.quotepath=false diff-tree --root --no-commit-id --name-only -r HEAD > /tmp/doctology-changed-files.txt
python3 .agents/skills/repo-docs-intelligence-bootstrap/scripts/validate_repo_docs_intelligence.py --repo-root . --changed-files /tmp/doctology-changed-files.txt
```

위 명령은 현재 커밋에서 바뀐 경로를 검증합니다. 커밋 전 개발 중에는 working tree 변경과 정확히 일치하는 정규화된 목록을 전달하세요.

구조와 유지보수 규칙은 [문서 포털](docs/README.md)을 참고하세요.
