from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "runtime/wiki_dashboard.py"
spec = importlib.util.spec_from_file_location("dashboard_under_test", SCRIPT)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)

FAKE_PI = '''import json,sys,time
def out(value):
 print(json.dumps(value),flush=True)
for line in sys.stdin:
 event=json.loads(line)
 if event['type']=='prompt':
  message=event['message']
  out({'id':event['id'],'type':'response','success':True})
  out({'type':'tool_execution_start','toolName':'read','args':{'path':'raw/inbox/source.md'}})
  out({'type':'tool_execution_end','toolName':'read'})
  if message.startswith('retry'):
   out({'type':'message_end','message':{'role':'assistant','stopReason':'error','content':[]}})
   out({'type':'agent_end','willRetry':True})
   out({'type':'auto_retry_start','attempt':1})
   time.sleep(.08)
   out({'type':'auto_retry_end','success':True})
  if not message.startswith('wait'):
   out({'type':'message_end','message':{'role':'assistant','stopReason':'stop','content':[{'type':'text','text':'요청 처리 완료'},{'type':'thinking','thinking':'PRIVATE_THOUGHT'}]}})
   out({'type':'agent_end','willRetry':False})
   time.sleep(.04)
   out({'type':'agent_settled'})
 elif event['type']=='steer':
  out({'type':'response','command':'steer','success':True})
 elif event['type']=='abort':
  out({'type':'agent_end'})
  out({'type':'agent_settled'})
 else:
  out({'type':'response','command':event['type'],'success':False})
'''


class WikiDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "vault"
        for name in ("raw/inbox", "wiki/concepts", "wiki/sources", "wiki/_meta/ingest_reports"):
            (self.root / name).mkdir(parents=True)
        (self.root / "AGENTS.md").write_text("# Wiki-only contract\n", encoding="utf-8")
        (self.root / "wiki/_meta/index.md").write_text("# Index\n", encoding="utf-8")
        (self.root / "wiki/_meta/log.md").write_text("# Log\n", encoding="utf-8")
        self.source = "raw/inbox/source.md"
        (self.root / self.source).write_text("# Source\n\nEvidence.\n", encoding="utf-8")

    def row(self):
        return dashboard.snapshot(self.root)["sources"][0]

    def receipt(self, projected=1, omitted=0, deferred=0):
        relative = "wiki/_meta/ingest_reports/ingest-source.md"
        total = projected + omitted + deferred
        (self.root / relative).write_text(
            f"---\nstatus: applied\ncoverage_mode: full\nraw_path: {self.source}\n"
            f"source_sha256: {dashboard.workflow.file_digest(self.root / self.source)}\n"
            f"source_units_total: {total}\nsource_units_projected: {projected}\n"
            f"source_units_omitted: {omitted}\nsource_units_deferred: {deferred}\n---\n"
            "# Coverage\n\n- unit -> `wiki/concepts/knowledge.md#facts`\n", encoding="utf-8")
        return relative

    def complete(self):
        w = dashboard.workflow
        run = w.start_run(self.root, self.source)
        for stage in w.PROCEDURE_ORDER:
            refs = [self.source]
            if stage in w.MUTATION_STAGES:
                page = self.root / "wiki/concepts/knowledge.md"
                with page.open("a", encoding="utf-8") as f:
                    f.write(f"\n# {stage}\n\nEvidence from source.\n")
                refs = ["wiki/concepts/knowledge.md"]
            if stage == "refresh_index_and_log":
                refs.append(self.receipt())
            if stage == "final_review_completed":
                refs.append("wiki/_meta/ingest_reports/ingest-source.md")
            w.record_stage(self.root, run["run_id"], stage, refs=refs, na_reason=None,
                           result="passed" if stage == "validate_structure" else None,
                           posture="ready" if stage == "final_review_completed" else None,
                           reviewed_fingerprint=w.state_fingerprint(self.root, self.source) if stage == "final_review_completed" else None)
        w.finish_run(self.root, run["run_id"])
        return run

    def app(self):
        fake = Path(self.temp.name) / "fake_pi.py"
        fake.write_text(FAKE_PI, encoding="utf-8")
        app = dashboard.Dashboard(self.root, [sys.executable, str(fake)])
        self.addCleanup(app.stop_process)
        self.addCleanup(lambda: self.wait_for(lambda: app.claim is None) if app.process else None)
        return app

    def wait_for(self, condition):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(.02)
        self.fail("Background RPC operation did not settle")

    def test_snapshot_is_read_only_and_pending_has_no_invented_coverage(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        row = self.row()
        self.assertEqual(row["stage"], "queued")
        self.assertIsNone(row["coverage"])
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_project_mode_includes_meta_docs_and_root_links_without_mutation(self):
        shutil.rmtree(self.root / "raw")
        (self.root / "docs").mkdir()
        (self.root / "docs/README.md").write_text("# Docs\n[Wiki](../wiki/_meta/index.md)", encoding="utf-8")
        (self.root / "README.md").write_text("# Project\n[Docs](docs/README.md)", encoding="utf-8")
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        app = dashboard.Dashboard(self.root)
        data = app.state()
        self.assertEqual(data["mode"], "project")
        self.assertTrue(data["readOnly"])
        self.assertFalse(data["demo"])
        self.assertEqual(data["sources"], [])
        self.assertIn("wiki/_meta/index.md", {n["id"] for n in data["graph"]["nodes"]})
        self.assertIn({"source":"README.md","target":"docs/README.md"}, data["graph"]["edges"])
        self.assertIn({"source":"docs/README.md","target":"wiki/_meta/index.md"}, data["graph"]["edges"])
        for action, body in (("start", {"message":"ingest","sources":[self.source]}), ("upload", {"name":"new.md","content":"hello"})):
            with self.assertRaises(ValueError):
                app.action(action, body)
        with self.assertRaises(ValueError):
            app.start("ingest", [self.source])
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.root / "raw").exists())

    def test_project_document_api_only_exposes_document_inventory(self):
        shutil.rmtree(self.root / "raw")
        (self.root / "docs").mkdir()
        (self.root / "docs/README.md").write_text("# Project documentation", encoding="utf-8")
        (self.root / "secret.md").write_text("not project documentation", encoding="utf-8")
        app = dashboard.Dashboard(self.root)
        server = dashboard.ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
        server.app = app
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(base + "/api/document?path=docs/README.md") as response:
            self.assertEqual(json.load(response)["content"], "# Project documentation")
        for relative in ("secret.md", "docs/../secret.md", "state/private.md"):
            with self.assertRaises(HTTPError) as error:
                urlopen(base + "/api/document?path=" + relative)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()

    def test_current_gate_completion_becomes_blocked_after_canonical_mutation(self):
        self.complete()
        self.assertEqual(self.row()["stage"], "done")
        (self.root / "wiki/concepts/knowledge.md").write_text("# Changed\n", encoding="utf-8")
        self.assertEqual(self.row()["stage"], "blocked")

    def test_coverage_rejects_stale_source_and_duplicate_receipts(self):
        report = self.receipt(projected=3, omitted=1, deferred=2)
        row = self.row()
        self.assertEqual(row["coverage"]["total"], 6)
        self.assertTrue(row["coverage"]["valid"])
        (self.root / self.source).write_text("# Source changed\n", encoding="utf-8")
        self.assertFalse(self.row()["coverage"]["valid"])
        (self.root / "wiki/_meta/ingest_reports/ingest-duplicate.md").write_text((self.root / report).read_text(), encoding="utf-8")
        self.assertIsNone(self.row()["coverage"])

    def test_current_run_is_not_blocked_by_unrelated_historical_batch(self):
        old = dashboard.batch.plan_batch(self.root, [self.source])
        self.complete()
        self.assertEqual(dashboard.batch.batch_status(self.root, old["batch_id"])["status"], "stale")
        self.assertEqual(self.row()["stage"], "done")

    def test_linked_batch_must_be_certified_before_done(self):
        current = dashboard.batch.plan_batch(self.root, [self.source])
        run = self.complete()
        dashboard.batch.link_run(self.root, current["batch_id"], self.source, run["run_id"])
        self.assertEqual(self.row()["stage"], "review")

    def test_malformed_run_is_reported_without_hiding_sources(self):
        path = self.root / "state/wiki_runs/bad.json"
        path.parent.mkdir(parents=True)
        path.write_text("{broken", encoding="utf-8")
        data = dashboard.snapshot(self.root)
        self.assertEqual(len(data["sources"]), 1)
        self.assertEqual(len(data["warnings"]), 1)

    def test_graph_uses_real_links_and_ignores_ambiguous_names_and_fenced_code(self):
        for relative, content in {
            "wiki/concepts/a.md": "# A\n[[b]] [[missing]]\n[Source](../sources/source.md)\n```md\n[[fake]]\n```",
            "wiki/concepts/b.md": "# B\n",
            "wiki/sources/b.md": "# Other B\n",
            "wiki/sources/source.md": "# Source\n[[concepts/a]]",
            "wiki/concepts/fake.md": "# Not linked\n",
        }.items():
            (self.root / relative).write_text(content, encoding="utf-8")
        graph = dashboard.snapshot(self.root)["graph"]
        self.assertEqual({(e["source"], e["target"]) for e in graph["edges"]}, {
            ("wiki/concepts/a.md", "wiki/sources/source.md"),
            ("wiki/sources/source.md", "wiki/concepts/a.md"),
        })

    def test_path_traversal_symlink_and_source_overwrite_are_rejected(self):
        app = self.app()
        with self.assertRaises(ValueError):
            dashboard.inside(self.root, "raw/../../private.md")
        (self.root / "raw/inbox/outside.md").symlink_to(Path(self.temp.name) / "secret.md")
        with self.assertRaises(ValueError):
            dashboard.inside(self.root, "raw/inbox/outside.md")
        with self.assertRaises(FileExistsError):
            app.action("upload", {"name": "source.md", "content": "overwrite"})
        self.assertIn("Evidence", (self.root / self.source).read_text())

    def test_upload_is_persistent_and_immediately_visible(self):
        app = self.app()
        app.state()
        app.action("upload", {"name": "new.md", "content": "# New evidence\n"})
        self.assertEqual(len(app.state()["sources"]), 2)
        self.assertEqual((self.root / "raw/inbox/new.md").read_text(), "# New evidence\n")

    def test_rpc_finish_does_not_claim_wiki_completion_or_expose_thinking(self):
        app = self.app()
        app.start("finish", [self.source])
        self.wait_for(lambda: app.claim is None)
        self.assertEqual(app.job["status"], "finished")
        self.assertEqual(app.state()["sources"][0]["stage"], "queued")
        self.assertNotIn("PRIVATE_THOUGHT", json.dumps(app.job))
        restored = dashboard.Dashboard(self.root)
        self.assertEqual(restored.job["id"], app.job["id"])

    def test_rpc_waits_through_agent_end_and_retry_until_settled(self):
        app = self.app()
        app.start("retry", [self.source])
        self.wait_for(lambda: app.claim is None)
        self.assertEqual(app.job["status"], "finished")
        self.assertTrue(any(e["label"] == "모델 응답 재시도" for e in app.job["events"]))
        self.assertTrue(any(e["detail"] == "요청 처리 완료" for e in app.job["events"]))

    def test_steer_stop_and_duplicate_writer_lock(self):
        app = self.app()
        app.start("wait", [self.source])
        other = dashboard.Dashboard(self.root, app.pi_command)
        with self.assertRaises(ValueError):
            other.start("finish", [self.source])
        with self.assertRaises(ValueError):
            app.connect(str(self.root))
        app.action("steer", {"message": "Preserve all source facts"})
        app.action("stop", {})
        self.wait_for(lambda: app.claim is None)
        self.assertEqual(app.job["status"], "stopped")
        self.assertTrue(any(e["label"] == "추가 지시" for e in app.job["events"]))

    def test_http_origin_token_host_and_document_boundary(self):
        app = self.app()
        server = dashboard.ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
        server.app = app
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(base + "/") as r:
            self.assertIn(b"DocTology", r.read())
            self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])
        with urlopen(base + "/api/state") as r:
            self.assertFalse(json.load(r)["demo"])
        for headers in ({}, {"Origin": "https://hostile.example", "X-Dashboard-Token": app.token}, {"Origin": base}):
            request = Request(base + "/api/stop", data=b"{}", headers=headers, method="POST")
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
        request = Request(base + "/api/upload", data=json.dumps({"name":"http.md","content":"# Uploaded"}).encode(),
                          headers={"Origin":base,"X-Dashboard-Token":app.token,"Content-Type":"application/json"}, method="POST")
        with urlopen(request) as r:
            self.assertEqual(r.status, 200)
        with self.assertRaises(HTTPError) as error:
            urlopen(base + "/api/document?path=raw/../../secret.md")
        self.assertEqual(error.exception.code, 400)
        error.exception.close()
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(base + "/api/state", headers={"Host":"hostile.example"}))
        self.assertEqual(error.exception.code, 403)
        error.exception.close()


if __name__ == "__main__":
    unittest.main()
