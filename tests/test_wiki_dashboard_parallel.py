from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents/skills/llm-wiki-loop/scripts/wiki_dashboard.py"
spec = importlib.util.spec_from_file_location("dashboard_parallel_under_test", SCRIPT)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


FAKE_PI = r'''import json, os, sys
from pathlib import Path
capture = Path(sys.argv[1])
capture.write_text(json.dumps({"argv": sys.argv[2:], "env": {
    "role": os.environ.get("WIKI_STUDIO_BATCH_ROLE"),
    "tool": os.environ.get("WIKI_STUDIO_TOOL_URL"),
}}))
for line in sys.stdin:
    event = json.loads(line)
    if event.get("type") == "prompt":
        capture.with_suffix(".prompt").write_text(event["message"])
        print(json.dumps({"id": event.get("id"), "type": "response", "success": True}), flush=True)
        print(json.dumps({"type": "agent_settled"}), flush=True)
        break
    if event.get("type") == "abort":
        print(json.dumps({"type": "agent_settled"}), flush=True)
        break
'''


class FakePreparation:
    instances = []
    records = {}
    ready = False
    fail_start = False

    def __init__(self, root, sources, job_id, pi_command, model, helpers, on_change=None,
                 parallelism=3, resume=None):
        self.root, self.sources, self.job_id = Path(root), list(sources), job_id
        self.pi_command, self.model, self.helpers = pi_command, model, helpers
        self.parallelism, self.resume, self.on_change = parallelism, resume, on_change
        self.closed = False
        self.phase = "planning"
        self.cancelled, self.retried = [], []
        self.workers = [{"id": f"worker-{n}", "source": source, "status": "pending", "attempt": 0}
                        for n, source in enumerate(sources, 1)]
        type(self).instances.append(self)

    def start(self):
        if type(self).fail_start:
            raise ValueError("coordinator bridge rejected")
        return {"WIKI_STUDIO_BATCH_ROLE": "coordinator", "WIKI_STUDIO_TOOL_URL": "http://127.0.0.1:9"}

    def coordinator_ready(self):
        return type(self).ready

    def snapshot(self):
        return {"batchId": "batch-1", "phase": self.phase, "parallelism": self.parallelism,
                "workers": [dict(row) for row in self.workers]}

    def cancel(self, source=None):
        self.cancelled.append(source)
        for row in self.workers:
            if source is None or row["source"] == source:
                row["status"] = "stopped"

    def retry(self, source):
        self.retried.append(source)

    def close(self):
        self.closed = True

    @classmethod
    def read_record(cls, root, job_id):
        return json.loads(json.dumps(cls.records[job_id]))

    @classmethod
    def live_runners(cls, root, process_alive):
        return []


class WikiDashboardParallelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "vault"
        for folder in ("raw/inbox", "wiki/_meta", "wiki/sources", "state"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        (self.root / "AGENTS.md").write_text("# Wiki contract\n", encoding="utf-8")
        (self.root / "wiki/_meta/index.md").write_text("# Index\n", encoding="utf-8")
        (self.root / "wiki/_meta/log.md").write_text("# Log\n", encoding="utf-8")
        self.sources = ["raw/inbox/one.md", "raw/inbox/two.md"]
        for source in self.sources:
            (self.root / source).write_text("# Evidence\n", encoding="utf-8")
        self.capture = Path(self.temp.name) / "pi.json"
        self.fake_pi = Path(self.temp.name) / "pi.py"
        self.fake_pi.write_text(FAKE_PI, encoding="utf-8")
        FakePreparation.instances, FakePreparation.records = [], {}
        FakePreparation.ready, FakePreparation.fail_start = False, False
        self.apps = []

    def tearDown(self):
        for app in self.apps:
            app.stop_all()

    def app(self):
        app = dashboard.Dashboard(self.root, [sys.executable, str(self.fake_pi), str(self.capture)])
        self.apps.append(app)
        return app

    def wait_for(self, condition, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(.01)
        self.fail("background dashboard operation did not settle")

    def test_single_source_still_starts_directly_without_parallel_environment(self):
        app = self.app()
        app.start("single source", [self.sources[0]])
        self.wait_for(lambda: self.capture.with_suffix(".prompt").exists())
        launched = json.loads(self.capture.read_text())
        self.assertIsNone(launched["env"]["role"])
        self.assertNotIn("wiki_dashboard_batch_extension.mjs", " ".join(launched["argv"]))
        self.wait_for(lambda: app.claim is None)
        self.assertIsNone(app.preparation)

    def test_multi_source_wires_coordinator_role_extension_and_requested_model_without_default(self):
        app = self.app()
        FakePreparation.ready = True
        with mock.patch.object(dashboard.parallel_module, "BatchPreparation", FakePreparation):
            app.start("parallel source", self.sources, model="provider/model", parallelism=2)
            self.wait_for(lambda: self.capture.with_suffix(".prompt").exists())
            launched = json.loads(self.capture.read_text())
            preparation = FakePreparation.instances[-1]
            self.assertEqual("provider/model", preparation.model)
            self.assertEqual(2, preparation.parallelism)
            self.assertEqual("coordinator", launched["env"]["role"])
            self.assertIn("wiki_dashboard_batch_extension.mjs", " ".join(launched["argv"]))
            self.assertIn("--model", launched["argv"])
            self.wait_for(lambda: app.claim is None)

    def test_rejects_duplicate_oversized_sources_and_invalid_parallelism_before_coordinator(self):
        app = self.app()
        with mock.patch.object(dashboard.parallel_module, "BatchPreparation", FakePreparation):
            for selected, parallelism in (([self.sources[0], self.sources[0]], 2),
                                          (self.sources * 7, 2), (self.sources, 0),
                                          (self.sources, True), (self.sources, 5)):
                with self.assertRaises(ValueError):
                    app.start("reject", selected, parallelism=parallelism)
        self.assertEqual([], FakePreparation.instances)

    def test_prompt_waits_for_ready_and_unready_coordinator_cannot_finish(self):
        app = self.app()
        with mock.patch.object(dashboard.parallel_module, "BatchPreparation", FakePreparation):
            app.start("must wait", self.sources)
            self.wait_for(lambda: self.capture.exists())
            self.assertFalse(self.capture.with_suffix(".prompt").exists())
            preparation = FakePreparation.instances[-1]
            FakePreparation.ready = True
            self.wait_for(lambda: self.capture.with_suffix(".prompt").exists())
            self.wait_for(lambda: app.claim is None)
            self.assertEqual("failed", app.job["status"])
            self.assertFalse(preparation.closed is False)

    def test_failed_coordinator_setup_is_failed_and_cleaned_not_finished(self):
        app = self.app()
        FakePreparation.fail_start = True
        with mock.patch.object(dashboard.parallel_module, "BatchPreparation", FakePreparation):
            with self.assertRaisesRegex(ValueError, "coordinator bridge rejected"):
                app.start("broken", self.sources)
        self.assertEqual("failed", app.job["status"])
        self.assertTrue(FakePreparation.instances[-1].closed)
        self.assertIsNone(app.claim)

    def test_public_source_controls_require_identity_and_only_permitted_worker_state(self):
        app = self.app()
        FakePreparation.ready = False
        with mock.patch.object(dashboard.parallel_module, "BatchPreparation", FakePreparation):
            app.start("controls", self.sources)
            prep = FakePreparation.instances[-1]
            prep.workers[0]["status"] = "reading"
            public = app.state()["job"]["parallel"]["workers"]
            self.assertTrue(public[0]["canStop"])
            self.assertFalse(public[0]["canRetry"])
            for body in ({"expectedRoot": "wrong", "jobId": app.job["id"], "source": self.sources[0]},
                         {"expectedRoot": str(self.root.resolve()), "jobId": "job-other", "source": self.sources[0]},
                         {"expectedRoot": str(self.root.resolve()), "jobId": app.job["id"], "source": "raw/inbox/not-in-batch.md"}):
                with self.assertRaises(ValueError):
                    app.action("batch-worker-stop", body)
            result = app.action("batch-worker-stop", {"expectedRoot": str(self.root.resolve()),
                                                        "jobId": app.job["id"], "source": self.sources[0]})
            self.assertEqual({"ok": True, "source": self.sources[0], "requested": "stop"}, result)
            self.wait_for(lambda: prep.cancelled == [self.sources[0]])
            prep.phase = "preparing"
            retry_public = app.state()["job"]["parallel"]["workers"][0]
            self.assertTrue(retry_public["canRetry"])
            self.assertEqual({"ok": True, "source": self.sources[0], "requested": "retry"},
                             app.action("batch-worker-retry", {"expectedRoot": str(self.root.resolve()),
                                                                "jobId": app.job["id"], "source": self.sources[0]}))
            self.assertEqual([self.sources[0]], prep.retried)

    def test_resume_prompt_replays_exact_complete_frozen_plans(self):
        app = self.app()
        plans = [
            {"source": self.sources[1], "instructions": "두 번째 원문의 고유 사실을 보존합니다."},
            {"source": self.sources[0], "instructions": "첫 번째 원문에서 검증된 주장만 준비합니다."},
        ]
        resume = {"jobId": "job-frozen-plans", "workers": plans}
        FakePreparation.ready = True
        with mock.patch.object(dashboard.parallel_module, "BatchPreparation", FakePreparation):
            app.start("same batch retry", self.sources, resume=resume)
            self.wait_for(lambda: self.capture.with_suffix(".prompt").exists())
            launched = json.loads(self.capture.read_text())
            system_prompt = launched["argv"][launched["argv"].index("--append-system-prompt") + 1]
            encoded = system_prompt.split("<frozen-prepare-arguments>\n", 1)[1].split(
                "\n</frozen-prepare-arguments>", 1)[0]
            self.assertEqual({"plans": plans}, json.loads(encoded))
            self.assertIn("Do not regenerate, summarize, or edit", system_prompt)
            self.wait_for(lambda: app.claim is None)

    def test_partial_or_missing_frozen_plans_are_not_invented_in_resume_prompt(self):
        FakePreparation.ready = True
        cases = (
            {"jobId": "job-partial-plans", "workers": [{"source": self.sources[0], "instructions": "only one"}]},
            {"jobId": "job-no-plans", "workers": [{"source": source} for source in self.sources]},
        )
        with mock.patch.object(dashboard.parallel_module, "BatchPreparation", FakePreparation):
            for resume in cases:
                self.capture.unlink(missing_ok=True)
                self.capture.with_suffix(".prompt").unlink(missing_ok=True)
                app = self.app()
                app.start("resume safely", self.sources, resume=resume)
                self.wait_for(lambda: self.capture.with_suffix(".prompt").exists())
                launched = json.loads(self.capture.read_text())
                system_prompt = launched["argv"][launched["argv"].index("--append-system-prompt") + 1]
                self.assertNotIn("<frozen-prepare-arguments>", system_prompt)
                self.wait_for(lambda: app.claim is None)

    def test_persisted_cleanup_pending_hides_retry_until_dead_pid_recovery(self):
        app = self.app()
        job_id = "job-cleanup"
        app.job = {"id": job_id, "status": "stopped", "message": "recover", "sources": self.sources}
        with mock.patch.object(dashboard.parallel_module, "BatchPreparation", FakePreparation):
            FakePreparation.records[job_id] = {
                "jobId": job_id, "inputs": {"parallelism": 2}, "workers": [{
                    "id": "worker-1", "source": self.sources[0], "status": "stopped", "attempt": 1,
                    "runnerPid": os.getpid(), "cleanupPending": True, "retryEligible": False,
                }],
            }
            blocked = app.state()["job"]["parallel"]["workers"][0]
            self.assertTrue(blocked["cleanupPending"])
            self.assertFalse(blocked["canRetry"])
            FakePreparation.records[job_id]["workers"][0]["runnerPid"] = 999999999
            recovered = app.state()["job"]["parallel"]["workers"][0]
            self.assertFalse(recovered["cleanupPending"])
            self.assertTrue(recovered["canRetry"])

    def prepared_record(self, job_id="job-integrate", *, statuses=None, apply_event=None):
        statuses = statuses or ["prepared"] * len(self.sources)
        return {
            "jobId": job_id,
            "batchId": "batch-integrate",
            "inputs": {"model": "frozen-provider-model", "parallelism": 2},
            "retrySources": [self.sources[0]],
            "workers": [{"id": f"worker-{number}", "source": source, "status": status,
                         "attempt": 1, "cleanupPending": False}
                        for number, (source, status) in enumerate(zip(self.sources, statuses), 1)],
            "manifest": {"apply_event": apply_event},
        }

    def test_batch_resume_requires_current_identity_and_reuses_frozen_all_source_record(self):
        app = self.app()
        job_id = "job-integrate"
        record = self.prepared_record(job_id)
        app.job = {"id": job_id, "status": "stopped", "message": "finish integration",
                   "sources": list(self.sources)}
        with mock.patch.object(dashboard.parallel_module, "BatchPreparation", FakePreparation), \
             mock.patch.object(dashboard.batch, "load_manifest", return_value=("ignored", {"apply_event": None})), \
             mock.patch.object(app, "start", return_value={"id": job_id}) as started:
            FakePreparation.records[job_id] = record
            for body in ({"expectedRoot": "wrong", "jobId": job_id},
                         {"expectedRoot": str(self.root.resolve()), "jobId": "job-other"}):
                with self.assertRaises(ValueError):
                    app.action("batch-resume", body)
            result = app.action("batch-resume", {"expectedRoot": str(self.root.resolve()), "jobId": job_id})
        self.assertEqual({"id": job_id}, result)
        self.assertEqual(1, started.call_count)
        args, kwargs = started.call_args.args, started.call_args.kwargs
        self.assertEqual("finish integration", args[0])
        self.assertEqual(self.sources, args[1])
        self.assertEqual("frozen-provider-model", args[2])
        self.assertEqual(2, kwargs["parallelism"])
        self.assertNotIn("retrySources", kwargs["resume"])
        self.assertEqual(self.sources, [row["source"] for row in kwargs["resume"]["workers"]])

    def test_batch_resume_is_suppressed_for_active_applied_or_partial_preparation(self):
        app = self.app()
        job_id = "job-suppressed"
        app.job = {"id": job_id, "status": "stopped", "message": "finish", "sources": self.sources}
        cases = (
            ("active", self.prepared_record(job_id), "running", mock.Mock(poll=mock.Mock(return_value=None)), None),
            ("applied", self.prepared_record(job_id, apply_event={"id": "already-applied"}), "stopped", None, {"id": "already-applied"}),
            ("partial", self.prepared_record(job_id, statuses=["prepared", "stopped"]), "stopped", None, None),
        )
        with mock.patch.object(dashboard.parallel_module, "BatchPreparation", FakePreparation), \
             mock.patch.object(dashboard.batch, "load_manifest") as load_manifest:
            for _name, record, status, process, apply_event in cases:
                app.job["status"], app.process, app.claim = status, process, None
                FakePreparation.records[job_id] = record
                load_manifest.return_value = ("ignored", {"apply_event": apply_event})
                self.assertFalse(app._parallel_public()["canResumeIntegration"])
                with mock.patch.object(app, "start") as started:
                    with self.assertRaises(ValueError):
                        app.action("batch-resume", {"expectedRoot": str(self.root.resolve()), "jobId": job_id})
                    started.assert_not_called()
        app.process = None

    def test_connect_blocks_owned_cleanup_pending_preparation_without_claim_or_live_process(self):
        app = self.app()
        other = Path(self.temp.name) / "other-vault"
        for folder in ("raw/inbox", "wiki/_meta", "state"):
            (other / folder).mkdir(parents=True, exist_ok=True)
        (other / "AGENTS.md").write_text("# Wiki contract\n", encoding="utf-8")
        (other / "wiki/_meta/index.md").write_text("# Index\n", encoding="utf-8")
        (other / "wiki/_meta/log.md").write_text("# Log\n", encoding="utf-8")
        preparation = mock.Mock()
        preparation.snapshot.return_value = {"workers": [{"source": self.sources[0], "status": "stopped",
                                                            "cleanupPending": True}]}
        app.preparation, app.claim, app.process = preparation, None, None
        with self.assertRaises(ValueError):
            app.connect(str(other))
        self.assertEqual(self.root.resolve(), app.root)

    def test_stopped_record_resume_stays_parallel_and_never_starts_single_source(self):
        app = self.app()
        job_id = "job-resume"
        FakePreparation.records[job_id] = {
            "jobId": job_id, "inputs": {"model": "", "parallelism": 2},
            "workers": [{"source": self.sources[0], "status": "stopped"}],
        }
        app.job = {"id": job_id, "status": "stopped", "message": "resume", "sources": self.sources}
        record_path = self.root / f"state/dashboard_jobs/parallel/{job_id}.json"
        record_path.parent.mkdir(parents=True)
        record_path.write_text("{}", encoding="utf-8")
        with mock.patch.object(dashboard.parallel_module, "BatchPreparation", FakePreparation):
            with mock.patch.object(app, "start", wraps=app.start) as started:
                result = app.resume_queued_parallel(job_id, self.sources[0])
                self.assertEqual(job_id, result["id"])
                self.assertEqual(1, started.call_count)
                selected = started.call_args.args[1]
                kwargs = started.call_args.kwargs
                self.assertEqual(self.sources, selected)
                self.assertEqual(job_id, kwargs["resume"]["jobId"])
                self.assertEqual([self.sources[0]], kwargs["resume"]["retrySources"])
                self.assertEqual(1, len(FakePreparation.instances))


if __name__ == "__main__":
    unittest.main()
