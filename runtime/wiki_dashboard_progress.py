"""Bounded, in-memory progress for one cancellable read operation."""
from __future__ import annotations

import copy
import secrets
import threading
import time


class ReadCancelled(ValueError):
    pass


class ReadProgress:
    def __init__(self, root, *, timeout=300, job_id=None):
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.timeout = timeout
        self.started = time.monotonic()
        self.thread = None
        self.record = {"id": job_id or secrets.token_hex(12), "root": str(root), "status": "running",
                       "stage": "queued", "path": "", "current": None, "total": None,
                       "startedAt": time.time(), "lastActivityAt": time.time(), "events": []}

    def check(self):
        if time.monotonic() - self.started > self.timeout:
            self.cancelled.set()
            raise ReadCancelled("읽기 제한 시간이 지났습니다. 마지막 파일과 드라이브 상태를 확인하세요.")
        if self.cancelled.is_set():
            raise ReadCancelled("연결을 취소했습니다. 이전 위키는 유지됩니다.")

    def update(self, stage, *, path="", current=None, total=None):
        with self.lock:
            self.check()
            now = time.time()
            previous = self.record
            append = (stage != previous["stage"] or not previous["events"] or now-previous["events"][-1]["time"] >= 1
                      or (total is not None and current == total and previous.get("current") != current))
            previous.update(stage=stage, path=str(path)[:4096], current=current, total=total, lastActivityAt=now)
            if append:
                previous["events"] = (previous["events"] + [{"time":now, "stage":stage, "path":str(path)[:4096],
                                                            "current":current, "total":total}])[-60:]

    def finish(self, status="ready", *, error=None, result=None):
        with self.lock:
            if self.record["status"] in {"ready", "failed", "cancelled"}:
                return
            self.record.update(status=status, endedAt=time.time())
            if error:
                self.record["error"] = str(error)[:2000]
            if result is not None:
                self.record["result"] = result

    def commit(self, action):
        """Linearize cancellation against a short, I/O-free publication."""
        with self.lock:
            self.check()
            result = action()
            self.finish(result=result)
            return result

    def cancel(self):
        with self.lock:
            if self.record["status"] == "running":
                self.cancelled.set()
                self.record["status"] = "cancelling"
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            result = copy.deepcopy(self.record)
            now = time.time()
            result["elapsedSeconds"] = round(max(0, result.get("endedAt", now)-result["startedAt"]), 1)
            result["quietSeconds"] = round(max(0, now-result["lastActivityAt"]), 1)
            result["stalled"] = result["status"] in {"running", "cancelling"} and result["quietSeconds"] >= 15
            return result

    def run(self, target):
        def work():
            try:
                result = target(self)
                self.finish(result=result)
            except ReadCancelled as exc:
                self.finish("cancelled", error=str(exc))
            except Exception as exc:
                self.finish("failed", error=f"{type(exc).__name__}: {exc}")
        self.thread = threading.Thread(target=work, name="wiki-read-progress", daemon=True)
        self.thread.start()
