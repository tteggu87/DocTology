"""HTTP/source-entry integration checks independent of module-local mocks."""
from __future__ import annotations

import importlib.util
import json
import os
from unittest.mock import patch
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "runtime/wiki_dashboard.py"
spec = importlib.util.spec_from_file_location("dashboard_entries_under_test", SCRIPT)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class SourceEntryHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "vault"
        for folder in ("raw/inbox", "wiki/_meta", "wiki/concepts"):
            (self.root / folder).mkdir(parents=True)
        (self.root / "AGENTS.md").write_text("# Wiki-only test contract\n", encoding="utf-8")
        (self.root / "wiki/_meta/index.md").write_text("# Index\n", encoding="utf-8")
        (self.root / "wiki/_meta/log.md").write_text("# Log\n", encoding="utf-8")
        self.app = dashboard.Dashboard(self.root)
        self.addCleanup(self.app.stop_all)
        self.server = dashboard.ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
        self.server.app = self.app
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def post(self, route, body, authorized=True):
        headers = {"Content-Type": "application/json", "Origin": self.base}
        if authorized:
            headers["X-Dashboard-Token"] = self.app.token
        request = Request(self.base + "/api/" + route, data=json.dumps(body).encode(), headers=headers)
        with urlopen(request) as response:
            return json.load(response)

    def expect_error(self, code, route, body, authorized=True):
        with self.assertRaises(HTTPError) as result:
            self.post(route, body, authorized)
        self.assertEqual(result.exception.code, code)
        result.exception.close()

    def test_render_and_status_never_enable_watching_or_write_state(self):
        with urlopen(self.base + "/api/state") as response:
            state = json.load(response)
        self.assertFalse(state["automation"]["enabled"])
        self.assertFalse(state["automation"]["autoRun"])
        self.app.automation.tick()
        self.assertFalse((self.root / "state").exists())

    def test_new_routes_require_token_and_expected_root(self):
        body = {"enabled": True, "autoRun": False, "sourcePath": str(self.root / "raw"),
                "includeExisting": False, "expectedRoot": str(self.root)}
        self.expect_error(403, "watch-config", body, authorized=False)
        self.expect_error(400, "watch-config", {**body, "expectedRoot": "/stale"})
        self.assertFalse((self.root / "state").exists())

    def test_authorized_watch_config_is_manual_by_default(self):
        result = self.post("watch-config", {
            "expectedRoot": str(self.root), "enabled": True, "autoRun": False,
            "sourcePath": str(self.root / "raw"), "includeExisting": False,
        })
        self.assertTrue(result["enabled"])
        self.assertFalse(result["autoRun"])
        self.assertEqual(result["sourcePath"], str(self.root / "raw"))

    def test_real_save_module_enqueues_exact_preview_through_main(self):
        preview = self.post("chat-save-preview", {
            "expectedRoot": str(self.root), "title": "User-selected test note",
            "messages": [{"role": "user", "content": "Only an integration test."},
                         {"role": "assistant", "content": "This note remains unverified."}],
        })
        payload = {"expectedRoot": str(self.root), "previewId": preview["previewId"]}
        saved = self.post("chat-save", payload)
        self.assertEqual((self.root / saved["sourcePath"]).read_text(encoding="utf-8"), preview["markdown"])
        self.assertEqual(saved["item"]["origin"], "conversation")
        self.assertEqual(saved["item"]["status"], "pending")
        again = self.post("chat-save", payload)
        self.assertEqual(again["item"]["id"], saved["item"]["id"])
        self.assertEqual(len(self.app.automation.status()["queue"]), 1)
        self.assertFalse(list((self.root / "wiki/concepts").glob("*.md")))

    def test_surviving_runner_blocks_save_upload_and_new_execution(self):
        preview = self.post("chat-save-preview", {
            "expectedRoot": str(self.root), "title": "Orphan exclusion",
            "messages": [{"role": "user", "content": "A test."},
                         {"role": "assistant", "content": "An unverified test."}],
        })
        job_dir = self.root / "state/dashboard_jobs"
        job_dir.mkdir(parents=True)
        (job_dir / "job-surviving.json").write_text(json.dumps({
            "id": "job-surviving", "status": "running", "ownerPid": -1, "runnerPid": os.getpid(),
        }), encoding="utf-8")
        self.assertTrue(self.app.has_live_runner())
        self.expect_error(400, "chat-save", {"expectedRoot": str(self.root), "previewId": preview["previewId"]})
        self.assertFalse((self.root / preview["sourcePath"]).exists())
        self.expect_error(400, "upload", {"name": "blocked.md", "content": "Not written."})
        self.assertFalse((self.root / "raw/inbox/blocked.md").exists())
        source = self.root / "raw/inbox/selected.md"
        source.write_text("# Test\n", encoding="utf-8")
        self.app.pi_command = ["not-invoked"]
        with self.assertRaises(dashboard.WriterBusyError):
            self.app.start("No concurrent model", ["raw/inbox/selected.md"])
        self.app.connect(str(self.root))
        self.assertEqual(self.app.job["status"], "external")

    def test_partial_save_has_structured_recovery_and_retries_same_raw(self):
        preview = self.post("chat-save-preview", {
            "expectedRoot": str(self.root), "title": "Recovery",
            "messages": [{"role": "user", "content": "Keep these bytes."},
                         {"role": "assistant", "content": "Still unverified."}],
        })
        body = {"expectedRoot": str(self.root), "previewId": preview["previewId"]}
        with patch.object(self.app.automation, "enqueue_source", side_effect=RuntimeError("queue unavailable")):
            with self.assertRaises(HTTPError) as failed:
                self.post("chat-save", body)
            self.assertEqual(failed.exception.code, 409)
            details = json.load(failed.exception)
            failed.exception.close()
        self.assertTrue(details["recoverable"])
        self.assertFalse(details["queueHandoff"])
        self.assertEqual(details["sourcePath"], preview["sourcePath"])
        self.assertEqual((self.root / preview["sourcePath"]).read_text(encoding="utf-8"), preview["markdown"])
        recovered = self.post("chat-save", body)
        self.assertTrue(recovered["alreadySaved"])
        self.assertEqual(recovered["item"]["status"], "pending")
        self.assertEqual(len(list((self.root / "raw/inbox/conversations").glob("*.md"))), 1)

    def test_state_paginates_every_actionable_queue_row(self):
        self.app.automation.queue = [
            {"id": f"queue-{number}", "status": "pending", "updatedAt": number,
             "source": f"raw/inbox/{number}.md", "title": str(number)}
            for number in range(105)
        ]
        with urlopen(self.base + "/api/state") as response:
            first = json.load(response)["automation"]
        with urlopen(self.base + "/api/state?queueOffset=100") as response:
            second = json.load(response)["automation"]
        self.assertEqual(len(first["queue"]), 100)
        self.assertEqual(len(second["queue"]), 5)
        self.assertEqual(second["queuePage"], {"offset": 100, "limit": 100, "total": 105})
        self.assertEqual(second["counts"]["pending"], 105)
        self.assertEqual(len({row["id"] for row in first["queue"] + second["queue"]}), 105)
        for invalid in ("-1", "not-a-number", "1000001"):
            with self.assertRaises(HTTPError) as result:
                urlopen(self.base + "/api/state?queueOffset=" + invalid)
            self.assertEqual(result.exception.code, 400)
            result.exception.close()

    def test_project_mode_denies_source_entry_and_keeps_read_only(self):
        project = Path(self.temp.name) / "project"
        (project / "wiki").mkdir(parents=True)
        (project / "AGENTS.md").write_text("# Project\n", encoding="utf-8")
        self.app.connect(str(project))
        for route in ("watch-config", "watch-run", "watch-ignore", "chat-save-preview", "chat-save"):
            self.expect_error(400, route, {"expectedRoot": str(project)})
        self.assertFalse((project / "state").exists())
        self.assertFalse((project / "raw").exists())

    def test_preview_is_read_only_and_root_switch_invalidates_commit(self):
        preview = self.post("chat-save-preview", {
            "expectedRoot": str(self.root), "title": "Integration note",
            "messages": [{"role": "user", "content": "This is a test-only note."},
                         {"role": "assistant", "content": "Recorded as an unverified conversation."}],
        })
        self.assertIn("previewId", preview)
        self.assertIn("markdown", preview)
        self.assertFalse(list((self.root / "raw").rglob("*.md")))
        self.assertFalse((self.root / "state").exists())
        other = Path(self.temp.name) / "other"
        for folder in ("raw", "wiki"):
            (other / folder).mkdir(parents=True)
        (other / "AGENTS.md").write_text("# Wiki-only\n", encoding="utf-8")
        self.app.connect(str(other))
        self.expect_error(400, "chat-save", {"expectedRoot": str(self.root), "previewId": preview["previewId"]})
        self.expect_error(400, "chat-save", {"expectedRoot": str(other), "previewId": preview["previewId"]})
        self.assertFalse(list((other / "raw").rglob("*.md")))


if __name__ == "__main__":
    unittest.main()
