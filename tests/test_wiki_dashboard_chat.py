from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "runtime/wiki_dashboard.py"
spec = importlib.util.spec_from_file_location("dashboard_chat_under_test", SCRIPT)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)

FAKE_WRITER_PI = r'''import json,os,sys
capture=os.environ.get('WIKI_STUDIO_WRITER_CAPTURE')
if capture:
 with open(capture,'w',encoding='utf-8') as stream: json.dump(sys.argv[1:],stream)
for line in sys.stdin:
 event=json.loads(line)
 if event.get('type')=='prompt':
  print(json.dumps({'id':event['id'],'type':'response','success':True}),flush=True)
 elif event.get('type')=='steer' and event.get('message')=='mutate-topic':
  with open('wiki/concepts/topic.md','w',encoding='utf-8') as stream:
   stream.write('# Changed by writer\\n\\nCurrent writer content.\\n')
  print(json.dumps({'type':'response','command':'steer','success':True}),flush=True)
 elif event.get('type')=='abort':
  print(json.dumps({'type':'agent_end','willRetry':False}),flush=True)
  print(json.dumps({'type':'agent_settled'}),flush=True)
  break
'''


FAKE_CHAT_PI = r'''import json,os,sys,time
from urllib.request import Request,urlopen
capture=sys.argv[1]
def out(value):
 print(json.dumps(value,ensure_ascii=False),flush=True)
def tool(name,args):
 req=Request(os.environ['WIKI_STUDIO_TOOL_URL'],data=json.dumps({'tool':name,'arguments':args}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+os.environ['WIKI_STUDIO_TOOL_TOKEN']})
 with urlopen(req) as response: return json.load(response)
if os.environ.get('WIKI_STUDIO_TOOL_URL'):
 tool('ready',{})
for line in sys.stdin:
 event=json.loads(line)
 if event.get('type')=='prompt':
  with open(capture,'w',encoding='utf-8') as stream:
   json.dump({'argv':sys.argv[2:],'cwd':os.getcwd(),'message':event['message'],
              'agentDir':os.environ.get('PI_CODING_AGENT_DIR')},stream,ensure_ascii=False)
  message=event['message']
  out({'id':event['id'],'type':'response','success':True})
  if '"question": "unknown"' in message:
   print('provider error: unknown model ollama/private-model API_KEY=DO_NOT_EXPOSE',file=sys.stderr,flush=True)
   out({'id':'initial','type':'response','success':False,'error':'unknown model ollama/private-model API_KEY=DO_NOT_EXPOSE'})
  elif '"question": "fail"' in message:
   print('provider API_KEY=DO_NOT_EXPOSE raw failure',file=sys.stderr,flush=True)
   out({'id':'initial','type':'response','success':False,'error':'API_KEY=DO_NOT_EXPOSE'})
  elif '"question": "wait"' in message:
   out({'type':'message_update','assistantMessageEvent':{'type':'text_delta','delta':'부분 응답 [1]'}})
  elif '"question": "read-and-wait"' in message:
   out({'type':'message_start','message':{'role':'assistant'}})
   tool('wiki_read',{'path':'wiki/concepts/topic.md'})
   out({'type':'tool_execution_end','toolName':'wiki_read','toolCallId':'read-and-wait'})
  elif '"question": "huge-stream"' in message:
   out({'type':'message_update','assistantMessageEvent':{'type':'text_delta','delta':'S'*32001}})
  elif '"question": "huge-final"' in message:
   out({'type':'message_end','message':{'role':'assistant','stopReason':'stop','content':[{'type':'text','text':'F'*32001}]}})
   out({'type':'agent_settled'})
  else:
   if os.environ.get('WIKI_STUDIO_TOOL_URL') and '절대로없는검색어' not in message:
    out({'type':'message_start','message':{'role':'assistant'}})
    out({'type':'message_end','message':{'role':'assistant','stopReason':'toolUse','content':[{'type':'text','text':'문서를 먼저 확인합니다.'}]}})
    tool('wiki_list',{})
    tool('wiki_read',{'path':'wiki/concepts/topic.md'})
    out({'type':'tool_execution_end','toolName':'wiki_read','toolCallId':'read-1'})
   out({'type':'message_start','message':{'role':'assistant'}})
   out({'type':'message_update','assistantMessageEvent':{'type':'text_delta','delta':'부분 응답 [1]'}})
   time.sleep(.06)
   out({'type':'message_end','message':{'role':'assistant','stopReason':'stop','content':[{'type':'text','text':'로컬 근거 답변 [1]. 존재하지 않는 번호 [9].'},{'type':'thinking','thinking':'SECRET'}]}})
   out({'type':'agent_end','willRetry':False})
   time.sleep(.03)
   out({'type':'agent_settled'})
 elif event.get('type')=='test-finish':
  out({'type':'message_end','message':{'role':'assistant','stopReason':'stop','content':[{'type':'text','text':'로컬 근거 답변 [1].'}]}})
  out({'type':'agent_end','willRetry':False})
  out({'type':'agent_settled'})
 elif event.get('type')=='abort':
  out({'type':'agent_end','willRetry':False})
  out({'type':'agent_settled'})
'''


class WikiDashboardChatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "vault"
        for name in ("raw/inbox", "wiki/concepts", "wiki/sources", "wiki/_meta/ingest_reports"):
            (self.root / name).mkdir(parents=True)
        (self.root / "AGENTS.md").write_text("# Wiki-only contract\n", encoding="utf-8")
        (self.root / "wiki/_meta/index.md").write_text("# Index\n", encoding="utf-8")
        (self.root / "wiki/_meta/log.md").write_text("# Log\n", encoding="utf-8")
        (self.root / "raw/inbox/source.md").write_text("# 실제 원문\n\n한글 유니코드 근거입니다.\n", encoding="utf-8")
        (self.root / "wiki/concepts/topic.md").write_text(
            "# 한글 유니코드 주제\n\n한글 유니코드 근거와 설명입니다.\n"
            "[실제 원문](../../raw/inbox/source.md)\n"
            "[외부 탈출](../../../outside.md)\n[[other]]\n[[duplicate]]\n",
            encoding="utf-8",
        )
        (self.root / "wiki/concepts/other.md").write_text("# Other\n", encoding="utf-8")
        (self.root / "wiki/concepts/duplicate.md").write_text("# Wiki duplicate\n", encoding="utf-8")
        (self.root / "raw/inbox/duplicate.md").write_text("# Raw duplicate\n", encoding="utf-8")
        self.outside = Path(self.temp.name) / "outside.md"
        self.outside.write_text("# Outside secret\n", encoding="utf-8")
        (self.root / "raw/inbox/escape.md").symlink_to(self.outside)
        self.fake = Path(self.temp.name) / "fake_chat_pi.py"
        self.fake.write_text(FAKE_CHAT_PI, encoding="utf-8")
        self.writer = Path(self.temp.name) / "fake_writer_pi.py"
        self.writer.write_text(FAKE_WRITER_PI, encoding="utf-8")
        self.capture = Path(self.temp.name) / "capture.json"

    def app(self, root=None, **kwargs):
        app = dashboard.Dashboard(root or self.root, [sys.executable, str(self.fake), str(self.capture)], **kwargs)
        self.addCleanup(app.stop_all)
        return app

    def wait_for(self, condition):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(.01)
        self.fail("Background chat did not settle")

    def test_unicode_retrieval_is_bounded_prefers_wiki_and_uses_grounded_excerpt(self):
        candidates = dashboard.lexical_candidates(self.root, "wiki", "한글 유니코드")
        self.assertLessEqual(len(candidates), 6)
        self.assertEqual(candidates[0]["id"], "wiki/concepts/topic.md")
        self.assertIn("한글 유니코드 근거와 설명입니다.", candidates[0]["excerpt"])
        self.assertEqual(candidates[0]["rawSources"], [{"id": "raw/inbox/source.md", "title": "실제 원문"}])
        self.assertEqual([item["number"] for item in candidates], list(range(1, len(candidates) + 1)))

    def test_document_payload_resolves_only_real_inventory_links_and_sources(self):
        (self.root / "wiki/concepts/root-link.md").write_text(
            "# Root link\n\n[Source](raw/inbox/source.md)\n", encoding="utf-8")
        payload = dashboard.document_payload(self.root, "wiki", "wiki/concepts/topic.md")
        self.assertEqual(payload["root"], str(self.root.resolve()))
        self.assertEqual(payload["path"], "wiki/concepts/topic.md")
        self.assertEqual(payload["title"], "한글 유니코드 주제")
        self.assertEqual(payload["text"], payload["content"])
        self.assertEqual(payload["contentHash"], dashboard.hashlib.sha256((self.root / payload["path"]).read_bytes()).hexdigest())
        self.assertEqual(payload["rawSources"], [{"id": "raw/inbox/source.md", "title": "실제 원문"}])
        self.assertEqual({(item["id"], item["kind"]) for item in payload["links"]}, {
            ("raw/inbox/source.md", "source"), ("wiki/concepts/other.md", "wiki")
        })
        rooted = dashboard.document_payload(self.root, "wiki", "wiki/concepts/root-link.md")
        self.assertEqual(rooted["rawSources"], [{"id": "raw/inbox/source.md", "title": "실제 원문"}])
        for path in ("wiki/concepts/../../../outside.md", "raw/inbox/escape.md", "raw/../outside.md"):
            with self.assertRaises(ValueError):
                dashboard.document_payload(self.root, "wiki", path)

    def test_coverage_receipt_is_an_explicit_source_trace(self):
        source = self.root / "raw/inbox/source.md"
        (self.root / "wiki/concepts/covered.md").write_text("# Covered\n\nReceipt-backed facts.\n", encoding="utf-8")
        (self.root / "wiki/_meta/ingest_reports/ingest-source.md").write_text(
            "---\nstatus: applied\nraw_path: raw/inbox/source.md\n"
            f"source_sha256: {dashboard.workflow.file_digest(source)}\n---\n"
            "# Receipt\n\n- mapped to `wiki/concepts/covered.md#facts`\n",
            encoding="utf-8",
        )
        payload = dashboard.document_payload(self.root, "wiki", "wiki/concepts/covered.md")
        self.assertEqual(payload["rawSources"], [{"id": "raw/inbox/source.md", "title": "실제 원문"}])

    def test_async_chat_filters_citations_and_invokes_locked_down_pi(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file() and not p.is_symlink()}
        app = self.app()
        started = app.start_chat("한글 유니코드", [{"role": "user", "content": "이전 질문"}], "test/model")
        self.assertEqual(started["status"], "running")
        self.wait_for(lambda: app.chat_status(started["id"])["status"] != "running")
        result = app.chat_status(started["id"])
        self.assertEqual(result["status"], "finished")
        self.assertEqual(result["answer"], "로컬 근거 답변 [1]. 존재하지 않는 번호 [9].")
        self.assertEqual([item["number"] for item in result["references"]], [1])
        self.assertGreaterEqual(len(result["candidates"]), 1)
        self.assertNotIn("SECRET", json.dumps(result, ensure_ascii=False))
        captured = json.loads(self.capture.read_text(encoding="utf-8"))
        for flag in ("--mode", "rpc", "--no-builtin-tools", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-context-files", "--no-session", "-e"):
            self.assertIn(flag, captured["argv"])
        self.assertNotIn("--skill", captured["argv"])
        self.assertEqual(captured["cwd"], str(self.root.resolve()))
        self.assertIn('"role": "user"', captured["message"])
        self.assertIn("question은 답해야 할 사용자의 질문", captured["message"])
        self.assertIn("숫자 인용은 읽은 근거의 출처 표시", captured["argv"][captured["argv"].index("--append-system-prompt") + 1])
        self.assertNotIn("--no-tools", captured["argv"])
        self.assertTrue(result["exploration"]["ready"])
        self.assertEqual(result["exploration"]["readCount"], 1)
        self.assertNotIn("WIKI_STUDIO_TOOL_TOKEN", captured["message"])
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file() and not p.is_symlink()}
        self.assertEqual(before, after)

    def test_writer_uses_adapter_skill_and_gate_entrypoint_paths(self):
        capture = Path(self.temp.name) / "writer-argv.json"
        app = dashboard.Dashboard(self.root, [sys.executable, str(self.writer)])
        self.addCleanup(app.stop_all)
        with mock.patch.dict("os.environ", {"WIKI_STUDIO_WRITER_CAPTURE": str(capture)}):
            app.start("capture writer command", ["raw/inbox/source.md"])
        self.wait_for(capture.is_file)
        argv = json.loads(capture.read_text(encoding="utf-8"))
        self.assertEqual(argv[argv.index("--skill") + 1], str(dashboard.LOOP_SKILL))
        instructions = argv[argv.index("--append-system-prompt") + 1]
        self.assertIn(json.dumps(str(dashboard.LOOP_ENTRYPOINT)), instructions)
        self.assertIn(str(dashboard.LOOP_SKILL / "SKILL.md"), instructions)
        self.assertNotIn("--gate-path", argv)  # Not a Pi CLI option.
        app.action("stop", {})
        self.wait_for(lambda: app.claim is None)

    def test_project_mode_allows_chat_but_still_blocks_ingest(self):
        shutil.rmtree(self.root / "raw")
        (self.root / "docs").mkdir()
        (self.root / "docs/README.md").write_text("# 프로젝트 채팅\n\n읽기 전용 근거입니다.\n", encoding="utf-8")
        app = self.app()
        self.assertEqual(app.mode, "project")
        self.assertTrue(app.state()["chatAvailable"])
        started = app.start_chat("프로젝트 채팅")
        self.wait_for(lambda: app.chat_status(started["id"])["status"] != "running")
        self.assertEqual(app.chat_status(started["id"])["status"], "finished")
        with self.assertRaises(ValueError):
            app.action("upload", {"name": "new.md", "content": "# New"})
        with self.assertRaises(ValueError):
            app.action("start", {"message": "ingest", "sources": ["raw/inbox/source.md"]})
        self.assertFalse((self.root / "raw").exists())

    def test_old_assistant_citations_are_removed_before_current_turn_prompt(self):
        app = self.app()
        started = app.start_chat("한글 유니코드", [
            {"role": "user", "content": "이전 질문 [1]"},
            {"role": "assistant", "content": "과거 답변 [1] 및 [27]"},
        ])
        self.wait_for(lambda: app.chat_status(started["id"])["status"] != "running")
        captured = json.loads(self.capture.read_text(encoding="utf-8"))
        marker = captured["message"].split("<chat-data>\n", 1)[1].rsplit("\n</chat-data>", 1)[0]
        prompt_data = json.loads(marker)
        self.assertEqual(prompt_data["history"][0]["content"], "이전 질문 [1]")
        self.assertEqual(prompt_data["history"][1]["content"], "과거 답변  및 ")
        system_prompt = captured["argv"][captured["argv"].index("--append-system-prompt") + 1]
        self.assertIn("오직 이번 요청의 wiki_read가 반환한 number만", system_prompt)
        self.assertIn("history의 과거 인용 번호를 재사용하지 마세요", system_prompt)

    def test_streaming_and_final_answers_fail_safely_at_32000_characters(self):
        for message, expected in (("huge-stream", "S"), ("huge-final", "F")):
            with self.subTest(message=message):
                app = self.app()
                started = app.start_chat(message)
                self.wait_for(lambda: app.chat_status(started["id"])["status"] != "running")
                result = app.chat_status(started["id"])
                self.assertEqual(result["status"], "failed")
                self.assertEqual(len(result["answer"]), 32000)
                self.assertEqual(set(result["answer"]), {expected})
                self.assertEqual(result["error"], "모델 응답이 허용된 길이를 초과해 안전하게 중단했습니다.")
                self.assertLess(len(json.dumps(result, ensure_ascii=False)), 50000)

    def test_unread_documents_never_become_citation_evidence(self):
        app = self.app()
        started = app.start_chat("절대로없는검색어")
        self.wait_for(lambda: app.chat_status(started["id"])["status"] != "running")
        result = app.chat_status(started["id"])
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["references"], [])
        captured = json.loads(self.capture.read_text(encoding="utf-8"))
        self.assertNotIn('localEvidenceCandidates', captured["message"])

    def test_chat_and_writer_are_independent_lanes_until_each_is_stopped(self):
        app = self.app()
        app.pi_command = [sys.executable, str(self.writer)]
        writer = app.start("long writer", ["raw/inbox/source.md"])
        self.assertEqual(writer["id"], app.job["id"])
        self.assertIsNone(app.process.poll())
        self.assertIsNotNone(app.claim)
        with self.assertRaises(ValueError):
            app.start("second writer", ["raw/inbox/source.md"])
        with self.assertRaises(ValueError):
            app.action("upload", {"name": "during-writer.md", "content": "# Blocked\n"})

        app.pi_command = [sys.executable, str(self.fake), str(self.capture)]
        first_chat = app.start_chat("wait")
        self.wait_for(lambda: bool(app.chat_status(first_chat["id"])["answer"]))
        app.stop_chat(first_chat["id"])
        self.wait_for(lambda: app.chat_status(first_chat["id"])["status"] == "stopped")
        self.assertIsNone(app.process.poll())
        self.assertIsNotNone(app.claim)
        app.action("stop", {})
        self.wait_for(lambda: app.claim is None)

        second_chat = app.start_chat("wait")
        self.wait_for(lambda: bool(app.chat_status(second_chat["id"])["answer"]))
        app.pi_command = [sys.executable, str(self.writer)]
        second_writer = app.start("writer during chat", ["raw/inbox/source.md"])
        self.assertEqual(second_writer["id"], app.job["id"])
        self.assertIsNone(app.process.poll())
        app.action("stop", {})
        self.wait_for(lambda: app.claim is None)
        self.assertEqual(app.chat_status(second_chat["id"])["status"], "running")
        app.stop_chat(second_chat["id"])
        self.wait_for(lambda: app.chat_status(second_chat["id"])["status"] == "stopped")

    def test_live_connect_is_rejected_and_finished_id_becomes_stale_after_switch(self):
        app = self.app()
        waiting = app.start_chat("wait")
        self.wait_for(lambda: bool(app.chat_status(waiting["id"])["answer"]))
        with self.assertRaises(ValueError):
            app.connect(str(self.root))
        app.stop_chat(waiting["id"])
        self.wait_for(lambda: app.chat_status(waiting["id"])["status"] == "stopped")
        other = Path(self.temp.name) / "other"
        (other / "wiki/_meta").mkdir(parents=True)
        (other / "AGENTS.md").write_text("# Project\n", encoding="utf-8")
        (other / "wiki/_meta/index.md").write_text("# Other\n", encoding="utf-8")
        app.connect(str(other))
        with self.assertRaises(ValueError):
            app.chat_status(waiting["id"])

    def test_cancellation_settles_stopped_with_partial_answer(self):
        app = self.app()
        started = app.start_chat("wait")
        self.wait_for(lambda: app.chat_status(started["id"])["answer"] == "부분 응답 [1]")
        response = app.stop_chat(started["id"])
        self.assertEqual(response["id"], started["id"])
        self.wait_for(lambda: app.chat_status(started["id"])["status"] == "stopped")
        result = app.chat_status(started["id"])
        self.assertEqual(result["status"], "stopped")
        self.assertIn("endedAt", result)

    def test_stop_and_status_remain_available_during_blocked_tool_io(self):
        app = self.app()
        entered, release = threading.Event(), threading.Event()
        original = dashboard.document_inventory
        def blocked_inventory(root, mode):
            entered.set()
            release.wait(timeout=4)
            return original(root, mode)
        with mock.patch.object(dashboard, "document_inventory", blocked_inventory):
            started = app.start_chat("한글 유니코드")
            try:
                self.assertTrue(entered.wait(timeout=3))
                began = time.monotonic()
                self.assertEqual(app.chat_status(started["id"])["status"], "running")
                app.stop_chat(started["id"])
                self.assertLess(time.monotonic() - began, .75)
            finally:
                release.set()
        self.wait_for(lambda: app.chat_status(started["id"])["status"] == "stopped")
        self.assertEqual(app.chat_status(started["id"])["candidates"], [])

    def test_stopped_chat_does_not_wait_for_post_stop_evidence_io(self):
        app = self.app()
        started = app.start_chat("wait")
        self.wait_for(lambda: bool(app.chat_status(started["id"])["answer"]))
        bridge = app.chat_tools[started["id"]]
        bridge.call("wiki_read", {"path": "wiki/concepts/topic.md"})
        forbidden_inventory = mock.Mock(side_effect=AssertionError("Unexpected post-stop I/O"))
        bridge.document_inventory = forbidden_inventory
        process = app.chat_processes[started["id"]]
        app.stop_chat(started["id"])
        app._force_chat_stop(started["id"], process)
        self.wait_for(lambda: app.chat_status(started["id"])["status"] == "stopped")
        forbidden_inventory.assert_not_called()
        self.assertEqual(app.chat_status(started["id"])["candidates"], [])

    def test_live_writer_mutation_invalidates_read_chat_evidence_before_settlement(self):
        app = self.app()
        app.pi_command = [sys.executable, str(self.writer)]
        app.start("held writer", ["raw/inbox/source.md"])
        writer = app.process
        self.assertIsNone(writer.poll())

        app.pi_command = [sys.executable, str(self.fake), str(self.capture)]
        started = app.start_chat("read-and-wait")
        self.wait_for(lambda: app.chat_status(started["id"])["exploration"]["readCount"] == 1)
        self.assertIsNone(writer.poll())
        app.action("steer", {"message": "mutate-topic"})
        self.wait_for(lambda: (self.root / "wiki/concepts/topic.md").read_text(encoding="utf-8").startswith("# Changed by writer"))
        self.assertIsNone(writer.poll())

        chat = app.chat_processes[started["id"]]
        chat.stdin.write(json.dumps({"type": "test-finish"}) + "\n")
        chat.stdin.flush()
        self.wait_for(lambda: app.chat_status(started["id"])["status"] != "running")
        result = app.chat_status(started["id"])
        self.assertEqual("finished", result["status"])
        self.assertTrue(result["exploration"]["staleEvidence"])
        self.assertGreater(result["exploration"]["invalidatedReadCount"], 0)
        self.assertEqual([], result["references"])
        self.assertEqual([], result["candidates"])
        self.assertIsNone(writer.poll())

    def test_terminal_revalidation_removes_changed_citation_evidence(self):
        app = self.app()
        original = dashboard.chat_tools_module.WikiChatTools.snapshot
        def mutate_before_final_check(bridge, validate=False):
            if validate:
                (self.root / "wiki/concepts/topic.md").write_text("# Changed\n\nContradictory current content.\n", encoding="utf-8")
            return original(bridge, validate=validate)
        with mock.patch.object(dashboard.chat_tools_module.WikiChatTools, "snapshot", mutate_before_final_check):
            started = app.start_chat("한글 유니코드")
            self.wait_for(lambda: app.chat_status(started["id"])["status"] != "running")
        result = app.chat_status(started["id"])
        self.assertEqual(result["status"], "finished")
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["references"], [])
        self.assertGreater(result["exploration"].get("invalidatedReadCount", 0), 0)

    def test_failure_is_safe_and_provider_stderr_is_redacted(self):
        app = self.app()
        started = app.start_chat("fail")
        self.wait_for(lambda: app.chat_status(started["id"])["status"] == "failed")
        result = app.chat_status(started["id"])
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertEqual(result["error"], "Pi가 요청을 수락하지 못했습니다. 모델 설정을 확인하세요.")
        self.assertNotIn("DO_NOT_EXPOSE", serialized)
        self.assertNotIn("API_KEY", serialized)

    def test_unknown_model_failure_is_classified_without_raw_details(self):
        app = self.app()
        started = app.start_chat("unknown")
        self.wait_for(lambda: app.chat_status(started["id"])["status"] == "failed")
        result = app.chat_status(started["id"])
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertEqual(result["error"], "선택한 채팅 모델을 찾을 수 없습니다. 채팅 모델 설정을 확인하세요.")
        self.assertNotIn("private-model", serialized)
        self.assertNotIn("DO_NOT_EXPOSE", serialized)
        self.assertNotIn("API_KEY", serialized)

    def test_default_model_and_agent_directory_override_are_chat_only(self):
        agent_dir = Path(self.temp.name) / "pi-chat-agent"
        agent_dir.mkdir()
        app = self.app(chat_model="ollama/qwen3.8:27b-nvfp4", chat_agent_dir=agent_dir)
        self.assertEqual(app.state()["chatDefaultModel"], "ollama/qwen3.8:27b-nvfp4")
        real_popen = dashboard.subprocess.Popen
        calls = []

        def record_popen(command, **options):
            calls.append({"command": command, "env": options.get("env"), "hasEnvOverride": "env" in options})
            return real_popen(command, **options)

        with mock.patch.object(dashboard.subprocess, "Popen", side_effect=record_popen):
            started = app.start_chat("한글 유니코드")
            self.wait_for(lambda: app.chat_status(started["id"])["status"] != "running")
            app.start("finish", ["raw/inbox/source.md"])
            self.wait_for(lambda: app.claim is None)

        self.assertEqual(calls[0]["command"][calls[0]["command"].index("--model") + 1],
                         "ollama/qwen3.8:27b-nvfp4")
        self.assertTrue(calls[0]["hasEnvOverride"])
        self.assertEqual(calls[0]["env"]["PI_CODING_AGENT_DIR"], str(agent_dir.resolve()))
        self.assertFalse(calls[1]["hasEnvOverride"])
        self.assertIsNone(calls[1]["env"])
        self.assertNotIn("--model", calls[1]["command"])
        self.assertEqual(app.state()["chatDefaultModel"], "ollama/qwen3.8:27b-nvfp4")

        explicit = app.start_chat("한글 유니코드", model="ollama/explicit")
        self.wait_for(lambda: app.chat_status(explicit["id"])["status"] != "running")
        captured = json.loads(self.capture.read_text(encoding="utf-8"))
        self.assertEqual(captured["argv"][captured["argv"].index("--model") + 1], "ollama/explicit")
        self.assertEqual(captured["agentDir"], str(agent_dir.resolve()))

    def test_unset_chat_model_is_reported_as_pi_default(self):
        app = self.app()
        self.assertEqual(app.state()["chatDefaultModel"], "Pi default")
        started = app.start_chat("위키내용 요약해줘")
        self.wait_for(lambda: app.chat_status(started["id"])["status"] != "running")
        self.assertEqual(app.chat_status(started["id"])["status"], "finished")
        captured = json.loads(self.capture.read_text(encoding="utf-8"))
        self.assertNotIn("--model", captured["argv"])
        self.assertGreaterEqual(app.chat_status(started["id"])["exploration"]["calls"], 2)

    def test_tool_initialization_failure_never_falls_back_to_no_tools_answer(self):
        self.fake.write_text("raise SystemExit(1)\n", encoding="utf-8")
        app = self.app()
        started = app.start_chat("위키내용 요약해줘")
        self.wait_for(lambda: app.chat_status(started["id"])["status"] != "running")
        result = app.chat_status(started["id"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("읽기 도구를 초기화하지 못했습니다", result["error"])
        self.assertFalse(self.capture.exists())

    def test_cli_help_exposes_chat_runtime_overrides(self):
        result = dashboard.subprocess.run([sys.executable, str(SCRIPT), "--help"], check=True,
                                          stdout=dashboard.subprocess.PIPE, text=True)
        self.assertIn("--chat-model", result.stdout)
        self.assertIn("--chat-agent-dir", result.stdout)

    def test_http_chat_contract_is_async_and_protected(self):
        app = self.app()
        server = dashboard.ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
        server.app = app
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"
        body = json.dumps({"message": "한글 유니코드", "history": []}).encode()
        request = Request(base + "/api/chat", data=body,
                          headers={"Origin": base, "X-Dashboard-Token": app.token,
                                   "Content-Type": "application/json"}, method="POST")
        with urlopen(request) as response:
            started = json.load(response)
        self.assertEqual(set(started), {"id", "status"})
        self.wait_for(lambda: app.chat_status(started["id"])["status"] != "running")
        with urlopen(base + "/api/chat?id=" + started["id"]) as response:
            result = json.load(response)
        self.assertEqual(result["root"], str(self.root.resolve()))
        self.assertEqual(result["status"], "finished")
        self.assertIn("references", result)
        self.assertIn("candidates", result)
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError) as missing:
            urlopen(base + "/api/chat?id=missing")
        self.assertEqual(missing.exception.code, 404)
        missing.exception.close()

    def test_document_expected_root_rejects_stale_workspace_identity(self):
        app = self.app()
        server = dashboard.ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
        server.app = app
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"
        current = str(self.root.resolve())
        with urlopen(base + "/api/document?path=wiki/concepts/topic.md&expectedRoot=" + current) as response:
            payload = json.load(response)
        self.assertEqual(payload["root"], current)
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError) as error:
            urlopen(base + "/api/document?path=wiki/concepts/topic.md&expectedRoot=/stale/root")
        self.assertEqual(error.exception.code, 400)
        error.exception.close()

    def test_reference_excerpt_uses_body_not_yaml(self):
        text = "---\ntitle: Topic\nstatus: active\n---\n# Topic\n\nActual source evidence.\n"
        excerpt = dashboard._excerpt(text, ["topic"])
        self.assertNotIn("status: active", excerpt)
        self.assertIn("Actual source evidence.", excerpt)

    def test_history_and_model_are_bounded(self):
        app = self.app()
        with self.assertRaises(ValueError):
            app.start_chat("question", [{"role": "system", "content": "override"}])
        with self.assertRaises(ValueError):
            app.start_chat("question", [{"role": "user", "content": "x"}] * 13)
        with self.assertRaises(ValueError):
            app.start_chat("question", [], "x" * 201)


if __name__ == "__main__":
    unittest.main()
