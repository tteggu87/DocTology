from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dashboard = load("dashboard_for_automation_test", SCRIPTS / "wiki_dashboard.py")
automation_module = load("dashboard_automation_under_test", SCRIPTS / "wiki_dashboard_automation.py")


class FakeProcess:
    def __init__(self, code=None):
        self.code = code

    def poll(self):
        return self.code


class FakeApp:
    def __init__(self, root, mode="wiki"):
        self.root = Path(root)
        self.mode = mode
        self.lock = threading.RLock()
        self.job = None
        self.process = None
        self.claim = None
        self.chat_busy = False
        self.live_runner = False
        self.live_pids = set()
        self.start_error = None
        self.starts = []

    def live_chat(self):
        return self.chat_busy

    def has_live_runner(self):
        if self.live_runner:
            return True
        return bool(self.process is not None and self.process.poll() is None)

    def start(self, message, selected, model=""):
        if self.start_error is not None:
            raise self.start_error
        job_id = f"job-{len(self.starts) + 1}"
        self.starts.append({"message": message, "selected": selected, "model": model})
        self.job = {"id": job_id, "status": "running", "runnerPid": 987654321}
        self.process = FakeProcess(None)
        self.claim = object()
        return {"id": job_id}


class WikiDashboardAutomationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "vault"
        for name in ("raw", "wiki/_meta", "state"):
            (self.root / name).mkdir(parents=True)
        (self.root / "AGENTS.md").write_text("# Wiki-only\n", encoding="utf-8")
        (self.root / "wiki/_meta/index.md").write_text("# Index\n", encoding="utf-8")
        (self.root / "wiki/_meta/log.md").write_text("# Log\n", encoding="utf-8")
        self.stages = {}
        self.references = {}
        self.app = FakeApp(self.root)
        self.automation = self.make_automation(self.app)
        self.automation.load(self.root, "wiki")

    def make_automation(self, app):
        def source_snapshot(root, mode="wiki"):
            sources = [
                {"id": source, "stage": stage, "references": self.references.get(source, [])}
                for source, stage in self.stages.items()
            ]
            return {"sources": sources}

        return automation_module.Automation(app, {
            "inside": dashboard.inside,
            "workflow": dashboard.workflow,
            "snapshot": source_snapshot,
            "process_alive": lambda pid: pid in app.live_pids,
        })

    @staticmethod
    def digest(data):
        return "sha256:" + hashlib.sha256(data).hexdigest()

    def write_raw(self, relative="raw/source.md", data=b"# Source\n\nEvidence.\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def queue_item(self, source="raw/source.md", run_requested=False, origin="upload"):
        self.write_raw(source)
        return self.automation.enqueue_source(source, origin, run_requested=run_requested)

    def finish_app(self, status="finished"):
        self.app.claim = None
        self.app.process.code = 0
        self.app.job["status"] = status

    def test_default_tick_and_worker_are_disabled_and_create_no_state(self):
        untouched = Path(self.temp.name) / "fresh"
        (untouched / "raw").mkdir(parents=True)
        app = FakeApp(untouched)
        automation = self.make_automation(app)
        status = automation.load(untouched, "wiki")
        self.assertTrue(status["available"])
        self.assertFalse(status["enabled"])
        self.assertFalse(status["autoRun"])
        self.assertEqual(status["sourcePath"], str((untouched / "raw").resolve()))
        automation.tick()
        worker_ticked = threading.Event()
        original_tick = automation.tick

        def observed_tick():
            worker_ticked.set()
            return original_tick()

        automation.tick = observed_tick
        automation.start_worker()
        self.assertTrue(worker_ticked.wait(1), "daemon worker did not execute its initial tick")
        automation.stop_worker()
        self.assertFalse((untouched / "state").exists())

    def test_fresh_instance_discovers_persisted_disabled_config_read_only(self):
        external = Path(self.temp.name) / "configured"
        external.mkdir()
        self.automation.configure({"sourcePath": str(external), "enabled": False, "autoRun": True})
        state_path = self.root / "state/dashboard_automation/state.json"
        before = state_path.stat().st_mtime_ns
        other = self.make_automation(FakeApp(self.root))
        other.load(self.root, "wiki")
        other.tick()
        self.assertEqual(str(external.resolve()), other.status()["sourcePath"])
        self.assertTrue(other.status()["autoRun"])
        self.assertEqual(before, state_path.stat().st_mtime_ns)

    def test_opt_in_baselines_existing_then_debounces_add_and_modify(self):
        self.write_raw("raw/existing.md", b"# Existing\n")
        self.automation.configure({"enabled": True})
        self.automation.tick()
        self.assertEqual([], self.automation.status()["queue"])
        added = self.write_raw("raw/new.md", b"# New\n\none\n")
        self.automation.tick()
        self.assertEqual([], self.automation.status()["queue"])
        self.automation.tick()
        first = self.automation.status()["queue"][0]
        self.assertEqual(("pending", "added", "raw/new.md"),
                         (first["status"], first["change"], first["source"]))
        added.write_bytes(b"# New\n\ntwo\n")
        self.automation.tick()
        self.automation.tick()
        items = {item["change"]: item for item in self.automation.status()["queue"]}
        self.assertEqual("pending", items["modified"]["status"])
        self.assertEqual("superseded", items["added"]["status"])

    def test_include_existing_requires_two_stable_observations(self):
        self.write_raw()
        self.automation.configure({"enabled": True, "includeExisting": True})
        self.automation.tick()
        self.assertEqual(0, self.automation.status()["counts"]["pending"])
        self.automation.tick()
        self.assertEqual(1, self.automation.status()["counts"]["pending"])

    def test_persisted_content_dedupe_survives_restart(self):
        self.write_raw()
        self.automation.configure({"enabled": True, "includeExisting": True})
        self.automation.tick()
        self.automation.tick()
        item_id = self.automation.status()["queue"][0]["id"]
        replacement = self.make_automation(FakeApp(self.root))
        replacement.load(self.root, "wiki")
        replacement.tick()
        replacement.tick()
        self.assertEqual([item_id], [item["id"] for item in replacement.status()["queue"]])

    def test_internal_source_keeps_actual_path_and_external_import_is_exact_and_unique(self):
        internal = self.write_raw("raw/folder/a.md", b"# Internal\n")
        self.automation.configure({"enabled": True, "includeExisting": True})
        self.automation.tick(); self.automation.tick()
        self.assertEqual("raw/folder/a.md", self.automation.status()["queue"][0]["source"])
        self.assertEqual(b"# Internal\n", internal.read_bytes())

        external = Path(self.temp.name) / "drop"
        external.mkdir()
        payload = b"# External\n\nExact bytes\r\n"
        watched = external / "report.md"
        watched.write_bytes(payload)
        self.automation.configure({"sourcePath": str(external), "enabled": True, "includeExisting": True})
        self.automation.tick(); self.automation.tick()
        item = self.automation.status()["queue"][0]
        copied = self.root / item["source"]
        self.assertTrue(item["source"].startswith("raw/inbox/watched/report-"))
        self.assertEqual(payload, copied.read_bytes())
        watched.write_bytes(b"# External\n\nSecond version\n")
        self.automation.tick(); self.automation.tick()
        copies = sorted((self.root / "raw/inbox/watched").glob("*.md"))
        self.assertEqual(2, len(copies))
        self.assertEqual(payload, copies[0].read_bytes() if copies[0] == copied else copies[1].read_bytes())

    def test_symlink_forbidden_roots_and_scan_limits_fail_safely(self):
        external = Path(self.temp.name) / "outside"
        external.mkdir()
        (external / "real.md").write_text("# Outside\n", encoding="utf-8")
        link = self.root / "raw/escape.md"
        try:
            link.symlink_to(external / "real.md")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        self.automation.configure({"enabled": True, "includeExisting": True})
        self.automation.tick(); self.automation.tick()
        self.assertEqual([], self.automation.status()["queue"])
        self.assertIn("symlink", self.automation.status()["lastError"].lower())
        for forbidden in (self.root, self.root / "wiki", self.root / "state", self.root / ".agents"):
            forbidden.mkdir(parents=True, exist_ok=True)
            with self.assertRaises(ValueError):
                self.automation.configure({"sourcePath": str(forbidden), "enabled": True})
        many = Path(self.temp.name) / "many"
        many.mkdir()
        for index in range(self.automation.MAX_FILES + 1):
            (many / f"{index}.md").write_text("# X\n", encoding="utf-8")
        self.automation.configure({"sourcePath": str(many), "enabled": True, "includeExisting": True})
        self.automation.tick()
        self.assertIn("scan limit", self.automation.status()["lastError"].lower())
        self.assertEqual(0, self.automation.status()["counts"]["pending"])

    def test_oversize_is_visible_and_not_queued(self):
        self.write_raw(data=b"x" * (self.automation.MAX_BYTES + 1))
        status = self.automation.configure({"enabled": True})
        self.assertIn(str(self.automation.MAX_BYTES), status["lastError"])
        self.automation.tick()
        status = self.automation.status()
        self.assertIn(str(self.automation.MAX_BYTES), status["lastError"])
        self.assertEqual(0, status["counts"]["pending"])

    def test_external_import_rechecks_live_runner_after_writer_lease(self):
        external = Path(self.temp.name) / "runner-drop"
        external.mkdir()
        (external / "source.md").write_bytes(b"# Deferred import\n")
        self.automation.configure({"sourcePath": str(external), "enabled": True, "includeExisting": True})
        self.automation.tick()
        self.app.live_runner = True
        self.automation.tick()
        self.assertEqual(0, self.automation.status()["counts"]["pending"])
        self.assertFalse((self.root / "raw/inbox/watched").exists())
        self.app.live_runner = False
        self.automation.tick()
        self.assertEqual(1, self.automation.status()["counts"]["pending"])
        self.assertEqual(1, len(list((self.root / "raw/inbox/watched").glob("*.md"))))

    def test_external_deletion_records_review_without_removing_import(self):
        external = Path(self.temp.name) / "drop"
        external.mkdir()
        watched = external / "source.md"
        watched.write_bytes(b"# Watched\n")
        self.automation.configure({"sourcePath": str(external), "enabled": True, "includeExisting": True})
        self.automation.tick(); self.automation.tick()
        copied = self.root / self.automation.status()["queue"][0]["source"]
        watched.unlink()
        self.automation.tick(); self.automation.tick()
        deleted = next(item for item in self.automation.status()["queue"] if item["status"] == "deleted")
        self.assertEqual("deleted", deleted["change"])
        self.assertTrue(copied.is_file())

    def test_live_chat_does_not_pause_explicit_manual_launch_but_writer_claim_does(self):
        item = self.queue_item()
        self.app.chat_busy = True
        result = self.automation.run_item(item["id"])
        self.assertEqual("running", result["status"])
        self.assertEqual([["raw/source.md"]], [start["selected"] for start in self.app.starts])
        self.assertIn("coverage_mode=full", self.app.starts[0]["message"])
        self.finish_app()
        self.app.claim = object()
        second = self.queue_item("raw/second.md")
        blocked = self.automation.run_item(second["id"])
        self.assertEqual("pending", blocked["status"])
        self.assertEqual(1, len(self.app.starts))

    def test_busy_ignores_live_chat_but_retains_all_writer_and_queue_guards(self):
        self.app.chat_busy = True
        self.assertFalse(self.automation._busy())
        self.app.claim = object()
        self.assertTrue(self.automation._busy())
        self.app.claim = None
        self.app.process = FakeProcess(None)
        self.assertTrue(self.automation._busy())
        self.app.process.code = 0
        self.app.live_runner = True
        self.assertTrue(self.automation._busy())
        self.app.live_runner = False
        self.automation.queue.append({"id": "running-item", "status": "running"})
        self.assertTrue(self.automation._busy())

    def test_live_runner_hook_pauses_dispatch(self):
        self.queue_item(run_requested=True)
        self.app.live_runner = True
        self.automation.tick()
        self.assertEqual([], self.app.starts)
        self.assertEqual("pending", self.automation.status()["queue"][0]["status"])
        self.app.live_runner = False
        self.automation.tick()
        self.assertEqual(1, len(self.app.starts))

    def test_retryable_writer_contention_keeps_authorized_item_pending(self):
        class RetryableBusy(ValueError):
            retryable = True

        item = self.queue_item(run_requested=True)
        self.app.start_error = RetryableBusy("writer lease is held")
        self.automation.tick()
        pending = next(row for row in self.automation.status()["queue"] if row["id"] == item["id"])
        self.assertEqual("pending", pending["status"])
        self.assertNotIn("jobId", pending)
        self.assertNotIn("startedAt", pending)
        self.assertNotIn("endedAt", pending)
        self.app.start_error = None
        self.automation.tick()
        self.assertEqual("running", self.automation.status()["queue"][0]["status"])
        self.assertEqual(1, len(self.app.starts))

    def test_group_dispatch_selects_only_authorized_current_unique_sources_and_binds_one_job(self):
        first = self.queue_item("raw/first.md", run_requested=True)
        second = self.queue_item("raw/second.md", run_requested=True)
        excluded = self.queue_item("raw/excluded.md", run_requested=False)
        self.automation.tick()
        self.assertEqual([[first["source"], second["source"]]], [start["selected"] for start in self.app.starts])
        rows = {row["id"]: row for row in self.automation.status()["queue"]}
        self.assertEqual("pending", rows[excluded["id"]]["status"])
        self.assertEqual("running", rows[first["id"]]["status"])
        self.assertEqual(rows[first["id"]]["jobId"], rows[second["id"]]["jobId"])

    def test_group_dispatch_supersedes_only_stale_selected_source(self):
        stale = self.queue_item("raw/stale.md", run_requested=True)
        current = self.queue_item("raw/current.md", run_requested=True)
        self.write_raw("raw/stale.md", b"# Changed\n")
        self.automation.tick()
        rows = {row["id"]: row for row in self.automation.status()["queue"]}
        self.assertEqual("superseded", rows[stale["id"]]["status"])
        self.assertEqual("running", rows[current["id"]]["status"])
        self.assertEqual([["raw/current.md"]], [start["selected"] for start in self.app.starts])

    def test_group_writer_contention_rolls_back_every_selected_item(self):
        class RetryableBusy(ValueError):
            retryable = True

        first = self.queue_item("raw/first.md", run_requested=True)
        second = self.queue_item("raw/second.md", run_requested=True)
        self.app.start_error = RetryableBusy("writer lease is held")
        self.automation.tick()
        rows = {row["id"]: row for row in self.automation.status()["queue"]}
        for item in (first, second):
            self.assertEqual("pending", rows[item["id"]]["status"])
            self.assertNotIn("jobId", rows[item["id"]])
            self.assertNotIn("startedAt", rows[item["id"]])

    def test_group_completion_uses_each_source_current_gates(self):
        first = self.queue_item("raw/first.md", run_requested=True)
        second = self.queue_item("raw/second.md", run_requested=True)
        self.automation.tick()
        self.stages[first["source"]] = "done"
        self.references[first["source"]] = ["wiki/sources/first.md"]
        self.finish_app()
        self.automation.tick()
        rows = {row["id"]: row for row in self.automation.status()["queue"]}
        self.assertEqual("completed", rows[first["id"]]["status"])
        self.assertEqual("needs_attention", rows[second["id"]]["status"])

    def test_auto_dispatch_requires_enabled_and_auto_run(self):
        self.queue_item(run_requested=False)
        self.automation.configure({"enabled": False, "autoRun": True})
        self.automation.tick()
        self.assertEqual([], self.app.starts)
        self.automation.configure({"enabled": True, "autoRun": True})
        self.automation.tick()
        self.assertEqual(1, len(self.app.starts))

    def test_source_path_switch_does_not_auto_run_old_watcher_rows(self):
        first = Path(self.temp.name) / "first-watch"
        second = Path(self.temp.name) / "second-watch"
        first.mkdir(); second.mkdir()
        (first / "old.md").write_bytes(b"# Old folder\n")
        self.automation.configure({
            "sourcePath": str(first), "enabled": True, "autoRun": False, "includeExisting": True,
        })
        self.automation.tick(); self.automation.tick()
        old = self.automation.status()["queue"][0]
        persisted = json.loads((self.root / "state/dashboard_automation/state.json").read_text(encoding="utf-8"))
        self.assertEqual(str(first.resolve()), persisted["queue"][0]["_watchSourcePath"])
        old_generation = persisted["queue"][0]["_watchGeneration"]
        self.automation.configure({"sourcePath": str(second), "enabled": True, "autoRun": True})
        self.automation.tick()
        self.assertEqual([], self.app.starts)
        current = json.loads((self.root / "state/dashboard_automation/state.json").read_text(encoding="utf-8"))
        self.assertGreater(current["config"]["generation"], old_generation)
        launched = self.automation.run_item(old["id"])
        self.assertEqual("running", launched["status"])
        self.assertEqual([old["source"]], self.app.starts[0]["selected"])

    def test_disabling_pauses_automatic_pending_dispatch_without_stopping_running(self):
        first = self.queue_item("raw/first.md")
        self.queue_item("raw/second.md")
        self.automation.configure({"enabled": True, "autoRun": True})
        self.automation.tick()
        self.assertEqual(1, len(self.app.starts))
        self.assertEqual([first["source"], "raw/second.md"], self.app.starts[0]["selected"])
        self.automation.configure({"enabled": False})
        self.assertIsNone(self.app.process.poll())
        self.finish_app()
        self.automation.tick()
        self.assertEqual(1, len(self.app.starts))
        second = next(item for item in self.automation.status()["queue"] if item["source"] == "raw/second.md")
        self.assertEqual("needs_attention", second["status"])

    def test_finished_pi_without_gates_needs_attention_but_verified_done_completes(self):
        item = self.queue_item(run_requested=True)
        self.automation.tick()
        self.finish_app()
        self.automation.tick()
        result = next(row for row in self.automation.status()["queue"] if row["id"] == item["id"])
        self.assertEqual("needs_attention", result["status"])

        other = self.write_raw("raw/done.md", b"# Done\n")
        second = self.automation.enqueue_source("raw/done.md", "upload", run_requested=True)
        self.automation.tick()
        self.stages["raw/done.md"] = "done"
        self.references["raw/done.md"] = ["wiki/sources/done.md"]
        self.finish_app()
        self.automation.tick()
        completed = next(row for row in self.automation.status()["queue"] if row["id"] == second["id"])
        self.assertEqual("completed", completed["status"])
        self.assertEqual(["wiki/sources/done.md"], completed["targets"])
        self.assertEqual(b"# Done\n", other.read_bytes())

    def test_current_hash_must_match_verified_done(self):
        item = self.queue_item(run_requested=True)
        self.automation.tick()
        self.stages["raw/source.md"] = "done"
        self.write_raw(data=b"# Source changed\n")
        self.finish_app()
        self.automation.tick()
        result = next(row for row in self.automation.status()["queue"] if row["id"] == item["id"])
        self.assertEqual("needs_attention", result["status"])

    def test_completed_item_is_demoted_when_later_gates_become_stale(self):
        item = self.queue_item(run_requested=True)
        self.automation.tick()
        self.stages["raw/source.md"] = "done"
        self.finish_app()
        self.automation.tick()
        self.assertEqual("completed", self.automation.status()["queue"][0]["status"])
        self.stages["raw/source.md"] = "blocked"
        self.automation.tick()
        demoted = next(row for row in self.automation.status()["queue"] if row["id"] == item["id"])
        self.assertEqual("needs_attention", demoted["status"])
        self.assertIn("gates changed", demoted["reason"])
        self.assertEqual(1, len(self.app.starts))

    def test_attention_item_becomes_completed_when_current_gates_restore(self):
        item = self.queue_item(run_requested=True)
        self.automation.tick()
        self.finish_app()
        self.automation.tick()
        self.assertEqual("needs_attention", self.automation.status()["queue"][0]["status"])
        self.stages["raw/source.md"] = "done"
        self.references["raw/source.md"] = ["wiki/sources/source.md"]
        self.automation.tick()
        restored = next(row for row in self.automation.status()["queue"] if row["id"] == item["id"])
        self.assertEqual("completed", restored["status"])
        self.assertEqual(["wiki/sources/source.md"], restored["targets"])
        self.assertEqual(1, len(self.app.starts))

    def test_run_item_short_circuits_when_current_gates_already_restored(self):
        item = self.queue_item(run_requested=True)
        self.automation.tick()
        self.finish_app()
        self.automation.tick()
        self.stages["raw/source.md"] = "done"
        restored = self.automation.run_item(item["id"])
        self.assertEqual("completed", restored["status"])
        self.assertEqual(1, len(self.app.starts))

    def test_project_mode_never_creates_automation_state(self):
        project = Path(self.temp.name) / "project"
        (project / "wiki").mkdir(parents=True)
        app = FakeApp(project, "project")
        automation = self.make_automation(app)
        status = automation.load(project, "project")
        self.assertFalse(status["available"])
        self.assertFalse(status["enabled"])
        self.assertIn("read-only", status["lastError"])
        automation.configure({"enabled": True, "autoRun": True})
        automation.tick()
        self.assertFalse((project / "state").exists())
        with self.assertRaises(ValueError):
            automation.enqueue_source("raw/x.md", "conversation")

    def test_explicit_attention_retry_starts_despite_live_chat(self):
        item = self.queue_item(run_requested=True)
        self.automation.tick()
        old_job_id = self.app.job["id"]
        self.finish_app()
        self.automation.tick()
        self.assertEqual("needs_attention", self.automation.status()["queue"][0]["status"])
        self.app.chat_busy = True
        retried = self.automation.run_item(item["id"])
        self.assertEqual("running", retried["status"])
        self.assertNotEqual(old_job_id, retried["jobId"])
        self.assertEqual(2, len(self.app.starts))

    def test_attention_retry_uses_parallel_resume_hook_when_accepted(self):
        item = self.queue_item(run_requested=True)
        self.automation.tick()
        old_job_id = self.app.job["id"]
        self.finish_app()
        self.automation.tick()
        calls = []
        def resume(job_id, source):
            calls.append((job_id, source))
            return {"id": old_job_id}
        self.app.resume_queued_parallel = resume
        retried = self.automation.run_item(item["id"])
        self.assertEqual("running", retried["status"])
        self.assertEqual(old_job_id, retried["jobId"])
        self.assertEqual([(old_job_id, item["source"])], calls)
        self.assertEqual(1, len(self.app.starts))

    def test_attention_retry_falls_back_only_when_parallel_hook_has_no_record(self):
        item = self.queue_item(run_requested=True)
        self.automation.tick()
        self.finish_app()
        self.automation.tick()
        old_job_id = self.app.job["id"]
        calls = []
        def resume(job_id, source):
            calls.append((job_id, source))
            return None
        self.app.resume_queued_parallel = resume
        retried = self.automation.run_item(item["id"])
        self.assertEqual("running", retried["status"])
        self.assertEqual([(old_job_id, item["source"])], calls)
        self.assertEqual(2, len(self.app.starts))

    def test_attention_retry_parallel_hook_failure_keeps_attention_without_fallback(self):
        item = self.queue_item(run_requested=True)
        self.automation.tick()
        self.finish_app()
        self.automation.tick()
        def resume(job_id, source):
            raise ValueError("parallel batch is stale")
        self.app.resume_queued_parallel = resume
        with self.assertRaisesRegex(ValueError, "parallel batch is stale"):
            self.automation.run_item(item["id"])
        row = next(row for row in self.automation.status()["queue"] if row["id"] == item["id"])
        self.assertEqual("needs_attention", row["status"])
        self.assertEqual(1, len(self.app.starts))

    def test_attention_retry_rejects_changed_hash_and_live_interrupted_runner(self):
        item = self.queue_item(run_requested=True)
        self.automation.tick()
        self.finish_app()
        self.automation.tick()
        self.write_raw(data=b"# Changed after failure\n")
        with self.assertRaises(ValueError):
            self.automation.run_item(item["id"])
        self.write_raw()
        self.app.job.update({"status": "interrupted", "runnerPid": 12345})
        self.app.live_pids.add(12345)
        with self.assertRaises(ValueError):
            self.automation.run_item(item["id"])

    def test_interrupted_live_runner_stays_running_until_pid_exits(self):
        self.queue_item(run_requested=True)
        self.automation.tick()
        self.app.claim = None
        self.app.process.code = 0
        self.app.job.update({"status": "interrupted", "runnerPid": 12345})
        self.app.live_pids.add(12345)
        self.automation.tick()
        self.assertEqual("running", self.automation.status()["queue"][0]["status"])
        self.app.live_pids.clear()
        self.automation.tick()
        self.assertEqual("needs_attention", self.automation.status()["queue"][0]["status"])

    def test_interrupted_restart_becomes_attention_without_retry(self):
        item = self.queue_item(run_requested=True)
        self.automation.tick()
        self.assertEqual(1, len(self.app.starts))
        restarted_app = FakeApp(self.root)
        restarted = self.make_automation(restarted_app)
        status = restarted.load(self.root, "wiki")
        recovered = next(row for row in status["queue"] if row["id"] == item["id"])
        self.assertEqual("needs_attention", recovered["status"])
        restarted.tick()
        self.assertEqual([], restarted_app.starts)

    def test_conversation_enqueue_dedupes_watcher_and_preserves_title(self):
        data = b"# Chat source\n\nSaved answer.\n"
        self.write_raw("raw/inbox/chat.md", data)
        item = self.automation.enqueue_source(
            "raw/inbox/chat.md", "conversation", self.digest(data), run_requested=True,
            metadata={"title": "Saved conversation"},
        )
        self.automation.configure({"enabled": True, "sourcePath": str(self.root / "raw"), "includeExisting": True})
        self.automation.tick(); self.automation.tick()
        queue = self.automation.status()["queue"]
        self.assertEqual(1, len(queue))
        self.assertEqual(item["id"], queue[0]["id"])
        self.assertEqual("conversation", queue[0]["change"])
        self.assertEqual("Saved conversation", queue[0]["title"])

    def test_conversation_enqueue_promotes_same_pending_watcher_item(self):
        data = b"# Shared\n"
        self.write_raw("raw/shared.md", data)
        self.automation.configure({"enabled": True, "includeExisting": True})
        self.automation.tick(); self.automation.tick()
        watched_id = self.automation.status()["queue"][0]["id"]
        instruction = "Treat this conversation as unverified provenance."
        result = self.automation.enqueue_source(
            "raw/shared.md", "conversation", self.digest(data), run_requested=True,
            metadata={"title": "Conversation title", "instruction": instruction},
        )
        self.assertEqual(watched_id, result["id"])
        self.assertEqual("conversation", result["origin"])
        self.assertEqual("conversation", result["change"])
        self.assertEqual("Conversation title", result["title"])
        persisted = json.loads((self.root / "state/dashboard_automation/state.json").read_text(encoding="utf-8"))
        self.assertEqual(instruction, persisted["queue"][0]["_instruction"])
        self.automation.configure({"enabled": False, "autoRun": False})
        self.automation.tick()
        self.assertEqual(1, len(self.app.starts))
        self.assertIn("Trusted source-handling instruction", self.app.starts[0]["message"])
        self.assertIn(instruction, self.app.starts[0]["message"])

    def test_instruction_is_bounded(self):
        self.write_raw()
        with self.assertRaises(ValueError):
            self.automation.enqueue_source(
                "raw/source.md", "conversation", run_requested=True,
                metadata={"instruction": "x" * 4_001},
            )

    def test_raw_subfolder_is_watchable_and_keeps_actual_raw_path(self):
        self.write_raw("raw/inbox/manual/note.md", b"# Nested raw\n")
        watched = self.root / "raw/inbox/manual"
        self.automation.configure({"sourcePath": str(watched), "enabled": True, "includeExisting": True})
        self.automation.tick(); self.automation.tick()
        self.assertEqual("raw/inbox/manual/note.md", self.automation.status()["queue"][0]["source"])
        generated = self.root / "raw/inbox/watched"
        generated.mkdir(parents=True, exist_ok=True)
        with self.assertRaises(ValueError):
            self.automation.configure({"sourcePath": str(generated), "enabled": True})

    def test_status_pages_queue_without_losing_pending_state(self):
        for index in range(105):
            source = f"raw/{index}.md"
            self.write_raw(source, f"# {index}\n".encode())
            self.automation.enqueue_source(source, "upload")
        first = self.automation.status()
        second = self.automation.status(offset=100)
        clamped = self.automation.status(offset=1_000_000)
        self.assertEqual(100, len(first["queue"]))
        self.assertEqual({"offset": 0, "limit": 100, "total": 105}, first["queuePage"])
        self.assertEqual(5, len(second["queue"]))
        self.assertEqual({"offset": 100, "limit": 100, "total": 105}, second["queuePage"])
        self.assertEqual(second["queue"], clamped["queue"])
        self.assertEqual(100, clamped["queuePage"]["offset"])
        self.assertEqual(105, first["counts"]["pending"])
        self.assertEqual(first["counts"], second["counts"])
        for invalid in (-1, 1_000_001, 1.5, True, "100"):
            with self.subTest(offset=invalid), self.assertRaises(ValueError):
                self.automation.status(offset=invalid)
        persisted = json.loads((self.root / "state/dashboard_automation/state.json").read_text(encoding="utf-8"))
        self.assertEqual(105, len(persisted["queue"]))


if __name__ == "__main__":
    unittest.main()
