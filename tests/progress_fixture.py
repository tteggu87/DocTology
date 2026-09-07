"""Synthetic large-vault shape from the reported UX failure; never a certified corpus."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def make_vault(root: Path, *, sources=635, reports=639, wiki_pages=1328, runs=510):
    root = root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("Fixture target must be empty")
    for name in ("raw/inbox", "wiki/concepts", "wiki/_meta/ingest_reports", "state/wiki_runs"):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "AGENTS.md").write_text("# Synthetic progress fixture\n\nRead-only QA data; never claim semantic certification.\n", encoding="utf-8")
    (root / "wiki/_meta/index.md").write_text("# 대용량 진행 표시 검증용 위키\n\n이 자료는 합성 품질을 증명하지 않는 테스트 데이터입니다.\n", encoding="utf-8")
    (root / "wiki/_meta/log.md").write_text("# Fixture log\n", encoding="utf-8")
    digests = {}
    for index in range(sources):
        relative = f"raw/inbox/source-{index:04}.md"
        body = f"# 검증용 원문 {index:04}\n\n연결 진행 표시와 응답성을 확인하는 합성 자료입니다.\n" + "\n작업 기록과 위키 문서는 서로 다른 역할을 가집니다.\n" * 8
        (root / relative).write_text(body, encoding="utf-8")
        digests[relative] = "sha256:" + hashlib.sha256(body.encode()).hexdigest()
    for index in range(reports):
        relative = f"raw/inbox/source-{index % sources:04}.md"
        report = f"---\nstatus: applied\ncoverage_mode: full\nraw_path: {relative}\nsource_sha256: {digests[relative]}\nsource_units_total: 2\nsource_units_projected: 1\nsource_units_omitted: 0\nsource_units_deferred: 1\n---\n# Fixture receipt {index}\n\n- part -> `wiki/concepts/topic-0000.md#facts`\n\nThis is test data, not a completed ingest.\n"
        (root / f"wiki/_meta/ingest_reports/ingest-{index:04}.md").write_text(report, encoding="utf-8")
    count = wiki_pages - reports - 2
    for index in range(count):
        target = (index + 1) % count
        (root / f"wiki/concepts/topic-{index:04}.md").write_text(
            f"# 검증용 개념 {index:04}\n\n## Facts\n\nPi 진행 상태와 문서 탐색을 설명하는 합성 테스트 페이지입니다.\n\n[[topic-{target:04}]]\n", encoding="utf-8")
    for index in range(runs):
        relative = f"raw/inbox/source-{index % sources:04}.md"
        (root / f"state/wiki_runs/fixture-{index:04}.json").write_text(json.dumps({
            "run_id":f"fixture-{index:04}", "source":relative, "source_sha256":digests[relative],
            "status":"active", "stages":{}, "coverage_mode":"full", "updated_at":"2026-09-07T00:00:00Z",
        }), encoding="utf-8")
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    print(make_vault(args.target))
