from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH_PATH = ROOT / "scripts" / "wiki_batch.py"
BOOTSTRAP_PATH = ROOT / ".agents" / "skills" / "llm-wiki-bootstrap" / "scripts" / "bootstrap_llm_wiki.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WikiBatchGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.batch = load_module(BATCH_PATH, "wiki_batch_under_test")
        cls.bootstrap = load_module(BOOTSTRAP_PATH, "bootstrap_for_batch_test")

    def make_vault(self, base: Path) -> tuple[Path, str]:
        root = base / "vault"
        self.bootstrap.scaffold(root, force=False, profile="wiki-only")
        source = root / "raw" / "inbox" / "example.md"
        source.write_text("# Example\n\nEvidence.\n", encoding="utf-8")
        questions = root / "wiki" / "_meta" / "representative_questions.json"
        questions.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "cases": [
                        {
                            "id": "direct_lookup",
                            "question": "What does the example say?",
                            "required": True,
                            "expected_posture": "supported",
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return root, "raw/inbox/example.md"

    def make_draft(self, root: Path, name: str, body: str) -> Path:
        draft = root / "state" / "worker_drafts" / name
        page = draft / "wiki" / "sources" / "source-example.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(body, encoding="utf-8")
        return draft

    def test_unobserved_mutation_blocks_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, source = self.make_vault(Path(tmp))
            manifest = self.batch.plan_batch(root, [source])
            batch_id = manifest["batch_id"]
            draft = self.make_draft(root, "a", "# Example\n")
            self.batch.stage_draft(root, batch_id, source, str(draft.relative_to(root)))
            mutation = root / "wiki" / "concepts" / "outside-writer.md"
            mutation.write_text("# Outside Writer\n", encoding="utf-8")

            with self.assertRaisesRegex(self.batch.BatchError, "unobserved_mutation"):
                self.batch.apply_batch(root, batch_id, "writer-1")

    def test_single_writer_apply_and_later_state_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, source = self.make_vault(Path(tmp))
            manifest = self.batch.plan_batch(root, [source])
            batch_id = manifest["batch_id"]
            draft = self.make_draft(
                root,
                "a",
                "---\ntitle: Example\ntype: source\nstatus: active\nraw_path: raw/inbox/example.md\n---\n\n# Example\n\nSummary.\n",
            )
            self.batch.stage_draft(root, batch_id, source, str(draft.relative_to(root)))
            event = self.batch.apply_batch(root, batch_id, "writer-1")

            self.assertEqual(event["writer_id"], "writer-1")
            self.assertTrue((root / "wiki" / "sources" / "source-example.md").exists())
            with self.assertRaisesRegex(self.batch.BatchError, "already has a writer"):
                self.batch.apply_batch(root, batch_id, "writer-2")

            fingerprint = self.batch.batch_status(root, batch_id)["current_fingerprint"]
            receipt = self.batch.record_question(
                root,
                batch_id,
                "direct_lookup",
                "supported",
                ["wiki/sources/source-example.md"],
                "reviewer-test",
                fingerprint,
            )
            self.assertEqual(receipt["corpus_fingerprint"], fingerprint)

            page = root / "wiki" / "sources" / "source-example.md"
            page.write_text(page.read_text(encoding="utf-8") + "\nLater mutation.\n", encoding="utf-8")
            _path, current_manifest = self.batch.load_manifest(root, batch_id)
            current_manifest["certification"] = {"corpus_fingerprint": fingerprint, "status": "pass"}
            self.batch.write_json(self.batch.manifest_path(root, batch_id), current_manifest)
            status = self.batch.batch_status(root, batch_id)

        self.assertEqual(status["status"], "stale")
        self.assertTrue(status["certification_stale"])

    def test_conflicting_worker_drafts_block_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, source_a = self.make_vault(Path(tmp))
            source_b_path = root / "raw" / "inbox" / "second.md"
            source_b_path.write_text("# Second\n", encoding="utf-8")
            source_b = "raw/inbox/second.md"
            manifest = self.batch.plan_batch(root, [source_a, source_b])
            batch_id = manifest["batch_id"]
            draft_a = self.make_draft(root, "a", "# Version A\n")
            draft_b = self.make_draft(root, "b", "# Version B\n")
            self.batch.stage_draft(root, batch_id, source_a, str(draft_a.relative_to(root)))
            self.batch.stage_draft(root, batch_id, source_b, str(draft_b.relative_to(root)))

            with self.assertRaisesRegex(self.batch.BatchError, "conflicting staged drafts"):
                self.batch.apply_batch(root, batch_id, "writer-1")

    def test_full_batch_repair_to_certified_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, source = self.make_vault(Path(tmp))
            run = self.batch.workflow.start_run(root, source)
            run_id = run["run_id"]
            stage_args = dict(na_reason=None, result=None, posture=None, reviewed_fingerprint=None)
            self.batch.workflow.record_stage(root, run_id, "inspect_contract_and_index", refs=["AGENTS.md", "wiki/_meta/index.md"], **stage_args)
            self.batch.workflow.record_stage(root, run_id, "inspect_source_and_existing_scope", refs=[source, "wiki/_meta/index.md"], **stage_args)
            self.batch.workflow.record_stage(root, run_id, "semantic_plan_frozen", refs=["AGENTS.md", source], **stage_args)

            manifest = self.batch.plan_batch(root, [source])
            batch_id = manifest["batch_id"]
            self.batch.link_run(root, batch_id, source, run_id)
            draft = root / "state" / "worker_drafts" / "golden"
            source_page = draft / "wiki" / "sources" / "source-example.md"
            source_page.parent.mkdir(parents=True, exist_ok=True)
            source_page.write_text(
                "---\ntitle: Example\ntype: source\nstatus: active\nraw_path: raw/inbox/example.md\n---\n\n# Example\n\n## Summary\n\nEvidence summary.\n",
                encoding="utf-8",
            )
            index = draft / "wiki" / "_meta" / "index.md"
            index.parent.mkdir(parents=True, exist_ok=True)
            index.write_text("# Index\n\n- [[source-example]]\n", encoding="utf-8")
            (draft / "wiki" / "_meta" / "log.md").write_text(
                "# Log\n\n- Ingested `raw/inbox/example.md` through [[source-example]].\n",
                encoding="utf-8",
            )
            self.batch.stage_draft(root, batch_id, source, str(draft.relative_to(root)))
            self.batch.apply_batch(root, batch_id, "writer-golden")

            self.batch.workflow.record_stage(root, run_id, "register_or_resolve_source", refs=["wiki/sources/source-example.md"], **stage_args)
            self.batch.workflow.record_stage(
                root, run_id, "update_source_page", refs=["wiki/sources/source-example.md"],
                na_reason="source_page_current", result=None, posture=None, reviewed_fingerprint=None,
            )
            self.batch.workflow.record_stage(
                root, run_id, "update_affected_pages", refs=["wiki/sources/source-example.md"],
                na_reason="no_affected_page_promotion", result=None, posture=None, reviewed_fingerprint=None,
            )
            self.batch.workflow.record_stage(
                root, run_id, "refresh_index_and_log", refs=["wiki/_meta/index.md", "wiki/_meta/log.md"],
                na_reason="meta_current_after_batch_apply", result=None, posture=None, reviewed_fingerprint=None,
            )
            self.batch.workflow.record_stage(
                root, run_id, "validate_structure", refs=["wiki/sources/source-example.md", "wiki/_meta/index.md"],
                na_reason=None, result="passed", posture=None, reviewed_fingerprint=None,
            )
            fingerprint = self.batch.workflow.state_fingerprint(root, source)
            self.batch.workflow.record_stage(
                root, run_id, "final_review_completed", refs=["wiki/sources/source-example.md"],
                na_reason=None, result=None, posture="ready", reviewed_fingerprint=fingerprint,
            )
            self.assertEqual(self.batch.workflow.finish_run(root, run_id)["status"], "pass")

            batch_fingerprint = self.batch.batch_status(root, batch_id)["current_fingerprint"]
            self.batch.record_question(
                root, batch_id, "direct_lookup", "supported", ["wiki/sources/source-example.md"],
                "reviewer-golden", batch_fingerprint,
            )
            certification = self.batch.certify_batch(root, batch_id)

        self.assertEqual(certification["status"], "pass")
        self.assertEqual(certification["blockers"], [])


if __name__ == "__main__":
    unittest.main()
