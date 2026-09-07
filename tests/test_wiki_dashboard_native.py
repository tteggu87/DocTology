"""Native session ownership and protocol cases independent of a paid model."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import sys
import subprocess
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_dashboard_test", ROOT / "runtime/wiki_dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)
native = dashboard.native_module


class FakeProcess:
    def __init__(self, pid):
        self.pid, self.code = pid, None
    def poll(self):
        return self.code


class FakeRPC:
    instances = []
    fail_prompt = False
    wrong_resume = False
    command_only = False
    switched = False
    def __init__(self, command, root, *, model, session_file, agent_dir, on_event, on_exit, terminate):
        self.root, self.events, self.exit = root, on_event, on_exit
        self.process = FakeProcess(2_000_000 + len(self.instances))
        self.prompts, self.sent, self.diagnostics = [], [], []
        self.resume = session_file
        if session_file:
            self.file = Path(session_file)
            self.session_id = json.loads(self.file.read_text().splitlines()[0])["id"]
        else:
            self.session_id = "session-" + str(len(self.instances))
            self.file = root / "state/native-test" / (self.session_id + ".jsonl")
            self.file.parent.mkdir(parents=True, exist_ok=True)
            self.file.write_text(json.dumps({"type":"session","id":self.session_id,"cwd":str(root)}) + "\n")
        self.instances.append(self)
    def request(self, name, **kwargs):
        if name == "get_state":
            return {"sessionId":"wrong" if self.switched or self.resume and self.wrong_resume else self.session_id,"sessionFile":str(self.file),"model":{"id":"test-model"},"thinkingLevel":"medium",**({"isStreaming":False} if self.command_only else {})}
        if name == "get_session_stats":
            return {"tokens":{"input":10,"output":2,"cacheRead":0,"cacheWrite":0},"contextUsage":{"tokens":12,"contextWindow":100}}
        if name == "prompt":
            self.prompts.append(kwargs["message"])
            if self.fail_prompt:
                raise native.NativeError("Acceptance is uncertain")
            return {}
        raise AssertionError(name)
    def send(self, body):
        self.sent.append(body)
        if body["type"] == "abort":
            self.events({"type":"agent_settled"})
    def finish(self, text="answer"):
        self.events({"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":text}],"stopReason":"stop"}})
        self.events({"type":"agent_settled"})
    def close(self):
        self.process.code = 0
        self.exit()


class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / "vault"
        for folder in ("raw", "wiki/_meta"):
            (self.root / folder).mkdir(parents=True)
        (self.root / "AGENTS.md").write_text("# Wiki test\n")
        (self.root / "wiki/_meta/index.md").write_text("# Index\n")
        (self.root / "wiki/_meta/log.md").write_text("# Log\n")
        FakeRPC.instances = []
        FakeRPC.fail_prompt = FakeRPC.wrong_resume = FakeRPC.command_only = FakeRPC.switched = False
        self.app = self.make_app()
    def make_app(self):
        app = dashboard.Dashboard(self.root, pi_command=["fake-pi"])
        app.native.rpc_factory = FakeRPC
        self.addCleanup(app.stop_all)
        return app
    def wait(self, predicate):
        end=time.monotonic()+3
        while not predicate():
            if time.monotonic()>end:self.fail("background operation did not settle")
            time.sleep(.01)
    def begin(self, request_id="turn-1", conversation="c1", message="hello", app=None):
        app=app or self.app
        return app.native_action("native-chat",{"expectedRoot":str(self.root),"conversationId":conversation,"requestId":request_id,"message":message})
    def test_settled_turn_keeps_dispatch_barrier_until_old_state_request_exits(self):
        blocked, release = threading.Event(), threading.Event()
        original = FakeRPC.request
        def request(rpc, name, **kwargs):
            if name == "get_state" and rpc.prompts and threading.current_thread().name == "native-pi-start":
                blocked.set()
                release.wait(3)
                raise native.NativeError("late state failure")
            return original(rpc, name, **kwargs)
        with mock.patch.object(FakeRPC, "request", request):
            self.begin()
            self.assertTrue(blocked.wait(2))
            rpc = FakeRPC.instances[-1]
            rpc.finish()
            self.wait(lambda: self.app.native.jobs["turn-1"]["status"] == "finished")
            self.assertTrue(self.app.native.is_busy())
            with self.assertRaises(native.NativeError):
                self.begin("turn-2")
            release.set()
            self.wait(lambda: not self.app.native.is_busy())
        self.begin("turn-2")
        self.wait(lambda: len(FakeRPC.instances) == 2 and bool(FakeRPC.instances[-1].prompts))
        FakeRPC.instances[-1].finish("next answer")
        self.wait(lambda: self.app.native.jobs["turn-2"]["status"] == "finished")
        self.assertIsNone(FakeRPC.instances[-1].process.poll())

    def ready(self):
        self.wait(lambda: bool(FakeRPC.instances and FakeRPC.instances[-1].prompts))
        return FakeRPC.instances[-1]
    def finish(self, request_id="turn-1", text="answer"):
        FakeRPC.instances[-1].finish(text)
        self.wait(lambda:self.app.native_status(request_id)["status"]!="running")
    def close(self):
        summary=self.app.native.summary()
        self.app.native_action("native-close",{"expectedRoot":str(self.root),"conversationId":summary["conversationId"],"generation":summary["generation"]})
        self.wait(lambda:not self.app.native.is_open())

    def test_same_conversation_three_turns_keep_one_process_and_native_history(self):
        for index in range(3):
            self.begin(f"turn-{index}",message=f"question {index}")
            self.wait(lambda: bool(FakeRPC.instances) and len(FakeRPC.instances[0].prompts)==index+1)
            self.finish(f"turn-{index}",f"answer {index}")
        self.assertEqual(len(FakeRPC.instances),1)
        self.assertEqual(FakeRPC.instances[0].prompts,["question 0","question 1","question 2"])
        self.assertIsNone(FakeRPC.instances[0].process.poll())
        self.assertEqual(self.app.native_status("turn-2")["native"]["sessionId"],"session-0")
        self.assertEqual(self.app.native_status("turn-2")["references"],[])

    def test_duplicate_content_is_idempotent_and_conflicting_reuse_is_rejected(self):
        self.begin();rpc=self.ready()
        self.begin()
        self.assertEqual(rpc.prompts,["hello"])
        with self.assertRaises(native.NativeError):self.begin(message="different")
        with self.assertRaises(native.NativeError):self.begin(request_id="other")
        self.finish()
        self.assertEqual(self.begin()["status"],"finished")
        self.assertEqual(len(rpc.prompts),1)

    def test_session_holds_writer_claim_and_root_until_explicit_close(self):
        self.begin();self.ready();self.finish()
        path=self.root/"state/dashboard_jobs/.writer.lock"
        self.assertIsNone(dashboard.workflow.acquire_refresh_claim(path,"other"))
        with self.assertRaisesRegex(ValueError,"Pi 기본 세션"):
            self.app.connect(str(self.root))
        self.close()
        claim=dashboard.workflow.acquire_refresh_claim(path,"other")
        self.assertIsNotNone(claim)
        dashboard.workflow.release_refresh_claim(claim)

    def test_session_resume_is_server_bound_and_late_events_do_not_cross_conversations(self):
        self.begin();old=self.ready();self.finish();session=old.session_id
        self.begin("turn-2","c2");self.wait(lambda:len(FakeRPC.instances)==2 and FakeRPC.instances[-1].prompts)
        old.events({"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"wrong conversation"}]}})
        self.assertEqual(self.app.native_status("turn-2")["answer"],"")
        self.finish("turn-2")
        self.begin("turn-3","c1");self.wait(lambda:len(FakeRPC.instances)==3 and FakeRPC.instances[-1].prompts)
        self.assertEqual(FakeRPC.instances[-1].session_id,session)
        self.assertEqual(FakeRPC.instances[-1].resume,str(old.file))
        with self.assertRaisesRegex(native.NativeError,"세션이 바뀌"):
            self.app.native.close(self.root,"c2","old-generation")
        self.finish("turn-3")

    def test_ui_choices_preserve_native_values_and_reject_stale_replies(self):
        self.begin();rpc=self.ready()
        secret_option="secret=not-for-log"
        rpc.events({"type":"extension_ui_request","id":"ui-1","method":"select","title":"Pick","options":[secret_option,"normal"]})
        status=self.app.native_status("turn-1")
        self.assertNotIn("not-for-log",json.dumps(status))
        self.app.native_action("native-ui",{"expectedRoot":str(self.root),"id":"turn-1","interactionId":"ui-1","optionIndex":0})
        self.assertEqual(rpc.sent[-1]["value"],secret_option)
        with self.assertRaises(native.NativeError):
            self.app.native_action("native-ui",{"expectedRoot":str(self.root),"id":"turn-1","interactionId":"ui-1","optionIndex":0})
        rpc.events({"type":"extension_ui_request","id":"ui-2","method":"custom"})
        self.assertEqual(rpc.sent[-1],{"type":"extension_ui_response","id":"ui-2","cancelled":True})
        self.finish()

    def test_abort_keeps_session_and_next_turn_works(self):
        self.begin();rpc=self.ready()
        self.app.native_action("native-chat-stop",{"expectedRoot":str(self.root),"id":"turn-1"})
        self.wait(lambda:self.app.native_status("turn-1")["status"]=="stopped")
        self.begin("turn-2")
        self.wait(lambda:len(rpc.prompts)==2)
        self.finish("turn-2")
        self.assertEqual(len(FakeRPC.instances),1)

    def test_uncertain_acceptance_closes_before_retry_and_is_not_replayed_on_restart(self):
        FakeRPC.fail_prompt=True
        self.begin();self.wait(lambda:self.app.native_status("turn-1")["status"]=="failed" and not self.app.native.is_open())
        self.assertEqual(len(FakeRPC.instances[0].prompts),1)
        self.assertEqual(self.begin()["status"],"failed")
        self.app.stop_all()
        FakeRPC.fail_prompt=False
        other=self.make_app()
        self.begin(app=other)
        self.wait(lambda:other.native_status("turn-1")["status"]=="failed" and not other.native.is_open())
        self.assertEqual(len(FakeRPC.instances),1)
        self.assertIn("자동",other.native_status("turn-1")["error"])

    def test_surviving_owner_and_wrong_resume_identity_block_new_work(self):
        self.begin();rpc=self.ready();self.finish();self.close()
        registry=self.app.native._path(self.root)
        payload=json.loads(registry.read_text())
        payload["sessions"]["c1"]["pid"]=os.getpid()
        registry.write_text(json.dumps(payload))
        other=self.make_app()
        with self.assertRaises(ValueError):self.begin("other",app=other)
        payload["sessions"]["c1"]["pid"]=None;registry.write_text(json.dumps(payload))
        FakeRPC.wrong_resume=True
        self.begin("wrong",app=other)
        self.wait(lambda:other.native_status("wrong")["status"]=="failed" and not other.native.is_open())
        self.assertEqual(FakeRPC.instances[-1].prompts,[])

    def test_shutdown_during_start_keeps_lease_until_canceled_process_exits(self):
        entered, release = threading.Event(), threading.Event()
        def delayed(*args, **kwargs):
            entered.set();release.wait(3)
            return FakeRPC(*args, **kwargs)
        self.app.native.rpc_factory=delayed
        self.begin();self.assertTrue(entered.wait(1))
        errors=[]
        def shutdown():
            try:self.app.native.shutdown()
            except Exception as exc:errors.append(exc)
        worker=threading.Thread(target=shutdown);worker.start()
        self.wait(lambda:self.app.native.shutting_down)
        self.assertIsNotNone(self.app.native.claim)
        release.set();worker.join(3)
        self.wait(lambda:not self.app.native.is_open())
        self.assertEqual(errors,[])
        self.assertEqual(FakeRPC.instances[0].prompts,[])
        self.assertIsNotNone(FakeRPC.instances[0].process.poll())

    def test_cancelled_start_retains_child_and_lease_when_termination_fails(self):
        entered, release = threading.Event(), threading.Event()
        def delayed(*args, **kwargs):
            entered.set(); release.wait(3)
            rpc = FakeRPC(*args, **kwargs)
            rpc.close = mock.Mock(side_effect=native.NativeError("termination not confirmed"))
            return rpc
        self.app.native.rpc_factory = delayed
        self.begin(); self.assertTrue(entered.wait(1))
        self.app.native.jobs["turn-1"]["stopRequested"] = True
        release.set()
        self.wait(lambda: self.app.native.dispatching is None)
        rpc = FakeRPC.instances[-1]
        self.assertIs(self.app.native.rpc, rpc)
        registry = json.loads((self.root / "state/dashboard_native/registry.json").read_text())
        self.assertEqual(registry["sessions"]["c1"]["pid"], rpc.process.pid)
        self.assertIsNone(rpc.process.poll())
        self.assertIsNotNone(self.app.native.claim)
        self.assertTrue(self.app.native.is_open())
        rpc.close = lambda: FakeRPC.close(rpc)

    def test_success_after_retry_clears_recoverable_error(self):
        self.begin();rpc=self.ready()
        rpc.events({"type":"message_end","message":{"role":"assistant","content":[],"stopReason":"error","errorMessage":"429 retry"}})
        self.finish(text="recovered")
        result=self.app.native_status("turn-1")
        self.assertEqual(result["status"],"finished")
        self.assertNotIn("error",result)

    def test_handled_extension_command_finishes_without_agent_event(self):
        FakeRPC.command_only=True
        self.begin(message="/local-command")
        self.wait(lambda:self.app.native_status("turn-1")["status"]!="running")
        result=self.app.native_status("turn-1")
        self.assertEqual(result["status"],"finished")
        self.assertTrue(result["native"]["commandOnly"])
        self.assertEqual(result["answer"],"")

    def test_multiple_dialogs_are_queued_and_stop_cancels_the_remaining_request(self):
        self.begin();rpc=self.ready()
        for index in (1,2):rpc.events({"type":"extension_ui_request","method":"confirm","id":f"ui-{index}","title":"confirm"})
        self.assertEqual(self.app.native_status("turn-1")["native"]["interaction"]["id"],"ui-1")
        self.app.native.respond(self.root,"turn-1",{"interactionId":"ui-1","confirmed":True})
        self.assertEqual(self.app.native_status("turn-1")["native"]["interaction"]["id"],"ui-2")
        self.app.native.stop(self.root,"turn-1")
        self.wait(lambda:self.app.native_status("turn-1")["status"]=="stopped")
        self.assertIn({"type":"extension_ui_response","id":"ui-2","cancelled":True},rpc.sent)

    def test_old_stop_timer_cannot_close_a_followup(self):
        timers=[]
        class Timer:
            def __init__(self, seconds, callback):timers.append(callback)
            def start(self):pass
        self.begin();rpc=self.ready()
        with mock.patch.object(native.threading,"Timer",Timer):self.app.native.stop(self.root,"turn-1")
        self.wait(lambda:self.app.native_status("turn-1")["status"]=="stopped")
        self.begin("turn-2");self.wait(lambda:len(rpc.prompts)==2)
        timers[0]()
        self.assertIsNone(rpc.process.poll())
        self.finish("turn-2")

    def test_completed_receipt_and_hash_survive_restart_replay(self):
        self.begin();self.ready();self.finish();self.close()
        path=self.app.native._path(self.root)
        before=json.loads(path.read_text())["turns"]["turn-1"]
        other=self.make_app();self.begin(app=other)
        self.wait(lambda:other.native_status("turn-1")["status"]!="running" and not other.native.is_open())
        self.assertEqual(other.native_status("turn-1")["executionStatus"],"finished")
        self.assertEqual(json.loads(path.read_text())["turns"]["turn-1"],before)
        another=self.make_app();self.begin(app=another,message="conflict")
        self.wait(lambda:another.native_status("turn-1")["status"]!="running" and not another.native.is_open())
        self.assertEqual(json.loads(path.read_text())["turns"]["turn-1"],before)

    def test_registry_failure_before_prompt_never_executes_agent(self):
        with mock.patch.object(self.app.native,"_persist",side_effect=OSError("read-only disk")):
            self.begin()
            self.wait(lambda:self.app.native_status("turn-1")["status"]!="running" and not self.app.native.is_open())
        self.assertEqual(FakeRPC.instances,[])

    def test_normal_launch_allows_native_but_cross_root_and_project_requests_are_denied(self):
        self.begin()
        self.ready()
        self.finish()
        with self.assertRaises(ValueError):
            self.app.native_action("native-chat",{"expectedRoot":"wrong","conversationId":"c1","requestId":"x","message":"hello"})
        self.app.mode = "project"
        with self.assertRaises(ValueError):
            self.begin("project-turn")

    def test_rpc_uses_lf_framing_and_keeps_unicode_separators_inside_messages(self):
        script = "import sys,json\nfor line in sys.stdin.buffer:\n q=json.loads(line);print(json.dumps({'type':'response','id':q['id'],'success':True,'data':{'text':'line\\u2028separator'}},ensure_ascii=False),flush=True)\n"
        events=[]
        rpc=native.PiRPC([sys.executable,"-u","-c",script],self.root,model="",session_file=None,agent_dir=None,on_event=events.append,on_exit=lambda:None,terminate=lambda p:p.terminate() if p.poll() is None else None)
        try:
            self.assertEqual(rpc.request("get_state")["text"],"line\u2028separator")
            self.assertEqual(rpc.request("get_messages")["text"],"line\u2028separator")
            self.assertEqual(rpc.diagnostics,[])
        finally:rpc.close()
        self.assertIsNotNone(rpc.process.poll())

    @unittest.skipIf(os.name=="nt","POSIX process-group evidence; Windows requires its own surface")
    def test_close_terminates_owned_child_even_when_it_ignores_term(self):
        script = "import sys,json,subprocess,time\nchild=subprocess.Popen([sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)'])\ntime.sleep(.1)\nfor line in sys.stdin.buffer:\n q=json.loads(line);print(json.dumps({'type':'response','id':q['id'],'success':True,'data':{'pid':child.pid}}),flush=True)\n"
        rpc=native.PiRPC([sys.executable,"-u","-c",script],self.root,model="",session_file=None,agent_dir=None,on_event=lambda event:None,on_exit=lambda:None,terminate=lambda p:p.terminate() if p.poll() is None else None)
        pid=rpc.request("get_state")["pid"]
        rpc.close()
        state=subprocess.run(["ps","-p",str(pid),"-o","stat="],capture_output=True,text=True).stdout.strip()
        self.assertTrue(not state or state.startswith("Z"),state)

    def test_tool_events_are_bounded_and_never_create_verified_citations(self):
        self.begin();rpc=self.ready()
        for index in range(40):
            rpc.events({"type":"tool_execution_start","toolCallId":str(index),"toolName":"bash","args":{"password":"sensitive","command":"echo test"}})
            rpc.events({"type":"tool_execution_end","toolCallId":str(index),"toolName":"bash","result":{"content":[{"type":"text","text":"output"}]},"isError":False})
        result=self.app.native_status("turn-1")
        self.assertEqual(len(result["native"]["tools"]),32)
        self.assertEqual(result["native"]["toolCalls"],40)
        self.assertNotIn("sensitive",json.dumps(result))
        self.finish(text="native answer [1]")
        self.assertEqual(self.app.native_status("turn-1")["references"],[])


if __name__=='__main__':unittest.main()
