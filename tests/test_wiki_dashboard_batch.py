from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
GATE_SCRIPTS = ROOT / ".agents" / "skills" / "llm-wiki-loop" / "scripts"
RUNTIME = ROOT / "runtime"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


workflow = load("wiki_workflow_for_dashboard_batch", GATE_SCRIPTS / "wiki_workflow.py")
batch = load("wiki_batch_for_dashboard_batch", GATE_SCRIPTS / "wiki_batch.py")
chat_tools = load("wiki_chat_tools_for_dashboard_batch", RUNTIME / "wiki_dashboard_chat_tools.py")
supervisor = load("wiki_dashboard_batch_under_test", RUNTIME / "wiki_dashboard_batch.py")


FAKE_PI = r'''import json,os,re,sys,time
from pathlib import Path
control=Path(sys.argv[1])
for line in sys.stdin:
 event=json.loads(line)
 if event.get('type')!='prompt':
  continue
 match=re.search(r'<batch-worker-data>\n(.*?)\n</batch-worker-data>',event['message'],re.S)
 data=json.loads(match.group(1))
 stem=Path(data['source']).stem
 pid=os.getpid()
 (control/f'{stem}-{pid}.started').write_text(data['draftDir'])
 print(json.dumps({'id':'initial','type':'response','success':True}),flush=True)
 release=control/f'{stem}-{pid}.release'
 while not release.exists(): time.sleep(.01)
 if (control/f'{stem}-{pid}.fail').exists():
  print(json.dumps({'type':'message_end','message':{'role':'assistant','stopReason':'error','content':[]}}),flush=True)
  if (control/f'{stem}-{pid}.recover').exists():
   print(json.dumps({'type':'auto_retry_end','success':True}),flush=True)
 print(json.dumps({'type':'agent_end','willRetry':False}),flush=True)
 time.sleep(.02)
 print(json.dumps({'type':'agent_settled'}),flush=True)
 break
'''


def digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root, _mode):
    root = Path(root)
    result = {}
    for pattern in ("AGENTS.md", "wiki/**/*.md", "raw/**/*.md"):
        for path in root.glob(pattern):
            if path.is_file() and not path.is_symlink():
                result[path.relative_to(root).as_posix()] = path
    return result


def payload(root, mode, relative):
    path = inventory(root, mode)[relative]
    return {"id": relative, "path": relative, "title": path.stem,
            "content": path.read_text(encoding="utf-8")}


def terminate(process):
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=.5)
    except Exception:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def process_alive(pid):
    if not isinstance(pid, int) or pid <= 1:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class FakeSourceDraftTools:
    lock = threading.Lock()
    instances = []

    def __init__(self, root, source, draft_root, helpers, on_change=None):
        self.root = Path(root)
        self.source = source
        self.draft_root = draft_root
        self.helpers = helpers
        self.on_change = on_change
        self.ready = True
        self.result = None
        self.stopped = False
        with self.lock:
            self.instances.append(self)

    @classmethod
    def reset(cls):
        with cls.lock:
            cls.instances = []

    @classmethod
    def latest(cls, source):
        with cls.lock:
            matches = [item for item in cls.instances if item.source == source]
        if not matches:
            raise AssertionError(f"No draft tool for {source}")
        return matches[-1]

    def start(self):
        return {"WIKI_STUDIO_TOOL_URL": "http://127.0.0.1:9/",
                "WIKI_STUDIO_TOOL_TOKEN": "fake-worker-token"}

    def snapshot(self, validate=False):
        return {"ready": self.ready and not self.stopped,
                "exploration": {"calls": 7, "readCount": 3}}

    def stop(self):
        self.stopped = True
        self.ready = False

    def draft_result(self):
        return copy.deepcopy(self.result)

    def submit(self, suffix=""):
        attempt = self.root / self.draft_root
        target = attempt / "files" / "wiki" / "sources" / f"{Path(self.source).stem}{suffix}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# Draft {self.source}\n", encoding="utf-8")
        result = {
            "submitted": True,
            "source": self.source,
            "sourceHash": digest(self.root / self.source),
            "draftDir": self.draft_root + "/files",
            "files": [{"path": target.relative_to(attempt / "files").as_posix(),
                       "sha256": digest(target), "bytes": target.stat().st_size}],
            "summary": f"Prepared {self.source}",
            "plan": f"Project the verified claims from {self.source}.",
            "readEvidence": [
                {"path": self.source, "sha256": digest(self.root / self.source), "complete": True},
                {"path": "AGENTS.md", "sha256": digest(self.root / "AGENTS.md"), "complete": True},
                {"path": "wiki/_meta/index.md", "sha256": digest(self.root / "wiki/_meta/index.md"), "complete": True},
            ],
        }
        (attempt / "proposal.json").write_text(
            json.dumps(result, ensure_ascii=False) + "\n", encoding="utf-8")
        self.result = result
        if self.on_change:
            self.on_change()
        return result


class WikiDashboardBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "vault"
        for folder in ("raw/inbox", "wiki/_meta", "wiki/sources", "state"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        (self.root / "AGENTS.md").write_text("# Wiki contract\n", encoding="utf-8")
        (self.root / "wiki/_meta/index.md").write_text("# Index\n", encoding="utf-8")
        (self.root / "wiki/_meta/log.md").write_text("# Log\n", encoding="utf-8")
        self.sources = []
        for index in range(5):
            relative = f"raw/inbox/source-{index}.md"
            (self.root / relative).write_text(f"# Source {index}\n\nEvidence {index}.\n", encoding="utf-8")
            self.sources.append(relative)
        (self.root / "wiki/_meta/representative_questions.json").write_text(
            json.dumps({"schema_version": 1, "cases": [{
                "id": "direct_lookup", "question": "What evidence is in these sources?",
                "required": True, "expected_posture": "supported",
            }]}) + "\n", encoding="utf-8")
        self.control = Path(self.temp.name) / "control"
        self.control.mkdir()
        self.fake_pi = Path(self.temp.name) / "fake_pi.py"
        self.fake_pi.write_text(FAKE_PI, encoding="utf-8")
        FakeSourceDraftTools.reset()
        self.apps = []

    def tearDown(self):
        for app in self.apps:
            app.close()

    def app(self, sources, parallelism=3, resume=None, job_id="parallel-job"):
        helpers = {
            "WikiChatTools": chat_tools.WikiChatTools,
            "WikiChatToolError": chat_tools.WikiChatToolError,
            "SourceDraftTools": FakeSourceDraftTools,
            "document_inventory": inventory,
            "document_payload": payload,
            "workflow": workflow,
            "batch": batch,
            "terminate": terminate,
            "process_alive": process_alive,
        }
        app = supervisor.BatchPreparation(
            self.root, list(sources), job_id,
            [sys.executable, str(self.fake_pi), str(self.control)], "", helpers,
            parallelism=parallelism, resume=resume,
        )
        self.apps.append(app)
        return app

    def prepare(self, app, sources=None):
        sources = sources or app.sources
        env = app.start()
        self.assertEqual(env["WIKI_STUDIO_BATCH_ROLE"], "coordinator")
        app._coordinator.call("ready", {})
        return app._coordinator.call("batch_prepare", {
            "plans": [{"source": source, "instructions": f"Prepare {source}"}
                      for source in sources]
        })

    def wait(self, condition, message="background preparation did not settle", timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = condition()
            if value:
                return value
            time.sleep(.01)
        self.fail(message)

    def live_rows(self, app):
        return [row for row in app.snapshot()["workers"]
                if row["status"] in {"reading", "drafting"}]

    def running_rows(self, app):
        return [row for row in self.live_rows(app) if row.get("runnerPid")]

    def release(self, app, source, *, submit=True, fail=False, recover=False, suffix=""):
        row = next(row for row in app.snapshot()["workers"] if row["source"] == source)
        pid = row["runnerPid"]
        tool = FakeSourceDraftTools.latest(source)
        if submit:
            tool.submit(suffix=suffix)
        if fail:
            (self.control / f"{Path(source).stem}-{pid}.fail").touch()
        if recover:
            (self.control / f"{Path(source).stem}-{pid}.recover").touch()
        (self.control / f"{Path(source).stem}-{pid}.release").touch()

    def canonical_files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for pattern in ("AGENTS.md", "raw/**/*.md", "wiki/**/*")
                for path in self.root.glob(pattern) if path.is_file()}

    def test_real_overlap_prepares_only_state_and_records_exact_pre_stages(self):
        sources = self.sources[:2]
        before = self.canonical_files()
        app = self.app(sources, parallelism=2)
        started = self.prepare(app)
        self.assertIsInstance(started["batchId"], str)
        self.wait(lambda: len(self.running_rows(app)) == 2)
        pids = {row["runnerPid"] for row in self.running_rows(app)}
        self.assertEqual(len(pids), 2)
        self.assertTrue(all(process_alive(pid) for pid in pids))
        for source in sources:
            self.release(app, source)
        result = self.wait(lambda: app.snapshot() if app.snapshot()["phase"] == "prepared" else None)
        self.assertEqual([row["status"] for row in result["workers"]], ["prepared", "prepared"])
        handoff = app._coordinator.call("batch_status", {})["handoff"]
        self.assertEqual(handoff["batchId"], result["batchId"])
        self.assertEqual({row["source"] for row in handoff["workers"]}, set(sources))
        self.assertTrue(all(row["runId"] and row["draftDir"] and row["instructions"]
                            for row in handoff["workers"]))
        self.assertEqual(before, self.canonical_files())
        _path, manifest = batch.load_manifest(self.root, result["batchId"])
        self.assertIsNone(manifest["apply_event"])
        self.assertTrue(all(not row["staged_files"] for row in manifest["sources"]))
        for row in app.export_record()["workers"]:
            _run_path, run = workflow.load_run(self.root, row["runId"])
            self.assertEqual(tuple(run["stages"]), (
                "inspect_contract_and_index", "inspect_source_and_existing_scope",
                "semantic_plan_frozen",
            ))
            self.assertEqual(run["status"], "active")
            refs = run["stages"]["semantic_plan_frozen"]["references"]
            self.assertEqual(refs[0]["path"], row["result"]["proposalRef"])

    def test_cancel_rejects_retry_until_old_attempt_cleanup_finishes(self):
        sources = self.sources[:2]
        entered = threading.Event()
        release_termination = threading.Event()

        def held_terminate(process):
            entered.set()
            release_termination.wait(timeout=3)
            terminate(process)

        app = self.app(sources, parallelism=2, job_id="attempt-race")
        app.terminate = held_terminate
        self.prepare(app)
        self.wait(lambda: len(self.running_rows(app)) == 2)
        old_row = next(row for row in self.running_rows(app)
                       if row["source"] == sources[0])
        old_pid = old_row["runnerPid"]
        cancel_errors = []

        def cancel_target():
            try:
                app.cancel(sources[0])
            except Exception as exc:
                cancel_errors.append(exc)

        cancel_thread = threading.Thread(target=cancel_target)
        cancel_thread.start()
        self.assertTrue(entered.wait(timeout=2))
        stopped = next(row for row in app.snapshot()["workers"]
                       if row["source"] == sources[0])
        self.assertEqual(stopped["status"], "stopped")
        self.assertTrue(stopped["cleanupPending"])
        self.assertFalse(stopped["retryEligible"])
        self.assertTrue(supervisor.BatchPreparation.live_runners(
            self.root, process_alive))
        with self.assertRaisesRegex(supervisor.BatchPreparationError, "cleanup"):
            app.retry(sources[0])
        self.assertEqual(next(row for row in app.snapshot()["workers"]
                              if row["source"] == sources[0])["attempt"], 1)

        release_termination.set()
        cancel_thread.join(timeout=3)
        self.assertFalse(cancel_thread.is_alive())
        self.assertEqual(cancel_errors, [])
        self.wait(lambda: next(row for row in app.snapshot()["workers"]
                               if row["source"] == sources[0])["retryEligible"])
        self.assertFalse(process_alive(old_pid))
        app.retry(sources[0])
        new_row = self.wait(lambda: next((row for row in self.running_rows(app)
                                         if row["source"] == sources[0]), None))
        self.assertEqual(new_row["attempt"], 2)
        self.assertNotEqual(new_row["runnerPid"], old_pid)
        time.sleep(.05)
        self.assertEqual(app._processes[sources[0]].pid, new_row["runnerPid"])

    def test_partial_planning_resume_reuses_batch_and_runs(self):
        sources = self.sources[:2]
        app = self.app(sources, parallelism=2, job_id="partial-plan")
        app.start()
        app._coordinator.call("ready", {})
        real_link = batch.link_run
        calls = 0

        def fail_second_link(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise batch.BatchError("injected second link failure")
            return real_link(*args, **kwargs)

        with mock.patch.object(batch, "link_run", side_effect=fail_second_link):
            with self.assertRaises(chat_tools.WikiChatToolError):
                app._coordinator.call("batch_prepare", {"plans": [
                    {"source": source, "instructions": f"Prepare {source}"}
                    for source in sources
                ]})
        partial = supervisor.BatchPreparation.read_record(self.root, "partial-plan")
        self.assertFalse(partial["planningComplete"])
        batch_id = partial["batchId"]
        run_ids = [row["runId"] for row in partial["workers"]]
        self.assertEqual(len(set(run_ids)), 2)
        self.assertEqual(len(list((self.root / "state/wiki_batches").glob("*/manifest.json"))), 1)
        self.assertEqual(len(list((self.root / "state/wiki_runs").glob("*.json"))), 2)
        _manifest_path, manifest = batch.load_manifest(self.root, batch_id)
        self.assertEqual(manifest["sources"][0]["run_id"], run_ids[0])
        self.assertIsNone(manifest["sources"][1]["run_id"])

        resumed = self.app(sources, parallelism=2, resume=partial,
                           job_id="partial-plan")
        resumed.start()
        resumed._coordinator.call("ready", {})
        restarted = resumed._coordinator.call("batch_prepare", {"plans": [
            {"source": source, "instructions": f"Prepare {source}"}
            for source in sources
        ]})
        self.assertEqual(restarted["batchId"], batch_id)
        self.assertTrue(resumed.export_record()["planningComplete"])
        self.assertEqual([row["runId"] for row in restarted["workers"]], run_ids)
        self.assertEqual(len(list((self.root / "state/wiki_batches").glob("*/manifest.json"))), 1)
        self.assertEqual(len(list((self.root / "state/wiki_runs").glob("*.json"))), 2)
        _manifest_path, repaired = batch.load_manifest(self.root, batch_id)
        self.assertEqual([row["run_id"] for row in repaired["sources"]], run_ids)
        resumed.cancel()

    def test_hard_crash_orphan_run_fails_closed_without_duplication(self):
        sources = self.sources[:2]
        seed = self.app(sources, job_id="orphan-boundary")
        manifest = batch.plan_batch(self.root, sources)
        orphan = workflow.start_run(self.root, sources[0], coverage_mode="full")
        record = seed.export_record()
        record.update({
            "batchId": manifest["batch_id"],
            "batchBaselineFingerprint": manifest["baseline_fingerprint"],
            "batchCurrentFingerprint": manifest["current_fingerprint"],
            "planningComplete": False,
            "phase": "needs_attention",
        })
        before_runs = {path.name for path in (self.root / "state/wiki_runs").glob("*.json")}
        resumed = self.app(sources, resume=record, job_id="orphan-boundary")
        resumed.start()
        resumed._coordinator.call("ready", {})
        with self.assertRaisesRegex(chat_tools.WikiChatToolError, "manual repair"):
            resumed._coordinator.call("batch_prepare", {"plans": [
                {"source": source, "instructions": f"Prepare {source}"}
                for source in sources
            ]})
        after_runs = {path.name for path in (self.root / "state/wiki_runs").glob("*.json")}
        self.assertEqual(after_runs, before_runs)
        self.assertEqual(after_runs, {f"{orphan['run_id']}.json"})
        self.assertEqual(len(list((self.root / "state/wiki_batches").glob("*/manifest.json"))), 1)

    def test_recovered_auto_retry_can_prepare_but_unrecovered_error_fails(self):
        sources = self.sources[:2]
        app = self.app(sources, parallelism=2, job_id="auto-retry")
        self.prepare(app)
        self.wait(lambda: len(self.running_rows(app)) == 2)
        self.release(app, sources[0], fail=True, recover=True)
        self.release(app, sources[1])
        result = self.wait(lambda: app.snapshot()
                           if app.snapshot()["phase"] == "prepared" else None)
        self.assertTrue(all(row["status"] == "prepared" for row in result["workers"]))

        second = self.app(self.sources[2:4], parallelism=2,
                          job_id="auto-retry-unrecovered")
        self.prepare(second)
        self.wait(lambda: len(self.running_rows(second)) == 2)
        self.release(second, self.sources[2], fail=True)
        self.release(second, self.sources[3])
        failed = self.wait(lambda: second.snapshot()
                           if second.snapshot()["phase"] == "needs_attention"
                           and not self.live_rows(second) else None)
        statuses = {row["source"]: row["status"] for row in failed["workers"]}
        self.assertEqual(statuses[self.sources[2]], "failed")
        self.assertEqual(statuses[self.sources[3]], "prepared")

    def test_parallelism_is_strict_and_one_failure_does_not_cancel_others(self):
        sources = self.sources[:4]
        app = self.app(sources, parallelism=2)
        self.prepare(app)
        self.wait(lambda: len(self.running_rows(app)) == 2)
        first = [row["source"] for row in self.running_rows(app)]
        self.assertEqual(len(first), 2)
        self.assertEqual(sum(row["status"] == "pending" for row in app.snapshot()["workers"]), 2)
        self.release(app, first[0], submit=False, fail=True)
        self.release(app, first[1])
        self.wait(lambda: len(FakeSourceDraftTools.instances) >= 4)
        self.assertLessEqual(len(self.live_rows(app)), 2)
        for source in sources:
            row = next(row for row in app.snapshot()["workers"] if row["source"] == source)
            if row["status"] in {"reading", "drafting"}:
                self.release(app, source)
        result = self.wait(lambda: app.snapshot() if app.snapshot()["phase"] == "needs_attention" and
                           not self.live_rows(app) else None)
        statuses = {row["source"]: row["status"] for row in result["workers"]}
        self.assertEqual(statuses[first[0]], "failed")
        self.assertTrue(all(statuses[source] == "prepared" for source in sources if source != first[0]))

    def test_separate_cancel_stops_only_target_and_other_worker_survives(self):
        sources = self.sources[:2]
        app = self.app(sources, parallelism=2)
        self.prepare(app)
        self.wait(lambda: len(self.running_rows(app)) == 2)
        app.cancel(sources[0])
        self.release(app, sources[1])
        result = self.wait(lambda: app.snapshot() if not self.live_rows(app) else None)
        statuses = {row["source"]: row["status"] for row in result["workers"]}
        self.assertEqual(statuses, {sources[0]: "stopped", sources[1]: "prepared"})
        self.assertEqual(result["phase"], "needs_attention")

    def test_stale_source_fails_closed_without_ready_claim(self):
        sources = self.sources[:2]
        app = self.app(sources, parallelism=2)
        self.prepare(app)
        self.wait(lambda: len(self.running_rows(app)) == 2)
        (self.root / sources[0]).write_text("# Changed source\n", encoding="utf-8")
        for source in sources:
            self.release(app, source)
        result = self.wait(lambda: app.snapshot()
                           if not self.live_rows(app)
                           and not any(row["cleanupPending"]
                                       for row in app.snapshot()["workers"])
                           else None)
        self.assertEqual(result["phase"], "needs_attention")
        self.assertNotIn("prepared", {row["status"] for row in result["workers"]})
        self.assertTrue(any("stale" in row.get("error", "") or "changed" in row.get("error", "")
                            for row in result["workers"]))

    def test_explicit_retry_uses_new_attempt_and_preserves_old_artifact(self):
        sources = self.sources[:2]
        app = self.app(sources, parallelism=2)
        self.prepare(app)
        self.wait(lambda: len(self.running_rows(app)) == 2)
        self.release(app, sources[0])
        self.release(app, sources[1], fail=True, suffix="-old")
        self.wait(lambda: app.snapshot()["phase"] == "needs_attention" and not self.live_rows(app)
                  and any(row["source"] == sources[1] and row["retryEligible"]
                          and not row["cleanupPending"] for row in app.snapshot()["workers"]))
        failed = next(row for row in app.snapshot()["workers"] if row["source"] == sources[1])
        old_proposal = self.root / failed["draftDir"] / ".." / "proposal.json"
        old_proposal = old_proposal.resolve()
        self.assertTrue(old_proposal.is_file())
        prepared_pointer = next(row["draftDir"] for row in app.snapshot()["workers"]
                                if row["source"] == sources[0])
        app.retry(sources[1])
        self.wait(lambda: next(row for row in app.snapshot()["workers"]
                               if row["source"] == sources[1])["attempt"] == 2 and
                  len(self.running_rows(app)) == 1)
        self.release(app, sources[1], suffix="-new")
        result = self.wait(lambda: app.snapshot() if app.snapshot()["phase"] == "prepared" else None)
        self.assertTrue(old_proposal.is_file())
        self.assertEqual(next(row["draftDir"] for row in result["workers"]
                              if row["source"] == sources[0]), prepared_pointer)
        retried = next(row for row in result["workers"] if row["source"] == sources[1])
        self.assertEqual(retried["attempt"], 2)
        self.assertIn("attempt-2/files", retried["draftDir"])

    def test_resume_marks_interrupted_and_never_auto_replays(self):
        sources = self.sources[:2]
        first = self.app(sources, parallelism=2, job_id="resume-job")
        self.prepare(first)
        self.wait(lambda: len(self.running_rows(first)) == 2)
        active_record = first.export_record()
        first.cancel()
        self.wait(lambda: not self.live_rows(first))
        instance_count = len(FakeSourceDraftTools.instances)
        resumed = self.app(sources, parallelism=2, resume=active_record, job_id="resume-job")
        resumed.start()
        time.sleep(.1)
        self.assertEqual(len(FakeSourceDraftTools.instances), instance_count)
        self.assertEqual(resumed.snapshot()["phase"], "needs_attention")
        self.assertEqual({row["status"] for row in resumed.snapshot()["workers"]}, {"interrupted"})
        with self.assertRaises(supervisor.BatchPreparationError):
            resumed.retry(sources[0])
        self.prepare(resumed)
        resumed.cancel(sources[0])
        resumed.retry(sources[0])
        self.wait(lambda: any(item.source == sources[0] and item.draft_root.endswith("attempt-2")
                              for item in FakeSourceDraftTools.instances))
        record = supervisor.BatchPreparation.read_record(self.root, "resume-job")
        self.assertEqual(record["jobId"], "resume-job")
        self.assertTrue(supervisor.BatchPreparation.live_runners(self.root, process_alive))

    def test_server_only_resume_retry_replays_exactly_one_nonprepared_source(self):
        sources = self.sources[:2]
        first = self.app(sources, parallelism=2, job_id="server-retry-job")
        self.prepare(first)
        self.wait(lambda: len(self.running_rows(first)) == 2)
        self.release(first, sources[0])
        self.release(first, sources[1], submit=False, fail=True)
        self.wait(lambda: first.snapshot()["phase"] == "needs_attention" and
                  not self.live_rows(first))
        record = first.export_record()
        prepared_before = next(row for row in record["workers"]
                               if row["source"] == sources[0])["draftDir"]
        record["retrySources"] = [sources[1]]
        first.close()
        count_before = len(FakeSourceDraftTools.instances)

        resumed = self.app(sources, parallelism=2, resume=record,
                           job_id="server-retry-job")
        resumed.start()
        time.sleep(.05)
        self.assertEqual(len(FakeSourceDraftTools.instances), count_before)
        self.prepare(resumed)
        self.wait(lambda: len(self.running_rows(resumed)) == 1)
        active = self.running_rows(resumed)[0]
        self.assertEqual(active["source"], sources[1])
        self.assertEqual(active["attempt"], 2)
        untouched = next(row for row in resumed.snapshot()["workers"]
                         if row["source"] == sources[0])
        self.assertEqual(untouched["status"], "prepared")
        self.assertEqual(untouched["draftDir"], prepared_before)
        self.release(resumed, sources[1], suffix="-resumed")
        result = self.wait(lambda: resumed.snapshot()
                           if resumed.snapshot()["phase"] == "prepared" else None)
        self.assertTrue(all(row["status"] == "prepared" for row in result["workers"]))
        self.assertNotIn("retrySources", resumed.export_record())

    def test_live_runners_ignores_idle_owner_and_terminal_worker_pids(self):
        folder = self.root / "state/dashboard_jobs/parallel"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "runner-guard.json"
        record = {
            "jobId": "runner-guard", "ownerPid": os.getpid(), "phase": "prepared",
            "workers": [
                {"source": self.sources[0], "status": "prepared", "runnerPid": os.getpid()},
                {"source": self.sources[1], "status": "stopped", "runnerPid": os.getpid()},
            ],
        }
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(supervisor.BatchPreparation.live_runners(
            self.root, process_alive), [])

        record["phase"] = "preparing"
        record["workers"][0]["status"] = "reading"
        path.write_text(json.dumps(record), encoding="utf-8")
        active = supervisor.BatchPreparation.live_runners(self.root, process_alive)
        self.assertEqual(active[0]["jobId"], "runner-guard")
        self.assertIn(os.getpid(), active[0]["pids"])

        record["workers"][0]["runnerPid"] = 999_999_999
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(supervisor.BatchPreparation.live_runners(
            self.root, process_alive), [])

        record["phase"] = "needs_attention"
        record["workers"][0]["status"] = "interrupted"
        record["workers"][0]["runnerPid"] = os.getpid()
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assertTrue(supervisor.BatchPreparation.live_runners(
            self.root, process_alive))

        record["phase"] = "stopped"
        record["workers"][0]["status"] = "stopped"
        record["workers"][0]["cleanupPending"] = True
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assertTrue(supervisor.BatchPreparation.live_runners(
            self.root, process_alive))
        record["workers"][0]["cleanupPending"] = False
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(supervisor.BatchPreparation.live_runners(
            self.root, process_alive), [])

    def test_control_polls_do_not_consume_document_read_budgets(self):
        app = self.app(self.sources[:2], job_id="control-budget")
        app.start()
        self.assertFalse(app.coordinator_ready())
        app._coordinator.call("ready", {})
        self.assertTrue(app.coordinator_ready())
        before = app._coordinator.snapshot()["exploration"]
        for _ in range(125):
            status = app._coordinator.call("batch_status", {})
            self.assertEqual(status["phase"], "planning")
        after = app._coordinator.snapshot()["exploration"]
        self.assertEqual(after["calls"], before["calls"])
        self.assertEqual(after["readCount"], before["readCount"])
        self.assertEqual(
            after["limits"]["remainingReturnedCharacters"],
            before["limits"]["remainingReturnedCharacters"],
        )
        app._coordinator.call("wiki_list", {"scope": "wiki", "limit": 1})
        self.assertEqual(app._coordinator.snapshot()["exploration"]["calls"],
                         before["calls"] + 1)

    def test_close_preserves_prepared_phase_and_durable_fact(self):
        sources = self.sources[:2]
        app = self.app(sources, parallelism=2, job_id="prepared-close")
        self.prepare(app)
        self.wait(lambda: len(self.running_rows(app)) == 2)
        for source in sources:
            self.release(app, source)
        self.wait(lambda: app.snapshot()["phase"] == "prepared")
        app.close()
        self.assertEqual(app.snapshot()["phase"], "prepared")
        record = supervisor.BatchPreparation.read_record(self.root, "prepared-close")
        self.assertEqual(record["phase"], "prepared")
        self.assertTrue(all(row["status"] == "prepared" for row in record["workers"]))

    def test_stubborn_owned_process_stays_tracked_until_confirmed_exit(self):
        class StubbornProcess:
            def __init__(self):
                self.pid = os.getpid()
                self.stdin = None
                self.stdout = None
                self.stderr = None
                self.exited = False

            def poll(self):
                return 0 if self.exited else None

            def wait(self, timeout=None):
                if not self.exited:
                    raise TimeoutError("still running")
                return 0

        app = self.app(self.sources[:2], job_id="stubborn-cleanup")
        process = StubbornProcess()
        app.terminate = lambda _process: None
        source = self.sources[0]
        with app._lock:
            row = app._workers[source]
            row.update({
                "status": "stopped", "attempt": 1, "runnerPid": process.pid,
                "cleanupPending": True, "retryEligible": False,
            })
            app._workers[self.sources[1]].update({
                "status": "stopped", "cleanupPending": False,
                "retryEligible": True,
            })
            app._processes[source] = process
            app._phase = "stopped"
        app._publish_change()

        with self.assertRaisesRegex(supervisor.BatchPreparationError, "still alive"):
            app.close()
        blocked = next(row for row in app.snapshot()["workers"]
                       if row["source"] == source)
        self.assertTrue(blocked["cleanupPending"])
        self.assertFalse(blocked["retryEligible"])
        self.assertIs(app._processes[source], process)
        self.assertTrue(supervisor.BatchPreparation.live_runners(
            self.root, process_alive))

        process.exited = True
        app.close()
        cleared = next(row for row in app.snapshot()["workers"]
                       if row["source"] == source)
        self.assertFalse(cleared["cleanupPending"])
        self.assertTrue(cleared["retryEligible"])
        self.assertNotIn(source, app._processes)
        self.assertEqual(supervisor.BatchPreparation.live_runners(
            self.root, process_alive), [])

    def test_close_cleans_up_even_when_record_persistence_fails(self):
        sources = self.sources[:2]
        app = self.app(sources, parallelism=2, job_id="cleanup-failure")
        self.prepare(app)
        self.wait(lambda: len(self.running_rows(app)) == 2)
        pids = [row["runnerPid"] for row in self.running_rows(app)]
        coordinator = app._coordinator
        with mock.patch.object(app, "_publish_change", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(supervisor.BatchPreparationError, "persist"):
                app.close()
        self.assertTrue(all(not process_alive(pid) for pid in pids))
        self.assertTrue(all(tool.stopped for tool in FakeSourceDraftTools.instances))
        with self.assertRaises(chat_tools.WikiChatToolError):
            coordinator.call("batch_status", {})

    def test_worker_prompt_contains_full_coverage_contract_and_role_boundary(self):
        app = self.app(self.sources[:2], job_id="prompt-contract")
        prompt = app._worker_prompt(
            self.sources[0], "state/wiki_batches/example/workers/worker-1/attempt-1",
            "Preserve the source evidence.",
        )
        for required in (
            "coverage_mode: full", "source_units_total", "source_units_projected",
            "source_units_omitted", "source_units_deferred", "Projected Units",
            "Omitted Units", "Deferred Units", "current batch seal remains the sole certification",
            "No shell is available", digest(self.root / self.sources[0]),
        ):
            self.assertIn(required, prompt)

    def test_errors_are_value_errors_and_public_workers_include_run_id(self):
        self.assertTrue(issubclass(supervisor.BatchPreparationError, ValueError))
        app = self.app(self.sources[:2], parallelism=1, job_id="public-run-id")
        started = self.prepare(app)
        self.assertTrue(all(row.get("runId") for row in started["workers"]))
        app.cancel()

    def test_resume_rejects_stale_hash_and_apply_event_forbids_repreparation(self):
        sources = self.sources[:2]
        app = self.app(sources, parallelism=2, job_id="guard-job")
        self.prepare(app)
        self.wait(lambda: len(self.running_rows(app)) == 2)
        record = app.export_record()
        app.cancel()
        (self.root / sources[0]).write_text("# stale\n", encoding="utf-8")
        with self.assertRaisesRegex(supervisor.BatchPreparationError, "resume inputs"):
            self.app(sources, parallelism=2, resume=record, job_id="guard-job")
        (self.root / sources[0]).write_text("# Source 0\n\nEvidence 0.\n", encoding="utf-8")

        # A recorded apply is coordinator-only recovery territory. No worker may restart.
        manifest_path, manifest = batch.load_manifest(self.root, record["batchId"])
        manifest["apply_event"] = {"result_fingerprint": manifest["baseline_fingerprint"]}
        manifest["status"] = "applied"
        batch.write_json(manifest_path, manifest)
        resumed = self.app(sources, parallelism=2, resume=record, job_id="guard-job")
        resumed.start()
        with self.assertRaises(supervisor.BatchPreparationError):
            resumed._coordinator_prepare({"plans": [
                {"source": source, "instructions": f"Prepare {source}"} for source in sources
            ]})
        self.assertEqual(len(self.live_rows(resumed)), 0)
        self.assertIn("apply event", resumed.snapshot().get("error", ""))

    def test_resume_rejects_tampered_prepared_draft_hash(self):
        sources = self.sources[:2]
        app = self.app(sources, parallelism=2, job_id="draft-hash-job")
        self.prepare(app)
        self.wait(lambda: len(self.running_rows(app)) == 2)
        for source in sources:
            self.release(app, source)
        self.wait(lambda: app.snapshot()["phase"] == "prepared")
        record = app.export_record()
        first_file = record["workers"][0]["result"]["files"][0]["path"]
        draft_dir = self.root / record["workers"][0]["draftDir"]
        (draft_dir / first_file).write_text("# tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(supervisor.BatchPreparationError, "hash is stale"):
            self.app(sources, parallelism=2, resume=record, job_id="draft-hash-job")

    def test_source_and_question_validation_is_fail_closed(self):
        with self.assertRaises(supervisor.BatchPreparationError):
            self.app([self.sources[0], self.sources[0]])
        questions = self.root / "wiki/_meta/representative_questions.json"
        questions.unlink()
        app = self.app(self.sources[:2])
        app.start()
        app._coordinator.call("ready", {})
        with self.assertRaises(chat_tools.WikiChatToolError):
            app._coordinator.call("batch_prepare", {"plans": [
                {"source": source, "instructions": "Plan"} for source in self.sources[:2]
            ]})
        self.assertFalse(questions.exists())
        invalid = {"schema_version": 1, "cases": [{
            "id": "placeholder", "question": "Replace with a question", "required": True,
            "expected_posture": "supported",
        }]}
        app2 = self.app(self.sources[2:4], job_id="questions-job")
        app2.start()
        app2._coordinator.call("ready", {})
        with self.assertRaises(chat_tools.WikiChatToolError):
            app2._coordinator.call("batch_prepare", {"plans": [
                {"source": source, "instructions": "Plan"} for source in self.sources[2:4]
            ], "questions": invalid})
        self.assertFalse(questions.exists())

        valid = {"schema_version": 1, "cases": [{
            "id": "direct", "question": "What does this fixed source set establish?",
            "required": True, "expected_posture": "supported",
        }]}
        app3 = self.app(self.sources[3:5], job_id="valid-questions-job")
        app3.start()
        app3._coordinator.call("ready", {})
        started = app3._coordinator.call("batch_prepare", {"plans": [
            {"source": source, "instructions": "Plan"} for source in self.sources[3:5]
        ], "questions": valid})
        self.assertIsInstance(started["batchId"], str)
        self.assertEqual(json.loads(questions.read_text(encoding="utf-8")), valid)
        app3.cancel()


if __name__ == "__main__":
    unittest.main()
