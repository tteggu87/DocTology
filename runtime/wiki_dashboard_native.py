"""Opt-in native Pi RPC sessions. Pi owns history and tools; Studio owns routing."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import secrets
import shutil
import signal
import subprocess
import threading
import time

from wiki_dashboard_native_citations import NativeCitations, CITATION_INSTRUCTION


class NativeError(ValueError):
    pass


def display_text(value, limit=3000):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = re.sub(r"(?i)\b(api[_-]?key|access[_-]?token|password|secret|authorization)\s*[\"']?\s*[:=]\s*[\"']?[^\s,\"'}]+", r"\1=[REDACTED]", text)
    text = re.sub(r"(?i)\bBearer\s+\S+|\bsk-[A-Za-z0-9_-]{20,}", "[REDACTED]", text)
    return text[:limit]


def text_blocks(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(item.get("text", "") for item in value if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str))
    return ""


class PiRPC:
    """One native CLI process with strict LF framing and correlated commands."""
    MAX_FRAME = 8 * 1024 * 1024

    def __init__(self, command, root, *, model="", session_file=None, agent_dir=None, on_event, on_exit, terminate):
        command = list(command)
        if os.name == "nt" and Path(command[0]).suffix.lower() in {".cmd", ".bat"}:
            cli = Path(command[0]).parent / "node_modules/@earendil-works/pi-coding-agent/dist/cli.js"
            node = shutil.which("node")
            if not node or not cli.is_file():
                raise NativeError("Windows의 Pi Node 실행 파일을 찾지 못했습니다. npm 전역 Pi 설치를 확인하세요.")
            command = [node, str(cli), *command[1:]]
        self.command = [*command, "--mode", "rpc", "--append-system-prompt", CITATION_INSTRUCTION]
        if session_file:
            self.command.extend(["--session", str(session_file)])
        if model:
            self.command.extend(["--model", model])
        environment = os.environ.copy()
        if agent_dir:
            environment["PI_CODING_AGENT_DIR"] = str(agent_dir)
        self.process = subprocess.Popen(self.command, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, env=environment, start_new_session=os.name != "nt")
        self.on_event, self.on_exit, self.terminate = on_event, on_exit, terminate
        self.lock, self.write_lock = threading.RLock(), threading.Lock()
        self.pending = {}
        self.closed = False
        self.reader_dead = threading.Event()
        self.cleanup_done = False
        self.close_lock = threading.Lock()
        self.diagnostics = []
        self.reader = threading.Thread(target=self._read, name="native-pi-rpc", daemon=True)
        self.reader.start()
        threading.Thread(target=self._stderr, name="native-pi-stderr", daemon=True).start()

    def send(self, body):
        data = (json.dumps(body, ensure_ascii=False) + "\n").encode("utf-8")
        with self.write_lock:
            if self.reader_dead.is_set() or self.process.poll() is not None:
                raise NativeError("Pi 세션이 종료되었습니다. 새 요청 전에 세션 상태를 확인하세요.")
            try:
                self.process.stdin.write(data)
                self.process.stdin.flush()
            except (OSError, ValueError) as exc:
                raise NativeError("Pi 요청 전달을 확인하지 못했습니다. 자동 재전송하지 않습니다.") from exc

    def request(self, command, *, timeout=10, pause_timeout=None, **arguments):
        request_id = "rpc-" + secrets.token_hex(8)
        response = queue.Queue(maxsize=1)
        with self.lock:
            self.pending[request_id] = response
        try:
            self.send({"id": request_id, "type": command, **arguments})
            remaining = timeout
            while True:
                started = time.monotonic()
                try:
                    value = response.get(timeout=min(.25, max(.01, remaining)))
                    break
                except queue.Empty:
                    if not pause_timeout or not pause_timeout():
                        remaining -= time.monotonic() - started
                    if remaining <= 0:
                        raise NativeError(f"Pi {command} 응답 확인 시간이 지났습니다. 요청을 자동 재전송하지 않습니다.") from None
            if not value.get("success"):
                raise NativeError(display_text(value.get("error", "Pi 요청을 처리하지 못했습니다."), 1000))
            return value.get("data", {})
        finally:
            with self.lock:
                self.pending.pop(request_id, None)

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(self.MAX_FRAME + 1)
                if not line:
                    break
                if len(line) > self.MAX_FRAME:
                    while line and not line.endswith(b"\n"):
                        line = self.process.stdout.readline(self.MAX_FRAME + 1)
                    self.on_event({"type": "studio_notice", "message": "큰 Pi 이벤트는 화면 표시에서 생략했습니다. 원본은 Pi 세션에 남습니다."})
                    continue
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeError):
                    self.diagnostics = (self.diagnostics + ["Pi가 JSONL이 아닌 출력을 보냈습니다."])[-8:]
                    continue
                if not isinstance(event, dict):
                    continue
                if event.get("type") == "response":
                    with self.lock:
                        target = self.pending.get(event.get("id"))
                    if target is not None:
                        try:
                            target.put_nowait(event)
                        except queue.Full:
                            pass
                else:
                    self.on_event(event)
        except (OSError, ValueError):
            pass
        finally:
            self.reader_dead.set()
            with self.lock:
                for target in self.pending.values():
                    try:
                        target.put_nowait({"success": False, "error": "Pi 연결이 종료되었습니다. 접수된 요청을 자동 재전송하지 않습니다."})
                    except queue.Full:
                        pass
            self.on_exit()

    def _stderr(self):
        try:
            for raw in iter(lambda: self.process.stderr.readline(8193), b""):
                self.diagnostics = (self.diagnostics + [display_text(raw.decode("utf-8", errors="replace"), 1000)])[-8:]
        except (OSError, ValueError):
            pass

    def close(self):
        with self.close_lock:
            if self.cleanup_done:
                return
            self.closed = True
            if os.name == "nt" and self.process.poll() is None:
                subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"], capture_output=True, timeout=8)
            self.terminate(self.process)
            try:
                self.process.wait(timeout=6)
            except subprocess.TimeoutExpired:
                raise NativeError("Pi 프로세스 종료를 확인하지 못했습니다. 쓰기 잠금을 유지합니다.") from None
            if os.name != "nt":
                # A child can ignore SIGTERM after the Pi parent has exited.
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if self.reader is not threading.current_thread():
                self.reader.join(timeout=2)
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass
            self.cleanup_done = True


class NativeSessions:
    """One live session; bounded turn projections and a derived resume registry."""
    MAX_JOBS = 32

    def __init__(self, command, *, workflow, inside, terminate, process_alive, agent_dir=None, rpc_factory=PiRPC):
        self.command, self.workflow, self.inside = command, workflow, inside
        self.terminate, self.process_alive, self.agent_dir = terminate, process_alive, agent_dir
        self.rpc_factory = rpc_factory
        self.lock = threading.RLock()
        self.jobs, self.active = {}, None
        self.dispatching = None
        self.rpc = None
        self.citations = None
        self.root = None
        self.conversation = None
        self.generation = None
        self.model_request = ""
        self.info = {}
        self.claim = None
        self.closing = False
        self.registry = None
        self.registry_root = None
        self.shutting_down = False
        self.starting_rpc = False
        self.start_done = threading.Event()
        self.start_done.set()

    def is_open(self):
        with self.lock:
            return self.rpc is not None or self.active is not None or self.claim is not None or self.closing

    def is_busy(self):
        with self.lock:
            return self.active is not None or self.dispatching is not None or self.closing

    def summary(self):
        with self.lock:
            return {"open": self.is_open(), "busy": self.is_busy(), "closing": self.closing,
                    "root": str(self.root) if self.root else None, "conversationId": self.conversation,
                    "generation": self.generation, **copy.deepcopy(self.info)}

    def _path(self, root):
        return self.inside(root, "state/dashboard_native/registry.json")

    def _load(self, root):
        path = self._path(root)
        if not path.exists():
            return {"version": 1, "root": str(root), "sessions": {}, "turns": {}}
        if path.is_symlink() or path.stat().st_size > 2_000_000:
            raise NativeError("Pi 세션 연결 기록을 안전하게 읽을 수 없습니다.")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1 or data.get("root") != str(root) or not isinstance(data.get("sessions"), dict) or not isinstance(data.get("turns"), dict):
            raise NativeError("Pi 세션 연결 기록이 현재 위키와 맞지 않습니다.")
        return data

    def _persist(self):
        if self.registry is not None:
            path = self._path(self.registry_root)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.workflow.write_json(path, self.registry)

    def has_survivor(self, root):
        try:
            data = self._load(root)
            return any(isinstance(row, dict) and row.get("pid") and self.process_alive(row["pid"])
                       for row in data["sessions"].values())
        except (OSError, ValueError, TypeError):
            return True  # Corrupt ownership is not permission to start another writer.

    @staticmethod
    def _identifier(value, label):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
            raise NativeError(f"{label} 식별자가 올바르지 않습니다.")
        return value

    def begin(self, root, conversation, request_id, message, model=""):
        root = Path(root).resolve()
        conversation = self._identifier(conversation, "대화")
        request_id = self._identifier(request_id, "질문")
        if not isinstance(message, str) or not 1 <= len(message.strip()) <= 8000 or not isinstance(model, str) or len(model) > 200:
            raise NativeError("질문 또는 모델 입력이 올바르지 않습니다.")
        fingerprint = hashlib.sha256(json.dumps([str(root), conversation, "native", message, model], ensure_ascii=False).encode()).hexdigest()
        with self.lock:
            if self.shutting_down:
                raise NativeError("서버가 종료 중입니다. 새 Pi 요청을 받지 않습니다.")
            if self.info.get("unusable"):
                raise NativeError("Pi 세션 상태를 확인하지 못했습니다. 세션을 닫은 뒤 다시 연결하세요.")
            previous = self.jobs.get(request_id)
            if previous:
                if previous["inputHash"] != fingerprint:
                    raise NativeError("같은 질문 식별자로 다른 내용을 실행할 수 없습니다.")
                return self._public(previous)
            if self.active is not None or self.dispatching is not None or self.closing:
                raise NativeError("현재 Pi 질문 또는 세션 종료가 끝난 뒤 요청하세요.")
            if self.root is not None and self.root != root and self.is_open():
                raise NativeError("기존 Pi 세션을 닫은 뒤 위키를 바꿔 주세요.")
            while len(self.jobs) >= self.MAX_JOBS:
                self.jobs.pop(next(iter(self.jobs)))
            job = {"id": request_id, "root": str(root), "conversationId": conversation, "inputHash": fingerprint,
                   "status": "running", "startedAt": time.time(), "answer": "", "references": [], "candidates": [],
                   "progress": {"phase": "starting", "lastSignalAt": time.time()},
                   "native": {"tools": [], "interaction": None, "notice": "Pi 기본 세션 준비 중", "stats": None},
                   "generation": None, "stopRequested": False, "errorSeen": False}
            self.jobs[request_id], self.active = job, request_id
            self.dispatching = request_id
        threading.Thread(target=self._run, args=(job, root, conversation, message, model), name="native-pi-start", daemon=True).start()
        return self._public(job)

    def _resume_path(self, row, root):
        path = row.get("sessionFile")
        if not path:
            raise NativeError("이 대화의 Pi 세션 파일이 없습니다. 새 대화를 시작해 주세요.")
        path = Path(path)
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise NativeError("이 대화의 Pi 세션 파일을 찾을 수 없습니다. 자동으로 새 문맥을 만들지 않습니다.")
        with path.open("rb") as handle:
            header = json.loads(handle.readline(65537))
        if header.get("type") != "session" or header.get("id") != row.get("sessionId") or Path(header.get("cwd", "")).resolve() != root:
            raise NativeError("Pi 세션의 위키 또는 식별자가 연결 기록과 다릅니다.")
        return str(path)

    def _run(self, job, root, conversation, message, model):
        try:
            with self.lock:
                if self.shutting_down:
                    self._finish(job, "stopped")
                    return
                reuse = self.rpc is not None and self.conversation == conversation and self.root == root and self.model_request == model and self.rpc.process.poll() is None
            if not reuse:
                self._close_process()
                claim_path = self.inside(root, "state/dashboard_jobs/.writer.lock")
                claim_path.parent.mkdir(parents=True, exist_ok=True)
                claim = self.workflow.acquire_refresh_claim(claim_path, "native-" + secrets.token_hex(8))
                if claim is None:
                    raise NativeError("다른 위키 작업이 실행 중입니다. 끝난 뒤 Pi 기본 세션을 여세요.")
                with self.lock:
                    self.claim = claim
                    registry = self._load(root)
                    if any(isinstance(row, dict) and row.get("pid") and self.process_alive(row["pid"]) for row in registry["sessions"].values()):
                        raise NativeError("이전 Pi 프로세스가 남아 있습니다. 해당 세션 종료를 확인한 뒤 다시 연결하세요.")
                    self.registry, self.registry_root = registry, root
                    prior = registry["turns"].get(job["id"])
                    if prior:
                        self._recover_prior(job, prior)
                        self.workflow.release_refresh_claim(self.claim)
                        self.claim = None
                        return
                    row = registry["sessions"].get(conversation)
                    resume = self._resume_path(row, root) if row else None
                    self.root, self.conversation, self.model_request = root, conversation, model
                    self.citations = NativeCitations(root)
                    self.generation = secrets.token_hex(12)
                    generation = self.generation
                    job["generation"] = generation
                    self._reserve_record(job)  # No native prompt may precede durable request identity.
                with self.lock:
                    if self.shutting_down or job["stopRequested"]:
                        self._finish(job, "stopped")
                        self.workflow.release_refresh_claim(self.claim)
                        self.claim = None
                        return
                    self.starting_rpc = True
                    self.start_done.clear()
                rpc = None
                try:
                    rpc = self.rpc_factory(self.command, root, model=model, session_file=resume, agent_dir=self.agent_dir,
                                           on_event=lambda event: self._event(generation, event),
                                           on_exit=lambda: self._exited(generation), terminate=self.terminate)
                    with self.lock:
                        cancelled_start = self.shutting_down or job["stopRequested"] or self.generation != generation
                        self.rpc = rpc  # Retain ownership even if cancellation cleanup fails.
                        self.registry["sessions"][conversation] = {**(row or {}), "pid": rpc.process.pid, "ownerPid": os.getpid()}
                        self._persist()
                    if cancelled_start:
                        rpc.close()
                        raise NativeError("Pi 시작 요청이 취소되었습니다. 새 프로세스를 종료했습니다.")
                finally:
                    with self.lock:
                        self.starting_rpc = False
                        self.start_done.set()
                info = rpc.request("get_state", timeout=30, pause_timeout=lambda:self._waiting_for_user(job))
                if not isinstance(info, dict) or not info.get("sessionId") or not info.get("sessionFile"):
                    raise NativeError("Pi 기본 세션 정보를 확인하지 못했습니다.")
                if row and (info["sessionId"] != row["sessionId"] or Path(info["sessionFile"]).resolve() != Path(resume).resolve()):
                    raise NativeError("요청한 Pi 세션 대신 다른 세션이 열렸습니다. 질문을 전송하지 않았습니다.")
                with self.lock:
                    self.info = {"sessionId": info["sessionId"], "model": (info.get("model") or {}).get("id"), "thinkingLevel": info.get("thinkingLevel")}
                    self.registry["sessions"][conversation] = {**self.info, "sessionFile": info["sessionFile"], "pid": rpc.process.pid, "ownerPid": os.getpid()}
                    self._persist()
            else:
                with self.lock:
                    job["generation"] = self.generation
                    prior = self.registry["turns"].get(job["id"])
                    if prior:
                        self._recover_prior(job, prior)
                        return
                    self._reserve_record(job)
            observed = self.rpc.request("get_state", timeout=10)
            self._check_identity(observed)
            if observed.get("isStreaming") or observed.get("isCompacting") or observed.get("pendingMessageCount", 0):
                raise NativeError("Pi 세션의 이전 작업이 아직 끝나지 않았습니다. 새 질문을 전송하지 않았습니다.")
            with self.lock:
                if job["stopRequested"]:
                    self._finish(job, "stopped")
                    return
                job["native"].update(self.info)
                job["native"]["notice"] = ""
            self.rpc.request("prompt", timeout=30, pause_timeout=lambda:self._waiting_for_user(job), message=message)
            observed = self.rpc.request("get_state", timeout=10)
            self._check_identity(observed)
            with self.lock:
                if job["status"] == "running":
                    job["progress"] = {"phase": "waiting", "lastSignalAt": time.time()}
                    handled = (not job.get("agentStarted") and not observed.get("isStreaming", True)
                               and not observed.get("isCompacting", False) and not observed.get("pendingMessageCount", 0))
                    if handled:
                        job["native"]["commandOnly"] = True
                        job["native"]["notice"] = job["native"].get("notice") or "Pi 명령이 처리되었습니다. 모델 답변을 생성한 요청은 아닙니다."
                        self._finish(job, "finished")
        except Exception as exc:
            with self.lock:
                self.closing = True
                if job["status"] == "running":
                    self._finish(job, "stopped" if job["stopRequested"] or self.shutting_down else "failed", str(exc))
            # An uncertain prompt cannot leave an untracked streaming process.
            try:
                self._close_process()
            except Exception as cleanup:
                with self.lock:
                    job["error"] = display_text(str(exc) + " · " + str(cleanup), 1800)
            finally:
                with self.lock:
                    self.closing = False

        finally:
            with self.lock:
                if self.dispatching == job["id"]:
                    self.dispatching = None

    def _waiting_for_user(self, job):
        with self.lock:
            return bool(job["native"].get("interaction")) and not job["stopRequested"] and not self.shutting_down

    def _reserve_record(self, job):
        if job["id"] not in self.registry["turns"] and len(self.registry["turns"]) >= 1024:
            raise NativeError("실험 모드의 요청 기록 한도에 도달했습니다. 기존 Pi 세션은 보존하며 새 실행은 시작하지 않습니다.")
        self.registry["turns"][job["id"]] = self._record(job)
        self._persist()

    def _record(self, job):
        return {key: job[key] for key in ("id", "root", "conversationId", "inputHash", "status", "startedAt")}

    def _check_identity(self, observed):
        with self.lock:
            row = (self.registry or {}).get("sessions", {}).get(self.conversation, {})
            if (not isinstance(observed, dict) or observed.get("sessionId") != row.get("sessionId")
                    or str(Path(observed.get("sessionFile", "")).resolve()) != str(Path(row.get("sessionFile", "")).resolve())):
                raise NativeError("Pi에서 세션이 변경되었습니다. 이 실험 모드에서는 별도 세션 전환 명령을 지원하지 않습니다. 세션을 닫고 새 대화로 연결하세요.")

    def _recover_prior(self, job, prior):
        if prior.get("inputHash") != job["inputHash"]:
            raise NativeError("저장된 질문 식별자가 다른 실행을 가리킵니다.")
        execution = "uncertain" if prior.get("status") == "running" else prior.get("status", "unknown")
        job.update(status="failed", executionStatus=execution, resultAvailable=False, endedAt=time.time(),
                   error=f"이미 접수한 질문입니다(이전 실행: {execution}). Pi 세션에 보관된 결과를 확인하세요. 자동 재실행하지 않았습니다.")
        job["native"]["notice"] = "원래 실행 상태는 유지했습니다. 현재 화면에서 이전 결과를 복원하지 못했습니다."
        if self.active == job["id"]:
            self.active = None

    def _finish(self, job, status, error=None):
        job["status"], job["endedAt"] = status, time.time()
        job["progress"] = {"phase": "finished" if status == "finished" else "stopped" if status == "stopped" else "failed", "lastSignalAt": time.time()}
        job["native"]["interaction"] = None
        job.pop("_interactions", None)
        if error:
            job["error"] = display_text(error, 1800)
        if self.active == job["id"]:
            self.active = None
        previous = (self.registry or {}).get("turns", {}).get(job["id"])
        if previous and previous.get("inputHash") == job["inputHash"] and self.registry_root == Path(job["root"]):
            self.registry["turns"][job["id"]] = self._record(job)
            try:
                self._persist()
            except (OSError, ValueError) as exc:
                job["status"] = "failed"
                job["error"] = "Pi 실행 기록 저장을 확인하지 못했습니다. 자동 재실행하지 않습니다. " + display_text(str(exc), 500)

    def _event(self, generation, event):
        kind = event.get("type")
        with self.lock:
            job = self.jobs.get(self.active)
            if not job or job.get("generation") != generation or self.generation != generation or job["status"] != "running":
                return
            now = time.time()
            job["progress"]["lastSignalAt"] = now
            if kind in {"agent_start", "turn_start", "auto_compaction_start"}:
                job["agentStarted"] = True
                job["progress"]["phase"] = "model"
            elif kind == "message_start" and (event.get("message") or {}).get("role") == "assistant":
                job["answer"] = ""
            elif kind == "message_update":
                update = event.get("assistantMessageEvent") or {}
                if update.get("type") == "text_delta" and isinstance(update.get("delta"), str):
                    combined = job["answer"] + update["delta"]
                    job["answer"] = combined[:32000]
                    job["native"]["truncated"] = len(combined) > 32000 or job["native"].get("truncated", False)
                    job["progress"]["phase"] = "answer"
            elif kind == "message_end":
                message = event.get("message") or {}
                if message.get("role") == "assistant":
                    text = text_blocks(message.get("content"))
                    job["answer"] = text[:32000]
                    job["native"]["truncated"] = len(text) > 32000
                    job["errorSeen"] = message.get("stopReason") == "error"
                    if job["errorSeen"]:
                        job["error"] = display_text(message.get("errorMessage", "Pi 모델 응답이 실패했습니다."), 1800)
                    else:
                        job.pop("error", None)
            elif kind in {"tool_execution_start", "tool_execution_update", "tool_execution_end"}:
                tool_id = str(event.get("toolCallId", ""))[:200]
                tools = job["native"]["tools"]
                item = next((row for row in tools if row["id"] == tool_id), None)
                if item is None:
                    known = job.setdefault("_tool_ids", set())
                    known.add(tool_id)
                    job["native"]["toolCalls"] = len(known)
                    item = {"id": tool_id, "tool": display_text(event.get("toolName", "tool"), 100), "status": "running", "args": "", "output": ""}
                    tools.append(item)
                    del tools[:-32]
                if "args" in event:
                    item["args"] = display_text(event["args"], 1000)
                result = event.get("result") or event.get("partialResult") or {}
                item["output"] = display_text(text_blocks(result.get("content")), 3000)
                if kind == "tool_execution_end":
                    item["status"] = "error" if event.get("isError") else "ok"
                job["progress"]["phase"] = "tool"
            elif kind == "extension_ui_request":
                method = event.get("method")
                if method in {"confirm", "select", "input", "editor"}:
                    options = event.get("options") or []
                    initial = event.get("prefill", event.get("initialValue", "")) or ""
                    if not isinstance(options, list) or any(not isinstance(option, str) for option in options) or len(options)>40 or not isinstance(initial, str) or len(initial)>8000:
                        job["native"]["notice"] = "이 입력 요청은 표시 한도를 넘어 취소했습니다. Pi 터미널에서 확인하세요."
                        if self.rpc:
                            self.rpc.send({"type":"extension_ui_response", "id":event.get("id"), "cancelled":True})
                        return
                    interactions = job.setdefault("_interactions", [])
                    if len(interactions) >= 16:
                        if self.rpc:
                            self.rpc.send({"type":"extension_ui_response", "id":event.get("id"), "cancelled":True})
                        job["native"]["notice"] = "동시 입력 요청 한도를 넘은 요청은 취소했습니다."
                        return
                    public = {"id": str(event.get("id", ""))[:200], "method": method,
                        "title": display_text(event.get("title", "Pi 입력 요청"), 1000),
                        "message": display_text(event.get("message", ""), 2000),
                        "options": [display_text(option, 500) for option in options],
                        "initialValue": initial}
                    interactions.append({"public":public, "options":options})
                    job["native"]["interaction"] = interactions[0]["public"]
                elif method in {"notify", "setStatus", "setTitle", "setWidget", "set_editor_text"}:
                    notice = event.get("message", event.get("text"))
                    if isinstance(notice, str) and notice:
                        job["native"]["notice"] = display_text(notice, 1000)
                else:
                    job["native"]["notice"] = "이 Pi 화면 요청은 아직 지원하지 않아 취소했습니다: " + display_text(method, 80)
                    if event.get("id") and self.rpc:
                        self.rpc.send({"type": "extension_ui_response", "id": event["id"], "cancelled": True})
            elif kind == "studio_notice":
                job["native"]["notice"] = event["message"]
            elif kind == "agent_settled":
                threading.Thread(target=self._settled, args=(generation, job["id"]), name="native-pi-settled", daemon=True).start()

    def _settled(self, generation, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or self.active != job_id or self.generation != generation or job["status"] != "running":
                return
            rpc = self.rpc
            citations = self.citations
        stats = None
        try:
            if rpc:
                self._check_identity(rpc.request("get_state", timeout=3))
                observed = rpc.request("get_session_stats", timeout=3)
                if isinstance(observed, dict):
                    stats = {"tokens": observed.get("tokens"), "contextUsage": observed.get("contextUsage")}
        except NativeError as exc:
            if "세션이 변경" in str(exc):
                with self.lock:
                    if self.active != job_id or self.generation != generation or self.rpc is not rpc or job["status"] != "running":
                        return
                    self.closing = True
                    self.info["unusable"] = True
                    job = self.jobs.get(job_id)
                    if job and job["status"] == "running":
                        self._finish(job, "failed", str(exc))
                try:
                    self._close_process()
                except Exception:
                    pass
                finally:
                    with self.lock:
                        self.closing = False
                return
        except Exception:
            pass
        references, read_documents, citation_notice = [], [], ""
        if rpc and citations and not job.get("stopRequested") and not job.get("errorSeen"):
            try:
                citations.update(rpc.request("get_entries", timeout=3, **citations.request_arguments()))
                references, read_documents = citations.project(job["answer"])
                for reference in references:
                    reference["excerpt"] = display_text(reference["excerpt"], 1000)
                    reference["title"] = display_text(reference["title"], 500)
            except Exception:
                citation_notice = "Pi 읽기 기록과 출처를 대조하지 못했습니다. 답변은 유지하며 인용 연결은 생략했습니다."
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or self.generation != generation or job.get("generation") != generation or job["status"] != "running":
                return
            job["references"] = references
            job["native"]["readDocuments"] = read_documents
            job["native"]["citationNotice"] = citation_notice
            job["native"]["stats"] = stats
            self.info["stats"] = stats
            status = "stopped" if job["stopRequested"] else "failed" if job["errorSeen"] or not job["answer"].strip() else "finished"
            self._finish(job, status, job.get("error") if status == "failed" else None)

    def _exited(self, generation):
        with self.lock:
            if self.generation != generation:
                return
            self.info["unusable"] = True
            self.info["error"] = "Pi 연결이 종료되었습니다. 세션을 닫고 다시 이어가세요."
            job = self.jobs.get(self.active)
            if job and job.get("generation") == generation and job["status"] == "running":
                self._finish(job, "stopped" if job["stopRequested"] else "failed", "Pi 연결이 종료되었습니다. 이전 실행을 자동 재전송하지 않습니다.")

    def _public(self, job):
        with self.lock:
            return copy.deepcopy({key: value for key, value in job.items() if key not in {"inputHash", "stopRequested", "errorSeen", "generation"} and not key.startswith("_")} | {"processRunning": bool(self.rpc and self.rpc.process.poll() is None)})

    def status(self, root, request_id):
        with self.lock:
            job = self.jobs.get(request_id)
            if job and job["root"] == str(root):
                return self._public(job)
        prior = self._load(root)["turns"].get(request_id)
        if prior and prior.get("root") == str(root):
            return {"id": request_id, "root": str(root), "status": "failed", "executionStatus": "uncertain" if prior.get("status") == "running" else prior.get("status", "unknown"), "resultAvailable":False, "answer": "", "native": {"tools": [], "notice":"원래 실행 상태는 유지하며 이전 결과는 Pi 세션에 보관됩니다."},
                    "error": "이전 서버에서 접수한 질문입니다. 현재 화면에서 결과를 복원하지 못했습니다. 자동 재실행하지 않습니다."}
        raise NativeError("이 위키의 Pi 질문 기록을 찾을 수 없습니다.")

    def stop(self, root, request_id):
        with self.lock:
            job = self.jobs.get(request_id)
            if not job or job["root"] != str(root):
                raise NativeError("현재 위키의 질문이 아닙니다.")
            if job["status"] != "running":
                return {"id": request_id, "status": job["status"]}
            job["stopRequested"] = True
            rpc, generation = self.rpc, self.generation
            dialogs = [row["public"]["id"] for row in job.pop("_interactions", [])]
            job["native"]["interaction"] = None
        if rpc:
            for dialog in dialogs:
                rpc.send({"type":"extension_ui_response", "id":dialog, "cancelled":True})
            rpc.send({"type": "abort"})
            def force():
                with self.lock:
                    if self.active != request_id or self.generation != generation:
                        return
                    self.closing = True
                try:
                    self._close_process()
                finally:
                    with self.lock:
                        self.closing = False
            timer = threading.Timer(5, force)
            timer.daemon = True
            timer.start()
        return {"id": request_id, "status": "stopping"}

    def respond(self, root, request_id, body):
        with self.lock:
            job = self.jobs.get(request_id)
            if not job or self.active != request_id or job["root"] != str(root) or job.get("generation") != self.generation:
                raise NativeError("이 입력 요청은 현재 Pi 질문에 속하지 않습니다.")
            interaction = job["native"].get("interaction")
            if not interaction or interaction["id"] != body.get("interactionId"):
                raise NativeError("이미 끝났거나 다른 Pi 입력 요청입니다.")
            cancelled = body.get("cancelled", False)
            if not isinstance(cancelled, bool):
                raise NativeError("취소 값이 올바르지 않습니다.")
            response = {"type": "extension_ui_response", "id": interaction["id"], "cancelled": cancelled}
            if not cancelled:
                if interaction["method"] == "confirm":
                    if not isinstance(body.get("confirmed"), bool):
                        raise NativeError("확인 또는 거절을 선택하세요.")
                    response["confirmed"] = body["confirmed"]
                elif interaction["method"] == "select":
                    index = body.get("optionIndex")
                    options = job.get("_interactions", [{}])[0].get("options", [])
                    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(options):
                        raise NativeError("Pi 선택 값을 확인하세요.")
                    response["value"] = options[index]
                else:
                    value = body.get("value")
                    if not isinstance(value, str) or len(value) > 8000:
                        raise NativeError("Pi 입력 값이 올바르지 않습니다.")
                    response["value"] = value
            self.rpc.send(response)
            queue_ = job.get("_interactions", [])
            if queue_:
                queue_.pop(0)
            job["native"]["interaction"] = queue_[0]["public"] if queue_ else None
            return {"ok": True}

    def close(self, root, conversation=None, generation=None):
        with self.lock:
            if self.is_open() and (conversation != self.conversation or generation != self.generation):
                raise NativeError("Pi 세션이 바뀌었습니다. 현재 세션을 확인한 뒤 닫으세요.")
            if self.root is not None and self.root != root:
                raise NativeError("현재 위키의 Pi 세션이 아닙니다.")
            if self.active is not None or self.dispatching is not None:
                raise NativeError("응답을 중단하거나 완료한 뒤 세션을 닫으세요.")
            if self.closing:
                return {"status": "closing"}
            self.closing = True
        def run():
            try:
                self._close_process()
            except Exception as exc:
                with self.lock:
                    self.info["error"] = display_text(str(exc), 1000)
            finally:
                with self.lock:
                    self.closing = False
        threading.Thread(target=run, name="native-pi-close", daemon=True).start()
        return {"status": "closing"}

    def _close_process(self):
        with self.lock:
            if self.starting_rpc:
                raise NativeError("Pi 프로세스가 시작 중입니다. 종료 확인 전까지 쓰기 잠금을 유지합니다.")
            rpc, generation = self.rpc, self.generation
        if rpc:
            rpc.close()
        with self.lock:
            if self.rpc is not rpc or self.generation != generation:
                return
            if self.registry is not None and self.conversation in self.registry["sessions"]:
                self.registry["sessions"][self.conversation]["pid"] = None
                self._persist()
            self.rpc = None
            self.info = {}
            if self.claim is not None:
                self.workflow.release_refresh_claim(self.claim)
                self.claim = None

    def shutdown(self):
        with self.lock:
            self.shutting_down = True
            if self.active in self.jobs:
                self.jobs[self.active]["stopRequested"] = True
        if not self.start_done.wait(6):
            raise NativeError("Pi 시작 종료를 기다리는 중입니다. 쓰기 잠금을 유지합니다.")
        self._close_process()
