from __future__ import annotations

import errno
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = (
    ROOT
    / ".agents"
    / "skills"
    / "llm-wiki-loop"
    / "scripts"
    / "wiki_workflow.py"
)
LOOP_ENTRYPOINT = (
    ROOT / ".agents" / "skills" / "llm-wiki-loop" / "scripts" / "wiki_loop.py"
)
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

    def make_vault(
        self, base: Path, *, sqlite_enabled: bool = True
    ) -> tuple[Path, Path]:
        root = base / "vault"
        self.bootstrap.scaffold(
            root,
            force=False,
            profile="wiki-only",
            sqlite_enabled=sqlite_enabled,
        )
        source = root / "raw" / "inbox" / "example.md"
        source.write_text("# Example\n\nEvidence.\n", encoding="utf-8")
        return root, source

    def test_loop_runtime_operates_bootstrap_vault_without_installing_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            preflight = subprocess.run(
                [sys.executable, str(LOOP_ENTRYPOINT), "--repo-root", str(root), "preflight"],
                check=False,
                capture_output=True,
                text=True,
            )
            started = subprocess.run(
                [
                    sys.executable,
                    str(LOOP_ENTRYPOINT),
                    "--repo-root",
                    str(root),
                    "workflow",
                    "start",
                    "--workflow",
                    "ingest",
                    "--source",
                    "raw/inbox/example.md",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            self.assertEqual(json.loads(preflight.stdout)["state"], "ready")
            self.assertEqual(started.returncode, 0, started.stderr)
            self.assertEqual(json.loads(started.stdout)["runtime"], "llm-wiki-loop")
            for name in ("wiki_workflow.py", "wiki_batch.py", "pipeline_check.py"):
                self.assertFalse((root / "scripts" / name).exists())

    def test_preflight_reports_but_does_not_manage_legacy_repo_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            legacy = root / "scripts" / "wiki_workflow.py"
            legacy.write_text("legacy runtime\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(LOOP_ENTRYPOINT), "--repo-root", str(root), "preflight"],
                check=False,
                capture_output=True,
                text=True,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(payload["state"], "ready")
            self.assertEqual(payload["legacy_repo_runtime"], ["scripts/wiki_workflow.py"])
            self.assertEqual(legacy.read_text(encoding="utf-8"), "legacy runtime\n")

    def test_loop_runtime_accepts_a_compatible_non_bootstrap_wiki(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "existing-wiki"
            (root / "raw" / "inbox").mkdir(parents=True)
            (root / "wiki" / "_meta").mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Existing wiki\n", encoding="utf-8")
            (root / "wiki" / "_meta" / "index.md").write_text(
                "# Index\n", encoding="utf-8"
            )
            (root / "raw" / "inbox" / "example.md").write_text(
                "# Example\n\nEvidence.\n", encoding="utf-8"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(LOOP_ENTRYPOINT),
                    "--repo-root",
                    str(root),
                    "workflow",
                    "start",
                    "--workflow",
                    "ingest",
                    "--source",
                    "raw/inbox/example.md",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["runtime"], "llm-wiki-loop")
            self.assertTrue((root / "state" / "wiki_runs").is_dir())
            self.assertFalse((root / "scripts").exists())

    def test_preflight_does_not_promote_a_child_path_to_parent_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            child = root / "missing-child"
            result = subprocess.run(
                [sys.executable, str(LOOP_ENTRYPOINT), "--repo-root", str(child), "preflight"],
                check=False,
                capture_output=True,
                text=True,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(payload["state"], "not_ready")
            self.assertIn("not a directory", payload["reason"])
            self.assertNotIn("repo_root", payload)

    def test_preflight_requires_file_and_directory_surface_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "malformed"
            root.mkdir()
            (root / "AGENTS.md").mkdir()
            (root / "raw").write_text("not a directory\n", encoding="utf-8")
            (root / "wiki").write_text("not a directory\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(LOOP_ENTRYPOINT), "--repo-root", str(root), "preflight"],
                check=False,
                capture_output=True,
                text=True,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(payload["state"], "not_ready")
            self.assertEqual(
                payload["reasons"],
                [
                    "missing required wiki surfaces: AGENTS.md (file), raw (directory), wiki (directory)"
                ],
            )

    def test_dispatch_rejects_nested_root_override_for_every_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root, _source = self.make_vault(base)
            other = base / "other"
            other.mkdir()
            for command in ("workflow", "batch", "check"):
                with self.subTest(command=command):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(LOOP_ENTRYPOINT),
                            "--repo-root",
                            str(root),
                            command,
                            "--root",
                            str(other),
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    )

                    payload = json.loads(result.stderr)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(payload["state"], "not_ready")
                    self.assertIn("nested --root is forbidden", payload["reason"])
            for command in ("workflow", "batch", "check"):
                with self.subTest(command=command, spelling="abbreviated"):
                    required = {
                        "workflow": [
                            "start",
                            "--workflow",
                            "ingest",
                            "--source",
                            "raw/inbox/example.md",
                        ],
                        "batch": ["plan", "--source", "raw/inbox/example.md"],
                        "check": ["--source", "raw/inbox/example.md"],
                    }[command]
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(LOOP_ENTRYPOINT),
                            "--repo-root",
                            str(root),
                            command,
                            f"--roo={other}",
                            *required,
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    )

                    self.assertEqual(result.returncode, 2)
                    self.assertIn("unrecognized arguments", result.stderr)
            self.assertEqual(list(other.iterdir()), [])

    def write_coverage_receipt(
        self,
        root: Path,
        *,
        projected: int = 1,
        omitted: int = 0,
        deferred: int = 0,
    ) -> str:
        source = root / "raw" / "inbox" / "example.md"
        total = projected + omitted + deferred
        relative = "wiki/_meta/ingest_reports/ingest-example.md"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            'title: "Ingest coverage for Example"\n'
            "type: meta\n"
            "status: applied\n"
            "coverage_mode: full\n"
            "raw_path: raw/inbox/example.md\n"
            f'source_sha256: "{self.workflow.file_digest(source)}"\n'
            f"source_units_total: {total}\n"
            f"source_units_projected: {projected}\n"
            f"source_units_omitted: {omitted}\n"
            f"source_units_deferred: {deferred}\n"
            "---\n\n# Coverage\n\n- Raw path: `raw/inbox/example.md`\n",
            encoding="utf-8",
        )
        return relative

    def test_windows_lock_backend_acquires_and_releases_one_byte(self) -> None:
        class FakeMsvcrt:
            LK_NBLCK = 1
            LK_UNLCK = 2

            def __init__(self) -> None:
                self.calls: list[tuple[int, int]] = []

            def locking(self, _descriptor: int, mode: int, size: int) -> None:
                self.calls.append((mode, size))

        backend = FakeMsvcrt()
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "workflow.lock"
            with (
                mock.patch.object(self.workflow, "_fcntl", None),
                mock.patch.object(self.workflow, "_msvcrt", backend),
            ):
                descriptor = self.workflow.acquire_refresh_claim(lock_path, "wiki-test")
                self.assertIsNotNone(descriptor)
                self.workflow.release_refresh_claim(descriptor)

            claim = json.loads(lock_path.read_text(encoding="utf-8"))

        self.assertEqual(claim["run_id"], "wiki-test")
        self.assertEqual(backend.calls, [(backend.LK_NBLCK, 1), (backend.LK_UNLCK, 1)])

    def test_windows_nonblocking_contention_closes_descriptor(self) -> None:
        class BusyMsvcrt:
            LK_NBLCK = 1

            @staticmethod
            def locking(_descriptor: int, _mode: int, _size: int) -> None:
                raise OSError(errno.EACCES, "locked")

        opened: list[int] = []
        original_open = os.open

        def recording_open(*args, **kwargs):
            descriptor = original_open(*args, **kwargs)
            opened.append(descriptor)
            return descriptor

        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(self.workflow, "_fcntl", None),
                mock.patch.object(self.workflow, "_msvcrt", BusyMsvcrt()),
                mock.patch.object(self.workflow.os, "open", side_effect=recording_open),
            ):
                result = self.workflow.acquire_refresh_claim(
                    Path(tmp) / "workflow.lock", "wiki-test"
                )

        self.assertIsNone(result)
        with self.assertRaises(OSError):
            os.fstat(opened[0])

    def test_windows_blocking_contention_retries(self) -> None:
        class RetryingMsvcrt:
            LK_NBLCK = 1
            LK_UNLCK = 2

            def __init__(self) -> None:
                self.attempts = 0

            def locking(self, _descriptor: int, mode: int, _size: int) -> None:
                if mode == self.LK_NBLCK:
                    self.attempts += 1
                    if self.attempts == 1:
                        raise OSError(errno.EACCES, "locked")

        backend = RetryingMsvcrt()
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(self.workflow, "_fcntl", None),
                mock.patch.object(self.workflow, "_msvcrt", backend),
                mock.patch.object(self.workflow.time, "sleep") as sleep,
            ):
                descriptor = self.workflow.acquire_refresh_claim(
                    Path(tmp) / "workflow.lock", "wiki-test", blocking=True
                )
                self.workflow.release_refresh_claim(descriptor)

        self.assertEqual(backend.attempts, 2)
        sleep.assert_called_once_with(0.05)

    def test_claim_write_failure_closes_acquired_descriptor(self) -> None:
        class FakeMsvcrt:
            LK_NBLCK = 1

            @staticmethod
            def locking(_descriptor: int, _mode: int, _size: int) -> None:
                return None

        opened: list[int] = []
        original_open = os.open

        def recording_open(*args, **kwargs):
            descriptor = original_open(*args, **kwargs)
            opened.append(descriptor)
            return descriptor

        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(self.workflow, "_fcntl", None),
                mock.patch.object(self.workflow, "_msvcrt", FakeMsvcrt()),
                mock.patch.object(self.workflow.os, "open", side_effect=recording_open),
                mock.patch.object(
                    self.workflow.os, "write", side_effect=OSError("write failed")
                ),
            ):
                with self.assertRaisesRegex(OSError, "write failed"):
                    self.workflow.acquire_refresh_claim(
                        Path(tmp) / "workflow.lock", "wiki-test"
                    )

        with self.assertRaises(OSError):
            os.fstat(opened[0])

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

    def record_ready_completion(
        self,
        root: Path,
        run_id: str,
        *,
        coverage_receipt: bool = True,
        coverage_deferred: int = 0,
        posture: str = "ready",
    ) -> None:
        self.record_preflight(root, run_id)
        source_page = root / "wiki" / "sources" / "source-example.md"
        source_page.write_text(
            "---\ntitle: Example\ntype: source\nstatus: active\n"
            "raw_path: raw/inbox/example.md\n---\n\n# Example\n\nSummary.\n",
            encoding="utf-8",
        )
        self.workflow.record_stage(
            root, run_id, "register_or_resolve_source",
            refs=["wiki/sources/source-example.md"], na_reason=None, result=None,
            posture=None, reviewed_fingerprint=None,
        )
        source_page.write_text(
            source_page.read_text(encoding="utf-8") + "\n## Key Facts\n\n- Evidence.\n",
            encoding="utf-8",
        )
        self.workflow.record_stage(
            root, run_id, "update_source_page",
            refs=["wiki/sources/source-example.md"], na_reason=None, result=None,
            posture=None, reviewed_fingerprint=None,
        )
        self.workflow.record_stage(
            root, run_id, "update_affected_pages", refs=[],
            na_reason="no_affected_page_promotion", result=None, posture=None,
            reviewed_fingerprint=None,
        )
        final_refs = ["wiki/sources/source-example.md"]
        refresh_refs = ["wiki/_meta/log.md"]
        if coverage_receipt:
            receipt = self.write_coverage_receipt(
                root, projected=1, deferred=coverage_deferred
            )
            final_refs.append(receipt)
            refresh_refs.append(receipt)
        log = root / "wiki" / "_meta" / "log.md"
        log.write_text(
            log.read_text(encoding="utf-8") + "\n- Example ingest updated.\n",
            encoding="utf-8",
        )
        self.workflow.record_stage(
            root, run_id, "refresh_index_and_log", refs=refresh_refs,
            na_reason=None, result=None, posture=None, reviewed_fingerprint=None,
        )
        self.workflow.record_stage(
            root, run_id, "validate_structure",
            refs=["wiki/sources/source-example.md"], na_reason=None, result="passed",
            posture=None, reviewed_fingerprint=None,
        )
        fingerprint = self.workflow.state_fingerprint(root, "raw/inbox/example.md")
        self.workflow.record_stage(
            root, run_id, "final_review_completed",
            refs=final_refs, na_reason=None, result=None,
            posture=posture, reviewed_fingerprint=fingerprint,
        )

    def test_full_coverage_is_default_and_requires_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            run = self.workflow.start_run(root, "raw/inbox/example.md")
            self.assertEqual(run["coverage_mode"], "full")
            with self.assertRaisesRegex(
                self.workflow.WorkflowError, "requires exactly one ingest report"
            ):
                self.record_ready_completion(
                    root, run["run_id"], coverage_receipt=False
                )

    def test_full_coverage_rejects_deferred_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            run = self.workflow.start_run(root, "raw/inbox/example.md")
            with self.assertRaisesRegex(
                self.workflow.WorkflowError, "cannot leave deferred"
            ):
                self.record_ready_completion(
                    root,
                    run["run_id"],
                    coverage_deferred=1,
                )

    def test_explicit_summary_mode_does_not_require_full_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            run = self.workflow.start_run(
                root, "raw/inbox/example.md", coverage_mode="summary"
            )
            self.record_ready_completion(
                root, run["run_id"], coverage_receipt=False
            )
            result = self.workflow.finish_run(root, run["run_id"])

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["coverage_mode"], "summary")

    def test_deferred_full_coverage_can_close_review_as_partial_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            run = self.workflow.start_run(root, "raw/inbox/example.md")
            self.record_ready_completion(
                root,
                run["run_id"],
                coverage_deferred=1,
                posture="partial",
            )
            result = self.workflow.finish_run(root, run["run_id"])

        self.assertEqual(result["status"], "blocked")
        self.assertIn("FINAL_REVIEW_NOT_READY", result["blockers"])

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

            receipt = self.write_coverage_receipt(root)
            log = root / "wiki" / "_meta" / "log.md"
            log.write_text(log.read_text(encoding="utf-8") + "\n- Example ingest updated.\n", encoding="utf-8")
            self.workflow.record_stage(
                root, run_id, "refresh_index_and_log", refs=["wiki/_meta/log.md", receipt],
                na_reason=None, result=None, posture=None, reviewed_fingerprint=None,
            )
            self.workflow.record_stage(
                root, run_id, "validate_structure", refs=["wiki/sources/source-example.md"],
                na_reason=None, result="passed", posture=None, reviewed_fingerprint=None,
            )
            fingerprint = self.workflow.state_fingerprint(root, "raw/inbox/example.md")
            self.workflow.record_stage(
                root, run_id, "final_review_completed", refs=["wiki/sources/source-example.md", receipt],
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
        self.assertFalse(stale["retrieval_ready"])
        self.assertEqual(stale["retrieval_status"], "stale")

    def test_finish_refreshes_retrieval_once_and_semantic_unavailable_is_non_blocking(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            run = self.workflow.start_run(root, "raw/inbox/example.md")
            self.record_ready_completion(root, run["run_id"])
            with mock.patch.object(
                self.workflow,
                "run_retrieval_refresh",
                wraps=self.workflow.run_retrieval_refresh,
            ) as refresh:
                first = self.workflow.finish_run(root, run["run_id"])
                second = self.workflow.finish_run(root, run["run_id"])

        self.assertEqual(refresh.call_count, 1)
        self.assertTrue(first["wiki_complete"])
        self.assertTrue(first["retrieval_ready"])
        self.assertEqual(first["retrieval_status"], "ready")
        self.assertEqual(first["semantic_status"], "unavailable")
        self.assertEqual(first["retrieval_refresh"], second["retrieval_refresh"])
        self.assertIsNotNone(first["retrieval_refresh"]["corpus_fingerprint"])

    def test_sqlite_off_completion_reports_retrieval_not_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp), sqlite_enabled=False)
            run = self.workflow.start_run(root, "raw/inbox/example.md")
            self.record_ready_completion(root, run["run_id"])
            result = self.workflow.finish_run(root, run["run_id"])

        self.assertTrue(result["wiki_complete"])
        self.assertFalse(result["retrieval_ready"])
        self.assertEqual(result["retrieval_status"], "not_enabled")
        self.assertEqual(result["semantic_status"], "unavailable")

    def test_same_run_stale_snapshot_cannot_regress_ready_or_duplicate_refresh(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            run = self.workflow.start_run(root, "raw/inbox/example.md")
            run_id = run["run_id"]
            self.record_ready_completion(root, run_id)
            started = threading.Event()
            release = threading.Event()
            results = []

            def delayed_refresh(_root):
                started.set()
                self.assertTrue(release.wait(timeout=5))
                return {
                    "retrieval_ready": True,
                    "retrieval_status": "ready",
                    "semantic_status": "unavailable",
                }

            with mock.patch.object(
                self.workflow, "run_retrieval_refresh", side_effect=delayed_refresh
            ) as refresh:
                first_worker = threading.Thread(
                    target=lambda: results.append(
                        self.workflow.finish_run(root, run_id)
                    )
                )
                first_worker.start()
                self.assertTrue(started.wait(timeout=5))
                stale_worker = threading.Thread(
                    target=lambda: results.append(
                        self.workflow.finish_run(root, run_id)
                    )
                )
                stale_worker.start()
                stale_worker.join(timeout=0.1)
                self.assertTrue(stale_worker.is_alive())
                release.set()
                first_worker.join(timeout=5)
                stale_worker.join(timeout=5)

            _path, stored = self.workflow.load_run(root, run_id)

        self.assertFalse(first_worker.is_alive())
        self.assertFalse(stale_worker.is_alive())
        self.assertEqual(refresh.call_count, 1)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["run_status"] == "completed" for result in results))
        self.assertTrue(all(result["retrieval_status"] == "ready" for result in results))
        self.assertTrue(
            all(result["retrieval_refresh"]["attempt"] == 1 for result in results)
        )
        self.assertEqual(stored["retrieval_refresh"]["retrieval_status"], "ready")
        self.assertEqual(stored["retrieval_refresh"]["attempt"], 1)

    def test_interrupted_pending_refresh_reclaims_stale_process_lock_and_retries_once(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            run = self.workflow.start_run(root, "raw/inbox/example.md")
            run_id = run["run_id"]
            self.record_ready_completion(root, run_id)
            crash_script = """
import importlib.util
import os
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("crashing_workflow", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.run_retrieval_refresh = lambda _root: os._exit(23)
module.finish_run(Path(sys.argv[2]), sys.argv[3])
"""
            interrupted = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    crash_script,
                    str(WORKFLOW_PATH),
                    str(root),
                    run_id,
                ],
                check=False,
            )
            self.assertEqual(interrupted.returncode, 23)
            _path, pending = self.workflow.load_run(root, run_id)
            self.assertEqual(
                pending["retrieval_refresh"]["retrieval_status"], "pending"
            )
            self.assertEqual(pending["retrieval_refresh"]["attempt"], 1)

            recovered_payload = {
                "retrieval_ready": True,
                "retrieval_status": "ready",
                "semantic_status": "unavailable",
            }
            with mock.patch.object(
                self.workflow,
                "run_retrieval_refresh",
                return_value=recovered_payload,
            ) as refresh:
                recovered = self.workflow.finish_run(root, run_id)
                repeated = self.workflow.finish_run(root, run_id)

        self.assertEqual(refresh.call_count, 1)
        self.assertEqual(recovered["retrieval_status"], "ready")
        self.assertEqual(recovered["retrieval_refresh"]["attempt"], 2)
        self.assertEqual(recovered["retrieval_refresh"], repeated["retrieval_refresh"])

    def test_preexisting_unlocked_refresh_file_does_not_block_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            run = self.workflow.start_run(root, "raw/inbox/example.md")
            run_id = run["run_id"]
            self.record_ready_completion(root, run_id)
            self.workflow.retrieval_refresh_lock_path(root).write_text(
                '{"owner_pid": 999999, "claimed_at": "stale"}\n',
                encoding="utf-8",
            )
            with mock.patch.object(
                self.workflow,
                "run_retrieval_refresh",
                return_value={
                    "retrieval_ready": True,
                    "retrieval_status": "ready",
                    "semantic_status": "unavailable",
                },
            ) as refresh:
                result = self.workflow.finish_run(root, run_id)

        self.assertEqual(refresh.call_count, 1)
        self.assertEqual(result["retrieval_status"], "ready")

    def test_different_runs_share_one_repo_global_refresh_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            first = self.workflow.start_run(root, "raw/inbox/example.md")
            self.record_ready_completion(root, first["run_id"])
            _first_path, first_payload = self.workflow.load_run(root, first["run_id"])
            second_id = "wiki-second-completed-run"
            second_payload = json.loads(json.dumps(first_payload))
            second_payload["run_id"] = second_id
            self.workflow.write_json(
                self.workflow.run_path(root, second_id), second_payload
            )
            started = threading.Event()
            release = threading.Event()
            results = []

            def delayed_refresh(_root):
                started.set()
                self.assertTrue(release.wait(timeout=5))
                return {
                    "retrieval_ready": True,
                    "retrieval_status": "ready",
                    "semantic_status": "unavailable",
                }

            with mock.patch.object(
                self.workflow, "run_retrieval_refresh", side_effect=delayed_refresh
            ) as refresh:
                worker = threading.Thread(
                    target=lambda: results.append(
                        self.workflow.finish_run(root, first["run_id"])
                    )
                )
                worker.start()
                self.assertTrue(started.wait(timeout=5))
                blocked = self.workflow.finish_run(root, second_id)
                _second_path, stored_second = self.workflow.load_run(root, second_id)
                self.assertTrue(blocked["wiki_complete"])
                self.assertEqual(blocked["run_status"], "completed")
                self.assertEqual(blocked["retrieval_status"], "pending")
                self.assertEqual(stored_second["status"], "completed")
                self.assertEqual(
                    stored_second["retrieval_refresh"]["retrieval_status"],
                    "pending",
                )
                self.assertNotIn("attempt", stored_second["retrieval_refresh"])
                self.assertEqual(refresh.call_count, 1)
                release.set()
                worker.join(timeout=5)

            self.assertFalse(worker.is_alive())
            self.assertEqual(results[0]["retrieval_status"], "ready")
            claim = json.loads(
                self.workflow.retrieval_refresh_lock_path(root).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(claim["run_id"], first["run_id"])

            with mock.patch.object(
                self.workflow,
                "run_retrieval_refresh",
                return_value={
                    "retrieval_ready": True,
                    "retrieval_status": "ready",
                    "semantic_status": "unavailable",
                },
            ) as second_refresh:
                recovered = self.workflow.finish_run(root, second_id)

        self.assertEqual(second_refresh.call_count, 1)
        self.assertEqual(recovered["retrieval_status"], "ready")
        self.assertEqual(recovered["retrieval_refresh"]["attempt"], 1)

    def test_refresh_timeout_recovers_ready_lexical_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            self.workflow.run_retrieval_refresh(root)
            ready = self.workflow.subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"state":"ready","semantic_lane":"unavailable"}',
                stderr="",
            )
            with mock.patch.object(
                self.workflow.subprocess,
                "run",
                side_effect=[
                    self.workflow.subprocess.TimeoutExpired("refresh", 1),
                    ready,
                ],
            ):
                result = self.workflow.run_retrieval_refresh(root)

        self.assertTrue(result["retrieval_ready"])
        self.assertEqual(result["retrieval_status"], "ready")
        self.assertEqual(result["semantic_status"], "unavailable")

    def test_refresh_failure_fallback_preserves_semantic_status_and_counts(self) -> None:
        cases = (
            ("ready", 4, "ready"),
            ("unavailable", 2, "partial"),
            ("pending", 0, "pending"),
            ("unavailable", 0, "unavailable"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root, _source = self.make_vault(Path(tmp))
            failed = self.workflow.subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="refresh failed"
            )
            for semantic_lane, semantic_vectors, expected in cases:
                with self.subTest(semantic_lane=semantic_lane, vectors=semantic_vectors):
                    status = self.workflow.subprocess.CompletedProcess(
                        args=[],
                        returncode=0,
                        stdout=json.dumps(
                            {
                                "state": "ready",
                                "semantic_lane": semantic_lane,
                                "semantic_vectors": semantic_vectors,
                                "semantic_cohort_fingerprint": "sha256:test",
                            }
                        ),
                        stderr="",
                    )
                    with mock.patch.object(
                        self.workflow.subprocess,
                        "run",
                        side_effect=[failed, status],
                    ):
                        result = self.workflow.run_retrieval_refresh(root)

                    self.assertTrue(result["retrieval_ready"])
                    self.assertEqual(result["semantic_status"], expected)
                    self.assertEqual(result["semantic_vectors"], semantic_vectors)
                    self.assertEqual(
                        result["semantic_cohort_fingerprint"], "sha256:test"
                    )


if __name__ == "__main__":
    unittest.main()
