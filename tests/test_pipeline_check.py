from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_CHECK_PATH = ROOT / "scripts" / "pipeline_check.py"
BOOTSTRAP_PATH = ROOT / ".agents" / "skills" / "llm-wiki-bootstrap" / "scripts" / "bootstrap_llm_wiki.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PipelineCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pipeline_check = load_module(PIPELINE_CHECK_PATH, "pipeline_check_under_test")
        cls.bootstrap = load_module(BOOTSTRAP_PATH, "bootstrap_for_pipeline_check_test")

    def scaffold_archived(self, root: Path, profile: str = "wiki-plus-ontology") -> None:
        self.bootstrap._scaffold_archived_profile_for_contract_tests(
            root, force=False, profile=profile
        )

    def test_missing_source_is_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold_archived(root)

            result = self.pipeline_check.check_source(root, "raw/inbox/missing.md")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["source_page_stage"], "failed")
        self.assertIn("source_exists", [item["name"] for item in result["checks"]])

    def test_existing_source_without_source_page_is_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold_archived(root)
            source = root / "raw" / "inbox" / "example.md"
            source.write_text("# Example\n", encoding="utf-8")

            result = self.pipeline_check.check_source(root, "raw/inbox/example.md")

        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["source_page_stage"], "pending")
        self.assertEqual(result["semantic_status"], "pending")

    def test_ontology_integrity_is_profile_aware(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "wiki-only"
            self.bootstrap.scaffold(root, force=False, profile="wiki-only")
            wiki_only = self.pipeline_check.ontology_integrity_check(root)

            ontology_results = []
            for profile in ("wiki-plus-ontology", "llm-first-ontology"):
                ontology_root = Path(tmp) / profile
                self.scaffold_archived(ontology_root, profile)
                ontology_results.append(self.pipeline_check.ontology_integrity_check(ontology_root))

        self.assertEqual(wiki_only["status"], "not_applicable")
        self.assertEqual([item["status"] for item in ontology_results], ["ok", "ok"])

    def test_ontology_integrity_rejects_unreviewed_accepted_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold_archived(root)
            jsonl = root / "warehouse" / "jsonl"
            (jsonl / "documents.jsonl").write_text('{"document_id":"doc:1"}\n', encoding="utf-8")
            (jsonl / "entities.jsonl").write_text('{"entity_id":"entity:1"}\n', encoding="utf-8")
            (jsonl / "claims.jsonl").write_text(
                '{"claim_id":"claim:1","status":"accepted","review_state":"approved","subject_id":"entity:1","source_document_id":"doc:1"}\n',
                encoding="utf-8",
            )

            result = self.pipeline_check.ontology_integrity_check(root)

        self.assertEqual(result["status"], "failed")
        self.assertTrue(
            any(code.startswith("ACCEPTED_CLAIM_MISSING_REVIEW:claim:1") for code in result["reason_codes"])
        )
        self.assertIn("ACCEPTED_CLAIM_WITHOUT_EVIDENCE:claim:1", result["reason_codes"])

    def test_ontology_integrity_rejects_derived_edge_from_proposed_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold_archived(root)
            jsonl = root / "warehouse" / "jsonl"
            (jsonl / "claims.jsonl").write_text(
                '{"claim_id":"claim:1","status":"proposed","review_state":"needs_review"}\n',
                encoding="utf-8",
            )
            (jsonl / "derived_edges.jsonl").write_text(
                '{"source_claim_id":"claim:1","source":"entity:a","target":"entity:b"}\n',
                encoding="utf-8",
            )

            result = self.pipeline_check.ontology_integrity_check(root)

        self.assertEqual(result["status"], "failed")
        self.assertIn("DERIVED_FROM_NON_ACCEPTED_CLAIM:1:claim:1", result["reason_codes"])

    def test_log_matching_uses_exact_source_identity_not_basename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold_archived(root)
            source_a = root / "raw" / "inbox" / "a" / "same.md"
            source_b = root / "raw" / "inbox" / "b" / "same.md"
            source_a.parent.mkdir(parents=True, exist_ok=True)
            source_b.parent.mkdir(parents=True, exist_ok=True)
            source_a.write_text("# A\n", encoding="utf-8")
            source_b.write_text("# B\n", encoding="utf-8")
            source_page_b = root / "wiki" / "sources" / "source-b-same.md"
            source_page_b.write_text(
                """---
title: "B Same"
type: source
status: inbox
created: 2026-05-07
updated: 2026-05-07
raw_path: "raw/inbox/b/same.md"
---

# B Same
""",
                encoding="utf-8",
            )
            log_path = root / "wiki" / "_meta" / "log.md"
            log_path.write_text(
                "# Log\n\n- Registered source at `raw/inbox/a/same.md`\n",
                encoding="utf-8",
            )

            result = self.pipeline_check.check_source(root, "raw/inbox/b/same.md")

        log_check = next(item for item in result["checks"] if item["name"] == "log_mentions_source")
        self.assertEqual(log_check["status"], "pending")

    def test_ingest_report_matching_uses_exact_source_identity_not_basename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold_archived(root)
            source_a = root / "raw" / "inbox" / "a" / "same.md"
            source_b = root / "raw" / "inbox" / "b" / "same.md"
            source_a.parent.mkdir(parents=True, exist_ok=True)
            source_b.parent.mkdir(parents=True, exist_ok=True)
            source_a.write_text("# A\n", encoding="utf-8")
            source_b.write_text("# B\n", encoding="utf-8")
            source_page_b = root / "wiki" / "sources" / "source-b-same.md"
            source_page_b.write_text(
                """---
title: "B Same"
type: source
status: inbox
created: 2026-05-07
updated: 2026-05-07
raw_path: "raw/inbox/b/same.md"
---

# B Same
""",
                encoding="utf-8",
            )
            reports_dir = root / "wiki" / "_meta" / "ingest_reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / "ingest-a-same.md").write_text(
                """---
title: "A Same Report"
type: ingest_report
status: partial
---

## Source Registered

- Raw path: `raw/inbox/a/same.md`
- Source page: [[source-a-same]]
""",
                encoding="utf-8",
            )

            result = self.pipeline_check.check_source(root, "raw/inbox/b/same.md")

        report_check = next(item for item in result["checks"] if item["name"] == "ingest_report_exists")
        self.assertEqual(report_check["status"], "pending")

    def test_full_growth_artifacts_mark_growth_loop_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold_archived(root)
            source = root / "raw" / "inbox" / "example.md"
            source.write_text("# Example\n", encoding="utf-8")
            source_page = root / "wiki" / "sources" / "source-example.md"
            source_page.write_text(
                """---
title: "Example"
type: source
status: growth-applied
created: 2026-05-07
updated: 2026-05-07
raw_path: "raw/inbox/example.md"
---

# Example
""",
                encoding="utf-8",
            )
            report_dir = root / "wiki" / "_meta" / "ingest_reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            report = report_dir / "ingest-example.md"
            report.write_text(
                """---
title: "Example Report"
type: ingest_report
status: applied
---

## Source Registered

- Raw path: `raw/inbox/example.md`
- Source page: [[source-example]]

## Applied Affected Pages

- `wiki/concepts/example.md`: created
""",
                encoding="utf-8",
            )
            proposed = root / "warehouse" / "jsonl" / "proposed_claims.jsonl"
            proposed.write_text(
                '{"raw_path":"raw/inbox/example.md","source_page":"wiki/sources/source-example.md","status":"proposed"}\n',
                encoding="utf-8",
            )
            (root / "wiki" / "_meta" / "index.md").write_text(
                "# Index\n\n- [[source-example]]\n- [[ingest-example]]\n",
                encoding="utf-8",
            )
            (root / "wiki" / "_meta" / "log.md").write_text(
                "# Log\n\n- Full ingest apply for `raw/inbox/example.md` via [[source-example]] and [[ingest-example]]\n",
                encoding="utf-8",
            )

            result = self.pipeline_check.check_source(root, "raw/inbox/example.md")

        self.assertEqual(result["semantic_status"], "growth_loop_applied")
        jsonl_check = next(item for item in result["checks"] if item["name"] == "jsonl_projection")
        wiki_check = next(item for item in result["checks"] if item["name"] == "broader_wiki_projection")
        self.assertEqual(jsonl_check["status"], "ok")
        self.assertEqual(wiki_check["status"], "ok")

    def test_skipped_affected_pages_do_not_mark_growth_loop_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.scaffold_archived(root)
            source = root / "raw" / "inbox" / "example.md"
            source.write_text("# Example\n", encoding="utf-8")
            source_page = root / "wiki" / "sources" / "source-example.md"
            source_page.write_text(
                """---
title: "Example"
type: source
status: growth-applied
created: 2026-05-07
updated: 2026-05-07
raw_path: "raw/inbox/example.md"
---

# Example
""",
                encoding="utf-8",
            )
            report_dir = root / "wiki" / "_meta" / "ingest_reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            report = report_dir / "ingest-example.md"
            report.write_text(
                """---
title: "Example Report"
type: ingest_report
status: applied
---

## Source Registered

- Raw path: `raw/inbox/example.md`
- Source page: [[source-example]]

## Applied Affected Pages

- `wiki/concepts/example.md`: created

## Skipped Affected Pages

- `affected page path is outside allowed wiki folders`
""",
                encoding="utf-8",
            )
            proposed = root / "warehouse" / "jsonl" / "proposed_claims.jsonl"
            proposed.write_text(
                '{"raw_path":"raw/inbox/example.md","source_page":"wiki/sources/source-example.md","status":"proposed"}\n',
                encoding="utf-8",
            )
            (root / "wiki" / "_meta" / "index.md").write_text(
                "# Index\n\n- [[source-example]]\n- [[ingest-example]]\n",
                encoding="utf-8",
            )
            (root / "wiki" / "_meta" / "log.md").write_text(
                "# Log\n\n- Full ingest apply for `raw/inbox/example.md` via [[source-example]] and [[ingest-example]]\n",
                encoding="utf-8",
            )

            result = self.pipeline_check.check_source(root, "raw/inbox/example.md")

        self.assertEqual(result["semantic_status"], "pending_broader_projection")
        wiki_check = next(item for item in result["checks"] if item["name"] == "broader_wiki_projection")
        self.assertEqual(wiki_check["status"], "pending")

    def test_strict_cli_rejects_pending_source_and_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            self.bootstrap.scaffold(root, force=False, profile="wiki-only")
            source = root / "raw" / "inbox" / "pending.md"
            source.write_text("# Pending\n", encoding="utf-8")
            manifest = root / "batch.json"
            manifest.write_text(
                json.dumps({"schema_version": 1, "sources": [{"path": "raw/inbox/pending.md"}]}) + "\n",
                encoding="utf-8",
            )

            source_result = subprocess.run(
                [sys.executable, str(PIPELINE_CHECK_PATH), "--root", str(root), "--source", "raw/inbox/pending.md", "--strict"],
                text=True,
                capture_output=True,
                check=False,
            )
            batch_result = subprocess.run(
                [sys.executable, str(PIPELINE_CHECK_PATH), "--root", str(root), "--batch", "batch.json", "--strict"],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(source_result.returncode, 1)
        self.assertEqual(batch_result.returncode, 1)
        self.assertIn("pending", batch_result.stdout)


if __name__ == "__main__":
    unittest.main()
