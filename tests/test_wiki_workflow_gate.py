from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "scripts" / "wiki_workflow.py"
BOOTSTRAP_PATH = ROOT / ".agents" / "skills" / "llm-wiki-bootstrap" / "scripts" / "bootstrap_llm_wiki.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WikiWorkflowGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = load_module(WORKFLOW_PATH, "wiki_workflow_under_test")
        cls.bootstrap = load_module(BOOTSTRAP_PATH, "bootstrap_for_workflow_test")

    def make_vault(self, base: Path) -> tuple[Path, Path]:
        root = base / "vault"
        self.bootstrap.scaffold(root, force=False, profile="wiki-only")
        source = root / "raw" / "inbox" / "example.md"
        source.write_text("# Example\n\nEvidence.\n", encoding="utf-8")
        return root, source

    def record_preflight(self, root: Path, run_id: str) -> None:
        self.workflow.record_stage(
            root,
            run_id,
            "inspect_contract_and_index",
            refs=["AGENTS.md", "wiki/_meta/index.md"],
            na_reason=None,
            result=None,
            posture=None,
            reviewed_fingerprint=None,
        )
        self.workflow.record_stage(
            root,
            run_id,
            "inspect_source_and_existing_scope",
            refs=["raw/inbox/example.md", "wiki/_meta/index.md"],
            na_reason=None,
            result=None,
            posture=None,
            reviewed_fingerprint=None,
        )
        self.workflow.record_stage(
            root,
            run_id,
            "semantic_plan_frozen",
            refs=["AGENTS.md", "raw/inbox/example.md", "wiki/_meta/index.md"],
            na_reason=None,
            result=None,
            posture=None,
            reviewed_fingerprint=None,
        )

    def test_missing_stage_blocks_finish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            run = self.workflow.start_run(root, "raw/inbox/example.md")
            result = self.workflow.finish_run(root, run["run_id"])

        self.assertEqual(result["status"], "blocked")
        self.assertIn("PROCEDURE_STAGE_MISSING", result["blockers"])

    def test_semantic_plan_must_precede_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            run = self.workflow.start_run(root, "raw/inbox/example.md")
            run_id = run["run_id"]
            self.workflow.record_stage(
                root,
                run_id,
                "inspect_contract_and_index",
                refs=["AGENTS.md"],
                na_reason=None,
                result=None,
                posture=None,
                reviewed_fingerprint=None,
            )
            self.workflow.record_stage(
                root,
                run_id,
                "inspect_source_and_existing_scope",
                refs=["raw/inbox/example.md"],
                na_reason=None,
                result=None,
                posture=None,
                reviewed_fingerprint=None,
            )
            (root / "wiki" / "concepts" / "too-early.md").write_text("# Too Early\n", encoding="utf-8")

            with self.assertRaisesRegex(self.workflow.WorkflowError, "before the first wiki mutation"):
                self.workflow.record_stage(
                    root,
                    run_id,
                    "semantic_plan_frozen",
                    refs=["raw/inbox/example.md"],
                    na_reason=None,
                    result=None,
                    posture=None,
                    reviewed_fingerprint=None,
                )

    def test_repair_to_pass_and_later_mutation_stales_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            run = self.workflow.start_run(root, "raw/inbox/example.md")
            run_id = run["run_id"]
            self.record_preflight(root, run_id)

            source_page = root / "wiki" / "sources" / "source-example.md"
            source_page.write_text(
                "---\ntitle: Example\ntype: source\nstatus: active\nraw_path: raw/inbox/example.md\n---\n\n# Example\n\nSummary.\n",
                encoding="utf-8",
            )
            self.workflow.record_stage(
                root, run_id, "register_or_resolve_source", refs=["wiki/sources/source-example.md"],
                na_reason=None, result=None, posture=None, reviewed_fingerprint=None,
            )

            source_page.write_text(source_page.read_text(encoding="utf-8") + "\n## Key Facts\n\n- Evidence.\n", encoding="utf-8")
            self.workflow.record_stage(
                root, run_id, "update_source_page", refs=["wiki/sources/source-example.md"],
                na_reason=None, result=None, posture=None, reviewed_fingerprint=None,
            )
            self.workflow.record_stage(
                root, run_id, "update_affected_pages", refs=["wiki/sources/source-example.md"],
                na_reason="no_affected_page_promotion", result=None, posture=None, reviewed_fingerprint=None,
            )

            log = root / "wiki" / "_meta" / "log.md"
            log.write_text(log.read_text(encoding="utf-8") + "\n- Example ingest updated.\n", encoding="utf-8")
            self.workflow.record_stage(
                root, run_id, "refresh_index_and_log", refs=["wiki/_meta/log.md"],
                na_reason=None, result=None, posture=None, reviewed_fingerprint=None,
            )
            self.workflow.record_stage(
                root, run_id, "validate_structure", refs=["wiki/sources/source-example.md"],
                na_reason=None, result="passed", posture=None, reviewed_fingerprint=None,
            )
            fingerprint = self.workflow.state_fingerprint(root, "raw/inbox/example.md")
            self.workflow.record_stage(
                root, run_id, "final_review_completed", refs=["wiki/sources/source-example.md"],
                na_reason=None, result=None, posture="ready", reviewed_fingerprint=fingerprint,
            )
            passed = self.workflow.finish_run(root, run_id)
            self.assertEqual(passed["status"], "pass")
            self.assertEqual(passed["run_status"], "completed")

            source_page.write_text(source_page.read_text(encoding="utf-8") + "\nChanged later.\n", encoding="utf-8")
            _path, payload = self.workflow.load_run(root, run_id)
            stale = self.workflow.project_status(root, payload)

        self.assertEqual(stale["status"], "blocked")
        self.assertIn("final_review_completed", stale["stale_stages"])


if __name__ == "__main__":
    unittest.main()
