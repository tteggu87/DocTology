from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BATCH_PATH = (
    ROOT
    / ".agents"
    / "skills"
    / "llm-wiki-loop"
    / "scripts"
    / "wiki_batch.py"
)
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

    def start_preplanned_run(self, root: Path, source: str) -> str:
        run = self.batch.workflow.start_run(root, source)
        run_id = run["run_id"]
        stage_args = dict(
            na_reason=None,
            result=None,
            posture=None,
            reviewed_fingerprint=None,
        )
        self.batch.workflow.record_stage(
            root,
            run_id,
            "inspect_contract_and_index",
            refs=["AGENTS.md", "wiki/_meta/index.md"],
            **stage_args,
        )
        self.batch.workflow.record_stage(
            root,
            run_id,
            "inspect_source_and_existing_scope",
            refs=[source, "wiki/_meta/index.md"],
            **stage_args,
        )
        self.batch.workflow.record_stage(
            root,
            run_id,
            "semantic_plan_frozen",
            refs=["AGENTS.md", source],
            **stage_args,
        )
        return run_id

    def write_source_draft(
        self,
        root: Path,
        draft_name: str,
        source: str,
        page_stem: str,
        report_stem: str,
    ) -> Path:
        draft = root / "state" / "worker_drafts" / draft_name
        page = draft / "wiki" / "sources" / f"{page_stem}.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            "---\n"
            f"title: {page_stem}\n"
            "type: source\n"
            "status: active\n"
            f"raw_path: {source}\n"
            "---\n\n"
            f"# {page_stem}\n\nEvidence summary.\n",
            encoding="utf-8",
        )
        report = draft / "wiki" / "_meta" / "ingest_reports" / f"{report_stem}.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            "---\n"
            f'title: "Ingest coverage for {page_stem}"\n'
            "type: meta\n"
            "status: applied\n"
            "coverage_mode: full\n"
            f"raw_path: {source}\n"
            f'source_sha256: "{self.batch.workflow.file_digest(root / source)}"\n'
            "source_units_total: 1\n"
            "source_units_projected: 1\n"
            "source_units_omitted: 0\n"
            "source_units_deferred: 0\n"
            "---\n\n"
            "# Coverage\n\n"
            f"- Raw path: `{source}`\n"
            f"- Source page: [[{page_stem}]]\n",
            encoding="utf-8",
        )
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
            with self.assertRaisesRegex(self.batch.BatchError, "seal fingerprint is stale"):
                self.batch.seal_batch(
                    root,
                    batch_id,
                    "reviewer-test",
                    ["wiki/sources/source-example.md"],
                )

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
            receipt = draft / "wiki" / "_meta" / "ingest_reports" / "ingest-example.md"
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text(
                "---\n"
                'title: "Ingest coverage for Example"\n'
                "type: meta\n"
                "status: applied\n"
                "coverage_mode: full\n"
                "raw_path: raw/inbox/example.md\n"
                f'source_sha256: "{self.batch.workflow.file_digest(root / source)}"\n'
                "source_units_total: 1\n"
                "source_units_projected: 1\n"
                "source_units_omitted: 0\n"
                "source_units_deferred: 0\n"
                "---\n\n# Coverage\n\n- Raw path: `raw/inbox/example.md`\n",
                encoding="utf-8",
            )
            index = draft / "wiki" / "_meta" / "index.md"
            index.parent.mkdir(parents=True, exist_ok=True)
            index.write_text(
                "# Index\n\n- [[source-example]]\n- [[ingest-example]]\n",
                encoding="utf-8",
            )
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
                root, run_id, "refresh_index_and_log", refs=["wiki/_meta/index.md", "wiki/_meta/log.md", "wiki/_meta/ingest_reports/ingest-example.md"],
                na_reason="meta_current_after_batch_apply", result=None, posture=None, reviewed_fingerprint=None,
            )
            self.batch.workflow.record_stage(
                root, run_id, "validate_structure", refs=["wiki/sources/source-example.md", "wiki/_meta/index.md"],
                na_reason=None, result="passed", posture=None, reviewed_fingerprint=None,
            )
            fingerprint = self.batch.workflow.state_fingerprint(root, source)
            self.batch.workflow.record_stage(
                root, run_id, "final_review_completed", refs=["wiki/sources/source-example.md", "wiki/_meta/ingest_reports/ingest-example.md"],
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

    def test_two_source_batch_seals_one_snapshot_and_refreshes_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, source_a = self.make_vault(Path(tmp))
            source_b = "raw/inbox/second.md"
            (root / source_b).write_text("# Second\n\nMore evidence.\n", encoding="utf-8")
            run_a = self.start_preplanned_run(root, source_a)
            run_b = self.start_preplanned_run(root, source_b)

            manifest = self.batch.plan_batch(root, [source_a, source_b])
            batch_id = manifest["batch_id"]
            self.batch.link_run(root, batch_id, source_a, run_a)
            self.batch.link_run(root, batch_id, source_b, run_b)

            draft_a = self.write_source_draft(
                root, "seal-a", source_a, "source-example", "ingest-example"
            )
            index = draft_a / "wiki" / "_meta" / "index.md"
            index.parent.mkdir(parents=True, exist_ok=True)
            index.write_text(
                "# Index\n\n"
                "- [[source-example]]\n"
                "- [[ingest-example]]\n"
                "- [[source-second]]\n"
                "- [[ingest-second]]\n",
                encoding="utf-8",
            )
            (draft_a / "wiki" / "_meta" / "log.md").write_text(
                "# Log\n\n"
                f"- Ingested `{source_a}` through [[source-example]].\n"
                f"- Ingested `{source_b}` through [[source-second]].\n",
                encoding="utf-8",
            )
            draft_b = self.write_source_draft(
                root, "seal-b", source_b, "source-second", "ingest-second"
            )
            self.batch.stage_draft(root, batch_id, source_a, str(draft_a.relative_to(root)))
            self.batch.stage_draft(root, batch_id, source_b, str(draft_b.relative_to(root)))
            self.batch.apply_batch(root, batch_id, "writer-seal")

            fingerprint = self.batch.batch_status(root, batch_id)["current_fingerprint"]
            self.batch.record_question(
                root,
                batch_id,
                "direct_lookup",
                "supported",
                ["wiki/sources/source-example.md", "wiki/sources/source-second.md"],
                "question-reviewer",
                fingerprint,
            )
            wiki_before_seal = self.batch.corpus_fingerprint(
                root, self.batch.load_manifest(root, batch_id)[1]
            )
            refresh_result = {
                "retrieval_ready": True,
                "retrieval_status": "ready",
                "semantic_status": "ready",
            }
            with mock.patch.object(
                self.batch.workflow,
                "run_retrieval_refresh",
                side_effect=OSError("injected refresh interruption"),
            ) as refresh:
                with self.assertRaisesRegex(OSError, "injected refresh interruption"):
                    self.batch.seal_batch(
                        root,
                        batch_id,
                        "batch-reviewer",
                        ["wiki/sources/source-example.md", "wiki/sources/source-second.md"],
                    )
            _path, refreshing_manifest = self.batch.load_manifest(root, batch_id)
            self.assertEqual(refreshing_manifest["seal_attempt"]["status"], "refreshing")

            with mock.patch.object(
                self.batch.workflow,
                "run_retrieval_status",
                return_value=refresh_result,
            ) as refresh_status:
                original_write_json = self.batch.workflow.write_json
                live_run_writes = 0

                def fail_second_live_run(path, payload):
                    nonlocal live_run_writes
                    if path.parent.name == "wiki_runs":
                        live_run_writes += 1
                        if live_run_writes == 2:
                            raise OSError("injected seal interruption")
                    return original_write_json(path, payload)

                with mock.patch.object(
                    self.batch.workflow,
                    "write_json",
                    side_effect=fail_second_live_run,
                ):
                    with self.assertRaisesRegex(OSError, "injected seal interruption"):
                        self.batch.seal_batch(
                            root,
                            batch_id,
                            "batch-reviewer",
                            [
                                "wiki/sources/source-example.md",
                                "wiki/sources/source-second.md",
                            ],
                        )
            _path, interrupted_manifest = self.batch.load_manifest(root, batch_id)
            self.assertEqual(interrupted_manifest["status"], "sealing")
            self.assertEqual(interrupted_manifest["seal_attempt"]["status"], "prepared")
            self.assertIsNone(interrupted_manifest["seal_event"])

            attempt = interrupted_manifest["seal_attempt"]
            review_path = root / attempt["review_path"]
            original_review = json.loads(review_path.read_text(encoding="utf-8"))
            self.batch.write_json(review_path, {**original_review, "reviewer": "tampered"})
            with self.assertRaisesRegex(self.batch.BatchError, "final review receipt changed"):
                self.batch.seal_batch(
                    root,
                    batch_id,
                    "batch-reviewer",
                    ["wiki/sources/source-example.md", "wiki/sources/source-second.md"],
                )
            self.batch.write_json(review_path, original_review)

            guarded = attempt["prepared_runs"][1]
            guarded_run_path = self.batch.workflow.run_path(root, guarded["run_id"])
            guarded_run = json.loads(guarded_run_path.read_text(encoding="utf-8"))
            self.batch.workflow.write_json(
                guarded_run_path, {**guarded_run, "outside_seal_marker": True}
            )
            with self.assertRaisesRegex(self.batch.BatchError, "outside prepared seal"):
                self.batch.seal_batch(
                    root,
                    batch_id,
                    "batch-reviewer",
                    ["wiki/sources/source-example.md", "wiki/sources/source-second.md"],
                )
            backup_path = root / guarded["backup_path"]
            self.batch.workflow.write_json(
                guarded_run_path,
                json.loads(backup_path.read_text(encoding="utf-8")),
            )
            sealed = self.batch.seal_batch(
                root,
                batch_id,
                "batch-reviewer",
                ["wiki/sources/source-example.md", "wiki/sources/source-second.md"],
            )
            wiki_after_seal = self.batch.corpus_fingerprint(
                root, self.batch.load_manifest(root, batch_id)[1]
            )

            self.assertEqual(sealed["status"], "pass")
            self.assertEqual(wiki_before_seal, wiki_after_seal)
            self.assertEqual(wiki_after_seal, fingerprint)
            refresh.assert_called_once_with(root.resolve())
            refresh_status.assert_called_once_with(root.resolve())
            for run_id in (run_a, run_b):
                _path, run = self.batch.workflow.load_run(root, run_id)
                self.assertEqual(run["status"], "completed")
                self.assertEqual(run["batch_corpus_fingerprint"], fingerprint)
                self.assertEqual(
                    run["stages"]["final_review_completed"]["batch_apply"][
                        "result_fingerprint"
                    ],
                    fingerprint,
                )
                self.assertEqual(
                    self.batch.workflow.project_status(root, run)["status"], "pass"
                )

            _path, final_manifest = self.batch.load_manifest(root, batch_id)
            self.assertEqual(final_manifest["status"], "certified")
            self.assertEqual(final_manifest["certification"]["status"], "pass")
            self.assertTrue(
                (root / "state" / "wiki_batches" / batch_id / "final_review.json").is_file()
            )

    def test_question_receipt_revalidation_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, source = self.make_vault(Path(tmp))
            manifest = self.batch.plan_batch(root, [source])
            batch_id = manifest["batch_id"]
            fingerprint = manifest["current_fingerprint"]
            receipt = self.batch.record_question(
                root,
                batch_id,
                "direct_lookup",
                "supported",
                ["AGENTS.md"],
                "question-reviewer",
                fingerprint,
            )
            receipt_path = (
                root
                / "state"
                / "wiki_batches"
                / batch_id
                / "question_receipts"
                / "direct_lookup.json"
            )
            cases = (
                ("schema_version", 2, "QUESTION_RECEIPT_SCHEMA_INVALID"),
                ("batch_id", "other-batch", "QUESTION_RECEIPT_BATCH_MISMATCH"),
                ("case_id", "other-case", "QUESTION_RECEIPT_CASE_MISMATCH"),
                ("reviewer", "", "QUESTION_REVIEWER_MISSING"),
                ("evidence", [], "QUESTION_EVIDENCE_MISSING"),
                ("evidence", {"path": "AGENTS.md"}, "QUESTION_EVIDENCE_INVALID"),
                (
                    "evidence",
                    [{"path": "AGENTS.md", "sha256": "sha256:wrong"}],
                    "QUESTION_EVIDENCE_STALE",
                ),
            )
            for field, value, expected in cases:
                with self.subTest(field=field, expected=expected):
                    changed = {**receipt, field: value}
                    self.batch.write_json(receipt_path, changed)
                    blockers = self.batch.representative_question_blockers(
                        root, manifest, fingerprint
                    )
                    self.assertTrue(
                        any(item.startswith(expected) for item in blockers), blockers
                    )


if __name__ == "__main__":
    unittest.main()
