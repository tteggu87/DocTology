"""Regressions for delayed tool sockets, corpus read amplification and live SQLite."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest import mock
from urllib import request, error

from progress_fixture import make_vault

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("read_performance_dashboard", ROOT / "runtime/wiki_dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class ReadPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = make_vault(Path(self.temp.name) / "vault", sources=8, reports=8, wiki_pages=20, runs=0)
        self.catalog = dashboard.documents_module.DocumentCatalog(dashboard.workflow, dashboard.batch)

    def bridge(self, payload=None, index=None):
        bridge = dashboard.chat_tools_module.WikiChatTools(self.root, "wiki", {
            "document_inventory": self.catalog.document_inventory,
            "document_inventory_subset": self.catalog.document_inventory_subset,
            "document_payload": payload or self.catalog.document_payload,
            "search_index": index,
        })
        self.addCleanup(bridge.stop)
        return bridge

    def wait_for(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate():
            if time.monotonic() >= deadline:
                self.fail("request did not settle")
            time.sleep(.01)

    def test_read_avoids_unrelated_raw_hashes_and_reuses_receipt_parsing(self):
        bridge = self.bridge()
        with mock.patch.object(dashboard.workflow, "file_digest", wraps=dashboard.workflow.file_digest) as hashes:
            read = bridge.call("wiki_read", {"path": "wiki/concepts/topic-0001.md"})
            self.assertEqual(hashes.call_count, 0)
        self.assertEqual(read["number"], 1)
        with mock.patch.object(dashboard.workflow, "frontmatter_from_text", wraps=dashboard.workflow.frontmatter_from_text) as parse:
            bridge.call("wiki_read", {"path": "wiki/concepts/topic-0002.md"})
            self.assertEqual(parse.call_count, 0)
        # An edited receipt and changed raw hash must not survive the cache.
        report = self.root / "wiki/_meta/ingest_reports/ingest-0000.md"
        report.write_text(report.read_text().replace("topic-0000", "topic-0001"))
        read = bridge.call("wiki_read", {"path": "wiki/concepts/topic-0001.md"})
        self.assertEqual(len(read["document"]["rawSources"]), 1)
        (self.root / "raw/inbox/source-0000.md").write_text("# changed")
        read = bridge.call("wiki_read", {"path": "wiki/concepts/topic-0001.md"})
        self.assertEqual(read["document"]["rawSources"], [])

    def test_timeout_during_candidate_construction_preserves_previous_evidence(self):
        bridge = self.bridge()
        path = "wiki/concepts/topic-0001.md"
        bridge.call("wiki_read", {"path": path, "limit": 5})
        before = bridge.snapshot()
        budget = bridge._returned_characters
        merge = bridge._merge_ranges
        def slow(ranges):
            time.sleep(.08)
            return merge(ranges)
        bridge.TOOL_TIMEOUT_SECONDS = .03
        with mock.patch.object(bridge, "_merge_ranges", side_effect=slow):
            with self.assertRaises(dashboard.chat_tools_module.WikiChatToolError) as failure:
                bridge.call("wiki_read", {"path": path, "offset": 5})
        self.assertEqual(failure.exception.status, 504)
        self.assertEqual(bridge.snapshot()["candidates"], before["candidates"])
        self.assertEqual(bridge._returned_characters, budget)

    def test_late_response_timeout_does_not_count_a_successful_read(self):
        bridge = self.bridge()
        original = bridge._result
        def slow(*args, **kwargs):
            time.sleep(.07)
            return original(*args, **kwargs)
        bridge.TOOL_TIMEOUT_SECONDS = .03
        with mock.patch.object(bridge, "_result", side_effect=slow):
            with self.assertRaises(dashboard.chat_tools_module.WikiChatToolError):
                bridge.call("wiki_read", {"path":"wiki/concepts/topic-0001.md"})
        result = bridge.snapshot()
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["exploration"]["retrievalUsage"]["readCalls"], 0)
        self.assertEqual(result["exploration"]["events"][-1]["status"], "error")

    def test_subset_admission_matches_inventory_and_rechecks_escapes(self):
        inventory = self.catalog.document_inventory(self.root, "wiki")
        self.assertEqual(self.catalog.document_inventory_subset(self.root, "wiki", list(inventory)), inventory)
        path = self.root / "wiki/concepts/topic-0001.md"
        path.unlink()
        outside = Path(self.temp.name) / "outside.md"
        outside.write_text("not approved")
        path.symlink_to(outside)
        self.assertEqual(self.catalog.document_inventory_subset(self.root, "wiki", ["wiki/concepts/topic-0001.md", "../outside.md"]), {})

    def test_sqlite_search_updates_changed_added_deleted_files_and_counts_fts(self):
        index = dashboard.index_module.StudioIndex(self.root)
        index.ensure(self.catalog.document_inventory(self.root, "wiki"))
        bridge = self.bridge(index=index)
        path = self.root / "wiki/concepts/new.md"
        path.write_text("# 신규 한국어\n특별검색문자열 알파")
        result = bridge.call("wiki_search", {"query": "특별검색문자열"})
        self.assertEqual(result["method"], "fts")
        self.assertEqual([row["id"] for row in result["results"]], ["wiki/concepts/new.md"])
        read = bridge.call("wiki_read", {"path": "wiki/concepts/new.md"})
        self.assertTrue(read["citationCandidate"])
        path.write_text("# 새 내용\n베타")
        self.assertEqual(bridge.call("wiki_search", {"query": "특별검색문자열"})["count"], 0)
        self.assertEqual(bridge.call("wiki_search", {"query": "베타"})["count"], 1)
        path.unlink()
        self.assertEqual(bridge.call("wiki_search", {"query": "베타"})["count"], 0)
        self.assertEqual(bridge.snapshot(validate=True)["candidates"], [])
        self.assertEqual(bridge.snapshot()["exploration"]["retrievalUsage"]["counts"]["fts"], 4)

    def test_common_fts_terms_bound_file_reads_and_preserve_scope(self):
        for number in range(260):
            (self.root / f"wiki/concepts/many-{number}.md").write_text("# Common needle\nneedle text")
        index = dashboard.index_module.StudioIndex(self.root)
        bridge = self.bridge(index=index)
        with mock.patch.object(bridge, "_text_for", wraps=bridge._text_for) as reads:
            result = bridge.call("wiki_search", {"query":"needle", "scope":"wiki"})
        self.assertEqual(result["method"], "fts")
        self.assertTrue(result["candidateLimited"])
        self.assertFalse(result["totalIsExact"])
        self.assertLessEqual(reads.call_count, 120)
        self.assertTrue(all(row["id"].startswith("wiki/") for row in result["results"]))

    def test_connection_builds_sqlite_without_modifying_markdown_or_old_root_on_failure(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        app = dashboard.Dashboard()
        self.addCleanup(app.stop_all)
        app.connect(str(self.root), enable_sqlite=True)
        self.assertTrue((self.root / "state/studio_search.sqlite").is_file())
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*.md")})
        status = app.retrieval_status({"expectedRoot": str(self.root)})
        self.assertTrue(status["chatMethods"]["fts"])
        self.assertEqual(status["studio"]["state"], "current")
        with mock.patch.object(dashboard.index_module.StudioIndex, "ensure", side_effect=ValueError("blocked")):
            with self.assertRaisesRegex(ValueError, "blocked"):
                app.connect(str(self.root), enable_sqlite=True)
        self.assertEqual(app.root, self.root)

    def test_document_http_read_releases_app_lock_and_rejects_a_late_root(self):
        app = dashboard.Dashboard(self.root)
        self.addCleanup(app.stop_all)
        entered, release = threading.Event(), threading.Event()
        original = dashboard.document_payload
        def slow(*args):
            entered.set();release.wait(3)
            return original(*args)
        server = dashboard.ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
        server.app = app
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        outcome = []
        def get_document():
            try:
                with request.urlopen(f"http://127.0.0.1:{server.server_port}/api/document?path=wiki/concepts/topic-0001.md", timeout=3) as response:
                    outcome.append(response.status)
            except error.HTTPError as exc:
                outcome.append(exc.code);exc.close()
        with mock.patch.object(dashboard, "document_payload", side_effect=slow):
            thread = threading.Thread(target=get_document)
            thread.start()
            try:
                self.assertTrue(entered.wait(1))
                self.assertTrue(app.lock.acquire(False));app.lock.release()
                other = make_vault(Path(self.temp.name)/"other", sources=1, reports=1, wiki_pages=5, runs=0)
                app.connect(str(other))
            finally:
                release.set();thread.join(3)
        self.assertEqual(outcome, [400])

    def test_server_timeout_cancels_late_read_and_rejects_retry_queue(self):
        entered, release = threading.Event(), threading.Event()
        def slow(*args):
            entered.set()
            release.wait(3)
            return self.catalog.document_payload(*args)
        bridge = self.bridge(payload=slow)
        bridge.TOOL_TIMEOUT_SECONDS = .15
        env = bridge.start()
        def call():
            req = request.Request(env["WIKI_STUDIO_TOOL_URL"], data=json.dumps({"tool":"wiki_read","arguments":{"path":"wiki/concepts/topic-0001.md"}}).encode(), headers={"Authorization":"Bearer " + env["WIKI_STUDIO_TOOL_TOKEN"]})
            return request.urlopen(req, timeout=2)
        try:
            start = time.monotonic()
            with self.assertRaises(error.HTTPError) as failure:
                call()
            self.assertEqual(failure.exception.code, 504)
            failure.exception.close()
            self.assertLess(time.monotonic() - start, 1)
            with self.assertRaises(error.HTTPError) as retry:
                call()
            self.assertEqual(retry.exception.code, 409)
            retry.exception.close()
        finally:
            release.set()
        self.wait_for(lambda: not bridge._http_operation_lock.locked())
        self.assertEqual(bridge.snapshot()["candidates"], [])
        bridge.TOOL_TIMEOUT_SECONDS = 2
        with call() as response:
            self.assertTrue(json.load(response)["result"]["citationCandidate"])

    def test_disconnected_socket_cancels_request_without_traceback(self):
        entered, release = threading.Event(), threading.Event()
        def slow(*args):
            entered.set();release.wait(3)
            return self.catalog.document_payload(*args)
        bridge = self.bridge(payload=slow)
        env = bridge.start()
        server_errors = []
        bridge._server.handle_error = lambda *args: server_errors.append(args)
        port = bridge._server.server_address[1]
        body = json.dumps({"tool":"wiki_read","arguments":{"path":"wiki/concepts/topic-0001.md"}}).encode()
        connection = socket.create_connection(("127.0.0.1", port))
        header = f"POST / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {env['WIKI_STUDIO_TOOL_TOKEN']}\r\nContent-Length: {len(body)}\r\n\r\n".encode()
        connection.sendall(header + body)
        try:
            self.assertTrue(entered.wait(1))
            connection.close()
            time.sleep(.15)
        finally:
            connection.close();release.set()
        self.wait_for(lambda: not bridge._http_operation_lock.locked())
        self.assertEqual(bridge.snapshot()["candidates"], [])
        self.assertEqual(server_errors, [])


if __name__ == "__main__":
    unittest.main()
