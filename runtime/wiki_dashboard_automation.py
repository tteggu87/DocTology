#!/usr/bin/env python3
"""Opt-in watcher and sequential queue for the loop-owned Wiki Studio.

This module is intentionally independent from ``wiki_dashboard.py`` so the loop
skill remains self-contained and the dashboard can integrate it without making
watching a condition of ordinary read-only connections.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any


class Automation:
    MAX_FILES = 500
    MAX_BYTES = 2_000_000
    STABLE_OBSERVATIONS = 2
    STATUS_QUEUE_LIMIT = 100
    MAX_BATCH_SOURCES = 12
    POLL_SECONDS = 2.0
    TERMINAL = {"completed", "needs_attention", "ignored", "deleted", "superseded"}

    def __init__(self, app, helpers: dict[str, Any]):
        required = {"inside", "workflow", "snapshot", "process_alive"}
        missing = required - set(helpers)
        if missing:
            raise ValueError("automation helpers are incomplete")
        self.app = app
        self.inside = helpers["inside"]
        self.workflow = helpers["workflow"]
        self.snapshot_helper = helpers["snapshot"]
        self.process_alive = helpers["process_alive"]
        self.root: Path | None = None
        self.mode = "project"
        self.config: dict[str, Any] = self._default_config(None)
        self.baseline: dict[str, Any] = {"known": {}, "observations": {}}
        self.queue: list[dict[str, Any]] = []
        self.last_error: str | None = None
        self.checked_at: float | None = None
        self._state_error: str | None = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()

    @staticmethod
    def _default_config(root: Path | None) -> dict[str, Any]:
        return {
            "enabled": False,
            "autoRun": False,
            "sourcePath": str((root / "raw").resolve()) if root else "",
            "generation": 0,
        }

    def _state_dir(self) -> Path:
        if not self.root:
            raise ValueError("No wiki workspace is connected.")
        return self.inside(self.root, "state/dashboard_automation")

    def _state_path(self) -> Path:
        return self._state_dir() / "state.json"

    def _lock_path(self) -> Path:
        return self._state_dir() / ".lock"

    @staticmethod
    def _read_object(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("state must be an object")
        return value

    def _apply_state(self, state: dict[str, Any]) -> None:
        config = state.get("config", {})
        baseline = state.get("baseline", {})
        queue = state.get("queue", [])
        if not isinstance(config, dict) or not isinstance(baseline, dict) or not isinstance(queue, list):
            raise ValueError("state fields are invalid")
        known = baseline.get("known", {})
        observations = baseline.get("observations", {})
        if not isinstance(known, dict) or not isinstance(observations, dict):
            raise ValueError("baseline fields are invalid")
        if not all(isinstance(item, dict) and isinstance(item.get("id"), str) for item in queue):
            raise ValueError("queue entries are invalid")
        default = self._default_config(self.root)
        default.update({key: config[key] for key in ("enabled", "autoRun", "sourcePath", "generation") if key in config})
        if not isinstance(default["enabled"], bool) or not isinstance(default["autoRun"], bool):
            raise ValueError("configuration flags are invalid")
        if not isinstance(default["sourcePath"], str):
            raise ValueError("source path is invalid")
        if (not isinstance(default["generation"], int) or isinstance(default["generation"], bool)
                or default["generation"] < 0):
            raise ValueError("configuration generation is invalid")
        self.config = default
        self.baseline = {"known": known, "observations": observations}
        self.queue = queue
        self.last_error = state.get("lastError") if isinstance(state.get("lastError"), str) else None
        self.checked_at = state.get("checkedAt") if isinstance(state.get("checkedAt"), (int, float)) else None

    def _state_payload(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "config": self.config,
            "baseline": self.baseline,
            "queue": self.queue,
            "lastError": self.last_error,
            "checkedAt": self.checked_at,
        }

    def _reload(self) -> None:
        if not self.root or self.mode == "project":
            return
        path = self._state_path()
        if not path.is_file():
            self.config = self._default_config(self.root)
            self.baseline = {"known": {}, "observations": {}}
            self.queue = []
            self.last_error = None
            self.checked_at = None
            self._state_error = None
            return
        try:
            self._apply_state(self._read_object(path))
            self._state_error = None
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self._state_error = "Automation state is unreadable; it was not overwritten."
            self.last_error = self._state_error

    def _persist(self) -> None:
        if self.mode == "project" or not self.root:
            return
        if self._state_error:
            raise ValueError(self._state_error)
        self.workflow.write_json(self._state_path(), self._state_payload())

    def load(self, root, mode) -> dict[str, Any]:
        """Restore state for a connection without creating or changing target files."""
        with self.app.lock:
            self.root = Path(root).expanduser().resolve() if root else None
            self.mode = mode
            self.config = self._default_config(self.root)
            self.baseline = {"known": {}, "observations": {}}
            self.queue = []
            self.last_error = None
            self.checked_at = None
            self._state_error = None
            if self.root and mode != "project":
                self._reload()
                self._recover_in_memory()
            elif mode == "project":
                self.last_error = "Automation is disabled in read-only project mode."
            return self.status()

    def _source_path(self) -> Path:
        return Path(self.config["sourcePath"]).expanduser().resolve()

    def _validate_source_path(self, raw: Any) -> Path:
        if not self.root:
            raise ValueError("No wiki workspace is connected.")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("sourcePath must be an absolute folder path.")
        candidate_input = Path(raw).expanduser()
        if not candidate_input.is_absolute():
            raise ValueError("sourcePath must be an absolute folder path.")
        if candidate_input.is_symlink():
            raise ValueError("A symlink cannot be used as the watched folder.")
        candidate = candidate_input.resolve()
        if not candidate.is_dir():
            raise ValueError("The watched folder does not exist.")
        root = self.root.resolve()
        raw_root = (root / "raw").resolve()
        watched_imports = (raw_root / "inbox" / "watched").resolve()
        if candidate == raw_root or candidate.is_relative_to(raw_root):
            if candidate == watched_imports or candidate.is_relative_to(watched_imports):
                raise ValueError("The dashboard's generated watched-import folder cannot watch itself.")
            return candidate
        forbidden = [(root / name).resolve() for name in ("wiki", "state", ".agents")]
        if candidate == root or candidate in root.parents:
            raise ValueError("The watched folder cannot contain the target workspace.")
        if candidate.is_relative_to(root):
            raise ValueError("Only the target raw folder or an independent external folder may be watched.")
        if any(candidate == item or candidate in item.parents or item.is_relative_to(candidate) for item in forbidden):
            raise ValueError("The watched folder overlaps generated wiki, state, or skill files.")
        return candidate

    def _acquire_automation_claim(self):
        claim = self.workflow.acquire_refresh_claim(
            self._lock_path(), f"dashboard-automation-{os.getpid()}", blocking=False
        )
        if claim is None:
            raise ValueError("Another dashboard is updating this automation queue.")
        return claim

    def configure(self, body) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise ValueError("Automation configuration must be an object.")
        with self.app.lock:
            if self.mode == "project":
                self.last_error = "Automation is disabled in read-only project mode."
                return self.status()
            for key in body:
                if key not in {"enabled", "autoRun", "sourcePath", "includeExisting"}:
                    raise ValueError("Unsupported automation configuration field.")
            for key in ("enabled", "autoRun", "includeExisting"):
                if key in body and not isinstance(body[key], bool):
                    raise ValueError(f"{key} must be true or false.")
            claim = self._acquire_automation_claim()
            try:
                self._reload()
                if self._state_error:
                    raise ValueError(self._state_error)
                source = self._validate_source_path(body.get("sourcePath", self.config["sourcePath"]))
                source_changed = str(source) != self.config["sourcePath"]
                was_enabled = self.config["enabled"]
                enabled = body.get("enabled", self.config["enabled"])
                auto_run = body.get("autoRun", self.config["autoRun"])
                include_existing = body.get("includeExisting", False)
                generation = self.config.get("generation", 0) + int(source_changed)
                self.config = {
                    "enabled": enabled, "autoRun": auto_run, "sourcePath": str(source),
                    "generation": generation,
                }
                if source_changed:
                    self.baseline = {"known": {}, "observations": {}}
                self.last_error = None
                if enabled and not include_existing and (source_changed or not self.baseline["known"] or not was_enabled):
                    scan, errors, complete = self._scan(source)
                    if complete:
                        self.baseline = {
                            "known": {
                                relative: {
                                    "hash": row["hash"], "size": row["size"], "mtimeNs": row["mtimeNs"],
                                    "present": True, "source": self._internal_source(source, relative),
                                }
                                for relative, row in scan.items() if not row.get("oversize")
                            },
                            "observations": {},
                        }
                    if errors:
                        self.last_error = " ".join(errors)
                self.checked_at = time.time()
                self._persist()
            finally:
                self.workflow.release_refresh_claim(claim)
        return self.status()

    @staticmethod
    def _hash_bytes(data: bytes) -> str:
        return "sha256:" + hashlib.sha256(data).hexdigest()

    @staticmethod
    def _safe_title(text: str, fallback: str) -> str:
        match = re.search(r"^#\s+(.+)$", text, re.M)
        value = match.group(1).strip() if match else fallback
        value = re.sub(r"[\x00-\x1f\x7f]+", " ", value).strip()
        return value[:200] or fallback[:200]

    @staticmethod
    def _clean_reason(value: str) -> str:
        return re.sub(r"[\x00-\x1f\x7f]+", " ", value).strip()[:400]

    def _scan(self, source_root: Path) -> tuple[dict[str, dict[str, Any]], list[str], bool]:
        rows: dict[str, dict[str, Any]] = {}
        errors: list[str] = []
        entries = 0
        symlinks = 0
        oversize = 0
        try:
            for current, dirs, names in os.walk(source_root, followlinks=False):
                current_path = Path(current)
                kept = []
                for name in dirs:
                    path = current_path / name
                    if name.startswith(".") or path.is_symlink():
                        symlinks += int(path.is_symlink())
                        continue
                    if path == (self.root / "raw" / "inbox" / "watched").resolve():
                        continue
                    kept.append(name)
                dirs[:] = kept
                for name in names:
                    path = current_path / name
                    if name.startswith(".") or path.is_symlink() or path.suffix.lower() != ".md":
                        symlinks += int(path.is_symlink())
                        continue
                    entries += 1
                    if entries > self.MAX_FILES:
                        return {}, [f"Scan limit exceeded: more than {self.MAX_FILES} Markdown files."], False
                    try:
                        before = path.stat()
                        if before.st_size > self.MAX_BYTES:
                            oversize += 1
                            relative = path.relative_to(source_root).as_posix()
                            rows[relative] = {"oversize": True, "size": before.st_size, "mtimeNs": before.st_mtime_ns}
                            continue
                        data = path.read_bytes()
                        after = path.stat()
                        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                            continue
                        relative = path.relative_to(source_root).as_posix()
                        rows[relative] = {
                            "hash": self._hash_bytes(data), "size": len(data), "mtimeNs": after.st_mtime_ns,
                            "data": data,
                        }
                    except OSError:
                        errors.append("A watched Markdown file could not be read.")
        except OSError:
            return {}, ["The watched folder could not be scanned."], False
        if oversize:
            errors.append(f"{oversize} Markdown file(s) exceed the {self.MAX_BYTES} byte limit.")
        if symlinks:
            errors.append(f"{symlinks} symlink entry or entries were ignored.")
        return rows, errors, True

    def _internal_source(self, source_root: Path, relative: str) -> str | None:
        if not self.root:
            return None
        raw_root = (self.root / "raw").resolve()
        if source_root == raw_root or source_root.is_relative_to(raw_root):
            return (source_root / relative).relative_to(self.root.resolve()).as_posix()
        return None

    @staticmethod
    def _queue_key(source: str, content_hash: str) -> str:
        return source + "\0" + content_hash

    def _find_key(self, key: str) -> dict[str, Any] | None:
        return next((item for item in self.queue if item.get("_key") == key), None)

    def _supersede_pending(self, source: str, content_hash: str, now: float) -> None:
        for item in self.queue:
            if (item.get("source") == source and item.get("status") == "pending"
                    and item.get("_contentHash") != content_hash):
                item["status"] = "superseded"
                item["reason"] = "A newer stable version was queued before this version started."
                item["updatedAt"] = now
                item["endedAt"] = now

    def _enqueue(self, source: str, origin: str, content_hash: str, *, change: str,
                 title: str, run_requested: bool, status: str = "pending", reason: str | None = None,
                 watched_path: str | None = None, instruction: str | None = None,
                 watch_generation: int | None = None, watch_source_path: str | None = None) -> dict[str, Any]:
        key = self._queue_key(source, content_hash)
        existing = self._find_key(key)
        now = time.time()
        if existing:
            if existing.get("status") == "pending":
                if run_requested:
                    existing["_runRequested"] = True
                if origin == "conversation":
                    existing.update({"origin": "conversation", "change": "conversation", "title": title[:200]})
                    if instruction:
                        existing["_instruction"] = instruction
                existing["updatedAt"] = now
            return existing
        if status == "pending":
            self._supersede_pending(source, content_hash, now)
        item_id = "queue-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
        item = {
            "id": item_id, "source": source, "title": title[:200], "origin": origin[:40],
            "status": status, "change": change, "createdAt": now, "updatedAt": now,
            "targets": [], "_key": key, "_contentHash": content_hash,
            "_runRequested": bool(run_requested),
        }
        if reason:
            item["reason"] = self._clean_reason(reason)
        if watched_path:
            item["_watchedPath"] = watched_path
        if instruction:
            item["_instruction"] = instruction
        if watch_generation is not None:
            item["_watchGeneration"] = watch_generation
        if watch_source_path is not None:
            item["_watchSourcePath"] = watch_source_path
        if status in self.TERMINAL:
            item["endedAt"] = now
        self.queue.append(item)
        return item

    @staticmethod
    def _copy_name(relative: str, content_hash: str) -> str:
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(relative).stem).strip(".-") or "source"
        return f"{stem[:80]}-{content_hash.removeprefix('sha256:')[:16]}.md"

    def _copy_external(self, relative: str, data: bytes, content_hash: str) -> str:
        destination_dir = self.inside(self.root, "raw/inbox/watched", ("raw/",))
        destination = destination_dir / self._copy_name(relative, content_hash)
        writer = self.workflow.acquire_refresh_claim(
            self.inside(self.root, "state/dashboard_jobs/.writer.lock"), "automation-import", blocking=False
        )
        if writer is None:
            raise BlockingIOError("The wiki writer is busy; the stable file will be imported later.")
        temporary = None
        try:
            if self._has_live_runner():
                raise BlockingIOError("A live wiki runner appeared; the stable file will be imported later.")
            destination_dir.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if destination.is_file() and self._hash_bytes(destination.read_bytes()) == content_hash:
                    return destination.relative_to(self.root).as_posix()
                destination = destination.with_name(
                    f"{destination.stem}-{content_hash.removeprefix('sha256:')}{destination.suffix}"
                )
            temporary = destination.with_name(destination.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
            with temporary.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if self._hash_bytes(destination.read_bytes()) != content_hash:
                    raise ValueError("A watched import destination collision was detected.")
            return destination.relative_to(self.root).as_posix()
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
            self.workflow.release_refresh_claim(writer)

    def _observe(self, scan: dict[str, dict[str, Any]], source_root: Path) -> None:
        known = self.baseline["known"]
        observations = self.baseline["observations"]
        present = set(scan)
        for relative, row in scan.items():
            if row.get("oversize"):
                observations.pop(relative, None)
                continue
            old = known.get(relative)
            if old and old.get("present", True) and old.get("hash") == row["hash"]:
                observations.pop(relative, None)
                continue
            marker = row["hash"]
            prior = observations.get(relative, {})
            count = int(prior.get("count", 0)) + 1 if prior.get("marker") == marker else 1
            observations[relative] = {"marker": marker, "count": count}
            if count < self.STABLE_OBSERVATIONS:
                continue
            change = "modified" if old and old.get("present", True) else "added"
            source = self._internal_source(source_root, relative)
            try:
                if source is None:
                    source = self._copy_external(relative, row["data"], row["hash"])
                text = row["data"].decode("utf-8", errors="replace")
                self._enqueue(
                    source, "watcher", row["hash"], change=change,
                    title=self._safe_title(text, Path(relative).stem), run_requested=False,
                    watched_path=str(source_root / relative),
                    watch_generation=self.config.get("generation", 0),
                    watch_source_path=self.config.get("sourcePath"),
                )
                known[relative] = {
                    "hash": row["hash"], "size": row["size"], "mtimeNs": row["mtimeNs"],
                    "present": True, "source": source,
                }
                observations.pop(relative, None)
            except BlockingIOError as exc:
                self.last_error = self._clean_reason(str(exc))
        for relative, old in list(known.items()):
            if relative in present or not old.get("present", True):
                continue
            prior = observations.get(relative, {})
            count = int(prior.get("count", 0)) + 1 if prior.get("marker") == "deleted" else 1
            observations[relative] = {"marker": "deleted", "count": count}
            if count < self.STABLE_OBSERVATIONS:
                continue
            source = old.get("source") or str(source_root / relative)
            deletion_hash = old.get("hash", "sha256:unknown") + ":deleted"
            self._enqueue(
                source, "watcher", deletion_hash, change="deleted",
                title=Path(relative).stem, run_requested=False, status="deleted",
                reason="The watched source was deleted; no raw or wiki file was removed.",
                watched_path=str(source_root / relative),
            )
            old["present"] = False
            observations.pop(relative, None)

    def enqueue_source(self, source, origin, content_hash=None, run_requested=False, metadata=None) -> dict[str, Any]:
        with self.app.lock:
            if self.mode == "project":
                raise ValueError("Automation cannot write in read-only project mode.")
            if not isinstance(origin, str) or not origin.strip() or len(origin) > 40:
                raise ValueError("A bounded queue origin is required.")
            if not isinstance(run_requested, bool):
                raise ValueError("run_requested must be true or false.")
            if metadata is not None and not isinstance(metadata, dict):
                raise ValueError("metadata must be an object.")
            path = self.inside(self.root, source, ("raw/",))
            if not path.is_file() or path.is_symlink() or path.suffix.lower() != ".md":
                raise ValueError("The queued source must be an existing Markdown file under raw/.")
            data = path.read_bytes()
            if len(data) > self.MAX_BYTES:
                raise ValueError(f"The queued Markdown file exceeds {self.MAX_BYTES} bytes.")
            actual_hash = self._hash_bytes(data)
            if content_hash is not None and content_hash != actual_hash:
                raise ValueError("The supplied content hash does not match the current raw source.")
            title = (metadata or {}).get("title")
            if title is not None and (not isinstance(title, str) or len(title) > 200):
                raise ValueError("The queue title must be at most 200 characters.")
            instruction = (metadata or {}).get("instruction")
            if instruction is not None and (not isinstance(instruction, str) or not instruction.strip()
                                            or len(instruction) > 4_000):
                raise ValueError("The source-handling instruction must be 1 to 4,000 characters.")
            instruction = instruction.strip() if isinstance(instruction, str) else None
            title = title.strip() if isinstance(title, str) else self._safe_title(
                data.decode("utf-8", errors="replace"), path.stem
            )
            claim = self._acquire_automation_claim()
            try:
                self._reload()
                item = self._enqueue(
                    source, origin.strip(), actual_hash,
                    change="conversation" if origin == "conversation" else "added",
                    title=title or path.stem, run_requested=run_requested, instruction=instruction,
                )
                watched = self._source_path()
                raw_root = (self.root / "raw").resolve()
                if watched.is_relative_to(raw_root) and path.resolve().is_relative_to(watched):
                    relative = path.resolve().relative_to(watched).as_posix()
                    stat = path.stat()
                    self.baseline["known"][relative] = {
                        "hash": actual_hash, "size": len(data), "mtimeNs": stat.st_mtime_ns,
                        "present": True, "source": source,
                    }
                    self.baseline["observations"].pop(relative, None)
                self.checked_at = time.time()
                self._persist()
                result = self._public_item(item)
            finally:
                self.workflow.release_refresh_claim(claim)
        return result

    def _lookup(self, item_id: str) -> dict[str, Any]:
        item = next((row for row in self.queue if row.get("id") == item_id), None)
        if item is None:
            raise ValueError("The automation queue item was not found.")
        return item

    def run_item(self, item_id) -> dict[str, Any]:
        resolved = None
        with self.app.lock:
            if self.mode == "project":
                raise ValueError("Automation cannot run in read-only project mode.")
            claim = self._acquire_automation_claim()
            try:
                self._reload()
                item = self._lookup(item_id)
                if item.get("status") not in {"pending", "needs_attention"}:
                    raise ValueError("Only a pending or review-needed queue item can be run.")
                done, targets = self._verified_done(item)
                if done:
                    now = time.time()
                    item.update({"status": "completed", "targets": targets, "updatedAt": now})
                    item.setdefault("endedAt", now)
                    item["_runRequested"] = False
                    item.pop("reason", None)
                    resolved = self._public_item(item)
                else:
                    if item.get("status") == "needs_attention":
                        if not self._current_hash_matches(item):
                            raise ValueError("The raw source changed; queue its current stable version instead.")
                        if self._job_alive(self._linked_job(item)):
                            raise ValueError("The linked runner is still alive and cannot be retried.")
                        resume = getattr(self.app, "resume_queued_parallel", None)
                        if item.get("jobId") and callable(resume):
                            try:
                                result = resume(item["jobId"], item["source"])
                            except Exception as exc:
                                item["updatedAt"] = time.time()
                                item["reason"] = self._clean_reason(str(exc)) or "Parallel retry could not be resumed."
                                self._persist()
                                raise
                            if result is not None:
                                if not isinstance(result, dict) or not isinstance(result.get("id"), str):
                                    raise ValueError("The dashboard did not return a job id.")
                                now = time.time()
                                item.update({
                                    "status": "running", "jobId": result["id"], "startedAt": now,
                                    "updatedAt": now, "targets": [],
                                })
                                item.pop("endedAt", None)
                                item.pop("reason", None)
                                self._persist()
                                resolved = self._public_item(item)
                            else:
                                item.update({"status": "pending", "targets": []})
                                for key in ("jobId", "startedAt", "endedAt", "reason"):
                                    item.pop(key, None)
                        else:
                            item.update({"status": "pending", "targets": []})
                            for key in ("jobId", "startedAt", "endedAt", "reason"):
                                item.pop(key, None)
                    if resolved is None:
                        item["_runRequested"] = True
                        item["updatedAt"] = time.time()
                self._persist()
            finally:
                self.workflow.release_refresh_claim(claim)
        if resolved is not None:
            return resolved
        self.tick()
        with self.app.lock:
            return self._public_item(self._lookup(item_id))

    def ignore_item(self, item_id) -> dict[str, Any]:
        with self.app.lock:
            if self.mode == "project":
                raise ValueError("Automation cannot write in read-only project mode.")
            claim = self._acquire_automation_claim()
            try:
                self._reload()
                item = self._lookup(item_id)
                if item.get("status") not in {"pending", "needs_attention"}:
                    raise ValueError("Only pending or review-needed items can be ignored.")
                now = time.time()
                item.update({"status": "ignored", "updatedAt": now, "endedAt": now,
                             "reason": "Ignored by explicit request."})
                self._persist()
                return self._public_item(item)
            finally:
                self.workflow.release_refresh_claim(claim)

    def _snapshot_row(self, source: str) -> dict[str, Any] | None:
        if not self.root:
            return None
        try:
            state = self.snapshot_helper(self.root, self.mode)
            return next((row for row in state.get("sources", []) if row.get("id") == source), None)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _current_hash_matches(self, item: dict[str, Any]) -> bool:
        try:
            path = self.inside(self.root, item["source"], ("raw/",))
            return path.is_file() and self._hash_bytes(path.read_bytes()) == item.get("_contentHash")
        except (OSError, ValueError, KeyError):
            return False

    def _linked_job(self, item: dict[str, Any]) -> dict[str, Any] | None:
        job_id = item.get("jobId")
        current = getattr(self.app, "job", None)
        if isinstance(current, dict) and current.get("id") == job_id:
            return current
        if not self.root or not isinstance(job_id, str):
            return None
        try:
            path = self.inside(self.root, f"state/dashboard_jobs/{job_id}.json")
            return self._read_object(path) if path.is_file() else None
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def _verified_done(self, item: dict[str, Any]) -> tuple[bool, list[str]]:
        if not self._current_hash_matches(item):
            return False, []
        row = self._snapshot_row(item.get("source", ""))
        if row and row.get("stage") == "done":
            targets = row.get("references", [])
            return True, sorted({value for value in targets if isinstance(value, str)})
        return False, []

    def _job_alive(self, job: dict[str, Any] | None) -> bool:
        if not job:
            return False
        process = getattr(self.app, "process", None)
        current = getattr(self.app, "job", None)
        if isinstance(current, dict) and current.get("id") == job.get("id") and process is not None:
            try:
                if process.poll() is None:
                    return True
            except (AttributeError, OSError):
                return True
        if job.get("status") not in {"running", "starting", "stopping", "interrupted", "external"}:
            return False
        return bool(self.process_alive(job.get("runnerPid")))

    def _recover_in_memory(self) -> None:
        for item in self.queue:
            status = item.get("status")
            if status in {"completed", "needs_attention"}:
                done, targets = self._verified_done(item)
                if done:
                    if status != "completed":
                        now = time.time()
                        item.update({"status": "completed", "updatedAt": now})
                        item.setdefault("endedAt", now)
                    item["targets"] = targets
                    item.pop("reason", None)
                    continue
                if status == "completed":
                    now = time.time()
                    item.update({
                        "status": "needs_attention", "updatedAt": now,
                        "reason": "The source or completion gates changed after this item was verified.",
                    })
                continue
            if status != "running":
                continue
            done, targets = self._verified_done(item)
            if done:
                now = time.time()
                item.update({"status": "completed", "targets": targets, "updatedAt": now, "endedAt": now})
                item.pop("reason", None)
                continue
            job = self._linked_job(item)
            if self._job_alive(job):
                continue
            now = time.time()
            item.update({
                "status": "needs_attention", "updatedAt": now, "endedAt": now,
                "reason": "The linked execution was interrupted or ended without current completion gates.",
            })

    def _reconcile(self) -> None:
        self._recover_in_memory()
        for item in self.queue:
            if item.get("status") != "running":
                continue
            job = self._linked_job(item)
            if self._job_alive(job):
                continue
            done, targets = self._verified_done(item)
            now = time.time()
            if done:
                item.update({"status": "completed", "targets": targets, "updatedAt": now, "endedAt": now})
                item.pop("reason", None)
            else:
                item.update({
                    "status": "needs_attention", "updatedAt": now, "endedAt": now,
                    "reason": "Execution ended, but the current source has no verified completed wiki run.",
                })

    def _has_live_runner(self) -> bool:
        checker = getattr(self.app, "has_live_runner", None)
        if callable(checker):
            try:
                return bool(checker())
            except (OSError, ValueError, TypeError):
                return True
        process = getattr(self.app, "process", None)
        if process is not None:
            try:
                if process.poll() is None:
                    return True
            except (AttributeError, OSError):
                return True
        job = getattr(self.app, "job", None)
        return bool(isinstance(job, dict)
                    and job.get("status") in {"running", "starting", "stopping", "interrupted", "external"}
                    and self.process_alive(job.get("runnerPid")))

    def _busy(self) -> bool:
        if self._has_live_runner():
            return True
        if getattr(self.app, "claim", None) is not None:
            return True
        process = getattr(self.app, "process", None)
        if process is not None:
            try:
                if process.poll() is None:
                    return True
            except (AttributeError, OSError):
                return True
        # Read-only chats do not own a writer slot or postpone authorized work.
        return any(item.get("status") == "running" for item in self.queue)

    def _auto_eligible(self, item: dict[str, Any]) -> bool:
        if not (self.config.get("enabled") and self.config.get("autoRun")):
            return False
        if item.get("origin") != "watcher":
            return True
        return (item.get("_watchGeneration") == self.config.get("generation")
                and item.get("_watchSourcePath") == self.config.get("sourcePath"))

    def _dispatch(self) -> None:
        if self._busy():
            return
        selected: list[dict[str, Any]] = []
        selected_sources: set[str] = set()
        for item in self.queue:
            if len(selected) >= self.MAX_BATCH_SOURCES:
                break
            if (item.get("status") != "pending"
                    or not (item.get("_runRequested") or self._auto_eligible(item))):
                continue
            source = item.get("source")
            if not isinstance(source, str) or source in selected_sources:
                continue
            if not self._current_hash_matches(item):
                now = time.time()
                item.update({
                    "status": "superseded", "updatedAt": now, "endedAt": now,
                    "reason": "The raw source changed before execution could start.",
                })
                continue
            selected.append(item)
            selected_sources.add(source)
        if not selected:
            return
        now = time.time()
        for item in selected:
            item.update({"status": "running", "startedAt": now, "updatedAt": now})
            item.pop("reason", None)
        self._persist()  # Fail closed: a crash before app.start becomes review-needed, never an automatic retry.
        sources = [item["source"] for item in selected]
        if len(selected) == 1:
            message = (
                "Process exactly the selected Markdown source with llm-wiki-loop coverage_mode=full. "
                "Preserve raw bytes, account for every source unit, use the existing procedure and quality gates, "
                "and do not report completion unless the current source run is verified ready."
            )
            if selected[0].get("_instruction"):
                message += "\n\nTrusted source-handling instruction:\n" + selected[0]["_instruction"]
        else:
            message = (
                "Process exactly the selected Markdown sources as one llm-wiki-loop batch with coverage_mode=full. "
                "Preserve raw bytes, account for every source unit, use the existing procedure and quality gates, "
                "and do not report completion unless every current source run is verified ready."
            )
            instructions = [
                {"source": item["source"], "trusted_source_handling_instruction": item["_instruction"]}
                for item in selected if item.get("_instruction")
            ]
            if instructions:
                message += "\n\nTrusted source-handling instructions by source (JSON):\n" + json.dumps(
                    instructions, ensure_ascii=False, sort_keys=True
                )
        try:
            result = self.app.start(message, sources, "")
            if not isinstance(result, dict) or not isinstance(result.get("id"), str):
                raise ValueError("The dashboard did not return a job id.")
            now = time.time()
            for item in selected:
                item["jobId"] = result["id"]
                item["updatedAt"] = now
        except Exception as exc:
            now = time.time()
            if getattr(exc, "retryable", False):
                for item in selected:
                    item.update({
                        "status": "pending", "updatedAt": now,
                        "reason": "The wiki writer is busy; this authorized item remains pending.",
                    })
                    for key in ("jobId", "startedAt", "endedAt"):
                        item.pop(key, None)
            else:
                for item in selected:
                    item.update({
                        "status": "needs_attention", "updatedAt": now, "endedAt": now,
                        "reason": "The explicitly authorized execution could not be started.",
                    })

    def tick(self) -> dict[str, Any]:
        with self.app.lock:
            if self.mode == "project" or not self.root:
                self.last_error = "Automation is disabled in read-only project mode."
                self.checked_at = time.time()
                return self.status()
            state_path = self._state_path()
            if state_path.is_file():
                self._reload()  # Observe configuration written by another service without first creating a lock.
            if not self.config.get("enabled") and not self.queue:
                self.checked_at = time.time()
                return self.status()
            try:
                claim = self._acquire_automation_claim()
            except ValueError as exc:
                self.last_error = self._clean_reason(str(exc))
                self.checked_at = time.time()
                return self.status()
            try:
                self._reload()
                if self._state_error:
                    return self.status()
                self._reconcile()
                scan_errors: list[str] = []
                if self.config.get("enabled"):
                    source = self._validate_source_path(self.config["sourcePath"])
                    scan, scan_errors, complete = self._scan(source)
                    if complete:
                        self._observe(scan, source)
                self.last_error = " ".join(scan_errors) if scan_errors else self.last_error if self.last_error and "writer is busy" in self.last_error else None
                self._dispatch()
                self.checked_at = time.time()
                self._persist()
            except (OSError, ValueError, TypeError) as exc:
                self.last_error = self._clean_reason(str(exc)) or "Automation tick failed safely."
                self.checked_at = time.time()
                try:
                    self._persist()
                except (OSError, ValueError, TypeError):
                    pass
            finally:
                self.workflow.release_refresh_claim(claim)
            return self.status()

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(self.POLL_SECONDS)

    def start_worker(self) -> None:
        with self.app.lock:
            if self._worker and self._worker.is_alive():
                return
            self._stop.clear()
            self._worker = threading.Thread(target=self._worker_loop, name="wiki-dashboard-automation", daemon=True)
            self._worker.start()

    def stop_worker(self) -> None:
        self._stop.set()
        worker = self._worker
        if worker and worker is not threading.current_thread():
            worker.join(timeout=self.POLL_SECONDS + 1)
        self._worker = None

    @staticmethod
    def _public_item(item: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "id", "source", "title", "origin", "status", "change", "reason", "jobId",
            "createdAt", "updatedAt", "startedAt", "endedAt", "targets",
        )
        return {key: item[key] for key in keys if key in item}

    def status(self, offset=0) -> dict[str, Any]:
        if (not isinstance(offset, int) or isinstance(offset, bool)
                or offset < 0 or offset > 1_000_000):
            raise ValueError("Queue offset must be an integer from 0 to 1,000,000.")
        with self.app.lock:
            available = bool(self.root and self.mode != "project")
            ordered = sorted(self.queue, key=lambda item: (item.get("updatedAt", 0), item.get("id", "")), reverse=True)
            total = len(ordered)
            effective_offset = offset
            if total and effective_offset >= total:
                effective_offset = ((total - 1) // self.STATUS_QUEUE_LIMIT) * self.STATUS_QUEUE_LIMIT
            public_queue = [self._public_item(item) for item in
                            ordered[effective_offset:effective_offset + self.STATUS_QUEUE_LIMIT]]
            counts = {
                "pending": sum(item.get("status") == "pending" for item in self.queue),
                "running": sum(item.get("status") == "running" for item in self.queue),
                "completed": sum(item.get("status") == "completed" for item in self.queue),
                "needsAttention": sum(item.get("status") == "needs_attention" for item in self.queue),
            }
            return {
                "available": available,
                "enabled": bool(available and self.config.get("enabled")),
                "autoRun": bool(available and self.config.get("autoRun")),
                "sourcePath": self.config.get("sourcePath", ""),
                "checkedAt": self.checked_at,
                "lastError": self.last_error,
                "queue": public_queue,
                "queuePage": {
                    "offset": effective_offset,
                    "limit": self.STATUS_QUEUE_LIMIT,
                    "total": total,
                },
                "counts": counts,
                "limits": {
                    "maxFiles": self.MAX_FILES,
                    "maxBytes": self.MAX_BYTES,
                    "stableObservations": self.STABLE_OBSERVATIONS,
                    "responseQueueEntries": self.STATUS_QUEUE_LIMIT,
                    "pollSeconds": self.POLL_SECONDS,
                },
            }
