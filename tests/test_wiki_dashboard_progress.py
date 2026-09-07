from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock
from urllib import request, error

from progress_fixture import make_vault

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("progress_dashboard_test", ROOT / "runtime/wiki_dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = make_vault(Path(self.tmp.name)/"one", sources=3, reports=3, wiki_pages=10, runs=3)

    def wait_for(self, condition):
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(.01)
        self.fail("Background work did not settle")

    def test_run_memo_rechecks_only_changed_run_and_reuses_graph(self):
        catalog = dashboard.documents_module.DocumentCatalog(dashboard.workflow, dashboard.batch)
        with mock.patch.object(dashboard.workflow, "project_status_many", wraps=dashboard.workflow.project_status_many) as status, mock.patch.object(catalog, "graph", wraps=catalog.graph) as graph:
            first = catalog.snapshot(self.root)
            second = catalog.snapshot(self.root)
            self.assertEqual(first["sources"], second["sources"])
            self.assertEqual(status.call_count, 1)
            path = self.root / "state/wiki_runs/fixture-0000.json"
            payload = json.loads(path.read_text())
            payload["updated_at"] = "2026-09-08T00:00:00Z"
            path.write_text(json.dumps(payload))
            current = catalog.snapshot(self.root)
            self.assertEqual(len(status.call_args.args[1]), 1)
            self.assertEqual(status.call_count, 2)
            self.assertEqual(graph.call_count, 1)
        fresh = dashboard.documents_module.DocumentCatalog(dashboard.workflow, dashboard.batch).snapshot(self.root)
        self.assertEqual(current["sources"], fresh["sources"])
        # Consumers must not be able to corrupt memoized values.
        current["graph"]["nodes"].clear()
        current["sources"][0]["run"]["blockers"].clear()
        self.assertEqual(catalog.snapshot(self.root)["graph"], fresh["graph"])
        self.assertEqual(catalog.snapshot(self.root)["sources"], fresh["sources"])

    def test_run_memo_invalidates_source_corpus_contract_and_warehouse(self):
        catalog = dashboard.documents_module.DocumentCatalog(dashboard.workflow, dashboard.batch)
        with mock.patch.object(dashboard.workflow, "project_status_many", wraps=dashboard.workflow.project_status_many) as status:
            catalog.snapshot(self.root)
            source = self.root / "raw/inbox/source-0000.md"
            source.write_text(source.read_text() + "\nChanged raw")
            catalog.snapshot(self.root)
            self.assertEqual([run["source"] for run in status.call_args.args[1]], ["raw/inbox/source-0000.md"])
            page = self.root / "wiki/concepts/topic-0000.md"
            page.write_text(page.read_text() + "\nChanged wiki")
            catalog.snapshot(self.root)
            self.assertEqual(len(status.call_args.args[1]), 3)
            before = catalog.signature(self.root)
            warehouse = self.root / "warehouse/jsonl"
            warehouse.mkdir(parents=True)
            (warehouse / "test.jsonl").write_text('{}\n')
            self.assertNotEqual(before, catalog.signature(self.root))
            calls = status.call_count
            catalog.snapshot(self.root)
            self.assertEqual(status.call_count, calls + 1)
            self.assertEqual(len(status.call_args.args[1]), 3)
            calls = status.call_count
            with mock.patch.object(dashboard.workflow, "procedure_contract_digest", return_value="changed-contract"):
                catalog.snapshot(self.root)
            self.assertEqual(status.call_count, calls + 1)
            self.assertEqual(len(status.call_args.args[1]), 3)

    def test_run_memo_tracks_internal_symlink_target_even_for_same_inode(self):
        for relative in ("AGENTS.md", "raw/inbox/source-0000.md"):
            with self.subTest(relative=relative):
                path = self.root / relative
                one, two = path.with_name(path.name+".target-a"), path.with_name(path.name+".target-b")
                path.rename(one)
                two.hardlink_to(one)
                path.symlink_to(one.name)
                catalog = dashboard.documents_module.DocumentCatalog(dashboard.workflow, dashboard.batch)
                with mock.patch.object(dashboard.workflow, "project_status_many", wraps=dashboard.workflow.project_status_many) as status:
                    catalog.snapshot(self.root)
                    before = catalog.signature(self.root)
                    path.unlink();path.symlink_to(two.name)
                    self.assertNotEqual(before, catalog.signature(self.root))
                    result = catalog.snapshot(self.root)
                    self.assertEqual(status.call_count, 2)
                    selected = next(row for row in result["sources"] if row["id"]=="raw/inbox/source-0000.md")
                    self.assertEqual(selected["run"]["current_fingerprint"], dashboard.workflow.state_fingerprint(self.root, selected["id"]))

    def test_bulk_status_matches_scalar_and_hashes_each_path_once(self):
        w = dashboard.workflow
        payloads = [json.loads(p.read_text()) for p in (self.root/"state/wiki_runs").glob("*.json")]
        expected = {p["source"]:w.project_status(self.root,p) for p in payloads}
        with mock.patch.object(w, "file_digest", wraps=w.file_digest) as digest:
            actual = w.project_status_many(self.root,payloads)
        self.assertEqual(actual,expected)
        paths = [call.args[0] for call in digest.call_args_list]
        self.assertEqual(len(paths),len(set(paths)))
        self.assertEqual(w.procedure_contract_digest(), dashboard.batch.workflow.procedure_contract_digest())

    def test_bulk_status_respects_internal_contract_symlink(self):
        w = dashboard.workflow
        contract = self.root/"AGENTS.md"
        contract.rename(self.root/"contract.md")
        contract.symlink_to("contract.md")
        payload = json.loads(next((self.root/"state/wiki_runs").glob("*.json")).read_text())
        self.assertEqual(w.project_status_many(self.root,[payload])[payload["source"]],w.project_status(self.root,payload))

    def test_bulk_batch_status_matches_scalar(self):
        batch = dashboard.batch
        plans = [batch.plan_batch(self.root,[f"raw/inbox/source-{i:04}.md"]) for i in range(3)]
        ids = [p["batch_id"] for p in plans]
        expected = {key:batch.batch_status(self.root,key) for key in ids}
        with mock.patch.object(batch.workflow,"file_digest",wraps=batch.workflow.file_digest) as digest:
            actual = batch.batch_status_many(self.root,ids)
        self.assertEqual(actual,expected)
        paths = [call.args[0] for call in digest.call_args_list]
        self.assertEqual(len(paths),len(set(paths)))

    def test_unchanged_state_reuses_snapshot_and_external_change_rebuilds(self):
        app = dashboard.Dashboard(self.root)
        with mock.patch.object(dashboard,"snapshot",wraps=dashboard.snapshot) as build:
            app.state()
            app.cached_at = 0
            app.state()
            self.assertEqual(build.call_count,1)
            path = self.root/"wiki/concepts/topic-0000.md"
            path.write_text("# Changed\n",encoding="utf-8")
            app.cached_at = 0
            current = app.state()
            self.assertEqual(build.call_count,2)
            self.assertTrue(any(n["title"]=="Changed" for n in current["graph"]["nodes"]))

    def test_slow_view_keeps_app_lock_and_status_available_single_flight(self):
        app = dashboard.Dashboard(self.root)
        initial = app.state()
        app.cache = None
        entered, release = threading.Event(),threading.Event()
        original = dashboard.snapshot
        def slow(root,mode,progress=None):
            progress("graph",path="wiki/concepts/topic-0000.md",current=1,total=8)
            entered.set();release.wait(4)
            return original(root,mode,progress)
        with mock.patch.object(dashboard,"snapshot",side_effect=slow) as build:
            app.state(wait=False)
            self.assertTrue(entered.wait(1))
            try:
                start = time.monotonic()
                result = app.state(wait=False)
                self.assertLess(time.monotonic()-start,.5)
                self.assertEqual(result["sources"],initial["sources"])
                self.assertFalse(result["snapshotFresh"])
                self.assertTrue(app.lock.acquire(False));app.lock.release()
                self.assertEqual(build.call_count,1)
            finally:release.set()
            self.wait_for(lambda:not app._snapshot_guard.locked())

    def test_connection_cancel_preserves_old_root_and_reports_blocked_file(self):
        app = dashboard.Dashboard(self.root)
        target = make_vault(Path(self.tmp.name)/"two",sources=2,reports=2,wiki_pages=8,runs=2)
        entered, release = threading.Event(),threading.Event()
        original = dashboard.snapshot
        def slow(root,mode,progress=None):
            progress("reports",path="wiki/_meta/ingest_reports/ingest-0000.md",current=0,total=2)
            entered.set();release.wait(4)
            progress("reports",current=2,total=2)
            return original(root,mode,progress)
        with mock.patch.object(dashboard,"snapshot",side_effect=slow):
            result = app.start_connection(str(target),"cancel-test")
            self.assertTrue(entered.wait(1))
            try:
                status = app.connection_status(result["id"])
                self.assertEqual(status["stage"],"reports")
                self.assertIn("ingest-0000",status["path"])
                self.assertTrue(app.lock.acquire(False));app.lock.release()
                app.cancel_connection(result["id"])
                self.assertEqual(app.root,self.root)
            finally:release.set()
            self.wait_for(lambda:app.connection_status(result["id"])["status"]=="cancelled")
        self.assertEqual(app.root,self.root)

    def test_late_old_view_cannot_overwrite_new_connection(self):
        app = dashboard.Dashboard(self.root)
        target = make_vault(Path(self.tmp.name)/"two",sources=2,reports=2,wiki_pages=8,runs=2)
        entered, release = threading.Event(),threading.Event()
        original = dashboard.snapshot
        def slow(root,mode,progress=None):
            entered.set();release.wait(4)
            return original(root,mode,progress)
        with mock.patch.object(dashboard,"snapshot",side_effect=slow):
            app.state(wait=False)
            self.assertTrue(entered.wait(1))
            try:app.connect(str(target))
            finally:release.set()
            self.wait_for(lambda:not app._snapshot_guard.locked())
        self.assertEqual(app.root,target)
        self.assertEqual(app.state()["root"],str(target))

    def test_cancel_before_start_and_old_cancel_never_cancel_new_attempt(self):
        app = dashboard.Dashboard()
        app.cancel_connection("not-arrived")
        self.assertEqual(app.start_connection(str(self.root),"not-arrived")["status"],"cancelled")
        self.assertIsNone(app.root)
        progress = dashboard.progress_module.ReadProgress(self.root,job_id="new")
        app._connection_work=progress
        app.cancel_connection("old")
        self.assertFalse(progress.cancelled.is_set())
        app.cancel_connection("new")
        replacement=dashboard.progress_module.ReadProgress(self.root,job_id="replacement")
        replacement.finish()
        app._connection_work=replacement
        with mock.patch.object(dashboard.progress_module.ReadProgress,"run") as start:
            self.assertEqual(app.start_connection(str(self.root),"new")["status"],"cancelled")
            start.assert_not_called()

    def test_queue_verification_is_shared_and_does_not_hold_app_lock(self):
        app = dashboard.Dashboard(self.root)
        queue = app.automation
        body = (self.root/"raw/inbox/source-0000.md").read_bytes()
        queue.queue=[{"id":f"q{i}","source":"raw/inbox/source-0000.md","status":"completed","_contentHash":queue._hash_bytes(body)} for i in range(3)]
        queue._persist()
        entered, release = threading.Event(),threading.Event()
        calls=[]
        def slow(root,mode):
            calls.append(root);entered.set();release.wait(4)
            return {"sources":[{"id":"raw/inbox/source-0000.md","stage":"done","references":[]}]}
        queue.snapshot_helper=slow
        thread=threading.Thread(target=queue.tick)
        thread.start()
        self.assertTrue(entered.wait(1))
        try:
            self.assertTrue(app.lock.acquire(False));app.lock.release()
            self.assertEqual(len(queue.status()["queue"]),3)
        finally:release.set();thread.join(4)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(calls),1)

    def test_late_queue_result_cannot_repopulate_a_different_workspace(self):
        app=dashboard.Dashboard(self.root)
        queue=app.automation
        data=(self.root/'raw/inbox/source-0000.md').read_bytes()
        queue.queue=[{'id':'old','source':'raw/inbox/source-0000.md','status':'completed','_contentHash':queue._hash_bytes(data)}]
        queue._persist()
        entered,release=threading.Event(),threading.Event()
        def blocked(root,mode):
            entered.set();release.wait(4)
            return {'sources':[{'id':'raw/inbox/source-0000.md','stage':'done','references':[]}]}
        queue.snapshot_helper=blocked
        thread=threading.Thread(target=queue.tick);thread.start()
        self.assertTrue(entered.wait(1))
        target=make_vault(Path(self.tmp.name)/'other',sources=1,reports=1,wiki_pages=5,runs=1)
        try:app.connect(str(target))
        finally:release.set();thread.join(4)
        self.assertEqual(app.root,target)
        self.assertEqual(queue.queue,[])
        self.assertFalse((target/'state/dashboard_automation/state.json').exists())

    def test_tool_scan_activity_remains_visible_and_cancelable_during_slow_read(self):
        tools=dashboard.chat_tools_module
        bridge=tools.WikiChatTools(self.root,'wiki',{
            'document_inventory':dashboard.document_inventory,'document_payload':dashboard.document_payload,
        })
        bridge.call('ready',{})
        entered,release=threading.Event(),threading.Event()
        original=bridge._text_for
        def blocked(relative,inventory):
            entered.set();release.wait(4)
            return original(relative,inventory)
        errors=[]
        def search():
            try:bridge.call('wiki_search',{'query':'검증','scope':'wiki'})
            except tools.WikiChatToolError as exc:errors.append(exc)
        with mock.patch.object(bridge,'_text_for',side_effect=blocked):
            thread=threading.Thread(target=search);thread.start()
            self.assertTrue(entered.wait(1))
            try:
                start=time.monotonic();view=bridge.snapshot()
                self.assertLess(time.monotonic()-start,.5)
                active=view['exploration']['active']
                self.assertEqual(active['tool'],'wiki_search')
                self.assertEqual(active['query'],'검증')
                self.assertGreater(active['total'],0)
                self.assertIsInstance(active['current'],int)
                self.assertTrue(active['path'].startswith('wiki/'))
                start=time.monotonic();bridge.stop();self.assertLess(time.monotonic()-start,.5)
            finally:release.set();thread.join(4)
        self.assertTrue(errors)
        self.assertEqual(bridge.snapshot()['candidates'],[])

    def test_thinking_events_only_become_activity_metadata(self):
        app=dashboard.Dashboard(self.root)
        bridge=dashboard.chat_tools_module.WikiChatTools(self.root,'wiki',{
            'document_inventory':dashboard.document_inventory,'document_payload':dashboard.document_payload,
        })
        bridge.call('ready',{})
        events=[{'type':'agent_start'},
                {'type':'message_update','assistantMessageEvent':{'type':'thinking_delta','delta':'PRIVATE_THOUGHT_SENTINEL'}},
                {'type':'auto_retry_start'},
                {'type':'message_end','message':{'role':'assistant','stopReason':'stop','content':[{'type':'text','text':'답변'},{'type':'thinking','thinking':'PRIVATE_THOUGHT_SENTINEL'}]}},
                {'type':'agent_settled'}]
        process=mock.Mock()
        process.stdin=io.StringIO();process.stdout=io.StringIO(''.join(json.dumps(event)+'\n' for event in events));process.stderr=io.StringIO('PRIVATE_STDERR_SENTINEL')
        process.poll.return_value=0
        app.chat_jobs['chat-test']={'id':'chat-test','root':str(self.root),'status':'running','answer':'','references':[],'candidates':[],'startedAt':time.time()}
        app.chat_processes['chat-test']=process;app.chat_tools['chat-test']=bridge
        app.consume_chat('chat-test',process)
        result=app.chat_status('chat-test')
        self.assertNotIn('PRIVATE_',json.dumps(result))
        self.assertTrue(any(event['phase']=='model' for event in result['progress']['events']))
        self.assertTrue(any(event['phase']=='retry' for event in result['progress']['events']))
        self.assertEqual(result['status'],'finished')

    def test_http_progress_can_be_polled_and_cancelled_while_snapshot_is_blocked(self):
        app=dashboard.Dashboard(self.root)
        server=dashboard.ThreadingHTTPServer(('127.0.0.1',0),dashboard.Handler);server.app=app
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base=f'http://127.0.0.1:{server.server_port}'
        def post(route,body):
            req=request.Request(base+'/api/'+route,data=json.dumps(body).encode(),headers={'Origin':base,'X-Dashboard-Token':app.token,'Content-Type':'application/json'})
            with request.urlopen(req,timeout=1) as response:return json.load(response)
        entered,release=threading.Event(),threading.Event()
        def blocked(root,mode,progress=None):
            progress('graph',path='wiki/slow.md');entered.set();release.wait(4);progress('graph')
            return {}
        with mock.patch.object(dashboard,'snapshot',side_effect=blocked):
            result=post('connect-start',{'root':str(self.root),'id':'http-progress'})
            self.assertTrue(entered.wait(1))
            try:
                with request.urlopen(base+'/api/connection?id='+result['id'],timeout=1) as response:
                    self.assertEqual(json.load(response)['path'],'wiki/slow.md')
                self.assertEqual(post('connect-cancel',{'id':result['id']})['status'],'cancelling')
            finally:release.set()
            self.wait_for(lambda:app.connection_status(result['id'])['status']=='cancelled')


class LargeVaultRegression(unittest.TestCase):
    def test_reported_volume_parses_each_report_once_and_never_promotes_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=make_vault(Path(tmp)/'large')
            reports=[]
            original=Path.read_text
            def counted(path,*args,**kwargs):
                if path.parent.name=='ingest_reports':reports.append(path)
                return original(path,*args,**kwargs)
            with mock.patch.object(Path,'read_text',counted):
                view=dashboard.snapshot(root)
            self.assertEqual(len(view['sources']),635)
            self.assertEqual(len(reports),639)
            self.assertEqual(len(set(reports)),639)
            self.assertFalse(any(row['stage']=='done' for row in view['sources']))
            self.assertTrue(all(row['coverage'] is None for row in view['sources'][:4]))


if __name__=='__main__':unittest.main()
